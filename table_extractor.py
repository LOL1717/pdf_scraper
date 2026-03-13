#!/usr/bin/env python3
"""Extract tables from PDF files and export them as CSV files."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Iterable, List, Sequence


def sanitize_cell(value: object) -> str:
    """Normalize table cell values for cleaner exports."""
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_table(raw_table: Sequence[Sequence[object]]) -> List[List[str]]:
    """Convert a raw table into a rectangular list of cleaned strings."""
    cleaned_rows: List[List[str]] = []
    max_cols = 0

    for raw_row in raw_table:
        cleaned_row = [sanitize_cell(cell) for cell in raw_row]
        max_cols = max(max_cols, len(cleaned_row))
        cleaned_rows.append(cleaned_row)

    for row in cleaned_rows:
        if len(row) < max_cols:
            row.extend([""] * (max_cols - len(row)))

    return cleaned_rows


def extract_tables_from_pdf(pdf_path: Path) -> Iterable[tuple[int, int, List[List[str]]]]:
    """Yield tuples of (page_number, table_number_on_page, cleaned_table)."""
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency: pdfplumber. Install it with `pip install -r requirements.txt`."
        ) from exc

    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()
            for table_index, table in enumerate(tables, start=1):
                if not table:
                    continue
                cleaned = clean_table(table)
                if any(any(cell for cell in row) for row in cleaned):
                    yield page_index, table_index, cleaned


def write_table_csv(table: Sequence[Sequence[str]], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerows(table)


def preview_table(table: Sequence[Sequence[str]], rows: int) -> None:
    """Print a compact preview of the first N rows of a table."""
    if rows <= 0:
        return

    preview_rows = table[:rows]
    print("  preview:")
    for row in preview_rows:
        print("    | " + " | ".join(cell or " " for cell in row) + " |")

    remaining = len(table) - len(preview_rows)
    if remaining > 0:
        print(f"    ... ({remaining} more row(s))")


def process_pdf(pdf_file: Path, output_dir: Path, preview_rows: int = 0) -> int:
    if not pdf_file.exists():
        print(f"[ERROR] File not found: {pdf_file}", file=sys.stderr)
        return 0

    written_tables = 0
    base_name = pdf_file.stem

    try:
        extracted_tables = extract_tables_from_pdf(pdf_file)
        for page_num, table_num, table in extracted_tables:
            output_name = f"{base_name}_page_{page_num:03d}_table_{table_num:02d}.csv"
            output_path = output_dir / output_name
            write_table_csv(table, output_path)
            written_tables += 1
            print(f"[OK] {pdf_file.name}: page {page_num}, table {table_num} -> {output_path}")
            preview_table(table, preview_rows)
    except RuntimeError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 0

    if written_tables == 0:
        print(f"[WARN] No tables detected in {pdf_file}")

    return written_tables


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract tables from PDF files and save each table as a CSV file."
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="One or more PDF files and/or directories containing PDFs.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default="extracted_tables",
        help="Directory where CSV files will be written (default: extracted_tables).",
    )
    parser.add_argument(
        "--preview-rows",
        type=int,
        default=0,
        help="Print first N rows of each extracted table in the terminal (default: 0).",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Recursively include PDFs from subdirectories when an input is a folder.",
    )
    return parser.parse_args(argv)


def gather_pdf_files(paths: Sequence[str], recursive: bool = False) -> List[Path]:
    pdf_files: List[Path] = []

    for input_path in paths:
        path = Path(input_path)
        if path.is_file() and path.suffix.lower() == ".pdf":
            pdf_files.append(path)
        elif path.is_dir():
            globber = path.rglob("*.pdf") if recursive else path.glob("*.pdf")
            pdf_files.extend(sorted(globber))
        else:
            print(f"[WARN] Skipping unsupported input: {path}", file=sys.stderr)

    unique_files = sorted(set(pdf_files))
    return unique_files


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    output_dir = Path(args.output_dir)

    if args.preview_rows < 0:
        print("[ERROR] --preview-rows must be >= 0", file=sys.stderr)
        return 1

    pdf_files = gather_pdf_files(args.inputs, recursive=args.recursive)
    if not pdf_files:
        print("[ERROR] No PDF files found in the provided inputs.", file=sys.stderr)
        return 1

    total_tables = 0
    for pdf_file in pdf_files:
        total_tables += process_pdf(pdf_file, output_dir, args.preview_rows)

    print(f"[DONE] Extracted {total_tables} tables from {len(pdf_files)} PDF file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
