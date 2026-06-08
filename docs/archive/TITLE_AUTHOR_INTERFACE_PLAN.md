# Title author interface — implementation plan

**Status:** **archived** (Phases A–F complete; hexdemo is the reference layout). Living guide: [`TITLE_AUTHORING.md`](../TITLE_AUTHORING.md).

**One-line goal:** Give title authors **one coherent programming interface** for match flow — rules in pack-root modules, a single combat binding into declared arcs, presentation in a segment registry — so authors do not need to learn engine pipelines, bucket handoff protocols, or duplicate hook surfaces.

**Author hub:** [`TITLE_AUTHORING.md`](../TITLE_AUTHORING.md). **Hexdemo map:** [`games/hexdemo/hooks/README.md`](../../games/hexdemo/hooks/README.md).

**Related:** [`COMPOSABLE_ARCS_PLAN.md`](COMPOSABLE_ARCS_PLAN.md) (arc runtime), [`RULE_COMPOSITION.md`](../RULE_COMPOSITION.md) (future reusable rule pieces).

---

## Current state (hexdemo)

Extension-key titles with a declared combat arc (`SEG_ATTACK`) use **one attack path**:

```
Attack RPC → SetArcCursor(attack) → submit_event("Attack")
  → binding.attack_arc_effect (resolve + Attack + ApplyCombatEffects + CombatOutcome)
  → classify → retreat / advance gates or done
  → restore_routine_cursor when overlay completes
```

| Author concern | Hexdemo module | Hook / arc slot |
|----------------|----------------|-----------------|
| CRT / dice | `combat_rules.py` | `AttackHook.resolve_attack` |
| Post-attack bucket | `combat_outcome.py` | `AttackHook.combat_outcome_after_applied` → `CombatOutcome` |
| Cleanup guards/effects | `combat_rules.HexdemoCombatRules` (`BINDING`) | `ArcHook.COMBAT_ARC` via `combat_rules_binding_to_arc_spec` |
| Low-level cleanup mutations | `combat_actions.py` | Called from binding effect methods |
| Gate ui_mode strings / phase clear | `combat_transitions.py` | `COMBAT_ARC_GATE_UI_MODES`, `clear_combat_state_actions` |
| “May I attack?” (rules) | `combat_rules.validate_attack` | Engine segment gate runs first |
| Movement / retreat | `movement_rules.py` | `MovementHook.*` adapters |
| Buttons / copy | `segment_ui.py`, `presentation/` | `UIHook` dock + inform |

**Removed from engine and hexdemo:** `AttackHook.AFTER_ATTACK_APPLIED`, `follow_up_after_attack`, deprecated attack cleanup hook slots (`ON_RETREAT_OBLIGATION_CLEARED`, `COMBAT_DISRUPT_*`, `IS_COMBAT_ADVANCE_MOVE`). Cleanup and advance `MoveUnit` routing are **arc-only**.

**Engine-owned:** wire normalize, `submit_event`, `Attack` / `ApplyCombatEffects` assembly, `restore_routine_cursor` after overlay completion, movement payload bridge, `current_segment` projection.

**Still hybrid (not author API):** `_execute_imperative_attack` for packs without `SEG_ATTACK`; movement `ResolvePassMovementInterrupt` fallback when arc sync fails.

---

## Why (original problem)

Composable arcs finished **combat cleanup** as a declared FSM (`submit_event` on retreat, advance, disrupt). Before Phases C–D, authors had to learn two systems for one feature (resolve hooks + separate handoff + duplicate cleanup slots). That split is **closed** in hexdemo; new packs should copy [`games/template/`](../../games/template/) + hexdemo, not pre-2025 hook shapes.

---

## Target author mental model

Authors work in **three layers** only (aligned with [`TITLE_AUTHORING.md` § Flow vs presentation](TITLE_AUTHORING.md#flow-vs-presentation-authoring-model)):

```
┌─────────────────────────────────────────────────────────┐
│  RULES (pack root)                                       │
│  Pure policy: GameState (+ typed contexts) → outcomes   │
│  e.g. session_state.py, combat_rules.py, movement_rules.py │
└──────────────────────────┬──────────────────────────────┘
                           │ called from
┌──────────────────────────▼──────────────────────────────┐
│  FLOW BINDING (one module per arc family)                │
│  combat_arc.py — single class wires rules → ArcSpec      │
│  turn_arc_schedule.py, hooks/arcs.py — registry only     │
└──────────────────────────┬──────────────────────────────┘
                           │ thin adapters
┌──────────────────────────▼──────────────────────────────┐
│  HOOKS (integration)                                     │
│  hooks/*.py — @bind_title_hook only; preview + UI        │
└─────────────────────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│  PRESENTATION                                            │
│  segment_ui.py registry + presentation/ + shell_ui       │
└─────────────────────────────────────────────────────────┘
```

**Author question map** (no engine pipeline in the answer):

| Question | Author API (target) |
|----------|---------------------|
| Is this attack legal? | `rules.validate_attack(ctx)`; engine applies segment deny first |
| What happens when dice land? | `rules.resolve_attack(ctx) → CombatOutcome` |
| What must players do next? | Declared combat arc (engine applies outcome → cursor) |
| Retreat / advance / disrupt | Same binding as cleanup (arc effects) |
| Buttons / map mode | Segment registry + `presentation/` |
| Auto-advance phase after attack / move | Optional policy methods on binding or tiny hooks |
| Move budget / ZoC / retreat legality? | `movement_rules.py` (`MovementRulesBinding`) |
| Stepwise path / interrupts? | Engine movement arc bridge (authors supply step cost + interrupt factions hooks only) |

**Engine-owned (authors never implement):** `execute_authority_attack_request` wire normalize + `submit_event`, `restore_routine_cursor` when the combat overlay finishes, `Attack` / `ApplyCombatEffects` assembly helpers, movement payload bridge, `current_segment` projection. `begin_combat_arc` remains a **test / cleanup-only** entry when bucket state is already set without an `Attack` RPC.

---

## Design decisions (resolved for this plan)

1. **Single combat binding type.** One author-facing class (working name `CombatRulesBinding`) implements validate, resolve, and all `CombatArcEffectsBinding` guards/effects. Lives in `games/<pack>/combat_arc.py`; hooks re-export only what the engine still calls by slot name during migration.

2. **`CombatOutcome` title DTO.** Authors return a stable pack-level outcome type (outcome enum, retreat metadata, optional table/CRT fields, bucket patch hints). The engine adapter converts to `AttackResolution` + `StateAction`s during migration, then owns conversion entirely.

3. **Bucket access only via `session_state` helpers.** Documented author API uses typed accessors (`retreat_obligations(state)`, `set_last_combat(...)`, etc.). Raw bucket key strings are not part of the author guide.

4. **Cleanup only on the arc.** `AttackHook` slots `combat_disrupt_instead_of_retreat`, `combat_resolve_advance`, `on_retreat_obligation_cleared`, `is_combat_advance_move` are deprecated and removed from author docs; arc binding is authoritative.

5. **Incremental delivery.** Phases A–C improve the interface without requiring full `Attack` → `submit_event` migration (Phase D). Movement unification (Phase E) follows the same pattern later.

---

## Phases

### Phase A — Clarify and trim the public surface

**Status:** done.

**Goal:** Stop documenting and wiring duplicate cleanup paths; authors see one cleanup owner.

#### Sub-steps (completed)

1. **Marked deprecated** on `AttackHook`: `COMBAT_DISRUPT_INSTEAD_OF_RETREAT`, `COMBAT_RESOLVE_ADVANCE`, `ON_RETREAT_OBLIGATION_CLEARED`, `IS_COMBAT_ADVANCE_MOVE`; documented in [`PACK_HOOK_CONTRACTS.md`](../PACK_HOOK_CONTRACTS.md).
2. **Removed dead server paths:** `GameServer._on_retreat_obligation_cleared` / `_maybe_open_combat_advance_after_retreat`; tests use `begin_combat_arc`.
3. **Docs:** [`TITLE_AUTHORING.md`](../TITLE_AUTHORING.md), [`PACK_HOOK_CONTRACTS.md`](../PACK_HOOK_CONTRACTS.md), [`games/hexdemo/hooks/README.md`](../../games/hexdemo/hooks/README.md).
4. **Hexdemo:** Unbound cleanup slots from `hooks/attack.py`; `combat_arc.py` owns cleanup + `ArcSpec.advance_move_detector` for advance `MoveUnit` pre-routing.

#### Tests that must stay green

`test_hooks_contract`, `test_combat_hexdemo`, `test_combat_arc_dispatch`, `test_authoring_combat_pattern`.

---

### Phase B — Engine-owned segment gate before title validate

**Status:** done.

**Goal:** Authors do not import `arc_segment` in `validate_attack`.

#### Sub-steps (completed)

1. `execute_authority_attack_request` calls `segment_denies_action_for_faction` before `validate_attack` when `session_state_key` is set; message `ATTACK_BLOCKED_BY_ACTIVE_SEGMENT_MSG`.
2. Removed segment deny from hexdemo `validate_attack`; `arc_segment.segment_denies_action` delegates to `segment_wire`.
3. Documented in [`PACK_HOOK_CONTRACTS.md`](../PACK_HOOK_CONTRACTS.md) and [`TITLE_AUTHORING.md`](../TITLE_AUTHORING.md).

#### Tests

`test_authority_attack.test_attack_rejected_on_retreat_gate_before_title_validate`; `test_combat_hexdemo` and `test_arc_segment` unchanged.

---

### Phase C — `CombatOutcome` + engine adapter (collapse handoff)

**Status:** done.

**Goal:** Replace `after_attack_applied` / `follow_up_after_attack` with one author outcome type and an engine adapter that applies state + starts classify.

#### Sub-steps

1. **Add** `hexengine.authoring.combat_outcome` (or `hexengine.hooks.attack_outcome`): `CombatOutcome` dataclass + `apply_outcome(outcome, ctx) -> list[StateAction]` engine helper (or title-scoped adapter interface).
2. **Extend** `CombatRulesBinding` / pattern: `resolve_attack(ctx) -> CombatOutcome` (authors may still return `AttackResolution` during deprecation window via adapter).
3. **Engine:** After `Attack` + `ApplyCombatEffects`, call `outcome.to_state_actions(ctx)` instead of `follow_up_after_attack`; then `begin_combat_arc` unchanged.
4. **Hexdemo:** Move `follow_up_after_attack` body into `CombatOutcome` builder in `combat_outcome.py` or `combat_transitions.py`; delete `AttackHook.AFTER_ATTACK_APPLIED` from author path when adapter is sole caller.
5. **Deprecate** `AttackHook.AFTER_ATTACK_APPLIED` in docs; remove from `validate_title_contract` requirements.

#### Author migration (hexdemo)

| Before | After |
|--------|-------|
| `resolve_attack` → `AttackResolution` | `resolve_attack` → `CombatOutcome` (includes effects + bucket patch) |
| `after_attack_applied` → `ApplyBucketPatch` list | *(removed — engine applies `CombatOutcome.patch`)* |
| Arc guards read bucket | Unchanged; bucket shape stable via `session_state` helpers |

#### Tests

`test_combat_transitions`, `test_combat_arc_runner_2b`–`2d`, `test_combat_hexdemo`; new unit tests on `CombatOutcome` → state actions parity with current `follow_up_after_attack`.

---

### Phase D — `Attack` as an arc transition

**Status:** done.

**Goal:** Single FSM for routine combat: `Attack` RPC goes through `submit_event` on the routine combat segment; resolution + classify are one declared transition chain.

#### Sub-steps

1. **Pattern:** `authoring.patterns.combat.build_combat_phase_arc` or extend routine combat arc with `Attack` on + transition to overlay cleanup arc (or inline cleanup subgraph).
2. **Engine:** `execute_authority_attack_request` shrinks to: normalize wire → `submit_event(..., "Attack", ...)` on active routine/combat cursor; runner effect calls title `resolve` and applies `CombatOutcome`.
3. **Remove** imperative `begin_combat_arc` call from attack pipeline; classify becomes the next automatic segment(s) in the same or overlay arc.
4. **Hexdemo:** Wire routine `combat` segment `allowed_actions` to include `Attack`; bind resolve effect to existing rules module.
5. Update `AUTHORITY_ATTACK_PIPELINE` enum to reflect arc-driven steps or retire the module in favor of arc runner docs.

#### Risks / notes

- RNG / `Attack` state action ordering must remain undo-safe and replay-identical.
- Auto-advance-after-attack runs after arc rests on owned segment or completes overlay.

#### Tests

Full combat integration suite + replay/undo tests if present.

---

### Phase E — Movement author interface (same pattern)

**Status:** done.

**Goal:** One `MovementRulesBinding`; engine owns stepwise payload bridge until movement arc is fully runner-driven.

#### Sub-steps

1. Document target: movement hooks = preview + policy; stepwise open/continue = engine bridge calling binding methods.
2. Introduce `MovementOutcome` or step descriptors for retreat path finalize (optional).
3. Consolidate hexdemo movement hook slices into `movement_rules.py` + thin hooks.
4. Align with [`COMPOSABLE_ARCS_PLAN.md` § Phase 3](COMPOSABLE_ARCS_PLAN.md) remaining hybrid notes (retire `ResolvePassMovementInterrupt` fallback when runner always accepts).

#### Tests

`test_movement_sequence`, `test_retreat_path`, `test_movement_arc_runner_3b`.

---

### Phase F — Template pack and authoring scaffold

**Status:** done.

**Goal:** New titles copy one combat module, not hexdemo’s split layout.

#### Sub-steps

1. **`games/template/`:** Add stub `combat_arc.py` with `CombatRulesBinding` implementing no-op / minimal resolve; `COMBAT_ARC` optional until `session_state_key` + combat schedule.
2. **`authoring.patterns.combat`:** Export `combat_rules_binding_to_arc_spec(binding, gates)` helper.
3. **`TITLE_AUTHORING.md`:** “Minimal combat title” checklist (registry + binding + segment registry + presentation row per `ui_mode`).
4. **`validate_title_contract`:** When `session_state_key` + combat schedule, require binding implements required methods (structural check or protocol).

---

## Success criteria (met)

- A new title author can implement combat by filling **one binding class** and a **segment registry** without reading `authority_attack.py` or bucket handoff timing.
- `AttackHook` author surface is **validate, resolve, combat_outcome_after_applied, preview, auto-advance** only; cleanup slots removed from engine and hexdemo.
- Hexdemo matches the three-layer layout; `hooks/attack.py` and `hooks/arcs.py` are thin.
- Author docs steer away from raw `combat_gate` and bucket key strings; `session_state` helpers are the API.
- Combat/movement integration tests green (690+ as of last full run).

---

## Out of scope

- Mid-session pack switching.
- Full [`RULE_COMPOSITION.md`](RULE_COMPOSITION.md) declarative rule DSL (this plan uses Python bindings; composition library may plug in later).
- Client-side authority or draft FSM changes (presentation registry work continues in [`SKINNING_AFFORDANCES_PLAN.md`](../SKINNING_AFFORDANCES_PLAN.md)).
- Rewriting CRT / hexdemo rules content (only how they are wired).

---

## Suggested implementation order

| Order | Phase | Rationale |
|-------|-------|-----------|
| 1 | A | Low risk; immediate clarity |
| 2 | B | Small engine change; removes pack import of `arc_segment` |
| 3 | C | Biggest author win without arc graph surgery |
| 4 | F | Template + docs so new packs do not copy old shape |
| 5 | D | Structural; depends on C stabilizing `CombatOutcome` |
| 6 | E | Parallel track after combat interface settles |

---

## Doc touchpoints (per phase)

| Document | Updates |
|----------|---------|
| [`TITLE_AUTHORING.md`](../TITLE_AUTHORING.md) | Author checklist, combat API table, link to this plan |
| [`PACK_HOOK_CONTRACTS.md`](../PACK_HOOK_CONTRACTS.md) | Deprecate cleanup attack hooks; document `CombatOutcome` when added |
| [`COMPOSABLE_ARCS_PLAN.md`](COMPOSABLE_ARCS_PLAN.md) | Note attack migration track (Phase D of this plan) |
| [`games/hexdemo/hooks/README.md`](../../games/hexdemo/hooks/README.md) | Single combat binding diagram |
| [`engine_game_boundary_matrix.md`](../engine_game_boundary_matrix.md) | Attack resolution row → arc transition when Phase D lands |

---

## Reference: hexdemo combat layout (implemented)

| Piece | Module | Notes |
|-------|--------|-------|
| CRT / resolve | `combat_rules.py` | `BINDING.resolve_attack`; `hooks/attack.py` adapter only |
| Bucket after attack | `combat_outcome.py` | `CombatOutcome`; engine applies via arc `attack` effect |
| Arc spec | `combat_arc.py` | `combat_rules_binding_to_arc_spec(BINDING, …)` |
| Classify / gates | `combat_rules.BINDING` | Guards/effects; `attack_arc_effect` for `Attack` segment |
| Retreat/advance/disrupt mutations | `combat_actions.py` | Invoked from binding methods |
| Gate constants / phase clear | `combat_transitions.py` | No post-attack handoff helpers |
| Segment deny in validate | — | Engine `segment_denies_action_for_faction` before validate |
| UI / dock | `presentation/`, `hooks/turn_action_dock.py`, `combat_gate_panel_actions` | `current_segment` drives End Phase; cleanup gate buttons from title helper |
