"""Sample user module for worker-smoke.py: one component per common kind, plus a noisy import."""
from rlgym.api import DoneCondition, RewardFunction

print("sample_components imported")  # must land in worker.log, not corrupt the protocol


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
