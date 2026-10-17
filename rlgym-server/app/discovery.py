"""Inspect the user's Python interpreter and discover the RLGym components in their modules,
through the worker process (worker/worker.py runs inside that interpreter)."""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from . import config, settings
from .worker_bridge import Worker, WorkerError

# Same keys as KINDS in worker/worker.py, in the order RLGym builds an env.
ComponentKind = Literal[
    "transition_engine", "state_mutator", "obs_builder", "action_parser",
    "reward_function", "done_condition", "shared_info_provider",
]
KINDS: tuple[ComponentKind, ...] = ComponentKind.__args__


class PythonInfo(BaseModel):
    python: str | None = Field(description="Python version, e.g. 3.12.2; null if it didn't start")
    executable: str
    rlgym_api: str | None = Field(description="Installed rlgym-api version; null if not importable")
    error: str | None = Field(description="Why the interpreter or rlgym.api couldn't be used")


# Names chosen to stay clear of the generated Angular client: it already emits a `param.ts`,
# and `Component` would clash with Angular's @Component decorator.
class ComponentParam(BaseModel):
    name: str
    type: str | None
    default: str | None = Field(description="repr() of the default; null when required")
    required: bool


class DiscoveredComponent(BaseModel):
    kind: ComponentKind
    name: str
    module: str
    qualified_name: str
    doc: str | None
    params: list[ComponentParam]


class ModuleError(BaseModel):
    module: str
    message: str


class DiscoverRequest(BaseModel):
    modules: list[str] | None = Field(
        default=None, description="Modules to scan; the saved list when omitted"
    )

    @field_validator("modules")
    @classmethod
    def clean_modules(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else settings.clean_module_list(v)


class DiscoverResult(BaseModel):
    components: dict[ComponentKind, list[DiscoveredComponent]] = Field(
        description="Every kind is present, possibly with an empty list"
    )
    errors: list[ModuleError]


_worker = Worker(config.worker_script())


def get_worker() -> Worker:
    return _worker


WorkerDep = Annotated[Worker, Depends(get_worker)]


def stop_worker() -> None:
    _worker.stop()


def _interpreter(override: str | None = None) -> str:
    python = (override or "").strip() or settings.load().python
    if not python:
        raise HTTPException(409, "No Python interpreter selected; choose one in Settings")
    return python


router = APIRouter(tags=["discovery"])


# Plain `def`: Worker.call blocks, so FastAPI runs these in its threadpool.
@router.get("/python/info")
def get_python_info(
    worker: WorkerDep,
    python: Annotated[str | None, Query(description="Interpreter to check instead of the saved one")] = None,
) -> PythonInfo:
    executable = _interpreter(python)
    try:
        return PythonInfo.model_validate(worker.call(executable, "info"))
    except WorkerError as exc:
        # Not an API failure: the settings page shows this next to the chosen path.
        return PythonInfo(python=None, executable=executable, rlgym_api=None, error=str(exc))


@router.post("/components/discover")
def discover_components(worker: WorkerDep, request: DiscoverRequest) -> DiscoverResult:
    python = _interpreter()
    modules = settings.load().modules if request.modules is None else request.modules
    try:
        result = worker.call(python, "discover", {"modules": modules})
    except WorkerError as exc:
        raise HTTPException(502, str(exc)) from exc
    grouped: dict[ComponentKind, list[DiscoveredComponent]] = {kind: [] for kind in KINDS}
    for c in result["components"]:
        grouped[c["kind"]].append(DiscoveredComponent.model_validate(c))
    return DiscoverResult(
        components=grouped,
        errors=[ModuleError.model_validate(e) for e in result["errors"]],
    )
