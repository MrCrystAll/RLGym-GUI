from typing import Any

import numpy as np
from rlgym.api import TransitionEngine

from .state import CartPoleState

INTEGRATORS = ("euler", "semi-implicit")


class CartPoleEngine(TransitionEngine[str, CartPoleState, float]):
    """Classic cart-pole physics: each agent pushes its own cart left or right to keep a hinged pole
    upright. Carts are independent (no collisions), so `n_carts` simply runs several balancing tasks
    side by side. `tau` is the time step in seconds; `integrator` is "euler" (as in the original
    task) or "semi-implicit" (more stable). `seed` drives the random wind gusts."""

    def __init__(self, n_carts: int = 1, tau: float = 0.02, integrator: str = "euler", seed: int | None = None):
        if n_carts < 1:
            raise ValueError(f"n_carts must be at least 1, got {n_carts}")
        if integrator not in INTEGRATORS:
            raise ValueError(f"integrator must be one of {INTEGRATORS}, got {integrator!r}")
        self.n_carts = n_carts
        self.tau = tau
        self.integrator = integrator
        self.seed = seed
        self._rng = np.random.default_rng(seed)
        self._state = CartPoleState.upright(n_carts)

    @property
    def agents(self) -> list[str]:
        return list(self._state.agents)

    @property
    def max_num_agents(self) -> int:
        return self.n_carts

    @property
    def state(self) -> CartPoleState:
        return self._state

    @property
    def config(self) -> dict[str, Any]:
        return {"n_carts": self.n_carts, "tau": self.tau, "integrator": self.integrator, "seed": self.seed}

    @config.setter
    def config(self, value: dict[str, Any]):
        self.tau = value.get("tau", self.tau)
        self.integrator = value.get("integrator", self.integrator)

    def create_base_state(self) -> CartPoleState:
        return CartPoleState.upright(self.n_carts)

    def set_state(self, desired_state: CartPoleState, shared_info: dict[str, Any]) -> CartPoleState:
        self._state = desired_state.copy()
        return self._state

    def step(self, actions: dict[str, float], shared_info: dict[str, Any]) -> CartPoleState:
        s = self._state
        force = np.array([float(actions.get(agent, 0.0)) for agent in s.agents]) + s.wind
        if s.wind_gust_std > 0:
            force = force + self._rng.normal(0.0, s.wind_gust_std, size=len(s.agents))

        # Equations of motion from Florian (2007), as used by Gym's CartPole.
        total_mass = s.mass_cart + s.mass_pole
        polemass_length = s.mass_pole * s.half_pole_length
        cos, sin = np.cos(s.theta), np.sin(s.theta)
        temp = (force + polemass_length * s.theta_dot ** 2 * sin) / total_mass
        theta_acc = (s.gravity * sin - cos * temp) / (
            s.half_pole_length * (4.0 / 3.0 - s.mass_pole * cos ** 2 / total_mass))
        x_acc = temp - polemass_length * theta_acc * cos / total_mass

        if self.integrator == "euler":
            s.x = s.x + self.tau * s.x_dot
            s.x_dot = s.x_dot + self.tau * x_acc
            s.theta = s.theta + self.tau * s.theta_dot
            s.theta_dot = s.theta_dot + self.tau * theta_acc
        else:
            s.x_dot = s.x_dot + self.tau * x_acc
            s.x = s.x + self.tau * s.x_dot
            s.theta_dot = s.theta_dot + self.tau * theta_acc
            s.theta = s.theta + self.tau * s.theta_dot
        s.tick += 1
        return s

    def close(self) -> None:
        pass
