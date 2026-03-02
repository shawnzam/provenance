# Dependencies

## Runtime

| Package | Purpose |
|---------|---------|
| [Django](https://djangoproject.com) | ORM, SQLite management, FTS5 virtual table, admin web UI |
| [Typer](https://typer.tiangolo.com) | CLI framework built on Click |
| [openai](https://github.com/openai/openai-python) | OpenAI API client (isolated to `ai/openai_provider.py`) |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | Loads `~/.provenance/.env` at startup |
| [Rich](https://rich.readthedocs.io) | Terminal formatting, tables, colour output |
| [python-slugify](https://github.com/un33k/python-slugify) | Auto-generates URL-safe slugs from names/titles |
| [PyMuPDF](https://pymupdf.readthedocs.io) | PDF → Markdown conversion for `docs import` |
| [prompt-toolkit](https://python-prompt-toolkit.readthedocs.io) | REPL input handling, history, key bindings |
| [mcp](https://github.com/modelcontextprotocol/python-sdk) | MCP server protocol (Claude Desktop integration) |

## Dev

| Package | Purpose |
|---------|---------|
| [pytest](https://pytest.org) | Test runner |
| [pytest-django](https://pytest-django.readthedocs.io) | Django integration for pytest |
| [MkDocs](https://www.mkdocs.org) | Documentation site generator |
| [mkdocs-material](https://squidfunk.github.io/mkdocs-material/) | Material Design theme for MkDocs |

## Optional external binaries

| Tool | Install | Purpose |
|------|---------|---------|
| [icalBuddy](https://hasseg.org/icalBuddy/) | `brew install ical-buddy` | macOS calendar access (Outlook/Exchange) |

---

## Design decisions

**Why Django for a local CLI tool?**
Django's ORM gives a production-quality relational data layer with zero configuration. Migrations are built in, the admin UI is free, and queryset filtering is expressive. SQLite is the database — no server required.

**Why is OpenAI isolated to one file?**
`import openai` appears only in `ai/openai_provider.py`. All other code uses the `AIProvider` abstract base class from `ai/base.py`. This makes swapping or adding providers (Anthropic, Ollama, local models) a one-file change.

**Why FTS5 instead of a vector search library?**
FTS5 is built into SQLite — zero additional dependencies, no binary to install, no cloud service. Porter stemming + BM25 ranking handles the vast majority of notes search queries well. True vector search (sqlite-vec) is planned for a future release.

**Why separate `~/.provenance` from the code repo?**
Personal data (notes, database, API keys) never touches the code repo. The tool can be installed from GitHub without carrying any personal information. `PROVENANCE_HOME` can be overridden to put data anywhere.
