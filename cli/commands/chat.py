"""
Provenance interactive REPL — full-featured, personality-driven.

Type fast and sloppy — auto-correct has your back.
Commands, questions, meeting captures, notes, and AI all in one place.
"""
import json
import re
import shutil
import subprocess
import sys
import zoneinfo
from datetime import datetime, date
from pathlib import Path
from typing import Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console()
err = Console(stderr=True)

from cli.paths import PROVENANCE_HOME as BASE_DIR
HISTORY_FILE = BASE_DIR / ".chat_history"
SETTINGS_FILE = BASE_DIR / "settings.json"
STATS_FILE = BASE_DIR / "command_stats.json"

EASTERN = zoneinfo.ZoneInfo("America/New_York")

# ── Settings ──────────────────────────────────────────────────────────────────

_SETTING_DEFAULTS: dict = {
    "autocorrect":          True,
    "editor":               "code",
    "assistant_name":       "P",
    "day_summary":          True,
    "quote_on_start":       True,
    "show_time_in_prompt":  True,
    "auto_open_notes":      False,
    "autocorrect_min_words": 3,
}

_SETTING_DOCS: dict = {
    "autocorrect":          "Fix typos in prose input before processing (true/false)",
    "editor":               "Command to open files  (code, vim, nano, …)",
    "assistant_name":       "Name shown in prompt and greeting",
    "day_summary":          "Show day summary on startup (true/false)",
    "quote_on_start":       "Show an AI-generated quote on startup (true/false)",
    "show_time_in_prompt":  "Show current time in the prompt (true/false)",
    "auto_open_notes":      "Auto-open meeting notes in editor after creation (true/false)",
    "autocorrect_min_words": "Min words before autocorrect kicks in (int)",
}


def _load_settings() -> dict:
    data: dict = {}
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text())
        except Exception:
            pass
    return {k: data.get(k, v) for k, v in _SETTING_DEFAULTS.items()}


def _save_settings(settings: dict) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2))


def _set_setting(settings: dict, key: str, raw: str) -> str:
    if key not in _SETTING_DEFAULTS:
        keys = ", ".join(_SETTING_DEFAULTS)
        return f"[red]Unknown setting:[/red] {key!r}\nAvailable: {keys}"
    default = _SETTING_DEFAULTS[key]
    if isinstance(default, bool):
        value: object = raw.lower() in ("true", "1", "yes", "on")
    elif isinstance(default, int):
        try:
            value = int(raw)
        except ValueError:
            return f"[red]Expected integer for {key!r}, got:[/red] {raw!r}"
    else:
        value = raw
    settings[key] = value
    _save_settings(settings)
    return f"[green]✓[/green]  {key} = [bold]{value!r}[/bold]"


# ── Command stats ─────────────────────────────────────────────────────────────

def _load_stats() -> dict:
    if STATS_FILE.exists():
        try:
            return json.loads(STATS_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_stats(stats: dict) -> None:
    STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATS_FILE.write_text(json.dumps(stats, indent=2))


def _record(stats: dict, cmd: str) -> None:
    stats[cmd] = stats.get(cmd, 0) + 1
    stats["_total"] = stats.get("_total", 0) + 1


def _print_stats(stats: dict) -> None:
    user_stats = {k: v for k, v in stats.items() if not k.startswith("_")}
    total = stats.get("_total", 0)
    sessions = stats.get("_sessions", 0)
    if not user_stats:
        console.print("[dim]No stats yet — start using commands![/dim]")
        return
    sorted_stats = sorted(user_stats.items(), key=lambda x: x[1], reverse=True)
    t = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE, pad_edge=False)
    t.add_column("Command")
    t.add_column("Uses", justify="right")
    t.add_column("Share", justify="right", style="dim")
    for cmd, count in sorted_stats[:15]:
        pct = f"{count / total * 100:.0f}%" if total else "—"
        t.add_row(cmd, str(count), pct)
    console.print(f"\n[bold]Command stats[/bold]  [dim]{total} inputs · {sessions} session{'s' if sessions != 1 else ''}[/dim]")
    console.print(t)
    if total >= 10:
        top = sorted_stats[0][0]
        console.print(f"\n[dim]Your go-to: '{top}'. Type /help to discover other commands.[/dim]")


# ── Day summary ───────────────────────────────────────────────────────────────

def _day_summary(settings: dict) -> None:
    now = datetime.now(EASTERN)
    day_str = now.strftime("%A, %B %-d, %Y")
    time_str = now.strftime("%-I:%M %p EST")

    meetings_today: list = []
    actions_open: int = 0
    last_note_name: Optional[str] = None

    try:
        from core.models import Meeting, ActionItem
        meetings_today = list(
            Meeting.objects.filter(date=now.date())
            .order_by("title")
            .prefetch_related("attendees")
        )
        actions_open = ActionItem.objects.filter(status="open").count()
    except Exception:
        pass

    # Most recently modified note
    notes_dir = BASE_DIR / "notes"
    if notes_dir.exists():
        all_notes = sorted(
            (p for p in notes_dir.rglob("*.md") if p.is_file()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if all_notes:
            last_note_name = all_notes[0].name

    lines: list[str] = []
    lines.append(f"[bold]{day_str}[/bold]  [dim]{time_str}[/dim]")
    lines.append("")

    if meetings_today:
        lines.append("[cyan]Meetings today[/cyan]")
        for m in meetings_today:
            first_names = [a.name.split()[0] for a in m.attendees.all()[:4]]
            attendee_str = ", ".join(first_names)
            lines.append(f"  [dim]◆[/dim] {m.title}  [dim]{attendee_str}[/dim]")
    else:
        lines.append("[dim]No meetings scheduled today[/dim]")

    lines.append("")

    if actions_open == 0:
        lines.append("[green]✓ No open actions[/green]")
    elif actions_open <= 3:
        lines.append(f"[green]{actions_open} open action{'s' if actions_open != 1 else ''}[/green]")
    elif actions_open <= 7:
        lines.append(f"[yellow]{actions_open} open actions[/yellow]")
    else:
        lines.append(f"[red]{actions_open} open actions — time to triage[/red]")

    if last_note_name:
        lines.append(f"[dim]Last note: {last_note_name}[/dim]")

    console.print(Panel(
        "\n".join(lines),
        border_style="dim cyan",
        padding=(0, 1),
        expand=False,
    ))


# ── Greeting ──────────────────────────────────────────────────────────────────

def _greeting_text() -> str:
    hour = datetime.now(EASTERN).hour
    if 5 <= hour < 12:
        return "Good morning."
    elif 12 <= hour < 17:
        return "Good afternoon."
    elif 17 <= hour < 21:
        return "Good evening."
    else:
        return "Working late."


# ── Helpers ───────────────────────────────────────────────────────────────────

_PREVIEW_MAX = 120


def _preview(text: str, max_chars: int = _PREVIEW_MAX) -> str:
    """Return text truncated to max_chars with ellipsis if needed."""
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "…"


# ── Auto-correct ──────────────────────────────────────────────────────────────

_CORRECT_SYSTEM = (
    "You are a fast typo corrector. Fix obvious spelling mistakes and typos only. "
    "Do NOT rephrase, reorder, add words, change meaning, or modify proper nouns, "
    "names, slugs, dates, or technical terms. "
    "Return ONLY the corrected text with no explanation or punctuation changes. "
    "If nothing needs fixing, return the input unchanged."
)


def _autocorrect(text: str, settings: dict) -> tuple[str, bool]:
    """Return (corrected_text, was_changed). Always fails open."""
    if not settings.get("autocorrect", True):
        return text, False
    min_words = int(settings.get("autocorrect_min_words", 3))
    if len(text.split()) < min_words:
        return text, False
    try:
        from ai.registry import get_provider
        corrected = get_provider().complete(system=_CORRECT_SYSTEM, user=text).strip()
        # Guard against runaway responses
        if not corrected or len(corrected) > len(text) * 2 or len(corrected) < len(text) // 3:
            return text, False
        changed = corrected != text
        return corrected, changed
    except Exception:
        return text, False


# ── Open in editor ────────────────────────────────────────────────────────────

def _open_in_editor(target: str, settings: dict) -> None:
    editor = settings.get("editor", "code")
    path: Optional[Path] = None

    # Direct path
    candidate = Path(target)
    if candidate.exists():
        path = candidate
    elif (BASE_DIR / target).exists():
        path = BASE_DIR / target

    # Meeting slug
    if not path:
        try:
            from core.models import Meeting
            m = Meeting.objects.filter(slug=target).first()
            if m and m.notes_file:
                p = BASE_DIR / m.notes_file
                if p.exists():
                    path = p
        except Exception:
            pass

    # Fuzzy: notes file containing target string
    if not path:
        notes_dir = BASE_DIR / "notes"
        candidates = [p for p in notes_dir.rglob("*.md") if target.lower() in p.name.lower()]
        if len(candidates) == 1:
            path = candidates[0]
        elif len(candidates) > 1:
            console.print(f"[yellow]Multiple matches for[/yellow] {target!r}:")
            for c in candidates[:8]:
                console.print(f"  [cyan]{c.relative_to(BASE_DIR)}[/cyan]")
            console.print("[dim]Be more specific[/dim]")
            return

    if not path or not path.exists():
        err.print(f"[red]Can't find:[/red] {target!r}")
        err.print("[dim]Try a meeting slug, doc slug, file path, or part of a filename[/dim]")
        return

    if not shutil.which(editor):
        err.print(f"[red]Editor not found:[/red] {editor!r}")
        err.print(f"[dim]Change with: /set editor vim[/dim]")
        return

    subprocess.Popen([editor, str(path)])
    console.print(f"[dim]→ {editor} {path.relative_to(BASE_DIR)}[/dim]")


# ── Quick meeting wizard ──────────────────────────────────────────────────────

def _quick_meeting(inline_tokens: list[str], settings: dict, history: list) -> None:
    """Guided meeting creation. Works inline (#standup) or interactive."""
    if inline_tokens:
        raw_title = " ".join(inline_tokens)
    else:
        raw_title = console.input("[cyan]Meeting title:[/cyan] ").strip()
        if not raw_title:
            return

    today_str = date.today().isoformat()

    raw_attendees = console.input(
        "[cyan]Attendees[/cyan] [dim](full names, comma-separated; Enter to skip)[/dim]: "
    ).strip()
    raw_notes = console.input(
        "[cyan]Notes[/cyan] [dim](brief summary; Enter to skip)[/dim]: "
    ).strip()

    attendee_names = (
        [a.strip() for a in raw_attendees.split(",") if a.strip()]
        if raw_attendees else []
    )

    from cli.tools import add_meeting
    result = add_meeting(
        title=raw_title,
        date=today_str,
        attendee_names=attendee_names,
        summary=raw_notes,
        notes=raw_notes,
    )
    console.print(f"[green]✓[/green] {result}")

    # Offer or auto-open notes
    from slugify import slugify
    slug = slugify(f"{today_str}-{raw_title}")
    notes_path = BASE_DIR / "notes" / "meetings" / f"{slug}.md"

    if settings.get("auto_open_notes") and notes_path.exists():
        _open_in_editor(slug, settings)
    elif notes_path.exists():
        console.print(f"[dim]Type 'open {slug}' to edit notes[/dim]")


# ── Quick action ──────────────────────────────────────────────────────────────

def _quick_action(description: str) -> None:
    if not description.strip():
        err.print("[red]Usage:[/red] +<action description>")
        return
    try:
        from core.models import ActionItem
        item = ActionItem.objects.create(description=description.strip())
        console.print(f"[green]✓[/green] Action [dim]#{item.pk}[/dim] — {description.strip()}")
    except Exception as e:
        err.print(f"[red]Error:[/red] {e}")


# ── Slash commands ────────────────────────────────────────────────────────────

def _handle_slash(line: str, settings: dict, history: list, stats: dict) -> None:
    """Handle /command lines."""
    parts = line[1:].split()
    if not parts:
        _print_help()
        return

    cmd = parts[0].lower()
    rest = parts[1:]

    if cmd in ("help", "h", "?"):
        _print_help()

    elif cmd == "today":
        _day_summary(settings)

    elif cmd == "stats":
        _print_stats(stats)

    elif cmd in ("open", "edit"):
        if rest:
            _open_in_editor(" ".join(rest), settings)
        else:
            err.print(f"[red]Usage:[/red] /{cmd} <slug or path>")

    elif cmd == "set":
        if not rest or rest == ["?"]:
            t = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE, pad_edge=False)
            t.add_column("Key", style="cyan")
            t.add_column("Current")
            t.add_column("Description", style="dim")
            for k in _SETTING_DEFAULTS:
                t.add_row(k, repr(settings.get(k, _SETTING_DEFAULTS[k])), _SETTING_DOCS.get(k, ""))
            console.print(t)
            console.print("[dim]/set <key> <value> to change[/dim]")
        elif len(rest) >= 2:
            msg = _set_setting(settings, rest[0], " ".join(rest[1:]))
            console.print(msg)
        else:
            err.print("[red]Usage:[/red] /set <key> <value>  or  /set  (list all)")

    elif cmd == "recap":
        days = int(rest[0]) if rest and rest[0].isdigit() else 7
        _run_recap(days, history)

    elif cmd == "focus":
        _run_focus(history)

    elif cmd == "paste":
        # Multi-line input mode — safe for any terminal, no bracketed paste needed.
        # Esc+Enter or Meta+Enter submits; Ctrl+C cancels.
        console.print("[dim]Paste mode — [bold]Esc+Enter[/bold] to submit, Ctrl+C to cancel[/dim]")
        try:
            from prompt_toolkit import prompt as _pt_prompt
            from prompt_toolkit.styles import Style as _Style
            pasted = _pt_prompt(
                "paste> ",
                multiline=True,
                style=_Style.from_dict({"": "dim"}),
            )
            if pasted.strip():
                import re
                joined = re.sub(r"[ \t]{2,}", " ",
                                pasted.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")).strip()
                console.print(f"[dim]→ {joined[:80]}{'…' if len(joined) > 80 else ''}[/dim]")
                _dispatch(joined, history, settings, stats)
        except (KeyboardInterrupt, EOFError):
            console.print("[dim]cancelled[/dim]")

    elif cmd == "note":
        if rest:
            _run_jot(" ".join(rest))
        else:
            _list_notes([])

    elif cmd == "meeting":
        _quick_meeting(rest, settings, history)

    else:
        err.print(f"[red]Unknown slash command:[/red] /{cmd}")
        err.print("[dim]Try /help[/dim]")


def _print_help() -> None:
    console.print("""
[bold cyan]provenance[/bold cyan] — command reference

[bold]Conversation[/bold]
  [cyan]ask[/cyan] <question>           Search CRM + notes, AI answers
  [cyan]ai[/cyan] <instruction>         Raw AI call (no context search)
  [cyan]search[/cyan] <query>           Search DB and notes

[bold]Capture[/bold]
  [cyan]note that[/cyan] <text>          Save observation as a markdown note (auto-titled)
  [cyan]note[/cyan] <text>              Freeform text → AI extracts people/meetings/actions
  [cyan]jot[/cyan] <text>              Same as "note that" — always saves raw, no extraction
  [cyan]remember[/cyan] <text>          Add to personal context (always visible to AI)
  [cyan]proof[/cyan] <text or file>     Proofread via AI

[bold]Quick entry[/bold]  [dim](prefix shorthands)[/dim]
  [cyan]@[/cyan]name                    Look up a person          [dim]@roger[/dim]
  [cyan]#[/cyan]title                   Create a meeting          [dim]#standup with team[/dim]
  [cyan]+[/cyan]task                    Add an action item        [dim]+send Amy the deck[/dim]
  [cyan]![/cyan]text                    Proofread text            [dim]!this sentance has erors[/dim]

[bold]Data[/bold]
  [cyan]people[/cyan] list / add / <slug>
  [cyan]meetings[/cyan] list / add / show <slug>
  [cyan]actions[/cyan] list / add / done <id>
  [cyan]docs[/cyan] list / show <slug>
  [cyan]open[/cyan] <slug or path>       Open file in editor

[bold]Slash commands[/bold]
  [cyan]/today[/cyan]                   Refresh day summary
  [cyan]/set[/cyan]                     List all settings
  [cyan]/set[/cyan] <key> <value>       Change a setting        [dim]/set editor vim[/dim]
  [cyan]/recap[/cyan] [days]            AI recap of recent activity  [dim]default 7[/dim]
  [cyan]/focus[/cyan]                   AI prioritization of open actions
  [cyan]/meeting[/cyan] [title]         Quick meeting wizard
  [cyan]/stats[/cyan]                   Your command usage history
  [cyan]/paste[/cyan]                   Multi-line input mode (Esc+Enter to submit)
  [cyan]/help[/cyan]                    This help

[bold]Session[/bold]
  [dim]exit / quit / Ctrl+D[/dim]

[dim]Tip: unknown input is automatically treated as an 'ask' question[/dim]
[dim]Tip: /set autocorrect false to disable typo correction[/dim]
""")


def _run_recap(days: int, history: list) -> None:
    q = (
        f"Give me a concise recap of my activity over the past {days} days. "
        "Search for recent meetings, look at open action items, and check relevant notes. "
        "Summarize key themes, people I've engaged with, and anything outstanding. Be direct."
    )
    _run_ask(q.split(), history)


def _run_focus(history: list) -> None:
    q = (
        "Look at all my open action items. Prioritize them for today based on urgency, "
        "due dates, and what makes sense given my context. Give me a concrete short list. "
        "Be direct — I need to know what to do first."
    )
    _run_ask(q.split(), history)


# ── Command handlers ──────────────────────────────────────────────────────────

def _run_ask(args: list, history: list) -> None:
    if not args:
        err.print("[red]Usage:[/red] ask <question>")
        return
    from cli.commands.ai import ask_agent
    ask_agent(" ".join(args), history=history)


def _run_search(args: list) -> None:
    if not args:
        err.print("[red]Usage:[/red] search <query>")
        return
    from cli.commands.search import search as _search
    _invoke(_search, args)


def _run_proof(args: list) -> None:
    if not args:
        err.print("[red]Usage:[/red] proof <text or file path>")
        return
    from cli.commands.ai import proof as _proof
    if args[0].lower() == "read" and len(args) > 1:
        args = args[1:]
    if len(args) == 1 and ("/" in args[0] or args[0].endswith(".md")):
        _invoke(_proof, ["--file", args[0]])
    else:
        _invoke(_proof, args)


def _run_ai(args: list) -> None:
    if not args:
        err.print("[red]Usage:[/red] ai <instruction>")
        return
    from cli.commands.ai import ai as _ai
    _invoke(_ai, args)


def _run_note(args: list) -> None:
    from cli.commands.capture import note as _note
    _invoke(_note, args)


def _run_jot(text: str) -> None:
    """Save text as a raw markdown note — no CRM extraction. Auto-generates a title via AI."""
    text = text.strip()
    if not text:
        err.print("[red]Usage:[/red] note that <observation>  or  jot <text>")
        return

    # Ask AI for a short title
    title = None
    try:
        from ai.registry import get_provider
        title = get_provider().complete(
            system=(
                "Generate a short 3–5 word title for this note. "
                "Return ONLY the title — no quotes, no punctuation, no explanation."
            ),
            user=text,
        ).strip().strip('"').strip("'")
    except Exception:
        pass

    if not title:
        title = " ".join(text.split()[:5])  # fallback: first 5 words

    from cli.commands.capture import _save_note
    _save_note(title, text)


def _run_remember(args: list) -> None:
    if not args:
        err.print("[red]Usage:[/red] remember <anything>")
        return
    from cli.commands.capture import remember as _remember
    _invoke(_remember, args)


def _run_people(args: list) -> None:
    from cli.commands.people import app as people_app
    _invoke_app(people_app, args)


def _run_meetings(args: list) -> None:
    from cli.commands.meetings import app as meetings_app
    _invoke_app(meetings_app, args)


def _run_actions(args: list) -> None:
    from cli.commands.actions import app as actions_app
    _invoke_app(actions_app, args)


def _run_docs(args: list) -> None:
    from cli.commands.docs import app as docs_app
    _invoke_app(docs_app, args)


def _run_reading(args: list) -> None:
    from cli.commands.reading import app as reading_app
    _invoke_app(reading_app, args)


def _run_read_url(url: str) -> None:
    """Save a URL to the reading list with spinner feedback."""
    with console.status("[dim]Fetching and summarizing…[/dim]"):
        from cli.commands.reading import save_reading_item
        result = save_reading_item(url)
    console.print(f"[green]✓[/green] {result}")


def _list_notes(args: list) -> None:
    """List all markdown files under notes/, grouped by folder."""
    filter_term = " ".join(args).lower() if args else ""
    notes_dir = BASE_DIR / "notes"
    if not notes_dir.exists():
        err.print("[red]notes/ directory not found[/red]")
        return

    groups: dict[str, list[Path]] = {}
    for p in sorted(notes_dir.rglob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True):
        if filter_term and filter_term not in p.name.lower() and filter_term not in p.read_text().lower()[:200]:
            continue
        folder = str(p.parent.relative_to(notes_dir)) if p.parent != notes_dir else "."
        groups.setdefault(folder, []).append(p)

    if not groups:
        console.print("[dim]No notes found[/dim]" + (f" matching {filter_term!r}" if filter_term else ""))
        return

    total = sum(len(v) for v in groups.values())
    console.print(f"\n[bold]Notes[/bold]  [dim]{total} files[/dim]\n")

    for folder in sorted(groups):
        label = "root" if folder == "." else folder
        console.print(f"[cyan]{label}/[/cyan]")
        for p in groups[folder]:
            rel = p.relative_to(notes_dir)
            console.print(f"  [dim]{p.name}[/dim]")
    console.print()
    console.print(f"[dim]open <filename> to edit  ·  notes <keyword> to filter[/dim]")


def _invoke(fn, args: list) -> None:
    import typer
    old_argv = sys.argv[:]
    sys.argv = ["provenance"] + [str(a) for a in args]
    try:
        app = typer.Typer()
        app.command()(fn)
        app(standalone_mode=False)
    except SystemExit:
        pass
    finally:
        sys.argv = old_argv


def _invoke_app(typer_app, args: list) -> None:
    old_argv = sys.argv[:]
    sys.argv = ["provenance"] + (args if args else ["--help"])
    try:
        typer_app(standalone_mode=False)
    except SystemExit:
        pass
    finally:
        sys.argv = old_argv


# ── Completer & prompt style ──────────────────────────────────────────────────

def _make_keybindings() -> KeyBindings:
    kb = KeyBindings()

    # eager=True ensures this fires before prompt_toolkit's default BracketedPaste
    # handler, which would otherwise insert newlines verbatim.
    @kb.add(Keys.BracketedPaste, eager=True)
    def _handle_paste(event) -> None:
        """Collapse newlines in pasted text so the whole block arrives as one line."""
        import re
        data = event.data.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
        data = re.sub(r"[ \t]{2,}", " ", data).strip()
        event.current_buffer.insert_text(data)

    return kb


def _make_completer() -> WordCompleter:
    return WordCompleter(
        [
            "ask", "search", "proof", "ai",
            "note", "jot", "remember",
            "people", "people list", "people add",
            "meetings", "meetings list", "meetings add", "meetings show",
            "actions", "actions list", "actions add", "actions done",
            "docs", "docs list", "docs show",
            "reading", "reading list", "reading add", "reading show", "reading done",
            "notes",
            "open", "edit",
            "/today", "/set", "/stats", "/recap", "/focus", "/meeting", "/paste", "/help",
            "help", "today", "stats",
            "exit", "quit",
        ],
        sentence=True,
        ignore_case=True,
    )


PROMPT_STYLE = Style.from_dict({
    "prompt.name":  "bold cyan",
    "prompt.time":  "dim cyan",
    "prompt.arrow": "bold cyan",
})


def _prompt_tokens(settings: dict):
    name = settings.get("assistant_name", "P")
    if settings.get("show_time_in_prompt", True):
        now = datetime.now(EASTERN)
        t = now.strftime("%-I:%M")
        return [
            ("class:prompt.name", name),
            ("class:prompt.time", f" {t}"),
            ("class:prompt.arrow", " ❯ "),
        ]
    return [("class:prompt.arrow", f"{name} ❯ ")]


# ── Main dispatch ─────────────────────────────────────────────────────────────

# Verbs whose trailing tokens are prose → eligible for autocorrect
_PROSE_VERBS = {"ask", "note", "remember", "ai"}
# Verbs that are fully structured → never autocorrect
_STRUCT_VERBS = {"people", "meetings", "actions", "docs", "search", "open", "edit",
                 "help", "today", "stats", "exit", "quit", "q"}


def _dispatch(line: str, history: list, settings: dict, stats: dict) -> bool:
    """Parse and run one REPL line. Returns False to exit."""
    line = line.strip()
    if not line:
        return True

    # Strip "provenance " prefix (muscle memory from CLI)
    if line.lower().startswith("provenance "):
        line = line[len("provenance "):].strip()

    # Exit
    if line.lower() in ("exit", "quit", "q"):
        return False

    # Help
    if line.lower() in ("help", "?"):
        _print_help()
        return True

    # Today (no slash)
    if line.lower() == "today":
        _day_summary(settings)
        return True

    # Stats (no slash)
    if line.lower() == "stats":
        _print_stats(stats)
        return True

    # Bare URL → save to reading list
    if re.match(r"^https?://\S+$", line):
        _record(stats, "read")
        _run_read_url(line)
        return True

    # Slash commands
    if line.startswith("/"):
        _handle_slash(line, settings, history, stats)
        return True

    # Bare file path or slug typed directly → open in editor
    # Matches: something.md  or  notes/foo/bar.md  or  a-meeting-slug (single token, no spaces)
    _lline = line.strip()
    if " " not in _lline and (
        _lline.endswith(".md")
        or "/" in _lline
        or (len(_lline) > 5 and "-" in _lline and _lline == _lline.lower()
            and not any(c in _lline for c in ("?", "!", "@", "#", "+")))
    ):
        # Looks like a slug or file path — try to open it, fall through to ask if not found
        candidate = Path(_lline)
        base_candidate = BASE_DIR / _lline
        if (candidate.exists() or base_candidate.exists()
                or _lline.endswith(".md")):
            _record(stats, "open")
            _open_in_editor(_lline, settings)
            return True

    # ── Prefix shorthands ────────────────────────────────────────────────────

    if line.startswith("@"):
        # @roger          → show Roger's profile
        # @roger meetings → ask about Roger's meetings (routes to ask agent)
        rest = line[1:].strip()
        _record(stats, "@")
        if not rest:
            _run_people(["list"])
        else:
            parts = rest.split(None, 1)
            name = parts[0]          # first word is the person handle
            extra = parts[1] if len(parts) > 1 else ""
            if extra:
                # Additional query — hand the whole thing to ask
                _run_ask(rest.split(), history)
            else:
                # Plain name/slug — show profile via people routing
                _run_people([name])
        return True

    if line.startswith("#"):
        # #standup with team → quick meeting
        rest = line[1:].strip().split()
        _record(stats, "#")
        _quick_meeting(rest, settings, history)
        return True

    if line.startswith("+"):
        # +send Amy the deck → quick action
        rest = line[1:].strip()
        _record(stats, "+")
        _quick_action(rest)
        return True

    if line.startswith("!"):
        # !bad sentance → proof
        rest = line[1:].strip()
        _record(stats, "!")
        _run_proof(rest.split() if rest else [])
        return True

    # ── Standard dispatch ────────────────────────────────────────────────────

    tokens = line.split()
    verb = tokens[0].lower()
    rest = tokens[1:]

    try:
        if verb in ("exit", "quit", "q"):
            return False

        elif verb in ("open", "edit"):
            _record(stats, "open")
            if rest:
                _open_in_editor(" ".join(rest), settings)
            else:
                err.print("[red]Usage:[/red] open <slug or path>")

        elif verb == "ask":
            _record(stats, "ask")
            prose = " ".join(rest)
            corrected, changed = _autocorrect(prose, settings)
            if changed:
                err.print(f"[dim]✓ {_preview(corrected)}[/dim]")
            _run_ask(corrected.split(), history)

        elif verb == "search":
            _record(stats, "search")
            _run_search(rest)

        elif verb == "proof":
            # Don't autocorrect — that's the whole point of proof
            _record(stats, "proof")
            _run_proof(rest)

        elif verb == "ai":
            _record(stats, "ai")
            prose = " ".join(rest)
            corrected, changed = _autocorrect(prose, settings)
            if changed:
                err.print(f"[dim]✓ {_preview(corrected)}[/dim]")
            _run_ai(corrected.split())

        elif verb == "note":
            _record(stats, "note")
            prose = " ".join(rest)
            corrected, changed = _autocorrect(prose, settings)
            if changed:
                err.print(f"[dim]✓ {_preview(corrected)}[/dim]")
            # "note that X" → save as raw markdown note (no CRM extraction)
            # "note <CRM text>" → extract people/meetings/actions as before
            stripped = corrected.lstrip()
            if stripped.lower().startswith("that "):
                _run_jot(stripped[5:])
            else:
                _run_note(corrected.split())

        elif verb == "jot":
            # Explicit raw-note command — always saves as markdown, no extraction
            _record(stats, "jot")
            prose = " ".join(rest)
            corrected, changed = _autocorrect(prose, settings)
            if changed:
                err.print(f"[dim]✓ {_preview(corrected)}[/dim]")
            _run_jot(corrected)

        elif verb == "remember":
            _record(stats, "remember")
            prose = " ".join(rest)
            corrected, changed = _autocorrect(prose, settings)
            if changed:
                err.print(f"[dim]✓ {_preview(corrected)}[/dim]")
            _run_remember(corrected.split())

        elif verb == "people":
            _record(stats, "people")
            _run_people(rest)

        elif verb == "meetings":
            _record(stats, "meetings")
            _run_meetings(rest)

        elif verb == "actions":
            _record(stats, "actions")
            _run_actions(rest)

        elif verb == "docs":
            _record(stats, "docs")
            _run_docs(rest)

        elif verb in ("reading", "read"):
            _record(stats, "reading")
            # "read <url>" → save URL directly; otherwise delegate to reading subcommands
            if rest and re.match(r"^https?://", rest[0]):
                _run_read_url(rest[0])
            else:
                _run_reading(rest if rest else ["list"])

        elif verb == "notes":
            _record(stats, "notes")
            _list_notes(rest)

        else:
            # Unknown verb → treat whole line as a natural-language question
            _record(stats, "ask")
            corrected, changed = _autocorrect(line, settings)
            if changed:
                err.print(f"[dim]✓ {_preview(corrected)}[/dim]")
            _run_ask(corrected.split(), history)

    except SystemExit:
        pass
    except KeyboardInterrupt:
        console.print()
    except Exception as e:
        err.print(f"[red]Error:[/red] {e}")

    return True


# ── Entry point ───────────────────────────────────────────────────────────────

def chat():
    """Start the full-featured interactive REPL."""
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    settings = _load_settings()
    stats = _load_stats()

    # Increment session counter
    stats["_sessions"] = stats.get("_sessions", 0) + 1

    # ── Greeting ─────────────────────────────────────────────────────────────
    greeting = _greeting_text()
    name = settings.get("assistant_name", "P")
    console.print(f"\n[bold cyan]{name}[/bold cyan]  [dim]{greeting}[/dim]")
    console.print()

    # ── Day summary ───────────────────────────────────────────────────────────
    if settings.get("day_summary", True):
        _day_summary(settings)
        console.print()

    # ── Welcome quote ─────────────────────────────────────────────────────────
    if settings.get("quote_on_start", True):
        try:
            from ai.registry import get_provider
            quote = get_provider().complete(
                system=(
                    "Respond with a single short quote (1–2 sentences) about work, "
                    "knowledge, relationships, or staying organized. "
                    "No attribution, no quote marks, no preamble."
                ),
                user="One quote.",
            )
            console.print(f"[dim italic]{quote.strip()}[/dim italic]\n")
        except Exception:
            pass

    # ── First-time hint ───────────────────────────────────────────────────────
    sessions = stats.get("_sessions", 1)
    if sessions == 1:
        console.print("[dim]Type /help to see all commands, or just start talking.[/dim]\n")

    # ── Self-improvement tip (every 50 total inputs) ──────────────────────────
    total = stats.get("_total", 0)
    if total > 0 and total % 50 == 0:
        user_stats = {k: v for k, v in stats.items() if not k.startswith("_")}
        if user_stats:
            top_cmd = max(user_stats, key=user_stats.__getitem__)
            tip_map = {
                "ask":      "Try '@name' for instant person lookup or '#title' to create a meeting fast.",
                "search":   "Try 'ask' for AI-powered answers rather than raw search.",
                "people":   "Try '@name' as a shorthand — it's faster than 'people <slug>'.",
                "meetings": "Try '#title' to create a meeting with an interactive wizard.",
                "note":     "Try 'remember <fact>' to add things the AI will always know about you.",
            }
            tip = tip_map.get(top_cmd)
            if tip:
                console.print(f"[dim]💡 {tip}[/dim]\n")

    # ── REPL loop ─────────────────────────────────────────────────────────────
    session: PromptSession = PromptSession(
        history=FileHistory(str(HISTORY_FILE)),
        auto_suggest=AutoSuggestFromHistory(),
        completer=_make_completer(),
        key_bindings=_make_keybindings(),
        style=PROMPT_STYLE,
    )

    # Multi-turn conversation history — shared across all `ask` calls this session
    history: list[dict] = []

    while True:
        try:
            line = session.prompt(lambda: _prompt_tokens(settings))
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]See you.[/dim]")
            break

        if not _dispatch(line, history, settings, stats):
            console.print("[dim]See you.[/dim]")
            break

    _save_stats(stats)
