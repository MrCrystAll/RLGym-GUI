from typing import Any

import numpy as np
from rlgym.api import SharedInfoProvider

from .state import CartPoleState


class EpisodeStats(SharedInfoProvider[str, CartPoleState]):
    """Keeps running episode statistics in the shared info, under `key`: the tick count and, with
    `track_max_angle`, the largest pole angle (in degrees) each agent has reached so far."""

    def __init__(self, key: str = "episode", track_max_angle: bool = True):
        self.key = key
        self.track_max_angle = track_max_angle

    def create(self, shared_info: dict[str, Any]) -> dict[str, Any]:
        shared_info[self.key] = {"ticks": 0}
        return shared_info

    def _update(self, agents: list[str], state: CartPoleState, stats: dict[str, Any]) -> None:
        stats["ticks"] = state.tick
        if self.track_max_angle:
            angles = stats.setdefault("max_angle_deg", {})
            for agent in agents:
                angle = float(np.degrees(abs(state.theta[state.index(agent)])))
                angles[agent] = max(angles.get(agent, 0.0), angle)

    def set_state(self, agents: list[str], initial_state: CartPoleState, shared_info: dict[str, Any]) -> dict[str, Any]:
        shared_info[self.key] = {"ticks": 0}
        self._update(agents, initial_state, shared_info[self.key])
        return shared_info

    def step(self, agents: list[str], state: CartPoleState, shared_info: dict[str, Any]) -> dict[str, Any]:
        self._update(agents, state, shared_info.setdefault(self.key, {"ticks": 0}))
        return shared_info
