"""Tests of the real report publisher and v7 decision contract; no SQL runs."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from support import WORKFLOW

sys.path.insert(0, str(WORKFLOW))
import pyodbc
import run_sistertwin_workflow as workflow
import validate_sistertwin_vehicles as validation


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.guard = patch.object(pyodbc, "connect", side_effect=AssertionError("Live SQL is forbidden"))
        self.guard.start()
        self.addCleanup(self.guard.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def staging(self):
        staging = self.root / "Staging"
        reports = self.root / "Reports"
        staging.mkdir()
        reports.mkdir()
        a, b = staging / "validation.xlsx", staging / "gap.xlsx"
        a.write_bytes(b"validated-workbook-placeholder")
        b.write_bytes(b"gap-workbook-placeholder")
        return staging, reports, {"report_timestamp": "2026-11-17_120000",
                                  "validation_report": str(a), "gap_report": str(b)}

    def test_report_pair_uses_one_run_timestamp(self):
        staging, reports, status = self.staging()
        workflow.publish_reports(staging, status, "a" * 32, reports)
        self.assertFalse(staging.exists())
        self.assertEqual(Path(status["validation_report"]).name, "VCdb_Validation_2026-11-17_120000.xlsx")
        self.assertEqual(Path(status["gap_report"]).name, "GapReport_v7_2026-11-17_120000.xlsx")
        self.assertTrue(all(Path(status[k]).is_file() for k in ("validation_report", "gap_report")))
        self.assertEqual(len(list(reports.iterdir())), 1)

    def test_missing_second_file_never_publishes_report_directory(self):
        staging, reports, status = self.staging()
        Path(status["gap_report"]).unlink()
        with self.assertRaises(ValueError):
            workflow.publish_reports(staging, status, "b" * 32, reports)
        self.assertEqual(list(reports.iterdir()), [])
        self.assertTrue(staging.exists())

    def test_invalid_timestamp_never_renames_staging(self):
        staging, reports, status = self.staging()
        status["report_timestamp"] = "../outside"
        with self.assertRaises(ValueError):
            workflow.publish_reports(staging, status, "c" * 32, reports)
        self.assertTrue(Path(status["validation_report"]).exists())
        self.assertEqual(list(reports.iterdir()), [])

    def test_current_review_labels_are_accepted(self):
        rows = [("Needs review - no reference contains all eligible parts", 2),
                ("Needs review - missing part number", 1)]
        connection = MagicMock()
        connection.cursor.return_value.nextset.return_value = False
        connection.cursor.return_value.fetchall.return_value = rows
        with patch.object(validation, "connect", return_value=connection):
            self.assertEqual(workflow.build_v7(False), dict(rows))
        connection.commit.assert_called_once()
        connection.rollback.assert_not_called()
