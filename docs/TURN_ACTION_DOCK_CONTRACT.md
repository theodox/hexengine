# Turn action dock — contract

Titles with `session_state_key` **must** bind **`TURN_ACTION_DOCK_FOR_VIEWER`** (contract validation). The server emits commit UI on **`StateUpdate.interaction_panels` only** — no `primary_actions` fallback. The client merges preview **`panel_actions`** into panel `turn_actions`.

**Authors:** [`TITLE_AUTHORING.md`](TITLE_AUTHORING.md) (hub) · **Related:** [`PACK_HOOK_CONTRACTS.md`](PACK_HOOK_CONTRACTS.md), [`SKINNING_AFFORDANCES_PLAN.md`](SKINNING_AFFORDANCES_PLAN.md), [`map_selection_preview`](#relationship-to-map_selection_preview).

---

## Purpose

Players need one place to **commit** turn decisions (end phase, disrupt, confirm attack, etc.). Titles differ in how many branches exist between commits; hexdemo is a small tree, future titles may be larger.

The **turn action dock** is the title-owned description of that commit UI. The engine renders it and sends `action_request`; the title decides which actions exist, which are enabled, and how each branch is skinned.

---

## Three lanes (do not collapse)

| Lane | Transport | Title owns | Engine owns |
|------|-----------|------------|-------------|
| **Tell** | `StateUpdate.interaction_messages` (+ optional `ui_popup`) | Copy, banner HTML, priority/kinds | Merge partial hooks; client picks one visible row |
| **Commit** | `StateUpdate.interaction_panels` via **`TURN_ACTION_DOCK_FOR_VIEWER`** | Full dock: panels, actions, enablement, `presentation_id` skin | Render panel; wire buttons to `action_request` |
| **Map pick** | `map_selection_preview_request` / `map_selection_preview` | Per-`InteractionKind` legality + `commit_payload` | RPC routing; optional `panel_actions` on preview |

**Rule:** Tell is for status and narrative. The dock is for buttons. Map pick validates drafts; the dock (or preview `panel_actions`) ratifies them.

**Rule:** Do not put `onclick` or forms in dock `html`. Every commit is an `actions[]` row → `action_request`.

---

## Draft locus (invariant)

Map SELECT drafts are **client-local until commit**. The server never persists in-progress draft in `GameState` or `session_state` by default.

| Layer | Owns | Does not own |
|-------|------|--------------|
| **Client** | Draft input, cancel/undo, draft-step skin and headline, `_map_selection_preview` cache | Authoritative match state |
| **Preview RPC** | Legality opinion on a draft **snapshot** (`status_text`, `panel_actions`, `commit_payload`, highlights) | Stored draft |
| **Dock hook** | Baseline panel from authoritative segment + turn (`presentation_id`, gate `actions[]`) | Client draft |
| **Commit** | `action_request` + title validators → `GameState` / bucket / arc cursor | — |

**Rules**

- **Preview consults; commit authorizes.** Each `map_selection_preview_request` sends a snapshot; the preview hook answers for that snapshot only.
- **`TURN_ACTION_DOCK_FOR_VIEWER` has no draft field** by design ([`TurnActionDockContext`](../src/hexengine/hooks/ui_turn_action_dock.py)).
- **Ratify buttons** come from preview `panel_actions` merged on the client, or from local panel routes ([`client_panel_actions.py`](../src/hexengine/game/arcs/client_panel_actions.py)) that still end in `action_request` with re-validation.
- **Draft-step presentation ids** (e.g. `attack_draft`) are **client-only** skins while a local SELECT is active; the server wire stays at the idle `presentation_id` (`attack_ready`, `retreat_gate`, …).

Titles that need pre-commit server-visible state must opt in explicitly (e.g. `session_state` keys) and document that escape hatch; it is not the default SELECT model.

See also: [`archive/COMPOSABLE_ARCS_PLAN.md` § Drafts are nested client-local sub-arcs](archive/COMPOSABLE_ARCS_PLAN.md#drafts-are-nested-client-local-sub-arcs-not-guards).

---

## Player interaction primitives

Titles expose many player-facing flows; the engine reuses a small set of **primitives**. Map pick and the dock are two transports; primitives describe **what the player is doing**, not separate wire types.

### Primitive catalog

| Primitive | Meaning | Primary transport | Typical commit |
|-----------|---------|-------------------|----------------|
| **INFORM** | Status, narrative, “what’s going on” | `interaction_messages`, optional `ui_popup`; dock `headline` / decorative `html` | None (display only) |
| **SELECT** | Build or change a **draft** the title will validate | `map_selection_preview_request` / `map_selection_preview` (units and/or map) | Deferred until ratified |
| **DECIDE** | Choose among discrete options and **commit** | Dock `actions[]` and/or `inputs[]` → `action_request` | Immediate on click (or after inputs merged) |
| **SEQUENCE** | Ordered steps of INFORM → SELECT → DECIDE (repeat) | Title session + `presentation_id` / step index; not a fifth wire | Per-step commits |

**Composition rule:** SEQUENCE is title-orchestrated composition of the other three. The engine does not need a `sequence` RPC; the title advances steps and swaps `presentation_id`, preview `InteractionKind`, and banner copy.

### Mapping common title flows

| Player-facing flow | Primitives involved |
|--------------------|---------------------|
| Turn banner / combat CRT | INFORM |
| Pick attackers + target hex (attack plan) | SELECT (units + map) → DECIDE (Confirm / Cancel via preview `panel_actions` merged into dock) |
| Mandatory multi-hex retreat | SELECT (`retreat_path`, click-extend) → DECIDE (Confirm / Cancel / Undo on dock) |
| End phase / disrupt / combat advance | DECIDE (dock only) |
| Inspect unit popup | `INFORM_POPUP` |
| Yes/no or enumerated choice (no map) | DECIDE (`actions[]` or `inputs[]` + confirm row) |
| “Pick path, then confirm” wizard | SEQUENCE: INFORM → SELECT (path) → DECIDE |
| “Pick ammunition, then path, then confirm” | SEQUENCE: DECIDE (inputs) → SELECT → DECIDE |
| Scripted event / season card (must dismiss) | SEQUENCE: INFORM (dock `html`) → DECIDE (Acknowledge or branch) |

### Player prompts

A **player prompt** is a title-authored beat where the player reads copy (optional graphics) and commits via the dock. It is **not** a new wire type or primitive. It is a **prompt sequence**: one or more INFORM steps (banner and/or dock `headline` / `html`) followed by DECIDE (`actions[]` → `action_request`).

Blocking scripted events (season cards, scenario intros, “click Continue”) use this pattern:

| Piece | Author with |
|-------|-------------|
| Copy + image | Dock `headline` + `html` from `resources/templates/` (HTML ladder); optional `interaction_messages` for a banner line |
| Acknowledge / choice | DECIDE: one or more dock action rows (e.g. `AcknowledgeEvent`, branch A / B) |
| Skin key | `presentation_id` (e.g. `event_prompt`) — opaque to engine; pack CSS may center or modal-style the panel |
| Queue / script id | Session state (`session_state`); not client-readable for legality |

Do **not** use `ui_popup` for blocking prompts — that lane is hex-anchored, ephemeral INFORM. Do **not** put `onclick` in prompt HTML; every commit is a dock action row.

Longer flows add SELECT between INFORM and DECIDE (attack plan, retreat path). Authority-side blocking is a **prompt segment** in the turn arc — see [`archive/COMPOSABLE_ARCS_PLAN.md` § Prompt segments](archive/COMPOSABLE_ARCS_PLAN.md#prompt-segments).

### SELECT — draft shapes (same wire, title policy)

`map_selection_preview_request` carries `kind` (`InteractionKind`) and a title-defined **`draft`** object. The preview hook interprets shape and returns legality, highlights, and optional `commit_payload`.

| Draft shape | Example fields | Player gesture |
|-------------|----------------|----------------|
| **Single hex** | `target_hex`, `hex` | One map click |
| **Multi-hex set** | `hexes: [...]` | Repeated clicks / toggles (order usually irrelevant) |
| **Ordered path** | `path: [{i,j,k}, ...]` or `from_hex` / `to_hex` | Click-to-extend, or drag along hexes |
| **Unit(s)** | `attacker_ids`, `unit_ids` | Unit clicks |
| **Combined** | path + units + kind-specific keys | Attack plan, convoy route, placement + facing, etc. |

New `InteractionKind` values (e.g. `attack_plan`, `place_structure`, `trace_path`, `bombard_corridor`) select which hook runs; they do **not** imply a new top-level primitive.

### SELECT — path selection (subset of map SELECT)

**Hex path selection is map SELECT with an ordered path draft**, not a separate primitive beside INFORM / SELECT / DECIDE / SEQUENCE.

| Concern | Title-owned (preview hook + rules) | Engine-owned (v1) |
|---------|--------------------------------------|---------------------|
| How path is built | Click-to-extend, drag sampling, endpoints-only (server A*), undo last hex | Route `map_selection_preview` by `kind`; render highlights from response |
| When it commits | Confirm after complete path vs commit on drop | Same `action_request` validation as any commit |
| Path vs unordered set | Adjacency, max length, LOS along chain, fixed start/end | Same RPC; different `validate_*` in title |

**Path building modes (illustrative):**

| Mode | Draft growth | Preview role |
|------|--------------|--------------|
| Click-to-extend | Append hex on each click | `legal_next_hexes` (or equivalent) from path tip |
| Drag along hexes | Client samples hexes under cursor | Validate on drop and/or stream preview like move drag |
| Endpoints only | `{ start, end }` | Server returns normalized `preview_path_hexes`, `confirm_enabled` |
| Edit / undo | Pop last hex or branch | `status_text`, invalid suffix handling |

**Commit patterns for paths:**

| Pattern | Fits primitives as |
|---------|-------------------|
| Confirm path | SELECT builds draft → preview sets `confirm_enabled` + `commit_payload` → DECIDE (Confirm) → `action_request` with full path |
| Commit on drop | SELECT during drag; single RPC on drop (move/retreat today via `unit_preview`, not `map_selection_preview`) |

**Preview response fields (conceptual extensions for path kinds):**

| Field | Use |
|-------|-----|
| `legal_next_hexes` | Hexes legal to append from current path tip |
| `path_valid` / `confirm_enabled` | Whole draft passes title rules |
| `preview_path_hexes` | Server-normalized path (snap, simplify) |
| `through_hexes` | Highlight chain (retreat “through” already uses similar highlighting) |
| `commit_payload` | Wire-ready path for Confirm |
| `panel_actions` | Confirm, Cancel, Undo last hex (same action row schema as dock) |

**Path vs multi-hex set:** unordered sets answer “any of these”; ordered paths answer “this chain in order” (adjacency, length caps, corridor rules).

**Existing code alignment:**

| Today | Primitive reading |
|-------|-------------------|
| Attack plan (`attack_plan` + `ATTACK_PLAN_PREVIEW`) | SELECT (units + target hex) + DECIDE merge via `panel_actions` |
| Mandatory retreat path (`retreat_path` + `RETREAT_PATH_PREVIEW`) | SELECT (ordered `path` draft, click-to-extend) + DECIDE (Confirm / Cancel / Undo on dock) |
| Move / optional one-hop retreat drag (`unit_preview_request`) | Path-like SELECT for one unit + budget; **commit on drop** (no dock Confirm) |
| Future path kinds (placement, corridors, …) | Same `map_selection_preview` lane; register kind + client apply handler |

### SELECT → DECIDE ratify

1. Client holds draft locally; sends `map_selection_preview_request` on changes.
2. Server returns legality, map highlights, `status_text`, `confirm_enabled`, `commit_payload`, optional **`panel_actions`**.
3. Client merges `panel_actions` into dock `actions[]` (see [Client merge](#client-behavior)).
4. Confirm dispatches via [`client_panel_actions.py`](../src/hexengine/game/arcs/client_panel_actions.py): **`preview_commit`** routes (e.g. `Attack` → `commit_payload`) or **`local`** routes (e.g. `retreat_path_confirm` → `confirm_retreat_path()`), else default `action_request` with row `payload` + dock `inputs[]`.

The dock hook does not receive draft ([draft locus](#draft-locus-invariant)); baseline dock buttons and draft-ratify buttons coexist via client merge.

### Client draft presentation

`presentation_id` is an opaque skin key on the dock panel wire. The server hook returns the **idle** skin for the active segment (`attack_ready`, `retreat_gate`, …). Engine does not interpret step graphs.

While a **client-local** map SELECT draft is active, the browser overrides effective `presentation_id` and headline on panel `turn_actions` (CSS modifier + `.hexengine-panel__headline`). These draft skins are not sent by the server hook:

| Server `presentation_id` | Client draft active | Effective `presentation_id` | Headline source |
|--------------------------|---------------------|----------------------------|-----------------|
| `attack_ready` | Attack plan (target and/or attackers) | `attack_draft` | Preview `status_text`, or target-set fallback |
| `attack_ready` | None (Combat idle) | `attack_ready` | `shell_ui.attack_pick_target_status` |
| `retreat_gate` | Retreat path picking | `retreat_path_draft` | Preview `status_text` |
| `retreat_gate` | None | `retreat_gate` | Server `headline` + optional gate `html` |

Coaching copy for attack and retreat drafting lives on the **dock headline**, not a separate status strip. Map chrome (LOS lines, retreat polyline) stays on the map layer.

---

## Hook

### `UIHook.TURN_ACTION_DOCK_FOR_VIEWER`

| | |
|--|--|
| **When** | Every per-recipient `StateUpdate` |
| **Binding** | `@bind_title_hook(UIHook.TURN_ACTION_DOCK_FOR_VIEWER)` in the title hooks package |
| **Returns** | `list[TurnDockPanel]` from `hexengine.authoring.present`, or `ENGINE_DEFAULT` (engine serializes to wire; schema below) |

### `TurnActionDockContext`

Frozen dataclass in [`ui_turn_action_dock.py`](../src/hexengine/hooks/ui_turn_action_dock.py):

| Field | Type | Notes |
|-------|------|-------|
| `state` | `GameState` | Authoritative match state |
| `viewer_faction` | `str \| None` | Recipient faction |
| `session_state_key` | `str \| None` | From `GameData.session_state_key` |
| `shell_ui` | `Mapping[str, Any]` | Declarative labels from `GameData` |
| `schedule_index` | `int` | Current rota index |
| `current_faction` | `str` | Turn owner |
| `current_phase` | `str` | e.g. `Move`, `Combat` |
| `phase_actions_remaining` | `int` | Actions left in current phase slot |
| `viewer_is_turn_owner` | `bool` | `viewer_faction == current_faction` |
| `client_contract_features` | `frozenset[str]` | e.g. `map_selection_previews`, `attack_planning_ui` |
| `current_segment` | `dict \| None` | Per-viewer segment projection (`allowed_actions`, `presentation_id`, …) |

The hook **does not** receive client-local draft state ([draft locus](#draft-locus-invariant)). Confirm/Cancel rows are merged on the client from the last `map_selection_preview` (see [Client merge](#client-behavior)).

Titles set **`presentation_id`** for skinning (engine does not enumerate values).

---

## Panel wire schema (`schema: 1`)

Each list entry is one panel. v1 uses a single panel on host `user-controls`; multi-panel lists are allowed for wizards or stacked UI in complex titles.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `schema` | `int` | yes | Always **`1`** |
| `id` | `str` | yes | Stable panel id (convention: `turn_actions`) |
| `host` | `str` | yes | DOM host element id. Default **`user-controls`** (`#user-controls` in `hexes.html`) |
| `presentation_id` | `str` | no | **Title-defined** idle skin key (e.g. `routine`, `retreat_gate`, `attack_ready`). Opaque to engine. Used for templates/CSS. Draft skins (`attack_draft`, …) are client-only overlays — see [Client draft presentation](#client-draft-presentation). |
| `headline` | `str` | no | Short dock title (plain text). Long CRT stays in `interaction_messages`. |
| `html` | `str` | no | Decorative fragment only. Escape dynamic values. |
| `css_class` | `str` | no | Panel root classes (e.g. `mytitle-dock mytitle-dock--retreat-gate`) |
| `actions` | `list` | yes | Button rows (schema below). May be empty only if dock is intentionally hidden. |
| `inputs` | `list` | no | Optional form fields merged into clicked action `payload` |

**Empty list:** No dock panels → client shows no commit card on `host`.

**Multiple panels:** Allowed. Client mounts each on `host` in list order (insertion order TBD in client; document in implementation).

### Example panel (routine turn, hexdemo-shaped)

```json
{
  "schema": 1,
  "id": "turn_actions",
  "host": "user-controls",
  "presentation_id": "routine",
  "headline": "Your turn",
  "html": "<div class=\"hexdemo-dock-hint\">…</div>",
  "css_class": "hexdemo-turn-dock hexdemo-turn-dock--routine",
  "actions": [
    {
      "schema": 1,
      "id": "end_phase",
      "action_type": "NextPhase",
      "label": "End Phase",
      "title": "Advance to the next phase in the schedule.",
      "payload": {},
      "css_class": "hexengine-primary-action--end-phase",
      "enabled": true,
      "group": "primary"
    }
  ],
  "inputs": []
}
```

---

## Action row schema (`schema: 1`)

Same shape as [action rows](PACK_HOOK_CONTRACTS.md#action-row-schema-shared) with optional layout hints.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `schema` | `int` | yes | **`1`** |
| `id` | `str` | yes | Stable; client upserts by `id` |
| `action_type` | `str` | yes | Must be a server-accepted `action_request` type (e.g. `NextPhase`, `CombatAdvance`, `Attack`, `CombatDisruptInsteadOfRetreat`) |
| `label` | `str` | yes | Button face text |
| `title` | `str` | no | Tooltip |
| `payload` | `object` | no | Default `{}`. Server validates on RPC. For `Attack`, prefer client using `commit_payload` from preview when draft-driven. |
| `css_class` | `str` | no | Button modifier |
| `enabled` | `bool` | yes | `false` → visible disabled |
| `group` | `str` | no | Layout hint: `primary`, `secondary`, `danger`. Client may sort or style; unknown values ignored. |
| `order` | `int` | no | Optional sort key within panel; lower first |

**Client-only / special dispatch:** Registered in [`client_panel_actions.py`](../src/hexengine/game/arcs/client_panel_actions.py) (`PANEL_ACTION_ROUTES`). Titles should not rely on the server accepting these as ordinary RPCs:

| Match | Dispatch | Behavior |
|-------|----------|----------|
| `AttackPlanCancel` | local | Clear attack-plan draft |
| `RetreatPathCancel` / `RetreatPathUndo` | local | Clear or pop retreat path draft |
| `id: retreat_path_confirm` | local | `confirm_retreat_path()` (uses preview `commit_payload` internally) |
| `PlaceMarkerCancel` | local | Clear place-marker relocate draft |
| `id: place_marker_confirm` | local | `confirm_place_marker()` → `MoveMarker` with preview `commit_payload` |
| `Attack` (when preview `confirm_enabled`) | preview_commit | `execute_action_request("Attack", commit_payload)` then clear draft |

Unregistered rows: `execute_action_request(action_type, payload ∪ inputs)`.

**`NextPhase` payload:** Empty `{}` on wire. Client or server builds the concrete `NextPhase` action from `GameDefinition` + `state.turn`.

---

## `ENGINE_DEFAULT` behavior

When the hook returns `ENGINE_DEFAULT`, the server uses [`default_turn_action_dock_for_viewer`](../src/hexengine/hooks/ui_turn_action_dock.py):

1. **`end_phase`** (`NextPhase`) when `NextPhase` is in the segment's allowed set (or when no segment descriptor is present); otherwise shown disabled.
2. One panel: `id: turn_actions`, `host: user-controls`, `presentation_id` from enriched `current_segment` when present; otherwise `routine` (turn owner) or `hidden`. Titles with `session_state_key` must bind `ENRICH_CURRENT_SEGMENT`.

The catalog default does **not** inject combat cleanup gate rows (Disrupt / Advance / Skip). Titles using [`build_combat_cleanup_arc`](../src/hexengine/authoring/patterns/combat.py) call [`combat_gate_panel_actions`](../src/hexengine/authoring/patterns/combat.py) from their dock hook (hexdemo: [`turn_action_dock.py`](../games/hexdemo/hooks/turn_action_dock.py)).

Titles that bind **`TURN_ACTION_DOCK_FOR_VIEWER`** replace this composition.

---

## Server dispatch

On each `StateUpdate` per player:

```
panels = hooks.ui.turn_action_dock(ctx)
if panels is ENGINE_DEFAULT:
    panels = catalog_default_turn_action_dock(ctx)
state_update.interaction_panels = panels or None
# primary_actions omitted when turn_action_dock_for_viewer is bound
```

**Validation (startup / optional runtime):**

- Every `action_type` in default dock for this pack's schedule should be accepted by `GameServer` action handling (document per pack).
- `presentation_id` is not validated by engine (title vocabulary).

**Authority:** Only actions the server would accept on `action_request` may appear with `enabled: true`. Titles must not offer Confirm Attack when `validate_attack` would fail.

---

## Client behavior

### Host

- DOM: `#user-controls` (class `hexengine-primary-actions`), `flex-direction: column-reverse`.
- All commit buttons live under panel `actions` hosts (`.hexengine-panel__actions`).

### Rendering

- Reuse [`ClientInteractionPanelsMixin`](../src/hexengine/game/arcs/client_interaction_panels.py).
- `.hexengine-panel__headline` — server `headline`, then client draft presentation overrides (see [Client draft presentation](#client-draft-presentation)).
- `html` → `.hexengine-panel__html` via `innerHTML` (trusted title content).
- `actions[]` → buttons; click → [`resolve_panel_action_route`](../src/hexengine/game/arcs/client_panel_actions.py) or default RPC.
- `_sync_turn_action_dock_sequence_skin()` — effective `presentation_id` CSS + `data-presentation-id` on panel root.

### Map selection apply handlers

Preview responses are applied by kind via [`client_map_selection_registry.py`](../src/hexengine/game/arcs/client_map_selection_registry.py) (`_MAP_SELECTION_APPLY_METHODS`). New kinds: add a row `(InteractionKind, "_apply_<kind>_preview")` and implement the method on the game mixin.

### Map selection merge

When **`map_selection_previews`** is in `client_contract.features` and the client holds an active draft for a kind (e.g. `attack_plan`):

1. Client sends `map_selection_preview_request` on draft changes.
2. On `map_selection_preview`, read optional **`panel_actions`** from response.
3. **Merge** into the dock panel's action strip: preview actions override same `id`; preview-only ids appended; server dock actions remain unless same `id`.
4. **End Phase** on the dock is disabled while attack-plan or retreat-path drafts are active (client policy; see [draft locus](#draft-locus-invariant)).
5. Confirm uses the panel-action registry (`preview_commit` or local confirm handlers).

### Feature flags

| Feature | Meaning |
|---------|---------|
| `map_selection_previews` | Preview RPC + merge `panel_actions` into dock |
| `attack_planning_ui` | Map clicks for attack draft (client); requires `map_selection_previews` for confirm enablement |

---

## Skinning by `presentation_id` (title convention)

Engine treats `presentation_id` as an opaque string. Recommended pack layout:

```
games/<pack>/resources/
  templates/dock/<presentation_id>.html   # optional; fallback to generic dock.html
  ui.css                         # .<pack>-turn-dock--<presentation_id> { … }
```

| Mechanism | Use |
|-----------|-----|
| `presentation_id` | Choose template + CSS modifier (idle segment skin from server hook) |
| `headline` | Plain short title in dock chrome |
| `html` | Extra hint markup from template |
| `shell_ui` | Labels keyed by convention, e.g. `dock_<arc>_hint`, `end_phase_label` |
| `css_class` | Panel root; include arc modifier |

**Do not** encode game rules in CSS class names only — keep enablement on `actions[].enabled`.

---

## Hexdemo reference skins (example vocabulary)

Illustrative `presentation_id` values for [`games/hexdemo`](../games/hexdemo/); not enforced by engine.

| `presentation_id` | When | Typical `actions` | End Phase |
|------------|-------------------|-------------------|-----------|
| `hidden` | Not viewer's turn / spectator | `[]` (empty panel list) | — |
| `routine` | Your turn, routine segment (`NextPhase` allowed) | `end_phase` | enabled |
| `attack_ready` | Combat phase, attack segment (hexdemo) | `end_phase`; preview merge when drafting | enabled (client disables while draft active) |
| `attack_draft` | **Client override** while attack-plan draft active (server may still send `attack_ready`) | Merged `attack_plan_confirm`, `attack_plan_cancel` | disabled on client |
| `retreat_gate` | Retreat segment active for viewer (`retreat_obligations` and/or disrupt gate) | `combat_disrupt_instead`, `end_phase` (disabled) | disabled |
| `retreat_path_draft` | **Client override** while `retreat_path` SELECT active | Merged Confirm / Cancel / Undo | disabled on client |
| `place_marker_draft` | **Client override** while `place_marker` SELECT active (Shift+click marker) | Merged Confirm / Cancel | disabled on client |
| `advance_gate` | Advance segment active, viewer is advancing faction | `combat_advance` | disabled |

**Retreat fulfillment (hexdemo):** Multi-hex mandatory retreat uses **`retreat_path`** click-extend + dock Confirm (stepwise `MoveUnit`). One-hop retreat may still use **unit drag** (`unit_preview`, commit on drop). CRT / phase flavor stays in **`interaction_messages`**; short “what to do” copy is on the dock **`headline`** during gates and drafts.

---

## Relationship to map_selection_preview

| Message | Role |
|---------|------|
| [`map_selection_preview_request`](../src/hexengine/server/protocol/client.py) | Client → server: `kind` (`InteractionKind`), `draft` object |
| [`map_selection_preview`](../src/hexengine/server/protocol/server.py) | Server → client: legality, `status_text`, `confirm_enabled`, `commit_payload`, optional **`panel_actions`** |

**`InteractionKind` (map preview registry):** `attack_plan`, `retreat_path`, `place_marker` ([`gamedef/interactions.py`](../src/hexengine/gamedef/interactions.py), server [`map_selection_registry.py`](../src/hexengine/hooks/map_selection_registry.py), client [`client_map_selection_registry.py`](../src/hexengine/game/arcs/client_map_selection_registry.py)). `inspect_unit` uses `INFORM_POPUP`, not map-selection preview. Marker drag still uses `marker_preview_request`; click-confirm relocate uses `place_marker` + dock Confirm. New kinds: extend `InteractionKind`, register server row + client apply method — see [PACK_HOOK_CONTRACTS.md § Map selection preview](PACK_HOOK_CONTRACTS.md#map-selection-preview_map_selection_preview_request--map_selection_preview).

**Contract alignment:** Preview `panel_actions` use the **same action row schema** as the dock. The dock hook supplies baseline buttons; preview supplies draft-ratify buttons.

**Not the same as drag preview:** `unit_preview_request` / `marker_preview_request` serve move/retreat/marker drag (commit on drop). Generalized SELECT–confirm flows use `map_selection_preview` even when the UX feels path-like; titles may unify policy in one preview module over time.

---

## `interaction_messages` interaction

Partial hooks remain valid for **tell**:

- `PHASE_BANNER_*`, `COMBAT_INSTRUCTION_*`, `ADVANCE_GATE_BANNERS_*` still compose banner rows.
- Prefer moving short “what to do now” into `dock.headline` over time; banner keeps CRT and phase flavor.

Full **`INTERACTION_MESSAGES`** override still replaces the entire banner list; independent of dock hook.
