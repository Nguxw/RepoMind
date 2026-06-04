from __future__ import annotations

from pydantic import BaseModel, Field

from packages.code_intelligence.models import CodeSymbol, RepoGraph
from packages.harness.state import AgentRun, AskAnswer
from packages.repo_ingestion.models import FileNode, RepoProfile
from packages.wiki_engine.models import WikiPage


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


class SymbolsResponse(BaseModel):
    repo_id: str
    symbols: list[CodeSymbol]


class RepoGraphResponse(BaseModel):
    repo_id: str
    graph: RepoGraph


class GenerateWikiResponse(BaseModel):
    repo_id: str
    run_id: str
    pages: list[WikiPage]


class WikiListResponse(BaseModel):
    repo_id: str
    pages: list[WikiPage]


class WikiPageResponse(BaseModel):
    repo_id: str
    page: WikiPage


class AskRepositoryRequest(BaseModel):
    question: str = Field(..., min_length=1)


class SourceFileResponse(BaseModel):
    repo_id: str
    file_path: str
    content: str
    line_count: int


class RunResponse(BaseModel):
    run: AgentRun


class AskRepositoryResponse(AskAnswer):
    pass
