"""The lander's state as plain data, separate from the Box2D world the engine builds from it.

Mutators edit a LunarState (terrain, gravity, wind, where each lander starts); the engine turns it
into Box2D bodies in set_state() and copies the bodies back into it after every step.

Constants and geometry come from gymnasium's LunarLander (MIT licence,
https://github.com/Farama-Foundation/Gymnasium/blob/main/gymnasium/envs/box2d/lunar_lander.py).
"""
import copy
import math
from dataclasses import dataclass, field

FPS = 50
SCALE = 30.0                    # pixels per metre in gymnasium's viewport; the geometry is in pixels

MAIN_ENGINE_POWER = 13.0
SIDE_ENGINE_POWER = 0.6
MAIN_ENGINE_Y_LOCATION = 4
SIDE_ENGINE_HEIGHT = 14
SIDE_ENGINE_AWAY = 12

LANDER_POLY = [(-14, +17), (-17, 0), (-17, -10), (+17, -10), (+17, 0), (+14, +17)]
LEG_AWAY = 20
LEG_DOWN = 18
LEG_W, LEG_H = 2, 8
LEG_SPRING_TORQUE = 40

VIEWPORT_W = 600
VIEWPORT_H = 400
W = VIEWPORT_W / SCALE          # world width, metres
H = VIEWPORT_H / SCALE          # world height, metres
CHUNKS = 11                     # terrain points
HELIPAD_Y = H / 4


def chunk_x() -> list[float]:
    return [W / (CHUNKS - 1) * i for i in range(CHUNKS)]


@dataclass
class LanderState:
    """One lander. Positions in metres, angle in radians."""
    x: float = W / 2
    y: float = H
    vx: float = 0.0
    vy: float = 0.0
    angle: float = 0.0
    angular_velocity: float = 0.0
    # Applied once when the lander is created, like gymnasium's random initial push (newtons).
    push: tuple[float, float] = (0.0, 0.0)
    legs_contact: tuple[bool, bool] = (False, False)
    crashed: bool = False                # the body (not a leg) touched the ground; stays True
    at_rest: bool = False                # Box2D put the body to sleep: it has stopped moving
    main_power: float = 0.0              # throttle used on the last step, 0..1
    side_power: float = 0.0              # side engine used on the last step, 0..1
    fuel_used: float = 0.0               # sum of main + side power over the episode


@dataclass
class LunarState:
    terrain_y: list[float] = field(default_factory=lambda: [HELIPAD_Y] * CHUNKS)
    helipad_x1: float = chunk_x()[CHUNKS // 2 - 1]
    helipad_x2: float = chunk_x()[CHUNKS // 2 + 1]
    helipad_y: float = HELIPAD_Y
    gravity: float = -10.0
    wind_power: float = 0.0              # 0: no wind
    turbulence_power: float = 0.0        # 0: no turbulence
    landers: dict[str, LanderState] = field(default_factory=dict)
    tick: int = 0

    def copy(self) -> "LunarState":
        return copy.deepcopy(self)

    # The classic 8-value observation of one lander, as gymnasium computes it.
    def classic_obs(self, agent: str) -> list[float]:
        lander = self.landers[agent]
        return [
            (lander.x - W / 2) / (W / 2),
            (lander.y - (self.helipad_y + LEG_DOWN / SCALE)) / (H / 2),
            lander.vx * (W / 2) / FPS,
            lander.vy * (H / 2) / FPS,
            lander.angle,
            20.0 * lander.angular_velocity / FPS,
            1.0 if lander.legs_contact[0] else 0.0,
            1.0 if lander.legs_contact[1] else 0.0,
        ]

    def out_of_bounds(self, agent: str, max_abs_x: float = 1.0) -> bool:
        return abs(self.classic_obs(agent)[0]) >= max_abs_x

    def pad_center(self) -> tuple[float, float]:
        return (self.helipad_x1 + self.helipad_x2) / 2, self.helipad_y


def lander_names(n: int) -> list[str]:
    return [f"lander_{i}" for i in range(n)]


def start_x(i: int, n: int) -> float:
    """Landers start side by side above the pad, 3 m apart."""
    return W / 2 + (i - (n - 1) / 2) * 3.0


def rotate(x: float, y: float, angle: float) -> tuple[float, float]:
    c, s = math.cos(angle), math.sin(angle)
    return x * c - y * s, x * s + y * c
