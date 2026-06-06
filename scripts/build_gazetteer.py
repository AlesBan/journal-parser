#!/usr/bin/env python3
"""
Build local gazetteer from open data sources + custom YAML.

Sources (automatic):
  - openFDA NDC API (EN brand/generic/ingredients, no API key)
  - data/custom/entries.yaml

Sources (manual path, optional):
  - RxNorm RXNCONSO.RRF (--rxnorm-rrf) — requires UTS download
  - PubChem CID-Synonym-filtered.gz (--pubchem-gz) — ~1 GB
  - Russian CSV (--ru-csv) — columns: display, name (or search_key)
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
import time
from pathlib import Path
from typing import Dict, Generator, Iterable, List, Optional, Set

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from journal_parser.gazetteer.index import build_index_from_entries
from journal_parser.normalize import normalize

OPENFDA_NDC_URL = "https://api.fda.gov/drug/ndc.json"
OPENFDA_DRUGSFDA_URL = "https://api.fda.gov/drug/drugsfda.json"

# RxNorm RRF columns (0-based) used in RXNCONSO.RRF
_RXN_RXCUI = 0
_RXN_STR = 14
_RXN_TTY = 12
_RXN_SAB = 11
_RXN_LAT = 1
_RXN_SUPPRESS = 16

_RXN_TTY_KEEP = {
    "IN",
    "PIN",
    "SCD",
    "SCDF",
    "SCDG",
    "SBDC",
    "BN",
    "BPCK",
    "GPCK",
    "SY",
}


def load_stopwords(path: Path) -> Set[str]:
    if not path.exists():
        return set()
    keys = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        keys.add(normalize(line))
    return keys


def load_custom_yaml(path: Path) -> List[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return list(data.get("entries") or [])


def load_ru_csv(path: Path) -> List[dict]:
    entries: List[dict] = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            display = (
                row.get("display")
                or row.get("name")
                or row.get("trade_name")
                or row.get("торговое")
                or row.get("Торговое наименование")
                or ""
            ).strip()
            if not display:
                continue
            extra = (
                row.get("search_key")
                or row.get("inn")
                or row.get("mnn")
                or row.get("МНН")
                or row.get("substance")
                or ""
            ).strip()
            keys = [display]
            if extra and extra != display:
                keys.append(extra)
            entries.append(
                {
                    "concept_id": f"ru_csv:{i}",
                    "display": display,
                    "lang": "ru",
                    "source": "ru_csv",
                    "search_keys_raw": keys,
                }
            )
    return entries


def _parse_link_next(headers: dict) -> Optional[str]:
    link = headers.get("Link") or headers.get("link")
    if not link:
        return None
    for part in link.split(","):
        if 'rel="next"' in part or "rel=next" in part:
            segment = part.split(";")[0].strip()
            if segment.startswith("<") and segment.endswith(">"):
                return segment[1:-1]
    return None


def _openfda_fetch(url: str, limit: int, max_records: Optional[int]) -> Generator[dict, None, None]:
    """
    Paginate openFDA using Link search_after (skip capped at 25k).
    """
    session = requests.Session()
    next_url: Optional[str] = None
    fetched = 0
    first = True

    while True:
        if first:
            resp = session.get(
                url,
                params={"limit": limit, "sort": "product_ndc:asc"},
                timeout=120,
            )
            first = False
        else:
            if not next_url:
                break
            resp = session.get(next_url, timeout=120)
        resp.raise_for_status()
        payload = resp.json()
        results = payload.get("results") or []
        if not results:
            break
        for row in results:
            yield row
            fetched += 1
            if max_records and fetched >= max_records:
                return
        next_url = _parse_link_next(resp.headers)
        if not next_url:
            break
        time.sleep(0.2)


def _names_from_ndc(row: dict) -> List[str]:
    names: List[str] = []
    for field in ("generic_name", "brand_name", "brand_name_base"):
        v = row.get(field)
        if v and isinstance(v, str):
            names.append(v.strip())
    for ing in row.get("active_ingredients") or []:
        n = ing.get("name")
        if n:
            names.append(str(n).strip())
    return names


def _concept_id_from_openfda(row: dict, fallback_name: str) -> str:
    openfda = row.get("openfda") or {}
    rxcui = openfda.get("rxcui")
    if rxcui:
        return f"rxcui:{rxcui[0]}"
    unii = openfda.get("unii")
    if unii:
        return f"unii:{unii[0]}"
    return f"openfda:{normalize(fallback_name)}"


def iter_openfda_ndc(max_records: Optional[int]) -> List[dict]:
    entries: List[dict] = []
    seen: Set[str] = set()

    for row in _openfda_fetch(OPENFDA_NDC_URL, limit=1000, max_records=max_records):
        names = _names_from_ndc(row)
        if not names:
            continue
        display = row.get("generic_name") or row.get("brand_name") or names[0]
        concept_id = _concept_id_from_openfda(row, display)
        if concept_id in seen:
            # merge keys into existing entry
            for e in entries:
                if e["concept_id"] == concept_id:
                    e["search_keys_raw"] = list(
                        dict.fromkeys(e["search_keys_raw"] + names)
                    )
                    break
            continue
        seen.add(concept_id)
        entries.append(
            {
                "concept_id": concept_id,
                "display": display,
                "lang": "en",
                "source": "openfda_ndc",
                "search_keys_raw": names,
            }
        )
    return entries


def iter_rxnorm_rrf(path: Path, max_rows: Optional[int]) -> List[dict]:
    entries: List[dict] = []
    by_rxcui: Dict[str, dict] = {}
    count = 0

    with path.open(encoding="utf-8") as f:
        for line in f:
            if max_rows and count >= max_rows:
                break
            parts = line.rstrip("\n").split("|")
            if len(parts) < 17:
                continue
            if parts[_RXN_LAT] != "ENG":
                continue
            if parts[_RXN_SUPPRESS] == "Y":
                continue
            if parts[_RXN_TTY] not in _RXN_TTY_KEEP:
                continue
            rxcui = parts[_RXN_RXCUI]
            name = parts[_RXN_STR].strip()
            if not name:
                continue
            count += 1
            if rxcui not in by_rxcui:
                by_rxcui[rxcui] = {
                    "concept_id": f"rxcui:{rxcui}",
                    "display": name,
                    "lang": "en",
                    "source": "rxnorm",
                    "search_keys_raw": [],
                }
            keys = by_rxcui[rxcui]["search_keys_raw"]
            if name not in keys:
                keys.append(name)

    entries.extend(by_rxcui.values())
    return entries


def iter_pubchem_gz(path: Path, max_rows: Optional[int]) -> List[dict]:
    """CID<TAB>Synonym per line. Very large — use max_rows for testing."""
    entries: List[dict] = []
    by_cid: Dict[str, dict] = {}
    count = 0

    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            if max_rows and count >= max_rows:
                break
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 2:
                continue
            cid, synonym = parts[0].strip(), parts[1].strip()
            if not synonym or len(synonym) > 120:
                continue
            count += 1
            key = f"pubchem:{cid}"
            if key not in by_cid:
                by_cid[key] = {
                    "concept_id": key,
                    "display": synonym,
                    "lang": "en",
                    "source": "pubchem",
                    "search_keys_raw": [],
                }
            keys = by_cid[key]["search_keys_raw"]
            if synonym not in keys:
                keys.append(synonym)
            if len(keys) > 40:
                continue

    entries.extend(by_cid.values())
    return entries


def write_gazetteer(
    concepts: dict,
    warnings: List[str],
    out_path: Path,
    meta: dict,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "meta": meta,
        "concepts": concepts,
        "warnings_count": len(warnings),
        "warnings_sample": warnings[:50],
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=0), encoding="utf-8")

    # Stats sidecar
    stats = {
        "concepts": len(concepts),
        "search_keys": sum(len(c["search_keys"]) for c in concepts.values()),
        "warnings": len(warnings),
        **meta,
    }
    stats_path = out_path.with_suffix(".stats.json")
    stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build journal-parser gazetteer.")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "built" / "gazetteer.json",
    )
    parser.add_argument(
        "--custom",
        type=Path,
        default=ROOT / "data" / "custom" / "entries.yaml",
    )
    parser.add_argument(
        "--stopwords",
        type=Path,
        default=ROOT / "data" / "custom" / "stopwords.txt",
    )
    parser.add_argument("--min-key-length", type=int, default=6)
    parser.add_argument(
        "--skip-openfda",
        action="store_true",
        help="Do not download openFDA (offline build).",
    )
    parser.add_argument(
        "--openfda-max",
        type=int,
        default=None,
        help="Limit openFDA NDC records (for quick test).",
    )
    parser.add_argument("--rxnorm-rrf", type=Path, help="Path to RXNCONSO.RRF")
    parser.add_argument("--rxnorm-max-rows", type=int, default=None)
    parser.add_argument("--pubchem-gz", type=Path, help="PubChem synonym gzip")
    parser.add_argument("--pubchem-max-rows", type=int, default=None)
    parser.add_argument("--ru-csv", type=Path, help="Russian names CSV export")
    args = parser.parse_args()

    all_entries: List[dict] = []
    sources_used: List[str] = []

    if args.custom.exists():
        all_entries.extend(load_custom_yaml(args.custom))
        sources_used.append("custom_yaml")

    if args.ru_csv:
        all_entries.extend(load_ru_csv(args.ru_csv))
        sources_used.append("ru_csv")

    if not args.skip_openfda:
        print("Fetching openFDA NDC names...", flush=True)
        all_entries.extend(iter_openfda_ndc(args.openfda_max))
        sources_used.append("openfda_ndc")

    if args.rxnorm_rrf:
        print(f"Parsing RxNorm {args.rxnorm_rrf}...", flush=True)
        all_entries.extend(iter_rxnorm_rrf(args.rxnorm_rrf, args.rxnorm_max_rows))
        sources_used.append("rxnorm")

    if args.pubchem_gz:
        print(f"Parsing PubChem {args.pubchem_gz}...", flush=True)
        all_entries.extend(iter_pubchem_gz(args.pubchem_gz, args.pubchem_max_rows))
        sources_used.append("pubchem")

    if not all_entries:
        print("No entries to build.", file=sys.stderr)
        return 1

    stop = load_stopwords(args.stopwords)
    concepts, warnings = build_index_from_entries(
        all_entries,
        min_key_length=args.min_key_length,
        stop_keys=stop,
    )

    meta = {
        "sources": sources_used,
        "entry_rows": len(all_entries),
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_gazetteer(concepts, warnings, args.output, meta)

    print(f"Built {args.output}")
    print(f"  concepts: {len(concepts)}")
    print(f"  search_keys: {sum(len(c['search_keys']) for c in concepts.values())}")
    print(f"  warnings: {len(warnings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
