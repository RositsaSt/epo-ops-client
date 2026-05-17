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
    IMAGES = "images"
    
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
    so the caller can log outcomes uniformly. Works for both JSON (DownloadTask)
    and PDF (PDFDownloadTask) downloads — the download_task field holds whichever
    task type was executed.

    Fields
    ------
    download_task:
        The original task object (DownloadTask or PDFDownloadTask).
    pub_id:
        Human-readable identifier for logging (e.g. pub_id or country+pub+kind).
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
        Path of the output file (even for skipped/failed outcomes).
    """
    download_task: DownloadTask | PDFDownloadTask
    pub_id: str                     # human-readable id for logging
    is_successful: bool
    download_status: str            # downloaded / skipped / failed
    http_status_code: int
    bytes_written: int
    status_message: str
    output_file_path: Path

@dataclass(frozen=True)
class PageSelection:
    """
    Represents which pages to download for a given publication.
    
    Modes:
    - kind = "first": download only the first page (for quick checks or when fulltext is not needed)
    - kind = "all": download all pages (for comprehensive data retrieval)
    - kind = "range": download a specific range of pages (e.g. pages 1-5) - between start (inclusive) and end (inclusive)
    """
    kind: str
    start: int | None = None
    end: int | None = None

    @staticmethod
    def first_page() -> PageSelection:
        return PageSelection(kind="first", start=1, end=1)
    
    @staticmethod
    def all_pages() -> PageSelection:
        return PageSelection(kind="all", start=None, end=None)
    
    @staticmethod
    def page_range(start: int, end: int) -> PageSelection:
        if start < 1 or end < start:
            raise ValueError("Invalid page range: start must be >= 1 and end must be >= start")
        return PageSelection(kind="range", start=start, end=end)
    
@dataclass(frozen=True)
class PDFDownloadTask:
    """
    Represents a task to download a PDF image from OPS.

    Fields
    ------
    country: str
        The country code of the publication (e.g. "EP").
    pub_num: str
        The publication number without kind code (e.g. "1000000").
    kind: str
        The kind code of the publication (e.g. "A1").
    page_selection: PageSelection
        Which pages to download (first, all, or a specific range). Default is first page only.
    """
    country: str
    pub_num: str
    kind: str
    page_selection: PageSelection = PageSelection.first_page()

    def output_base_filename(self, total_pages: int | None = None) -> str:
        """
        Generates a base filename for the downloaded PDF based on the publication details and page selection.

        Examples:
        - For country="EP", pub_num="1000000", kind="A1", and first page selection, returns "EP1000000A1_page1"
        - For all pages selection, returns "EP1000000A1_all_pages"
        - For a range of pages (e.g. 1-5), returns "EP1000000A1_pages_1-5"
        """
        base_name = f"{self.country}{self.pub_num}{self.kind}"
        if self.page_selection.kind == "first":
            return f"{base_name}_page1"
        elif self.page_selection.kind == "all":
            if total_pages is not None:
                return f"{base_name}_pages_1-{total_pages}"
        elif self.page_selection.kind == "range" and self.page_selection.start and self.page_selection.end:
            return f"{base_name}_pages_{self.page_selection.start}-{self.page_selection.end}"
        else:
            raise ValueError(f"Unknown page selection kind: {self.page_selection.kind}")
