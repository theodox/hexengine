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
| 1 | GameRoot packaging | `games/<GameName>/scenarios/<id>/scenario.toml` (e.g. [`games/hexdemo/scenarios/default/scenario.toml`](games/hexdemo/scenarios/default/scenario.toml); title Python under `games/hexdemo/`) | Pack declares rota via manifest `entry_callable` → `load_game_definition()` (see [`games/alt_schedule/__init__.py`](games/alt_schedule/__init__.py) as a stub example) | [`resolve_scenario_path_with_game_root`](src/hexengine/gameroot.py): default pack is **hexdemo** when `games/hexdemo` exists on a parent of the engine; CLI `--scenario-file`, `--game-root`, `--scenario-id`, zip → temp extract cache; fails if no pack resolves (no silent fallback to engine-only scenario). **`turn_rules.asset_base_url`** (`/pack/<id>/`); dev static server [`hexengine.dev.static_server`](src/hexengine/dev/static_server.py) | low | Production host must mount `/pack/<id>/` or rewrite to pack `resources/` |
| 2 | Scenario schema / loader | TOML + terrain / markers tables per [`src/hexengine/scenarios/load/parse.py`](src/hexengine/scenarios/load/parse.py) | — | [`load_scenario`](src/hexengine/scenarios/loader.py), [`scenario_to_initial_state`](src/hexengine/scenarios/loader.py) → [`GameState`](src/hexengine/state/game_state.py); display dicts from scenario model | low | Keep additive schema per [`docs/WIRE_COMPATIBILITY.md`](docs/WIRE_COMPATIBILITY.md) |
| 3 | Presentation vs simulation | `map_display`, `unit_graphics`, `marker_graphics`, asset paths in TOML | — | [`StateUpdate`](src/hexengine/server/protocol.py) carries `map_display`, `global_styles`, `unit_graphics`, `marker_graphics`, `markers`; server holds `GameServer.markers` parallel to `ActionManager` state | med | Pack HTTP + base URL for relative assets; clarify markers in undo/snapshot story |
| 4 | Turn schedule (game ↔ engine handshake) | — | [`GameDefinition.get_next_phase`](src/hexengine/gamedef/protocol.py) implemented in [`src/hexengine/gamedef/builtin.py`](src/hexengine/gamedef/builtin.py); [`advance_turn_action_for_state`](src/hexengine/gamedef/builtin.py) for tests/tooling | Server: [`_get_next_phase`](src/hexengine/server/game_server.py) → `_game_definition.get_next_phase`; after `MoveUnit` + `SpendAction`, auto [`NextPhase`](src/hexengine/server/game_server.py) when actions depleted. Client End Phase: turn action dock `end_phase` row → `action_request` `NextPhase` (server validates schedule); switching titles without reload is out of scope | med | — |
| 5 | Action economy (handshake) | — | Title should own per-action costs when generalized | [`GameServer._handle_action_request`](src/hexengine/server/game_server.py): after `execute(MoveUnit)`, `execute(SpendAction(1))`; then optional `NextPhase` | med | Configurable costs / post-execute hook; align any client-side “costs action” hints |
| 6 | Movement legality | Terrain on board / `LocationState` from scenario | Movement hooks (`movement_budget_for_unit`, ZOC, step cost); hexdemo reads unit `movement` attribute | Server [`_validate_move_unit_request`](src/hexengine/server/game_server.py) before `MoveUnit`. Client preview via **`unit_preview_request`** → [`server/preview.py`](src/hexengine/server/preview.py) (no local `compute_valid_moves`) | med | Stepwise arc + stricter catalog defaults; keep preview/validation in one module (done for preview) |
| 7 | Markers | Types/placements in TOML ([`marker_placements`](src/hexengine/scenarios/load/parse.py), etc.) | Optional `GameDefinition.marker_placement_rule` (hexdemo exposes property) | Server [`_marker_destination_allowed`](src/hexengine/server/game_server.py); preview via **`marker_preview_request`** + [`compute_marker_drag_preview`](src/hexengine/server/preview.py) | low | Custom hexdemo placement rules beyond engine default |
| 8 | RNG + audit | — | Future: title consumes rolls and applies combat/outcomes | [`RngService`](src/hexengine/gamedef/rng.py); [`rng_log`](src/hexengine/state/game_state.py) + wire in [`snapshot.py`](src/hexengine/state/snapshot.py); production gameplay paths do not call `RngService` yet — [`tests/test_rng_service.py`](tests/test_rng_service.py) | low now; med with undo + combat | Wire rolls into authoritative actions; keep draws server-side |
| 9 | Affordances (`InteractionKind`+) | — | Vocabulary in [`gamedef/interactions.py`](src/hexengine/gamedef/interactions.py) | No dedicated affordance routing layer in engine yet; actions go through existing protocol | low → med as surface grows | Map each interaction kind to title policy vs engine transport once used |

---

## Follow-ups (not duplicated in table)

- **`LOAD_SNAPSHOT`:** [`_handle_load_snapshot`](src/hexengine/server/game_server.py) replaces `ActionManager` state only; does not reset `markers` / `map_display` / graphics dicts — document trust model and field coverage.
- **Pack assets:** Dev server serves `/pack/<id>/`; production must mirror that mount. Scenario map backgrounds still use site-root-relative paths from `load_scenario(static_root=…)`.

Replace `Next` cells with issue links when you file tickets.
