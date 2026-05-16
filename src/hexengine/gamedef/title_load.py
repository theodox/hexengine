"""
Title-load **pack hook** context and results (`[hooks.title_load]` in hexengine_pack.toml).

The browser runs a **client title-load arc** (`hexengine.game.arcs.client_title_load`)
with engine-owned segments (resolve scenario, boot local server, connect). Segments
named splash and setup invoke pack callables declared in the manifest; other segments
are engine-only. See that module for segment vs hook vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class TitleLoadContext:
    """Inputs for the optional pre-connect setup hook."""

    pack_id: str
    pack_root: Path
    scenario_path: Path


@dataclass(frozen=True, slots=True)
class TitleLoadResult:
    """Outcome of the setup hook; `continue_connect=False` aborts `Game.connect()`."""

    continue_connect: bool = True


__all__ = ["TitleLoadContext", "TitleLoadResult"]
