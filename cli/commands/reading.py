"""Reading list — save URLs, get AI summaries, track what you've read."""
import json
import re
import sys
from html.parser import HTMLParser
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()
err = Console(stderr=True)
app = typer.Typer(help="Reading list — save and manage articles.")


# ── HTML fetch + parse ────────────────────────────────────────────────────────

class _TextExtractor(HTMLParser):
    """Strip HTML to plain text, skipping script/style/nav blocks."""

    _SKIP_TAGS = {"script", "style", "nav", "header", "footer", "aside", "noscript"}

    def __init__(self):
        super().__init__()
        self._skip_depth = 0
        self._chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() in self._SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag.lower() in self._SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth:
            text = data.strip()
            if text:
                self._chunks.append(text)

    def get_text(self) -> str:
        return " ".join(self._chunks)


def _fetch(url: str) -> tuple[str, str]:
    """Fetch URL, return (raw_title_from_html, body_text). Raises on failure."""
    import httpx

    resp = httpx.get(
        url,
        follow_redirects=True,
        timeout=15,
        headers={"User-Agent": "Mozilla/5.0 (compatible; Provenance/1.0)"},
    )
    resp.raise_for_status()
    html = resp.text

    # Extract <title>
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    raw_title = re.sub(r"\s+", " ", m.group(1)).strip() if m else ""

    # Strip HTML to text
    parser = _TextExtractor()
    parser.feed(html)
    body = parser.get_text()

    return raw_title, body


_SUMMARIZE_SYSTEM = (
    "You are a research assistant. Given the text of a web article, extract the title "
    "and write a concise 2-3 sentence summary of the key points. "
    'Respond with JSON only: {"title": "...", "summary": "..."}'
)


def _summarize(raw_title: str, body: str) -> tuple[str, str]:
    """Call AI to get a clean title and summary. Returns (title, summary)."""
    from ai.registry import get_provider

    # Truncate body to stay within a reasonable token budget
    excerpt = body[:6000]
    if raw_title:
        excerpt = f"Page title: {raw_title}\n\n{excerpt}"

    raw = get_provider().complete(system=_SUMMARIZE_SYSTEM, user=excerpt).strip()

    # Strip markdown code fences if the model added them
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        data = json.loads(raw)
        return data.get("title", raw_title).strip(), data.get("summary", "").strip()
    except json.JSONDecodeError:
        return raw_title, raw[:300]


# ── Core save function (shared by CLI and agent tool) ─────────────────────────

def save_reading_item(
    url: str,
    tags: str = "",
    notes: str = "",
    skip_summarize: bool = False,
) -> str:
    """
    Fetch, summarize, and save a URL to the reading list.
    Returns a human-readable result string.
    """
    from core.models import ReadingItem

    # Duplicate check
    existing = ReadingItem.objects.filter(url=url).first()
    if existing:
        return f"Already in reading list: {existing.title or url} (slug: {existing.slug})"

    title, summary = "", ""

    if not skip_summarize:
        try:
            raw_title, body = _fetch(url)
            title, summary = _summarize(raw_title, body)
        except Exception as e:
            err.print(f"[yellow]Warning:[/yellow] could not fetch/summarize: {e}")
            title = url  # fallback

    item = ReadingItem.objects.create(
        url=url,
        title=title,
        summary=summary,
        tags=tags,
        notes=notes,
    )
    return (
        f"Saved: {item.title or item.url}\n"
        f"  Slug: {item.slug}\n"
        f"  Summary: {item.summary[:200] + '…' if len(item.summary) > 200 else item.summary}"
    )


# ── CLI commands ──────────────────────────────────────────────────────────────

@app.command("add")
def add(
    url: str = typer.Argument(..., help="URL to save"),
    tags: str = typer.Option("", "--tags", "-t", help="Comma-separated tags"),
    notes: str = typer.Option("", "--notes", "-n", help="Your initial notes"),
    json_out: bool = typer.Option(False, "--json", help="JSON output"),
):
    """Fetch a URL, summarize it, and add it to your reading list."""
    with console.status("[dim]Fetching and summarizing…[/dim]"):
        result = save_reading_item(url, tags=tags, notes=notes)
    console.print(f"[green]✓[/green] {result}")


@app.command("list")
def list_items(
    status: Optional[str] = typer.Option(None, "--status", "-s", help="to_read | read | archived"),
    tag: Optional[str] = typer.Option(None, "--tag", "-t", help="Filter by tag"),
    limit: int = typer.Option(20, "--limit", "-n", help="Max items to show"),
    json_out: bool = typer.Option(False, "--json", help="JSON output"),
):
    """List reading list items."""
    from core.models import ReadingItem
    from django.db.models import Q

    qs = ReadingItem.objects.all()
    if status:
        qs = qs.filter(status=status)
    elif not status:
        # Default: to_read first, then others
        qs = qs.order_by(
            "-created_at"
        )
    if tag:
        qs = qs.filter(tags__icontains=tag)

    items = list(qs[:limit])

    if json_out:
        out = [
            {"slug": i.slug, "title": i.title, "url": i.url,
             "status": i.status, "tags": i.tags, "summary": i.summary}
            for i in items
        ]
        console.print(json.dumps(out, indent=2))
        return

    if not items:
        console.print("[dim]No items found.[/dim]")
        return

    STATUS_STYLE = {"to_read": "cyan", "read": "green", "archived": "dim"}
    t = Table(box=box.SIMPLE, pad_edge=False, show_header=True, header_style="bold")
    t.add_column("Status", style="dim", width=8)
    t.add_column("Title")
    t.add_column("Tags", style="dim")
    t.add_column("Slug", style="dim")

    for item in items:
        style = STATUS_STYLE.get(item.status, "")
        title = item.title or item.url[:60]
        t.add_row(
            f"[{style}]{item.status}[/{style}]",
            title[:70],
            item.tags or "",
            item.slug,
        )

    console.print(t)


@app.command("show")
def show(slug: str = typer.Argument(..., help="Item slug")):
    """Show full details for a reading list item."""
    from core.models import ReadingItem

    item = ReadingItem.objects.filter(slug=slug).first()
    if not item:
        err.print(f"[red]Not found:[/red] {slug}")
        raise typer.Exit(1)

    console.print(f"\n[bold]{item.title or item.url}[/bold]")
    console.print(f"[dim]{item.url}[/dim]")
    console.print(f"Status: [cyan]{item.status}[/cyan]  |  Tags: {item.tags or '—'}  |  Added: {item.created_at.date()}")
    if item.summary:
        console.print(f"\n[bold]Summary[/bold]\n{item.summary}")
    if item.notes:
        console.print(f"\n[bold]Notes[/bold]\n{item.notes}")
    console.print()


@app.command("done")
def done(slug: str = typer.Argument(..., help="Item slug to mark as read")):
    """Mark a reading list item as read."""
    from core.models import ReadingItem
    from django.utils import timezone

    item = ReadingItem.objects.filter(slug=slug).first()
    if not item:
        err.print(f"[red]Not found:[/red] {slug}")
        raise typer.Exit(1)

    item.status = "read"
    item.read_at = timezone.now()
    item.save()
    console.print(f"[green]✓[/green] Marked as read: {item.title or slug}")


@app.command("notes")
def add_notes(
    slug: str = typer.Argument(..., help="Item slug"),
    text: list[str] = typer.Argument(..., help="Notes to append"),
):
    """Append notes to a reading list item."""
    from core.models import ReadingItem

    item = ReadingItem.objects.filter(slug=slug).first()
    if not item:
        err.print(f"[red]Not found:[/red] {slug}")
        raise typer.Exit(1)

    new_note = " ".join(text).strip()
    item.notes = (item.notes + "\n\n" + new_note).strip() if item.notes else new_note
    item.save()
    console.print(f"[green]✓[/green] Notes updated on: {item.title or slug}")
