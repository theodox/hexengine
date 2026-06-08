"""
Author-facing session-state bucket patches.

Build ``BucketPatch`` values and apply them with ``ApplyBucketPatch`` (or return
``CombatOutcome`` from attack hooks). Engine read/write helpers remain internal
until phase 2 renames land.
"""

from __future__ import annotations

from ..state.actions import ApplyBucketPatch
from ..state.title_extension import BucketPatch

__all__ = ["ApplyBucketPatch", "BucketPatch"]
