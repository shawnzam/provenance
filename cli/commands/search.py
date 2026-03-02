import json
import os
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

console = Console()
err = Console(stderr=True)

from cli.paths import PROVENANCE_HOME as BASE_DIR, NOTES_DIR, DB_PATH


def search(
    query: list[str] = typer.Argument(..., help="Search query — no quotes needed"),
    json_out: bool = typer.Option(False, "--json", help="Output as JSON"),
    db_only: bool = typer.Option(False, "--db", help="Search database only, skip notes"),
    notes_only: bool = typer.Option(False, "--notes", help="Search notes only, skip database"),
    sem: bool = typer.Option(False, "--sem", help="Use semantic (FTS5) search in notes"),
    lex: bool = typer.Option(False, "--lex", help="Use BM25 full-text ranking in notes"),
    topk: int = typer.Option(10, "--topk", "-k", help="Max notes results (lex/sem only)"),
    context: int = typer.Option(2, "--context", "-C", help="Lines of context around each match"),
):
    """Search people, meetings, and actions in the database, then notes via FTS5."""
    q = " ".join(query).strip()
    db_results = {}
    piping = not sys.stdout.isatty()

    if not notes_only:
        db_results = _search_db(q)

    if json_out:
        typer.echo(json.dumps(db_results, indent=2))
        return

    # --- DB results ---
    if not notes_only:
        _print_db_results(db_results, q)

    # --- Notes results via FTS5 ---
    if not db_only:
        if not notes_only and any(db_results.values()) and not piping:
            console.print("\n[bold]Notes[/bold]")
        _search_notes_fts(q, sem=sem, lex=lex, topk=topk, context=context, piping=piping)


def _search_db(query: str) -> dict:
    from core.models import Person, Meeting, ActionItem, Document
    from django.db.models import Q

    q = query.strip()

    people = list(
        Person.objects.filter(
            Q(name__icontains=q) | Q(role__icontains=q) | Q(org__icontains=q)
            | Q(tags__icontains=q) | Q(notes__icontains=q) | Q(relationship_context__icontains=q)
        )
    )

    meetings = list(
        Meeting.objects.filter(
            Q(title__icontains=q) | Q(summary__icontains=q) | Q(tags__icontains=q)
            | Q(attendees__name__icontains=q)
        ).distinct()
    )

    actions = list(
        ActionItem.objects.filter(
            Q(description__icontains=q) | Q(tags__icontains=q)
        ).select_related("person", "meeting")
    )

    documents = list(
        Document.objects.filter(
            Q(title__icontains=q) | Q(tags__icontains=q) | Q(notes__icontains=q) | Q(source__icontains=q)
        )
    )

    return {
        "people": [p.to_dict() for p in people],
        "meetings": [m.to_dict() for m in meetings],
        "actions": [a.to_dict() for a in actions],
        "documents": [d.to_dict() for d in documents],
    }


def _print_db_results(results: dict, query: str):
    people = results.get("people", [])
    meetings = results.get("meetings", [])
    actions = results.get("actions", [])

    total = len(people) + len(meetings) + len(actions)
    if total == 0:
        console.print(f"[dim]No database matches for '{query}'.[/dim]")
        return

    if people:
        console.print(f"\n[bold]People[/bold]")
        t = Table(show_header=True, header_style="bold blue", box=None, pad_edge=False)
        t.add_column("Slug", style="dim")
        t.add_column("Name")
        t.add_column("Role")
        t.add_column("Org")
        for p in people:
            t.add_row(p["slug"], p["name"], p.get("role", ""), p.get("org", ""))
        console.print(t)

    if meetings:
        console.print(f"\n[bold]Meetings[/bold]")
        t = Table(show_header=True, header_style="bold blue", box=None, pad_edge=False)
        t.add_column("Date")
        t.add_column("Title")
        t.add_column("Slug", style="dim")
        for m in meetings:
            t.add_row(m["date"], m["title"], m["slug"])
        console.print(t)

    if actions:
        console.print(f"\n[bold]Actions[/bold]")
        t = Table(show_header=True, header_style="bold blue", box=None, pad_edge=False)
        t.add_column("ID", style="dim")
        t.add_column("Status")
        t.add_column("Description")
        for a in actions:
            t.add_row(str(a["id"]), a["status"], a["description"][:60])
        console.print(t)

    documents = results.get("documents", [])
    if documents:
        console.print(f"\n[bold]Documents[/bold]")
        t = Table(show_header=True, header_style="bold blue", box=None, pad_edge=False)
        t.add_column("Slug", style="dim")
        t.add_column("Title")
        t.add_column("Source")
        for d in documents:
            t.add_row(d["slug"], d["title"], d.get("source", ""))
        console.print(t)


def _search_notes_fts(
    query: str,
    sem: bool = False,
    lex: bool = False,
    topk: int = 10,
    context: int = 2,
    piping: bool = False,
):
    from cli.tools import search_notes
    mode = "semantic" if sem else ("lex" if lex else "regex")
    result = search_notes(query, mode=mode, context_lines=context)
    if result:
        console.print(result)


def index_notes_cmd():
    """Build or rebuild the FTS5 full-text search index for notes/."""
    from cli.indexer import index_notes, NOTES_DIR
    console.print(f"[dim]Indexing {NOTES_DIR}…[/dim]")
    index_notes(quiet=False)
    console.print("[green]✓[/green] Index complete.")


def doctor():
    """Check that all required dependencies and config are in place."""
    ok = True

    if DB_PATH.exists():
        console.print(f"[green]✓[/green] Database: {DB_PATH}")
    else:
        console.print(f"[red]✗[/red] Database not found at {DB_PATH}")
        console.print("  Run: [bold]uv run python manage.py migrate[/bold]")
        ok = False

    try:
        from django.db import connection
        with connection.cursor() as cur:
            cur.execute("SELECT count(*) FROM notes_fts")
            count = cur.fetchone()[0]
        console.print(f"[green]✓[/green] FTS5 index: {count} documents indexed")
        if count == 0:
            console.print("  Run: [bold]provenance index[/bold] to build the index")
    except Exception:
        console.print("[red]✗[/red] FTS5 index table not found")
        console.print("  Run: [bold]uv run python manage.py migrate[/bold]")
        ok = False

    api_key = os.environ.get("PROVENANCE_OPENAI_API_KEY", "")
    if api_key and api_key != "sk-...":
        console.print(f"[green]✓[/green] PROVENANCE_OPENAI_API_KEY is set")
    else:
        console.print("[yellow]![/yellow] PROVENANCE_OPENAI_API_KEY not set")
        console.print("  Add to .env: PROVENANCE_OPENAI_API_KEY=sk-...")
        ok = False

    provider = os.environ.get("PROVENANCE_AI_PROVIDER", "openai")
    console.print(f"[green]✓[/green] AI provider: {provider}")

    model = os.environ.get("PROVENANCE_AI_MODEL", "gpt-4o")
    console.print(f"[green]✓[/green] AI model: {model}")

    proofread_model = os.environ.get("PROVENANCE_PROOFREAD_AI_MODEL")
    if proofread_model:
        console.print(f"[green]✓[/green] Proofread model: {proofread_model}")

    if ok:
        console.print("\n[bold green]All checks passed.[/bold green]")
    else:
        console.print("\n[bold yellow]Some checks failed — see above.[/bold yellow]")
        raise typer.Exit(1)
