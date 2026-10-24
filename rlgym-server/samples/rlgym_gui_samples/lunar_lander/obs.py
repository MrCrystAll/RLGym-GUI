import math
from typing import Any

import numpy as np
from rlgym.api import ObsBuilder

from .spaces import Box
from .state import FPS, LunarState


class LanderObs(ObsBuilder[str, np.ndarray, LunarState, Box]):
    """gymnasium's 8-value observation: position relative to the pad and velocity (both scaled to
    roughly -1..1), angle, angular velocity, and whether each leg touches the ground. Without
    `include_legs`, only the first 6 values."""

    LOW = (-2.5, -2.5, -10.0, -10.0, -2 * math.pi, -10.0, 0.0, 0.0)
    HIGH = (2.5, 2.5, 10.0, 10.0, 2 * math.pi, 10.0, 1.0, 1.0)

    def __init__(self, include_legs: bool = True):
        self.include_legs = include_legs

    def _size(self) -> int:
        return 8 if self.include_legs else 6

    def get_obs_space(self, agent: str) -> Box:
        n = self._size()
        return Box(self.LOW[:n], self.HIGH[:n])

    def reset(self, agents: list[str], initial_state: LunarState, shared_info: dict[str, Any]) -> None:
        pass

    def build_obs(self, agents: list[str], state: LunarState, shared_info: dict[str, Any]) -> dict[str, np.ndarray]:
        n = self._size()
        return {a: np.asarray(state.classic_obs(a)[:n], dtype=np.float32) for a in agents}


class PadRelativeObs(ObsBuilder[str, np.ndarray, LunarState, Box]):
    """Physical units instead of gymnasium's scaling: offset to the pad centre in metres, velocity
    in m/s, angle (radians), angular velocity (rad/s), the two leg contacts, and optionally the
    fuel used so far. Values are clipped to ±`clip` unless it's None."""

    def __init__(self, include_fuel: bool = False, clip: float | None = 10.0):
        if clip is not None and clip <= 0:
            raise ValueError(f"clip must be positive or None, got {clip}")
        self.include_fuel = include_fuel
        self.clip = clip

    def get_obs_space(self, agent: str) -> Box:
        n = 9 if self.include_fuel else 8
        bound = math.inf if self.clip is None else self.clip
        low = [-bound] * n
        high = [bound] * n
        low[6] = low[7] = 0.0
        high[6] = high[7] = 1.0
        if self.include_fuel:
            low[8] = 0.0
        return Box(tuple(low), tuple(high))

    def reset(self, agents: list[str], initial_state: LunarState, shared_info: dict[str, Any]) -> None:
        pass

    def build_obs(self, agents: list[str], state: LunarState, shared_info: dict[str, Any]) -> dict[str, np.ndarray]:
        pad_x, pad_y = state.pad_center()
        out = {}
        for a in agents:
            lander = state.landers[a]
            values = [lander.x - pad_x, lander.y - pad_y, lander.vx, lander.vy, lander.angle,
                      lander.angular_velocity, float(lander.legs_contact[0]), float(lander.legs_contact[1])]
            if self.include_fuel:
                values.append(lander.fuel_used / FPS)
            obs = np.asarray(values, dtype=np.float32)
            if self.clip is not None:
                obs[:6] = np.clip(obs[:6], -self.clip, self.clip)
                if self.include_fuel:
                    obs[8] = min(obs[8], self.clip)
            out[a] = obs
        return out
