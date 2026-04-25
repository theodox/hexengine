# Engine / game boundary matrix (Phase 0)

Inventory for checklist items 1–9 in [`.cursor/plans/test_game_boundary_plan.md`](../.cursor/plans/test_game_boundary_plan.md). Rows below were checked against the codebase (paths relative to repo root).

**Columns (short):**

- **Pack** — Data under `games/<GameName>/` and `scenario.toml` only.
- **Title** — `games/<GameName>/` Python, `GameDefinition`, hooks the title supplies.
- **Engine** — `hexengine` (server, loader, client shell, state, wire).
- **Strain** — Does this seam fight **reproducibility / rewind / pure state**? (`none` / `low` / `med` / `high`).
- **Next** — One-line follow-up.

---

## Omitted from numbered checklist (track separately)

| Topic | Pack | Title | Engine | Strain | Next |
|-------|------|-------|--------|--------|------|
| Factions / lobby beyond two players | Faction strings in scenario TOML | [`GameDefinition.available_factions()`](src/hexengine/gamedef/protocol.py) | [`GameServer._handle_join_game`](src/hexengine/server/game_server.py): assigns from `available_factions`; error text still says `"max 2 players"` when list exhausted | low until >2 factions used | Align copy with dynamic `available_factions`; stress-test join when title expands roster |

---

## Items 1–9

| # | Dimension | Pack | Title | Engine | Strain | Next |
|---|-----------|------|-------|--------|--------|------|
| 1 | GameRoot packaging | `games/<GameName>/scenarios/<id>/scenario.toml` (e.g. [`games/hexdemo/scenarios/default/scenario.toml`](games/hexdemo/scenarios/default/scenario.toml); title Python under `games/hexdemo/`) | [`--schedule sequential`](src/hexengine/gameroot.py) vs default interleaved; example hook [`games/alt_schedule/__init__.py`](games/alt_schedule/__init__.py) | [`resolve_scenario_path_with_game_root`](src/hexengine/gameroot.py): default pack is **hexdemo** when `games/hexdemo` exists on a parent of the engine; CLI `--scenario-file`, `--game-root`, `--scenario-id`, zip → temp extract cache; fails if no pack resolves (no silent fallback to engine-only scenario). **No** `StaticFiles` / `/pack/` / `asset_base_url` in `hexengine` | low | Phase 1: static pack route + `asset_base_url` on wire if browsers load pack assets by URL |
| 2 | Scenario schema / loader | TOML + terrain / markers tables per [`src/hexengine/scenarios/load/parse.py`](src/hexengine/scenarios/load/parse.py) | — | [`load_scenario`](src/hexengine/scenarios/loader.py), [`scenario_to_initial_state`](src/hexengine/scenarios/loader.py) → [`GameState`](src/hexengine/state/game_state.py); display dicts from scenario model | low | Keep additive schema per [`docs/WIRE_COMPATIBILITY.md`](docs/WIRE_COMPATIBILITY.md) |
| 3 | Presentation vs simulation | `map_display`, `unit_graphics`, `marker_graphics`, asset paths in TOML | — | [`StateUpdate`](src/hexengine/server/protocol.py) carries `map_display`, `global_styles`, `unit_graphics`, `marker_graphics`, `markers`; server holds `GameServer.markers` parallel to `ActionManager` state | med | Pack HTTP + base URL for relative assets; clarify markers in undo/snapshot story |
| 4 | Turn schedule (game ↔ engine handshake) | — | [`GameDefinition.get_next_phase`](src/hexengine/gamedef/protocol.py) implemented in [`src/hexengine/gamedef/builtin.py`](src/hexengine/gamedef/builtin.py); [`advance_turn_action_for_state`](src/hexengine/gamedef/builtin.py) for browser UI | Server: [`_get_next_phase`](src/hexengine/server/game_server.py) → `_game_definition.get_next_phase`; after `MoveUnit` + `SpendAction`, auto [`NextPhase`](src/hexengine/server/game_server.py) when actions depleted. Client [`Game.advance_turn`](src/hexengine/game/game.py) builds `NextPhase` from a thin `GameDefinition` rebuilt from [`StateUpdate.turn_rules`](src/hexengine/server/protocol.py) (server still recomputes the next slot); switching titles without reload is out of scope | med | — |
| 5 | Action economy (handshake) | — | Title should own per-action costs when generalized | [`GameServer._handle_action_request`](src/hexengine/server/game_server.py): after `execute(MoveUnit)`, `execute(SpendAction(1))`; then optional `NextPhase` | med | Configurable costs / post-execute hook; align any client-side “costs action” hints |
| 6 | Movement legality | Terrain on board / `LocationState` from scenario | Title should own legality + movement budget API when enforced | Server [`MoveUnit.apply`](src/hexengine/state/actions.py) only checks unit exists and `from_hex`; **no** path/terrain/budget check. Client preview [`compute_valid_moves`](src/hexengine/state/logic.py) with hardcoded `movement_budget=4.0` in [`game.py`](src/hexengine/game/game.py) | high | Server-side validation before `MoveUnit`, or server-published allowed hexes; unify budget with title rules |
| 7 | Markers | Types/placements in TOML ([`marker_placements`](src/hexengine/scenarios/load/parse.py), etc.) | Injectable [`MarkerPlacementRule`](src/hexengine/server/game_server.py) | Server [`_marker_destination_allowed`](src/hexengine/server/game_server.py); [`websocket_server.main`](src/hexengine/server/websocket_server.py) passes `marker_placement_rule=None`. Client [`start_drag_preview_marker`](src/hexengine/game/game.py) calls `marker_destination_hexes_for_preview(..., None)` — comment notes mismatch with custom server rule | med | Thread same rule into client preview; or server-driven highlight set |
| 8 | RNG + audit | — | Future: title consumes rolls and applies combat/outcomes | [`RngService`](src/hexengine/gamedef/rng.py); [`rng_log`](src/hexengine/state/game_state.py) + wire in [`snapshot.py`](src/hexengine/state/snapshot.py); production gameplay paths do not call `RngService` yet — [`tests/test_rng_service.py`](tests/test_rng_service.py) | low now; med with undo + combat | Wire rolls into authoritative actions; keep draws server-side |
| 9 | Affordances (`InteractionKind`+) | — | Vocabulary in [`gamedef/interactions.py`](src/hexengine/gamedef/interactions.py) | No dedicated affordance routing layer in engine yet; actions go through existing protocol | low → med as surface grows | Map each interaction kind to title policy vs engine transport once used |

---

## Follow-ups (not duplicated in table)

- **`LOAD_SNAPSHOT`:** [`_handle_load_snapshot`](src/hexengine/server/game_server.py) replaces `ActionManager` state only; does not reset `markers` / `map_display` / graphics dicts — document trust model and field coverage.
- **Pack assets:** No HTTP static mount in engine; relative paths in scenario need an owner-hosted base URL or future `/pack/` integration.

Replace `Next` cells with issue links when you file tickets.
