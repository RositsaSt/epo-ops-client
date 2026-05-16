from __future__ import annotations

import requests
from tqdm import tqdm

from .downloader import DataDownloader
from ..infrastructure.auth import OPSAuthClient
from ..config import OPSConfig
from ..infrastructure.http_client import OPSClient
from ..infrastructure.json_store import JsonResponseStore
from ..io.logging_csv import DownloadLogEntry, DownloadLogger
from ..domain.models import DownloadTask
from ..infrastructure.response_handler import ResponseHandler
from ..infrastructure.rate_limiter import RateLimiter
from ..infrastructure.retry_policy import RetryPolicy

def fetch_and_store_abstracts(
    download_tasks: list[DownloadTask],
    *,
    downloader_config: OPSConfig,
    auth_client: OPSAuthClient,
    rate_limiter: RateLimiter,
    download_logger: DownloadLogger,
) -> None:
    """
    Download many abstracts sequentially and append a CSV log entry per task.
    """
    download_logger.init_if_missing()
    downloader_config.output_dir.mkdir(parents=True, exist_ok=True)

    http_client = OPSClient(downloader_config, auth_client)
    json_store = JsonResponseStore(downloader_config.output_dir)
    response_handler = ResponseHandler(json_store=json_store)
    retry_policy = RetryPolicy(max_attempts=downloader_config.max_retry_attempts)

    downloader_service = DataDownloader(
        config=downloader_config,
        http_client=http_client,
        json_store=json_store,
        response_handler=response_handler,
        retry_policy=retry_policy,
        rate_limiter=rate_limiter,
    )

    session = requests.Session()
    progress_bar = tqdm(total=len(download_tasks), desc="Downloading", unit="file")

    for task in download_tasks:
        result = downloader_service.fetch_and_store_abstract(task, session=session)

        download_logger.append_row(
            DownloadLogEntry(
                timestamp=DownloadLogger.current_timestamp_string(),
                pub_id=result.download_task.pub_id,
                download_status=result.download_status,
                http_status_code=result.http_status_code,
                status_message=result.status_message,
                output_file_path=str(result.output_file_path),
            )
        )
        progress_bar.update(1)

    progress_bar.close()