# A package on purpose: pytest then puts samples/ (the first folder up without an __init__.py) on
# sys.path, so the tests import rlgym_gui_samples from this checkout, not an installed copy. The name
# isn't "tests" so it can't be confused with rlgym-server/tests.
