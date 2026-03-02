import json
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from cli.completions import (
    complete_person_slug, complete_org, complete_tags, complete_meeting_slug
)

app = typer.Typer(help="Manage people in your network.", no_args_is_help=True)
console = Console()
err = Console(stderr=True)


def _get_person(slug: str):
    from core.models import Person
    try:
        return Person.objects.get(slug=slug)
    except Person.DoesNotExist:
        err.print(f"[red]No person found with slug '{slug}'.[/red]")
        err.print("Run [bold]provenance people list[/bold] to see available slugs.")
        raise typer.Exit(1)


@app.command("list")
def list_people(
    json_out: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List all people."""
    from core.models import Person
    people = list(Person.objects.all())

    if json_out:
        typer.echo(json.dumps([p.to_dict() for p in people], indent=2))
        return

    if not people:
        console.print("[dim]No people yet. Use [bold]provenance people add[/bold] to get started.[/dim]")
        return

    table = Table(show_header=True, header_style="bold blue")
    table.add_column("Slug")
    table.add_column("Name")
    table.add_column("Role")
    table.add_column("Org")
    table.add_column("Email")

    for p in people:
        table.add_row(p.slug, p.name, p.role, p.org, p.email)

    console.print(table)


@app.command("add")
def add_person(
    name: str = typer.Argument(..., help="Full name"),
    role: Optional[str] = typer.Option(None, "--role", "-r", help="Job title or role"),
    org: Optional[str] = typer.Option(None, "--org", "-o", help="Organization", autocompletion=complete_org),
    email: Optional[str] = typer.Option(None, "--email", "-e", help="Email address"),
    context: Optional[str] = typer.Option(None, "--context", "-c", help="Relationship context"),
    notes: Optional[str] = typer.Option(None, "--notes", "-n", help="Freeform notes about this person"),
    tags: Optional[str] = typer.Option(None, "--tags", "-t", help="Comma-separated tags", autocompletion=complete_tags),
    update: bool = typer.Option(False, "--update", "-u", help="Update existing person without prompting"),
    json_out: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Add a new person, or update them if they already exist."""
    from core.models import Person
    from slugify import slugify
    from cli.text_utils import check

    # Correct prose fields after Typer has validated all options
    role = check(role) if role else role
    context = check(context) if context else context
    notes = check(notes) if notes else notes

    slug = slugify(name)
    existing = Person.objects.filter(slug=slug).first()

    if existing:
        # Build dict of fields explicitly provided (not None)
        updates = {k: v for k, v in {
            "name": name,
            "role": role,
            "org": org,
            "email": email,
            "relationship_context": context,
            "notes": notes,
            "tags": tags,
        }.items() if v is not None}

        if not update:
            console.print(f"\n[yellow]'{slug}' already exists:[/yellow]")
            console.print(f"  Name:  {existing.name}")
            if existing.role:
                console.print(f"  Role:  {existing.role}")
            if existing.org:
                console.print(f"  Org:   {existing.org}")
            if existing.email:
                console.print(f"  Email: {existing.email}")

            if len(updates) > 1:  # more than just name
                console.print("\n[dim]Would update:[/dim]")
                for k, v in updates.items():
                    if k != "name":
                        console.print(f"  {k}: {v}")

            confirmed = typer.confirm("\nUpdate this person?", default=False)
            if not confirmed:
                raise typer.Exit(0)

        for field, value in updates.items():
            setattr(existing, field, value)
        existing.save()

        if json_out:
            typer.echo(json.dumps(existing.to_dict(), indent=2))
            return

        console.print(f"[green]Updated[/green] {existing.name} ([bold]{existing.slug}[/bold])")
        return

    person = Person.objects.create(
        name=name,
        role=role or "",
        org=org or "",
        email=email or "",
        relationship_context=context or "",
        notes=notes or "",
        tags=tags or "",
    )

    if json_out:
        typer.echo(json.dumps(person.to_dict(), indent=2))
        return

    console.print(f"[green]Added[/green] {person.name} ([bold]{person.slug}[/bold])")


@app.command("show")
def show_person(
    slug: str = typer.Argument(..., help="Person slug", autocompletion=complete_person_slug),
    json_out: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show details for a person."""
    person = _get_person(slug)

    if json_out:
        typer.echo(json.dumps(person.to_dict(), indent=2))
        return

    console.print(f"\n[bold]{person.name}[/bold]  [dim]{person.slug}[/dim]")
    if person.role:
        console.print(f"  Role:  {person.role}")
    if person.org:
        console.print(f"  Org:   {person.org}")
    if person.email:
        console.print(f"  Email: {person.email}")
    if person.relationship_context:
        console.print(f"\n[dim]Context:[/dim] {person.relationship_context}")
    if person.notes:
        console.print(f"\n[dim]Notes:[/dim]\n{person.notes}")
    if person.tags:
        tags = [t.strip() for t in person.tags.split(",") if t.strip()]
        console.print(f"\n[dim]Tags:[/dim] {', '.join(tags)}")
    console.print()


@app.command("meetings")
def person_meetings(
    slug: str = typer.Argument(..., help="Person slug", autocompletion=complete_person_slug),
    json_out: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List meetings for a person."""
    person = _get_person(slug)
    meetings = list(person.meetings.order_by("-date"))

    if json_out:
        typer.echo(json.dumps({
            "person": person.to_dict(),
            "meetings": [m.to_dict() for m in meetings],
        }, indent=2))
        return

    if not meetings:
        console.print(f"[dim]No meetings recorded for {person.name}.[/dim]")
        return

    console.print(f"\n[bold]Meetings with {person.name}[/bold]\n")
    table = Table(show_header=True, header_style="bold blue")
    table.add_column("Date")
    table.add_column("Title")
    table.add_column("Slug")

    for m in meetings:
        table.add_row(str(m.date), m.title, m.slug)

    console.print(table)
    console.print()
