"""Run one manually selected assistant query against the configured services."""

import asyncio
from uuid import uuid4

from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.assistant.agent import document_agent
from app.assistant.deps import DocumentAgentDeps
from app.config import settings
from app.grounding.validator import GroundingValidator
from app.retrieval.retriever import DocumentRetriever
from ingest.repository import create_sessionmaker

USER_QUERIES = {
    "apple_revenue_mix": "Across Apple's latest 10-K, what happened to Services revenue?",
    "generative_ai_margins": "What do the filings disclose about generative AI margins?",
}


def run_query(query_key: str = "apple_revenue_mix") -> None:
    query = USER_QUERIES[query_key]

    async def run() -> None:
        retriever = DocumentRetriever(session_factory=create_sessionmaker())
        validator = GroundingValidator()
        passages = await retriever.retrieve(query, top_k=5, candidate_k=50)
        agent = document_agent
        model = OpenAIChatModel(
            "gpt-4o-mini",
            provider=OpenAIProvider(api_key=settings.OPENAI_API_KEY),
        )
        result = await agent.run(
            query,
            deps=DocumentAgentDeps(
                user_id=uuid4(),
                thread_id=uuid4(),
                retriever=retriever,
                grounding_validator=validator,
            ),
            model=model,
        )
        answer = validator.validate(result.output, passages)
        print(answer.model_dump_json(indent=2))

    asyncio.run(run())


if __name__ == "__main__":
    run_query()
