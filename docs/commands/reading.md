# Reading list

Provenance includes a lightweight reading list for tracking articles, papers, and URLs you want to read.

```bash
provenance reading <subcommand>
```

---

## Add

Save a URL to your reading list:

```bash
provenance reading add "https://arxiv.org/abs/2303.12528" \
  --title "Sparks of AGI" \
  --tags "ai,research,llm"
```

Or in the REPL:

```
P ❯ add to reading list https://arxiv.org/abs/2303.12528
```

The title is optional — if omitted, the URL is used as the display name.

### Options

| Flag | Description |
|---|---|
| `--title TEXT` | Display title (defaults to URL) |
| `--tags TEXT` | Comma-separated tags |
| `--notes TEXT` | Initial notes |

---

## List

```bash
provenance reading list
provenance reading list --status unread
provenance reading list --status read
provenance reading list --tag ai
```

### Options

| Flag | Description |
|---|---|
| `--status TEXT` | Filter: `unread`, `reading`, `read` |
| `--tag TEXT` | Filter by tag |
| `--json` | Output as JSON |

---

## Show

View details for a single item:

```bash
provenance reading show sparks-of-agi
```

---

## Update

Change status, add notes, or update tags:

```bash
# Mark as read
provenance reading update sparks-of-agi --status read

# Add notes
provenance reading update sparks-of-agi --notes "Great paper on emergent capabilities"

# Mark as currently reading
provenance reading update sparks-of-agi --status reading
```

### Options

| Flag | Description |
|---|---|
| `--status TEXT` | `unread`, `reading`, or `read` |
| `--title TEXT` | Update title |
| `--tags TEXT` | Replace tags (comma-separated) |
| `--notes TEXT` | Update notes |

---

## Delete

```bash
provenance reading delete sparks-of-agi
```

---

## MCP tools

The reading list is also available to Claude Desktop via MCP:

| Tool | Description |
|---|---|
| `add_reading_item` | Add a URL to the reading list |
| `search_reading_list` | Search by title, tag, or status |
| `update_reading_item` | Update status, notes, or tags |

---

## Data model

| Field | Description |
|---|---|
| `title` | Display name |
| `url` | URL (optional) |
| `slug` | Auto-generated from title |
| `status` | `unread`, `reading`, or `read` |
| `tags` | Comma-separated tags |
| `notes` | Free-text notes |
| `summary` | AI-generated summary (future) |
| `created_at` | When added |
| `read_at` | When marked read |
