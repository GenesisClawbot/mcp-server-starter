#!/usr/bin/env python3
"""
System Shell MCP Server Template - Phase 2 Product

Provides filesystem and shell access via MCP tools.
Execute commands, read/write files, list directories, and inspect environment.

Tools:
  - execute_command(command, working_dir, timeout): Run shell command via subprocess
  - read_file(path): Read file contents (max 100KB)
  - write_file(path, content): Write/overwrite file
  - list_directory(path): List files and dirs with metadata
  - get_environment(): Return current dir, Python version, OS info

Security: Designed for local development use - execute_command runs with the same
permissions as the server process. Do not expose this server on untrusted networks.

Usage:
  python3 mcp_shell_template.py
"""

import asyncio
import json
import os
import subprocess
import sys
import platform
from pathlib import Path
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Initialize server with metadata for MCP clients
server = Server("shell-mcp-server")
server.name = "shell-mcp-server"
server.version = "0.1.0"


def _validate_path(path: str) -> bool:
    """Validate that a path exists and is within reasonable bounds.
    
    Returns False for absolute paths outside workspace and obvious traversal attempts.
    """
    if not path:
        return False
    if path.startswith('/'):
        return False
    if '..' in path:
        return False
    return True


def _execute_command(command: str, working_dir: str = ".", timeout: int = 30) -> dict:
    """Execute a shell command and return stdout, stderr, and return code.
    
    Args:
        command: Shell command to execute
        working_dir: Working directory for command execution (default: ".")
        timeout: Command timeout in seconds (default: 30)
    
    Returns:
        Dict with keys: stdout (str), stderr (str), returncode (int)
    
    Security note: Runs with the same permissions as the server process.
    """
    if not _validate_path(working_dir) and working_dir != ".":
        if not os.path.exists(working_dir):
            return {
                "stdout": "",
                "stderr": f"Invalid working_dir: {working_dir}",
                "returncode": 1
            }
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": f"Command timed out after {timeout} seconds",
            "returncode": 124
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": f"Command execution failed: {str(e)}",
            "returncode": 1
        }


def _read_file(path: str, max_size: int = 102400) -> dict:
    """Read file contents.
    
    Args:
        path: File path to read
        max_size: Maximum file size to read (default: 100KB)
    
    Returns:
        Dict with 'content' key (str) or 'error' key
    
    Security note: Enforces maximum read size to prevent memory issues.
    """
    if not _validate_path(path):
        return {"error": f"Invalid path: {path}"}
    
    try:
        file_path = Path(path)
        
        # Check if file exists
        if not file_path.exists():
            return {"error": f"File not found: {path}"}
        
        # Check if it's a file (not directory)
        if not file_path.is_file():
            return {"error": f"Path is not a file: {path}"}
        
        # Check file size
        file_size = file_path.stat().st_size
        if file_size > max_size:
            return {"error": f"File too large: {file_size} bytes (max {max_size})"}
        
        # Read and return content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return {"content": content}
    
    except UnicodeDecodeError:
        return {"error": f"File is not valid UTF-8 text: {path}"}
    except Exception as e:
        return {"error": f"Read failed: {str(e)}"}


def _write_file(path: str, content: str) -> dict:
    """Write content to file (creates or overwrites).
    
    Args:
        path: File path to write
        content: Content to write (str)
    
    Returns:
        Dict with 'success' key (bool) and optional 'error' key
    
    Security note: Creates parent directories if they don't exist.
    """
    if not _validate_path(path):
        return {"success": False, "error": f"Invalid path: {path}"}
    
    try:
        file_path = Path(path)
        
        # Create parent directories if needed
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return {"success": True, "path": str(file_path.absolute())}
    
    except Exception as e:
        return {"success": False, "error": f"Write failed: {str(e)}"}


def _list_directory(path: str = ".") -> dict:
    """List contents of a directory.
    
    Args:
        path: Directory path (default: ".")
    
    Returns:
        Dict with 'entries' key (list of dicts with name, type, size) or 'error' key
    """
    if path != "." and not _validate_path(path):
        if not os.path.exists(path):
            return {"error": f"Invalid path: {path}"}
    
    try:
        dir_path = Path(path)
        
        if not dir_path.exists():
            return {"error": f"Directory not found: {path}"}
        
        if not dir_path.is_dir():
            return {"error": f"Path is not a directory: {path}"}
        
        entries = []
        for item in dir_path.iterdir():
            try:
                stat = item.stat()
                entries.append({
                    "name": item.name,
                    "type": "dir" if item.is_dir() else "file",
                    "size": stat.st_size if item.is_file() else None,
                    "modified": stat.st_mtime
                })
            except (OSError, PermissionError):
                # Skip files we can't stat (permissions, etc)
                entries.append({
                    "name": item.name,
                    "type": "dir" if item.is_dir() else "file",
                    "size": None,
                    "modified": None,
                    "error": "Permission denied or inaccessible"
                })
        
        return {
            "path": str(dir_path.absolute()),
            "entries": sorted(entries, key=lambda x: x["name"])
        }
    
    except Exception as e:
        return {"error": f"List failed: {str(e)}"}


def _get_environment() -> dict:
    """Return current environment information.
    
    Returns:
        Dict with cwd, python_version, os_name, os_version, sys_platform
    """
    return {
        "cwd": os.getcwd(),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "os_name": platform.system(),
        "os_version": platform.release(),
        "platform": sys.platform,
        "arch": platform.machine()
    }


# Register tools with MCP server

@server.list_tools()
async def list_tools():
    """List all available tools."""
    return [
        Tool(
            name="execute_command",
            description="Execute a shell command",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute"
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "Working directory for command (default: .)",
                        "default": "."
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Command timeout in seconds (default: 30)",
                        "default": 30
                    }
                },
                "required": ["command"]
            }
        ),
        Tool(
            name="read_file",
            description="Read file contents (max 100KB)",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path to read"
                    }
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="write_file",
            description="Write content to file (creates or overwrites)",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path to write"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write"
                    }
                },
                "required": ["path", "content"]
            }
        ),
        Tool(
            name="list_directory",
            description="List directory contents with metadata",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path (default: .)",
                        "default": "."
                    }
                }
            }
        ),
        Tool(
            name="get_environment",
            description="Get current working directory, Python version, and OS info",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Call a tool by name with arguments."""
    
    if name == "execute_command":
        result = _execute_command(
            command=arguments.get("command", ""),
            working_dir=arguments.get("working_dir", "."),
            timeout=arguments.get("timeout", 30)
        )
        return [TextContent(type="text", text=json.dumps(result))]
    
    elif name == "read_file":
        result = _read_file(path=arguments.get("path", ""))
        return [TextContent(type="text", text=json.dumps(result))]
    
    elif name == "write_file":
        result = _write_file(
            path=arguments.get("path", ""),
            content=arguments.get("content", "")
        )
        return [TextContent(type="text", text=json.dumps(result))]
    
    elif name == "list_directory":
        result = _list_directory(path=arguments.get("path", "."))
        return [TextContent(type="text", text=json.dumps(result))]
    
    elif name == "get_environment":
        result = _get_environment()
        return [TextContent(type="text", text=json.dumps(result))]
    
    else:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]


async def main():
    """Main entry point using correct MCP 1.26.0 pattern."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
