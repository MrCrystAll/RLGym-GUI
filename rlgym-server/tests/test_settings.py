import json

import pytest
from fastapi.testclient import TestClient

from app import config, settings
from app.api import app

TOKEN = "test-token"


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    d = tmp_path / "data"                                # doesn't exist yet, like a first launch
    monkeypatch.setattr(config, "DATA_DIR", str(d))
    return d


@pytest.fixture
def client(data_dir, monkeypatch):
    monkeypatch.setattr(config, "TOKEN", TOKEN)
    return TestClient(app, headers={"X-Api-Token": TOKEN})


def test_defaults_when_nothing_saved(client):
    r = client.get("/settings")
    assert r.status_code == 200
    assert r.json() == {"python": None, "modules": []}


def test_put_then_get(client, data_dir):
    body = {"python": "C:/Python312/python.exe", "modules": ["my_bot.rewards", "my_bot.obs"]}
    r = client.put("/settings", json=body)
    assert r.status_code == 200
    assert r.json() == body

    assert client.get("/settings").json() == body
    assert json.loads((data_dir / "settings.json").read_text(encoding="utf-8")) == body


def test_survives_a_restart(client, data_dir):
    client.put("/settings", json={"python": "py.exe", "modules": ["a"]})
    # A new process only has the file: load() must read it back.
    assert settings.load() == settings.Settings(python="py.exe", modules=["a"])


def test_cleans_up_hand_typed_values(client):
    r = client.put("/settings", json={"python": "  ", "modules": [" a ", "", "b", "a", "  "]})
    assert r.json() == {"python": None, "modules": ["a", "b"]}


def test_partial_body_uses_defaults(client):
    r = client.put("/settings", json={"modules": ["a"]})
    assert r.json() == {"python": None, "modules": ["a"]}


@pytest.mark.parametrize("content", ["{not json", '{"modules": "not a list"}', ""])
def test_unreadable_file_falls_back_to_defaults(client, data_dir, content):
    data_dir.mkdir()
    (data_dir / "settings.json").write_text(content, encoding="utf-8")
    assert client.get("/settings").json() == {"python": None, "modules": []}


def test_rejects_invalid_body(client, data_dir):
    r = client.put("/settings", json={"modules": "not a list"})
    assert r.status_code == 422
    assert not (data_dir / "settings.json").exists()


def test_save_leaves_no_temp_file(client, data_dir):
    client.put("/settings", json={"modules": ["a"]})
    assert sorted(p.name for p in data_dir.iterdir()) == ["settings.json"]
