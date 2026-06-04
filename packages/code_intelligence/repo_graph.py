from __future__ import annotations

from pathlib import Path

from packages.code_intelligence.models import CodeSymbol, GraphEdge, GraphNode, RepoGraph
from packages.repo_ingestion.manifests import is_config_file, is_dependency_file
from packages.repo_ingestion.models import RepoProfile


def build_repo_graph(repo_id: str, profile: RepoProfile, file_paths: list[str], symbols: list[CodeSymbol]) -> RepoGraph:
    builder = _RepoGraphBuilder(repo_id)
    repository_id = f"repo:{repo_id}"
    builder.add_node(GraphNode(id=repository_id, type="Repository", name=profile.name, metadata={"source_url": profile.source_url}))

    for file_path in sorted(file_paths):
        builder.add_file_path(repository_id, file_path)

    for dependency_file in profile.dependency_files:
        dependency_id = f"dependency:{dependency_file}"
        builder.add_node(GraphNode(id=dependency_id, type="Dependency", name=Path(dependency_file).name, file_path=dependency_file))
        builder.add_edge(GraphEdge(source=repository_id, target=dependency_id, type="depends_on", metadata={"file_path": dependency_file}))

    for config_file in profile.config_files:
        config_id = f"config:{config_file}"
        builder.add_node(GraphNode(id=config_id, type="Config", name=Path(config_file).name, file_path=config_file))
        builder.add_edge(GraphEdge(source=repository_id, target=config_id, type="contains", metadata={"file_path": config_file}))

    for symbol in symbols:
        builder.add_symbol(symbol)

    return RepoGraph(repo_id=repo_id, nodes=list(builder.nodes.values()), edges=list(builder.edges.values()))


class _RepoGraphBuilder:
    def __init__(self, repo_id: str) -> None:
        self.repo_id = repo_id
        self.nodes: dict[str, GraphNode] = {}
        self.edges: dict[str, GraphEdge] = {}

    def add_node(self, node: GraphNode) -> None:
        self.nodes.setdefault(node.id, node)

    def add_edge(self, edge: GraphEdge) -> None:
        key = f"{edge.source}->{edge.type}->{edge.target}"
        self.edges.setdefault(key, edge)

    def add_file_path(self, repository_id: str, file_path: str) -> None:
        parts = Path(file_path).parts
        parent_id = repository_id
        accumulated: list[str] = []
        for part in parts[:-1]:
            accumulated.append(part)
            directory_path = "/".join(accumulated)
            directory_id = f"dir:{directory_path}"
            self.add_node(GraphNode(id=directory_id, type="Directory", name=part, file_path=directory_path))
            self.add_edge(GraphEdge(source=parent_id, target=directory_id, type="contains"))
            parent_id = directory_id

        node_type = "Config" if is_config_file(file_path) else "Dependency" if is_dependency_file(file_path) else "File"
        file_id = f"file:{file_path}"
        self.add_node(GraphNode(id=file_id, type=node_type, name=Path(file_path).name, file_path=file_path))
        self.add_edge(GraphEdge(source=parent_id, target=file_id, type="contains"))

    def add_symbol(self, symbol: CodeSymbol) -> None:
        if symbol.type == "import":
            dependency_id = f"dependency:import:{symbol.name}"
            self.add_node(GraphNode(id=dependency_id, type="Dependency", name=symbol.name, metadata={"source": "import"}))
            self.add_edge(
                GraphEdge(
                    source=f"file:{symbol.file_path}",
                    target=dependency_id,
                    type="imports",
                    metadata={"line": symbol.start_line, "signature": symbol.signature},
                )
            )
            return

        node_type = {
            "class": "Class",
            "function": "Function",
            "method": "Method",
            "export": "Dependency",
        }.get(symbol.type, "Function")
        symbol_id = f"symbol:{symbol.id}"
        self.add_node(
            GraphNode(
                id=symbol_id,
                type=node_type,
                name=symbol.name,
                file_path=symbol.file_path,
                start_line=symbol.start_line,
                end_line=symbol.end_line,
                metadata={"signature": symbol.signature, "language": symbol.language},
            )
        )
        self.add_edge(GraphEdge(source=f"file:{symbol.file_path}", target=symbol_id, type="defines"))
