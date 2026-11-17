"""Local filesystem tests only; never connects to a database."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from support import WORKFLOW
sys.path.insert(0, str(WORKFLOW))
import sistertwin_upload as upload


class UploadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "upload.csv"
        self.source.write_bytes(b"new data")
        self.target = self.root / "current.csv"
        self.target.write_bytes(b"old data")
        self.digest = hashlib.sha256(self.source.read_bytes()).hexdigest()

    def test_snapshot_is_independent(self):
        saved = upload.snapshot(self.source, self.digest, self.root)
        self.source.write_bytes(b"changed")
        self.assertEqual(saved.read_bytes(), b"new data")

    def test_bad_checksum_never_snapshots(self):
        for checksum in (None, "", "x" * 64, "f" * 64):
            with self.assertRaises(ValueError):
                upload.snapshot(self.source, checksum, self.root)
        self.assertFalse((self.root / "submitted_input.csv").exists())

    def test_oversized_or_empty_upload_rejected(self):
        for data in (b"", b"a" * (upload.MAX_BYTES + 1)):
            self.source.write_bytes(data)
            with self.assertRaises(ValueError):
                upload.snapshot(self.source, hashlib.sha256(data).hexdigest(), self.root)

    def test_success_backs_up_and_keeps_new_default(self):
        status = {}
        with upload.replace_input(self.source, self.target, self.root, status):
            self.assertEqual(self.target.read_bytes(), b"new data")
        self.assertEqual((self.root / "previous_input.csv").read_bytes(), b"old data")
        self.assertTrue(status["csv_replaced"])

    def test_refresh_failure_restores_old_csv(self):
        status = {}
        with self.assertRaisesRegex(ValueError, "SQL failed"):
            with upload.replace_input(self.source, self.target, self.root, status):
                raise ValueError("SQL failed")
        self.assertEqual(self.target.read_bytes(), b"old data")
        self.assertTrue(status["csv_restored_after_refresh_failure"])

    def test_external_edit_not_overwritten_during_recovery(self):
        with self.assertRaisesRegex(RuntimeError, "changed externally"):
            with upload.replace_input(self.source, self.target, self.root, {}):
                self.target.write_bytes(b"manual edit")
                raise ValueError("SQL failed")
        self.assertEqual(self.target.read_bytes(), b"manual edit")

    def test_atomic_replace_failure_preserves_previous(self):
        with patch.object(upload.os, "replace", side_effect=OSError("network unavailable")):
            with self.assertRaises(OSError):
                with upload.replace_input(self.source, self.target, self.root, {}):
                    self.fail("Must not run refresh")
        self.assertEqual(self.target.read_bytes(), b"old data")
        self.assertEqual(list(self.root.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
