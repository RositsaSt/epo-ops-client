from __future__ import annotations

import time


class RateLimiter:
    """
    Simple sequential rate limiter for controlling request frequency.

    This implementation is designed for single-threaded execution.
    It ensures that at most `max_requests_per_second` requests are made
    by enforcing a minimum time interval between consecutive calls.

    Example
    -------
    >>> limiter = RateLimiter(max_requests_per_second=1.0)
    >>> for task in tasks:
    ...     limiter.wait_for_slot()
    ...     perform_request()
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
    

    def wait_for_slot(self) -> None:
        """
        Blocks until the next request is allowed under the configured rate.
        
        This method:
        1. Calculates the elapsed time since the previous request.
        2. Sleeps if necessary to respect the configured rate.
        3. Updates the internal timestamp for the next call.
        """
        if self._minimum_interval_seconds == 0.0:
            # Throttling disabled
            return
        
        current_timestamp = time.monotonic()
        elapsed_seconds = current_timestamp - self._last_request_timestamp
        
        remaining_wait = self._minimum_interval_seconds - elapsed_seconds
        
        if remaining_wait > 0:
            time.sleep(remaining_wait)
            
        self._last_request_timestamp = time.monotonic()
