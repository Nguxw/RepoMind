from __future__ import annotations

from packages.storage.db import create_repository_store
from packages.storage.postgres import SqlRepositoryStore
from packages.storage.repositories import FileRepositoryStore


def test_file_storage_setting_wins_over_database_url(monkeypatch) -> None:
    monkeypatch.setenv("REPOMIND_STORAGE", "file")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://repomind:repomind@postgres:5432/repomind")

    store = create_repository_store()

    assert isinstance(store, FileRepositoryStore)


def test_auto_storage_uses_postgres_database_url(monkeypatch) -> None:
    monkeypatch.setenv("REPOMIND_STORAGE", "auto")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    store = create_repository_store()

    assert isinstance(store, SqlRepositoryStore)
