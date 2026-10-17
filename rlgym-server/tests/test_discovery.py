"""/python/info and /components/discover, end to end through a real worker process."""
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


def select(python=PYTHON, modules=()):
    settings.save(settings.Settings(python=python, modules=list(modules)))


def test_info_needs_an_interpreter(client):
    r = client.get("/python/info")
    assert r.status_code == 409
    assert "choose one in Settings" in r.json()["detail"]


def test_info_for_the_saved_interpreter(client):
    select()
    r = client.get("/python/info")
    assert r.status_code == 200
    info = r.json()
    assert info["python"] == sys.version.split()[0]
    assert info["rlgym_api"]
    assert info["error"] is None


def test_info_for_a_path_not_saved_yet(client):
    # The settings page checks a browsed path before saving it.
    r = client.get("/python/info", params={"python": PYTHON})
    assert r.status_code == 200
    assert r.json()["error"] is None
    assert settings.load().python is None


def test_info_reports_an_interpreter_that_cannot_start(client, tmp_path):
    missing = str(tmp_path / "no-such-python.exe")
    r = client.get("/python/info", params={"python": missing})
    assert r.status_code == 200
    info = r.json()
    assert info["executable"] == missing
    assert info["python"] is None
    assert "Cannot start" in info["error"]


def test_discover_needs_an_interpreter(client):
    r = client.post("/components/discover", json={"modules": ["sample_components"]})
    assert r.status_code == 409


def test_discover_groups_components_by_kind(client):
    select()
    r = client.post("/components/discover", json={"modules": ["sample_components", "broken_module"]})
    assert r.status_code == 200
    result = r.json()

    assert list(result["components"]) == list(discovery.KINDS)
    assert [c["name"] for c in result["components"]["reward_function"]] == ["GoalReward"]
    assert [c["name"] for c in result["components"]["done_condition"]] == ["TickLimit"]
    assert result["components"]["obs_builder"] == []
    assert result["components"]["done_condition"][0]["params"] == [
        {"name": "ticks", "type": "int", "default": None, "required": True},
    ]
    assert result["errors"] == [{"module": "broken_module", "message": "RuntimeError: broken on purpose"}]


def test_discover_uses_the_saved_modules_by_default(client):
    select(modules=["sample_components"])
    r = client.post("/components/discover", json={})
    assert r.status_code == 200
    assert len(r.json()["components"]["reward_function"]) == 1


def test_discover_cleans_the_module_list(client):
    select(modules=["sample_components"])
    r = client.post("/components/discover", json={"modules": ["  ", " sample_components "]})
    assert r.status_code == 200
    assert r.json()["errors"] == []
    assert len(r.json()["components"]["reward_function"]) == 1


def test_discover_reports_a_worker_failure(client):
    select()
    hung = Worker(config.worker_script(), timeout=1)
    app.dependency_overrides[discovery.get_worker] = lambda: hung
    r = client.post("/components/discover", json={"modules": ["hanging_module"]})
    hung.stop()
    assert r.status_code == 502
    assert "didn't answer 'discover'" in r.json()["detail"]
