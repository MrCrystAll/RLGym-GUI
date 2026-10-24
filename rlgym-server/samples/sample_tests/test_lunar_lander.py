import numpy as np
import pytest
from rlgym.api import RLGym, StateMutator

from rlgym_gui_samples.lunar_lander import (
    AnyOf, ClassicReward, ContinuousThrust, Crashed, DiscreteThrust, EpisodeStats, FuelCost, GameOver,
    Gravity, Landed, LanderObs, LandingReward, LunarLanderEngine, Mutators, OutOfBounds, PadRelativeObs,
    PlanetPreset, RandomStart, RandomTerrain, ShapingReward, StuckThrottle, TickLimit, WeightedSum, Wind,
)

from .helpers import run_episode


def make_env(**overrides) -> RLGym:
    parts = dict(
        transition_engine=LunarLanderEngine(seed=0),
        state_mutator=Mutators([RandomTerrain(seed=1), RandomStart(seed=2)]),
        obs_builder=LanderObs(),
        action_parser=DiscreteThrust(),
        reward_fn=ClassicReward(),
        termination_cond=GameOver(),
        truncation_cond=TickLimit(1000),
        shared_info_provider=EpisodeStats(),
    )
    parts.update(overrides)
    return RLGym(**parts)


def random_actions(seed: int = 0):
    rng = np.random.default_rng(seed)
    return lambda env: {a: env.action_spaces[a].sample(rng) for a in env.agents}


def constant(action):
    return lambda env: {a: action for a in env.agents}


@pytest.mark.parametrize("overrides", [
    {},
    {"action_parser": ContinuousThrust(), "obs_builder": PadRelativeObs(include_fuel=True)},
    {"obs_builder": LanderObs(include_legs=False), "reward_fn": WeightedSum([ShapingReward(), FuelCost()], [1.0, 2.0])},
    {"state_mutator": Mutators([RandomTerrain(roughness=0.5, seed=3), PlanetPreset("mars"), Wind(10.0, 1.0)])},
    {"termination_cond": AnyOf([Landed(require_both_legs=False), Crashed(), OutOfBounds()]),
     "reward_fn": LandingReward(landed_condition=Landed(require_both_legs=False))},
    {"transition_engine": LunarLanderEngine(n_landers=3, seed=4)},
])
def test_random_episodes_end(overrides):
    env = make_env(**overrides)
    for episode in range(2):
        steps = run_episode(env, random_actions(episode), max_steps=1000)
        assert steps < 1000, "a random lander should crash, land or leave the screen before the tick limit"
    env.close()


def test_spaces_match_observations_and_actions():
    for obs_builder, parser in [(LanderObs(), DiscreteThrust()), (PadRelativeObs(clip=None), ContinuousThrust())]:
        env = make_env(obs_builder=obs_builder, action_parser=parser)
        obs = env.reset()
        for agent in env.agents:
            assert obs[agent].shape == env.observation_spaces[agent].shape
            assert env.action_spaces[agent].contains(env.action_spaces[agent].sample(np.random.default_rng(0)))
        env.close()


def test_free_fall_and_main_engine():
    falling = make_env(state_mutator=Gravity(-10.0))
    falling.reset()
    for _ in range(20):
        falling.step({"lander_0": 0})
    burning = make_env(state_mutator=Gravity(-10.0))
    burning.reset()
    for _ in range(20):
        burning.step({"lander_0": 2})
    fall, burn = falling.state.landers["lander_0"], burning.state.landers["lander_0"]
    assert fall.vy < -3.0                       # ~ -10 m/s² for 0.4 s
    assert burn.vy > fall.vy + 2.0              # the main engine slows the descent
    assert burn.fuel_used == 20 and fall.fuel_used == 0


def test_gravity_presets_change_the_fall():
    speeds = {}
    for body in ("moon", "gymnasium"):
        env = make_env(state_mutator=PlanetPreset(body))
        env.reset()
        for _ in range(25):
            env.step({"lander_0": 0})
        speeds[body] = env.state.landers["lander_0"].vy
    assert speeds["gymnasium"] < speeds["moon"] < 0


class DropOverPad(StateMutator):
    """Test-only: puts the lander `height` metres above the pad."""

    def __init__(self, height: float):
        self.height = height

    def apply(self, state, shared_info):
        for lander in state.landers.values():
            lander.y = state.helipad_y + self.height


def test_landing_on_the_pad():
    """Dropped just above the flat pad, a lander with idle engines lands without crashing."""
    env = make_env(state_mutator=DropOverPad(0.5), termination_cond=Landed(),
                   reward_fn=LandingReward(landed_condition=Landed()), truncation_cond=TickLimit(600))
    env.reset()
    total = 0.0
    for _ in range(600):
        _, rewards, terminated, _ = env.step({"lander_0": 0})
        total += rewards["lander_0"]
        if terminated["lander_0"]:
            break
    lander = env.state.landers["lander_0"]
    assert terminated["lander_0"] and not lander.crashed and all(lander.legs_contact)
    assert total == 100.0                       # paid once
    assert env.shared_info["lunar_lander"]["landed"] == ["lander_0"]


def test_free_fall_from_higher_crashes():
    env = make_env(state_mutator=DropOverPad(2.0), termination_cond=Crashed(), truncation_cond=TickLimit(600))
    steps = run_episode(env, constant(0), max_steps=600)
    assert steps < 600 and env.state.landers["lander_0"].crashed


def test_crash_penalty_is_paid_once():
    env = make_env(reward_fn=LandingReward(crash_penalty=-50.0), termination_cond=Crashed(),
                   state_mutator=Mutators([Gravity(-20.0), RandomStart(max_force=0.0, max_tilt=3.0, seed=0)]))
    env.reset()
    total, crashed_at = 0.0, None
    for t in range(400):
        _, rewards, terminated, _ = env.step({"lander_0": 0})
        total += rewards["lander_0"]
        if terminated["lander_0"] and crashed_at is None:
            crashed_at = t
    assert crashed_at is not None and total == -50.0


def test_seeded_runs_are_identical():
    def trajectory():
        env = make_env(state_mutator=Mutators([RandomTerrain(seed=5), RandomStart(seed=6), Wind()]))
        env.reset()
        act = random_actions(7)
        out = [env.step(act(env))[0]["lander_0"] for _ in range(60)]
        env.close()
        return np.array(out)
    np.testing.assert_array_equal(trajectory(), trajectory())


def test_resets_start_fresh():
    env = make_env(transition_engine=LunarLanderEngine(n_landers=2, seed=0))
    worlds = set()
    for _ in range(5):
        env.reset()
        engine = env.transition_engine
        worlds.add(id(engine.world))
        # terrain + 2 landers × (body + 2 legs): nothing left over from the previous episode
        assert len(engine.world.bodies) == 1 + 2 * 3
        for lander in env.state.landers.values():
            assert lander.fuel_used == 0 and not lander.crashed and lander.legs_contact == (False, False)
        assert env.state.tick == 0
        for _ in range(150):
            env.step({a: 2 for a in env.agents})
    env.close()
    assert env.transition_engine.world is None


@pytest.mark.parametrize("build, message", [
    (lambda: StuckThrottle(), "broken on purpose"),
    (lambda: Gravity(5.0), "gravity must be between -20 and 0"),
    (lambda: PlanetPreset("pluto"), "body must be one of"),
    (lambda: WeightedSum([FuelCost()], [1.0, 2.0]), "1 rewards but 2 weights"),
    (lambda: LunarLanderEngine(n_landers=0), "n_landers must be at least 1"),
    (lambda: TickLimit(0), "max_ticks must be at least 1"),
])
def test_invalid_components_fail_with_a_clear_message(build, message):
    with pytest.raises((ValueError, RuntimeError), match=message):
        build()
