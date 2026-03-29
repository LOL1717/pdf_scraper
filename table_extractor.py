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


def table_metrics(table: Sequence[Sequence[str]]) -> dict[str, float]:
    """Compute simple quality metrics used for noisy-table filtering."""
    row_count = len(table)
    col_count = max((len(row) for row in table), default=0)
    total_cells = row_count * col_count if row_count and col_count else 0
    non_empty_cells = sum(1 for row in table for cell in row if cell.strip())

    cell_lengths = [len(cell.strip()) for row in table for cell in row]
    largest_cell_len = max(cell_lengths, default=0)
    total_text_len = sum(cell_lengths)

    all_text = " ".join(cell for row in table for cell in row)
    alpha_chars = sum(1 for ch in all_text if ch.isalpha())
    non_space_chars = sum(1 for ch in all_text if not ch.isspace())

    alpha_ratio = (alpha_chars / non_space_chars) if non_space_chars else 0.0
    largest_cell_ratio = (largest_cell_len / total_text_len) if total_text_len else 0.0

    return {
        "row_count": float(row_count),
        "col_count": float(col_count),
        "non_empty_cells": float(non_empty_cells),
        "alpha_ratio": alpha_ratio,
        "largest_cell_ratio": largest_cell_ratio,
    }


def is_quality_table(table: Sequence[Sequence[str]], args: argparse.Namespace) -> tuple[bool, str]:
    """Decide whether the table looks usable or likely extraction noise."""
    metrics = table_metrics(table)

    if metrics["row_count"] < args.min_rows:
        return False, f"rows<{args.min_rows}"
    if metrics["col_count"] < args.min_cols:
        return False, f"cols<{args.min_cols}"
    if metrics["non_empty_cells"] < args.min_non_empty_cells:
        return False, f"non_empty<{args.min_non_empty_cells}"
    if metrics["alpha_ratio"] < args.min_alpha_ratio:
        return False, f"alpha_ratio<{args.min_alpha_ratio}"
    if metrics["largest_cell_ratio"] > args.max_single_cell_ratio:
        return False, f"largest_cell_ratio>{args.max_single_cell_ratio}"

    return True, "ok"


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


def process_pdf(pdf_file: Path, output_dir: Path, args: argparse.Namespace) -> int:
    if not pdf_file.exists():
        print(f"[ERROR] File not found: {pdf_file}", file=sys.stderr)
        return 0

    written_tables = 0
    skipped_tables = 0
    base_name = pdf_file.stem

    try:
        extracted_tables = extract_tables_from_pdf(pdf_file)
        for page_num, table_num, table in extracted_tables:
            is_valid, reason = is_quality_table(table, args)
            if not is_valid and not args.keep_filtered:
                skipped_tables += 1
                print(
                    f"[SKIP] {pdf_file.name}: page {page_num}, table {table_num} ({reason})",
                    file=sys.stderr,
                )
                continue

            output_name = f"{base_name}_page_{page_num:03d}_table_{table_num:02d}.csv"
            output_path = output_dir / output_name
            write_table_csv(table, output_path)
            written_tables += 1
            print(f"[OK] {pdf_file.name}: page {page_num}, table {table_num} -> {output_path}")
            preview_table(table, args.preview_rows)
    except RuntimeError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 0

    if written_tables == 0:
        print(f"[WARN] No tables detected in {pdf_file}")

    if skipped_tables > 0:
        print(f"[INFO] Filtered out {skipped_tables} noisy table(s) in {pdf_file.name}")

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
    parser.add_argument("--min-rows", type=int, default=2, help="Minimum rows per table.")
    parser.add_argument("--min-cols", type=int, default=2, help="Minimum columns per table.")
    parser.add_argument(
        "--min-non-empty-cells",
        type=int,
        default=4,
        help="Minimum number of non-empty cells required to keep a table.",
    )
    parser.add_argument(
        "--min-alpha-ratio",
        type=float,
        default=0.1,
        help="Minimum alphabetic-character ratio in extracted text.",
    )
    parser.add_argument(
        "--max-single-cell-ratio",
        type=float,
        default=0.9,
        help="Drop tables where one cell contains too much of the table text.",
    )
    parser.add_argument(
        "--keep-filtered",
        action="store_true",
        help="Keep tables even if quality filters mark them as noisy.",
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


def validate_args(args: argparse.Namespace) -> str | None:
    if args.preview_rows < 0:
        return "--preview-rows must be >= 0"
    if args.min_rows < 1:
        return "--min-rows must be >= 1"
    if args.min_cols < 1:
        return "--min-cols must be >= 1"
    if args.min_non_empty_cells < 1:
        return "--min-non-empty-cells must be >= 1"
    if not 0 <= args.min_alpha_ratio <= 1:
        return "--min-alpha-ratio must be between 0 and 1"
    if not 0 <= args.max_single_cell_ratio <= 1:
        return "--max-single-cell-ratio must be between 0 and 1"
    return None


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    output_dir = Path(args.output_dir)

    validation_error = validate_args(args)
    if validation_error:
        print(f"[ERROR] {validation_error}", file=sys.stderr)
        return 1

    pdf_files = gather_pdf_files(args.inputs, recursive=args.recursive)
    if not pdf_files:
        print("[ERROR] No PDF files found in the provided inputs.", file=sys.stderr)
        return 1

    total_tables = 0
    for pdf_file in pdf_files:
        total_tables += process_pdf(pdf_file, output_dir, args)

    print(f"[DONE] Extracted {total_tables} tables from {len(pdf_files)} PDF file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
