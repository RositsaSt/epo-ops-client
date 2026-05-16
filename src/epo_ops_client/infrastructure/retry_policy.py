from __future__ import annotations

import random
from dataclasses import dataclass

import requests


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
    """
    if retry_after_header_value and retry_after_header_value.isdigit():
        return float(int(retry_after_header_value))

    backoff_with_jitter = (2 ** (attempt_number - 1)) + random.random()
    return float(min(maximum_sleep_seconds, backoff_with_jitter))


@dataclass(frozen=True)
class RetryDecision:
    should_retry: bool
    sleep_seconds: float
    reason: str
    
class RetryPolicy:
    """
    Encapsulates retry decisions (which HTTP codes retry, how long to sleep, etc.).
    """

    def __init__(
        self,
        *,
        max_attempts: int,
        retryable_http_status_codes: set[int] | None = None,
        maximum_sleep_seconds: float = 60.0,
    ) -> None:
        self._max_attempts = max_attempts
        self._retryable_http_status_codes = retryable_http_status_codes or {429, 500, 502, 503, 504}
        self._maximum_sleep_seconds = maximum_sleep_seconds

    @property
    def max_attempts(self) -> int:
        return self._max_attempts

    def on_http_response(self, *, response: requests.Response, attempt_number: int) -> RetryDecision:
        code = response.status_code
        if code in self._retryable_http_status_codes:
            retry_after = response.headers.get("Retry-After")
            sleep_seconds = _compute_retry_sleep_seconds(
                attempt_number=attempt_number,
                retry_after_header_value=retry_after,
                maximum_sleep_seconds=self._maximum_sleep_seconds,
            )
            return RetryDecision(
                should_retry=True,
                sleep_seconds=sleep_seconds,
                reason=f"retryable HTTP {code}",
            )
        return RetryDecision(should_retry=False, sleep_seconds=0.0, reason="non-retryable HTTP")

    def on_request_exception(self, *, exc: requests.RequestException, attempt_number: int) -> RetryDecision:
        sleep_seconds = _compute_retry_sleep_seconds(
            attempt_number=attempt_number,
            retry_after_header_value=None,
            maximum_sleep_seconds=self._maximum_sleep_seconds,
        )
        return RetryDecision(
            should_retry=True,
            sleep_seconds=sleep_seconds,
            reason=f"request error: {exc}",
        )

    def should_continue(self, attempt_number: int) -> bool:
        return attempt_number < self._max_attempts