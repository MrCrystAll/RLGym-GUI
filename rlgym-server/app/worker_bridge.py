import itertools
import json
import queue
import subprocess
import sys
import threading
from pathlib import Path

from . import config


class WorkerError(Exception):
    pass


class Worker:
    def __init__(self, script: Path, timeout: float | None = None):
        self.script = script
        self.timeout = config.WORKER_TIMEOUT if timeout is None else timeout
        self._proc = None
        self._python = None
        self._log = None
        self._lines = None
        self._lock = threading.Lock()
        self._ids = itertools.count(1)

    def _ensure(self, python: str):
        if self._proc and self._proc.poll() is None and self._python == python:
            return
        self.stop()
        data_dir = Path(config.DATA_DIR)
        data_dir.mkdir(parents=True, exist_ok=True)      # e.g. ./data on a fresh dev checkout
        self._log = open(data_dir / "worker.log", "a", encoding="utf-8")
        try:
            self._proc = subprocess.Popen(
                [python, "-u", str(self.script)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._log,
                text=True, encoding="utf-8",
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
        except OSError as exc:
            self.stop()
            raise WorkerError(f"Cannot start '{python}': {exc}") from exc
        self._python = python
        self._lines = queue.Queue()
        threading.Thread(target=_read_lines, args=(self._proc.stdout, self._lines), daemon=True).start()

    def call(self, python: str, method: str, params: dict | None = None, timeout: float | None = None):
        timeout = self.timeout if timeout is None else timeout
        with self._lock:
            self._ensure(python)
            req = {"id": next(self._ids), "method": method, "params": params or {}}
            try:
                self._proc.stdin.write(json.dumps(req) + "\n")
                self._proc.stdin.flush()
                line = self._lines.get(timeout=timeout)
            except OSError:                              # broken pipe: it died before reading
                line = None
            except queue.Empty:
                # User code is stuck (heavy import, input(), infinite loop...). Kill it so the
                # lock is released; the next call starts a fresh worker.
                self.stop()
                raise WorkerError(
                    f"The worker didn't answer '{method}' within {timeout:g}s and was stopped "
                    "(see worker.log)"
                ) from None
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
            self._proc.wait()
        self._proc = None
        if self._log:
            self._log.close()
            self._log = None


# readline() on a pipe can't time out (and select() doesn't work on Windows pipes), so a thread
# reads the worker's stdout and call() waits on the queue with a timeout instead.
def _read_lines(stream, lines: queue.Queue):
    try:
        for line in stream:
            lines.put(line)
    except (OSError, ValueError):                        # pipe closed under us by stop()
        pass
    lines.put(None)                                      # EOF: the worker exited
