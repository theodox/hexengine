"""
DisplayManager - Syncs display layer with committed game state.

This bridges the gap between immutable GameState and the mutable DOM/SVG display.
It observes state changes and updates displays accordingly, and handles temporary
preview visuals during drag operations.
"""

from typing import TYPE_CHECKING, Dict, Optional

from ..hexes.types import Hex
from ..units import DisplayUnit, GameUnit
from ..state import GameState
from ..units.graphics import DisplayUnit
from ..units.game import GameUnit

import logging


if TYPE_CHECKING:
    from ..map import Map


class DisplayManager:
    """
    Syncs display with committed game state.

    Key responsibilities:
    1. Create/update/remove DisplayUnit instances based on GameState
    2. Show temporary drag previews without affecting committed state
    3. Clear previews and restore committed positions

    This is the ONLY class that should modify display positions after initial setup.
    Game logic modifies GameState, DisplayManager syncs displays to match.
    """

    def __init__(self, map_canvas: "Map", game_board=None):
        """
        Initialize display manager.

        Args:
            map_canvas: The Map instance containing layers and layout
            game_board: Optional GameBoard instance for registering units
        """
        self._canvas = map_canvas
        self._board = game_board
        self._unit_displays: Dict[str, DisplayUnit] = {}
        self.logger = logging.getLogger("display_manager")

    def sync_from_state(self, game_state: GameState) -> None:
        """
        Update all displays to match committed game state.

        This is called:
        - On initial setup
        - After every action execution
        - After undo/redo

        Args:
            game_state: The current committed game state
        """
        # Update or create displays for all active units
        for unit_id, unit_state in game_state.board.units.items():
            if unit_state.active:
                if unit_id not in self._unit_displays:
                    self._create_unit_display(unit_state)
                else:
                    self._update_unit_display(unit_id, unit_state)

        # Remove displays for deleted/inactive units
        for unit_id in list(self._unit_displays.keys()):
            unit_state = game_state.board.units.get(unit_id)
            if unit_state is None or not unit_state.active:
                self._remove_unit_display(unit_id)

    def _create_unit_display(self, unit_state) -> None:
        """Create a new display for a unit."""

        # Map unit types to their graphics creators
        graphics_creators = self._get_graphics_creators()

        # Get the appropriate creator for this unit type
        creator_class = graphics_creators.get(unit_state.unit_type)
        if not creator_class:
            self.logger.error(
                f"No graphics creator for unit type {unit_state.unit_type}"
            )
            return

        # Register the creator's CSS if not already done
        creator_class.register()

        # Create display unit
        display = DisplayUnit(
            unit_id=unit_state.unit_id,
            unit_type=unit_state.unit_type,
            layout=self._canvas.hex_layout,
        )

        # Use the graphics creator to build the SVG elements
        creator = creator_class()
        creator.create(display)

        # Position it
        display.position = unit_state.position
        display.visible = unit_state.active

        from ..document import js

        self.logger.debug(
            f"Created unit {unit_state.unit_id}, visible={unit_state.active}, display attr={display.proxy.getAttribute('display')}"
        )

        # Add faction-based class
        display.push_classes(unit_state.faction.lower())

        # Add to layer - access the UnitLayer's SVG element directly
        unit_layer = self._canvas._unit_layer
        unit_layer._svg.appendChild(display.proxy)

        from ..document import js

        self.logger.debug(
            f"Added {unit_state.unit_id} to SVG with id: {unit_layer._svg.id}"
        )
        self.logger.debug(
            f"Unit parent: {display.proxy.parentElement.id if display.proxy.parentElement else 'None'}"
        )
        self.logger.debug(
            f"Unit has data-unit: {display.proxy.getAttribute('data-unit')}"
        )

        # Create GameUnit wrapper
        game_unit = GameUnit(
            unit_id=unit_state.unit_id,
            unit_type=unit_state.unit_type,
            unit_display=display,
        )
        game_unit.health = unit_state.health
        game_unit.active = unit_state.active

        # Add to board if available
        if self._board:
            # Check if position is occupied (from old state)
            if unit_state.position in self._board._board:
                # Remove old unit at this position first
                old_unit = self._board._board[unit_state.position]
                if old_unit.unit_id != unit_state.unit_id:
                    self.logger.warning(f"Replacing unit at {unit_state.position}")
                    del self._board._board[unit_state.position]
                    if old_unit.unit_id in self._board._units:
                        del self._board._units[old_unit.unit_id]

            # Add to board
            self._board._board[unit_state.position] = game_unit
            self._board._units[unit_state.unit_id] = game_unit

        # Track the display
        self._unit_displays[unit_state.unit_id] = display

    def _get_graphics_creators(self):
        """Get map of unit type to graphics creator class."""
        from ..game.scenarios.canuck import CanuckGraphicsCreator
        from ..game.scenarios.generic import GenericGraphicsCreator

        return {
            "canuck": CanuckGraphicsCreator,
            "soldier": GenericGraphicsCreator,
        }

    def _update_unit_display(self, unit_id: str, unit_state) -> None:
        """Update an existing display to match state."""
        display = self._unit_displays[unit_id]

        # Update position if changed
        if display.position != unit_state.position:
            display.position = unit_state.position

        # Update visibility
        display.visible = unit_state.active

        # Update health display if text element exists
        if display.text_element:
            display.set_text(str(unit_state.health))

    def _remove_unit_display(self, unit_id: str) -> None:
        """Remove a display unit."""
        if unit_id in self._unit_displays:
            display = self._unit_displays[unit_id]
            display.proxy.remove()
            del self._unit_displays[unit_id]

    def show_preview(
        self, unit_id: str, pixel_x: float, pixel_y: float, is_valid: bool
    ) -> None:
        """
        Show temporary drag preview at coordinates.

        This does NOT affect committed state - it's purely visual.
        The display will be moved to these coordinates and styled
        based on validity.

        Args:
            unit_id: ID of unit being previewed
            pixel_x: X coordinate (in map space, already inverse-transformed)
            pixel_y: Y coordinate (in map space, already inverse-transformed)
            is_valid: Whether the preview position is a valid move
        """
        display = self._unit_displays.get(unit_id)
        if display:
            # Debug: log unit type and coordinates
            unit_type = display.unit_type
            self.logger.debug(
                f"show_preview: unit={unit_id}, type={unit_type}, coords=({pixel_x:.1f}, {pixel_y:.1f})"
            )
            
            # Use map-space coordinates directly (no further transformation needed)
            display.display_at(pixel_x, pixel_y)

            # Style based on validity
            display.enabled = is_valid

    def clear_preview(self, unit_id: str, committed_position: Hex) -> None:
        """
        Clear preview and restore display to committed position.

        Args:
            unit_id: ID of unit to restore
            committed_position: The position from committed GameState
        """
        display = self._unit_displays.get(unit_id)
        if display:
            # Restore committed position
            x, y = self._canvas.hex_layout.hex_to_pixel(committed_position)
            display.position = committed_position

            # Restore enabled state
            display.enabled = True

    def get_display(self, unit_id: str) -> Optional[DisplayUnit]:
        """Get display unit by ID."""
        return self._unit_displays.get(unit_id)

    def highlight_hexes(self, hexes: set[Hex]) -> None:
        """
        Highlight a set of hexes (e.g., valid move targets).

        Args:
            hexes: Set of hex coordinates to highlight
        """
        # Delegate to map's draw_hexes method
        self._canvas.draw_hexes(hexes)

    def clear_highlights(self) -> None:
        """Clear all hex highlights."""
        self._canvas.svg_layer.clear()

    def refresh_unit_positions(self) -> None:
        """
        Recompute every unit's SVG transform from its hex and the current hex layout.

        Not needed for pan/zoom: those use CSS transforms on map layers while unit
        coordinates stay in map space. Call when hex layout parameters change.
        """
        for unit_id, display in self._unit_displays.items():
            # Re-apply the position to force recalculation with current layout
            hex_pos = display._hex
            x, y = self._canvas.hex_layout.hex_to_pixel(hex_pos)
            display.proxy.setAttribute("transform", f"translate({x},{y})")

        self.logger.debug("Refreshed %s unit positions", len(self._unit_displays))
