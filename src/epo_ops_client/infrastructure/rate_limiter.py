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
        # Lock to make this rate limiter safe to use across threads
        self._lock = threading.Lock()

    def _time_to_wait(self, current_timestamp: float) -> float:
        elapsed_seconds = current_timestamp - self._last_request_timestamp
        remaining_wait = self._minimum_interval_seconds - elapsed_seconds
        return max(0.0, remaining_wait)


    def wait_for_slot(self) -> None:
        """
        Blocks until the next request is allowed under the configured rate.
        """
        if self._minimum_interval_seconds == 0.0:
            return

        while True:
            now = time.monotonic()
            with self._lock:
                remaining = self._time_to_wait(now)
                if remaining <= 0:
                    # we can proceed and update last timestamp
                    self._last_request_timestamp = time.monotonic()
                    return
                # otherwise, compute how long to wait (release lock while sleeping)
            # sleep outside of lock so other threads may check
            time.sleep(remaining)
