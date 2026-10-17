"""Write the FastAPI schema to rlgym-server/openapi.json, the input of the Angular client generator."""
import json
import os
import sys
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_DIR))
# Pin the version so the committed file doesn't change with RLGYM_GUI_VERSION.
os.environ["RLGYM_GUI_VERSION"] = "0.0.0"

from app.api import app  # noqa: E402

out = SERVER_DIR / "openapi.json"
schema = app.openapi()
# Compare parsed JSON so line-ending conversion by git doesn't count as a change.
if not out.exists() or json.loads(out.read_text(encoding="utf-8")) != schema:
    out.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Updated {out}")
