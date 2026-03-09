"""
Wiki-link resolution for Provenance notes.

Syntax: [[slug-or-filename]]

Resolution order (first match wins):
  1. Meeting   — slug → Meeting.notes_file
  2. Note file — any .md file under notes/ whose stem matches slug
  3. Person    — slug → inline summary from Person fields
"""
import re
from pathlib import Path

WIKI_LINK_RE = re.compile(r"\[\[([^\]\n]+)\]\]")


def _read_safe(path: Path) -> str | None:
    try:
        return path.read_text()
    except OSError:
        return None


def resolve_slug(slug: str, base_dir: Path) -> str | None:
    """Return content for a [[slug]], or None if nothing matches."""
    slug = slug.strip()

    # 1. Meeting
    try:
        from core.models import Meeting
        m = Meeting.objects.filter(slug=slug).first()
        if m and m.notes_file:
            text = _read_safe(base_dir / m.notes_file)
            if text is not None:
                return text
    except Exception:
        pass

    # 2. Any .md file under notes/ whose stem matches slug
    notes_dir = base_dir / "notes"
    if notes_dir.exists():
        for p in notes_dir.rglob("*.md"):
            if p.stem == slug:
                text = _read_safe(p)
                if text is not None:
                    return text

    # 3. Person — synthesise a brief inline summary
    try:
        from core.models import Person
        p = Person.objects.filter(slug=slug).first()
        if p:
            parts = [f"# {p.name}"]
            if p.role or p.org:
                parts.append(f"**Role:** {p.role or '—'}  **Org:** {p.org or '—'}")
            if p.email:
                parts.append(f"**Email:** {p.email}")
            if p.relationship_context:
                parts.append(f"\n{p.relationship_context.strip()}")
            if p.notes:
                parts.append(f"\n{p.notes.strip()}")
            return "\n".join(parts)
    except Exception:
        pass

    return None


def expand_links(
    content: str,
    base_dir: Path,
    depth: int = 2,
    visited: frozenset | None = None,
) -> str:
    """
    Replace every [[slug]] in *content* with the resolved content of that slug,
    up to *depth* recursive hops.  Already-visited slugs are skipped to prevent
    cycles.
    """
    if visited is None:
        visited = frozenset()

    if depth == 0 or not WIKI_LINK_RE.search(content):
        return content

    def _replace(match: re.Match) -> str:
        slug = match.group(1).strip()

        if slug in visited:
            return f"*[[{slug}]] — already included above*"

        resolved = resolve_slug(slug, base_dir)
        if resolved is None:
            return f"*[[{slug}]] — not found*"

        # Recurse before embedding
        inner = expand_links(resolved, base_dir, depth - 1, visited | {slug})

        header = f"\n\n{'─' * 60}\n### Linked: {slug}\n{'─' * 60}\n"
        footer = f"\n{'─' * 60}\n"
        return header + inner.strip() + footer

    return WIKI_LINK_RE.sub(_replace, content)
