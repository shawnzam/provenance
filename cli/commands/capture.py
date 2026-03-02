import json
import sys
from datetime import date
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from cli.completions import complete_doc_or_file

console = Console()
err = Console(stderr=True)

from cli.paths import PROVENANCE_HOME as BASE_DIR

_EXTRACT_PEOPLE_SYSTEM = """\
You are a personal CRM assistant extracting people from an org chart or organizational document.

Extract every distinct person mentioned. For each person capture:
- Full name
- Role or job title
- Organization or department
- Email address if present
- Reporting structure or context (e.g. "Reports to Jane Smith", "Head of West Coast")

Return ONLY valid JSON:
{{
  "people": [
    {{
      "name": "Full Name",
      "role": "title or role (empty string if unknown)",
      "org": "organization or department (empty string if unknown)",
      "email": "email address (empty string if not present)",
      "relationship_context": "reporting structure or relevant context (empty string if unknown)",
      "notes": "any other relevant details (empty string if none)"
    }}
  ]
}}

Return ONLY the JSON object, no markdown fences or other text.\
"""

_EXTRACT_SYSTEM = """\
You are a personal CRM assistant. Extract structured data from a freeform note.

Return ONLY valid JSON with this structure (omit arrays that have no entries):
{{
  "people": [
    {{
      "name": "Full Name",
      "role": "job title or role (empty string if unknown)",
      "org": "organization (empty string if unknown)",
      "email": "email address (empty string if not mentioned)",
      "relationship_context": "how they know each other or relevant context (empty string if unknown)",
      "notes": "any other relevant details (empty string if none)"
    }}
  ],
  "meetings": [
    {{
      "title": "short descriptive title for this encounter",
      "date": "YYYY-MM-DD",
      "attendees": ["Full Name matching people array"],
      "summary": "brief summary of what happened or was discussed"
    }}
  ],
  "actions": [
    {{
      "description": "what needs to be done",
      "due_date": "YYYY-MM-DD or null",
      "person_name": "Full Name or null"
    }}
  ]
}}

Rules:
- Today's date is {today}.
- Use exact full names from "people" when listing meeting attendees.
- Create a meeting entry if the note describes an encounter, call, or meeting.
- Create action entries for any tasks, follow-ups, or commitments mentioned.
- Return ONLY the JSON object, no markdown fences or other text.\
"""


def note(
    text: list[str] = typer.Argument(None, help="Freeform note — no quotes needed. When piped, used as the title."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without saving"),
):
    """Capture a freeform note — AI extracts people, meetings, and actions automatically.

    When piped to, saves stdin as a named markdown note instead:\n
      provenance ask get def of Jevons paradox | provenance note Jevons Paradox\n
      provenance ask who is Amy Hallow | provenance note Amy Hallow profile\n\n
    Freeform capture:\n
      provenance note today I met Andy Dryer from OpenAI, our new account rep\n
      provenance note --yes call with Sarah tomorrow, need to send her the deck
    """
    piped = not sys.stdin.isatty()

    if piped:
        # Stdin mode: save content as a raw markdown note file
        content = sys.stdin.read().strip()
        if not content:
            err.print("[red]No content received from pipe.[/red]")
            raise typer.Exit(1)
        title = " ".join(text).strip() if text else None
        if not title:
            title = typer.prompt("Note title")
        _save_note(title, content, dry_run=dry_run)
        return

    raw = " ".join(text).strip() if text else ""

    if not raw:
        err.print("[red]Provide a note, or pipe content in and give a title.[/red]")
        err.print("  provenance note today I met Andy Dryer from OpenAI")
        err.print("  provenance ask ... | provenance note My Title")
        raise typer.Exit(1)

    console.print("[dim]Extracting structured data…[/dim]")

    try:
        from ai.registry import get_provider
        provider = get_provider()
        system = _EXTRACT_SYSTEM.format(today=date.today().isoformat())
        response = provider.complete(system=system, user=raw)
        # Strip markdown code fences if model wraps output anyway
        cleaned = response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            cleaned = "\n".join(lines[1:])
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3].strip()
        extracted = json.loads(cleaned)
    except json.JSONDecodeError:
        err.print("[red]AI returned invalid JSON. Try rephrasing the note.[/red]")
        raise typer.Exit(1)
    except RuntimeError as e:
        err.print(f"[red]AI error: {e}[/red]")
        raise typer.Exit(1)

    people = extracted.get("people", [])
    meetings = extracted.get("meetings", [])
    actions = extracted.get("actions", [])

    if not any([people, meetings, actions]):
        console.print("[yellow]Nothing to create — no structured data found in that note.[/yellow]")
        raise typer.Exit(0)

    _print_preview(people, meetings, actions)

    if dry_run:
        raise typer.Exit(0)

    if not yes:
        typer.confirm("\nCreate these records?", default=True, abort=True)

    # People first — build name→slug map for meeting attendee resolution
    slug_map: dict[str, str] = {}
    _create_people(people, slug_map)
    _create_meetings(meetings, slug_map)
    _create_actions(actions, slug_map)

    console.print("\n[bold green]Done.[/bold green]")


def _save_note(title: str, content: str, dry_run: bool = False):
    from slugify import slugify
    from datetime import date as _date

    slug = slugify(title)
    today = _date.today().isoformat()
    notes_dir = BASE_DIR / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    dest = notes_dir / f"{today}-{slug}.md"

    body = f"# {title}\n\n_{today}_\n\n---\n\n{content}\n"

    if dry_run:
        console.print(f"[dim]Would save to {dest.relative_to(BASE_DIR)}[/dim]")
        console.print(body[:400])
        return

    dest.write_text(body)
    console.print(f"[green]Saved[/green] {dest.relative_to(BASE_DIR)}")

    from cli.indexer import index_notes
    index_notes()


def _print_preview(people: list, meetings: list, actions: list):
    if people:
        console.print("\n[bold]People[/bold]")
        for p in people:
            line = f"  [bold]{p['name']}[/bold]"
            details = " — ".join(x for x in [p.get("role"), p.get("org")] if x)
            if details:
                line += f"  [dim]{details}[/dim]"
            console.print(line)
            if p.get("relationship_context"):
                console.print(f"    [dim]{p['relationship_context']}[/dim]")

    if meetings:
        console.print("\n[bold]Meetings[/bold]")
        for m in meetings:
            console.print(f"  [bold]{m['title']}[/bold]  [dim]{m.get('date', '')}[/dim]")
            attendees = ", ".join(m.get("attendees", []))
            if attendees:
                console.print(f"    Attendees: {attendees}")
            if m.get("summary"):
                console.print(f"    [dim]{m['summary']}[/dim]")

    if actions:
        console.print("\n[bold]Actions[/bold]")
        for a in actions:
            line = f"  {a['description']}"
            if a.get("due_date"):
                line += f"  [dim](due {a['due_date']})[/dim]"
            if a.get("person_name"):
                line += f"  [dim]→ {a['person_name']}[/dim]"
            console.print(line)


def _create_people(people: list, slug_map: dict):
    from core.models import Person
    from slugify import slugify

    for p in people:
        name = p["name"]
        slug = slugify(name)
        slug_map[name] = slug

        existing = Person.objects.filter(slug=slug).first()
        if existing:
            # Fill in any blank fields with new data — never overwrite existing
            changed = False
            for key, field in [
                ("role", "role"), ("org", "org"), ("email", "email"),
                ("relationship_context", "relationship_context"), ("notes", "notes"),
            ]:
                val = p.get(key, "")
                if val and not getattr(existing, field):
                    setattr(existing, field, val)
                    changed = True
            if changed:
                existing.save()
                console.print(f"[cyan]Updated[/cyan]  {name} ([dim]{slug}[/dim])")
            else:
                console.print(f"[dim]Exists[/dim]   {name} ([dim]{slug}[/dim])")
        else:
            Person.objects.create(
                name=name,
                slug=slug,
                role=p.get("role", ""),
                org=p.get("org", ""),
                email=p.get("email", ""),
                relationship_context=p.get("relationship_context", ""),
                notes=p.get("notes", ""),
            )
            console.print(f"[green]Created[/green]  {name} ([dim]{slug}[/dim])")


def _create_meetings(meetings: list, slug_map: dict):
    from core.models import Meeting, Person
    from slugify import slugify

    notes_dir = BASE_DIR / "notes" / "meetings"
    notes_dir.mkdir(parents=True, exist_ok=True)

    for m in meetings:
        title = m["title"]
        date_str = m.get("date") or date.today().isoformat()
        slug = slugify(f"{date_str}-{title}")

        if Meeting.objects.filter(slug=slug).exists():
            console.print(f"[dim]Exists[/dim]   {title} ([dim]{slug}[/dim])")
            continue

        attendee_objects = []
        for name in m.get("attendees", []):
            person_slug = slug_map.get(name)
            if person_slug:
                p = Person.objects.filter(slug=person_slug).first()
                if p:
                    attendee_objects.append(p)

        notes_filename = f"{slug}.md"
        notes_path = notes_dir / notes_filename
        attendee_names_str = ", ".join(p.name for p in attendee_objects)
        summary = m.get("summary", "")
        notes_path.write_text(
            f"# {title}\n\n"
            f"**Date:** {date_str}  \n"
            f"**Attendees:** {attendee_names_str}  \n\n"
            f"## Notes\n\n{summary}\n\n"
            f"## Action Items\n\n\n"
        )

        meeting = Meeting.objects.create(
            title=title,
            date=date_str,
            summary=summary,
            notes_file=f"notes/meetings/{notes_filename}",
        )
        meeting.attendees.set(attendee_objects)
        console.print(f"[green]Created[/green]  {title} ([dim]{slug}[/dim])")

    from cli.indexer import index_notes
    index_notes()


def _create_actions(actions: list, slug_map: dict):
    from core.models import ActionItem, Person

    for a in actions:
        person_obj = None
        person_name = a.get("person_name")
        if person_name:
            person_slug = slug_map.get(person_name)
            if person_slug:
                person_obj = Person.objects.filter(slug=person_slug).first()

        item = ActionItem.objects.create(
            description=a["description"],
            due_date=a.get("due_date") or None,
            person=person_obj,
        )
        desc_preview = a["description"][:60]
        console.print(f"[green]Created[/green]  Action #{item.pk}: {desc_preview}")


def extract(
    source: str = typer.Argument(..., help="Document slug (from 'provenance docs list') or file path", autocompletion=complete_doc_or_file),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without saving"),
    chunk_size: int = typer.Option(6000, "--chunk", help="Max characters per AI call (for large docs)"),
):
    """Extract and import all people from an org chart or document.

    Accepts a doc slug already in the database, or any .md / .txt / .pdf file path.

    Examples:\n
      provenance extract org-chart-2026\n
      provenance extract ~/Downloads/team-directory.pdf\n
      provenance extract notes/docs/wharton-faculty.md --dry-run
    """
    content, label = _read_source(source)
    if not content:
        raise typer.Exit(1)

    console.print(f"[dim]Reading: {label} ({len(content):,} chars)[/dim]")

    # Chunk large documents — avoid hitting context limits
    chunks = _chunk_text(content, chunk_size)
    if len(chunks) > 1:
        console.print(f"[dim]Document is large — processing in {len(chunks)} chunks…[/dim]")

    all_people: list[dict] = []
    seen_names: set[str] = set()

    try:
        from ai.registry import get_provider
        provider = get_provider()

        for i, chunk in enumerate(chunks, 1):
            if len(chunks) > 1:
                console.print(f"[dim]Chunk {i}/{len(chunks)}…[/dim]")
            response = provider.complete(system=_EXTRACT_PEOPLE_SYSTEM, user=chunk)
            cleaned = response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.splitlines()
                cleaned = "\n".join(lines[1:])
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3].strip()
            extracted = json.loads(cleaned)
            for p in extracted.get("people", []):
                if p.get("name") and p["name"] not in seen_names:
                    all_people.append(p)
                    seen_names.add(p["name"])

    except json.JSONDecodeError:
        err.print("[red]AI returned invalid JSON. Try a smaller --chunk size or rephrase.[/red]")
        raise typer.Exit(1)
    except RuntimeError as e:
        err.print(f"[red]AI error: {e}[/red]")
        raise typer.Exit(1)

    if not all_people:
        console.print("[yellow]No people found in that document.[/yellow]")
        raise typer.Exit(0)

    # Preview table
    console.print(f"\n[bold]Found {len(all_people)} people[/bold]\n")
    t = Table(show_header=True, header_style="bold blue", box=None, pad_edge=False)
    t.add_column("Name")
    t.add_column("Role")
    t.add_column("Org")
    t.add_column("Context", style="dim")
    for p in all_people:
        t.add_row(
            p["name"],
            p.get("role", ""),
            p.get("org", ""),
            (p.get("relationship_context") or "")[:60],
        )
    console.print(t)

    if dry_run:
        raise typer.Exit(0)

    if not yes:
        typer.confirm(f"\nImport all {len(all_people)} people?", default=True, abort=True)

    slug_map: dict[str, str] = {}
    _create_people(all_people, slug_map)
    console.print(f"\n[bold green]Done — {len(all_people)} people processed.[/bold green]")


def _read_source(source: str) -> tuple[str, str]:
    """Return (content, label) from a doc slug or file path."""
    path = Path(source)

    # Looks like a file path — resolve directly
    if path.suffix or path.exists():
        if not path.exists():
            # Try relative to BASE_DIR
            path = BASE_DIR / source
        if not path.exists():
            err.print(f"[red]File not found: {source}[/red]")
            return "", ""
        return _read_file(path), str(path)

    # Otherwise treat as a doc slug — normalize underscores to hyphens
    slug = source.replace("_", "-")
    try:
        from core.models import Document
        doc = Document.objects.get(slug=slug)
        doc_path = BASE_DIR / doc.file_path
        if not doc_path.exists():
            err.print(f"[red]File not found at {doc.file_path}[/red]")
            err.print("Run [bold]provenance docs list[/bold] to check the path.")
            return "", ""
        return _read_file(doc_path), f"{doc.title} ({doc.slug})"
    except Exception:
        err.print(f"[red]No document with slug '{source}'.[/red]")
        err.print("Run [bold]provenance docs list[/bold] or pass a file path directly.")
        return "", ""


def _read_file(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        try:
            import fitz
            doc = fitz.open(str(path))
            pages = [page.get_text().strip() for page in doc]
            doc.close()
            return "\n\n".join(p for p in pages if p)
        except ImportError:
            err.print("[red]pymupdf required for PDF: uv add pymupdf[/red]")
            return ""
    return path.read_text(errors="replace")


def _chunk_text(text: str, chunk_size: int) -> list[str]:
    """Split text into chunks at paragraph boundaries."""
    if len(text) <= chunk_size:
        return [text]
    chunks, current = [], []
    current_len = 0
    for para in text.split("\n\n"):
        if current_len + len(para) > chunk_size and current:
            chunks.append("\n\n".join(current))
            current, current_len = [], 0
        current.append(para)
        current_len += len(para)
    if current:
        chunks.append("\n\n".join(current))
    return chunks


CONTEXT_FILE = BASE_DIR / "notes" / "context.md"


def remember(
    text: list[str] = typer.Argument(..., help="Thing to remember — no quotes needed"),
):
    """Save a personal context note the AI will always remember.

    Examples:\n
      provenance remember when I say my team I mean Roger Chu, Will Haun, Yemi Afolabi and John Piotrowski\n
      provenance remember I am the Director of IT at Wharton\n
      provenance remember my 1:1 with Amy is every Tuesday
    """
    note = " ".join(text).strip()

    CONTEXT_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Initialise file with header if new
    if not CONTEXT_FILE.exists():
        CONTEXT_FILE.write_text("# Personal Context\n\n")

    with CONTEXT_FILE.open("a") as f:
        f.write(f"- {note}\n")

    console.print(f"[green]Remembered:[/green] {note}")
    console.print(f"[dim]{CONTEXT_FILE.relative_to(BASE_DIR)}[/dim]")
