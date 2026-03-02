# REPL

The REPL is the primary interface to Provenance. Start it with:

```bash
provenance chat
```

On launch you get a **day summary** — today's meetings, open actions, your last note — a time-aware greeting, and a persistent prompt.

---

## Natural language

Just type. Unknown input is automatically sent to the AI agent, which searches your CRM and notes for relevant context before answering:

```
P 9:15 ❯ who am I meeting with this week?
P 9:15 ❯ prep me for my Erik Santoro call
P 9:15 ❯ what did I learn from the ISO team last month?
P 9:15 ❯ summarize my open action items
```

---

## Prefix shorthands

| Prefix | Action | Example |
|---|---|---|
| `@name` | Look up a person | `@roger` |
| `#title` | Create a meeting | `#standup with ISO team` |
| `+task` | Add an action item | `+send Amy the deck by Friday` |
| `!text` | Proofread | `!this sentance has erors` |

---

## Capture commands

```
note that <observation>     Save raw markdown note (auto-titled, no CRM extraction)
jot <text>                  Same as "note that"
note <text>                 Extract people/meetings/actions from text
remember <fact>             Add to context.md (always visible to AI)
proof <text or file>        Proofread via AI
```

### `remember`

Appends a fact to `~/.provenance/notes/context.md` and confirms it was saved:

```
P ❯ remember I will no longer have direct reports after March 21st
✓ Saved to context.md
```

### `note that` vs `note`

- `note that <text>` — saves a raw Markdown file with an AI-generated filename. No CRM extraction.
- `note <text>` — runs the full extraction pipeline: creates the note *and* pulls out any people, meetings, or actions mentioned.

---

## Data commands

```
people list / add / <slug>
meetings list / add / show <slug>
actions list / add / done <id>
docs list / show <slug>
notes [keyword]             List all notes files, optionally filtered
open <slug or path>         Open file in your $EDITOR
```

---

## Slash commands

| Command | Description |
|---|---|
| `/today` | Refresh day summary |
| `/set` | Show all settings |
| `/set <key> <value>` | Change a setting (e.g. `/set editor vim`) |
| `/recap [days]` | AI recap of recent activity (default 7 days) |
| `/focus` | AI prioritization of open actions |
| `/meeting` | Quick meeting wizard |
| `/paste` | Multi-line paste mode (Esc+Enter to submit) |
| `/note` | List notes or save a note |
| `/stats` | Command usage history |
| `/help` | Full command reference |

---

## Autocorrect

Type fast — prose input is silently corrected before dispatch. A dim `✓ corrected text` appears on stderr when something changed.

Disable it:

```
P ❯ /set autocorrect false
```

---

## Settings

Settings persist in `~/.provenance/settings.json`. View all:

```
P ❯ /set
```

Common settings:

| Key | Default | Description |
|---|---|---|
| `editor` | `$EDITOR` | Editor opened by `open` command |
| `autocorrect` | `true` | Silently fix prose before dispatch |
| `model` | from `.env` | Override AI model for this session |

---

## Context window

The AI agent receives:
- Your full `context.md`
- Today's calendar events (if icalBuddy is installed)
- The last few turns of conversation
- Search results retrieved for your current query

It does not have access to all your notes at once — it retrieves relevant snippets via search on each turn.
