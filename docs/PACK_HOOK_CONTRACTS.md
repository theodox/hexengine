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

**Title authors** should not treat wire payloads as the primary API. They declare **flow** in arcs (segments, `kind`, allowed actions) and **presentation** in `shell_ui`, templates, pack markup helpers, and thin hook adapters. The engine **projects** hook results and segment state onto wire messages the client renders.

| You author | You do not author (engine internal) |
|------------|-------------------------------------|
| Arc segments + segment `kind` strings | `StateUpdate` message assembly |
| [`TitleHooks`](../src/hexengine/hooks/wiring.py) callables + contexts | WebSocket `schema` / `omit_if_none` rules |
| `shell_ui`, templates, `presentation_id` / `dock_arc` skin keys | `BrowserWebSocketClient` field parsing for legality |
| Preview hook: draft in → legality + `commit_payload` out | Client computing legal hex sets locally |
| Optional **segment presentation registry** (one row per UX mode) | `dock_arc_from_segment` heuristics (engine fallback when a `kind` is unregistered) |

**Hook return shapes:** turn dock and inform popups should return **`TurnDockPanel` / `InformPopup`** from `hexengine.authoring.present` (hexdemo reference). Legacy `dict` rows are still accepted; the engine normalizes via `hexengine.hooks.internal.ui_wire` before wire assembly. Prefer:

- Typed contexts (`TurnActionDockContext`, `InformPopupContext`, …) for inputs.
- `turn_dock_panel`, `inform_popup`, pack `presentation/` helpers for outputs.
- No hand-built wire dicts in `games/*` except tests.

**Wire tables below** document what the client receives after projection. Use them when debugging network traffic or extending the engine renderer — not when writing a new title pack. Author workflow: [`TITLE_AUTHORING.md` § Flow vs presentation](TITLE_AUTHORING.md#flow-vs-presentation-authoring-model) and [§ Segment presentation registry](TITLE_AUTHORING.md#segment-presentation-registry).

**P3:** `current_segment` includes `presentation_id` and `interaction_mode` when the title binds `UIHook.ENRICH_CURRENT_SEGMENT` (hexdemo: `hooks/segment_presentation.py`). Engine defaults apply when the hook is omitted.

**P4:** INFORM ``inspect`` resolves ``inform_profile`` from ``current_segment`` when the client omits ``inform_kind`` (`hexengine.arcs.inform_wire`). Title popups key off profile + reason (hexdemo: `presentation/inform.py`).

**P5:** ``validate_arc_contract`` / ``validate_title_contract`` ensure declared arc segment ``kind`` values ⊆ ``segment_presentation_registry`` (`hexengine.authoring.segment_ui_validate`). Titles with ``title_state_extension_key`` must bind ``UIHook.SEGMENT_PRESENTATION_REGISTRY``.

## UI affordances — wire schemas and hooks (v1)

Per-recipient UI payloads travel on **`StateUpdate`** (banner messages, turn action dock panels, map overlays) or as standalone server messages (**`ui_popup`**). Titles customize copy and affordances through **`UIHook`** callables bound with `@bind_title_hook`; return **`ENGINE_DEFAULT`** to request engine composition or catalog defaults.

Code references: [`StateUpdate`](../src/hexengine/server/protocol/server.py), [`UIPopupWire`](../src/hexengine/server/protocol/server.py), [`UIHooks` / `UIHook`](../src/hexengine/hooks/ui.py), server builders in [`game_server.py`](../src/hexengine/server/game_server.py), client renderers in [`game.py`](../src/hexengine/game/game.py).

### Dual-field rule (text + optional html)

Every rich message should ship **plain `text` plus optional `html`**:

| Field | Role |
|-------|------|
| **`text`** | Required on `interaction_messages` rows; fallback when `html` is absent; accessibility; tests and logs |
| **`html`** | Optional HTML **fragment** (not a full document); client prefers `html` over `text` when both are non-empty |

Same rule applies to **`POPUP_MESSAGE`** hook results and **`ui_popup`** wire payloads. Do **not** put player actions in HTML (`onclick`, forms); use the **turn action dock** (`interaction_panels` `actions[]`) + `action_request`.

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
2. **Combat rows** — `UIHook.COMBAT_INTERACTION_MESSAGES` → `list[dict]` (hexdemo: [`hooks/ui.py`](../games/hexdemo/hooks/ui.py)). Context includes `shell_ui` from `game_data.toml`. When the hook returns `ENGINE_DEFAULT`, the engine builds rows from `current_segment.kind` plus `COMBAT_INSTRUCTION_FOR_VIEWER` and `ADVANCE_GATE_BANNERS_FOR_VIEWER` ([`ui_combat_messages.py`](../src/hexengine/hooks/ui_combat_messages.py)). The engine does not read title bucket `combat_gate` for banners.

`game_server` does not parse `last_combat` / `combat_gate` directly for banners (engine boundary 2). **`combat_event`** messages for retreat UI still use `last_combat` in [`_broadcast_combat_events`](../src/hexengine/server/game_server.py) — separate from INFORM.

**Full override:** `INTERACTION_MESSAGES(state, viewer_faction)` → `list[dict]` replaces the entire default list. Partial hooks are ignored when this hook is bound and does not return `ENGINE_DEFAULT`.

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
| `host` | `str` | yes | DOM element id (default `advance`) |
| `dock_arc` | `str` | no | Title-defined skin key (opaque to engine) |
| `headline` | `str` | no | Short dock title |
| `html` | `str` | no | Decorative fragment only (no inline handlers) |
| `css_class` | `str` | no | Panel root class |
| `actions` | `list` | yes | Action rows (schema below) |
| `inputs` | `list` | no | `{id, kind, label, name, default?, options?}` — merged into action `payload` on click |

**Dispatch:** `TURN_ACTION_DOCK_FOR_VIEWER(ctx)` → `list[dict]` or `ENGINE_DEFAULT` → [`default_turn_action_dock_for_viewer`](../src/hexengine/hooks/ui_turn_action_dock.py). Hexdemo: [`games/hexdemo/hooks/turn_action_dock.py`](../games/hexdemo/hooks/turn_action_dock.py).

When `title_state_extension_key` is set, **`TURN_ACTION_DOCK_FOR_VIEWER` is required**; the server never emits **`StateUpdate.primary_actions`** ([`ClientInteractionPanelsMixin`](../src/hexengine/game/arcs/client_interaction_panels.py)).

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

Gate rows (disrupt, advance, end phase) are composed inside the turn action dock via `TURN_ACTION_DOCK_FOR_VIEWER`, driven by `StateUpdate.current_segment.allowed_actions`.

### `StateUpdate.map_overlays`

Map-space DOM overlays under `#map-world`. See inline doc on [`StateUpdate`](../src/hexengine/server/protocol/server.py). Built from `UIHook.MAP_OVERLAYS` or engine default (empty list).

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `schema` | `int` | yes | **`1`** |
| `id` | `str` | yes | Stable id; replace prior overlay with same id |
| `kind` | `str` | yes | e.g. `glyph` |
| `hex` | `{i,j,k}` | yes | Map anchor |
| `text` | `str` | kind-specific | Glyph text |
| `css_class` | `str` | no | Title CSS hook |

### `ui_popup` (standalone message)

Sent on **`InspectRequest`**, not embedded in `StateUpdate`. Two hooks, one wire:

| `target_kind` | Hook | When |
|---------------|------|------|
| `unit`, `marker` | **`POPUP_MESSAGE`** | Double-click inspect, Enter on selection |
| `inform` | **`INFORM_POPUP`** | Map callouts (`context.inform_kind`, `target_id` = reason, optional `hex` / `unit_id`) |

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

**Hook return dict** (server adds `hex`): same fields except `hex`. At least one of `text` or `html` required.

Example from hexdemo [`unit_inspect_popup`](../games/hexdemo/ui_markup.py):

```python
{
    "text": "u1 | infantry | union | [3, 4]",
    "html": "<div class=\"hexdemo-unit-inspect\">…</div>",  # from templates/unit_inspect.html
    "kind": "info",
    "ttl_ms": 1500,
}
```

Use **`text` + `html`** together; the server forwards `ttl_ms` and optional `css_class` to the client popup.

### Map selection preview (`map_selection_preview_request` / `map_selection_preview`)

SELECT drafts (map/unit picks before commit) use one RPC pair. The server dispatches by **`kind`** ([`InteractionKind`](../src/hexengine/gamedef/interactions.py)) through [`map_selection_registry`](../src/hexengine/hooks/map_selection_registry.py). Full primitive model: [`TURN_ACTION_DOCK_CONTRACT.md`](TURN_ACTION_DOCK_CONTRACT.md#player-interaction-primitives).

**Client request:** [`MapSelectionPreviewRequest`](../src/hexengine/server/protocol/client.py) — `kind`, `draft` object, optional `request_id`.

**Server response:** [`MapSelectionPreviewWire`](../src/hexengine/server/protocol/server.py) — `kind`, `status_text`, `confirm_enabled`, optional `valid_target_hexes`, `eligible_attacker_ids`, `commit_payload`, `panel_actions` (same action row schema as the turn action dock).

**Feature flag:** `turn_rules.client_contract.features` includes **`map_selection_previews`** when [`bound_map_selection_kinds`](../src/hexengine/hooks/map_selection_registry.py) is non-empty for the title.

#### Kind → hook binding (registry)

| `InteractionKind` | Title hook | Draft / notes |
|-------------------|------------|---------------|
| `attack_plan` | `AttackHook.ATTACK_PLAN_PREVIEW` → `hooks.attack.attack_plan_preview` | `target_hex`, `attacker_ids`; returns `panel_actions` (hexdemo) |
| `retreat_path` | `MovementHook.RETREAT_PATH_PREVIEW` → `hooks.movement.retreat_path_preview` | `unit_id`, `path[]`; `legal_next_hexes`, stepwise `commit_payload` (hexdemo) |
| `inspect_unit` | — | Inspect uses `POPUP_MESSAGE` (INFORM), not map-selection preview |
| `place_marker` | `UIHook.PLACE_MARKER_PREVIEW` → `hooks.ui.place_marker_preview` | `marker_id`, `to_hex`; legal destinations from title rule; `MoveMarker` commit (hexdemo). Shift+click marker to start; drag unchanged. |

To add a kind: extend `InteractionKind`, register a row in [`map_selection_registry.py`](../src/hexengine/hooks/map_selection_registry.py), bind a title hook, add a client apply row in [`client_map_selection_registry.py`](../src/hexengine/game/arcs/client_map_selection_registry.py) (`_MAP_SELECTION_APPLY_METHODS`), optionally add panel-action routes in [`client_panel_actions.py`](../src/hexengine/game/arcs/client_panel_actions.py), and document draft/response fields in the title pack.

### UI hook inventory

Bind with `@bind_title_hook(UIHook.…)` in the title hooks package. Values match [`UIHook`](../src/hexengine/hooks/ui.py) enum names.

| Hook | When invoked | Signature | Return | `ENGINE_DEFAULT` behavior |
|------|--------------|-----------|--------|---------------------------|
| **`INTERACTION_MESSAGES`** | Every per-player `StateUpdate` | `(state, viewer_faction)` | `list[dict]` | Server builds default list (phase + combat + advance rows) |
| **`PHASE_BANNER_TEXT_FOR_VIEWER`** | Default message composition | `(ctx: PhaseBannerContext)` | `str` | [`default_phase_banner_text_for_viewer`](../src/hexengine/hooks/ui.py) |
| **`PHASE_BANNER_HTML_FOR_VIEWER`** | Default message composition | `(ctx: PhaseBannerContext)` | `str` | Omitted — phase row is text-only |
| **`COMBAT_INSTRUCTION_FOR_VIEWER`** | After combat with retreat context | `(ctx: CombatInteractionContext)` | `(instruction, message)` | [`default_combat_instruction_for_viewer`](../src/hexengine/hooks/ui.py) |
| **`ADVANCE_GATE_BANNERS_FOR_VIEWER`** | Active segment kind is advance gate | `(ctx: AdvanceGateInteractionContext)` | `(text_advancing, text_other)` | [`default_advance_gate_banners_for_viewer`](../src/hexengine/hooks/ui.py) |
| **`POPUP_MESSAGE`** | `InspectRequest` (`unit` / `marker`) | `(state, viewer_faction, target_kind, target_id)` | `dict` | Minimal debug text |
| **`INFORM_POPUP`** | `InspectRequest` (`inform`) | `(ctx: InformPopupContext)` | `dict` | [`default_inform_popup_for_viewer`](../src/hexengine/hooks/inform_popup.py) |
| **`MAP_OVERLAYS`** | Every per-player `StateUpdate` | `(state, viewer_faction)` | `list[dict]` | `[]` |
| **`TURN_ACTION_DOCK_FOR_VIEWER`** | Every per-player `StateUpdate` | `(ctx: TurnActionDockContext)` | `list[dict]` panels | Engine catalog ([`default_turn_action_dock_for_viewer`](../src/hexengine/hooks/ui_turn_action_dock.py)) |
| **`INTERACTION_PANELS_FOR_VIEWER`** | When dock hook not bound | `(ctx: InteractionPanelsContext)` | `list[dict]` | Engine catalog ([`ui_interaction_panels`](../src/hexengine/hooks/ui_interaction_panels.py)) |
| **`COMBAT_INTERACTION_MESSAGES`** | Default `interaction_messages` combat slice (after phase row) | `(ctx: CombatInteractionMessagesContext)` | `list[dict]` | [`default_combat_interaction_messages`](../src/hexengine/hooks/ui_combat_messages.py) using segment kind + partial combat/advance hooks |
| **`COMBAT_EVENT_SUMMARY`** | After combat, to fan out `combat_event` wires | `(state)` | `CombatEventSummary \| None` | `None` (no `combat_event` broadcast) |

**Partial vs full message hooks**

- **Partial** — customize one slice; server merges into the default `interaction_messages` list.
- **Full** — `INTERACTION_MESSAGES` replaces the entire list; do not rely on partial hooks when the full hook is bound.
- **Phase banner** — always provide sensible `text` via `PHASE_BANNER_TEXT_FOR_VIEWER` even when `PHASE_BANNER_HTML_FOR_VIEWER` supplies display HTML.

Context dataclasses: [`CombatInteractionContext`](../src/hexengine/hooks/ui.py), [`AdvanceGateInteractionContext`](../src/hexengine/hooks/ui.py), [`CombatInteractionMessagesContext`](../src/hexengine/hooks/ui_combat_messages.py), [`PhaseBannerContext`](../src/hexengine/hooks/ui.py), [`TurnActionDockContext`](../src/hexengine/hooks/ui_turn_action_dock.py).

**Phase advance blocking:** `NextPhase` legality and End Phase dock enablement derive from `current_segment.allowed_actions` ([`segment_blocks_routine_phase_advance`](../src/hexengine/arcs/segment_wire.py)). Titles with `title_state_extension_key` must bind `ArcHook.TURN_ARC_REGISTRY`.

### Attack hook inventory (combat policy)

Bind with `@bind_title_hook(AttackHook.…)`. Values match [`AttackHook`](../src/hexengine/hooks/attack.py). **There are no attack cleanup hook slots** — retreat, disrupt, and advance run through the declared combat arc (`ArcHook.COMBAT_ARC`).

For packs with `title_state_extension_key`, the engine rejects `Attack` when `current_segment` omits it for the actor **before** `validate_attack` runs (`ATTACK_BLOCKED_BY_ACTIVE_SEGMENT_MSG` in `authority_attack.py`). Title validate is rules-only (phase, LOS, CRT inputs, etc.).

| Hook | When invoked | Signature / context | Return | `ENGINE_DEFAULT` behavior |
|------|--------------|---------------------|--------|---------------------------|
| **`VALIDATE_ATTACK`** | After engine segment gate, before resolve | `(ctx: AttackContext)` | `None` or raise | Unsupported attack |
| **`RESOLVE_ATTACK`** | Combat arc `attack` segment (or imperative path without `SEG_ATTACK`) | `(ctx: AttackContext)` | `AttackResolution` or `CombatOutcome` (with embedded resolution) | Unsupported attack |
| **`ATTACK_PLAN_PREVIEW`** | `map_selection_preview` kind `attack_plan` | `(ctx: AttackPlanPreviewContext)` | preview dict | Empty/minimal preview |
| **`AUTO_ADVANCE_PHASE_AFTER_ATTACK`** | After attack applied + broadcast | `(state: GameState)` | `bool` | No auto-advance |
| **`COMBAT_OUTCOME_AFTER_APPLIED`** | After `Attack` + `ApplyCombatEffects` inside arc `attack` effect | `(ctx: AfterAttackAppliedContext)` | [`CombatOutcome`](../src/hexengine/hooks/combat_outcome.py) | No bucket follow-up |

When the combat overlay finishes (classify `done` or last cleanup step), the engine calls **`restore_routine_cursor`** so the turn slot cursor (and `NextPhase` on the routine combat segment) returns.

**Removed (do not document or bind):** `AFTER_ATTACK_APPLIED`, `ON_RETREAT_OBLIGATION_CLEARED`, `COMBAT_DISRUPT_INSTEAD_OF_RETREAT`, `COMBAT_RESOLVE_ADVANCE`, `IS_COMBAT_ADVANCE_MOVE`. Cleanup uses arc effects; advance `MoveUnit` uses [`ArcSpec.advance_move_detector`](../src/hexengine/arcs/runner.py) on `COMBAT_ARC`.

**Bucket patches:** return [`CombatOutcome`](../src/hexengine/hooks/combat_outcome.py) from `combat_outcome_after_applied` (or embed in `resolve_attack`); engine applies `PatchTitleBucket` via [`combat_outcome_apply`](../src/hexengine/server/arcs/combat_outcome_apply.py). Read bucket via [`title_bucket`](../src/hexengine/state/title_extension.py) / pack `title_state` module.

**Movement author layout:** policy in pack-root [`movement_rules.py`](../games/hexdemo/movement_rules.py) implementing [`MovementRulesBinding`](../src/hexengine/hooks/movement_rules.py); [`hooks/movement.py`](../games/hexdemo/hooks/movement.py) binds slots. Stepwise payload and arc cursor sync stay in `authority_movement` / movement arc runner.

**Combat author layout:** one [`CombatRulesBinding`](../src/hexengine/hooks/combat_rules.py) class (hexdemo: [`combat_rules.py`](../games/hexdemo/combat_rules.py)); [`combat_rules_binding_to_arc_spec`](../src/hexengine/authoring/patterns/combat.py) produces `ArcHook.COMBAT_ARC`. Bind `ArcHook.COMBAT_RULES_BINDING` for startup structural validation. Scaffold: [`games/template/combat_arc.py`](../games/template/combat_arc.py).

**Reference pack:** [`games/hexdemo/hooks/`](../games/hexdemo/hooks/) (`attack.py`, `movement.py`, `arcs.py`, `turn_action_dock.py`, `ui.py`); policy [`combat_rules.py`](../games/hexdemo/combat_rules.py), [`combat_outcome.py`](../games/hexdemo/combat_outcome.py), [`combat_actions.py`](../games/hexdemo/combat_actions.py), [`combat_transitions.py`](../games/hexdemo/combat_transitions.py), [`movement_rules.py`](../games/hexdemo/movement_rules.py), [`title_state.py`](../games/hexdemo/title_state.py). Inventory: [`SKINNING_CLIENT_INVENTORY.md`](SKINNING_CLIENT_INVENTORY.md). Boundary matrix: [`engine_game_boundary_matrix.md`](engine_game_boundary_matrix.md).

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
| **5 — Full hook override** | `INTERACTION_MESSAGES` returns complete `list[dict]` with `html` per row | Total control over banner composition |

**Wire surfaces that accept `html` (v1)**

| Surface | Hook / field | Display-only |
|---------|--------------|--------------|
| Turn banner | `interaction_messages[].html`, `PHASE_BANNER_HTML_FOR_VIEWER` | Yes |
| Inspect popup | `POPUP_MESSAGE` → `ui_popup.html` | Yes |
| Title-load splash | `[hooks.title_load]` splash resource | Yes |
| Turn action dock | `interaction_panels[].headline`, `html` (display); `actions[]` commit | `actions[]` → `action_request` |

**Do not:** raw f-string HTML without escape; inline `onclick`; Jinja in v1; live `GameState` copy in static TOML.

---

## Target model (not fully implemented)

Authors should be able to answer, without reading engine internals:

1. **Which hooks does my pack implement?** (required vs optional vs engine default)
2. **What is each hook’s signature and when does it run?** (arc segment, server RPC, client-only, …)
3. **What fails if I get it wrong?** — prefer **fail at pack load / server start / typecheck**, not mid-match or silent skip.
4. **Which UX mode is active?** — one **segment presentation registry** row per `kind` (primitive, `presentation_id`, optional `interaction_mode`, inform profile) — see [`TITLE_AUTHORING.md` § Segment presentation registry](TITLE_AUTHORING.md#segment-presentation-registry).

Planned mechanisms (apply across **both** systems over time):

### 1. Explicit contracts

- **Required vs optional** per hook point (not inferred only from “table present” in TOML).
- Document **arc segment** (engine) vs **pack hook** (title) for client flows — same vocabulary as [`hexengine.game.arcs.client_title_load`](../src/hexengine/game/arcs/client_title_load.py).
- Extend `validate_title_contract` (or siblings) for more schedule/hook combinations, not only combat/attack.
- **Segment UI registry (P5):** every explicit `kind` used in declared arcs has a registry row — enforced at startup when `SEGMENT_PRESENTATION_REGISTRY` is bound.

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
| Attack | `TitleHooks.attack` | [`authority_attack`](../src/hexengine/server/arcs/authority_attack.py); `validate_title_contract` if schedule has combat | Required `validate_attack` / `resolve_attack` when schedule implies combat; optional `combat_outcome_after_applied`; cleanup via `ArcHook.COMBAT_ARC` — see [Attack hook inventory](#attack-hook-inventory-combat-policy) |
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
