"""Read-only database/CSV preflight. Never executes stored procedures or changes SQL data."""
import sys
from layout_support import CONTROL, CURRENT_CSV, REPORTS, SETTINGS
from run_sistertwin_workflow import preflight


def main():
    try:
        for directory in (CONTROL / "Data", CONTROL / "Queue", CONTROL / "Runs", REPORTS):
            if not directory.is_dir():
                raise FileNotFoundError(f"Missing folder: {directory}. Run migration preparation first.")
        preflight(CURRENT_CSV, REPORTS, SETTINGS["trust_server_certificate"])
        print("CHECK PASSED. No SQL tables or data changed. No workflow was started.")
        return 0
    except Exception as error:
        print(f"CHECK FAILED: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
