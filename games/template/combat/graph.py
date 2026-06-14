"""
Interaction aftermath graph (outline only — template pack).

This file is a **reading map**, not executable graph code. The move-only template
does not bind ``ArcHook.COMBAT_ARC``. When you enable interaction:

1. Copy ``games/hexdemo/combat/graph.py`` into this pack and customize topology.
2. Wire guards/effects in ``combat/rules.py`` (``CombatRulesBinding``).
3. Keep gate ``ui_mode`` strings aligned across ``combat/transitions.py``,
   graph segment args, and ``ui/segment_registry.py`` (or ``segment_ui.py``).
4. Expose ``ArcSpec`` from ``combat/arc.py`` and bind via ``hooks/arcs.py`` or
   ``arcs/wiring.py``.

Until then, ``games/template/combat_arc.py`` can use
``combat_rules_binding_to_arc_spec`` (engine convenience — graph lives in
``src/hexengine/authoring/patterns/combat.py``).

Hexdemo reference flow (after ``Attack`` commit):

    classify → retreat gates → resolve loop → advance gate → done

See ``games/hexdemo/combat/README.md`` and
``docs/TITLE_AUTHORING.md`` § Interaction arc graph.
"""

__all__: list[str] = []
