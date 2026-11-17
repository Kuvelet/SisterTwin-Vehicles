"""Export the saved v7 gap report without changing or filtering its records."""

import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime
from pathlib import Path
import sys
import tempfile
from zipfile import ZipFile

import pyodbc
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


COLUMNS = (
    "GapGroupID", "MissingRegionGroupID", "Expansion Reason",
    "Inclusion Decision", "Make", "Model", "Missing Make", "Missing Model",
    "Year", "Archetype", "Part", "PartGroup", "Category", "Description",
    "Position", "cid", "Engine", "Engine Designation", "EngineMake",
    "EngineVIN", "Reference Region", "Missing Region", "Submodel", "Air",
    "Aspiration", "BodyStyle", "BrakeType", "CarbNumber", "CarbType", "Color",
    "Connection Type", "Cylinder Head Type", "Drive Type", "Emissions",
    "FootNote", "Fuel System", "Fuel Type", "Lead Length", "Note",
    "OE Number", "Quantity", "Split Year", "Transmission", "Vendor",
    "Supersession Note", "ESN Range",
)
QUERY = (
    "SELECT " + ", ".join(f"[{column}]" for column in COLUMNS)
    + " FROM dbo.SisterTwin_DescriptionGapReport_v7"
    + " ORDER BY [Missing Make], [Missing Model], [Year], [Description],"
    + " [Make], [Model], [Part], [Missing Region],"
    + " [GapGroupID], [MissingRegionGroupID];"
)
from layout_support import REPORTS
DEFAULT_OUTPUT = REPORTS


def read_rows(cursor):
    while True:
        batch = cursor.fetchmany(2000)
        if not batch:
            return
        yield from batch


def write_report(rows, output_dir):
    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d_%H%M%S_%f")
    destination = output_dir / f"SisterTwin_GapReport_v7_{timestamp}.xlsx"
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("v7 Gap Report")
    sheet.freeze_panes = "A2"
    sheet.sheet_view.zoomScale = 85
    sheet.row_dimensions[1].height = 34
    widths = {
        "GapGroupID": 16, "MissingRegionGroupID": 25,
        "Expansion Reason": 52, "Inclusion Decision": 50,
        "Year": 10, "Part": 22, "Description": 40,
        "Model": 27, "Missing Model": 27, "PartGroup": 32,
        "Category": 32, "Note": 48, "FootNote": 48,
        "Supersession Note": 48,
    }
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="176B63")
    header_cells = []
    for index, name in enumerate(COLUMNS, 1):
        sheet.column_dimensions[get_column_letter(index)].width = widths.get(name, 24)
        cell = WriteOnlyCell(sheet, value=name)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        header_cells.append(cell)
    sheet.append(header_cells)

    count = 0
    decisions = Counter()
    temporary_path = None
    try:
        for row in rows:
            if count >= 1_048_575:
                raise ValueError("Report exceeds the Excel worksheet row limit.")
            if len(row) != len(COLUMNS):
                raise ValueError("Unexpected number of source columns.")
            cells = []
            for name, value in zip(COLUMNS, row):
                if isinstance(value, str) and len(value) > 32767:
                    raise ValueError(
                        f"Row {count + 1}, {name}: text exceeds Excel's cell limit."
                    )
                # Force SQL strings to text, preserving zeros and formula-like text.
                cell = WriteOnlyCell(sheet, value=value)
                if isinstance(value, str):
                    cell.data_type = "s"
                    cell.number_format = "@"
                elif isinstance(value, int):
                    cell.number_format = "0"
                cells.append(cell)
            sheet.append(cells)
            count += 1
            decisions[row[3]] += 1
            if count % 10000 == 0:
                print(f"Prepared {count:,} rows...", flush=True)

        sheet.auto_filter.ref = f"A1:{get_column_letter(len(COLUMNS))}{count + 1}"
        # Write beside the final file; publish only after saving and checking it.
        with tempfile.NamedTemporaryFile(
            dir=output_dir, prefix=".v7_export_", suffix=".xlsx", delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
        workbook.save(temporary_path)
        with ZipFile(temporary_path) as archive:
            if archive.testzip() is not None:
                raise ValueError("Workbook ZIP integrity verification failed.")
        temporary_path.rename(destination)
    finally:
        if not sheet.closed:
            sheet.close()
        workbook.close()
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return destination, count, decisions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--trust-server-certificate", action="store_true",
        help="Skip certificate verification for this connection; retain encryption.",
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
    print("Reading saved v7 report. No database rows will be changed.", flush=True)
    with closing(pyodbc.connect(connection_string, timeout=15, autocommit=True)) as connection:
        connection.timeout = 600
        with closing(connection.cursor()) as cursor:
            cursor.execute(QUERY)
            headers = tuple(column[0] for column in cursor.description)
            if headers != COLUMNS:
                raise ValueError("The source report columns do not match the export definition.")
            destination, count, decisions = write_report(read_rows(cursor), args.output_dir)
    print(f"Exported rows: {count}", flush=True)
    for decision, number in sorted(decisions.items(), key=lambda item: str(item[0])):
        print(f"{decision}: {number}", flush=True)
    print(f"Excel file: {destination}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"EXPORT FAILED: {error}", file=sys.stderr, flush=True)
        sys.exit(1)
