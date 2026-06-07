"""
Map callout copy keyed by ``inform_profile`` (from ``segment_ui`` / ``current_segment``).

Shell keys follow ``{profile}_{reason}`` in ``game_data.toml`` → ``shell_ui``.
Profiles without rows in ``_REASONS_BY_PROFILE`` still get CSS from ``_CSS_BY_PROFILE``
and generic shell/fallback text until client lanes add reason ids.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from hexengine.authoring.present import InformPopup
from hexengine.authoring.present import inform_popup as build_inform_popup
from hexengine.hooks.ui_turn_action_dock import _shell_ui_label


@dataclass(frozen=True, slots=True)
class InformReasonRow:
    shell_key: str
    default_text: str
    ttl_ms: int = 1500


# ``inform_profile`` → reason id → row
_REASONS_BY_PROFILE: dict[str, dict[str, InformReasonRow]] = {
    "attack_plan": {
        "no_enemy_on_hex": InformReasonRow(
            "attack_plan_no_enemy_on_hex",
            "No enemy unit on that hex.",
            ttl_ms=500,
        ),
        "no_attackable_enemy": InformReasonRow(
            "attack_plan_no_attackable_enemy",
            "No attackable enemy on that hex.",
            ttl_ms=750,
        ),
        "cannot_attack_target": InformReasonRow(
            "attack_plan_cannot_attack_target",
            "Cannot attack target.",
            ttl_ms=1000,
        ),
    },
}

_CSS_BY_PROFILE: dict[str, str] = {
    "attack_plan": "hexdemo-inform-popup hexdemo-inform-popup--attack-plan",
    "retreat_gate": "hexdemo-inform-popup hexdemo-inform-popup--retreat-gate",
    "advance_gate": "hexdemo-inform-popup hexdemo-inform-popup--advance-gate",
}


def inform_popup_for_profile(
    shell_ui: Mapping[str, Any],
    profile: str,
    reason: str,
) -> InformPopup:
    """Build one INFORM callout for a registry ``inform_profile`` + reason id."""

    pid = str(profile or "").strip()
    rid = str(reason or "").strip()
    rows = _REASONS_BY_PROFILE.get(pid, {})
    row = rows.get(rid)
    if row is None:
        text = _shell_ui_label(
            shell_ui,
            f"{pid}_{rid}" if pid else f"inform_{rid}",
            f"{pid.replace('_', ' ') if pid else 'Inform'}: {rid.replace('_', ' ')}.",
        )
        ttl_ms = 1500
    else:
        text = _shell_ui_label(shell_ui, row.shell_key, row.default_text)
        ttl_ms = row.ttl_ms
    css = _CSS_BY_PROFILE.get(pid, "hexdemo-inform-popup")
    return build_inform_popup(
        text=text,
        kind="info",
        ttl_ms=ttl_ms,
        css_class=css,
    )


__all__ = ["InformReasonRow", "inform_popup_for_profile"]
