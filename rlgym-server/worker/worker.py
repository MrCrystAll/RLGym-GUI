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
    if a is inspect.Parameter.empty:
        return None
    # formatannotation keeps generics whole (Optional[int], not Optional) and builtins short
    # (float, not builtins.float). String annotations (from __future__ import annotations) as is.
    return a if isinstance(a, str) else inspect.formatannotation(a)


def _own_doc(cls):
    # Not inspect.getdoc: it falls back to the base class, so an undocumented reward would show
    # rlgym's generic "The reward function class..." text.
    doc = cls.__dict__.get("__doc__")
    return inspect.cleandoc(doc) if doc else None


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
                                   "qualified_name": qname, "doc": _own_doc(cls),
                                   "params": _params(cls)})
    return {"components": components, "errors": errors}


# The arguments of rlgym.api.RLGym(...) (minus the renderer) and the component kind each takes;
# same as SLOT_KINDS and REQUIRED_SLOTS in the backend's configs.py.
SLOT_KINDS = {
    "transition_engine": "transition_engine",
    "state_mutator": "state_mutator",
    "obs_builder": "obs_builder",
    "action_parser": "action_parser",
    "reward_fn": "reward_function",
    "termination_cond": "done_condition",
    "truncation_cond": "done_condition",
    "shared_info_provider": "shared_info_provider",
}
REQUIRED_SLOTS = ("transition_engine", "state_mutator", "obs_builder", "action_parser", "reward_fn")


def _error(exc):
    return f"{type(exc).__name__}: {exc}"


def _import_class(qualified_name):
    """my_bot.rewards.GoalReward -> the class. The module part is the longest prefix that imports,
    so nested classes (my_bot.rewards.Outer.Inner) work too."""
    parts = qualified_name.split(".")
    for i in range(len(parts) - 1, 0, -1):
        module_name = ".".join(parts[:i])
        try:
            obj = importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            # Only "this prefix isn't a module" means try a shorter one; a missing dependency
            # inside the user's module is a real error.
            if exc.name and module_name.startswith(exc.name):
                continue
            raise
        for attr in parts[i:]:
            obj = getattr(obj, attr)
        return obj
    raise ImportError(f"No module found for '{qualified_name}'")


def _build(slot, choice, bases):
    """Construct one component. Returns (instance, None) or (None, {stage, param, error})."""
    try:
        cls = _import_class(choice["qualified_name"])
    except Exception as exc:
        return None, {"stage": "import", "param": None, "error": _error(exc)}
    base = bases.get(SLOT_KINDS[slot])
    if not (inspect.isclass(cls) and base is not None and issubclass(cls, base)):
        return None, {"stage": "kind", "param": None,
                      "error": f"{choice['qualified_name']} is not a {base.__name__ if base else SLOT_KINDS[slot]}"}
    # Arguments are Python expressions, evaluated where the class is defined, so they can use
    # what its module imports (np.float32(1), SomeOtherComponent()...). A copy: eval must not
    # leave anything behind in the user's module.
    namespace = dict(vars(sys.modules[cls.__module__]))
    kwargs = {}
    for name, expr in choice.get("params", {}).items():
        try:
            kwargs[name] = eval(expr, namespace)
        except Exception as exc:                         # SyntaxError included
            return None, {"stage": "argument", "param": name, "error": _error(exc)}
    try:
        return cls(**kwargs), None
    except Exception as exc:
        return None, {"stage": "construct", "param": None, "error": _error(exc)}


def validate(params):
    """Build every chosen component, then RLGym(...) from them. Nothing is reset or stepped."""
    import rlgym.api as api
    bases = {k: getattr(api, n) for k, n in KINDS.items() if hasattr(api, n)}
    chosen = params.get("components", {})
    built, slots = {}, {}
    for slot in SLOT_KINDS:
        if slot not in chosen:
            continue
        instance, problem = _build(slot, chosen[slot], bases)
        slots[slot] = problem or {"stage": None, "param": None, "error": None}
        if problem is None:
            built[slot] = instance
    missing = [s for s in REQUIRED_SLOTS if s not in chosen]
    env_built, env_error = False, None
    # Only worth trying when every chosen part built and nothing required is missing: otherwise
    # the error would just repeat the ones above.
    if not missing and len(built) == len(slots):
        try:
            api.RLGym(**built)
            env_built = True
        except Exception as exc:
            env_error = _error(exc)
    return {"ok": env_built, "slots": slots, "missing": missing,
            "env_built": env_built, "env_error": env_error}


METHODS = {"info": info, "discover": discover, "validate": validate}


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