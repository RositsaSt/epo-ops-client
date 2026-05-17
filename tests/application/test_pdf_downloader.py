"""
Tests for PDFPageDownloader.
"""
from __future__ import annotations

import io
import struct
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from epo_ops_client.domain.models import PDFDownloadTask, PageSelection
from epo_ops_client.config import OPSConfig


def _minimal_pdf_bytes(num_pages: int = 1) -> bytes:
    """
    Generate a minimal valid single-page PDF as bytes.
    Uses the pypdf library so merge tests are realistic.
    """
    try:
        from pypdf import PdfWriter
    except ImportError:
        pytest.skip("pypdf not installed")

    writer = PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=595, height=842)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _make_config(tmp_path: Path) -> OPSConfig:
    return OPSConfig(
        output_dir=tmp_path / "output",
        log_file_path=tmp_path / "log.csv",
    )


class TestFetchPageURL:
    """Verify that _fetch_page uses ?Range=N as a query param, not an HTTP Range header."""

    def test_range_is_query_param_not_header(self, tmp_path: Path):
        from epo_ops_client.application.pdf_downloader import PDFPageDownloader
        from epo_ops_client.infrastructure.rate_limiter import RateLimiter
        from epo_ops_client.infrastructure.retry_policy import RetryPolicy

        config = _make_config(tmp_path)
        auth = MagicMock()
        auth.get_valid_token.return_value = "tok"

        captured_urls: list[str] = []
        captured_headers: list[dict] = []

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = _minimal_pdf_bytes()

        def mock_get(url, *, headers, timeout):
            captured_urls.append(url)
            captured_headers.append(dict(headers))
            return mock_response

        session = MagicMock()
        session.get.side_effect = mock_get

        downloader = PDFPageDownloader(
            config=config,
            auth_client=auth,
            rate_limiter=RateLimiter(max_requests_per_second=0),
            retry_policy=RetryPolicy(max_attempts=3),
            output_dir=config.output_dir,
        )

        task = PDFDownloadTask(
            country="EP", pub="1000000", kind="A1",
            page_selection=PageSelection.first_page(),
        )
        downloader._fetch_page(task=task, page_number=3, session=session)

        assert len(captured_urls) == 1
        url = captured_urls[0]
        assert "?Range=3" in url, f"Expected ?Range=3 in URL, got: {url}"
        # Must NOT be an HTTP Range header
        assert "Range" not in captured_headers[0], (
            f"Range should be a query param, not a header. Headers: {captured_headers[0]}"
        )


class TestMergePages:
    def test_merge_two_pages_produces_two_page_pdf(self, tmp_path: Path):
        from epo_ops_client.application.pdf_downloader import PDFPageDownloader
        from pypdf import PdfReader

        output_path = tmp_path / "merged.pdf"
        page1 = _minimal_pdf_bytes(1)
        page2 = _minimal_pdf_bytes(1)

        PDFPageDownloader._merge_pages([page1, page2], output_path)

        assert output_path.exists()
        reader = PdfReader(output_path)
        assert len(reader.pages) == 2

    def test_merge_writes_atomically(self, tmp_path: Path):
        """No .tmp.pdf file should remain after a successful merge."""
        from epo_ops_client.application.pdf_downloader import PDFPageDownloader

        output_path = tmp_path / "merged.pdf"
        PDFPageDownloader._merge_pages([_minimal_pdf_bytes()], output_path)

        tmp_leftovers = list(tmp_path.glob("*.tmp.pdf"))
        assert not tmp_leftovers, f"Temp files left behind: {tmp_leftovers}"


class TestDownloadFirstPage:
    def test_download_first_page_creates_file(self, tmp_path: Path):
        from epo_ops_client.application.pdf_downloader import PDFPageDownloader
        from epo_ops_client.infrastructure.rate_limiter import RateLimiter
        from epo_ops_client.infrastructure.retry_policy import RetryPolicy

        config = _make_config(tmp_path)
        auth = MagicMock()
        auth.get_valid_token.return_value = "tok"

        pdf_bytes = _minimal_pdf_bytes()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = pdf_bytes
        session = MagicMock()
        session.get.return_value = mock_response

        downloader = PDFPageDownloader(
            config=config,
            auth_client=auth,
            rate_limiter=RateLimiter(max_requests_per_second=0),
            retry_policy=RetryPolicy(max_attempts=3),
            output_dir=config.output_dir,
        )

        task = PDFDownloadTask(
            country="EP", pub="1000000", kind="A1",
            page_selection=PageSelection.first_page(),
        )
        result = downloader.download(task, session=session)

        assert result.is_successful
        assert result.download_status == "downloaded"
        assert result.output_file_path.exists()
        assert result.bytes_written > 0
