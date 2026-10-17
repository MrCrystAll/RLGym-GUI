"""Drive the Python worker through app.worker_bridge, exactly as the API does.

    <rlgym-server>/.venv/Scripts/python.exe worker-smoke.py [module ...]

Defaults to a bundled sample module (sample_components.py). Pass real module names to discover
those instead, e.g. rlgym.rocket_league.reward_functions (needs `rlgym[rl]` in that interpreter).
Set WORKER_PYTHON to run the worker under a different interpreter than this one.
"""
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SERVER = HERE.parents[3] / "rlgym-server"
data_dir = Path(tempfile.gettempdir()) / "rlgym-run" / "data"
data_dir.mkdir(parents=True, exist_ok=True)  # worker_bridge does not create it (RLGYM-10)
os.environ.setdefault("RLGYM_GUI_DATA_DIR", str(data_dir))
os.environ["PYTHONPATH"] = os.pathsep.join(filter(None, [str(HERE), os.environ.get("PYTHONPATH")]))
sys.path.insert(0, str(SERVER))

from app.worker_bridge import Worker, WorkerError  # noqa: E402

python = os.environ.get("WORKER_PYTHON", sys.executable)
modules = sys.argv[1:] or ["sample_components"]
worker = Worker(SERVER / "worker" / "worker.py")
try:
    print("info     ->", worker.call(python, "info"))
    result = worker.call(python, "discover", {"modules": modules})
    print(f"discover -> {len(result['components'])} components from {modules}")
    for c in result["components"]:
        params = ", ".join(f"{p['name']}: {p['type']}" + ("" if p["required"] else f" = {p['default']}") for p in c["params"])
        print(f"  {c['kind']:<20} {c['qualified_name']}({params})")
    for e in result["errors"]:
        print(f"  ERROR {e['module']}: {e['message']}")
except WorkerError as exc:
    print("WorkerError:", exc)
finally:
    worker.stop()
log = data_dir / "worker.log"
print(f"--- worker.log ({log}), last lines:")
print("".join(log.read_text(encoding="utf-8").splitlines(keepends=True)[-10:]) if log.exists() else "(empty)")
