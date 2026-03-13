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

You will see logs like:

```text
[OK] paper.pdf: page 3, table 1 -> extracted_tables/paper_page_003_table_01.csv
[DONE] Extracted 1 tables from 1 PDF file(s).
```

### 2) Extract from a folder of PDFs

```bash
python table_extractor.py path/to/pdf_folder
```

### 3) Include PDFs from nested subfolders

```bash
python table_extractor.py path/to/pdf_folder --recursive
```

### 4) Print table preview directly in terminal

```bash
python table_extractor.py path/to/paper.pdf --preview-rows 5
```

This prints first 5 rows of each detected table so you can quickly verify extraction without opening CSV files.

### 5) Choose custom output directory

```bash
python table_extractor.py path/to/pdf_folder -o output_tables
```

## How to see extracted tables

Open generated CSV files in:

- Excel / Google Sheets / LibreOffice
- or terminal:

```bash
head -n 20 extracted_tables/paper_page_003_table_01.csv
```

## Output format

Each detected table is saved as one CSV file:

- `{pdf_name}_page_001_table_01.csv`
- `{pdf_name}_page_001_table_02.csv`
- ...

All files are written under `extracted_tables/` by default.
