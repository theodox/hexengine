"""
Example usage of the new immutable state system.

This demonstrates how the new architecture separates game state from UI concerns
and enables clean preview functionality without corrupting committed state.
"""

from hexengine.hexes.types import Hex
from hexengine.state import (
    GameState, UnitState, BoardState, TurnState,
    ActionManager, MoveUnit, AddUnit, DeleteUnit,
    compute_valid_moves
)
from hexengine.client import UIState


def example_basic_usage():
    """Basic example: create state, add units, move them."""
    
    # 1. Create initial game state
    game_state = GameState.create_empty(
        initial_faction="Blue",
        initial_phase="Movement"
    )
    
    # 2. Create action manager (gatekeeper for all state changes)
    action_mgr = ActionManager(game_state)
    
    # 3. Add some units via actions
    add_tank = AddUnit(
        unit_id="tank-1",
        unit_type="tank",
        faction="Blue",
        position=Hex(0, 0, 0),
        health=100
    )
    action_mgr.execute(add_tank)
    
    add_soldier = AddUnit(
        unit_id="soldier-1", 
        unit_type="infantry",
        faction="Red",
        position=Hex(2, -1, -1),
        health=50
    )
    action_mgr.execute(add_soldier)
    
    # 4. Get current state (read-only)
    current = action_mgr.current_state
    print(f"Units: {list(current.board.units.keys())}")
    print(f"Tank position: {current.board.units['tank-1'].position}")
    
    # 5. Move a unit
    move = MoveUnit(
        unit_id="tank-1",
        from_hex=Hex(0, 0, 0),
        to_hex=Hex(1, 0, -1)
    )
    action_mgr.execute(move)
    
    # 6. State has changed, but old reference is unchanged (immutability!)
    print(f"Old state still has tank at: {current.board.units['tank-1'].position}")
    print(f"New state has tank at: {action_mgr.current_state.board.units['tank-1'].position}")
    
    # 7. Undo!
    action_mgr.undo()
    print(f"After undo, tank at: {action_mgr.current_state.board.units['tank-1'].position}")
    
    # 8. Redo!
    action_mgr.redo()
    print(f"After redo, tank at: {action_mgr.current_state.board.units['tank-1'].position}")


def example_drag_preview():
    """Example: drag preview without corrupting state."""
    
    # Setup
    game_state = GameState.create_empty()
    action_mgr = ActionManager(game_state)
    ui_state = UIState()
    
    # Add a unit
    action_mgr.execute(AddUnit(
        unit_id="tank-1",
        unit_type="tank", 
        faction="Blue",
        position=Hex(0, 0, 0)
    ))
    
    # === USER CLICKS ON UNIT ===
    ui_state.select_unit("tank-1")
    
    # Compute valid moves from COMMITTED state
    valid_moves = compute_valid_moves(
        action_mgr.current_state,
        unit_id="tank-1",
        movement_budget=4.0
    )
    ui_state.set_constraints(valid_moves)
    
    print(f"Valid moves: {valid_moves}")
    
    # === USER STARTS DRAGGING ===
    ui_state.start_drag(
        unit_id="tank-1",
        original_position=Hex(0, 0, 0),
        pixel_x=100.0,
        pixel_y=100.0
    )
    
    # === USER DRAGS OVER DIFFERENT HEXES ===
    # Update preview (just visual, no state change!)
    ui_state.update_drag(
        pixel_x=150.0,
        pixel_y=120.0,
        target_hex=Hex(1, 0, -1)
    )
    
    # Check if this hex is valid
    if ui_state.drag_preview.is_valid:
        print(f"Dragging over valid hex: {ui_state.drag_preview.potential_target}")
        # Update display to show unit at visual position with "valid" highlight
    else:
        print("Dragging over invalid hex")
        # Update display to show unit at visual position with "invalid" highlight
    
    # === USER RELEASES MOUSE ===
    final_preview = ui_state.end_drag()
    
    # IMPORTANT: Game state is still unchanged!
    original_position = action_mgr.current_state.board.units["tank-1"].position
    print(f"State still shows tank at: {original_position}")
    
    # Only commit if valid
    if final_preview and final_preview.is_valid and final_preview.potential_target:
        move = MoveUnit(
            unit_id=final_preview.unit_id,
            from_hex=final_preview.original_position,
            to_hex=final_preview.potential_target
        )
        action_mgr.execute(move)  # NOW state changes
        print(f"Committed move! Tank now at: {action_mgr.current_state.board.units['tank-1'].position}")
    else:
        print("Invalid drop - unit returns to original position (no state change needed!)")


def example_observer_pattern():
    """Example: using observers to sync display with state."""
    
    game_state = GameState.create_empty()
    action_mgr = ActionManager(game_state)
    
    # Define an observer that syncs display
    def sync_display_with_state(new_state: GameState):
        """Called whenever state changes."""
        print(f"\n=== STATE CHANGED ===")
        print(f"Turn: {new_state.turn.current_faction} - {new_state.turn.current_phase}")
        print(f"Units in game: {len(new_state.board.units)}")
        for unit_id, unit in new_state.board.units.items():
            if unit.active:
                print(f"  - {unit_id}: {unit.faction} {unit.unit_type} at {unit.position}")
        print("=" * 40)
    
    # Register observer
    action_mgr.add_observer(sync_display_with_state)
    
    # Now any action triggers the observer
    action_mgr.execute(AddUnit(
        unit_id="tank-1",
        unit_type="tank",
        faction="Blue", 
        position=Hex(0, 0, 0)
    ))
    
    action_mgr.execute(MoveUnit(
        unit_id="tank-1",
        from_hex=Hex(0, 0, 0),
        to_hex=Hex(1, 0, -1)
    ))
    
    action_mgr.execute(DeleteUnit(unit_id="tank-1"))
    
    action_mgr.undo()  # Observer called again!


def example_serialization():
    """Example: state is fully serializable for save/load/network."""
    
    import json
    from dataclasses import asdict
    
    # Create some state
    game_state = GameState.create_empty()
    action_mgr = ActionManager(game_state)
    
    action_mgr.execute(AddUnit(
        unit_id="tank-1",
        unit_type="tank",
        faction="Blue",
        position=Hex(0, 0, 0)
    ))
    
    # Serialize to JSON
    state_dict = asdict(action_mgr.current_state)
    
    # Would need custom serializer for Hex, but the structure is clean:
    print("Serializable state structure:")
    print(json.dumps(state_dict, indent=2, default=str))
    
    # For network sync, you'd send just the action:
    # Client -> Server: {"action": "MoveUnit", "unit_id": "tank-1", "from": ..., "to": ...}
    # Server executes action, sends new state to all clients
    # Clients update their local state


if __name__ == "__main__":
    print("=" * 60)
    print("EXAMPLE 1: Basic Usage")
    print("=" * 60)
    example_basic_usage()
    
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Drag Preview Without State Corruption")
    print("=" * 60)
    example_drag_preview()
    
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Observer Pattern for Display Sync")
    print("=" * 60)
    example_observer_pattern()
    
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Serialization")
    print("=" * 60)
    example_serialization()
