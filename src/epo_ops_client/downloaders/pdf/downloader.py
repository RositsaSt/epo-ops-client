from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import time

import requests

from ..first_page.config import OPSFirstPageDownloaderConfig as LegacyConfig
from ...domain.models import PDFDownloadTask, PageSelection
from ...infrastructure.auth import OPSAuthClient
from ...infrastructure.retry_policy import RetryPolicy
from ...infrastructure.response_handler import ResponseHandler
from ...infrastructure.json_store import JsonResponseStore
from ...infrastructure.rate_limiter import RateLimiter
from epo_ops_client.downloaders.first_page import config


def _build_output_path(output_dir: Path, task: PDFDownloadTask) -> Path:
    return output_dir / f"{task.output_basename()}.pdf"


def download_one_pdf(
    task: PDFDownloadTask,
    *,
    config: LegacyConfig | None = None,
    auth_client: OPSAuthClient,
    response_handler: ResponseHandler,
    rate_limiter: RateLimiter,
    session: requests.Session | None = None,
    json_store: JsonResponseStore | None = None,
    retry_policy: RetryPolicy | None = None,
) -> None:
    """
    Download a single PDF task (single page or page-range or multiple pages).
    This initial implementation supports the 'first' and small range semantics by
    issuing requests with the Range header when appropriate.
    """
    cfg = config or LegacyConfig()
    out_dir = cfg.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    if session is None:
        session = requests.Session()

    url_template = cfg.image_url_template()
    url = url_template.format(
        country=task.country,
        pub=task.pub_number,
        kind=task.kind
    )

    headers = {
        "Authorization": f"Bearer {auth_client.get_valid_token()}",
        "Accept": "application/pdf",
    }

    # Determine Range header value from task.page_selection
    if task.page_selection.kind == "first":
        headers["Range"] = cfg.ops_image_range_header_value
    elif task.page_selection.kind == "range" and task.page_selection.start and task.page_selection.end:
        # OPS API expects 1-based page numbers in the Range header, e.g. "Range: pages=1-5"
        headers["Range"] = f"{task.page_selection.start}-{task.page_selection.end}"
    elif task.page_selection.kind == "all":
        # For all pages, we do not set a Range header and let OPS return the full PDF
        headers["Range"] = cfg.ops_image_range_header_value
    
    # Basic retry loop
    retry_loop = retry_policy or RetryPolicy(max_attempts=cfg.max_retry_attempts, backoff_factor=2)
    last_exception = None
    for attempt in range(1, retry_loop.max_attempts + 1):
        try:
            response = session.get(url, headers=headers, timeout=cfg.http_request_timeout_seconds)
            if response.status_code == 401:
                # Try refreshing token and retrying immediately
                auth_client.force_refresh_token()
                headers["Authorization"] = f"Bearer {auth_client.get_valid_token()}"
                continue
            
            if response.status_code != 200:
                decision = retry_loop.on_http_response(response=response, attempt_number=attempt)
                if decision.should_retry and retry_loop.should_continue(attempt):
                    time.sleep(decision.sleep_seconds)
                    continue
                
                # If not retrying, raise for non-success status to be handled by caller
                response.raise_for_status()
            
            output_path = _build_output_path(cfg.output_dir, task)

            # If we got a successful response, handle it and return
            return response_handler.handle_success(
                download_task=task,
                output_path=output_path,
                response=response,
            )
        
        except requests.RequestException as exc:
            last_exception = exc
            decision = retry_loop.on_request_exception(exception=exc, attempt_number=attempt)
            if decision.should_retry and retry_loop.should_continue(attempt):
                time.sleep(decision.sleep_seconds)
                continue
            raise
            
    # If we exhausted retries, raise the last exception encountered
    if last_exception:
        raise last_exception
        
def download_many_pdf(
    tasks: Iterable[PDFDownloadTask],
    *,
    config: LegacyConfig | None = None,
    auth_client: OPSAuthClient,
    response_handler: ResponseHandler,
    rate_limiter: RateLimiter,
) -> None:
    """
    Sequential runner for a set of PDFDownloadTask. Later commits will add ThreadPoolExecutor batching.
    """
    for task in tasks:
        rate_limiter.wait_for_slot()
        download_one_pdf(
            task=task,
            config=config,
            auth_client=auth_client,
            response_handler=response_handler,
            rate_limiter=rate_limiter,
        )