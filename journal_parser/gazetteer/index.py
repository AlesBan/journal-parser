from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

import ahocorasick

from journal_parser.normalize import is_valid_search_key, normalize


@dataclass(frozen=True)
class ConceptHit:
    concept_id: str
    display: str
    search_key: str
    source: str


class GazetteerIndex:
    def __init__(self, concepts: Dict[str, dict], automaton: ahocorasick.Automaton):
        self.concepts = concepts
        self._automaton = automaton

    def find_in_text(self, normalized_page_text: str) -> List[ConceptHit]:
        hits: List[ConceptHit] = []
        seen: Set[Tuple[str, int]] = set()

        for end_index, payload in self._automaton.iter(normalized_page_text):
            concept_id, search_key = payload
            start = end_index - len(search_key) + 1
            key = (concept_id, start)
            if key in seen:
                continue
            seen.add(key)
            concept = self.concepts[concept_id]
            hits.append(
                ConceptHit(
                    concept_id=concept_id,
                    display=concept["display"],
                    search_key=search_key,
                    source=concept.get("source", ""),
                )
            )
        return hits


def load_gazetteer(path: Path) -> GazetteerIndex:
    data = json.loads(path.read_text(encoding="utf-8"))
    concepts = data["concepts"]
    automaton = ahocorasick.Automaton()
    for concept_id, concept in concepts.items():
        for key in concept["search_keys"]:
            if key not in automaton:
                automaton.add_word(key, (concept_id, key))
    automaton.make_automaton()
    return GazetteerIndex(concepts=concepts, automaton=automaton)


def build_index_from_entries(
    entries: Iterable[dict],
    min_key_length: int = 6,
    stop_keys: Optional[Set[str]] = None,
) -> Tuple[Dict[str, dict], List[str]]:
    """
    entries: dicts with concept_id, display, search_keys_raw[], source, lang
    Returns concepts map and build warnings.
    """
    stop = stop_keys or set()
    concepts: Dict[str, dict] = {}
    key_owner: Dict[str, str] = {}
    warnings: List[str] = []

    for entry in entries:
        concept_id = entry["concept_id"]
        display = entry["display"]
        source = entry.get("source", "unknown")
        lang = entry.get("lang", "")

        if concept_id not in concepts:
            concepts[concept_id] = {
                "display": display,
                "source": source,
                "lang": lang,
                "search_keys": [],
            }
        elif concepts[concept_id]["display"] != display:
            # Prefer RU display when merging.
            if lang == "ru":
                concepts[concept_id]["display"] = display

        raw_keys = entry.get("search_keys_raw") or []
        if isinstance(raw_keys, str):
            raw_keys = [raw_keys]

        for raw in raw_keys:
            key = normalize(raw)
            if not is_valid_search_key(key, min_key_length):
                continue
            if key in stop:
                continue
            if key in key_owner and key_owner[key] != concept_id:
                warnings.append(
                    f"conflict: key '{key}' -> {key_owner[key]} and {concept_id}"
                )
                continue
            key_owner[key] = concept_id
            keys_list = concepts[concept_id]["search_keys"]
            if key not in keys_list:
                keys_list.append(key)

    # Longest keys first for overlapping matches (stored sorted per concept).
    for concept in concepts.values():
        concept["search_keys"].sort(key=len, reverse=True)

    return concepts, warnings
