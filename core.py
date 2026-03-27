"""
core.py — Shared MD5 logic for both CLI and GUI frontends.
No external dependencies; stdlib only.
"""

import hashlib
import json
import os
from pathlib import Path

# ── Default database path (sits next to this file) ───────────────────────────
DEFAULT_DB = Path(__file__).parent / "md5_database.json"


# ── Database helpers ──────────────────────────────────────────────────────────

def load_database(db_path: Path = DEFAULT_DB) -> dict:
    """Load the JSON hash database.  Returns {} if the file doesn't exist yet."""
    if not db_path.exists():
        return {}
    with open(db_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_database(db: dict, db_path: Path = DEFAULT_DB) -> None:
    """Persist the hash database to disk."""
    with open(db_path, "w", encoding="utf-8") as fh:
        json.dump(db, fh, indent=2)


def add_to_database(md5: str, label: str = "", db_path: Path = DEFAULT_DB) -> None:
    """Add (or update) an entry in the database."""
    db = load_database(db_path)
    db[md5] = label or md5
    save_database(db, db_path)


def remove_from_database(md5: str, db_path: Path = DEFAULT_DB) -> bool:
    """Remove a hash from the database.  Returns True if it was present."""
    db = load_database(db_path)
    if md5 in db:
        del db[md5]
        save_database(db, db_path)
        return True
    return False


# ── Hashing ───────────────────────────────────────────────────────────────────

def hash_file(filepath: str | Path, chunk_size: int = 1 << 20) -> str:
    """Return the MD5 hex-digest of a file, reading in chunks (memory-safe)."""
    h = hashlib.md5()
    with open(filepath, "rb") as fh:
        while chunk := fh.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


# ── Core check ────────────────────────────────────────────────────────────────

class CheckResult:
    IN_LIBRARY = "IN_LIBRARY"
    NEW_ARCHIVE = "NEW_ARCHIVE"

    def __init__(self, filepath: str, md5: str, status: str, label: str = ""):
        self.filepath = filepath
        self.md5      = md5
        self.status   = status          # IN_LIBRARY | NEW_ARCHIVE
        self.label    = label           # friendly name stored in DB, if any

    @property
    def in_library(self) -> bool:
        return self.status == self.IN_LIBRARY

    def __repr__(self) -> str:
        return f"<CheckResult {self.status} md5={self.md5} file={self.filepath}>"


def check_file(filepath: str | Path, db_path: Path = DEFAULT_DB) -> CheckResult:
    """
    Hash *filepath* and look it up in the database.

    Returns a CheckResult with status IN_LIBRARY or NEW_ARCHIVE.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    md5 = hash_file(filepath)
    db  = load_database(db_path)

    if md5 in db:
        return CheckResult(str(filepath), md5, CheckResult.IN_LIBRARY, db[md5])
    return CheckResult(str(filepath), md5, CheckResult.NEW_ARCHIVE)
