"""
Test to verify the key requirement: clean preview without state corruption.

This test demonstrates that units can appear to move during drag operations
without the underlying game state being modified until the action is committed.
"""

from hexengine.hexes.types import Hex
from hexengine.state import (
    GameState, ActionManager, AddUnit, MoveUnit,
    compute_valid_moves
)
from hexengine.client import UIState


def test_preview_doesnt_corrupt_state():
    """Verify that drag preview doesn't modify committed game state."""
    
    print("Setting up game...")
    game_state = GameState.create_empty()
    action_mgr = ActionManager(game_state)
    ui_state = UIState()
    
    # Add a unit at origin
    original_pos = Hex(0, 0, 0)
    action_mgr.execute(AddUnit(
        unit_id="test-unit",
        unit_type="tank",
        faction="Blue",
        position=original_pos
    ))
    
    print(f"✓ Unit added at {original_pos}")
    
    # Verify initial state
    state1 = action_mgr.current_state
    assert state1.board.units["test-unit"].position == original_pos
    print(f"✓ Confirmed: committed state has unit at {original_pos}")
    
    # === SIMULATE DRAG OPERATION ===
    print("\n--- Starting drag simulation ---")
    
    # User clicks and starts dragging
    ui_state.select_unit("test-unit")
    ui_state.start_drag("test-unit", original_pos, 100.0, 100.0)
    print("✓ Drag started (UI state only)")
    
    # Compute where user CAN move (from committed state)
    valid_moves = compute_valid_moves(action_mgr.current_state, "test-unit", 4.0)
    ui_state.set_constraints(valid_moves)
    print(f"✓ Computed {len(valid_moves)} valid moves from committed state")
    
    # User drags to several different positions
    drag_positions = [
        (150.0, 120.0, Hex(1, 0, -1)),
        (200.0, 140.0, Hex(2, 0, -2)),
        (180.0, 160.0, Hex(1, 1, -2)),
    ]
    
    for pixel_x, pixel_y, hover_hex in drag_positions:
        ui_state.update_drag(pixel_x, pixel_y, hover_hex)
        
        # CRITICAL CHECK: State should NEVER change during drag
        state_during_drag = action_mgr.current_state
        unit_position = state_during_drag.board.units["test-unit"].position
        
        assert unit_position == original_pos, \
            f"STATE CORRUPTED! Unit moved to {unit_position} during drag!"
        
        print(f"✓ Dragged over {hover_hex} - state still has unit at {original_pos}")
    
    print("\n--- Drag preview complete ---")
    
    # Verify state hasn't changed after all that dragging
    state_after_drag = action_mgr.current_state
    assert state_after_drag.board.units["test-unit"].position == original_pos
    print(f"✓ After extensive dragging, committed state unchanged: {original_pos}")
    
    # === COMMIT THE MOVE ===
    print("\n--- Committing move ---")
    
    final_preview = ui_state.end_drag()
    target_hex = Hex(1, 0, -1)
    
    if final_preview and final_preview.is_valid:
        # NOW we modify state via action
        action_mgr.execute(MoveUnit(
            unit_id="test-unit",
            from_hex=original_pos,
            to_hex=target_hex
        ))
        print(f"✓ Move committed via ActionManager")
    
    # Verify state NOW changed
    final_state = action_mgr.current_state
    assert final_state.board.units["test-unit"].position == target_hex
    print(f"✓ Committed state now has unit at {target_hex}")
    
    # Verify old state reference is still unchanged (immutability)
    assert state1.board.units["test-unit"].position == original_pos
    print(f"✓ Old state reference still shows unit at {original_pos} (immutability!)")
    
    print("\n" + "=" * 60)
    print("✅ SUCCESS: Preview system works without state corruption!")
    print("=" * 60)
    print("\nKey points demonstrated:")
    print("1. Drag operations update UI state only")
    print("2. Committed game state never changes during drag")
    print("3. State only changes when action is executed")
    print("4. Old state references remain unchanged (immutability)")


def test_invalid_drop_no_state_change():
    """Verify that invalid drops don't modify state."""
    
    print("\n\nTesting invalid drop scenario...")
    
    game_state = GameState.create_empty()
    action_mgr = ActionManager(game_state)
    ui_state = UIState()
    
    # Add a unit
    original_pos = Hex(0, 0, 0)
    action_mgr.execute(AddUnit(
        unit_id="test-unit",
        unit_type="tank",
        faction="Blue",
        position=original_pos
    ))
    
    state_before = action_mgr.current_state
    
    # Start drag
    ui_state.select_unit("test-unit")
    ui_state.start_drag("test-unit", original_pos, 100.0, 100.0)
    
    # Drag to an INVALID position (far away, unreachable)
    invalid_hex = Hex(100, -50, -50)  # Way out of range
    ui_state.update_drag(500.0, 500.0, invalid_hex)
    
    # End drag (invalid drop)
    preview = ui_state.end_drag()
    
    # Don't commit because invalid
    if not preview.is_valid:
        print("✓ Drop was invalid, no action executed")
    
    # Verify state UNCHANGED
    state_after = action_mgr.current_state
    assert state_after.board.units["test-unit"].position == original_pos
    print(f"✓ State unchanged after invalid drop: unit still at {original_pos}")
    
    # In fact, state object is THE SAME (no new state created)
    assert state_before is state_after
    print("✓ State object is literally the same instance (no mutation occurred)")
    
    print("\n✅ Invalid drops correctly leave state unchanged!")


def test_undo_after_preview():
    """Verify that undo works correctly after preview operations."""
    
    print("\n\nTesting undo after preview...")
    
    game_state = GameState.create_empty()
    action_mgr = ActionManager(game_state)
    ui_state = UIState()
    
    # Add unit
    pos1 = Hex(0, 0, 0)
    action_mgr.execute(AddUnit(
        unit_id="test-unit",
        unit_type="tank",
        faction="Blue",
        position=pos1
    ))
    
    state_after_add = action_mgr.current_state
    
    # Do a drag preview and commit
    ui_state.select_unit("test-unit")
    ui_state.start_drag("test-unit", pos1, 100.0, 100.0)
    
    # Compute valid moves
    valid_moves = compute_valid_moves(action_mgr.current_state, "test-unit", 4.0)
    ui_state.set_constraints(valid_moves)
    
    pos2 = Hex(1, 0, -1)
    ui_state.update_drag(150.0, 120.0, pos2)
    preview = ui_state.end_drag()
    
    if preview and preview.is_valid:
        action_mgr.execute(MoveUnit("test-unit", pos1, pos2))
    
    state_after_move = action_mgr.current_state
    assert state_after_move.board.units["test-unit"].position == pos2
    print(f"✓ Unit moved to {pos2}")
    
    # Now undo
    action_mgr.undo()
    state_after_undo = action_mgr.current_state
    assert state_after_undo.board.units["test-unit"].position == pos1
    print(f"✓ After undo, unit back at {pos1}")
    
    # Redo
    action_mgr.redo()
    state_after_redo = action_mgr.current_state
    assert state_after_redo.board.units["test-unit"].position == pos2
    print(f"✓ After redo, unit at {pos2} again")
    
    print("\n✅ Undo/redo works correctly with preview system!")


if __name__ == "__main__":
    test_preview_doesnt_corrupt_state()
    test_invalid_drop_no_state_change()
    test_undo_after_preview()
    
    print("\n" + "=" * 60)
    print("🎉 ALL TESTS PASSED!")
    print("=" * 60)
    print("\nThe preview system successfully:")
    print("  ✓ Allows visual drag without state corruption")
    print("  ✓ Only commits changes via ActionManager.execute()")
    print("  ✓ Leaves state unchanged on invalid drops")
    print("  ✓ Works seamlessly with undo/redo")
    print("  ✓ Maintains immutability guarantees")
