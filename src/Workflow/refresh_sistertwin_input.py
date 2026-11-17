"""Validate the raw CSV; optionally refresh the catalog input and run v0."""

import argparse
import csv
import re
import sys
from pathlib import Path

import pyodbc


COLUMNS = ["Years", "Make_A", "Model_A", "Make_B", "Model_B"]
from layout_support import CURRENT_CSV
DEFAULT_CSV = str(CURRENT_CSV)


def read_input(path):
    with Path(path).open("r", encoding="cp1252", newline="") as source:
        reader = csv.DictReader(source, strict=True)
        if (
            reader.fieldnames is None
            or len(reader.fieldnames) != len(COLUMNS)
            or set(reader.fieldnames) != set(COLUMNS)
        ):
            raise ValueError("Expected exactly these columns: " + ", ".join(COLUMNS))
        rows = list(reader)
    if not rows:
        raise ValueError("CSV is empty; refusing to replace the current data.")

    expected_expanded = 0
    records = []
    for number, row in enumerate(rows, start=2):
        if None in row:
            raise ValueError(f"Record {number}: extra CSV values.")
        for column in COLUMNS:
            value = row[column]
            if value is None or not value.strip():
                raise ValueError(f"Record {number}: blank {column}.")
            if len(value.encode("utf-16-le")) > 100:
                raise ValueError(f"Record {number}: {column} exceeds nvarchar(50).")

        years = row["Years"].replace("\u2013", "-").replace("\u2014", "-")
        # Reject forms that v0 might silently skip or partially expand.
        if re.fullmatch(r"[0-9]{4}(?:\s*-\s*[0-9]{4})?", years) is None:
            raise ValueError(f"Record {number}: unexpected year range {row['Years']!r}.")
        start, end = int(years[:4]), int(years[-4:])
        if end < start or end - start + 1 > 150:
            raise ValueError(f"Record {number}: invalid range or exceeds v0's 150-year limit.")
        expected_expanded += end - start + 1
        records.append(tuple(row[column] for column in COLUMNS))
    return records, expected_expanded


def refresh(records, expected_expanded, trust_certificate):
    connection_string = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        r"SERVER=CATALOGSQL\CATALOG;"
        "DATABASE=CatalogDb;Trusted_Connection=yes;Encrypt=yes;"
        f"TrustServerCertificate={'yes' if trust_certificate else 'no'};"
    )
    connection = pyodbc.connect(connection_string, autocommit=False, timeout=15)
    try:
        cursor = connection.cursor()
        cursor.execute("SET XACT_ABORT ON; SET NOCOUNT ON; IF @@TRANCOUNT = 0 BEGIN TRANSACTION;")
        cursor.execute("""
            DECLARE @Result int;
            EXEC @Result = sys.sp_getapplock
                @Resource = N'SisterTwin_Python_InputRefresh',
                @LockMode = N'Exclusive',
                @LockOwner = N'Transaction',
                @LockTimeout = 0;
            IF @Result < 0
                THROW 50001, 'Another Python input refresh is running.', 1;
        """)
        print("Processing: refreshing raw table...", flush=True)
        cursor.execute("TRUNCATE TABLE dbo.SisterTwin_Vehicles_Raw;")
        cursor.executemany("""
            INSERT INTO dbo.SisterTwin_Vehicles_Raw
                (Years, Make_A, Model_A, Make_B, Model_B)
            VALUES (?, ?, ?, ?, ?);
        """, records)

        print("Processing: running v0...", flush=True)
        cursor.execute("EXEC dbo.usp_CreateSisterTwin_Vehicles_Raw_Expanded_v0;")
        # Consume all procedure results before issuing verification queries.
        while cursor.nextset():
            pass

        raw_count = cursor.execute(
            "SELECT COUNT_BIG(1) FROM dbo.SisterTwin_Vehicles_Raw;"
        ).fetchone()[0]
        expanded_count = cursor.execute(
            "SELECT COUNT_BIG(1) FROM dbo.SisterTwin_Vehicles_Raw_Expanded;"
        ).fetchone()[0]
        if raw_count != len(records) or expanded_count != expected_expanded:
            raise ValueError(
                f"Count mismatch: raw={raw_count}, expanded={expanded_count}; "
                f"expected raw={len(records)}, expanded={expected_expanded}."
            )
        connection.commit()
        print(f"Completed: {raw_count} raw rows; {expanded_count} expanded rows.")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default=DEFAULT_CSV)
    parser.add_argument("--execute", action="store_true", help="Update SQL tables and run v0.")
    parser.add_argument("--trust-server-certificate", action="store_true")
    args = parser.parse_args()
    try:
        records, expected_expanded = read_input(args.csv)
        print(f"CSV validated: {len(records)} raw rows; expected expansion: {expected_expanded}.")
        if not args.execute:
            print("Check only. No database connection opened and no data changed.")
            return 0
        if args.trust_server_certificate:
            print("WARNING: Server certificate verification is disabled for this run.", file=sys.stderr)
        refresh(records, expected_expanded, args.trust_server_certificate)
        return 0
    except Exception as error:
        print(f"FAILED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
