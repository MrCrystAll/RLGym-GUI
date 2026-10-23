from typing import Any, Literal

from rlgym.api import DoneCondition

from .state import GridState


class GoalReached(DoneCondition[str, GridState]):
    """Ends the episode when agents reach a goal. `mode` says for whom: "each" ends it per agent as
    each one arrives, "any" ends it for everyone as soon as one agent arrives, "all" only once every
    agent has arrived. Use it as the termination condition.
    """

    def __init__(self, mode: Literal["each", "any", "all"] = "each"):
        if mode not in ("each", "any", "all"):
            raise ValueError(f"mode must be 'each', 'any' or 'all', got {mode!r}")
        self.mode = mode

    def reset(self, agents: list[str], initial_state: GridState, shared_info: dict[str, Any]) -> None:
        pass

    def is_done(self, agents: list[str], state: GridState, shared_info: dict[str, Any]) -> dict[str, bool]:
        if self.mode == "each":
            return {a: state.reached[a] for a in agents}
        done = (any if self.mode == "any" else all)(state.reached[a] for a in agents)
        return {a: done for a in agents}


class TickLimit(DoneCondition[str, GridState]):
    """Ends the episode for every agent after `max_ticks` steps. Use it as the truncation condition."""

    def __init__(self, max_ticks: int):
        if max_ticks < 1:
            raise ValueError(f"max_ticks must be at least 1, got {max_ticks}")
        self.max_ticks = max_ticks

    def reset(self, agents: list[str], initial_state: GridState, shared_info: dict[str, Any]) -> None:
        pass

    def is_done(self, agents: list[str], state: GridState, shared_info: dict[str, Any]) -> dict[str, bool]:
        return {a: state.tick >= self.max_ticks for a in agents}


class FellInLava(DoneCondition[str, GridState]):
    """Ends the episode for an agent that stepped into lava, or for everyone with `everyone`."""

    def __init__(self, everyone: bool = False):
        self.everyone = everyone

    def reset(self, agents: list[str], initial_state: GridState, shared_info: dict[str, Any]) -> None:
        pass

    def is_done(self, agents: list[str], state: GridState, shared_info: dict[str, Any]) -> dict[str, bool]:
        if self.everyone:
            done = any(state.in_lava[a] for a in agents)
            return {a: done for a in agents}
        return {a: state.in_lava[a] for a in agents}


class AnyOf(DoneCondition[str, GridState]):
    """Done for an agent when any of `conditions` is, e.g. [GoalReached(), FellInLava()]: RLGym takes
    a single termination condition, this combines several.
    """

    def __init__(self, conditions: list[DoneCondition]):
        if not conditions:
            raise ValueError("AnyOf needs at least one condition")
        for c in conditions:
            if not isinstance(c, DoneCondition):
                raise TypeError(f"AnyOf takes done conditions, got {type(c).__name__}")
        self.conditions = list(conditions)

    def reset(self, agents: list[str], initial_state: GridState, shared_info: dict[str, Any]) -> None:
        for c in self.conditions:
            c.reset(agents, initial_state, shared_info)

    def is_done(self, agents: list[str], state: GridState, shared_info: dict[str, Any]) -> dict[str, bool]:
        results = [c.is_done(agents, state, shared_info) for c in self.conditions]
        return {a: any(r[a] for r in results) for a in agents}
