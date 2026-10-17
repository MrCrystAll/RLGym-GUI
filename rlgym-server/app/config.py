import os
import sys
from pathlib import Path

PORT = int(os.environ.get("RLGYM_GUI_PORT", 8000))
TOKEN = os.environ.get("RLGYM_GUI_TOKEN", "dev-token")
DATA_DIR = os.environ.get("RLGYM_GUI_DATA_DIR", "./data")
VERSION = os.environ.get("RLGYM_GUI_VERSION", "0.0.1")


def worker_script() -> Path:
    """worker.py runs in the user's interpreter, so it ships as a plain file, not frozen code.
    Frozen (PyInstaller): bundled under sys._MEIPASS/worker/. From source: rlgym-server/worker/."""
    root = getattr(sys, "_MEIPASS", None) or Path(__file__).resolve().parent.parent
    return Path(root) / "worker" / "worker.py"