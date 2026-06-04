from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, MetaData, String, Text, create_engine, delete, select
from sqlalchemy.orm import Session, declarative_base

from packages.storage.repositories import RepositoryRecord

Base = declarative_base(metadata=MetaData())


class RepositoryRow(Base):
    __tablename__ = "repositories"

    repo_id = Column(String(64), primary_key=True)
    source_url = Column(Text, nullable=False)
    local_path = Column(Text, nullable=False)
    payload = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)


class FileRow(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repo_id = Column(String(64), ForeignKey("repositories.repo_id", ondelete="CASCADE"), index=True, nullable=False)
    file_path = Column(Text, nullable=False)
    payload = Column(Text, nullable=False)


class SymbolRow(Base):
    __tablename__ = "symbols"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repo_id = Column(String(64), ForeignKey("repositories.repo_id", ondelete="CASCADE"), index=True, nullable=False)
    symbol_id = Column(Text, nullable=False)
    payload = Column(Text, nullable=False)


class EdgeRow(Base):
    __tablename__ = "edges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repo_id = Column(String(64), ForeignKey("repositories.repo_id", ondelete="CASCADE"), index=True, nullable=False)
    source = Column(Text, nullable=False)
    target = Column(Text, nullable=False)
    edge_type = Column(String(64), nullable=False)
    payload = Column(Text, nullable=False)


class WikiPageRow(Base):
    __tablename__ = "wiki_pages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repo_id = Column(String(64), ForeignKey("repositories.repo_id", ondelete="CASCADE"), index=True, nullable=False)
    slug = Column(String(128), nullable=False)
    payload = Column(Text, nullable=False)


class WikiCitationRow(Base):
    __tablename__ = "wiki_citations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repo_id = Column(String(64), ForeignKey("repositories.repo_id", ondelete="CASCADE"), index=True, nullable=False)
    page_slug = Column(String(128), nullable=False)
    file_path = Column(Text, nullable=False)
    start_line = Column(Integer, nullable=False)
    end_line = Column(Integer, nullable=False)
    payload = Column(Text, nullable=False)


class AgentRunRow(Base):
    __tablename__ = "agent_runs"

    run_id = Column(String(64), primary_key=True)
    repo_id = Column(String(64), ForeignKey("repositories.repo_id", ondelete="CASCADE"), index=True, nullable=False)
    task = Column(Text, nullable=False)
    payload = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)


class ToolCallRow(Base):
    __tablename__ = "tool_calls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), ForeignKey("agent_runs.run_id", ondelete="CASCADE"), index=True, nullable=False)
    tool = Column(Text, nullable=False)
    payload = Column(Text, nullable=False)


class SqlRepositoryStore:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.getenv("DATABASE_URL", "sqlite:///data/repomind.db")
        connect_args = {"check_same_thread": False} if self.database_url.startswith("sqlite") else {}
        self.engine = create_engine(self.database_url, future=True, connect_args=connect_args)
        Base.metadata.create_all(self.engine)

    @property
    def repos_dir(self):
        from pathlib import Path

        root = Path(os.getenv("REPOMIND_DATA_DIR", "data")).resolve()
        path = root / "repos"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save(self, record: RepositoryRecord) -> None:
        payload = record.model_dump(mode="json")
        with Session(self.engine) as session:
            self._delete_derived(session, record.repo_id)
            existing = session.get(RepositoryRow, record.repo_id)
            row = existing or RepositoryRow(repo_id=record.repo_id)
            row.source_url = record.source_url
            row.local_path = record.local_path
            row.payload = json.dumps(payload)
            row.created_at = _to_datetime(payload.get("created_at"))
            session.merge(row)
            session.flush()
            self._insert_derived(session, record)
            session.commit()

    def get(self, repo_id: str) -> RepositoryRecord | None:
        with Session(self.engine) as session:
            row = session.get(RepositoryRow, repo_id)
            if row is None:
                return None
            return RepositoryRecord.model_validate_json(row.payload)

    def find_run(self, run_id: str):
        with Session(self.engine) as session:
            row = session.get(AgentRunRow, run_id)
            if row is None:
                return None
            repo = session.get(RepositoryRow, row.repo_id)
            if repo is None:
                return None
            record = RepositoryRecord.model_validate_json(repo.payload)
            for run in record.agent_runs:
                if run.run_id == run_id:
                    return record, run
            return None

    def _delete_derived(self, session: Session, repo_id: str) -> None:
        run_ids = [row.run_id for row in session.execute(select(AgentRunRow.run_id).where(AgentRunRow.repo_id == repo_id)).all()]
        if run_ids:
            session.execute(delete(ToolCallRow).where(ToolCallRow.run_id.in_(run_ids)))
        for table in (FileRow, SymbolRow, EdgeRow, WikiPageRow, WikiCitationRow, AgentRunRow):
            session.execute(delete(table).where(table.repo_id == repo_id))

    def _insert_derived(self, session: Session, record: RepositoryRecord) -> None:
        for file_path in _file_paths(record.file_tree):
            session.add(FileRow(repo_id=record.repo_id, file_path=file_path, payload=json.dumps({"file_path": file_path})))
        for symbol in record.symbols:
            session.add(SymbolRow(repo_id=record.repo_id, symbol_id=symbol.id, payload=symbol.model_dump_json()))
        for edge in record.graph_or_empty().edges:
            session.add(EdgeRow(repo_id=record.repo_id, source=edge.source, target=edge.target, edge_type=edge.type, payload=edge.model_dump_json()))
        for page in record.wiki_pages:
            session.add(WikiPageRow(repo_id=record.repo_id, slug=page.slug, payload=page.model_dump_json()))
            for section in page.sections:
                for citation in section.citations:
                    session.add(
                        WikiCitationRow(
                            repo_id=record.repo_id,
                            page_slug=page.slug,
                            file_path=citation.file_path,
                            start_line=citation.start_line,
                            end_line=citation.end_line,
                            payload=citation.model_dump_json(),
                        )
                    )
        for run in record.agent_runs:
            session.add(AgentRunRow(run_id=run.run_id, repo_id=record.repo_id, task=run.task, payload=run.model_dump_json(), created_at=run.created_at))
            for step in run.steps:
                session.add(ToolCallRow(run_id=run.run_id, tool=step.tool, payload=step.model_dump_json()))


def _file_paths(node) -> list[str]:
    paths: list[str] = []
    if node.type == "file":
        paths.append(node.path)
    for child in node.children:
        paths.extend(_file_paths(child))
    return paths


def _to_datetime(value) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc)
