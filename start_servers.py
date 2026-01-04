"""Start both HTTP and WebSocket game servers."""
import subprocess
import sys
import time
from pathlib import Path


def main():
    """Launch HTTP server and game server concurrently."""
    print("=" * 60)
    print("Starting Hexes Servers")
    print("=" * 60)
    print()
    
    # Start HTTP server for static files
    print("Starting HTTP server on http://localhost:8000")
    http_process = subprocess.Popen(
        [sys.executable, "-m", "http.server", "8000"],
        cwd=Path(__file__).parent
    )
    
    # Give HTTP server time to start
    time.sleep(1)
    
    # Start WebSocket game server
    print("Starting WebSocket game server on ws://localhost:8765")
    print()
    print("=" * 60)
    print("Servers running!")
    print("=" * 60)
    print("Open http://localhost:8000/hexes.html?mode=multi&name=Player1&faction=Red")
    print("Press Ctrl+C to stop both servers")
    print("=" * 60)
    print()
    
    # Import and run the async websocket server
    # This will block until interrupted
    try:
        import asyncio
        from hexengine.server.websocket_server import main as server_main
        asyncio.run(server_main())
    except KeyboardInterrupt:
        print("\n\nShutting down servers...")
    finally:
        http_process.terminate()
        http_process.wait()
        print("Servers stopped")


if __name__ == "__main__":
    main()
