from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import create_app
from packages.repo_ingestion.clone import CloneResult
from packages.storage import FileRepositoryStore


def test_import_profile_and_files_endpoints(tmp_path: Path):
    repo_root = tmp_path / "fixture_repo"
    repo_root.mkdir()
    (repo_root / "README.md").write_text("# Fixture\n", encoding="utf-8")
    (repo_root / "main.py").write_text("import os\n\nclass App:\n    def run(self):\n        return os.getcwd()\n", encoding="utf-8")

    def fake_clone(url: str, destination_root: str, timeout_seconds: int) -> CloneResult:
        return CloneResult(
            repo_id="repo123",
            local_path=str(repo_root),
            commit_sha="abc123",
            normalized_url="https://github.com/example/fixture.git",
        )

    app = create_app(store=FileRepositoryStore(tmp_path / "data"), clone_func=fake_clone)
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    imported = client.post("/api/repos/import", json={"url": "https://github.com/example/fixture"})
    assert imported.status_code == 200
    assert imported.json()["repo_id"] == "repo123"
    assert imported.json()["repo_name"] == "fixture"

    profile = client.get("/api/repos/repo123/profile")
    assert profile.status_code == 200
    assert profile.json()["profile"]["readme_files"] == ["README.md"]

    files = client.get("/api/repos/repo123/files")
    assert files.status_code == 200
    assert files.json()["tree"]["type"] == "directory"

    symbols = client.get("/api/repos/repo123/symbols")
    assert symbols.status_code == 200
    symbol_names = {symbol["name"] for symbol in symbols.json()["symbols"]}
    assert {"os", "App", "run"} <= symbol_names

    graph = client.get("/api/repos/repo123/graph")
    assert graph.status_code == 200
    graph_payload = graph.json()["graph"]
    assert any(node["type"] == "Repository" for node in graph_payload["nodes"])
    assert any(edge["type"] == "defines" for edge in graph_payload["edges"])

    source = client.get("/api/repos/repo123/source", params={"path": "main.py"})
    assert source.status_code == 200
    assert "class App" in source.json()["content"]

    wiki = client.post("/api/repos/repo123/wiki/generate")
    assert wiki.status_code == 200
    assert wiki.json()["run_id"]
    assert len(wiki.json()["pages"]) >= 6

    wiki_list = client.get("/api/repos/repo123/wiki")
    assert wiki_list.status_code == 200
    assert any(page["slug"] == "overview" for page in wiki_list.json()["pages"])

    wiki_page = client.get("/api/repos/repo123/wiki/overview")
    assert wiki_page.status_code == 200
    assert wiki_page.json()["page"]["title"] == "Overview"

    escaped_source = client.get("/api/repos/repo123/source", params={"path": "../outside.py"})
    assert escaped_source.status_code == 400

    ask = client.post("/api/repos/repo123/ask", json={"question": "Where is the app class?"})
    assert ask.status_code == 200
    assert ask.json()["citations"]

    trace = client.get(f"/api/runs/{ask.json()['run_id']}/trace")
    assert trace.status_code == 200
    assert trace.json()["run"]["steps"]
