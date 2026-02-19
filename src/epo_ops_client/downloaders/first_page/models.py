from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DownloadTask:
    """
    Represents a single OPS image download request.

    Identifies a specific patent publication image via:
    - country (e.g., "EP")
    - pub_number (e.g., "0884389")
    - kind (e.g., "A1")
    """
    pub_number: str
    kind: str
    country: str = "EP"