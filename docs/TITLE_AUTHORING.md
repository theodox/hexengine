# Title authoring guide

**Start here** if you are building or extending a game pack (title) on hexengine. This page gives **high-level summaries** and **API entry points**; deep wire schemas and client behavior live in linked contract docs.

**Reference pack:** [`games/hexdemo/`](../games/hexdemo/) — copy patterns from code when docs and implementation disagree; prefer updating this guide when behavior changes.

---

## What you are building

A **title pack** is a self-contained game: scenario TOML, `resources/`, Python under `games/<pack_id>/`, and `hexengine_pack.toml`. The **server is authoritative** for legality and state; the **browser client** renders wire payloads and sends `action_request`. Your pack supplies **policy** (rules) and **presentation** (copy, HTML, which buttons exist) through **hooks** the engine calls at known times.

| Layer | You own | Engine owns |
|-------|---------|-------------|
| Match rules | `GameDefinition`, hooks, rules modules | Turn schedule plumbing, action dispatch arcs |
| Scenario | `scenarios/*/scenario.toml`, placements | Loader schema, initial `GameState` |
| Player UX | Messages, dock, previews, templates, CSS | DOM hosts, RPC routing, merge/render |
| Trust | Same process as server today — treat pack code as trusted | See [`PACK_TRUST_MODEL.md`](PACK_TRUST_MODEL.md) |

---

## Reading order

| Step | Doc | Why |
|------|-----|-----|
| 1 | This page | Map of concepts and APIs |
| 2 | [`games/hexdemo/README.md`](../games/hexdemo/README.md) | Pack layout, PYTHONPATH, `game_config` |
| 3 | [`games/hexdemo/hooks/README.md`](../games/hexdemo/hooks/README.md) | Rules vs hooks, three wiring paths |
| 4 | [`TURN_ACTION_DOCK_CONTRACT.md`](TURN_ACTION_DOCK_CONTRACT.md) | Player primitives + three wire lanes |
| 5 | [`PACK_HOOK_CONTRACTS.md`](PACK_HOOK_CONTRACTS.md) | Wire field tables + hook inventory |
| 6 | [`SKINNING_CLIENT_INVENTORY.md`](SKINNING_CLIENT_INVENTORY.md) | Which client module does what |
| 7 | [`engine_game_boundary_matrix.md`](engine_game_boundary_matrix.md) | Server vs title per domain |
| 8 | [`TITLE_LOAD_HOOKS.md`](TITLE_LOAD_HOOKS.md) | Splash / setup manifest hooks |

**Planning only (not API):** [`SKINNING_AFFORDANCES_PLAN.md`](SKINNING_AFFORDANCES_PLAN.md) (roadmap/status), [`RULE_COMPOSITION.md`](RULE_COMPOSITION.md) (future rule catalog).

---

## High-level: player interaction model

Players never “click HTML to commit.” They use three **wire lanes** mapped to four **primitives**:

```
┌─────────────────────────────────────────────────────────────┐
│  INFORM — interaction_messages, ui_popup, dock headline/html │
├─────────────────────────────────────────────────────────────┤
│  DECIDE — interaction_panels (turn action dock on #user-controls)  │
├─────────────────────────────────────────────────────────────┤
│  SELECT — map_selection_preview (click-confirm) OR drag preview│
└─────────────────────────────────────────────────────────────┘
```

| Primitive | Meaning | Primary API |
|-----------|---------|-------------|
| **INFORM** | Tell; no commit | `UIHook` message / popup / overlay hooks |
| **SELECT** | Build a draft; server validates | `map_selection_preview_*` or `unit_preview` / `marker_preview` |
| **DECIDE** | Discrete commit | Dock `actions[]` → `action_request` |
| **SEQUENCE** | Ordered steps of the above | Title `dock_arc` + preview `status_text` + client draft skin (v1) |

**Authoring rules**

- Do not put `onclick` or forms in banner/dock `html`.
- Do not read `GameState.extension` on the client for buttons or legality.
- Use preview RPCs for legal hexes (drag and map-selection), not client-side reachability.

Full primitive catalog and path-draft shapes: [`TURN_ACTION_DOCK_CONTRACT.md` § Player interaction primitives](TURN_ACTION_DOCK_CONTRACT.md#player-interaction-primitives).

---

## High-level: three ways title code is wired

| Path | When | Declare | Example (hexdemo) |
|------|------|---------|-------------------|
| **`TitleHooks`** | Every in-match RPC / state update | `@bind_title_hook` in `hooks/*.py`, `build_hooks()` | `movement.py`, `turn_action_dock.py` |
| **Manifest title-load** | Browser connect / server boot | `[hooks.title_load]` in `hexengine_pack.toml` | `hooks/title_load.py` |
| **Turn schedule** | Phase entry | `GameDefinition.after_phase_transition` | `hooks/turn_schedule.py` |

**Rules vs hooks:** put reusable `GameState` policy in pack-root modules (`combat.py`, `movement_rules.py`, …); keep `hooks/*.py` thin adapters. See [`games/hexdemo/hooks/README.md`](../games/hexdemo/hooks/README.md).

---

## API: pack manifest and discovery

| Item | Location | Notes |
|------|----------|-------|
| `hexengine_pack.toml` | Pack root | `[python].entry_*`, `[hooks.title_load]`, pack id |
| `load_game_definition` | `engine_entry.py` | Required for authoritative server |
| Scenario | `scenarios/<id>/scenario.toml` | Units, map, markers — schema in `hexengine.scenarios` |
| `GameData` | `resources/game_data.toml` | `shell_ui`, styles, extension key |
| PYTHONPATH | `games/` directory | `import hexdemo` (or your pack id) |

Server prepends `games/` when loading a scenario path; see hexdemo README for local dev exports.

---

## Title bucket and combat transitions (hexdemo pattern)

Match-scoped title state lives in `GameState.extension[<pack_id>]`. Read/write through one module (hexdemo: [`title_state.py`](../games/hexdemo/title_state.py)). Reserved top-level keys prefixed `hexengine_` are engine-only.

Hexdemo **`combat_gate`** values and transitions are documented in [`combat_transitions.py`](../games/hexdemo/combat_transitions.py) (FSM table, constants, `blocks_routine_phase_advance`, dock arcs). New pack combat behavior should start there; hook files stay thin `@bind_title_hook` adapters.

---

## API: `TitleHooks` bundles

Assembled with [`assemble_title_hooks`](../src/hexengine/hooks/wiring.py). Enum markers: [`MovementHook`](../src/hexengine/hooks/movement.py), [`AttackHook`](../src/hexengine/hooks/attack.py), [`UIHook`](../src/hexengine/hooks/ui.py).

| Bundle | Typical responsibilities | Contract / validation |
|--------|-------------------------|---------------------|
| **movement** | Step cost, ZoC, retreat obligations, retreat path preview, **auto-advance after move spend** | Movement arc; retreat preview optional; `AUTO_ADVANCE_PHASE_AFTER_MOVE_SPEND` (catalog default: advance when action pool empty) |
| **attack** | `validate_attack`, `resolve_attack`, attack plan preview, optional **`after_attack_applied`** (follow-up `StateAction`s after `Attack` + effects), **`on_retreat_obligation_cleared`** (optional advance gate after retreat/disrupt), **auto-advance after attack** | **Required** if schedule includes combat (`validate_title_contract`); `AUTO_ADVANCE_PHASE_AFTER_ATTACK` has no catalog default (omit hook = no auto-advance) |
| **ui** | Banners, dock, popups, overlays, combat banners, **block routine phase advance** | `COMBAT_INTERACTION_MESSAGES`, `BLOCKS_ROUTINE_PHASE_ADVANCE` |

Return **`ENGINE_DEFAULT`** from a hook to use engine catalog behavior for that slot.

Hook inventory (signatures, when invoked): [`PACK_HOOK_CONTRACTS.md` § Hook inventory](PACK_HOOK_CONTRACTS.md#hook-inventory-current-surfaces) and [§ UI hook inventory](PACK_HOOK_CONTRACTS.md#ui-hook-inventory).

---

## API: player UX (wire + hooks)

### INFORM — banners and popups

| Wire | Hook(s) | Return shape |
|------|---------|--------------|
| `StateUpdate.interaction_messages` | `PHASE_BANNER_*`, `COMBAT_INSTRUCTION_*`, `ADVANCE_GATE_*`, or full `INTERACTION_MESSAGES` | `list[dict]` rows: `schema`, `kind`, `text`, optional `html`, `dedupe_key`, `ttl_ms`, `css_class` |
| `ui_popup` (inspect unit/marker) | `POPUP_MESSAGE` | `{text?, html?, kind?, ttl_ms?, css_class?}` + server sets `hex` |
| `ui_popup` (map feedback) | **`INFORM_POPUP`** via `inspect` + `target_kind=inform` | Same dict; client `Game.show_inform_popup(inform_kind, reason, hex=…, unit_id=…)` |
| `StateUpdate.map_overlays` | `MAP_OVERLAYS` | `list[dict]` overlay rows |

**Two `ui_popup` paths, one renderer:** unit/marker double-click → `POPUP_MESSAGE`; transient map callouts (e.g. illegal attack hex) → `INFORM_POPUP`. Both arrive as `ui_popup` on the client (`_handle_ui_popup`). Do not call `popup_manager.create_popup` from title/game client code for player-facing copy.

**Inform request:** `InspectRequest` with `target_kind: "inform"`, `target_id: <reason>`, `context: { inform_kind, hex?, unit_id? }`. Hexdemo: [`inform_popups.py`](../games/hexdemo/inform_popups.py), `shell_ui` keys `attack_plan_*`.

**Dev console repeater (optional):** When the dev console is initialized (`#status-line`), `Game.repeat_ui_popup_to_dev_console` (default `True`) mirrors each `ui_popup` plain-text line on the status strip via [`dev_console.repeat_ui_popup_to_status`](../src/hexengine/dev_console.py). This is for debugging only — not a player-facing channel. Do not call `dev_console.set_status` for routine INFORM copy; use the repeater or log lines instead. Server/connection errors may still set status directly.

**HTML ladder (v1):** CSS → `resources/templates/*.html` → `ui_markup.py` → optional `hexengine.ui.display` → full message override. Escape dynamic values. Details: [`PACK_HOOK_CONTRACTS.md` § HTML authoring ladder](PACK_HOOK_CONTRACTS.md#html-authoring-ladder-v1).

### DECIDE — turn action dock

| Wire | Hook | Context |
|------|------|---------|
| `StateUpdate.interaction_panels` | **`TURN_ACTION_DOCK_FOR_VIEWER`** | [`TurnActionDockContext`](../src/hexengine/hooks/ui_turn_action_dock.py) |

**Required** when `GameData.title_state_extension_key` is set (`validate_title_contract`). Commit UI is **`interaction_panels` only** — the flat `primary_actions` wire path is removed. All buttons live on panel `turn_actions` (host `advance`).

Panel / action row schemas: [`TURN_ACTION_DOCK_CONTRACT.md` § Panel wire schema](TURN_ACTION_DOCK_CONTRACT.md#panel-wire-schema-schema-1) and [`PACK_HOOK_CONTRACTS.md` § Action row schema](PACK_HOOK_CONTRACTS.md#action-row-schema-shared).

**Opaque skin key:** `dock_arc` (e.g. `routine`, `retreat_gate`, `attack_ready`) — engine does not interpret step graphs; use for CSS/templates/headlines.

### SELECT — map selection (click → Confirm on dock)

| Request | Response | Feature flag |
|---------|----------|--------------|
| `map_selection_preview_request` | `map_selection_preview` | `turn_rules.client_contract.features` includes `map_selection_previews` when [`bound_map_selection_kinds`](../src/hexengine/hooks/map_selection_registry.py) is non-empty |

**Request:** `kind` ([`InteractionKind`](../src/hexengine/gamedef/interactions.py)), title-defined **`draft`** object.

**Response (authoritative):** `status_text`, `confirm_enabled`, `valid_target_hexes`, `commit_payload`, optional **`panel_actions`** (same schema as dock buttons), kind-specific fields (`legal_next_hexes`, `preview_path_hexes`, …).

| `InteractionKind` | Title hook | Hexdemo module |
|-------------------|------------|----------------|
| `attack_plan` | `AttackHook.ATTACK_PLAN_PREVIEW` | `combat_planning` / `hooks/attack.py` |
| `retreat_path` | `MovementHook.RETREAT_PATH_PREVIEW` | `retreat_path_preview.py` |
| `place_marker` | `UIHook.PLACE_MARKER_PREVIEW` | `place_marker_preview.py`, `hooks/markers.py` |

Registry dispatch: [`map_selection_registry.py`](../src/hexengine/hooks/map_selection_registry.py). Server helper: [`compute_map_selection_preview`](../src/hexengine/server/map_selection.py).

**Ratify flow:** client holds draft (v1) → preview on change → merge `panel_actions` into dock → Confirm via [`client_panel_actions.py`](../src/hexengine/game/arcs/client_panel_actions.py) (`preview_commit`, `local`, or default RPC).

### SELECT — drag (commit on drop)

| Request | Use |
|---------|-----|
| `unit_preview_request` | Move, one-hop retreat |
| `marker_preview_request` | Marker drag relocate |

Feature: `server_drag_previews`. Server: [`compute_unit_drag_preview`](../src/hexengine/server/preview.py) / marker equivalent. **No dock Confirm** — drop sends `action_request`.

### SEQUENCE — multi-step UX (v1)

| Source | Responsibility |
|--------|----------------|
| Server dock hook | Baseline `dock_arc`, gate buttons, `headline`, decorative `html` |
| Preview hook | `status_text`, draft `panel_actions`, `confirm_enabled` |
| Client (hexdemo) | Overrides `attack_draft`, `retreat_path_draft`, `place_marker_draft`; merges headlines; disables `end_phase` during drafts |

Server dock hook **does not receive client draft** in v1. See [`TURN_ACTION_DOCK_CONTRACT.md` § SEQUENCE](TURN_ACTION_DOCK_CONTRACT.md#sequence-and-dock_arc).

### Client-only panel dispatch (engine registry)

Titles emit normal action rows; these matches are handled in the client before RPC:

| Match | Behavior |
|-------|----------|
| `AttackPlanCancel` | Clear attack draft |
| `RetreatPathCancel` / `RetreatPathUndo` | Clear / pop retreat path |
| `id: retreat_path_confirm` | Local confirm using preview `commit_payload` |
| `PlaceMarkerCancel` | Clear place-marker draft |
| `id: place_marker_confirm` | Local confirm → `MoveMarker` |
| `Attack` when preview `confirm_enabled` | `preview_commit` with `commit_payload` |

New special commits may require an engine row in `PANEL_ACTION_ROUTES` until manifest-driven routes exist.

---

## API: declarative data (`GameData` / `shell_ui`)

Loaded from pack `resources/game_data.toml` (and related tables). Use for **labels and coaching copy**, not legality.

| Key area | Examples (hexdemo) |
|----------|-------------------|
| Turn dock | `advance_turn_button_label`, `dock_*_headline`, `dock_gate_panel_hint` |
| Attack plan | `attack_confirm_label`, `attack_pick_target_status`, `attack_planning_phases` |
| Retreat path | `retreat_path_confirm_label`, `retreat_path_pick_hex_status`, `retreat_path_ready_status` |
| Place marker | `place_marker_confirm_label`, `place_marker_pick_hex_status`, … |
| Chrome | `interaction_kind_styles`, hex highlight classes in client title data |

Preview hooks receive `shell_ui` on context objects; dock hook receives it on `TurnActionDockContext`.

---

## Task checklists

### New pack (minimal)

1. Copy layout from hexdemo (or future `games/_template/`).
2. Implement `engine_entry.load_game_definition`, `build_hooks()`, scenario TOML.
3. Bind `TURN_ACTION_DOCK_FOR_VIEWER` if you want title-owned commit UI.
4. Add `hexengine_pack.toml` and verify `validate_title_contract` at server start.
5. Point authors at this guide; run pyright on `games/<pack>/`.

### New INFORM copy

1. Prefer `PHASE_BANNER_TEXT_FOR_VIEWER` + optional HTML hook.
2. Add template under `resources/templates/` + helper in `ui_markup.py`.
3. Add `shell_ui` keys only for strings reused in multiple places.

### New click-confirm map flow (`InteractionKind`)

1. Add kind string to [`InteractionKind`](../src/hexengine/gamedef/interactions.py) (engine).
2. Register server row in [`map_selection_registry.py`](../src/hexengine/hooks/map_selection_registry.py); bind title hook.
3. Implement preview: draft in → legality, `commit_payload`, `panel_actions` out.
4. Register client `_apply_*_preview` + draft gesture mixin (engine/hexdemo today).
5. Add `client_panel_actions` routes if Confirm is not a plain RPC.
6. Add `shell_ui` strings; document draft/response fields in pack README.
7. Update this guide + contract doc when shipped.

### New drag-only flow

1. Reuse movement/marker preview paths; align server validation with drop commit.
2. No `map_selection_preview` row unless you also need Confirm on dock.

---

## Stable vs planned

| Status | Topics |
|--------|--------|
| **Stable (v1)** | Three lanes, dock + `panel_actions` merge, registry kinds `attack_plan` / `retreat_path` / `place_marker`, drag previews, `ENGINE_DEFAULT`, HTML ladder tiers 1–3 |
| **Evolving** | Client-held draft; hexdemo-only SEQUENCE overrides; fault-tolerant title-load |
| **Planned** | `games/_template/`, stricter manifest validation, server draft on dock context, composable rule catalog ([`RULE_COMPOSITION.md`](RULE_COMPOSITION.md)) |

---

## Maintenance

When you change player UX or hook contracts:

1. Update the **authoritative** contract ([`TURN_ACTION_DOCK_CONTRACT.md`](TURN_ACTION_DOCK_CONTRACT.md), [`PACK_HOOK_CONTRACTS.md`](PACK_HOOK_CONTRACTS.md)) if wire or hook inventory changes.
2. Update **this guide** high-level tables and checklists if author workflow changes.
3. Update [`SKINNING_AFFORDANCES_PLAN.md`](SKINNING_AFFORDANCES_PLAN.md) shipped/status sections.
4. Update [`SKINNING_CLIENT_INVENTORY.md`](SKINNING_CLIENT_INVENTORY.md) if client modules move.
5. Keep [`games/hexdemo/`](../games/hexdemo/) reference code in sync.

---

## Related docs (full index)

| Doc | Audience |
|-----|----------|
| [`TITLE_AUTHORING.md`](TITLE_AUTHORING.md) | Title authors (this page) |
| [`TURN_ACTION_DOCK_CONTRACT.md`](TURN_ACTION_DOCK_CONTRACT.md) | Wire + primitives (API detail) |
| [`PACK_HOOK_CONTRACTS.md`](PACK_HOOK_CONTRACTS.md) | Wire schemas + hook roadmap |
| [`SKINNING_AFFORDANCES_PLAN.md`](SKINNING_AFFORDANCES_PLAN.md) | Implementation status / roadmap |
| [`SKINNING_CLIENT_INVENTORY.md`](SKINNING_CLIENT_INVENTORY.md) | Client file map |
| [`TITLE_LOAD_HOOKS.md`](TITLE_LOAD_HOOKS.md) | Connect-time hooks |
| [`engine_game_boundary_matrix.md`](engine_game_boundary_matrix.md) | Authority boundaries |
| [`PACK_TRUST_MODEL.md`](PACK_TRUST_MODEL.md) | Server trust / hosted packs |
| [`SERVER_ARCHITECTURE.md`](SERVER_ARCHITECTURE.md) | Server boot and scenarios |
| [`MULTIPLAYER_INTEGRATION.md`](MULTIPLAYER_INTEGRATION.md) | Client/server checklist |
