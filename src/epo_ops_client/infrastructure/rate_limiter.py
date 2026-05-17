from __future__ import annotations

import time
import threading
from typing import Optional


class RateLimiter:
    """
    Simple sequential rate limiter for controlling request frequency.

    This implementation is safe to use from multiple threads. It ensures that
    at most `max_requests_per_second` requests are made by enforcing a
    minimum time interval between consecutive calls.
    """
    
    def __init__(self, max_requests_per_second: float) -> None:
        """
        Parameters
        ----------
        max_requests_per_second : float
            Maximum allowed number of requests per second.
            If <= 0, throttling is disabled.
        """
        if max_requests_per_second <= 0:
            self._minimum_interval_seconds = 0.0
        else:
            self._minimum_interval_seconds = 1.0 / max_requests_per_second

        self._last_request_timestamp = 0.0
        self._penalty_until = 0.0  # monotonic timestamp; all threads wait until this expires

        # Lock to make this rate limiter safe to use across threads
        self._lock = threading.Lock()

    def _time_to_wait(self, current_timestamp: float) -> float:
        elapsed_seconds = current_timestamp - self._last_request_timestamp
        remaining_wait = self._minimum_interval_seconds - elapsed_seconds
        return max(0.0, remaining_wait)

    def apply_penalty(self, duration_seconds: float) -> None:
        """
        Signal all threads to pause for at least `duration_seconds`.

        Call this after receiving a 429 response so that every thread respects
        the backoff period — not just the one that got throttled.
        Thread-safe: only advances the penalty timestamp, never shortens it.
        """
        with self._lock:
            candidate = time.monotonic() + duration_seconds
            if candidate > self._penalty_until:
                self._penalty_until = candidate

    def wait_for_slot(self) -> None:
        """
        Blocks until the next request is allowed under the configured rate.

        Respects both the per-request rate limit and any active global penalty
        set by apply_penalty(). Sleeps outside the lock so other threads can
        check their own state concurrently.
        """
        if self._minimum_interval_seconds == 0.0 and self._penalty_until == 0.0:
            return

        while True:
            now = time.monotonic()
            with self._lock:
                penalty_remaining = max(0.0, self._penalty_until - now)
                rate_remaining = self._time_to_wait(now)
                remaining = max(penalty_remaining, rate_remaining)
                if remaining <= 0:
                    self._last_request_timestamp = time.monotonic()
                    return

            # Sleep outside the lock so other threads can check concurrently
            time.sleep(remaining)
