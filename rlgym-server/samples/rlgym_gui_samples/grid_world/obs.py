"""Observation builders. Spaces follow rlgym's convention: ("real", size) for a flat float vector."""
from typing import Any, Literal

import numpy as np
from rlgym.api import ObsBuilder

from .state import GridState, distances_from

ObsSpace = tuple[str, Any]


def _layers(state: GridState, agent: str, see_agents: bool) -> np.ndarray:
    """(5, height, width) float32 layers: walls, lava, goals, this agent, the other agents."""
    layers = np.zeros((5, *state.shape), dtype=np.float32)
    layers[0] = state.walls
    layers[1] = state.lava
    for cell in state.goals:
        layers[2][cell] = 1
    layers[3][state.agents[agent]] = 1
    if see_agents:
        for other, cell in state.agents.items():
            if other != agent:
                layers[4][cell] = 1
    return layers


class FullGridObs(ObsBuilder[str, np.ndarray, GridState, ObsSpace]):
    """Each agent sees the whole grid as 5 layers of the grid's size: walls, lava, goals, itself and
    the other agents (left empty when `see_agents` is off). Flattened to one vector unless `flatten`
    is off, in which case the observation is a (5, height, width) array. The size depends on the
    grid, so the space is known after the first reset.
    """

    def __init__(self, flatten: bool = True, see_agents: bool = True):
        self.flatten, self.see_agents = flatten, see_agents
        self._shape: tuple[int, ...] | None = None

    def get_obs_space(self, agent: str) -> ObsSpace:
        return "real", (int(np.prod(self._shape)) if self.flatten else self._shape) if self._shape else None

    def reset(self, agents: list[str], initial_state: GridState, shared_info: dict[str, Any]) -> None:
        self._shape = (5, *initial_state.shape)

    def build_obs(self, agents: list[str], state: GridState, shared_info: dict[str, Any]) -> dict[str, np.ndarray]:
        obs = {a: _layers(state, a, self.see_agents) for a in agents}
        return {a: o.ravel() for a, o in obs.items()} if self.flatten else obs


class LocalViewObs(ObsBuilder[str, np.ndarray, GridState, ObsSpace]):
    """Each agent only sees a square window of `radius` cells around itself: 4 layers (walls, lava,
    goals, other agents) of (2 * radius + 1)² cells, flattened. Cells outside the grid look like
    walls or like empty floor, depending on `outside`. With `include_position`, the agent's row and
    column (scaled to 0..1) are appended.
    """

    def __init__(self, radius: int = 2, see_agents: bool = True, outside: Literal["wall", "empty"] = "wall",
                 include_position: bool = False):
        if radius < 1:
            raise ValueError(f"radius must be at least 1, got {radius}")
        if outside not in ("wall", "empty"):
            raise ValueError(f"outside must be 'wall' or 'empty', got {outside!r}")
        self.radius, self.see_agents, self.outside = radius, see_agents, outside
        self.include_position = include_position

    @property
    def window(self) -> int:
        return 2 * self.radius + 1

    def get_obs_space(self, agent: str) -> ObsSpace:
        return "real", 4 * self.window ** 2 + (2 if self.include_position else 0)

    def reset(self, agents: list[str], initial_state: GridState, shared_info: dict[str, Any]) -> None:
        pass

    def view(self, state: GridState, agent: str) -> np.ndarray:
        """The (4, window, window) layers around `agent`, before flattening."""
        layers = _layers(state, agent, self.see_agents)[[0, 1, 2, 4]]
        r = self.radius
        padded = np.pad(layers, ((0, 0), (r, r), (r, r)))
        if self.outside == "wall":
            padded[0, :r, :] = padded[0, -r:, :] = padded[0, :, :r] = padded[0, :, -r:] = 1
        row, col = state.agents[agent]
        return padded[:, row:row + self.window, col:col + self.window]

    def build_obs(self, agents: list[str], state: GridState, shared_info: dict[str, Any]) -> dict[str, np.ndarray]:
        h, w = state.shape
        out = {}
        for a in agents:
            obs = self.view(state, a).ravel()
            if self.include_position:
                row, col = state.agents[a]
                obs = np.concatenate([obs, np.array([row / (h - 1), col / (w - 1)], dtype=np.float32)])
            out[a] = obs
        return out


class CoordinatesObs(ObsBuilder[str, np.ndarray, GridState, ObsSpace]):
    """Each agent gets numbers instead of a picture: its row and column, the offset to the nearest
    goal (by walking distance, walls and lava avoided) and whether it reached a goal; with
    `include_others`, the offset to every other agent too. With `normalize`, positions and offsets
    are divided by the grid size.
    """

    def __init__(self, normalize: bool = True, include_others: bool = False):
        self.normalize, self.include_others = normalize, include_others
        self._size: int | None = None

    def get_obs_space(self, agent: str) -> ObsSpace:
        return "real", self._size

    def reset(self, agents: list[str], initial_state: GridState, shared_info: dict[str, Any]) -> None:
        self._size = 5 + (2 * (len(agents) - 1) if self.include_others else 0)

    def build_obs(self, agents: list[str], state: GridState, shared_info: dict[str, Any]) -> dict[str, np.ndarray]:
        h, w = state.shape
        scale = np.array([h - 1, w - 1], dtype=np.float32) if self.normalize else np.ones(2, dtype=np.float32)
        out = {}
        for a in agents:
            pos = np.array(state.agents[a], dtype=np.float32)
            dist = distances_from(state, [state.agents[a]])
            reachable = [g for g in state.goals if np.isfinite(dist[g])]
            goal = min(reachable, key=lambda g: dist[g]) if reachable else state.agents[a]
            parts = [pos / scale, (np.array(goal, dtype=np.float32) - pos) / scale,
                     np.array([float(state.reached[a])], dtype=np.float32)]
            if self.include_others:
                parts += [(np.array(state.agents[o], dtype=np.float32) - pos) / scale
                          for o in agents if o != a]
            out[a] = np.concatenate(parts).astype(np.float32)
        return out
