from __future__ import annotations

import argparse
from pathlib import Path

from journal_parser.analyze import analyze_pdf


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="journal-parser CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_an = sub.add_parser("analyze", help="Analyze PDF and write .rtf report")
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
        help="Output directory for .rtf reports",
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


def cmd_analyze(args: argparse.Namespace) -> int:
    pdf = Path(args.pdf).resolve()
    include_path = Path(args.include).resolve()
    exclude_path = Path(args.exclude).resolve()
    out_dir = Path(args.out_dir).resolve()
    ocr_plugin = Path(args.ocr_plugin).resolve() if getattr(args, "ocr_plugin", None) else None
    report = analyze_pdf(
        pdf,
        out_dir=out_dir,
        include_path=include_path,
        exclude_path=exclude_path,
        ocr_plugin_path=ocr_plugin,
        ocr_force=bool(getattr(args, "ocr_force", False)),
    )
    print(f"Report written: {report}")
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
