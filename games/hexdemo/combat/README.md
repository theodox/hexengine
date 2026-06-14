# Hexdemo combat

**Start here for post-attack flow:** [`graph.py`](graph.py) — the combat arc FSM (segments and transitions).

## Reading order

| File | Answers |
|------|---------|
| [`graph.py`](graph.py) | What segments exist? What events move the arc? |
| [`rules.py`](rules.py) | CRT, guards, effects, `attack_arc_effect` |
| [`transitions.py`](transitions.py) | Gate `ui_mode` strings; when End Phase / attack planning is blocked |
| [`actions.py`](actions.py) | State mutations (retreat step, disrupt, advance) |
| [`outcome.py`](outcome.py) | `CombatOutcome` / bucket patch after attack |
| [`arc.py`](arc.py) | `ArcSpec` wrapper (owner resolver, hook export) |
| [`../ui/segment_registry.py`](../ui/segment_registry.py) | Presentation per `ui_mode` |
| [`../arcs/wiring.py`](../arcs/wiring.py) | `ArcHook` wiring (`TitleHooks.arcs`) |

## Attack path (one line)

`Attack` RPC → interaction commit segment (hexdemo: `attack`, from declared graph) → `BINDING.attack_arc_effect` → `classify` → retreat / advance gates or done.

Preview and CRT validation use `InteractionHook` slots in [`../hooks/interaction.py`](../hooks/interaction.py); authoritative commit runs through the arc only.

## Customizing the graph

Edit `graph.py` when changing segment topology. Keep guards/effects in `rules.py`. Gate `ui_mode` strings must stay aligned across `transitions.py`, `graph.py` segment `ui_mode` args, and `ui/segment_registry.py`.

Pack graph must stay aligned with engine `build_combat_cleanup_arc` unless you intentionally fork; see `tests/test_authoring_combat_pattern.py`.
