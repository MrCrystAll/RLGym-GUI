from typing import Any

from rlgym.api import SharedInfoProvider

from .done import is_landed
from .state import LunarState


class EpisodeStats(SharedInfoProvider[str, LunarState]):
    """Keeps a summary of the episode in `shared_info[key]`: the tick, each lander's fuel used,
    and which landers have landed or crashed so far. Handy to look at while stepping."""

    def __init__(self, key: str = "lunar_lander"):
        if not key:
            raise ValueError("key must not be empty")
        self.key = key

    def _stats(self, agents: list[str], state: LunarState) -> dict[str, Any]:
        return {
            "tick": state.tick,
            "fuel_used": {a: state.landers[a].fuel_used for a in agents},
            "landed": [a for a in agents if is_landed(state, a)],
            "crashed": [a for a in agents if state.landers[a].crashed],
        }

    def create(self, shared_info: dict[str, Any]) -> dict[str, Any]:
        shared_info[self.key] = {}
        return shared_info

    def set_state(self, agents: list[str], initial_state: LunarState, shared_info: dict[str, Any]) -> dict[str, Any]:
        shared_info[self.key] = self._stats(agents, initial_state)
        return shared_info

    def step(self, agents: list[str], state: LunarState, shared_info: dict[str, Any]) -> dict[str, Any]:
        shared_info[self.key] = self._stats(agents, state)
        return shared_info
