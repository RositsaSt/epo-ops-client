"""
Tests for DownloadLogger thread safety and resume logic.
"""
from __future__ import annotations

import csv
import threading
from pathlib import Path

import pytest

from epo_ops_client.io.logger import DownloadLogger, DownloadLogEntry


def _make_entry(pub_id: str, status: str = "downloaded", path: str = "/out/x.json") -> DownloadLogEntry:
    return DownloadLogEntry(
        timestamp="2026-01-01 00:00:00",
        pub_id=pub_id,
        download_status=status,
        http_status_code=200 if status == "downloaded" else 0,
        status_message="ok",
        output_file_path=path,
    )


class TestDownloadLoggerThreadSafety:
    def test_concurrent_append_no_corruption(self, tmp_path: Path):
        """
        20 threads each append 5 rows concurrently.
        The resulting CSV must have exactly 100 data rows with no partial writes.
        """
        log_path = tmp_path / "log.csv"
        logger = DownloadLogger(log_path)
        logger.init_if_missing()

        errors: list[Exception] = []

        def worker(thread_id: int):
            for i in range(5):
                try:
                    logger.append_row(_make_entry(f"pub-{thread_id}-{i}"))
                except Exception as exc:
                    errors.append(exc)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors

        with log_path.open("r", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        assert len(rows) == 100, f"Expected 100 rows, got {len(rows)}"
        # Every row must have all required fields
        required = {"timestamp", "pub_id", "download_status", "http_status_code",
                    "status_message", "output_file_path"}
        for row in rows:
            assert required.issubset(row.keys()), f"Missing fields in row: {row}"


class TestLoadCompletedOutputPaths:
    def test_returns_empty_set_when_log_missing(self, tmp_path: Path):
        logger = DownloadLogger(tmp_path / "nonexistent.csv")
        assert logger.load_completed_output_paths() == set()

    def test_returns_only_downloaded_paths(self, tmp_path: Path):
        log_path = tmp_path / "log.csv"
        logger = DownloadLogger(log_path)
        logger.init_if_missing()

        logger.append_row(_make_entry("A", status="downloaded", path="/out/a.json"))
        logger.append_row(_make_entry("B", status="failed", path="/out/b.json"))
        logger.append_row(_make_entry("C", status="skipped", path="/out/c.json"))
        logger.append_row(_make_entry("D", status="downloaded", path="/out/d.json"))

        completed = logger.load_completed_output_paths()
        assert completed == {"/out/a.json", "/out/d.json"}

    def test_resume_skips_already_completed(self, tmp_path: Path):
        """Simulate restart: completed paths from log are excluded from pending."""
        log_path = tmp_path / "log.csv"
        logger = DownloadLogger(log_path)
        logger.init_if_missing()
        logger.append_row(_make_entry("EP1000000A1", path="/out/EP1000000A1.json"))

        completed = logger.load_completed_output_paths()
        all_paths = ["/out/EP1000000A1.json", "/out/EP2000000A1.json"]
        pending = [p for p in all_paths if p not in completed]

        assert pending == ["/out/EP2000000A1.json"]
