import ast
import json

import pytest
from fastapi.testclient import TestClient

from app import config
from app.api import app

TOKEN = "test-token"
COMPLETE = {
    "transition_engine": {"qualified_name": "my_bot.engine.Sim", "params": {}},
    "state_mutator": {"qualified_name": "my_bot.state.KickoffMutator", "params": {"blue": "1", "orange": "1"}},
    "obs_builder": {"qualified_name": "my_bot.obs.DefaultObs", "params": {"zero_padding": "None"}},
    "action_parser": {"qualified_name": "my_bot.actions.LookupAction", "params": {}},
    "reward_fn": {"qualified_name": "my_bot.rewards.GoalReward", "params": {"weight": "2.0", "team": "'blue'"}},
    "termination_cond": {"qualified_name": "my_bot.done.TickLimit", "params": {"ticks": "300"}},
    "truncation_cond": {"qualified_name": "my_bot.done.TickLimit", "params": {"ticks": "10 * 60"}},
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(config, "TOKEN", TOKEN)
    return TestClient(app, headers={"X-Api-Token": TOKEN})


def create(client, name="Kickoff training", components=None):
    r = client.post("/configs", json={"name": name, "components": components or {}})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def export(client, config_id, fmt):
    r = client.get(f"/configs/{config_id}/export", params={"format": fmt})
    assert r.status_code == 200, r.text
    return r.json()


def test_snippet_builds_the_env_from_the_chosen_components(client):
    out = export(client, create(client, components=COMPLETE), "snippet")
    assert out["filename"] == "kickoff_training.py"
    assert out["missing_slots"] == []
    code = out["content"]
    ast.parse(code)                                      # valid Python
    assert "from rlgym.api import RLGym" in code
    # One import line per module, each class imported once even when used in two slots.
    assert "from my_bot.done import TickLimit\n" in code
    assert "from my_bot.rewards import GoalReward\n" in code
    # Argument expressions are written as-is.
    assert "reward_fn=GoalReward(weight=2.0, team='blue')," in code
    assert "truncation_cond=TickLimit(ticks=10 * 60)," in code
    assert "transition_engine=Sim()," in code
    assert "env = RLGym(" in code
    assert "__main__" not in code


def test_script_resets_and_closes_the_env(client):
    out = export(client, create(client, components=COMPLETE), "script")
    assert out["filename"] == "run_kickoff_training.py"
    code = out["content"]
    tree = ast.parse(code)
    assert any(isinstance(n, ast.FunctionDef) and n.name == "make_env" for n in tree.body)
    assert 'if __name__ == "__main__":' in code
    assert "env.reset()" in code and "env.close()" in code


def test_script_runs_with_stub_components(client, tmp_path, monkeypatch):
    # The generated script really constructs RLGym, resets it and prints the agents.
    stubs = tmp_path / "stub_bot.py"
    stubs.write_text(
        "class Engine:\n"
        "    agents = ['blue-0', 'orange-0']\n"
        "    def create_base_state(self): return {}\n"
        "    def set_state(self, state, shared_info): return state\n"
        "    def close(self): pass\n"
        "class Part:\n"
        "    def __init__(self, **kw): self.kw = kw\n"
        "    def apply(self, *a): pass\n"
        "    def reset(self, *a): pass\n"
        "    def build_obs(self, agents, state, shared_info): return {a: [0.0] for a in agents}\n"
    )
    parts = {s: {"qualified_name": "stub_bot.Part", "params": {}} for s in
             ("state_mutator", "obs_builder", "action_parser", "reward_fn")}
    parts["transition_engine"] = {"qualified_name": "stub_bot.Engine", "params": {}}
    parts["reward_fn"]["params"] = {"weight": "1.5"}
    code = export(client, create(client, components=parts), "script")["content"]

    monkeypatch.syspath_prepend(str(tmp_path))
    printed = []
    monkeypatch.setattr("builtins.print", lambda *a, **k: printed.append(" ".join(map(str, a))))
    exec(compile(code, "run_kickoff_training.py", "exec"), {"__name__": "__main__"})
    assert printed == ["2 agent(s)", "  blue-0: obs shape list", "  orange-0: obs shape list"]


def test_json_is_the_config_without_its_id(client):
    config_id = create(client, components={"reward_fn": COMPLETE["reward_fn"]})
    out = export(client, config_id, "json")
    assert out["filename"] == "kickoff_training.json"
    assert json.loads(out["content"]) == {"name": "Kickoff training", "components": {"reward_fn": COMPLETE["reward_fn"]}}


def test_json_can_be_imported_back(client):
    out = export(client, create(client, components=COMPLETE), "json")
    body = json.loads(out["content"])
    body["name"] = "Copy"
    assert client.post("/configs", json=body).status_code == 201


def test_incomplete_config_still_exports_with_placeholders(client):
    out = export(client, create(client, components={"reward_fn": COMPLETE["reward_fn"]}), "snippet")
    assert out["missing_slots"] == ["transition_engine", "state_mutator", "obs_builder", "action_parser"]
    code = out["content"]
    ast.parse(code)
    assert "    state_mutator=...,  # not chosen yet" in code
    assert "termination_cond" not in code                # optional and unset: left out


def test_same_class_name_from_two_modules_gets_an_alias(client):
    components = {
        "reward_fn": {"qualified_name": "a.rewards.Reward", "params": {}},
        "obs_builder": {"qualified_name": "b.obs.Reward", "params": {}},
    }
    code = export(client, create(client, components=components), "snippet")["content"]
    # obs_builder comes first in RLGym(...)'s order, so it keeps the plain name.
    assert "from b.obs import Reward\n" in code
    assert "from a.rewards import Reward as Reward_2\n" in code
    assert "obs_builder=Reward()," in code
    assert "reward_fn=Reward_2()," in code


@pytest.mark.parametrize("name, filename", [
    ("Kickoff training", "kickoff_training.py"),
    ("  1v1 / aerials!! ", "config_1v1_aerials.py"),
    ("???", "config.py"),
])
def test_filename_is_a_python_module_name(client, name, filename):
    assert export(client, create(client, name=name), "snippet")["filename"] == filename


def test_name_with_quotes_and_newlines_stays_a_comment(client):
    code = export(client, create(client, name='He said """hi"""\nprint("pwned")'), "snippet")["content"]
    ast.parse(code)
    assert '# RLGym environment: He said """hi""" print("pwned")' in code


def test_unknown_config_is_404(client):
    r = client.get(f"/configs/{'f' * 32}/export", params={"format": "json"})
    assert r.status_code == 404


def test_unknown_format_is_422(client):
    r = client.get(f"/configs/{create(client)}/export", params={"format": "yaml"})
    assert r.status_code == 422
