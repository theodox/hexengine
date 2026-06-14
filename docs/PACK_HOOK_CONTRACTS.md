# Pack and title hook contracts (roadmap)

Long-term direction for **all** title integration hooks: clearer author intent, **early validation** (pack discovery, server startup, and static typing where possible), and less silent best-effort behavior.

**Title authors:** start at [`TITLE_AUTHORING.md`](TITLE_AUTHORING.md) for high-level summaries and API entry points; use **this document** for wire field tables and hook inventory detail.

Title-load is the first manifest-driven hook surface; gameplay hooks already use a separate, stricter Python model. This document is the umbrella for converging them over time.

## Two hook systems today

| System | How titles declare | Validation today | Typical failure mode |
|--------|-------------------|------------------|----------------------|
| **`TitleHooks`** (movement, attack, UI, …) | Python: `@bind_title_hook`, `assemble_title_hooks`, `GameDefinition.hooks` | Partial — `validate_title_contract` at `GameServer` startup (e.g. combat schedule requires attack hooks); `@hook` contract metadata in engine catalog | `HookContractError` when schedule and hooks disagree |
| **Manifest hooks** (`[hooks.title_load]`, future TOML tables) | `hexengine_pack.toml` names module + callables + resources | Minimal — enabling the block wires integration; missing callables/resources are skipped or logged | Connect/load continues; easy to ship an incomplete pack |

Gameplay hooks are **typed in Python** (`MovementHook`, `AttackHook`, `UIHook`, …) and wired without stringly dispatch at call sites. Manifest hooks are still **string names + tolerant runtime** (see [`TITLE_LOAD_HOOKS.md`](TITLE_LOAD_HOOKS.md)).

**Skinning and affordances** (wire fields, UI hooks, dual **data-first / code-first** `GameData` authoring, **HTML snippet/template ladder**, current client inventory): see [`SKINNING_AFFORDANCES_PLAN.md`](SKINNING_AFFORDANCES_PLAN.md) and [`SKINNING_CLIENT_INVENTORY.md`](SKINNING_CLIENT_INVENTORY.md).

**Authoritative wire schemas and UI hook inventory (v1):** see [UI affordances — wire schemas and hooks](#ui-affordances--wire-schemas-and-hooks-v1) below.

**Turn action dock (commit UI):** [`TURN_ACTION_DOCK_CONTRACT.md`](TURN_ACTION_DOCK_CONTRACT.md) — hexdemo binds `TURN_ACTION_DOCK_FOR_VIEWER`. Player primitives (INFORM / SELECT / DECIDE / SEQUENCE): same doc + § Map selection preview below.

## Authoring vs wire

**Title authors** should not treat wire payloads as the primary API. They declare **flow** in arcs (segments, `ui_mode`, allowed actions) and **presentation** in `shell_ui`, templates, pack markup helpers, and thin hook adapters. The engine **projects** hook results and segment state onto wire messages the client renders.

**Terminology:** **`ui_mode`** is the arc segment UI/policy bucket (`current_segment.ui_mode`). **`InteractionKind`** names map-selection preview flows (`attack_plan`, `retreat_path`, …); the preview RPC wire field is still `kind`. Banner, popup, and overlay wire rows also carry a **`kind`** field for CSS priority — unrelated to segment `ui_mode`.

| You author | You do not author (engine internal) |
|------------|-------------------------------------|
| Arc segments + segment `ui_mode` strings | `StateUpdate` message assembly |
| [`TitleHooks`](../src/hexengine/hooks/wiring.py) callables + contexts | WebSocket `schema` / `omit_if_none` rules |
| `shell_ui`, templates, `presentation_id` skin keys | `BrowserWebSocketClient` field parsing for legality |
| Preview hook: draft in → legality + `commit_payload` out | Client computing legal hex sets locally |
| **Segment presentation registry** (one row per UX mode) | `UIHook.SEGMENT_PRESENTATION_REGISTRY` |
| **Segment wire enrichment** | `UIHook.ENRICH_CURRENT_SEGMENT` (required when `session_state_key` is set) |

**Hook return shapes:** turn dock and INFORM map popups **must** return **`TurnDockPanel` / `InformPopup`** from `hexengine.authoring.present`. The engine serializes via `hexengine.hooks.internal.ui_wire` only. **`bind_title_hook` accepts hook enums only.** Prefer:

- Typed contexts (`TurnActionDockContext`, `InformPopupContext`, …) for inputs.
- `turn_dock_panel`, `inform_popup`, pack `presentation/` helpers for outputs.
- No hand-built wire dicts in `games/*` except tests.

**Wire tables below** document what the client receives after projection. Use them when debugging network traffic or extending the engine renderer — not when writing a new title pack. Author workflow: [`TITLE_AUTHORING.md` § Flow vs presentation](TITLE_AUTHORING.md#flow-vs-presentation-authoring-model) and [§ Segment presentation registry](TITLE_AUTHORING.md#segment-presentation-registry).

**P3:** `current_segment` includes `presentation_id` and `interaction_mode` when the title binds `UIHook.ENRICH_CURRENT_SEGMENT` (hexdemo: `hooks/segment_presentation.py`). Required for packs with `session_state_key`.

**P4:** INFORM ``inspect`` resolves ``inform_profile`` from ``current_segment`` when the client omits ``inform_kind`` (`hexengine.arcs.inform_wire`). Title popups key off profile + reason (hexdemo: `presentation/inform.py`).

**P5:** ``validate_arc_contract`` / ``validate_title_contract`` ensure declared arc segment ``ui_mode`` values ⊆ ``segment_presentation_registry`` (`hexengine.authoring.segment_ui_validate`). Titles with ``session_state_key`` must bind ``UIHook.SEGMENT_PRESENTATION_REGISTRY``.

## UI affordances — wire schemas and hooks (v1)

Per-recipient UI payloads travel on **`StateUpdate`** (banner messages, turn action dock panels, map overlays) or as standalone server messages (**`ui_popup`**). Titles customize copy and affordances through **`UIHook`** callables bound with `@bind_title_hook`; return **`ENGINE_DEFAULT`** to request engine composition or catalog defaults.

Code references: [`StateUpdate`](../src/hexengine/server/protocol/server.py), [`UIPopupWire`](../src/hexengine/server/protocol/server.py), [`UIHooks` / `UIHook`](../src/hexengine/hooks/ui.py), server builders in [`game_server.py`](../src/hexengine/server/game_server.py), client renderers in [`game.py`](../src/hexengine/game/game.py).

### Dual-field rule (text + optional html)

Every rich message should ship **plain `text` plus optional `html`**:

| Field | Role |
|-------|------|
| **`text`** | Required on `interaction_messages` rows; fallback when `html` is absent; accessibility; tests and logs |
| **`html`** | Optional HTML **fragment** (not a full document); client prefers `html` over `text` when both are non-empty |

Same rule applies to **`INFORM_POPUP`** hook results and **`ui_popup`** wire payloads. Do **not** put player actions in HTML (`onclick`, forms); use the **turn action dock** (`interaction_panels` `actions[]`) + `action_request`.

HTML is **trusted title content** — the client uses `innerHTML` without sanitization. **Escape dynamic values** before interpolation (see [HTML authoring ladder](#html-authoring-ladder-v1)).

### `StateUpdate.interaction_messages`

Transient turn banner rows. Omitted from wire when `None`. Client shows **one** row: highest-priority `kind` among non-expired rows (`error` > `retreat` > `advance` > `wait` > `phase` > `info`).

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `schema` | `int` | yes | Always **`1`** |
| `kind` | `str` | yes | Semantic kind; drives client priority and default CSS. Common: `phase`, `retreat`, `wait`, `advance`, `info`, `error` |
| `text` | `str` | yes* | Plain-text body (*required unless `html` alone suffices for your tests; engine defaults always set `text`) |
| `html` | `str` | no | Rich fragment; client renders via `innerHTML` when set |
| `dedupe_key` | `str` | no | Client replaces prior row with same key (e.g. `phase:{schedule_index}`, `combat_prompt`) |
| `ttl_ms` | `int \| null` | no | Local expiry in ms; `null` = persistent until next `StateUpdate` |
| `css_class` | `str` | no | Extra class on `#interaction-banner`; if omitted, client uses `GameData.interaction_kind_styles` via `css_class_for_interaction_kind(kind)` |

**Server composition:** unless `UIHook.INTERACTION_MESSAGES` returns a full list, the server merges:

1. **Phase row** — `PHASE_BANNER_TEXT_FOR_VIEWER` → `text`; optional `PHASE_BANNER_HTML_FOR_VIEWER` → `html`
2. **Combat rows** — `UIHook.COMBAT_INTERACTION_MESSAGES` → `list[InteractionMessage]` (hexdemo: [`hooks/ui.py`](../games/hexdemo/hooks/ui.py)). Context includes `shell_ui` from `game_data.toml`. When the hook returns `ENGINE_DEFAULT`, the engine builds rows from `current_segment.ui_mode` plus `COMBAT_INSTRUCTION_FOR_VIEWER` and `ADVANCE_GATE_BANNERS_FOR_VIEWER` ([`ui_combat_messages.py`](../src/hexengine/hooks/ui_combat_messages.py)). The engine does not read session-state `combat_gate` for banners.

`game_server` does not parse `last_combat` / `combat_gate` directly for banners (engine boundary 2). **`combat_event`** messages for retreat UI still use `last_combat` in [`_broadcast_combat_events`](../src/hexengine/server/game_server.py) — separate from INFORM.

**Full override:** `INTERACTION_MESSAGES(state, viewer_faction)` → `list[InteractionMessage]` replaces the entire default list. Partial hooks are ignored when this hook is bound and does not return `ENGINE_DEFAULT`.

Example phase row (engine-shaped):

```json
{
  "schema": 1,
  "kind": "phase",
  "dedupe_key": "phase:3",
  "ttl_ms": null,
  "css_class": "interaction-msg--phase",
  "text": "Union: movement (actions: 2)",
  "html": "<span class=\"hexdemo-turn-banner\">…</span>"
}
```

### `StateUpdate.interaction_panels` (turn action dock)

Commit UI on host `#user-controls`. Full panel and action schemas: [`TURN_ACTION_DOCK_CONTRACT.md`](TURN_ACTION_DOCK_CONTRACT.md).

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `schema` | `int` | yes | **`1`** |
| `id` | `str` | yes | Stable id (convention: `turn_actions`) |
| `host` | `str` | yes | DOM element id (default `user-controls`) |
| `presentation_id` | `str` | no | Title-defined skin key (matches `current_segment.presentation_id`) |
| `headline` | `str` | no | Short dock title |
| `html` | `str` | no | Decorative fragment only (no inline handlers) |
| `css_class` | `str` | no | Panel root class |
| `actions` | `list` | yes | Action rows (schema below) |
| `inputs` | `list` | no | `{id, kind, label, name, default?, options?}` — merged into action `payload` on click |

**Dispatch:** `TURN_ACTION_DOCK_FOR_VIEWER(ctx)` → `list[TurnDockPanel]` or `ENGINE_DEFAULT` → [`default_turn_action_dock_for_viewer`](../src/hexengine/hooks/ui_turn_action_dock.py) (End Phase only). Hexdemo: [`games/hexdemo/hooks/turn_action_dock.py`](../games/hexdemo/hooks/turn_action_dock.py) — adds combat gate rows via [`combat_gate_panel_actions`](../src/hexengine/authoring/patterns/combat.py). Gate `presentation_id` / `interaction_mode` require `UIHook.ENRICH_CURRENT_SEGMENT` + segment registry.

When `session_state_key` is set, **`TURN_ACTION_DOCK_FOR_VIEWER` is required**; the server never emits **`StateUpdate.primary_actions`** ([`ClientInteractionPanelsMixin`](../src/hexengine/game/arcs/client_interaction_panels.py)).

### Core wire verbs (action_request)

Stable **mechanism** names the engine understands. Titles gate when each is legal via arc segment `allowed_actions` and guards — not via engine hardcoded title ids.

| Verb | Family | Routing |
|------|--------|---------|
| `MoveUnit` | Modification | Routine movement hooks; overlay path via `try_arc_move_unit` when interaction cursor active |
| `NextPhase` | Schedule | Routine arc segment |
| `Attack` | Interaction | Authority attack pipeline (`execute_authority_attack_request`) |
| `CombatAdvance`, `CombatDeclineAdvance`, `CombatDisruptInsteadOfRetreat` | Interaction aftermath | `try_arc_rpc` when declared on overlay graph (`overlay_rpc_action_types`) |
| Marker verbs (`MoveMarker`, …) | Board modification | Title hooks / server validators |

When an overlay arc is active, illegal RPCs for the current segment are **rejected** (`COMBAT_REJECTED_MSG` / segment deny) — not “title misconfigured.” Undeclared overlay with aftermath-only verbs → `COMBAT_ARC_REQUIRED_MSG`.

### Action row schema (shared)

Used in dock `actions[]` and in `map_selection_preview.panel_actions`.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `schema` | `int` | yes | **`1`** |
| `id` | `str` | yes | Stable id; client upserts by `id` |
| `action_type` | `str` | yes | Server RPC name (e.g. `NextPhase`, `CombatAdvance`, `Attack`) |
| `label` | `str` | yes | Button label |
| `title` | `str` | no | Tooltip |
| `payload` | `object` | no | Action params (default `{}`) |
| `css_class` | `str` | no | Extra button class |
| `enabled` | `bool` | yes | When `false`, button is shown disabled |
| `group` | `str` | no | Layout hint: `primary`, `secondary`, `danger` |
| `order` | `int` | no | Optional sort within panel |

### `StateUpdate.primary_actions` (removed from wire)

Commit rows live on `interaction_panels[].actions[]` via `TURN_ACTION_DOCK_FOR_VIEWER`. End Phase enablement follows `current_segment.allowed_actions`. Combat cleanup gate buttons (Disrupt / Advance / Skip) are title-owned: [`combat_gate_panel_actions`](../src/hexengine/authoring/patterns/combat.py) in the dock hook, not the engine catalog default.

### `StateUpdate.map_overlays`

Map-space DOM overlays under `#map-world`. See inline doc on [`StateUpdate`](../src/hexengine/server/protocol/server.py). Built from `UIHook.MAP_OVERLAYS` (`MapOverlay` DTO via `map_overlay_glyph`) or engine default (empty list); serialized in [`map_overlays_to_wire`](../src/hexengine/hooks/internal/ui_wire.py).

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `schema` | `int` | yes | **`1`** |
| `id` | `str` | yes | Stable id; replace prior overlay with same id |
| `kind` | `str` | yes | e.g. `glyph` |
| `hex` | `{i,j,k}` | yes | Map anchor |
| `text` | `str` | kind-specific | Glyph text |
| `css_class` | `str` | no | Title CSS hook |

### `ui_popup` (standalone message)

Sent on **`InspectRequest`**, not embedded in `StateUpdate`. One hook, one wire:

| `target_kind` | Hook | When |
|---------------|------|------|
| `unit`, `marker`, `inform` | **`INFORM_POPUP`** | Double-click inspect, Enter on selection; map callouts (`inform`: `context.inform_kind`, `target_id` = reason, optional `hex` / `unit_id`) |

Client entry point for inform: `Game.show_inform_popup(...)` → `send_inform_popup` on the WebSocket client.

**Wire type:** [`UIPopupWire`](../src/hexengine/server/protocol/server.py) (`wire_type: ui_popup`).

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `hex` | `{i,j,k}` | yes | Callout anchor (server sets from target position) |
| `kind` | `str` | no | Default `info` |
| `text` | `str` | one of text/html | Plain fallback |
| `html` | `str` | one of text/html | Rich fragment; client prefers over `text` |
| `ttl_ms` | `int \| null` | no | Auto-dismiss after ms; default **800** on wire when hook omits |
| `css_class` | `str` | no | Extra class on popup root |

**Hook return:** `InformPopup` DTO from `hexengine.authoring.present.inform_popup` (serialized via `inform_popup_to_wire`; server adds `hex`). At least one of `text` or `html` required.

Example from hexdemo [`unit_inspect_popup`](../games/hexdemo/ui_markup.py):

```python
inform_popup(
    text="u1 | infantry | union | [3, 4]",
    html="<div class=\"hexdemo-unit-inspect\">…</div>",  # from templates/unit_inspect.html
    kind="info",
    ttl_ms=1500,
)
```

Use **`text` + `html`** together; the server forwards `ttl_ms` and optional `css_class` to the client popup.

### Map selection preview (`map_selection_preview_request` / `map_selection_preview`)

SELECT drafts (map/unit picks before commit) use one RPC pair. Drafts are **client-local until commit**; preview consults per snapshot, commit authorizes. See [`TURN_ACTION_DOCK_CONTRACT.md` § Draft locus](TURN_ACTION_DOCK_CONTRACT.md#draft-locus-invariant). The server dispatches by **`kind`** ([`InteractionKind`](../src/hexengine/gamedef/interactions.py)) through [`map_selection_registry`](../src/hexengine/hooks/map_selection_registry.py). Full primitive model: [`TURN_ACTION_DOCK_CONTRACT.md`](TURN_ACTION_DOCK_CONTRACT.md#player-interaction-primitives).

**Client request:** [`MapSelectionPreviewRequest`](../src/hexengine/server/protocol/client.py) — `kind`, `draft` object, optional `request_id`.

**Server response:** [`MapSelectionPreviewWire`](../src/hexengine/server/protocol/server.py) — `kind`, `status_text`, `confirm_enabled`, optional `valid_target_hexes`, `eligible_attacker_ids`, `commit_payload`, `panel_actions` (same action row schema as the turn action dock). Title preview hooks return [`MapSelectionPreview`](../src/hexengine/ui/display.py); the engine serializes via [`map_selection_preview_to_wire`](../src/hexengine/hooks/internal/ui_wire.py).

**Feature flag:** `turn_rules.client_contract.features` includes **`map_selection_previews`** when [`bound_map_selection_kinds`](../src/hexengine/hooks/map_selection_registry.py) is non-empty for the title.

#### Kind → hook binding (registry)

| `InteractionKind` | Title hook | Draft / notes |
|-------------------|------------|---------------|
| `attack_plan` | `AttackHook.ATTACK_PLAN_PREVIEW` → `hooks.attack.attack_plan_preview` | `target_hex`, `attacker_ids`; returns `panel_actions` (hexdemo) |
| `retreat_path` | `MovementHook.RETREAT_PATH_PREVIEW` → `hooks.movement.retreat_path_preview` | `unit_id`, `path[]`; `legal_next_hexes`, stepwise `commit_payload` (hexdemo) |
| `inspect_unit` | — | Inspect uses `INFORM_POPUP`, not map-selection preview |
| `place_marker` | `UIHook.PLACE_MARKER_PREVIEW` → `hooks.ui.place_marker_preview` | `marker_id`, `to_hex`; legal destinations from title rule; `MoveMarker` commit (hexdemo). Shift+click marker to start; drag unchanged. |

To add an `InteractionKind`: extend the enum, register a row in [`map_selection_registry.py`](../src/hexengine/hooks/map_selection_registry.py), bind a title hook, declare client wiring in `game_data.toml` → `[client_contract.select_modes]` and optional `[client_contract.panel_action_routes]` (mirrored on `turn_rules.client_contract`; see [`client_contract.py`](../src/hexengine/gamedef/client_contract.py)). Engine defaults in [`client_map_selection_registry.py`](../src/hexengine/game/arcs/client_map_selection_registry.py) and [`client_panel_actions.py`](../src/hexengine/game/arcs/client_panel_actions.py) apply when the manifest omits rows.

### UI hook inventory

Bind with `@bind_title_hook(UIHook.…)` in the title hooks package. Values match [`UIHook`](../src/hexengine/hooks/ui.py) enum names.

| Hook | When invoked | Signature | Return | `ENGINE_DEFAULT` behavior |
|------|--------------|-----------|--------|---------------------------|
| **`INTERACTION_MESSAGES`** | Every per-player `StateUpdate` | `(state, viewer_faction)` | `list[InteractionMessage]` | Server builds default list (phase + combat + advance rows) |
| **`PHASE_BANNER_TEXT_FOR_VIEWER`** | Default message composition | `(ctx: PhaseBannerContext)` | `str` | [`default_phase_banner_text_for_viewer`](../src/hexengine/hooks/ui.py) |
| **`PHASE_BANNER_HTML_FOR_VIEWER`** | Default message composition | `(ctx: PhaseBannerContext)` | `str` | Omitted — phase row is text-only |
| **`COMBAT_INSTRUCTION_FOR_VIEWER`** | After combat with retreat context | `(ctx: CombatInteractionContext)` | `(instruction, message)` | [`default_combat_instruction_for_viewer`](../src/hexengine/hooks/ui.py) |
| **`ADVANCE_GATE_BANNERS_FOR_VIEWER`** | Active segment `ui_mode` is advance gate | `(ctx: AdvanceGateInteractionContext)` | `(text_advancing, text_other)` | [`default_advance_gate_banners_for_viewer`](../src/hexengine/hooks/ui.py) |
| **`INFORM_POPUP`** | `InspectRequest` (`unit` / `marker` / `inform`) | `(ctx: InformPopupContext)` | `InformPopup` | [`default_inform_popup_for_viewer`](../src/hexengine/hooks/inform_popup.py) |
| **`MAP_OVERLAYS`** | Every per-player `StateUpdate` | `(state, viewer_faction)` | `list[MapOverlay]` | `[]` |
| **`ENRICH_CURRENT_SEGMENT`** | Every per-player `current_segment` projection | `(ctx: SegmentPresentationContext)` | `SegmentPresentationPatch` | No enrichment (base segment only) |
| **`TURN_ACTION_DOCK_FOR_VIEWER`** | Every per-player `StateUpdate` | `(ctx: TurnActionDockContext)` | `list[TurnDockPanel]` | Engine catalog ([`default_turn_action_dock_for_viewer`](../src/hexengine/hooks/ui_turn_action_dock.py)). No draft on context — see [draft locus](TURN_ACTION_DOCK_CONTRACT.md#draft-locus-invariant). |
| **`COMBAT_INTERACTION_MESSAGES`** | Default `interaction_messages` combat slice (after phase row) | `(ctx: CombatInteractionMessagesContext)` | `list[InteractionMessage]` | [`default_combat_interaction_messages`](../src/hexengine/hooks/ui_combat_messages.py) using segment `ui_mode` + partial combat/advance hooks |
| **`COMBAT_EVENT_SUMMARY`** | After combat, to fan out `combat_event` wires | `(state)` | `CombatEventSummary \| None` | `None` (no `combat_event` broadcast) |

**Partial vs full message hooks**

- **Partial** — customize one slice; server merges into the default `interaction_messages` list.
- **Full** — `INTERACTION_MESSAGES` replaces the entire list with `InteractionMessage` DTOs; do not rely on partial hooks when the full hook is bound.
- **Phase banner** — always provide sensible `text` via `PHASE_BANNER_TEXT_FOR_VIEWER` even when `PHASE_BANNER_HTML_FOR_VIEWER` supplies display HTML.

Context dataclasses: [`CombatInteractionContext`](../src/hexengine/hooks/ui.py), [`AdvanceGateInteractionContext`](../src/hexengine/hooks/ui.py), [`CombatInteractionMessagesContext`](../src/hexengine/hooks/ui_combat_messages.py), [`PhaseBannerContext`](../src/hexengine/hooks/ui.py), [`TurnActionDockContext`](../src/hexengine/hooks/ui_turn_action_dock.py).

**Phase advance blocking:** `NextPhase` legality and End Phase dock enablement derive from `current_segment.allowed_actions` ([`segment_blocks_routine_phase_advance`](../src/hexengine/arcs/segment_wire.py)). Titles with `session_state_key` must bind `ArcHook.TURN_ARC_REGISTRY`.

### Attack hook inventory (combat policy)

Bind with `@bind_title_hook(AttackHook.…)`. Values match [`AttackHook`](../src/hexengine/hooks/attack.py). **There are no attack cleanup hook slots** — retreat, disrupt, and advance run through the declared combat arc (`ArcHook.COMBAT_ARC`).

For packs with `session_state_key`, the engine rejects `Attack` when `current_segment` omits it for the actor **before** `validate_attack` runs (`ATTACK_BLOCKED_BY_ACTIVE_SEGMENT_MSG` in `authority_attack.py`). Title validate is rules-only (phase, LOS, CRT inputs, etc.).

| Hook | When invoked | Signature / context | Return | `ENGINE_DEFAULT` behavior |
|------|--------------|---------------------|--------|---------------------------|
| **`VALIDATE_ATTACK`** | After engine segment gate, before resolve | `(ctx: AttackContext)` | `None` or raise | Unsupported attack |
| **`RESOLVE_ATTACK`** | Interaction arc segment with `Event("Attack")` (discovered via `arc_commit_segment_for_action`) | `(ctx: AttackContext)` | `AttackResolution` or `CombatOutcome` (with embedded resolution) | Unsupported attack |
| **`ATTACK_PLAN_PREVIEW`** | `map_selection_preview` `InteractionKind` `attack_plan` | `(ctx: AttackPlanPreviewContext)` | `MapSelectionPreview` | Empty/minimal preview |
| **`AUTO_ADVANCE_PHASE_AFTER_ATTACK`** | After attack applied + broadcast | `(state: GameState)` | `bool` | No auto-advance |
| **`COMBAT_OUTCOME_AFTER_APPLIED`** | After `Attack` + `ApplyCombatEffects` inside arc `attack` effect | `(ctx: AfterAttackAppliedContext)` | [`CombatOutcome`](../src/hexengine/hooks/combat_outcome.py) | No bucket follow-up |

When the combat overlay finishes (classify `done` or last cleanup step), the engine calls **`restore_routine_cursor`** so the turn slot cursor (and `NextPhase` on the routine combat segment) returns.

**Removed (do not document or bind):** `AFTER_ATTACK_APPLIED`, `ON_RETREAT_OBLIGATION_CLEARED`, `COMBAT_DISRUPT_INSTEAD_OF_RETREAT`, `COMBAT_RESOLVE_ADVANCE`, `IS_COMBAT_ADVANCE_MOVE`. Cleanup uses arc effects; advance `MoveUnit` uses [`ArcSpec.advance_move_detector`](../src/hexengine/arcs/runner.py) on `COMBAT_ARC`.

**Session-state patches:** build [`BucketPatch`](../src/hexengine/hooks/bucket.py) (author import from `hexengine.hooks.bucket`). Return it inside [`CombatOutcome`](../src/hexengine/hooks/combat_outcome.py) from `combat_outcome_after_applied` (or embed in `resolve_attack`); engine applies [`ApplyBucketPatch`](../src/hexengine/state/actions.py) via [`combat_outcome_apply`](../src/hexengine/server/arcs/combat_outcome_apply.py). Read session state via pack `session_state.bucket()` or engine `engine_read_session_state`.

**Movement author layout:** policy in [`movement/rules.py`](../games/hexdemo/movement/rules.py) implementing [`MovementRulesBinding`](../src/hexengine/hooks/movement_rules.py); [`hooks/movement.py`](../games/hexdemo/hooks/movement.py) binds slots. Stepwise payload and arc cursor sync stay in `authority_movement` / movement arc runner.

**Interaction arc author layout:**

| Layer | Hexdemo path | Role |
|-------|--------------|------|
| Graph (topology) | [`combat/graph.py`](../games/hexdemo/combat/graph.py) | Pack-visible aftermath FSM — **read first** when customizing flow |
| Binding (policy) | [`combat/rules.py`](../games/hexdemo/combat/rules.py) | One [`CombatRulesBinding`](../src/hexengine/hooks/combat_rules.py) class: guards, effects, CRT, `attack_arc_effect` |
| Arc spec shell | [`combat/arc.py`](../games/hexdemo/combat/arc.py) | `ArcSpec`, owner resolver, `advance_move_detector` |
| Hook wiring | [`arcs/wiring.py`](../games/hexdemo/arcs/wiring.py) | `ArcHook.COMBAT_ARC`, `COMBAT_RULES_BINDING`, `TURN_ARC_REGISTRY` |
| Turn rota | [`arcs/turn_schedule.py`](../games/hexdemo/arcs/turn_schedule.py) | `TurnArcRegistry` for routine modification + interaction segments |
| Presentation | [`ui/segment_registry.py`](../games/hexdemo/ui/segment_registry.py) | One row per segment `ui_mode` |

**Template shortcut:** [`combat_rules_binding_to_arc_spec`](../src/hexengine/authoring/patterns/combat.py) from a binding class in [`games/template/combat_arc.py`](../games/template/combat_arc.py) — no pack graph until you copy [`games/hexdemo/combat/graph.py`](../games/hexdemo/combat/graph.py). Optional outline: [`games/template/combat/graph.py`](../games/template/combat/graph.py).

Dock gate rows: [`combat_gate_panel_actions`](../src/hexengine/authoring/patterns/combat.py) from `TURN_ACTION_DOCK_FOR_VIEWER`.

**Reference pack hooks:** [`games/hexdemo/hooks/`](../games/hexdemo/hooks/) (`attack.py`, `movement.py`, `turn_action_dock.py`, `ui.py`); arc wiring [`arcs/wiring.py`](../games/hexdemo/arcs/wiring.py). Policy: [`combat/rules.py`](../games/hexdemo/combat/rules.py), [`combat/outcome.py`](../games/hexdemo/combat/outcome.py), [`combat/actions.py`](../games/hexdemo/combat/actions.py), [`combat/transitions.py`](../games/hexdemo/combat/transitions.py), [`movement/rules.py`](../games/hexdemo/movement/rules.py), [`state/session_state.py`](../games/hexdemo/state/session_state.py). Inventory: [`SKINNING_CLIENT_INVENTORY.md`](SKINNING_CLIENT_INVENTORY.md). Boundary matrix: [`engine_game_boundary_matrix.md`](engine_game_boundary_matrix.md).

### Client contract features (not wire rows)

Optional UX is gated via `StateUpdate.turn_rules.client_contract.features` (e.g. **`attack_planning_ui`**, **`map_selection_previews`**). Attack-plan confirm/cancel come from **`map_selection_preview.panel_actions`** merged into the turn action dock; `AttackPlanCancel` is client-local (no RPC). See [`client_map_selection.py`](../src/hexengine/game/arcs/client_map_selection.py), [`client_combat.py`](../src/hexengine/game/arcs/client_combat.py).

### HTML authoring ladder (v1)

Tiered approach for title HTML without arbitrary inline JS. Expanded narrative and hexdemo walkthrough: [`SKINNING_AFFORDANCES_PLAN.md` § Authoring](SKINNING_AFFORDANCES_PLAN.md#authoring).

| Tier | Mechanism | Best for |
|------|-----------|----------|
| **1 — CSS-first** | `GameData` + `resources/ui.css`; return `text` + `css_class` / faction classes on `#interaction-banner` | Bar colors, typography, layout chrome |
| **2 — Static templates** | `resources/templates/*.html` loaded with `read_pack_resource_text`; `{placeholders}` with **`html.escape`** on dynamic values | Designer-editable layout shells |
| **3 — Pack helpers** | Title module (e.g. `ui_markup.py`) wrapping templates + escape | Repeated patterns within one pack |
| **4 — Engine helpers** | [`hexengine.ui.display`](../src/hexengine/ui/display.py): `escape`, `interaction_message`, `InteractionMessage`, `load_html_template`, `render_html_template`, `pack_asset_href` | Shared API across packs |
| **5 — Full hook override** | `INTERACTION_MESSAGES` returns complete `list[InteractionMessage]` with optional `html` per row | Total control over banner composition |

**Wire surfaces that accept `html` (v1)**

| Surface | Hook / field | Display-only |
|---------|--------------|--------------|
| Turn banner | `interaction_messages[].html`, `PHASE_BANNER_HTML_FOR_VIEWER` | Yes |
| Inspect popup | `INFORM_POPUP` → `ui_popup.html` | Yes |
| Title-load splash | `[hooks.title_load]` splash resource | Yes |
| Turn action dock | `interaction_panels[].headline`, `html` (display); `actions[]` commit | `actions[]` → `action_request` |

**Do not:** raw f-string HTML without escape; inline `onclick`; Jinja in v1; live `GameState` copy in static TOML.

---

## Target model (partially implemented)

Authors should be able to answer, without reading engine internals:

1. **Which hooks does my pack implement?** (required vs optional vs engine default)
2. **What is each hook’s signature and when does it run?** (arc segment, server RPC, client-only, …)
3. **What fails if I get it wrong?** — prefer **fail at pack load / server start / typecheck**, not mid-match or silent skip.
4. **Which UX mode is active?** — one **segment presentation registry** row per `ui_mode` (primitive, `presentation_id`, optional `interaction_mode`, inform profile) — see [`TITLE_AUTHORING.md` § Segment presentation registry](TITLE_AUTHORING.md#segment-presentation-registry).

**Shipped toward this model:** presentation DTOs + `ui_wire` adapters (P2); `current_segment` enrich (P3); inform profile from segment (P4); segment registry validation (P5); `[client_contract]` in `game_data.toml` for client select modes and panel-action routes; combat gate dock rows in `combat_gate_panel_actions` (title helper, not engine wire).

**Still planned** (apply across **both** hook systems over time):

### 1. Explicit contracts

- **Required vs optional** per hook point (not inferred only from “table present” in TOML).
- Document **arc segment** (engine) vs **pack hook** (title) for client flows — same vocabulary as [`hexengine.game.arcs.client_title_load`](../src/hexengine/game/arcs/client_title_load.py).
- Extend `validate_title_contract` (or siblings) for more schedule/hook combinations, not only combat/attack.
- **Segment UI registry (P5):** every explicit `ui_mode` used in declared arcs has a registry row — enforced at startup when `SEGMENT_PRESENTATION_REGISTRY` is bound.

### 2. Early validation (“compile-time” in the broad sense)

- **Static typing:** hook protocols and context/result dataclasses (`TitleLoadContext`, `AttackContext`, …); titles checked with pyright/mypy in CI.
- **Discovery time:** when parsing `hexengine_pack.toml` or resolving a scenario — verify module import, callable presence, resource files on disk.
- **Server startup:** strict checks before accepting joins (build on existing `validate_title_contract`).
- **Dev vs prod:** optional strict mode (loud failures) vs production tolerance during transition.

### 3. Pack templates and stubs

Scaffolding (e.g. `games/_template/` or `hexengine init-pack`) should ship:

- Commented `hexengine_pack.toml` marking **required** and **optional** hook keys
- **Stub functions** with correct signatures and docstrings (what to fill in, what may return `ENGINE_DEFAULT`)
- Placeholder resources (`splash.html`, etc.)

Hexdemo remains the reference implementation; the template is the minimal “fill the blanks” pack.

### 4. Manifest schema evolution

For TOML-driven hooks, prefer explicit tables over implicit defaults, for example:

```toml
# Illustrative — not implemented
[hooks.title_load]
module = "mytitle.boot"
required = ["splash", "setup"]   # validated at discovery
optional = ["server_loaded"]

[hooks.title_load.splash]
html = "splash.html"
callable = "present_splash"
```

Align naming and validation rules with `TitleHooks` contract sentinels (`REQUIRED`, `PRESET`, `SINGLE_DEFAULT`) in [`hexengine.hooks.internal`](../src/hexengine/hooks/internal/contracts.py) where it makes sense.

## Hook inventory (current surfaces)

| Area | Declaration | Entry / validation | Notes |
|------|-------------|-------------------|--------|
| Movement | `TitleHooks.movement` | Server movement arc; hook catalog | `MovementHook` enum + `bind_title_hook` |
| Attack | `TitleHooks.attack` | [`authority_attack`](../src/hexengine/server/arcs/authority_attack.py); `validate_title_contract` when interaction is declared (today also phase-name heuristics — charter phase 4) | Required `validate_attack` / `resolve_attack` when interaction arc + combat slots; optional `combat_outcome_after_applied`; cleanup via `ArcHook.COMBAT_ARC` — see [Attack hook inventory](#attack-hook-inventory-combat-policy) |
| Arcs | `TitleHooks.arcs` | Arc runner, turn registry, overlay cursor | `TURN_ARC_REGISTRY`; `COMBAT_ARC` when interaction enabled; wire in [`arcs/wiring.py`](../games/hexdemo/arcs/wiring.py) (hexdemo) |
| UI | `TitleHooks.ui` | Client/server UI hook points | Per-viewer wire: [`interaction_messages`](#stateupdateinteraction_messages), [`interaction_panels`](#stateupdateinteraction_panels-turn-action-dock), [`ui_popup`](#ui-popup-standalone-message); see [UI affordances](#ui-affordances--wire-schemas-and-hooks-v1) |
| Title-load (client) | `[hooks.title_load]` | Client title-load arc; tolerant dispatch in `gameroot` | See [`TITLE_LOAD_HOOKS.md`](TITLE_LOAD_HOOKS.md) |
| Title-load (server) | same manifest | `try_pack_title_load_server` | One-shot log hook today |
| Game definition | `[python].entry_*` | Required for pack load | Already hard-required |

Future manifest tables (lobby, setup UI sync, asset packs) should follow the same contract story from the start.

## Composable rule sets (future)

Beyond hook **contracts**, titles should eventually assemble **rule sets** from engine-provided **composable pieces** (ZOC, terrain class, morale gates, …) plus custom rules where needed — declaratively where possible, in Python where not. Patterns are not clear enough to implement yet; see **[`RULE_COMPOSITION.md`](RULE_COMPOSITION.md)** for intent, open questions, and phased evolution. Hook and rules layers stay separate: composition is policy; hooks are when the engine invokes it.

## Phased rollout (suggested)

1. **Document and template** — template pack + stub modules; keep runtime tolerant.
2. **Discovery validation** — warnings/errors for manifest hooks and expanded `validate_title_contract`.
3. **CI typing** — pyright on `games/*` against engine hook protocols.
4. **Offline audit CLI** — static checks for packs that stay within hook/arc/rules-import boundaries (server admin / registry use); see [`PACK_TRUST_MODEL.md`](PACK_TRUST_MODEL.md#offline-audit-tooling-planned).
5. **Tighten runtime** — strict mode, then default strict for new packs.

## Related docs and code

- Composable rules (planning): [`RULE_COMPOSITION.md`](RULE_COMPOSITION.md)
- Title-load detail: [`TITLE_LOAD_HOOKS.md`](TITLE_LOAD_HOOKS.md)
- Hook authoring: [`src/hexengine/hooks/__init__.py`](../src/hexengine/hooks/__init__.py)
- Contract validation: [`src/hexengine/hooks/internal/contracts.py`](../src/hexengine/hooks/internal/contracts.py)
- Server arcs: [`src/hexengine/server/arcs/__init__.py`](../src/hexengine/server/arcs/__init__.py)
- Game definition protocol: [`src/hexengine/gamedef/protocol.py`](../src/hexengine/gamedef/protocol.py)
