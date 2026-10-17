import itertools
import json
import subprocess
import sys
import threading
from pathlib import Path

from . import config


class WorkerError(Exception):
    pass


class Worker:
    def __init__(self, script: Path):
        self.script = script
        self._proc = None
        self._python = None
        self._lock = threading.Lock()
        self._ids = itertools.count(1)

    def _ensure(self, python: str):
        if self._proc and self._proc.poll() is None and self._python == python:
            return
        self.stop()
        log = open(Path(config.DATA_DIR) / "worker.log", "a", encoding="utf-8")
        try:
            self._proc = subprocess.Popen(
                [python, "-u", str(self.script)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log,
                text=True, encoding="utf-8",
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
        except OSError as exc:
            raise WorkerError(f"Cannot start '{python}': {exc}") from exc
        self._python = python

    def call(self, python: str, method: str, params: dict | None = None):
        with self._lock:
            self._ensure(python)
            req = {"id": next(self._ids), "method": method, "params": params or {}}
            self._proc.stdin.write(json.dumps(req) + "\n")
            self._proc.stdin.flush()
            line = self._proc.stdout.readline()
            if not line:
                self.stop()
                raise WorkerError("The worker exited unexpectedly (see worker.log)")
            resp = json.loads(line)
        if "error" in resp:
            raise WorkerError(resp["error"])
        return resp["result"]

    def stop(self):
        if self._proc and self._proc.poll() is None:
            self._proc.kill()
        self._proc = None