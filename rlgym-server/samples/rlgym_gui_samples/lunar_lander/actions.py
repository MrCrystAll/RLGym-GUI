from typing import Any

import numpy as np
from rlgym.api import ActionParser

from .spaces import Box, Discrete
from .state import LunarState

# Engine actions are [main throttle 0..1, side engine -1..1].
_DISCRETE = {
    0: (0.0, 0.0),      # do nothing
    1: (0.0, -1.0),     # fire the left orientation engine
    2: (1.0, 0.0),      # fire the main engine
    3: (0.0, 1.0),      # fire the right orientation engine
}


class DiscreteThrust(ActionParser[str, int, np.ndarray, LunarState, Discrete]):
    """gymnasium's 4 discrete actions: 0 do nothing, 1 fire the left orientation engine, 2 fire the
    main engine, 3 fire the right orientation engine. Engines run at full power."""

    def __init__(self):
        pass

    def get_action_space(self, agent: str) -> Discrete:
        return Discrete(4)

    def reset(self, agents: list[str], initial_state: LunarState, shared_info: dict[str, Any]) -> None:
        pass

    def parse_actions(self, actions: dict[str, int], state: LunarState, shared_info: dict[str, Any]) -> dict[str, np.ndarray]:
        return {a: np.array(_DISCRETE[int(act)]) for a, act in actions.items()}


class ContinuousThrust(ActionParser[str, np.ndarray, np.ndarray, LunarState, Box]):
    """gymnasium's continuous actions, two values in -1..1. The first is the main engine: off at 0
    or below, then 50% to 100% power. The second steers: the side engines stay off while its
    magnitude is under `deadzone`, then fire left (negative) or right (positive) at 50% to 100%."""

    def __init__(self, deadzone: float = 0.5):
        if not 0.0 <= deadzone < 1.0:
            raise ValueError(f"deadzone must be in [0, 1), got {deadzone}")
        self.deadzone = deadzone

    def get_action_space(self, agent: str) -> Box:
        return Box((-1.0, -1.0), (1.0, 1.0))

    def reset(self, agents: list[str], initial_state: LunarState, shared_info: dict[str, Any]) -> None:
        pass

    def parse_actions(self, actions: dict[str, np.ndarray], state: LunarState, shared_info: dict[str, Any]) -> dict[str, np.ndarray]:
        out = {}
        for agent, action in actions.items():
            main_in, side_in = (float(v) for v in np.clip(np.asarray(action, dtype=np.float64), -1.0, 1.0))
            main = (main_in + 1.0) / 2.0 if main_in > 0.0 else 0.0
            side = float(np.sign(side_in)) * max(abs(side_in), 0.5) if abs(side_in) > self.deadzone else 0.0
            out[agent] = np.array([main, side])
        return out


class StuckThrottle(ActionParser[str, int, np.ndarray, LunarState, Discrete]):
    """A broken parser, on purpose: building it always fails, so you can see how the GUI reports a
    component whose constructor raises. Use DiscreteThrust or ContinuousThrust instead."""

    def __init__(self, throttle: float = 1.0):
        raise RuntimeError("StuckThrottle is broken on purpose: its throttle is stuck. "
                           "Pick DiscreteThrust or ContinuousThrust instead.")

    def get_action_space(self, agent: str) -> Discrete:
        return Discrete(1)

    def reset(self, agents: list[str], initial_state: LunarState, shared_info: dict[str, Any]) -> None:
        pass

    def parse_actions(self, actions, state, shared_info):
        return {}
