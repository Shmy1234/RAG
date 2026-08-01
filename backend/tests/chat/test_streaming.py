import asyncio
import json

from app.assistant.outputs import GroundedAnswer
from app.chat.stages import RetrievalError
from app.chat.streaming import stream_chat_turn, stream_grounded_answer
from app.grounding.validator import GroundingError


def test_stream_grounded_answer_emits_text_citations_and_finish_records():
    answer = GroundedAnswer(answer="Services revenue increased.")

    async def collect():
        return [part async for part in stream_grounded_answer(answer, chunk_size=10)]

    parts = asyncio.run(collect())

    assert parts[0] == 'data: {"type": "start", "messageId": "assistant-message"}\n\n'
    assert '"type": "text-delta"' in parts[2]
    assert '"type": "data-citations"' in parts[-2]
    assert parts[-1] == 'data: {"type": "finish", "finishReason": "stop"}\n\n'


def collect_turn(run_turn) -> list[str]:
    async def collect():
        return [part async for part in stream_chat_turn(run_turn, chunk_size=10)]

    return asyncio.run(collect())


def stages_in(parts: list[str]) -> list[str]:
    stages = []
    for part in parts:
        payload = json.loads(part.removeprefix("data: ").strip())
        if payload["type"] == "data-status":
            stages.append(payload["data"]["stage"])
    return stages


def test_stream_chat_turn_emits_stages_in_order_before_the_answer():
    async def run_turn(on_stage, on_answer_ready):
        await on_stage("routing")
        await on_stage("searching")
        await on_stage("analyzing")
        await on_stage("validating")
        await on_stage("saving")
        return GroundedAnswer(answer="Services revenue increased.")

    parts = collect_turn(run_turn)

    assert stages_in(parts) == ["routing", "searching", "analyzing", "validating", "saving"]
    last_status = max(index for index, part in enumerate(parts) if '"data-status"' in part)
    first_delta = min(index for index, part in enumerate(parts) if '"text-delta"' in part)
    assert last_status < first_delta
    assert parts[-1] == 'data: {"type": "finish", "finishReason": "stop"}\n\n'


def test_stream_chat_turn_accepts_short_non_rag_stage_sequence():
    async def run_turn(on_stage, on_answer_ready):
        await on_stage("routing")
        await on_stage("saving")
        return GroundedAnswer(answer="Hello.")

    parts = collect_turn(run_turn)

    assert stages_in(parts) == ["routing", "saving"]
    assert any('"delta": "Hello."' in part for part in parts)


def test_stream_chat_turn_reports_retrieval_failure_without_answer_text():
    async def run_turn(on_stage, on_answer_ready):
        await on_stage("searching")
        raise RetrievalError("pgvector connection reset at 10.0.0.4:5432")

    parts = collect_turn(run_turn)

    assert stages_in(parts) == ["searching"]
    assert '"code": "retrieval_failed"' in parts[-2]
    assert parts[-1] == 'data: {"type": "finish", "finishReason": "error"}\n\n'
    assert not any('"text-delta"' in part for part in parts)


def test_stream_chat_turn_reports_grounding_failure():
    async def run_turn(on_stage, on_answer_ready):
        await on_stage("searching")
        await on_stage("analyzing")
        await on_stage("validating")
        raise GroundingError("citation 2 does not map to retrieved evidence")

    parts = collect_turn(run_turn)

    assert stages_in(parts) == ["searching", "analyzing", "validating"]
    assert '"code": "grounding_failed"' in parts[-2]


def test_stream_chat_turn_never_leaks_exception_text():
    secret = "postgres://analyst:hunter2@db.internal:5432"

    async def run_turn(on_stage, on_answer_ready):
        await on_stage("searching")
        raise RuntimeError(secret)

    parts = collect_turn(run_turn)
    body = "".join(parts)

    assert '"code": "processing_failed"' in body
    assert secret not in body
    assert "RuntimeError" not in body


def test_stream_chat_turn_logs_unexpected_failure_with_traceback(monkeypatch):
    logged = []

    class FakeLogger:
        def exception(self, event, **context):
            logged.append((event, context))

    monkeypatch.setattr("app.chat.streaming.logger", FakeLogger())

    async def run_turn(on_stage, on_answer_ready):
        await on_stage("searching")
        raise RuntimeError("database unavailable")

    collect_turn(run_turn)

    assert logged == [
        (
            "chat_turn_failed",
            {"error_code": "processing_failed", "stage": "searching"},
        )
    ]


def test_stream_opens_before_slow_turn_work_completes():
    async def verify():
        release = asyncio.Event()

        async def run_turn(on_stage, on_answer_ready):
            await release.wait()
            return GroundedAnswer(answer="Finished.")

        stream = stream_chat_turn(run_turn)
        first = await asyncio.wait_for(anext(stream), timeout=0.1)
        release.set()
        await stream.aclose()
        return first

    first = asyncio.run(verify())

    assert first == 'data: {"type": "start", "messageId": "assistant-message"}\n\n'


def test_instant_text_arrives_before_persistence_finishes():
    async def verify():
        release_persistence = asyncio.Event()
        answer = GroundedAnswer(answer="Hello.")

        async def run_turn(on_stage, on_answer_ready):
            await on_stage("routing")
            await on_answer_ready(answer)
            await on_stage("saving")
            await release_persistence.wait()
            return answer

        stream = stream_chat_turn(run_turn)
        observed = []
        while not any('"text-delta"' in part for part in observed):
            observed.append(await asyncio.wait_for(anext(stream), timeout=0.1))
        assert not release_persistence.is_set()

        release_persistence.set()
        observed.extend([part async for part in stream])
        return observed

    parts = asyncio.run(verify())

    first_delta = next(index for index, part in enumerate(parts) if '"text-delta"' in part)
    saving = next(index for index, part in enumerate(parts) if '"stage": "saving"' in part)
    assert first_delta < saving
    assert parts[-1] == 'data: {"type": "finish", "finishReason": "stop"}\n\n'


def test_persistence_failure_after_early_text_finishes_with_typed_error():
    answer = GroundedAnswer(answer="Hello.")

    async def run_turn(on_stage, on_answer_ready):
        await on_answer_ready(answer)
        raise RuntimeError("database unavailable")

    parts = collect_turn(run_turn)

    assert any('"text-delta"' in part for part in parts)
    assert '"code": "processing_failed"' in parts[-2]
    assert parts[-1] == 'data: {"type": "finish", "finishReason": "error"}\n\n'
