from __future__ import annotations

import io
import time
from pathlib import Path
from typing import Callable

import requests

from ..config import OPSConfig
from ..domain.models import PDFDownloadTask, DownloadResult
from ..infrastructure.auth import OPSAuthClient
from ..infrastructure.rate_limiter import RateLimiter
from ..infrastructure.retry_policy import RetryPolicy


class PDFPageDownloader:
    """
    Downloads a PDFDownloadTask, potentially multiple pages, and merges them.

    Thread-safety
    -------------
    All mutable state is either per-call local or delegated to the shared
    RateLimiter (thread-safe, sleep-outside-lock) and OPSAuthClient (thread-safe
    after adding a lock). Pages within one task are always downloaded sequentially
    (API constraint: one page per request). Concurrency across tasks is handled
    by the runner layer.

    Page modes
    ----------
    - "first": downloads page 1 only, writes it directly.
    - "range": downloads pages start..end (inclusive), merges them.
    - "all": first queries the metadata endpoint for total page count,
             then downloads all pages and merges them.
    """

    def __init__(
        self,
        *,
        config: OPSConfig,
        auth_client: OPSAuthClient,
        rate_limiter: RateLimiter,
        retry_policy: RetryPolicy,
        output_dir: Path,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._config = config
        self._auth_client = auth_client
        self._rate_limiter = rate_limiter
        self._retry_policy = retry_policy
        self._output_dir = output_dir
        self._sleeper = sleeper

    def download(self, task: PDFDownloadTask, *, session: requests.Session) -> DownloadResult:
        """
        Download all required pages for `task` and return a DownloadResult
        pointing to the final (possibly merged) PDF file.
        """
        pub_id = f"{task.country}{task.pub}{task.kind}"
        output_path = self._output_dir / f"{task.output_base_filename()}.pdf"

        # Skip if already downloaded (secondary guard; the runner pre-filters via the log)
        if output_path.exists() and output_path.stat().st_size > 0:
            return DownloadResult(
                download_task=task,
                pub_id=pub_id,
                is_successful=True,
                download_status="skipped",
                http_status_code=0,
                bytes_written=int(output_path.stat().st_size),
                status_message="already exists",
                output_file_path=output_path,
            )

        self._output_dir.mkdir(parents=True, exist_ok=True)

        try:
            kind = task.page_selection.kind
            if kind == "first":
                page_bytes = self._fetch_page(task=task, page_number=1, session=session)
                bytes_written = self._write_bytes_atomic(output_path, page_bytes)
            elif kind == "range":
                start = task.page_selection.start or 1
                end = task.page_selection.end or 1
                pages = [
                    self._fetch_page(task=task, page_number=p, session=session)
                    for p in range(start, end + 1)
                ]
                bytes_written = self._merge_pages(pages, output_path)
            elif kind == "all":
                total = self._get_total_page_count(task, session=session)
                pages = [
                    self._fetch_page(task=task, page_number=p, session=session)
                    for p in range(1, total + 1)
                ]
                bytes_written = self._merge_pages(pages, output_path)
            else:
                raise ValueError(f"Unknown page_selection.kind: {kind!r}")

            return DownloadResult(
                download_task=task,
                pub_id=pub_id,
                is_successful=True,
                download_status="downloaded",
                http_status_code=200,
                bytes_written=bytes_written,
                status_message="ok",
                output_file_path=output_path,
            )

        except Exception as exc:
            return DownloadResult(
                download_task=task,
                pub_id=pub_id,
                is_successful=False,
                download_status="failed",
                http_status_code=0,
                bytes_written=0,
                status_message=str(exc),
                output_file_path=output_path,
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_page(
        self,
        *,
        task: PDFDownloadTask,
        page_number: int,
        session: requests.Session,
    ) -> bytes:
        """
        Download exactly one PDF page. Applies rate limiting and retry with
        cross-thread backoff (apply_penalty) on 429 responses.
        Returns raw PDF bytes on success; raises on unrecoverable failure.
        """
        url = (
            self._config.pdf_image_url_template().format(
                country=task.country, pub=task.pub, kind=task.kind
            )
            + f"?Range={page_number}"
        )

        for attempt in range(1, self._retry_policy.max_attempts + 1):
            self._rate_limiter.wait_for_slot()
            try:
                response = session.get(
                    url,
                    headers={
                        "Authorization": f"Bearer {self._auth_client.get_valid_token()}",
                        "Accept": "application/pdf",
                    },
                    timeout=self._config.http_request_timeout_seconds,
                )

                if response.status_code == 401:
                    self._auth_client.force_refresh_token()
                    continue

                if response.status_code == 200:
                    return response.content

                decision = self._retry_policy.on_http_response(
                    response=response, attempt_number=attempt
                )
                if decision.should_retry and self._retry_policy.should_continue(attempt):
                    self._rate_limiter.apply_penalty(decision.sleep_seconds)
                    self._sleeper(decision.sleep_seconds)
                    continue

                response.raise_for_status()

            except requests.RequestException as exc:
                decision = self._retry_policy.on_request_exception(
                    exc=exc, attempt_number=attempt
                )
                if decision.should_retry and self._retry_policy.should_continue(attempt):
                    self._sleeper(decision.sleep_seconds)
                    continue
                raise

        raise RuntimeError(
            f"Exhausted {self._retry_policy.max_attempts} retries for "
            f"{task.country}{task.pub}{task.kind} page {page_number}"
        )

    def _get_total_page_count(
        self, task: PDFDownloadTask, *, session: requests.Session
    ) -> int:
        """
        Query the OPS images metadata endpoint to determine the total page count.

        The EPO OPS images endpoint returns JSON containing drawing information,
        including the number of pages.
        """
        pub_id = f"{task.country}{task.pub}.{task.kind}"
        url = self._config.images_metadata_url_template().format(
            identifier_type="epodoc",
            pub_id=pub_id,
        )

        for attempt in range(1, self._retry_policy.max_attempts + 1):
            self._rate_limiter.wait_for_slot()
            try:
                response = session.get(
                    url,
                    headers={
                        "Authorization": f"Bearer {self._auth_client.get_valid_token()}",
                        "Accept": "application/json",
                    },
                    timeout=self._config.http_request_timeout_seconds,
                )

                if response.status_code == 401:
                    self._auth_client.force_refresh_token()
                    continue

                if response.status_code == 200:
                    return self._parse_page_count(response.json(), pub_id)

                decision = self._retry_policy.on_http_response(
                    response=response, attempt_number=attempt
                )
                if decision.should_retry and self._retry_policy.should_continue(attempt):
                    self._rate_limiter.apply_penalty(decision.sleep_seconds)
                    self._sleeper(decision.sleep_seconds)
                    continue

                response.raise_for_status()

            except requests.RequestException as exc:
                decision = self._retry_policy.on_request_exception(
                    exc=exc, attempt_number=attempt
                )
                if decision.should_retry and self._retry_policy.should_continue(attempt):
                    self._sleeper(decision.sleep_seconds)
                    continue
                raise

        raise RuntimeError(
            f"Could not retrieve page count for {pub_id} after "
            f"{self._retry_policy.max_attempts} attempts"
        )

    @staticmethod
    def _parse_page_count(data: object, pub_id: str) -> int:
        """
        Extract @number-of-pages from the OPS images metadata JSON response.

        The OPS JSON structure varies. This method tries the most common path
        and raises ValueError if the page count cannot be found.
        """
        try:
            world_data = data["ops:world-patent-data"]  # type: ignore[index]
            # The images endpoint returns ops:patent-family or ops:biblio-search
            # Try ops:patent-family path first
            try:
                members = world_data["ops:patent-family"]["ops:family-member"]
                if isinstance(members, dict):
                    members = [members]
                for member in members:
                    drawing = member.get("ops:drawing")
                    if drawing and "@number-of-pages" in drawing:
                        return int(drawing["@number-of-pages"])
            except (KeyError, TypeError):
                pass

            # Fallback: try ops:biblio-search path
            members = (
                world_data.get("ops:biblio-search", {})
                .get("ops:search-result", {})
                .get("ops:publication-reference", [])
            )
            if isinstance(members, dict):
                members = [members]
            for member in members:
                drawing = member.get("ops:drawing")
                if drawing and "@number-of-pages" in drawing:
                    return int(drawing["@number-of-pages"])

        except (KeyError, TypeError, AttributeError):
            pass

        raise ValueError(
            f"Could not extract page count from OPS metadata for {pub_id}. "
            "The response structure may have changed or this publication has no images."
        )

    @staticmethod
    def _merge_pages(page_bytes_list: list[bytes], output_path: Path) -> int:
        """
        Merge a list of single-page PDF byte buffers into one PDF file.
        Writes atomically via a temp file + rename.
        Returns the number of bytes written.
        """
        from pypdf import PdfWriter, PdfReader  # type: ignore[import]

        writer = PdfWriter()
        for page_bytes in page_bytes_list:
            reader = PdfReader(io.BytesIO(page_bytes))
            for page in reader.pages:
                writer.add_page(page)

        tmp_path = output_path.with_suffix(".tmp.pdf")
        with tmp_path.open("wb") as f:
            writer.write(f)
        tmp_path.replace(output_path)
        return output_path.stat().st_size

    @staticmethod
    def _write_bytes_atomic(output_path: Path, content: bytes) -> int:
        """Write raw bytes atomically via a temp file + rename."""
        tmp_path = output_path.with_suffix(".tmp.pdf")
        tmp_path.write_bytes(content)
        tmp_path.replace(output_path)
        return output_path.stat().st_size
