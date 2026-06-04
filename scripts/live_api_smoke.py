from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from apps.api.main import create_app
from packages.repo_ingestion.clone import CloneResult
from packages.storage import FileRepositoryStore


def main() -> None:
    with tempfile.TemporaryDirectory() as workspace:
        workspace_path = Path(workspace)
        repo_root = workspace_path / "fixture_repo"
        repo_root.mkdir()
        (repo_root / "README.md").write_text("# Live API Demo\n\nFastAPI application demo.\n", encoding="utf-8")
        (repo_root / "requirements.txt").write_text("fastapi\nuvicorn\n", encoding="utf-8")
        (repo_root / "main.py").write_text(
            "from fastapi import FastAPI\n\n"
            "class AppFactory:\n"
            "    def create(self):\n"
            "        return FastAPI()\n\n"
            "def create_app():\n"
            "    return AppFactory().create()\n",
            encoding="utf-8",
        )

        def fake_clone(url: str, destination_root: str, timeout_seconds: int) -> CloneResult:
            return CloneResult(
                repo_id="live-api-repo",
                local_path=str(repo_root),
                commit_sha="liveapi123",
                normalized_url="https://github.com/example/live-api-demo.git",
            )

        app = create_app(store=FileRepositoryStore(workspace_path / "data"), clone_func=fake_clone)
        client = TestClient(app)

        imported = client.post("/api/repos/import", json={"url": "https://github.com/example/live-api-demo"})
        imported.raise_for_status()
        repo_id = imported.json()["repo_id"]

        wiki = client.post(f"/api/repos/{repo_id}/wiki/generate")
        wiki.raise_for_status()
        wiki_trace = client.get(f"/api/runs/{wiki.json()['run_id']}/trace")
        wiki_trace.raise_for_status()

        ask = client.post(f"/api/repos/{repo_id}/ask", json={"question": "Where is the FastAPI app created?"})
        ask.raise_for_status()
        ask_trace = client.get(f"/api/runs/{ask.json()['run_id']}/trace")
        ask_trace.raise_for_status()

        print(
            {
                "repo_id": repo_id,
                "wiki_pages": len(wiki.json()["pages"]),
                "ask_has_citations": bool(ask.json()["citations"]),
                "wiki_trace_steps": len(wiki_trace.json()["run"]["steps"]),
                "ask_trace_steps": len(ask_trace.json()["run"]["steps"]),
                "wiki_token_usage": wiki_trace.json()["run"]["token_usage"],
                "ask_token_usage": ask_trace.json()["run"]["token_usage"],
                "answer_preview": ask.json()["answer"][:120],
            }
        )


if __name__ == "__main__":
    main()
