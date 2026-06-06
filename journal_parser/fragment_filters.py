from __future__ import annotations

from pathlib import Path


def load_fragments(path: Path) -> list[str]:
    """
    Load fragments from text file (one per line).
    - strips whitespace
    - ignores empty lines and comments starting with '#'
    - lowercases and replaces 'ё' -> 'е'
    """
    if not path.exists():
        return []
    out: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        v = line.strip()
        if not v or v.startswith("#"):
            continue
        out.append(v.lower().replace("ё", "е"))
    # Prefer longer fragments first to reduce accidental matches if we later
    # add more advanced matching (still substring-based right now).
    out = sorted(set(out), key=len, reverse=True)
    return out


def matches_any_fragment(text: str, fragments: list[str]) -> bool:
    t = text.lower().replace("ё", "е")
    return any(frag in t for frag in fragments)

