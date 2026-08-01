from collections.abc import AsyncIterator


def build_stub_reply(user_text: str) -> str:
    prompt = user_text.strip()
    if not prompt:
        return "I received your message. Phase 3 is wired for streaming, and retrieval will be added in Phase 5."
    return (
        "Stub response: I received your question about "
        f'"{prompt[:120]}". Retrieval and grounded citations will be added in Phase 5 and Phase 6.'
    )


async def stream_stub_reply(user_text: str) -> AsyncIterator[str]:
    reply = build_stub_reply(user_text)
    words = reply.split(" ")
    for index, word in enumerate(words):
        yield word
        if index < len(words) - 1:
            yield " "
