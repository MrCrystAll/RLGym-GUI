import json
import time

import pytest
from fastapi.testclient import TestClient

from app import config
from app.api import app

TOKEN = "test-token"
REWARD = {"qualified_name": "my_bot.rewards.GoalReward", "params": {"weight": "2.0"}}


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    d = tmp_path / "data"
    monkeypatch.setattr(config, "DATA_DIR", str(d))
    return d


@pytest.fixture
def client(data_dir, monkeypatch):
    monkeypatch.setattr(config, "TOKEN", TOKEN)
    return TestClient(app, headers={"X-Api-Token": TOKEN})


def create(client, name="Kickoff", components=None):
    r = client.post("/configs", json={"name": name, "components": components or {}})
    assert r.status_code == 201, r.text
    return r.json()


def test_empty_list_on_first_launch(client):
    r = client.get("/configs")
    assert r.status_code == 200
    assert r.json() == []


def test_create_then_get(client, data_dir):
    created = create(client, "  Kickoff  ", {"reward_fn": REWARD})
    assert created["name"] == "Kickoff"                  # trimmed
    assert len(created["id"]) == 32
    assert created["created_at"] == created["updated_at"]
    assert created["components"] == {"reward_fn": REWARD}

    r = client.get(f"/configs/{created['id']}")
    assert r.status_code == 200
    assert r.json() == created
    on_disk = json.loads((data_dir / "configs" / f"{created['id']}.json").read_text(encoding="utf-8"))
    assert on_disk["name"] == "Kickoff"


def test_params_default_to_empty(client):
    c = create(client, components={"reward_fn": {"qualified_name": "a.B"}})
    assert c["components"]["reward_fn"]["params"] == {}


def test_list_summarises_newest_first(client):
    full = {s: {"qualified_name": f"m.{s}"} for s in
            ("transition_engine", "state_mutator", "obs_builder", "action_parser", "reward_fn")}
    a = create(client, "A", {"reward_fn": REWARD})
    time.sleep(0.01)
    b = create(client, "B", {**full, "truncation_cond": {"qualified_name": "m.T"}})

    summaries = client.get("/configs").json()
    assert [s["id"] for s in summaries] == [b["id"], a["id"]]
    assert summaries[1]["slots"] == ["reward_fn"]
    assert summaries[1]["complete"] is False
    assert summaries[0]["slots"] == [
        "transition_engine", "state_mutator", "obs_builder", "action_parser", "reward_fn", "truncation_cond",
    ]
    assert summaries[0]["complete"] is True             # optional slots aren't needed


def test_update_keeps_id_and_created_at(client):
    c = create(client)
    time.sleep(0.01)
    r = client.put(f"/configs/{c['id']}", json={"name": "Renamed", "components": {"reward_fn": REWARD}})
    assert r.status_code == 200
    u = r.json()
    assert (u["id"], u["created_at"]) == (c["id"], c["created_at"])
    assert u["updated_at"] > c["updated_at"]
    assert u["name"] == "Renamed"
    assert client.get(f"/configs/{c['id']}").json() == u


def test_names_are_unique_ignoring_case(client):
    a = create(client, "Kickoff")
    r = client.post("/configs", json={"name": "KICKOFF"})
    assert r.status_code == 409
    assert r.json()["detail"] == "A config named 'Kickoff' already exists"   # the existing name

    b = create(client, "Other")
    assert client.put(f"/configs/{b['id']}", json={"name": "kickoff"}).status_code == 409
    # Saving a config under its own name is fine.
    assert client.put(f"/configs/{a['id']}", json={"name": "Kickoff"}).status_code == 200


def test_delete(client, data_dir):
    c = create(client)
    assert client.delete(f"/configs/{c['id']}").status_code == 204
    assert client.get(f"/configs/{c['id']}").status_code == 404
    assert client.get("/configs").json() == []
    assert client.delete(f"/configs/{c['id']}").status_code == 404


def test_unknown_id_is_404(client):
    missing = "0" * 32
    assert client.get(f"/configs/{missing}").status_code == 404
    assert client.put(f"/configs/{missing}", json={"name": "x"}).status_code == 404


@pytest.mark.parametrize("bad_id", ["nope", "..%2Fsettings", "A" * 32])
def test_malformed_id_is_rejected(client, bad_id):
    assert client.get(f"/configs/{bad_id}").status_code in (404, 422)


@pytest.mark.parametrize("body", [
    {"name": "   "},
    {"name": "x" * 101},
    {"name": "x", "components": {"renderer": {"qualified_name": "a.B"}}},
    {"name": "x", "components": {"reward_fn": {"qualified_name": ""}}},
    {"name": "x", "components": {"reward_fn": {"qualified_name": "a.B", "params": {"w": 1.0}}}},
], ids=["blank-name", "long-name", "unknown-slot", "blank-component", "non-string-param"])
def test_rejects_invalid_configs(client, data_dir, body):
    assert client.post("/configs", json=body).status_code == 422
    assert not (data_dir / "configs").exists()


def test_unreadable_file_is_skipped(client, data_dir):
    c = create(client)
    (data_dir / "configs" / ("f" * 32 + ".json")).write_text("{broken", encoding="utf-8")
    assert [s["id"] for s in client.get("/configs").json()] == [c["id"]]
    assert client.get(f"/configs/{'f' * 32}").status_code == 404


def test_save_leaves_no_temp_file(client, data_dir):
    c = create(client)
    assert [p.name for p in (data_dir / "configs").iterdir()] == [f"{c['id']}.json"]
