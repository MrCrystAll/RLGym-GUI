import numpy as np
import pytest
from rlgym.api import RLGym

from rlgym_gui_samples import cartpole as cp

from .helpers import run_episode


def make_env(n_carts=1, seed=0, mutator=None, obs=None, parser=None, reward=None,
             termination=None, truncation=None, shared=None, integrator="euler"):
    return RLGym(
        transition_engine=cp.CartPoleEngine(n_carts=n_carts, seed=seed, integrator=integrator),
        state_mutator=mutator or cp.RandomStart(seed=seed),
        obs_builder=obs or cp.CartPoleObs(),
        action_parser=parser or cp.DiscreteForce(),
        reward_fn=reward or cp.AliveReward(),
        termination_cond=termination if termination is not None else cp.AnyOf([cp.AngleLimit(), cp.OutOfBounds()]),
        truncation_cond=truncation if truncation is not None else cp.TickLimit(500),
        shared_info_provider=shared,
    )


def random_actor(seed=0):
    rng = np.random.default_rng(seed)

    def act(env):
        actions = {}
        for agent in env.agents:
            kind, size = env.action_space(agent)
            actions[agent] = int(rng.integers(size)) if kind == "discrete" else rng.uniform(-1, 1, size)
        return actions
    return act


def no_push(env):
    """0 for every agent: no force with ContinuousForce (with DiscreteForce, 0 is "push left")."""
    return {agent: 0.0 for agent in env.agents}


def uncontrolled_env(**parts):
    return make_env(parser=cp.ContinuousForce(), mutator=parts.pop("mutator", cp.UprightStart()),
                    termination=parts.pop("termination", cp.AngleLimit()), **parts)


def test_classic_cartpole_runs_and_random_play_falls_quickly():
    env = make_env()
    steps = run_episode(env, random_actor(), max_steps=500)
    assert 5 < steps < 200                               # random play drops the pole, but not instantly
    assert env.observation_space("cart_0") == ("real", 4)
    assert env.action_space("cart_0") == ("discrete", 2)


@pytest.mark.parametrize("parts", [
    dict(obs=cp.CartPoleObs(normalize=True), parser=cp.ContinuousForce(max_force=5.0)),
    dict(obs=cp.FullObs(include_others=True, history=2), parser=cp.DiscreteForce(n_levels=3), n_carts=3),
    dict(mutator=cp.MutatorSequence([cp.RandomStart(seed=1), cp.Gravity(planet="moon"),
                                     cp.PoleLength(2.0, randomize=True, seed=1), cp.Wind(1.0, "random", 0.5, seed=1)]),
         reward=cp.CombinedReward([cp.AliveReward(), cp.UprightReward(), cp.PositionPenalty(0.5)], [1.0, 0.5, 2.0]),
         shared=cp.EpisodeStats(), integrator="semi-implicit"),
    dict(termination=None, truncation=cp.TickLimit(50)),
])
def test_combinations_build_reset_and_step(parts):
    env = make_env(**parts)
    run_episode(env, random_actor(), max_steps=100)


def test_multi_cart_agents_and_obs_sizes():
    env = make_env(n_carts=3, obs=cp.FullObs(include_physics=True, include_others=True, history=1))
    obs = env.reset()
    assert env.agents == ["cart_0", "cart_1", "cart_2"]
    # (4 own + 3 physics + 2 other angles) x (history 1 + current)
    assert env.observation_space("cart_1") == ("real", 18)
    assert all(o.shape == (18,) for o in obs.values())


def test_upright_pole_stays_up_and_a_leaning_one_falls_without_control():
    env = uncontrolled_env()
    env.reset()
    for _ in range(200):
        _, _, terminated, _ = env.step(no_push(env))
    assert not terminated["cart_0"] and env.state.theta[0] == 0.0

    env = uncontrolled_env()
    env.reset()
    env.state.theta[0] = 0.01
    steps = 0
    while not env.step(no_push(env))[2]["cart_0"]:
        steps += 1
        assert steps < 500
    assert env.state.theta[0] > 0                        # fell the way it leaned


def ticks_to_fall(mutator):
    env = uncontrolled_env(mutator=cp.MutatorSequence([cp.UprightStart(), mutator]))
    env.reset()
    env.state.theta[:] = 0.05
    for tick in range(1, 1000):
        if env.step(no_push(env))[2]["cart_0"]:
            return tick
    raise AssertionError("pole never fell")


def test_gravity_and_pole_length_change_the_dynamics():
    earth = ticks_to_fall(cp.UprightStart())
    assert ticks_to_fall(cp.Gravity(planet="moon")) > earth
    assert ticks_to_fall(cp.Gravity(planet="jupiter")) < earth
    assert ticks_to_fall(cp.PoleLength(3.0)) > earth


def test_wind_pushes_the_carts():
    env = uncontrolled_env(mutator=cp.MutatorSequence([cp.UprightStart(), cp.Wind(5.0, "left")]))
    env.reset()
    for _ in range(10):
        env.step(no_push(env))
    assert env.state.x[0] < 0 and env.state.wind == -5.0


def test_rewards():
    env = uncontrolled_env(reward=cp.CombinedReward([cp.AliveReward(2.0), cp.PositionPenalty(1.0, 1)]))
    env.reset()
    env.state.x[0] = 0.5
    _, rewards, _, _ = env.step(no_push(env))
    assert rewards["cart_0"] == pytest.approx(2.0 - 0.5, abs=1e-6)


def test_tick_limit_and_episode_stats():
    env = uncontrolled_env(truncation=cp.TickLimit(7), shared=cp.EpisodeStats(key="stats"))
    assert run_episode(env, no_push, max_steps=50) == 7
    assert env.shared_info["stats"]["ticks"] == 7
    assert env.shared_info["stats"]["max_angle_deg"]["cart_0"] == 0.0


def test_same_seed_same_episode():
    def rollout():
        env = make_env(n_carts=2, seed=42, mutator=cp.MutatorSequence([cp.RandomStart(seed=42), cp.Wind(0.0, gust_std=2.0)]))
        env.reset()
        act = random_actor(7)
        return [env.step(act(env))[0]["cart_1"].copy() for _ in range(20)]
    for a, b in zip(rollout(), rollout()):
        np.testing.assert_array_equal(a, b)


@pytest.mark.parametrize("build, message", [
    (lambda: cp.UnstableMutator(), "broken on purpose"),
    (lambda: cp.PoleLength(-1.0), "length must be positive"),
    (lambda: cp.Gravity(planet="pluto"), "planet must be one of"),
    (lambda: cp.DiscreteForce(n_levels=1), "n_levels must be at least 2"),
    (lambda: cp.CartPoleEngine(integrator="rk4"), "integrator must be one of"),
    (lambda: cp.CombinedReward([cp.AliveReward()], [1.0, 2.0]), "2 weights for 1 rewards"),
    (lambda: cp.TickLimit(0), "max_ticks must be at least 1"),
])
def test_invalid_arguments_fail_clearly(build, message):
    with pytest.raises((ValueError, RuntimeError), match=message):
        build()
