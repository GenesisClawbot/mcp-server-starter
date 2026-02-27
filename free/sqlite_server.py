#!/usr/bin/env python3
"""
SQLite MCP Server Template - Phase 2 Product

Provides SQLite database access via MCP tools.
Execute queries, create/drop tables, insert rows, and introspect schema.

Tools:
  - execute_query(sql, db_path): Run any SQL query, returns rows as list of dicts
  - create_table(table_name, schema, db_path): Create a table from schema string
  - insert_row(table_name, data, db_path): Insert a row (data as JSON string)
  - get_schema(db_path): Get all table names and their column definitions
  - list_tables(db_path): List all table names in the database
  - drop_table(table_name, db_path): Drop a table (with confirmation check)

Database: defaults to "data.db" in current directory

Usage:
  python3 mcp_sqlite_template.py
"""

import asyncio
import json
import os
import sqlite3
import re
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Initialize server with metadata for MCP clients
server = Server("sqlite-mcp-server")
server.name = "sqlite-mcp-server"
server.version = "0.1.0"


def _validate_table_name(name: str) -> bool:
    """Validate table name to prevent SQL injection."""
    # Allow only alphanumeric, underscore, and letters
    # Must start with letter or underscore
    return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name))


def _validate_db_path(db_path: str) -> bool:
    """Validate database path for basic safety."""
    # Prevent directory traversal and absolute paths outside workspace
    # Allow relative paths and names in current directory
    if db_path.startswith('/'):
        return False
    if '..' in db_path:
        return False
    return True


def _get_db_connection(db_path: str):
    """Open a connection to the SQLite database.
    
    Returns tuple: (conn, error_msg) where error_msg is None if successful.
    """
    if not _validate_db_path(db_path):
        return None, f"Invalid db_path: {db_path}"
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        return conn, None
    except sqlite3.Error as e:
        return None, f"Database connection failed: {str(e)}"


def _execute_query(sql: str, db_path: str = "data.db") -> dict:
    """Execute a SQL query and return results.
    
    Args:
        sql: SQL query string (SELECT, INSERT, UPDATE, DELETE, etc.)
        db_path: Path to database file (default: "data.db")
    
    Returns:
        Dict with 'rows' (list of dicts) and optional 'error' key
    """
    conn, error = _get_db_connection(db_path)
    if error:
        return {"error": error}
    
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        
        # For SELECT queries, fetch and return rows
        if sql.strip().upper().startswith('SELECT'):
            rows = cursor.fetchall()
            # Convert Row objects to dicts
            result_rows = [dict(row) for row in rows]
            conn.close()
            return {"rows": result_rows}
        
        # For INSERT, UPDATE, DELETE, commit and return affected rows
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return {"rows": [], "affected_rows": affected}
    
    except sqlite3.Error as e:
        conn.close()
        return {"error": f"Query execution failed: {str(e)}"}


def _create_table(table_name: str, schema: str, db_path: str = "data.db") -> dict:
    """Create a new table.
    
    Args:
        table_name: Name of the table to create
        schema: Column definitions (e.g., "id INTEGER PRIMARY KEY, name TEXT, age INTEGER")
        db_path: Path to database file (default: "data.db")
    
    Returns:
        Dict with 'success' and optional 'error' key
    """
    if not _validate_table_name(table_name):
        return {"error": f"Invalid table name: {table_name}. Use alphanumeric and underscore only."}
    
    conn, error = _get_db_connection(db_path)
    if error:
        return {"error": error}
    
    try:
        cursor = conn.cursor()
        # Use IF NOT EXISTS to avoid errors if table already exists
        sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({schema})"
        cursor.execute(sql)
        conn.commit()
        conn.close()
        return {"success": True, "message": f"Table '{table_name}' created successfully"}
    
    except sqlite3.Error as e:
        conn.close()
        return {"error": f"Table creation failed: {str(e)}"}


def _insert_row(table_name: str, data: str, db_path: str = "data.db") -> dict:
    """Insert a row into a table.
    
    Args:
        table_name: Name of the table
        data: JSON string of key/value pairs (e.g., '{"name": "Alice", "age": 30}')
        db_path: Path to database file (default: "data.db")
    
    Returns:
        Dict with 'success' and optional 'error' key
    """
    if not _validate_table_name(table_name):
        return {"error": f"Invalid table name: {table_name}"}
    
    try:
        data_dict = json.loads(data)
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in data: {str(e)}"}
    
    conn, error = _get_db_connection(db_path)
    if error:
        return {"error": error}
    
    try:
        cursor = conn.cursor()
        columns = list(data_dict.keys())
        values = list(data_dict.values())
        
        # Build parameterized INSERT to prevent injection
        placeholders = ','.join(['?' for _ in columns])
        col_names = ','.join(columns)
        sql = f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})"
        
        cursor.execute(sql, values)
        conn.commit()
        conn.close()
        return {"success": True, "message": f"Row inserted into '{table_name}'"}
    
    except sqlite3.Error as e:
        conn.close()
        return {"error": f"Insert failed: {str(e)}"}


def _get_schema(db_path: str = "data.db") -> dict:
    """Get schema information for all tables in the database.
    
    Args:
        db_path: Path to database file (default: "data.db")
    
    Returns:
        Dict with 'schema' (list of table info) and optional 'error' key
    """
    conn, error = _get_db_connection(db_path)
    if error:
        return {"error": error}
    
    try:
        cursor = conn.cursor()
        # Get all tables from sqlite_master
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        schema_info = []
        for (table_name,) in tables:
            # Get column info for each table
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            col_defs = []
            for col_id, col_name, col_type, not_null, default_val, pk in columns:
                col_defs.append({
                    "name": col_name,
                    "type": col_type,
                    "not_null": bool(not_null),
                    "primary_key": bool(pk)
                })
            
            schema_info.append({
                "table": table_name,
                "columns": col_defs
            })
        
        conn.close()
        return {"schema": schema_info}
    
    except sqlite3.Error as e:
        conn.close()
        return {"error": f"Schema retrieval failed: {str(e)}"}


def _list_tables(db_path: str = "data.db") -> dict:
    """List all table names in the database.
    
    Args:
        db_path: Path to database file (default: "data.db")
    
    Returns:
        Dict with 'tables' (list of names) and optional 'error' key
    """
    conn, error = _get_db_connection(db_path)
    if error:
        return {"error": error}
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        return {"tables": tables}
    
    except sqlite3.Error as e:
        conn.close()
        return {"error": f"Table listing failed: {str(e)}"}


def _drop_table(table_name: str, db_path: str = "data.db") -> dict:
    """Drop a table from the database.
    
    Args:
        table_name: Name of the table to drop
        db_path: Path to database file (default: "data.db")
    
    Returns:
        Dict with 'success' and optional 'error' key
    """
    if not _validate_table_name(table_name):
        return {"error": f"Invalid table name: {table_name}"}
    
    conn, error = _get_db_connection(db_path)
    if error:
        return {"error": error}
    
    try:
        cursor = conn.cursor()
        # Check if table exists before dropping (confirmation check)
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        if not cursor.fetchone():
            conn.close()
            return {"error": f"Table '{table_name}' does not exist"}
        
        # Drop the table
        sql = f"DROP TABLE {table_name}"
        cursor.execute(sql)
        conn.commit()
        conn.close()
        return {"success": True, "message": f"Table '{table_name}' dropped successfully"}
    
    except sqlite3.Error as e:
        conn.close()
        return {"error": f"Drop failed: {str(e)}"}


# Register MCP tools
# Each tool is defined with name, description, and input schema

@server.list_tools()
async def list_tools():
    """List all available tools for the SQLite MCP server."""
    return [
        Tool(
            name="execute_query",
            description="Execute a SQL query (SELECT, INSERT, UPDATE, DELETE). Returns rows as list of dicts for SELECT queries.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "SQL query to execute"
                    },
                    "db_path": {
                        "type": "string",
                        "description": "Path to database file (default: data.db)",
                        "default": "data.db"
                    }
                },
                "required": ["sql"]
            }
        ),
        Tool(
            name="create_table",
            description="Create a new table with specified column definitions",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "Name of the table to create"
                    },
                    "schema": {
                        "type": "string",
                        "description": "Column definitions (e.g., 'id INTEGER PRIMARY KEY, name TEXT, age INTEGER')"
                    },
                    "db_path": {
                        "type": "string",
                        "description": "Path to database file (default: data.db)",
                        "default": "data.db"
                    }
                },
                "required": ["table_name", "schema"]
            }
        ),
        Tool(
            name="insert_row",
            description="Insert a row into a table",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "Name of the table"
                    },
                    "data": {
                        "type": "string",
                        "description": "JSON string of key/value pairs (e.g., '{\"name\": \"Alice\", \"age\": 30}')"
                    },
                    "db_path": {
                        "type": "string",
                        "description": "Path to database file (default: data.db)",
                        "default": "data.db"
                    }
                },
                "required": ["table_name", "data"]
            }
        ),
        Tool(
            name="get_schema",
            description="Get complete schema information for all tables in the database",
            inputSchema={
                "type": "object",
                "properties": {
                    "db_path": {
                        "type": "string",
                        "description": "Path to database file (default: data.db)",
                        "default": "data.db"
                    }
                }
            }
        ),
        Tool(
            name="list_tables",
            description="List all table names in the database",
            inputSchema={
                "type": "object",
                "properties": {
                    "db_path": {
                        "type": "string",
                        "description": "Path to database file (default: data.db)",
                        "default": "data.db"
                    }
                }
            }
        ),
        Tool(
            name="drop_table",
            description="Drop a table from the database (checks existence first)",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "Name of the table to drop"
                    },
                    "db_path": {
                        "type": "string",
                        "description": "Path to database file (default: data.db)",
                        "default": "data.db"
                    }
                },
                "required": ["table_name"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Route tool calls to appropriate handler functions."""
    try:
        if name == "execute_query":
            result = _execute_query(
                arguments.get("sql"),
                arguments.get("db_path", "data.db")
            )
        elif name == "create_table":
            result = _create_table(
                arguments.get("table_name"),
                arguments.get("schema"),
                arguments.get("db_path", "data.db")
            )
        elif name == "insert_row":
            result = _insert_row(
                arguments.get("table_name"),
                arguments.get("data"),
                arguments.get("db_path", "data.db")
            )
        elif name == "get_schema":
            result = _get_schema(arguments.get("db_path", "data.db"))
        elif name == "list_tables":
            result = _list_tables(arguments.get("db_path", "data.db"))
        elif name == "drop_table":
            result = _drop_table(
                arguments.get("table_name"),
                arguments.get("db_path", "data.db")
            )
        else:
            result = {"error": f"Unknown tool: {name}"}
        
        return [TextContent(type="text", text=json.dumps(result))]
    
    except Exception as e:
        # Catch any unexpected errors and return as JSON
        error_result = {"error": f"Tool execution error: {str(e)}"}
        return [TextContent(type="text", text=json.dumps(error_result))]


async def main():
    """Main entry point. Set up MCP stdio transport and run server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
