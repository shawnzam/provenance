# search

Search across your database and notes.

```bash
provenance search QUERY
```

Searches both the SQLite database (people, meetings, actions, documents) and your notes files. Notes search supports multiple backends — from simple regex matching to AI-powered hybrid search via [qmd](https://github.com/tobi/qmd).

---

## Examples

```bash
# Default: DB + regex match on notes files
provenance search "AI governance"

# Hybrid AI search — vector + BM25 + LLM reranking (requires qmd)
provenance search --qmd "discussions about trust and ethics"

# BM25 full-text ranking
provenance search --lex "budget planning"

# Pipe results to AI
provenance search "partner contacts" | provenance ai "who should I reach out to first?"
```

---

## Search modes

Notes search supports four modes. The first three use the built-in SQLite FTS5 index. The fourth uses [qmd](https://github.com/tobi/qmd), an external local search engine.

| Mode | Flag | Behavior |
|---|---|---|
| `regex` | (default) | Python grep across all notes files — exact names and IDs |
| `lex` | `--lex` | BM25 full-text ranking via FTS5 — best for topics and keywords |
| `semantic` | `--sem` | Also uses FTS5 (same index, different ranking) |
| `qmd` | `--qmd` | Hybrid AI search — vector embeddings + BM25 + LLM reranking. Best quality for complex or intent-based queries. Requires [qmd setup](#qmd-setup). |

---

## Options

| Flag | Short | Description |
|---|---|---|
| `--lex` | | BM25 full-text search via FTS5 |
| `--sem` | | Semantic-style search via FTS5 |
| `--qmd` | | Hybrid AI search via qmd (vector + BM25 + LLM reranking) |
| `--db` | | Search database only, skip notes |
| `--notes` | | Search notes only, skip database |
| `--topk` | `-k` | Max results for lex/sem (default 10) |
| `--context` | `-C` | Lines of context around each match (default 2) |
| `--json` | | Output as JSON |

---

## qmd setup

[qmd](https://github.com/tobi/qmd) is an optional local search engine that adds vector similarity and LLM-powered reranking to notes search. Everything runs on-device — no cloud, no API keys.

### Install

```bash
npm install -g @tobilu/qmd    # requires Node.js >= 22
```

### Index your notes

```bash
qmd collection add ~/.provenance/notes --name provenance-notes
qmd embed
```

First run downloads ~2GB of GGUF models to `~/.cache/qmd/models/`:

- Embedding model (gemma 300M) — vector generation
- Query expansion model (1.7B) — semantic query rewriting
- Reranker model (qwen3 0.6B) — relevance scoring

### Automatic re-indexing

Provenance automatically triggers `qmd update && qmd embed` in the background whenever a note is created or updated (via CLI, MCP, or REPL). No manual re-indexing needed for normal use.

For bulk imports or manual rebuilds:

```bash
qmd update && qmd embed
```

### qmd as MCP server (Claude Code)

qmd exposes its own MCP server, giving Claude Code direct access to search your notes without going through Provenance. Add to your Claude Code project config:

```json
{
  "mcpServers": {
    "qmd": {
      "type": "stdio",
      "command": "qmd",
      "args": ["mcp"]
    }
  }
}
```

This exposes six tools: `qmd_search` (BM25), `qmd_vector_search` (semantic), `qmd_deep_search` (hybrid with reranking), `qmd_get`, `qmd_multi_get`, and `qmd_status`.

---

## index

Build or refresh the FTS5 search index:

```bash
provenance index
```

The index updates automatically whenever Provenance writes a notes file (FTS5 and qmd are both re-indexed). Run this manually after bulk imports or if search returns stale results.

---

## doctor

Check that everything is configured and working:

```bash
provenance doctor
```

Checks: database exists and is accessible, FTS5 index is populated, `PROVENANCE_OPENAI_API_KEY` is set, AI provider and model are configured.
