"""
Combat interaction banner copy (``StateUpdate.interaction_messages`` rows).

Keyed by outcome / segment context; optional overrides via ``shell_ui`` in
``game_data.toml``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from hexengine.hooks.ui import (
    AdvanceGateInteractionContext,
    CombatInteractionContext,
)
from hexengine.hooks.ui_turn_action_dock import _shell_ui_label


def combat_instruction_for_viewer(
    ctx: CombatInteractionContext,
    shell_ui: Mapping[str, Any] | None = None,
) -> tuple[str, str]:
    """Return (instruction_kind, banner_text) for a post-combat outcome."""

    su = shell_ui if isinstance(shell_ui, Mapping) else {}
    recipient = str(ctx.viewer_faction).strip() if ctx.viewer_faction else ""
    outcome = ctx.outcome
    retreat_owner = ctx.retreat_owner_faction

    match (outcome, retreat_owner, recipient):
        case ("defender_destroyed", _, _):
            return (
                "resolved",
                _shell_ui_label(
                    su,
                    "combat_outcome_defender_destroyed",
                    "Defender destroyed.",
                ),
            )
        case ("none", _, _):
            return (
                "resolved",
                _shell_ui_label(
                    su,
                    "combat_outcome_none",
                    "Combat resolved with no effect.",
                ),
            )
        case (_, None, _):
            return (
                "resolved",
                _shell_ui_label(
                    su,
                    "combat_outcome_resolved",
                    "Combat resolved.",
                ),
            )
        case (_, ro, rec) if rec == ro:
            return (
                "retreat_required",
                _shell_ui_label(
                    su,
                    "combat_retreat_required",
                    "Mandatory retreat: move the unit one hex (exact distance).",
                ),
            )
        case _:
            return (
                "wait",
                _shell_ui_label(
                    su,
                    "combat_retreat_wait",
                    "Hold — waiting for the opponent's mandatory retreat.",
                ),
            )


def advance_gate_banners_for_viewer(
    ctx: AdvanceGateInteractionContext,
    shell_ui: Mapping[str, Any] | None = None,
) -> tuple[str, str]:
    """Return (advancing_faction_banner, waiting_faction_banner) for advance gate."""

    su = shell_ui if isinstance(shell_ui, Mapping) else {}
    return (
        _shell_ui_label(
            su,
            "combat_advance_prompt",
            "You may advance (click Advance).",
        ),
        _shell_ui_label(
            su,
            "combat_advance_wait",
            "Waiting for the opponent to advance.",
        ),
    )


__all__ = ["advance_gate_banners_for_viewer", "combat_instruction_for_viewer"]
