"""
Shell completion functions for all provenance arguments.
Each function returns (value, help_text) tuples so completions
show names/descriptions alongside slugs/IDs.
"""


def _db():
    """Return True if Django models are available."""
    try:
        from django.db import connection  # noqa: F401
        return True
    except Exception:
        return False


def complete_person_slug(ctx, incomplete):
    if not _db():
        return []
    try:
        from core.models import Person
        qs = Person.objects.filter(
            slug__startswith=incomplete
        ).values_list("slug", "name")[:20]
        return [(slug, name) for slug, name in qs]
    except Exception:
        return []


def complete_meeting_slug(ctx, incomplete):
    if not _db():
        return []
    try:
        from core.models import Meeting
        qs = Meeting.objects.filter(
            slug__startswith=incomplete
        ).values_list("slug", "title")[:20]
        return [(slug, title) for slug, title in qs]
    except Exception:
        return []


def complete_doc_slug(ctx, incomplete):
    """Complete by file stem from notes/docs/."""
    try:
        from cli.paths import PROVENANCE_HOME as BASE_DIR
        docs_dir = BASE_DIR / "notes" / "docs"
        if not docs_dir.exists():
            return []
        return [
            (p.stem, p.stem)
            for p in sorted(docs_dir.rglob("*.md"))
            if p.stem.startswith(incomplete)
        ][:20]
    except Exception:
        return []


def complete_open_action_id(ctx, incomplete):
    if not _db():
        return []
    try:
        from core.models import ActionItem
        qs = ActionItem.objects.filter(
            status__in=["open", "in_progress"]
        ).values_list("pk", "description")[:20]
        return [
            (str(pk), desc[:60])
            for pk, desc in qs
            if str(pk).startswith(incomplete)
        ]
    except Exception:
        return []


def complete_attendees(ctx, incomplete):
    """Complete comma-separated person slugs — handles 'slug1,slug2,<TAB>'."""
    if not _db():
        return []
    try:
        from core.models import Person
        parts = incomplete.split(",")
        current = parts[-1]
        prefix = ",".join(parts[:-1])
        qs = Person.objects.filter(
            slug__startswith=current
        ).values_list("slug", "name")[:20]
        if prefix:
            return [(f"{prefix},{slug}", name) for slug, name in qs]
        return [(slug, name) for slug, name in qs]
    except Exception:
        return []


def complete_doc_or_file(ctx, incomplete):
    """Complete note slugs from notes/docs/, then fall back to filesystem paths."""
    results = list(complete_doc_slug(ctx, incomplete))

    from pathlib import Path
    try:
        p = Path(incomplete) if incomplete else Path(".")
        if incomplete and not incomplete.endswith("/"):
            parent, stem = p.parent, p.name
        else:
            parent, stem = p, ""
        for entry in sorted(parent.iterdir()):
            if entry.name.startswith(stem):
                suffix = "/" if entry.is_dir() else ""
                results.append((str(entry) + suffix, ""))
    except Exception:
        pass

    return results[:20]


def complete_org(ctx, incomplete):
    if not _db():
        return []
    try:
        from core.models import Person
        return list(
            Person.objects.filter(org__istartswith=incomplete)
            .exclude(org="")
            .values_list("org", flat=True)
            .distinct()[:20]
        )
    except Exception:
        return []


def complete_tags(ctx, incomplete):
    if not _db():
        return []
    try:
        from core.models import Person, Meeting
        parts = incomplete.split(",")
        current = parts[-1].strip()
        prefix = ",".join(parts[:-1])
        all_tags: set[str] = set()
        for qs in [
            Person.objects.exclude(tags="").values_list("tags", flat=True),
            Meeting.objects.exclude(tags="").values_list("tags", flat=True),
        ]:
            for tag_str in qs:
                for t in tag_str.split(","):
                    t = t.strip()
                    if t and t.startswith(current):
                        all_tags.add(t)
        if prefix:
            return [(f"{prefix},{t}", "") for t in sorted(all_tags)[:20]]
        return sorted(all_tags)[:20]
    except Exception:
        return []
