"""
Author-facing unit attribute patches.

Build ``UnitAttributesPatch`` values and apply them with ``ApplyUnitAttributesPatch``.
"""

from __future__ import annotations

from ..state.actions import ApplyUnitAttributesPatch
from ..state.unit_attributes import UnitAttributesPatch

__all__ = ["ApplyUnitAttributesPatch", "UnitAttributesPatch"]
