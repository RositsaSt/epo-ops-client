from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from .infrastructure.auth import OPSAuthClient
from .config import OPSConfig
from .application.bulk_downloader import fetch_and_store_abstracts
from .io.io_tasks import load_download_tasks_from_csv
from .io.logging_csv import DownloadLogger
from .infrastructure.rate_limiter import RateLimiter
from .domain.models import OPSIdentifierType, OPSDataType


def main() -> None:
    """
    Entry point for the OPS first-page PDF downloader.

    Workflow:
    1. Load environment variables (.env)
    2. Validate OPS credentials
    3. Initialize configuration and services (auth, rate limiter, logger)
    4. Load download tasks from CSV (publication ids)
    5. Download abstracts sequentially and log results
    """
    
    load_dotenv()

    ops_key = os.getenv("EPO_OPS_KEY")
    ops_secret = os.getenv("EPO_OPS_SECRET")
    if not ops_key or not ops_secret:
        raise SystemExit("Missing EPO_OPS_KEY / EPO_OPS_SECRET in environment (.env).")
    
    parser = argparse.ArgumentParser(description="Download patent descriptions from EPO OPS.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Output directory for downloaded json files.")
    parser.add_argument("--log-file", type=Path, required=True, help="Output directory for the log file.")
    parser.add_argument("--tasks-csv", type=Path, required=True, help="Directory containing the input csv file.")
    parser.add_argument("--id-type", type=str, choices=[t.value for t in OPSIdentifierType],
                        default=OPSIdentifierType.DOCDB.value, help="Identifier type for OPS requests: docdb or epodoc. The default value is docdb.")
    parser.add_argument("--data-type", type=str, choices=[t.value for t in OPSDataType],
                        required=True, help="Type of data to be downloaded: biblio, abstract, full-cycle, fulltext, description, claims or equivalents.")
    args = parser.parse_args()

    downloader_config = OPSConfig(output_dir=args.output_dir, log_file_path=args.log_file)
    
    auth_client = OPSAuthClient(downloader_config.ops_api_base_url, ops_key, ops_secret, 
                                request_timeout_seconds=downloader_config.token_request_timeout_seconds)
    
    rate_limiter = RateLimiter(downloader_config.max_requests_per_second)
    
    download_logger = DownloadLogger(downloader_config.log_file_path)
    
    download_tasks = load_download_tasks_from_csv(str(args.tasks_csv), identifier_type=OPSIdentifierType(args.id_type), data_type=OPSDataType(args.data_type))
    
    fetch_and_store_abstracts(download_tasks, downloader_config=downloader_config, auth_client=auth_client, 
                  rate_limiter=rate_limiter, download_logger=download_logger)

    print(
        f"Download complete.\n"
        f"Log file: {downloader_config.log_file_path}\n"
        f"Output directory: {downloader_config.output_dir}"
        )


if __name__ == "__main__":
    main()
