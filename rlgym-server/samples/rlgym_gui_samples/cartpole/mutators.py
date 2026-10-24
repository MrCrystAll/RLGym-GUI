from typing import Any

import numpy as np
from rlgym.api import StateMutator

from .state import CartPoleState

PLANETS = {"earth": 9.8, "moon": 1.62, "mars": 3.71, "jupiter": 24.79}
WIND_DIRECTIONS = ("left", "right", "random")


class UprightStart(StateMutator[CartPoleState]):
    """Starts every cart at the centre, still, with its pole perfectly upright. Deterministic: without
    control the pole stays balanced forever, which makes it a good baseline to compare with."""

    def apply(self, state: CartPoleState, shared_info: dict[str, Any]) -> None:
        for arr in (state.x, state.x_dot, state.theta, state.theta_dot):
            arr[:] = 0.0


class RandomStart(StateMutator[CartPoleState]):
    """Starts each cart with its position, velocity, pole angle and angular velocity drawn uniformly
    from [-spread, spread], like Gym's CartPole (spread 0.05). Use `seed` for reproducible starts."""

    def __init__(self, spread: float = 0.05, seed: int | None = None):
        self.spread = spread
        self._rng = np.random.default_rng(seed)

    def apply(self, state: CartPoleState, shared_info: dict[str, Any]) -> None:
        for arr in (state.x, state.x_dot, state.theta, state.theta_dot):
            arr[:] = self._rng.uniform(-self.spread, self.spread, size=arr.shape)


class Gravity(StateMutator[CartPoleState]):
    """Sets the gravitational acceleration, in m/s². Give `planet` ("earth", "moon", "mars" or
    "jupiter") to use that planet's gravity instead of `gravity`. Lower gravity makes the pole fall
    more slowly and the task easier."""

    def __init__(self, gravity: float = 9.8, planet: str | None = None):
        if planet is not None and planet not in PLANETS:
            raise ValueError(f"planet must be one of {sorted(PLANETS)}, got {planet!r}")
        self.gravity = PLANETS[planet] if planet else gravity

    def apply(self, state: CartPoleState, shared_info: dict[str, Any]) -> None:
        state.gravity = self.gravity


class PoleLength(StateMutator[CartPoleState]):
    """Sets the length of the pole, in metres (the classic task uses 1.0). Longer poles fall more
    slowly. With `randomize`, each reset picks a length uniformly within ±`spread` of `length`.
    Rejects lengths that aren't positive."""

    def __init__(self, length: float = 1.0, randomize: bool = False, spread: float = 0.2, seed: int | None = None):
        if length <= 0:
            raise ValueError(f"length must be positive, got {length}")
        if randomize and spread >= length:
            raise ValueError(f"spread ({spread}) must be smaller than length ({length})")
        self.length = length
        self.randomize = randomize
        self.spread = spread
        self._rng = np.random.default_rng(seed)

    def apply(self, state: CartPoleState, shared_info: dict[str, Any]) -> None:
        length = self.length
        if self.randomize:
            length = self._rng.uniform(length - self.spread, length + self.spread)
        state.half_pole_length = length / 2


class Wind(StateMutator[CartPoleState]):
    """Adds a constant sideways force of `strength` newtons to every cart, blowing "left", "right" or
    in a "random" direction picked at each reset, plus random gusts with standard deviation
    `gust_std` newtons each tick (drawn by the engine, so they follow the engine's seed)."""

    def __init__(self, strength: float = 1.0, direction: str = "right", gust_std: float = 0.0,
                 seed: int | None = None):
        if direction not in WIND_DIRECTIONS:
            raise ValueError(f"direction must be one of {WIND_DIRECTIONS}, got {direction!r}")
        self.strength = strength
        self.direction = direction
        self.gust_std = gust_std
        self._rng = np.random.default_rng(seed)

    def apply(self, state: CartPoleState, shared_info: dict[str, Any]) -> None:
        direction = self.direction
        if direction == "random":
            direction = self._rng.choice(["left", "right"])
        state.wind = self.strength if direction == "right" else -self.strength
        state.wind_gust_std = self.gust_std


class MutatorSequence(StateMutator[CartPoleState]):
    """Applies several mutators in order, e.g. `[RandomStart(), Gravity(planet="moon"), Wind(2.0)]`:
    the way to combine a start position with physics changes in one slot."""

    def __init__(self, mutators: list[StateMutator]):
        if not mutators:
            raise ValueError("mutators must not be empty")
        self.mutators = list(mutators)

    def apply(self, state: CartPoleState, shared_info: dict[str, Any]) -> None:
        for mutator in self.mutators:
            mutator.apply(state, shared_info)


class UnstableMutator(StateMutator[CartPoleState]):
    """Fails on purpose: its constructor always raises, to see how the GUI reports a component that
    can't be built. `reason` is included in the error message."""

    def __init__(self, reason: str = "this mutator is broken on purpose"):
        raise RuntimeError(f"UnstableMutator can't be built: {reason}")

    def apply(self, state: CartPoleState, shared_info: dict[str, Any]) -> None:  # pragma: no cover
        pass
