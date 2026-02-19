from __future__ import annotations

import csv
from pathlib import Path

from .models import DownloadTask


def load_download_tasks_from_csv(
    csv_file_path: str | Path,
    *,
    pub_col: str = "pub_number",
    kind_col: str = "kind",
    country_col: str | None = None,
    default_country: str = "EP",
) -> list[DownloadTask]:
  """
  Loads download tasks from a CSV file.
  
  Expected columns by default:
    - pub_number
    - kind
    
  Optional COLUMN:
    - country
  """
  csv_file_path = Path(csv_file_path)
  download_tasks: list[DownloadTask] = []
  
  with csv_file_path.open("r", encoding="utf-8", newline="") as f:
      csv_reader = csv.DictReader(f)
      
      for row in csv_reader:
          pub_number = row[pub_col].strip()
          kind = row[kind_col].strip().upper()
          country = row[country_col].strip().upper() if country_col else default_country
          
          download_tasks.append(DownloadTask(pub_number=pub_number, kind=kind, country=country))
          
  return download_tasks
