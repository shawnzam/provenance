import json
import shutil
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from cli.completions import complete_doc_slug, complete_tags

app = typer.Typer(help="Manage reference documents.", no_args_is_help=True)
console = Console()
err = Console(stderr=True)

from cli.paths import PROVENANCE_HOME as BASE_DIR
DOCS_DIR = BASE_DIR / "notes" / "docs"


def _get_doc(slug: str):
    from core.models import Document
    try:
        return Document.objects.get(slug=slug)
    except Document.DoesNotExist:
        err.print(f"[red]No document with slug '{slug}'.[/red]")
        err.print("Run [bold]provenance docs list[/bold] to see available slugs.")
        raise typer.Exit(1)


def _pdf_to_markdown(pdf_path: Path) -> str:
    """Convert a PDF to markdown text using pymupdf."""
    try:
        import fitz  # pymupdf
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
    """List all tracked documents."""
    from core.models import Document
    docs = list(Document.objects.all())

    if json_out:
        typer.echo(json.dumps([d.to_dict() for d in docs], indent=2))
        return

    if not docs:
        console.print("[dim]No documents yet. Use [bold]provenance docs import[/bold] to add one.[/dim]")
        return

    table = Table(show_header=True, header_style="bold blue")
    table.add_column("Slug")
    table.add_column("Title")
    table.add_column("Source")
    table.add_column("Tags")

    for d in docs:
        tags = ", ".join(t.strip() for t in d.tags.split(",") if t.strip())
        table.add_row(d.slug, d.title, d.source or "", tags)

    console.print(table)


@app.command("import")
def import_doc(
    file: Path = typer.Argument(..., help="Path to .md or .pdf file to import"),
    title: Optional[str] = typer.Option(None, "--title", "-t", help="Title (defaults to filename stem)"),
    tags: str = typer.Option("", "--tags", help="Comma-separated tags", autocompletion=complete_tags),
    notes: str = typer.Option("", "--notes", "-n", help="Your notes about this document"),
    json_out: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Import a .md or .pdf file into notes/docs/ and register it."""
    from core.models import Document
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

    if Document.objects.filter(slug=slug).exists():
        err.print(f"[red]A document with slug '{slug}' already exists.[/red]")
        err.print(f"Use [bold]provenance docs show {slug}[/bold] to view it.")
        raise typer.Exit(1)

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    dest_name = f"{slug}.md"
    dest_path = DOCS_DIR / dest_name
    relative_path = f"notes/docs/{dest_name}"

    if suffix == ".pdf":
        console.print(f"[dim]Converting PDF…[/dim]")
        content = _pdf_to_markdown(file)
        header = f"# {doc_title}\n\n_Imported from: {file.name}_\n\n---\n\n"
        dest_path.write_text(header + content)
        source = file.name
    else:
        shutil.copy2(file, dest_path)
        source = file.name if file.resolve() != dest_path.resolve() else ""

    doc = Document.objects.create(
        title=doc_title,
        file_path=relative_path,
        source=source,
        tags=tags,
        notes=notes,
    )

    from cli.indexer import index_notes
    index_notes()

    if json_out:
        typer.echo(json.dumps(doc.to_dict(), indent=2))
        return

    console.print(f"[green]Imported[/green] {doc.title} ([bold]{doc.slug}[/bold])")
    console.print(f"  File: [dim]{relative_path}[/dim]")
    if suffix == ".pdf":
        console.print(f"  Converted from PDF: [dim]{file.name}[/dim]")


@app.command("add")
def add_doc(
    title: str = typer.Argument(..., help="Document title"),
    file: Path = typer.Option(..., "--file", "-f", help="Path to existing .md file"),
    tags: str = typer.Option("", "--tags", help="Comma-separated tags"),
    notes: str = typer.Option("", "--notes", "-n", help="Your notes about this document"),
    json_out: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Register an existing .md file you placed manually in notes/docs/."""
    from core.models import Document
    from slugify import slugify

    if not file.exists():
        err.print(f"[red]File not found: {file}[/red]")
        raise typer.Exit(1)

    slug = slugify(title)
    if Document.objects.filter(slug=slug).exists():
        err.print(f"[red]A document with slug '{slug}' already exists.[/red]")
        raise typer.Exit(1)

    # Store path relative to project root if possible
    try:
        rel = file.resolve().relative_to(BASE_DIR)
        file_path = str(rel)
    except ValueError:
        file_path = str(file.resolve())

    doc = Document.objects.create(
        title=title,
        file_path=file_path,
        tags=tags,
        notes=notes,
    )

    from cli.indexer import index_notes
    index_notes()

    if json_out:
        typer.echo(json.dumps(doc.to_dict(), indent=2))
        return

    console.print(f"[green]Added[/green] {doc.title} ([bold]{doc.slug}[/bold])")
    console.print(f"  File: [dim]{file_path}[/dim]")


@app.command("show")
def show_doc(
    slug: str = typer.Argument(..., help="Document slug", autocompletion=complete_doc_slug),
    json_out: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show document details and a preview of its content."""
    doc = _get_doc(slug)

    if json_out:
        typer.echo(json.dumps(doc.to_dict(), indent=2))
        return

    console.print(f"\n[bold]{doc.title}[/bold]  [dim]{doc.slug}[/dim]")
    if doc.source:
        console.print(f"  Source: {doc.source}")
    console.print(f"  File:   {doc.file_path}")
    if doc.tags:
        tags = [t.strip() for t in doc.tags.split(",") if t.strip()]
        console.print(f"  Tags:   {', '.join(tags)}")
    if doc.notes:
        console.print(f"\n[dim]Notes:[/dim] {doc.notes}")

    doc_path = BASE_DIR / doc.file_path
    if doc_path.exists():
        content = doc_path.read_text()
        preview = content[:800]
        console.print(f"\n[dim]--- Preview ---[/dim]\n{preview}")
        if len(content) > 800:
            console.print(f"[dim]… ({len(content)} chars total)[/dim]")
    else:
        console.print(f"\n[red]File not found at {doc.file_path}[/red]")
    console.print()
