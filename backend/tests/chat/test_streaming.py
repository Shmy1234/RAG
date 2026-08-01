import asyncio

from app.assistant.outputs import GroundedAnswer
from app.chat.streaming import stream_grounded_answer


def test_stream_grounded_answer_emits_text_citations_and_finish_records():
    answer = GroundedAnswer(answer="Services revenue increased.")

    async def collect():
        return [part async for part in stream_grounded_answer(answer, chunk_size=10)]

    parts = asyncio.run(collect())

    assert parts[0] == 'data: {"type": "start", "messageId": "assistant-message"}\n\n'
    assert '"type": "text-delta"' in parts[2]
    assert '"type": "data-citations"' in parts[-2]
    assert parts[-1] == 'data: {"type": "finish", "finishReason": "stop"}\n\n'
