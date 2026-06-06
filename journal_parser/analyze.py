from __future__ import annotations

import importlib.util
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from journal_parser.fragment_filters import load_fragments
from journal_parser.normalize import normalize
from journal_parser.rtf_report import write_rtf_report


_MORPH = None  # None=uninitialized, False=missing, else MorphAnalyzer


def _get_morph():
    global _MORPH
    if _MORPH is False:
        return None
    if _MORPH is not None:
        return _MORPH
    try:
        import pymorphy3  # type: ignore
    except ModuleNotFoundError:  # pragma: no cover
        _MORPH = False
        return None
    _MORPH = pymorphy3.MorphAnalyzer()
    return _MORPH


def _canonicalize_token(token: str) -> str:
    """
    Canonicalize token after matching:
    - for adjectives/participles -> nominative feminine singular (…ая/…яя) when possible
    - otherwise -> normal_form
    Falls back to the original token on parse/inflect failure.
    """
    t = (token or "").strip().lower().replace("ё", "е")
    if not t:
        return ""
    morph = _get_morph()
    if morph is None:
        return t
    parsed = morph.parse(t)
    if not parsed:
        return t
    p = parsed[0]
    pos = getattr(p.tag, "POS", None)
    if pos in {"ADJF", "ADJS", "PRTF", "PRTS"}:
        inf = p.inflect({"nomn", "femn", "sing"})
        if inf and inf.word:
            return inf.word.lower().replace("ё", "е")
        return t
    nf = getattr(p, "normal_form", None)
    if isinstance(nf, str) and nf:
        return nf.lower().replace("ё", "е")
    return t


def _merge_matches_by_canonical_form(matches: Dict[str, List[int]]) -> Dict[str, List[int]]:
    merged: Dict[str, set[int]] = {}
    for token, pages in matches.items():
        canon = _canonicalize_token(token) or token
        merged.setdefault(canon, set()).update(pages)
    return {k: sorted(v) for k, v in merged.items()}


def _get_fitz():
    try:
        import fitz  # type: ignore
    except ModuleNotFoundError as e:  # pragma: no cover
        raise SystemExit(
            "Missing dependency: pymupdf (import name: fitz). "
            "Install requirements.txt before running analyze."
        ) from e
    return fitz


def _load_ocr_plugin(path: Path):
    if not path.exists():
        raise SystemExit(f"OCR plugin not found: {path}")
    spec = importlib.util.spec_from_file_location("journal_parser_ocr_plugin", str(path))
    if spec is None or spec.loader is None:
        raise SystemExit(f"Cannot load OCR plugin: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    fn = getattr(mod, "extract_pages", None)
    if not callable(fn):
        raise SystemExit(
            f"OCR plugin must define callable extract_pages(pdf_path: Path) -> list[str]. Plugin: {path}"
        )
    return fn


def _normalize_page_text(text: str) -> str:
    if not text:
        return ""
    t = text.replace("\u00ad", "")
    t = re.sub(r"(?<=[А-Яа-яЁёA-Za-z])-\s*\n\s*(?=[А-Яа-яЁёA-Za-z])", "", t)
    t = t.replace("\n", " ")
    return t


CAND_RE = re.compile(r"[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё0-9\-\+\.\(\)\[\]]{3,}")
TOC_LINE_RE = re.compile(r"^\s*(.+?)\s+(\d{1,3})\s*$")
TOC_PAGE_ONLY_RE = re.compile(r"^\s*(\d{1,3})\s*$")
AUTHOR_LINE_RE = re.compile(r"^\s*(?:[А-ЯЁA-Z]\.[А-ЯЁA-Z]\.|[А-ЯЁA-Z][^a-zа-яё]+,).{0,}$")

_LAT_TO_CYR = str.maketrans(
    {"a": "а", "b": "в", "c": "с", "e": "е", "h": "н", "k": "к", "m": "м", "o": "о", "p": "р", "t": "т", "x": "х", "y": "у"}
)


def _clean_token(raw: str) -> str:
    t = (raw or "").strip().strip(" \t\r\n.,;:!?\"'`()[]{}")
    if not t:
        return ""
    t = t.lower().replace("ё", "е")
    if re.search(r"[а-я]", t) and re.search(r"[abcehkmoptxy]", t):
        t = t.translate(_LAT_TO_CYR)
    return t


def _text_quality_score(pages: List[str]) -> float:
    if not pages:
        return 0.0
    total = sum(len((p or "").strip()) for p in pages)
    return total / max(1, len(pages))


def extract_pages(
    pdf_path: Path,
    *,
    ocr_plugin_path: Path | None = None,
    ocr_force: bool = False,
    min_chars_per_page: int = 40,
) -> List[str]:
    fitz = _get_fitz()
    doc = fitz.open(pdf_path)
    pages: List[str] = []
    for i in range(doc.page_count):
        pages.append(doc[i].get_text("text") or "")
    doc.close()

    if ocr_plugin_path is None:
        return pages
    if not ocr_force and _text_quality_score(pages) >= min_chars_per_page:
        return pages

    extract = _load_ocr_plugin(ocr_plugin_path)
    ocr_pages = extract(pdf_path)
    if isinstance(ocr_pages, list) and ocr_pages:
        return [str(p or "") for p in ocr_pages]
    return pages


def extract_toc_entries(pages: List[str]) -> List[dict]:
    entries_by_page: Dict[int, str] = {}

    for page_text in pages[:15]:
        low = page_text.lower()
        is_toc_like = ("содержание" in low) or ("content" in low)
        bare_nums = [int(s.strip()) for s in page_text.splitlines() if re.fullmatch(r"\s*\d{1,3}\s*", s)]
        if len(bare_nums) >= 5:
            is_toc_like = True
        if not is_toc_like:
            continue

        title_buffer: List[str] = []
        for raw_line in page_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.lower() in {"clinical studies", "review", "clinical practice"}:
                break
            if line.lower() in {
                "содержание",
                "contents",
                "сontents",
                "клинические исследования",
                "обзор",
                "клиническая практика",
            }:
                title_buffer = []
                continue
            if AUTHOR_LINE_RE.match(line):
                continue

            m = TOC_LINE_RE.match(line)
            if m:
                title = m.group(1).strip(" .\t")
                page = int(m.group(2))
                if 1 <= page <= 300 and len(title) >= 3 and not re.fullmatch(r"[\d\W_]+", title):
                    prev = entries_by_page.get(page)
                    if prev is None or len(title) > len(prev):
                        entries_by_page[page] = title
                title_buffer = []
                continue

            mp = TOC_PAGE_ONLY_RE.match(line)
            if mp:
                page = int(mp.group(1))
                if not (1 <= page <= 300):
                    title_buffer = []
                    continue
                if title_buffer:
                    title = " ".join(title_buffer).strip(" .\t")
                    title = re.sub(r"\s+", " ", title)
                    if len(title) >= 3 and not re.fullmatch(r"[\d\W_]+", title):
                        prev = entries_by_page.get(page)
                        if prev is None or len(title) > len(prev):
                            entries_by_page[page] = title
                else:
                    entries_by_page.setdefault(page, f"статья (страница {page})")
                title_buffer = []
                continue

            if re.fullmatch(r"[\W_]+", line):
                continue
            title_buffer.append(line)
            if len(title_buffer) > 4:
                title_buffer = title_buffer[-2:]

    if not entries_by_page:
        return []
    clean_entries = {p: t for p, t in entries_by_page.items() if p >= 6} or entries_by_page
    entries: List[dict] = [{"title": clean_entries[p], "page": p} for p in sorted(clean_entries)]
    entries.sort(key=lambda x: x["page"])
    return entries


def build_article_breakdown(matches: Dict[str, List[int]], toc_entries: List[dict], pages_total: int) -> List[dict]:
    if not toc_entries:
        return []
    starts = sorted(set(int(item["page"]) for item in toc_entries if item.get("page")))
    if not starts:
        return []

    ranges: List[tuple[int, int]] = []
    for i, start in enumerate(starts):
        end = (starts[i + 1] - 1) if i + 1 < len(starts) else pages_total
        ranges.append((start, end))

    breakdown: List[dict] = []
    for start, end in ranges:
        article_substances: List[tuple[int, str]] = []
        for substance, pages in matches.items():
            in_range = sorted(p for p in pages if start <= p <= end)
            if in_range:
                article_substances.append((in_range[0], substance))
        if not article_substances:
            continue
        article_substances = sorted(article_substances, key=lambda x: (x[0], x[1].lower()))
        unique: list[str] = []
        seen: set[str] = set()
        for _, name in article_substances:
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(name)
        title = next((t["title"] for t in toc_entries if int(t["page"]) == start), f"статья {start}")
        breakdown.append({"start_page": start, "end_page": end, "title": title, "substances": unique})
    return breakdown


def _slugify(text: str) -> str:
    s = text.lower().replace("ё", "е").strip()
    s = re.sub(r"[^a-zа-я0-9]+", "-", s, flags=re.IGNORECASE)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "unknown"


def write_repo_report(
    *,
    out_dir: Path,
    doc_title: str,
    pages_total: int,
    matches: Dict[str, List[int]],
    toc_entries: List[dict] | None,
    article_breakdown: List[dict] | None,
    now: datetime | None = None,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows_rtf: list[tuple[int, str, str]] = []
    for i, name in enumerate(sorted(matches.keys(), key=str.lower), start=1):
        pages = ", ".join(str(p) for p in sorted(set(matches[name])))
        rows_rtf.append((i, name, pages))

    rtf_path = build_report_path(out_dir=out_dir, doc_title=doc_title, now=now)
    try:
        write_rtf_report(
            path=rtf_path,
            doc_title=doc_title,
            toc_entries=toc_entries or [],
            article_breakdown=article_breakdown or [],
            substances_rows=rows_rtf,
        )
    except PermissionError:
        # If the file is open/locked, write a sibling with a suffix.
        alt = rtf_path.with_name(rtf_path.stem + "__new" + rtf_path.suffix)
        write_rtf_report(
            path=alt,
            doc_title=doc_title,
            toc_entries=toc_entries or [],
            article_breakdown=article_breakdown or [],
            substances_rows=rows_rtf,
        )
        return alt
    return rtf_path


def build_report_path(*, out_dir: Path, doc_title: str, now: datetime | None = None) -> Path:
    out_dir = out_dir.resolve()
    n = now or datetime.now()
    return out_dir / f"{n.strftime('%Y-%m-%d')}__{_slugify(doc_title)[:80]}.rtf"


def analyze_pdf(
    pdf_path: Path,
    *,
    out_dir: Path,
    include_path: Path,
    exclude_path: Path,
    ocr_plugin_path: Path | None = None,
    ocr_force: bool = False,
    now: datetime | None = None,
) -> Path:
    include_fragments = load_fragments(include_path)
    exclude_fragments = load_fragments(exclude_path)
    if not include_fragments:
        raise SystemExit("include fragments file is empty (filters/include.txt).")

    pages = extract_pages(pdf_path, ocr_plugin_path=ocr_plugin_path, ocr_force=ocr_force)
    toc_entries = extract_toc_entries(pages)

    matches: Dict[str, List[int]] = {}
    for page_num, raw in enumerate(pages, start=1):
        prepared = _normalize_page_text(raw)
        seen_on_page: set[str] = set()
        for cand in set(CAND_RE.findall(prepared)):
            token = _clean_token(cand)
            if not token or token in seen_on_page:
                continue
            seen_on_page.add(token)
            token_key = normalize(token)
            if not (any(f in token for f in include_fragments) or any(f in token_key for f in include_fragments)):
                continue
            if any(f in token for f in exclude_fragments) or any(f in token_key for f in exclude_fragments):
                continue
            matches.setdefault(token, []).append(page_num)

    matches = _merge_matches_by_canonical_form(matches)

    article_breakdown = build_article_breakdown(matches, toc_entries, len(pages))
    return write_repo_report(
        out_dir=out_dir,
        doc_title=pdf_path.name,
        pages_total=len(pages),
        matches=matches,
        toc_entries=toc_entries,
        article_breakdown=article_breakdown,
        now=now,
    )

