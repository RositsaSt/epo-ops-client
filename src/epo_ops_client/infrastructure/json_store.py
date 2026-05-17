from __future__ import annotations

import json
from pathlib import Path

from ..domain.models import DownloadTask

class JsonResponseStore:
    """
    File store for persisting OPS responses as JSON.

    Responsibility
    --------------
    - Decide output path for a task
    - Skip if already present (optional policy)
    - Write JSON to disk atomically (temp file -> rename)
    """

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir   
    
    def output_path_for(self, task: DownloadTask) -> Path:
        """
        Compute the destination path for a task.
        """
        return self._output_dir / f"{task.pub_id}_{task.data_type.value}.json"

    def is_already_downloaded(self, path: Path, *, min_bytes: int = 1024) -> bool:
        """
        Decide whether an existing file counts as already downloaded.
        """
        return path.exists() and path.stat().st_size >= min_bytes
    
    
    def write_json_atomic(self, path: Path, payload: object) -> int:
        """
        Write a JSON-serializable payload to disk atomically.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        tmp_path.write_text(text, encoding="utf-8")
        tmp_path.replace(path)
        return path.stat().st_size
    
    def write_bytes_atomic(self, path: Path, content: bytes) -> int:
        """
        Write raw bytes to disk atomically.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_bytes(content)
        tmp_path.replace(path)
        return path.stat().st_size
