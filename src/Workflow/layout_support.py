"""Local configuration and shared layout helpers. No database calls."""
import json
import os
from pathlib import Path
import re
import time
from uuid import uuid4

BACKEND = Path(__file__).resolve().parents[1]
SETTINGS = json.loads((BACKEND / "Config" / "settings.json").read_text(encoding="utf-8-sig"))
ROOT = Path(SETTINGS["shared_root"])
CONTROL = ROOT / "Control"
REPORTS = ROOT / "Reports"
CURRENT_CSV = CONTROL / "Data" / "SisterTwin_Vehicles_Raw.csv"
ID = re.compile(r"[0-9a-f]{32}\Z")


def atomic_json(path, data):
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        for attempt in range(8):
            try:
                os.replace(temporary, path)
                return
            except PermissionError:
                if attempt == 7:
                    raise
                time.sleep(min(0.05 * 2 ** attempt, 0.4))
    finally:
        temporary.unlink(missing_ok=True)


def read_json(path):
    with path.open("rb") as stream:
        data = stream.read(65537)
    if len(data) > 65536:
        raise ValueError("JSON file is too large.")
    return json.loads(data.decode("utf-8-sig"))
