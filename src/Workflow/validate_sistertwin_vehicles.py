"""Validate pair-years in VCdb; optionally replace the catalog validation table."""

import argparse
from collections import Counter
import sys

import pyodbc


COLUMNS = (
    "Make_A, Model_A, Make_B, Model_B, OriginalYearRange, "
    "StartYear, EndYear, [Year], VehicleA_ACES_Status, "
    "VehicleB_ACES_Status, ACES_Status"
)

VALIDATION_SQL = """
WITH ACESVehicles AS
(
    SELECT DISTINCT
        Make.MakeName,
        Model.ModelName,
        BaseVehicle.YearID
    FROM dbo.BaseVehicle
    INNER JOIN dbo.Make
        ON Make.MakeID = BaseVehicle.MakeID
    INNER JOIN dbo.Model
        ON Model.ModelID = BaseVehicle.ModelID
)
SELECT
    Expanded.Make_A,
    Expanded.Model_A,
    Expanded.Make_B,
    Expanded.Model_B,
    Expanded.OriginalYearRange,
    Expanded.StartYear,
    Expanded.EndYear,
    Expanded.[Year],
    CAST(CASE WHEN VehicleA.MakeName IS NOT NULL
        THEN N'ACES Valid' ELSE N'Invalid' END AS nvarchar(50))
        AS VehicleA_ACES_Status,
    CAST(CASE WHEN VehicleB.MakeName IS NOT NULL
        THEN N'ACES Valid' ELSE N'Invalid' END AS nvarchar(50))
        AS VehicleB_ACES_Status,
    CAST(CASE WHEN VehicleA.MakeName IS NOT NULL
                   AND VehicleB.MakeName IS NOT NULL
        THEN N'ACES Valid' ELSE N'Invalid' END AS nvarchar(50))
        AS ACES_Status
FROM dbo.Sister_Analysis_ACES_Check_Data AS Expanded
LEFT JOIN ACESVehicles AS VehicleA
    ON VehicleA.MakeName = Expanded.Make_A
   AND VehicleA.ModelName = Expanded.Model_A
   AND VehicleA.YearID = Expanded.[Year]
LEFT JOIN ACESVehicles AS VehicleB
    ON VehicleB.MakeName = Expanded.Make_B
   AND VehicleB.ModelName = Expanded.Model_B
   AND VehicleB.YearID = Expanded.[Year]
ORDER BY Expanded.Make_A, Expanded.Model_A, Expanded.[Year],
         Expanded.Make_B, Expanded.Model_B;
"""


def connect(server, database, trust_certificate):
    return pyodbc.connect(
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={server};DATABASE={database};"
        "Trusted_Connection=yes;Encrypt=yes;"
        f"TrustServerCertificate={'yes' if trust_certificate else 'no'};",
        autocommit=False,
        timeout=15,
    )


def validate(trust_certificate):
    connection = connect("VEHICLESQL", "VehicleDb", trust_certificate)
    try:
        cursor = connection.cursor()
        # Keep the input stable while checking that the joins preserve row count.
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;")
        count = cursor.execute(
            "SELECT COUNT_BIG(1) FROM dbo.Sister_Analysis_ACES_Check_Data;"
        ).fetchone()[0]
        if count == 0:
            raise ValueError("Validation input is empty; refusing to continue.")
        cursor.execute(VALIDATION_SQL)
        rows = [tuple(row) for row in cursor.fetchall()]
        if len(rows) != count:
            raise ValueError(f"Validation changed the row count: {count} -> {len(rows)}.")
        for row in rows:
            if any(value is None for value in row):
                raise ValueError("Unexpected NULL in validation output.")
            expected = "ACES Valid" if row[8:10] == ("ACES Valid", "ACES Valid") else "Invalid"
            if row[10] != expected:
                raise ValueError("Pair status does not match individual vehicle statuses.")
        connection.commit()
        return rows
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def store_results(rows, trust_certificate):
    connection = connect(r"CATALOGSQL\CATALOG", "CatalogDb", trust_certificate)
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SET XACT_ABORT ON; SET NOCOUNT ON; "
            "IF @@TRANCOUNT = 0 BEGIN TRANSACTION;"
        )
        cursor.execute("""
            DECLARE @Result int;
            EXEC @Result = sys.sp_getapplock
                @Resource = N'SisterTwin_Python_ValidationReturn',
                @LockMode = N'Exclusive',
                @LockOwner = N'Transaction',
                @LockTimeout = 0;
            IF @Result < 0
                THROW 50001, 'Another Python validation return is running.', 1;
        """)
        print("Processing: recreating catalog validation results...", flush=True)
        cursor.execute("""
            IF OBJECT_ID(N'dbo.SisterTwin_Vehicles_Raw_Expanded_VCDB', N'U') IS NOT NULL
                DROP TABLE dbo.SisterTwin_Vehicles_Raw_Expanded_VCDB;
        """)
        cursor.execute("""
            CREATE TABLE dbo.SisterTwin_Vehicles_Raw_Expanded_VCDB
            (
                Make_A nvarchar(50) NOT NULL,
                Model_A nvarchar(50) NOT NULL,
                Make_B nvarchar(50) NOT NULL,
                Model_B nvarchar(50) NOT NULL,
                OriginalYearRange nvarchar(50) NOT NULL,
                StartYear int NOT NULL,
                EndYear int NOT NULL,
                [Year] int NOT NULL,
                VehicleA_ACES_Status nvarchar(50) NOT NULL,
                VehicleB_ACES_Status nvarchar(50) NOT NULL,
                ACES_Status nvarchar(50) NOT NULL
            );
        """)
        print("Processing: returning all validation results to catalog...", flush=True)
        cursor.executemany(
            f"INSERT INTO dbo.SisterTwin_Vehicles_Raw_Expanded_VCDB ({COLUMNS}) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
            rows,
        )
        cursor.execute(f"SELECT {COLUMNS} FROM dbo.SisterTwin_Vehicles_Raw_Expanded_VCDB;")
        returned = [tuple(row) for row in cursor.fetchall()]
        if Counter(returned) != Counter(rows):
            raise ValueError("Returned catalog data does not match validation results.")
        connection.commit()
        print(f"Completed: {len(rows)} validation rows returned and verified.")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Replace catalog validation results.")
    parser.add_argument("--trust-server-certificate", action="store_true")
    args = parser.parse_args()
    try:
        if args.trust_server_certificate:
            print("WARNING: Server certificate verification is disabled for this run.", file=sys.stderr)
        print("Processing: checking both vehicles against VCdb...", flush=True)
        rows = validate(args.trust_server_certificate)
        counts = Counter(row[10] for row in rows)
        print(f"Validation rows: {len(rows)}")
        print(f"ACES Valid: {counts['ACES Valid']}")
        print(f"Invalid: {counts['Invalid']}")
        if args.execute:
            store_results(rows, args.trust_server_certificate)
        else:
            print("Check only. No tables or data changed.")
        return 0
    except Exception as error:
        print(f"FAILED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
