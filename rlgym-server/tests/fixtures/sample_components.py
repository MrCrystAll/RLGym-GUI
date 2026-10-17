"""A user module as the worker sees it: two components, an abstract base, and a noisy import."""
from abc import ABC, abstractmethod

from rlgym.api import DoneCondition, RewardFunction

print("sample_components imported")  # must go to the worker log, not the protocol channel


class GoalReward(RewardFunction):
    """+weight when the given team scores."""

    def __init__(self, weight: float = 1.0, team: int = 0):
        self.weight = weight
        self.team = team

    def reset(self, *args, **kwargs):
        pass

    def get_rewards(self, *args, **kwargs):
        return {}


class TickLimit(DoneCondition):
    """Truncate after a fixed number of ticks."""

    def __init__(self, ticks: int):
        self.ticks = ticks

    def reset(self, *args, **kwargs):
        pass

    def is_done(self, *args, **kwargs):
        return {}


# rlgym.api's bases aren't ABCs, so a user base class has to mix in ABC to be abstract.
class AbstractReward(RewardFunction, ABC):
    """Abstract, so discovery must skip it."""

    @abstractmethod
    def extra(self): ...


class NotAComponent:
    pass
