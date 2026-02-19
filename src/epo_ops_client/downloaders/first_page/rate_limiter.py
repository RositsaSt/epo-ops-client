from __future__ import annotations

import threading
import time


class RateLimiter:
    """
    Thread-safe global rate limiter.

    Ensures that no more than `max_requests_per_second`
    requests are executed across all workers.
    """
    def __init__(self, max_requests_per_second: float) -> None:
        self._minimum_interval_seconds = 1.0 / max(max_requests_per_second, 0.0001)
        self._lock = threading.Lock()
        self._last_request_timestamp = 0.0

    def wait_for_slot(self) -> None:
        """
        Blocks until the next request is allowed under the configured rate.
        """
        with self._lock:
            current_timestamp = time.time()
            
            sleep_duration_seconds = self._minimum_interval_seconds - (current_timestamp - self._last_request_timestamp)
            
            if sleep_duration_seconds > 0:
                time.sleep(sleep_duration_seconds)
                
            self._last_request_timestamp = time.time()
