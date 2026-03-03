# AI commands

Three AI-powered commands: `ai` for explicit pipe-based synthesis, `ask` for automatic retrieval + answer, and `proof` for proofreading.

---

## ai

Send piped context and an instruction to the configured AI provider.

```bash
provenance ai "INSTRUCTION"
```

Reads context from stdin, combines it with your instruction, and calls the AI. If nothing is piped, the instruction is sent on its own.

### Examples

```bash
# Summarise a person's meetings
provenance people alex-rivera meetings --json | provenance ai "write a short bio before our next meeting"

# Prioritise open actions
provenance actions list --status open --json | provenance ai "prioritize these and suggest what to do this week"

# Chain multiple sources
{ provenance people alex-rivera --json; provenance people alex-rivera meetings --json; } | \
  provenance ai "draft a prep briefing for my next meeting with Tom"
```

---

## ask

Ask a natural language question. Automatically retrieves relevant context from your database and notes, then answers.

```bash
provenance ask "QUESTION" [OPTIONS]
```

### Examples

```bash
# Default: DB + BM25 notes search
provenance ask "what do I know about Tom?"

# Semantic search for conceptual queries
provenance ask "what were my concerns about the new role?"

# See what context was retrieved before the answer
provenance ask "who should I follow up with?" --verbose

# DB only (skip notes search)
provenance ask "who have I met from Acme Corp?" --no-notes
```

### Options

| Flag | Short | Description |
|---|---|---|
| `--topk` | `-k` | Notes results to retrieve (default 5) |
| `--context` | `-C` | Lines of context per match (default 5) |
| `--no-db` | | Skip database search |
| `--no-notes` | | Skip notes search |
| `--verbose` | `-v` | Print retrieved context to stderr |

### How it works

1. Strips stop words from your question to extract search terms
2. Queries the database for matching people, meetings, and actions
3. Runs FTS5 search on your notes with the extracted terms
4. Formats all matches as structured context
5. Sends context + question to the AI

---

## proof

Proofread text via AI.

```bash
# Text directly
provenance proof "this sentance has erors"

# A file
provenance proof ~/draft.md

# Pipe
cat draft.md | provenance proof
```

Prints the corrected text to stdout. Useful before sending an email or document.

---

## --check-text / -ct

Global flag available on all commands that proofread free-text arguments via AI before saving.

```bash
provenance -ct people add "Alex Rivera" --context "Met hom at the offsite evnt in Januray"

# stderr:
#   ~ 'Met hom at the offsite evnt in Januray'
#   ✓ 'Met him at the offsite event in January'
```

Uses `PROVENANCE_PROOFREAD_AI_MODEL` (falls back to `PROVENANCE_AI_MODEL`). Set it to a fast model like `gpt-4o-mini` to keep latency low.

---

## AI provider configuration

| Env var | Default | Description |
|---|---|---|
| `PROVENANCE_AI_PROVIDER` | `openai` | Provider name |
| `PROVENANCE_AI_MODEL` | `gpt-4o` | Model for `ai`, `ask`, and the REPL agent |
| `PROVENANCE_PROOFREAD_AI_MODEL` | _(uses AI_MODEL)_ | Model for `--check-text` and `proof` |
| `PROVENANCE_OPENAI_API_KEY` | _(required)_ | OpenAI API key |

To add a new provider, create a file in `ai/` subclassing `AIProvider` from `ai/base.py` and register it in `ai/registry.py`. See [Development](../development.md#adding-a-new-ai-provider).
