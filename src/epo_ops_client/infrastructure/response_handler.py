from __future__ import annotations

from pathlib import Path

import requests

from .json_store import JsonResponseStore
from ..domain.models import DownloadTask, DownloadResult

class ResponseHandler:
    """
    Converts a successful HTTP 200 response into a persisted file + DownloadResult.
    """

    def __init__(self, json_store: JsonResponseStore) -> None:
        self._store = json_store

    def handle_success(
        self,
        *,
        download_task: DownloadTask,
        output_path: Path,
        response: requests.Response,
    ) -> DownloadResult:
        try:
            payload = response.json()
            bytes_written = self._store.write_json_atomic(output_path, payload)
            return DownloadResult(
                download_task=download_task,
                is_successful=True,
                download_status="downloaded",
                http_status_code=response.status_code,
                bytes_written=bytes_written,
                status_message="ok",
                output_file_path=output_path,
            )
        except ValueError:
            bytes_written = self._store.write_bytes_atomic(output_path, response.content)
            return DownloadResult(
                download_task=download_task,
                is_successful=True,
                download_status="downloaded",
                http_status_code=response.status_code,
                bytes_written=bytes_written,
                status_message="ok (non-JSON payload saved as bytes)",
                output_file_path=output_path,
            )

    def handle_http_failure(
        self,
        *,
        download_task: DownloadTask,
        output_path: Path,
        response: requests.Response,
    ) -> DownloadResult:
        snippet = (response.text or "")[:200]
        return DownloadResult(
            download_task=download_task,
            is_successful=False,
            download_status="failed",
            http_status_code=response.status_code,
            bytes_written=0,
            status_message=snippet or f"HTTP {response.status_code}",
            output_file_path=output_path,
        )

