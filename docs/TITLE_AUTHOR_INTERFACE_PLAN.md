# Title author interface — implementation plan

**Status:** design / planning.

**One-line goal:** Give title authors **one coherent programming interface** for match flow — rules in pack-root modules, a single combat binding into declared arcs, presentation in a segment registry — so authors do not need to learn engine pipelines, bucket handoff protocols, or duplicate hook surfaces.

**Related:** [`COMPOSABLE_ARCS_PLAN.md`](COMPOSABLE_ARCS_PLAN.md) (arc runtime, mostly done for cleanup), [`TITLE_AUTHORING.md`](TITLE_AUTHORING.md) (author hub), [`RULE_COMPOSITION.md`](RULE_COMPOSITION.md) (future reusable rule pieces).

---

## Why

Composable arcs finished **combat cleanup** as a declared FSM (`submit_event` on retreat, advance, disrupt). **Attack resolution** for extension-key titles with a declared combat arc routes through `submit_event` on the arc `attack` segment (`validate` → `resolve` → `Attack` / `ApplyCombatEffects` → `CombatOutcome` → auto `classify`).

That split forces authors to learn two systems for one feature:

| Author concern | Today | Engine knowledge required |
|----------------|-------|---------------------------|
| Dice / CRT / outcome | `AttackHook.resolve_attack` | `AttackResolution`, `effects` shape |
| Post-attack match state | `AttackHook.combat_outcome_after_applied` → `CombatOutcome` | Bucket keys, timing vs `begin_combat_arc` |
| Cleanup gates | `CombatArcEffectsBinding` in `combat_arc.py` | Arc guards reading the same bucket |
| “May I attack?” | `validate_attack` + `arc_segment.segment_denies_action` | Segment projection from pack code |
| Cleanup RPC effects | Arc effects **and** vestigial `AttackHook` cleanup slots | Which path is live |

Hexdemo works, but the reference pack teaches **engine-shaped** integration: `combat_transitions.py` for handoff, `combat_actions.py` for arc effects, `hooks/attack.py` for both resolution and dead-end cleanup hooks.

---

## Target author mental model

Authors work in **three layers** only (aligned with [`TITLE_AUTHORING.md` § Flow vs presentation](TITLE_AUTHORING.md#flow-vs-presentation-authoring-model)):

```
┌─────────────────────────────────────────────────────────┐
│  RULES (pack root)                                       │
│  Pure policy: GameState (+ typed contexts) → outcomes   │
│  e.g. combat.py, title_state.py, movement_rules.py      │
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

**Engine-owned (authors never implement):** `execute_authority_attack_request` wire normalize + `submit_event`, `begin_combat_arc` (cleanup-only entry), `Attack` / `ApplyCombatEffects` assembly helpers, movement payload bridge, wire projection.

---

## Design decisions (resolved for this plan)

1. **Single combat binding type.** One author-facing class (working name `CombatRulesBinding`) implements validate, resolve, and all `CombatArcEffectsBinding` guards/effects. Lives in `games/<pack>/combat_arc.py`; hooks re-export only what the engine still calls by slot name during migration.

2. **`CombatOutcome` title DTO.** Authors return a stable pack-level outcome type (outcome enum, retreat metadata, optional table/CRT fields, bucket patch hints). The engine adapter converts to `AttackResolution` + `StateAction`s during migration, then owns conversion entirely.

3. **Bucket access only via `title_state` helpers.** Documented author API uses typed accessors (`retreat_obligations(state)`, `set_last_combat(...)`, etc.). Raw bucket key strings are not part of the author guide.

4. **Cleanup only on the arc.** `AttackHook` slots `combat_disrupt_instead_of_retreat`, `combat_resolve_advance`, `on_retreat_obligation_cleared`, `is_combat_advance_move` are deprecated and removed from author docs; arc binding is authoritative.

5. **Incremental delivery.** Phases A–C improve the interface without requiring full `Attack` → `submit_event` migration (Phase D). Movement unification (Phase E) follows the same pattern later.

---

## Phases

### Phase A — Clarify and trim the public surface

**Status:** done.

**Goal:** Stop documenting and wiring duplicate cleanup paths; authors see one cleanup owner.

#### Sub-steps (completed)

1. **Marked deprecated** on `AttackHook`: `COMBAT_DISRUPT_INSTEAD_OF_RETREAT`, `COMBAT_RESOLVE_ADVANCE`, `ON_RETREAT_OBLIGATION_CLEARED`, `IS_COMBAT_ADVANCE_MOVE`; documented in [`PACK_HOOK_CONTRACTS.md`](PACK_HOOK_CONTRACTS.md).
2. **Removed dead server paths:** `GameServer._on_retreat_obligation_cleared` / `_maybe_open_combat_advance_after_retreat`; tests use `begin_combat_arc`.
3. **Docs:** [`TITLE_AUTHORING.md`](TITLE_AUTHORING.md), [`PACK_HOOK_CONTRACTS.md`](PACK_HOOK_CONTRACTS.md), [`games/hexdemo/hooks/README.md`](../games/hexdemo/hooks/README.md).
4. **Hexdemo:** Unbound cleanup slots from `hooks/attack.py`; `combat_arc.py` owns cleanup + `ArcSpec.advance_move_detector` for advance `MoveUnit` pre-routing.

#### Tests that must stay green

`test_hooks_contract`, `test_combat_hexdemo`, `test_combat_arc_dispatch`, `test_authoring_combat_pattern`.

---

### Phase B — Engine-owned segment gate before title validate

**Status:** done.

**Goal:** Authors do not import `arc_segment` in `validate_attack`.

#### Sub-steps (completed)

1. `execute_authority_attack_request` calls `segment_denies_action_for_faction` before `validate_attack` when `title_state_extension_key` is set; message `ATTACK_BLOCKED_BY_ACTIVE_SEGMENT_MSG`.
2. Removed segment deny from hexdemo `validate_attack`; `arc_segment.segment_denies_action` delegates to `segment_wire`.
3. Documented in [`PACK_HOOK_CONTRACTS.md`](PACK_HOOK_CONTRACTS.md) and [`TITLE_AUTHORING.md`](TITLE_AUTHORING.md).

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
4. **Hexdemo:** Move `follow_up_after_attack` body into `CombatOutcome` builder in `combat.py` or `combat_transitions.py`; delete `AttackHook.AFTER_ATTACK_APPLIED` from author path when adapter is sole caller.
5. **Deprecate** `AttackHook.AFTER_ATTACK_APPLIED` in docs; remove from `validate_title_contract` requirements.

#### Author migration (hexdemo)

| Before | After |
|--------|-------|
| `resolve_attack` → `AttackResolution` | `resolve_attack` → `CombatOutcome` (includes effects + bucket patch) |
| `after_attack_applied` → `PatchTitleBucket` list | *(removed — engine applies from outcome)* |
| Arc guards read bucket | Unchanged; bucket shape stable via `title_state` helpers |

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

**Status:** not started.

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

**Status:** not started.

**Goal:** New titles copy one combat module, not hexdemo’s split layout.

#### Sub-steps

1. **`games/template/`:** Add stub `combat_arc.py` with `CombatRulesBinding` implementing no-op / minimal resolve; `COMBAT_ARC` optional until extension key + combat schedule.
2. **`authoring.patterns.combat`:** Export `combat_rules_binding_to_arc_spec(binding, gates)` helper.
3. **`TITLE_AUTHORING.md`:** “Minimal combat title” checklist (registry + binding + segment registry + presentation row per kind).
4. **`validate_title_contract`:** When extension key + combat schedule, require binding implements required methods (structural check or protocol).

---

## Success criteria

- A new title author can implement combat by filling **one binding class** and a **segment registry** without reading `authority_attack.py`, `authority_combat_cleanup.py`, or bucket handoff timing.
- `AttackHook` author surface is **validate, resolve, preview, auto-advance** (optional); no cleanup slots in docs or hexdemo.
- Hexdemo reference pack matches the three-layer layout; `hooks/attack.py` is thin.
- No author documentation of raw `combat_gate` or bucket key strings; `title_state` helpers are the API.
- All existing combat/movement integration tests green after each phase.

---

## Out of scope

- Mid-session pack switching.
- Full [`RULE_COMPOSITION.md`](RULE_COMPOSITION.md) declarative rule DSL (this plan uses Python bindings; composition library may plug in later).
- Client-side authority or draft FSM changes (presentation registry work continues in [`SKINNING_AFFORDANCES_PLAN.md`](SKINNING_AFFORDANCES_PLAN.md)).
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
| [`TITLE_AUTHORING.md`](TITLE_AUTHORING.md) | Author checklist, combat API table, link to this plan |
| [`PACK_HOOK_CONTRACTS.md`](PACK_HOOK_CONTRACTS.md) | Deprecate cleanup attack hooks; document `CombatOutcome` when added |
| [`COMPOSABLE_ARCS_PLAN.md`](COMPOSABLE_ARCS_PLAN.md) | Note attack migration track (Phase D of this plan) |
| [`games/hexdemo/hooks/README.md`](../games/hexdemo/hooks/README.md) | Single combat binding diagram |
| [`engine_game_boundary_matrix.md`](engine_game_boundary_matrix.md) | Attack resolution row → arc transition when Phase D lands |

---

## Reference: current vs target (hexdemo combat)

| Piece | Current module | Target owner |
|-------|----------------|--------------|
| CRT / resolve | `hooks/attack.py` | `combat.py` → binding.resolve |
| Bucket after attack | `combat_outcome.build_combat_outcome_after_applied` | `CombatOutcome` (engine applies) |
| Classify / gates | `combat_arc.py` effects | Same binding (guards/effects) |
| Retreat/advance/disrupt mutations | `combat_actions.py` | Same binding (effect methods) |
| Segment deny in validate | `arc_segment` in validate | Engine pre-check |
| UI / dock | `presentation/`, `turn_action_dock.py` | Unchanged |
