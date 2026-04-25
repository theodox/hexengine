"""
Title-pack bridge: **all** engine imports of repository game code (``hexdemo``, …) go through here.

The ``hexes`` wheel ships only ``hexengine``; game rules live under ``games/<pack>/`` at repo
layout (or on ``sys.path`` after :func:`hexengine.gameroot.ensure_hexdemo_package_import_path`).
The WebSocket server, local server, and scenario bootstrap call :func:`gameroot.load_game_definition_for_scenario`,
which delegates into this package so there is a single, documented place that imports title
Python from disk.

Adding a new pack:

1. Implement ``<pack>_bridge.py`` with a small ``load_game_definition(...)`` (and any other
   hooks the engine should call through a stable name).
2. Extend :func:`hexengine.gameroot.load_game_definition_for_scenario` with path detection and
   ``sys.path`` setup for that pack, then call the new bridge.
"""
