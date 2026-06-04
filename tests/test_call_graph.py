from pathlib import Path

from packages.code_intelligence.call_graph import extract_calls
from packages.code_intelligence.repo_graph import build_repo_graph
from packages.code_intelligence.symbol_extractor import extract_symbols
from packages.repo_ingestion.detect import scan_repository
from packages.repo_ingestion.profile import build_repo_profile


def test_python_call_graph_extracts_local_calls(tmp_path: Path):
    (tmp_path / "main.py").write_text(
        "def helper():\n"
        "    return 'ok'\n\n"
        "def main():\n"
        "    return helper()\n",
        encoding="utf-8",
    )
    scan = scan_repository(tmp_path)
    profile = build_repo_profile("repo-1", "https://github.com/example/demo.git", tmp_path, scan, "abc123")
    symbols = extract_symbols(tmp_path, scan.included_files)

    calls = extract_calls(tmp_path, scan.included_files, symbols)
    graph = build_repo_graph("repo-1", profile, scan.included_files, symbols)

    assert any(call.caller_name == "main" and call.callee_name == "helper" for call in calls)
    assert any(edge.type == "calls" and "helper" in edge.target for edge in graph.edges)
