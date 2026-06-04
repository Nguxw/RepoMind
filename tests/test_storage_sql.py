from pathlib import Path

from packages.code_intelligence import build_repo_graph, extract_symbols
from packages.repo_ingestion.detect import scan_repository
from packages.repo_ingestion.profile import build_repo_profile
from packages.storage.postgres import SqlRepositoryStore
from packages.storage.repositories import RepositoryRecord


def test_sql_repository_store_round_trips_record(tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "README.md").write_text("# Demo\n", encoding="utf-8")
    (repo_root / "main.py").write_text("def main():\n    return 'ok'\n", encoding="utf-8")
    scan = scan_repository(repo_root)
    profile = build_repo_profile("repo-sql", "https://github.com/example/demo.git", repo_root, scan, "abc123")
    symbols = extract_symbols(repo_root, scan.included_files)
    graph = build_repo_graph("repo-sql", profile, scan.included_files, symbols)
    record = RepositoryRecord(
        repo_id="repo-sql",
        source_url=profile.source_url,
        local_path=str(repo_root),
        profile=profile,
        file_tree=scan.file_tree,
        symbols=symbols,
        graph=graph,
    )
    store = SqlRepositoryStore(f"sqlite:///{tmp_path / 'repomind.db'}")

    store.save(record)
    loaded = store.get("repo-sql")

    assert loaded is not None
    assert loaded.profile.name == "demo"
    assert loaded.symbols
    assert loaded.graph is not None
    assert loaded.graph.edges
