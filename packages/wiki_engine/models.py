from __future__ import annotations

from pydantic import BaseModel, Field


class Citation(BaseModel):
    file_path: str
    start_line: int
    end_line: int
    status: str = "valid"
    message: str | None = None


class WikiSection(BaseModel):
    heading: str
    content: str
    citations: list[Citation] = Field(default_factory=list)


class MermaidDiagram(BaseModel):
    type: str = "mermaid"
    title: str
    content: str


class WikiPage(BaseModel):
    slug: str
    title: str
    summary: str
    sections: list[WikiSection] = Field(default_factory=list)
    diagrams: list[MermaidDiagram] = Field(default_factory=list)
    related_pages: list[str] = Field(default_factory=list)
    invalid_citation_warnings: list[str] = Field(default_factory=list)
