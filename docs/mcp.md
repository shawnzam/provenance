# Claude Desktop (MCP)

Provenance exposes all its tools as an MCP server over stdio. Claude Desktop connects to it locally — no network, no auth, no cloud.

---

## Setup

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "provenance": {
      "command": "/Users/yourname/.local/bin/uv",
      "args": ["run", "--directory", "/path/to/provenance", "python", "mcp_server.py"]
    }
  }
}
```

Replace `/Users/yourname/.local/bin/uv` with the output of `which uv`, and `/path/to/provenance` with your clone directory.

Restart Claude Desktop. You'll see a hammer icon in the input bar — click it to confirm Provenance is listed as a tool source.

---

## What you can ask

```
What meetings do I have this week?
Prep me for my 2pm with Alex
Add an action item to follow up with Jamie by Friday
What did we discuss about AI governance last month?
Who on my team should own the vendor evaluation?
Search my notes for anything about the vendor evaluation
```

---

## Available tools

### Read

| Tool | Description |
|---|---|
| `search_meetings` | Search meetings by date, person, or keyword |
| `get_meeting_notes` | Read the full notes file for a meeting; expands `[[wiki-links]]` inline |
| `get_note` | Read a freeform note by filename; expands `[[wiki-links]]` inline |
| `search_people` | Look up people by name, role, or org |
| `search_actions` | Search action items by status or keyword |
| `search_notes` | Full-text, semantic, and hybrid AI search across all notes (supports qmd) |
| `search_documents` | Search imported documents |
| `get_document` | Read an imported document; expands `[[wiki-links]]` inline |
| `search_reading_list` | Search your reading list |
| `get_calendar_events` | Read calendar events (requires icalBuddy) |
| `get_today` | Get today's date |

### Write

| Tool | Description |
|---|---|
| `add_person` | Add a new person to the CRM |
| `update_person` | Update a person's role, org, email, or notes |
| `add_meeting` | Create a meeting record and notes file |
| `update_meeting` | Update a meeting's title, date, summary, or attendees |
| `append_to_meeting_notes` | Append content to a meeting's notes file |
| `delete_meeting` | Delete a meeting and its notes file |
| `add_action` | Create an action item |
| `update_action` | Update an action item's status or due date |
| `add_reading_item` | Add a URL to your reading list |
| `update_reading_item` | Mark a reading item read, update notes or tags |
| `write_note_file` | Create or overwrite a freeform notes file |
| `update_user_context` | Append or replace `context.md` |

### `update_meeting` — attendee options

| Parameter | Behaviour |
|---|---|
| `add_attendees: ["name"]` | Add people without touching existing attendees |
| `remove_attendees: ["name"]` | Remove specific people |
| `set_attendees: ["name", ...]` | Replace the full attendee list |

People are matched by name or slug. Unrecognised names are skipped with a warning.

---

## Wiki-links

Notes, meeting files, and documents can link to each other using `[[slug]]` syntax. When Claude reads a file via `get_meeting_notes`, `get_document`, or `get_note`, it automatically follows links up to 2 hops deep and embeds the referenced content inline.

**Supported link targets:**

| `[[slug]]` resolves to | Example |
|---|---|
| Meeting (by slug) | `[[2026-03-10-intro-with-alex]]` |
| Document (by slug) | `[[ai-governance-framework]]` |
| Freeform note file (`notes/{slug}.md`) | `[[budget-notes]]` |
| Person (by slug — renders inline summary) | `[[alex-rivera]]` |

**Example in a meeting notes file:**

```markdown
## Notes

Discussed the project roadmap. See [[ai-governance-framework]] for the framework
we're aligning to, and [[alex-rivera]] for background on the attendee.
```

When Claude fetches that meeting, it gets the linked content embedded under a `### Linked: <slug>` header. Pass `follow_links: false` to any of the three tools to skip expansion.

---

## Personal context — `my_profile` prompt

Provenance ships with an MCP prompt that loads your `context.md` into the conversation. In Claude Desktop, open the prompt picker (the `+` icon or `/` slash menu) and select **my_profile**.

This is useful at the start of a session to orient Claude before asking questions.

!!! tip "Automatic context via custom instructions"
    For always-on context without manually invoking the prompt, add a system-level instruction in **Claude Desktop → Profile → Custom Instructions**:

    ```
    I use a local tool called Provenance to track my professional relationships, meetings, and notes.
    When I ask about people, meetings, actions, or work context, use the Provenance MCP tools
    to search for relevant information before answering.

    Key context about me: [paste a brief summary of your role and priorities here]
    ```

---

## Troubleshooting

**Hammer icon not showing** — Claude Desktop didn't find the server. Check that the `command` path in `claude_desktop_config.json` is absolute and correct (`which uv`).

**"Tool not found" errors** — The MCP server failed to start. Run the command manually to see the error:
```bash
uv run --directory /path/to/provenance python mcp_server.py
```

**No calendar results** — icalBuddy is not installed or your Outlook account isn't added to macOS Calendar. See [Calendar](calendar.md).

**Stale search results** — Run `provenance index` to rebuild the FTS5 index. If using qmd, also run `qmd update && qmd embed`.

---

## qmd MCP server (Claude Code)

In addition to the Provenance MCP server, you can add [qmd](https://github.com/tobi/qmd) as a separate MCP server for direct hybrid AI search over your notes. See [search — qmd setup](commands/search.md#qmd-setup) for installation and configuration.
