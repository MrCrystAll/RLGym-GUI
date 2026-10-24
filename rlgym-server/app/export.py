"""Export a saved config as Python (a snippet or a runnable script) or JSON."""
import re
from datetime import date
from enum import Enum

from fastapi import APIRouter
from pydantic import BaseModel, Field

from .configs import REQUIRED_SLOTS, SLOT_KINDS, ConfigId, ConfigIn, EnvConfig, Slot, _get


class ExportFormat(str, Enum):
    snippet = "snippet"
    script = "script"
    json = "json"


class ConfigExport(BaseModel):
    format: ExportFormat
    filename: str = Field(description="Suggested file name, derived from the config name")
    content: str
    missing_slots: list[Slot] = Field(
        description="Required slots without a component; the Python formats leave `...` in their place"
    )


def _slug(name: str) -> str:
    """A file name that is also a valid Python module name."""
    slug = re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_").lower() or "config"
    return f"config_{slug}" if slug[0].isdigit() else slug


def _imports(cfg: EnvConfig) -> tuple[list[str], dict[str, str]]:
    """`from module import A, B` lines, and the local name of each chosen class. Two classes with
    the same name from different modules get an alias."""
    by_module: dict[str, list[tuple[str, str]]] = {}
    local: dict[str, str] = {}
    taken: set[str] = {"RLGym"}
    for slot in SLOT_KINDS:
        choice = cfg.components.get(slot)
        if choice is None or choice.qualified_name in local:
            continue
        module, _, cls = choice.qualified_name.rpartition(".")
        alias, n = cls, 2
        while alias in taken:
            alias, n = f"{cls}_{n}", n + 1
        taken.add(alias)
        local[choice.qualified_name] = alias
        by_module.setdefault(module, []).append((cls, alias))
    lines = [
        f"from {module} import " + ", ".join(cls if cls == alias else f"{cls} as {alias}" for cls, alias in names)
        for module, names in sorted(by_module.items())
    ]
    return lines, local


def _python(cfg: EnvConfig, runnable: bool) -> str:
    import_lines, local = _imports(cfg)
    args = []
    for slot in SLOT_KINDS:
        choice = cfg.components.get(slot)
        if choice is None:
            if slot in REQUIRED_SLOTS:
                args.append(f"{slot}=...,  # not chosen yet")
            continue
        # Stored values are Python expressions: written as-is, not quoted.
        params = ", ".join(f"{k}={v}" for k, v in choice.params.items())
        args.append(f"{slot}={local[choice.qualified_name]}({params}),")

    # Comments rather than a docstring: the name is user text, and may contain quotes.
    name = " ".join(cfg.name.split())
    header = [
        f"# RLGym environment: {name}",
        f"# Exported from RLGym GUI on {date.today().isoformat()}.",
        "# Argument values are copied as written in the GUI: add any imports they need (e.g. numpy).",
        "",
        "from rlgym.api import RLGym",
        "",
        *import_lines,
        "",
    ]
    if not runnable:
        return "\n".join([*header, "", "env = RLGym(", *(f"    {a}" for a in args), ")", ""])
    return "\n".join([
        *header,
        "",
        "def make_env() -> RLGym:",
        "    return RLGym(",
        *(f"        {a}" for a in args),
        "    )",
        "",
        "",
        'if __name__ == "__main__":',
        "    env = make_env()",
        "    try:",
        "        obs = env.reset()",
        '        print(f"{len(env.agents)} agent(s)")',
        "        for agent, agent_obs in obs.items():",
        '            print(f"  {agent}: obs shape {getattr(agent_obs, \'shape\', type(agent_obs).__name__)}")',
        "    finally:",
        "        env.close()",
        "",
    ])


def export(cfg: EnvConfig, fmt: ExportFormat) -> ConfigExport:
    slug = _slug(cfg.name)
    if fmt is ExportFormat.json:
        # Same shape as the body of POST /configs, so the file can be imported back.
        content = ConfigIn(name=cfg.name, components=cfg.components).model_dump_json(indent=2) + "\n"
        filename = f"{slug}.json"
    elif fmt is ExportFormat.snippet:
        content, filename = _python(cfg, runnable=False), f"{slug}.py"
    else:
        content, filename = _python(cfg, runnable=True), f"run_{slug}.py"
    return ConfigExport(
        format=fmt, filename=filename, content=content,
        missing_slots=[s for s in REQUIRED_SLOTS if s not in cfg.components],
    )


router = APIRouter(prefix="/configs", tags=["configs"])


@router.get("/{config_id}/export")
def export_config(config_id: ConfigId, format: ExportFormat) -> ConfigExport:
    return export(_get(config_id), format)
