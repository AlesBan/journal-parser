import re

# Soft hyphen and common Unicode dashes treated as hyphen for merge rules.
_SOFT_HYPHEN = "\u00ad"
_DASH_CHARS = "-‐‑‒–—―"

# Keep letters (Latin + Cyrillic), digits, and formula-related symbols.
_KEEP_RE = re.compile(
    r"[^0-9a-zA-Z"
    r"\u0400-\u04FF"
    r"\(\)\[\]\+\.,]"
)

_WORD_HYPHEN_RE = re.compile(
    r"(?<=[a-zA-Z\u0400-\u04FF])[-"
    + re.escape(_DASH_CHARS)
    + r"]+(?=[a-zA-Z\u0400-\u04FF])"
)


def normalize(text: str) -> str:
    """
    Normalize text for gazetteer matching.

    - lower case; ё -> е
    - remove whitespace
    - remove word-break hyphens between letters
    - keep digits and formula symbols: () [] + . ,
    """
    if not text:
        return ""

    t = text.replace(_SOFT_HYPHEN, "")
    for d in _DASH_CHARS:
        t = t.replace(d, "-")

    t = t.lower().replace("ё", "е")
    t = re.sub(r"\s+", "", t)
    t = _WORD_HYPHEN_RE.sub("", t)
    t = _KEEP_RE.sub("", t)
    return t


def is_valid_search_key(key: str, min_length: int = 6) -> bool:
    if len(key) < min_length:
        return False
    if key.isdigit():
        return False
    if not re.search(r"[a-zA-Z\u0400-\u04FF]", key):
        return False
    return True
