from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps" / "web"
TMP_DIR = ROOT / "tmp"
PID_FILE = TMP_DIR / "repomind_servers.json"


def main() -> None:
    args = _parse_args()
    TMP_DIR.mkdir(exist_ok=True)
    env = _runtime_env(args)
    node = _find_node()
    _validate_runtime(node, args.mode, env)

    api_url = f"http://{args.host}:{args.api_port}"
    web_url = f"http://{args.host}:{args.web_port}"
    api_log = (TMP_DIR / "repomind_api.log").open("w", encoding="utf-8")
    web_log = (TMP_DIR / "repomind_web.log").open("w", encoding="utf-8")

    processes: list[subprocess.Popen] = []
    try:
        api = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "apps.api.main:app",
                "--host",
                args.host,
                "--port",
                str(args.api_port),
            ],
            cwd=ROOT,
            stdout=api_log,
            stderr=subprocess.STDOUT,
            env=env,
            creationflags=_creationflags(),
        )
        web = subprocess.Popen(
            _web_command(node, args),
            cwd=WEB,
            stdout=web_log,
            stderr=subprocess.STDOUT,
            env=env,
            creationflags=_creationflags(),
        )
        processes.extend([api, web])
        _write_pid_file(processes, args)

        _wait_for(f"{api_url}/health", "repomind-api", "API", TMP_DIR / "repomind_api.log")
        _wait_for(f"{web_url}/repos/new", "Repository evidence workbench", "Web", TMP_DIR / "repomind_web.log")

        print("")
        print("RepoMind is running.")
        print(f"  API: {api_url}")
        print(f"  Web: {web_url}/repos/new")
        print(f"  API log: {TMP_DIR / 'repomind_api.log'}")
        print(f"  Web log: {TMP_DIR / 'repomind_web.log'}")
        print("")

        if not args.no_browser:
            webbrowser.open(f"{web_url}/repos/new")

        if args.smoke:
            return

        print("Press Ctrl+C in this window to stop RepoMind.")
        while all(process.poll() is None for process in processes):
            time.sleep(1)
        _print_failed_processes(processes)
    except KeyboardInterrupt:
        print("\nStopping RepoMind...")
    finally:
        _stop_processes(processes)
        PID_FILE.unlink(missing_ok=True)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start RepoMind API and web workbench with one command.")
    parser.add_argument("--host", default="127.0.0.1", help="Host for local API and web servers.")
    parser.add_argument("--api-port", default=8000, type=int, help="FastAPI port.")
    parser.add_argument("--web-port", default=3000, type=int, help="Next.js port.")
    parser.add_argument("--mode", choices=["prod", "dev"], default="prod", help="Start standalone production server or Next.js dev server.")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the browser automatically.")
    parser.add_argument("--smoke", action="store_true", help="Start, verify both servers, then stop and exit.")
    return parser.parse_args()


def _runtime_env(args: argparse.Namespace) -> dict[str, str]:
    env = os.environ.copy()
    _load_dotenv(env)
    api_base = f"http://{args.host}:{args.api_port}"
    env["NEXT_PUBLIC_API_BASE_URL"] = env.get("NEXT_PUBLIC_API_BASE_URL") or api_base
    env["HOSTNAME"] = args.host
    env["PORT"] = str(args.web_port)
    env.setdefault("REPOMIND_STORAGE", "file")
    env.setdefault("REPOMIND_QUEUE_MODE", "inline")
    env.setdefault("REPOMIND_VECTOR_STORE", "memory")
    return env


def _load_dotenv(env: dict[str, str]) -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = _strip_env_value(value.strip())
        if key and key not in env:
            env[key] = value


def _strip_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _find_node() -> str:
    local_node = ROOT / ".conda" / "node.exe"
    if local_node.exists():
        return str(local_node)
    node = shutil.which("node") or shutil.which("node.exe")
    if node:
        return node
    raise RuntimeError("Node.js was not found. Install Node.js or create the local .conda environment first.")


def _validate_runtime(node: str, mode: str, env: dict[str, str]) -> None:
    try:
        import uvicorn  # noqa: F401
    except ImportError as exc:
        raise RuntimeError('Python dependency "uvicorn" is missing. Run: python -m pip install -e ".[dev,parser]"') from exc

    next_bin = WEB / "node_modules" / "next" / "dist" / "bin" / "next"
    if mode == "dev" and not next_bin.exists():
        raise RuntimeError("Frontend dependencies are missing. Run: cd apps/web && npm install")
    if mode == "prod":
        standalone = WEB / ".next" / "standalone" / "server.js"
        if not standalone.exists():
            _build_frontend(node, env)
        if not standalone.exists():
            raise RuntimeError("Production build did not create apps/web/.next/standalone/server.js")
        _prepare_standalone_assets()
    if not Path(node).exists() and not shutil.which(node):
        raise RuntimeError(f"Node runtime does not exist: {node}")


def _web_command(node: str, args: argparse.Namespace) -> list[str]:
    if args.mode == "prod":
        return [node, ".next/standalone/server.js"]
    next_bin = WEB / "node_modules" / "next" / "dist" / "bin" / "next"
    return [node, str(next_bin), "dev", "--hostname", args.host, "--port", str(args.web_port)]


def _build_frontend(node: str, env: dict[str, str]) -> None:
    next_bin = WEB / "node_modules" / "next" / "dist" / "bin" / "next"
    if not next_bin.exists():
        raise RuntimeError("Frontend dependencies are missing. Run: cd apps/web && npm install")
    build_log_path = TMP_DIR / "repomind_web_build.log"
    print("Frontend production build is missing. Building it now...")
    with build_log_path.open("w", encoding="utf-8") as build_log:
        process = subprocess.run(
            [node, str(next_bin), "build"],
            cwd=WEB,
            stdout=build_log,
            stderr=subprocess.STDOUT,
            env=env,
            check=False,
        )
    if process.returncode != 0:
        raise RuntimeError(f"Frontend build failed. Log: {build_log_path}\n\nLast log lines:\n{_tail(build_log_path)}")


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


def _wait_for(url: str, expected: str, name: str, log_path: Path, timeout_seconds: int = 90) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                body = response.read().decode("utf-8", errors="ignore")
            if expected in body:
                return
        except Exception as exc:
            last_error = exc
        time.sleep(1)
    tail = _tail(log_path)
    raise RuntimeError(f"{name} did not become ready at {url}. Last error: {last_error}\n\nLast log lines:\n{tail}")


def _tail(path: Path, lines: int = 40) -> str:
    if not path.exists():
        return ""
    return "\n".join(path.read_text(encoding="utf-8", errors="ignore").splitlines()[-lines:])


def _write_pid_file(processes: list[subprocess.Popen], args: argparse.Namespace) -> None:
    payload = {
        "api_pid": processes[0].pid,
        "web_pid": processes[1].pid,
        "host": args.host,
        "api_port": args.api_port,
        "web_port": args.web_port,
        "mode": args.mode,
    }
    PID_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _print_failed_processes(processes: list[subprocess.Popen]) -> None:
    for name, process, log_name in [
        ("API", processes[0], "repomind_api.log"),
        ("Web", processes[1], "repomind_web.log"),
    ]:
        if process.poll() is not None:
            print(f"{name} exited with code {process.returncode}. Log: {TMP_DIR / log_name}")


def _stop_processes(processes: list[subprocess.Popen]) -> None:
    for process in reversed(processes):
        if process.poll() is not None:
            continue
        _terminate_process_tree(process.pid)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


def _terminate_process_tree(pid: int) -> None:
    if sys.platform.startswith("win"):
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        return
    try:
        os.kill(pid, 15)
    except ProcessLookupError:
        return


def _creationflags() -> int:
    if sys.platform.startswith("win"):
        return subprocess.CREATE_NEW_PROCESS_GROUP
    return 0


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"RepoMind startup failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
