from __future__ import annotations

import base64
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

import websocket
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps" / "web"
NODE = ROOT / ".conda" / "node.exe"
TMP_DIR = ROOT / "tmp"
EDGE_BINARY = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
CHROME_BINARY = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")


def main() -> None:
    TMP_DIR.mkdir(exist_ok=True)
    server_processes = _ensure_servers()
    try:
        try:
            driver = _create_driver()
        except Exception as exc:
            _run_cdp_smoke(str(exc))
            return

        try:
            wait = WebDriverWait(driver, 20)

            driver.get("http://127.0.0.1:3000/repos/new")
            wait.until(EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "Repository evidence workbench"))
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder*='github.com']")))
            driver.save_screenshot(str(TMP_DIR / "browser_repos_new.png"))

            logs = _browser_errors(driver)
            print(
                json.dumps(
                    {
                        "repos_new": True,
                        "trace_http": _url_contains("http://127.0.0.1:3000/repos/example/trace/example-run", "Agent Trace"),
                        "console_errors": logs,
                        "screenshots": [
                            str(TMP_DIR / "browser_repos_new.png"),
                        ],
                    },
                    ensure_ascii=False,
                )
            )
        finally:
            driver.quit()
    finally:
        _stop_processes(server_processes)


def _create_driver():
    attempts = []
    if EDGE_BINARY.exists():
        options = webdriver.EdgeOptions()
        options.binary_location = str(EDGE_BINARY)
        _add_common_options(options)
        attempts.append(lambda: webdriver.Edge(options=options))
    if CHROME_BINARY.exists():
        options = webdriver.ChromeOptions()
        options.binary_location = str(CHROME_BINARY)
        _add_common_options(options)
        attempts.append(lambda: webdriver.Chrome(options=options))

    last_error: Exception | None = None
    for attempt in attempts:
        try:
            return attempt()
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Could not start a Selenium browser: {last_error}")


def _add_common_options(options) -> None:
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1440,1000")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.set_capability("goog:loggingPrefs", {"browser": "ALL"})


def _browser_errors(driver) -> list[str]:
    try:
        logs = driver.get_log("browser")
    except WebDriverException:
        return []
    return [item.get("message", "") for item in logs if item.get("level") == "SEVERE"]


def _ensure_servers() -> list[subprocess.Popen]:
    if _url_contains("http://127.0.0.1:8000/health", "repomind-api") and _url_contains(
        "http://127.0.0.1:3000/repos/new",
        "Repository evidence workbench",
    ):
        return []

    if not NODE.exists():
        raise RuntimeError(f"Missing local node runtime: {NODE}")

    _prepare_standalone_assets()
    env = _smoke_env()
    api_log = (TMP_DIR / "browser_api_server.log").open("w", encoding="utf-8")
    web_log = (TMP_DIR / "browser_web_server.log").open("w", encoding="utf-8")
    processes = [
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "apps.api.main:app", "--host", "127.0.0.1", "--port", "8000"],
            cwd=ROOT,
            stdout=api_log,
            stderr=subprocess.STDOUT,
            env=env,
            creationflags=_creationflags(),
        ),
        subprocess.Popen(
            [str(NODE), ".next/standalone/server.js"],
            cwd=WEB,
            stdout=web_log,
            stderr=subprocess.STDOUT,
            env=env,
            creationflags=_creationflags(),
        ),
    ]
    _wait_for_url("http://127.0.0.1:8000/health", "repomind-api")
    _wait_for_url("http://127.0.0.1:3000/repos/new", "Repository evidence workbench")
    return processes


def _smoke_env() -> dict[str, str]:
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
    return env


def _wait_for_url(url: str, expected: str, timeout_seconds: int = 60) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if _url_contains(url, expected):
            return
        time.sleep(1)
    raise RuntimeError(f"Timed out waiting for {url}")


def _url_contains(url: str, expected: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return expected in response.read().decode("utf-8", errors="ignore")
    except Exception:
        return False


def _stop_processes(processes: list[subprocess.Popen]) -> None:
    for process in processes:
        if process.poll() is not None:
            continue
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


def _creationflags() -> int:
    if sys.platform.startswith("win"):
        return subprocess.CREATE_NEW_PROCESS_GROUP
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


def _run_cdp_smoke(fallback_reason: str) -> None:
    binary = EDGE_BINARY if EDGE_BINARY.exists() else CHROME_BINARY
    if not binary.exists():
        raise RuntimeError(f"Could not start a Selenium browser: {fallback_reason}")

    port = _free_port()
    profile_dir = TMP_DIR / "cdp-browser-profile"
    shutil.rmtree(profile_dir, ignore_errors=True)
    profile_dir.mkdir(exist_ok=True)
    log_file = (TMP_DIR / "browser_cdp.log").open("w", encoding="utf-8")
    process = subprocess.Popen(
        [
            str(binary),
            "--headless=new",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile_dir}",
            "--remote-allow-origins=*",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "about:blank",
        ],
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    try:
        target = _wait_for_page_target(port)
        client = _CDPClient(target["webSocketDebuggerUrl"])
        try:
            client.call("Page.enable")
            client.call("Runtime.enable")
            client.call("Log.enable")
            _cdp_check_page(
                client,
                "http://127.0.0.1:3000/repos/new",
                "Repository evidence workbench",
                'document.querySelector(\'input[placeholder*="github.com"]\') !== null',
                TMP_DIR / "browser_repos_new.png",
            )
            print(
                json.dumps(
                    {
                        "repos_new": True,
                        "trace_http": _url_contains("http://127.0.0.1:3000/repos/example/trace/example-run", "Agent Trace"),
                        "console_errors": client.errors,
                        "screenshots": [
                            str(TMP_DIR / "browser_repos_new.png"),
                        ],
                        "fallback": "cdp",
                        "selenium_fallback_reason": fallback_reason,
                    },
                    ensure_ascii=False,
                )
            )
        finally:
            client.close()
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


def _cdp_check_page(client: "_CDPClient", url: str, required_text: str, required_expression: str, screenshot_path: Path) -> None:
    client.call("Page.navigate", {"url": url})
    deadline = time.time() + 30
    while time.time() < deadline:
        ready = client.evaluate("document.readyState === 'complete' || document.readyState === 'interactive'")
        has_text = client.evaluate(f"document.body && document.body.innerText.includes({json.dumps(required_text)})")
        has_required = client.evaluate(required_expression)
        if ready and has_text and has_required:
            data = client.call("Page.captureScreenshot", {"format": "png", "fromSurface": True})["data"]
            screenshot_path.write_bytes(base64.b64decode(data))
            return
        time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for rendered page: {url}")


def _wait_for_page_target(port: int, timeout_seconds: int = 20) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=2) as response:
                targets = json.loads(response.read().decode("utf-8"))
            for target in targets:
                if target.get("type") == "page" and target.get("webSocketDebuggerUrl"):
                    return target
        except Exception as exc:
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for browser CDP target: {last_error}")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class _CDPClient:
    def __init__(self, websocket_url: str) -> None:
        self.ws = websocket.create_connection(websocket_url, timeout=10)
        self.next_id = 1
        self.errors: list[str] = []

    def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        message_id = self.next_id
        self.next_id += 1
        self.ws.send(json.dumps({"id": message_id, "method": method, "params": params or {}}))
        while True:
            message = json.loads(self.ws.recv())
            self._record_event(message)
            if message.get("id") == message_id:
                if "error" in message:
                    raise RuntimeError(f"CDP call failed for {method}: {message['error']}")
                return message.get("result", {})

    def evaluate(self, expression: str) -> Any:
        result = self.call("Runtime.evaluate", {"expression": expression, "returnByValue": True})
        return (result.get("result") or {}).get("value")

    def close(self) -> None:
        self.ws.close()

    def _record_event(self, message: dict[str, Any]) -> None:
        method = message.get("method")
        params = message.get("params") or {}
        if method == "Log.entryAdded":
            entry = params.get("entry") or {}
            if entry.get("level") == "error":
                self.errors.append(str(entry.get("text", "")))
        if method == "Runtime.exceptionThrown":
            details = params.get("exceptionDetails") or {}
            self.errors.append(str(details.get("text", "Runtime exception")))


if __name__ == "__main__":
    main()
