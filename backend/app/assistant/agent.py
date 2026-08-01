from pathlib import Path
from uuid import UUID

from pydantic_ai import Agent, RunContext

from app.assistant.deps import DocumentAgentDeps
from app.assistant.outputs import GroundedAnswer
from app.retrieval.schemas import ChunkReference, SourcePassage

_instructions = Path(__file__).with_name("instructions.md").read_text()

document_agent = Agent(
    deps_type=DocumentAgentDeps,
    output_type=GroundedAnswer,
    instructions=_instructions,
)


@document_agent.tool
async def search_filings(
    ctx: RunContext[DocumentAgentDeps],
    query: str,
    top_k: int = 5,
) -> list[SourcePassage]:
    if top_k < 1:
        raise ValueError("top_k must be greater than zero")
    passages = await ctx.deps.retriever.retrieve(query, top_k=min(top_k, 10), candidate_k=50)
    ctx.deps.retrieved_passages.extend(passages)
    return passages


@document_agent.tool
async def read_chunk(
    ctx: RunContext[DocumentAgentDeps],
    chunk_id: UUID,
) -> ChunkReference | str:
    chunk = await ctx.deps.retriever.read_chunk(chunk_id)
    return chunk if chunk is not None else "No chunk was found for that id."


@document_agent.tool
async def read_surrounding_chunks(
    ctx: RunContext[DocumentAgentDeps],
    chunk_id: UUID,
    window: int = 1,
) -> dict[str, list[ChunkReference]] | str:
    if window < 0 or window > 3:
        raise ValueError("window must be between 0 and 3")
    result = await ctx.deps.retriever.read_surrounding_chunks(chunk_id, window=window)
    if result is None:
        return "No chunk was found for that id."
    return result
