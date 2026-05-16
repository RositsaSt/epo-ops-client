# EPO OPS Client

Utilities for downloading data from the EPO OPS API and extracting remarks from first-page patent PDFs.

## What is included

- OPS first-page downloader
- OPS abstract downloader code path
- OCR-based remarks extractor for patent PDFs

## Repository layout

- `src/epo_ops_client/downloaders/first_page/` - first-page downloader package
- `src/epo_ops_client/extractors/remarks/` - OCR extractor utilities
- `application/`, `infrastructure/`, `domain/`, `io/` - current modular downloader implementation
- `cli.py` - command-line entry point

## Requirements

- Python 3.12+
- EPO OPS credentials:
  - `EPO_OPS_KEY`
  - `EPO_OPS_SECRET`

For OCR extraction you also need system dependencies:
- Tesseract OCR
- Poppler

## Installation

```bash
pip install -r requirements.txt