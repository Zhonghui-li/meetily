# Meetily — Research Lab Fork

> This is a customized fork of [Meetily](https://github.com/Zackriya-Solutions/meeting-minutes) (Privacy-First AI Meeting Assistant) extended with Claude MCP integration and local automation for research lab use.
>
> For installation, architecture, and original features, see the [upstream repository](https://github.com/Zackriya-Solutions/meeting-minutes).

---

## What We Added

### 1. MCP Server — Claude Desktop Integration

`mcp_server/server.py` connects Claude Desktop directly to Meetily's local SQLite database via the [Model Context Protocol](https://modelcontextprotocol.io/). Claude can query all meeting history without any cloud dependency.

**Available tools:**

| Tool | Description |
|------|-------------|
| `list_meetings` | List all recorded meetings |
| `get_meeting_summary` | Get structured summary; auto-falls back to raw transcript when Groq summary unavailable |
| `get_meeting_transcript` | Retrieve raw transcript text directly |
| `search_meetings` | Keyword search across transcripts and summaries |
| `get_action_items` | Extract action items across meetings, optionally filtered by person |

**Setup — add to `~/Library/Application Support/Claude/claude_desktop_config.json`:**

```json
{
  "mcpServers": {
    "meetily": {
      "command": "/path/to/meetily/backend/venv/bin/python3",
      "args": ["/path/to/meetily/mcp_server/server.py"]
    }
  }
}
```

Then ask Claude: *"List my recent meetings"* or *"What action items came out of last week's meeting?"*

---

### 2. One-Click Startup (`start_meeting.sh`)

Automates the full macOS setup before a meeting:

1. Switches system audio output to Multi-Output Device (speakers + BlackHole 2ch)
2. Starts the FastAPI backend if not already running
3. Opens the Meetily app

```bash
bash start_meeting.sh
```

---

## Roadmap: Proactive Meeting Agent

Currently the system only answers questions you remember to ask. The next phase adds a **Proactive Agent** that automatically runs after each meeting to:

- Detect overdue action items by cross-referencing meeting history via semantic vector search
- Surface conflicting decisions across meetings
- Push findings without requiring manual queries

This will use a **LangGraph StateGraph** pipeline with **hybrid BM25+FAISS retrieval**, replacing the current keyword-only SQL search with semantic understanding — building on the architecture from our [Agentic RAG project](https://github.com/Zhonghui-li/agentic-rag).

---

## License

MIT — same as the upstream project.
