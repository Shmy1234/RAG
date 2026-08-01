"""OpenAI embedding batching and response validation."""

import tiktoken
from openai import OpenAI

from app.config import settings
from ingest.chunking import OPENAI_MAX_INPUT_TOKENS, ChunkRecord

DEFAULT_MAX_BATCH_TOKENS = 250_000
DEFAULT_MAX_BATCH_ITEMS = 256


def count_embedding_tokens(text: str, model: str) -> int:
    return len(tiktoken.encoding_for_model(model).encode(text))


def batch_embedding_inputs(
    chunks: list[ChunkRecord],
    max_batch_tokens: int = DEFAULT_MAX_BATCH_TOKENS,
    max_batch_items: int = DEFAULT_MAX_BATCH_ITEMS,
) -> list[list[ChunkRecord]]:
    batches: list[list[ChunkRecord]] = []
    current: list[ChunkRecord] = []
    current_tokens = 0

    for chunk in chunks:
        if not chunk.text.strip():
            raise ValueError(f"Chunk {chunk.chunk_index} has empty embedding text")
        if chunk.token_count > OPENAI_MAX_INPUT_TOKENS:
            raise ValueError(
                f"Chunk {chunk.chunk_index} has {chunk.token_count} tokens; "
                f"OpenAI's maximum is {OPENAI_MAX_INPUT_TOKENS}"
            )
        if chunk.token_count > max_batch_tokens:
            raise ValueError(
                f"Chunk {chunk.chunk_index} exceeds the embedding batch budget of "
                f"{max_batch_tokens} tokens"
            )
        if current and (
            current_tokens + chunk.token_count > max_batch_tokens
            or len(current) >= max_batch_items
        ):
            batches.append(current)
            current = []
            current_tokens = 0
        current.append(chunk)
        current_tokens += chunk.token_count

    if current:
        batches.append(current)
    return batches


def validate_embedding_dimensions(
    vectors: list[list[float]],
    dimensions: int,
) -> list[list[float]]:
    for index, vector in enumerate(vectors):
        if len(vector) != dimensions:
            raise ValueError(
                f"Embedding {index} has dimension {len(vector)}; expected {dimensions}"
            )
    return vectors


def embed_texts(
    texts: list[str],
    model: str,
    dimensions: int,
) -> list[list[float]]:
    if not texts:
        return []
    if any(not text.strip() for text in texts):
        raise ValueError("Embedding input cannot be empty")

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    response = client.embeddings.create(
        model=model,
        input=texts,
        dimensions=dimensions,
        encoding_format="float",
    )
    vectors = [item.embedding for item in sorted(response.data, key=lambda item: item.index)]
    return validate_embedding_dimensions(vectors, dimensions)
