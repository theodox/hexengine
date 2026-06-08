# Engine boundary 2 — implementation plan

> **Historical — boundary-2 branch.** Current author interface: [`TITLE_AUTHOR_INTERFACE_PLAN.md`](TITLE_AUTHOR_INTERFACE_PLAN.md)
> (implemented) and [`TITLE_AUTHORING.md`](TITLE_AUTHORING.md). Arc runtime: [`COMPOSABLE_ARCS_PLAN.md`](COMPOSABLE_ARCS_PLAN.md).
> Removed APIs referenced below (`BLOCKS_ROUTINE_PHASE_ADVANCE`, `follow_up_after_attack`,
> `AttackHook.AFTER_ATTACK_APPLIED`, attack cleanup hook slots,
> `blocks_routine_phase_advance`, `dock_arc_hint`, `GATE_RETREAT` / `GATE_ADVANCE` aliases,
> `DOCK_ARC_*` UI tokens) are **not** part of the current hexdemo pack. Legality and End Phase
> blocking use `current_segment.allowed_actions` via
> [`segment_blocks_routine_phase_advance`](../src/hexengine/arcs/segment_wire.py); hexdemo
> delegates through [`arc_segment.py`](../games/hexdemo/arc_segment.py).

Branch: `engine_boundary_2` (from skinning squash on `main`).

**Goal:** Clarify engine vs title ownership for **match state**, **combat transitions**, and **phase advance** — without a monolithic engine combat state machine and without requiring mid-session title switches.

**Already shipped on this branch**

- Squash-merge skinning (INFORM / SELECT / DECIDE, mandatory turn action dock, `#user-controls`).
- Commit `move phase end to game code`: `MovementHook.AUTO_ADVANCE_PHASE_AFTER_MOVE_SPEND`, `_maybe_auto_advance_phase`, hexdemo gate policy.

**Companion docs**

| Doc | Role |
|-----|------|
| [`TITLE_AUTHORING.md`](TITLE_AUTHORING.md) | Author hub |
| [`engine_game_boundary_matrix.md`](engine_game_boundary_matrix.md) | Per-dimension ownership (update as phases land) |
| [`TURN_ACTION_DOCK_CONTRACT.md`](TURN_ACTION_DOCK_CONTRACT.md) | Player primitives |
| [`PACK_HOOK_CONTRACTS.md`](PACK_HOOK_CONTRACTS.md) | Wire + hooks |

---

## Principles

1. **One match = one title.** `GameData.session_state_key` is fixed for the server process; do not design for hot-swapping packs mid-session.
2. **Engine = mechanism.** Undoable `StateAction`s, RPC arcs, schedule math (`get_next_phase`), primitive transports.
3. **Title = policy + graph.** When to set gates, obligations, auto-advance, INFORM copy, segment `ui_mode` / `presentation_id`, and `InteractionKind` previews.
4. **No engine combat phase enum.** Titles may use enums in pack code; engine must not require a universal graph.
5. **Client does not read extension for legality.** Wire + hooks only for commit paths (existing skinning rule).

---

## Current pain (baseline)

| Area | Today | Strain |
|------|--------|--------|
| Match state | Was `extension["hexdemo"]` + `hexengine_*` | Now `session_state` / `engine_state` / `session_state_key`; `BucketPatch` + `ApplyBucketPatch` for writes |
| Combat FSM | Implicit in bucket keys: `combat_gate`, `last_combat`, `retreat_obligations`, `advance`, `attacks_this_phase` | Engine + hexdemo + `game_server` INFORM all parse same strings |
| Phase advance | Title hooks for move/attack; explicit `NextPhase` on dock | Improved; gate checks duplicated (dock, movement auto-advance) |
| Engine actions | ~~`OpenCombatAdvance`, `ResolveCombatAdvance`, `ResolveDisruptInsteadOfRetreat`, `ClearTitleCombatExtension`~~ removed | Combat cleanup + phase-scoped key clearing now title-owned (`games/hexdemo/combat_actions.py`, `combat_transitions.clear_combat_state_actions`); engine actions hold no hexdemo key literals |

---

## Phase A — Session-state ergonomics (no wire break) ✅

**Objective:** Single place to resolve the title key; less `extension.get("hexdemo")` noise.

**Status:** Implemented on `engine_boundary_2` (helpers, `games/hexdemo/session_state.py`, hexdemo refactors, `GameServer._engine_read_session_state`, tests in `test_engine_session_state.py`).

### A.1 Match-scoped key on server

- Add `MatchContext` (or fields on `GameServer`): `engine_session_state_key: str | None` set once from `game_data.session_state_key`.
- Replace repeated `_engine_session_state_key()` lookups in arcs with `self.match.engine_session_state_key` where it simplifies (keep one method as facade).

### A.2 Engine helpers (`hexengine.state.engine_session_state`)

| API | Behavior |
|-----|----------|
| `engine_read_session_state(state, key) -> dict` | `state.session_state` when `key == state.session_state_key`, else `{}` |
| `engine_write_session_state(state, key, bucket: dict) -> GameState` | Shallow replace session-state dict |
| `ApplyBucketPatch` + `BucketPatch` | Generic undoable patch (replaces ad-hoc copies in actions) |

Reserved top-level keys: prefix `hexengine_` (e.g. `hexengine_movement_arc`) — engine only.

### A.3 Hexdemo consolidation ✅

- `games/hexdemo/session_state.py` — all reads of `PACK_SESSION_STATE_KEY` (retreat helpers merged from removed `combat.py`).
- Hooks stay thin: delegate to `session_state` / `combat_transitions` / `combat_rules`.

### A.4 Client

- Cache title key on connect from `turn_rules` (already mostly true).
- Audit `client_combat.py` extension reads — display-only or remove; no legality.

**Exit criteria:** No new `state.extension.get(PACK_…)` outside `session_state.py` in hexdemo; server uses `engine_read_session_state()` in new/edited code paths.

**Tests:** Existing combat/movement tests green; `test_engine_session_state.py` covers read/write and `ApplyBucketPatch` revert.

---

## Phase B — Decouple combat INFORM / gate reads from `game_server` ✅

**Objective:** Stop encoding hexdemo combat narrative in `GameServer._interaction_messages_for_player_id`.

**Status (shipped):** `UIHook.COMBAT_INTERACTION_MESSAGES`, `ui_combat_messages.py`, hexdemo `combat_transitions` / `presentation/interaction_messages.py` (via `hooks/ui.py`), `NextPhase` guard.

**Superseded:** `UIHook.BLOCKS_ROUTINE_PHASE_ADVANCE` and `blocks_routine_phase_advance` — replaced by declared arc segments and [`segment_blocks_routine_phase_advance`](../src/hexengine/arcs/segment_wire.py). Hexdemo auto-advance uses [`arc_segment.phase_advance_blocked`](../games/hexdemo/arc_segment.py).

### B.1 Hook: combat / phase blocking (unified policy)

| Hook | Bundle | Purpose |
|------|--------|---------|
| *(removed)* `blocks_routine_phase_advance` | was `UIHook` | **Superseded** — active segment `allowed_actions` |
| `combat_interaction_messages(ctx) -> list[InteractionMessage] \| ENGINE_DEFAULT` | `UIHook` | Per-viewer INFORM rows from segment `ui_mode` + partial combat hooks |

- Phase advance blocking and End Phase dock enablement: `current_segment` + `segment_blocks_routine_phase_advance`.
- Auto-advance after move/attack: title attack/movement hooks call `arc_segment.phase_advance_blocked` (hexdemo).
- Move `game_server` combat banner branches behind `combat_interaction_messages` (hexdemo implements; catalog default: empty or minimal).

### B.2 Document gate strings as title-owned

- In [`TITLE_AUTHORING.md`](TITLE_AUTHORING.md): `combat_gate` values are **pack conventions**, not engine enums.
- Engine catalog default dock adds End Phase only; combat gate dock rows are title helpers (`combat_gate_panel_actions`), not engine segment wire.

**Exit criteria:** Banner path has no direct reads of `last_combat` / `combat_gate` except via hook dispatch (`COMBAT_INTERACTION_MESSAGES` / catalog default). `combat_event` broadcast may still read `last_combat`.

**Tests:** `test_combat_hexdemo` message kinds unchanged; hook contract tests for new UI/Movement enum members.

---

## Phase C — Combat transition writes (hook follow-ups) ✅

**Objective:** Titles return follow-up state changes; engine runs arcs in fixed order.

**Status:** C.1 hook + authority step; C.2 `ClearUnitRetreatObligation` via `ApplyBucketPatch`, disrupt gate upgrade in hexdemo `follow_up_after_attack` (removed from `ApplyCombatEffects`); C.3 `ON_RETREAT_OBLIGATION_CLEARED` + unified server dispatch (retreat fulfillment + disrupt path). `Attack.apply` session writes remain engine-side until a later migration.

### C.1 Hook: `after_attack_applied(ctx) -> list[StateAction] | ENGINE_DEFAULT` ✅

Context: `GameState`, `AttackResolution`, `session_state_key`, attacker/defender ids, player faction.

- `authority_attack` after `Attack` + `ApplyCombatEffects`:
  1. Existing resolve path
  2. Call hook; execute returned actions
  3. Broadcast combat events
  4. `attack.auto_advance` + `_maybe_auto_advance_phase` (unchanged order)

- Hexdemo: move obligation / `last_combat` / `attacks_this_phase` / `combat_gate` writes from resolve path into this list where possible (incremental).

### C.2 Generalize cleanup actions ✅ (incremental)

- Prefer `ApplyBucketPatch` over ad-hoc session-state copies (`ClearUnitRetreatObligation` migrated).
- Done: `OpenCombatAdvance` / `ResolveCombatAdvance` / `ResolveDisruptInsteadOfRetreat` extracted to pack-local `games/hexdemo/combat_actions.py`; engine cleanup arc dispatches title hooks (`COMBAT_RESOLVE_ADVANCE`, `COMBAT_DISRUPT_INSTEAD_OF_RETREAT`, `ON_RETREAT_OBLIGATION_CLEARED`).

### C.3 Optional: `on_retreat_obligation_cleared(ctx)` ✅

- `RetreatObligationClearedContext`; `GameServer._on_retreat_obligation_cleared` (legacy `_maybe_open_combat_advance_after_retreat` alias).
- Call sites: retreat stack fulfillment, `CombatDisruptInsteadOfRetreat` after obligations clear.
- Hexdemo binds `combat_transitions.on_retreat_obligation_cleared` (delegates to engine default).

**Exit criteria:** No new inline `hx["combat_gate"] = …` in server arcs except inside generic patch actions driven by title.

**Tests:** Retreat/advance integration tests; undo/revert for patch actions.

---

## Phase D — Hexdemo explicit combat transitions (pack only) ✅

**Objective:** One readable FSM doc in code for authors; engine stays ignorant.

**Status:** `combat_transitions.py` FSM table, gate constants, `attack_planning_blocked_reason`, `follow_up_after_attack`; `combat_policy.py` removed; presentation skin via [`segment_ui.py`](../games/hexdemo/segment_ui.py) + [`hooks/turn_action_dock.py`](../games/hexdemo/hooks/turn_action_dock.py). Removed: `blocks_routine_phase_advance`, `dock_arc_hint`, `DOCK_ARC_*`, `GATE_RETREAT` / `GATE_ADVANCE` aliases.

### D.1 `games/hexdemo/combat_transitions.py` ✅

| Export | Role |
|--------|------|
| Gate constants | `GATE_AWAITING_RETREAT`, `GATE_AWAITING_RETREAT_OR_DISRUPT`, `GATE_AWAITING_ADVANCE` (match segment `ui_mode`) |
| `GATES_BLOCKING_ROUTINE` | Declaration parity / local guards |
| `attack_planning_blocked_reason` | Attack plan preview + validation messaging |
| `follow_up_after_attack` | `AttackHook.AFTER_ATTACK_APPLIED` bucket patches |
| `clear_combat_state_actions` | Phase-scoped key clear on `NextPhase` |
Phase advance blocking: [`arc_segment.phase_advance_blocked`](../games/hexdemo/arc_segment.py), not exports from this module.

Dock skin: [`segment_ui.resolve_presentation_id`](../games/hexdemo/segment_ui.py) + `UIHook.ENRICH_CURRENT_SEGMENT`, not `dock_arc_hint`.

Include a short state table in module docstring (routine ↔ retreat gate ↔ advance gate ↔ routine).

### D.2 Wire adapters in `hooks/` ✅

- `@bind_title_hook` wrappers only; no business logic in hook files.

**Exit criteria:** New combat behavior starts in `combat_transitions.py` + `session_state.py`, not scattered string checks. (Engine `Attack.apply` gate writes remain until a later migration.)

---

## Phase E — Optional `GameState` split (wire migration) ✅

**Status:** `GameState.session_state`, `engine_state`, `session_state_key` only (no combined `extension` map on state or wire). Helpers in `engine_session_state.py`; server sets `session_state_key` from `GameData` on match start.

```text
GameState
  board, turn, rng_log
  session_state: dict[str, Any]      # was extension[pack_id]
  engine_state: dict[str, Any]   # movement arc, future engine ephemeral
  session_state_key: str | None
```

- Snapshot / `game_state_to_wire_dict` merge for v1 compat or bump wire schema.
- Migration helper: `extension` ↔ split on load.

---

## Phase F — Docs and matrix maintenance ✅

| Item | Action |
|------|--------|
| [`engine_game_boundary_matrix.md`](engine_game_boundary_matrix.md) | Rows #9–11 + boundary-2 quick reference |
| [`TITLE_AUTHORING.md`](TITLE_AUTHORING.md) | Session state / `BucketPatch` / combat transitions section |
| [`PACK_HOOK_CONTRACTS.md`](PACK_HOOK_CONTRACTS.md) | `COMBAT_INTERACTION_MESSAGES`, segment presentation (P3–P5), attack follow-up hooks |
| This plan | Phases A–F marked complete on `engine_boundary_2` |

---

## Suggested PR order

```text
PR1  Phase A     engine_session_state helpers + hexdemo session_state.py
PR2  Phase B     combat_interaction_messages (+ later: segment-based phase blocking)
PR3  Phase C.1   after_attack_applied + hexdemo adapter
PR4  Phase C.2   patch_engine_read_session_state_action migration (incremental)
PR5  Phase D     combat_transitions.py table + delegate hooks
PR6  Phase E     (optional) GameState.session_state / engine_state split
```

Each PR should keep pytest green (`test_combat_hexdemo`, `test_hooks_contract`, `test_retreat_path`, `test_turn_action_dock`, `test_network`).

---

## Out of scope (this track)

- Mid-session title / pack switching
- Engine-wide `CombatPhase` enum
- Client-side combat FSM
- Full removal of hexdemo-shaped `OpenCombatAdvance` without a second title reference
- RNG wired into combat resolve
- `LOAD_SNAPSHOT` resetting markers/graphics (separate matrix follow-up)

---

## Open decisions

| Question | Resolution |
|----------|------------|
| `blocks_routine_phase_advance` on `UIHook` vs `MovementHook`? | **Resolved — removed.** Use `current_segment` + `segment_blocks_routine_phase_advance`; hexdemo via `arc_segment`. |
| Clear whole session state on `NextPhase` vs named keys only? | **Named keys** (`PHASE_SCOPED_COMBAT_KEYS` in `combat_transitions.py`). |
| Require `after_attack_applied` when `session_state_key` set? | **No** — optional hook; hexdemo binds `follow_up_after_attack`. |

---

## Success criteria (track complete)

- Title combat policy readable in `games/hexdemo/combat_transitions.py` + `session_state.py`.
- `game_server` does not interpret hexdemo `combat_gate` / `last_combat` for INFORM banners (hook path only).
- Phase advance blocking reads active arc segment; post-move auto-advance uses `arc_segment.phase_advance_blocked` (hexdemo).
- Extension access for titles goes through helpers; engine keys stay prefixed `hexengine_`.
- [`engine_game_boundary_matrix.md`](engine_game_boundary_matrix.md) reflects post-skinning + this track.
