# PDF Table Extractor

This repository includes a Python script to extract tables from research PDFs and save each table as a CSV file.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run and see output

### 1) Extract tables from one PDF

```bash
python table_extractor.py path/to/paper.pdf
```

### 2) Extract from a folder of PDFs (including subfolders)

```bash
python table_extractor.py path/to/pdf_folder --recursive
```

### 3) Print table preview directly in terminal

```bash
python table_extractor.py path/to/paper.pdf --preview-rows 5
```

### 4) Filter noisy detections (recommended for research papers)

Some PDFs contain figures/charts that `pdfplumber` may incorrectly detect as tables. Use quality filters to reduce noisy CSV output:

**Bash / Git Bash:**

```bash
python table_extractor.py papers --recursive --preview-rows 2 \
  --min-rows 2 --min-cols 2 --min-non-empty-cells 6 \
  --min-alpha-ratio 0.15 --max-single-cell-ratio 0.85 \
  -o extracted_tables
```

**PowerShell (Windows):**

```powershell
python table_extractor.py papers --recursive --preview-rows 2 `
  --min-rows 2 --min-cols 2 --min-non-empty-cells 6 `
  --min-alpha-ratio 0.15 --max-single-cell-ratio 0.85 `
  -o extracted_tables
```

If you get `unrecognized arguments`, first verify you are running the updated script:

```bash
python table_extractor.py --help
```

You should see these flags in help output:
`--min-rows`, `--min-cols`, `--min-non-empty-cells`, `--min-alpha-ratio`, `--max-single-cell-ratio`.

If you want to keep every detected table anyway, add:

```bash
--keep-filtered
```
## How to verify output quickly

Count output files:

```bash
find extracted_tables -type f -name "*.csv" | wc -l
```

Open sample output in terminal:

```bash
head -n 20 extracted_tables/paper_page_003_table_01.csv
```

## Output format

Each detected table is saved as one CSV file:

- `{pdf_name}_page_001_table_01.csv`
- `{pdf_name}_page_001_table_02.csv`
- ...

All files are written under `extracted_tables/` by default.

## Structured scientific extraction from parsed JSON

If you already have parsed PDF JSON (`text`, `tables`, `images`, `metadata`), run:

```bash
python structured_extractor.py parsed_paper.json -o structured_output.json
```

Output schema:

- `metadata`: title/authors/year/domain
- `context`: problem/objective
- `experiment`: dataset/method/baselines/metrics
- `tables`: meaningful experimental/result tables only
- `results`: best method + key values
- `insights`: short findings
