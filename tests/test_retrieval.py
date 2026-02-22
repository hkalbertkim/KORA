from kora.retrieval import InMemoryRetrievalStore


def test_retrieval_ttl_expiry() -> None:
    now = [1000.0]

    def _clock() -> float:
        return now[0]

    store = InMemoryRetrievalStore(max_entries=10, clock=_clock)
    store.put("k", {"v": 1}, ttl_seconds=1)
    assert store.get("k") == {"v": 1}

    now[0] = 1002.0
    assert store.get("k") is None
