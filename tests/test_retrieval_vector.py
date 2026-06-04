from packages.retrieval.vector_search import InMemoryVectorStore


def test_in_memory_vector_store_returns_semantic_overlap():
    store = InMemoryVectorStore()
    store.upsert_texts([
        ("a", "fastapi app factory", {"path": "main.py"}),
        ("b", "training dataset pipeline", {"path": "train.py"}),
    ])

    hits = store.search("where is fastapi created", limit=1)

    assert hits[0].id == "a"
