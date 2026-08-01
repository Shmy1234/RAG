from collections.abc import Sequence
from uuid import UUID

from app.assistant.outputs import GroundedAnswer
from app.retrieval.schemas import ChunkReference, SourcePassage


class GroundingError(ValueError):
    """Raised when an answer cannot be tied to the current retrieved evidence."""


class GroundingValidator:
    def validate(
        self,
        answer: GroundedAnswer,
        passages: Sequence[SourcePassage],
    ) -> GroundedAnswer:
        chunks = self._chunk_index(passages)
        if not answer.citations:
            if self._is_insufficient_evidence(answer.answer):
                return answer
            raise GroundingError("answer must include at least one citation")

        cited_chunks: list[ChunkReference] = []
        seen_ids: set[UUID] = set()
        for citation in answer.citations:
            chunk = chunks.get(citation.chunk_id)
            if chunk is None:
                raise GroundingError("citation refers to a chunk that was not retrieved")
            if citation.quoted_text not in chunk.text:
                raise GroundingError("citation quote does not appear in the retrieved chunk")
            if citation.citation_label != chunk.citation_label:
                raise GroundingError("citation label does not match the retrieved chunk")
            if citation.location_label != chunk.location_label:
                raise GroundingError("citation location does not match the retrieved chunk")
            if chunk.chunk_id not in seen_ids:
                cited_chunks.append(chunk)
                seen_ids.add(chunk.chunk_id)

        return answer.model_copy(update={"cited_passages": self._passages_for_chunks(passages, cited_chunks)})

    @staticmethod
    def _chunk_index(passages: Sequence[SourcePassage]) -> dict[UUID, ChunkReference]:
        chunks: dict[UUID, ChunkReference] = {}
        for passage in passages:
            chunks[passage.center.chunk.chunk_id] = passage.center.chunk
            for chunk in passage.previous_chunks + passage.next_chunks:
                chunks[chunk.chunk_id] = chunk
        return chunks

    @staticmethod
    def _passages_for_chunks(
        passages: Sequence[SourcePassage],
        cited_chunks: Sequence[ChunkReference],
    ) -> list[SourcePassage]:
        cited_ids = {chunk.chunk_id for chunk in cited_chunks}
        return [
            passage
            for passage in passages
            if passage.center.chunk.chunk_id in cited_ids
            or any(chunk.chunk_id in cited_ids for chunk in passage.previous_chunks)
            or any(chunk.chunk_id in cited_ids for chunk in passage.next_chunks)
        ]

    @staticmethod
    def _is_insufficient_evidence(answer: str) -> bool:
        normalized = answer.casefold()
        return any(
            phrase in normalized
            for phrase in (
                "not enough evidence",
                "insufficient evidence",
                "corpus does not contain enough",
                "cannot determine from the available filings",
            )
        )
