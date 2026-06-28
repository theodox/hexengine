# Hexdemo arcs (match flow)

**Turn rota:** [`turn_schedule.py`](turn_schedule.py) — `hexdemo_schedule_slots` and `build_hexdemo_turn_arc_registry` (authoritative). Wired once on `ArcHook.TURN_ARC_REGISTRY` via [`wiring.py`](wiring.py) → `hooks.build_hooks()`.

**Arc hook wiring:** [`wiring.py`](wiring.py) — `@bind_title_hook(ArcHook.…)` for turn registry, movement arc preset (`ENGINE_MOVEMENT_ARC_PRESET`), combat arc spec, and combat rules binding.

**Combat subgraph:** [`../combat/graph.py`](../combat/graph.py) — post-attack FSM (read for segment topology).

**Segment reads:** [`segment.py`](segment.py) — `current_segment` projection, `phase_advance_blocked`, action legality helpers.

## Reading order

| File | Answers |
|------|---------|
| `turn_schedule.py` | When does each faction move/attack? |
| `../combat/graph.py` | What happens after `Attack`? |
| `wiring.py` | How flow is exposed on `TitleHooks.arcs` |
| `../combat/rules.py` | Guards, effects, CRT behind the combat graph |
| `../hooks/modification.py`, `../hooks/interaction.py` | Movement and attack policy hook slots |
