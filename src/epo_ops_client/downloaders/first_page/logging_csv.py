from __future__ import annotations

import csv
import threading
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DownloadLogEntry:
    timestamp: str
    country: str
    pub_number: str
    kind: str
    download_status: str        # downloaded / skipped / failed
    http_status_code: int
    bytes_written: int
    status_message: str
    output_file_path: str


class ThreadSafeCsvDownloadLogger:
    """
    Thread-safe append-only CSV logger for download runs.
    """
    _csv_header_columns = ["timestamp", "country", "pub_number", "kind", 
                           "download_status", "http_status_code", "bytes_written", 
                           "status_message", "output_file_path"]

    def __init__(self, log_file_path: Path) -> None:
        self._log_file_path = log_file_path
        self._write_lock = threading.Lock()

    def init_if_missing(self) -> None:
        """
        Creates the CSV file and writes the header if it does not exist.
        """
        if self._log_file_path.exists():
            return
        
        self._log_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with self._log_file_path.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(self._csv_header_columns)

    def append_row(self, log_entry: DownloadLogEntry) -> None:
        """
        Appends a single log entry in a thread-safe manner.
        """
        with self._write_lock:
            with self._log_file_path.open("a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow([
                    log_entry.timestamp, log_entry.country, log_entry.pub_number, log_entry.kind,
                    log_entry.download_status, log_entry.http_status_code, log_entry.bytes_written, 
                    log_entry.status_message, log_entry.output_file_path
                ])

    @staticmethod
    def current_timestamp_string() -> str:
        """
        Returns the current UTC timestamp formatted for logging.
        """
        return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
