---
name: run-app
description: Launch and drive the RLGym GUI to see changes working - the Electron app (with the Angular dev server and the FastAPI backend it spawns), the backend API on its own, or the Python worker. Use when asked to run, start, screenshot or check logs/errors of the app, API or worker, or to verify a change in the real app rather than only in tests.
---

Three scripts, all in this folder (`rlgym-app/.claude/skills/run-app/`). Each one starts what it
needs, prints every log layer, and stops what it started. Run them from any directory.

## One-time setup

```bash
npm install --prefix rlgym-app/.claude/skills/run-app     # playwright-core for the driver
```

Also needed (normally already there): `rlgym-server/.venv` with `requirements.txt` installed,
`npm install` in `rlgym-app/` and in `electron/`.

## Electron app - `driver.cjs`

```bash
node rlgym-app/.claude/skills/run-app/driver.cjs ss:home dark ss:home-dark
```

- Reuses a running `ng serve` on :4200, or starts one (and stops it afterwards). See
  [Parallel runs](#parallel-runs-git-worktrees-subagents) for another port.
- Launches Electron in dev mode; Electron spawns the backend from `rlgym-server/.venv` on a random port.
- Waits for the home page's backend status line ("Backend vX running"), then runs the steps.
- Log tags: `[main]`/`[main:err]` main process + backend (uvicorn), `[renderer:*]` console,
  page errors and failed requests, `[api]` every renderer -> backend response, `[ng]` dev server.
- Screenshots go to `$TMP/rlgym-run/` (override `RLGYM_SHOT_DIR`). **Open them with Read** - a log
  without errors is not proof the page rendered.

Steps: `ss:<name>`, `goto:#/<route>`, `click:<css>`, `click-text:<text>`, `type:<css>=<text>`,
`wait:<css>`, `text[:<css>]`, `eval:<js>`, `sleep:<ms>`, `dark`, `light`, `size:<w>x<h>`.
Full descriptions are at the top of `driver.cjs`; add new step types there when needed.

The driver's profile starts with no interpreter selected. To get components to pick from, export
`PYTHONPATH=<this folder>` (the worker inherits it) and set the interpreter (an **absolute** path)
and the `sample_components` module first:

```bash
export PYTHONPATH="$(cygpath -w "$PWD/rlgym-app/.claude/skills/run-app")"
node rlgym-app/.claude/skills/run-app/driver.cjs "goto:#/settings" \
  "type:#python=$(cygpath -w "$PWD/rlgym-server/.venv/Scripts/python.exe")" \
  "type:#modules=sample_components" "click-text:Save" sleep:1500 ...
```

### Parallel runs (git worktrees, subagents)

Several copies can run at once if each one sets its own port:

```bash
RLGYM_NG_PORT=4301 RLGYM_PYTHON=<main checkout>/rlgym-server/.venv/Scripts/python.exe \
  node rlgym-app/.claude/skills/run-app/driver.cjs ss:home
```

- `RLGYM_NG_PORT` makes the driver start its own `ng serve` on that port, from this checkout. It
  fails instead of reusing a server already there, since that one may be serving another worktree.
- The Electron profile (settings, saved configs) and screenshots get their own folders:
  `$TMP/rlgym-run-profile-<port>/` and `$TMP/rlgym-run-<port>/`.
- A new worktree has no `rlgym-server/.venv` (it's untracked). `RLGYM_PYTHON` runs the
  backend from this worktree's code with the main checkout's venv.
- It has no `node_modules` either: run `npm install` in `rlgym-app/` and `electron/`, plus the
  one-time setup above, before the first run.
- `api-smoke.sh` takes `RLGYM_SMOKE_PORT` the same way.

## Backend alone - `api-smoke.sh`

```bash
bash rlgym-app/.claude/skills/run-app/api-smoke.sh            # health, version, auth, openapi sync
bash rlgym-app/.claude/skills/run-app/api-smoke.sh /python/info   # plus extra GET routes
```

Runs on port 8123 (`RLGYM_SMOKE_PORT`) with token `smoke`, prints each response with its status,
checks the live schema against `rlgym-server/openapi.json`, then dumps the uvicorn log.
For POST routes, start it the same way and `curl -X POST -H 'X-Api-Token: smoke'` by hand.

## Worker - `worker-smoke.py`

```bash
rlgym-server/.venv/Scripts/python.exe rlgym-app/.claude/skills/run-app/worker-smoke.py [module ...]
```

Calls `info` and `discover` through `app.worker_bridge` (the same path the API uses) and prints
the components found plus the tail of `worker.log`. With no args it discovers
`sample_components.py` from this folder. `WORKER_PYTHON=<path>` runs the worker under another
interpreter, the way a user-selected interpreter would.

## Gotchas

- **`ELECTRON_RUN_AS_NODE=1`** is exported by VS Code to every child process, turning
  `electron.exe` into plain Node ("bad option: --remote-debugging-port", Playwright reports
  "Process failed to launch!"). The driver strips it. A plain `npm start` from a VS Code
  terminal hits the same thing - unset it first.
- **Single-instance lock**: when the user already has the app open, a second launch quits
  immediately. The driver uses its own `--user-data-dir` so the two don't collide. Never kill the
  user's own Electron / `ng serve` / backend processes - check what's running before cleaning up.
- **`rlgym.rocket_league` is not installed** in `rlgym-server/.venv` (only `rlgym.api`), so
  discovering real RL components needs `pip install "rlgym[rl]"` in the target interpreter.
- In dev the "Check for updates" button shows briefly, then disappears: the updater reports
  `disabled` when the app isn't packaged. Expected.
- The Electron security warning about Content-Security-Policy is dev-only and expected.
- `/docs` returns 401 like every other route (token middleware), so use `curl` with the token
  rather than a browser.
