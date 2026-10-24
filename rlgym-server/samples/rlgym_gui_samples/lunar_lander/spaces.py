"""Minimal observation/action spaces. rlgym.api leaves the space types open; these two cover the
lander and know how to sample themselves, which the tests and a random-action stepper need."""
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Discrete:
    n: int

    def sample(self, rng: np.random.Generator) -> int:
        return int(rng.integers(self.n))

    def contains(self, x) -> bool:
        return isinstance(x, (int, np.integer)) and 0 <= x < self.n


@dataclass(frozen=True)
class Box:
    low: tuple[float, ...]
    high: tuple[float, ...]

    @property
    def shape(self) -> tuple[int, ...]:
        return (len(self.low),)

    def sample(self, rng: np.random.Generator) -> np.ndarray:
        low, high = np.asarray(self.low), np.asarray(self.high)
        # Unbounded dimensions sample from a normal distribution, like gymnasium's Box.
        bounded = np.isfinite(low) & np.isfinite(high)
        out = rng.normal(size=len(low))
        out[bounded] = rng.uniform(low[bounded], high[bounded])
        return out.astype(np.float32)

    def contains(self, x) -> bool:
        x = np.asarray(x)
        return x.shape == self.shape and bool(np.all(x >= self.low) and np.all(x <= self.high))
