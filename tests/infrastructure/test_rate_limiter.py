"""
Tests for RateLimiter including the new apply_penalty() cross-thread backoff.
"""
from __future__ import annotations

import threading
import time

import pytest

from epo_ops_client.infrastructure.rate_limiter import RateLimiter


class TestApplyPenalty:
    def test_penalty_blocks_all_threads(self):
        """
        Thread A applies a 0.3s penalty; thread B should block at wait_for_slot()
        for at least that duration.
        """
        limiter = RateLimiter(max_requests_per_second=100)  # very fast, no rate interference

        # Apply penalty before thread B starts
        limiter.apply_penalty(0.3)

        start = time.monotonic()
        limiter.wait_for_slot()
        elapsed = time.monotonic() - start

        assert elapsed >= 0.25, f"Expected ~0.3s block, got {elapsed:.3f}s"

    def test_penalty_only_advances_never_shortens(self):
        """Calling apply_penalty with a shorter duration after a longer one is a no-op."""
        limiter = RateLimiter(max_requests_per_second=100)
        limiter.apply_penalty(1.0)
        limiter.apply_penalty(0.1)  # should NOT shorten the existing penalty

        start = time.monotonic()
        limiter.wait_for_slot()
        elapsed = time.monotonic() - start

        assert elapsed >= 0.9, f"Expected ~1.0s block, got {elapsed:.3f}s"

    def test_cross_thread_penalty_propagation(self):
        """
        Thread A applies penalty while thread B is about to call wait_for_slot().
        Thread B should respect the penalty.
        """
        limiter = RateLimiter(max_requests_per_second=100)
        b_elapsed: list[float] = []
        b_ready = threading.Event()
        penalty_applied = threading.Event()

        def thread_a():
            b_ready.wait()
            limiter.apply_penalty(0.3)
            penalty_applied.set()

        def thread_b():
            b_ready.set()
            penalty_applied.wait()
            start = time.monotonic()
            limiter.wait_for_slot()
            b_elapsed.append(time.monotonic() - start)

        ta = threading.Thread(target=thread_a)
        tb = threading.Thread(target=thread_b)
        ta.start()
        tb.start()
        ta.join()
        tb.join()

        assert b_elapsed, "Thread B never recorded elapsed time"
        assert b_elapsed[0] >= 0.2, f"Expected thread B to wait ~0.3s, got {b_elapsed[0]:.3f}s"


class TestRateLimiterConcurrency:
    def test_existing_rate_limit_still_works(self):
        """Original rate-limiting behaviour is preserved after adding apply_penalty."""
        limiter = RateLimiter(max_requests_per_second=10)
        n = 5
        start = time.monotonic()
        for _ in range(n):
            limiter.wait_for_slot()
        elapsed = time.monotonic() - start
        # n requests at 10 req/s → at least (n-1) * 0.1s
        assert elapsed >= (n - 1) * 0.09
