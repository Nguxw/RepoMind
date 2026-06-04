from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PID_FILE = ROOT / "tmp" / "repomind_servers.json"


def main() -> None:
    if not PID_FILE.exists():
        print("RepoMind is not running, or no pid file was found.")
        return
    payload = json.loads(PID_FILE.read_text(encoding="utf-8"))
    stopped: list[int] = []
    for key in ("web_pid", "api_pid"):
        pid = payload.get(key)
        if not isinstance(pid, int):
            continue
        _terminate_process_tree(pid)
        stopped.append(pid)
    PID_FILE.unlink(missing_ok=True)
    print(f"Stopped RepoMind processes: {stopped}")


def _terminate_process_tree(pid: int) -> None:
    if sys.platform.startswith("win"):
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return


if __name__ == "__main__":
    main()
