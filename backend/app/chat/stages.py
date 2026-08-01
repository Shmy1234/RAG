from typing import Literal

Stage = Literal["routing", "searching", "analyzing", "validating", "saving"]

ErrorCode = Literal["retrieval_failed", "grounding_failed", "processing_failed"]

STAGE_ORDER: tuple[Stage, ...] = ("routing", "searching", "analyzing", "validating", "saving")


class RetrievalError(Exception):
    """Raised when the filing corpus could not be searched for a turn."""
