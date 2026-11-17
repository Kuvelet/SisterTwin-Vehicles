"""Read saved VCdb validation results and export a timestamped Excel workbook."""

import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime
from pathlib import Path
import sys
import tempfile
from layout_support import REPORTS

import pyodbc
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo


QUERY = """
SELECT
    [Make_A], [Model_A], [Make_B], [Model_B],
    [OriginalYearRange], [StartYear], [EndYear], [Year],
    [VehicleA_ACES_Status], [VehicleB_ACES_Status], [ACES_Status]
FROM dbo.SisterTwin_Vehicles_Raw_Expanded_VCDB
ORDER BY [Make_A], [Model_A], [Year], [Make_B], [Model_B],
         [OriginalYearRange], [StartYear], [EndYear],
         [VehicleA_ACES_Status], [VehicleB_ACES_Status], [ACES_Status];
"""


def write_report(headers, rows, output_dir):
    if not rows:
        raise ValueError("Validation table is empty; no report was published.")
    if len(rows) > 1_048_575:
        raise ValueError("Results exceed Excel's single-sheet row limit.")

    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d_%H%M%S_%f")
    destination = output_dir / f"SisterTwin_VCdb_Validation_{timestamp}.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "VCdb Validation"
    sheet.append(headers)
    for row in rows:
        sheet.append(tuple(row))
        for cell in sheet[sheet.max_row]:
            if isinstance(cell.value, str):
                # Preserve source text literally, including formula-like values.
                cell.data_type = "s"
                cell.number_format = "@"
            elif isinstance(cell.value, int):
                cell.number_format = "0"

    sheet.freeze_panes = "A2"
    widths = [20, 28, 20, 28, 23, 13, 13, 11, 29, 29, 20]
    for index, width in enumerate(widths, 1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    sheet.row_dimensions[1].height = 32
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="176B63")
        cell.alignment = Alignment(vertical="center", wrap_text=True)

    table = Table(displayName="VCdbValidationResults", ref=sheet.dimensions)
    table.tableStyleInfo = TableStyleInfo(
        name="TableStyleMedium4", showRowStripes=True
    )
    sheet.add_table(table)

    # Publish only after the complete workbook has been written and checked.
    with tempfile.NamedTemporaryFile(
        dir=output_dir, prefix=".vcdb_export_", suffix=".xlsx", delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
    try:
        workbook.save(temporary_path)
        with closing(load_workbook(temporary_path, read_only=True)) as check:
            exported = check["VCdb Validation"]
            if exported.max_row != len(rows) + 1 or exported.max_column != len(headers):
                raise ValueError("Workbook verification failed: unexpected dimensions.")
            if next(exported.values) != tuple(headers):
                raise ValueError("Workbook verification failed: unexpected headers.")
        temporary_path.rename(destination)
    finally:
        workbook.close()
        temporary_path.unlink(missing_ok=True)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path,
        default=REPORTS,
    )
    parser.add_argument(
        "--trust-server-certificate", action="store_true",
        help="Skip server certificate verification; encryption remains enabled.",
    )
    args = parser.parse_args()
    if not args.output_dir.is_dir():
        raise ValueError(f"Output folder is unavailable: {args.output_dir}")

    trust = "yes" if args.trust_server_certificate else "no"
    if args.trust_server_certificate:
        print("WARNING: Server certificate verification is disabled for this run.", flush=True)
    connection_string = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        "SERVER=CATALOGSQL\\CATALOG;DATABASE=CatalogDb;"
        "Trusted_Connection=yes;Encrypt=yes;"
        f"TrustServerCertificate={trust};"
    )
    with closing(pyodbc.connect(connection_string, timeout=15, autocommit=True)) as connection:
        connection.timeout = 120
        cursor = connection.cursor()
        cursor.execute(QUERY)
        headers = [column[0] for column in cursor.description]
        rows = cursor.fetchall()
    destination = write_report(headers, rows, args.output_dir)
    counts = Counter(row[-1] for row in rows)
    print(f"Exported rows: {len(rows)}", flush=True)
    for status, count in sorted(counts.items()):
        print(f"{status}: {count}", flush=True)
    print(f"Excel file: {destination}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"EXPORT FAILED: {error}", file=sys.stderr, flush=True)
        sys.exit(1)
