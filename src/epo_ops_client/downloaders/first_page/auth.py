from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import requests
from requests.auth import HTTPBasicAuth


@dataclass
class OAuthAccessToken:
    """
    Represents an OAuth access token and its expiration timestamp.
    """
    token_value: str
    expires_epoch_seconds: float


class OPSAuthClient:
    """
    Handles fetching and caching of OPS OAuth access tokens using
    the client_credentials grant type.

    Features:
    - Automatically refreshes expired tokens
    - Refreshes slightly before expiration (safety margin)
    - Thread-safe
    """
    def __init__(self, base_url: str, ops_key: str, ops_secret: str, request_timeout_seconds: int = 30) -> None:
        self._oauth_token_endpoint = base_url + "/auth/accesstoken"
        self._client_credentials_auth = HTTPBasicAuth(ops_key, ops_secret)
        self._request_timeout_seconds = request_timeout_seconds

        self._lock = threading.Lock()
        self._cached_token: OAuthAccessToken | None = None

    def _request_new_token(self) -> OAuthAccessToken:
        """
        Requests a new OAuth access token from OPS.
        """
        response = requests.post(
            self._oauth_token_endpoint,
            data={"grant_type": "client_credentials"},
            auth=self._client_credentials_auth,
            timeout=self._request_timeout_seconds,
        )
        response.raise_for_status()
        token_payload = response.json()

        token_value = token_payload["access_token"]
        expires_in = float(token_payload.get("expires_in", 3600))
        
        # Refresh slightly before actual expiration
        expires_epoch_seconds = time.time() + max(0.0, expires_in - 60.0)
        return OAuthAccessToken(token_value=token_value, expires_epoch_seconds=expires_epoch_seconds)

    def get_valid_token(self) -> str:
        """
        Returns a valid (non-expired) access token.
        Automatically refreshes if needed.
        """
        with self._lock:
            if self._cached_token is None or time.time() >= self._cached_token.expires_epoch_seconds:
                self._cached_token = self._request_new_token()
                
            return self._cached_token.token_value

    def force_refresh_token(self) -> str:
        """
        Forces retrieval of a new access token.
        Useful after receiving a 401 response.
        """
        with self._lock:
            self._cached_token = self._request_new_token()
            return self._cached_token.token_value
