# RLGym GUI

A desktop workbench for [RLGym](https://rlgym.org/) environments: point it at the Python
interpreter of your RLGym project, browse the components (observation builders, rewards, done
conditions...) defined in your modules, and, in upcoming releases, build, step through and compare
environments.

Windows only for now. Download the installer from
[Releases](https://github.com/MrCrystAll/RLGym-GUI/releases); the app updates itself.

## How it fits together

```
electron/         Desktop shell. Starts the backend on a free port with a random token,
                  then loads the UI. Also owns the auto-updater and native dialogs.
rlgym-app/        Angular UI. Talks to the backend through a client generated from
                  rlgym-server/openapi.json.
rlgym-server/     FastAPI backend (app/) plus the worker (worker/worker.py).
```

The backend never imports your code itself. It starts `worker/worker.py` in **your** Python
interpreter, the one with your RLGym project installed, and talks to it over stdin/stdout (JSON
lines). A broken or slow module only affects the worker, which is restarted on the next call.
Packaged, the backend is frozen with PyInstaller and `worker.py` ships next to it as a plain file.

## Development setup

You need:

- Node.js 22+ and npm
- Python 3.12
- Java 11+, used by `openapi-generator` to generate the Angular API client

Install each part once:

```powershell
# Backend
cd rlgym-server
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt

# UI (postinstall generates the API client into src/app/api)
cd ..\rlgym-app
npm install

# Desktop shell
cd ..\electron
npm install
```

## Running the app

Two terminals:

```powershell
# 1. UI dev server on http://localhost:4200 (also regenerates the API client when the backend changes)
cd rlgym-app
npm start

# 2. Electron: starts the backend from rlgym-server\.venv and opens the UI
cd electron
npm start
```

In a VS Code terminal, run `$env:ELECTRON_RUN_AS_NODE = $null` first: VS Code sets it, and it
makes Electron start as plain Node.

The backend can also run on its own, on port 8000 with the token `dev-token`:

```powershell
cd rlgym-server
.venv\Scripts\python main.py
# every request needs the header  X-Api-Token: dev-token
```

### Configuration

The backend reads these environment variables (Electron sets the first four):

| Variable | Default | |
|---|---|---|
| `RLGYM_GUI_PORT` | `8000` | Port to listen on (127.0.0.1 only) |
| `RLGYM_GUI_TOKEN` | `dev-token` | Required in the `X-Api-Token` header of every request |
| `RLGYM_GUI_DATA_DIR` | `./data` | Settings and `worker.log` (Electron: the app's user data folder) |
| `RLGYM_GUI_VERSION` | `0.0.1` | Reported by `/version` |
| `RLGYM_GUI_WORKER_TIMEOUT` | `60` | Seconds a worker call may take before the worker is restarted |

`RLGYM_PYTHON` makes Electron, in dev, start the backend with another interpreter than
`rlgym-server\.venv`.

## Tests

```powershell
cd rlgym-server; .venv\Scripts\python -m pytest     # API, settings, discovery, worker protocol
cd rlgym-app;    npm test -- --watch=false          # Angular (Vitest)
```

CI runs both on every push and pull request to `dev` and `master`.

## API client

`rlgym-server/openapi.json` is generated from the FastAPI routes and committed; the Angular client in
`rlgym-app/src/app/api` is generated from it and not committed.

- `npm start` in `rlgym-app` keeps both up to date while you work.
- Otherwise, after changing backend routes or models: `npm run gen:spec` then `npm run gen:api`
  in `rlgym-app`.

CI fails if `openapi.json` doesn't match the routes, so commit it with the backend change.

## Building an installer locally

Releases are built by CI (see below), but the same steps work locally:

```powershell
cd rlgym-app; npm run build           # UI into electron\renderer
cd ..\rlgym-server
.venv\Scripts\pip install pyinstaller==6.22.3
.venv\Scripts\pyinstaller main.py --name rlgym-backend --noconfirm --clean --collect-submodules uvicorn --add-data "worker/worker.py;worker"
cd ..\electron; npm run pack:dist     # installer in electron\dist
```

## Contributing and releases

Every change has an RLGYM Jira ticket, a `<type>/RLGYM-<n>_<description>` branch off `dev`, a pull
request to `dev`, and, if users can see it, a `CHANGELOG.md` entry. Releases are cut from a
`release/*` branch with `node scripts/release.mjs <x.y.z>`; merging its pull request into `master`
builds, tags and publishes the release. The details are in [CLAUDE.md](CLAUDE.md).
