# Title authoring guide

**Combat / movement author interface (done):** hexdemo uses one `CombatRulesBinding` in [`combat/rules.py`](../games/hexdemo/combat/rules.py) and movement policy in [`movement/rules.py`](../games/hexdemo/movement/rules.py); see [§ Modification vs interaction](#modification-vs-interaction) and [§ Combat and movement (hexdemo)](#combat-and-movement-hexdemo). Phase history: [`archive/TITLE_AUTHOR_INTERFACE_PLAN.md`](archive/TITLE_AUTHOR_INTERFACE_PLAN.md).

**Start here** if you are building or extending a game pack (title) on hexengine. This page gives **high-level summaries** and **API entry points**; deep wire schemas and client behavior live in linked contract docs.

**Reference pack:** [`games/hexdemo/`](../games/hexdemo/) — copy patterns from code when docs and implementation disagree; prefer updating this guide when behavior changes.

---

## What you are building

A **title pack** is a self-contained game: scenario TOML, `resources/`, Python under `games/<pack_id>/`, and `hexengine_pack.toml`. The **server is authoritative** for legality and state; the **browser client** renders wire payloads and sends `action_request`. Your pack supplies **policy** (rules) and **presentation** (copy, HTML, which buttons exist) through **hooks** the engine calls at known times.

| Layer | You own | Engine owns |
|-------|---------|-------------|
| Match rules | `GameDefinition`, hooks, rules modules, declared arcs | Arc runner, cursor, RPC routing (see [`ENGINE_TITLE_CHARTER.md`](ENGINE_TITLE_CHARTER.md)) |
| Scenario | `scenarios/*/scenario.toml`, placements | Loader schema, initial `GameState` |
| Player UX | Messages, dock, previews, templates, CSS | DOM hosts, RPC routing, merge/render |
| Trust | Same process as server today — treat pack code as trusted | See [`PACK_TRUST_MODEL.md`](PACK_TRUST_MODEL.md) |

---

## Vocabulary: pack, title, client, server

Docs and code use four layers; they are not interchangeable.

| Term | Means | Typical locations / APIs |
|------|--------|---------------------------|
| **Pack** | On-disk game unit: `games/<pack_id>/`, `hexengine_pack.toml`, `resources/`, scenario TOML | `hexengine.game_packs`, `pack.id`, `PACK_*` contract docs |
| **Title** | Author’s match logic and presentation: rules, declared arcs, `TitleHooks`, `GameDefinition` — runs in the **server** process | `games/<pack_id>/hooks/`, `combat/rules.py`, `TitleHooks`, `validate_title_contract` |
| **Title pack** | Both: the thing you ship (pack layout + title code). Preferred when talking to authors | “Build a title pack”, `games/hexdemo/` |
| **Server** | Authoritative match: arc runner, RPC routing, `GameState`, wire assembly | `hexengine.server`, `GameServer` |
| **Client** | Thin **browser** runtime: renders `StateUpdate`, holds map/dock drafts, sends `action_request` | `hexengine.game`, `client_*` modules, `client_contract` in `game_data.toml` |

**Not the same:**

- **Client ≠ title** — the browser does not run `combat/rules.py` or `TitleHooks`; it consumes wire and manifest data (`ClientTitleData`, `client_title_load`).
- **Pack ≠ client** — pack Python executes on the server; the client reads `client_contract` and assets from the pack directory.
- **Title ≠ server** — the title supplies policy and content; the engine owns mechanics titles must not reimplement (`hexengine.server.*` internals).

When a module name says `client_title_*`, that is **title manifest on the client** (splash, contract features), not “the client instead of the server.”

**Title arc imports:** pack Python should use `hexengine.arcs` for declarative types (Arc, ArcContext, ArcSpec, …) and `hexengine.arcs.title.*` for match-runtime helpers (lookup, attack commit, segment projection). Do not import `hexengine.server` for those. See `hexengine.arcs.title` package docstring.

Normative ownership detail: [`ENGINE_TITLE_CHARTER.md`](ENGINE_TITLE_CHARTER.md).

---

## Modification vs interaction

Two **families** frame hook and RPC design: `ModificationHook` / `TitleHooks.modification` and `InteractionHook` / `TitleHooks.interaction`.

| Family | Meaning | Core wire verb | Hook enum | Required? |
|--------|---------|----------------|-----------|-----------|
| **Modification** | One entity’s board state changes (chiefly locomotion) | `MoveUnit` | `ModificationHook` | Yes for typical hex titles |
| **Interaction** | Two or more parties; resolution may spawn follow-up changes | `Attack` (one kind today) | `InteractionHook` + interaction arc | **Optional** — a move-only title is valid |
| **Board modification** | Markers, terrain, placement | `MoveMarker`, … | Marker/placement hooks | Title-specific |

**Modification** is the baseline: most titles need legal unit movement and configure when/how via movement policy and routine arc segments.

**Interaction** is opt-in: no wargame combat, no `Attack` segment, and no interaction arc is a complete title when you do not declare those pieces. The engine rejects illegal RPCs at the **active segment**, not as “misconfigured title.”

Follow-up moves after interaction (retreat steps, combat advance) are **modifications** authorized by an **interaction aftermath** arc segment, not a second interaction.

**Where to read in hexdemo:**

| Family | Flow (arcs) | Policy (rules) | Hook adapters |
|--------|-------------|----------------|---------------|
| Modification | [`arcs/turn_schedule.py`](../games/hexdemo/arcs/turn_schedule.py) routine segments | [`movement/rules.py`](../games/hexdemo/movement/rules.py) | [`hooks/modification.py`](../games/hexdemo/hooks/modification.py) |
| Interaction | [`combat/graph.py`](../games/hexdemo/combat/graph.py) overlay FSM | [`combat/rules.py`](../games/hexdemo/combat/rules.py) | [`hooks/interaction.py`](../games/hexdemo/hooks/interaction.py), [`arcs/wiring.py`](../games/hexdemo/arcs/wiring.py) |

Normative boundary: [`ENGINE_TITLE_CHARTER.md`](ENGINE_TITLE_CHARTER.md).

---

## Reading order

| Step | Doc | Why |
|------|-----|-----|
| 1 | This page | Map of concepts and APIs |
| 2 | [`ENGINE_TITLE_CHARTER.md`](ENGINE_TITLE_CHARTER.md) | Engine vs title ownership and arc-first flow (normative) |
| 3 | [`games/hexdemo/README.md`](../games/hexdemo/README.md) | Pack layout, PYTHONPATH, `game_config` |
| 4 | [`games/hexdemo/hooks/README.md`](../games/hexdemo/hooks/README.md) | Rules vs hooks, three wiring paths |
| 5 | [`TURN_ACTION_DOCK_CONTRACT.md`](TURN_ACTION_DOCK_CONTRACT.md) | Player primitives + three wire lanes |
| 6 | [`PACK_HOOK_CONTRACTS.md`](PACK_HOOK_CONTRACTS.md) | Wire field tables + hook inventory |
| 7 | [`SKINNING_CLIENT_INVENTORY.md`](SKINNING_CLIENT_INVENTORY.md) | Which client module does what |
| 8 | [`engine_game_boundary_matrix.md`](engine_game_boundary_matrix.md) | Server vs title per domain |
| 9 | [`TITLE_LOAD_HOOKS.md`](TITLE_LOAD_HOOKS.md) | Splash / setup manifest hooks |
| 10 | [`games/hexdemo/arcs/README.md`](../games/hexdemo/arcs/README.md) | Turn rota + arc hook wiring |
| 11 | [`games/hexdemo/combat/README.md`](../games/hexdemo/combat/README.md) | Interaction aftermath graph (if combat) |

**Planning only (not API):** [`SKINNING_AFFORDANCES_PLAN.md`](SKINNING_AFFORDANCES_PLAN.md) (roadmap/status), [`RULE_COMPOSITION.md`](RULE_COMPOSITION.md) (future rule catalog). Doc index and archived plans: [`README.md`](README.md), [`archive/README.md`](archive/README.md).

### Pack reading order (hexdemo, flow-first)

Use this when tracing **match shape** inside the reference pack (mirrors [`ENGINE_TITLE_CHARTER.md` § Author reading order](ENGINE_TITLE_CHARTER.md#author-reading-order-flow-centric)):

| Order | Path | Question |
|-------|------|----------|
| 1 | [`arcs/turn_schedule.py`](../games/hexdemo/arcs/turn_schedule.py) | When does each faction act? |
| 2 | [`combat/graph.py`](../games/hexdemo/combat/graph.py) | What happens after interaction commit? (skip if move-only) |
| 3 | [`arcs/wiring.py`](../games/hexdemo/arcs/wiring.py) | How is flow exposed on `TitleHooks.arcs`? |
| 4 | [`movement/rules.py`](../games/hexdemo/movement/rules.py), [`combat/rules.py`](../games/hexdemo/combat/rules.py) | Modification and interaction policy |
| 5 | [`ui/segment_registry.py`](../games/hexdemo/ui/segment_registry.py) | What does each `ui_mode` look like? |
| 6 | [`hooks/`](../games/hexdemo/hooks/) | Hook adapters only |

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
- Do not read `GameState.session_state` / extension-shaped fields on the client for buttons or legality.
- Use preview RPCs for legal hexes (drag and map-selection), not client-side reachability.

Full primitive catalog and path-draft shapes: [`TURN_ACTION_DOCK_CONTRACT.md` § Player interaction primitives](TURN_ACTION_DOCK_CONTRACT.md#player-interaction-primitives).

---

## High-level: three ways title code is wired

| Path | When | Declare | Example (hexdemo) |
|------|------|---------|-------------------|
| **`TitleHooks`** | Every in-match RPC / state update | `@bind_title_hook` in `hooks/*.py`, `build_hooks()` | `modification.py`, `interaction.py`, `turn_action_dock.py` |
| **Manifest title-load** | Browser connect / server boot | `[hooks.title_load]` in `hexengine_pack.toml` | `hooks/title_load.py` |
| **Turn schedule** | Phase entry | `GameDefinition.after_phase_transition` | `game_config.py` → `combat_transitions` |

**Rules vs hooks:** put reusable `GameState` policy in pack modules (`state/session_state.py`, `movement/rules.py`, `combat/rules.py`, …); keep `hooks/*.py` thin adapters. See [`games/hexdemo/hooks/README.md`](../games/hexdemo/hooks/README.md).

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
│  Arc segments: owner, allowed actions, ui_mode             │
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

## Interaction arc graph

When a title declares wargame-style interaction, the **aftermath FSM** should be readable in the pack before opening engine internals.

| Approach | When | Read first |
|----------|------|------------|
| **Pack-owned graph** (hexdemo) | You customize segment topology or want flow visible to authors | [`games/hexdemo/combat/graph.py`](../games/hexdemo/combat/graph.py) — builds `Arc` via `authoring.builder`; [`combat/arc.py`](../games/hexdemo/combat/arc.py) wraps `ArcSpec` |
| **Engine convenience wrapper** (template) | Minimal title, default cleanup shape, no topology edits | [`combat_rules_binding_to_arc_spec`](../src/hexengine/authoring/patterns/combat.py) from a binding class — copy [`games/hexdemo/combat/graph.py`](../games/hexdemo/combat/graph.py) when you need to read or change the FSM |

**Split of responsibilities:**

| Module | Owns |
|--------|------|
| `combat/graph.py` | Segment ids, owners, `ui_mode`, transitions, allowed actions |
| `combat/rules.py` | Guards, effects, CRT, `attack_arc_effect` on the binding |
| `combat/transitions.py` | Gate `ui_mode` strings, phase-scoped session-state clear |
| `combat/actions.py` | State mutations invoked from binding effects |
| `ui/segment_registry.py` | Presentation row per `ui_mode` |

Graph parity with the engine pattern is tested in CI (`test_hexdemo_combat_graph_matches_engine_pattern`). See [`games/hexdemo/combat/README.md`](../games/hexdemo/combat/README.md) and [`combat/graph.py`](../games/hexdemo/combat/graph.py).

---

## Segment presentation registry

**Reference pattern** (hexdemo: [`ui/segment_registry.py`](../games/hexdemo/ui/segment_registry.py); template: [`games/template/segment_ui.py`](../games/template/segment_ui.py)):

One **registry row per segment UX mode**, aligned with the `ui_mode` string on arc segments. Each row ties flow to presentation without duplicating logic across engine, dock hook, and client.

| Registry field | Author meaning | Engine / client use (internal) |
|----------------|----------------|--------------------------------|
| **`ui_mode`** | Stable UI/policy bucket in the declared arc (e.g. `awaiting_retreat`, `combat`) | `current_segment.ui_mode` |
| **`presentation_id`** | Skin key for CSS and templates (e.g. `retreat_gate`, `attack_ready`) | panel `css_class` modifiers and wire `presentation_id` |
| **`primitive`** | INFORM, SELECT, DECIDE, or SEQUENCE | Which wire lane(s) are active |
| **`interaction_mode`** | Optional [`InteractionKind`](../src/hexengine/gamedef/interactions.py) (`attack_plan`, `retreat_path`, `place_marker`, or none) | Map-selection preview + client draft skin |
| **`inform_profile`** | Optional key for default banner / coaching hooks | `COMBAT_INTERACTION_MESSAGES`, phase rows |

**Example (conceptual):**

```python
# games/<pack>/ui/segment_registry.py — one place to read “what UX mode is this?”
SegmentPresentation(
    ui_mode="awaiting_retreat",
    presentation_id="retreat_gate",
    primitive=Primitive.SELECT,
    interaction_mode="retreat_path",
    inform_profile="retreat_gate",
)
```

Arc declarations use the same `ui_mode` strings. Dock and inform hooks **look up** the row and call pack helpers (`ui_markup`, `shell_ui`); they do not re-derive mode from phase names or bucket strings.

**Presentation customization** (goal b) is keyed by `presentation_id` and `inform_profile`:

| Asset | Edit | Keyed by |
|-------|------|----------|
| Short labels | `game_data.toml` → `shell_ui` | `presentation_id` + action id |
| Dock headline / hint HTML | `ui_markup.py` + `resources/templates/` | `presentation_id` |
| Banners | `presentation/interaction_messages.py` + thin `UIHook` adapters | `segment.ui_mode` (combat/advance gates) and combat outcome |
| Map popups | `presentation/inform.py` via `hooks/ui.inform_popup_for_viewer` | `inform_profile` + `reason` (from `current_segment` when client omits `inform_kind`) |
| CSS | pack `resources/ui.css` | `.…-turn-dock--{presentation_id}` |

**Do not** in pack code: build raw wire dicts for dock panels or inform popups (except tests); read `client.interaction_panels` for legality; branch on `combat_gate` for affordances — use [`arcs/segment.py`](../games/hexdemo/arcs/segment.py) helpers and `current_segment` via hook context.

**Presentation DTOs (P2):** return `TurnDockPanel`, `InformPopup`, `MapSelectionPreview`, `InteractionMessage`, `MapOverlay`, and `SegmentPresentationPatch` from `hexengine.authoring.present` (`turn_dock_panel`, `panel_action`, `inform_popup`, `map_selection_preview`, `interaction_message`, `map_overlay_glyph`, …). The engine converts them in `hexengine.hooks.internal.ui_wire` before `StateUpdate`, `ui_popup`, or `map_selection_preview` wire messages.

**P3 (done):** `current_segment` on `StateUpdate` carries `presentation_id` and `interaction_mode` (title `enrich_current_segment` hook + engine default). The client turn-dock SEQUENCE skin keys off `interaction_mode`, not separate `*_draft` booleans.

**P4 (done):** INFORM map callouts resolve `inform_profile` from `current_segment` when the client omits `inform_kind` (`hexengine.arcs.inform_wire`). Title copy lives in `presentation/inform.py` keyed by profile + reason; engine `default_inform_popup_for_viewer` uses the same shell key pattern.

**P5 (done):** At server startup, `validate_title_contract` checks every explicit segment `ui_mode` in declared arcs is registered in `PRESENTATION_BY_UI_MODE` (bind `UIHook.SEGMENT_PRESENTATION_REGISTRY`). Required when `session_state_key` is set.

**Draft locus:** Map SELECT drafts are client-local until commit; preview consults, commit authorizes. See [`TURN_ACTION_DOCK_CONTRACT.md` § Draft locus](TURN_ACTION_DOCK_CONTRACT.md#draft-locus-invariant).

---

## API: pack manifest and discovery

| Item | Location | Notes |
|------|----------|-------|
| `hexengine_pack.toml` | Pack root | `[python].entry_*`, `[hooks.title_load]`, pack id |
| `load_game_definition` | `engine_entry.py` | Required for authoritative server |
| Scenario | `scenarios/<id>/scenario.toml` | Units, map, markers — schema in `hexengine.scenarios` |
| `GameData` | `resources/game_data.toml` | `shell_ui`, styles, `session_state_key`, `[client_contract]` client wiring |
| PYTHONPATH | `games/` directory | `import hexdemo` (or your pack id) |

Server prepends `games/` when loading a scenario path; see hexdemo README for local dev exports.

---

## Session state and bucket patches

**Session state** is per-match pack data on **`GameState.session_state`** (not the browser/WebSocket client session). The pack id is **`GameState.session_state_key`**, set from **`GameData.session_state_key`** in `game_data.toml`.

| Layer | Authors import | Engine uses |
|-------|----------------|-------------|
| **Read** | Pack `session_state.bucket(state)` + typed helpers | `engine_read_session_state(state, key)` |
| **Write (delta)** | `BucketPatch` + `ApplyBucketPatch` from [`hexengine.hooks.bucket`](../src/hexengine/hooks/bucket.py) | Same action; merge via `engine_write_session_state` |
| **Unit attributes** | `UnitAttributesPatch` + `ApplyUnitAttributesPatch` from [`hexengine.hooks.unit`](../src/hexengine/hooks/unit.py) | Shallow merge into `UnitState.attributes` |
| **Combat handoff** | `CombatOutcome(patch=BucketPatch(...))` from `combat_outcome_after_applied` | `combat_outcome_apply` → `ApplyBucketPatch` before classify |

**Glossary:** *bucket* = the session-state dict; *patch* = a partial update (`BucketPatch.values` merged, `remove_keys` dropped). Do not scatter raw key strings — centralize reads in one pack module (hexdemo: [`session_state.py`](../games/hexdemo/session_state.py)).

**Engine ephemeral data** lives in **`GameState.engine_state`** (`hexengine_*` keys only). Snapshots and `StateUpdate.game_state` carry `session_state`, `engine_state`, and `session_state_key`.

### Combat and movement (hexdemo)

| Layer | Module | Role |
|-------|--------|------|
| **Interaction graph** | [`combat/graph.py`](../games/hexdemo/combat/graph.py) | Pack-visible aftermath FSM (segments, transitions) |
| **Combat binding** | [`combat/rules.py`](../games/hexdemo/combat/rules.py) | `HexdemoCombatRules` / `BINDING`: CRT, validate, `CombatOutcome`, arc guards/effects, `attack_arc_effect` |
| **Outcome builder** | [`combat/outcome.py`](../games/hexdemo/combat/outcome.py) | `build_combat_outcome_after_applied` → `BucketPatch` for classify |
| **Arc spec** | [`combat/arc.py`](../games/hexdemo/combat/arc.py) | `build_hexdemo_combat_arc_spec`; owner resolver; wired via [`arcs/wiring.py`](../games/hexdemo/arcs/wiring.py) |
| **Cleanup mutations** | [`combat/actions.py`](../games/hexdemo/combat/actions.py) | Retreat step, disrupt, advance resolve (called from binding) |
| **Gate ui_modes / phase clear** | [`combat/transitions.py`](../games/hexdemo/combat/transitions.py) | `COMBAT_ARC_GATE_UI_MODES`, `clear_combat_state_actions`, attack-planning block copy |
| **Combat gate dock rows** | [`authoring/patterns/combat.py`](../src/hexengine/authoring/patterns/combat.py) | `combat_gate_panel_actions` — Disrupt / Advance / Skip `PanelAction` rows from `allowed_actions` + `shell_ui` |
| **Session-state reads** | [`state/session_state.py`](../games/hexdemo/state/session_state.py) | `bucket()`, retreat obligations, advance offer |
| **Modification policy** | [`movement/rules.py`](../games/hexdemo/movement/rules.py) | Budget, ZoC, step cost, retreat constraints |
| **Hook adapters** | [`hooks/interaction.py`](../games/hexdemo/hooks/interaction.py), [`hooks/modification.py`](../games/hexdemo/hooks/modification.py) | `@bind_title_hook` only |
| **Segment projection** | [`arcs/segment.py`](../games/hexdemo/arcs/segment.py) | `phase_advance_blocked`, planning block helpers |

**Attack RPC flow:** engine discovers the interaction commit segment from the declared graph (`arc_commit_segment_for_action`, typically `attack` in hexdemo) → cursor → `submit_event` → binding applies resolution + `CombatOutcome` → `classify` auto-advances to cleanup gates or completes → **`restore_routine_cursor`** so routine combat segment (and End Phase) return. Legality and dock rows read **`current_segment`**, not bucket gate strings. Legacy **`combat_gate`** is not written; it is cleared on phase advance for old saves.

**Author `InteractionHook` surface:** `validate_attack`, `resolve_attack`, `combat_outcome_after_applied`, `attack_plan_preview`, `auto_advance_phase_after_attack` only. No cleanup slots on `InteractionHook` (removed).

---

## API: `TitleHooks` bundles

Assembled with [`assemble_title_hooks`](../src/hexengine/hooks/wiring.py). Enum markers: [`ModificationHook`](../src/hexengine/hooks/modification.py), [`InteractionHook`](../src/hexengine/hooks/interaction.py), [`UIHook`](../src/hexengine/hooks/ui.py). Fields on `TitleHooks`: `.modification`, `.interaction`, `.ui`, `.arcs`.

| Bundle | Typical responsibilities | Contract / validation |
|--------|-------------------------|---------------------|
| **modification** | Step cost, ZoC, retreat obligations, retreat path preview, **auto-advance after move spend** | Movement arc; retreat preview optional; `AUTO_ADVANCE_PHASE_AFTER_MOVE_SPEND` (catalog default: advance when action pool empty) |
| **interaction** | `validate_attack` (rules only — segment legality is engine-default when `session_state_key` is set), `resolve_attack`, attack plan preview, optional **`combat_outcome_after_applied`** (`CombatOutcome` + `BucketPatch`), **auto-advance after attack** | **Required** when you declare an interaction arc (`ArcHook.COMBAT_ARC` returning `ArcSpec`); `AUTO_ADVANCE_PHASE_AFTER_ATTACK` has no catalog default (omit hook = no auto-advance) |
| **ui** | Banners, dock, popups, overlays, combat banners | `COMBAT_INTERACTION_MESSAGES`, `TURN_ACTION_DOCK_FOR_VIEWER` |
| **arcs** | Turn registry, **interaction arc** (overlay graph + cleanup subgraph), optional **movement arc preset** (`ENGINE_MOVEMENT_ARC_PRESET` for stepwise moves / retreat paths), optional **combat rules binding** for contract check | `TURN_ARC_REGISTRY`, `COMBAT_ARC` (when interaction enabled); `MOVEMENT_ARC` preset (hexdemo: stepwise + retreat continuation); `COMBAT_RULES_BINDING` (hexdemo: validates `BINDING` at startup). Wired in [`arcs/wiring.py`](../games/hexdemo/arcs/wiring.py) |

Return **`ENGINE_DEFAULT`** from a hook to use engine catalog behavior for that slot.

Hook inventory (signatures, when invoked): [`PACK_HOOK_CONTRACTS.md` § Hook inventory](PACK_HOOK_CONTRACTS.md#hook-inventory-current-surfaces) and [§ UI hook inventory](PACK_HOOK_CONTRACTS.md#ui-hook-inventory).

---

## API: player UX (hooks; wire is reference)

Hooks are the **author surface**. Return presentation DTOs from `hexengine.authoring.present` (turn dock, inform, previews, banners, overlays, segment enrich); the engine serializes via `hexengine.hooks.internal.ui_wire`. Prefer typed contexts and pack helpers over copying wire schemas from this guide.

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

**Required** when `GameData.session_state_key` is set (`validate_title_contract`). Compose End Phase from `current_segment` (`segment_allows_action` / `_end_phase_row`); add combat cleanup gate rows with [`combat_gate_panel_actions`](../src/hexengine/authoring/patterns/combat.py) when using `build_combat_cleanup_arc`. Wire panel id is conventionally `turn_actions`.

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
| `attack_plan` | `InteractionHook.ATTACK_PLAN_PREVIEW` | `combat_planning` / `hooks/interaction.py` |
| `retreat_path` | `ModificationHook.RETREAT_PATH_PREVIEW` | [`movement/retreat_preview.py`](../games/hexdemo/movement/retreat_preview.py) |
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

**Player prompts** (scripted events, season cards, acknowledge-then-continue) are prompt sequences: INFORM on the dock (`headline` / `html`) then DECIDE; blocking is a **prompt segment** in the turn arc. See [`TURN_ACTION_DOCK_CONTRACT.md` § Player prompts](TURN_ACTION_DOCK_CONTRACT.md#player-prompts) and [`archive/COMPOSABLE_ARCS_PLAN.md` § Prompt segments](archive/COMPOSABLE_ARCS_PLAN.md#prompt-segments).

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

### Minimal interaction title (`session_state_key` + combat schedule)

1. Set `session_state_key` in `game_data.toml`; add `state/session_state.py` accessors (no raw bucket strings in author code).
2. Declare `ArcHook.TURN_ARC_REGISTRY` with schedule slots whose `allowed_actions` includes `Attack` (see [`arcs/turn_schedule.py`](../games/hexdemo/arcs/turn_schedule.py)).
3. Implement one `CombatRulesBinding` in `combat/rules.py`; build `ArcSpec` from [`combat/graph.py`](../games/hexdemo/combat/graph.py) + [`combat/arc.py`](../games/hexdemo/combat/arc.py) (or template: [`combat_rules_binding_to_arc_spec`](../src/hexengine/authoring/patterns/combat.py)); bind via [`arcs/wiring.py`](../games/hexdemo/arcs/wiring.py) (`ArcHook.COMBAT_ARC`, optional `COMBAT_RULES_BINDING`).
4. Thin `hooks/interaction.py` adapters to binding methods; add `movement/rules.py` if retreat/move policy is non-default.
5. Register segment `ui_mode` values in `ui/segment_registry.py` (routine combat segment, each gate `ui_mode`); bind `UIHook.SEGMENT_PRESENTATION_REGISTRY`, `ENRICH_CURRENT_SEGMENT`, and `TURN_ACTION_DOCK_FOR_VIEWER`.
6. In the dock hook, call `combat_gate_panel_actions(seg, ctx.shell_ui)` plus `_end_phase_row`; add presentation rows under `presentation/` for each `presentation_id`; run `validate_title_contract` and combat integration tests.

### New INFORM copy

1. Prefer `PHASE_BANNER_TEXT_FOR_VIEWER` + optional HTML hook.
2. Add template under `resources/templates/` + helper in `ui_markup.py`.
3. Add `shell_ui` keys only for strings reused in multiple places.

### New click-confirm map flow (`InteractionKind`)

1. Add enum value to [`InteractionKind`](../src/hexengine/gamedef/interactions.py) (engine).
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
| **Stable (v1)** | Three lanes, dock + `panel_actions` merge, `InteractionKind` values `attack_plan` / `retreat_path` / `place_marker`, drag previews, `ENGINE_DEFAULT`, HTML ladder tiers 1–3, `current_segment`-driven legality, `authoring.present` DTOs + `ui_wire` serialization, `combat_gate_panel_actions` for cleanup gate dock rows |
| **Evolving** | Client-held draft; SEQUENCE skin from `current_segment.interaction_mode`; segment registry + `presentation/inform.py` (hexdemo reference); manifest `[client_contract]` client routes |
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
| [`ENGINE_TITLE_CHARTER.md`](ENGINE_TITLE_CHARTER.md) | Engine vs title ownership (normative) |
| [`archive/ENGINE_TITLE_CHARTER_PLAN.md`](archive/ENGINE_TITLE_CHARTER_PLAN.md) | Charter migration (archived phase history) |
| [`archive/COMBAT_ARC_GRAPH_PLAN.md`](archive/COMBAT_ARC_GRAPH_PLAN.md) | Pack-visible interaction graph (archived phase history) |
| [`archive/TITLE_AUTHOR_INTERFACE_PLAN.md`](archive/TITLE_AUTHOR_INTERFACE_PLAN.md) | Combat/movement interface (archived phase history) |
| [`archive/COMPOSABLE_ARCS_PLAN.md`](archive/COMPOSABLE_ARCS_PLAN.md) | Composable arcs (archived phase history) |
| [`archive/ENGINE_BOUNDARY_2_PLAN.md`](archive/ENGINE_BOUNDARY_2_PLAN.md) | Engine boundary 2 (archived phase history) |
| [`TURN_ACTION_DOCK_CONTRACT.md`](TURN_ACTION_DOCK_CONTRACT.md) | Wire + primitives (API detail) |
| [`PACK_HOOK_CONTRACTS.md`](PACK_HOOK_CONTRACTS.md) | Wire schemas + hook roadmap |
| [`SKINNING_AFFORDANCES_PLAN.md`](SKINNING_AFFORDANCES_PLAN.md) | Implementation status / roadmap |
| [`SKINNING_CLIENT_INVENTORY.md`](SKINNING_CLIENT_INVENTORY.md) | Client file map |
| [`TITLE_LOAD_HOOKS.md`](TITLE_LOAD_HOOKS.md) | Connect-time hooks |
| [`engine_game_boundary_matrix.md`](engine_game_boundary_matrix.md) | Authority boundaries |
| [`PACK_TRUST_MODEL.md`](PACK_TRUST_MODEL.md) | Server trust / hosted packs |
| [`SERVER_ARCHITECTURE.md`](SERVER_ARCHITECTURE.md) | Server boot and scenarios |
| [`MULTIPLAYER_INTEGRATION.md`](MULTIPLAYER_INTEGRATION.md) | Client/server checklist |
