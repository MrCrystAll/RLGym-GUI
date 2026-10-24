"""POST /configs/validate, end to end through a real worker process."""
import sys

import pytest
from fastapi.testclient import TestClient

from app import config, discovery, settings
from app.api import app
from app.worker_bridge import Worker
from conftest import FIXTURES

TOKEN = "test-token"
PYTHON = sys.executable


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(config, "TOKEN", TOKEN)
    monkeypatch.setenv("PYTHONPATH", str(FIXTURES))     # the worker inherits it
    worker = Worker(config.worker_script())
    app.dependency_overrides[discovery.get_worker] = lambda: worker
    yield TestClient(app, headers={"X-Api-Token": TOKEN})
    app.dependency_overrides.clear()
    worker.stop()


def choice(name, **params):
    return {"qualified_name": f"env_components.{name}", "params": params}


FULL = {
    "transition_engine": choice("Engine"),
    "state_mutator": choice("Mutator"),
    "obs_builder": choice("Obs", scale="2.0"),
    "action_parser": choice("Actions"),
    "reward_fn": choice("Reward"),
}


def validate(client, components):
    return client.post("/configs/validate", json={"components": components})


def test_needs_an_interpreter(client):
    r = validate(client, FULL)
    assert r.status_code == 409
    assert "choose one in Settings" in r.json()["detail"]


def test_a_complete_config_builds(client):
    settings.save(settings.Settings(python=PYTHON))
    r = validate(client, FULL)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["env_built"] is True
    assert body["missing"] == []
    assert body["slots"]["obs_builder"] == {"stage": None, "param": None, "error": None}


def test_reports_problems_per_slot(client):
    settings.save(settings.Settings(python=PYTHON))
    r = validate(client, {"reward_fn": choice("Picky", weight="-1"), "obs_builder": choice("Obs", scale="nope")})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["slots"]["reward_fn"] == {
        "stage": "construct", "param": None, "error": "ValueError: weight must be >= 0",
    }
    assert body["slots"]["obs_builder"]["stage"] == "argument"
    assert body["slots"]["obs_builder"]["param"] == "scale"
    assert body["missing"] == ["transition_engine", "state_mutator", "action_parser"]
    assert body["env_error"] is None


def test_rejects_an_unknown_slot(client):
    settings.save(settings.Settings(python=PYTHON))
    assert validate(client, {"renderer": choice("Reward")}).status_code == 422


def test_worker_failure_is_a_502(client, tmp_path):
    settings.save(settings.Settings(python=str(tmp_path / "no-such-python.exe")))
    r = validate(client, FULL)
    assert r.status_code == 502
    assert "Cannot start" in r.json()["detail"]
