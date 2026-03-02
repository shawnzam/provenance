# people

Manage people in your network.

```
provenance people [COMMAND]
```

---

## list

List all people in the database.

```bash
provenance people list
provenance people list --json
```

| Flag | Description |
|------|-------------|
| `--json` | Output as JSON array |

---

## add

Add a new person, or update an existing one if the slug already exists.

```bash
provenance people add "Tom Sever"
provenance people add "Tom Sever" --role "Professor of Marketing" --org "Wharton"
provenance people add "Tom Sever" --email "tsever@wharton.upenn.edu" --context "Met at orientation"
provenance people add "Tom Sever" --role "Professor" --update   # skip confirmation prompt
```

| Argument / Flag | Short | Description |
|-----------------|-------|-------------|
| `NAME` | | Full name (required) |
| `--role` | `-r` | Job title or role |
| `--org` | `-o` | Organization |
| `--email` | `-e` | Email address |
| `--context` | `-c` | Relationship context — how you know them, why they matter |
| `--notes` | `-n` | Freeform notes |
| `--tags` | `-t` | Comma-separated tags |
| `--update` | `-u` | Update existing record without prompting |
| `--json` | | Output result as JSON |

If a person with the same slug already exists, you'll be shown their current details and prompted to confirm the update. Pass `--update` to skip the prompt (useful in scripts).

!!! tip "Proofread on the way in"
    Add `-ct` to proofread prose fields before saving:
    ```bash
    provenance -ct people add "Tom Sevr" --role "Profsor of Markting"
    ```

---

## show

Show full details for a person.

```bash
provenance people show tom-sever
provenance people tom-sever           # shorthand
provenance people tom-sever --json
```

| Argument | Description |
|----------|-------------|
| `SLUG` | Person slug (see `list` for slugs) |
| `--json` | Output as JSON |

---

## meetings

List all meetings for a person.

```bash
provenance people meetings tom-sever
provenance people tom-sever meetings          # shorthand
provenance people tom-sever meetings --json
```

| Argument | Description |
|----------|-------------|
| `SLUG` | Person slug |
| `--json` | Output as JSON (includes person + meetings array) |

The `--json` output is designed for piping:

```bash
provenance people tom-sever meetings --json | provenance ai "write a short bio before our next meeting"
```
