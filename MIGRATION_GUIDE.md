# State System Refactoring - Migration Guide

## Overview

This refactor separates game state from display/UI concerns, enabling:
- ✅ Clean preview system (drag units without corrupting state)
- ✅ Immutable state (easier reasoning, undo/redo, time-travel debugging)
- ✅ Client-server ready (state is serializable, actions are commands)
- ✅ Testable (pure functions for state transitions)

## Architecture

### Three Layers

```
┌─────────────────────────────────────────────┐
│  STATE LAYER (server + client)              │
│  - GameState (immutable)                    │
│  - ActionManager (gatekeeper)               │
│  - Actions (pure state transformations)     │
└─────────────────────────────────────────────┘
                    ↑
                    │ observes
                    │
┌─────────────────────────────────────────────┐
│  CLIENT LAYER (client only)                 │
│  - UIState (selection, drag preview)        │
│  - DisplayManager (syncs display with state)│
└─────────────────────────────────────────────┘
                    ↑
                    │ renders
                    │
┌─────────────────────────────────────────────┐
│  DISPLAY LAYER (client only)                │
│  - DisplayUnit (DOM/SVG manipulation)       │
│  - Map rendering                            │
└─────────────────────────────────────────────┘
```

## Key Components

### State Layer (`src/hexengine/state/`)

**game_state.py**
- `UnitState` - Pure unit data (no display)
- `BoardState` - All units and locations
- `TurnState` - Turn/phase/faction info
- `GameState` - Complete game state

All frozen dataclasses with helper methods like `with_position()`.

**action_manager.py**
- `ActionManager` - Single point for state mutations
- Methods: `execute()`, `undo()`, `redo()`
- Observer pattern for display sync

**actions.py**
- `MoveUnit` - Move a unit
- `DeleteUnit` - Deactivate a unit
- `AddUnit` - Add a new unit
- `SpendAction` - Spend action points

All actions have `apply(state) -> new_state` and `revert(state) -> new_state`.

**logic.py**
- `compute_valid_moves()` - Calculate legal moves
- `compute_reachable_hexes()` - Pathfinding
- Pure functions that read state without modifying

### Client Layer (`src/hexengine/client/`)

**ui_state.py**
- `UIState` - Local UI state (selection, hover)
- `DragPreview` - Temporary drag visual state

Mutable, not synced to server.

## Migration Strategy

### Phase 1: Parallel Systems ✅ DONE

- [x] Create new state layer alongside old code
- [x] Create ActionManager
- [x] Create new state-based actions
- [x] Create UIState and DragPreview

### Phase 2: Create Display Manager (NEXT)

Create `src/hexengine/client/display_manager.py`:

```python
class DisplayManager:
    """Syncs display with committed game state."""
    
    def __init__(self, map_canvas: Map):
        self._canvas = map_canvas
        self._unit_displays: dict[str, DisplayUnit] = {}
    
    def sync_from_state(self, game_state: GameState):
        """Update displays to match committed state."""
        # Create/update displays for all units
        for unit_id, unit_state in game_state.board.units.items():
            if unit_id not in self._unit_displays:
                self._create_unit_display(unit_state)
            else:
                self._update_unit_display(unit_id, unit_state)
        
        # Remove displays for deleted/inactive units
        for unit_id in list(self._unit_displays.keys()):
            unit_state = game_state.board.units.get(unit_id)
            if unit_state is None or not unit_state.active:
                self._remove_unit_display(unit_id)
    
    def show_preview(self, unit_id: str, pixel_x: float, pixel_y: float, 
                    is_valid: bool):
        """Show drag preview (temporary, doesn't affect state)."""
        display = self._unit_displays.get(unit_id)
        if display:
            display.display_at(pixel_x, pixel_y)
            display.enabled = is_valid
    
    def clear_preview(self, unit_id: str, committed_position: Hex):
        """Clear preview, return to committed position."""
        display = self._unit_displays.get(unit_id)
        if display:
            x, y = self._canvas.hex_layout.hex_to_pixel(committed_position)
            display.position = committed_position
            display.enabled = True
```

### Phase 3: Refactor Game Class

Update `src/hexengine/game/game.py`:

**OLD:**
```python
class Game:
    def __init__(self):
        self.board = GameBoard(self.canvas)  # Mutable state
        self.selection = None
```

**NEW:**
```python
class Game:
    def __init__(self):
        # State management
        initial_state = GameState.create_empty()
        self.action_mgr = ActionManager(initial_state)
        
        # Client-side UI state
        self.ui_state = UIState()
        
        # Display sync
        self.display_mgr = DisplayManager(self.canvas)
        self.action_mgr.add_observer(self.display_mgr.sync_from_state)
        
        # Initialize display from state
        self.display_mgr.sync_from_state(self.action_mgr.current_state)
```

### Phase 4: Refactor Mouse Handlers

Update `src/hexengine/game/events/mouse.py`:

**OLD (mutates state during drag):**
```python
def _unit_drag(self, eventInfo):
    if not self.selection:
        return
    self.selection.display_at(*eventInfo.position)  # Direct mutation!
```

**NEW (preview only, no state mutation):**
```python
def _unit_drag(self, eventInfo):
    if not self.ui_state.selected_unit_id:
        return
    
    # Compute constraints from COMMITTED state
    state = self.action_mgr.current_state
    unit = state.board.units[self.ui_state.selected_unit_id]
    constraints = compute_valid_moves(state, unit.unit_id, movement_budget=4.0)
    self.ui_state.set_constraints(constraints)
    
    # Update UI state (no game state change!)
    self.ui_state.update_drag(
        pixel_x=eventInfo.position[0],
        pixel_y=eventInfo.position[1],
        target_hex=eventInfo.hex
    )
    
    # Update display preview (visual only)
    if self.ui_state.drag_preview:
        self.display_mgr.show_preview(
            unit_id=self.ui_state.drag_preview.unit_id,
            pixel_x=eventInfo.position[0],
            pixel_y=eventInfo.position[1],
            is_valid=self.ui_state.drag_preview.is_valid
        )
```

**OLD (commits on mouseup):**
```python
def _unit_mouseup(self, eventInfo):
    if eventInfo.hex in self.board.constraints:
        move = Move(self.selection.unit_id, self.selection.position, eventInfo.hex)
        self.enqueue(move)  # Old system
```

**NEW:**
```python
def _unit_mouseup(self, eventInfo):
    preview = self.ui_state.end_drag()
    
    if not preview:
        return
    
    # Clear preview visually
    state = self.action_mgr.current_state
    unit = state.board.units[preview.unit_id]
    self.display_mgr.clear_preview(preview.unit_id, unit.position)
    
    # Commit if valid
    if preview.is_valid and preview.potential_target:
        action = MoveUnit(
            unit_id=preview.unit_id,
            from_hex=preview.original_position,
            to_hex=preview.potential_target
        )
        self.action_mgr.execute(action)  # ONLY state mutation point!
```

### Phase 5: Update Hotkeys

**OLD:**
```python
@Hotkey("z", Modifiers.CONTROL)
def undo(self):
    if self._history_pointer > 0:
        self._history_pointer -= 1
        move = self._moves[self._history_pointer]
        move.undo(self.board)  # Direct mutation
```

**NEW:**
```python
@Hotkey("z", Modifiers.CONTROL)  
def undo(self):
    self.action_mgr.undo()
    # Display automatically syncs via observer!
```

### Phase 6: Remove Old Code

Once everything works with the new system:
- Remove `GameBoard._selection`
- Remove `GameBoard._constraints` 
- Remove `GameBoard.hilite()` / `clear_hilite()`
- Remove mutation methods from `GameUnit`
- Remove old `Action` protocol and old `Move`/`DeleteUnit`
- Remove `GameHistoryMixin` (replaced by ActionManager)

## Testing the New System

Run the example:
```bash
python EXAMPLE_NEW_STATE_SYSTEM.py
```

This demonstrates:
1. Basic usage (create state, execute actions)
2. Drag preview without state corruption
3. Observer pattern for display sync
4. Serialization for save/load/network

## Benefits Recap

**Before:**
- State scattered across Game, GameBoard, GameUnit
- Display logic mixed with state
- Drag operations directly mutate unit positions
- Undo/redo manually manages bidirectional mutations
- Can't serialize state for network

**After:**
- Single source of truth (ActionManager.current_state)
- Pure state (GameState) separate from display (DisplayManager)
- Preview is visual-only, state unchanged until commit
- Undo/redo is built-in (event sourcing)
- State is fully serializable (frozen dataclasses)

## Next Steps

1. Create DisplayManager
2. Add ActionManager to Game class
3. Refactor one mouse handler (start with unit drag)
4. Test thoroughly
5. Gradually migrate other handlers
6. Remove old code once everything works
