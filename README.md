# mcp-server-starter

Eight working MCP server templates for Claude Desktop. Copy one, fill in the .env, run it.

I built these while wiring Claude into my actual dev workflow. Most MCP examples show you the minimal tool definition and stop there. These include the parts that actually matter in practice: proper stdio transport setup, retry logic, structured error returns, rate limiting, and MCP-compliant metadata Claude can reason about.

---

## Free templates (3)

No accounts, no API keys, no Docker. These work offline.

### sqlite-csv

Connect Claude to a local SQLite database or CSV files. Ask questions in plain English, get SQL back, inspect schemas, import CSV data on the fly.

```bash
cd free
python sqlite_server.py
```

Works offline. Zero external dependencies beyond the standard library + pandas. The CSV import is the bit I use most - drop a data export in, ask Claude what's in it.

---

### web-search

Search the web and fetch readable text from any URL. DuckDuckGo out of the box, no API key. Optional Brave Search upgrade path in the config if you want it.

```bash
cd free
python websearch_server.py
```

Results are cached locally so you don't hit the same URL twice in a session. The readability extraction strips nav and ads and gives Claude actual article content to work with.

---

### system-shell

Run shell commands, check CPU/memory/disk, tail logs, list processes. Whitelist-based by default so you control exactly what Claude can execute.

```bash
cd free
python shell_server.py
```

Whitelist mode is on by default. There's an unrestricted mode for local dev if you want it - documented in the template README. Leave the whitelist on in any environment you care about.

---

## Paid templates (5)

These follow the same patterns as the free ones. Same error handling, same setup structure, same code style. They just need API tokens for external services.

**GitHub** - PR reviewer, diff summarisation, issue and repo search. Needs a GitHub personal access token.

**Notion** - Read and write to your Notion workspace. Page search, database queries, block creation. Needs a Notion integration token.

**Slack** - Send messages, read channel history, search conversations. Needs a Slack bot token with the right scopes.

**Memory** - Persistent memory store using local SQLite. No subscription, no external service. Lets Claude remember things across conversations by writing to and querying a structured local store.

**Linear** - Issue tracker integration. Create issues, list sprint work, update statuses, pull team summaries. Needs a Linear API key.

---

## How the transport works

All eight templates use the same stdio server pattern. This is what actually running an MCP server looks like with the current SDK (`mcp 1.26.0`):

```python
from mcp.server.stdio import stdio_server

async def main():
    async with stdio_server() as (r, w):
        await server.run(r, w, server.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

The `stdio_server()` context manager handles the transport lifecycle. You get reader and writer streams, pass them to `server.run()`, done. Claude Desktop communicates over stdin/stdout, which is why there's no port configuration.

---

## Setup (Claude Desktop)

Add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "sqlite": {
      "command": "python",
      "args": ["/path/to/free/sqlite_server.py"]
    }
  }
}
```

Restart Claude Desktop. The tools show up automatically.

Full config examples are in each template's README.

---

## Get the full pack

All 8 templates (3 free + 5 paid) for a one-time £19.

- Stripe: [Buy for £19](https://buy.stripe.com/9B6dR300j8tL6A7aNQ9ws00)
- Gumroad: https://buy.stripe.com/9B6dR300j8tL6A7aNQ9ws00 (Gumroad listing coming soon)

No subscription. You get the files, you keep them.

---

## Questions

Open an issue. I check them.
