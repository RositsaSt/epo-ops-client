from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from enum import Enum

class OPSIdentifierType(str, Enum):
    """
    Valid identifier types supported by EPO OPS.
    """
    DOCDB = "docdb"
    EPODOC = "epodoc"
    
class OPSDataType(str, Enum):
    """
    Valid data types supported by EPO OPS.
    """
    BIBLIO = "biblio"
    ABSTRACT = "abstract"
    FULL_CYCLE = "full-cycle"
    FULLTEXT = "fulltext"
    DESCRIPTION = "description"
    CLAIMS = "claims"
    EQUIVALENTS = "equivalents"
    
@dataclass(frozen=True)
class DownloadTask:
    """
    Immutable value object representing a single OPS download request.

    A DownloadTask encapsulates the minimal unit of work for the
    abstract downloader pipeline.
    """
    pub_id: str
    data_type: OPSDataType
    identifier_type: OPSIdentifierType = OPSIdentifierType.DOCDB

    
@dataclass(frozen=True)
class DownloadResult:
    """
    Value object describing the outcome of a single download attempt.

    This result is returned by the downloader regardless of success/failure,
    so the caller can log outcomes uniformly.

    Fields
    ------
    download_task:
        The requested publication identifier and identifier type (docdb/epodoc).
    is_successful:
        True when the operation produced a usable file OR was intentionally skipped.
    download_status:
        One of {"downloaded", "skipped", "failed"}.
    http_status_code:
        HTTP status code received from OPS (0 if the request never reached the server).
    bytes_written:
        How many bytes were written to disk (0 on failure).
    status_message:
        Short, human-readable explanation of what happened (for logs/debugging).
    output_file_path:
        Path of the JSON file (even for skipped/failed outcomes).
    """
    download_task: DownloadTask
    is_successful: bool
    download_status: str            # downloaded / skipped / failed
    http_status_code: int
    bytes_written: int
    status_message: str
    output_file_path: Path