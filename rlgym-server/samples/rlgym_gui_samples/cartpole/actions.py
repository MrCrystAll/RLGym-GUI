from typing import Any

import numpy as np
from rlgym.api import ActionParser

from .state import CartPoleState


def _scalar(action: Any) -> float:
    return float(np.asarray(action).reshape(-1)[0])


class DiscreteForce(ActionParser[str, int, float, CartPoleState, tuple]):
    """Each agent picks one of `n_levels` forces evenly spaced between -force and +force newtons.
    The classic task is n_levels=2: push left or push right at 10 N. An odd number of levels
    includes "don't push". Action space: ("discrete", n_levels)."""

    def __init__(self, n_levels: int = 2, force: float = 10.0):
        if n_levels < 2:
            raise ValueError(f"n_levels must be at least 2, got {n_levels}")
        self.n_levels = n_levels
        self.force = force
        self._forces = np.linspace(-force, force, n_levels)

    def get_action_space(self, agent: str) -> tuple:
        return "discrete", self.n_levels

    def reset(self, agents: list[str], initial_state: CartPoleState, shared_info: dict[str, Any]) -> None:
        pass

    def parse_actions(self, actions: dict[str, int], state: CartPoleState, shared_info: dict[str, Any]) -> dict[str, float]:
        parsed = {}
        for agent, action in actions.items():
            level = int(_scalar(action))
            if not 0 <= level < self.n_levels:
                raise ValueError(f"{agent}: action {level} is outside 0..{self.n_levels - 1}")
            parsed[agent] = float(self._forces[level])
        return parsed


class ContinuousForce(ActionParser[str, float, float, CartPoleState, tuple]):
    """Each agent outputs a value in [-1, 1], scaled to a force of up to `max_force` newtons. Values
    outside the range are clipped, unless `clip` is off, in which case they're an error. Action
    space: ("real", 1)."""

    def __init__(self, max_force: float = 10.0, clip: bool = True):
        self.max_force = max_force
        self.clip = clip

    def get_action_space(self, agent: str) -> tuple:
        return "real", 1

    def reset(self, agents: list[str], initial_state: CartPoleState, shared_info: dict[str, Any]) -> None:
        pass

    def parse_actions(self, actions: dict[str, float], state: CartPoleState, shared_info: dict[str, Any]) -> dict[str, float]:
        parsed = {}
        for agent, action in actions.items():
            value = _scalar(action)
            if self.clip:
                value = min(max(value, -1.0), 1.0)
            elif not -1.0 <= value <= 1.0:
                raise ValueError(f"{agent}: action {value} is outside [-1, 1]")
            parsed[agent] = value * self.max_force
        return parsed
