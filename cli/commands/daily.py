"""
Daily summary commands.

  provenance daily log "finished Q1 budget review"
  provenance daily show
  provenance daily show 2026-03-06
  provenance daily generate
"""
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from cli.paths import DAILY_DIR, PROVENANCE_HOME as BASE_DIR

console = Console()
err = Console(stderr=True)

app = typer.Typer(help="Daily log and summary.", no_args_is_help=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _daily_path(date_str: str | None = None) -> Path:
    d = date_str or date.today().isoformat()
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    return DAILY_DIR / f"{d}.md"


def _ensure_log_section(path: Path, date_str: str) -> None:
    """Create file with header + Log section if it doesn't exist yet."""
    if not path.exists():
        path.write_text(f"# Daily Summary — {date_str}\n\n## Log\n\n")


def _append_log_entry(path: Path, entry: str, date_str: str) -> None:
    _ensure_log_section(path, date_str)
    ts = datetime.now().strftime("%H:%M")
    line = f"- {ts} — {entry}\n"

    content = path.read_text()
    if "## Log" not in content:
        content += f"\n\n## Log\n\n{line}"
        path.write_text(content)
        return

    # Insert at the end of the Log section (before the next ## heading, or EOF)
    log_match = re.search(r"^## Log\s*\n", content, re.MULTILINE)
    if not log_match:
        content += line
        path.write_text(content)
        return

    rest = content[log_match.end():]
    next_section = re.search(r"^##\s", rest, re.MULTILINE)
    if next_section:
        insert_at = log_match.end() + next_section.start()
        content = content[:insert_at] + line + "\n" + content[insert_at:]
    else:
        content = content.rstrip("\n") + "\n" + line

    path.write_text(content)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@app.command("log")
def log_entry(
    text: list[str] = typer.Argument(None, help="Entry text — no quotes needed"),
    date_str: Optional[str] = typer.Option(None, "--date", "-d", help="Date (YYYY-MM-DD, default today)"),
):
    """Append a timestamped entry to today's daily log.

    Examples:\n
      provenance daily log finished Q1 budget review\n
      provenance daily log sent agenda to Tom for tomorrow's meeting\n
      provenance daily log --date 2026-03-06 retrospective note
    """
    if text:
        entry = " ".join(text).strip()
    elif not sys.stdin.isatty():
        entry = sys.stdin.read().strip()
    else:
        entry = ""

    if not entry:
        err.print("[red]Provide log text or pipe content in.[/red]")
        raise typer.Exit(1)

    d = date_str or date.today().isoformat()
    path = _daily_path(d)
    _append_log_entry(path, entry, d)
    ts = datetime.now().strftime("%H:%M")
    console.print(f"[green]Logged[/green] {ts} — {entry}")
    console.print(f"[dim]{path.relative_to(BASE_DIR.parent)}[/dim]")


@app.command("show")
def show(
    date_str: Optional[str] = typer.Argument(None, help="Date to show (YYYY-MM-DD, default today)"),
):
    """Show the daily summary for today or a given date.

    Examples:\n
      provenance daily show\n
      provenance daily show 2026-03-06
    """
    d = date_str or date.today().isoformat()
    path = _daily_path(d)
    if not path.exists():
        console.print(f"[yellow]No daily summary for {d}.[/yellow]")
        raise typer.Exit(0)
    console.print(path.read_text())


@app.command("generate")
def generate(
    date_str: Optional[str] = typer.Option(None, "--date", "-d", help="Date (YYYY-MM-DD, default today)"),
    append: bool = typer.Option(True, "--append/--no-append", help="Append summary to daily file (default true)"),
):
    """Generate an AI summary of the day and append it to the daily file.

    Pulls today's meetings, open actions, and existing log entries, then
    asks the AI to write a short narrative summary.

    Examples:\n
      provenance daily generate\n
      provenance daily generate --date 2026-03-06\n
      provenance daily generate --no-append   # just print, don't save
    """
    d = date_str or date.today().isoformat()

    console.print(f"[dim]Gathering context for {d}…[/dim]")
    context_parts: list[str] = []

    # Today's meetings
    try:
        from core.models import Meeting
        meetings = list(Meeting.objects.filter(date=d).prefetch_related("attendees"))
        if meetings:
            lines = ["Meetings today:"]
            for m in meetings:
                attendee_names = ", ".join(p.name for p in m.attendees.all())
                lines.append(f"  - {m.title}" + (f" (with {attendee_names})" if attendee_names else ""))
                if m.summary:
                    lines.append(f"    Summary: {m.summary}")
            context_parts.append("\n".join(lines))
    except Exception as e:
        err.print(f"[dim]Could not fetch meetings: {e}[/dim]")

    # Open actions
    try:
        from core.models import ActionItem
        actions = list(ActionItem.objects.filter(status="open").select_related("person"))
        if actions:
            lines = ["Open action items:"]
            for a in actions:
                line = f"  - {a.description}"
                if a.person:
                    line += f" (→ {a.person.name})"
                if a.due_date:
                    line += f" [due {a.due_date}]"
                lines.append(line)
            context_parts.append("\n".join(lines))
    except Exception as e:
        err.print(f"[dim]Could not fetch actions: {e}[/dim]")

    # Existing log entries
    path = _daily_path(d)
    if path.exists():
        existing = path.read_text().strip()
        if existing:
            context_parts.append(f"Daily log so far:\n{existing}")

    if not context_parts:
        console.print("[yellow]No data found for today — nothing to summarize.[/yellow]")
        raise typer.Exit(0)

    context_block = "\n\n".join(context_parts)

    system = (
        "You are a professional assistant helping summarize a workday. "
        "Write a concise narrative paragraph (3–5 sentences) summarizing the day based on the context provided. "
        "Focus on what was accomplished, key themes, and any important follow-ups. "
        "Write in first person. Do not list bullet points — write flowing prose."
    )
    user = f"Date: {d}\n\n{context_block}"

    console.print("[dim]Generating summary…[/dim]")
    try:
        from ai.registry import get_provider
        provider = get_provider()
        summary_text = provider.complete(system=system, user=user)
    except RuntimeError as e:
        err.print(f"[red]AI error: {e}[/red]")
        raise typer.Exit(1)

    ts_generated = datetime.now().strftime("%H:%M")
    block = f"\n\n## AI Summary (generated {ts_generated})\n\n{summary_text.strip()}\n"

    console.print(f"\n[bold]## AI Summary[/bold]\n{summary_text.strip()}\n")

    if append:
        _ensure_log_section(path, d)
        with path.open("a") as f:
            f.write(block)
        console.print(f"[green]Appended to[/green] {path.relative_to(BASE_DIR.parent)}")
