import asyncio
from typing import ClassVar

import pytest

from app.retrieval.embeddings import OpenAIQueryEmbedder


class FakeEmbedding:
    embedding: ClassVar[list[float]] = [0.1, 0.2, 0.3]


class FakeResponse:
    data: ClassVar[list[FakeEmbedding]] = [FakeEmbedding()]


class FakeEmbeddingsClient:
    def __init__(self):
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeResponse()


class FakeClient:
    def __init__(self):
        self.embeddings = FakeEmbeddingsClient()


def test_embed_query_uses_configured_model_and_dimensions(monkeypatch):
    monkeypatch.setattr("app.retrieval.embeddings.settings.OPENAI_EMBEDDING_DIMENSIONS", 3)
    fake_client = FakeClient()
    embedder = OpenAIQueryEmbedder(client=fake_client)

    vector = asyncio.run(embedder.embed_query("  Apple revenue mix  "))

    assert vector == [0.1, 0.2, 0.3]
    assert fake_client.embeddings.calls == [
        {
            "model": "text-embedding-3-small",
            "input": ["Apple revenue mix"],
            "dimensions": 3,
            "encoding_format": "float",
        }
    ]


def test_embed_query_rejects_blank_query():
    embedder = OpenAIQueryEmbedder(client=FakeClient())

    with pytest.raises(ValueError, match="query"):
        asyncio.run(embedder.embed_query("   "))
