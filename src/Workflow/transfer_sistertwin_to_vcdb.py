"""Check expanded vehicles, or replace the VCdb validation input with them."""

import argparse
from collections import Counter
import sys

import pyodbc


COLUMNS = (
    "Make_A, Model_A, Make_B, Model_B, OriginalYearRange, "
    "StartYear, EndYear, [Year]"
)


def connect(server, database, trust_certificate):
    return pyodbc.connect(
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={server};DATABASE={database};"
        "Trusted_Connection=yes;Encrypt=yes;"
        f"TrustServerCertificate={'yes' if trust_certificate else 'no'};",
        autocommit=False,
        timeout=15,
    )


def read_expanded(trust_certificate):
    connection = connect(r"CATALOGSQL\CATALOG", "CatalogDb", trust_certificate)
    try:
        cursor = connection.cursor()
        cursor.execute(
            f"SELECT {COLUMNS} FROM dbo.SisterTwin_Vehicles_Raw_Expanded "
            "ORDER BY Make_A, Model_A, [Year], Make_B, Model_B;"
        )
        rows = [tuple(row) for row in cursor.fetchall()]
        connection.commit()
    finally:
        connection.close()

    if not rows:
        raise ValueError("Expanded source is empty; refusing to replace the destination.")
    for number, row in enumerate(rows, start=1):
        for value in row[:5]:
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Source row {number}: missing text value.")
            if len(value.encode("utf-16-le")) > 100:
                raise ValueError(f"Source row {number}: text exceeds nvarchar(50).")
        start, end, year = row[5:]
        if not all(isinstance(value, int) for value in (start, end, year)):
            raise ValueError(f"Source row {number}: years must be integers.")
        if not start <= year <= end:
            raise ValueError(f"Source row {number}: year outside its original range.")
    return rows


def run(execute, trust_certificate):
    rows = read_expanded(trust_certificate)
    print(f"Source checked: {len(rows)} expanded rows.", flush=True)
    connection = connect("VEHICLESQL", "VehicleDb", trust_certificate)
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT DB_NAME();")
        print(f"Destination connection successful: {cursor.fetchone()[0]}.", flush=True)
        connection.commit()
        if not execute:
            print("Check only. No tables or data changed.")
            return

        cursor.execute(
            "SET XACT_ABORT ON; SET NOCOUNT ON; "
            "IF @@TRANCOUNT = 0 BEGIN TRANSACTION;"
        )
        cursor.execute("""
            DECLARE @Result int;
            EXEC @Result = sys.sp_getapplock
                @Resource = N'SisterTwin_Python_VCdbInputTransfer',
                @LockMode = N'Exclusive',
                @LockOwner = N'Transaction',
                @LockTimeout = 0;
            IF @Result < 0
                THROW 50001, 'Another Python VCdb input transfer is running.', 1;
        """)
        print("Processing: recreating VCdb validation input...", flush=True)
        cursor.execute("""
            IF OBJECT_ID(N'dbo.Sister_Analysis_ACES_Check_Data', N'U') IS NOT NULL
                DROP TABLE dbo.Sister_Analysis_ACES_Check_Data;
            CREATE TABLE dbo.Sister_Analysis_ACES_Check_Data
            (
                Make_A nvarchar(50) NOT NULL,
                Model_A nvarchar(50) NOT NULL,
                Make_B nvarchar(50) NOT NULL,
                Model_B nvarchar(50) NOT NULL,
                OriginalYearRange nvarchar(50) NOT NULL,
                StartYear int NOT NULL,
                EndYear int NOT NULL,
                [Year] int NOT NULL
            );
        """)
        print("Processing: transferring expanded rows...", flush=True)
        cursor.executemany(
            f"INSERT INTO dbo.Sister_Analysis_ACES_Check_Data ({COLUMNS}) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
            rows,
        )
        cursor.execute(f"SELECT {COLUMNS} FROM dbo.Sister_Analysis_ACES_Check_Data;")
        returned_rows = [tuple(row) for row in cursor.fetchall()]
        # Check every value and duplicate count, not just the total number of rows.
        if Counter(returned_rows) != Counter(rows):
            raise ValueError("Destination values do not match the expanded source.")
        connection.commit()
        print(f"Completed: {len(rows)} rows transferred and verified.")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--trust-server-certificate", action="store_true")
    args = parser.parse_args()
    try:
        if args.trust_server_certificate:
            print("WARNING: Server certificate verification is disabled for this run.", file=sys.stderr)
        run(args.execute, args.trust_server_certificate)
        return 0
    except Exception as error:
        print(f"FAILED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
