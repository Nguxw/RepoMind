from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

SymbolType = Literal["class", "function", "method", "import", "export"]
GraphNodeType = Literal["Repository", "Directory", "File", "Class", "Function", "Method", "Config", "Dependency", "WikiPage"]
GraphEdgeType = Literal["contains", "defines", "imports", "depends_on", "documents", "related_to"]


class CodeSymbol(BaseModel):
    id: str
    name: str
    type: SymbolType
    file_path: str
    start_line: int
    end_line: int
    signature: str
    language: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphNode(BaseModel):
    id: str
    type: GraphNodeType
    name: str
    file_path: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str
    target: str
    type: GraphEdgeType
    metadata: dict[str, Any] = Field(default_factory=dict)


class RepoGraph(BaseModel):
    repo_id: str
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
