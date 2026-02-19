from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DownloadTask:
    """A single OPS image request (publication + kind + country)."""
    pub_number: str          # e.g. "0884389"
    kind: str                # e.g. "A1"
    country: str = "EP"      # e.g. "EP" (default), "US", "WO", etc.