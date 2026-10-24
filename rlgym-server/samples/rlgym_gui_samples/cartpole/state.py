"""The cart-pole state: one cart (agent) per array entry, plus the physics the mutators can change."""
from dataclasses import dataclass, field, replace

import numpy as np

# Defaults of the classic cart-pole (Barto, Sutton & Anderson 1983; OpenAI Gym's CartPole-v1).
GRAVITY = 9.8
MASS_CART = 1.0
MASS_POLE = 0.1
HALF_POLE_LENGTH = 0.5


def agent_ids(n_carts: int) -> list[str]:
    return [f"cart_{i}" for i in range(n_carts)]


@dataclass
class CartPoleState:
    """Positions are in metres, angles in radians (0 = upright, positive = leaning right)."""
    x: np.ndarray
    x_dot: np.ndarray
    theta: np.ndarray
    theta_dot: np.ndarray
    gravity: float = GRAVITY
    mass_cart: float = MASS_CART
    mass_pole: float = MASS_POLE
    half_pole_length: float = HALF_POLE_LENGTH
    wind: float = 0.0              # constant horizontal force on every cart, in newtons
    wind_gust_std: float = 0.0     # standard deviation of a random force added each tick
    tick: int = 0
    agents: list[str] = field(default_factory=list)

    @classmethod
    def upright(cls, n_carts: int) -> "CartPoleState":
        zeros = lambda: np.zeros(n_carts, dtype=np.float64)
        return cls(x=zeros(), x_dot=zeros(), theta=zeros(), theta_dot=zeros(), agents=agent_ids(n_carts))

    def index(self, agent: str) -> int:
        return self.agents.index(agent)

    def copy(self) -> "CartPoleState":
        return replace(self, x=self.x.copy(), x_dot=self.x_dot.copy(), theta=self.theta.copy(),
                       theta_dot=self.theta_dot.copy(), agents=list(self.agents))
