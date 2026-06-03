"""current_segment presentation enrichment (P3)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GAMES = str(REPO_ROOT / "games")
SRC = str(REPO_ROOT / "src")
for p in (GAMES, SRC):
    if p not in sys.path:
        sys.path.insert(0, p)

from hexengine.arcs.segment_wire import default_segment_presentation_patch
from hexengine.game.arcs.client_interaction_panels import (
    effective_turn_dock_presentation_id,
)


def test_default_patch_infers_attack_plan_from_locus() -> None:
    seg = {
        "kind": "combat",
        "allowed_actions": ["Attack", "NextPhase"],
        "action_locus": {"Attack": "client_draft", "NextPhase": "server"},
    }
    patch = default_segment_presentation_patch(
        seg, viewer_may_act=True, current_phase="Combat"
    )
    assert patch["presentation_id"] == "attack_ready"
    assert patch["interaction_mode"] == "attack_plan"


def test_client_effective_presentation_id_uses_interaction_mode() -> None:
    assert (
        effective_turn_dock_presentation_id(
            "attack_ready",
            "attack_plan",
            interaction_draft_active=True,
        )
        == "attack_draft"
    )
    assert (
        effective_turn_dock_presentation_id(
            "retreat_gate",
            "retreat_path",
            interaction_draft_active=False,
        )
        == "retreat_gate"
    )


def test_hexdemo_enrich_hook_wired() -> None:
    from games.hexdemo.hooks import build_hooks

    assert build_hooks().ui.enrich_current_segment is not None
