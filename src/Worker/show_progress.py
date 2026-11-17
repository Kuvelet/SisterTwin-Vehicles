"""Display one request's live log; never starts or stops the workflow itself."""

import argparse
import codecs
import ctypes
import json
import os
from pathlib import Path
import re
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Workflow"))
from layout_support import CONTROL
TERMINAL = {"Completed", "Failed", "Interrupted"}


def follow(request_id, control=CONTROL, interval=0.5, linger=8):
    log_path = control / "Runs" / request_id / "workflow.log"
    status_path = control / "Runs" / request_id / "status.json"
    offset = 0
    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    waiting = False

    def tail():
        nonlocal offset
        if not log_path.exists():
            return
        with log_path.open("rb") as stream:
            stream.seek(offset)
            while chunk := stream.read(65536):
                offset += len(chunk)
                print(decoder.decode(chunk), end="", flush=True)

    print("Sister/Twin report generation on WORKERHOST", flush=True)
    print(f"Request: {request_id}", flush=True)
    print("Live output only. Closing this window does not cancel the report.\n", flush=True)
    while True:
        try:
            tail()
            with status_path.open("rb") as stream:
                data = stream.read(65537)
            if len(data) > 65536:
                raise ValueError("Status file is unexpectedly large.")
            status = json.loads(data.decode("utf-8"))
            if status.get("request_id") != request_id:
                raise ValueError("Status does not match this request.")
            if waiting:
                print("\nConnection restored.\n", flush=True)
                waiting = False
            if status.get("status") in TERMINAL:
                tail()
                print(decoder.decode(b"", final=True), end="", flush=True)
                print(f"\n{status['status']}: {status.get('message', '')}", flush=True)
                print(f"Log: {log_path}", flush=True)
                print(f"This window closes in {linger} seconds. The worker stays in the background.", flush=True)
                time.sleep(linger)
                return 0
        except (OSError, ValueError) as error:
            if not waiting:
                print(f"\nWaiting for shared-folder status: {error}\nThe report may still be running.\n", flush=True)
                waiting = True
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request-id", required=True)
    args = parser.parse_args()
    if re.fullmatch(r"[0-9a-f]{32}", args.request_id) is None:
        parser.error("Invalid request identifier.")
    if sys.stdout is not None:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if os.name == "nt":
        ctypes.windll.kernel32.SetConsoleTitleW("Sister/Twin Reports - Live Progress")
    try:
        return follow(args.request_id)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
