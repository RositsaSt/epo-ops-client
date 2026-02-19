from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import requests
from tqdm import tqdm

from .auth import OPSAuthClient
from .config import OPSFirstPageDownloaderConfig
from .logging_csv import DownloadLogEntry, ThreadSafeCsvDownloadLogger
from .models import DownloadTask
from .rate_limiter import RateLimiter


# HTTP status codes that should be retried with backoff.
RETRYABLE_HTTP_STATUS_CODES  = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class DownloadResult:
    """
    Result of attempting to download a single OPS first-page PDF.

    Attributes:
        download_task: The task describing which publication image to fetch.
        is_successful: True if the operation succeeded (including "skipped").
        download_status: One of: "downloaded", "skipped", "failed".
        http_status_code: HTTP status code received (0 if request never reached server).
        bytes_written_count: Number of bytes written to disk (0 on failure).
        status_message: Human-readable message explaining outcome.
        output_file_path: Destination path for the PDF (even if skipped/failed).
    """
    download_task: DownloadTask
    is_successful: bool
    download_status: str            # downloaded / skipped / failed
    http_status_code: int
    bytes_written: int
    status_message: str
    output_file_path: Path


def _chunk_download_tasks(download_tasks: list[DownloadTask], batch_size: int) -> Iterator[list[DownloadTask]]:
    """
    Yield successive batches of download tasks.

    Args:
        download_tasks: Full list of tasks to process.
        batch_size: Maximum number of tasks in each yielded batch.

    Yields:
        Lists of DownloadTask with length <= batch_size.
    """
    for index in range(0, len(download_tasks), batch_size):
        yield download_tasks[index:index + batch_size]


_thread_local_storage = threading.local()


def _get_thread_local_session() -> requests.Session:
    """
    Return a thread-local requests.Session.

    Using a session per thread enables HTTP connection reuse while keeping
    thread-safety predictable.
    """
    session = getattr(_thread_local_storage, "session", None)
    if session is None:
        session = requests.Session()
        _thread_local_storage.session = session
    return session


def _build_output_file_path(downloader_config: OPSFirstPageDownloaderConfig, download_task: DownloadTask) -> Path:
    """
    Build the destination file path for a downloaded first-page PDF.

    Filename format:
        {country}{pub_number}{kind}_page1.pdf

    Args:
        downloader_config: Downloader configuration (contains output directory).
        download_task: Task describing publication country/number/kind.

    Returns:
        Full path where the PDF should be written.
    """
    file_name = f"{download_task.country}{download_task.pub_number}{download_task.kind}_page1.pdf"
    return downloader_config.output_dir / file_name


def _is_valid_pdf_content(file_content: bytes) -> bool:
    """
    Best-effort validation that the response body looks like a PDF.
    """
    return file_content.startswith(b"%PDF")

def _compute_retry_sleep_seconds(
    *,
    attempt_number: int,
    retry_after_header_value: str | None,
    maximum_sleep_seconds: float = 60.0,
) -> float:
    """
    Compute how long to sleep before retrying a request.

    Preference order:
      1) If Retry-After header is present and numeric, use it (seconds).
      2) Otherwise use exponential backoff with jitter: 2^(attempt-1) + random(0,1).

    Args:
        attempt_number: 1-based attempt number.
        retry_after_header_value: Value of the Retry-After header (if any).
        maximum_sleep_seconds: Upper bound for the computed sleep.

    Returns:
        Sleep duration in seconds.
    """
    if retry_after_header_value and retry_after_header_value.isdigit():
        return float(int(retry_after_header_value))

    backoff_with_jitter = (2 ** (attempt_number - 1)) + random.random()
    return float(min(maximum_sleep_seconds, backoff_with_jitter))

def download_one(
    download_task: DownloadTask,
    *,
    downloader_config: OPSFirstPageDownloaderConfig,
    auth_client: OPSAuthClient,
    rate_limiter: RateLimiter,
) -> DownloadResult:
    """
    Download one first-page PDF for a single OPS image task.

    Behavior:
    - Ensures output directory exists.
    - Skips download if the output file exists and is larger than 1 KiB.
    - Applies global rate limiting before each HTTP attempt.
    - Retries on retryable HTTP codes (429/5xx) and network exceptions.
    - Refreshes OAuth token and retries on HTTP 401.

    Args:
        download_task: Publication task (country + number + kind).
        downloader_config: Runtime configuration (timeouts, retry attempts, output dir, etc.).
        auth_client: OPS OAuth client used to obtain/refresh Bearer token.
        rate_limiter: Global limiter shared across workers.

    Returns:
        DownloadResult describing outcome and output path.
    """
    downloader_config.output_dir.mkdir(parents=True, exist_ok=True)
    output_file_path = _build_output_file_path(downloader_config, download_task)

    # Skip if already downloaded and non-trivial size
    if output_file_path.exists() and output_file_path.stat().st_size > 1024:
        return DownloadResult(download_task, True, "skipped", 200, int(output_file_path.stat().st_size), "already exists", output_file_path)

    image_download_url = downloader_config.image_url_template().format(
        country=download_task.country, pub=download_task.pub_number, kind=download_task.kind
    )

    request_headers: dict[str, str] = {
        "Authorization": f"Bearer {auth_client.get_valid_token()}",
        "Accept": "application/pdf",
        "Range": downloader_config.ops_image_range_header_value,
    }

    last_status_message = ""
    http_status_code = 0
    session = _get_thread_local_session()

    for attempt_number in range(1, downloader_config.max_retry_attempts + 1):
        rate_limiter.wait_for_slot()
        
        try:
            response = session.get(image_download_url, headers=request_headers, timeout=downloader_config.http_request_timeout_seconds)
            http_status_code = response.status_code

            if http_status_code == 401:
                # Token expired/invalid — refresh and retry.
                request_headers["Authorization"] = f"Bearer {auth_client.force_refresh()}"
                last_status_message = "token refreshed"
                continue

            if http_status_code in RETRYABLE_HTTP_STATUS_CODES:
                retry_after_header = response.headers.get("Retry-After", "")
                sleep_duration_seconds = _compute_retry_sleep_seconds(
                    attempt_number=attempt_number,
                    retry_after_header_value=retry_after_header,
                )
                last_status_message = (
                    f"retryable HTTP {http_status_code}, sleeping {sleep_duration_seconds:.1f}s"
                )
                time.sleep(sleep_duration_seconds)
                continue

            if http_status_code != 200:
                response_snippet = ""
                try:
                    response_snippet = response.text[:200].replace("\n", " ")
                except Exception:
                    response_snippet = "non-text body"
                    
                return DownloadResult(download_task, False, "failed", http_status_code, 0, 
                                      f"HTTP {http_status_code}: {response_snippet}", output_file_path)

            pdf_content = response.content
            if not _is_valid_pdf_content(pdf_content):
                return DownloadResult(download_task, False, "failed", http_status_code, 0, 
                                      f"not a PDF; first bytes={pdf_content[:20]!r}", output_file_path)

            output_file_path.write_bytes(pdf_content)
            
            return DownloadResult(download_task, True, "downloaded", http_status_code, 
                                  len(pdf_content), last_status_message or "ok", output_file_path)

        except requests.RequestException as request_error:
            sleep_duration_seconds = _compute_retry_sleep_seconds(attempt_number=attempt_number, retry_after_header_value=None)
            last_status_message = f"request error: {request_error}; sleeping {sleep_duration_seconds:.1f}s"
            time.sleep(sleep_duration_seconds)

    return DownloadResult(download_task, False, "failed", http_status_code, 0, last_status_message or "exhausted retries", output_file_path)


def download_many(
    download_tasks: list[DownloadTask],
    *,
    downloader_config: OPSFirstPageDownloaderConfig,
    auth_client: OPSAuthClient,
    rate_limiter: RateLimiter,
    download_logger: ThreadSafeCsvDownloadLogger,
) -> None:
    """
    Download many OPS first-page PDFs using batching, a progress bar, and a thread pool.

    This function is responsible for orchestration:
    - Initializes the CSV log if needed.
    - Ensures output directory exists.
    - Splits tasks into batches to limit in-flight futures.
    - Runs each batch with ThreadPoolExecutor for concurrency.
    - Logs one CSV row per completed task.

    Args:
        download_tasks: List of tasks to download.
        downloader_config: Runtime configuration.
        auth_client: OPS OAuth client.
        rate_limiter: Global rate limiter shared across workers.
        download_logger: Thread-safe CSV logger (dependency-injected).
    """
    download_logger.init_if_missing()
    downloader_config.output_dir.mkdir(parents=True, exist_ok=True)

    total_task_count = len(download_tasks)
    progress_bar = tqdm(total=total_task_count, desc="Downloading front pages", unit="file")

    from concurrent.futures import ThreadPoolExecutor, as_completed

    for task_batch in _chunk_download_tasks(download_tasks, downloader_config.batch_size):
        with ThreadPoolExecutor(max_workers=downloader_config.max_workers) as ex:
            futures = [
                ex.submit(download_one, task, downloader_config=downloader_config, auth_client=auth_client, rate_limiter=rate_limiter)
                for task in task_batch
            ]
            for future in as_completed(futures):
                download_result: DownloadResult = future.result()

                download_logger.append_row(DownloadLogEntry(
                    timestamp=ThreadSafeCsvDownloadLogger.current_timestamp_string(),
                    country=download_result.download_task.country,
                    pub_number=download_result.download_task.pub_number,
                    kind=download_result.download_task.kind,
                    download_status=download_result.download_status,
                    http_status_code=download_result.http_status_code,
                    bytes_written=download_result.bytes_written,
                    status_message=download_result.status_message,
                    output_file_path=str(download_result.output_file_path),
                ))
                progress_bar.update(1)

    progress_bar.close()
