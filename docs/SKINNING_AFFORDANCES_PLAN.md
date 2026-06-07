# Skinning and generic affordances — implementation plan

Roadmap for title UX: **communicate**, **draft selections**, **commit choices**, and **skin** the result. Player flows use four **primitives** (INFORM, SELECT, DECIDE, SEQUENCE) over three **wire lanes** — see [`TURN_ACTION_DOCK_CONTRACT.md`](TURN_ACTION_DOCK_CONTRACT.md).

**Authors:** start at [`TITLE_AUTHORING.md`](TITLE_AUTHORING.md) (summaries + API index). This file tracks **implementation status** and roadmap.

**Companion docs**

| Doc | Role |
|-----|------|
| [`TITLE_AUTHORING.md`](TITLE_AUTHORING.md) | Title author hub (start here) |
| [`TURN_ACTION_DOCK_CONTRACT.md`](TURN_ACTION_DOCK_CONTRACT.md) | Commit dock + primitives (authoritative wire detail) |
| [`SKINNING_CLIENT_INVENTORY.md`](SKINNING_CLIENT_INVENTORY.md) | Client modules and RPCs |
| [`PACK_HOOK_CONTRACTS.md`](PACK_HOOK_CONTRACTS.md) | Wire schemas + hook inventory |

---

## Current architecture

```
┌─────────────────────────────────────────────────────────────┐
│  INFORM: interaction_messages (+ optional dock headline)     │
├─────────────────────────────────────────────────────────────┤
│  #user-controls  turn action dock (interaction_panels / turn_actions)│
│    actions[] from TURN_ACTION_DOCK + preview panel_actions   │
│    headline + dock_arc (server + client SEQUENCE overrides)  │
├─────────────────────────────────────────────────────────────┤
│  Map: SELECT — map_selection_preview OR unit_preview drag    │
└─────────────────────────────────────────────────────────────┘
```

| Lane | Primitive | Wire / RPC | Title binds |
|------|-----------|------------|-------------|
| Tell | INFORM | `interaction_messages`, `ui_popup` | Message + popup hooks |
| Map pick | SELECT | `map_selection_preview_*`, `unit_preview_*` | Per-kind preview hooks ([`map_selection_registry`](../src/hexengine/hooks/map_selection_registry.py)) |
| Commit | DECIDE | `interaction_panels` via **`TURN_ACTION_DOCK_FOR_VIEWER`** | [`turn_action_dock.py`](../games/hexdemo/hooks/turn_action_dock.py) (hexdemo) |

**Rules**

- Banner and dock `html` are display-only — no `onclick`. Commits are dock `actions[]` → `action_request` (or client registry handlers).
- `StateUpdate.primary_actions` is omitted when the title binds the dock hook.
- Draft ratify buttons come from preview `panel_actions`, merged into dock panel `turn_actions`.

### SELECT transports (both intentional)

| Transport | Use | Commit |
|-----------|-----|--------|
| `map_selection_preview` | Click/toggle/path drafts (`InteractionKind` + `draft`) | Confirm on dock via [`client_panel_actions.py`](../src/hexengine/game/arcs/client_panel_actions.py) |
| `unit_preview` / `marker_preview` | Move, one-hop retreat, marker drag | On drop → `action_request` |

### Primitives (summary)

| Primitive | Role |
|-----------|------|
| INFORM | Status, narrative, popups; short prompts on dock `headline` during SEQUENCE |
| SELECT | Build draft; server returns legality + highlights |
| DECIDE | Buttons on turn action dock |
| SEQUENCE | Server `dock_arc` + client overrides (`attack_draft`, `retreat_path_draft`, `place_marker_draft`) while drafts active |

Attack plan: SELECT → preview → merge `panel_actions` → Confirm (`Attack` + `commit_payload`).

Retreat path: SELECT → preview → merge `panel_actions` → Confirm (`retreat_path_confirm` local handler).

Place marker (click-confirm): SELECT → preview → merge `panel_actions` → Confirm (`place_marker_confirm` → `MoveMarker`). Drag relocate unchanged (`marker_preview`).

### Shipped in engine + hexdemo

| Area | Location |
|------|----------|
| Turn action dock | `UIHook.TURN_ACTION_DOCK_FOR_VIEWER`, [`ui_turn_action_dock.py`](../src/hexengine/hooks/ui_turn_action_dock.py), [`client_interaction_panels.py`](../src/hexengine/game/arcs/client_interaction_panels.py) |
| Client SEQUENCE skin | [`client_interaction_panels.py`](../src/hexengine/game/arcs/client_interaction_panels.py) (`effective_turn_dock_presentation_id`, headline overrides) |
| Panel action registry | [`client_panel_actions.py`](../src/hexengine/game/arcs/client_panel_actions.py) |
| Map-selection (server) | [`map_selection_registry.py`](../src/hexengine/hooks/map_selection_registry.py), [`map_selection.py`](../src/hexengine/server/map_selection.py) |
| Map-selection (client) | [`client_map_selection_registry.py`](../src/hexengine/game/arcs/client_map_selection_registry.py), [`client_map_selection.py`](../src/hexengine/game/arcs/client_map_selection.py) |
| Attack plan SELECT | `AttackHook.ATTACK_PLAN_PREVIEW`, [`client_combat.py`](../src/hexengine/game/arcs/client_combat.py) (LOS + target overlay) |
| Retreat path SELECT | `MovementHook.RETREAT_PATH_PREVIEW`, [`client_retreat_path.py`](../src/hexengine/game/arcs/client_retreat_path.py), [`retreat_path.py`](../src/hexengine/retreat_path.py) |
| Place marker SELECT | `UIHook.PLACE_MARKER_PREVIEW`, [`place_marker_preview.py`](../games/hexdemo/place_marker_preview.py), [`client_place_marker.py`](../src/hexengine/game/arcs/client_place_marker.py) |
| Drag SELECT | [`server/preview.py`](../src/hexengine/server/preview.py) |
| INFORM | Message hooks, templates, [`ui_markup.py`](../games/hexdemo/ui_markup.py), `/pack/<id>/` assets |
| Pack data | `GameData` / `shell_ui`, `interaction_kind_styles` |

### Client contract features

| Feature | When advertised | Behavior |
|---------|-----------------|----------|
| `server_drag_previews` | `GameServer` | `unit_preview` / `marker_preview` on drag |
| `map_selection_previews` | Any bound registry kind | `map_selection_preview_*`; merge `panel_actions` on dock |
| `attack_planning_ui` | Attack validate+resolve hooks | Map/unit picks for `attack_plan`; LOS overlay (no separate commit strip) |

---

## Track C status

### C.1–C.2 — Turn action dock + attack plan SELECT

Shipped. See contract doc and [`test_turn_action_dock.py`](../tests/test_turn_action_dock.py).

### C.3 — Path SELECT (click-confirm retreat)

Shipped for hexdemo mandatory retreat:

| Piece | Location |
|-------|----------|
| Kind | `retreat_path` (`InteractionKind`) |
| Preview + legality | [`retreat_path.py`](../src/hexengine/retreat_path.py), [`games/hexdemo/retreat_path_preview.py`](../games/hexdemo/retreat_path_preview.py) |
| Wire fields | `legal_next_hexes`, `through_hexes`, `preview_path_hexes`, `commit_payload.path`, `panel_actions` |
| Client | [`client_retreat_path.py`](../src/hexengine/game/arcs/client_retreat_path.py) (polyline on `#map-svg`, click-extend) |
| Stepwise commit | [`handle_authority_retreat_path_move_unit`](../src/hexengine/server/arcs/authority_movement.py) |

Drag retreat (`unit_preview`) remains for one-hop drops; path mode activates when the selected unit has a retreat obligation.

### C.4 — SEQUENCE polish + client registries

Shipped:

| Piece | Location |
|-------|----------|
| Client `dock_arc` overrides | `attack_draft`, `retreat_path_draft`, `place_marker_draft` in [`client_interaction_panels.py`](../src/hexengine/game/arcs/client_interaction_panels.py) |
| Dock headline coaching | Preview `status_text` + `shell_ui` idle copy (attack-plan status strip removed) |
| Panel action registry | [`client_panel_actions.py`](../src/hexengine/game/arcs/client_panel_actions.py) |
| Client preview apply registry | [`client_map_selection_registry.py`](../src/hexengine/game/arcs/client_map_selection_registry.py) |
| Tests | [`test_turn_dock_sequence.py`](../tests/test_turn_dock_sequence.py), [`test_client_panel_actions.py`](../tests/test_client_panel_actions.py), [`test_client_map_selection_registry.py`](../tests/test_client_map_selection_registry.py) |

### D — Place marker click-confirm (shipped)

| Piece | Location |
|-------|----------|
| Kind | `place_marker` (`InteractionKind`) |
| Preview | [`games/hexdemo/place_marker_preview.py`](../games/hexdemo/place_marker_preview.py), `hooks/markers.py` |
| Wire | `markers` passed into `compute_map_selection_preview`; `MoveMarker` `commit_payload` |
| Client | [`client_place_marker.py`](../src/hexengine/game/arcs/client_place_marker.py) (Shift+click marker, pick hex, Confirm) |
| Tests | [`test_place_marker_preview.py`](../tests/test_place_marker_preview.py) |

### Later

| Work | Notes |
|------|--------|
| New `InteractionKind` rows | Placement, gate hex-pick when drag is insufficient |
| `MovementHook` preview override | Custom reach sets without duplicating validation |
| Server-held draft on dock context | If client-only draft drifts from server |
| Generalized client SEQUENCE overrides | Today `*_draft` arcs are hexdemo client code; target: `interaction_mode` from segment registry ([`TITLE_AUTHORING.md` § Segment presentation registry](TITLE_AUTHORING.md#segment-presentation-registry)) |
| Segment presentation registry | One pack module: `kind` → `presentation_id`, primitive, `interaction_mode`; dock/inform hooks lookup instead of parallel if-chains |
| Retreat path rules tweaks | Step count vs movement budget (title rules; see `retreat_path.py`) |
| `games/_template/` pack | Scaffold named in [`PACK_HOOK_CONTRACTS.md`](PACK_HOOK_CONTRACTS.md) |

---

## Authoring {#authoring}

### Mental model

```
INFORM   →  GameData + ui.css + templates + message hooks
SELECT   →  server map_selection_registry row + title preview hook
           + client_map_selection_registry apply method
DECIDE   →  TURN_ACTION_DOCK_FOR_VIEWER (panel id turn_actions)
           + optional client_panel_actions route for special commits
SEQUENCE →  server dock_arc + client draft overrides + shell_ui copy
```

### `shell_ui` (hexdemo examples)

- `advance_turn_button_label` — End Phase on dock
- `attack_confirm_label`, `attack_cancel_label`, `attack_planning_phases`
- `attack_pick_target_status`, `attack_target_set_status` — Combat idle / draft headline fallbacks
- `retreat_path_*_label`, `retreat_path_pick_hex_status`, `retreat_path_ready_status`
- `place_marker_*_label`, `place_marker_pick_hex_status`, `place_marker_ready_status`
- `dock_gate_panel_hint` — HTML on retreat/advance gate dock arcs
- `dock_*_headline` — Server dock titles per arc (`dock_retreat_gate_headline`, …)

### HTML ladder (INFORM only)

Tiers 1–5: CSS → templates → `ui_markup.py` → `hexengine.ui.display` → full `INTERACTION_MESSAGES` override. Details in [`PACK_HOOK_CONTRACTS.md`](PACK_HOOK_CONTRACTS.md#html-authoring-ladder-v1) and [`SKINNING_CLIENT_INVENTORY.md`](SKINNING_CLIENT_INVENTORY.md).

### Runtime copy and commits

| Need | Author with |
|------|-------------|
| Banners | `PHASE_BANNER_*`, `COMBAT_INSTRUCTION_*`, templates |
| Commit buttons | `TURN_ACTION_DOCK_FOR_VIEWER` + preview `panel_actions` |
| Draft legality | Preview hook for `InteractionKind` |
| Short “what now” during drafts | Preview `status_text` → dock headline (client) |
| Inspect | `POPUP_MESSAGE` |
| Map glyphs | `MAP_OVERLAYS` |

---

## UI hooks (active)

| Hook | Primitive |
|------|-----------|
| `INTERACTION_MESSAGES`, `PHASE_BANNER_*`, `COMBAT_INSTRUCTION_*`, `ADVANCE_GATE_*` | INFORM |
| `POPUP_MESSAGE`, `MAP_OVERLAYS` | INFORM |
| **`TURN_ACTION_DOCK_FOR_VIEWER`** | DECIDE |
| **`AttackHook.ATTACK_PLAN_PREVIEW`** | SELECT (`attack_plan`) |
| **`MovementHook.RETREAT_PATH_PREVIEW`** | SELECT (`retreat_path`) |
| **`UIHook.PLACE_MARKER_PREVIEW`** | SELECT (`place_marker`) |

Full table: [`PACK_HOOK_CONTRACTS.md` § UI hook inventory](PACK_HOOK_CONTRACTS.md#ui-hook-inventory).

---

## Do not

- Client reads `GameState.title_state` (or other raw buckets) for buttons or affordances
- Inline `onclick` in title HTML
- Separate commit DOM outside the dock panel
- Client-computed legal hex sets for drag (use preview RPCs)
- `popup_manager.create_popup` for player-facing copy (use `Game.show_inform_popup` → `INFORM_POPUP` hook)
- `dev_console.set_status` for INFORM popups (use optional `repeat_ui_popup_to_dev_console` on `Game` instead)

---

## Out of scope

- Engine-modeled SEQUENCE step graphs
- Jinja or full templating engines in v1
- Rewriting combat simulation or extension bucket shape
