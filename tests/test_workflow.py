"""Offline tests. SQL connections are mocked; company databases are never called."""

import argparse
import csv
from contextlib import nullcontext
import importlib.util
import io
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch


from support import WORKFLOW as ROOT
sys.path.insert(0, str(ROOT))
if importlib.util.find_spec("pyodbc") is None:
    sys.modules["pyodbc"] = types.SimpleNamespace(connect=MagicMock())

import pyodbc
from openpyxl import load_workbook
import refresh_sistertwin_input as raw
import transfer_sistertwin_to_vcdb as transfer
import validate_sistertwin_vehicles as validation
import export_vcdb_validation as validation_export
import export_sistertwin_v7 as gap_export
import run_sistertwin_workflow as workflow


EXPANDED = ("Source", "Model A", "Target", "Model B", "2000-2001", 2000, 2001, 2000)
VALIDATED = EXPANDED + ("ACES Valid", "Invalid", "Invalid")


class BaseTest(unittest.TestCase):
    def setUp(self):
        self.guard = patch.object(pyodbc, "connect", side_effect=AssertionError("Real SQL connections are forbidden in tests."))
        self.guard.start()
        self.addCleanup(self.guard.stop)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT.parent)
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def connection(self, rows=()):
        connection = MagicMock()
        connection.cursor.return_value.nextset.return_value = False
        connection.cursor.return_value.fetchall.return_value = list(rows)
        return connection


class InputTests(BaseTest):
    def csv_file(self, rows, headers=None):
        path = self.folder / "input.csv"
        with path.open("w", encoding="cp1252", newline="") as target:
            writer = csv.writer(target)
            writer.writerow(raw.COLUMNS if headers is None else headers)
            writer.writerows(rows)
        return path

    def test_encoding_ranges_and_original_values(self):
        path = self.csv_file([
            ["2000\u20132001", "Citro\u00ebn", "Model", "Other", "Model"],
            ["2020", "One", "Model", "Two", "Model"],
        ])
        rows, count = raw.read_input(path)
        self.assertEqual((len(rows), count), (2, 3))
        self.assertEqual(rows[0][1], "Citro\u00ebn")
        self.assertEqual(rows[0][0], "2000\u20132001")

    def test_invalid_input_is_rejected(self):
        cases = [
            [],
            [["2001-2000", "A", "B", "C", "D"]],
            [["1900-2050", "A", "B", "C", "D"]],
            [["2000-2001", "", "B", "C", "D"]],
            [["2000-2001", "A" * 51, "B", "C", "D"]],
            [[" 2000-2001", "A", "B", "C", "D"]],
            [["2000 onwards", "A", "B", "C", "D"]],
            [["2000-2001", "A", "B", "C"]],
            [["2000-2001", "A", "B", "C", "D", "extra"]],
        ]
        for rows in cases:
            with self.subTest(rows=rows):
                with self.assertRaises(ValueError):
                    raw.read_input(self.csv_file(rows))

    def test_duplicate_headers_rejected(self):
        headers = raw.COLUMNS + ["Make_A"]
        with self.assertRaises(ValueError):
            raw.read_input(self.csv_file([["2000", "A", "B", "C", "D", "A"]], headers))


class TransactionTests(BaseTest):
    def test_raw_refresh_commits_only_verified_counts(self):
        for counts in [(1, 2), (1, 1)]:
            with self.subTest(counts=counts):
                connection = self.connection()
                connection.cursor.return_value.execute.return_value.fetchone.side_effect = [[n] for n in counts]
                with patch.object(pyodbc, "connect", return_value=connection):
                    if counts == (1, 2):
                        raw.refresh([("2000-2001", "A", "B", "C", "D")], 2, False)
                        connection.commit.assert_called_once()
                    else:
                        with self.assertRaises(ValueError):
                            raw.refresh([("2000-2001", "A", "B", "C", "D")], 2, False)
                        connection.rollback.assert_called_once()
                        connection.commit.assert_not_called()
                connection.close.assert_called_once()

    def test_transfer_check_only_does_not_write(self):
        connection = self.connection()
        connection.cursor.return_value.fetchone.return_value = ["VehicleDb"]
        with patch.object(transfer, "read_expanded", return_value=[EXPANDED]), patch.object(transfer, "connect", return_value=connection):
            transfer.run(False, False)
        queries = [call.args[0] for call in connection.cursor.return_value.execute.call_args_list]
        self.assertEqual(queries, ["SELECT DB_NAME();"])

    def test_transfer_verified_and_older_compatible(self):
        connection = self.connection([EXPANDED])
        connection.cursor.return_value.fetchone.return_value = ["VehicleDb"]
        with patch.object(transfer, "read_expanded", return_value=[EXPANDED]), patch.object(transfer, "connect", return_value=connection):
            transfer.run(True, False)
        queries = "\n".join(call.args[0] for call in connection.cursor.return_value.execute.call_args_list)
        self.assertIn("IF OBJECT_ID", queries)
        self.assertNotIn("DROP TABLE IF EXISTS", queries)
        self.assertEqual(connection.commit.call_count, 2)
        connection.rollback.assert_not_called()

    def test_transfer_mismatch_rolls_back(self):
        connection = self.connection([])
        connection.cursor.return_value.fetchone.return_value = ["VehicleDb"]
        with patch.object(transfer, "read_expanded", return_value=[EXPANDED]), patch.object(transfer, "connect", return_value=connection):
            with self.assertRaises(ValueError):
                transfer.run(True, False)
        connection.rollback.assert_called_once()
        self.assertEqual(connection.commit.call_count, 1)

    def test_validation_query_and_status(self):
        connection = self.connection([VALIDATED])
        connection.cursor.return_value.execute.return_value.fetchone.return_value = [1]
        with patch.object(validation, "connect", return_value=connection):
            self.assertEqual(validation.validate(False), [VALIDATED])
        self.assertIn("SELECT DISTINCT", validation.VALIDATION_SQL)
        self.assertNotIn("SELECT *", validation.VALIDATION_SQL)
        self.assertIn("VehicleB.YearID = Expanded.[Year]", validation.VALIDATION_SQL)
        connection.commit.assert_called_once()

    def test_validation_count_mismatch_stops(self):
        connection = self.connection([VALIDATED])
        connection.cursor.return_value.execute.return_value.fetchone.return_value = [2]
        with patch.object(validation, "connect", return_value=connection):
            with self.assertRaises(ValueError):
                validation.validate(False)
        connection.rollback.assert_called_once()

    def test_return_results_success_and_mismatch(self):
        for returned in [[VALIDATED], [VALIDATED, VALIDATED]]:
            with self.subTest(count=len(returned)):
                connection = self.connection(returned)
                with patch.object(validation, "connect", return_value=connection):
                    if len(returned) == 1:
                        validation.store_results([VALIDATED], False)
                        connection.commit.assert_called_once()
                    else:
                        with self.assertRaises(ValueError):
                            validation.store_results([VALIDATED], False)
                        connection.rollback.assert_called_once()
                        connection.commit.assert_not_called()

    def test_v7_calls_existing_procedure(self):
        connection = self.connection([("Include - selected reference vehicle", 2)])
        with patch.object(validation, "connect", return_value=connection):
            counts = workflow.build_v7(False)
        self.assertEqual(sum(counts.values()), 2)
        connection.cursor.return_value.execute.assert_any_call("EXEC dbo.usp_CreateSisterTwin_DescriptionGapReport_v7;")
        queries = "\n".join(call.args[0] for call in connection.cursor.return_value.execute.call_args_list)
        self.assertIn("COUNT_BIG(1) AS [RowCount]", queries)
        self.assertNotIn("AS RowCount", queries)
        connection.commit.assert_called_once()

    def test_v7_unexpected_status_rolls_back(self):
        connection = self.connection([(None, 1)])
        with patch.object(validation, "connect", return_value=connection):
            with self.assertRaises(ValueError):
                workflow.build_v7(False)
        connection.rollback.assert_called_once()
        connection.commit.assert_not_called()


class LockTests(BaseTest):
    def test_competing_run_is_rejected_and_connection_closed(self):
        connection = self.connection()
        connection.cursor.return_value.fetchone.return_value = [-1]
        with patch.object(validation, "connect", return_value=connection):
            with self.assertRaises(RuntimeError):
                with workflow.workflow_lock(False):
                    self.fail("Lock should not be granted")
        connection.close.assert_called_once()

    def test_lock_released_when_stage_fails(self):
        connection = self.connection()
        connection.cursor.return_value.fetchone.return_value = [0]
        with patch.object(validation, "connect", return_value=connection):
            with self.assertRaises(ValueError):
                with workflow.workflow_lock(False):
                    raise ValueError("stage failed")
        connection.close.assert_called_once()

    def test_lost_lock_is_detected(self):
        connection = self.connection()
        connection.cursor.return_value.fetchone.return_value = ["NoLock"]
        with self.assertRaises(RuntimeError):
            workflow.ensure_lock(connection)


class ExportTests(BaseTest):
    def gap_row(self):
        row = [None] * len(gap_export.COLUMNS)
        for name, value in {
            "GapGroupID": 1, "MissingRegionGroupID": 1,
            "Expansion Reason": "No expansion",
            "Inclusion Decision": "Include - selected reference vehicle",
            "Make": "Sample", "Model": "Reference", "Missing Make": "Sample",
            "Missing Model": "Target", "Year": 2020, "Part": "00123",
            "Description": "Sample part", "Missing Region": "USA-CAN-MEX",
            "Note": "=1+1",
        }.items():
            row[gap_export.COLUMNS.index(name)] = value
        return tuple(row)

    def test_gap_workbook_preserves_text_and_columns(self):
        path, count, decisions = gap_export.write_report([self.gap_row()], self.folder)
        self.assertEqual(count, 1)
        book = load_workbook(path)
        try:
            sheet = book.active
            self.assertEqual(sheet.max_column, 46)
            self.assertEqual(sheet.max_row, 2)
            self.assertEqual(sheet.freeze_panes, "A2")
            self.assertEqual(sheet.auto_filter.ref, "A1:AT2")
            self.assertEqual(sheet.cell(2, 11).value, "00123")
            note = sheet.cell(2, gap_export.COLUMNS.index("Note") + 1)
            self.assertEqual((note.value, note.data_type), ("=1+1", "s"))
            self.assertEqual(sheet.cell(2, 9).value, 2020)
        finally:
            book.close()

    def test_empty_gap_report_is_valid_header_only(self):
        path, count, decisions = gap_export.write_report([], self.folder)
        self.assertEqual(count, 0)
        book = load_workbook(path)
        try:
            self.assertEqual(book.active.max_row, 1)
        finally:
            book.close()

    def test_validation_workbook(self):
        headers = ["Make_A", "Model_A", "Make_B", "Model_B", "OriginalYearRange", "StartYear", "EndYear", "Year", "VehicleA_ACES_Status", "VehicleB_ACES_Status", "ACES_Status"]
        path = validation_export.write_report(headers, [VALIDATED], self.folder)
        book = load_workbook(path)
        try:
            self.assertEqual(book.active.max_column, 11)
            self.assertEqual(book.active.max_row, 2)
            self.assertEqual(book.active["K2"].value, "Invalid")
        finally:
            book.close()

    def test_changed_gap_counts_do_not_publish(self):
        connection = self.connection()
        connection.cursor.return_value.description = [(name,) for name in gap_export.COLUMNS]
        connection.cursor.return_value.fetchmany.side_effect = [[self.gap_row()], []]
        with patch.object(validation, "connect", return_value=connection):
            with self.assertRaises(ValueError):
                workflow.export_gap({"Include - selected reference vehicle": 2}, self.folder, False)
        self.assertEqual(list(self.folder.glob("*.xlsx")), [])
