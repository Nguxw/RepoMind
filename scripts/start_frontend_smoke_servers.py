from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps" / "web"
NODE = ROOT / ".conda" / "node.exe"
TMP_DIR = ROOT / "tmp"
PID_FILE = TMP_DIR / "frontend_smoke_servers.json"


def main() -> None:
    if not NODE.exists():
        raise SystemExit(f"Missing local node runtime: {NODE}")
    TMP_DIR.mkdir(exist_ok=True)
    _prepare_standalone_assets()

    env = os.environ.copy()
    env.update(
        {
            "REPOMIND_STORAGE": "file",
            "REPOMIND_QUEUE_MODE": "inline",
            "REPOMIND_VECTOR_STORE": "memory",
            "NEXT_PUBLIC_API_BASE_URL": "http://127.0.0.1:8000",
            "HOSTNAME": "127.0.0.1",
            "PORT": "3000",
        }
    )

    api_log = (TMP_DIR / "api_smoke_server.log").open("w", encoding="utf-8")
    web_log = (TMP_DIR / "web_smoke_server.log").open("w", encoding="utf-8")

    api = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "apps.api.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=ROOT,
        stdout=api_log,
        stderr=subprocess.STDOUT,
        env=env,
        creationflags=_creationflags(),
    )
    web = subprocess.Popen(
        [str(NODE), ".next/standalone/server.js"],
        cwd=WEB,
        stdout=web_log,
        stderr=subprocess.STDOUT,
        env=env,
        creationflags=_creationflags(),
    )

    PID_FILE.write_text(json.dumps({"api_pid": api.pid, "web_pid": web.pid}, indent=2), encoding="utf-8")
    _wait_for("http://127.0.0.1:8000/health")
    _wait_for("http://127.0.0.1:3000/repos/new")
    print({"api_pid": api.pid, "web_pid": web.pid, "pid_file": str(PID_FILE)})


def _wait_for(url: str, timeout_seconds: int = 60) -> str:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                return response.read().decode("utf-8", errors="ignore")
        except Exception as exc:
            last_error = exc
            time.sleep(1)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def _creationflags() -> int:
    if sys.platform.startswith("win"):
        return subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    return 0


def _prepare_standalone_assets() -> None:
    standalone = WEB / ".next" / "standalone"
    static_src = WEB / ".next" / "static"
    static_dst = standalone / ".next" / "static"
    public_src = WEB / "public"
    public_dst = standalone / "public"
    if static_src.exists():
        shutil.rmtree(static_dst, ignore_errors=True)
        shutil.copytree(static_src, static_dst)
    if public_src.exists():
        shutil.copytree(public_src, public_dst, dirs_exist_ok=True)


if __name__ == "__main__":
    main()
