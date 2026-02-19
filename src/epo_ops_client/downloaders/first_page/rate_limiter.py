from __future__ import annotations

import threading
import time


class RateLimiter:
    """
    Global rate limiter: ensures at most `rate_per_sec` requests/sec across all workers.
    """
    def __init__(self, rate_per_sec: float) -> None:
        self._min_interval = 1.0 / max(rate_per_sec, 0.0001)
        self._lock = threading.Lock()
        self._last_ts = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.time()
            sleep_for = self._min_interval - (now - self._last_ts)
            if sleep_for > 0:
                time.sleep(sleep_for)
            self._last_ts = time.time()
