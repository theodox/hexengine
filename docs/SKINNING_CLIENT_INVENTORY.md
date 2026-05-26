# Client skinning inventory

File-level map of how the browser renders title UX. Server owns legality; the client renders wire payloads and sends `action_request`.

**Authors:** [`TITLE_AUTHORING.md`](TITLE_AUTHORING.md) · **Related:** [`SKINNING_AFFORDANCES_PLAN.md`](SKINNING_AFFORDANCES_PLAN.md), [`TURN_ACTION_DOCK_CONTRACT.md`](TURN_ACTION_DOCK_CONTRACT.md#player-interaction-primitives), [`PACK_HOOK_CONTRACTS.md`](PACK_HOOK_CONTRACTS.md#ui-affordances--wire-schemas-and-hooks-v1).

---

## Primitives → client modules

| Primitive | Client behavior | Modules |
|-----------|-----------------|---------|
| INFORM | Banner row, inspect popup | [`game.py`](../src/hexengine/game/game.py), `interaction_messages` sync |
| SELECT | Draft, preview RPC, highlights | [`client_map_selection.py`](../src/hexengine/game/arcs/client_map_selection.py), [`client_map_selection_registry.py`](../src/hexengine/game/arcs/client_map_selection_registry.py), drag via [`server/preview.py`](../src/hexengine/server/preview.py) |
| DECIDE | Dock panel `actions[]` | [`client_interaction_panels.py`](../src/hexengine/game/arcs/client_interaction_panels.py), [`client_panel_actions.py`](../src/hexengine/game/arcs/client_panel_actions.py) |
| SEQUENCE | Server `dock_arc` + client overrides + headline | [`client_interaction_panels.py`](../src/hexengine/game/arcs/client_interaction_panels.py), [`client_combat.py`](../src/hexengine/game/arcs/client_combat.py), [`client_retreat_path.py`](../src/hexengine/game/arcs/client_retreat_path.py) |

**Attack plan:** SELECT → `map_selection_preview` → merge `panel_actions` → `Attack` uses `preview_commit` route.

**Retreat path:** SELECT → preview → merge `panel_actions` → `retreat_path_confirm` uses local `confirm_retreat_path()`.

**Place marker (click-confirm):** SELECT → preview → merge `panel_actions` → `place_marker_confirm` uses local `confirm_place_marker()`. Drag uses `marker_preview_request`.

---

## Turn action dock (`#user-controls`)

| Module | Role |
|--------|------|
| [`client_interaction_panels.py`](../src/hexengine/game/arcs/client_interaction_panels.py) | Renders `StateUpdate.interaction_panels`; `headline`, `html`, `actions[]`, `inputs[]`; merges preview actions; SEQUENCE skin (`attack_draft`, `retreat_path_draft`, `place_marker_draft`) |
| [`client_panel_actions.py`](../src/hexengine/game/arcs/client_panel_actions.py) | `PANEL_ACTION_ROUTES`: local + `preview_commit` dispatch before default RPC |
| [`game.py`](../src/hexengine/game/game.py) | `_sync_interaction_panels()` on state sync |
| [`games/hexdemo/hooks/turn_action_dock.py`](../games/hexdemo/hooks/turn_action_dock.py) | Hexdemo server dock rows and baseline `dock_arc` |

`primary_actions` wire and `_primary_actions_row` sync only run when the title does **not** bind `TURN_ACTION_DOCK_FOR_VIEWER`.

---

## Map selection preview (client)

| Module | Role |
|--------|------|
| [`client_map_selection.py`](../src/hexengine/game/arcs/client_map_selection.py) | `map_selection_preview_request` / response handling |
| [`client_map_selection_registry.py`](../src/hexengine/game/arcs/client_map_selection_registry.py) | Kind → `_apply_*_preview` method table |
| [`client_combat.py`](../src/hexengine/game/arcs/client_combat.py) | `_apply_attack_plan_preview` (via `_sync_attack_plan_ui`) |
| [`client_retreat_path.py`](../src/hexengine/game/arcs/client_retreat_path.py) | `_apply_retreat_path_preview` (highlights, polyline, dock refresh) |
| [`client_place_marker.py`](../src/hexengine/game/arcs/client_place_marker.py) | `_apply_place_marker_preview` (legal hex highlights, dock refresh) |

Add a kind: one row in `_MAP_SELECTION_APPLY_METHODS` + title server registry row + preview hook.

---

## Attack planning chrome (map only)

| Module | Role |
|--------|------|
| [`client_combat.py`](../src/hexengine/game/arcs/client_combat.py) | Target overlay, artillery LOS lines; gated by `attack_planning_ui` |
| [`game/events/mouse.py`](../src/hexengine/game/events/mouse.py) | Target/attacker picks when attack planning active |

Coaching copy is on the **dock headline** (not a separate `#user-controls` status strip). Commit buttons are only on the turn action dock.

---

## Place marker relocate (click-confirm)

| Module | Role |
|--------|------|
| [`client_place_marker.py`](../src/hexengine/game/arcs/client_place_marker.py) | Shift+click marker, pick hex, dock Confirm/Cancel |

Drag relocate unchanged: `marker_preview_request` on [`server/preview.py`](../src/hexengine/server/preview.py).

---

## Retreat path chrome (map only)

| Module | Role |
|--------|------|
| [`client_retreat_path.py`](../src/hexengine/game/arcs/client_retreat_path.py) | Click-extend draft, SVG path polyline on `#map-svg`, dock Confirm/Undo/Cancel |

---

## INFORM

| Module | Role |
|--------|------|
| `interaction_messages` | `#interaction-banner`; prefers `html` over `text` |
| [`ui_markup.py`](../games/hexdemo/ui_markup.py) | Hexdemo templates + flag URLs (`/pack/hexdemo/…`) |
| `POPUP_MESSAGE` → `ui_popup` | Unit/marker inspect (double-click / Enter) |
| `INFORM_POPUP` → `ui_popup` | Map callouts: `Game.show_inform_popup` → `inspect` + `target_kind=inform` |
| [`inform_popups.py`](../games/hexdemo/inform_popups.py) | Hexdemo copy for inform reasons (`shell_ui` `attack_plan_*`) |

Use `<img src="…">` for flags in banner HTML (not `url()` in CSS against the page URL).

---

## Drag SELECT

| RPC | Role |
|-----|------|
| `unit_preview_request` | Move / one-hop retreat legal hex highlights |
| `marker_preview_request` | Marker placement drag |

Client does not compute legal moves locally. Multi-hex mandatory retreat with Confirm uses **`map_selection_preview`** (`retreat_path`), not drag-only.

---

## Client contract features

| Feature | Behavior |
|---------|----------|
| `server_drag_previews` | Required for drag highlights |
| `map_selection_previews` | `map_selection_preview_request` + dock merge + apply registry |
| `attack_planning_ui` | Attack-plan map/unit UX + LOS overlay |
| `retreat_obligations` | Retreat path mode + retreat drag gating |
| `suggested_focus_unit_id` | Auto-focus unit after sync |

---

## Server wire (per viewer)

| Field | When |
|-------|------|
| `interaction_messages` | Always (when composed) |
| `interaction_panels` | When dock hook returns panels |
| `primary_actions` | **Not sent** when title binds turn action dock |
| `map_overlays` | When hook returns overlays |

Combat policy (`combat_gate`, `retreat_obligations`) stays in server `GameState.extension` only — not read by the client for buttons.
