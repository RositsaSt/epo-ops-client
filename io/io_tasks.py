from __future__ import annotations

import csv
from pathlib import Path

from ..domain.models import DownloadTask, OPSIdentifierType, OPSDataType


def load_download_tasks_from_csv(
    csv_file_path: str | Path,
    identifier_type: OPSIdentifierType,
    data_type: OPSDataType,
    *,
    pub_id_col: str = "pub_id",
) -> list[DownloadTask]:
  """
  Loads download tasks from a CSV file.
  
  Expected columns by default:
    - pub_id
  """
  csv_file_path = Path(csv_file_path)
  download_tasks: list[DownloadTask] = []
  
  with csv_file_path.open("r", encoding="utf-8", newline="") as f:
      csv_reader = csv.DictReader(f)
      
      for row in csv_reader:
          pub_id = row[pub_id_col].strip()

          download_tasks.append(DownloadTask(pub_id=pub_id, identifier_type=identifier_type, data_type=data_type))
          
  return download_tasks
