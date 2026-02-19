from __future__ import annotations

import csv
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class LogRow:
    ts: str
    country: str
    pub_number: str
    kind: str
    status: str        # downloaded / skipped / failed
    http_status: int
    bytes_written: int
    message: str
    out_path: str


class CsvRunLog:
    """
    Thread-safe append-only CSV logger.
    """
    _header = ["ts", "country", "pub_number", "kind", "status", "http_status", "bytes", "message", "out_path"]

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()

    def init_if_missing(self) -> None:
        if self._path.exists():
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(self._header)

    def append(self, row: LogRow) -> None:
        with self._lock:
            with self._path.open("a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow([
                    row.ts, row.country, row.pub_number, row.kind,
                    row.status, row.http_status, row.bytes_written, row.message, row.out_path
                ])

    @staticmethod
    def now_ts() -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S")
