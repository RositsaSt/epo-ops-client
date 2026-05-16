from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OPSConfig:
    """
    Immutable runtime configuration for downloading data from EPO OPS.

    Note: This configuration is for sequential execution (no threading).
    Throttling is enforced by sleeping between requests based on max_requests_per_second.
    """
    #Filesystem
    output_dir: Path
    log_file_path: Path
    
    # OPS API
    ops_api_base_url: str = "https://ops.epo.org/3.2/"

    # Throttling
    max_requests_per_second: float = 1.0

    # Network timeouts
    http_request_timeout_seconds: int = 90
    token_request_timeout_seconds: int = 30

    # Retry policy
    max_retry_attempts: int = 5
    
    def url_template(self) -> str:
        """
        Returns the OPS template URL for abstract retrieval.

        Template placeholders:
            {pud_id} - publication id incl. country, bublication number and kind code (e.g., EP1000000A1)
            {type}   - one of docdb or epodoc
        """
        return self.ops_api_base_url + "/rest-services/published-data/publication/{identifier_type}/{pub_id}/{data_type}"