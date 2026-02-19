from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Tuple

import requests
from tqdm import tqdm

from .auth import OPSAuthClient
from .config import DownloaderConfig
from .logging_csv import CsvRunLog, LogRow
from .models import DownloadTask
from .rate_limiter import RateLimiter


RETRY_STATUS = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class DownloadResult:
    task: DownloadTask
    ok: bool
    status: str            # downloaded / skipped / failed
    http_status: int
    bytes_written: int
    message: str
    out_path: Path


def _chunked(items: list[DownloadTask], size: int) -> Iterator[list[DownloadTask]]:
    for i in range(0, len(items), size):
        yield items[i:i + size]


_thread_local = threading.local()


def _get_thread_session() -> requests.Session:
    sess = getattr(_thread_local, "session", None)
    if sess is None:
        sess = requests.Session()
        _thread_local.session = sess
    return sess


def _out_path(config: DownloaderConfig, task: DownloadTask) -> Path:
    fname = f"{task.country}{task.pub_number}{task.kind}_page1.pdf"
    return config.out_dir / fname


def _is_pdf(content: bytes) -> bool:
    return content.startswith(b"%PDF")


def download_one(
    task: DownloadTask,
    *,
    config: DownloaderConfig,
    auth: OPSAuthClient,
    limiter: RateLimiter,
) -> DownloadResult:
    """
    Download one first-page PDF for a task.

    Returns a structured DownloadResult; no side effects besides writing the file.
    """
    config.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = _out_path(config, task)

    # Skip if already downloaded and non-trivial size
    if out_path.exists() and out_path.stat().st_size > 1024:
        return DownloadResult(task, True, "skipped", 200, int(out_path.stat().st_size), "already exists", out_path)

    url = config.image_url_template().format(country=task.country, pub=task.pub_number, kind=task.kind)

    headers = {
        "Authorization": f"Bearer {auth.get()}",
        "Accept": "application/pdf",
        "Range": config.range_header_value,  # keep your behavior, but now configurable
    }

    last_msg = ""
    http_status = 0
    session = _get_thread_session()

    for attempt in range(1, config.max_attempts + 1):
        limiter.wait()
        try:
            r = session.get(url, headers=headers, timeout=config.request_timeout_s)
            http_status = r.status_code

            if http_status == 401:
                # token expired/invalid — refresh and retry
                headers["Authorization"] = f"Bearer {auth.force_refresh()}"
                last_msg = "token refreshed"
                continue

            if http_status in RETRY_STATUS:
                retry_after = r.headers.get("Retry-After", "")
                if retry_after.isdigit():
                    sleep_s = int(retry_after)
                else:
                    sleep_s = min(60.0, (2 ** (attempt - 1)) + random.random())
                last_msg = f"retryable HTTP {http_status}, sleeping {sleep_s:.1f}s"
                time.sleep(sleep_s)
                continue

            if http_status != 200:
                snippet = ""
                try:
                    snippet = r.text[:200].replace("\n", " ")
                except Exception:
                    snippet = "non-text body"
                return DownloadResult(task, False, "failed", http_status, 0, f"HTTP {http_status}: {snippet}", out_path)

            content = r.content
            if not _is_pdf(content):
                return DownloadResult(task, False, "failed", http_status, 0, f"not a PDF; first bytes={content[:20]!r}", out_path)

            out_path.write_bytes(content)
            return DownloadResult(task, True, "downloaded", http_status, len(content), last_msg or "ok", out_path)

        except requests.RequestException as e:
            sleep_s = min(60.0, (2 ** (attempt - 1)) + random.random())
            last_msg = f"request error: {e}; sleeping {sleep_s:.1f}s"
            time.sleep(sleep_s)

    return DownloadResult(task, False, "failed", http_status, 0, last_msg or "exhausted retries", out_path)


def download_many(
    tasks: list[DownloadTask],
    *,
    config: DownloaderConfig,
    auth: OPSAuthClient,
    limiter: RateLimiter,
    run_log: CsvRunLog,
) -> None:
    """
    Bulk download with chunking + progress bar.

    Logging is injected (dependency inversion) so you can swap CSV logging with
    SQLite, JSONL, etc. later.
    """
    run_log.init_if_missing()
    config.out_dir.mkdir(parents=True, exist_ok=True)

    total = len(tasks)
    pbar = tqdm(total=total, desc="Downloading front pages", unit="file")

    from concurrent.futures import ThreadPoolExecutor, as_completed

    for chunk in _chunked(tasks, config.chunk_size):
        with ThreadPoolExecutor(max_workers=config.workers) as ex:
            futures = [
                ex.submit(download_one, t, config=config, auth=auth, limiter=limiter)
                for t in chunk
            ]
            for fut in as_completed(futures):
                res: DownloadResult = fut.result()
                run_log.append(LogRow(
                    ts=CsvRunLog.now_ts(),
                    country=res.task.country,
                    pub_number=res.task.pub_number,
                    kind=res.task.kind,
                    status=res.status,
                    http_status=res.http_status,
                    bytes_written=res.bytes_written,
                    message=res.message,
                    out_path=str(res.out_path),
                ))
                pbar.update(1)

    pbar.close()
