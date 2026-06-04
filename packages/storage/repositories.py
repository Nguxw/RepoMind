from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from packages.code_intelligence.models import CodeSymbol, RepoGraph
from packages.repo_ingestion.models import FileNode, RepoProfile


class RepositoryRecord(BaseModel):
    repo_id: str
    source_url: str
    local_path: str
    profile: RepoProfile
    file_tree: FileNode
    symbols: list[CodeSymbol] = Field(default_factory=list)
    graph: RepoGraph | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FileRepositoryStore:
    def __init__(self, base_path: str | Path | None = None) -> None:
        root = Path(base_path or os.getenv("REPOMIND_DATA_DIR", "data")).resolve()
        self.root = root
        self.repos_dir = root / "repos"
        self.metadata_dir = root / "metadata"
        self.repos_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

    def save(self, record: RepositoryRecord) -> None:
        path = self._record_path(record.repo_id)
        payload = record.model_dump(mode="json")
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def get(self, repo_id: str) -> RepositoryRecord | None:
        path = self._record_path(repo_id)
        if not path.exists():
            return None
        return RepositoryRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def _record_path(self, repo_id: str) -> Path:
        return self.metadata_dir / f"{repo_id}.json"
