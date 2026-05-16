"""Title-owned match configuration (non-executable data), distinct from `TitleHooks`.

Parsed on the client from `turn_rules` via `hexengine.gamedef.client_title_data.ClientTitleData`.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any


@dataclass(frozen=True, slots=True)
class GameData:
    """Declarative knobs mirrored into `StateUpdate.turn_rules` (v1 wire fields only)."""

    gamedata_schema: int = 1
    max_active_units_per_hex: int | None = None
    movement_budget_attribute_key: str | None = None
    title_state_extension_key: str | None = None
    faction_display_names: dict[str, str] = field(default_factory=dict)
    faction_css_classes: dict[str, str] = field(default_factory=dict)
    title_css_file: str | None = None
    title_css: str | None = None
    hex_highlight_ui: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "faction_display_names", dict(self.faction_display_names)
        )
        object.__setattr__(self, "faction_css_classes", dict(self.faction_css_classes))
        object.__setattr__(self, "hex_highlight_ui", dict(self.hex_highlight_ui))

    @staticmethod
    def empty() -> GameData:
        """Default built-in / test definitions with no title wire overrides."""
        return GameData()

    def replacing(self, **changes: Any) -> GameData:
        """Return a copy with selected fields replaced (e.g. scenario overrides)."""
        return replace(self, **changes)


__all__ = ["GameData"]
