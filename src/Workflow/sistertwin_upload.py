"""Snapshot and replace an explicitly confirmed CSV. No database access here."""

from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import re
from uuid import uuid4

MAX_BYTES = 2 * 1024 * 1024


def snapshot(source, expected_hash, run_dir):
    if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        raise ValueError("A valid upload checksum is required.")
    with Path(source).open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    if not data or len(data) > MAX_BYTES:
        raise ValueError("The uploaded CSV must be nonempty and no larger than 2 MB.")
    if hashlib.sha256(data).hexdigest() != expected_hash:
        raise ValueError("The uploaded CSV changed after confirmation. Submit it again.")
    destination = Path(run_dir) / "submitted_input.csv"
    with destination.open("xb") as stream:
        stream.write(data)
    return destination


def atomic_bytes(path, data):
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def replace_input(source, target, run_dir, status):
    """Caller holds the workflow lock; restore CSV if the raw refresh fails."""
    target = Path(target)
    previous = target.read_bytes()
    replacement = Path(source).read_bytes()
    backup = Path(run_dir) / "previous_input.csv"
    with backup.open("xb") as stream:
        stream.write(previous)
    status["previous_csv_backup"] = str(backup)
    status["uploaded_csv_sha256"] = hashlib.sha256(replacement).hexdigest()
    atomic_bytes(target, replacement)
    status["csv_replaced"] = True
    try:
        yield
    except BaseException:
        # Do not overwrite a separate manual edit made during the failed refresh.
        if target.read_bytes() != replacement:
            raise RuntimeError(f"Raw refresh failed and the CSV changed externally. Restore manually from {backup}.")
        atomic_bytes(target, previous)
        status["csv_replaced"] = False
        status["csv_restored_after_refresh_failure"] = True
        raise
