"""
Single runtime gateway to hexengine.authoring (strict import boundary).

Only this module and hooks.internal.contracts may import hexengine.authoring
from engine runtime code. Titles import authoring directly.
"""

from __future__ import annotations

from typing import Any


def validate_declared_arcs(game_definition: Any) -> list[str]:
    """Run arc/registry validation for a game definition (startup)."""

    from ...authoring.validate import validate_arc_contract_for_definition

    return validate_arc_contract_for_definition(game_definition)


__all__ = [
    "validate_declared_arcs",
]
