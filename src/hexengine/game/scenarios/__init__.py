"""
Deprecated compatibility shim. Import from ``hexengine.scenarios`` instead.
"""

from __future__ import annotations

import importlib
import warnings
from types import ModuleType

warnings.warn(
    "hexengine.game.scenarios is deprecated; use hexengine.scenarios instead.",
    DeprecationWarning,
    stacklevel=2,
)

_mod: ModuleType = importlib.import_module("hexengine.scenarios")
for _name in _mod.__all__:
    globals()[_name] = getattr(_mod, _name)
__all__: list[str] = list(_mod.__all__)
