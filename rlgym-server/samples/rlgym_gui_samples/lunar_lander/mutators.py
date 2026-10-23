from typing import Any, Literal

import numpy as np
from rlgym.api import StateMutator

from .state import CHUNKS, H, LunarState


class RandomTerrain(StateMutator[LunarState]):
    """Random hills around a flat landing pad, like gymnasium's terrain. `roughness` scales the
    hills (0 is flat ground, 1 is gymnasium's) and `pad_half_width` is how many terrain points on
    each side of the centre stay flat for the pad. `seed` makes the terrain repeatable."""

    def __init__(self, roughness: float = 1.0, pad_half_width: int = 2, seed: int | None = None):
        if not 0 <= pad_half_width <= CHUNKS // 2:
            raise ValueError(f"pad_half_width must be between 0 and {CHUNKS // 2}, got {pad_half_width}")
        self.roughness = roughness
        self.pad_half_width = pad_half_width
        self._rng = np.random.default_rng(seed)

    def apply(self, state: LunarState, shared_info: dict[str, Any]) -> None:
        height = self._rng.uniform(0, H / 2, size=(CHUNKS + 1,)) * self.roughness
        mid = CHUNKS // 2
        height[mid - self.pad_half_width: mid + self.pad_half_width + 1] = state.helipad_y
        state.terrain_y = [float(0.33 * (height[i - 1] + height[i] + height[i + 1])) for i in range(CHUNKS)]
        # Smoothing pulls the pad edges down a little; keep the pad itself exactly flat.
        for i in range(mid - self.pad_half_width + 1, mid + self.pad_half_width):
            state.terrain_y[i] = state.helipad_y


class RandomStart(StateMutator[LunarState]):
    """Gives every lander a random push when it appears, as gymnasium does (`max_force` newtons in
    each direction; 1000 is gymnasium's), and optionally shifts it sideways by up to `max_offset_x`
    metres and tilts it by up to `max_tilt` radians. `seed` makes the starts repeatable."""

    def __init__(self, max_force: float = 1000.0, max_offset_x: float = 0.0, max_tilt: float = 0.0,
                 seed: int | None = None):
        self.max_force = max_force
        self.max_offset_x = max_offset_x
        self.max_tilt = max_tilt
        self._rng = np.random.default_rng(seed)

    def apply(self, state: LunarState, shared_info: dict[str, Any]) -> None:
        for lander in state.landers.values():
            lander.push = (float(self._rng.uniform(-self.max_force, self.max_force)),
                           float(self._rng.uniform(-self.max_force, self.max_force)))
            lander.x += float(self._rng.uniform(-self.max_offset_x, self.max_offset_x))
            lander.angle = float(self._rng.uniform(-self.max_tilt, self.max_tilt))


class Gravity(StateMutator[LunarState]):
    """Sets gravity in m/s² (negative pulls down). The Moon's is about -1.6; gymnasium uses -10.
    Values from -20 up to (not including) 0 are accepted: anything else is rejected when the
    component is built, which shows how the GUI reports a constructor error."""

    def __init__(self, gravity: float = -10.0):
        if not -20.0 <= gravity < 0.0:
            raise ValueError(f"gravity must be between -20 and 0 (negative pulls down), got {gravity}")
        self.gravity = gravity

    def apply(self, state: LunarState, shared_info: dict[str, Any]) -> None:
        state.gravity = self.gravity


PRESET_GRAVITY = {"moon": -1.62, "mars": -3.71, "titan": -1.35, "gymnasium": -10.0}


class PlanetPreset(StateMutator[LunarState]):
    """Picks gravity from a named body: "moon", "mars", "titan", or "gymnasium" (the -10 m/s² the
    original environment uses). Lower gravity means a slower fall but also a floatier lander."""

    def __init__(self, body: Literal["moon", "mars", "titan", "gymnasium"] = "moon"):
        if body not in PRESET_GRAVITY:
            raise ValueError(f"body must be one of {', '.join(PRESET_GRAVITY)}, got {body!r}")
        self.body = body

    def apply(self, state: LunarState, shared_info: dict[str, Any]) -> None:
        state.gravity = PRESET_GRAVITY[self.body]


class Wind(StateMutator[LunarState]):
    """Turns on gymnasium's wind: a sideways force of up to `wind_power` newtons and a rotating
    torque of up to `turbulence_power`, both varying smoothly over time, and only while the lander
    is airborne. gymnasium recommends at most 20 and 2."""

    def __init__(self, wind_power: float = 15.0, turbulence_power: float = 1.5):
        if wind_power < 0 or turbulence_power < 0:
            raise ValueError("wind_power and turbulence_power can't be negative")
        self.wind_power = wind_power
        self.turbulence_power = turbulence_power

    def apply(self, state: LunarState, shared_info: dict[str, Any]) -> None:
        state.wind_power = self.wind_power
        state.turbulence_power = self.turbulence_power


class Mutators(StateMutator[LunarState]):
    """Applies several mutators in order, e.g. `[RandomTerrain(), RandomStart(), Wind(10.0)]`:
    the RLGym config only takes one state mutator."""

    def __init__(self, mutators: list[StateMutator]):
        if not mutators:
            raise ValueError("mutators must not be empty")
        self.mutators = list(mutators)

    def apply(self, state: LunarState, shared_info: dict[str, Any]) -> None:
        for mutator in self.mutators:
            mutator.apply(state, shared_info)
