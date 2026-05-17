from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OPSConfig:
    """
    Immutable runtime configuration for downloading data from EPO OPS.

    This configuration is intended for sequential execution.
    Throttling is enforced by sleeping between requests based on
    max_requests_per_second.
    """

    # Filesystem
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

    def published_data_url_template(self) -> str:
        """
        Returns the OPS URL template for published-data retrieval.

        Template placeholders:
            {identifier_type} - one of docdb or epodoc
            {pub_id}          - publication ID, e.g. EP1000000A1
            {data_type}       - biblio, abstract, full-cycle, fulltext, description, claims, equivalents, or images
        """
        return (
            f"{self.ops_api_base_url}"
            "rest-services/published-data/publication/{identifier_type}/{pub_id}/{data_type}"
        )
    
    def pdf_image_url_template(self) -> str:
        """
        Returns the OPS URL template for PDF image retrieval (one page at a time).

        Template placeholders:
            {country} - country code, e.g. EP
            {pub_num}     - publication number, e.g. 1000000
            {kind}    - kind code, e.g. A1

        Append ?Range={page_number} to select a specific page (1-based).
        Example: .../EP/1000000/A1/fullimage?Range=1
        """
        return (
            f"{self.ops_api_base_url}"
            "rest-services/published-data/images/{country}/{pub_num}/{kind}/fullimage"
        )

    def images_metadata_url_template(self) -> str:
        """
        Returns the OPS URL template for image metadata (total page count, etc.).

        Template placeholders:
            {identifier_type} - one of docdb or epodoc
            {pub_id}          - publication ID formatted for the identifier type
                                e.g. for epodoc: EP1000000A1

        Example: .../publication/epodoc/EP1000000A1/images
        """
        return (
            f"{self.ops_api_base_url}"
            "rest-services/published-data/publication/{identifier_type}/{pub_id}/images"
        )