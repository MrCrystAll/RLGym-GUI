"""Lunar Lander: land a craft between two flags, in Box2D (RLGYM-36).

Adapted from gymnasium's LunarLander (MIT licence). A classic setup:

    RLGym(
        transition_engine=LunarLanderEngine(seed=0),
        state_mutator=Mutators([RandomTerrain(), RandomStart()]),
        obs_builder=LanderObs(),
        action_parser=DiscreteThrust(),
        reward_fn=ClassicReward(),
        termination_cond=GameOver(),
        truncation_cond=TickLimit(1000),
    )
"""
from .actions import ContinuousThrust, DiscreteThrust, StuckThrottle
from .done import AnyOf, Crashed, GameOver, Landed, OutOfBounds, TickLimit
from .engine import LunarLanderEngine
from .mutators import Gravity, Mutators, PlanetPreset, RandomStart, RandomTerrain, Wind
from .obs import LanderObs, PadRelativeObs
from .rewards import ClassicReward, FuelCost, LandingReward, ShapingReward, WeightedSum
from .shared_info import EpisodeStats
from .spaces import Box, Discrete
from .state import LanderState, LunarState

__all__ = [
    "LunarLanderEngine",
    "RandomTerrain", "RandomStart", "Gravity", "PlanetPreset", "Wind", "Mutators",
    "LanderObs", "PadRelativeObs",
    "DiscreteThrust", "ContinuousThrust", "StuckThrottle",
    "ShapingReward", "FuelCost", "LandingReward", "WeightedSum", "ClassicReward",
    "Landed", "Crashed", "OutOfBounds", "GameOver", "AnyOf", "TickLimit",
    "EpisodeStats",
    "Box", "Discrete", "LanderState", "LunarState",
]
