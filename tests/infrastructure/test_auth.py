"""
Tests for OPSAuthClient thread safety.
"""
from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest

from epo_ops_client.infrastructure.auth import OPSAuthClient, OAuthAccessToken


def _make_auth_client() -> OPSAuthClient:
    return OPSAuthClient(
        base_url="https://ops.epo.org/3.2/rest-services",
        ops_key="test-key",
        ops_secret="test-secret",
        request_timeout_seconds=10,
    )


def _fake_token_response(token_value: str = "tok", expires_in: int = 3600) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"access_token": token_value, "expires_in": expires_in}
    return resp


class TestOPSAuthClientThreadSafety:
    def test_token_fetched_once_across_concurrent_threads(self):
        """
        10 threads calling get_valid_token() concurrently must result in
        _request_new_token being called exactly once (token is cached).
        """
        client = _make_auth_client()
        call_count = 0
        original_request = client._request_new_token

        def counted_request():
            nonlocal call_count
            call_count += 1
            import time
            return OAuthAccessToken(
                token_value="cached-tok",
                expires_epoch_seconds=time.time() + 3600,
            )

        client._request_new_token = counted_request  # type: ignore[method-assign]

        results: list[str] = []
        errors: list[Exception] = []

        def worker():
            try:
                results.append(client.get_valid_token())
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(results) == 10
        assert all(r == "cached-tok" for r in results)
        assert call_count == 1, f"Expected 1 token fetch, got {call_count}"

    def test_force_refresh_updates_cached_token(self):
        client = _make_auth_client()
        import time

        call_index = 0

        def two_tokens():
            nonlocal call_index
            call_index += 1
            return OAuthAccessToken(
                token_value=f"token-{call_index}",
                expires_epoch_seconds=time.time() + 3600,
            )

        client._request_new_token = two_tokens  # type: ignore[method-assign]

        first = client.get_valid_token()
        second = client.force_refresh_token()
        third = client.get_valid_token()  # should use cached second token

        assert first == "token-1"
        assert second == "token-2"
        assert third == "token-2"
        assert call_index == 2
