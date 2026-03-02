# Setup

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.11+ | Managed by `uv` — you don't need to install it separately |
| [`uv`](https://docs.astral.sh/uv/getting-started/installation/) | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| [Claude Desktop](https://claude.ai/download) | Optional — MCP integration (no OpenAI key needed) |
| OpenAI API key | Optional — only needed for the standalone REPL and `ask`/`ai` commands |
| [`icalBuddy`](https://hasseg.org/icalBuddy/) | Optional — macOS only, for Outlook/Exchange calendar access |

---

## Install

### From GitHub (recommended)

```bash
uv tool install git+https://github.com/shawnzam/provenance
```

This installs the `provenance` command globally. You can run it from anywhere.

### Local development

```bash
git clone https://github.com/shawnzam/provenance
cd provenance
uv sync
uv run provenance --help
```

---

## Initialize

Create the `~/.provenance/` data directory:

```bash
provenance init
```

This creates:

```
~/.provenance/
├── notes/
│   ├── meetings/
│   ├── docs/
│   └── context.md      ← personal context always visible to the AI
└── provenance.db       ← SQLite database (created automatically)
```

Safe to run multiple times — skips anything that already exists. The database is created on first run.

!!! tip "Custom location"
    Set `PROVENANCE_HOME` to override the default `~/.provenance`:
    ```bash
    export PROVENANCE_HOME=/path/to/your/data
    ```

---

## Configure

Create `~/.provenance/.env`:

```bash
cp /path/to/provenance/.env.example ~/.provenance/.env
```

Or create it directly:

```ini title="~/.provenance/.env"
# Django internals — generate any long random string (required)
DJANGO_SECRET_KEY=change-me-to-a-long-random-string
DJANGO_DEBUG=True

# OpenAI — only needed for the standalone REPL, provenance ask, and provenance ai
# Not required if you use Claude Desktop (MCP)
PROVENANCE_OPENAI_API_KEY=sk-...
PROVENANCE_AI_PROVIDER=openai
PROVENANCE_AI_MODEL=gpt-4o
PROVENANCE_PROOFREAD_AI_MODEL=gpt-4o-mini   # optional, defaults to PROVENANCE_AI_MODEL
```

---

## Verify

```bash
provenance doctor
```

Expected output:

```
✓ Database: /Users/you/.provenance/provenance.db
✓ Notes dir: /Users/you/.provenance/notes
✓ FTS5 index: ok
✓ PROVENANCE_OPENAI_API_KEY is set
✓ AI provider: openai
✓ AI model: gpt-4o

All checks passed.
```

---

## Migrations

If you upgrade Provenance and the database schema has changed, run:

```bash
provenance migrate
```

This is also run automatically by `provenance init` if the database doesn't exist yet.

---

## icalBuddy (optional — macOS calendar)

Install to enable calendar access via `get_calendar_events`:

```bash
brew install ical-buddy
```

Then add your Outlook account under **System Settings → Internet Accounts** (Exchange). macOS Calendar syncs it locally; Provenance reads from there — no credentials stored.

See [Calendar](calendar.md) for usage.

---

## Django admin (optional)

A full web UI for browsing and editing data:

```bash
cd /path/to/provenance
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

Open [http://localhost:8000/admin/](http://localhost:8000/admin/).

!!! note
    `manage.py` is only available in the development clone, not via `uv tool install`.
    For the installed version, use the CLI or MCP for all data access.
