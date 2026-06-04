from __future__ import annotations

import os

from packages.config import load_env_file
from packages.storage.postgres import SqlRepositoryStore
from packages.storage.repositories import FileRepositoryStore


def create_repository_store():
    load_env_file()
    storage = os.getenv("REPOMIND_STORAGE", "file").lower()
    database_url = os.getenv("DATABASE_URL", "")
    if storage in {"postgres", "postgresql", "sql"}:
        return SqlRepositoryStore(database_url=database_url)
    if storage == "auto" and database_url:
        return SqlRepositoryStore(database_url=database_url)
    return FileRepositoryStore()
