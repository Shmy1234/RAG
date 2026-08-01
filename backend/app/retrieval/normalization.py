import re

_TOKEN_RE = re.compile(r"[A-Za-z]+\d+[A-Za-z0-9'-]*|[A-Za-z][A-Za-z'-]*|\d+(?:\.\d+)?%?|\S")
_FILLER_WORDS = frozenset(
    {
        "can",
        "could",
        "please",
        "tell",
        "show",
        "give",
        "just",
        "really",
        "actually",
        "basically",
        "kind",
        "sort",
        "like",
        "maybe",
        "perhaps",
        "i",
        "we",
        "you",
        "our",
        "the",
        "a",
        "an",
        "in",
        "for",
    }
)


def normalize_full_text_query(query: str) -> str:
    tokens = _TOKEN_RE.findall(query.strip())
    kept = [token for token in tokens if token.lower() not in _FILLER_WORDS]
    normalized = " ".join(kept).strip()
    return normalized or query.strip()
