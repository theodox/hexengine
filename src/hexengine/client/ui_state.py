"""
Client-side UI state - ephemeral, not synced to server.

This represents temporary UI state like selections, hover effects, and drag previews.
Unlike GameState, this is MUTABLE and local to the client.
"""

from dataclasses import dataclass, field
from typing import Optional

from ..hexes.types import Hex


@dataclass
class DragPreview:
    """Represents a drag-in-progress preview.
    
    This is temporary visual state - the unit hasn't actually moved in the
    game state yet. Only when the drag completes with a valid target does
    an action get sent to the ActionManager to commit the move.
    """
    unit_id: str
    visual_position: tuple[float, float]  # Pixel coordinates for display
    original_position: Hex  # Where the unit actually is in game state
    potential_target: Optional[Hex]  # Hex we're hovering over
    is_valid: bool  # Whether the potential target is a legal move
    
    def with_position(self, pixel_x: float, pixel_y: float) -> "DragPreview":
        """Update the visual position."""
        return DragPreview(
            unit_id=self.unit_id,
            visual_position=(pixel_x, pixel_y),
            original_position=self.original_position,
            potential_target=self.potential_target,
            is_valid=self.is_valid,
        )
    
    def with_target(self, target_hex: Optional[Hex], is_valid: bool) -> "DragPreview":
        """Update the potential target."""
        return DragPreview(
            unit_id=self.unit_id,
            visual_position=self.visual_position,
            original_position=self.original_position,
            potential_target=target_hex,
            is_valid=is_valid,
        )


@dataclass
class UIState:
    """Client-side UI state.
    
    This is mutable and local - it doesn't affect game state and isn't
    synchronized over the network. It tracks things like:
    - What unit is selected
    - What hex we're hovering over
    - Drag preview state
    - Valid movement constraints for the selected unit
    """
    
    # Selection
    selected_unit_id: Optional[str] = None
    
    # Hover/cursor state
    hover_hex: Optional[Hex] = None
    
    # Drag preview (only set during active drag)
    drag_preview: Optional[DragPreview] = None
    
    # Valid moves for selected unit (computed from game state)
    movement_constraints: set[Hex] = field(default_factory=set)
    
    def select_unit(self, unit_id: Optional[str]) -> None:
        """Select a unit (or clear selection if None)."""
        self.selected_unit_id = unit_id
        if unit_id is None:
            self.movement_constraints.clear()
    
    def start_drag(self, unit_id: str, original_position: Hex, 
                   pixel_x: float, pixel_y: float) -> None:
        """Start a drag preview."""
        self.drag_preview = DragPreview(
            unit_id=unit_id,
            visual_position=(pixel_x, pixel_y),
            original_position=original_position,
            potential_target=None,
            is_valid=False,
        )
    
    def update_drag(self, pixel_x: float, pixel_y: float, 
                    target_hex: Optional[Hex]) -> None:
        """Update drag preview position and target."""
        if self.drag_preview is None:
            return
        
        is_valid = target_hex in self.movement_constraints if target_hex else False
        self.drag_preview = self.drag_preview.with_position(pixel_x, pixel_y)
        self.drag_preview = self.drag_preview.with_target(target_hex, is_valid)
    
    def end_drag(self) -> Optional[DragPreview]:
        """End drag preview and return the final preview state."""
        preview = self.drag_preview
        self.drag_preview = None
        return preview
    
    def set_constraints(self, constraints: set[Hex]) -> None:
        """Set the valid movement hexes for the selected unit."""
        self.movement_constraints = constraints
    
    def clear_constraints(self) -> None:
        """Clear movement constraints."""
        self.movement_constraints.clear()
    
    def is_dragging(self) -> bool:
        """Check if a drag is currently in progress."""
        return self.drag_preview is not None
