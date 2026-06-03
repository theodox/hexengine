"""
Turn action dock presentation keyed by ``presentation_id`` (skin), not wire fields.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from hexengine.hooks.ui_turn_action_dock import _shell_ui_label

from ..ui_markup import render_dock_gate_panel_html

# ``presentation_id`` → (shell_ui headline key, default headline, use gate hint html)
_DOCK_SKINS: dict[str, tuple[str, str, bool]] = {
    "hidden": ("", "", False),
    "routine": ("dock_routine_headline", "Your turn", False),
    "attack_ready": ("dock_attack_ready_headline", "Combat", False),
    "retreat_gate": ("dock_retreat_gate_headline", "Retreat", True),
    "advance_gate": ("dock_advance_gate_headline", "Advance", True),
    # Client SEQUENCE overrides (effective arc on the browser)
    "attack_draft": ("dock_attack_ready_headline", "Combat", False),
    "retreat_path_draft": ("dock_retreat_gate_headline", "Retreat", False),
    "place_marker_draft": ("dock_routine_headline", "Your turn", False),
}


def dock_headline(
    shell_ui: Mapping[str, Any],
    presentation_id: str,
) -> str:
    """Plain-text dock headline for a presentation skin."""

    pid = str(presentation_id or "").strip()
    if pid == "hidden":
        return ""
    spec = _DOCK_SKINS.get(pid)
    if spec is None:
        return _shell_ui_label(shell_ui, "dock_routine_headline", "Your turn")
    key, default, _ = spec
    if not key:
        return ""
    return _shell_ui_label(shell_ui, key, default)


def dock_panel_html(
    shell_ui: Mapping[str, Any],
    presentation_id: str,
) -> str:
    """Optional decorative HTML under the dock headline."""

    pid = str(presentation_id or "").strip()
    spec = _DOCK_SKINS.get(pid)
    if spec is None or not spec[2]:
        return ""
    hint = shell_ui.get("dock_gate_panel_hint") if isinstance(shell_ui, Mapping) else None
    hint_s = str(hint).strip() if isinstance(hint, str) else ""
    if not hint_s:
        return ""
    return render_dock_gate_panel_html(hint_s)


__all__ = ["dock_headline", "dock_panel_html"]
