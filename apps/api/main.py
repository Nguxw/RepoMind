from __future__ import annotations

import os
from typing import Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from apps.api.schemas import (
    FileTreeResponse,
    ImportRepositoryRequest,
    ImportRepositoryResponse,
    RepoProfileResponse,
)
from packages.repo_ingestion.clone import CloneResult, InvalidRepositoryUrl, RepositoryCloneError, clone_repository
from packages.repo_ingestion.detect import scan_repository
from packages.repo_ingestion.profile import build_repo_profile
from packages.storage import FileRepositoryStore, RepositoryRecord

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
    app.state.store = store or FileRepositoryStore()
    app.state.clone_repository = clone_func

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

        store.save(
            RepositoryRecord(
                repo_id=clone_result.repo_id,
                source_url=clone_result.normalized_url,
                local_path=clone_result.local_path,
                profile=profile,
                file_tree=scan.file_tree,
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

    return app


def _get_record_or_404(request: Request, repo_id: str) -> RepositoryRecord:
    store: FileRepositoryStore = request.app.state.store
    record = store.get(repo_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Repository {repo_id} was not found.")
    return record


app = create_app()
