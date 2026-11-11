import importlib.util
import sys
from pathlib import Path

# Import the repo root as the `greenlight` package for tests.
_root = Path(__file__).parent
if "greenlight" not in sys.modules:
    spec = importlib.util.spec_from_file_location("greenlight", _root / "__init__.py", submodule_search_locations=[str(_root)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules["greenlight"] = mod
    spec.loader.exec_module(mod)
