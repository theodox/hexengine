"""Start both HTTP and WebSocket game servers."""
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path

BASE_URL = "http://localhost:8000/hexes.html"
PLAYER1_URL = f"{BASE_URL}?mode=multi&name=Player1&faction=Red"
PLAYER2_URL = f"{BASE_URL}?mode=multi&name=Player2&faction=Blue"


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
        cwd=Path(__file__).parent,
    )

    # Give HTTP server time to start
    time.sleep(1)

    # Start WebSocket game server in a thread so we can open the browser after it's ready
    print("Starting WebSocket game server on ws://localhost:8765")
    server_error = None

    def run_websocket_server():
        nonlocal server_error
        try:
            import asyncio
            from hexengine.server.websocket_server import main as server_main
            asyncio.run(server_main())
        except Exception as e:
            server_error = e
            traceback.print_exc()

    server_thread = threading.Thread(target=run_websocket_server, daemon=True)
    server_thread.start()

    # Wait for WebSocket server to be ready (or to fail)
    time.sleep(2)

    if server_error is not None:
        print("ERROR: WebSocket server failed to start:", file=sys.stderr)
        traceback.print_exception(type(server_error), server_error, server_error.__traceback__, file=sys.stderr)
        http_process.terminate()
        http_process.wait()
        sys.exit(1)

    print()
    print("=" * 60)
    print("Servers running!")
    print("=" * 60)
    print("Opening browser with two player tabs...")
    print("Press Ctrl+C to stop both servers")
    print("=" * 60)
    print()

    # Open two tabs: one for each player
    webbrowser.open(PLAYER1_URL)
    webbrowser.open(PLAYER2_URL)

    try:
        server_thread.join()
    except KeyboardInterrupt:
        print("\n\nShutting down servers...")
    finally:
        http_process.terminate()
        http_process.wait()
        print("Servers stopped")


if __name__ == "__main__":
    main()
