from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OPSFirstPageDownloaderConfig:
    """
    Immutable runtime configuration for downloading first-page PDFs
    from the EPO OPS Published Data Images endpoint.

    This is a pure configuration object to enable:
    - Dependency injection
    - Testability
    - Reproducibility
    """
    
    # OPS API
    ops_api_base_url: str = "https://ops.epo.org/3.2"
    default_country_code: str = "EP"

    #Filesystem
    output_dir: Path = Path("data/front_pages")
    log_file_path: Path = Path("data/front_pages/download_log.csv")

    # Concurrency + throttling
    max_workers: int = 1
    max_requests_per_second: float = 1.0
    batch_size: int = 100

    # Network timeouts
    http_request_timeout_seconds: int = 90
    token_request_timeout_seconds: int = 30

    # Retry policy
    max_retry_attempts: int = 7

    # OPS-specific image header value
    ops_image_range_header_value: str = "1"

    def image_url_template(self) -> str:
        """
        Returns the OPS template URL for full-image PDF retrieval.

        Template placeholders:
            {country} - publication country code (e.g., EP)
            {pub}     - publication number
            {kind}    - kind code (e.g., A1, B1)
        """
        return self.ops_api_base_url + "/rest-services/published-data/images/{country}/{pub}/{kind}/fullimage.pdf"
