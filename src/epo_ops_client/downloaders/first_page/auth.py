from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import requests
from requests.auth import HTTPBasicAuth


@dataclass
class _Token:
    access_token: str
    expires_at: float  # epoch seconds


class OPSAuthClient:
    """
    Fetches and caches OPS OAuth tokens (client_credentials).

    - Refreshes token if missing or close to expiry
    - Can be forced to refresh (e.g., after a 401)
    """
    def __init__(self, base_url: str, ops_key: str, ops_secret: str, timeout_s: int = 30) -> None:
        self._token_url = base_url + "/auth/accesstoken"
        self._auth = HTTPBasicAuth(ops_key, ops_secret)
        self._timeout_s = timeout_s

        self._lock = threading.Lock()
        self._token: _Token | None = None

    def _fetch_token(self) -> _Token:
        r = requests.post(
            self._token_url,
            data={"grant_type": "client_credentials"},
            auth=self._auth,
            timeout=self._timeout_s,
        )
        r.raise_for_status()
        payload = r.json()

        access = payload["access_token"]
        expires_in = float(payload.get("expires_in", 3600))
        # refresh a bit early
        expires_at = time.time() + max(0.0, expires_in - 60.0)
        return _Token(access_token=access, expires_at=expires_at)

    def get(self) -> str:
        with self._lock:
            if self._token is None or time.time() >= self._token.expires_at:
                self._token = self._fetch_token()
            return self._token.access_token

    def force_refresh(self) -> str:
        with self._lock:
            self._token = self._fetch_token()
            return self._token.access_token
