from packages.code_intelligence.models import CodeSymbol
from packages.code_intelligence.repo_graph import build_repo_graph
from packages.repo_ingestion.models import RepoProfile


def test_build_repo_graph_creates_contains_defines_imports_and_depends_edges():
    profile = RepoProfile(
        repo_id="repo-1",
        name="demo",
        source_url="https://github.com/example/demo.git",
        local_path="/tmp/demo",
        commit_sha="abc123",
        dependency_files=["requirements.txt"],
        config_files=["pyproject.toml"],
    )
    symbols = [
        CodeSymbol(
            id="src/main.py:1:import:fastapi",
            name="fastapi",
            type="import",
            file_path="src/main.py",
            start_line=1,
            end_line=1,
            signature="from fastapi import FastAPI",
            language="Python",
        ),
        CodeSymbol(
            id="src/main.py:4:function:create_app",
            name="create_app",
            type="function",
            file_path="src/main.py",
            start_line=4,
            end_line=8,
            signature="def create_app():",
            language="Python",
        ),
    ]

    graph = build_repo_graph(
        repo_id="repo-1",
        profile=profile,
        file_paths=["requirements.txt", "pyproject.toml", "src/main.py"],
        symbols=symbols,
    )

    node_ids = {node.id for node in graph.nodes}
    edge_keys = {(edge.source, edge.type, edge.target) for edge in graph.edges}

    assert "repo:repo-1" in node_ids
    assert "dir:src" in node_ids
    assert "file:src/main.py" in node_ids
    assert "symbol:src/main.py:4:function:create_app" in node_ids
    assert ("repo:repo-1", "contains", "dir:src") in edge_keys
    assert ("dir:src", "contains", "file:src/main.py") in edge_keys
    assert ("file:src/main.py", "defines", "symbol:src/main.py:4:function:create_app") in edge_keys
    assert ("file:src/main.py", "imports", "dependency:import:fastapi") in edge_keys
    assert ("repo:repo-1", "depends_on", "dependency:requirements.txt") in edge_keys
