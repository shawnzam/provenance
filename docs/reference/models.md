# Data Models

All models live in `core/models/`. Each has a `to_dict()` method used for `--json` output and piping.

---

## Person

Represents someone in your network.

| Field | Type | Description |
|-------|------|-------------|
| `name` | CharField(200) | Full name |
| `slug` | SlugField(200) | Auto-generated from name, unique. CLI identifier. |
| `role` | CharField(200) | Job title or role |
| `org` | CharField(200) | Organisation |
| `email` | EmailField | Email address |
| `relationship_context` | TextField | How you know them, why they matter |
| `notes` | TextField | Freeform notes |
| `tags` | CharField(500) | Comma-separated tags |
| `created_at` | DateTimeField | Auto-set on creation |
| `updated_at` | DateTimeField | Auto-updated on save |

**`to_dict()` output:**
```json
{
  "slug": "alex-rivera",
  "name": "Alex Rivera",
  "role": "VP of Engineering",
  "org": "Acme Corp",
  "email": "alex@acme.com",
  "relationship_context": "Met at the onboarding session",
  "notes": "",
  "tags": ["partner", "engineering"]
}
```

---

## Meeting

Represents a meeting, linked to attendees and a notes file.

| Field | Type | Description |
|-------|------|-------------|
| `title` | CharField(300) | Meeting title |
| `slug` | SlugField(350) | Auto-generated from date + title |
| `date` | DateField | Meeting date |
| `attendees` | ManyToManyField(Person) | People who attended |
| `summary` | TextField | Brief summary |
| `notes_file` | CharField(500) | Relative path to the `.md` notes file |
| `tags` | CharField(500) | Comma-separated tags |

Notes files are stored at `notes/meetings/<slug>.md` and created automatically by `meetings add`.

**`to_dict()` output:**
```json
{
  "slug": "2026-03-10-intro-with-alex",
  "title": "Intro with Alex",
  "date": "2026-03-10",
  "attendees": [{"slug": "alex-rivera", "name": "Alex Rivera"}],
  "summary": "",
  "notes_file": "notes/meetings/2026-03-10-intro-with-alex.md",
  "tags": []
}
```

---

## ActionItem

A task or follow-up, optionally linked to a person and meeting.

| Field | Type | Description |
|-------|------|-------------|
| `description` | TextField | What needs to be done |
| `status` | CharField | `open`, `in_progress`, `done`, `cancelled` |
| `due_date` | DateField | Optional due date |
| `person` | ForeignKey(Person) | Optional owner |
| `meeting` | ForeignKey(Meeting) | Optional source meeting |
| `tags` | CharField(500) | Comma-separated tags |

Default status on creation: `open`.

---

## Document

A reference document imported into `notes/docs/`.

| Field | Type | Description |
|-------|------|-------------|
| `title` | CharField(300) | Document title |
| `slug` | SlugField(350) | Auto-generated from title |
| `file_path` | CharField(500) | Relative path to the `.md` file |
| `source` | CharField(300) | Original filename (for imports) |
| `tags` | CharField(500) | Comma-separated tags |
| `notes` | TextField | Your notes about this document |

---

## Slug generation

All slugs are generated using [python-slugify](https://github.com/un33k/python-slugify):

- `"Alex Rivera"` → `alex-rivera`
- `"2026-03-10 Intro with Alex"` → `2026-03-10-intro-with-alex`
- `"AI Ethics & Governance"` → `ai-ethics-governance`

Slugs are unique per model type. If a collision occurs, an error is raised with guidance.
