from __future__ import annotations

import hashlib
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
        # Keep the interface ready without forcing a remote write in tests.
        raise NotImplementedError("Qdrant upsert is configured but not enabled in the MVP worker path yet.")


def create_vector_store():
    if os.getenv("REPOMIND_VECTOR_STORE", "memory").lower() == "qdrant":
        return QdrantVectorStore()
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
