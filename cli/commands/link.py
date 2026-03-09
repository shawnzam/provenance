"""
Wiki-link management commands.

  provenance link suggest          # show what would be linked (dry run)
  provenance link suggest --file notes/2026-03-07-ideas.md
  provenance link apply            # write links in-place (prompts first)
  provenance link apply --yes      # no prompt
  provenance link check            # report broken [[slugs]]
"""
import re
from difflib import unified_diff
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.syntax import Syntax

from cli.paths import PROVENANCE_HOME as BASE_DIR

console = Console()
err = Console(stderr=True)

app = typer.Typer(help="Manage [[wiki-links]] in notes.", no_args_is_help=True)

# Matches existing [[...]] so we don't double-link
_EXISTING_LINK_RE = re.compile(r"\[\[[^\]]+\]\]")
# Matches markdown headings — skip linking inside these
_HEADING_RE = re.compile(r"^#{1,6}\s")
# Matches fenced code blocks
_CODE_FENCE_RE = re.compile(r"^```")


# ---------------------------------------------------------------------------
# Build entity map: display name / title → slug
# ---------------------------------------------------------------------------

def _build_entity_map() -> dict[str, str]:
    """Return {display_name_lower: slug} for people, meetings, and documents."""
    entities: dict[str, str] = {}

    try:
        from core.models import Person
        for p in Person.objects.all():
            entities[p.name.lower()] = p.slug
    except Exception:
        pass

    try:
        from core.models import Meeting
        for m in Meeting.objects.all():
            entities[m.title.lower()] = m.slug
    except Exception:
        pass

    try:
        from core.models import Document
        for d in Document.objects.all():
            entities[d.title.lower()] = d.slug
    except Exception:
        pass

    # NOTE: freeform note stems are intentionally excluded — too many single-word
    # stems (e.g. "context", "open") match common English words and create noise.
    # Users can manually add [[slug]] links to freeform notes.

    return entities


# ---------------------------------------------------------------------------
# Core linking logic
# ---------------------------------------------------------------------------

def _insert_links(content: str, entities: dict[str, str]) -> str:
    """
    Return new content with first-occurrence [[slug]] links inserted.
    Skips headings, code blocks, and text already inside [[...]].
    Only links the first occurrence of each name per file.
    """
    lines = content.splitlines(keepends=True)
    in_code_block = False
    linked: set[str] = set()  # slugs already linked in this file
    result = []

    for line in lines:
        # Track code fences
        if _CODE_FENCE_RE.match(line):
            in_code_block = not in_code_block
            result.append(line)
            continue

        if in_code_block or _HEADING_RE.match(line):
            result.append(line)
            continue

        # Build a set of ranges already covered by [[...]] links
        occupied: set[int] = set()
        for m in _EXISTING_LINK_RE.finditer(line):
            occupied.update(range(m.start(), m.end()))

        # Try to replace first occurrence of each entity name
        # Sort by length descending so "Alex Rivera" matches before "Alex"
        for name, slug in sorted(entities.items(), key=lambda x: -len(x[0])):
            if slug in linked:
                continue
            pattern = re.compile(re.escape(name), re.IGNORECASE)
            m = pattern.search(line)
            if not m:
                continue
            # Skip if match overlaps an existing [[...]] span
            if occupied & set(range(m.start(), m.end())):
                continue
            # Insert link around the matched text (preserve original casing)
            original = line[m.start():m.end()]
            replacement = f"[[{slug}|{original}]]" if original.lower() != slug else f"[[{slug}]]"
            line = line[:m.start()] + replacement + line[m.end():]
            linked.add(slug)
            # Rebuild occupied after edit (offsets shift, but we only link once per slug anyway)
            occupied = set()
            for ex in _EXISTING_LINK_RE.finditer(line):
                occupied.update(range(ex.start(), ex.end()))

        result.append(line)

    return "".join(result)


def _get_target_files(file_arg: Optional[str]) -> list[Path]:
    if file_arg:
        p = Path(file_arg)
        if not p.is_absolute():
            p = BASE_DIR / p
        if not p.exists():
            err.print(f"[red]File not found: {file_arg}[/red]")
            raise typer.Exit(1)
        return [p]
    notes_dir = BASE_DIR / "notes"
    if not notes_dir.exists():
        return []
    return sorted(notes_dir.rglob("*.md"))


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@app.command("suggest")
def suggest(
    file: Optional[str] = typer.Option(None, "--file", "-f", help="Limit to one file"),
    min_length: int = typer.Option(4, "--min-length", help="Minimum entity name length to link"),
):
    """Show a diff of wiki-links that would be added. No files are changed.

    Examples:\n
      provenance link suggest\n
      provenance link suggest --file notes/2026-03-07-ideas.md
    """
    entities = {k: v for k, v in _build_entity_map().items() if len(k) >= min_length}
    files = _get_target_files(file)

    if not files:
        console.print("[yellow]No notes files found.[/yellow]")
        return

    changed = 0
    for path in files:
        original = path.read_text()
        updated = _insert_links(original, entities)
        if original == updated:
            continue
        changed += 1
        rel = path.relative_to(BASE_DIR)
        diff = list(unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=f"a/{rel}",
            tofile=f"b/{rel}",
        ))
        console.print(Syntax("".join(diff), "diff", theme="monokai"))

    if changed == 0:
        console.print("[green]No changes to suggest — all names already linked or not found.[/green]")
    else:
        console.print(f"\n[bold]{changed} file(s) would be updated.[/bold] Run [bold]provenance link apply[/bold] to write.")


@app.command("apply")
def apply(
    file: Optional[str] = typer.Option(None, "--file", "-f", help="Limit to one file"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    min_length: int = typer.Option(4, "--min-length", help="Minimum entity name length to link"),
):
    """Add [[wiki-links]] to notes in-place (first occurrence of each name).

    Examples:\n
      provenance link apply --yes\n
      provenance link apply --file notes/2026-03-07-ideas.md
    """
    entities = {k: v for k, v in _build_entity_map().items() if len(k) >= min_length}
    files = _get_target_files(file)

    if not files:
        console.print("[yellow]No notes files found.[/yellow]")
        return

    pending: list[tuple[Path, str]] = []
    for path in files:
        original = path.read_text()
        updated = _insert_links(original, entities)
        if original != updated:
            pending.append((path, updated))

    if not pending:
        console.print("[green]Nothing to update.[/green]")
        return

    console.print(f"[bold]{len(pending)} file(s) will be updated:[/bold]")
    for path, _ in pending:
        console.print(f"  {path.relative_to(BASE_DIR)}")

    if not yes:
        # typer.confirm can behave unexpectedly when stdin is non-tty (e.g. uv run).
        # Read input directly so the user always gets a real prompt.
        try:
            answer = input("\nWrite changes? [Y/n]: ").strip().lower()
        except EOFError:
            answer = ""
        if answer not in ("", "y", "yes"):
            console.print("[yellow]Aborted.[/yellow]")
            raise typer.Exit(0)

    for path, updated in pending:
        path.write_text(updated)
        console.print(f"[green]Updated[/green] {path.relative_to(BASE_DIR)}")

    from cli.indexer import index_notes
    index_notes()
    console.print(f"\n[bold green]Done — {len(pending)} file(s) updated.[/bold green]")


def _strip_broken_links(content: str) -> str:
    """Unwrap [[slug]] links that don't resolve to any known entity."""
    from cli.link_utils import resolve_slug

    def _replace(m: re.Match) -> str:
        raw = m.group(0)[2:-2]            # strip [[ ]]
        slug = raw.split("|")[0].strip()
        label = raw.split("|")[1].strip() if "|" in raw else slug
        if resolve_slug(slug, BASE_DIR) is None:
            return label  # unwrap to plain text
        return m.group(0)  # keep valid link

    return _EXISTING_LINK_RE.sub(_replace, content)


@app.command("clean")
def clean(
    file: Optional[str] = typer.Option(None, "--file", "-f", help="Limit to one file"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing"),
):
    """Remove [[wiki-links]] that don't resolve to any known entity.

    Use this to clean up noisy links written by an earlier run of 'apply'
    when the entity map included common words (e.g. [[open]], [[context]]).

    Examples:\n
      provenance link clean --dry-run\n
      provenance link clean --yes
    """
    files = _get_target_files(file)
    pending: list[tuple[Path, str]] = []

    for path in files:
        original = path.read_text()
        updated = _strip_broken_links(original)
        if original != updated:
            pending.append((path, updated))

    if not pending:
        console.print("[green]All [[wiki-links]] are valid — nothing to clean.[/green]")
        return

    if dry_run:
        for path, updated in pending:
            original = path.read_text()
            diff = list(unified_diff(
                original.splitlines(keepends=True),
                updated.splitlines(keepends=True),
                fromfile=str(path.relative_to(BASE_DIR)),
                tofile="(cleaned)",
            ))
            console.print(Syntax("".join(diff), "diff", theme="monokai"))
        console.print(f"\n[bold]{len(pending)} file(s) would be cleaned.[/bold]")
        return

    console.print(f"[bold]{len(pending)} file(s) have broken links to remove:[/bold]")
    for path, _ in pending:
        console.print(f"  {path.relative_to(BASE_DIR)}")

    if not yes:
        try:
            answer = input("\nClean these files? [Y/n]: ").strip().lower()
        except EOFError:
            answer = ""
        if answer not in ("", "y", "yes"):
            console.print("[yellow]Aborted.[/yellow]")
            raise typer.Exit(0)

    for path, updated in pending:
        path.write_text(updated)
        console.print(f"[green]Cleaned[/green] {path.relative_to(BASE_DIR)}")

    from cli.indexer import index_notes
    index_notes()
    console.print(f"\n[bold green]Done — {len(pending)} file(s) cleaned.[/bold green]")


@app.command("check")
def check(
    file: Optional[str] = typer.Option(None, "--file", "-f", help="Limit to one file"),
):
    """Report broken [[slugs]] — links that don't resolve to any known entity or file.

    Examples:\n
      provenance link check\n
      provenance link check --file notes/2026-03-07-ideas.md
    """
    from cli.link_utils import resolve_slug

    files = _get_target_files(file)
    broken: list[tuple[str, str]] = []  # (file, slug)

    for path in files:
        content = path.read_text()
        for m in _EXISTING_LINK_RE.finditer(content):
            raw = m.group(0)[2:-2]  # strip [[ and ]]
            slug = raw.split("|")[0].strip()  # handle [[slug|label]]
            if resolve_slug(slug, BASE_DIR) is None:
                broken.append((str(path.relative_to(BASE_DIR)), slug))

    if not broken:
        console.print("[green]All [[wiki-links]] resolve correctly.[/green]")
        return

    console.print(f"[bold red]{len(broken)} broken link(s):[/bold red]\n")
    for file_rel, slug in broken:
        console.print(f"  [dim]{file_rel}[/dim]  →  [red][[{slug}]][/red]")
