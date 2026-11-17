"""Load actual workflow modules from an isolated temporary backend copy."""
import atexit
import json
from pathlib import Path
import shutil
import tempfile

_temp = tempfile.TemporaryDirectory(prefix="sistertwin-offline-tests-")
atexit.register(_temp.cleanup)
BACKEND = Path(_temp.name)
WORKFLOW = BACKEND / "Workflow"
shutil.copytree(Path(__file__).resolve().parents[1] / "src" / "Workflow", WORKFLOW,
                ignore=shutil.ignore_patterns("__pycache__"))
(BACKEND / "Config").mkdir()
(BACKEND / "Config" / "settings.json").write_text(json.dumps({
    "shared_root": str(BACKEND / "isolated-share"),
    "worker_computer": "OFFLINE-TEST-ONLY",
    "python_executable": "python",
    "trust_server_certificate": False,
    "show_progress_window": False,
}), encoding="utf8")
