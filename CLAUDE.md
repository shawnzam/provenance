# Provenance — Project Brief

## What This Is

Provenance is a local-first personal CRM and memory tool built for professional use — specifically to support onboarding into a senior IT/AI leadership role. It helps the user track people, meetings, notes, and action items, and surfaces relevant context on demand through structured queries and semantic search.

The name reflects knowing where things came from — context, relationships, decisions, all with a clear record of origin.

This is a personal productivity tool, not a product. It runs entirely on the user's machine. No accounts, no cloud sync, no multi-user concerns.

## Stack

| Layer            | Choice                                                         |
|------------------|----------------------------------------------------------------|
| Language         | Python 3.11+                                                   |
| CLI              | Typer                                                          |
| Web + ORM        | Django + SQLite                                                |
| Notes            | Markdown files on disk                                         |
| Search           | SQLite FTS5 with Porter stemming — built-in, no external deps  |
| AI provider      | OpenAI first (pluggable)                                       |
| Package mgmt     | uv                                                             |

## Folder Structure

```
provenance/
├── CLAUDE.md
├── pyproject.toml
├── .env.example
├── manage.py
├── provenance/          # Django project config
│   ├── settings.py
│   └── urls.py
├── core/                # Django app — models
│   ├── models/
│   │   ├── person.py
│   │   ├── meeting.py
│   │   ├── action_item.py
│   │   └── topic.py
│   └── admin.py
├── cli/                 # Typer CLI
│   ├── main.py
│   └── commands/
│       ├── people.py
│       ├── meetings.py
│       ├── actions.py
│       ├── search.py
│       └── ai.py
├── ai/                  # Provider abstraction
│   ├── base.py
│   ├── openai_provider.py
│   └── registry.py
├── notes/meetings/      # One .md per meeting
├── data/                # SQLite DB (gitignored)
└── tests/
```

## Data Models

- **Person** — name, slug, role, org, email, relationship_context, notes, tags
- **Meeting** — date, title, attendees (M2M Person), summary, notes_file path, tags
- **ActionItem** — description, due_date, status, person (FK), meeting (FK), tags
- **Topic** — name, slug, description

## CLI Design

```bash
# Structured queries
provenance people list
provenance people tom-sever
provenance people tom-sever meetings
provenance meetings --person "Tom Sever" --after 2026-03-01
provenance actions --status open

# Add data
provenance people add "Tom Sever" --role "Professor" --org "Wharton"
provenance meetings add --title "Intro with Tom" --date 2026-03-10 --attendees tom-sever

# Semantic search (delegates to ck)
provenance search "times I spoke about AI ethics"

# AI enrichment — reads stdin, instruction as argument
provenance ai "write a bio based on what I know"

# Chainable
provenance search "AI ethics" | provenance ai "find news articles to challenge my thinking"
provenance people tom-sever meetings | provenance ai "write a bio before our next meeting"
provenance actions --status open | provenance ai "prioritize these and suggest a weekly plan"
```

Pipe protocol: `provenance ai` reads context from stdin, instruction from argument. Constructs a system + user message and sends to the configured provider.

## AI Provider Architecture

```python
# ai/base.py — abstract, no provider imports here
class AIProvider(ABC):
    def complete(self, system: str, user: str) -> str: ...

# ai/openai_provider.py — only file that imports openai
class OpenAIProvider(AIProvider): ...

# ai/registry.py — reads PROVENANCE_AI_PROVIDER env var
def get_provider() -> AIProvider: ...
```

Adding Anthropic, Ollama etc. later = one new file.

## Environment Variables

```
PROVENANCE_OPENAI_API_KEY=sk-...
PROVENANCE_AI_PROVIDER=openai
PROVENANCE_AI_MODEL=gpt-4o
DJANGO_SECRET_KEY=...
DJANGO_DEBUG=True
```

## First Milestone — Build in Order

1. **Scaffold** — uv project, Django + core app, all models + migrations, admin registered, runserver works
2. **CLI skeleton** — Typer root app, all command groups stubbed, `provenance --help` works
3. **People commands** — list, add, show, show meetings
4. **Meetings commands** — list (filterable), add (creates DB record + blank .md file), show
5. **AI pipe** — AIProvider base, OpenAIProvider, `provenance ai` reads stdin, test chains work
6. **Search** — `provenance search` queries SQLite FTS5; `provenance doctor` checks DB, FTS5 index, API key

## Design Constraints

- No cloud, no accounts. `.env` is gitignored.
- CLI is primary. Django admin is the web UI — don't build a custom dashboard yet.
- `--json` on all commands enables piping.
- No `import openai` outside `openai_provider.py`.
- Slugs are the CLI-friendly IDs, auto-generated from names/titles.
- Missing config = loud, actionable error. Not a stack trace.
- Don't reimplement ck. Wire to it and move on.

## Done When

```bash
provenance people add "Tom Sever" --role "Professor of Marketing" --org "Wharton"
provenance meetings add --title "Intro with Tom" --date 2026-03-10 --attendees tom-sever
provenance people tom-sever meetings --json | provenance ai "write a short bio before our next meeting"
# → OpenAI returns a useful paragraph
```
