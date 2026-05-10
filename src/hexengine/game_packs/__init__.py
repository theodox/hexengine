"""
Game pack loading for the hexes wheel (engine ships hexengine only).

Rules live under games/<pack_id>/ with a small manifest:

- hexengine_pack.toml — pack.id, python.path_add, python.entry_module,
  python.entry_callable (see hexengine.game_packs.registry).

hexengine.gameroot.load_game_definition_for_scenario resolves the owning pack from the
scenario path and imports the declared entry callable (no per-title branches in gameroot).
"""
