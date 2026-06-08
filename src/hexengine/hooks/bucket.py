"""
Author-facing session-state bucket patches.

Build ``BucketPatch`` values and apply them with ``ApplyBucketPatch`` (or return
``CombatOutcome`` from attack hooks). Engine read/write uses
``hexengine.state.engine_session_state``.
"""

from __future__ import annotations

from ..state.actions import ApplyBucketPatch
from ..state.engine_session_state import BucketPatch

__all__ = ["ApplyBucketPatch", "BucketPatch"]
