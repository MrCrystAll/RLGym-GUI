from typing import Any

import numpy as np
from rlgym.api import ObsBuilder

from .state import CartPoleState

# Rough magnitudes used to scale observations into about [-1, 1].
SCALES = np.array([2.4, 3.0, 0.21, 3.5])


class CartPoleObs(ObsBuilder[str, np.ndarray, CartPoleState, tuple]):
    """The classic 4-value observation of each agent's own cart: position, velocity, pole angle and
    pole angular velocity. With `normalize`, each value is divided by a typical magnitude so it lies
    roughly in [-1, 1]. Observation space: ("real", 4)."""

    def __init__(self, normalize: bool = False):
        self.normalize = normalize

    def get_obs_space(self, agent: str) -> tuple:
        return "real", 4

    def reset(self, agents: list[str], initial_state: CartPoleState, shared_info: dict[str, Any]) -> None:
        pass

    def build_obs(self, agents: list[str], state: CartPoleState, shared_info: dict[str, Any]) -> dict[str, np.ndarray]:
        obs = {}
        for agent in agents:
            i = state.index(agent)
            values = np.array([state.x[i], state.x_dot[i], state.theta[i], state.theta_dot[i]])
            obs[agent] = values / SCALES if self.normalize else values
        return obs


class FullObs(ObsBuilder[str, np.ndarray, CartPoleState, tuple]):
    """The cart's own 4 values, plus optionally the physics the mutators set (gravity, pole length,
    wind: `include_physics`) and the pole angles of the other carts (`include_others`, for
    multi-cart runs). `history` stacks that many previous observations after the current one, so the
    observation size grows with it: ("real", (4 + 3 + n_other_carts) × (history + 1))."""

    def __init__(self, include_physics: bool = True, include_others: bool = False, history: int = 0):
        if history < 0:
            raise ValueError(f"history must be 0 or more, got {history}")
        self.include_physics = include_physics
        self.include_others = include_others
        self.history = history
        self._n_agents = 1
        self._past: dict[str, list[np.ndarray]] = {}

    def _frame_size(self) -> int:
        return 4 + (3 if self.include_physics else 0) + (self._n_agents - 1 if self.include_others else 0)

    def get_obs_space(self, agent: str) -> tuple:
        return "real", self._frame_size() * (self.history + 1)

    def reset(self, agents: list[str], initial_state: CartPoleState, shared_info: dict[str, Any]) -> None:
        self._n_agents = len(agents)
        self._past = {agent: [] for agent in agents}

    def _frame(self, agent: str, state: CartPoleState) -> np.ndarray:
        i = state.index(agent)
        parts = [state.x[i], state.x_dot[i], state.theta[i], state.theta_dot[i]]
        if self.include_physics:
            parts += [state.gravity, 2 * state.half_pole_length, state.wind]
        if self.include_others:
            parts += [state.theta[j] for j in range(len(state.agents)) if j != i]
        return np.array(parts, dtype=np.float64)

    def build_obs(self, agents: list[str], state: CartPoleState, shared_info: dict[str, Any]) -> dict[str, np.ndarray]:
        obs = {}
        for agent in agents:
            frame = self._frame(agent, state)
            past = self._past.setdefault(agent, [])
            # Before there's enough history, repeat the current frame.
            frames = [frame] + [past[k] if k < len(past) else frame for k in range(self.history)]
            obs[agent] = np.concatenate(frames)
            past.insert(0, frame)
            del past[self.history:]
        return obs
