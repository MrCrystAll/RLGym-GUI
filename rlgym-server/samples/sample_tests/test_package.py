import importlib
from pathlib import Path

import pytest

import rlgym_gui_samples

ENVS = ["cartpole", "lunar_lander", "grid_world"]


def test_imports_from_this_checkout():
    # Not from a copy installed elsewhere (e.g. pip install -e of another worktree).
    assert Path(rlgym_gui_samples.__file__).parent == Path(__file__).parent.parent / "rlgym_gui_samples"


@pytest.mark.parametrize("env", ENVS)
def test_env_package_imports(env):
    importlib.import_module(f"rlgym_gui_samples.{env}")
