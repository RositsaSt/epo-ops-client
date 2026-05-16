from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable, Literal

import requests

from ..config import OPSConfig
from ..domain.models import DownloadTask
from ..infrastructure.response_handler import ResponseHandler
from ..infrastructure.rate_limiter import RateLimiter
from ..infrastructure.retry_policy import RetryPolicy


DownloadStatus = Literal["downloaded", "skipped", "failed"]


# ----------------------------
# Domain result (value object)
# ----------------------------

@dataclass(frozen=True)
class DownloadResult:
    """
    Outcome of a single download attempt (including skip/failure).

    Note: for "skipped", http_status_code is 0 because no request was made.
    """
    download_task: DownloadTask
    is_successful: bool
    download_status: DownloadStatus
    http_status_code: int
    bytes_written: int
    status_message: str
    output_file_path: Path


# ----------------------------
# Protocols (DIP / testability)
# ----------------------------
    
@runtime_checkable
class HttpClient(Protocol):
    def build_url(self, download_task: DownloadTask) -> str: ...
    def get_request(
        self,
        *,
        download_task: DownloadTask,
        session: requests.Session,
        timeout_seconds: int,
    ) -> requests.Response: ...
    def refresh_token(self) -> str: ...


@runtime_checkable
class ResponseStore(Protocol):
    def output_path_for(self, task: DownloadTask) -> Path: ...
    def is_already_downloaded(self, path: Path, *, min_bytes: int = 1024) -> bool: ...
    def write_json_atomic(self, path: Path, payload: object) -> int: ...
    def write_bytes_atomic(self, path: Path, content: bytes) -> int: ...


class Sleeper(Protocol):
    def __call__(self, seconds: float) -> None: ...    
    
        
class DataDownloader:
    """
    Orchestrates the workflow for downloading exactly one abstract.

    Responsibilities:
    - skip policy (already downloaded)
    - rate limiting per attempt
    - retry loop via RetryPolicy
    - token refresh on 401
    - delegates persistence to ResponseHandler / store
    """

    def __init__(
        self,
        *,
        config: OPSConfig,
        http_client: HttpClient,
        json_store: ResponseStore,
        response_handler: ResponseHandler,
        retry_policy: RetryPolicy,
        rate_limiter: RateLimiter,
        sleeper: Sleeper = time.sleep,
        min_valid_file_bytes: int = 1024,
    ) -> None:
        self._config = config
        self._client = http_client
        self._store = json_store
        self._response_handler = response_handler
        self._retry_policy = retry_policy
        self._rate_limiter = rate_limiter
        self._sleeper = sleeper
        self._min_valid_file_bytes = min_valid_file_bytes

    def fetch_and_store_abstract(self, download_task: DownloadTask, *, session: requests.Session) -> DownloadResult:
        output_path = self._store.output_path_for(download_task)

        if self._store.is_already_downloaded(output_path, min_bytes=self._min_valid_file_bytes):
            return DownloadResult(
                download_task=download_task,
                is_successful=True,
                download_status="skipped",
                http_status_code=0,  # no HTTP call happened
                bytes_written=int(output_path.stat().st_size),
                status_message="already exists",
                output_file_path=output_path,
            )

        last_message = ""
        last_http_code = 0

        for attempt_number in range(1, self._retry_policy.max_attempts + 1):
            self._rate_limiter.wait_for_slot()
    
            try:
                response = self._client.get_request(
                    download_task=download_task,
                    session=session,
                    timeout_seconds=self._config.http_request_timeout_seconds,
                )
                last_http_code = response.status_code

                if response.status_code == 401:
                    # special-case: refresh token and retry immediately
                    self._client.refresh_token()
                    last_message = "token refreshed after 401"
                    if self._retry_policy.should_continue(attempt_number):
                        continue
                    break
                
                if response.status_code == 200:
                    return self._response_handler.handle_success(
                        download_task=download_task,
                        output_path=output_path,
                        response=response,
                    )
                
                decision = self._retry_policy.on_http_response(response=response, attempt_number=attempt_number)
                if decision.should_retry and self._retry_policy.should_continue(attempt_number):
                    last_message = f"{decision.reason}; sleeping {decision.sleep_seconds:.1f}s"
                    self._sleeper(decision.sleep_seconds)
                    continue

                return self._response_handler.handle_http_failure(
                    download_task=download_task,
                    output_path=output_path,
                    response=response,
                )

            except requests.RequestException as exc:
                decision = self._retry_policy.on_request_exception(exc=exc, attempt_number=attempt_number)
                last_message = f"{decision.reason}; sleeping {decision.sleep_seconds:.1f}s"

                if decision.should_retry and self._retry_policy.should_continue(attempt_number):
                    self._sleeper(decision.sleep_seconds)
                    continue

                break
        
        return DownloadResult(
            download_task=download_task,
            is_successful=False,
            download_status="failed",
            http_status_code=last_http_code,
            bytes_written=0,
            status_message=last_message or "exhausted retries",
            output_file_path=output_path,
        )