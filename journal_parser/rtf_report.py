from __future__ import annotations

import re
from pathlib import Path


def _rtf_escape(text: str) -> str:
    # Basic RTF escaping for ASCII + UTF-16 escapes for others.
    out: list[str] = []
    for ch in text:
        code = ord(ch)
        if ch in {"\\", "{", "}"}:
            out.append("\\" + ch)
        elif 0x20 <= code <= 0x7E:
            out.append(ch)
        else:
            # RTF \uN? uses signed 16-bit values; for BMP this is fine.
            signed = code if code < 0x8000 else code - 0x10000
            out.append(rf"\u{signed}?")
    return "".join(out)


def _rtf_par(text: str) -> str:
    return _rtf_escape(text) + r"\par" + "\n"


def write_rtf_report(
    *,
    path: Path,
    doc_title: str,
    toc_entries: list[dict] | None,
    article_breakdown: list[dict] | None,
    substances_rows: list[tuple[int, str, str]],
) -> Path:
    """
    Write a simple RTF report that opens nicely in Windows 11 Notepad/WordPad.
    """
    lines: list[str] = []
    lines.append(r"{\rtf1\ansi\deff0")
    lines.append(r"{\fonttbl{\f0 Segoe UI;}}")
    lines.append(r"\fs28\b " + _rtf_escape(doc_title) + r"\b0\par")
    lines.append(r"\par")

    def heading(text: str) -> None:
        lines.append(r"\fs24\b " + _rtf_escape(text) + r"\b0\par")
        lines.append(r"\fs20 ")

    if toc_entries:
        heading("Оглавление (извлечено)")
        for item in toc_entries:
            page = item.get("page")
            title = str(item.get("title", "")).strip()
            if title:
                lines.append(_rtf_par(f"- {page}: {title}"))
        lines.append(r"\par")

    if article_breakdown:
        heading("Результаты анализа по статьям")
        for item in article_breakdown:
            start_page = item.get("start_page")
            substances = item.get("substances", []) or []
            if substances:
                lines.append(_rtf_par(f"- {start_page} – {', '.join(substances)}"))
        lines.append(r"\par")

    heading("Найденные действующие вещества")
    # Real RTF table (renders nicely in Word/WordPad; Notepad will show RTF markup)
    # Keep total width within a typical page text area (twips).
    # Make the "pages" column as narrow as practical; let it wrap.
    # Column widths in twips (approx): №(600), name(5200), pages(2500)
    total_w = 8400
    col1 = 600
    col2 = col1 + 5200
    col3 = min(total_w, col2 + 2500)

    def row(c1: str, c2: str, c3: str, *, header: bool = False) -> None:
        lines.append(rf"\trowd\trgaph108\trleft0\trwWidth{total_w}\trftsWidth3")
        lines.append(rf"\cellx{col1}\cellx{col2}\cellx{col3}")
        if header:
            lines.append(r"\b")
        for cell_text in (c1, c2, c3):
            lines.append(r"\intbl " + _rtf_escape(cell_text) + r"\cell")
        if header:
            lines.append(r"\b0")
        lines.append(r"\row")

    row("№", "Действующее вещество", "Страницы", header=True)
    for i, name, pages in substances_rows:
        safe_name = re.sub(r"\s+", " ", name).strip()
        safe_pages = re.sub(r"\s+", " ", pages).strip()
        row(str(i), safe_name, safe_pages, header=False)

    lines.append("}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path

