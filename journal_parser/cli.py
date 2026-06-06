from __future__ import annotations

import argparse
import importlib.util
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from journal_parser.normalize import normalize
from journal_parser.fragment_filters import load_fragments


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
    """
    Load external OCR/image-to-word plugin from a python file path.
    The plugin must expose: extract_pages(pdf_path: Path) -> list[str]
    """
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
            f"OCR plugin must define callable extract_pages(pdf_path: Path) -> list[str]. "
            f"Plugin: {path}"
        )
    return fn


def _normalize_page_text(text: str) -> str:
    """
    Minimal normalization for substring matching:
    - remove soft hyphen
    - merge переносы вида "сло-\\nво" -> "слово"
    - replace remaining newlines with spaces
    """
    if not text:
        return ""
    t = text.replace("\u00ad", "")
    t = re.sub(r"(?<=[А-Яа-яЁёA-Za-z])-\s*\n\s*(?=[А-Яа-яЁёA-Za-z])", "", t)
    t = t.replace("\n", " ")
    return t

# Candidate token pattern (keeps hyphenated and formula-ish words)
CAND_RE = re.compile(r"[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё0-9\-\+\.\(\)\[\]]{3,}")
TOC_LINE_RE = re.compile(r"^\s*(.+?)\s+(\d{1,3})\s*$")
TOC_PAGE_ONLY_RE = re.compile(r"^\s*(\d{1,3})\s*$")
AUTHOR_LINE_RE = re.compile(
    r"^\s*(?:[А-ЯЁA-Z]\.[А-ЯЁA-Z]\.|[А-ЯЁA-Z][^a-zа-яё]+,).{0,}$"
)

def _text_quality_score(pages: List[str]) -> float:
    """
    Heuristic: returns ratio of non-whitespace chars to pages.
    Used only to decide whether to trigger OCR fallback.
    """
    if not pages:
        return 0.0
    total = sum(len((p or "").strip()) for p in pages)
    return total / max(1, len(pages))


def _extract_pages(
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

    score = _text_quality_score(pages)
    if not ocr_force and score >= min_chars_per_page:
        return pages

    extract_pages = _load_ocr_plugin(ocr_plugin_path)
    ocr_pages = extract_pages(pdf_path)
    if isinstance(ocr_pages, list) and ocr_pages:
        return [str(p or "") for p in ocr_pages]
    return pages


def _extract_toc_entries(pages: List[str]) -> List[dict]:
    """
    Try to parse TOC from early pages. We look for lines ending with page numbers.
    """
    entries_by_page: Dict[int, str] = {}

    for page_text in pages[:15]:
        low = page_text.lower()
        is_toc_like = ("содержание" in low) or ("content" in low)
        # Fallback signal: a page with many bare numeric lines is likely TOC.
        bare_nums = [
            int(s.strip()) for s in page_text.splitlines() if re.fullmatch(r"\s*\d{1,3}\s*", s)
        ]
        if len(bare_nums) >= 5:
            is_toc_like = True

        if not is_toc_like:
            continue

        title_buffer: List[str] = []
        for raw_line in page_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            # Stop parsing bilingual duplicate block for current TOC page.
            if line.lower() in {"clinical studies", "review", "clinical practice"}:
                break

            # Skip known non-title lines in TOC area.
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

            # Author lines are not article titles.
            if AUTHOR_LINE_RE.match(line):
                continue

            # Case 1: "Title ... 34" on same line.
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

            # Case 2: page number on separate line after accumulated title lines.
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
                    # Numeric anchor without title - keep placeholder.
                    entries_by_page.setdefault(page, f"статья (страница {page})")
                title_buffer = []
                continue

            # Otherwise collect as part of multi-line title.
            # Skip pure punctuation/noise lines.
            if re.fullmatch(r"[\W_]+", line):
                continue
            title_buffer.append(line)
            # avoid runaway buffers
            if len(title_buffer) > 4:
                title_buffer = title_buffer[-2:]

    if not entries_by_page:
        return []

    # Keep only plausible article start pages (discard front matter pages).
    clean_entries = {p: t for p, t in entries_by_page.items() if p >= 6}
    if not clean_entries:
        clean_entries = entries_by_page

    entries: List[dict] = [{"title": clean_entries[p], "page": p} for p in sorted(clean_entries)]
    entries.sort(key=lambda x: x["page"])
    return entries


def _build_article_breakdown(
    matches: Dict[str, List[int]],
    toc_entries: List[dict],
    pages_total: int,
) -> List[dict]:
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
        if article_substances:
            # Keep article order by first occurrence, then name.
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
            breakdown.append(
                {
                    "start_page": start,
                    "end_page": end,
                    "title": title,
                    "substances": unique,
                }
            )
    return breakdown


def cmd_analyze(args: argparse.Namespace) -> int:
    pdf = Path(args.pdf).resolve()

    include_fragments = load_fragments(Path(args.include).resolve())
    exclude_fragments = load_fragments(Path(args.exclude).resolve())
    if not include_fragments:
        raise SystemExit("include fragments file is empty (filters/include.txt).")

    ocr_plugin = Path(args.ocr_plugin).resolve() if getattr(args, "ocr_plugin", None) else None
    pages = _extract_pages(pdf, ocr_plugin_path=ocr_plugin, ocr_force=bool(getattr(args, "ocr_force", False)))
    toc_entries = _extract_toc_entries(pages)

    matches: Dict[str, List[int]] = {}

    for page_num, raw in enumerate(pages, start=1):
        prepared = _normalize_page_text(raw)
        seen_on_page: set[str] = set()
        for cand in set(CAND_RE.findall(prepared)):
            token = cand.strip().lower().replace("ё", "е")
            if not token or token in seen_on_page:
                continue
            seen_on_page.add(token)
            token_key = normalize(token)
            # include → exclude
            if not (any(f in token for f in include_fragments) or any(f in token_key for f in include_fragments)):
                continue
            if any(f in token for f in exclude_fragments) or any(f in token_key for f in exclude_fragments):
                # explicitly excluded
                continue
            matches.setdefault(token, []).append(page_num)

    article_breakdown = _build_article_breakdown(matches, toc_entries, len(pages))
    report = _write_repo_report(
        out_dir=Path(args.out_dir).resolve(),
        doc_title=pdf.name,
        pages_total=len(pages),
        matches=matches,
        toc_entries=toc_entries,
        article_breakdown=article_breakdown,
    )
    print(f"Report written: {report}")
    print(f"Matched substances: {len(matches)}")
    return 0


def _slugify(text: str) -> str:
    s = text.lower().replace("ё", "е").strip()
    s = re.sub(r"[^a-zа-я0-9]+", "-", s, flags=re.IGNORECASE)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "unknown"


def _write_repo_report(
    out_dir: Path,
    doc_title: str,
    pages_total: int,
    matches: Dict[str, List[int]],
    toc_entries: List[dict] | None = None,
    article_breakdown: List[dict] | None = None,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    path = out_dir / f"{now.strftime('%Y-%m-%d')}__{_slugify(doc_title)[:80]}.md"
    lines: list[str] = [
        "",
        f"# {doc_title}",
        "",
    ]
    if toc_entries:
        lines += ["## Оглавление (извлечено)", ""]
        for item in toc_entries:
            page = item.get("page")
            title = str(item.get("title", "")).strip()
            if title:
                lines.append(f"- {page}: {title}")
    if article_breakdown:
        lines += ["", "## Результаты анализа по статьям", ""]
        for item in article_breakdown:
            start_page = item.get("start_page")
            substances = item.get("substances", []) or []
            if not substances:
                continue
            lines.append(f"- {start_page} – {', '.join(substances)}")
    lines += [
        "",
        "## Найденные действующие вещества",
        "",
        "| № | Действующее вещество | Страницы |",
        "|---|---|---|",
    ]

    for i, name in enumerate(sorted(matches.keys(), key=str.lower), start=1):
        pages = ", ".join(str(p) for p in sorted(set(matches[name])))
        lines.append(f"| {i} | {name} | {pages} |")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="journal-parser CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_an = sub.add_parser("analyze", help="Analyze PDF and write markdown report")
    p_an.add_argument("pdf", help="Path to PDF file")
    p_an.add_argument(
        "--include",
        default=str(Path("filters") / "include.txt"),
        help="Path to include fragments file",
    )
    p_an.add_argument(
        "--exclude",
        default=str(Path("filters") / "exclude.txt"),
        help="Path to exclude fragments file",
    )
    p_an.add_argument(
        "--out-dir",
        default=str(Path("reports")),
        help="Output directory for markdown reports",
    )
    p_an.add_argument(
        "--ocr-plugin",
        default="",
        help="Optional path to python OCR plugin file (must export extract_pages(pdf_path: Path) -> list[str])",
    )
    p_an.add_argument(
        "--ocr-force",
        action="store_true",
        help="Force OCR plugin usage (otherwise used only if text extraction is poor)",
    )
    p_an.set_defaults(func=cmd_analyze)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
