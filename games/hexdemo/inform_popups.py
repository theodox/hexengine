"""Map callouts for INFORM ``inform`` inspect requests (attack-plan feedback, etc.)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from hexengine.hooks.inform_popup import InformPopupContext


def _shell_label(shell_ui: Mapping[str, Any], key: str, default: str) -> str:
    raw = shell_ui.get(key) if isinstance(shell_ui, Mapping) else None
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return default


def inform_popup(ctx: InformPopupContext) -> dict[str, Any]:
    su = ctx.shell_ui if isinstance(ctx.shell_ui, Mapping) else {}
    kind = str(ctx.inform_kind or "").strip()
    reason = str(ctx.reason or "").strip()

    if kind == "attack_plan":
        if reason == "no_enemy_on_hex":
            text = _shell_label(
                su,
                "attack_plan_no_enemy_on_hex",
                "No enemy unit on that hex.",
            )
        elif reason == "no_attackable_enemy":
            text = _shell_label(
                su,
                "attack_plan_no_attackable_enemy",
                "No attackable enemy on that hex.",
            )
        elif reason == "cannot_attack_target":
            text = _shell_label(
                su,
                "attack_plan_cannot_attack_target",
                "Cannot attack target.",
            )
        else:
            text = _shell_label(
                su,
                f"attack_plan_{reason}",
                f"Attack plan: {reason.replace('_', ' ')}.",
            )
        return {
            "text": text,
            "kind": "info",
            "ttl_ms": 1500,
            "css_class": "hexdemo-inform-popup hexdemo-inform-popup--attack-plan",
        }

    return {
        "text": _shell_label(
            su,
            f"inform_{kind}_{reason}",
            f"{kind}: {reason.replace('_', ' ')}.",
        ),
        "kind": "info",
        "ttl_ms": 1500,
    }


__all__ = ["inform_popup"]
