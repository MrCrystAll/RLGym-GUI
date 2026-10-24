import inspect

import numpy as np
import pytest
from rlgym.api import (
    ActionParser, DoneCondition, ObsBuilder, RewardFunction, RLGym, SharedInfoProvider, StateMutator,
    TransitionEngine,
)

from rlgym_gui_samples import grid_world as gw
from rlgym_gui_samples.grid_world import (
    AddLava, AnyOf, BumpPenalty, CardinalMoves, CoordinatesObs, DistanceShaping, FellInLava, FixedMap,
    FullGridObs, GoalReached, GoalReward, GridEngine, GridStats, KingMoves, LavaPenalty, LocalViewObs,
    MazeGenerator, MutatorSequence, RandomPlacement, RandomWalls, StepPenalty, TeleportTraps, TickLimit,
    WeightedSum, parse_layout,
)

from .helpers import run_episode

UP, DOWN, LEFT, RIGHT, STAY = range(5)                   # CardinalMoves


def random_actions(seed=0):
    rng = np.random.default_rng(seed)

    def act(env):
        return {a: int(rng.integers(env.action_space(a)[1])) for a in env.agents}
    return act


def make_env(state_mutator=None, obs_builder=None, action_parser=None, reward_fn=None, engine=None,
             termination=None, truncation=None, shared_info=None):
    return RLGym(
        transition_engine=engine or GridEngine(),
        state_mutator=state_mutator or FixedMap(),
        obs_builder=obs_builder or LocalViewObs(),
        action_parser=action_parser or CardinalMoves(),
        reward_fn=reward_fn or WeightedSum([GoalReward(), StepPenalty()]),
        termination_cond=termination or AnyOf([GoalReached(), FellInLava()]),
        truncation_cond=truncation or TickLimit(100),
        shared_info_provider=shared_info,
    )


def step(env, **moves):
    """Step with the given CardinalMoves actions; agents not named stay."""
    return env.step({a: moves.get(a, STAY) for a in env.agents})


# --- Every part, together ---------------------------------------------------------------------------

@pytest.mark.parametrize("state_mutator, obs_builder, action_parser", [
    (FixedMap(), LocalViewObs(), CardinalMoves()),
    (MazeGenerator(9, 7, seed=1), FullGridObs(), KingMoves()),
    (MutatorSequence([RandomWalls(0.25, seed=2), RandomPlacement(n_goals=2, seed=3)]),
     CoordinatesObs(include_others=True), CardinalMoves(allow_stay=False)),
    (MutatorSequence([FixedMap(), AddLava(count=4, seed=4)]), FullGridObs(flatten=False), KingMoves(False)),
])
def test_runs_episodes(state_mutator, obs_builder, action_parser):
    env = make_env(state_mutator, obs_builder, action_parser,
                   reward_fn=WeightedSum([GoalReward(), StepPenalty(), DistanceShaping(metric="path"),
                                          BumpPenalty(), LavaPenalty()]),
                   shared_info=GridStats())
    for _ in range(3):
        run_episode(env, random_actions(), max_steps=150)


def test_observations_match_their_space():
    for obs_builder in (LocalViewObs(radius=3, include_position=True), FullGridObs(), CoordinatesObs(include_others=True)):
        env = make_env(obs_builder=obs_builder)
        obs = env.reset()
        for agent, o in obs.items():
            kind, size = env.observation_space(agent)
            assert kind == "real" and o.shape == (size,) and o.dtype == np.float32


def test_action_spaces():
    env = make_env(action_parser=KingMoves())
    env.reset()
    assert env.action_space("agent_0") == ("discrete", 9)
    assert CardinalMoves(allow_stay=False).get_action_space("agent_0") == ("discrete", 4)


def test_every_component_is_exported_and_concrete():
    bases = (TransitionEngine, StateMutator, ObsBuilder, ActionParser, RewardFunction, DoneCondition, SharedInfoProvider)
    components = [obj for obj in vars(gw).values() if inspect.isclass(obj) and issubclass(obj, bases)]
    kinds = {base for base in bases for c in components if issubclass(c, base)}
    assert kinds == set(bases)                           # at least one of each kind
    assert not [c for c in components if inspect.isabstract(c)]
    assert all(c.__dict__.get("__doc__") for c in components)   # the Components page shows it


# --- Maps --------------------------------------------------------------------------------------------

def test_parses_a_map():
    state = parse_layout("""
        #####
        #1.G#
        #A~0#
        #####
    """)
    assert state.shape == (4, 5)
    assert state.goals == [(1, 3)]
    assert state.agents == {"agent_0": (2, 3), "agent_1": (1, 1), "agent_2": (2, 1)}
    assert state.lava[2, 2] and state.walls[0].all()
    assert state.render() == "#####\n#1.G#\n#2~0#\n#####"


@pytest.mark.parametrize("layout, message", [
    ("####\n#A.G#\n#####", "same length"),
    ("#####\n#A..#\n#####", "no goal"),
    ("#####\n#..G#\n#####", "no agent"),
    ("#####\n#A?G#\n#####", "Unknown map character '?'"),
    ("#####\n#1.1#\n#.G.#", "appears twice"),
])
def test_rejects_bad_maps(layout, message):
    with pytest.raises(ValueError, match=message):
        FixedMap(layout)


def test_maze_needs_odd_sizes():
    with pytest.raises(ValueError, match="odd"):
        MazeGenerator(10, 11)


def test_maze_is_solvable():
    env = make_env(MazeGenerator(15, 11, seed=7), engine=GridEngine(n_agents=3))
    env.reset()
    state = env.state
    assert state.shape == (11, 15) and len(state.agents) == 3
    assert gw.state.every_agent_can_reach_a_goal(state)


def test_random_walls_keep_goals_reachable():
    for seed in range(10):
        env = make_env(RandomWalls(density=0.5, seed=seed), engine=GridEngine(10, 10))
        env.reset()
        assert gw.state.every_agent_can_reach_a_goal(env.state)


def test_random_walls_give_up_when_impossible():
    env = make_env(MutatorSequence([FixedMap("#####\n#A.G#\n#...#\n#####"), RandomWalls(0.9, max_tries=3, seed=0)]))
    with pytest.raises(RuntimeError, match="3 tries"):
        for _ in range(20):                              # some draws might still leave a path
            env.reset()


def test_teleport_traps_always_fail():
    with pytest.raises(NotImplementedError, match="fails on purpose"):
        TeleportTraps()


@pytest.mark.parametrize("make", [
    lambda: GridEngine(width=2), lambda: GridEngine(collisions="bounce"), lambda: GridEngine(slip=1.5),
    lambda: LocalViewObs(radius=0), lambda: GoalReached("some"), lambda: TickLimit(0),
    lambda: DistanceShaping(metric="chebyshev"), lambda: WeightedSum([GoalReward()], weights=[1, 2]),
    lambda: WeightedSum([GoalReached()]), lambda: RandomWalls(density=1.0),
])
def test_bad_arguments_raise(make):
    with pytest.raises((ValueError, TypeError)):
        make()


# --- Movement rules ----------------------------------------------------------------------------------

CORRIDOR = "#######\n#0...G#\n#.#####\n#1....#\n#######"


def test_moves_and_walls():
    env = make_env(FixedMap(CORRIDOR))
    env.reset()
    step(env, agent_0=RIGHT)
    assert env.state.agents["agent_0"] == (1, 2)
    step(env, agent_0=UP)                                # wall
    assert env.state.agents["agent_0"] == (1, 2) and env.state.bumped["agent_0"]
    step(env, agent_1=UP)
    assert env.state.agents["agent_1"] == (2, 1)


def test_reaching_the_goal_rewards_terminates_and_freezes():
    env = make_env(FixedMap(CORRIDOR), reward_fn=GoalReward(reward=5.0))
    env.reset()
    for _ in range(3):
        obs, rewards, terminated, truncated = step(env, agent_0=RIGHT)
    assert rewards == {"agent_0": 0.0, "agent_1": 0.0} and not terminated["agent_0"]
    obs, rewards, terminated, truncated = step(env, agent_0=RIGHT)
    assert rewards["agent_0"] == 5.0 and terminated == {"agent_0": True, "agent_1": False}
    step(env, agent_0=LEFT)                              # done agents stay put
    assert env.state.agents["agent_0"] == (1, 5)


def test_agents_block_each_other():
    env = make_env(FixedMap("#######\n#0.1.G#\n#######"))
    env.reset()
    step(env, agent_0=RIGHT, agent_1=LEFT)               # both into (1, 2)
    assert env.state.agents == {"agent_0": (1, 1), "agent_1": (1, 3)}
    step(env, agent_0=RIGHT)
    step(env, agent_0=RIGHT, agent_1=LEFT)               # swap places
    assert env.state.agents == {"agent_0": (1, 2), "agent_1": (1, 3)}


def test_agents_pass_through_each_other():
    env = make_env(FixedMap("#######\n#0.1.G#\n#######"), engine=GridEngine(collisions="pass"))
    env.reset()
    step(env, agent_0=RIGHT, agent_1=LEFT)
    assert env.state.agents == {"agent_0": (1, 2), "agent_1": (1, 2)}


def test_lava():
    env = make_env(FixedMap("######\n#0~.G#\n#1...#\n######"), reward_fn=LavaPenalty(2.0))
    env.reset()
    obs, rewards, terminated, truncated = step(env, agent_0=RIGHT)
    assert rewards == {"agent_0": -2.0, "agent_1": 0.0} and terminated == {"agent_0": True, "agent_1": False}


def test_goal_modes():
    layout = "######\n#0G..#\n#1..G#\n######"
    for mode, expected in [("each", {"agent_0": True, "agent_1": False}),
                           ("any", {"agent_0": True, "agent_1": True}),
                           ("all", {"agent_0": False, "agent_1": False})]:
        env = make_env(FixedMap(layout), termination=GoalReached(mode))
        env.reset()
        assert step(env, agent_0=RIGHT)[2] == expected


def test_tick_limit_truncates():
    env = make_env(truncation=TickLimit(3))
    env.reset()
    assert [step(env)[3]["agent_0"] for _ in range(3)] == [False, False, True]


def test_step_penalty_and_shaping():
    env = make_env(FixedMap(CORRIDOR),
                   reward_fn=WeightedSum([StepPenalty(0.1), DistanceShaping(scale=1.0)], weights=[1.0, 0.5]))
    env.reset()
    rewards = step(env, agent_0=RIGHT, agent_1=RIGHT)[1]
    # Each moved one cell closer to the goal (Manhattan): -0.1 step penalty + 0.5 * 1 shaping.
    assert rewards == {"agent_0": pytest.approx(0.4), "agent_1": pytest.approx(0.4)}


def test_shared_info():
    env = make_env(FixedMap(CORRIDOR), shared_info=GridStats())
    env.reset()
    for _ in range(4):
        step(env, agent_0=RIGHT)
    info = env.shared_info
    assert info["tick"] == 4 and info["goals_reached"] == 1
    assert info["visits"]["agent_0"][1, 5] == 1 and info["visits"]["agent_1"][3, 1] == 5


# --- Observations ------------------------------------------------------------------------------------

def test_local_view():
    obs_builder = LocalViewObs(radius=1)
    env = make_env(FixedMap("#####\n#0~G#\n#1..#\n#####"), obs_builder=obs_builder)
    env.reset()
    walls, lava, goals, others = obs_builder.view(env.state, "agent_0")
    np.testing.assert_array_equal(walls, [[1, 1, 1], [1, 0, 0], [1, 0, 0]])
    np.testing.assert_array_equal(lava, [[0, 0, 0], [0, 0, 1], [0, 0, 0]])
    np.testing.assert_array_equal(others, [[0, 0, 0], [0, 0, 0], [0, 1, 0]])
    assert not goals.any()                               # 2 cells away


def test_local_view_outside_the_grid():
    for outside, expected in [("wall", 1), ("empty", 0)]:
        obs_builder = LocalViewObs(radius=2, outside=outside)
        env = make_env(FixedMap("0G"), obs_builder=obs_builder)   # no walls at all
        env.reset()
        walls = obs_builder.view(env.state, "agent_0")[0]
        assert walls[0, 0] == expected and walls[2, 2] == 0


# --- Determinism -------------------------------------------------------------------------------------

def test_seeds_make_runs_reproducible():
    def run():
        env = make_env(MutatorSequence([MazeGenerator(11, 9, seed=3), AddLava(count=2, seed=4)]),
                       engine=GridEngine(slip=0.3, seed=5))
        act = random_actions(seed=6)
        env.reset()
        trace = [env.state.render()]
        for _ in range(30):
            step_result = env.step(act(env))
            trace.append((env.state.render(), step_result[1]))
        return trace
    assert run() == run()
