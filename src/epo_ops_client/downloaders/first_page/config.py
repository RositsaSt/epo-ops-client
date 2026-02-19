from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DownloaderConfig:
    """
    Runtime configuration for OPS first-page downloads.

    Keep this as a pure data object to make testing/config injection easy.
    """
    base_url: str = "https://ops.epo.org/3.2"
    country_default: str = "EP"

    out_dir: Path = Path("front_pages")
    log_path: Path = Path("download_log.csv")

    # Concurrency + throttling
    workers: int = 1
    rate_per_sec: float = 1.0
    chunk_size: int = 100

    # Network
    request_timeout_s: int = 90
    token_timeout_s: int = 30

    # Retries
    max_attempts: int = 7

    # OPS-specific: Range header value you were using
    range_header_value: str = "1"

    def image_url_template(self) -> str:
        return self.base_url + "/rest-services/published-data/images/{country}/{pub}/{kind}/fullimage.pdf"
