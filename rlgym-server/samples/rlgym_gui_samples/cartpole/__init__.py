"""CartPole: balance a pole on a moving cart (RLGYM-35).

A typical config: CartPoleEngine, RandomStart, CartPoleObs, DiscreteForce, AliveReward,
AngleLimit (termination) and TickLimit(500) (truncation): that's Gym's CartPole-v1. The other
components change the physics (Gravity, PoleLength, Wind), the observations, actions and rewards.
UnstableMutator fails on purpose.
"""
from .actions import ContinuousForce, DiscreteForce
from .done import AngleLimit, AnyOf, OutOfBounds, TickLimit
from .engine import CartPoleEngine
from .mutators import Gravity, MutatorSequence, PoleLength, RandomStart, UnstableMutator, UprightStart, Wind
from .obs import CartPoleObs, FullObs
from .rewards import AliveReward, CombinedReward, PositionPenalty, UprightReward
from .shared_info import EpisodeStats
from .state import CartPoleState

__all__ = [
    "CartPoleEngine", "CartPoleState",
    "UprightStart", "RandomStart", "Gravity", "PoleLength", "Wind", "MutatorSequence", "UnstableMutator",
    "CartPoleObs", "FullObs",
    "DiscreteForce", "ContinuousForce",
    "AliveReward", "UprightReward", "PositionPenalty", "CombinedReward",
    "AngleLimit", "OutOfBounds", "TickLimit", "AnyOf",
    "EpisodeStats",
]
