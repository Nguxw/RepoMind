from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class FileNode(BaseModel):
    name: str
    path: str
    type: Literal["directory", "file"]
    size: int = 0
    children: list["FileNode"] = Field(default_factory=list)


class RepositoryScan(BaseModel):
    root_path: str
    included_files: list[str]
    file_tree: FileNode
    total_included_bytes: int


class RepoProfile(BaseModel):
    repo_id: str
    name: str
    source_url: str
    local_path: str
    commit_sha: str
    description: str | None = None
    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    package_managers: list[str] = Field(default_factory=list)
    readme_files: list[str] = Field(default_factory=list)
    dependency_files: list[str] = Field(default_factory=list)
    config_files: list[str] = Field(default_factory=list)
    entrypoints: list[str] = Field(default_factory=list)
    test_files: list[str] = Field(default_factory=list)
    important_files: list[str] = Field(default_factory=list)
    important_directories: list[str] = Field(default_factory=list)
    file_count: int = 0
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
