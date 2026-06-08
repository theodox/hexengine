# Hexdemo hooks

This folder is where **title policy** lives. The engine calls it through different wiring paths.

**Start:** [`docs/TITLE_AUTHORING.md`](../../../docs/TITLE_AUTHORING.md) (author hub). This README is a **pack-local map**; wire detail is in [`docs/PACK_HOOK_CONTRACTS.md`](../../../docs/PACK_HOOK_CONTRACTS.md) and [`docs/TURN_ACTION_DOCK_CONTRACT.md`](../../../docs/TURN_ACTION_DOCK_CONTRACT.md).

## Three lanes

| Lane | Modules here | How the engine reaches it |
|------|----------------|---------------------------|
| **`TitleHooks`** (in-match) | `movement.py`, `attack.py`, `ui.py`, `overlays.py`, `arcs.py` | `HexdemoGameDefinition.hooks` → `build_hooks()` in `__init__.py` |
| **Manifest title-load** | `title_load.py` | `hexengine_pack.toml` `[hooks.title_load]` + client connect arc (`SPLASH` / `SETUP` segments) |
| **Phase transition** | `game_config.py` → `combat_transitions` | `HexdemoGameDefinition.after_phase_transition` (not `TitleHooks`) |

**Arc segments** (resolve scenario, boot local server, WebSocket, dismiss splash) are engine-owned in `hexengine.game.arcs.client_title_load`. Only the title-load **hooks** above are pack Python.

## Rules vs hooks

These are **layers**, not two different species of title code.

| | **Rules** (policy) | **Hooks** (integration) |
|--|-------------------|-------------------------|
| **Answers** | What is legal? What does movement cost? | When does the engine ask, and in what API shape? |
| **Style** | Pure functions: `GameState` (+ args) → values / sets / violations | Named slots on `TitleHooks`, manifest title-load, or server injectables |
| **Depends on** | State and title data only (no WebSocket, DOM, `GameServer`) | Arcs, RPC handlers, connect pipeline, phase callbacks |
| **Testing** | Direct tests on `GameState` | Often needs hook assembly or server host |
| **Opt out** | N/A — this *is* the title law when invoked | May return `ENGINE_DEFAULT` for engine catalog defaults |

**Healthy pattern:** hooks stay thin; they call into **rules** modules.

```text
MoveUnit / movement arc  →  MovementHook.*  →  hooks/movement.py  →  ../movement/rules.py (+ ../state retreat reads)
Attack RPC               →  combat arc attack segment → BINDING.attack_arc_effect
                         →  AttackHook.* (preview, auto-advance) → hooks/attack.py → ../combat/rules.py
Combat cleanup RPCs      →  combat arc       →  hooks/arcs.py      →  ../combat/arc.py → ../combat/rules.BINDING
```

Hexdemo today:

| Rules (policy) | Hook adapters |
|----------------|---------------|
| `../combat/rules.py` — `BINDING`: CRT, validate, outcome, arc guards/effects | `attack.py`, `arcs.py` |
| `../combat/outcome.py` — post-attack `BucketPatch` builder | `attack.py` → `COMBAT_OUTCOME_AFTER_APPLIED` |
| `../combat/actions.py` — retreat/disrupt/advance state actions | Called from `BINDING` only |
| `../combat/transitions.py` — gate `ui_mode` strings, phase-scoped clear, planning block | Used by arc spec + `game_config` |
| `../movement/rules.py` — budget, ZoC, step cost, retreat constraints | `movement.py` |
| `../state/session_state.py` — session-state reads (`bucket()`, retreat helpers) | `movement_rules`, `combat/rules` |
| `../marker_rules.py` — `MarkerPlacementRule` factory | Injected on `GameServer`, not `TitleHooks` |

Keep **one coherent policy** in pack modules when it is reused (server validation + client preview + unit tests). Movement legality lives in [`movement/rules.py`](../movement/rules.py); `hooks/movement.py` is adapters only.

Longer term, the engine may offer **composable rule pieces** (ZOC, terrain, morale, …) that titles assemble declaratively, with custom rules alongside — see `docs/RULE_COMPOSITION.md` (planning only; not implemented).

## `TitleHooks` modules (sketch)

| Module | Role | Wired via |
|--------|------|-----------|
| `movement.py` | Wires `movement.rules.BINDING`; retreat path preview | `MOVEMENT_HOOKS` dict |
| `../movement/rules.py` | Budget, ZoC, retreat constraints, step cost, auto-advance | Called from hooks; tests import directly |
| `../movement/retreat_preview.py` | Retreat path map-selection preview | `retreat_path_preview` hook slot |
| `attack.py` | Thin adapters: validate, resolve, outcome, plan preview, auto-advance | `@bind_title_hook(AttackHook.…)` — no cleanup slots |
| `../combat/rules.py` | `HexdemoCombatRules` / `BINDING`: CRT, validate, arc guards/effects, `attack_arc_effect` | `ArcHook.COMBAT_RULES_BINDING` |
| `../combat/outcome.py` | `build_combat_outcome_after_applied` → `CombatOutcome` | Called from binding / `attack.py` |
| `../combat/arc.py` | `combat_rules_binding_to_arc_spec` + owner resolver | `ArcHook.COMBAT_ARC` via `hooks/arcs.py` |
| `arcs.py` | `COMBAT_ARC`, `COMBAT_RULES_BINDING`, `TURN_ARC_REGISTRY` | `@bind_title_hook(ArcHook.…)` |
| `ui.py` | Phase/combat banners, inspect, inform popups, combat event summary | `@bind_title_hook(UIHook.…)`; copy from `presentation/` |
| `../presentation/inform.py` | INFORM map callouts keyed by `inform_profile` + `reason` | Used by `ui.inform_popup_for_viewer` |
| `../presentation/interaction_messages.py` | Combat/advance banner copy for `interaction_messages` | Used by `ui.combat_interaction_messages` |
| `turn_action_dock.py` | Commit dock — `combat_gate_panel_actions` + End Phase; returns `TurnDockPanel` from `hexengine.authoring.present`; copy via [`segment_ui.py`](../segment_ui.py) + [`presentation/`](../presentation/) | `@bind_title_hook(UIHook.TURN_ACTION_DOCK_FOR_VIEWER)` |
| `segment_presentation.py` | `presentation_id` / `interaction_mode` on `current_segment` wire | `@bind_title_hook(UIHook.ENRICH_CURRENT_SEGMENT)` |
| `segment_ui_registry.py` | Exposes `PRESENTATION_BY_UI_MODE` for P5 load-time validation | `@bind_title_hook(UIHook.SEGMENT_PRESENTATION_REGISTRY)` |
| `arcs.py` | Turn arc registry + combat arc declarations | `@bind_title_hook(ArcHook.…)` |
| `markers.py` | Place-marker map-selection preview | `@bind_title_hook(UIHook.PLACE_MARKER_PREVIEW)` |
| `../ui_markup.py` | HTML templates + flag URLs (tier 2–3; `hexengine.ui.display`) | Imported by `ui.py`, `turn_action_dock.py` |
| `../resources/templates/` | `phase_banner.html`, `unit_inspect.html`, `dock_gate.html` | Loaded by `ui_markup` |
| `../resources/flags/` | Example faction SVGs (banner `<img>`, optional `unit_graphics`) | See `flags/README.md` |
| `overlays.py` | Map overlay glyphs | UI hooks |

Implementations may return `hexengine.hooks.ENGINE_DEFAULT` to defer to engine catalog defaults. Combat schedules that include an attack/combat phase need `validate_attack` and `resolve_attack` present (see `validate_title_contract`).

## Manifest title-load (`title_load.py`)

Declared in `hexengine_pack.toml`:

- `present_splash(html)` — client; HTML from `resources/splash.html`
- `run_setup(ctx) -> TitleLoadResult` — client; v1 always continues connect

Today the engine is **fault-tolerant** if a callable is missing; future packs should treat manifest keys as explicit contracts (`docs/TITLE_LOAD_HOOKS.md`).

## Adding title behavior

1. **Shared policy** — add or extend a pack module (`state/session_state.py`, …): pure `GameState` in/out.
2. **In-match integration** — wire a **hook** in `hooks/*.py` with `bind_title_hook`; call the rules module from the hook body; ensure `build_hooks()` still assembles it.
3. **Connect / splash / lobby** — `title_load.py` or a future manifest table.
4. **Phase entry** — `after_phase_transition` in `game_config.py` (e.g. `combat_transitions`).

Optional future layout: `hexdemo/rules/` for policy modules and `hexdemo/hooks/` only as adapters.

## See also

- Author hub: [`docs/TITLE_AUTHORING.md`](../../../docs/TITLE_AUTHORING.md)
- Pack overview: `../README.md`
- Policy modules: `../marker_rules.py`, `../state/session_state.py`
- Boundary matrix (movement legality): `docs/engine_game_boundary_matrix.md`
- Engine hook authoring: `hexengine.hooks` package docstring
- Title-load detail: `docs/TITLE_LOAD_HOOKS.md`
- Contract roadmap: `docs/PACK_HOOK_CONTRACTS.md`
