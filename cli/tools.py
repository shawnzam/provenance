"""
Tool definitions and implementations for the AI agent loop.
Each tool maps 1-to-1 to a Django query or ck search.
"""
import json
import shutil
import subprocess
from datetime import date, timedelta
from pathlib import Path

from cli.paths import PROVENANCE_HOME as BASE_DIR

# ---------------------------------------------------------------------------
# Tool schema (OpenAI function-calling format)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_meetings",
            "description": (
                "Search meetings by date range, attendee name, or keyword. "
                "Use date filters for questions like 'today', 'this week', 'last month'. "
                "Returns title, date, slug, attendees, and summary for each match."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Exact date (YYYY-MM-DD)"},
                    "date_from": {"type": "string", "description": "Start of date range (YYYY-MM-DD)"},
                    "date_to": {"type": "string", "description": "End of date range (YYYY-MM-DD)"},
                    "person": {"type": "string", "description": "Filter by attendee name or slug"},
                    "keyword": {"type": "string", "description": "Keyword in title or summary"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_meeting_notes",
            "description": (
                "Get the full notes file for a specific meeting. Use after search_meetings to get details. "
                "Wiki-links ([[slug]]) in the notes are followed automatically (up to 2 hops) unless "
                "follow_links is set to false."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "slug": {"type": "string", "description": "Meeting slug from search_meetings"},
                    "follow_links": {
                        "type": "boolean",
                        "description": "Expand [[wiki-links]] inline (default true)",
                    },
                },
                "required": ["slug"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": (
                "Search notes in notes/docs/ (resumes, plans, frameworks, drafts, etc.) by title or keyword. "
                "Documents are plain markdown files — no separate database. "
                "Returns slug (file stem) and path. Use get_document to read the full content."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "Word or phrase to match against file title or content"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_document",
            "description": (
                "Read the full content of a note file by its slug (file stem). "
                "Use after search_documents, or if you already know the slug. "
                "Wiki-links ([[slug]]) are followed recursively up to 2 hops deep by default: "
                "each [[slug]] in the file is resolved to the referenced note/meeting/person and "
                "embedded inline under a '### Linked: <slug>' header. This lets you pull a rich "
                "context tree from a single entry point. Pass follow_links=false to get raw content only."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "slug": {"type": "string", "description": "File stem slug (e.g. 'wharton-ai-governance-framework-v01')"},
                    "follow_links": {
                        "type": "boolean",
                        "description": "Recursively expand [[wiki-links]] up to 2 hops (default true). Each linked slug is resolved — Meeting → notes file, Person → inline summary, any .md file → content — and embedded inline.",
                    },
                },
                "required": ["slug"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_note",
            "description": (
                "Read any note file from the notes/ directory by filename or slug. "
                "Use this for freeform notes, daily summaries, or any .md file outside notes/docs/. "
                "Wiki-links ([[slug]]) are followed recursively up to 2 hops deep by default: "
                "each [[slug]] in the note is resolved and embedded inline under '### Linked: <slug>'. "
                "Pass follow_links=false to get raw content without link expansion."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Note filename or slug (with or without .md, e.g. '2026-03-07-ideas' or 'context')",
                    },
                    "follow_links": {
                        "type": "boolean",
                        "description": "Recursively expand [[wiki-links]] up to 2 hops (default true). Cycle-safe — already-visited slugs are noted but not re-expanded.",
                    },
                },
                "required": ["filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_people",
            "description": "Search people by name, role, org, or any keyword.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "Name, role, org, or general keyword"},
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_actions",
            "description": "Search action items by status or keyword.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["open", "in_progress", "done"],
                        "description": "Filter by status",
                    },
                    "keyword": {"type": "string", "description": "Keyword in description"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_notes",
            "description": (
                "Search notes files. Choose the right mode for the query:\n"
                "- regex: exact match — use for specific terms, names, acronyms, IDs (e.g. 'ISO', 'GPT-4', 'Colleen O Neill')\n"
                "- lex: BM25 full-text ranking — use for topics, keywords, document-level relevance (e.g. 'budget planning', 'AI governance')\n"
                "- semantic: conceptual/embedding search — use for fuzzy or intent-based queries (e.g. 'times I felt stressed', 'discussions about trust')\n"
                "- qmd: hybrid AI search (vector + BM25 + LLM reranking) — best quality for complex/intent queries, slower\n"
                "Use context_lines to pull more surrounding text when the user wants details, full notes, or deeper context (e.g. 10–20). Default is 3."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term or phrase"},
                    "mode": {
                        "type": "string",
                        "enum": ["regex", "lex", "semantic", "qmd"],
                        "description": "regex for exact terms/names; lex for BM25 topics/concepts; semantic for FTS5 stemming; qmd for hybrid AI search (best quality, slower)",
                    },
                    "context_lines": {
                        "type": "integer",
                        "description": "Lines of context around each match (default 3; use 10–20 for full details or when user wants more depth)",
                    },
                },
                "required": ["query", "mode"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_today",
            "description": "Get today's date and day of week.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_daily_summary",
            "description": (
                "Read the daily summary file for a given date (default today). "
                "Contains timestamped log entries and any AI-generated summary blocks."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Date (YYYY-MM-DD, default today)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_daily",
            "description": (
                "Append a timestamped log entry to the daily summary file. "
                "Use this to capture quick notes, decisions, or progress throughout the day."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entry": {"type": "string", "description": "The log entry text"},
                    "date": {"type": "string", "description": "Date (YYYY-MM-DD, default today)"},
                },
                "required": ["entry"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "append_to_daily_summary",
            "description": (
                "Append a block of content (e.g. an AI-generated summary) to a daily summary file. "
                "Use this after synthesizing meetings, actions, and log entries into a narrative."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Markdown content to append"},
                    "date": {"type": "string", "description": "Date (YYYY-MM-DD, default today)"},
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_meeting",
            "description": (
                "Create a new meeting record and notes file. "
                "Use attendee_names with full names — they will be matched to existing people automatically. "
                "Put any known details (agenda, context, caveats) in the notes field."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Meeting title"},
                    "date": {"type": "string", "description": "Date (YYYY-MM-DD)"},
                    "attendee_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Full names of attendees",
                    },
                    "summary": {"type": "string", "description": "One-line summary"},
                    "notes": {"type": "string", "description": "Content to pre-fill in the notes file"},
                },
                "required": ["title", "date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "append_to_meeting_notes",
            "description": (
                "Append content to an existing meeting's notes file. "
                "Use this when the user asks to add notes, summaries, or sections to a meeting. "
                "Use search_meetings or get_meeting_notes first to find the slug and see existing content."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "slug": {"type": "string", "description": "Meeting slug"},
                    "content": {"type": "string", "description": "Markdown content to append"},
                },
                "required": ["slug", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apply_wiki_links",
            "description": (
                "Scan notes and insert [[wiki-links]] for known people and meetings — "
                "first occurrence of each name per file only. Safe to run repeatedly; "
                "already-linked text and headings/code blocks are skipped. "
                "Use this after adding new people or meetings, or to enrich a specific note. "
                "Returns a summary of how many files and links were added."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file": {
                        "type": "string",
                        "description": "Limit to one file (relative path from notes/, e.g. '2026-03-09-ideas.md'). Omit to scan all notes.",
                    },
                    "min_length": {
                        "type": "integer",
                        "description": "Minimum entity name length to link (default 4, raise to reduce noise)",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_note_file",
            "description": (
                "Create or overwrite a freeform note file under notes/. "
                "Use for saving research, observations, or any content the user wants stored as a note. "
                "filename should be YYYY-MM-DD-short-slug.md format."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Filename under notes/ (e.g. 2026-02-27-topic.md)"},
                    "content": {"type": "string", "description": "Full markdown content to write"},
                },
                "required": ["filename", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_meeting",
            "description": (
                "Update a meeting's details or attendees. Use search_meetings first to find the slug. "
                "To add/remove individual attendees use add_attendees/remove_attendees. "
                "To replace the full attendee list use set_attendees. "
                "People are matched by name or slug."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "slug": {"type": "string", "description": "Meeting slug (from search_meetings)"},
                    "title": {"type": "string", "description": "New meeting title"},
                    "date": {"type": "string", "description": "New date (YYYY-MM-DD)"},
                    "summary": {"type": "string", "description": "New or updated summary"},
                    "add_attendees": {
                        "type": "array", "items": {"type": "string"},
                        "description": "Names to add to attendees (without removing existing ones)",
                    },
                    "remove_attendees": {
                        "type": "array", "items": {"type": "string"},
                        "description": "Names to remove from attendees",
                    },
                    "set_attendees": {
                        "type": "array", "items": {"type": "string"},
                        "description": "Replace the full attendee list with these names",
                    },
                },
                "required": ["slug"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_person",
            "description": (
                "Add a new person to the CRM. Use when the user mentions someone who isn't already tracked. "
                "Search first with search_people to avoid duplicates. "
                "Tag personal contacts with 'personal' (e.g. tags='personal') so they are excluded "
                "from the Work view of the graph and kept separate from professional contacts."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Full name"},
                    "role": {"type": "string", "description": "Job title or role"},
                    "org": {"type": "string", "description": "Organization or department"},
                    "email": {"type": "string", "description": "Email address"},
                    "relationship_context": {"type": "string", "description": "How you know them / relevant context"},
                    "notes": {"type": "string", "description": "Additional notes"},
                    "tags": {"type": "string", "description": "Comma-separated tags. Use 'personal' to exclude from work graph."},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_person",
            "description": (
                "Update an existing person's details — role, org, email, notes, or relationship context. "
                "Use search_people first to find the slug. Only updates fields you explicitly provide."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "slug": {"type": "string", "description": "Person slug (from search_people)"},
                    "role": {"type": "string", "description": "New job title or role"},
                    "org": {"type": "string", "description": "New organization or department"},
                    "email": {"type": "string", "description": "New email address"},
                    "relationship_context": {"type": "string", "description": "How you know them / relevant context"},
                    "notes": {"type": "string", "description": "Additional notes"},
                },
                "required": ["slug"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_meeting",
            "description": (
                "Delete a meeting record and its notes file by slug. "
                "Use search_meetings first to find the slug if you don't know it. "
                "Only call this when the user explicitly asks to delete or remove a meeting."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "slug": {"type": "string", "description": "Meeting slug to delete"},
                },
                "required": ["slug"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_action",
            "description": (
                "Create a new action item / todo. Use this when the user wants to add a task, "
                "reminder, follow-up, or todo. Optionally link to a person or set a due date."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "What needs to be done"},
                    "due_date": {"type": "string", "description": "Due date (YYYY-MM-DD), optional"},
                    "person_name": {"type": "string", "description": "Full name of related person, optional"},
                    "tags": {"type": "string", "description": "Comma-separated tags, optional"},
                },
                "required": ["description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_reading_item",
            "description": (
                "Save a URL to the reading list. Fetches the page, generates an AI summary, "
                "and stores it. Use when the user shares a link they want to save or read later."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to save"},
                    "tags": {"type": "string", "description": "Comma-separated tags, optional"},
                    "notes": {"type": "string", "description": "Initial notes about why you're saving this, optional"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_reading_list",
            "description": (
                "Search the reading list by keyword, tag, or status. "
                "Use for questions like 'what articles have I saved about X?' or 'show my unread items'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "Search in title, summary, notes, and URL"},
                    "tag": {"type": "string", "description": "Filter by tag"},
                    "status": {
                        "type": "string",
                        "enum": ["to_read", "read", "archived"],
                        "description": "Filter by status",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_user_context",
            "description": (
                "Update the user's personal context file (notes/context.md). "
                "Use to record new facts about the user, update their role/team/priorities, "
                "or append new sections. Prefer append=true to preserve existing content."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Text to write"},
                    "append": {
                        "type": "boolean",
                        "description": "If true (default), append to existing file. If false, replace entire file.",
                    },
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_reading_item",
            "description": (
                "Update a reading list item's status, tags, or notes. "
                "Use to mark articles as read/archived, append notes, or retag. "
                "Requires the item slug (get it from search_reading_list)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "slug": {"type": "string", "description": "The item's slug identifier"},
                    "status": {
                        "type": "string",
                        "enum": ["to_read", "read", "archived"],
                        "description": "New status",
                    },
                    "tags": {"type": "string", "description": "Replace tags with this comma-separated string"},
                    "notes": {"type": "string", "description": "Text to append to existing notes"},
                },
                "required": ["slug"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_calendar_events",
            "description": (
                "Get calendar events from macOS Calendar (synced from Outlook). "
                "Use for questions like 'what's on my calendar today/this week', "
                "'when am I meeting with X', or 'do I have anything Thursday'. "
                "Defaults to work calendars for the next 7 days."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date_from": {"type": "string", "description": "Start date (YYYY-MM-DD). Defaults to today."},
                    "date_to": {"type": "string", "description": "End date inclusive (YYYY-MM-DD). Defaults to 7 days out."},
                    "calendars": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Calendar names to query. Defaults to work calendars.",
                    },
                    "keyword": {"type": "string", "description": "Filter events by keyword in title, location, or notes."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_action",
            "description": (
                "Update an existing action item — mark it done, change status, or update description. "
                "Use search_actions first to find the action ID."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action_id": {"type": "integer", "description": "The action item ID (from search_actions)"},
                    "status": {
                        "type": "string",
                        "enum": ["open", "in_progress", "done", "cancelled"],
                        "description": "New status",
                    },
                    "description": {"type": "string", "description": "Updated description, optional"},
                },
                "required": ["action_id"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def get_today(**_) -> str:
    today = date.today()
    return f"Today is {today.strftime('%A, %B %d, %Y')} ({today.isoformat()})"


# ---------------------------------------------------------------------------
# Daily summary tools
# ---------------------------------------------------------------------------

def _daily_path(date_str: str | None = None) -> Path:
    from cli.paths import DAILY_DIR
    d = date_str or date.today().isoformat()
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    return DAILY_DIR / f"{d}.md"


def _ensure_daily_log_section(path: Path, date_str: str) -> None:
    if not path.exists():
        path.write_text(f"# Daily Summary — {date_str}\n\n## Log\n\n")


def get_daily_summary(date: str | None = None) -> str:
    path = _daily_path(date)
    if not path.exists():
        d = date or __import__("datetime").date.today().isoformat()
        return f"No daily summary for {d} yet."
    return path.read_text()


def log_daily(entry: str, date: str | None = None) -> str:
    import re as _re
    from datetime import datetime as _dt
    d = date or __import__("datetime").date.today().isoformat()
    path = _daily_path(d)
    _ensure_daily_log_section(path, d)

    ts = _dt.now().strftime("%H:%M")
    line = f"- {ts} — {entry}\n"

    content = path.read_text()
    log_match = _re.search(r"^## Log\s*\n", content, _re.MULTILINE)
    if not log_match:
        content += f"\n\n## Log\n\n{line}"
    else:
        rest = content[log_match.end():]
        next_sec = _re.search(r"^##\s", rest, _re.MULTILINE)
        if next_sec:
            insert_at = log_match.end() + next_sec.start()
            content = content[:insert_at] + line + "\n" + content[insert_at:]
        else:
            content = content.rstrip("\n") + "\n" + line

    path.write_text(content)
    return f"Logged {ts} — {entry} → daily_summaries/{d}.md"


def append_to_daily_summary(content: str, date: str | None = None) -> str:
    d = date or __import__("datetime").date.today().isoformat()
    path = _daily_path(d)
    _ensure_daily_log_section(path, d)
    with path.open("a") as f:
        f.write("\n" + content.strip() + "\n")
    return f"Appended to daily_summaries/{d}.md"


def search_meetings(
    date: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    person: str | None = None,
    keyword: str | None = None,
) -> str:
    from core.models import Meeting
    from django.db.models import Q

    qs = Meeting.objects.all()

    if date:
        qs = qs.filter(date=date)
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    if person:
        qs = qs.filter(
            Q(attendees__name__icontains=person) | Q(attendees__slug__icontains=person)
        ).distinct()
    if keyword:
        qs = qs.filter(
            Q(title__icontains=keyword) | Q(summary__icontains=keyword)
        ).distinct()

    meetings = list(qs.order_by("-date"))
    if not meetings:
        return "No meetings found."

    lines = []
    for m in meetings:
        attendees = ", ".join(a.name for a in m.attendees.all())
        lines.append(f"Meeting: {m.title}")
        lines.append(f"  Date: {m.date}  Slug: {m.slug}")
        lines.append(f"  Attendees: {attendees}")
        if m.summary:
            lines.append(f"  Summary: {m.summary}")
    return "\n".join(lines)


def get_meeting_notes(slug: str, follow_links: bool = True) -> str:
    from core.models import Meeting
    from cli.link_utils import expand_links
    try:
        m = Meeting.objects.get(slug=slug)
    except Meeting.DoesNotExist:
        return f"No meeting with slug '{slug}'."

    if not m.notes_file:
        return f"Meeting '{m.title}' has no notes file."

    notes_path = BASE_DIR / m.notes_file
    if not notes_path.exists():
        return f"Notes file not found: {m.notes_file}"

    content = notes_path.read_text()
    if follow_links:
        content = expand_links(content, BASE_DIR, visited=frozenset([slug]))
    return content


def search_documents(keyword: str | None = None, tag: str | None = None) -> str:
    """Search .md files in notes/docs/ by title or keyword (file-based, no DB)."""
    docs_dir = BASE_DIR / "notes" / "docs"
    if not docs_dir.exists():
        return "No documents found (notes/docs/ directory does not exist)."

    results = []
    for p in sorted(docs_dir.rglob("*.md")):
        title = ""
        try:
            for line in p.read_text().splitlines():
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
        except OSError:
            pass
        title = title or p.stem.replace("-", " ").title()

        if keyword:
            kw = keyword.lower()
            try:
                content_lower = p.read_text().lower()
            except OSError:
                content_lower = ""
            if kw not in title.lower() and kw not in content_lower:
                continue

        rel = str(p.relative_to(BASE_DIR))
        results.append(f"Document: {title}\n  Slug: {p.stem}  File: {rel}")

    if not results:
        return "No documents found matching that query."
    return "\n".join(results)


def get_document(slug: str, follow_links: bool = True) -> str:
    """Read a note file by slug (file stem). Searches notes/ recursively."""
    from cli.link_utils import expand_links

    notes_dir = BASE_DIR / "notes"
    if notes_dir.exists():
        for p in notes_dir.rglob("*.md"):
            if p.stem == slug:
                content = p.read_text()
                if follow_links:
                    content = expand_links(content, BASE_DIR, visited=frozenset([slug]))
                return content

    return f"No note found with slug '{slug}'. Use search_documents or search_notes to find it."


def get_note(filename: str, follow_links: bool = True) -> str:
    from cli.link_utils import expand_links
    from pathlib import PurePosixPath
    safe = PurePosixPath(filename).name  # strip path traversal
    if not safe.endswith(".md"):
        safe += ".md"

    note_path = BASE_DIR / "notes" / safe
    if not note_path.exists():
        return f"Note not found: notes/{safe}"

    content = note_path.read_text()
    slug = PurePosixPath(safe).stem  # filename without .md
    if follow_links:
        content = expand_links(content, BASE_DIR, visited=frozenset([slug]))
    return content


def search_people(keyword: str) -> str:
    from core.models import Person
    from django.db.models import Q
    import functools, operator

    # Search each word independently so "Josh Beeman" matches "Joshua Beeman"
    words = keyword.strip().split()
    def _q(w):
        return (
            Q(name__icontains=w) | Q(role__icontains=w)
            | Q(org__icontains=w) | Q(notes__icontains=w)
            | Q(relationship_context__icontains=w)
        )
    combined = functools.reduce(operator.or_, (_q(w) for w in words))
    qs = Person.objects.filter(combined).distinct()

    people = list(qs)
    if not people:
        return f"No people found matching '{keyword}'."

    lines = []
    for p in people:
        lines.append(f"Person: {p.name} ({p.slug})")
        if p.role:
            lines.append(f"  Role: {p.role}")
        if p.org:
            lines.append(f"  Org: {p.org}")
        if p.relationship_context:
            lines.append(f"  Context: {p.relationship_context}")
        if p.notes:
            lines.append(f"  Notes: {p.notes[:200]}")
    return "\n".join(lines)


def search_actions(status: str | None = None, keyword: str | None = None) -> str:
    from core.models import ActionItem
    from django.db.models import Q

    qs = ActionItem.objects.select_related("person", "meeting")
    if status:
        qs = qs.filter(status=status)
    if keyword:
        qs = qs.filter(Q(description__icontains=keyword))

    actions = list(qs.order_by("due_date"))
    if not actions:
        return "No action items found."

    lines = []
    for a in actions:
        due = f" (due {a.due_date})" if a.due_date else ""
        person = f" — {a.person.name}" if a.person else ""
        lines.append(f"[{a.status}] {a.description}{due}{person}")
    return "\n".join(lines)


def _search_notes_qmd(query: str, context_lines: int = 3) -> str:
    """Hybrid search via qmd (vector + BM25 + LLM reranking)."""
    qmd_bin = shutil.which("qmd")
    if not qmd_bin:
        return "qmd not installed. Run: npm install -g @tobilu/qmd"

    cmd = [qmd_bin, "query", query, "--json", "-n", "8",
           "-c", "provenance-notes"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return "qmd query timed out."
    if result.returncode != 0:
        stderr = result.stderr.strip()
        return f"qmd error: {stderr}" if stderr else "qmd query failed."

    import json as _json
    stdout = result.stdout.strip()
    # qmd may print progress text before JSON on first run (model downloads)
    # Find the JSON array start
    bracket = stdout.find("[")
    if bracket > 0:
        stdout = stdout[bracket:]
    try:
        items = _json.loads(stdout)
    except _json.JSONDecodeError:
        return "qmd returned invalid JSON."

    if not items:
        return f"No notes found for '{query}'."

    hits = []
    for item in items:
        file_uri = item.get("file", "")
        # qmd://provenance-notes/path.md → notes/path.md
        rel = file_uri.replace("qmd://provenance-notes/", "notes/")
        score = item.get("score", 0)
        snippet = item.get("snippet", "").strip()

        # Try to read the actual file and show context if available
        full_path = BASE_DIR / rel
        if full_path.exists() and context_lines > 0:
            try:
                text = full_path.read_text()
                lines = text.splitlines()
                terms = query.lower().split()
                shown: set[int] = set()
                for i, line in enumerate(lines):
                    if any(t in line.lower() for t in terms):
                        for j in range(
                            max(0, i - context_lines),
                            min(len(lines), i + context_lines + 1),
                        ):
                            shown.add(j)
                if shown:
                    excerpt = "\n".join(f"  {lines[i]}" for i in sorted(shown))
                    hits.append(f"[{rel}] (score: {score:.2f})\n{excerpt}")
                    continue
            except Exception:
                pass

        # Fallback: use qmd's snippet
        indented = "\n".join(f"  {l}" for l in snippet.splitlines())
        hits.append(f"[{rel}] (score: {score:.2f})\n{indented}")

    return "\n\n".join(hits)


def search_notes(query: str, mode: str = "regex", context_lines: int = 3) -> str:
    notes_dir = BASE_DIR / "notes"

    if mode == "qmd":
        return _search_notes_qmd(query, context_lines)

    if mode in ("lex", "semantic"):
        # FTS5 — find matching files ranked by BM25, then extract context lines in Python.
        # FTS5 MATCH syntax: multi-word queries match docs containing all words (AND).
        # Wrap each word in quotes to treat as literal phrases, not FTS5 operators.
        fts_query = " ".join(f'"{w}"' for w in query.split()) if query.strip() else query
        matched_paths: list[str] = []
        try:
            from django.db import connection
            with connection.cursor() as cur:
                cur.execute(
                    "SELECT path FROM notes_fts WHERE notes_fts MATCH %s ORDER BY rank LIMIT 8",
                    [fts_query],
                )
                matched_paths = [row[0] for row in cur.fetchall()]
        except Exception:
            pass  # FTS5 table missing or query error — fall through to Python grep

        if matched_paths:
            terms = query.lower().split()
            hits = []
            for rel in matched_paths:
                path = BASE_DIR / rel
                try:
                    text = path.read_text()
                except Exception:
                    continue
                lines = text.splitlines()
                shown: set[int] = set()
                for i, line in enumerate(lines):
                    if any(t in line.lower() for t in terms):
                        for j in range(
                            max(0, i - context_lines),
                            min(len(lines), i + context_lines + 1),
                        ):
                            shown.add(j)
                if shown:
                    excerpt = "\n".join(f"  {lines[i]}" for i in sorted(shown))
                else:
                    # FTS5 matched via stemming but no exact term in lines — show opening
                    excerpt = "\n".join(f"  {l}" for l in lines[:context_lines * 2])
                hits.append(f"[{rel}]\n{excerpt}")
            if hits:
                return "\n\n".join(hits)

    # Regex mode (or FTS5 fallback) — plain Python grep
    if not notes_dir.exists():
        return f"No notes found for '{query}'."

    terms = query.lower().split()
    hits = []
    for path in sorted(notes_dir.rglob("*.md")):
        try:
            text = path.read_text()
        except Exception:
            continue
        if all(t in text.lower() for t in terms):
            lines = text.splitlines()
            shown = set()
            for i, line in enumerate(lines):
                if any(t in line.lower() for t in terms):
                    for j in range(
                        max(0, i - context_lines),
                        min(len(lines), i + context_lines + 1),
                    ):
                        shown.add(j)
            excerpt = "\n".join(f"  {lines[i]}" for i in sorted(shown))
            hits.append(f"[{path.relative_to(BASE_DIR)}]\n{excerpt}")

    return "\n\n".join(hits) if hits else f"No notes found for '{query}'."


def add_meeting(
    title: str,
    date: str,
    attendee_names: list[str] | None = None,
    summary: str = "",
    notes: str = "",
) -> str:
    from core.models import Meeting, Person
    from slugify import slugify
    from cli.commands.meetings import _name_score

    # Resolve attendee names to Person objects (fuzzy match, create stubs if needed)
    attendee_objects = []
    seen_slugs: set[str] = set()

    all_people = list(Person.objects.values_list("slug", "name"))
    slug_for_name = {name: slug for slug, name in all_people}

    for name in (attendee_names or []):
        slug = slugify(name)
        if slug in seen_slugs:
            continue

        # Exact slug match
        try:
            p = Person.objects.get(slug=slug)
            attendee_objects.append(p)
            seen_slugs.add(p.slug)
            continue
        except Person.DoesNotExist:
            pass

        # Fuzzy match
        scored = sorted(
            ((existing, _name_score(name, existing)) for existing in slug_for_name
             if slug_for_name[existing] not in seen_slugs),
            key=lambda x: x[1],
            reverse=True,
        )
        best_name, best_score = scored[0] if scored else (None, 0.0)

        if best_score >= 0.5 and best_name:
            p = Person.objects.get(slug=slug_for_name[best_name])
            attendee_objects.append(p)
            seen_slugs.add(p.slug)
        else:
            p, _ = Person.objects.get_or_create(slug=slug, defaults={"name": name})
            attendee_objects.append(p)
            seen_slugs.add(slug)

    meeting_slug = slugify(f"{date}-{title}")
    if Meeting.objects.filter(slug=meeting_slug).exists():
        return f"A meeting with slug '{meeting_slug}' already exists."

    # Build notes file
    notes_dir = BASE_DIR / "notes" / "meetings"
    notes_dir.mkdir(parents=True, exist_ok=True)
    notes_filename = f"{meeting_slug}.md"
    notes_path = notes_dir / notes_filename
    attendee_names_str = ", ".join(p.name for p in attendee_objects)
    notes_body = notes if notes else ""
    notes_path.write_text(
        f"# {title}\n\n"
        f"**Date:** {date}  \n"
        f"**Attendees:** {attendee_names_str}  \n\n"
        f"## Notes\n\n{notes_body}\n\n"
        f"## Action Items\n\n\n"
    )

    meeting = Meeting.objects.create(
        title=title,
        date=date,
        summary=summary,
        notes_file=f"notes/meetings/{notes_filename}",
    )
    meeting.attendees.set(attendee_objects)

    from cli.indexer import index_file
    index_file(notes_path)

    return (
        f"Meeting created: {title} on {date} (slug: {meeting_slug})\n"
        f"Attendees: {attendee_names_str}\n"
        f"Notes file: notes/meetings/{notes_filename}"
    )


def append_to_meeting_notes(slug: str, content: str) -> str:
    from core.models import Meeting
    try:
        m = Meeting.objects.get(slug=slug)
    except Meeting.DoesNotExist:
        return f"No meeting with slug '{slug}'."

    if not m.notes_file:
        return f"Meeting '{m.title}' has no notes file."

    notes_path = BASE_DIR / m.notes_file
    if not notes_path.exists():
        return f"Notes file not found: {m.notes_file}"

    existing = notes_path.read_text()
    # Insert before the Action Items section if it exists, otherwise just append
    if "## Action Items" in existing:
        updated = existing.replace(
            "## Action Items",
            f"{content.strip()}\n\n## Action Items",
        )
    else:
        updated = existing.rstrip() + f"\n\n{content.strip()}\n"

    notes_path.write_text(updated)

    from cli.indexer import index_file
    index_file(notes_path)

    return f"Appended to {m.notes_file} ({len(content)} chars)"


def write_note_file(filename: str, content: str) -> str:
    # Sanitize — keep it inside notes/
    from pathlib import PurePosixPath
    safe_name = PurePosixPath(filename).name  # strip any path traversal
    if not safe_name.endswith(".md"):
        safe_name += ".md"

    notes_dir = BASE_DIR / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    dest = notes_dir / safe_name
    dest.write_text(content.strip() + "\n")

    from cli.indexer import index_file
    index_file(dest)

    return f"Saved notes/{safe_name} ({len(content)} chars)"


def add_person(
    name: str,
    role: str = "",
    org: str = "",
    email: str = "",
    relationship_context: str = "",
    notes: str = "",
    tags: str = "",
) -> str:
    from core.models import Person
    from slugify import slugify as _slugify

    slug = _slugify(name)
    if Person.objects.filter(slug=slug).exists():
        return f"'{name}' already exists (slug: {slug}). Use update_person to modify them."

    p = Person.objects.create(
        name=name,
        slug=slug,
        role=role,
        org=org,
        email=email,
        relationship_context=relationship_context,
        notes=notes,
        tags=tags,
    )
    return f"Added {p.name} ({p.slug})" + (f" — {p.role} at {p.org}" if p.role or p.org else "")


def update_meeting(
    slug: str,
    title: str | None = None,
    date: str | None = None,
    summary: str | None = None,
    add_attendees: list[str] | None = None,
    remove_attendees: list[str] | None = None,
    set_attendees: list[str] | None = None,
) -> str:
    from core.models import Meeting, Person
    from slugify import slugify as _slugify

    try:
        m = Meeting.objects.get(slug=slug)
    except Meeting.DoesNotExist:
        return f"No meeting with slug '{slug}'. Use search_meetings to find the right slug."

    changed = []

    if title is not None:
        m.title = title
        changed.append("title")
    if date is not None:
        from datetime import date as _date
        try:
            m.date = _date.fromisoformat(date)
            changed.append("date")
        except ValueError:
            return f"Invalid date '{date}'. Use YYYY-MM-DD."
    if summary is not None:
        m.summary = summary
        changed.append("summary")

    if changed:
        m.save()

    def _resolve_people(names: list[str]) -> tuple[list, list]:
        found, missing = [], []
        for name in names:
            slug_guess = _slugify(name)
            p = (Person.objects.filter(slug=slug_guess).first()
                 or Person.objects.filter(name__iexact=name).first()
                 or Person.objects.filter(slug__icontains=slug_guess).first())
            if p:
                found.append(p)
            else:
                missing.append(name)
        return found, missing

    warnings = []

    if set_attendees is not None:
        people, missing = _resolve_people(set_attendees)
        m.attendees.set(people)
        changed.append(f"attendees → {[p.slug for p in people]}")
        if missing:
            warnings.append(f"not found: {missing}")

    else:
        if add_attendees:
            people, missing = _resolve_people(add_attendees)
            m.attendees.add(*people)
            changed.append(f"added {[p.slug for p in people]}")
            if missing:
                warnings.append(f"not found (skipped): {missing}")

        if remove_attendees:
            people, missing = _resolve_people(remove_attendees)
            m.attendees.remove(*people)
            changed.append(f"removed {[p.slug for p in people]}")
            if missing:
                warnings.append(f"not found: {missing}")

    if not changed:
        return f"{m.title}: nothing to update."

    current = [p.slug for p in m.attendees.all()]
    result = f"Updated '{m.title}' ({m.slug}): {', '.join(str(c) for c in changed)}. Attendees now: {current}"
    if warnings:
        result += f". Warnings: {'; '.join(warnings)}"
    return result


def update_person(
    slug: str,
    role: str | None = None,
    org: str | None = None,
    email: str | None = None,
    relationship_context: str | None = None,
    notes: str | None = None,
) -> str:
    from core.models import Person
    try:
        p = Person.objects.get(slug=slug)
    except Person.DoesNotExist:
        # Try fuzzy slug match
        from slugify import slugify as _slugify
        p = Person.objects.filter(slug__icontains=slug.replace("-", "")).first()
        if not p:
            return f"No person with slug '{slug}'. Use search_people to find the right slug."

    changed = []
    for field, value in [("role", role), ("org", org), ("email", email),
                         ("relationship_context", relationship_context), ("notes", notes)]:
        if value is not None:
            setattr(p, field, value)
            changed.append(field)
    p.save()

    if not changed:
        return f"{p.name}: nothing to update."
    return f"Updated {p.name} ({p.slug}): {', '.join(changed)} → role={p.role!r}"


def delete_meeting(slug: str) -> str:
    from core.models import Meeting
    try:
        m = Meeting.objects.get(slug=slug)
    except Meeting.DoesNotExist:
        return f"No meeting with slug '{slug}'."

    title = m.title
    notes_file = m.notes_file

    # Remove notes file from disk if it exists
    if notes_file:
        notes_path = BASE_DIR / notes_file
        if notes_path.exists():
            notes_path.unlink()

    m.delete()
    return f"Deleted meeting '{title}' (slug: {slug})" + (
        f" and removed notes file {notes_file}" if notes_file else ""
    )


def add_action(
    description: str,
    due_date: str | None = None,
    person_name: str | None = None,
    tags: str = "",
) -> str:
    from core.models import ActionItem, Person

    person_obj = None
    if person_name:
        from slugify import slugify as _slugify
        person_obj = (
            Person.objects.filter(slug=_slugify(person_name)).first()
            or Person.objects.filter(name__icontains=person_name).first()
        )

    item = ActionItem.objects.create(
        description=description,
        due_date=due_date or None,
        person=person_obj,
        tags=tags,
    )
    person_str = f" — linked to {person_obj.name}" if person_obj else ""
    due_str = f" (due {due_date})" if due_date else ""
    return f"Action #{item.pk} created: {description}{due_str}{person_str}"


def update_action(
    action_id: int,
    status: str | None = None,
    description: str | None = None,
) -> str:
    from core.models import ActionItem
    try:
        item = ActionItem.objects.get(pk=action_id)
    except ActionItem.DoesNotExist:
        return f"No action item with ID {action_id}."

    changed = []
    if status:
        item.status = status
        changed.append(f"status → {status}")
    if description:
        item.description = description
        changed.append("description updated")
    item.save()

    if not changed:
        return f"Action #{action_id}: nothing to change."
    return f"Action #{action_id} updated: {', '.join(changed)}. Description: {item.description[:80]}"


def add_reading_item(url: str, tags: str = "", notes: str = "") -> str:
    from cli.commands.reading import save_reading_item
    return save_reading_item(url, tags=tags, notes=notes)


def search_reading_list(
    keyword: str | None = None,
    tag: str | None = None,
    status: str | None = None,
) -> str:
    from core.models import ReadingItem
    from django.db.models import Q

    qs = ReadingItem.objects.all()
    if status:
        qs = qs.filter(status=status)
    if tag:
        qs = qs.filter(tags__icontains=tag)
    if keyword:
        qs = qs.filter(
            Q(title__icontains=keyword)
            | Q(summary__icontains=keyword)
            | Q(notes__icontains=keyword)
            | Q(url__icontains=keyword)
        ).distinct()

    items = list(qs[:20])
    if not items:
        return "No reading list items found."

    lines = []
    for item in items:
        lines.append(f"[{item.status}] {item.title or item.url}")
        lines.append(f"  URL: {item.url}")
        lines.append(f"  Slug: {item.slug}  Tags: {item.tags or '—'}  Added: {item.created_at.date()}")
        if item.summary:
            lines.append(f"  Summary: {item.summary[:200]}")
        if item.notes:
            lines.append(f"  Notes: {item.notes[:150]}")
    return "\n".join(lines)


def update_user_context(content: str, append: bool = True) -> str:
    context_file = BASE_DIR / "notes" / "context.md"
    if append and context_file.exists():
        existing = context_file.read_text().rstrip()
        context_file.write_text(existing + "\n\n" + content.strip() + "\n")
        return f"Appended {len(content)} chars to context.md"
    else:
        context_file.write_text(content.strip() + "\n")
        return f"Replaced context.md ({len(content)} chars)"


def update_reading_item(
    slug: str,
    status: str | None = None,
    tags: str | None = None,
    notes: str | None = None,
) -> str:
    from core.models import ReadingItem
    from django.utils import timezone

    item = ReadingItem.objects.filter(slug=slug).first()
    if not item:
        return f"Reading item not found: {slug}"

    changes = []
    if status:
        item.status = status
        if status == "read" and not item.read_at:
            item.read_at = timezone.now()
        changes.append(f"status → {status}")
    if tags is not None:
        item.tags = tags
        changes.append(f"tags → {tags or '(cleared)'}")
    if notes:
        item.notes = (item.notes + "\n\n" + notes).strip() if item.notes else notes
        changes.append("notes appended")

    if not changes:
        return "No changes specified."

    item.save()
    return f"Updated '{item.title or slug}': {', '.join(changes)}"


# Default calendars to query
_WORK_CALENDARS = ["Calendar", "Shawn Zamechek", "Office Hours", "Family"]


def get_calendar_events(
    date_from: str | None = None,
    date_to: str | None = None,
    calendars: list[str] | None = None,
    keyword: str | None = None,
) -> str:
    from datetime import date as _date, timedelta

    today = _date.today()

    try:
        start = _date.fromisoformat(date_from) if date_from else today
    except ValueError:
        return f"Invalid date_from: {date_from!r}. Use YYYY-MM-DD."
    try:
        end = _date.fromisoformat(date_to) if date_to else today + timedelta(days=7)
    except ValueError:
        return f"Invalid date_to: {date_to!r}. Use YYYY-MM-DD."

    cal_list = calendars if calendars else _WORK_CALENDARS

    ical = shutil.which("icalBuddy") or "/opt/homebrew/bin/icalBuddy"
    if not shutil.which(ical) and not Path(ical).exists():
        return "icalBuddy not found. Install with: brew install ical-buddy"

    # -b ""     : no bullet prefix
    # -nc       : no color codes
    # -iep      : include only these properties
    # -ic       : limit to these calendar names
    # -df "%Y-%m-%d" : ISO date format so we get consistent output
    calendars_arg = ",".join(cal_list)
    cmd = [
        ical,
        "-b", "",
        "-sc",           # separate events by calendar (shows calendar name as section header)
        "-iep", "title,datetime,location,attendees",
        "-df", "%Y-%m-%d",
        "-ic", calendars_arg,
        f"eventsFrom:{start.isoformat()}",
        f"to:{end.isoformat()}",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

    if result.returncode != 0:
        return f"Calendar error: {result.stderr.strip()}"

    raw = result.stdout.strip()
    if not raw:
        suffix = f" matching '{keyword}'" if keyword else ""
        return f"No events{suffix} from {start.isoformat()} to {end.isoformat()}."

    # Apply keyword filter line-by-line (filter out event blocks that don't match)
    if keyword:
        kw = keyword.lower()
        filtered_blocks = []
        current: list[str] = []
        for line in raw.splitlines():
            if line and not line.startswith(" "):
                # New event title
                if current:
                    block = "\n".join(current)
                    if kw in block.lower():
                        filtered_blocks.append(block)
                current = [line]
            else:
                current.append(line)
        if current:
            block = "\n".join(current)
            if kw in block.lower():
                filtered_blocks.append(block)
        if not filtered_blocks:
            return f"No events matching '{keyword}' from {start.isoformat()} to {end.isoformat()}."
        raw = "\n".join(filtered_blocks)

    header = f"Calendar — {start.isoformat()} to {end.isoformat()}"
    return f"{header}\n\n{raw}"


def apply_wiki_links(file: str | None = None, min_length: int = 4) -> str:
    """Scan notes: add [[wiki-links]] for known entities, remove broken ones."""
    import re
    from cli.commands.link import _build_entity_map, _insert_links, _strip_broken_links
    from cli.paths import PROVENANCE_HOME as BASE_DIR

    entities = {k: v for k, v in _build_entity_map().items() if len(k) >= min_length}

    if file:
        p = BASE_DIR / "notes" / file if not file.startswith("/") else BASE_DIR / file
        if not p.exists():
            return f"File not found: {file}"
        files = [p]
    else:
        notes_dir = BASE_DIR / "notes"
        files = sorted(notes_dir.rglob("*.md")) if notes_dir.exists() else []

    if not files:
        return "No notes files found."

    links_added = 0
    links_removed = 0
    files_changed = 0

    for path in files:
        original = path.read_text()

        # Step 1: remove broken links (deleted people, old slugs, etc.)
        cleaned = _strip_broken_links(original)

        # Step 2: insert links for known entities
        updated = _insert_links(cleaned, entities)

        if updated == original:
            continue

        before = len(re.findall(r"\[\[", original))
        after = len(re.findall(r"\[\[", updated))
        diff = after - before
        if diff > 0:
            links_added += diff
        else:
            links_removed += abs(diff)

        path.write_text(updated)
        files_changed += 1

    if files_changed == 0:
        return "No changes needed — links are up to date."

    from cli.indexer import index_notes
    index_notes()

    parts = []
    if links_added:
        parts.append(f"added {links_added} link(s)")
    if links_removed:
        parts.append(f"removed {links_removed} broken link(s)")
    scope = f"notes/{file}" if file else "all notes"
    return f"Updated {files_changed} file(s) in {scope}: {', '.join(parts)}."


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

TOOL_FN = {
    "get_today": get_today,
    "get_daily_summary": get_daily_summary,
    "log_daily": log_daily,
    "append_to_daily_summary": append_to_daily_summary,
    "search_meetings": search_meetings,
    "get_meeting_notes": get_meeting_notes,
    "add_meeting": add_meeting,
    "delete_meeting": delete_meeting,
    "search_documents": search_documents,
    "get_document": get_document,
    "get_note": get_note,
    "search_people": search_people,
    "search_actions": search_actions,
    "search_notes": search_notes,
    "update_user_context": update_user_context,
    "add_reading_item": add_reading_item,
    "search_reading_list": search_reading_list,
    "update_reading_item": update_reading_item,
    "get_calendar_events": get_calendar_events,
    "add_action": add_action,
    "update_action": update_action,
    "add_person": add_person,
    "update_meeting": update_meeting,
    "update_person": update_person,
    "append_to_meeting_notes": append_to_meeting_notes,
    "write_note_file": write_note_file,
    "apply_wiki_links": apply_wiki_links,
}


def run_tool(name: str, arguments: dict) -> str:
    fn = TOOL_FN.get(name)
    if not fn:
        return f"Unknown tool: {name}"
    try:
        return fn(**arguments)
    except Exception as e:
        return f"Tool error ({name}): {e}"
