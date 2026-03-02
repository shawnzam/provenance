"""
Management command: import all .md files from notes/docs/ into the Document table.
Skips files already registered (matched by file_path). Safe to re-run.
"""
import re
from pathlib import Path

from django.core.management.base import BaseCommand

BASE_DIR = Path(__file__).resolve().parents[3]
DOCS_DIR = BASE_DIR / "notes" / "docs"

# Map filename keywords → tags
_TAG_RULES = [
    (r"linkedin", "linkedin"),
    (r"resume", "resume"),
    (r"90.day|onboarding", "onboarding"),
    (r"governance|framework", "governance"),
    (r"job.desc", "job-description"),
    (r"research|analysis|playbook", "research"),
    (r"wharton", "wharton"),
    (r"dysgraphia", "personal"),
    (r"org", "org-chart"),
]


def _title_from_file(path: Path) -> str:
    """Extract the first # heading, or fall back to a prettified filename."""
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if line.startswith("#"):
            return re.sub(r"^#+\s*", "", line).strip()
    # Fallback: convert filename to title
    return path.stem.replace("-", " ").replace("_", " ").title()


def _tags_from_filename(name: str) -> str:
    tags = []
    for pattern, tag in _TAG_RULES:
        if re.search(pattern, name, re.IGNORECASE):
            tags.append(tag)
    return ", ".join(tags)


class Command(BaseCommand):
    help = "Import documents from notes/docs/ into the Document table"

    def handle(self, *args, **options):
        from core.models import Document

        if not DOCS_DIR.exists():
            self.stderr.write(f"docs directory not found: {DOCS_DIR}")
            return

        md_files = sorted(DOCS_DIR.glob("*.md"))
        if not md_files:
            self.stdout.write("No .md files found in notes/docs/")
            return

        created = skipped = 0
        for path in md_files:
            rel = str(path.relative_to(BASE_DIR))
            if Document.objects.filter(file_path=rel).exists():
                skipped += 1
                continue

            title = _title_from_file(path)
            tags = _tags_from_filename(path.name)

            from slugify import slugify
            base_slug = slugify(title)
            slug = base_slug
            n = 2
            while Document.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{n}"
                n += 1

            doc = Document(
                title=title,
                slug=slug,
                file_path=rel,
                source=path.name,
                tags=tags,
            )
            doc.save()
            created += 1
            self.stdout.write(f"  + {doc.slug}  ({rel})")

        self.stdout.write(
            self.style.SUCCESS(f"\nDone — {created} imported, {skipped} already present.")
        )
