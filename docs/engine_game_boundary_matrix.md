# Engine / game boundary matrix

Inventory for checklist items 1–9 in [`.cursor/plans/test_game_boundary_plan.md`](../.cursor/plans/test_game_boundary_plan.md), plus **engine boundary 2** rows (match state split, combat policy). Implementation track: [`ENGINE_BOUNDARY_2_PLAN.md`](ENGINE_BOUNDARY_2_PLAN.md) (phases A–F). Rows were checked against the codebase (paths relative to repo root).

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
| 1 | GameRoot packaging | `games/<GameName>/scenarios/<id>/scenario.toml` (e.g. [`games/hexdemo/scenarios/default/scenario.toml`](games/hexdemo/scenarios/default/scenario.toml); title Python under `games/hexdemo/`) | Pack declares rota via manifest `entry_callable` → `load_game_definition()` (see [`games/template/engine_entry.py`](games/template/engine_entry.py) as a minimal example) | [`resolve_scenario_path_with_game_root`](src/hexengine/gameroot.py): default pack is **hexdemo** when `games/hexdemo` exists on a parent of the engine; CLI `--scenario-file`, `--game-root`, `--scenario-id`, zip → temp extract cache; fails if no pack resolves (no silent fallback to engine-only scenario). **`turn_rules.asset_base_url`** (`/pack/<id>/`); dev static server [`hexengine.dev.static_server`](src/hexengine/dev/static_server.py) | low | Production host must mount `/pack/<id>/` or rewrite to pack `resources/` |
| 2 | Scenario schema / loader | TOML + terrain / markers tables per [`src/hexengine/scenarios/load/parse.py`](src/hexengine/scenarios/load/parse.py) | — | [`load_scenario`](src/hexengine/scenarios/loader.py), [`scenario_to_initial_state`](src/hexengine/scenarios/loader.py) → [`GameState`](src/hexengine/state/game_state.py); snapshots wire `session_state`, `engine_state`, `session_state_key` ([`snapshot.py`](src/hexengine/state/snapshot.py)); display dicts from scenario model | low | Keep additive schema per [`docs/WIRE_COMPATIBILITY.md`](docs/WIRE_COMPATIBILITY.md) |
| 3 | Presentation vs simulation | `map_display`, `unit_graphics`, `marker_graphics`, asset paths in TOML | — | [`StateUpdate`](src/hexengine/server/protocol.py) carries `map_display`, `global_styles`, `unit_graphics`, `marker_graphics`, `markers`; server holds `GameServer.markers` parallel to `ActionManager` state | med | Pack HTTP + base URL for relative assets; clarify markers in undo/snapshot story |
| 4 | Turn schedule (game ↔ engine handshake) | — | [`GameDefinition.get_next_phase`](src/hexengine/gamedef/protocol.py); hexdemo [`ArcHook.TURN_ARC_REGISTRY`](games/hexdemo/hooks/arcs.py) + [`segment_blocks_routine_phase_advance`](src/hexengine/arcs/segment_wire.py) | Server: [`NextPhase`](src/hexengine/server/game_server.py) rejected when active segment omits `NextPhase`; auto-advance after move/attack via movement/attack hooks using [`arc_segment.phase_advance_blocked`](games/hexdemo/arc_segment.py) | med | — |
| 5 | Action economy (handshake) | — | Title owns auto-advance policy via movement/attack hooks; blocked when [`arc_segment.phase_advance_blocked`](games/hexdemo/arc_segment.py) (active segment omits `NextPhase`) | [`GameServer._handle_action_request`](src/hexengine/server/game_server.py): after `execute(MoveUnit)`, `execute(SpendAction(1))`; then [`_maybe_auto_advance_phase`](src/hexengine/server/game_server.py) | med | Configurable spend amounts per action type |
| 6 | Movement legality | Terrain on board / `LocationState` from scenario | `MovementHook` (`movement_budget_for_unit`, ZOC, step cost); hexdemo binds in [`hooks/movement.py`](games/hexdemo/hooks/movement.py) (unit `movement` attribute) | Server [`_validate_move_unit_request`](src/hexengine/server/game_server.py) before `MoveUnit`. Client preview via **`unit_preview_request`** → [`server/preview.py`](src/hexengine/server/preview.py) (no local `compute_valid_moves`) | med | Stepwise arc + stricter catalog defaults; keep preview/validation in one module (done for preview) |
| 7 | Markers | Types/placements in TOML ([`marker_placements`](src/hexengine/scenarios/load/parse.py), etc.) | Optional `GameDefinition.marker_placement_rule` (hexdemo exposes property) | Server [`_marker_destination_allowed`](src/hexengine/server/game_server.py); preview via **`marker_preview_request`** + [`compute_marker_drag_preview`](src/hexengine/server/preview.py) | low | Custom hexdemo placement rules beyond engine default |
| 8 | RNG + audit | — | Future: title consumes rolls and applies combat/outcomes | [`RngService`](src/hexengine/gamedef/rng.py); [`rng_log`](src/hexengine/state/game_state.py) + wire in [`snapshot.py`](src/hexengine/state/snapshot.py); production gameplay paths do not call `RngService` yet — [`tests/test_rng_service.py`](tests/test_rng_service.py) | low now; med with undo + combat | Wire rolls into authoritative actions; keep draws server-side |
| 9 | Affordances (`InteractionKind`+) | — | Preview policy per kind via bound hooks; hexdemo implements attack plan, retreat path, place marker; combat gate dock rows via [`combat_gate_panel_actions`](src/hexengine/authoring/patterns/combat.py) in title dock hook | [`InteractionKind`](src/hexengine/gamedef/interactions.py) enum; server dispatch [`map_selection_registry.py`](src/hexengine/hooks/map_selection_registry.py) → `map_selection_preview_request`; client apply table in [`client_map_selection_registry.py`](src/hexengine/game/arcs/client_map_selection_registry.py). **Draft storage = client; preview = consult; commit = authority** ([`TURN_ACTION_DOCK_CONTRACT.md` § Draft locus](docs/TURN_ACTION_DOCK_CONTRACT.md#draft-locus-invariant)). `inspect_unit` uses `INFORM_POPUP`, not map-selection | med | Add kinds by extending enum + registry row + client apply + title hook |
| 10 | Title match state bucket | `GameData.session_state_key` in [`game_data.toml`](games/hexdemo/resources/game_data.toml) | Pack module reads/writes bucket ([`session_state.py`](games/hexdemo/session_state.py)); combat graph in [`combat_transitions.py`](games/hexdemo/combat_transitions.py). `last_combat`, `retreat_obligations`, `advance`, `disrupt_instead_offered` are **pack conventions**; legacy `combat_gate` is not written (cleared on phase advance) | [`GameState.session_state`](src/hexengine/state/game_state.py), `session_state_key`, [`engine_read_session_state`](src/hexengine/state/engine_session_state.py) / [`PatchTitleBucket`](src/hexengine/state/actions.py); `engine_state` for `hexengine_*` keys (e.g. movement arc). Wire/snapshot: no combined `extension` map | med | Slim engine `Attack.apply` bucket writes; optional pack-local advance actions |
| 11 | Combat transitions & INFORM | — | Unified [`combat_rules.BINDING`](games/hexdemo/combat_rules.py) + [`combat_outcome.py`](games/hexdemo/combat_outcome.py); gate kinds / phase clear in [`combat_transitions.py`](games/hexdemo/combat_transitions.py); cleanup mutations in [`combat_actions.py`](games/hexdemo/combat_actions.py); INFORM in [`hooks/ui.py`](games/hexdemo/hooks/ui.py) + [`presentation/`](games/hexdemo/presentation/) | [`authority_attack`](src/hexengine/server/arcs/authority_attack.py) (`submit_event` on `SEG_ATTACK`, `restore_routine_cursor` on overlay done), [`authority_combat_cleanup`](src/hexengine/server/arcs/authority_combat_cleanup.py) (`ArcSpec.advance_move_detector` only); engine `Attack` / `ApplyCombatEffects` are board+rng only; `combat_event` fan-out from `UIHook.COMBAT_EVENT_SUMMARY`. **No hexdemo combat key literals in engine.** | none | — |

---

## Engine boundary 2 — quick reference

| Concern | Title | Engine |
|---------|-------|--------|
| Where is pack state? | `GameState.session_state` (one dict per match; key fixed at match start) | `GameState.engine_state` for ephemeral engine keys only |
| Who blocks `NextPhase`? | Active arc segment (`current_segment.allowed_actions`) | Server [`segment_blocks_routine_phase_advance`](src/hexengine/arcs/segment_wire.py) |
| Combat banners (INFORM) | `UIHook.COMBAT_INTERACTION_MESSAGES` or partial legacy hooks via catalog default | Merges phase row + hook/combat rows in `_interaction_messages_for_player_id` |
| Combat gate dock buttons | `combat_gate_panel_actions` in `TURN_ACTION_DOCK_FOR_VIEWER` | Catalog default dock: End Phase only; no gate row builder in `segment_wire` |
| `combat_event` wire (retreat UI) | `UIHook.COMBAT_EVENT_SUMMARY` → `CombatEventSummary` | `_broadcast_combat_events` fans out per viewer (no title bucket reads) |
| Post-attack bucket patches | `AttackHook.COMBAT_OUTCOME_AFTER_APPLIED` → hexdemo `combat_outcome.build_combat_outcome_after_applied` | Combat arc `attack` effect applies `CombatOutcome`; `classify` auto-advances; no `begin_combat_arc` on attack RPC |
| Routine cursor after cleanup | — | `restore_routine_cursor` when combat overlay completes (`drive_combat_arc_event` and successful arc `Attack`) |
| Post-retreat advance / disrupt / resolve advance | `CombatRulesBinding` methods on `BINDING` | Combat arc `submit_event` only; no `AttackHook` cleanup slots |
| Is this `MoveUnit` a combat advance? | `BINDING.detect_combat_advance_move` wired as `ArcSpec.advance_move_detector` | `authority_combat_cleanup.move_unit_is_combat_advance_fulfillment` |
| `combat_event` wire payload | `COMBAT_EVENT_SUMMARY` → `CombatEventSummary` | Fan-out per viewer + `COMBAT_INSTRUCTION_FOR_VIEWER`; `ENGINE_DEFAULT`/`None` = no combat events |

---

## Follow-ups (not duplicated in table)

- **`LOAD_SNAPSHOT`:** [`_handle_load_snapshot`](src/hexengine/server/game_server.py) replaces `ActionManager` state only; does not reset `markers` / `map_display` / graphics dicts — document trust model and field coverage.
- **Pack assets:** Dev server serves `/pack/<id>/`; production must mirror that mount. Scenario map backgrounds still use site-root-relative paths from `load_scenario(static_root=…)`.

Replace `Next` cells with issue links when you file tickets.
