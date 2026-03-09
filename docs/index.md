# Provenance

**Local-first personal CRM and memory tool for professional use.**

Track people, meetings, notes, and action items. Surface context on demand through Claude Desktop, an interactive REPL, or a structured CLI.

Runs entirely on your machine. No accounts, no cloud sync.

---

## Quick start — Claude Desktop

**No OpenAI key needed.** Connect Provenance to Claude Desktop and use Claude as your interface.

**1. Install**

```bash
uv tool install git+https://github.com/shawnzam/provenance
provenance init
```

**2. Add to `~/Library/Application Support/Claude/claude_desktop_config.json`**

```json
{
  "mcpServers": {
    "provenance": {
      "command": "/Users/yourname/.local/bin/uv",
      "args": ["--directory", "/path/to/provenance", "run", "python", "mcp_server.py"]
    }
  }
}
```

Replace `/Users/yourname/.local/bin/uv` with `$(which uv)` and `/path/to/provenance` with your clone path.

**3. Restart Claude Desktop and ask anything**

```
What meetings do I have this week?
Prep me for my 2pm with Alex
Add an action item to follow up with Jamie by Friday
What did we discuss about AI governance last month?
```

See [Claude Desktop](mcp.md) for the full guide.

---

## Standalone CLI + REPL

Prefer a terminal interface? Use the interactive REPL with an OpenAI key:

```bash
provenance chat
```

Or structured commands:

```bash
provenance people add "Alex Rivera" --role "VP of Engineering" --org "Acme Corp"
provenance meetings add --title "Intro with Alex" --date 2026-03-10 --attendees alex-rivera
provenance ask "what do I know about Alex?"
```

See [REPL](repl.md) and [Setup](setup.md) for configuration.

---

## How it works

```
┌─────────────────────────────────────────────────────┐
│  User Interfaces                                    │
│                                                     │
│  Claude Desktop (MCP)   provenance chat   CLI cmds  │
│  ← no OpenAI needed     ← needs OpenAI             │
└──────────┬────────────────┬──────────────┬──────────┘
           │                │              │
           └────────────────┼──────────────┘
                            │
              ┌─────────────▼─────────────┐
              │  Tool layer (cli/tools.py) │
              │  people · meetings         │
              │  actions · search · notes  │
              └──────────┬────────────────┘
                         │
            ┌────────────▼──────────────┐
            │  Local storage             │
            │  SQLite (Django ORM)       │
            │  FTS5 full-text index      │
            │  Markdown notes files      │
            └────────────────────────────┘
```

All data lives in `~/.provenance/`. The code repo contains no personal data.

---

## Key concepts

**Slugs** — CLI-friendly IDs auto-generated from names. `"Alex Rivera"` → `alex-rivera`. Use slugs wherever a command asks for an ID.

**Piping** — every command has `--json` output. Chain with `|` and feed into `provenance ai` for on-demand synthesis.

**MCP** — Provenance exposes all tools to Claude Desktop over stdio. No network, no auth, no OpenAI key needed. See [Claude Desktop](mcp.md).

**REPL** — standalone interactive interface powered by OpenAI. Type questions naturally, use prefix shorthands (`@name`, `#meeting`, `+action`), or issue slash commands (`/recap`, `/focus`). See [REPL](repl.md).

**`--check-text` / `-ct`** — proofread any free-text argument before it's saved: `provenance -ct people add "Tom Sevr" --context "Met hom last week"`.

**Wiki-links** — any note, meeting file, or document can link to another using `[[slug]]` syntax. When Claude reads a note via MCP, it follows links automatically (up to 2 hops) and embeds the linked content inline. Supported targets: meetings, documents, freeform notes, and people. See [Claude Desktop](mcp.md#wiki-links).
