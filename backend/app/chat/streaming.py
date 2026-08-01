import json
from collections.abc import AsyncIterator

from app.assistant.outputs import GroundedAnswer


async def stream_grounded_answer(
    answer: GroundedAnswer,
    *,
    chunk_size: int = 80,
) -> AsyncIterator[str]:
    if chunk_size < 1:
        raise ValueError("chunk_size must be greater than zero")

    yield _event({"type": "start", "messageId": "assistant-message"})
    yield _event({"type": "text-start", "id": "text-1"})
    for start in range(0, len(answer.answer), chunk_size):
        chunk = answer.answer[start : start + chunk_size]
        yield _event({"type": "text-delta", "id": "text-1", "delta": chunk})

    citation_data = [citation.model_dump(mode="json") for citation in answer.citations]
    yield _event({"type": "text-end", "id": "text-1"})
    yield _event({"type": "data-citations", "data": citation_data})
    yield _event({"type": "finish", "finishReason": "stop"})


def _event(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload)}\n\n"
