"""
Document commands — file-based, no DB.

Documents are just .md files. The notes/docs/ directory is the canonical
location, but any note can serve as a "document". Slugs = file stems.

  provenance docs list
  provenance docs show <slug>
  provenance docs import <file> [--title "..."]
"""
import json
import shutil
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from cli.paths import PROVENANCE_HOME as BASE_DIR

app = typer.Typer(help="Manage reference documents (notes in notes/docs/).", no_args_is_help=True)
console = Console()
err = Console(stderr=True)

DOCS_DIR = BASE_DIR / "notes" / "docs"


def _title_from_file(path: Path) -> str:
    """Extract first # heading or fall back to formatted stem."""
    try:
        for line in path.read_text().splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    except OSError:
        pass
    return path.stem.replace("-", " ").replace("_", " ").title()


def _find_note(slug: str) -> Path | None:
    """Find a .md file in notes/ whose stem matches slug."""
    notes_dir = BASE_DIR / "notes"
    if not notes_dir.exists():
        return None
    for p in notes_dir.rglob("*.md"):
        if p.stem == slug:
            return p
    return None


def _pdf_to_markdown(pdf_path: Path) -> str:
    try:
        import fitz
    except ImportError:
        err.print("[red]pymupdf is required for PDF import.[/red]")
        err.print("Run: uv add pymupdf")
        raise typer.Exit(1)

    doc = fitz.open(str(pdf_path))
    pages = []
    for i, page in enumerate(doc, 1):
        text = page.get_text().strip()
        if text:
            pages.append(f"## Page {i}\n\n{text}")
    doc.close()

    if not pages:
        err.print("[red]No text found in PDF. It may be a scanned image.[/red]")
        raise typer.Exit(1)

    return "\n\n---\n\n".join(pages)


@app.command("list")
def list_docs(
    json_out: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List all .md files in notes/docs/."""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(DOCS_DIR.rglob("*.md"))

    if not files:
        console.print("[dim]No documents yet. Drop a .md file in notes/docs/ or use [bold]provenance docs import[/bold].[/dim]")
        return

    if json_out:
        out = [{"slug": p.stem, "title": _title_from_file(p), "path": str(p.relative_to(BASE_DIR))} for p in files]
        typer.echo(json.dumps(out, indent=2))
        return

    table = Table(show_header=True, header_style="bold blue")
    table.add_column("Slug")
    table.add_column("Title")
    table.add_column("Path", style="dim")

    for p in files:
        table.add_row(p.stem, _title_from_file(p), str(p.relative_to(BASE_DIR)))

    console.print(table)


@app.command("show")
def show_doc(
    slug: str = typer.Argument(..., help="File stem (slug) of the document"),
    json_out: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show a document by its slug (file stem)."""
    path = _find_note(slug)
    if not path:
        err.print(f"[red]No note found with slug '{slug}'.[/red]")
        err.print("Run [bold]provenance docs list[/bold] or [bold]provenance notes list[/bold].")
        raise typer.Exit(1)

    title = _title_from_file(path)
    rel = str(path.relative_to(BASE_DIR))

    if json_out:
        content = path.read_text()
        typer.echo(json.dumps({"slug": slug, "title": title, "path": rel, "content": content}, indent=2))
        return

    console.print(f"\n[bold]{title}[/bold]  [dim]{slug}[/dim]")
    console.print(f"  File: [dim]{rel}[/dim]")
    content = path.read_text()
    preview = content[:800]
    console.print(f"\n[dim]--- Preview ---[/dim]\n{preview}")
    if len(content) > 800:
        console.print(f"[dim]… ({len(content)} chars total)[/dim]")
    console.print()


@app.command("import")
def import_doc(
    file: Path = typer.Argument(..., help="Path to .md or .pdf file to import"),
    title: Optional[str] = typer.Option(None, "--title", "-t", help="Override title (used as heading)"),
    json_out: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Copy a .md or .pdf file into notes/docs/ and index it."""
    from slugify import slugify

    if not file.exists():
        err.print(f"[red]File not found: {file}[/red]")
        raise typer.Exit(1)

    suffix = file.suffix.lower()
    if suffix not in {".md", ".pdf"}:
        err.print(f"[red]Unsupported file type '{suffix}'. Use .md or .pdf.[/red]")
        raise typer.Exit(1)

    doc_title = title or file.stem.replace("-", " ").replace("_", " ").title()
    slug = slugify(doc_title)

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    dest_path = DOCS_DIR / f"{slug}.md"

    if dest_path.exists():
        err.print(f"[red]File already exists: {dest_path.relative_to(BASE_DIR)}[/red]")
        raise typer.Exit(1)

    if suffix == ".pdf":
        console.print("[dim]Converting PDF…[/dim]")
        content = _pdf_to_markdown(file)
        header = f"# {doc_title}\n\n_Imported from: {file.name}_\n\n---\n\n"
        dest_path.write_text(header + content)
    else:
        shutil.copy2(file, dest_path)
        # Ensure file has a # heading so title is discoverable
        existing = dest_path.read_text()
        if not existing.lstrip().startswith("# "):
            dest_path.write_text(f"# {doc_title}\n\n{existing}")

    from cli.indexer import index_notes
    index_notes()

    rel = str(dest_path.relative_to(BASE_DIR))
    if json_out:
        typer.echo(json.dumps({"slug": slug, "title": doc_title, "path": rel}, indent=2))
        return

    console.print(f"[green]Imported[/green] {doc_title} ([bold]{slug}[/bold])")
    console.print(f"  File: [dim]{rel}[/dim]")
