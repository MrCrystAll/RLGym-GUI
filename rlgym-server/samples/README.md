# RLGym GUI samples

Small but complete RLGym environments for trying out RLGym GUI without a Rocket League setup: every
part of `RLGym(...)` is implemented, so configs built from them validate, export and run. Each
environment also has variants (mutators, rewards, done conditions...) with different constructor
arguments to play with in the editor, and a few components that fail on purpose to see the error
messages.

| Environment  | Module to scan                    | Physics |
| ------------ | --------------------------------- | ------- |
| CartPole     | `rlgym_gui_samples.cartpole`      | numpy   |
| Lunar Lander | `rlgym_gui_samples.lunar_lander`  | Box2D   |
| Grid world   | `rlgym_gui_samples.grid_world`    | numpy   |

## Use them in the app

1. Install the package in the interpreter you select in Settings (from the repository root):

   ```bash
   <that interpreter> -m pip install -e rlgym-server/samples
   ```

   `-e` means edits to the samples are picked up without reinstalling (after restarting the app,
   since the worker keeps modules loaded).
2. In Settings, add the module names above to the modules to scan.
3. Components lists them; create a config from them in Configs.

## Layout

```
rlgym_gui_samples/
  <env>/__init__.py      re-exports the env's components (discovery lists what a module exposes)
  <env>/...              the components, one module per part or however the env reads best
sample_tests/
  helpers.py             run_episode(): reset and step an env, checking what RLGym returns
  test_<env>.py          each env builds, resets and steps
```

## Tests

They run with the backend's (`pytest` from `rlgym-server/`, which installs these requirements
through `requirements-dev.txt`), or on their own:

```bash
cd rlgym-server
.venv/Scripts/python.exe -m pytest samples
```
