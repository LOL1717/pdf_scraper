#!/usr/bin/env python3
"""Extract structured scientific signals from parsed PDF JSON content."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

RESULT_KEYWORDS = {
    "result",
    "results",
    "comparison",
    "ablation",
    "performance",
    "experiment",
    "evaluation",
}

METRIC_KEYWORDS = {
    "accuracy",
    "f1",
    "precision",
    "recall",
    "auc",
    "ic50",
    "rmse",
    "mae",
    "bleu",
    "rouge",
    "mse",
}

METHOD_HINTS = ("model", "method", "approach", "framework", "algorithm")
BASELINE_HINTS = ("baseline", "compared with", "compared to", "state-of-the-art", "sota")
DATASET_HINTS = ("dataset", "data set", "corpus", "cohort")
OBJECTIVE_HINTS = ("objective", "aim", "goal", "we propose", "this study")
PROBLEM_HINTS = ("problem", "challenge", "limitation", "we address", "motivation")


def empty_structure() -> dict[str, Any]:
    return {
        "metadata": {"title": "", "authors": [], "year": "", "domain": ""},
        "context": {"problem": "", "objective": ""},
        "experiment": {"dataset": "", "method": "", "baselines": [], "metrics": []},
        "tables": [],
        "results": {"best_method": "", "key_values": []},
        "insights": [],
    }


def normalize_number(token: str) -> str:
    token = token.strip().replace(",", "")
    token = re.sub(r"(?<=\d)\s+(?=\d)", "", token)
    return token


def normalize_cell(cell: Any) -> str:
    text = "" if cell is None else str(cell)
    text = re.sub(r"\s+", " ", text).strip()

    percent_match = re.fullmatch(r"([-+]?\d+(?:\.\d+)?)\s*%", text)
    if percent_match:
        return f"{normalize_number(percent_match.group(1))}%"

    unit_match = re.fullmatch(r"([-+]?\d+(?:\.\d+)?)\s*(mg/ml|mg/mL|µg/ml|ug/ml|ng/ml)", text, re.I)
    if unit_match:
        value = normalize_number(unit_match.group(1))
        unit = unit_match.group(2).replace("mg/mL", "mg/ml")
        return f"{value} {unit.lower()}"

    if re.fullmatch(r"[-+]?\d[\d\s,]*(?:\.\d+)?", text):
        return normalize_number(text)

    return text


def flatten_text_blocks(text_field: Any) -> list[str]:
    blocks: list[str] = []

    if isinstance(text_field, str):
        blocks.append(text_field)
    elif isinstance(text_field, list):
        for item in text_field:
            if isinstance(item, str):
                blocks.append(item)
            elif isinstance(item, dict):
                for key in ("section", "heading", "title", "paragraph", "text", "content"):
                    value = item.get(key)
                    if isinstance(value, str):
                        blocks.append(value)
    elif isinstance(text_field, dict):
        for key in ("abstract", "introduction", "methods", "results", "discussion", "text"):
            value = text_field.get(key)
            if isinstance(value, str):
                blocks.append(value)
            elif isinstance(value, list):
                blocks.extend([v for v in value if isinstance(v, str)])

    return [b.strip() for b in blocks if b and b.strip()]


def infer_domain(full_text: str) -> str:
    text = full_text.lower()
    if any(k in text for k in ("antibody", "clinical", "patient", "biomedical", "drug", "ic50")):
        return "biomedical"
    if any(k in text for k in ("neural", "transformer", "accuracy", "benchmark", "dataset")):
        return "machine learning"
    if any(k in text for k in ("molecule", "reaction", "compound", "chemistry")):
        return "chemistry"
    return ""


def first_matching_line(lines: list[str], hints: tuple[str, ...]) -> str:
    for line in lines:
        low = line.lower()
        if any(h in low for h in hints):
            return line[:300]
    return ""


def extract_metrics(lines: list[str]) -> list[str]:
    found: list[str] = []
    text = " ".join(lines).lower()
    for metric in sorted(METRIC_KEYWORDS):
        if metric in text:
            found.append(metric)
    return found


def detect_table_caption(table_obj: dict[str, Any], idx: int) -> str:
    for key in ("caption", "title", "name"):
        value = table_obj.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return f"Table {idx + 1}"


def normalize_table(table_obj: Any, idx: int) -> dict[str, Any] | None:
    if not isinstance(table_obj, dict):
        return None

    rows = table_obj.get("rows")
    if not isinstance(rows, list) or not rows:
        return None

    cleaned_rows: list[list[str]] = []
    max_cols = 0

    for row in rows:
        if not isinstance(row, list):
            continue
        cleaned = [normalize_cell(c) for c in row]
        if any(cleaned):
            cleaned_rows.append(cleaned)
            max_cols = max(max_cols, len(cleaned))

    if not cleaned_rows:
        return None

    for row in cleaned_rows:
        if len(row) < max_cols:
            row.extend([""] * (max_cols - len(row)))

    headers = table_obj.get("columns")
    if not isinstance(headers, list) or not headers:
        headers = cleaned_rows[0]
        body = cleaned_rows[1:]
    else:
        headers = [normalize_cell(h) for h in headers]
        if len(headers) < max_cols:
            headers.extend([""] * (max_cols - len(headers)))
        body = cleaned_rows

    content_text = " ".join(headers + [c for r in body for c in r]).lower()
    numeric_cells = sum(1 for r in body for c in r if re.search(r"[-+]?\d", c))

    meaningful = any(k in content_text for k in RESULT_KEYWORDS.union(METRIC_KEYWORDS)) or numeric_cells >= 3
    if not meaningful:
        return None

    # Merge continuation rows with empty first cell into previous row
    merged: list[list[str]] = []
    for row in body:
        if merged and row and not row[0].strip() and any(cell.strip() for cell in row[1:]):
            for i, cell in enumerate(row):
                if cell.strip():
                    merged[-1][i] = (merged[-1][i] + " " + cell).strip()
        else:
            merged.append(row)

    return {
        "caption": detect_table_caption(table_obj, idx),
        "columns": headers,
        "rows": merged,
    }


def extract_best_result(tables: list[dict[str, Any]]) -> tuple[str, list[str]]:
    best_method = ""
    key_values: list[str] = []
    best_value = None

    for table in tables:
        cols = table.get("columns", [])
        rows = table.get("rows", [])
        metric_col_idx = None

        for i, col in enumerate(cols):
            low = col.lower()
            if any(m in low for m in METRIC_KEYWORDS) or "score" in low or "acc" in low:
                metric_col_idx = i
                break

        if metric_col_idx is None:
            continue

        for row in rows:
            if metric_col_idx >= len(row):
                continue
            value_text = row[metric_col_idx]
            match = re.search(r"[-+]?\d+(?:\.\d+)?", value_text)
            if not match:
                continue
            value = float(match.group(0))
            if best_value is None or value > best_value:
                best_value = value
                best_method = row[0] if row else ""
                key_values = [f"{cols[metric_col_idx]}: {value_text}"]

    return best_method, key_values


def extract_structured_data(parsed_json: dict[str, Any]) -> dict[str, Any]:
    result = empty_structure()

    metadata = parsed_json.get("metadata", {}) if isinstance(parsed_json, dict) else {}
    text_blocks = flatten_text_blocks(parsed_json.get("text", "")) if isinstance(parsed_json, dict) else []
    full_text = "\n".join(text_blocks)

    if isinstance(metadata, dict):
        title = metadata.get("title", "")
        authors = metadata.get("authors", [])
        year = metadata.get("year", "")

        result["metadata"]["title"] = title if isinstance(title, str) else ""
        result["metadata"]["authors"] = authors if isinstance(authors, list) else []
        result["metadata"]["year"] = str(year) if year else ""

    if not result["metadata"]["title"] and text_blocks:
        result["metadata"]["title"] = text_blocks[0][:200]

    result["metadata"]["domain"] = infer_domain(full_text)

    result["context"]["problem"] = first_matching_line(text_blocks, PROBLEM_HINTS)
    result["context"]["objective"] = first_matching_line(text_blocks, OBJECTIVE_HINTS)

    result["experiment"]["dataset"] = first_matching_line(text_blocks, DATASET_HINTS)
    result["experiment"]["method"] = first_matching_line(text_blocks, METHOD_HINTS)

    baseline_line = first_matching_line(text_blocks, BASELINE_HINTS)
    if baseline_line:
        result["experiment"]["baselines"] = [baseline_line]

    text_metrics = extract_metrics(text_blocks)

    raw_tables = parsed_json.get("tables", []) if isinstance(parsed_json, dict) else []
    if isinstance(raw_tables, list):
        normalized_tables = [normalize_table(t, i) for i, t in enumerate(raw_tables)]
        result["tables"] = [t for t in normalized_tables if t is not None]

    table_metric_text = " ".join(
        " ".join(t.get("columns", [])) for t in result["tables"] if isinstance(t, dict)
    )
    table_metrics = [m for m in sorted(METRIC_KEYWORDS) if m in table_metric_text.lower()]
    result["experiment"]["metrics"] = sorted(set(text_metrics + table_metrics))

    best_method, key_values = extract_best_result(result["tables"])
    result["results"]["best_method"] = best_method
    result["results"]["key_values"] = key_values

    insights: list[str] = []
    if best_method and key_values:
        insights.append(f"Best method identified: {best_method} ({key_values[0]}).")
    if result["experiment"]["dataset"]:
        insights.append("Dataset details were found in the parsed text.")
    if result["tables"]:
        insights.append(f"{len(result['tables'])} meaningful table(s) retained after filtering.")
    result["insights"] = insights[:3]

    if not any(
        [
            result["metadata"]["title"],
            result["context"]["problem"],
            result["experiment"]["dataset"],
            result["tables"],
            result["results"]["key_values"],
            result["insights"],
        ]
    ):
        return empty_structure()

    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract structured experimental data from parsed-paper JSON.")
    parser.add_argument("input_json", help="Path to parsed PDF JSON.")
    parser.add_argument("-o", "--output", default="structured_output.json", help="Output JSON path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input_json)
    output_path = Path(args.output)

    parsed = json.loads(input_path.read_text(encoding="utf-8"))
    structured = extract_structured_data(parsed)
    output_path.write_text(json.dumps(structured, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[DONE] Wrote structured output to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
