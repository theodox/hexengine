"""Engine default primary action rows for `UIHook.PRIMARY_ACTIONS_FOR_VIEWER`."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ..state import GameState


@dataclass(frozen=True, slots=True)
class PrimaryActionsContext:
    """Inputs for building per-viewer `StateUpdate.primary_actions` rows."""

    state: GameState
    viewer_faction: str | None
    extension_key: str | None
    shell_ui: Mapping[str, Any]


def _shell_ui_label(shell_ui: Mapping[str, Any], key: str, default: str) -> str:
    raw = shell_ui.get(key) if isinstance(shell_ui, Mapping) else None
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return default


def default_primary_actions_for_viewer(
    ctx: PrimaryActionsContext,
) -> list[dict[str, Any]]:
    """Engine catalog default: disrupt/advance rows from title extension state."""

    ek = str(ctx.extension_key).strip() if ctx.extension_key else ""
    if not ek:
        return []
    my = str(ctx.viewer_faction).strip() if ctx.viewer_faction else ""
    if not my:
        return []

    from ..state.title_extension import title_bucket

    hx = title_bucket(ctx.state, ek)
    if not hx:
        return []

    su = ctx.shell_ui if isinstance(ctx.shell_ui, Mapping) else {}
    out: list[dict[str, Any]] = []
    gate = str(hx.get("combat_gate", "")).strip()

    if gate == "awaiting_retreat_or_disrupt":
        ro = hx.get("retreat_obligations")
        if isinstance(ro, dict):
            for uid, raw in ro.items():
                try:
                    if int(raw) <= 0:
                        continue
                except (TypeError, ValueError):
                    continue
                u = ctx.state.board.units.get(str(uid))
                if u is not None and u.active and str(u.faction).strip() == my:
                    out.append(
                        {
                            "schema": 1,
                            "id": "combat_disrupt_instead",
                            "action_type": "CombatDisruptInsteadOfRetreat",
                            "label": _shell_ui_label(
                                su,
                                "disrupt_instead_label",
                                "Disrupt instead of retreat",
                            ),
                            "title": _shell_ui_label(
                                su,
                                "disrupt_instead_title",
                                "Take disruption on your retreating stack and waive "
                                "the mandatory retreat (when the title allows).",
                            ),
                            "payload": {},
                            "css_class": "hexengine-primary-action--disrupt",
                            "enabled": True,
                        }
                    )
                    break

    if gate == "awaiting_advance":
        adv = hx.get("advance")
        adv_faction = (
            str(adv.get("faction", "")).strip() if isinstance(adv, dict) else ""
        )
        if adv_faction == my:
            out.append(
                {
                    "schema": 1,
                    "id": "combat_advance",
                    "action_type": "CombatAdvance",
                    "label": _shell_ui_label(su, "combat_advance_label", "Advance"),
                    "title": _shell_ui_label(
                        su,
                        "combat_advance_title",
                        "Advance after opponent retreats (when allowed).",
                    ),
                    "payload": {},
                    "css_class": "hexengine-primary-action--advance",
                    "enabled": True,
                }
            )
            out.append(
                {
                    "schema": 1,
                    "id": "combat_decline_advance",
                    "action_type": "CombatDeclineAdvance",
                    "label": _shell_ui_label(
                        su, "combat_decline_advance_label", "Skip"
                    ),
                    "title": _shell_ui_label(
                        su,
                        "combat_decline_advance_title",
                        "Skip the optional advance.",
                    ),
                    "payload": {},
                    "css_class": "hexengine-primary-action--decline-advance",
                    "enabled": True,
                }
            )

    return out


__all__ = ["PrimaryActionsContext", "default_primary_actions_for_viewer"]
