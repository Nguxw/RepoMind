from __future__ import annotations

from collections import Counter
from pathlib import Path

from packages.code_intelligence.models import RepoGraph
from packages.repo_ingestion.models import RepoProfile
from packages.wiki_engine.models import MermaidDiagram


class DiagramGenerator:
    def architecture_diagram(self, profile: RepoProfile) -> MermaidDiagram:
        lines = ["flowchart TD", f"    Repo[\"{profile.name}\"]"]
        for directory in profile.important_directories[:8]:
            lines.append(f"    Repo --> {safe_id(directory)}[\"{directory}/\"]")
        if profile.frameworks:
            lines.append("    Repo --> Frameworks[\"Frameworks\"]")
            for framework in profile.frameworks[:6]:
                lines.append(f"    Frameworks --> {safe_id(framework)}[\"{framework}\"]")
        if len(lines) == 2:
            for file_path in profile.important_files[:6]:
                lines.append(f"    Repo --> {safe_id(file_path)}[\"{Path(file_path).name}\"]")
        return MermaidDiagram(title="Architecture Diagram", content="\n".join(lines))

    def dependency_diagram(self, graph: RepoGraph) -> MermaidDiagram:
        imports = [edge for edge in graph.edges if edge.type == "imports"]
        counter = Counter(edge.target.removeprefix("dependency:import:") for edge in imports)
        lines = ["flowchart LR", "    Source[\"Source Files\"]"]
        for name, _count in counter.most_common(10):
            lines.append(f"    Source --> {safe_id(name)}[\"{name}\"]")
        if len(lines) == 2:
            lines.append("    Source --> Files[\"Repository files\"]")
        return MermaidDiagram(title="Module Dependency Diagram", content="\n".join(lines))


def safe_id(value: str) -> str:
    cleaned = "".join(char if char.isalnum() else "_" for char in value)
    return "N_" + cleaned.strip("_")[:48]
