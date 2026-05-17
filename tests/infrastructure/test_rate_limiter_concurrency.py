import time
from threading import Thread

from epo_ops_client.infrastructure.rate_limiter import RateLimiter


def test_rate_limiter_concurrency_respects_rate():
    # Configure a limiter that allows 10 requests per second (0.1s interval)
    limiter = RateLimiter(max_requests_per_second=10.0)

    call_count_per_thread = 10
    num_threads = 2
    total_calls = call_count_per_thread * num_threads

    timestamps = []

    def worker(n):
        for _ in range(n):
            limiter.wait_for_slot()
            timestamps.append(time.time())

    threads = [Thread(target=worker, args=(call_count_per_thread,)) for _ in range(num_threads)]

    t0 = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.time() - t0

    # Minimum expected time between N sequential requests is (N-1) * 0.1s
    min_expected = (total_calls - 1) * (1.0 / 10.0)

    assert elapsed + 0.01 >= min_expected
