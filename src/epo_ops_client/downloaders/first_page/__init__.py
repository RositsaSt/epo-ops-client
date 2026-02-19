"""
EPO OPS Patent First Page Downloader.

Download first-page PDFs from EPO OPS for a list of publication numbers + kind codes.
"""

__all__ = [
    "OPSFirstPageDownloaderConfig",
    "DownloadTask",
    "OPSAuthClient",
    "RateLimiter",
    "ThreadSafeCsvDownloadLogger",
    "download_many",
    "load_download_tasks_from_csv",
]

__version__ = "0.1.0"

from .config import OPSFirstPageDownloaderConfig
from .models import DownloadTask
from .auth import OPSAuthClient
from .rate_limiter import RateLimiter
from .logging_csv import ThreadSafeCsvDownloadLogger
from .downloader import download_many
from .io_tasks import load_download_tasks_from_csv
