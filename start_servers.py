"""Start both HTTP and WebSocket game servers."""

from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path

BASE_URL = "http://localhost:8000/hexes.html"


def _wait_tcp_port(
    host: str, port: int, *, timeout_s: float = 30.0, poll_s: float = 0.05
) -> bool:
    """Return True once something accepts TCP connections on host:port."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.4):
                return True
        except OSError:
            time.sleep(poll_s)
    return False


def main():
    """Launch HTTP server and game server concurrently."""
    from hexengine.gameroot import add_game_launch_arguments

    parser = argparse.ArgumentParser(
        description="Start HTTP static server and WebSocket game server"
    )
    add_game_launch_arguments(parser)
    args = parser.parse_args()

    player1_url = f"{BASE_URL}?mode=multi&name=Player1&faction=confederate"
    player2_url = f"{BASE_URL}?mode=multi&name=Player2&faction=union"

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

    if not _wait_tcp_port("127.0.0.1", 8000, timeout_s=15.0):
        print("ERROR: HTTP server did not become ready on port 8000", file=sys.stderr)
        http_process.terminate()
        http_process.wait()
        sys.exit(1)

    # Start WebSocket game server in a thread so we can open the browser after it's ready
    print("Starting WebSocket game server on ws://localhost:8765")
    server_error = None
    ws_listen_ready = threading.Event()

    def run_websocket_server():
        nonlocal server_error
        try:
            import asyncio

            from hexengine.server.websocket_server import main as server_main

            asyncio.run(
                server_main(
                    scenario_file=args.scenario_file,
                    game_root=args.game_root,
                    scenario_id=args.scenario_id,
                    listen_ready_event=ws_listen_ready,
                )
            )
        except Exception as e:
            server_error = e
            traceback.print_exc()
    server_thread = threading.Thread(target=run_websocket_server, daemon=True)
    server_thread.start()

    # Wait until websockets.serve() is listening (do not TCP-probe 8765: a bare connect
    # then close sends no HTTP upgrade and the server logs InvalidMessage / EOFError).
    deadline = time.monotonic() + 120.0
    ws_ready = False
    while time.monotonic() < deadline:
        if server_error is not None:
            break
        if ws_listen_ready.wait(timeout=0.05):
            ws_ready = True
            break

    if server_error is not None:
        print("ERROR: WebSocket server failed to start:", file=sys.stderr)
        traceback.print_exception(
            type(server_error),
            server_error,
            server_error.__traceback__,
            file=sys.stderr,
        )
        http_process.terminate()
        http_process.wait()
        sys.exit(1)

    if not ws_ready:
        print(
            "ERROR: WebSocket server did not become ready on port 8765 (timeout)",
            file=sys.stderr,
        )
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
    webbrowser.open(player1_url)
    webbrowser.open(player2_url)

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
