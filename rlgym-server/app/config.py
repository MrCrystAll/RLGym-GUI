import os

PORT = int(os.environ.get("RLGYM_GUI_PORT", 8000))
TOKEN = os.environ.get("RLGYM_GUI_TOKEN", "dev-token")
DATA_DIR = os.environ.get("RLGYM_GUI_DATA_DIR", "./data")
VERSION = os.environ.get("RLGYM_GUI_VERSION", "0.0.1")