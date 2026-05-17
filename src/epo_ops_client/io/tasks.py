from __future__ import annotations

import csv
from pathlib import Path

from ..domain.models import (
    DownloadTask,
    OPSIdentifierType,
    OPSDataType,
    PDFDownloadTask,
    PageSelection,
)


def load_download_tasks_from_csv(
    csv_file_path: str | Path,
    *,
    data_type: OPSDataType,
    identifier_type: OPSIdentifierType = OPSIdentifierType.DOCDB,
    pub_id_col: str = "pub_id",
) -> list[DownloadTask]:
    """
    Load JSON endpoint download tasks from a CSV file.

    Expected CSV columns (by default):
        pub_id  — publication identifier (required)

    Parameters
    ----------
    csv_file_path:
        Path to the CSV file.
    data_type:
        The OPS data type to request (biblio, abstract, claims, etc.).
    identifier_type:
        docdb (default) or epodoc.
    pub_id_col:
        Column name for the publication ID (default: "pub_id").
    """
    csv_file_path = Path(csv_file_path)
    tasks: list[DownloadTask] = []
    with csv_file_path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            pub_id = row[pub_id_col].strip()
            if pub_id:
                tasks.append(DownloadTask(
                    pub_id=pub_id,
                    data_type=data_type,
                    identifier_type=identifier_type,
                ))
    return tasks


def load_pdf_tasks_from_csv(
    csv_file_path: str | Path,
    page_selection: PageSelection,
    *,
    country_col: str = "country",
    pub_col: str = "pub_number",
    kind_col: str = "kind",
    default_country: str = "EP",
) -> list[PDFDownloadTask]:
    """
    Load PDF download tasks from a CSV file.

    Expected CSV columns (by default):
        pub_number  — publication number without kind code (required), e.g. 1000000
        kind        — kind code (required), e.g. A1
        country     — country code (optional, defaults to `default_country`), e.g. EP

    Parameters
    ----------
    csv_file_path:
        Path to the CSV file.
    page_selection:
        Which pages to download for every task (first, all, or a range).
        Use PageSelection.first_page(), .all_pages(), or .page_range(start, end).
    country_col:
        Column name for the country code (default: "country").
    pub_col:
        Column name for the publication number (default: "pub_number").
    kind_col:
        Column name for the kind code (default: "kind").
    default_country:
        Fallback country code when the country column is absent or empty (default: "EP").
    """
    csv_file_path = Path(csv_file_path)
    tasks: list[PDFDownloadTask] = []
    with csv_file_path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            pub = row[pub_col].strip()
            kind = row[kind_col].strip()
            country = (row.get(country_col) or "").strip() or default_country
            if pub and kind:
                tasks.append(PDFDownloadTask(
                    country=country,
                    pub=pub,
                    kind=kind,
                    page_selection=page_selection,
                ))
    return tasks
