import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from cli.completions import complete_person_slug, complete_meeting_slug, complete_attendees, complete_tags

app = typer.Typer(help="Manage meetings.", no_args_is_help=True)
console = Console()
err = Console(stderr=True)

from cli.paths import NOTES_DIR as _NOTES_BASE, PROVENANCE_HOME
NOTES_DIR = _NOTES_BASE / "meetings"


def _get_meeting(slug: str):
    from core.models import Meeting
    try:
        return Meeting.objects.get(slug=slug)
    except Meeting.DoesNotExist:
        err.print(f"[red]No meeting found with slug '{slug}'.[/red]")
        err.print("Run [bold]provenance meetings list[/bold] to see available slugs.")
        raise typer.Exit(1)


@app.command("list")
def list_meetings(
    person: Optional[str] = typer.Option(None, "--person", "-p", help="Filter by person name or slug", autocompletion=complete_person_slug),
    after: Optional[str] = typer.Option(None, "--after", help="Filter meetings after date (YYYY-MM-DD)"),
    before: Optional[str] = typer.Option(None, "--before", help="Filter meetings before date (YYYY-MM-DD)"),
    json_out: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List meetings, optionally filtered."""
    from core.models import Meeting, Person

    qs = Meeting.objects.all()

    if person:
        try:
            p = Person.objects.get(slug=person)
        except Person.DoesNotExist:
            # Try name match
            p_qs = Person.objects.filter(name__icontains=person)
            if not p_qs.exists():
                err.print(f"[red]No person matching '{person}'.[/red]")
                raise typer.Exit(1)
            p = p_qs.first()
        qs = qs.filter(attendees=p)

    if after:
        qs = qs.filter(date__gte=after)
    if before:
        qs = qs.filter(date__lte=before)

    meetings = list(qs.order_by("-date"))

    if json_out:
        typer.echo(json.dumps([m.to_dict() for m in meetings], indent=2))
        return

    if not meetings:
        console.print("[dim]No meetings found.[/dim]")
        return

    table = Table(show_header=True, header_style="bold blue")
    table.add_column("Date")
    table.add_column("Title")
    table.add_column("Attendees")
    table.add_column("Slug")

    for m in meetings:
        attendees = ", ".join(p.name for p in m.attendees.all())
        table.add_row(str(m.date), m.title, attendees, m.slug)

    console.print(table)


@app.command("add")
def add_meeting(
    text: Optional[list[str]] = typer.Argument(None, help="Freeform description — AI extracts title, date, attendees"),
    title: Optional[str] = typer.Option(None, "--title", "-t", help="Meeting title"),
    date: Optional[str] = typer.Option(None, "--date", "-d", help="Date (YYYY-MM-DD)"),
    attendees: str = typer.Option("", "--attendees", "-a", help="Comma-separated person slugs", autocompletion=complete_attendees),
    summary: str = typer.Option("", "--summary", "-s", help="Brief summary"),
    tags: str = typer.Option("", "--tags", help="Comma-separated tags", autocompletion=complete_tags),
    json_out: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Add a meeting — structured flags or freeform text (AI extracts details).

    Structured:\n
      provenance meetings add --title "Team standup" --date 2026-03-10 --attendees tom-sever\n\n
    Freeform:\n
      provenance meetings add headed into an ra manager meeting with Alec and Nancy
    """
    from core.models import Meeting, Person
    from slugify import slugify
    from cli.text_utils import check
    from datetime import date as _date

    raw = " ".join(text).strip() if text else ""

    # Freeform path — no --title provided, extract from text via AI
    if not title and raw:
        extracted = _extract_meeting(raw)
        title = title or extracted.get("title", raw[:60])
        date = date or extracted.get("date") or _date.today().isoformat()
        summary = summary or extracted.get("summary", "")
        # Merge AI-extracted attendee names with any --attendees slugs provided
        ai_names = extracted.get("attendee_names", [])
        attendee_objects = _resolve_attendees_mixed(attendees, ai_names)
    elif not title:
        err.print("[red]Provide a description or use --title.[/red]")
        err.print("  provenance meetings add headed into standup with Tom")
        err.print("  provenance meetings add --title 'Standup' --date 2026-03-10")
        raise typer.Exit(1)
    else:
        date = date or _date.today().isoformat()
        title = check(title)
        summary = check(summary)
        attendee_objects = _resolve_attendee_slugs(attendees)

    slug = slugify(f"{date}-{title}")
    if Meeting.objects.filter(slug=slug).exists():
        err.print(f"[red]A meeting with slug '{slug}' already exists.[/red]")
        raise typer.Exit(1)

    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    notes_filename = f"{slug}.md"
    notes_path = NOTES_DIR / notes_filename
    attendee_names_str = ", ".join(p.name for p in attendee_objects)
    summary_section = f"{summary}\n\n" if summary else ""
    notes_path.write_text(
        f"# {title}\n\n"
        f"**Date:** {date}  \n"
        f"**Attendees:** {attendee_names_str}  \n\n"
        f"## Notes\n\n{summary_section}"
        f"## Action Items\n\n\n"
    )

    meeting = Meeting.objects.create(
        title=title,
        date=date,
        summary=summary,
        notes_file=f"notes/meetings/{notes_filename}",
        tags=tags,
    )
    meeting.attendees.set(attendee_objects)

    from cli.indexer import index_notes
    index_notes()

    if json_out:
        typer.echo(json.dumps(meeting.to_dict(), indent=2))
        return

    console.print(f"[green]Added[/green] {meeting.title} ([bold]{meeting.slug}[/bold])")
    if attendee_names_str:
        console.print(f"  Attendees: {attendee_names_str}")
    console.print(f"  Notes: [dim]{meeting.notes_file}[/dim]")


def _extract_meeting(raw: str) -> dict:
    """Use AI to extract title, date, attendee names from freeform text."""
    import json as _json
    from datetime import date as _date

    system = f"""\
Extract meeting details from a freeform description.
Today's date is {_date.today().isoformat()}.
Return ONLY valid JSON:
{{
  "title": "short meeting title",
  "date": "YYYY-MM-DD",
  "attendee_names": ["Full Name", ...],
  "summary": "brief summary or empty string"
}}
Infer date from context (today, tomorrow, yesterday, day of week).
Default to today if no date mentioned.\
"""
    try:
        from ai.registry import get_provider
        response = get_provider().complete(system=system, user=raw)
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(cleaned.splitlines()[1:])
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3].strip()
        return _json.loads(cleaned)
    except Exception:
        return {}


def _resolve_attendee_slugs(attendees_str: str) -> list:
    """Resolve comma-separated slugs to Person objects."""
    from core.models import Person
    objects = []
    for s in [a.strip() for a in attendees_str.split(",") if a.strip()]:
        try:
            objects.append(Person.objects.get(slug=s))
        except Person.DoesNotExist:
            err.print(f"[red]No person with slug '{s}'.[/red]")
            raise typer.Exit(1)
    return objects


def _name_score(query: str, candidate: str) -> float:
    """Score how well query matches candidate name (0–1).
    Handles: exact, prefix (≥4 chars), single-word-within, fuzzy."""
    import difflib
    q, c = query.lower().strip(), candidate.lower().strip()
    if q == c:
        return 1.0
    # Candidate starts with query (e.g. "Margaret" → "Margaret Troncelliti")
    if c.startswith(q) and len(q) >= 4:
        return 0.85
    # Query is an exact word within candidate (e.g. "Botto" → "Robert Botto")
    if len(q) >= 4 and q in c.split():
        return 0.80
    return difflib.SequenceMatcher(None, q, c).ratio()


def _resolve_attendees_mixed(attendees_str: str, ai_names: list) -> list:
    """Resolve AI-extracted names + explicit slugs to Person objects.
    Fuzzy-matches against existing people and prompts to confirm near-matches.
    Creates stub records only when nothing close enough is found."""
    import sys
    from core.models import Person
    from slugify import slugify

    piped = not sys.stdin.isatty()
    objects = []
    seen_slugs: set[str] = set()

    # Explicit slugs take priority
    for s in [a.strip() for a in attendees_str.split(",") if a.strip()]:
        try:
            p = Person.objects.get(slug=s)
            if p.slug not in seen_slugs:
                objects.append(p)
                seen_slugs.add(p.slug)
        except Person.DoesNotExist:
            err.print(f"[red]No person with slug '{s}'.[/red]")
            raise typer.Exit(1)

    # Build lookup table from all existing people
    all_people = list(Person.objects.values_list("slug", "name"))
    slug_for_name = {name: slug for slug, name in all_people}

    # First pass: score every AI name against existing people
    suggestions: list[tuple[str, str, str]] = []   # (ai_name, matched_name, matched_slug)
    unmatched: list[str] = []

    for name in ai_names:
        slug = slugify(name)
        if slug in seen_slugs:
            continue

        # Exact slug match — accept silently, no prompt needed
        try:
            p = Person.objects.get(slug=slug)
            objects.append(p)
            seen_slugs.add(p.slug)
            continue
        except Person.DoesNotExist:
            pass

        # Score every existing person; take the best
        scored = sorted(
            ((existing, _name_score(name, existing)) for existing in slug_for_name
             if slug_for_name[existing] not in seen_slugs),
            key=lambda x: x[1],
            reverse=True,
        )
        best_name, best_score = scored[0] if scored else (None, 0.0)

        if best_score >= 0.5 and best_name:
            suggestions.append((name, best_name, slug_for_name[best_name]))
        else:
            unmatched.append(name)

    # Prompt: accept all at once, or go one-by-one
    if suggestions and not piped:
        console.print("\n  [dim]Suggested matches:[/dim]")
        for ai_name, match_name, _ in suggestions:
            console.print(f"    [yellow]{ai_name}[/yellow] → [bold]{match_name}[/bold]")
        console.print()
        accept_all = typer.confirm("  Accept all?", default=True)
        console.print()
    else:
        accept_all = True  # piped: auto-accept

    for ai_name, match_name, matched_slug in suggestions:
        if accept_all:
            accepted = True
        else:
            accepted = typer.confirm(f"  '{ai_name}' → {match_name}?", default=True)

        if accepted:
            p = Person.objects.get(slug=matched_slug)
            objects.append(p)
            seen_slugs.add(matched_slug)
        else:
            # User rejected — create stub
            stub_slug = slugify(ai_name)
            p, created = Person.objects.get_or_create(slug=stub_slug, defaults={"name": ai_name})
            if created:
                console.print(f"[dim]Created stub[/dim] {ai_name} ([dim]{stub_slug}[/dim])")
            objects.append(p)
            seen_slugs.add(stub_slug)

    # Names with no close match — always create stubs
    for name in unmatched:
        slug = slugify(name)
        if slug not in seen_slugs:
            p, created = Person.objects.get_or_create(slug=slug, defaults={"name": name})
            if created:
                console.print(f"[dim]Created stub[/dim] {name} ([dim]{slug}[/dim])")
            objects.append(p)
            seen_slugs.add(slug)

    return objects


@app.command("show")
def show_meeting(
    slug: str = typer.Argument(..., help="Meeting slug", autocompletion=complete_meeting_slug),
    json_out: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show details for a meeting."""
    meeting = _get_meeting(slug)

    if json_out:
        typer.echo(json.dumps(meeting.to_dict(), indent=2))
        return

    console.print(f"\n[bold]{meeting.title}[/bold]  [dim]{meeting.slug}[/dim]")
    console.print(f"  Date: {meeting.date}")
    attendees = ", ".join(p.name for p in meeting.attendees.all())
    if attendees:
        console.print(f"  Attendees: {attendees}")
    if meeting.summary:
        console.print(f"\n[dim]Summary:[/dim] {meeting.summary}")
    if meeting.notes_file:
        notes_path = PROVENANCE_HOME / meeting.notes_file
        if notes_path.exists():
            console.print(f"\n[dim]Notes ({meeting.notes_file}):[/dim]")
            console.print(notes_path.read_text())
        else:
            console.print(f"\n[dim]Notes file:[/dim] {meeting.notes_file} [red](not found)[/red]")
    console.print()
