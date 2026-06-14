# Hexdemo arcs (match flow)

**Turn rota:** [`turn_schedule.py`](turn_schedule.py) — faction × phase schedule and routine arc registry.

**Arc hook wiring:** [`wiring.py`](wiring.py) — `@bind_title_hook(ArcHook.…)` for turn registry, combat arc spec, and combat rules binding. Assembled via [`../hooks/__init__.py`](../hooks/__init__.py) `build_hooks()`.

**Combat subgraph:** [`../combat/graph.py`](../combat/graph.py) — post-attack FSM (read for segment topology).

**Segment reads:** [`segment.py`](segment.py) — `current_segment` projection, `phase_advance_blocked`, action legality helpers.

## Reading order

| File | Answers |
|------|---------|
| `turn_schedule.py` | When does each faction move/attack? |
| `../combat/graph.py` | What happens after `Attack`? |
| `wiring.py` | How flow is exposed on `TitleHooks.arcs` |
| `../combat/rules.py` | Guards, effects, CRT behind the combat graph |
| `../hooks/movement.py`, `../hooks/attack.py` | Movement and attack policy hook slots |
