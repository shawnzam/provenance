"""
Index notes files into SQLite FTS5 for full-text and lexical search.

Two entry points:
  index_notes()        — full rebuild (call after bulk writes or on demand)
  index_file(path)     — incremental update for a single file (call after each write)

Both are safe to call from any context where Django is already set up.
"""
from pathlib import Path
from cli.paths import PROVENANCE_HOME, NOTES_DIR


def index_file(path: Path) -> None:
    """Update the FTS5 index for a single notes file."""
    from django.db import connection

    try:
        text = path.read_text()
    except Exception:
        return

    rel = str(path.relative_to(PROVENANCE_HOME))

    with connection.cursor() as cur:
        cur.execute("DELETE FROM notes_fts WHERE path = %s", [rel])
        cur.execute("INSERT INTO notes_fts (path, content) VALUES (%s, %s)", [rel, text])

    # If this is a meeting notes file, sync Meeting.content too
    _sync_meeting_content(rel, text)


def index_notes(quiet: bool = True) -> None:
    """Full rebuild — walk all notes files and repopulate the FTS5 table."""
    from django.db import connection

    if not NOTES_DIR.exists():
        return

    rows = []
    for path in NOTES_DIR.rglob("*.md"):
        try:
            text = path.read_text()
        except Exception:
            continue
        rel = str(path.relative_to(PROVENANCE_HOME))
        rows.append((rel, text))

    with connection.cursor() as cur:
        cur.execute("DELETE FROM notes_fts")
        cur.executemany(
            "INSERT INTO notes_fts (path, content) VALUES (%s, %s)", rows
        )

    # Sync Meeting.content for all meetings that have a notes file
    from core.models import Meeting

    for meeting in Meeting.objects.exclude(notes_file=""):
        path = PROVENANCE_HOME / meeting.notes_file
        if path.exists():
            try:
                content = path.read_text()
                if content != meeting.content:
                    meeting.content = content
                    meeting.save(update_fields=["content", "updated_at"])
            except Exception:
                pass


def _sync_meeting_content(rel_path: str, text: str) -> None:
    """If rel_path matches a Meeting.notes_file, update Meeting.content."""
    try:
        from core.models import Meeting

        Meeting.objects.filter(notes_file=rel_path).update(content=text)
    except Exception:
        pass
