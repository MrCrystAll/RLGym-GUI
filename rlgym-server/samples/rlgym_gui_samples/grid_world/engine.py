from typing import Any, Literal

import numpy as np
from rlgym.api import TransitionEngine

from .state import Cell, GridState, agent_id

Move = tuple[int, int]                                   # (row delta, column delta)
SLIP_MOVES: list[Move] = [(-1, 0), (1, 0), (0, -1), (0, 1)]


class GridEngine(TransitionEngine[str, GridState, Move]):
    """Agents walking on a grid of cells, one cell per step.

    The base state is an empty walled room of `width` x `height` cells with `n_agents` agents in the
    top-left corner and one goal in the bottom-right; state mutators reshape it (fixed maps, random
    walls, mazes...). Walking into a wall leaves the agent in place. With `collisions="block"`, two
    agents can't share a cell or swap places (goal cells excepted); with "pass" they walk through
    each other. An agent that reaches a goal or steps into lava stops moving. With `slip` > 0, each
    move is replaced by a random direction with that probability, using `seed`.
    """

    def __init__(self, width: int = 8, height: int = 8, n_agents: int = 2,
                 collisions: Literal["block", "pass"] = "block", slip: float = 0.0, seed: int | None = None):
        if width < 3 or height < 3:
            raise ValueError(f"The grid must be at least 3x3 (walls all around), got {width}x{height}")
        if n_agents < 1:
            raise ValueError(f"n_agents must be at least 1, got {n_agents}")
        if (width - 2) * (height - 2) < n_agents + 1:
            raise ValueError(f"A {width}x{height} grid has no room for {n_agents} agents and a goal")
        if collisions not in ("block", "pass"):
            raise ValueError(f"collisions must be 'block' or 'pass', got {collisions!r}")
        if not 0.0 <= slip <= 1.0:
            raise ValueError(f"slip is a probability, between 0 and 1; got {slip}")
        self._config = {"width": width, "height": height, "n_agents": n_agents,
                        "collisions": collisions, "slip": slip}
        self._rng = np.random.default_rng(seed)
        self._state: GridState | None = None

    @property
    def agents(self) -> list[str]:
        return list(self._state.agents) if self._state else []

    @property
    def max_num_agents(self) -> int:
        return max(self._config["n_agents"], len(self.agents))

    @property
    def state(self) -> GridState:
        return self._state

    @property
    def config(self) -> dict[str, Any]:
        return dict(self._config)

    @config.setter
    def config(self, value: dict[str, Any]):
        self._config.update(value)

    def create_base_state(self) -> GridState:
        h, w = self._config["height"], self._config["width"]
        walls = np.zeros((h, w), dtype=bool)
        walls[0, :] = walls[-1, :] = walls[:, 0] = walls[:, -1] = True
        interior = [(r, c) for r in range(1, h - 1) for c in range(1, w - 1)]
        goal = (h - 2, w - 2)
        starts = [cell for cell in interior if cell != goal][:self._config["n_agents"]]
        state = GridState(walls=walls, lava=np.zeros((h, w), dtype=bool), goals=[goal],
                          agents={agent_id(i): cell for i, cell in enumerate(starts)})
        state.refresh_flags()
        return state

    def set_state(self, desired_state: GridState, shared_info: dict[str, Any]) -> GridState:
        state = desired_state.copy()
        for agent, pos in state.agents.items():
            if not state.walkable(pos):
                raise ValueError(f"{agent} starts on a wall or outside the grid, at {pos}")
        state.tick = 0
        state.refresh_flags()
        self._state = state
        return state

    def step(self, actions: dict[str, Move], shared_info: dict[str, Any]) -> GridState:
        old = self._state
        state = old.copy()
        moving = [a for a in old.agents if not (old.reached[a] or old.in_lava[a])]
        targets: dict[str, Cell] = dict(old.agents)
        state.bumped = {a: False for a in old.agents}
        for agent in moving:
            dr, dc = actions.get(agent, (0, 0))
            if self._config["slip"] and self._rng.random() < self._config["slip"]:
                dr, dc = SLIP_MOVES[self._rng.integers(len(SLIP_MOVES))]
            r, c = old.agents[agent]
            target = (r + int(dr), c + int(dc))
            if not state.walkable(target):
                state.bumped[agent] = (dr, dc) != (0, 0)
                target = (r, c)
            targets[agent] = target
        if self._config["collisions"] == "block":
            targets = self._resolve_collisions(old, targets)
        state.agents = targets
        goals = set(state.goals)
        state.reached = {a: old.reached[a] or pos in goals for a, pos in targets.items()}
        state.in_lava = {a: old.in_lava[a] or bool(state.lava[pos]) for a, pos in targets.items()}
        state.tick = old.tick + 1
        self._state = state
        return state

    @staticmethod
    def _resolve_collisions(old: GridState, targets: dict[str, Cell]) -> dict[str, Cell]:
        """Send back to their cell any agents that would share a cell (except a goal) or swap
        places, until no conflict is left. Each pass sends at least one agent back, so it ends."""
        goals = set(old.goals)
        targets = dict(targets)
        changed = True
        while changed:
            changed = False
            agents = list(targets)
            for i, a in enumerate(agents):
                for b in agents[i + 1:]:
                    same_cell = targets[a] == targets[b] and targets[a] not in goals
                    swap = targets[a] == old.agents[b] and targets[b] == old.agents[a] and targets[a] != targets[b]
                    if same_cell or swap:
                        for x in (a, b):
                            if targets[x] != old.agents[x]:
                                targets[x] = old.agents[x]
                                changed = True
        return targets

    def close(self) -> None:
        pass
