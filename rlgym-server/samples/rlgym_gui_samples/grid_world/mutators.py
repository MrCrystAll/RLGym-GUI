from typing import Any

import numpy as np
from rlgym.api import StateMutator

from .state import DEFAULT_LAYOUT, Cell, GridState, distances_from, every_agent_can_reach_a_goal, parse_layout


def _replace(state: GridState, new: GridState) -> None:
    """Mutators get the state to change in place: copy every field of `new` into it."""
    state.walls, state.lava, state.goals = new.walls, new.lava, new.goals
    state.agents, state.tick = new.agents, new.tick
    state.refresh_flags()


class FixedMap(StateMutator[GridState]):
    """Replaces the grid with a hand-drawn map, one character per cell.

    `#` is a wall, `.` (or a space) an empty cell, `G` a goal, `~` lava, `A` an agent (numbered in
    reading order) and a digit the agent with that number. Rows must all be the same length and the
    map needs at least one goal and one agent; otherwise the constructor says what's wrong. Write
    the map as a Python string, e.g. "#####\\n#A.G#\\n#####" or a triple-quoted one.
    """

    def __init__(self, layout: str = DEFAULT_LAYOUT):
        self.layout = layout
        self._parsed = parse_layout(layout)              # fail now, not at the first reset

    def apply(self, state: GridState, shared_info: dict[str, Any]) -> None:
        _replace(state, self._parsed.copy())


class MazeGenerator(StateMutator[GridState]):
    """Replaces the grid with a random maze of `width` x `height` cells, carved by a randomized
    depth-first search, so there is exactly one path between any two cells.

    Walls sit on even rows and columns, so both sizes must be odd (and at least 5). The agents keep
    their number and start in the top-left corner; one goal goes on the cell farthest from them.
    """

    def __init__(self, width: int = 11, height: int = 11, seed: int | None = None):
        if width < 5 or height < 5 or width % 2 == 0 or height % 2 == 0:
            raise ValueError(f"MazeGenerator needs odd sizes of at least 5 (walls sit on even rows and "
                             f"columns), got {width}x{height}")
        self.width, self.height = width, height
        self._rng = np.random.default_rng(seed)

    def apply(self, state: GridState, shared_info: dict[str, Any]) -> None:
        h, w = self.height, self.width
        walls = np.ones((h, w), dtype=bool)
        start = (1, 1)
        walls[start] = False
        stack = [start]
        while stack:
            r, c = stack[-1]
            options = [(r + dr, c + dc) for dr, dc in ((-2, 0), (2, 0), (0, -2), (0, 2))
                       if 0 < r + dr < h - 1 and 0 < c + dc < w - 1 and walls[r + dr, c + dc]]
            if not options:
                stack.pop()
                continue
            nr, nc = options[self._rng.integers(len(options))]
            walls[(r + nr) // 2, (c + nc) // 2] = False
            walls[nr, nc] = False
            stack.append((nr, nc))
        new = GridState(walls=walls, lava=np.zeros((h, w), dtype=bool), goals=[], agents={})
        dist = distances_from(new, [start])
        cells = sorted(((int(r), int(c)) for r, c in zip(*np.nonzero(~walls))), key=lambda cell: dist[cell])
        agents = sorted(state.agents)
        if len(cells) < len(agents) + 1:
            raise ValueError(f"A {w}x{h} maze has no room for {len(agents)} agents and a goal")
        new.agents = dict(zip(agents, cells))
        new.goals = [cells[-1]]
        _replace(state, new)


class RandomWalls(StateMutator[GridState]):
    """Scatters walls over a fraction `density` of the free cells (cells without an agent, goal or
    lava), keeping the outer walls as they are.

    With `ensure_reachable`, it draws again (up to `max_tries` times) until every agent can still
    walk to a goal, and raises if it never manages to. `seed` makes the walls reproducible.
    """

    def __init__(self, density: float = 0.2, ensure_reachable: bool = True, max_tries: int = 50,
                 seed: int | None = None):
        if not 0.0 <= density <= 0.9:
            raise ValueError(f"density must be between 0 and 0.9, got {density}")
        if max_tries < 1:
            raise ValueError(f"max_tries must be at least 1, got {max_tries}")
        self.density, self.ensure_reachable, self.max_tries = density, ensure_reachable, max_tries
        self._rng = np.random.default_rng(seed)

    def apply(self, state: GridState, shared_info: dict[str, Any]) -> None:
        h, w = state.shape
        free = [cell for cell in state.free_cells() if 0 < cell[0] < h - 1 and 0 < cell[1] < w - 1]
        count = int(round(self.density * len(free)))
        base = state.walls.copy()
        for _ in range(self.max_tries):
            state.walls = base.copy()
            for i in self._rng.choice(len(free), size=count, replace=False):
                state.walls[free[i]] = True
            if not self.ensure_reachable or every_agent_can_reach_a_goal(state):
                return
        raise RuntimeError(f"No wall layout at density {self.density} left every agent a path to a goal "
                           f"in {self.max_tries} tries; lower the density or raise max_tries")


class RandomPlacement(StateMutator[GridState]):
    """Moves every agent and `n_goals` goals to random free cells (keeping walls and lava).

    Goals are placed first; agents then go on cells at least `min_goal_distance` steps (Manhattan)
    from every goal. Raises when the grid hasn't enough room.
    """

    def __init__(self, n_goals: int = 1, min_goal_distance: int = 0, seed: int | None = None):
        if n_goals < 1:
            raise ValueError(f"n_goals must be at least 1, got {n_goals}")
        self.n_goals, self.min_goal_distance = n_goals, min_goal_distance
        self._rng = np.random.default_rng(seed)

    def apply(self, state: GridState, shared_info: dict[str, Any]) -> None:
        agents = sorted(state.agents)
        state.goals, state.agents = [], {}
        cells = state.free_cells()
        if len(cells) < self.n_goals + len(agents):
            raise ValueError(f"Not enough free cells for {self.n_goals} goals and {len(agents)} agents")
        order = self._rng.permutation(len(cells))
        goals = [cells[i] for i in order[:self.n_goals]]
        far = [cells[i] for i in order[self.n_goals:]
               if all(abs(cells[i][0] - g[0]) + abs(cells[i][1] - g[1]) >= self.min_goal_distance for g in goals)]
        if len(far) < len(agents):
            raise ValueError(f"Not enough free cells at least {self.min_goal_distance} steps from the goals "
                             f"for {len(agents)} agents")
        state.goals = goals
        state.agents = dict(zip(agents, far))
        state.refresh_flags()


class AddLava(StateMutator[GridState]):
    """Pours lava on the grid: on the given `cells` ((row, column) pairs, e.g. [(2, 3), (2, 4)]) when
    set, otherwise on `count` random free cells. An agent that steps into lava stops there (see the
    FellInLava done condition and LavaPenalty reward). Cells on walls, goals or agents are skipped.
    """

    def __init__(self, count: int = 3, cells: list[tuple[int, int]] | None = None, seed: int | None = None):
        if count < 0:
            raise ValueError(f"count can't be negative, got {count}")
        self.count = count
        self.cells = [tuple(cell) for cell in cells] if cells is not None else None
        self._rng = np.random.default_rng(seed)

    def apply(self, state: GridState, shared_info: dict[str, Any]) -> None:
        free = state.free_cells()
        if self.cells is not None:
            chosen: list[Cell] = [cell for cell in self.cells if cell in set(free)]
        else:
            chosen = [free[i] for i in self._rng.choice(len(free), size=min(self.count, len(free)), replace=False)]
        for cell in chosen:
            state.lava[cell] = True
        state.refresh_flags()


class MutatorSequence(StateMutator[GridState]):
    """Applies several mutators in order, e.g. [MazeGenerator(15, 9), AddLava(count=4)] or
    [FixedMap(), RandomPlacement(n_goals=2)]. Later ones see what earlier ones did.
    """

    def __init__(self, mutators: list[StateMutator]):
        if not mutators:
            raise ValueError("MutatorSequence needs at least one mutator")
        for m in mutators:
            if not isinstance(m, StateMutator):
                raise TypeError(f"MutatorSequence takes state mutators, got {type(m).__name__}")
        self.mutators = list(mutators)

    def apply(self, state: GridState, shared_info: dict[str, Any]) -> None:
        for m in self.mutators:
            m.apply(state, shared_info)


class TeleportTraps(StateMutator[GridState]):
    """Always fails: there are no teleport traps in this grid world. It's here to see how the app
    reports a component whose constructor raises.
    """

    def __init__(self, pairs: int = 1):
        raise NotImplementedError("TeleportTraps isn't implemented: this grid world has no teleport mechanic "
                                  "(this component fails on purpose, to try out error messages)")

    def apply(self, state: GridState, shared_info: dict[str, Any]) -> None:  # pragma: no cover
        pass
