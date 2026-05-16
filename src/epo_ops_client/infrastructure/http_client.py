from __future__ import annotations

import requests

from .auth import OPSAuthClient
from ..config import OPSConfig
from ..domain.models import DownloadTask


class OPSClient:
    """
    HTTP client for retrieving patent abstracts from the EPO OPS Published Data API.

    Responsibility
    --------------
    - Build the abstract URL from the config + task
    - Perform the HTTP GET using a requests.Session
    - Attach authorization header (Bearer token) obtained from OPSAuthClient
    """

    def __init__(self, config: OPSConfig, auth_client: OPSAuthClient) -> None:
        self._config = config
        self._auth_client = auth_client

    def build_url(self, download_task: DownloadTask) -> str:
        """
        Build the OPS URL for the given download task.
        """
        return self._config.url_template().format(
            identifier_type=download_task.identifier_type.value,
            pub_id=download_task.pub_id,
            data_type=download_task.data_type.value
        )

    def get_request(
        self,
        *,
        download_task: DownloadTask,
        session: requests.Session,
        timeout_seconds: int,
        headers: dict[str, str] | None = None,
        stream: bool = False,
    ) -> requests.Response:
        """
        Execute a single HTTP GET request for one abstract.

        Returns
        -------
        requests.Response
            Raw response from OPS.
        """
        url = self.build_url(download_task)
        headers = {
            "Authorization": f"Bearer {self._auth_client.get_valid_token()}",
            "Accept": "application/json",
        }

        # Allow caller to override or add headers if needed (e.g. for PDF downloads)
        auth_header = {"Authorization": f"Bearer {self._auth_client.get_valid_token()}"}
        merged_headers = {}
        if headers:
            merged_headers.update(headers)
        merged_headers.update(auth_header)
        return session.get(url, headers=merged_headers, timeout=timeout_seconds, stream=stream)

    def refresh_token(self) -> str:
        """
        Force refresh the OPS OAuth token and return the new token value.

        Used after receiving 401 responses.
        """
        return self._auth_client.force_refresh_token()