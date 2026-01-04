# Multiplayer Server Architecture

## Overview

The game uses a **server-authoritative** architecture where:
- Server owns the canonical `GameState` via `ActionManager`
- Clients send action requests to server
- Server validates and executes actions
- Server broadcasts state updates to all clients
- Clients render the state they receive

This architecture works identically for single-player (client connects to local server) and multiplayer (multiple clients connect to remote server).

## Components

### Server Layer (`hexengine.server`)

**`GameServer`** - Transport-agnostic game logic
- Owns `ActionManager` (single source of truth)
- Validates action requests (turn order, legality)
- Executes actions and broadcasts state
- Manages player connections and faction assignments

**`WebSocketGameServer`** - WebSocket transport layer
- Wraps `GameServer` with WebSocket handling
- Routes messages between clients and `GameServer`
- Manages WebSocket connections

**`protocol.py`** - Communication protocol
- Defines message types (ACTION_REQUEST, STATE_UPDATE, etc.)
- Serialization/deserialization (JSON)
- Message structures (ActionRequest, StateUpdate, etc.)

## Message Flow

### Client Sends Action

```
Client                    WebSocket Server              GameServer
  |                              |                           |
  |--MoveUnit action------------>|                           |
  |                              |--handle_message()--------->|
  |                              |                           |
  |                              |                      Validate turn
  |                              |                      Execute action
  |                              |                           |
  |<-ActionResult(success)-------|<--------------------------|
  |                              |                           |
  |<-StateUpdate (new state)-----|<--broadcast_state_update--|
  |                              |                           |
```

### Player Joins Game

```
Client                    WebSocket Server              GameServer
  |                              |                           |
  |--JoinGameRequest------------>|                           |
  |                              |--handle_message()--------->|
  |                              |                           |
  |                              |                    Assign faction
  |                              |                    Register player
  |                              |                           |
  |<-StateUpdate (full state)----|<--------------------------|
  |                              |                           |
  |                              |--broadcast_player_joined->|
  |                              |                           |
```

## Protocol Messages

### Client → Server

**JOIN_GAME**
```json
{
  "type": "join_game",
  "payload": {
    "player_name": "Alice",
    "faction": "Blue"  // optional, auto-assigned if null
  }
}
```

**ACTION_REQUEST**
```json
{
  "type": "action_request",
  "payload": {
    "action_type": "MoveUnit",
    "player_id": "player-uuid",
    "params": {
      "unit_id": "tank-1",
      "from_hex": {"i": 0, "j": 0, "k": 0},
      "to_hex": {"i": 1, "j": 0, "k": -1}
    }
  }
}
```

### Server → Client

**STATE_UPDATE**
```json
{
  "type": "state_update",
  "payload": {
    "game_state": {
      "board": { ... },
      "turn": { ... }
    },
    "sequence_number": 42
  }
}
```

**ACTION_RESULT**
```json
{
  "type": "action_result",
  "payload": {
    "success": true,
    "action_id": "action-uuid"
  }
}
```

**ERROR**
```json
{
  "type": "error",
  "payload": {
    "error": "Not your turn (current: Blue)"
  }
}
```

## Server Validation

The server validates every action:

1. **Authentication** - Is the player in the game?
2. **Turn Order** - Is it this player's turn?
3. **Action Legality** - Is the action valid in current state?
4. **State Consistency** - Does the action match expected state?

Invalid actions are rejected with an error message.

## Single Player Setup

For single-player, the client starts a local server:

```python
# Start local server in background thread
server = GameServer()

# Client connects to localhost
# All interactions go through same protocol
# Only difference: server is local instead of remote
```

## Running the Server

### Standalone WebSocket Server

```python
python -m hexengine.server.websocket_server
```

Server runs on `ws://localhost:8765` by default.

### Custom Setup

```python
from hexengine.server import GameServer, WebSocketGameServer
from hexengine.state import GameState

# Create initial state
initial_state = GameState.create_empty()

# Option 1: Transport-agnostic server
game_server = GameServer(initial_state)

# Option 2: WebSocket server
ws_server = WebSocketGameServer(
    host="0.0.0.0",
    port=8765,
    initial_state=initial_state
)
await ws_server.start()
```

## Client Integration

The client needs minimal changes:

1. **Connect to server** (local or remote)
2. **Send actions** instead of executing directly
3. **Listen for state updates** and render
4. **Preview locally** (same as before, just don't send invalid actions)

```python
# OLD: Direct execution
action_mgr.execute(MoveUnit(...))

# NEW: Send to server
action_request = ActionRequest(
    action_type="MoveUnit",
    params={...},
    player_id=my_id
)
send_to_server(action_request.to_message())

# Listen for response
on_state_update(new_state):
    display_mgr.sync_from_state(new_state)
```

## Security Considerations

Current implementation is basic. For production:

- [ ] Add authentication/authorization
- [ ] Encrypt WebSocket connection (WSS)
- [ ] Rate limiting
- [ ] Input validation
- [ ] Session management
- [ ] Reconnection handling with state sync

## Dependencies

```bash
# For WebSocket server
pip install websockets

# Or add to pyproject.toml
[project.optional-dependencies]
server = ["websockets>=12.0"]
```

## Next Steps

1. Create client-side WebSocket wrapper
2. Update mouse handlers to send actions to server
3. Add reconnection logic
4. Implement spectator mode
5. Add game lobby for matchmaking
