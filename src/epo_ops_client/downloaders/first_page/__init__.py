"""
EPO OPS Patent First Page Downloader.

Download first-page PDFs from EPO OPS for a list of publication numbers + kind codes.
"""

__all__ = [
    "DownloaderConfig",
    "DownloadTask",
    "OPSAuthClient",
    "RateLimiter",
    "CsvRunLog",
    "download_many",
    "tasks_from_csv",
]

__version__ = "0.1.0"

from .config import DownloaderConfig
from .models import DownloadTask
from .auth import OPSAuthClient
from .rate_limiter import RateLimiter
from .logging_csv import CsvRunLog
from .downloader import download_many
from .io_tasks import tasks_from_csv
