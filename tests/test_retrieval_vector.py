from packages.retrieval.vector_search import InMemoryVectorStore, PgVectorStore


def test_in_memory_vector_store_returns_semantic_overlap():
    store = InMemoryVectorStore()
    store.upsert_texts([
        ("a", "fastapi app factory", {"path": "main.py"}),
        ("b", "training dataset pipeline", {"path": "train.py"}),
    ])

    hits = store.search("where is fastapi created", limit=1)

    assert hits[0].id == "a"


def test_pgvector_store_round_trips_with_sql_fallback(tmp_path):
    store = PgVectorStore(f"sqlite:///{tmp_path / 'vectors.db'}")
    store.upsert_texts([
        ("main", "fastapi app factory", {"path": "main.py"}),
        ("train", "training loop", {"path": "train.py"}),
    ])

    hits = store.search("fastapi application", limit=1)

    assert hits[0].id == "main"
    assert hits[0].metadata["path"] == "main.py"
