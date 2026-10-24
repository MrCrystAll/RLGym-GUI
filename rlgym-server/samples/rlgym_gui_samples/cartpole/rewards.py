from typing import Any

import numpy as np
from rlgym.api import RewardFunction

from .state import CartPoleState


class AliveReward(RewardFunction[str, CartPoleState, float]):
    """The classic reward: `value` for every tick the agent's pole is still up (not terminated), 0
    once it has fallen."""

    def __init__(self, value: float = 1.0):
        self.value = value

    def reset(self, agents: list[str], initial_state: CartPoleState, shared_info: dict[str, Any]) -> None:
        pass

    def get_rewards(self, agents: list[str], state: CartPoleState, is_terminated: dict[str, bool],
                    is_truncated: dict[str, bool], shared_info: dict[str, Any]) -> dict[str, float]:
        return {agent: 0.0 if is_terminated[agent] else self.value for agent in agents}


class UprightReward(RewardFunction[str, CartPoleState, float]):
    """A smooth balance reward: `scale` × cos(pole angle), so 1 × scale when perfectly upright and
    less as the pole leans. Gives a signal even before the pole falls."""

    def __init__(self, scale: float = 1.0):
        self.scale = scale

    def reset(self, agents: list[str], initial_state: CartPoleState, shared_info: dict[str, Any]) -> None:
        pass

    def get_rewards(self, agents: list[str], state: CartPoleState, is_terminated: dict[str, bool],
                    is_truncated: dict[str, bool], shared_info: dict[str, Any]) -> dict[str, float]:
        return {agent: self.scale * float(np.cos(state.theta[state.index(agent)])) for agent in agents}


class PositionPenalty(RewardFunction[str, CartPoleState, float]):
    """Penalizes drifting away from the centre: -`weight` × |position|^`power`. Keeps agents from
    balancing by running off to one side."""

    def __init__(self, weight: float = 0.1, power: int = 2):
        self.weight = weight
        self.power = power

    def reset(self, agents: list[str], initial_state: CartPoleState, shared_info: dict[str, Any]) -> None:
        pass

    def get_rewards(self, agents: list[str], state: CartPoleState, is_terminated: dict[str, bool],
                    is_truncated: dict[str, bool], shared_info: dict[str, Any]) -> dict[str, float]:
        return {agent: -self.weight * abs(float(state.x[state.index(agent)])) ** self.power for agent in agents}


class CombinedReward(RewardFunction[str, CartPoleState, float]):
    """The weighted sum of other rewards, e.g. `[AliveReward(), PositionPenalty(0.5)]` with weights
    `[1.0, 2.0]`. Without `weights`, every reward counts once."""

    def __init__(self, rewards: list[RewardFunction], weights: list[float] | None = None):
        if not rewards:
            raise ValueError("rewards must not be empty")
        if weights is not None and len(weights) != len(rewards):
            raise ValueError(f"got {len(weights)} weights for {len(rewards)} rewards")
        self.rewards = list(rewards)
        self.weights = list(weights) if weights is not None else [1.0] * len(rewards)

    def reset(self, agents: list[str], initial_state: CartPoleState, shared_info: dict[str, Any]) -> None:
        for reward in self.rewards:
            reward.reset(agents, initial_state, shared_info)

    def get_rewards(self, agents: list[str], state: CartPoleState, is_terminated: dict[str, bool],
                    is_truncated: dict[str, bool], shared_info: dict[str, Any]) -> dict[str, float]:
        total = {agent: 0.0 for agent in agents}
        for reward, weight in zip(self.rewards, self.weights):
            for agent, value in reward.get_rewards(agents, state, is_terminated, is_truncated, shared_info).items():
                total[agent] += weight * value
        return total
