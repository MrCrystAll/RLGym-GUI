"""Components with the shapes real user code has: no docstring, generic annotations."""
from typing import Optional

from rlgym.api import ObsBuilder, StateMutator


class Undocumented(StateMutator):
    def __init__(self):
        pass

    def apply(self, *args, **kwargs):
        pass


class Generic(ObsBuilder):
    """Indented docstring.

        Second paragraph, indented.
    """

    def __init__(self, max_players: Optional[int] = None, names: list[str] = (), scale: "float" = 1.0):
        pass

    def get_obs_space(self, *args, **kwargs):
        pass

    def reset(self, *args, **kwargs):
        pass

    def build_obs(self, *args, **kwargs):
        pass
