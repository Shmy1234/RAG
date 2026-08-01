"""Run one manually selected assistant query against the configured services."""

import asyncio
import json
from uuid import uuid4

from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.assistant.agent import agent_usage_limits, document_agent
from app.assistant.deps import DocumentAgentDeps
from app.config import settings
from app.grounding.validator import GroundingValidator
from app.retrieval.retriever import DocumentRetriever
from app.retrieval.schemas import RetrievalFilters
from ingest.repository import create_sessionmaker

USER_QUERIES = {
    "apple_revenue_mix": "Across Apple's latest 10-K, what happened to Services revenue?",
    "generative_ai_margins": "What do the filings disclose about generative AI margins?",
}

QUERY_FILTERS = {
    "apple_revenue_mix": RetrievalFilters(
        tickers=("AAPL",),
        filing_types=("10-K",),
        fiscal_years=(2025,),
    ),
    "generative_ai_margins": RetrievalFilters(),
}


def format_answer(answer) -> str:
    return json.dumps(
        {
            "answer": answer.answer,
            "citations": [citation.model_dump(mode="json") for citation in answer.citations],
        },
        indent=2,
    )


async def run_query(query_key: str = "apple_revenue_mix") -> None:
    query = USER_QUERIES[query_key]
    filters = QUERY_FILTERS[query_key]

    retriever = DocumentRetriever(session_factory=create_sessionmaker())
    validator = GroundingValidator()
    model = OpenAIChatModel(
        "gpt-4o-mini",
        provider=OpenAIProvider(api_key=settings.OPENAI_API_KEY),
    )
    deps = DocumentAgentDeps(
        user_id=uuid4(),
        thread_id=uuid4(),
        retriever=retriever,
        grounding_validator=validator,
        retrieval_filters=filters,
    )
    result = await document_agent.run(
        query,
        deps=deps,
        model=model,
        usage_limits=agent_usage_limits(),
    )
    answer = validator.validate(
        result.output,
        deps.retrieved_passages,
        evidence_candidates=deps.evidence_candidates,
    )
    print(format_answer(answer))


def main() -> None:
    asyncio.run(run_query())


if __name__ == "__main__":
    main()
