from typing import Any

import numpy as np
from rlgym.api import DoneCondition

from .state import CartPoleState


class AngleLimit(DoneCondition[str, CartPoleState]):
    """Done once the pole leans more than `max_degrees` from vertical (12° in the classic task):
    the usual termination condition."""

    def __init__(self, max_degrees: float = 12.0):
        if not 0 < max_degrees < 90:
            raise ValueError(f"max_degrees must be between 0 and 90, got {max_degrees}")
        self.max_degrees = max_degrees

    def reset(self, agents: list[str], initial_state: CartPoleState, shared_info: dict[str, Any]) -> None:
        pass

    def is_done(self, agents: list[str], state: CartPoleState, shared_info: dict[str, Any]) -> dict[str, bool]:
        limit = np.radians(self.max_degrees)
        return {agent: bool(abs(state.theta[state.index(agent)]) > limit) for agent in agents}


class OutOfBounds(DoneCondition[str, CartPoleState]):
    """Done once the cart leaves the track, i.e. its position goes beyond ±`x_threshold` metres
    (2.4 in the classic task)."""

    def __init__(self, x_threshold: float = 2.4):
        self.x_threshold = x_threshold

    def reset(self, agents: list[str], initial_state: CartPoleState, shared_info: dict[str, Any]) -> None:
        pass

    def is_done(self, agents: list[str], state: CartPoleState, shared_info: dict[str, Any]) -> dict[str, bool]:
        return {agent: bool(abs(state.x[state.index(agent)]) > self.x_threshold) for agent in agents}


class TickLimit(DoneCondition[str, CartPoleState]):
    """Done for every agent after `max_ticks` steps: the usual truncation condition (CartPole-v1
    uses 500). Required: there's no sensible default episode length."""

    def __init__(self, max_ticks: int):
        if max_ticks < 1:
            raise ValueError(f"max_ticks must be at least 1, got {max_ticks}")
        self.max_ticks = max_ticks

    def reset(self, agents: list[str], initial_state: CartPoleState, shared_info: dict[str, Any]) -> None:
        pass

    def is_done(self, agents: list[str], state: CartPoleState, shared_info: dict[str, Any]) -> dict[str, bool]:
        return {agent: state.tick >= self.max_ticks for agent in agents}


class AnyOf(DoneCondition[str, CartPoleState]):
    """Done when any of the given conditions is, e.g. `[AngleLimit(), OutOfBounds()]` for the full
    classic termination rule in one slot."""

    def __init__(self, conditions: list[DoneCondition]):
        if not conditions:
            raise ValueError("conditions must not be empty")
        self.conditions = list(conditions)

    def reset(self, agents: list[str], initial_state: CartPoleState, shared_info: dict[str, Any]) -> None:
        for condition in self.conditions:
            condition.reset(agents, initial_state, shared_info)

    def is_done(self, agents: list[str], state: CartPoleState, shared_info: dict[str, Any]) -> dict[str, bool]:
        done = {agent: False for agent in agents}
        for condition in self.conditions:
            for agent, value in condition.is_done(agents, state, shared_info).items():
                done[agent] = done[agent] or value
        return done
