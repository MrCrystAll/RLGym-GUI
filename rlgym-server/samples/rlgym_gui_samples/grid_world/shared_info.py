from typing import Any

import numpy as np
from rlgym.api import SharedInfoProvider

from .state import GridState


class GridStats(SharedInfoProvider[str, GridState]):
    """Keeps episode statistics in the shared info every component receives: "tick", "goals_reached"
    (how many agents are on a goal) and, with `track_visits`, "visits", a per-agent count of how many
    steps it spent on each cell (an array the grid's size).
    """

    def __init__(self, track_visits: bool = True):
        self.track_visits = track_visits

    def create(self, shared_info: dict[str, Any]) -> dict[str, Any]:
        shared_info.update({"tick": 0, "goals_reached": 0})
        if self.track_visits:
            shared_info["visits"] = {}
        return shared_info

    def set_state(self, agents: list[str], initial_state: GridState, shared_info: dict[str, Any]) -> dict[str, Any]:
        shared_info["tick"] = 0
        shared_info["goals_reached"] = sum(initial_state.reached[a] for a in agents)
        if self.track_visits:
            shared_info["visits"] = {a: np.zeros(initial_state.shape, dtype=np.int32) for a in agents}
            for a in agents:
                shared_info["visits"][a][initial_state.agents[a]] += 1
        return shared_info

    def step(self, agents: list[str], state: GridState, shared_info: dict[str, Any]) -> dict[str, Any]:
        shared_info["tick"] = state.tick
        shared_info["goals_reached"] = sum(state.reached[a] for a in agents)
        if self.track_visits:
            for a in agents:
                shared_info["visits"][a][state.agents[a]] += 1
        return shared_info
