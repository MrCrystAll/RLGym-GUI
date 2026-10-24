"""The Box2D physics behind the lander.

Adapted from gymnasium's LunarLander (MIT licence,
https://github.com/Farama-Foundation/Gymnasium/blob/main/gymnasium/envs/box2d/lunar_lander.py):
same body, legs, engines and wind, rewritten as an rlgym.api TransitionEngine, without rendering,
and with any number of landers sharing the terrain (they don't collide with each other).
"""
import math
import warnings
from typing import Any

import numpy as np
from rlgym.api import TransitionEngine

with warnings.catch_warnings():
    # Box2D's SWIG bindings trip "builtin type ... has no __module__" on Python 3.12; harmless.
    warnings.filterwarnings("ignore", "builtin type .* has no __module__", DeprecationWarning)
    import Box2D
    from Box2D.b2 import edgeShape, fixtureDef, polygonShape, revoluteJointDef

from .state import (
    CHUNKS, FPS, LANDER_POLY, LEG_AWAY, LEG_DOWN, LEG_H, LEG_SPRING_TORQUE, LEG_W,
    MAIN_ENGINE_POWER, MAIN_ENGINE_Y_LOCATION, SCALE, SIDE_ENGINE_AWAY, SIDE_ENGINE_HEIGHT,
    SIDE_ENGINE_POWER, W, LanderState, LunarState, chunk_x, lander_names, rotate, start_x,
)

# Collision categories: landers and legs only collide with the terrain (category 1), not each other.
TERRAIN, LANDER, LEG = 0x0001, 0x0010, 0x0020


class _Contacts(Box2D.b2ContactListener):
    """Tracks which legs touch the ground and which landers' bodies hit it."""

    def __init__(self, engine: "LunarLanderEngine"):
        super().__init__()
        self.engine = engine

    def _touch(self, contact, touching: bool):
        for body in (contact.fixtureA.body, contact.fixtureB.body):
            tag = body.userData
            if not tag:
                continue
            agent, part = tag
            if part == "body" and touching:
                self.engine._crashed[agent] = True
            elif part in (0, 1):
                self.engine._legs[agent][part] = touching

    def BeginContact(self, contact):
        self._touch(contact, True)

    def EndContact(self, contact):
        self._touch(contact, False)


class LunarLanderEngine(TransitionEngine[str, LunarState, np.ndarray]):
    """Box2D physics for one or more lunar landers over a shared terrain, adapted from gymnasium's
    LunarLander. Each lander takes an engine action [main, side]: main throttle 0..1 and side engine
    -1..1 (negative fires the left engine). Landers start above the pad and don't collide with each
    other. `seed` fixes the engine's randomness (exhaust dispersion, wind phase); `fps` is the
    simulation rate (gymnasium uses 50)."""

    def __init__(self, n_landers: int = 1, seed: int | None = None, fps: int = FPS):
        if n_landers < 1:
            raise ValueError(f"n_landers must be at least 1, got {n_landers}")
        if fps <= 0:
            raise ValueError(f"fps must be positive, got {fps}")
        self.n_landers = n_landers
        self.fps = fps
        self._rng = np.random.default_rng(seed)
        self._world: Box2D.b2World | None = None
        self._state = LunarState()
        self._bodies: dict[str, Any] = {}
        self._leg_bodies: dict[str, list[Any]] = {}
        self._legs: dict[str, list[bool]] = {}
        self._crashed: dict[str, bool] = {}
        self._wind_idx: dict[str, int] = {}
        self._torque_idx: dict[str, int] = {}
        self._contacts = _Contacts(self)

    # --- TransitionEngine -------------------------------------------------------------------

    @property
    def agents(self) -> list[str]:
        return list(self._state.landers)

    @property
    def max_num_agents(self) -> int:
        return self.n_landers

    @property
    def state(self) -> LunarState:
        return self._state

    @property
    def config(self) -> dict[str, Any]:
        return {"n_landers": self.n_landers, "fps": self.fps}

    @config.setter
    def config(self, value: dict[str, Any]):
        self.n_landers = value.get("n_landers", self.n_landers)
        self.fps = value.get("fps", self.fps)

    def create_base_state(self) -> LunarState:
        """Flat ground at pad height, no wind, every lander at the top, still and upright."""
        names = lander_names(self.n_landers)
        return LunarState(landers={a: LanderState(x=start_x(i, len(names))) for i, a in enumerate(names)})

    def set_state(self, desired_state: LunarState, shared_info: dict[str, Any]) -> LunarState:
        self._destroy()
        state = desired_state.copy()
        state.tick = 0
        world = Box2D.b2World(gravity=(0, state.gravity))
        world.contactListener = self._contacts
        self._world = world

        moon = world.CreateStaticBody(shapes=edgeShape(vertices=[(0, 0), (W, 0)]))
        xs = chunk_x()
        for i in range(CHUNKS - 1):
            moon.CreateEdgeFixture(vertices=[(xs[i], state.terrain_y[i]), (xs[i + 1], state.terrain_y[i + 1])],
                                   density=0, friction=0.1)

        for agent, lander in state.landers.items():
            self._create_lander(agent, lander)
            lander.crashed = lander.at_rest = False
            lander.legs_contact = (False, False)
            lander.main_power = lander.side_power = lander.fuel_used = 0.0
        self._state = state
        self._sync()
        return self._state

    def step(self, actions: dict[str, np.ndarray], shared_info: dict[str, Any]) -> LunarState:
        state = self._state
        for agent, action in actions.items():
            if agent in self._bodies:
                self._apply(agent, np.asarray(action, dtype=np.float64), state)
        self._world.Step(1.0 / self.fps, 6 * 30, 2 * 30)
        state.tick += 1
        self._sync()
        return state

    def close(self) -> None:
        self._destroy()

    # --- internals --------------------------------------------------------------------------

    def _create_lander(self, agent: str, lander: LanderState):
        world = self._world
        body = world.CreateDynamicBody(
            position=(lander.x, lander.y), angle=lander.angle,
            fixtures=fixtureDef(
                shape=polygonShape(vertices=[(x / SCALE, y / SCALE) for x, y in LANDER_POLY]),
                density=5.0, friction=0.1, categoryBits=LANDER, maskBits=TERRAIN, restitution=0.0,
            ),
        )
        body.userData = (agent, "body")
        body.linearVelocity = (lander.vx, lander.vy)
        body.angularVelocity = lander.angular_velocity
        legs = []
        for side, i in enumerate((-1, +1)):
            dx, dy = rotate(-i * LEG_AWAY / SCALE, 0.0, lander.angle)
            leg = world.CreateDynamicBody(
                position=(lander.x + dx, lander.y + dy), angle=lander.angle + i * 0.05,
                fixtures=fixtureDef(shape=polygonShape(box=(LEG_W / SCALE, LEG_H / SCALE)),
                                    density=1.0, restitution=0.0, categoryBits=LEG, maskBits=TERRAIN),
            )
            leg.userData = (agent, side)
            leg.linearVelocity = (lander.vx, lander.vy)
            rjd = revoluteJointDef(
                bodyA=body, bodyB=leg, localAnchorA=(0, 0), localAnchorB=(i * LEG_AWAY / SCALE, LEG_DOWN / SCALE),
                enableMotor=True, enableLimit=True, maxMotorTorque=LEG_SPRING_TORQUE, motorSpeed=+0.3 * i,
            )
            if i == -1:
                rjd.lowerAngle, rjd.upperAngle = 0.9 - 0.5, 0.9
            else:
                rjd.lowerAngle, rjd.upperAngle = -0.9, -0.9 + 0.5
            world.CreateJoint(rjd)
            legs.append(leg)
        if lander.push != (0.0, 0.0):
            body.ApplyForceToCenter(tuple(float(f) for f in lander.push), True)
        self._bodies[agent] = body
        self._leg_bodies[agent] = legs
        self._legs[agent] = [False, False]
        self._crashed[agent] = False
        # Random phase for the wind and turbulence curves, as gymnasium does.
        self._wind_idx[agent] = int(self._rng.integers(-9999, 9999))
        self._torque_idx[agent] = int(self._rng.integers(-9999, 9999))

    def _apply(self, agent: str, action: np.ndarray, state: LunarState):
        body = self._bodies[agent]
        lander = state.landers[agent]
        legs = self._legs[agent]
        if (state.wind_power or state.turbulence_power) and not any(legs):
            wi, ti = self._wind_idx[agent], self._torque_idx[agent]
            wind = math.tanh(math.sin(0.02 * wi) + math.sin(math.pi * 0.01 * wi)) * state.wind_power
            torque = math.tanh(math.sin(0.02 * ti) + math.sin(math.pi * 0.01 * ti)) * state.turbulence_power
            self._wind_idx[agent], self._torque_idx[agent] = wi + 1, ti + 1
            body.ApplyForceToCenter((wind, 0.0), True)
            body.ApplyTorque(torque, True)

        main = float(np.clip(action[0], 0.0, 1.0))
        side = float(np.clip(action[1], -1.0, 1.0))
        tip = (math.sin(body.angle), math.cos(body.angle))
        across = (-tip[1], tip[0])
        dispersion = [float(self._rng.uniform(-1.0, +1.0)) / SCALE for _ in range(2)]

        if main > 0.0:
            ox = tip[0] * (MAIN_ENGINE_Y_LOCATION / SCALE + 2 * dispersion[0]) + across[0] * dispersion[1]
            oy = -tip[1] * (MAIN_ENGINE_Y_LOCATION / SCALE + 2 * dispersion[0]) - across[1] * dispersion[1]
            pos = (body.position[0] + ox, body.position[1] + oy)
            body.ApplyLinearImpulse((-ox * MAIN_ENGINE_POWER * main, -oy * MAIN_ENGINE_POWER * main), pos, True)

        side_power = abs(side)
        if side_power > 0.0:
            direction = math.copysign(1.0, side)
            ox = tip[0] * dispersion[0] + across[0] * (3 * dispersion[1] + direction * SIDE_ENGINE_AWAY / SCALE)
            oy = -tip[1] * dispersion[0] - across[1] * (3 * dispersion[1] + direction * SIDE_ENGINE_AWAY / SCALE)
            pos = (body.position[0] + ox - tip[0] * 17 / SCALE, body.position[1] + oy + tip[1] * SIDE_ENGINE_HEIGHT / SCALE)
            body.ApplyLinearImpulse((-ox * SIDE_ENGINE_POWER * side_power, -oy * SIDE_ENGINE_POWER * side_power), pos, True)

        lander.main_power = main
        lander.side_power = side_power
        lander.fuel_used += main + side_power

    def _sync(self):
        """Copy the bodies back into the state."""
        for agent, body in self._bodies.items():
            lander = self._state.landers[agent]
            lander.x, lander.y = float(body.position[0]), float(body.position[1])
            lander.vx, lander.vy = float(body.linearVelocity[0]), float(body.linearVelocity[1])
            lander.angle = float(body.angle)
            lander.angular_velocity = float(body.angularVelocity)
            lander.legs_contact = (self._legs[agent][0], self._legs[agent][1])
            lander.crashed = lander.crashed or self._crashed[agent]
            lander.at_rest = not body.awake

    def _destroy(self):
        if self._world is None:
            return
        self._world.contactListener = None
        for body in list(self._world.bodies):
            self._world.DestroyBody(body)
        self._world = None
        self._bodies.clear()
        self._leg_bodies.clear()
        self._legs.clear()
        self._crashed.clear()

    @property
    def world(self) -> Box2D.b2World | None:
        """The current Box2D world (None before the first reset and after close)."""
        return self._world
