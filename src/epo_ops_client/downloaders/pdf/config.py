from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class OPSPdfDownloaderConfig:
    ops_api_base_url: str = "https://ops.epo.org/3.2"
    output_dir: Path = Path("data")
    log_file_path: Path = Path("data/download_log.csv")
    max_workers: int = 1
    max_requests_per_second: float = 1.0
    batch_size: int = 100
    http_request_timeout_seconds: int = 90
    token_request_timeout_seconds: int = 30
    max_retry_attempts: int = 7
    ops_image_range_header_value: str = "1"

    def image_url_template(self) -> str:
        return self.ops_api_base_url + "/rest-services/published-data/images/{country}/{pub}/{kind}/fullimage.pdf"