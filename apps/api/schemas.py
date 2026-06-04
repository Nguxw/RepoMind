from __future__ import annotations

from pydantic import BaseModel, Field

from packages.repo_ingestion.models import FileNode, RepoProfile


class ImportRepositoryRequest(BaseModel):
    url: str = Field(..., min_length=1, description="Public GitHub repository URL")


class ImportRepositoryResponse(BaseModel):
    repo_id: str
    repo_name: str
    local_path: str
    commit_sha: str
    languages: list[str]
    important_files: list[str]
    profile_url: str


class FileTreeResponse(BaseModel):
    repo_id: str
    tree: FileNode


class RepoProfileResponse(BaseModel):
    repo_id: str
    profile: RepoProfile
