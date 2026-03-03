# meetings

Manage meetings and their notes.

```
provenance meetings [COMMAND]
```

---

## list

List meetings, with optional filters.

```bash
provenance meetings list
provenance meetings list --person alex-rivera
provenance meetings list --after 2026-03-01
provenance meetings list --before 2026-04-01 --json
```

| Flag | Short | Description |
|------|-------|-------------|
| `--person` | `-p` | Filter by person name or slug |
| `--after` | | Show meetings on or after date (`YYYY-MM-DD`) |
| `--before` | | Show meetings on or before date (`YYYY-MM-DD`) |
| `--json` | | Output as JSON array |

---

## add

Add a meeting and create a blank Markdown notes file.

```bash
provenance meetings add --title "Intro with Alex" --date 2026-03-10 --attendees alex-rivera
provenance meetings add --title "Team standup" --date 2026-03-11 --attendees "alex-rivera,jordan-lee" --summary "Sprint planning"
```

| Flag | Short | Description |
|------|-------|-------------|
| `--title` | `-t` | Meeting title (required) |
| `--date` | `-d` | Date in `YYYY-MM-DD` format (required) |
| `--attendees` | `-a` | Comma-separated person slugs |
| `--summary` | `-s` | Brief summary |
| `--tags` | | Comma-separated tags |
| `--json` | | Output result as JSON |

After running `add`, a Markdown file is created at `notes/meetings/<slug>.md` with a template:

```markdown
# Intro with Alex

**Date:** 2026-03-10
**Attendees:** Alex Rivera

## Notes


## Action Items

```

Open it in your editor to fill in meeting notes. The file is picked up by `provenance search` automatically.

!!! info "Auto-indexing"
    The search index is updated automatically in the background after each `meetings add`.

---

## show

Show full details for a meeting, including the contents of its notes file.

```bash
provenance meetings show 2026-03-10-intro-with-alex
provenance meetings show 2026-03-10-intro-with-alex --json
```

| Argument | Description |
|----------|-------------|
| `SLUG` | Meeting slug (see `list` for slugs) |
| `--json` | Output as JSON |
