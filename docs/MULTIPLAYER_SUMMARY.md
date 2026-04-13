# Multiplayer System Summary

## What We Built

A complete **server-authoritative multiplayer system** that treats single-player and multiplayer identically - the only difference is whether the server is local or remote.

## Architecture Overview

```
Client Layer (hexengine.client)
├── WebSocketClient        - Connects to server, sends actions, receives updates
├── LocalServerManager     - Starts local server for single-player (requires `game_definition=`)
├── UIState                - Local UI state (selections, previews)
└── DisplayManager         - Syncs game state to visual display

Server Layer (hexengine.server)
├── GameServer             - Game logic, action validation, state management (requires `game_definition=`)
├── WebSocketGameServer    - WebSocket transport layer (forwards `game_definition` to GameServer)
└── protocol.py            - Message types and serialization

Game Layer (hexengine.game)
├── Game                   - Base game class (local execution)
└── NetworkGame            - Network-enabled game (sends to server)
```

## Key Features

### 1. Server-Authoritative Design
- Server owns canonical GameState via ActionManager
- All actions validated server-side
- Clients cannot cheat or desync
- Turn order enforced by server

### 2. Unified Single/Multiplayer
```python
# Single-player (local server): resolves `games/…` pack, loads title rules, then starts embedded server
game = NetworkGame(use_local_server=True)

# Multiplayer (remote server)
game = NetworkGame(use_local_server=False, server_url="ws://server:8765")
```

Both use the same WebSocket protocol; local mode additionally needs a discoverable game pack on disk unless you pass explicit paths where the API supports it.

### 3. Clean Separation of Concerns
- **GameState**: Immutable game state (what happened)
- **UIState**: Mutable client state (what user is doing)
- **ActionManager**: Single mutation point (on server)
- **DisplayManager**: State → visuals (on client)

### 4. Preview System Integration
- Drag previews work locally (no server communication)
- Only committed moves sent to server
- Server validates before applying
- Invalid moves rejected with error message

## Message Flow Example

### Player Moves Unit

```
Client                     Server                   Other Clients
  |                          |                           |
  |--MoveUnit action-------->|                           |
  |                          | Validate:                 |
  |                          | - Is it player's turn?    |
  |                          | - Is move legal?          |
  |                          | - Does unit exist?        |
  |                          |                           |
  |<-ActionResult(success)---|                           |
  |                          |                           |
  |<-StateUpdate(new state)--|--StateUpdate(new state)-->|
  |                          |                           |
  | Display syncs            |                           | Display syncs
```

### Invalid Move Attempt

```
Client                     Server
  |                          |
  |--MoveUnit action-------->|
  |                          | Validate:
  |                          | ❌ Not your turn!
  |                          |
  |<-ActionResult(failed)----|
  |<-Error("Not your turn")|
  |                          |
  | Show error to user       |
```

## Files Created

### Server Infrastructure
- `src/hexengine/server/__init__.py` - Package exports
- `src/hexengine/server/protocol.py` - Message types and serialization
- `src/hexengine/server/game_server.py` - Core game server logic
- `src/hexengine/server/websocket_server.py` - WebSocket transport

### Client Infrastructure  
- `src/hexengine/client/websocket_client.py` - WebSocket client
- `src/hexengine/client/local_server.py` - Local server manager
- `src/hexengine/client/__init__.py` - Updated exports

### Game Integration
- `src/hexengine/game/network_game.py` - Network-enabled Game class
- `src/hexengine/game/__init__.py` - Export NetworkGame

### Documentation
- `SERVER_ARCHITECTURE.md` - Server design and protocol
- `MULTIPLAYER_INTEGRATION.md` - Integration guide
- `tests/test_network.py` - Headless `GameServer` / protocol usage examples

### Tests
- `tests/test_network.py` - Unit tests for networking

### Dependencies
- `pyproject.toml` - `websockets` is a core dependency; `dev` extras include pytest/ruff

## Protocol Messages

### Client → Server
- `JOIN_GAME` - Join game with name and faction
- `ACTION_REQUEST` - Request to execute action
- `LEAVE_GAME` - Disconnect from game

### Server → Client
- `STATE_UPDATE` - Full game state update
- `ACTION_RESULT` - Result of action attempt
- `PLAYER_JOINED` - Another player joined
- `PLAYER_LEFT` - Another player left
- `ERROR` - Error message

## How Existing Code Works

### Mouse Handlers (No Changes Needed!)

```python
# In mouse handler:
def _unit_mouseup(self, eventInfo):
    if preview.is_valid:
        action = MoveUnit(...)
        self.execute_action(action)  # ← This is polymorphic!
```

- `Game.execute_action()` → Executes locally via ActionManager
- `NetworkGame.execute_action()` → Sends to server via WebSocket

**Mouse handlers don't know the difference!**

### Action Execution Flow

**Before (Local):**
```python
game.execute_action(action)
  → action_mgr.execute(action)
    → state = action.apply(state)
      → observers notified
        → display syncs
```

**After (Network):**
```python
game.execute_action(action)
  → client.send_action(...)
    → [Network transmission]
      → server validates
        → server executes
          → server broadcasts
            → client receives state update
              → display syncs
```

## Usage

### Start Server

```bash
# Standalone server
python -m hexengine.server.websocket_server
```

### Single Player

```python
from hexengine.game import NetworkGame

game = NetworkGame(
    player_name="Alice",
    use_local_server=True  # Auto-starts server
)

await game.connect()
# Game ready - plays locally with server validation
```

### Multiplayer

```python
# Player 1 (faction strings must match the server's title, e.g. hexdemo: confederate | union)
game1 = NetworkGame(
    player_name="Alice",
    preferred_faction="union",
    server_url="ws://localhost:8765",
    use_local_server=False,
)
await game1.connect()

# Player 2
game2 = NetworkGame(
    player_name="Bob",
    preferred_faction="confederate",
    server_url="ws://localhost:8765",
    use_local_server=False,
)
await game2.connect()

# Both players see same state
# Actions from either are validated and broadcast
```

## Testing

```bash
# Install dev extras (pytest, ruff) if needed, then:
pytest tests/test_network.py -q
```

## Next Steps

1. **Update `__main__.py`** to use NetworkGame
2. **Add connection UI** showing:
   - Connected players
   - Current turn
   - Connection status
3. **Add error feedback** for:
   - "Not your turn"
   - "Invalid move"
   - "Connection lost"
4. **Add reconnection** handling
5. **Add game lobby** for matchmaking
6. **Deploy server** for internet play

## Benefits

✅ **Cheat-proof** - Server validates everything  
✅ **Network-ready** - Already built for multiplayer  
✅ **Testable** - Server logic independent of transport  
✅ **Clean code** - Mouse handlers unchanged  
✅ **Flexible** - Same code for single/multi player  
✅ **Scalable** - Server can handle multiple games  

## Current State

- [x] Server infrastructure complete
- [x] Client infrastructure complete
- [x] NetworkGame class implemented
- [x] Protocol defined and tested
- [x] Local server mode working
- [x] Documentation complete
- [ ] Main entry point updated
- [ ] Connection UI added
- [ ] Full integration testing
- [ ] Deployment configuration

The foundation is complete and ready for integration!
