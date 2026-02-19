from __future__ import annotations

import csv
from pathlib import Path

from .models import DownloadTask


def tasks_from_csv(
    path: str | Path,
    *,
    pub_col: str = "pub_number",
    kind_col: str = "kind",
    country_col: str | None = None,
    default_country: str = "EP",
) -> list[DownloadTask]:
    """
    Load tasks from a CSV.

    Expected columns by default:
      pub_number, kind
    Optionally:
      country
    """
    path = Path(path)
    tasks: list[DownloadTask] = []

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pub_number = row[pub_col].strip()
            kind = row[kind_col].strip().upper()
            country = row[country_col].strip().upper() if country_col else default_country
            tasks.append(DownloadTask(pub_number=pub_number, kind=kind, country=country))

    return tasks
