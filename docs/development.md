# Development

## Project layout

```
provenance/                    # Code repo — no personal data
├── CLAUDE.md
├── README.md
├── pyproject.toml             # deps, entry point, build config
├── mkdocs.yml                 # docs config
├── manage.py                  # Django management (dev only)
├── mcp_server.py              # MCP stdio server for Claude Desktop
│
├── provenance/                # Django project config
│   ├── settings.py
│   └── urls.py
│
├── core/                      # Django app — data models
│   ├── models/
│   │   ├── person.py
│   │   ├── meeting.py
│   │   ├── action_item.py
│   │   ├── document.py
│   │   └── reading_item.py
│   ├── migrations/
│   └── admin.py
│
├── cli/                       # Typer CLI
│   ├── main.py                # entry point, Django setup, command registration
│   ├── paths.py               # single source of truth: PROVENANCE_HOME, NOTES_DIR, etc.
│   ├── arg_normalizer.py      # rewrites sys.argv before Typer sees it
│   ├── setup_django.py        # configures Django settings module
│   ├── indexer.py             # FTS5 index management
│   ├── tools.py               # all agent/MCP tool implementations
│   └── commands/
│       ├── people.py
│       ├── meetings.py
│       ├── actions.py
│       ├── docs.py
│       ├── reading.py
│       ├── search.py          # search + doctor + index_notes_cmd
│       ├── capture.py         # note, jot, remember, extract
│       ├── ai.py              # ai + ask + proof + agent loop
│       ├── chat.py            # interactive REPL
│       └── init.py            # first-run setup (init + migrate)
│
├── ai/                        # Provider abstraction
│   ├── base.py                # AIProvider ABC
│   ├── openai_provider.py     # only file that imports openai
│   ├── registry.py            # reads PROVENANCE_AI_PROVIDER env var
│   └── text_checker.py        # batch proofreading for --check-text
│
└── docs/                      # MkDocs source

~/.provenance/                 # Personal data — not in repo
├── .env
├── provenance.db
├── settings.json
├── .chat_history
└── notes/
    ├── context.md
    ├── meetings/
    └── docs/
```

---

## Running locally

```bash
# Install dependencies (including dev)
uv sync --dev

# Apply migrations
uv run python manage.py migrate

# Run any command
uv run provenance --help
uv run provenance people list

# Django admin
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

---

## Serving docs

```bash
uv run mkdocs serve
```

Opens at [http://localhost:8000](http://localhost:8000). Live-reloads on changes.

```bash
uv run mkdocs build   # output in site/
```

---

## Running tests

```bash
uv run pytest
uv run pytest -v
uv run pytest tests/test_people.py
```

Tests use `pytest-django`. The test database is created and destroyed automatically.

---

## Adding a new AI provider

1. Create `ai/<name>_provider.py` subclassing `AIProvider`:

```python
from ai.base import AIProvider

class MyProvider(AIProvider):
    def complete(self, system: str, user: str, model: str | None = None) -> str:
        # call your API here
        ...
```

2. Register it in `ai/registry.py`:

```python
from ai.my_provider import MyProvider

_PROVIDERS = {
    "openai": lambda: OpenAIProvider(),
    "myprovider": lambda: MyProvider(),
}
```

3. Set in `~/.provenance/.env`:

```ini
PROVENANCE_AI_PROVIDER=myprovider
```

---

## arg_normalizer

`cli/arg_normalizer.py` rewrites `sys.argv` before Typer processes it:

- **`--check-text` / `-ct`** — strips the flag and sets a global enable state; `ai/text_checker.py` is called inside each command on prose fields
- **Slug shorthand** — `provenance people tom-sever` → `provenance people show tom-sever`; `provenance people tom-sever meetings` → `provenance people meetings tom-sever`
- **Natural language fallback** — `provenance who is Tom Sever?` (2+ words, no flags) → `provenance ask who is Tom Sever?`

---

## paths.py

`cli/paths.py` is the single source of truth for all data paths:

```python
PROVENANCE_HOME  # ~/.provenance (or $PROVENANCE_HOME)
NOTES_DIR        # ~/.provenance/notes
DB_PATH          # ~/.provenance/provenance.db
ENV_FILE         # ~/.provenance/.env
```

All code that needs these paths imports from here. Setting `PROVENANCE_HOME` env var moves the entire data directory.

---

## FTS5 search index

Notes files are indexed into an SQLite FTS5 virtual table (`notes_fts`) using Porter stemming.

- `cli/indexer.py` — `index_file(path)` for incremental updates, `index_notes()` for full rebuild
- The index is updated automatically after every write operation
- Rebuild manually: `provenance index`

The search implementation uses Django's cursor directly with `%s` parameterized queries (not `?` — Django's cursor wrapper uses Python's `%` operator).
