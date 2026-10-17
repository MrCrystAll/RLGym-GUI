"""RLGym GUI worker. Runs inside the USER's Python interpreter.
Only the stdlib and rlgym.api may be imported at module level."""
from __future__ import annotations

import importlib
import importlib.metadata as md
import inspect
import json
import os
import sys

# Keep the protocol channel clean: anything user code prints goes to stderr.
_proto = os.fdopen(os.dup(sys.stdout.fileno()), "w", encoding="utf-8")
sys.stdout = sys.stderr

KINDS = {
    "transition_engine": "TransitionEngine",
    "state_mutator": "StateMutator",
    "obs_builder": "ObsBuilder",
    "action_parser": "ActionParser",
    "reward_function": "RewardFunction",
    "done_condition": "DoneCondition",
    "shared_info_provider": "SharedInfoProvider",
}


def info(_params):
    result = {"python": sys.version.split()[0], "executable": sys.executable,
              "rlgym_api": None, "error": None}
    try:
        import rlgym.api  # noqa: F401
        try:
            result["rlgym_api"] = md.version("rlgym-api")
        except Exception:
            result["rlgym_api"] = "unknown"
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def _type_name(a):
    return None if a is inspect.Parameter.empty else (getattr(a, "__name__", None) or str(a))


def _params(cls):
    try:
        sig = inspect.signature(cls.__init__)
    except (TypeError, ValueError):
        return []
    out = []
    for p in list(sig.parameters.values())[1:]:          # skip self
        if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        required = p.default is p.empty
        out.append({"name": p.name, "type": _type_name(p.annotation),
                    "default": None if required else repr(p.default), "required": required})
    return out


def discover(params):
    import rlgym.api as api
    bases = {k: getattr(api, n) for k, n in KINDS.items() if hasattr(api, n)}
    components, errors, seen = [], [], set()
    for name in params.get("modules", []):
        try:
            module = importlib.import_module(name)
        except Exception as exc:                         # a broken module must not kill the worker
            errors.append({"module": name, "message": f"{type(exc).__name__}: {exc}"})
            continue
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__.startswith("rlgym.api") or inspect.isabstract(cls):
                continue
            kind = next((k for k, b in bases.items() if issubclass(cls, b)), None)
            qname = f"{cls.__module__}.{cls.__qualname__}"
            if kind and qname not in seen:
                seen.add(qname)
                components.append({"kind": kind, "name": cls.__name__, "module": cls.__module__,
                                   "qualified_name": qname, "doc": inspect.getdoc(cls),
                                   "params": _params(cls)})
    return {"components": components, "errors": errors}


METHODS = {"info": info, "discover": discover}


def main():
    for line in sys.stdin:                               # loop ends (process exits) when the backend dies
        line = line.strip()
        if not line:
            continue
        req = json.loads(line)
        try:
            resp = {"id": req["id"], "result": METHODS[req["method"]](req.get("params") or {})}
        except Exception as exc:
            resp = {"id": req.get("id"), "error": f"{type(exc).__name__}: {exc}"}
        _proto.write(json.dumps(resp) + "\n")
        _proto.flush()


if __name__ == "__main__":
    main()