"""The grid world's state, and helpers shared by its components."""
import textwrap
from collections import deque
from dataclasses import dataclass, field

import numpy as np

Cell = tuple[int, int]                                   # (row, column)

# One cell per character: '#' wall, '.' or ' ' empty, 'G' goal, '~' lava, 'A' an agent (numbered in
# reading order), '0'-'9' the agent with that number.
DEFAULT_LAYOUT = """
#########
#A..#..G#
#...#...#
#.~...~.#
#A..#...#
#########
"""


@dataclass
class GridState:
    walls: np.ndarray                                    # bool (height, width)
    lava: np.ndarray                                     # bool (height, width)
    goals: list[Cell]
    agents: dict[str, Cell]                              # agent id -> cell
    reached: dict[str, bool] = field(default_factory=dict)   # standing on (or has reached) a goal
    in_lava: dict[str, bool] = field(default_factory=dict)
    bumped: dict[str, bool] = field(default_factory=dict)    # tried to walk into a wall last step
    tick: int = 0

    @property
    def shape(self) -> tuple[int, int]:
        return self.walls.shape

    def copy(self) -> "GridState":
        return GridState(
            walls=self.walls.copy(), lava=self.lava.copy(), goals=list(self.goals),
            agents=dict(self.agents), reached=dict(self.reached), in_lava=dict(self.in_lava),
            bumped=dict(self.bumped), tick=self.tick,
        )

    def inside(self, cell: Cell) -> bool:
        r, c = cell
        return 0 <= r < self.shape[0] and 0 <= c < self.shape[1]

    def walkable(self, cell: Cell) -> bool:
        return self.inside(cell) and not self.walls[cell]

    def free_cells(self) -> list[Cell]:
        """Walkable cells with no lava, goal or agent on them, in reading order."""
        taken = set(self.goals) | set(self.agents.values())
        return [(int(r), int(c)) for r, c in zip(*np.nonzero(~self.walls & ~self.lava)) if (r, c) not in taken]

    def refresh_flags(self) -> None:
        """Recompute reached / in_lava from positions, and clear bumped (after a mutator moved things)."""
        goals = set(self.goals)
        self.reached = {a: pos in goals for a, pos in self.agents.items()}
        self.in_lava = {a: bool(self.lava[pos]) for a, pos in self.agents.items()}
        self.bumped = {a: False for a in self.agents}

    def render(self) -> str:
        """The grid as text, in the same characters a layout uses (agents as their number)."""
        rows = [["#" if w else "~" if l else "." for w, l in zip(wr, lr)] for wr, lr in zip(self.walls, self.lava)]
        for r, c in self.goals:
            rows[r][c] = "G"
        for agent, (r, c) in self.agents.items():
            rows[r][c] = agent.removeprefix("agent_")[-1]
        return "\n".join("".join(row) for row in rows)

    __str__ = render


def agent_id(n: int) -> str:
    return f"agent_{n}"


def parse_layout(layout: str) -> GridState:
    """A layout string (see DEFAULT_LAYOUT) -> GridState. Raises ValueError explaining what's wrong."""
    lines = [line.rstrip() for line in textwrap.dedent(layout).strip("\n").splitlines()]
    if not lines or not any(lines):
        raise ValueError("The map is empty")
    widths = {len(line) for line in lines}
    if len(widths) > 1:
        lengths = ", ".join(f"row {i + 1}: {len(line)}" for i, line in enumerate(lines))
        raise ValueError(f"Every map row must have the same length ({lengths})")
    height, width = len(lines), widths.pop()
    walls = np.zeros((height, width), dtype=bool)
    lava = np.zeros((height, width), dtype=bool)
    goals: list[Cell] = []
    numbered: dict[int, Cell] = {}
    unnumbered: list[Cell] = []
    for r, line in enumerate(lines):
        for c, ch in enumerate(line):
            if ch == "#":
                walls[r, c] = True
            elif ch == "~":
                lava[r, c] = True
            elif ch == "G":
                goals.append((r, c))
            elif ch == "A":
                unnumbered.append((r, c))
            elif ch.isdigit():
                if int(ch) in numbered:
                    raise ValueError(f"Agent {ch} appears twice in the map")
                numbered[int(ch)] = (r, c)
            elif ch not in ". ":
                raise ValueError(f"Unknown map character {ch!r} at row {r + 1}, column {c + 1} "
                                 "(use # . G ~ A or a digit)")
    if not goals:
        raise ValueError("The map has no goal ('G')")
    if not numbered and not unnumbered:
        raise ValueError("The map has no agent ('A' or a digit)")
    agents = {agent_id(n): cell for n, cell in sorted(numbered.items())}
    n = 0
    for cell in unnumbered:                              # 'A's take the numbers digits left free
        while n in numbered:
            n += 1
        agents[agent_id(n)] = cell
        n += 1
    state = GridState(walls=walls, lava=lava, goals=goals, agents=dict(sorted(agents.items())))
    state.refresh_flags()
    return state


def distances_from(state: GridState, sources: list[Cell]) -> np.ndarray:
    """Shortest walking distance (4 directions, avoiding walls and lava) from the nearest source to
    every cell; inf where unreachable."""
    dist = np.full(state.shape, np.inf)
    queue = deque()
    for s in sources:
        if state.walkable(s):
            dist[s] = 0
            queue.append(s)
    while queue:
        r, c = queue.popleft()
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nxt = (r + dr, c + dc)
            if state.walkable(nxt) and not state.lava[nxt] and dist[nxt] == np.inf:
                dist[nxt] = dist[r, c] + 1
                queue.append(nxt)
    return dist


def every_agent_can_reach_a_goal(state: GridState) -> bool:
    dist = distances_from(state, state.goals)
    return all(np.isfinite(dist[pos]) for pos in state.agents.values())
