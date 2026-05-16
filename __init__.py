"""
EPO OPS Abstract Downloader.

Download the abstract from EPO OPS for a list of publication ids.
"""

__all__ = [
    "OPSConfig",
    "DownloadTask",
    "DownloadResult",
    "OPSAuthClient",
    "RateLimiter",
    "DownloadLogger",
    "fetch_and_store_abstracts",
    "load_download_tasks_from_csv",
]

__version__ = "0.1.0"

from .config import OPSConfig
from .domain.models import DownloadTask, DownloadResult
from .infrastructure.auth import OPSAuthClient
from .infrastructure.rate_limiter import RateLimiter
from .io.logging_csv import DownloadLogger
from .application.bulk_downloader import fetch_and_store_abstracts
from .io.io_tasks import load_download_tasks_from_csv