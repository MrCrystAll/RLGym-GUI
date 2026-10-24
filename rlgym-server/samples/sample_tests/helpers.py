"""Shared checks for the sample environments' tests."""
from collections.abc import Callable
from typing import Any

from rlgym.api import RLGym


def run_episode(env: RLGym, act: Callable[[Any], dict], max_steps: int = 200) -> int:
    """Reset `env`, then step it with `act(env)` (one action per agent) until every agent is done or
    `max_steps` is reached. Checks the shapes of what RLGym returns; returns the number of steps."""
    obs = env.reset()
    agents = env.agents
    assert agents, "reset() left no agents"
    assert set(obs) == set(agents)
    for step in range(1, max_steps + 1):
        obs, rewards, terminated, truncated = env.step(act(env))
        for result in (obs, rewards, terminated, truncated):
            assert set(result) == set(agents)
        if all(terminated[a] or truncated[a] for a in agents):
            return step
    return max_steps
