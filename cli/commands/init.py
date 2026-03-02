"""First-run setup — create ~/.provenance directory structure."""
import typer
from rich.console import Console
from cli.paths import PROVENANCE_HOME, NOTES_DIR, DB_PATH, ENV_FILE

console = Console()
err = Console(stderr=True)


def migrate():
    """Apply database migrations. Run once after install and after upgrades."""
    from django.core.management import call_command
    console.print("[dim]Running migrations…[/dim]")
    call_command("migrate", "--run-syncdb")
    console.print(f"[green]✓[/green] Database ready: {DB_PATH}")


def init():
    """Set up ~/.provenance with the required directory structure.

    Safe to run multiple times — skips anything that already exists.
    """
    created = []

    for d in [
        PROVENANCE_HOME,
        NOTES_DIR,
        NOTES_DIR / "meetings",
        NOTES_DIR / "docs",
    ]:
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            created.append(str(d))
            console.print(f"[green]Created[/green] {d}")
        else:
            console.print(f"[dim]Exists[/dim]  {d}")

    context_file = NOTES_DIR / "context.md"
    if not context_file.exists():
        context_file.write_text("# Personal Context\n\n")
        console.print(f"[green]Created[/green] {context_file}")
    else:
        console.print(f"[dim]Exists[/dim]  {context_file}")

    console.print()

    if not ENV_FILE.exists():
        console.print(f"[yellow]Next:[/yellow] create {ENV_FILE} with:")
        console.print("  PROVENANCE_OPENAI_API_KEY=sk-...")
        console.print("  PROVENANCE_AI_PROVIDER=openai")
        console.print("  PROVENANCE_AI_MODEL=gpt-4o")
        console.print("  DJANGO_SECRET_KEY=<random string>")
    else:
        console.print(f"[green]✓[/green] {ENV_FILE}")

    if not DB_PATH.exists():
        console.print(f"\n[dim]Running migrations…[/dim]")
        from django.core.management import call_command
        call_command("migrate", "--run-syncdb")
        console.print(f"[green]✓[/green] Database created: {DB_PATH}")
    else:
        console.print(f"[green]✓[/green] {DB_PATH}")
