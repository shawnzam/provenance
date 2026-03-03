import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from cli.paths import PROVENANCE_HOME as BASE_DIR

console = Console()
err = Console(stderr=True)

SYSTEM_PROMPT = (
    "You are a knowledgeable assistant helping the user manage their professional relationships "
    "and work context. You will be given structured data (people, meetings, notes, action items) "
    "from the user's personal CRM. Answer in a clear, concise, and professional tone."
)

def _ask_system_prompt() -> str:
    from datetime import date
    today = date.today().strftime("%A, %B %d, %Y")

    base = (
        f"You are a knowledgeable assistant with access to the user's personal CRM, notes, and live calendar. "
        f"Today's date is {today}. "
        f"You have access to the following tools:\n"
        f"- search_meetings: logged meetings in the CRM database\n"
        f"- get_calendar_events: live Outlook calendar via macOS Calendar (use this for 'what's on my calendar', 'what do I have today/this week', scheduling questions)\n"
        f"- search_people, search_notes, search_actions, get_meeting_notes: CRM and notes\n"
        f"For any question about schedule, availability, or upcoming events, always call get_calendar_events. "
        f"For questions about past meetings or meeting notes, use search_meetings. "
        f"Answer based on the provided context. If the context doesn't contain enough information, say so clearly. "
        f"Be concise and professional."
    )

    context_file = BASE_DIR / "notes" / "context.md"
    if context_file.exists():
        ctx = context_file.read_text().strip()
        if ctx:
            base += f"\n\n## Personal context\n{ctx}"

    return base


def ai(
    instruction: list[str] = typer.Argument(..., help="What to do with the piped context — no quotes needed"),
):
    """Send piped context + instruction to the configured AI provider."""
    # Read context from stdin if available
    context = ""
    if not sys.stdin.isatty():
        context = sys.stdin.read().strip()

    instruction = " ".join(instruction).strip()

    if not context and not instruction:
        err.print("[red]Provide an instruction and optionally pipe in context.[/red]")
        err.print("Example: provenance people tom-sever meetings --json | provenance ai \"write a bio\"")
        raise typer.Exit(1)

    user_message = instruction
    if context:
        user_message = f"Context:\n\n{context}\n\n---\n\nInstruction: {instruction}"

    try:
        from ai.registry import get_provider
        provider = get_provider()
        result = provider.complete(system=SYSTEM_PROMPT, user=user_message)
        console.print(result, style="bright_green")
    except RuntimeError as e:
        err.print(f"[red]Configuration error:[/red] {e}")
        raise typer.Exit(1)


_STOP_WORDS = {
    "what", "who", "when", "where", "why", "how", "do", "does", "did", "i",
    "know", "about", "tell", "me", "my", "can", "you", "is", "are", "was",
    "were", "have", "has", "had", "the", "a", "an", "of", "to", "in", "on",
    "at", "for", "with", "and", "or", "any", "all", "there",
}


def _keywords(question: str) -> str:
    """Strip question/stop words and return the remaining content terms."""
    words = question.rstrip("?!. ").split()
    content = [w for w in words if w.lower() not in _STOP_WORDS]
    return " ".join(content) if content else question


_MAX_HISTORY_CHARS = 80_000  # ~20k tokens — trim oldest exchanges beyond this


def _trim_history(messages: list[dict]) -> list[dict]:
    """Drop oldest user/assistant exchanges if history is getting large."""
    total = sum(len(str(m.get("content", ""))) for m in messages)
    while total > _MAX_HISTORY_CHARS and len(messages) > 1:
        # Remove the oldest exchange (may be 1–3 messages: user + tool results + assistant)
        dropped = messages.pop(0)
        total -= len(str(dropped.get("content", "")))
    return messages


def _tool_label(name: str, arguments: dict) -> str:
    """Return the equivalent provenance CLI command for a tool call."""
    a = arguments

    if name == "search_meetings":
        parts = ["provenance meetings list"]
        if "date" in a:
            parts += ["--after", a["date"], "--before", a["date"]]
        if "date_from" in a:
            parts += ["--after", a["date_from"]]
        if "date_to" in a:
            parts += ["--before", a["date_to"]]
        if "person" in a:
            parts += ["--person", a["person"]]
        if "keyword" in a:
            parts += ["--keyword", a["keyword"]]
        return " ".join(parts)

    if name == "get_meeting_notes":
        return f"provenance meetings show {a.get('slug', '')}"

    if name == "search_people":
        return f"provenance search {a.get('keyword', '')}"

    if name == "search_actions":
        parts = ["provenance actions list"]
        if "status" in a:
            parts += ["--status", a["status"]]
        if "keyword" in a:
            parts += ["--keyword", a["keyword"]]
        return " ".join(parts)

    if name == "search_documents":
        parts = ["provenance docs list"]
        if "keyword" in a:
            parts += ["--keyword", a["keyword"]]
        if "tag" in a:
            parts += ["--tag", a["tag"]]
        return " ".join(parts)

    if name == "get_document":
        return f"provenance docs show {a.get('slug', '')}"

    if name == "search_notes":
        mode = a.get("mode", "regex")
        ctx = a.get("context_lines", 3)
        suffix = f"  # {mode}" + (f", -C {ctx}" if ctx != 3 else "")
        return f"provenance search {a.get('query', '')}{suffix}"

    if name == "get_today":
        return "provenance doctor  # checking today's date"

    if name == "add_meeting":
        parts = ["provenance meetings add", f"--title \"{a.get('title', '')}\"", f"--date {a.get('date', '')}"]
        names = a.get("attendee_names", [])
        if names:
            parts.append(f"# attendees: {', '.join(names)}")
        return " ".join(parts)

    if name == "append_to_meeting_notes":
        return f"provenance meetings append {a.get('slug', '')}  # {len(a.get('content',''))} chars"

    if name == "write_note_file":
        return f"provenance note write {a.get('filename', '')}"

    if name == "update_meeting":
        parts = [f"provenance meetings update {a.get('slug', '')}"]
        if a.get("add_attendees"):
            parts.append(f"# add: {', '.join(a['add_attendees'])}")
        if a.get("remove_attendees"):
            parts.append(f"# remove: {', '.join(a['remove_attendees'])}")
        if a.get("set_attendees"):
            parts.append(f"# set attendees: {', '.join(a['set_attendees'])}")
        return " ".join(parts)

    if name == "add_person":
        parts = [f"provenance people add \"{a.get('name', '')}\""]
        if a.get('role'):
            parts.append(f"--role \"{a['role']}\"")
        if a.get('org'):
            parts.append(f"--org \"{a['org']}\"")
        return " ".join(parts)

    if name == "update_person":
        parts = [f"provenance people update {a.get('slug', '')}"]
        if a.get('role'):
            parts.append(f"--role \"{a['role']}\"")
        return " ".join(parts)

    if name == "delete_meeting":
        return f"provenance meetings delete {a.get('slug', '')}"

    if name == "add_action":
        desc = a.get('description', '')[:60]
        due = f" --due {a['due_date']}" if a.get('due_date') else ""
        person = f" --person \"{a['person_name']}\"" if a.get('person_name') else ""
        return f"provenance actions add \"{desc}\"{due}{person}"

    if name == "get_calendar_events":
        parts = ["calendar"]
        if a.get("date_from"):
            parts.append(a["date_from"])
        if a.get("date_to"):
            parts.append(f"→ {a['date_to']}")
        if a.get("keyword"):
            parts.append(f"'{a['keyword']}'")
        return " ".join(parts)

    if name == "update_action":
        parts = [f"provenance actions update {a.get('action_id', '')}"]
        if a.get('status'):
            parts.append(f"--status {a['status']}")
        return " ".join(parts)

    if name == "add_reading_item":
        url = a.get("url", "")
        tags = f" --tags \"{a['tags']}\"" if a.get("tags") else ""
        return f"provenance reading add {url}{tags}"

    if name == "update_user_context":
        mode = "append" if a.get("append", True) else "replace"
        return f"# update context.md ({mode}, {len(a.get('content', ''))} chars)"

    if name == "update_reading_item":
        parts = [f"provenance reading"]
        if a.get("status") == "read":
            parts = [f"provenance reading done {a.get('slug', '')}"]
        else:
            parts = [f"provenance reading update {a.get('slug', '')}"]
            if a.get("status"):
                parts.append(f"--status {a['status']}")
        return " ".join(parts)

    if name == "search_reading_list":
        parts = ["provenance reading list"]
        if a.get("query"):
            parts.append(f"# search: {a['query']}")
        if a.get("status"):
            parts += ["--status", a["status"]]
        if a.get("tag"):
            parts += ["--tag", a["tag"]]
        return " ".join(parts)

    return f"provenance {name} {a}"


def ask_agent(
    question: str,
    history: list[dict] | None = None,
) -> list[dict]:
    """Run the tool-use agent loop for a question.

    history: shared message list for multi-turn sessions (mutated in place).
    Returns the updated history so callers can persist it.
    """
    from cli.tools import TOOLS, run_tool

    if history is None:
        history = []

    history.append({"role": "user", "content": question})
    _trim_history(history)

    try:
        from ai.registry import get_provider
        provider = get_provider()
    except RuntimeError as e:
        err.print(f"[red]Configuration error:[/red] {e}")
        return history

    status = err.status("[dim]thinking…[/dim]")
    status.start()

    for _round in range(6):
        text_out, tool_calls = provider.chat_with_tools(
            system=_ask_system_prompt(),
            messages=history,
            tools=TOOLS,
        )

        if not tool_calls:
            status.stop()
            if text_out:
                console.print(text_out, style="bright_green")
                history.append({"role": "assistant", "content": text_out})
            return history

        # Append assistant turn with tool calls
        history.append({
            "role": "assistant",
            "tool_calls": [tc["_raw"] for tc in tool_calls],
        })

        # Each tool call: stop spinner → print permanently → restart spinner
        for tc in tool_calls:
            label = _tool_label(tc["name"], tc["arguments"])
            status.stop()
            err.print(f"[dim]→ {label}[/dim]")
            status.start()
            result = run_tool(tc["name"], tc["arguments"])
            history.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result,
            })

    status.stop()
    err.print("[yellow]Reached max tool-call rounds.[/yellow]")
    final = provider.complete(system=_ask_system_prompt(), user=question)
    console.print(final, style="bright_green")
    history.append({"role": "assistant", "content": final})
    return history


def ask(
    text: list[str] = typer.Argument(..., help="Question — no quotes needed"),
):
    """Ask a question — AI decides which tools to call, then answers.

    No quotes needed:\n
      provenance ask who works with amy hallow\n
      provenance ask tell me about my meetings today\n
      provenance ask what is the Jevons paradox
    """
    # When piped: use stdin as context + args as instruction (no tool loop)
    if not sys.stdin.isatty():
        piped_context = sys.stdin.read().strip()
        if piped_context:
            instruction = " ".join(text).strip()
            if not instruction:
                err.print("[red]Provide an instruction after the pipe.[/red]")
                err.print("Example: provenance search hyperscaler | provenance ask summarize this")
                raise typer.Exit(1)
            user_message = f"Context:\n\n{piped_context}\n\n---\n\nInstruction: {instruction}"
            try:
                from ai.registry import get_provider
                result = get_provider().complete(system=_ask_system_prompt(), user=user_message)
                console.print(result, style="bright_green")
            except RuntimeError as e:
                err.print(f"[red]Configuration error:[/red] {e}")
                raise typer.Exit(1)
            return

    ask_agent(" ".join(text).strip())


PROOF_SYSTEM_PROMPT = (
    "You are a professional editor. The user will give you text to proofread. "
    "Fix spelling, grammar, punctuation, and clarity issues. "
    "Return ONLY the corrected text — no explanations, no commentary, no markdown fences. "
    "Preserve the original structure, tone, and formatting."
)


def proof(
    text: Optional[list[str]] = typer.Argument(None, help="Text to proofread — no quotes needed"),
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="Path to a file to proofread"),
    write: bool = typer.Option(False, "--write", "-w", help="Write proofread content back to the file (requires --file)"),
):
    """Proofread text via AI — pass inline, from a file, or pipe it in.

    Inline:\n
      provenance proof this is a sentance with bad grammer\n\n
    File (print result):\n
      provenance proof --file notes/meetings/standup.md\n\n
    File (write back in place):\n
      provenance proof --file notes/meetings/standup.md --write\n\n
    Piped:\n
      cat somefile.md | provenance proof
    """
    if write and not file:
        err.print("[red]--write requires --file.[/red]")
        raise typer.Exit(1)

    content = ""

    if text:
        joined = " ".join(text).strip()
        # Auto-detect file path — single token with "/" or ".md" extension
        maybe_path = Path(joined) if len(text) == 1 else None
        if maybe_path and (maybe_path.exists() or joined.endswith(".md")):
            file = maybe_path
        else:
            content = joined
    if not content and file:
        if not file.exists():
            err.print(f"[red]File not found: {file}[/red]")
            raise typer.Exit(1)
        content = file.read_text().strip()
    if not content and not sys.stdin.isatty():
        content = sys.stdin.read().strip()

    if not content:
        err.print("[red]Provide text, a --file, or pipe content in.[/red]")
        err.print("  provenance proof this sentence has erors")
        err.print("  provenance proof --file notes/meetings/standup.md")
        err.print("  cat draft.md | provenance proof")
        raise typer.Exit(1)

    try:
        from ai.registry import get_provider
        provider = get_provider()
        result = provider.complete(system=PROOF_SYSTEM_PROMPT, user=content)
    except RuntimeError as e:
        err.print(f"[red]Configuration error:[/red] {e}")
        raise typer.Exit(1)

    if write and file:
        file.write_text(result + "\n")
        err.print(f"[green]Written[/green] {file}")
    else:
        console.print(result, style="bright_green")


def _parse_temporal(words: list[str]):
    """Detect temporal phrases and return (date_filter_kwargs, remaining_words).

    Handles: today, yesterday, tomorrow, this week, last week,
             this month, last month, Monday–Sunday (nearest past).
    Returns a dict suitable for Meeting.objects.filter(**kwargs).
    """
    from datetime import date, timedelta
    today = date.today()
    text = " ".join(words).lower()

    WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

    date_filter: dict = {}
    remove: set[str] = set()

    if "this week" in text:
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        date_filter = {"date__gte": monday, "date__lte": sunday}
        remove = {"this", "week"}
    elif "last week" in text:
        monday = today - timedelta(days=today.weekday() + 7)
        sunday = monday + timedelta(days=6)
        date_filter = {"date__gte": monday, "date__lte": sunday}
        remove = {"last", "week"}
    elif "this month" in text:
        date_filter = {"date__year": today.year, "date__month": today.month}
        remove = {"this", "month"}
    elif "last month" in text:
        first = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        last = today.replace(day=1) - timedelta(days=1)
        date_filter = {"date__gte": first, "date__lte": last}
        remove = {"last", "month"}
    elif "yesterday" in text:
        date_filter = {"date": today - timedelta(days=1)}
        remove = {"yesterday"}
    elif "tomorrow" in text:
        date_filter = {"date": today + timedelta(days=1)}
        remove = {"tomorrow"}
    elif "today" in text:
        date_filter = {"date": today}
        remove = {"today"}
    else:
        for i, wd in enumerate(WEEKDAYS):
            if wd in text:
                days_ago = (today.weekday() - i) % 7 or 7
                date_filter = {"date": today - timedelta(days=days_ago)}
                remove = {wd}
                break

    remaining = [w for w in words if w.lower() not in remove]
    return date_filter, remaining


def _person_q(word: str):
    from django.db.models import Q
    return (
        Q(name__icontains=word) | Q(role__icontains=word) | Q(org__icontains=word)
        | Q(notes__icontains=word) | Q(relationship_context__icontains=word)
    )


def _meeting_q(word: str):
    from django.db.models import Q
    return (
        Q(title__icontains=word) | Q(summary__icontains=word)
        | Q(attendees__name__icontains=word)
    )


def _db_context(query: str) -> str:
    """Return a compact text summary of DB matches for the query."""
    try:
        from core.models import Person, Meeting, ActionItem, Document
        from django.db.models import Q
        import functools, operator

        words = query.strip().split()
        if not words:
            return ""

        # Extract temporal phrases and get a date filter for meetings
        date_filter, content_words = _parse_temporal(words)

        # Fall back to all words for text search if nothing left after stripping temporal words
        search_words = content_words if content_words else words

        # OR across all words so "amy hallow" finds records matching either word
        person_q = functools.reduce(operator.or_, (_person_q(w) for w in search_words))
        action_q = functools.reduce(operator.or_, (Q(description__icontains=w) for w in search_words))

        # Meetings: date filter takes priority; supplement with text filter if no date match
        if date_filter:
            meetings = list(Meeting.objects.filter(**date_filter).distinct().order_by("date"))
            if not meetings and content_words:
                # Date matched nothing — fall back to text
                meeting_q = functools.reduce(operator.or_, (_meeting_q(w) for w in search_words))
                meetings = list(Meeting.objects.filter(meeting_q).distinct())
        else:
            meeting_q = functools.reduce(operator.or_, (_meeting_q(w) for w in search_words))
            meetings = list(Meeting.objects.filter(meeting_q).distinct())

        people = list(Person.objects.filter(person_q).distinct())
        actions = list(ActionItem.objects.filter(action_q
        ).select_related("person", "meeting"))

        lines: list[str] = []
        for p in people:
            lines.append(f"Person: {p.name} ({p.slug}) — {p.role or ''} at {p.org or ''}")
            if p.relationship_context:
                lines.append(f"  Context: {p.relationship_context}")
            if p.notes:
                lines.append(f"  Notes: {p.notes[:200]}")
        for m in meetings:
            attendees = ", ".join(a.name for a in m.attendees.all())
            lines.append(f"Meeting: {m.title} on {m.date} (attendees: {attendees})")
            if m.summary:
                lines.append(f"  Summary: {m.summary}")
        for a in actions:
            lines.append(f"Action [{a.status}]: {a.description}")

        return "\n".join(lines)
    except Exception:
        return ""


