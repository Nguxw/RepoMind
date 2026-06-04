from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class VectorDocument:
    id: str
    text: str
    metadata: dict
    vector: list[float]


class InMemoryVectorStore:
    def __init__(self) -> None:
        self.documents: dict[str, VectorDocument] = {}

    def upsert_texts(self, texts: list[tuple[str, str, dict]]) -> None:
        for doc_id, text, metadata in texts:
            self.documents[doc_id] = VectorDocument(id=doc_id, text=text, metadata=metadata, vector=embed_text(text))

    def search(self, query: str, limit: int = 5) -> list[VectorDocument]:
        query_vector = embed_text(query)
        return sorted(self.documents.values(), key=lambda doc: cosine(query_vector, doc.vector), reverse=True)[:limit]


class QdrantVectorStore:
    def __init__(self, url: str | None = None, collection: str = "repomind") -> None:
        try:
            from qdrant_client import QdrantClient
        except ImportError as exc:
            raise RuntimeError("qdrant-client is not installed. Install repomind[vector] or use in-memory vector search.") from exc
        self.url = url or os.getenv("QDRANT_URL", "http://localhost:6333")
        self.collection = collection
        self.client = QdrantClient(url=self.url)

    def upsert_texts(self, texts: list[tuple[str, str, dict]]) -> None:
        from qdrant_client.models import Distance, PointStruct, VectorParams

        self._ensure_collection()
        points = [
            PointStruct(
                id=_stable_point_id(doc_id),
                vector=embed_text(text),
                payload={"doc_id": doc_id, "text": text, **metadata},
            )
            for doc_id, text, metadata in texts
        ]
        self.client.upsert(collection_name=self.collection, points=points)

    def search(self, query: str, limit: int = 5) -> list[VectorDocument]:
        self._ensure_collection()
        vector = embed_text(query)
        if hasattr(self.client, "query_points"):
            response = self.client.query_points(collection_name=self.collection, query=vector, limit=limit)
            points = response.points
        else:
            points = self.client.search(collection_name=self.collection, query_vector=vector, limit=limit)
        results: list[VectorDocument] = []
        for point in points:
            payload = point.payload or {}
            text = str(payload.get("text", ""))
            doc_id = str(payload.get("doc_id", point.id))
            metadata = {key: value for key, value in payload.items() if key not in {"text", "doc_id"}}
            results.append(VectorDocument(id=doc_id, text=text, metadata=metadata, vector=vector))
        return results

    def _ensure_collection(self) -> None:
        from qdrant_client.models import Distance, VectorParams

        try:
            self.client.get_collection(self.collection)
        except Exception:
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=64, distance=Distance.COSINE),
            )


class PgVectorStore:
    def __init__(self, database_url: str | None = None) -> None:
        from sqlalchemy import Column, MetaData, String, Text, create_engine
        from sqlalchemy.orm import declarative_base

        self.database_url = database_url or os.getenv("DATABASE_URL", "sqlite:///data/repomind_vectors.db")
        self.engine = create_engine(self.database_url, future=True, connect_args={"check_same_thread": False} if self.database_url.startswith("sqlite") else {})
        Base = declarative_base(metadata=MetaData())

        class VectorRow(Base):
            __tablename__ = "vector_documents"

            id = Column(String(128), primary_key=True)
            text = Column(Text, nullable=False)
            metadata_json = Column(Text, nullable=False)
            vector_json = Column(Text, nullable=False)

        self.row_model = VectorRow
        Base.metadata.create_all(self.engine)

    def upsert_texts(self, texts: list[tuple[str, str, dict]]) -> None:
        from sqlalchemy.orm import Session

        with Session(self.engine) as session:
            for doc_id, text, metadata in texts:
                row = self.row_model(id=doc_id, text=text, metadata_json=json.dumps(metadata), vector_json=json.dumps(embed_text(text)))
                session.merge(row)
            session.commit()

    def search(self, query: str, limit: int = 5) -> list[VectorDocument]:
        from sqlalchemy import select
        from sqlalchemy.orm import Session

        query_vector = embed_text(query)
        with Session(self.engine) as session:
            rows = session.execute(select(self.row_model)).scalars().all()
        documents = [
            VectorDocument(
                id=row.id,
                text=row.text,
                metadata=json.loads(row.metadata_json),
                vector=json.loads(row.vector_json),
            )
            for row in rows
        ]
        return sorted(documents, key=lambda doc: cosine(query_vector, doc.vector), reverse=True)[:limit]


def create_vector_store():
    store = os.getenv("REPOMIND_VECTOR_STORE", "memory").lower()
    if store == "qdrant":
        return QdrantVectorStore()
    if store in {"pgvector", "postgres"}:
        return PgVectorStore()
    return InMemoryVectorStore()


def embed_text(text: str, dimensions: int = 64) -> list[float]:
    vector = [0.0] * dimensions
    for token in text.lower().split():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:2], "big") % dimensions
        vector[index] += 1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def _stable_point_id(value: str) -> str:
    import uuid

    return str(uuid.uuid5(uuid.NAMESPACE_URL, value))
