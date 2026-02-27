#!/usr/bin/env python3
"""
Web Search MCP Server Template - Phase 2 Product

Provides web search capabilities via MCP tools.
Zero authentication required - works out of the box using DuckDuckGo lite HTML scraping.
Optional: Brave API if BRAVE_API_KEY environment variable is set.

Tools:
  - search_web(query, max_results): Search the web, returns list of {title, url, snippet}
  - fetch_page(url, max_chars): Fetch and extract plain text from a webpage
  - get_search_engine(): Returns which search engine is active ("brave" or "duckduckgo")

Features:
  - Primary: DuckDuckGo lite HTML scraping (no API key required)
  - Optional: Brave API fallback (requires BRAVE_API_KEY env var)
  - Graceful degradation if DuckDuckGo is blocked
  - 10 second timeout on all requests
  - JSON-serializable output

Usage:
  python3 mcp_websearch_template.py
"""

import asyncio
import json
import os
import re
import requests
from bs4 import BeautifulSoup
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Initialize server with metadata for MCP clients
server = Server("websearch-mcp-server")
server.name = "websearch-mcp-server"
server.version = "0.1.0"

# Configuration
DUCKDUCKGO_URL = "https://html.duckduckgo.com/html/"
BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")
REQUEST_TIMEOUT = 10
DEFAULT_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"


def get_active_search_engine() -> str:
    """Return which search engine is currently active."""
    if BRAVE_API_KEY:
        return "brave"
    return "duckduckgo"


def search_duckduckgo(query: str, max_results: int = 5) -> list:
    """
    Search using DuckDuckGo lite HTML scraping (no API key required).
    Returns list of {title, url, snippet} dicts.
    """
    try:
        headers = {"User-Agent": DEFAULT_USER_AGENT}
        params = {"q": query, "kl": "uk-en"}
        
        response = requests.get(
            DUCKDUCKGO_URL,
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        results = []
        
        # Find all result divs with class "result__body"
        result_bodies = soup.find_all("div", class_="result__body")
        
        for body in result_bodies[:max_results]:
            try:
                # Extract title from .result__title a
                title_elem = body.find("a", class_="result__title")
                title = title_elem.get_text(strip=True) if title_elem else "No title"
                
                # Extract URL from .result__url
                url_elem = body.find("a", class_="result__url")
                url = url_elem.get_text(strip=True) if url_elem else ""
                
                # Extract snippet from .result__snippet
                snippet_elem = body.find("a", class_="result__snippet")
                snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                
                if url:  # Only add if we got a URL
                    results.append({
                        "title": title,
                        "url": url,
                        "snippet": snippet
                    })
            except Exception:
                # Skip malformed results
                continue
        
        return results
    
    except requests.exceptions.Timeout:
        return []
    except requests.exceptions.RequestException:
        # DuckDuckGo may block or be unavailable
        return []
    except Exception:
        return []


def search_brave(query: str, max_results: int = 5) -> list:
    """
    Search using Brave API (requires BRAVE_API_KEY environment variable).
    Returns list of {title, url, snippet} dicts.
    """
    try:
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": BRAVE_API_KEY
        }
        params = {"q": query, "count": max_results}
        
        response = requests.get(
            BRAVE_API_URL,
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        
        data = response.json()
        results = []
        
        for result in data.get("web", [])[:max_results]:
            results.append({
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "snippet": result.get("description", "")
            })
        
        return results
    
    except requests.exceptions.Timeout:
        return []
    except requests.exceptions.RequestException:
        return []
    except Exception:
        return []


@server.list_tools()
async def list_tools():
    """Register available MCP tools."""
    return [
        Tool(
            name="search_web",
            description="Search the web for information. Uses Brave API if available, falls back to DuckDuckGo.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query string"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 5)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="fetch_page",
            description="Fetch and extract plain text content from a webpage.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL of the webpage to fetch"
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "Maximum characters to return (default: 3000)",
                        "default": 3000
                    }
                },
                "required": ["url"]
            }
        ),
        Tool(
            name="get_search_engine",
            description="Get the active search engine (brave or duckduckgo).",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Handle tool calls."""
    
    if name == "search_web":
        query = arguments.get("query", "")
        max_results = arguments.get("max_results", 5)
        
        if not query:
            return [TextContent(type="text", text="Error: query parameter is required")]
        
        # Try Brave API first if available
        if BRAVE_API_KEY:
            results = search_brave(query, max_results)
            if results:
                return [TextContent(
                    type="text",
                    text=json.dumps(results, indent=2)
                )]
        
        # Fall back to DuckDuckGo
        results = search_duckduckgo(query, max_results)
        if results:
            return [TextContent(
                type="text",
                text=json.dumps(results, indent=2)
            )]
        
        # If both fail, return empty with message
        return [TextContent(
            type="text",
            text=json.dumps({
                "results": [],
                "message": "No results found or search service unavailable"
            }, indent=2)
        )]
    
    elif name == "fetch_page":
        url = arguments.get("url", "")
        max_chars = arguments.get("max_chars", 3000)
        
        if not url:
            return [TextContent(type="text", text="Error: url parameter is required")]
        
        try:
            headers = {"User-Agent": DEFAULT_USER_AGENT}
            response = requests.get(
                url,
                headers=headers,
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            
            # Parse HTML and extract text
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Get text and clean up whitespace
            text = soup.get_text()
            text = re.sub(r'\s+', ' ', text).strip()
            
            # Truncate to max_chars
            if len(text) > max_chars:
                text = text[:max_chars] + "..."
            
            return [TextContent(type="text", text=text)]
        
        except requests.exceptions.Timeout:
            return [TextContent(type="text", text=f"Error: Request timeout fetching {url}")]
        except requests.exceptions.RequestException as e:
            return [TextContent(type="text", text=f"Error: Failed to fetch {url}: {str(e)}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    elif name == "get_search_engine":
        engine = get_active_search_engine()
        return [TextContent(
            type="text",
            text=json.dumps({
                "engine": engine,
                "brave_api_key_set": bool(BRAVE_API_KEY)
            }, indent=2)
        )]
    
    else:
        return [TextContent(type="text", text=f"Error: Unknown tool {name}")]


async def main():
    """Main async entry point using correct MCP transport pattern."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
