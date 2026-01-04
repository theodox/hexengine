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
    
    def __init__(self, map_canvas: "Map"):
        """
        Initialize display manager.
        
        Args:
            map_canvas: The Map instance containing layers and layout
        """
        self._canvas = map_canvas
        self._unit_displays: Dict[str, DisplayUnit] = {}
        
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
        # Import here to avoid circular dependency
        from ..units.graphics import DisplayUnit
        
        # Create display unit
        display = DisplayUnit(
            unit_id=unit_state.unit_id,
            unit_type=unit_state.unit_type,
            layout=self._canvas.hex_layout
        )
        
        # Get graphics creator for this unit type
        # TODO: Need to look up the appropriate graphics creator based on unit_type
        # For now, we'll need to integrate with existing unit creation system
        
        # Position it
        display.position = unit_state.position
        display.visible = unit_state.active
        
        # Add to layer
        self._canvas.units._svg.appendChild(display.proxy)
        
        # Track it
        self._unit_displays[unit_state.unit_id] = display
    
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
        self, 
        unit_id: str, 
        pixel_x: float, 
        pixel_y: float, 
        is_valid: bool
    ) -> None:
        """
        Show temporary drag preview at pixel coordinates.
        
        This does NOT affect committed state - it's purely visual.
        The display will be moved to these coordinates and styled
        based on validity.
        
        Args:
            unit_id: ID of unit being previewed
            pixel_x: X pixel coordinate
            pixel_y: Y pixel coordinate
            is_valid: Whether the preview position is a valid move
        """
        display = self._unit_displays.get(unit_id)
        if display:
            # Move to preview position
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
        self._canvas.svg._svg.clear()
