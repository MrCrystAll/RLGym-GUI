"""Action parsers: an integer per agent -> a (row delta, column delta) move for GridEngine. Spaces
follow rlgym's convention: ("discrete", number of actions)."""
from typing import Any

import numpy as np
from rlgym.api import ActionParser

from .engine import Move
from .state import GridState

ActionSpace = tuple[str, int]

CARDINAL: list[Move] = [(-1, 0), (1, 0), (0, -1), (0, 1)]                 # up, down, left, right
DIAGONAL: list[Move] = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
STAY: Move = (0, 0)


def _index(action: Any) -> int:
    """Accepts a plain int or a numpy scalar/array of one element (what most policies output)."""
    return int(np.asarray(action).reshape(-1)[0])


class _MoveTable(ActionParser[str, Any, Move, GridState, ActionSpace]):
    moves: list[Move]

    def get_action_space(self, agent: str) -> ActionSpace:
        return "discrete", len(self.moves)

    def reset(self, agents: list[str], initial_state: GridState, shared_info: dict[str, Any]) -> None:
        pass

    def parse_actions(self, actions: dict[str, Any], state: GridState, shared_info: dict[str, Any]) -> dict[str, Move]:
        out = {}
        for agent, action in actions.items():
            i = _index(action)
            if not 0 <= i < len(self.moves):
                raise ValueError(f"Action {i} for {agent} is out of range: this parser has {len(self.moves)} actions")
            out[agent] = self.moves[i]
        return out


class CardinalMoves(_MoveTable):
    """One discrete action per agent: 0 up, 1 down, 2 left, 3 right, and 4 stay in place when
    `allow_stay` is on.
    """

    def __init__(self, allow_stay: bool = True):
        self.allow_stay = allow_stay
        self.moves = CARDINAL + ([STAY] if allow_stay else [])


class KingMoves(_MoveTable):
    """Like a chess king: one discrete action per agent among the 4 straight moves (0 up, 1 down,
    2 left, 3 right), the 4 diagonals (4 up-left, 5 up-right, 6 down-left, 7 down-right) and, when
    `allow_stay` is on, 8 to stay. Diagonals can slip between two walls touching at a corner.
    """

    def __init__(self, allow_stay: bool = True):
        self.allow_stay = allow_stay
        self.moves = CARDINAL + DIAGONAL + ([STAY] if allow_stay else [])
