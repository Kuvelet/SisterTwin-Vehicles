"""Run the Sister/Twin workflow on the current computer using Windows authentication."""

import argparse
from collections import Counter
from contextlib import contextmanager, closing, redirect_stdout, redirect_stderr
from datetime import datetime, timezone
import json
import os
import re
from pathlib import Path
import socket
import sys
import tempfile
import traceback
from uuid import uuid4

import export_sistertwin_v7 as gap_export
import export_vcdb_validation as validation_export
import refresh_sistertwin_input as raw_input
import transfer_sistertwin_to_vcdb as transfer
import validate_sistertwin_vehicles as validation
import sistertwin_upload as upload
import hashlib
from layout_support import CONTROL, REPORTS, CURRENT_CSV, ID, atomic_json, read_json


DEFAULT_OUTPUT = REPORTS
BUILD = "2026-10-12.layout3.partlists"
DECISIONS = {
    "Include - selected reference vehicle",
    "Exclude - another reference vehicle selected",
    "Exclude - Missing Region is NULL",
    "Needs review - no reference contains all eligible parts",
    "Needs review - missing part number",
}


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_status(path, status):
    status["updated_utc"] = utc_now()
    atomic_json(path, status)


@contextmanager
def workflow_lock(trust):
    # A session-owned lock covers all stages, even though they use separate connections.
    connection = validation.connect(r"CATALOGSQL\CATALOG", "CatalogDb", trust)
    connection.autocommit = True
    acquired = False
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SET NOCOUNT ON;
            DECLARE @Result int;
            EXEC @Result = sys.sp_getapplock
                @Resource = N'SisterTwin_Python_FullWorkflow',
                @LockMode = N'Exclusive',
                @LockOwner = N'Session',
                @LockTimeout = 0;
            SELECT @Result;
        """)
        if cursor.fetchone()[0] < 0:
            raise RuntimeError("Another full Python workflow is running. Try again after it finishes.")
        acquired = True
        yield connection
    finally:
        # Release explicitly rather than relying on a pooled connection's close.
        try:
            if acquired:
                connection.cursor().execute("""
                    EXEC sys.sp_releaseapplock
                        @Resource = N'SisterTwin_Python_FullWorkflow',
                        @LockOwner = N'Session';
                """)
        finally:
            connection.close()


def ensure_lock(connection):
    cursor = connection.cursor()
    cursor.execute("""
        SELECT APPLOCK_MODE(N'public', N'SisterTwin_Python_FullWorkflow', N'Session');
    """)
    if cursor.fetchone()[0] != "Exclusive":
        raise RuntimeError("The workflow lock was lost; stopping before the next stage.")


def preflight(csv_path, output_dir, trust):
    records, expanded_count = raw_input.read_input(csv_path)
    print(f"CSV checked: {len(records)} rows; expected expansion: {expanded_count}.")
    # Check file creation before any database changes.
    with tempfile.NamedTemporaryFile(dir=output_dir, prefix=".sistertwin_access_", suffix=".tmp"):
        pass

    with closing(validation.connect(r"CATALOGSQL\CATALOG", "CatalogDb", trust)) as connection:
        cursor = connection.cursor()
        for name, kind in (
            ("dbo.SisterTwin_Vehicles_Raw", "U"),
            ("dbo.usp_CreateSisterTwin_Vehicles_Raw_Expanded_v0", "P"),
            ("dbo.usp_CreateSisterTwin_DescriptionGapReport_v7", "P"),
        ):
            cursor.execute("SELECT OBJECT_ID(?, ?);", name, kind)
            if cursor.fetchone()[0] is None:
                raise RuntimeError(f"Required catalog object is missing or not visible: {name}")
        cursor.execute("SELECT TOP (0) Years, Make_A, Model_A, Make_B, Model_B FROM dbo.SisterTwin_Vehicles_Raw;")
        connection.commit()
    with closing(validation.connect("VEHICLESQL", "VehicleDb", trust)) as connection:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT TOP (1) Make.MakeName, Model.ModelName, BaseVehicle.YearID
            FROM dbo.BaseVehicle
            INNER JOIN dbo.Make ON Make.MakeID = BaseVehicle.MakeID
            INNER JOIN dbo.Model ON Model.ModelID = BaseVehicle.ModelID;
        """)
        if cursor.fetchone() is None:
            raise RuntimeError("VCdb has no make/model/year records. Check its refresh status.")
        connection.commit()
    print("Both databases and the required objects are accessible.")
    return records, expanded_count


def build_v7(trust):
    connection = validation.connect(r"CATALOGSQL\CATALOG", "CatalogDb", trust)
    try:
        connection.timeout = 0
        cursor = connection.cursor()
        cursor.execute("SET XACT_ABORT ON; SET NOCOUNT ON; IF @@TRANCOUNT = 0 BEGIN TRANSACTION;")
        cursor.execute("EXEC dbo.usp_CreateSisterTwin_DescriptionGapReport_v7;")
        while cursor.nextset():
            pass
        cursor.execute("""
            SELECT [Inclusion Decision], COUNT_BIG(1) AS [RowCount]
            FROM dbo.SisterTwin_DescriptionGapReport_v7
            GROUP BY [Inclusion Decision];
        """)
        counts = dict(cursor.fetchall())
        if set(counts) - DECISIONS:
            raise ValueError(f"Unexpected v7 inclusion decisions: {list(counts)}")
        connection.commit()
        for decision, count in sorted(counts.items()):
            print(f"{decision}: {count}")
        print(f"v7 rows: {sum(counts.values())}")
        return counts
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def export_validation(rows, output_dir, trust):
    with closing(validation.connect(r"CATALOGSQL\CATALOG", "CatalogDb", trust)) as connection:
        connection.timeout = 120
        cursor = connection.cursor()
        cursor.execute(validation_export.QUERY)
        headers = [column[0] for column in cursor.description]
        stored = [tuple(row) for row in cursor.fetchall()]
        if Counter(stored) != Counter(rows):
            raise ValueError("Catalog validation data changed before export. No workbook published.")
        connection.commit()
    return validation_export.write_report(headers, stored, output_dir)


def export_gap(counts, output_dir, trust):
    with closing(validation.connect(r"CATALOGSQL\CATALOG", "CatalogDb", trust)) as connection:
        connection.timeout = 600
        cursor = connection.cursor()
        cursor.execute(gap_export.QUERY)
        if tuple(column[0] for column in cursor.description) != gap_export.COLUMNS:
            raise ValueError("The v7 export columns do not match the expected schema.")
        # Verify totals while streaming, before the exporter publishes the workbook.
        def verified_rows():
            seen = Counter()
            for row in gap_export.read_rows(cursor):
                seen[row[3]] += 1
                yield row
            if dict(seen) != counts:
                raise ValueError("v7 counts changed before export. No workbook published.")

        destination, count, decisions = gap_export.write_report(verified_rows(), output_dir)
        connection.commit()
    return destination


def execute_workflow(args, status, status_path):
    status["report_timestamp"] = datetime.now().strftime("%Y-%m-%d_%H%M%S")

    def stage(number, name, function, *arguments):
        status["current_stage"] = name
        write_status(status_path, status)
        print(f"\nProcessing [{number}/7]: {name}", flush=True)
        result = function(*arguments)
        status["completed_stages"].append(name)
        write_status(status_path, status)
        return result

    if not args.execute:
        stage(1, "Check CSV, connections and output folder", preflight,
              args.csv, args.output_dir, args.trust_server_certificate)
        print("\nCheck passed. No database tables or data changed.")
        return

    with workflow_lock(args.trust_server_certificate) as lock:
        replace_csv = getattr(args, "replace_raw_csv", False)
        run_dir = status_path.parent
        snapshot_path = run_dir / "input.csv"
        if replace_csv:
            # The worker already moved the uploaded file into this run; no duplicate copy.
            with snapshot_path.open("rb") as source:
                data = source.read(upload.MAX_BYTES + 1)
            if hashlib.sha256(data).hexdigest() != args.expected_csv_sha256:
                raise ValueError("Uploaded input changed after submission. Submit it again.")
        else:
            with args.csv.open("rb") as source:
                data = source.read(upload.MAX_BYTES + 1)
            with snapshot_path.open("xb") as destination:
                destination.write(data)
        if not data or len(data) > upload.MAX_BYTES:
            raise ValueError("Input must be nonempty and at most 2 MB.")
        args.csv = snapshot_path
        status["input_snapshot"] = str(snapshot_path)
        status["input_sha256"] = hashlib.sha256(data).hexdigest()
        checked, _ = raw_input.read_input(snapshot_path)
        if len(checked) > 10000:
            raise ValueError("Input may contain at most 10,000 vehicle pairs.")
        if any(ord(ch) < 32 or 127 <= ord(ch) <= 159 for row in checked for value in row for ch in value):
            raise ValueError("Input fields must not contain control characters.")
        records, expanded_count = stage(1, "Check CSV, connections and output folder", preflight,
                                       args.csv, args.output_dir, args.trust_server_certificate)
        status["raw_rows"] = len(records)
        status["expected_expanded_rows"] = expanded_count
        ensure_lock(lock)
        def refresh_input():
            if replace_csv:
                with upload.replace_input(args.csv, CURRENT_CSV, status_path.parent, status):
                    print(f"Previous CSV backed up: {status['previous_csv_backup']}")
                    write_status(status_path, status)
                    raw_input.refresh(records, expanded_count, args.trust_server_certificate)
            else:
                raw_input.refresh(records, expanded_count, args.trust_server_certificate)

        stage(2, "Refresh raw table and run v0", refresh_input)
        ensure_lock(lock)
        stage(3, "Transfer expanded vehicles to VEHICLESQL", transfer.run,
              True, args.trust_server_certificate)
        ensure_lock(lock)

        def validate_and_return():
            rows = validation.validate(args.trust_server_certificate)
            if len(rows) != expanded_count:
                raise ValueError("Validation row count differs from this run's expanded input.")
            validation.store_results(rows, args.trust_server_certificate)
            counts = dict(Counter(row[10] for row in rows))
            status["validation_counts"] = counts
            for name, count in sorted(counts.items()):
                print(f"{name}: {count}")
            return rows

        rows = stage(4, "Validate both vehicles and return results", validate_and_return)
        ensure_lock(lock)
        validation_path = stage(5, "Export validation workbook", export_validation,
                                rows, args.output_dir, args.trust_server_certificate)
        status["validation_report"] = str(validation_path)
        print(f"Excel file: {validation_path}")
        ensure_lock(lock)
        counts = stage(6, "Run existing v7 stored procedure", build_v7,
                       args.trust_server_certificate)
        status["gap_counts"] = counts
        ensure_lock(lock)
        gap_path = stage(7, "Export v7 workbook", export_gap,
                        counts, args.output_dir, args.trust_server_certificate)
        status["gap_report"] = str(gap_path)
        for path in (validation_path, gap_path):
            if not path.is_file() or path.stat().st_size == 0:
                raise RuntimeError(f"Expected report file is missing or empty: {path}")
        print(f"Excel file: {gap_path}")
        publish_reports(args.output_dir, status, status_path.parent.name)


def publish_reports(staging, status, request_id, reports=REPORTS):
    """Publish both workbooks with one directory rename on the same share."""
    timestamp = status["report_timestamp"]
    if not isinstance(timestamp, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{6}", timestamp):
        raise ValueError("Invalid report timestamp.")
    filenames = {
        "validation_report": f"VCdb_Validation_{timestamp}.xlsx",
        "gap_report": f"GapReport_v7_{timestamp}.xlsx",
    }
    for key, filename in filenames.items():
        path = Path(status[key])
        if path.parent.resolve() != staging.resolve() or not path.is_file() or path.stat().st_size == 0:
            raise ValueError("Missing or unexpected staged report.")
        path.rename(staging / filename)
    # Full request ID prevents collisions even when two requests share a timestamp.
    destination = reports / (datetime.now().strftime("%Y-%m-%d_%H%M%S") + "_" + request_id)
    staging.rename(destination)
    status["reports_folder"] = str(destination)
    for key, filename in filenames.items():
        status[key] = str(destination / filename)
    print(f"Reports published: {destination}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--trust-server-certificate", action="store_true")
    parser.add_argument("--request-id", required=True)
    args = parser.parse_args()
    if not ID.fullmatch(args.request_id) or not args.execute:
        parser.error("Use the worker for execution, or Check_Setup.cmd for a read-only check.")
    run_id = args.request_id
    run_dir = CONTROL / "Runs" / run_id
    status_path = run_dir / "status.json"
    status = read_json(status_path)
    if status.get("request_id") != run_id or status.get("status") != "Processing":
        raise ValueError("This request was not claimed or is already finished. Never replay a run.")
    request = read_json(run_dir / "request.json")
    args.replace_raw_csv = request.get("input_mode") == "upload"
    args.expected_csv_sha256 = request.get("csv_sha256")
    args.csv = run_dir / "input.csv" if args.replace_raw_csv else CURRENT_CSV
    args.output_dir = run_dir / "Staging"
    status.update(run_id=run_id, build=BUILD, completed_stages=[], computer=socket.gethostname())
    try:
        # The worker alone owns the log file; stdout/stderr go into that one file.
        args.output_dir.mkdir(exist_ok=False)
        REPORTS.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=REPORTS, prefix=".access_", suffix=".tmp"):
            pass
        print(f"Sister/Twin workflow build {BUILD}")
        print(f"Request: {run_id}")
        if args.trust_server_certificate:
            print("WARNING: Certificate verification is disabled; encryption remains enabled.")
        execute_workflow(args, status, status_path)
        status.update(status="Finishing", message="Reports generated; worker is verifying completion.", finished_utc=utc_now())
        write_status(status_path, status)
        return 0
    except (Exception, KeyboardInterrupt) as error:
        status.update(status="Failed", message=str(error) or "Interrupted.", error=str(error), finished_utc=utc_now())
        traceback.print_exc()
        try:
            # Only remove known temporary export files inside this run, never published reports.
            if args.output_dir.is_dir():
                for path in args.output_dir.iterdir():
                    if path.is_file() and not path.is_symlink() and path.suffix in (".xlsx", ".tmp"):
                        path.unlink()
                if not any(args.output_dir.iterdir()):
                    args.output_dir.rmdir()
            write_status(status_path, status)
        except OSError as cleanup_error:
            print(f"Could not finish status/temporary-file cleanup: {cleanup_error}")
        print("Earlier database stages may remain committed. No automatic rerun is attempted.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
