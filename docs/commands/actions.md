# actions

Track action items linked to people and meetings.

```
provenance actions [COMMAND]
```

---

## list

List action items, with optional filters.

```bash
provenance actions list
provenance actions list --status open
provenance actions list --person tom-sever --json
```

| Flag | Short | Description |
|------|-------|-------------|
| `--status` | `-s` | Filter by status: `open`, `in_progress`, `done`, `cancelled` |
| `--person` | `-p` | Filter by person slug |
| `--json` | | Output as JSON array |

Status values are colour-coded in the terminal: yellow = open, blue = in_progress, green = done, dim = cancelled.

---

## add

Add a new action item.

```bash
provenance actions add "Send Tom the AI governance framework"
provenance actions add "Review slides" --due 2026-03-15 --person tom-sever
provenance actions add "Book venue" --meeting 2026-03-10-intro-with-tom --due 2026-03-12
```

| Argument / Flag | Short | Description |
|-----------------|-------|-------------|
| `DESCRIPTION` | | What needs to be done (required) |
| `--due` | `-d` | Due date (`YYYY-MM-DD`) |
| `--person` | `-p` | Person slug to associate |
| `--meeting` | `-m` | Meeting slug to associate |
| `--tags` | | Comma-separated tags |
| `--json` | | Output result as JSON |

New items are created with status `open`.

---

## done

Mark an action item as done.

```bash
provenance actions done 3
provenance actions done 3 --json
```

| Argument | Description |
|----------|-------------|
| `ID` | Numeric action item ID (shown in `list`) |
| `--json` | Output updated record as JSON |

---

## Pipe example

```bash
provenance actions list --status open --json | provenance ai "prioritize these and suggest a focus for this week"
```
