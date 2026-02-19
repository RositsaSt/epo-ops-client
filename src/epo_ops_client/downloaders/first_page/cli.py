from __future__ import annotations

import os
from dotenv import load_dotenv

from .auth import OPSAuthClient
from .config import OPSFirstPageDownloaderConfig
from .downloader import download_many
from .io_tasks import load_download_tasks_from_csv
from .logging_csv import ThreadSafeCsvDownloadLogger
from .rate_limiter import RateLimiter


def main() -> None:
    """
    Entry point for the OPS first-page PDF downloader.

    Workflow:
    1. Load environment variables (.env)
    2. Validate OPS credentials
    3. Initialize configuration and service objects
    4. Load download tasks from CSV
    5. Execute bulk download
    """
    
    load_dotenv()

    ops_key = os.getenv("EPO_OPS_KEY")
    ops_secret = os.getenv("EPO_OPS_SECRET")
    if not ops_key or not ops_secret:
        raise SystemExit("Missing EPO_OPS_KEY / EPO_OPS_SECRET in environment (.env).")

    downloader_config = OPSFirstPageDownloaderConfig()
    auth_client = OPSAuthClient(downloader_config.ops_api_base_url, ops_key, ops_secret, 
                                request_timeout_seconds=downloader_config.token_request_timeout_seconds)
    print(downloader_config.ops_api_base_url)
    rate_limiter = RateLimiter(downloader_config.max_requests_per_second)
    download_logger = ThreadSafeCsvDownloadLogger(downloader_config.log_file_path)
    download_tasks = load_download_tasks_from_csv("pub_number_kind.csv", default_country=downloader_config.default_country_code)
    
    download_many(download_tasks, downloader_config=downloader_config, auth_client=auth_client, 
                  rate_limiter=rate_limiter, download_logger=download_logger)

    print(
        f"Download complete.\n"
        f"Log file: {downloader_config.log_file_path}\n"
        f"Output directory: {downloader_config.output_dir}"
        )


if __name__ == "__main__":
    main()
