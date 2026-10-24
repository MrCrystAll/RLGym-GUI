"""Worker protocol tests: app.worker_bridge drives worker/worker.py in a real subprocess."""
import sys
from pathlib import Path

import pytest

from app import config
from app.worker_bridge import Worker, WorkerError
from conftest import FIXTURES, SERVER_DIR

PYTHON = sys.executable
WORKER_SCRIPT = config.worker_script()


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    # The worker inherits the environment, so this is how it finds the fixture modules.
    monkeypatch.setenv("PYTHONPATH", str(FIXTURES))
    return tmp_path


@pytest.fixture
def worker(data_dir):
    w = Worker(WORKER_SCRIPT)
    yield w
    w.stop()


def test_worker_script_from_source():
    assert WORKER_SCRIPT == SERVER_DIR / "worker" / "worker.py"
    assert WORKER_SCRIPT.is_file()


def test_worker_script_when_frozen(tmp_path, monkeypatch):
    # PyInstaller sets sys._MEIPASS to the bundle's data folder (_internal/ in onedir builds).
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert config.worker_script() == tmp_path / "worker" / "worker.py"


def test_info(worker):
    result = worker.call(PYTHON, "info")
    assert result["python"] == sys.version.split()[0]
    assert Path(result["executable"]).resolve() == Path(PYTHON).resolve()
    assert result["rlgym_api"]
    assert result["error"] is None


def test_discover_finds_concrete_components(worker):
    result = worker.call(PYTHON, "discover", {"modules": ["sample_components"]})

    assert result["errors"] == []
    by_name = {c["name"]: c for c in result["components"]}
    assert set(by_name) == {"GoalReward", "TickLimit"}

    reward = by_name["GoalReward"]
    assert reward["kind"] == "reward_function"
    assert reward["qualified_name"] == "sample_components.GoalReward"
    assert reward["doc"] == "+weight when the given team scores."
    assert reward["params"] == [
        {"name": "weight", "type": "float", "default": "1.0", "required": False},
        {"name": "team", "type": "int", "default": "0", "required": False},
    ]
    assert by_name["TickLimit"]["kind"] == "done_condition"
    assert by_name["TickLimit"]["params"] == [
        {"name": "ticks", "type": "int", "default": None, "required": True},
    ]


def test_discover_does_not_inherit_docstrings(worker):
    result = worker.call(PYTHON, "discover", {"modules": ["typed_components"]})
    by_name = {c["name"]: c for c in result["components"]}
    assert by_name["Undocumented"]["doc"] is None
    assert by_name["Generic"]["doc"] == "Indented docstring.\n\nSecond paragraph, indented."  # dedented


def test_discover_keeps_generic_types_whole(worker):
    result = worker.call(PYTHON, "discover", {"modules": ["typed_components"]})
    params = {p["name"]: p for c in result["components"] if c["name"] == "Generic" for p in c["params"]}
    assert params["max_players"]["type"] == "Optional[int]"
    assert params["names"]["type"] == "list[str]"
    assert params["scale"]["type"] == "float"            # string annotation, kept as written


def _choice(name, **params):
    return {"qualified_name": f"env_components.{name}", "params": params}


FULL = {
    "transition_engine": _choice("Engine"),
    "state_mutator": _choice("Mutator"),
    "obs_builder": _choice("Obs"),
    "action_parser": _choice("Actions"),
    "reward_fn": _choice("Reward"),
}
BUILT = {"stage": None, "param": None, "error": None}


def test_validate_builds_every_component_and_the_env(worker):
    components = {**FULL, "truncation_cond": _choice("Timeout", seconds="300 / 120")}
    result = worker.call(PYTHON, "validate", {"components": components})
    assert result == {
        "ok": True, "slots": {slot: BUILT for slot in components}, "missing": [],
        "env_built": True, "env_error": None,
    }


def test_validate_evaluates_arguments_in_the_components_module(worker):
    # math is imported by env_components, not by the worker.
    components = {**FULL, "obs_builder": _choice("Obs", scale="math.sqrt(4) * TAU")}
    assert worker.call(PYTHON, "validate", {"components": components})["ok"] is True


def test_validate_reports_each_kind_of_failure_per_slot(worker):
    components = {
        **FULL,
        "obs_builder": _choice("Obs", scale="1 +"),                       # not an expression
        "reward_fn": _choice("Picky", weight="-1"),                       # constructor raises
        "termination_cond": _choice("Timeout"),                           # required argument missing
        "truncation_cond": {"qualified_name": "env_components.Nope", "params": {}},
        "shared_info_provider": _choice("Reward"),                        # wrong kind for the slot
        "action_parser": _choice("Actions", unused="undefined_name"),     # name doesn't exist
    }
    result = worker.call(PYTHON, "validate", {"components": components})
    slots = result["slots"]

    assert slots["transition_engine"] == BUILT
    assert slots["obs_builder"]["stage"] == "argument"
    assert slots["obs_builder"]["param"] == "scale"
    assert slots["obs_builder"]["error"].startswith("SyntaxError")
    assert slots["action_parser"] == {
        "stage": "argument", "param": "unused", "error": "NameError: name 'undefined_name' is not defined",
    }
    assert slots["reward_fn"] == {"stage": "construct", "param": None, "error": "ValueError: weight must be >= 0"}
    assert slots["termination_cond"]["stage"] == "construct"
    assert "seconds" in slots["termination_cond"]["error"]
    assert slots["truncation_cond"]["stage"] == "import"
    assert "Nope" in slots["truncation_cond"]["error"]
    assert slots["shared_info_provider"] == {
        "stage": "kind", "param": None, "error": "env_components.Reward is not a SharedInfoProvider",
    }
    # The env isn't attempted: its error would only repeat the ones above.
    assert result["ok"] is False
    assert result["env_built"] is False and result["env_error"] is None


def test_validate_reports_missing_required_slots(worker):
    result = worker.call(PYTHON, "validate", {"components": {"reward_fn": _choice("Reward")}})
    assert result["slots"] == {"reward_fn": BUILT}
    assert result["missing"] == ["transition_engine", "state_mutator", "obs_builder", "action_parser"]
    assert result["ok"] is False and result["env_error"] is None


def test_validate_reports_an_env_that_fails_to_build(worker):
    components = {**FULL, "shared_info_provider": _choice("BrokenInfo")}
    result = worker.call(PYTHON, "validate", {"components": components})
    assert result["slots"]["shared_info_provider"] == BUILT
    assert result["env_built"] is False
    assert result["env_error"] == "RuntimeError: no shared info today"
    assert result["ok"] is False


def test_validate_reports_a_module_that_fails_to_import(worker):
    components = {**FULL, "reward_fn": {"qualified_name": "broken_module.Anything", "params": {}}}
    result = worker.call(PYTHON, "validate", {"components": components})
    assert result["slots"]["reward_fn"] == {
        "stage": "import", "param": None, "error": "RuntimeError: broken on purpose",
    }


def test_user_prints_go_to_the_log_not_the_protocol(worker, data_dir):
    worker.call(PYTHON, "discover", {"modules": ["sample_components"]})
    worker.stop()
    assert "sample_components imported" in (data_dir / "worker.log").read_text(encoding="utf-8")


def test_broken_module_is_reported_and_worker_survives(worker):
    result = worker.call(PYTHON, "discover", {"modules": ["broken_module", "sample_components"]})

    assert result["errors"] == [
        {"module": "broken_module", "message": "RuntimeError: broken on purpose"},
    ]
    assert len(result["components"]) == 2
    assert worker.call(PYTHON, "info")["error"] is None


def test_unknown_method_raises_and_worker_survives(worker):
    with pytest.raises(WorkerError, match="KeyError"):
        worker.call(PYTHON, "nope")
    assert worker.call(PYTHON, "info")["error"] is None


def test_reuses_the_process_between_calls(worker):
    worker.call(PYTHON, "info")
    pid = worker._proc.pid
    worker.call(PYTHON, "info")
    assert worker._proc.pid == pid


def test_restarts_after_stop(worker):
    worker.call(PYTHON, "info")
    worker.stop()
    assert worker._proc is None
    assert worker.call(PYTHON, "info")["error"] is None


def test_creates_a_missing_data_dir(data_dir, monkeypatch):
    missing = data_dir / "not" / "there"
    monkeypatch.setattr(config, "DATA_DIR", str(missing))
    w = Worker(WORKER_SCRIPT)
    try:
        assert w.call(PYTHON, "info")["error"] is None
    finally:
        w.stop()
    assert (missing / "worker.log").is_file()


def test_hanging_call_times_out_and_the_worker_recovers(worker):
    worker.call(PYTHON, "info")
    pid = worker._proc.pid

    with pytest.raises(WorkerError, match="didn't answer 'discover' within 1s"):
        worker.call(PYTHON, "discover", {"modules": ["hanging_module"]}, timeout=1)
    assert worker._proc is None                          # killed, lock released

    assert worker.call(PYTHON, "info")["error"] is None  # a fresh worker answers
    assert worker._proc.pid != pid


def test_default_timeout_comes_from_config(data_dir, monkeypatch):
    monkeypatch.setattr(config, "WORKER_TIMEOUT", 1)
    w = Worker(WORKER_SCRIPT)
    try:
        with pytest.raises(WorkerError, match="within 1s"):
            w.call(PYTHON, "discover", {"modules": ["hanging_module"]})
    finally:
        w.stop()


def test_stop_closes_the_log(worker):
    worker.call(PYTHON, "info")
    log = worker._log
    worker.stop()
    assert log.closed
    assert worker._log is None


def test_restart_closes_the_previous_log(worker):
    worker.call(PYTHON, "info")
    first = worker._log
    worker._proc.kill()
    worker._proc.wait()
    worker.call(PYTHON, "info")                          # dead process: _ensure restarts it
    assert first.closed
    assert not worker._log.closed


def test_missing_interpreter(worker, data_dir):
    with pytest.raises(WorkerError, match="Cannot start"):
        worker.call(str(data_dir / "no-such-python"), "info")


def test_worker_that_dies(data_dir):
    script = data_dir / "dies.py"
    script.write_text("import sys\nsys.exit(1)\n")
    w = Worker(script)
    with pytest.raises(WorkerError, match="exited unexpectedly"):
        w.call(PYTHON, "info")
    assert w._proc is None
