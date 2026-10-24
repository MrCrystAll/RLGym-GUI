"""A user module with one component of each kind RLGym(...) needs, plus some that fail on purpose."""
import math

from rlgym.api import (
    ActionParser, DoneCondition, ObsBuilder, RewardFunction, SharedInfoProvider, StateMutator,
    TransitionEngine,
)


class Engine(TransitionEngine):
    pass


class Mutator(StateMutator):
    pass


class Obs(ObsBuilder):
    def __init__(self, scale: float = 1.0):
        self.scale = scale


class Actions(ActionParser):
    pass


class Reward(RewardFunction):
    def __init__(self, weight: float = 1.0):
        self.weight = weight


class Timeout(DoneCondition):
    def __init__(self, seconds: float):
        self.seconds = seconds


class Picky(RewardFunction):
    """Its constructor rejects some values."""

    def __init__(self, weight: float = 1.0):
        if weight < 0:
            raise ValueError("weight must be >= 0")
        self.weight = weight


class BrokenInfo(SharedInfoProvider):
    """Builds fine, but RLGym(...) calls create() and that fails."""

    def create(self, shared_info):
        raise RuntimeError("no shared info today")


# Used by the "arguments can use the module's imports" test: math is imported above.
TAU = 2 * math.pi
