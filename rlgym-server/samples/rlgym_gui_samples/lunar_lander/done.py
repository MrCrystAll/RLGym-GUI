from typing import Any

from rlgym.api import DoneCondition

from .state import LunarState


def is_landed(state: LunarState, agent: str, require_both_legs: bool = True, max_speed: float = 0.1) -> bool:
    lander = state.landers[agent]
    if lander.crashed:
        return False
    if lander.at_rest:
        return True
    legs = all(lander.legs_contact) if require_both_legs else any(lander.legs_contact)
    speed = (lander.vx ** 2 + lander.vy ** 2) ** 0.5
    return legs and speed < max_speed and abs(lander.angular_velocity) < max_speed


class Landed(DoneCondition[str, LunarState]):
    """Done once the lander stands still on the ground without having crashed: both legs (or just
    one, without `require_both_legs`) touch the ground and it moves slower than `max_speed` m/s, or
    Box2D has put it to sleep."""

    def __init__(self, require_both_legs: bool = True, max_speed: float = 0.1):
        self.require_both_legs = require_both_legs
        self.max_speed = max_speed

    def reset(self, agents: list[str], initial_state: LunarState, shared_info: dict[str, Any]) -> None:
        pass

    def is_done(self, agents: list[str], state: LunarState, shared_info: dict[str, Any]) -> dict[str, bool]:
        return {a: is_landed(state, a, self.require_both_legs, self.max_speed) for a in agents}


class Crashed(DoneCondition[str, LunarState]):
    """Done when the lander's body, not a leg, touches the ground."""

    def __init__(self):
        pass

    def reset(self, agents: list[str], initial_state: LunarState, shared_info: dict[str, Any]) -> None:
        pass

    def is_done(self, agents: list[str], state: LunarState, shared_info: dict[str, Any]) -> dict[str, bool]:
        return {a: state.landers[a].crashed for a in agents}


class OutOfBounds(DoneCondition[str, LunarState]):
    """Done when the lander flies off the side of the screen: its horizontal position, scaled so
    the edges are ±1 as in the observation, reaches ±`max_abs_x`."""

    def __init__(self, max_abs_x: float = 1.0):
        if max_abs_x <= 0:
            raise ValueError(f"max_abs_x must be positive, got {max_abs_x}")
        self.max_abs_x = max_abs_x

    def reset(self, agents: list[str], initial_state: LunarState, shared_info: dict[str, Any]) -> None:
        pass

    def is_done(self, agents: list[str], state: LunarState, shared_info: dict[str, Any]) -> dict[str, bool]:
        return {a: state.out_of_bounds(a, self.max_abs_x) for a in agents}


class GameOver(DoneCondition[str, LunarState]):
    """gymnasium's termination: the lander crashed, left the screen, or came to rest."""

    def __init__(self):
        pass

    def reset(self, agents: list[str], initial_state: LunarState, shared_info: dict[str, Any]) -> None:
        pass

    def is_done(self, agents: list[str], state: LunarState, shared_info: dict[str, Any]) -> dict[str, bool]:
        return {a: state.landers[a].crashed or state.out_of_bounds(a) or state.landers[a].at_rest for a in agents}


class AnyOf(DoneCondition[str, LunarState]):
    """Done as soon as any of `conditions` is, e.g. `[Landed(), Crashed(), OutOfBounds()]`: the RLGym
    config only takes one termination condition."""

    def __init__(self, conditions: list[DoneCondition]):
        if not conditions:
            raise ValueError("conditions must not be empty")
        self.conditions = list(conditions)

    def reset(self, agents: list[str], initial_state: LunarState, shared_info: dict[str, Any]) -> None:
        for c in self.conditions:
            c.reset(agents, initial_state, shared_info)

    def is_done(self, agents: list[str], state: LunarState, shared_info: dict[str, Any]) -> dict[str, bool]:
        results = [c.is_done(agents, state, shared_info) for c in self.conditions]
        return {a: any(r[a] for r in results) for a in agents}


class TickLimit(DoneCondition[str, LunarState]):
    """Done after `max_ticks` physics steps (gymnasium truncates at 1000, 20 s at 50 fps). Meant as
    the truncation condition."""

    def __init__(self, max_ticks: int):
        if max_ticks < 1:
            raise ValueError(f"max_ticks must be at least 1, got {max_ticks}")
        self.max_ticks = max_ticks

    def reset(self, agents: list[str], initial_state: LunarState, shared_info: dict[str, Any]) -> None:
        pass

    def is_done(self, agents: list[str], state: LunarState, shared_info: dict[str, Any]) -> dict[str, bool]:
        return {a: state.tick >= self.max_ticks for a in agents}
