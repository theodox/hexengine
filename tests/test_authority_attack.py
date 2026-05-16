"""Tests for `hexengine.server.arcs.authority_attack` pipeline metadata and helpers."""

from __future__ import annotations

from hexengine.server.arcs.authority_attack import (
    AUTHORITY_ATTACK_PIPELINE,
    AuthorityAttackPipelineStep,
    dedupe_wire_id_list,
    normalize_attack_party_ids,
)

EXPECTED_ORDER = (
    AuthorityAttackPipelineStep.NORMALIZE_WIRE_AND_PARTIES,
    AuthorityAttackPipelineStep.HOOK_VALIDATE,
    AuthorityAttackPipelineStep.HOOK_RESOLVE,
    AuthorityAttackPipelineStep.REQUIRE_TITLE_EXTENSION_KEY,
    AuthorityAttackPipelineStep.COMMIT_ATTACK_AND_EFFECTS,
    AuthorityAttackPipelineStep.BROADCAST_COMBAT_EVENTS,
    AuthorityAttackPipelineStep.MAYBE_AUTO_ADVANCE_PHASE,
)


def test_authority_attack_pipeline_order_is_stable() -> None:
    assert AUTHORITY_ATTACK_PIPELINE == EXPECTED_ORDER
    assert len(AUTHORITY_ATTACK_PIPELINE) == 7


def test_normalize_attack_party_ids_anchor_first() -> None:
    p = {"attacker_ids": ["b", "a"]}
    assert normalize_attack_party_ids(p, anchor_id="a", plural_key="attacker_ids") == (
        "a",
        "b",
    )


def test_dedupe_wire_id_list() -> None:
    assert dedupe_wire_id_list(["x", " x ", "y", "x"]) == ["x", "y"]
