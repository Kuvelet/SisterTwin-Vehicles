"""Fixed-workflow worker. Run on WORKERHOST while the operator is signed in."""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
from uuid import uuid4


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Workflow"))
from layout_support import ROOT, REPORTS, CONTROL, SETTINGS, read_json

RUNNER = Path(__file__).resolve().parents[1] / "Workflow" / "run_sistertwin_workflow.py"
REQUEST_ID = re.compile(r"[0-9a-f]{32}\Z")
POLL_SECONDS = 3
WORKER_COMPUTER = SETTINGS["worker_computer"]
PYTHON_EXECUTABLE = Path(SETTINGS["python_executable"])
PROGRESS_VIEWER = Path(__file__).with_name("show_progress.py")


def open_progress_window(request_id):
    # This is only a log viewer. Closing its window cannot cancel the workflow.
    try:
        if not PROGRESS_VIEWER.is_file():
            raise FileNotFoundError(PROGRESS_VIEWER)
        return subprocess.Popen(
            [str(PYTHON_EXECUTABLE), "-u", str(PROGRESS_VIEWER), "--request-id", request_id],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            env={**os.environ, "PYTHONUTF8": "1"},
        )
    except OSError:
        logging.exception("Cannot open progress window; report generation continues normally.")
        return None


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def atomic_json(path, content):
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8")
        for attempt in range(8):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == 7:
                    raise
                # Brief SMB/reader locks are retryable; persistent denial still fails.
                time.sleep(min(0.05 * (2 ** attempt), 0.4))
    finally:
        temporary.unlink(missing_ok=True)


def read_request(path):
    if not REQUEST_ID.fullmatch(path.parent.name) or path.name != "request.json" or path.is_symlink() or path.parent.is_symlink():
        raise ValueError("Invalid request filename.")
    with path.open("rb") as source:
        data = source.read(4097)
    if len(data) > 4096:
        raise ValueError("Request is too large.")
    request = json.loads(data.decode("utf-8-sig"))
    if not isinstance(request, dict):
        raise ValueError("Unexpected request fields.")
    fields = {"version", "request_id", "action", "requested_by"}
    if request.get("version") == 2:
        fields |= {"input_mode", "csv_sha256"}
    if set(request) != fields:
        raise ValueError("Unexpected request fields.")
    if type(request["version"]) is not int or request["version"] not in (1, 2):
        raise ValueError("Unsupported request version.")
    if request["version"] == 2:
        mode, checksum = request["input_mode"], request["csv_sha256"]
        if mode not in ("current", "upload"):
            raise ValueError("Invalid input mode.")
        if mode == "current" and checksum is not None:
            raise ValueError("Unexpected CSV checksum.")
        if mode == "upload" and (not isinstance(checksum, str) or not re.fullmatch(r"[0-9a-f]{64}", checksum)):
            raise ValueError("Invalid CSV checksum.")
    if request["request_id"] != path.parent.name or request["action"] != "generate_reports":
        raise ValueError("Unsupported request.")
    if not isinstance(request["requested_by"], str) or not 1 <= len(request["requested_by"]) <= 256:
        raise ValueError("Invalid requester label.")
    return request


@contextmanager
def single_worker():
    import msvcrt
    folder = Path(os.environ["LOCALAPPDATA"]) / "SisterTwinWorker"
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "worker.lock").open("a+b") as lock:
        if lock.seek(0, 2) == 0:
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise RuntimeError("Another worker is already running under this account.") from error
        try:
            yield
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def verify_completed(request_id, exit_code, reports=REPORTS, control=CONTROL):
    if exit_code != 0:
        raise RuntimeError(f"Workflow exited with code {exit_code}. Review its run log.")
    manifest = read_json(control / "Runs" / request_id / "status.json")
    if manifest.get("status") != "Finishing" or manifest.get("run_id") != request_id:
        raise RuntimeError("The workflow did not confirm completion for this request.")
    outputs = {}
    folder = Path(manifest.get("reports_folder", ""))
    if folder.parent.resolve() != reports.resolve() or not folder.name.endswith("_" + request_id):
        raise RuntimeError("Unexpected reports folder.")
    for name in ("validation_report", "gap_report"):
        path = Path(manifest.get(name, ""))
        if path.parent.resolve() != folder.resolve() or path.suffix.lower() != ".xlsx":
            raise RuntimeError("Unexpected report path in workflow result.")
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError("An expected workbook is missing or empty.")
        outputs[name] = str(path)
    outputs["reports_folder"] = str(folder)
    return outputs


class Worker:
    def __init__(self):
        self.active = None
        self.worker_id = uuid4().hex
        self.started = utc_now()
        for folder in ("Queue", "Runs", "Data"):
            (CONTROL / folder).mkdir(parents=True, exist_ok=True)

    def heartbeat(self, state="Online"):
        atomic_json(CONTROL / "worker.json", {
            "version": 3, "layout": "compact-v1", "worker_id": self.worker_id, "computer": socket.gethostname(),
            "process_id": os.getpid(),
            "account": os.environ.get("USERNAME", ""), "started_utc": self.started,
            "updated_utc": utc_now(), "state": state, "active_request": self.active,
        })

    def status(self, request_id, state, message, **extra):
        path = CONTROL / "Runs" / request_id / "status.json"
        existing = read_json(path) if path.exists() else {}
        atomic_json(path, {**existing,
            "request_id": request_id, "status": state, "message": message,
            "updated_utc": utc_now(), **extra,
        })

    def reconcile(self):
        # Never automatically replay a request interrupted by a crash or logoff.
        for claimed in (CONTROL / "Runs").iterdir():
            if not REQUEST_ID.fullmatch(claimed.name) or not claimed.is_dir() or claimed.is_symlink():
                continue
            saved_status = claimed / "status.json"
            if saved_status.exists():
                state = read_json(saved_status).get("status")
                if state in ("Completed", "Failed", "Interrupted"):
                    continue
            self.status(claimed.name, "Interrupted", "Worker restarted. A child workflow may still be active. Check processes and logs before retrying.")

    def run_request(self, claimed):
        request_id = claimed.name
        self.active = request_id
        started = utc_now()
        capture = claimed / "workflow.log"
        try:
            request = read_request(claimed / "request.json")
            # The label is display-only; it is not authentication or a command.
            self.status(request_id, "Processing", "Generating reports on WORKERHOST.",
                        started_utc=started, requested_by=request["requested_by"], log=str(capture))
            self.heartbeat()
            command = [str(PYTHON_EXECUTABLE), "-u", str(RUNNER), "--execute",
                       "--request-id", request_id]
            if SETTINGS["trust_server_certificate"]:
                command.append("--trust-server-certificate")
            if request.get("input_mode") == "upload":
                staged = claimed / "input.csv"
                if staged.is_symlink():
                    raise ValueError("Uploaded CSV must not be a symbolic link.")
            with capture.open("w", encoding="utf-8") as output:
                process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT,
                                           creationflags=subprocess.CREATE_NO_WINDOW,
                                           env={**os.environ, "PYTHONUTF8": "1"})
                viewer = open_progress_window(request_id) if SETTINGS["show_progress_window"] else None
                while process.poll() is None:
                    try:
                        self.heartbeat()
                    except OSError:
                        logging.exception("Heartbeat write failed; waiting for the active workflow, not starting another.")
                    time.sleep(POLL_SECONDS)
                if viewer is not None:
                    viewer.poll()
            outputs = verify_completed(request_id, process.returncode)
            self.status(request_id, "Completed", "Both reports are ready.",
                        started_utc=started, finished_utc=utc_now(), log=str(capture), **outputs)
            logging.info("Request completed: %s", request_id)
        except Exception as error:
            logging.exception("Request failed: %s", request_id)
            self.status(request_id, "Failed", str(error),
                        started_utc=started, finished_utc=utc_now(), log=str(capture))
        finally:
            self.active = None

    def serve(self):
        self.reconcile()
        if sys.stdout is not None:
            print("Worker ready on WORKERHOST. Leave this running. Press Ctrl+C only when idle.", flush=True)
        while True:
            try:
                stop = Path(os.environ["LOCALAPPDATA"]) / "SisterTwinWorker" / "stop-layout3"
                if stop.exists():
                    stop.unlink()
                    self.heartbeat("Offline")
                    return
                self.heartbeat()
                requests = sorted((CONTROL / "Queue").iterdir(), key=lambda path: path.stat().st_mtime)
                for pending in requests:
                    if not REQUEST_ID.fullmatch(pending.name) or not pending.is_dir() or pending.is_symlink():
                        continue
                    claimed = CONTROL / "Runs" / pending.name
                    if claimed.exists():
                        logging.error("Duplicate request ID in Queue; left untouched: %s", pending.name)
                        continue
                    # Rename is the claim; only claimed files are ever executed.
                    try:
                        pending.rename(claimed)
                    except FileNotFoundError:
                        continue
                    self.run_request(claimed)
                    break
            except KeyboardInterrupt:
                self.heartbeat("Offline")
                raise
            except Exception:
                logging.exception("Worker cycle failed; retrying in a few seconds.")
            time.sleep(POLL_SECONDS)


def main():
    local_logs = Path(os.environ.get("LOCALAPPDATA", ".")) / "SisterTwinWorker"
    local_logs.mkdir(parents=True, exist_ok=True)
    if "--stop" in sys.argv:
        (local_logs / "stop-layout3").touch()
        print("Stop requested. The new worker will exit after any current run finishes.")
        return 0
    # Rotating worker-only diagnostics; no duplicated per-run workflow output.
    from logging.handlers import RotatingFileHandler
    log_path = CONTROL / "Data" / "worker.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(handlers=[RotatingFileHandler(log_path, maxBytes=1000000, backupCount=2, encoding="utf-8")], level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    try:
        if socket.gethostname().upper() != WORKER_COMPUTER:
            raise RuntimeError("Start this worker on WORKERHOST, not on a coworker's computer.")
        if not RUNNER.is_file():
            raise FileNotFoundError(f"Workflow runner is unavailable: {RUNNER}")
        if not PYTHON_EXECUTABLE.is_file():
            raise FileNotFoundError(f"Python executable is unavailable: {PYTHON_EXECUTABLE}")
        with single_worker():
            (local_logs / "stop-layout3").unlink(missing_ok=True)
            Worker().serve()
    except KeyboardInterrupt:
        return 0
    except Exception as error:
        logging.exception("Worker stopped")
        if sys.stderr is not None:
            print(f"WORKER FAILED: {error}\nLog: {log_path}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
