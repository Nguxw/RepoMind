from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from apps.api.schemas import (
    FileTreeResponse,
    GenerateWikiResponse,
    ImportRepositoryRequest,
    ImportRepositoryResponse,
    RepoGraphResponse,
    RepoProfileResponse,
    RunResponse,
    AskRepositoryRequest,
    AskRepositoryResponse,
    SourceFileResponse,
    SymbolsResponse,
    WikiListResponse,
    WikiPageResponse,
)
from packages.code_intelligence import build_repo_graph, extract_symbols
from packages.code_intelligence.models import RepoGraph
from packages.harness.runtime import AgentRuntime
from packages.model_gateway import create_model_client
from packages.repo_ingestion.clone import CloneResult, InvalidRepositoryUrl, RepositoryCloneError, clone_repository
from packages.repo_ingestion.detect import scan_repository
from packages.repo_ingestion.profile import build_repo_profile
from packages.storage import FileRepositoryStore, RepositoryRecord, create_repository_store
from packages.tasks import create_task_queue

CloneFunc = Callable[[str, str, int], CloneResult]


def create_app(
    store: FileRepositoryStore | None = None,
    clone_func: CloneFunc = clone_repository,
) -> FastAPI:
    app = FastAPI(
        title="RepoMind API",
        description="Repository ingestion and profiling API for RepoMind.",
        version="0.1.0",
    )
    app.state.store = store or create_repository_store()
    app.state.clone_repository = clone_func
    app.state.task_queue = create_task_queue()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "repomind-api"}

    @app.post("/api/repos/import", response_model=ImportRepositoryResponse)
    async def import_repository(payload: ImportRepositoryRequest, request: Request) -> ImportRepositoryResponse:
        store: FileRepositoryStore = request.app.state.store
        timeout = int(os.getenv("REPOMIND_CLONE_TIMEOUT_SECONDS", "120"))

        try:
            clone_result = await run_in_threadpool(
                request.app.state.clone_repository,
                payload.url,
                str(store.repos_dir),
                timeout,
            )
        except InvalidRepositoryUrl as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RepositoryCloneError as exc:
            raise HTTPException(status_code=400, detail=f"Repository clone failed: {exc}") from exc

        scan = await run_in_threadpool(scan_repository, clone_result.local_path)
        profile = await run_in_threadpool(
            build_repo_profile,
            clone_result.repo_id,
            clone_result.normalized_url,
            clone_result.local_path,
            scan,
            clone_result.commit_sha,
        )

        symbols = await run_in_threadpool(extract_symbols, clone_result.local_path, scan.included_files)
        graph = await run_in_threadpool(build_repo_graph, clone_result.repo_id, profile, scan.included_files, symbols)

        store.save(
            RepositoryRecord(
                repo_id=clone_result.repo_id,
                source_url=clone_result.normalized_url,
                local_path=clone_result.local_path,
                profile=profile,
                file_tree=scan.file_tree,
                symbols=symbols,
                graph=graph,
            )
        )

        return ImportRepositoryResponse(
            repo_id=profile.repo_id,
            repo_name=profile.name,
            local_path=profile.local_path,
            commit_sha=profile.commit_sha,
            languages=profile.languages,
            important_files=profile.important_files,
            profile_url=f"/api/repos/{profile.repo_id}/profile",
        )

    @app.get("/api/repos/{repo_id}/profile", response_model=RepoProfileResponse)
    async def get_profile(repo_id: str, request: Request) -> RepoProfileResponse:
        record = _get_record_or_404(request, repo_id)
        return RepoProfileResponse(repo_id=repo_id, profile=record.profile)

    @app.get("/api/repos/{repo_id}/files", response_model=FileTreeResponse)
    async def get_files(repo_id: str, request: Request) -> FileTreeResponse:
        record = _get_record_or_404(request, repo_id)
        return FileTreeResponse(repo_id=repo_id, tree=record.file_tree)

    @app.get("/api/repos/{repo_id}/symbols", response_model=SymbolsResponse)
    async def get_symbols(repo_id: str, request: Request) -> SymbolsResponse:
        record = _get_record_or_404(request, repo_id)
        return SymbolsResponse(repo_id=repo_id, symbols=record.symbols)

    @app.get("/api/repos/{repo_id}/graph", response_model=RepoGraphResponse)
    async def get_graph(repo_id: str, request: Request) -> RepoGraphResponse:
        record = _get_record_or_404(request, repo_id)
        graph = record.graph or RepoGraph(repo_id=repo_id)
        return RepoGraphResponse(repo_id=repo_id, graph=graph)

    @app.get("/api/repos/{repo_id}/source", response_model=SourceFileResponse)
    async def get_source_file(repo_id: str, request: Request, path: str = Query(..., min_length=1)) -> SourceFileResponse:
        record = _get_record_or_404(request, repo_id)
        content = _read_repo_file(record.local_path, path)
        return SourceFileResponse(repo_id=repo_id, file_path=path, content=content, line_count=len(content.splitlines()))

    @app.post("/api/repos/{repo_id}/wiki/generate", response_model=GenerateWikiResponse)
    async def generate_wiki(repo_id: str, request: Request) -> GenerateWikiResponse:
        store: FileRepositoryStore = request.app.state.store
        record = _get_record_or_404(request, repo_id)
        runtime = AgentRuntime(create_model_client())
        task = await request.app.state.task_queue.enqueue("generate_wiki_job", lambda: runtime.generate_wiki(record))
        if task.status != "completed":
            raise HTTPException(status_code=202, detail={"task_id": task.task_id, "status": task.status})
        pages, run = task.result
        record.wiki_pages = pages
        record.agent_runs.append(run)
        store.save(record)
        return GenerateWikiResponse(repo_id=repo_id, run_id=run.run_id, pages=pages)

    @app.get("/api/repos/{repo_id}/wiki", response_model=WikiListResponse)
    async def get_wiki(repo_id: str, request: Request) -> WikiListResponse:
        record = _get_record_or_404(request, repo_id)
        return WikiListResponse(repo_id=repo_id, pages=record.wiki_pages)

    @app.get("/api/repos/{repo_id}/wiki/{page_slug}", response_model=WikiPageResponse)
    async def get_wiki_page(repo_id: str, page_slug: str, request: Request) -> WikiPageResponse:
        record = _get_record_or_404(request, repo_id)
        pages = [page for page in record.wiki_pages if page.slug == page_slug]
        if not pages:
            raise HTTPException(status_code=404, detail=f"Wiki page {page_slug} was not found.")
        return WikiPageResponse(repo_id=repo_id, page=pages[0])

    @app.post("/api/repos/{repo_id}/ask", response_model=AskRepositoryResponse)
    async def ask_repository(repo_id: str, payload: AskRepositoryRequest, request: Request) -> AskRepositoryResponse:
        store: FileRepositoryStore = request.app.state.store
        record = _get_record_or_404(request, repo_id)
        if not record.wiki_pages:
            runtime = AgentRuntime(create_model_client())
            pages, wiki_run = await runtime.generate_wiki(record)
            record.wiki_pages = pages
            record.agent_runs.append(wiki_run)
        runtime = AgentRuntime(create_model_client())
        answer, run = await runtime.ask(record, payload.question)
        record.agent_runs.append(run)
        store.save(record)
        return AskRepositoryResponse(**answer.model_dump())

    @app.get("/api/runs/{run_id}", response_model=RunResponse)
    async def get_run(run_id: str, request: Request) -> RunResponse:
        store: FileRepositoryStore = request.app.state.store
        found = store.find_run(run_id)
        if found is None:
            raise HTTPException(status_code=404, detail=f"Run {run_id} was not found.")
        return RunResponse(run=found[1])

    @app.get("/api/runs/{run_id}/trace", response_model=RunResponse)
    async def get_run_trace(run_id: str, request: Request) -> RunResponse:
        return await get_run(run_id, request)

    return app


def _get_record_or_404(request: Request, repo_id: str) -> RepositoryRecord:
    store: FileRepositoryStore = request.app.state.store
    record = store.get(repo_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Repository {repo_id} was not found.")
    return record


def _read_repo_file(repo_root: str, relative_path: str) -> str:
    root = Path(repo_root).resolve()
    target = (root / relative_path).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="File path escapes repository root.")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail=f"File {relative_path} was not found.")
    return target.read_text(encoding="utf-8", errors="ignore")


app = create_app()
