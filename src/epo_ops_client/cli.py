from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

from .config import OPSConfig
from .domain.models import OPSIdentifierType, OPSDataType, PageSelection
from .infrastructure.auth import OPSAuthClient
from .infrastructure.rate_limiter import RateLimiter
from .io.logger import DownloadLogger
from .io.tasks import load_download_tasks_from_csv, load_pdf_tasks_from_csv
from .application.runner import run_data_downloads, run_pdf_downloads

# All --type values: the JSON data types plus "pdf" for image downloads
_JSON_DATA_TYPES = [t.value for t in OPSDataType]
_ALL_TYPES = _JSON_DATA_TYPES + ["pdf"]


def _parse_page_selection(value: str) -> PageSelection:
    """
    Parse --page-selection argument.
      first     → PageSelection.first_page()
      all       → PageSelection.all_pages()
      N-M       → PageSelection.page_range(N, M)  (e.g. "1-5")
    """
    if value == "first":
        return PageSelection.first_page()
    if value == "all":
        return PageSelection.all_pages()
    m = re.fullmatch(r"(\d+)-(\d+)", value)
    if m:
        return PageSelection.page_range(int(m.group(1)), int(m.group(2)))
    raise argparse.ArgumentTypeError(
        f"Invalid --page-selection {value!r}. "
        "Expected 'first', 'all', or a range like '1-5'."
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="epo-ops",
        description=(
            "Universal EPO OPS downloader.\n"
            "Downloads from any published-data endpoint "
            "(biblio, abstract, claims, PDF images, etc.)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--type",
        dest="data_type",
        required=True,
        choices=_ALL_TYPES,
        metavar="TYPE",
        help=(
            "Endpoint type to download. JSON types: "
            + ", ".join(_JSON_DATA_TYPES)
            + ". Use 'pdf' for full-image PDF downloads."
        ),
    )
    parser.add_argument(
        "--tasks-csv",
        type=Path,
        required=True,
        help=(
            "CSV file listing tasks. "
            "JSON types: must have a 'pub_id' column. "
            "PDF type: must have 'pub_number' and 'kind' columns; "
            "'country' is optional (default: EP)."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory where downloaded files are written.",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help=(
            "Path to the CSV download log (used for resume logic). "
            "Defaults to <output-dir>/download_log.csv."
        ),
    )
    parser.add_argument(
        "--id-type",
        dest="identifier_type",
        choices=[t.value for t in OPSIdentifierType],
        default=OPSIdentifierType.DOCDB.value,
        help="Identifier type for JSON downloads: docdb (default) or epodoc.",
    )
    parser.add_argument(
        "--page-selection",
        type=_parse_page_selection,
        default="first",
        metavar="SELECTION",
        help=(
            "Page selection for PDF downloads: "
            "'first' (default), 'all', or a range like '1-5'. "
            "Ignored for non-PDF types."
        ),
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help=(
            "Number of concurrent download threads. "
            "Defaults to 4 for JSON types and 2 for PDF."
        ),
    )
    parser.add_argument(
        "--requests-per-second",
        type=float,
        default=1.0,
        help="Maximum requests per second across all threads (default: 1.0).",
    )
    return parser


def main() -> None:
    load_dotenv()

    ops_key = os.getenv("EPO_OPS_KEY")
    ops_secret = os.getenv("EPO_OPS_SECRET")
    if not ops_key or not ops_secret:
        sys.exit("Missing EPO_OPS_KEY / EPO_OPS_SECRET in environment (.env).")

    parser = _build_parser()
    args = parser.parse_args()

    log_file = args.log_file or (args.output_dir / "download_log.csv")

    config = OPSConfig(
        output_dir=args.output_dir,
        log_file_path=log_file,
        max_requests_per_second=args.requests_per_second,
    )

    auth_client = OPSAuthClient(
        config.ops_api_base_url,
        ops_key,
        ops_secret,
        request_timeout_seconds=config.token_request_timeout_seconds,
    )
    rate_limiter = RateLimiter(config.max_requests_per_second)
    logger = DownloadLogger(log_file)

    if args.data_type == "pdf":
        max_workers = args.workers if args.workers is not None else 2
        tasks = load_pdf_tasks_from_csv(args.tasks_csv, args.page_selection)
        print(
            f"Loaded {len(tasks)} PDF task(s). "
            f"Page selection: {args.page_selection.kind}. "
            f"Workers: {max_workers}."
        )
        run_pdf_downloads(
            tasks,
            config=config,
            auth_client=auth_client,
            rate_limiter=rate_limiter,
            logger=logger,
            output_dir=args.output_dir,
            max_workers=max_workers,
        )
    else:
        max_workers = args.workers if args.workers is not None else 4
        data_type = OPSDataType(args.data_type)
        identifier_type = OPSIdentifierType(args.identifier_type)
        tasks = load_download_tasks_from_csv(
            args.tasks_csv,
            data_type=data_type,
            identifier_type=identifier_type,
        )
        print(
            f"Loaded {len(tasks)} task(s). "
            f"Type: {args.data_type}. "
            f"Workers: {max_workers}."
        )
        run_data_downloads(
            tasks,
            config=config,
            auth_client=auth_client,
            rate_limiter=rate_limiter,
            logger=logger,
            max_workers=max_workers,
        )

    print(
        f"\nDone. Log: {log_file}  Output: {args.output_dir}"
    )


if __name__ == "__main__":
    main()
