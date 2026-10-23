from typing import Any, Literal

import numpy as np
from rlgym.api import RewardFunction

from .state import GridState, distances_from


class GoalReward(RewardFunction[str, GridState, float]):
    """Gives `reward` to an agent on the step it reaches a goal. With `shared`, every agent gets it
    whenever any agent reaches a goal (a cooperative setup).
    """

    def __init__(self, reward: float = 1.0, shared: bool = False):
        self.reward, self.shared = reward, shared
        self._reached: dict[str, bool] = {}

    def reset(self, agents: list[str], initial_state: GridState, shared_info: dict[str, Any]) -> None:
        self._reached = dict(initial_state.reached)

    def get_rewards(self, agents: list[str], state: GridState, is_terminated: dict[str, bool],
                    is_truncated: dict[str, bool], shared_info: dict[str, Any]) -> dict[str, float]:
        new = [a for a in agents if state.reached[a] and not self._reached.get(a, False)]
        self._reached = dict(state.reached)
        if self.shared:
            return {a: self.reward * len(new) for a in agents}
        return {a: self.reward if a in new else 0.0 for a in agents}


class StepPenalty(RewardFunction[str, GridState, float]):
    """Takes `penalty` off every agent at each step, to favour short paths. Agents that are done
    (reached a goal or fell in lava) stop paying unless `after_goal` is on.
    """

    def __init__(self, penalty: float = 0.01, after_goal: bool = False):
        self.penalty, self.after_goal = penalty, after_goal

    def reset(self, agents: list[str], initial_state: GridState, shared_info: dict[str, Any]) -> None:
        pass

    def get_rewards(self, agents: list[str], state: GridState, is_terminated: dict[str, bool],
                    is_truncated: dict[str, bool], shared_info: dict[str, Any]) -> dict[str, float]:
        done = {a: state.reached[a] or state.in_lava[a] for a in agents}
        return {a: 0.0 if done[a] and not self.after_goal else -self.penalty for a in agents}


class DistanceShaping(RewardFunction[str, GridState, float]):
    """Rewards getting closer to the nearest goal: `scale` times the distance gained this step
    (negative when moving away). `metric` picks the distance: "manhattan" or "euclidean" as the crow
    flies, or "path" for the real walking distance around walls and lava.
    """

    def __init__(self, scale: float = 0.1, metric: Literal["manhattan", "euclidean", "path"] = "manhattan"):
        if metric not in ("manhattan", "euclidean", "path"):
            raise ValueError(f"metric must be 'manhattan', 'euclidean' or 'path', got {metric!r}")
        self.scale, self.metric = scale, metric
        self._last: dict[str, float] = {}

    def _distances(self, state: GridState) -> dict[str, float]:
        if self.metric == "path":
            dist = distances_from(state, state.goals)
            return {a: float(dist[pos]) for a, pos in state.agents.items()}
        goals = np.array(state.goals, dtype=float)
        out = {}
        for a, pos in state.agents.items():
            delta = np.abs(goals - np.array(pos, dtype=float))
            d = delta.sum(axis=1) if self.metric == "manhattan" else np.sqrt((delta ** 2).sum(axis=1))
            out[a] = float(d.min())
        return out

    def reset(self, agents: list[str], initial_state: GridState, shared_info: dict[str, Any]) -> None:
        self._last = self._distances(initial_state)

    def get_rewards(self, agents: list[str], state: GridState, is_terminated: dict[str, bool],
                    is_truncated: dict[str, bool], shared_info: dict[str, Any]) -> dict[str, float]:
        now = self._distances(state)
        out = {}
        for a in agents:
            before, after = self._last.get(a, now[a]), now[a]
            # Unreachable goals (path metric) give inf: no shaping rather than inf/nan rewards.
            out[a] = self.scale * (before - after) if np.isfinite(before) and np.isfinite(after) else 0.0
        self._last = now
        return out


class BumpPenalty(RewardFunction[str, GridState, float]):
    """Takes `penalty` off an agent each time it walks into a wall (or the edge of the grid)."""

    def __init__(self, penalty: float = 0.05):
        self.penalty = penalty

    def reset(self, agents: list[str], initial_state: GridState, shared_info: dict[str, Any]) -> None:
        pass

    def get_rewards(self, agents: list[str], state: GridState, is_terminated: dict[str, bool],
                    is_truncated: dict[str, bool], shared_info: dict[str, Any]) -> dict[str, float]:
        return {a: -self.penalty if state.bumped.get(a) else 0.0 for a in agents}


class LavaPenalty(RewardFunction[str, GridState, float]):
    """Takes `penalty` off an agent on the step it falls into lava."""

    def __init__(self, penalty: float = 1.0):
        self.penalty = penalty
        self._in_lava: dict[str, bool] = {}

    def reset(self, agents: list[str], initial_state: GridState, shared_info: dict[str, Any]) -> None:
        self._in_lava = dict(initial_state.in_lava)

    def get_rewards(self, agents: list[str], state: GridState, is_terminated: dict[str, bool],
                    is_truncated: dict[str, bool], shared_info: dict[str, Any]) -> dict[str, float]:
        out = {a: -self.penalty if state.in_lava[a] and not self._in_lava.get(a, False) else 0.0 for a in agents}
        self._in_lava = dict(state.in_lava)
        return out


class WeightedSum(RewardFunction[str, GridState, float]):
    """Adds up other rewards, each multiplied by its weight, e.g. rewards=[GoalReward(), StepPenalty(0.02),
    DistanceShaping(metric="path")] with weights=[1.0, 1.0, 0.5]. Without `weights`, every reward
    counts once.
    """

    def __init__(self, rewards: list[RewardFunction], weights: list[float] | None = None):
        if not rewards:
            raise ValueError("WeightedSum needs at least one reward")
        for r in rewards:
            if not isinstance(r, RewardFunction):
                raise TypeError(f"WeightedSum takes reward functions, got {type(r).__name__}")
        if weights is not None and len(weights) != len(rewards):
            raise ValueError(f"Got {len(rewards)} rewards but {len(weights)} weights")
        self.rewards = list(rewards)
        self.weights = list(weights) if weights is not None else [1.0] * len(rewards)

    def reset(self, agents: list[str], initial_state: GridState, shared_info: dict[str, Any]) -> None:
        for r in self.rewards:
            r.reset(agents, initial_state, shared_info)

    def get_rewards(self, agents: list[str], state: GridState, is_terminated: dict[str, bool],
                    is_truncated: dict[str, bool], shared_info: dict[str, Any]) -> dict[str, float]:
        total = {a: 0.0 for a in agents}
        for r, w in zip(self.rewards, self.weights):
            for a, value in r.get_rewards(agents, state, is_terminated, is_truncated, shared_info).items():
                total[a] += w * value
        return total
