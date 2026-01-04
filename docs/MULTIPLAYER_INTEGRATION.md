# Multiplayer Integration Guide

## Overview

The multiplayer system treats all games identically - whether single-player or multiplayer, the client always communicates with a server. The only difference is whether the server is local (same process) or remote (network).

## Quick Start

### Single Player (Local Server)

```python
from hexengine.game import NetworkGame

game = NetworkGame(
    server_url="ws://localhost:8765",
    player_name="Alice",
    preferred_faction="Blue",
    use_local_server=True  # Auto-starts local server
)

await game.connect()
```

### Multiplayer (Remote Server)

```python
game = NetworkGame(
    server_url="ws://game-server.com:8765",
    player_name="Bob",
    use_local_server=False  # Connect to remote
)

await game.connect()
```

## Architecture

```
Single Player:
┌─────────┐
│  Client │ ──────┐
│   UI    │       │
└─────────┘       │
                  ↓
            ┌──────────┐
            │  Local   │
            │  Server  │
            └──────────┘

Multiplayer:
┌─────────┐         ┌──────────┐
│ Client  │────────→│          │
│  (P1)   │←────────│  Remote  │
└─────────┘         │  Server  │
                    │          │
┌─────────┐         │          │
│ Client  │────────→│          │
│  (P2)   │←────────│          │
└─────────┘         └──────────┘
```

## Key Classes

### `NetworkGame` (Client)

Extends the base `Game` class to send actions to server instead of executing locally.

**Key Methods:**
- `connect()` - Connect to server and join game
- `disconnect()` - Disconnect from server
- `execute_action(action)` - Override that sends action to server
- `is_my_turn()` - Check if it's your turn

**Key Callbacks:**
- `on_state_update` - Called when server sends new state
- `on_connection_change` - Called when connection status changes
- `on_error` - Called on errors
- `on_action_result` - Called when server responds to your action

### `WebSocketClient`

Handles WebSocket communication with server.

**Features:**
- Automatic connection management
- Message serialization/deserialization
- Turn validation
- State synchronization

### `LocalServerManager`

Starts a local server for single-player.

**Usage:**
```python
manager = LocalServerManager(initial_state)
manager.start(port=8765)
```

## How Actions Work

### Old (Direct Execution)

```python
# Action executed immediately on client
action = MoveUnit(unit_id, from_hex, to_hex)
game.action_mgr.execute(action)
```

### New (Server-Authoritative)

```python
# Action sent to server
action = MoveUnit(unit_id, from_hex, to_hex)
game.execute_action(action)  # Sends to server

# Server validates:
# - Is it your turn?
# - Is the move legal?
# - Does the unit exist?

# If valid:
# - Server executes action
# - Server broadcasts new state to all clients
# - Clients update displays

# If invalid:
# - Server sends error
# - Client shows error to user
# - State unchanged
```

## Mouse Handler Integration

The mouse handlers already work correctly! They call `game.execute_action()`, which:

1. **Before (local):** Executed action immediately via ActionManager
2. **Now (network):** Sends action to server, waits for state update

No changes needed to mouse handlers - they're transport-agnostic.

## Turn Validation

Server validates turn order:

```python
# Server checks:
if player.faction != current_state.turn.current_faction:
    send_error("Not your turn")
    return

# Client can pre-validate for UX:
if not game.is_my_turn():
    show_message("Wait for your turn")
    return
```

## State Synchronization

```python
# Server broadcasts state after each action
StateUpdate {
    game_state: {...},  # Full GameState
    sequence_number: 42  # For ordering
}

# Client receives and updates display
def _handle_state_update(new_state):
    self.display_mgr.sync_from_state(new_state)
```

## Preview System

Preview system works identically:

```python
# During drag (local only, not sent to server):
game.ui_state.update_drag(pixel_x, pixel_y, target_hex)
game.display_mgr.show_preview(...)

# On drop (sent to server):
if preview.is_valid:
    action = MoveUnit(...)
    game.execute_action(action)  # → Server
```

## Error Handling

### Connection Errors

```python
client.on_error = lambda error: show_error_popup(error)
```

### Action Errors

```python
client.on_action_result = lambda success, error: (
    show_success() if success else show_error(error)
)
```

### Connection Loss

Server marks player as disconnected but preserves their state. When reconnecting:

```python
# Server sends full state on reconnect
await client.connect()  # Rejoins with same player_id
```

## Running the Server

### Standalone Server

```bash
# Terminal 1: Start server
python -m hexengine.server.websocket_server

# Terminal 2: Start client 1
python main.py  # Connect to localhost:8765

# Terminal 3: Start client 2
python main.py  # Also connect to localhost:8765
```

### Embedded Server (Single Player)

```python
# Server starts automatically
game = NetworkGame(use_local_server=True)
await game.connect()  # Starts server, then connects
```

## Migration Checklist

- [x] Create server infrastructure (GameServer, WebSocketServer)
- [x] Create client infrastructure (WebSocketClient)
- [x] Create NetworkGame class
- [x] LocalServerManager for single-player
- [ ] Update main entry point to use NetworkGame
- [ ] Add UI for connection status
- [ ] Add UI for "not your turn" feedback
- [ ] Add reconnection logic
- [ ] Add game lobby/matchmaking

## Next Steps

1. **Update `__main__.py`** to instantiate `NetworkGame` instead of `Game`
2. **Add connection UI** showing connected players
3. **Add turn indicator** showing whose turn it is
4. **Test with two clients** connecting to same server
5. **Deploy server** for remote multiplayer

## Example Usage

See [examples/network_game_example.py](../examples/network_game_example.py) for:
- Single-player setup
- Multiplayer setup
- Two-client local testing

## Dependencies

```bash
# Required for networking
pip install websockets
```

Or add to `pyproject.toml`:
```toml
[project.optional-dependencies]
multiplayer = ["websockets>=12.0"]
```
