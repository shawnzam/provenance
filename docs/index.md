# Provenance

**Local-first personal CRM and memory tool for professional use.**

Track people, meetings, notes, and action items. Surface context on demand through an AI-assisted REPL, a structured CLI, or directly from Claude Desktop via MCP.

Runs entirely on your machine. No accounts, no cloud sync.

---

## Install

```bash
uv tool install git+https://github.com/shawnzam/provenance
```

Then initialize your data directory:

```bash
provenance init
```

Set up `~/.provenance/.env` with your API key (see [Setup](setup.md)), then verify:

```bash
provenance doctor
```

---

## Quick start

```bash
# Launch the interactive REPL — the main interface
provenance chat

# Or use the structured CLI directly
provenance people add "Sarah Chen" --role "Director of AI" --org "Penn Medicine"
provenance meetings add --title "Intro with Sarah" --date 2026-03-10 --attendees sarah-chen
provenance actions add "Send Sarah the AI governance framework" --due 2026-03-15
provenance ask "what do I know about Sarah?"
```

---

## How it works

```
┌─────────────────────────────────────────────────────┐
│  User Interfaces                                    │
│                                                     │
│  provenance chat    provenance <cmd>   Claude       │
│  (REPL)             (structured CLI)  Desktop (MCP) │
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

**REPL** — the primary interface. Type questions naturally, use prefix shorthands (`@name`, `#meeting`, `+action`), or issue slash commands (`/recap`, `/focus`). See [REPL](repl.md).

**MCP** — Provenance exposes all tools to Claude Desktop over stdio. No network, no auth. See [Claude Desktop](mcp.md).

**`--check-text` / `-ct`** — proofread any free-text argument before it's saved: `provenance -ct people add "Tom Sevr" --context "Met hom last week"`.
