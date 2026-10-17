import sys
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"

# Make `app` importable without installing the server as a package.
sys.path.insert(0, str(SERVER_DIR))
