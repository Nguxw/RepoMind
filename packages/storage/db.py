from __future__ import annotations

import os

from packages.storage.postgres import SqlRepositoryStore
from packages.storage.repositories import FileRepositoryStore


def create_repository_store():
    storage = os.getenv("REPOMIND_STORAGE", "file").lower()
    database_url = os.getenv("DATABASE_URL", "")
    if storage in {"postgres", "postgresql", "sql"} or database_url.startswith(("postgresql://", "postgresql+")):
        return SqlRepositoryStore(database_url=database_url)
    return FileRepositoryStore()
