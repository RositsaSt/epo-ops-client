from __future__ import annotations

from pathlib import Path
from typing import Any

import requests

from .json_store import JsonResponseStore
from ..domain.models import DownloadTask, DownloadResult
from ..domain.models import PDFDownloadTask


def _looks_like_pdf(content: bytes, content_type: str | None) -> bool:

    """
    Best-effort detection for PDF payloads.
    """
    if content_type:
        if "pdf" in content_type.lower():
            return True
    
    #fallback to checking the magic bytes for PDF files (first 4 bytes should be "%PDF")
    return bool(content and content.startswith(b"%PDF"))
    
class ResponseHandler:
    """
    Converts a successful HTTP 200 response into a persisted file + DownloadResult.
    """

    def __init__(self, json_store: JsonResponseStore) -> None:
        self._store = json_store

    def handle_success(
        self,
        *,
        download_task: Any,     # DownloadTask or PDFDownloadTask
        output_path: Path,
        response: requests.Response,
    ) -> DownloadResult:
        # Prefer Content-Type to decide; fall back to JSON parsing, then PDF magic
        content_type = response.headers.get("Content-Type")

        # If the response advertises PDF or content looks like PDF -> save bytes
        if _looks_like_pdf(response.content, content_type):
            # optional extra validation: ensure PDF magic bytes
            if not response.content.startswith(b"%PDF"):
                # still write the bytes but mark caution in the status_message
                bytes_written = self._store.write_bytes_atomic(output_path, response.content)
                status_msg = "saved binary payload (not starting with %PDF)"
            else:
                bytes_written = self._store.write_bytes_atomic(output_path, response.content)
                status_msg = "ok"
            return DownloadResult(
                download_task=download_task,
                is_successful=True,
                download_status="downloaded",
                http_status_code=response.status_code,
                bytes_written=bytes_written,
                status_message=status_msg,
                output_file_path=output_path,
            )

        # Otherwise try JSON decode path
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
            # Unknown non-JSON, non-PDF payload: write bytes and warn
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
