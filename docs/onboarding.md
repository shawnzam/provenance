# Onboarding

After [setup](setup.md), spend a few minutes giving Provenance the context it needs to be useful from day one.

---

## 1. Tell it who you are

`~/.provenance/notes/context.md` is injected into the AI's system prompt on every request. The more it knows about you, the better its answers.

Edit it directly in any editor, or use the REPL:

```bash
provenance chat
```

```
P ❯ remember I am the Senior IT Director, Innovation & AI at Wharton
P ❯ remember my team is Roger, Will, Yemi, and John
P ❯ remember I report to Alec Lamon
P ❯ remember my top priority this quarter is the AI governance framework
```

Or write it directly — it's plain Markdown, no special format required:

```markdown title="~/.provenance/notes/context.md"
# Personal Context

## Identity
I am Shawn Zamechek, Senior IT Director, Innovation & AI at Wharton School, UPenn.

## My Team
- Roger Chu — engineering lead
- Will Haun — AI projects
- Yemi Afolabi — operations
- John Piotrowski — infrastructure

## Current Priorities
- AI governance framework (Q1 deadline)
- Wharton AI CoE launch
```

The AI re-reads `context.md` on every request, so edits take effect immediately.

---

## 2. Add the people you work with

### Freeform (fastest)

Describe someone naturally — AI extracts the details:

```bash
provenance note met with Sarah Chen from the AI CoE today, she leads responsible AI policy
```

Or in the REPL:

```
P ❯ note that I had a call with David Kim, CTO at Penn Medicine, exploring AI collaboration
```

### Structured

When you know the fields:

```bash
provenance people add "Tom Sever" \
  --role "Professor of Marketing" \
  --org "Wharton" \
  --context "Faculty sponsor for CARGO project"
```

### From a document

Paste an org chart, team directory, or any document — AI extracts everyone at once:

```bash
# From a file already in your docs
provenance extract org-chart-2026

# From any Markdown or PDF
provenance extract ~/Downloads/team-directory.pdf --dry-run
```

### Django admin

For bulk review and editing:

```bash
cd /path/to/provenance
uv run python manage.py runserver
```

Go to [http://localhost:8000/admin/](http://localhost:8000/admin/) → People.

---

## 3. Log your first meetings

```bash
# Freeform — AI extracts title, date, and attendees
provenance meetings add just wrapped up an intro call with Tom Sever and David Brubaker

# Structured
provenance meetings add \
  --title "Intro with Tom Sever" \
  --date 2026-03-10 \
  --attendees tom-sever
```

Each meeting creates a Markdown file in `~/.provenance/notes/meetings/`. Open it in your editor and write as much or as little as you want. Provenance indexes it automatically.

---

## 4. Build the search index

After adding notes and meetings:

```bash
provenance index
```

This populates the FTS5 full-text index so `search` and `ask` have something to work with. The index updates automatically after every write — run this manually only after bulk imports or if search seems stale.

---

## 5. Verify everything

```bash
provenance doctor
```

---

## Start using the REPL

The REPL is the main day-to-day interface. Start it once and keep it open:

```bash
provenance chat
```

See [REPL](repl.md) for the full guide.
