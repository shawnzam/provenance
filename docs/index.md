# Provenance

**Local-first personal CRM and memory tool for professional use.**

Track people, meetings, notes, and action items. Surface context on demand through Claude Desktop, an interactive REPL, or a structured CLI.

Runs entirely on your machine. No accounts, no cloud sync.

---

## Install

```bash
uv tool install git+https://github.com/shawnzam/provenance
provenance init
```

See [Setup](setup.md) for configuration details.

---

## Two ways to use it

### Claude Desktop (recommended — no OpenAI key required)

Connect Provenance to Claude Desktop via MCP. Use Claude as your interface — ask questions, log meetings, search your notes — all through a conversation.

```
What meetings do I have this week?
Prep me for my 2pm with Erik
Add an action item to follow up with Roger by Friday
What did we discuss about AI governance last month?
```

Claude handles the natural language. Provenance handles the data. See [Claude Desktop](mcp.md).

### Standalone CLI + REPL

Use Provenance on its own with an OpenAI key. The interactive REPL is the primary standalone interface:

```bash
provenance chat
```

Or use structured commands directly:

```bash
provenance people add "Sarah Chen" --role "Director of AI" --org "Penn Medicine"
provenance meetings add --title "Intro with Sarah" --date 2026-03-10 --attendees sarah-chen
provenance ask "what do I know about Sarah?"
```

See [REPL](repl.md) for the full guide.

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

**Slugs** — CLI-friendly IDs auto-generated from names. `"Sarah Chen"` → `sarah-chen`. Use slugs wherever a command asks for an ID.

**Piping** — every command has `--json` output. Chain with `|` and feed into `provenance ai` for on-demand synthesis.

**MCP** — Provenance exposes all tools to Claude Desktop over stdio. No network, no auth, no OpenAI key needed. See [Claude Desktop](mcp.md).

**REPL** — standalone interactive interface powered by OpenAI. Type questions naturally, use prefix shorthands (`@name`, `#meeting`, `+action`), or issue slash commands (`/recap`, `/focus`). See [REPL](repl.md).

**`--check-text` / `-ct`** — proofread any free-text argument before it's saved: `provenance -ct people add "Tom Sevr" --context "Met hom last week"`.
