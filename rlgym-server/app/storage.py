"""Small helpers for the JSON files kept under DATA_DIR."""
import os
from pathlib import Path


def write_text_atomic(path: Path, text: str) -> None:
    """Write then rename, so a crash mid-write never leaves a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
