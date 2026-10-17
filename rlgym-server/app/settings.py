"""User settings (Python interpreter, modules to scan), stored as DATA_DIR/settings.json."""
import logging
import os
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, Field, ValidationError, field_validator

from . import config

log = logging.getLogger(__name__)


class Settings(BaseModel):
    python: str | None = Field(
        default=None, description="Path to the Python executable that runs the worker"
    )
    modules: list[str] = Field(
        default_factory=list, description="Modules to scan for RLGym components"
    )

    @field_validator("python")
    @classmethod
    def blank_python_is_unset(cls, v: str | None) -> str | None:
        v = v.strip() if v else v
        return v or None

    @field_validator("modules")
    @classmethod
    def clean_modules(cls, v: list[str]) -> list[str]:
        # Trimmed, no blanks, no duplicates, order kept: the list is typed in by hand.
        return list(dict.fromkeys(m.strip() for m in v if m.strip()))


def _path() -> Path:
    return Path(config.DATA_DIR) / "settings.json"


def load() -> Settings:
    path = _path()
    try:
        return Settings.model_validate_json(path.read_bytes())
    except FileNotFoundError:
        return Settings()
    except (OSError, ValidationError) as exc:
        # A hand-edited or truncated file must not take the backend down; start from defaults.
        log.warning("Ignoring unreadable %s: %s", path, exc)
        return Settings()


def save(settings: Settings) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write then rename, so a crash mid-write never leaves a half-written settings file.
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(settings.model_dump_json(indent=2), encoding="utf-8")
    os.replace(tmp, path)


router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
def get_settings() -> Settings:
    return load()


@router.put("")
def update_settings(settings: Settings) -> Settings:
    save(settings)
    return settings
