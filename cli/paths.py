"""
Single source of truth for all data paths.

PROVENANCE_HOME defaults to ~/.provenance but can be overridden via the
PROVENANCE_HOME environment variable, e.g. for testing or multiple profiles.
"""
import os
from pathlib import Path

PROVENANCE_HOME = Path(os.environ.get("PROVENANCE_HOME", "~/.provenance")).expanduser()

NOTES_DIR = PROVENANCE_HOME / "notes"
DB_PATH = PROVENANCE_HOME / "provenance.db"
ENV_FILE = PROVENANCE_HOME / ".env"
