# Title authoring guide

**Combat / movement author interface (done):** [`TITLE_AUTHOR_INTERFACE_PLAN.md`](TITLE_AUTHOR_INTERFACE_PLAN.md) — Phases A–F implemented; hexdemo uses one `CombatRulesBinding` + `movement_rules.py`; see [§ Combat and movement (hexdemo)](#combat-and-movement-hexdemo).

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
| **SEQUENCE** | Ordered steps of the above | Title `presentation_id` + preview `status_text` + client draft skin |

**Authoring rules**

- Do not put `onclick` or forms in banner/dock `html`.
- Do not read `GameState.title_state` / extension-shaped fields on the client for buttons or legality.
- Use preview RPCs for legal hexes (drag and map-selection), not client-side reachability.

Full primitive catalog and path-draft shapes: [`TURN_ACTION_DOCK_CONTRACT.md` § Player interaction primitives](TURN_ACTION_DOCK_CONTRACT.md#player-interaction-primitives).

---

## High-level: three ways title code is wired

| Path | When | Declare | Example (hexdemo) |
|------|------|---------|-------------------|
| **`TitleHooks`** | Every in-match RPC / state update | `@bind_title_hook` in `hooks/*.py`, `build_hooks()` | `movement.py`, `turn_action_dock.py` |
| **Manifest title-load** | Browser connect / server boot | `[hooks.title_load]` in `hexengine_pack.toml` | `hooks/title_load.py` |
| **Turn schedule** | Phase entry | `GameDefinition.after_phase_transition` | `game_config.py` → `combat_transitions` |

**Rules vs hooks:** put reusable `GameState` policy in pack-root modules (`title_state.py`, `movement_rules.py`, …); keep `hooks/*.py` thin adapters. See [`games/hexdemo/hooks/README.md`](../games/hexdemo/hooks/README.md).

---

## Flow vs presentation (authoring model)

Design goals for player UX:

| Goal | Practice |
|------|----------|
| **Clear expression** | Declare *match flow* in arcs and a small UI vocabulary; avoid scattered `if presentation_id` / mouse branches. |
| **Easy customization** | Copy, HTML, and CSS live in `shell_ui`, templates, and keyed helpers — swappable without changing legality. |
| **Insulate from wire** | Hooks receive **typed contexts** and return **presentation values**; the engine projects them to `StateUpdate` / `ui_popup`. Do not assemble wire dicts in `games/*`. |

Authors work in **two layers only**:

```
┌─────────────────────────────────────────────────────────┐
│  FLOW (declarative, authoritative)                     │
│  Arc segments: owner, allowed actions, segment kind        │
│  + title registry: primitive, interaction mode, skin id  │
└──────────────────────────┬──────────────────────────────┘
                           │ engine projects (internal)
┌──────────────────────────▼──────────────────────────────┐
│  PRESENTATION (title-owned, swappable)                   │
│  shell_ui + templates + ui_markup + thin hook adapters   │
└─────────────────────────────────────────────────────────┘
```

- **Flow** answers who may act and which RPCs are legal (`current_segment` on the wire is an engine projection of this).
- **Presentation** answers headlines, banners, dock HTML, button labels, and map coaching strings.

Wire field tables live in [`PACK_HOOK_CONTRACTS.md`](PACK_HOOK_CONTRACTS.md) for debugging and client work; treat them as **reference**, not the author API. See [§ Authoring vs wire](PACK_HOOK_CONTRACTS.md#authoring-vs-wire).

---

## Segment presentation registry

**Reference pattern** (hexdemo: [`segment_ui.py`](../games/hexdemo/segment_ui.py); template pack should copy the same shape):

One **registry row per segment UX mode**, aligned with the `kind` string on arc segments. Each row ties flow to presentation without duplicating logic across engine, dock hook, and client.

| Registry field | Author meaning | Engine / client use (internal) |
|----------------|----------------|--------------------------------|
| **`kind`** | Stable id in the declared arc (e.g. `awaiting_retreat`, `routine_combat`) | `current_segment.kind` |
| **`presentation_id`** | Skin key for CSS and templates (e.g. `retreat_gate`, `attack_ready`) | panel `css_class` modifiers and wire `presentation_id` |
| **`primitive`** | INFORM, SELECT, DECIDE, or SEQUENCE | Which wire lane(s) are active |
| **`interaction_mode`** | Optional [`InteractionKind`](../src/hexengine/gamedef/interactions.py) (`attack_plan`, `retreat_path`, `place_marker`, or none) | Map-selection preview + client draft skin |
| **`inform_profile`** | Optional key for default banner / coaching hooks | `COMBAT_INTERACTION_MESSAGES`, phase rows |

**Example (conceptual):**

```python
# games/<pack>/segment_ui.py — one place to read “what UX mode is this?”
SegmentUi(
    kind="awaiting_retreat",
    presentation_id="retreat_gate",
    primitive=Primitive.SELECT,
    interaction_mode="retreat_path",
    inform_profile="retreat_gate",
)
```

Arc declarations use the same `kind` strings. Dock and inform hooks **look up** the row and call pack helpers (`ui_markup`, `shell_ui`); they do not re-derive mode from phase names or bucket strings.

**Presentation customization** (goal b) is keyed by `presentation_id` and `inform_profile`:

| Asset | Edit | Keyed by |
|-------|------|----------|
| Short labels | `game_data.toml` → `shell_ui` | `presentation_id` + action id |
| Dock headline / hint HTML | `ui_markup.py` + `resources/templates/` | `presentation_id` |
| Banners | `presentation/interaction_messages.py` + thin `UIHook` adapters | `segment.kind` (combat/advance gates) and combat outcome |
| Map popups | `presentation/inform.py` via `hooks/ui.inform_popup_for_viewer` | `inform_profile` + `reason` (from `current_segment` when client omits `inform_kind`) |
| CSS | pack `resources/ui.css` | `.…-turn-dock--{presentation_id}` |

**Do not** in pack code: build raw wire dicts for dock panels or inform popups (except tests); read `client.interaction_panels` for legality; branch on `combat_gate` for affordances — use [`arc_segment.py`](../games/hexdemo/arc_segment.py) helpers and `current_segment` via hook context.

**Presentation DTOs (P2):** return `TurnDockPanel`, `InformPopup`, `MapSelectionPreview`, `InteractionMessage`, `MapOverlay`, and `SegmentPresentationPatch` from `hexengine.authoring.present` (`turn_dock_panel`, `panel_action`, `inform_popup`, `map_selection_preview`, `interaction_message`, `map_overlay_glyph`, …). The engine converts them in `hexengine.hooks.internal.ui_wire` before `StateUpdate`, `ui_popup`, or `map_selection_preview` wire messages.

**P3 (done):** `current_segment` on `StateUpdate` carries `presentation_id` and `interaction_mode` (title `enrich_current_segment` hook + engine default). The client turn-dock SEQUENCE skin keys off `interaction_mode`, not separate `*_draft` booleans.

**P4 (done):** INFORM map callouts resolve `inform_profile` from `current_segment` when the client omits `inform_kind` (`hexengine.arcs.inform_wire`). Title copy lives in `presentation/inform.py` keyed by profile + reason; engine `default_inform_popup_for_viewer` uses the same shell key pattern.

**P5 (done):** At server startup, `validate_title_contract` checks every explicit segment `kind` in declared arcs is registered in `PRESENTATION_BY_SEGMENT_KIND` (bind `UIHook.SEGMENT_PRESENTATION_REGISTRY`). Required when `title_state_extension_key` is set.

**Draft locus:** Map SELECT drafts are client-local until commit; preview consults, commit authorizes. See [`TURN_ACTION_DOCK_CONTRACT.md` § Draft locus](TURN_ACTION_DOCK_CONTRACT.md#draft-locus-invariant).

---

## API: pack manifest and discovery

| Item | Location | Notes |
|------|----------|-------|
| `hexengine_pack.toml` | Pack root | `[python].entry_*`, `[hooks.title_load]`, pack id |
| `load_game_definition` | `engine_entry.py` | Required for authoritative server |
| Scenario | `scenarios/<id>/scenario.toml` | Units, map, markers — schema in `hexengine.scenarios` |
| `GameData` | `resources/game_data.toml` | `shell_ui`, styles, extension key, `[client_contract]` client wiring |
| PYTHONPATH | `games/` directory | `import hexdemo` (or your pack id) |

Server prepends `games/` when loading a scenario path; see hexdemo README for local dev exports.

---

## Title bucket and combat (hexdemo pattern)

Match-scoped title state lives in **`GameState.title_state`** (one bucket per match; pack id in **`GameState.title_bucket_key`** from `GameData.title_state_extension_key`). Read/write through one module (hexdemo: [`title_state.py`](../games/hexdemo/title_state.py) — use `bucket()` and typed helpers such as `attacks_this_phase()` rather than scattering raw key strings). Engine ephemeral keys live in **`GameState.engine_state`** and must use the `hexengine_` prefix (see [`title_extension.py`](../src/hexengine/state/title_extension.py)).

Authoritative match state uses **`GameState.title_state`** (title bucket) and **`GameState.engine_state`** (keys prefixed `hexengine_`). Snapshots and `StateUpdate` game_state carry `title_state`, `engine_state`, and `title_bucket_key`. Prefer `title_state.bucket()` / `hexengine.state.title_extension.title_bucket` over reading raw fields when the pack id matters.

### Combat and movement (hexdemo)

| Layer | Module | Role |
|-------|--------|------|
| **Combat binding** | [`combat_rules.py`](../games/hexdemo/combat_rules.py) | `HexdemoCombatRules` / `BINDING`: CRT, validate, `CombatOutcome`, arc guards/effects, `attack_arc_effect` |
| **Outcome builder** | [`combat_outcome.py`](../games/hexdemo/combat_outcome.py) | `build_combat_outcome_after_applied` → bucket patch for classify |
| **Arc spec** | [`combat_arc.py`](../games/hexdemo/combat_arc.py) | `combat_rules_binding_to_arc_spec`; owner resolver; `ArcHook.COMBAT_ARC` |
| **Cleanup mutations** | [`combat_actions.py`](../games/hexdemo/combat_actions.py) | Retreat step, disrupt, advance resolve (called from binding) |
| **Gate kinds / phase clear** | [`combat_transitions.py`](../games/hexdemo/combat_transitions.py) | `COMBAT_ARC_GATE_KINDS`, `clear_combat_state_actions`, attack-planning block copy |
| **Title bucket / retreat reads** | [`title_state.py`](../games/hexdemo/title_state.py) | `bucket()`, retreat obligations, advance offer |
| **Movement policy** | [`movement_rules.py`](../games/hexdemo/movement_rules.py) | Budget, ZoC, step cost, retreat constraints |
| **Hook adapters** | [`hooks/attack.py`](../games/hexdemo/hooks/attack.py), [`hooks/movement.py`](../games/hexdemo/hooks/movement.py) | `@bind_title_hook` only |
| **Segment projection** | [`arc_segment.py`](../games/hexdemo/arc_segment.py) | `phase_advance_blocked`, planning block helpers |

**Attack RPC flow:** engine sets combat arc `attack` segment → `submit_event` → binding applies resolution + `CombatOutcome` → `classify` auto-advances to cleanup gates or completes → **`restore_routine_cursor`** so routine combat segment (and End Phase) return. Legality and dock rows read **`current_segment`**, not bucket gate strings. Legacy **`combat_gate`** is not written; it is cleared on phase advance for old saves.

**Author `AttackHook` surface:** `validate_attack`, `resolve_attack`, `combat_outcome_after_applied`, `attack_plan_preview`, `auto_advance_phase_after_attack` only. No cleanup slots on `AttackHook` (removed).

---

## API: `TitleHooks` bundles

Assembled with [`assemble_title_hooks`](../src/hexengine/hooks/wiring.py). Enum markers: [`MovementHook`](../src/hexengine/hooks/movement.py), [`AttackHook`](../src/hexengine/hooks/attack.py), [`UIHook`](../src/hexengine/hooks/ui.py).

| Bundle | Typical responsibilities | Contract / validation |
|--------|-------------------------|---------------------|
| **movement** | Step cost, ZoC, retreat obligations, retreat path preview, **auto-advance after move spend** | Movement arc; retreat preview optional; `AUTO_ADVANCE_PHASE_AFTER_MOVE_SPEND` (catalog default: advance when action pool empty) |
| **attack** | `validate_attack` (rules only — segment legality is engine-default when extension key is set), `resolve_attack`, attack plan preview, optional **`combat_outcome_after_applied`** (`CombatOutcome` bucket handoff), **auto-advance after attack** | **Required** if schedule includes combat (`validate_title_contract`); `AUTO_ADVANCE_PHASE_AFTER_ATTACK` has no catalog default (omit hook = no auto-advance) |
| **ui** | Banners, dock, popups, overlays, combat banners | `COMBAT_INTERACTION_MESSAGES`, `TURN_ACTION_DOCK_FOR_VIEWER` |
| **arcs** | Turn registry, **combat arc** (`SEG_ATTACK` + cleanup subgraph), optional **combat rules binding** for contract check | `TURN_ARC_REGISTRY`, `COMBAT_ARC` (required); `COMBAT_RULES_BINDING` (hexdemo: validates `BINDING` methods at startup) |

Return **`ENGINE_DEFAULT`** from a hook to use engine catalog behavior for that slot.

Hook inventory (signatures, when invoked): [`PACK_HOOK_CONTRACTS.md` § Hook inventory](PACK_HOOK_CONTRACTS.md#hook-inventory-current-surfaces) and [§ UI hook inventory](PACK_HOOK_CONTRACTS.md#ui-hook-inventory).

---

## API: player UX (hooks; wire is reference)

Hooks are the **author surface**. Return plain dicts today; prefer typed contexts and pack helpers over copying wire schemas from this guide.

| Concern | Author API | Wire (engine only) |
|---------|------------|-------------------|
| Banners / popups | `UIHook` slots in `hooks/ui.py` | `interaction_messages`, `ui_popup` |
| Commit UI | `TURN_ACTION_DOCK_FOR_VIEWER` | `interaction_panels` |
| Map drafts | `*_PREVIEW` hooks, `InteractionKind` | `map_selection_preview` |
| Legality | Arc segments + rules modules | `current_segment`, `action_request` |

Full field tables: [`PACK_HOOK_CONTRACTS.md` § UI affordances](PACK_HOOK_CONTRACTS.md#ui-affordances--wire-schemas-and-hooks-v1).

### INFORM — banners and popups

| Hook(s) | Typical return (author) |
|------|---------|--------------|
| `PHASE_BANNER_*`, `COMBAT_INSTRUCTION_*`, `ADVANCE_GATE_*`, or full `INTERACTION_MESSAGES` | Return `InteractionMessage` via `interaction_message()`; engine serializes in `ui_wire` |
| **`INFORM_POPUP`** | `InformPopup` DTO (`text`, optional `html`, `kind`, `ttl_ms`, `css_class`) — server sets anchor `hex` |
| `MAP_OVERLAYS` | `list[MapOverlay]` via `map_overlay_glyph()` (glyph kind today) |

**One `ui_popup` path:** all `InspectRequest` targets (`unit`, `marker`, `inform`) go through **`INFORM_POPUP`** → `inform_popup_to_wire` → `ui_popup` on the client (`_handle_ui_popup`). Do not call `popup_manager.create_popup` from title/game client code for player-facing copy.

**Inspect requests:** `InspectRequest` with `target_kind` `unit` / `marker` / `inform`. Inform lane uses `target_id` as reason id and `context: { inform_kind?, hex?, unit_id? }`. Hexdemo: [`hooks/ui.py`](../games/hexdemo/hooks/ui.py) + [`presentation/inform.py`](../games/hexdemo/presentation/inform.py) + [`ui_markup.py`](../games/hexdemo/ui_markup.py) for unit inspect; `shell_ui` keys `attack_plan_*`.

**Dev console repeater (optional):** When the dev console is initialized (`#status-line`), `Game.repeat_ui_popup_to_dev_console` (default `True`) mirrors each `ui_popup` plain-text line on the status strip via [`dev_console.repeat_ui_popup_to_status`](../src/hexengine/dev_console.py). This is for debugging only — not a player-facing channel. Do not call `dev_console.set_status` for routine INFORM copy; use the repeater or log lines instead. Server/connection errors may still set status directly.

**HTML ladder (v1):** CSS → `resources/templates/*.html` → `ui_markup.py` → optional `hexengine.ui.display` → full message override. Escape dynamic values. Details: [`PACK_HOOK_CONTRACTS.md` § HTML authoring ladder](PACK_HOOK_CONTRACTS.md#html-authoring-ladder-v1).

### DECIDE — turn action dock

| Hook | Context |
|------|---------|
| **`TURN_ACTION_DOCK_FOR_VIEWER`** | [`TurnActionDockContext`](../src/hexengine/hooks/ui_turn_action_dock.py) — includes `current_segment`, `shell_ui` |

**Required** when `GameData.title_state_extension_key` is set (`validate_title_contract`). Commit buttons are composed from segment `allowed_actions` (gate rows) plus title presentation; wire panel id is conventionally `turn_actions`.

Panel / action wire schemas (reference): [`TURN_ACTION_DOCK_CONTRACT.md` § Panel wire schema](TURN_ACTION_DOCK_CONTRACT.md#panel-wire-schema-schema-1).

**Skin key:** `presentation_id` (e.g. `routine`, `retreat_gate`, `attack_ready`) — opaque to engine; use in CSS, templates, and the [segment presentation registry](#segment-presentation-registry). Draft skins (`attack_draft`, …) are client-only.

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

**Ratify flow:** client holds draft locally → preview on change → merge `panel_actions` into dock → Confirm via [`client_panel_actions.py`](../src/hexengine/game/arcs/client_panel_actions.py) (`preview_commit`, `local`, or default RPC). See [draft locus](TURN_ACTION_DOCK_CONTRACT.md#draft-locus-invariant).

### SELECT — drag (commit on drop)

| Request | Use |
|---------|-----|
| `unit_preview_request` | Move, one-hop retreat |
| `marker_preview_request` | Marker drag relocate |

Feature: `server_drag_previews`. Server: [`compute_unit_drag_preview`](../src/hexengine/server/preview.py) / marker equivalent. **No dock Confirm** — drop sends `action_request`.

### SEQUENCE — multi-step UX

**Player prompts** (scripted events, season cards, acknowledge-then-continue) are prompt sequences: INFORM on the dock (`headline` / `html`) then DECIDE; blocking is a **prompt segment** in the turn arc. See [`TURN_ACTION_DOCK_CONTRACT.md` § Player prompts](TURN_ACTION_DOCK_CONTRACT.md#player-prompts) and [`COMPOSABLE_ARCS_PLAN.md` § Prompt segments](COMPOSABLE_ARCS_PLAN.md#prompt-segments).

| Source | Responsibility |
|--------|----------------|
| Server dock hook | Baseline `presentation_id`, gate buttons, `headline`, decorative `html` |
| Preview hook | `status_text`, draft `panel_actions`, `confirm_enabled` (consult per snapshot) |
| Client (hexdemo) | Client-local draft input; draft skins (`attack_draft`, …); merges headlines; disables `end_phase` during drafts |

See [`TURN_ACTION_DOCK_CONTRACT.md` § Draft locus](TURN_ACTION_DOCK_CONTRACT.md#draft-locus-invariant) and [§ Client draft presentation](TURN_ACTION_DOCK_CONTRACT.md#client-draft-presentation).

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

Declare special commits in `game_data.toml` → `[client_contract.panel_action_routes]` (mirrored on `turn_rules.client_contract`). Engine defaults apply when the manifest omits rows.

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

1. Copy layout from [`games/template/`](../games/template/) (move-only) or hexdemo (full combat).
2. Implement `engine_entry.load_game_definition`, `build_hooks()`, scenario TOML.
3. Bind `TURN_ACTION_DOCK_FOR_VIEWER` if you want title-owned commit UI.
4. Add `hexengine_pack.toml` and verify `validate_title_contract` at server start.
5. Point authors at this guide; run pyright on `games/<pack>/`.

### Minimal combat title (extension key + combat schedule)

1. Set `title_state_extension_key` in `game_data.toml`; add `title_state.py` accessors (no raw bucket strings in author code).
2. Declare `ArcHook.TURN_ARC_REGISTRY` with combat schedule slots (`allowed_actions` includes `Attack`).
3. Implement one `CombatRulesBinding` in `combat_arc.py`; build `ArcSpec` with [`combat_rules_binding_to_arc_spec`](../src/hexengine/authoring/patterns/combat.py) and bind `ArcHook.COMBAT_ARC` (optional `ArcHook.COMBAT_RULES_BINDING` for contract validation).
4. Thin `hooks/attack.py` adapters to binding methods; add `movement_rules.py` if retreat/move policy is non-default.
5. Register segment kinds in `segment_ui.py` (routine `combat`, each combat gate kind); bind `UIHook.SEGMENT_PRESENTATION_REGISTRY` and `TURN_ACTION_DOCK_FOR_VIEWER`.
6. Add presentation rows under `presentation/` for each `presentation_id`; run `validate_title_contract` and combat integration tests.

### New INFORM copy

1. Prefer `PHASE_BANNER_TEXT_FOR_VIEWER` + optional HTML hook.
2. Add template under `resources/templates/` + helper in `ui_markup.py`.
3. Add `shell_ui` keys only for strings reused in multiple places.

### New click-confirm map flow (`InteractionKind`)

1. Add kind string to [`InteractionKind`](../src/hexengine/gamedef/interactions.py) (engine).
2. Register server row in [`map_selection_registry.py`](../src/hexengine/hooks/map_selection_registry.py); bind title hook.
3. Implement preview hook: return `MapSelectionPreview` (draft in → legality, `commit_payload`, `panel_actions` out).
4. Register client `_apply_*_preview` + draft gesture mixin (engine/hexdemo today).
5. Add `[client_contract.panel_action_routes]` rows if Confirm is not a plain RPC.
6. Add `shell_ui` strings; document draft/response fields in pack README.
7. Update this guide + contract doc when shipped.

### New drag-only flow

1. Reuse movement/marker preview paths; align server validation with drop commit.
2. No `map_selection_preview` row unless you also need Confirm on dock.

---

## Stable vs planned

| Status | Topics |
|--------|--------|
| **Stable (v1)** | Three lanes, dock + `panel_actions` merge, registry kinds `attack_plan` / `retreat_path` / `place_marker`, drag previews, `ENGINE_DEFAULT`, HTML ladder tiers 1–3, `current_segment`-driven legality |
| **Evolving** | Client-held draft; SEQUENCE skin from `current_segment.interaction_mode`; segment registry + `authoring.present` DTOs + `presentation/inform.py` (hexdemo reference) |
| **Planned** | Action label catalog in `shell_ui`; gesture policy from segment; stricter manifest validation; [`RULE_COMPOSITION.md`](RULE_COMPOSITION.md) |

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
| [`TITLE_AUTHOR_INTERFACE_PLAN.md`](TITLE_AUTHOR_INTERFACE_PLAN.md) | Combat/movement author interface (implemented; phase history) |
| [`TURN_ACTION_DOCK_CONTRACT.md`](TURN_ACTION_DOCK_CONTRACT.md) | Wire + primitives (API detail) |
| [`PACK_HOOK_CONTRACTS.md`](PACK_HOOK_CONTRACTS.md) | Wire schemas + hook roadmap |
| [`SKINNING_AFFORDANCES_PLAN.md`](SKINNING_AFFORDANCES_PLAN.md) | Implementation status / roadmap |
| [`SKINNING_CLIENT_INVENTORY.md`](SKINNING_CLIENT_INVENTORY.md) | Client file map |
| [`TITLE_LOAD_HOOKS.md`](TITLE_LOAD_HOOKS.md) | Connect-time hooks |
| [`engine_game_boundary_matrix.md`](engine_game_boundary_matrix.md) | Authority boundaries |
| [`PACK_TRUST_MODEL.md`](PACK_TRUST_MODEL.md) | Server trust / hosted packs |
| [`SERVER_ARCHITECTURE.md`](SERVER_ARCHITECTURE.md) | Server boot and scenarios |
| [`MULTIPLAYER_INTEGRATION.md`](MULTIPLAYER_INTEGRATION.md) | Client/server checklist |
