"""Grid world: agents move on a grid to reach a goal (RLGYM-37).

A small multi-agent grid: walls, goals, lava. A config that works out of the box:

    transition_engine=GridEngine(), state_mutator=FixedMap(), obs_builder=LocalViewObs(),
    action_parser=CardinalMoves(), reward_fn=WeightedSum([GoalReward(), StepPenalty()]),
    termination_cond=AnyOf([GoalReached(), FellInLava()]), truncation_cond=TickLimit(100),
    shared_info_provider=GridStats()

TeleportTraps always fails, and FixedMap, MazeGenerator... reject bad arguments: they're there to
see how the app reports errors.
"""
from .actions import CardinalMoves, KingMoves
from .done import AnyOf, FellInLava, GoalReached, TickLimit
from .engine import GridEngine
from .mutators import AddLava, FixedMap, MazeGenerator, MutatorSequence, RandomPlacement, RandomWalls, TeleportTraps
from .obs import CoordinatesObs, FullGridObs, LocalViewObs
from .rewards import BumpPenalty, DistanceShaping, GoalReward, LavaPenalty, StepPenalty, WeightedSum
from .shared_info import GridStats
from .state import DEFAULT_LAYOUT, GridState, parse_layout

__all__ = [
    "GridEngine",
    "FixedMap", "MazeGenerator", "RandomWalls", "RandomPlacement", "AddLava", "MutatorSequence", "TeleportTraps",
    "FullGridObs", "LocalViewObs", "CoordinatesObs",
    "CardinalMoves", "KingMoves",
    "GoalReward", "StepPenalty", "DistanceShaping", "BumpPenalty", "LavaPenalty", "WeightedSum",
    "GoalReached", "TickLimit", "FellInLava", "AnyOf",
    "GridStats",
    "GridState", "DEFAULT_LAYOUT", "parse_layout",
]
