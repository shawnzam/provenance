# search

Search across your database and notes.

```bash
provenance search QUERY
```

Searches both the SQLite database (people, meetings, actions, documents) and your notes files via FTS5 full-text search.

---

## Examples

```bash
# Default: DB + regex match on notes files
provenance search "AI governance"

# Pipe results to AI
provenance search "Wharton faculty" | provenance ai "who should I reach out to first?"
```

---

## Search modes

Notes are indexed into an SQLite FTS5 virtual table using Porter stemming. Three modes are available:

| Mode | Flag | Behavior |
|---|---|---|
| `regex` | (default) | Python grep across all notes files — exact names and IDs |
| `lex` | `--lex` | BM25 full-text ranking via FTS5 — best for topics and keywords |
| `semantic` | `--sem` | Also uses FTS5 (same index, different ranking) |

---

## Options

| Flag | Short | Description |
|---|---|---|
| `--lex` | | BM25 full-text search via FTS5 |
| `--sem` | | Semantic-style search via FTS5 |
| `--topk` | `-k` | Max results for lex/sem (default 10) |
| `--context` | `-C` | Lines of context around each match (default 2) |
| `--json` | | Output as JSON |

---

## index

Build or refresh the FTS5 search index:

```bash
provenance index
```

The index updates automatically whenever Provenance writes a notes file. Run this manually after bulk imports or if search returns stale results.

---

## doctor

Check that everything is configured and working:

```bash
provenance doctor
```

Checks: database exists and is accessible, FTS5 index is populated, `PROVENANCE_OPENAI_API_KEY` is set, AI provider and model are configured.
