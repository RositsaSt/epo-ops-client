from __future__ import annotations

import itertools
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from tqdm import tqdm

from ..config import OPSConfig
from ..domain.models import DownloadTask, PDFDownloadTask, DownloadResult
from ..infrastructure.auth import OPSAuthClient
from ..infrastructure.http_client import OPSClient
from ..infrastructure.json_store import JsonResponseStore
from ..infrastructure.rate_limiter import RateLimiter
from ..infrastructure.response_handler import ResponseHandler
from ..infrastructure.retry_policy import RetryPolicy
from ..io.logger import DownloadLogger, DownloadLogEntry
from .data_downloader import DataDownloader
from .pdf_downloader import PDFPageDownloader


# One requests.Session per thread (sessions are not thread-safe).
_thread_local = threading.local()


def _get_session() -> requests.Session:
    if not hasattr(_thread_local, "session"):
        _thread_local.session = requests.Session()
    return _thread_local.session


def _chunk(iterable: list, size: int):
    """Yield successive chunks of `size` from `iterable`."""
    it = iter(iterable)
    while True:
        batch = list(itertools.islice(it, size))
        if not batch:
            break
        yield batch


def _log_result(result: DownloadResult, logger: DownloadLogger) -> None:
    logger.append_row(DownloadLogEntry(
        timestamp=DownloadLogger.current_timestamp_string(),
        pub_id=result.pub_id,
        download_status=result.download_status,
        http_status_code=result.http_status_code,
        status_message=result.status_message,
        output_file_path=str(result.output_file_path),
    ))


def run_data_downloads(
    tasks: list[DownloadTask],
    *,
    config: OPSConfig,
    auth_client: OPSAuthClient,
    rate_limiter: RateLimiter,
    logger: DownloadLogger,
    max_workers: int = 4,
    batch_size: int = 100,
) -> None:
    """
    Download JSON endpoint tasks concurrently using a ThreadPoolExecutor.

    Supports all OPSDataType values (biblio, abstract, claims, etc.) — the
    data type is baked into each DownloadTask.

    Resume
    ------
    Reads the logger CSV at startup and skips tasks whose expected output path
    is already marked as "downloaded". The DataDownloader also checks file
    existence as a secondary guard.

    Backoff
    -------
    On 429, the receiving thread calls rate_limiter.apply_penalty() so ALL
    threads pause before their next request, preventing the pool from
    hammering a throttled API.

    Parameters
    ----------
    tasks:
        All tasks to download (already filtered to the desired data type).
    config:
        Shared OPSConfig (immutable).
    auth_client:
        Shared thread-safe OPSAuthClient.
    rate_limiter:
        Shared thread-safe RateLimiter (with apply_penalty support).
    logger:
        Shared thread-safe DownloadLogger.
    max_workers:
        Number of concurrent download threads.
    batch_size:
        Max futures in-flight at once (limits peak memory).
    """
    logger.init_if_missing()
    config.output_dir.mkdir(parents=True, exist_ok=True)

    completed_paths = logger.load_completed_output_paths()
    json_store = JsonResponseStore(config.output_dir)
    pending = [
        t for t in tasks
        if str(json_store.output_path_for(t)) not in completed_paths
    ]

    if not pending:
        return

    response_handler = ResponseHandler(json_store=json_store)
    retry_policy = RetryPolicy(max_attempts=config.max_retry_attempts)
    http_client = OPSClient(config, auth_client)

    downloader = DataDownloader(
        config=config,
        http_client=http_client,
        json_store=json_store,
        response_handler=response_handler,
        retry_policy=retry_policy,
        rate_limiter=rate_limiter,
    )

    progress = tqdm(total=len(pending), desc="Downloading data", unit="task")

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for batch in _chunk(pending, batch_size):
            futures = {
                pool.submit(downloader.fetch_and_store, task, session=_get_session()): task
                for task in batch
            }
            for future in as_completed(futures):
                try:
                    result = future.result()
                except Exception as exc:
                    task = futures[future]
                    result = DownloadResult(
                        download_task=task,
                        pub_id=task.pub_id,
                        is_successful=False,
                        download_status="failed",
                        http_status_code=0,
                        bytes_written=0,
                        status_message=str(exc),
                        output_file_path=json_store.output_path_for(task),
                    )
                _log_result(result, logger)
                progress.update(1)

    progress.close()


def run_pdf_downloads(
    tasks: list[PDFDownloadTask],
    *,
    config: OPSConfig,
    auth_client: OPSAuthClient,
    rate_limiter: RateLimiter,
    logger: DownloadLogger,
    output_dir: Path,
    max_workers: int = 2,
    batch_size: int = 20,
) -> None:
    """
    Download PDF image tasks concurrently using a ThreadPoolExecutor.

    Pages within a single PDFDownloadTask are always downloaded sequentially
    (API constraint: one page per request). Concurrency is across tasks only.

    Resume
    ------
    Reads the logger CSV at startup and skips tasks whose expected merged PDF
    output path is already marked as "downloaded". PDFPageDownloader also checks
    file existence as a secondary guard.

    Backoff
    -------
    On 429 (any page, any thread), rate_limiter.apply_penalty() is called so
    ALL threads pause before their next page fetch.

    Parameters
    ----------
    tasks:
        PDF tasks to download.
    config:
        Shared OPSConfig (immutable).
    auth_client:
        Shared thread-safe OPSAuthClient.
    rate_limiter:
        Shared thread-safe RateLimiter (with apply_penalty support).
    logger:
        Shared thread-safe DownloadLogger.
    output_dir:
        Directory where merged PDFs will be written.
    max_workers:
        Number of concurrent download threads. Keep low (2-4) since each task
        already makes multiple sequential HTTP requests.
    batch_size:
        Max futures in-flight at once.
    """
    logger.init_if_missing()
    output_dir.mkdir(parents=True, exist_ok=True)

    completed_paths = logger.load_completed_output_paths()
    pending = [
        t for t in tasks
        if str(output_dir / f"{t.output_base_filename()}.pdf") not in completed_paths
    ]

    if not pending:
        return

    retry_policy = RetryPolicy(max_attempts=config.max_retry_attempts)

    pdf_downloader = PDFPageDownloader(
        config=config,
        auth_client=auth_client,
        rate_limiter=rate_limiter,
        retry_policy=retry_policy,
        output_dir=output_dir,
    )

    progress = tqdm(total=len(pending), desc="Downloading PDFs", unit="task")

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for batch in _chunk(pending, batch_size):
            futures = {
                pool.submit(pdf_downloader.download, task, session=_get_session()): task
                for task in batch
            }
            for future in as_completed(futures):
                task = futures[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = DownloadResult(
                        download_task=task,
                        pub_id=f"{task.country}{task.pub}{task.kind}",
                        is_successful=False,
                        download_status="failed",
                        http_status_code=0,
                        bytes_written=0,
                        status_message=str(exc),
                        output_file_path=output_dir / f"{task.output_base_filename()}.pdf",
                    )
                _log_result(result, logger)
                progress.update(1)

    progress.close()
