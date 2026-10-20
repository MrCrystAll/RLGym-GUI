"""Named environment configs, one JSON file each under DATA_DIR/configs/."""
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Path as PathParam, Response, status
from pydantic import BaseModel, Field, ValidationError, field_validator

from . import config
from .discovery import ComponentKind
from .storage import write_text_atomic

log = logging.getLogger(__name__)

# The arguments of rlgym.api.RLGym(...), minus the renderer. Both done-condition slots take a
# done_condition component.
Slot = Literal[
    "transition_engine", "state_mutator", "obs_builder", "action_parser", "reward_fn",
    "termination_cond", "truncation_cond", "shared_info_provider",
]
SLOT_KINDS: dict[Slot, ComponentKind] = {
    "transition_engine": "transition_engine",
    "state_mutator": "state_mutator",
    "obs_builder": "obs_builder",
    "action_parser": "action_parser",
    "reward_fn": "reward_function",
    "termination_cond": "done_condition",
    "truncation_cond": "done_condition",
    "shared_info_provider": "shared_info_provider",
}
REQUIRED_SLOTS: tuple[Slot, ...] = (
    "transition_engine", "state_mutator", "obs_builder", "action_parser", "reward_fn",
)

ConfigId = Annotated[str, PathParam(pattern=r"^[0-9a-f]{32}$")]


class ComponentChoice(BaseModel):
    qualified_name: str = Field(min_length=1, description="e.g. my_bot.rewards.GoalReward")
    params: dict[str, str] = Field(
        default_factory=dict,
        description="Constructor arguments as Python literal expressions, e.g. '1.0', 'None', \"'blue'\"; "
                    "omitted ones use their default",
    )


class ConfigIn(BaseModel):
    name: str = Field(max_length=100)
    components: dict[Slot, ComponentChoice] = Field(
        default_factory=dict, description="The chosen component per slot; a missing slot isn't chosen yet"
    )

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class EnvConfig(ConfigIn):
    id: str
    created_at: datetime
    updated_at: datetime


class ConfigSummary(BaseModel):
    id: str
    name: str
    updated_at: datetime
    slots: list[Slot] = Field(description="Slots with a component chosen")
    complete: bool = Field(description="Every required slot has a component")


def _dir() -> Path:
    return Path(config.DATA_DIR) / "configs"


def _path(config_id: str) -> Path:
    return _dir() / f"{config_id}.json"


def _read(path: Path) -> EnvConfig | None:
    try:
        return EnvConfig.model_validate_json(path.read_bytes())
    except (OSError, ValidationError) as exc:
        # One hand-edited or truncated file must not hide all the others.
        log.warning("Ignoring unreadable config %s: %s", path, exc)
        return None


def _all() -> list[EnvConfig]:
    configs = (_read(p) for p in _dir().glob("*.json"))
    return [c for c in configs if c is not None]


def _get(config_id: str) -> EnvConfig:
    path = _path(config_id)
    found = _read(path) if path.is_file() else None
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such config")
    return found


def _check_name_free(name: str, except_id: str | None = None) -> None:
    for c in _all():
        if c.name.casefold() == name.casefold() and c.id != except_id:
            # Quote the existing name: it tells the user which config they collided with.
            raise HTTPException(status.HTTP_409_CONFLICT, f"A config named '{c.name}' already exists")


def _save(cfg: EnvConfig) -> EnvConfig:
    write_text_atomic(_path(cfg.id), cfg.model_dump_json(indent=2))
    return cfg


def _summary(cfg: EnvConfig) -> ConfigSummary:
    slots = [s for s in SLOT_KINDS if s in cfg.components]
    return ConfigSummary(
        id=cfg.id, name=cfg.name, updated_at=cfg.updated_at, slots=slots,
        complete=all(s in cfg.components for s in REQUIRED_SLOTS),
    )


router = APIRouter(prefix="/configs", tags=["configs"])


@router.get("")
def list_configs() -> list[ConfigSummary]:
    """Most recently updated first."""
    return [_summary(c) for c in sorted(_all(), key=lambda c: c.updated_at, reverse=True)]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_config(body: ConfigIn) -> EnvConfig:
    _check_name_free(body.name)
    now = datetime.now(timezone.utc)
    return _save(EnvConfig(id=uuid.uuid4().hex, created_at=now, updated_at=now, **body.model_dump()))


@router.get("/{config_id}")
def get_config(config_id: ConfigId) -> EnvConfig:
    return _get(config_id)


@router.put("/{config_id}")
def update_config(config_id: ConfigId, body: ConfigIn) -> EnvConfig:
    current = _get(config_id)
    _check_name_free(body.name, except_id=config_id)
    return _save(EnvConfig(
        id=config_id, created_at=current.created_at, updated_at=datetime.now(timezone.utc),
        **body.model_dump(),
    ))


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_config(config_id: ConfigId) -> Response:
    _get(config_id)
    _path(config_id).unlink()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
