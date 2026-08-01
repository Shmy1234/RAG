import pytest

from app.chat.stub_stream import build_stub_reply, stream_stub_reply


def test_build_stub_reply_includes_trimmed_prompt() -> None:
    reply = build_stub_reply("  What changed in Services?  ")

    assert '"What changed in Services?"' in reply
    assert "Phase 5" in reply


@pytest.mark.anyio
async def test_stream_stub_reply_yields_reconstructable_text() -> None:
    chunks = [chunk async for chunk in stream_stub_reply("What changed?")]

    assert "".join(chunks) == build_stub_reply("What changed?")
