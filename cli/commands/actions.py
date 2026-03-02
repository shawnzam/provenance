import json
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from cli.completions import complete_person_slug, complete_meeting_slug, complete_open_action_id, complete_tags

app = typer.Typer(help="Manage action items.", no_args_is_help=True)
console = Console()
err = Console(stderr=True)

STATUS_COLORS = {
    "open": "yellow",
    "in_progress": "blue",
    "done": "green",
    "cancelled": "dim",
}


@app.command("list")
def list_actions(
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status (open/in_progress/done/cancelled)"),
    person: Optional[str] = typer.Option(None, "--person", "-p", help="Filter by person slug", autocompletion=complete_person_slug),
    json_out: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List action items."""
    from core.models import ActionItem

    qs = ActionItem.objects.all()
    if status:
        qs = qs.filter(status=status)
    if person:
        qs = qs.filter(person__slug=person)

    items = list(qs.select_related("person", "meeting"))

    if json_out:
        typer.echo(json.dumps([i.to_dict() for i in items], indent=2))
        return

    if not items:
        console.print("[dim]No action items found.[/dim]")
        return

    table = Table(show_header=True, header_style="bold blue")
    table.add_column("ID", style="dim")
    table.add_column("Status")
    table.add_column("Description")
    table.add_column("Due")
    table.add_column("Person")

    for item in items:
        color = STATUS_COLORS.get(item.status, "white")
        table.add_row(
            str(item.pk),
            f"[{color}]{item.status}[/{color}]",
            item.description[:60],
            str(item.due_date) if item.due_date else "",
            item.person.name if item.person else "",
        )

    console.print(table)


@app.command("add")
def add_action(
    description: str = typer.Argument(..., help="Action item description"),
    due: Optional[str] = typer.Option(None, "--due", "-d", help="Due date (YYYY-MM-DD)"),
    person: Optional[str] = typer.Option(None, "--person", "-p", help="Person slug", autocompletion=complete_person_slug),
    meeting: Optional[str] = typer.Option(None, "--meeting", "-m", help="Meeting slug", autocompletion=complete_meeting_slug),
    tags: str = typer.Option("", "--tags", help="Comma-separated tags", autocompletion=complete_tags),
    json_out: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Add an action item."""
    from core.models import ActionItem, Person, Meeting
    from cli.text_utils import check

    description = check(description)

    person_obj = None
    if person:
        try:
            person_obj = Person.objects.get(slug=person)
        except Person.DoesNotExist:
            err.print(f"[red]No person with slug '{person}'.[/red]")
            raise typer.Exit(1)

    meeting_obj = None
    if meeting:
        try:
            meeting_obj = Meeting.objects.get(slug=meeting)
        except Meeting.DoesNotExist:
            err.print(f"[red]No meeting with slug '{meeting}'.[/red]")
            raise typer.Exit(1)

    item = ActionItem.objects.create(
        description=description,
        due_date=due or None,
        person=person_obj,
        meeting=meeting_obj,
        tags=tags,
    )

    if json_out:
        typer.echo(json.dumps(item.to_dict(), indent=2))
        return

    console.print(f"[green]Added[/green] action item #{item.pk}")


@app.command("done")
def mark_done(
    item_id: int = typer.Argument(..., help="Action item ID", autocompletion=complete_open_action_id),
    json_out: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Mark an action item as done."""
    from core.models import ActionItem
    try:
        item = ActionItem.objects.get(pk=item_id)
    except ActionItem.DoesNotExist:
        err.print(f"[red]No action item with ID {item_id}.[/red]")
        raise typer.Exit(1)

    item.status = "done"
    item.save()

    if json_out:
        typer.echo(json.dumps(item.to_dict(), indent=2))
        return

    console.print(f"[green]Marked #[/green]{item_id} as done.")
