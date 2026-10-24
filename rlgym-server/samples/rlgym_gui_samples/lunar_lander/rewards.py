import math
from typing import Any

from rlgym.api import DoneCondition, RewardFunction

from .state import LunarState


class ShapingReward(RewardFunction[str, LunarState, float]):
    """gymnasium's shaping: rewards getting closer to the pad, slowing down, staying level and
    touching the ground with the legs. Each step pays the change in
    `-distance_weight·distance - velocity_weight·speed - angle_weight·|angle| + leg_contact_bonus·legs`
    (in the observation's scaled units), so hovering in place earns nothing."""

    def __init__(self, distance_weight: float = 100.0, velocity_weight: float = 100.0,
                 angle_weight: float = 100.0, leg_contact_bonus: float = 10.0):
        self.distance_weight = distance_weight
        self.velocity_weight = velocity_weight
        self.angle_weight = angle_weight
        self.leg_contact_bonus = leg_contact_bonus
        self._previous: dict[str, float] = {}

    def _shaping(self, state: LunarState, agent: str) -> float:
        s = state.classic_obs(agent)
        return (-self.distance_weight * math.hypot(s[0], s[1])
                - self.velocity_weight * math.hypot(s[2], s[3])
                - self.angle_weight * abs(s[4])
                + self.leg_contact_bonus * (s[6] + s[7]))

    def reset(self, agents: list[str], initial_state: LunarState, shared_info: dict[str, Any]) -> None:
        self._previous = {a: self._shaping(initial_state, a) for a in agents}

    def get_rewards(self, agents: list[str], state: LunarState, is_terminated: dict[str, bool],
                    is_truncated: dict[str, bool], shared_info: dict[str, Any]) -> dict[str, float]:
        out = {}
        for a in agents:
            shaping = self._shaping(state, a)
            out[a] = shaping - self._previous.get(a, shaping)
            self._previous[a] = shaping
        return out


class FuelCost(RewardFunction[str, LunarState, float]):
    """A penalty for every step an engine fires, proportional to its power: `main_cost` for the
    main engine and `side_cost` for the side engines (gymnasium's 0.3 and 0.03)."""

    def __init__(self, main_cost: float = 0.3, side_cost: float = 0.03):
        self.main_cost = main_cost
        self.side_cost = side_cost

    def reset(self, agents: list[str], initial_state: LunarState, shared_info: dict[str, Any]) -> None:
        pass

    def get_rewards(self, agents: list[str], state: LunarState, is_terminated: dict[str, bool],
                    is_truncated: dict[str, bool], shared_info: dict[str, Any]) -> dict[str, float]:
        return {a: -(self.main_cost * state.landers[a].main_power + self.side_cost * state.landers[a].side_power)
                for a in agents}


class LandingReward(RewardFunction[str, LunarState, float]):
    """Pays `landed_bonus` once when the lander lands and `crash_penalty` once when it crashes or
    leaves the screen. Landing means coming to rest, as in gymnasium, unless `landed_condition` is
    given (e.g. `Landed(require_both_legs=False)`)."""

    def __init__(self, landed_bonus: float = 100.0, crash_penalty: float = -100.0,
                 landed_condition: DoneCondition | None = None):
        self.landed_bonus = landed_bonus
        self.crash_penalty = crash_penalty
        self.landed_condition = landed_condition
        self._paid: set[str] = set()

    def reset(self, agents: list[str], initial_state: LunarState, shared_info: dict[str, Any]) -> None:
        self._paid = set()
        if self.landed_condition is not None:
            self.landed_condition.reset(agents, initial_state, shared_info)

    def get_rewards(self, agents: list[str], state: LunarState, is_terminated: dict[str, bool],
                    is_truncated: dict[str, bool], shared_info: dict[str, Any]) -> dict[str, float]:
        landed = (self.landed_condition.is_done(agents, state, shared_info) if self.landed_condition
                  else {a: state.landers[a].at_rest and not state.landers[a].crashed for a in agents})
        out = {}
        for a in agents:
            reward = 0.0
            if a not in self._paid:
                if state.landers[a].crashed or state.out_of_bounds(a):
                    reward = self.crash_penalty
                elif landed[a]:
                    reward = self.landed_bonus
                if reward:
                    self._paid.add(a)
            out[a] = reward
        return out


class WeightedSum(RewardFunction[str, LunarState, float]):
    """Adds up other rewards, e.g. `[ShapingReward(), FuelCost()]`, each multiplied by its weight
    in `weights` (all 1 when None)."""

    def __init__(self, rewards: list[RewardFunction], weights: list[float] | None = None):
        if not rewards:
            raise ValueError("rewards must not be empty")
        if weights is not None and len(weights) != len(rewards):
            raise ValueError(f"got {len(rewards)} rewards but {len(weights)} weights")
        self.rewards = list(rewards)
        self.weights = list(weights) if weights is not None else [1.0] * len(rewards)

    def reset(self, agents: list[str], initial_state: LunarState, shared_info: dict[str, Any]) -> None:
        for r in self.rewards:
            r.reset(agents, initial_state, shared_info)

    def get_rewards(self, agents: list[str], state: LunarState, is_terminated: dict[str, bool],
                    is_truncated: dict[str, bool], shared_info: dict[str, Any]) -> dict[str, float]:
        total = {a: 0.0 for a in agents}
        for reward, weight in zip(self.rewards, self.weights):
            for a, value in reward.get_rewards(agents, state, is_terminated, is_truncated, shared_info).items():
                total[a] += weight * value
        return total


class ClassicReward(WeightedSum):
    """gymnasium's full LunarLander reward: ShapingReward + FuelCost + LandingReward with their
    default values. An episode scoring 200 or more counts as solved."""

    def __init__(self):
        super().__init__([ShapingReward(), FuelCost(), LandingReward()])
