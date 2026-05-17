# EPO OPS Client

Universal downloader for the [EPO Open Patent Services (OPS)](https://www.epo.org/en/searching-for-patents/data/web-services/ops) published-data API, plus an OCR-based remarks extractor for patent PDFs.

## Features

- Download any published-data endpoint: `biblio`, `abstract`, `claims`, `description`, `fulltext`, `full-cycle`, `equivalents`, `images`
- Download full-image PDFs with flexible page selection: first page, all pages, or a custom range
- Concurrent downloads with a configurable thread pool
- Thread-safe rate limiter with automatic 429-backoff
- Resume support via a CSV download log (already-downloaded files are skipped)
- OCR-based remarks extractor for patent first-page PDFs (optional)

## Repository layout

```
src/epo_ops_client/
├── application/          # Orchestration: data_downloader, pdf_downloader, runner
├── domain/               # Value objects: DownloadTask, PDFDownloadTask, PageSelection
├── infrastructure/       # Auth, HTTP client, rate limiter, response handler, retry policy
├── io/                   # CSV task loaders, download logger
├── extractors/remarks/   # OCR-based remarks extractor (requires optional OCR deps)
├── cli.py                # epo-ops command-line entry point
└── config.py             # OPSConfig dataclass
```

## Requirements

- Python 3.12+
- EPO OPS credentials (free registration at <https://developers.epo.org/>):
  - `EPO_OPS_KEY`
  - `EPO_OPS_SECRET`

For OCR extraction you also need system packages:
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)
- [Poppler](https://poppler.freedesktop.org/) (`pdfinfo` / `pdftoppm`)

## Installation

```bash
# Core dependencies only
pip install .

# With OCR extractor support
pip install ".[ocr]"

# Development (adds pytest)
pip install ".[dev]"
```

Or install directly from `requirements.txt` (includes OCR deps):

```bash
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in your working directory (or export the variables):

```
EPO_OPS_KEY=your_key_here
EPO_OPS_SECRET=your_secret_here
```

## CLI usage

The package installs an `epo-ops` command.

### Download JSON data (biblio, abstract, claims, …)

Prepare a CSV file with a `pub_id` column:

```
pub_id
EP.1000000.A1.DOCDB
EP.2000000.B1.DOCDB
```

```bash
epo-ops \
  --type biblio \
  --tasks-csv patents.csv \
  --output-dir ./output \
  --id-type docdb \
  --workers 4 \
  --requests-per-second 1.0
```

### Download PDF images

Prepare a CSV file with `pub_number` and `kind` columns (`country` is optional, defaults to `EP`):

```
pub_number,kind,country
1000000,A1,EP
2000000,B1,EP
```

```bash
# First page only (default)
epo-ops --type pdf --tasks-csv patents.csv --output-dir ./pdfs --page-selection first

# All pages (merged into a single PDF per publication)
epo-ops --type pdf --tasks-csv patents.csv --output-dir ./pdfs --page-selection all

# Pages 1 to 5
epo-ops --type pdf --tasks-csv patents.csv --output-dir ./pdfs --page-selection 1-5
```

### All CLI options

| Option | Default | Description |
|---|---|---|
| `--type TYPE` | (required) | `biblio`, `abstract`, `claims`, `description`, `fulltext`, `full-cycle`, `equivalents`, `images`, or `pdf` |
| `--tasks-csv PATH` | (required) | CSV file of tasks |
| `--output-dir PATH` | (required) | Directory for downloaded files |
| `--log-file PATH` | `<output-dir>/download_log.csv` | Resume log path |
| `--id-type` | `docdb` | `docdb` or `epodoc` (JSON types only) |
| `--page-selection` | `first` | `first`, `all`, or `N-M` range (PDF type only) |
| `--workers N` | 4 (JSON) / 2 (PDF) | Concurrent download threads |
| `--requests-per-second N` | `1.0` | Global rate limit across all threads |

## Resume behaviour

A CSV log is written to `--log-file` (default `<output-dir>/download_log.csv`). On subsequent runs, any publication already logged as `downloaded` or `skipped` is not re-requested.

## Running tests

```bash
pytest
```
