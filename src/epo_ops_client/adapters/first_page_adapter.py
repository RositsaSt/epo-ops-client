from future import annotations

from ..downloaders.first_page.models import DownloadTask as LegacyFirstPageTask
from ..domain.models import PDFDownloadTask, PageSelection
from pathlib import Path

def map_first_page_task_to_pdf_download_task(legacy: LegacyFirstPageTask, *, pages: PageSelection | None = None) -> PDFDownloadTask:
    """
    Maps a legacy DownloadTask (which only contains publication ID and data type) to a PDFDownloadTask
    with page selection set to first page only.

    If pages is provided it overrides the default 'first' selection.

    This adapter allows us to reuse the existing task generation logic while transitioning to the new
    PDF download approach.
    """
    selection = pages or PageSelection.first_page()

    return PDFDownloadTask(
        country=legacy.country,
        pub=legacy.pub_number,
        kind=legacy.kind,
        pages=selection
    )

def format_pdf_output_path(output_dir: Path, pdf_task: PDFDownloadTask, extension: str = ".pdf") -> Path:
    """
    Formats the output file path for a given PDFDownloadTask.
    """
    basename = pdf_task.output_base_filename()
    return output_dir / f"{basename}.{extension}"