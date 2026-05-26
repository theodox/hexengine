"""
HTTP static server with pack asset routing for local play.

Serves the site root (repo root when started via ``start_servers.py``) and maps
``GET /pack/<pack_id>/<path>`` to ``games/<pack_id>/resources/<path>``.
"""

from __future__ import annotations

import argparse
import http.server
import sys
from functools import partial
from pathlib import Path
from urllib.parse import unquote


def _repo_root_from_here() -> Path:
    return Path(__file__).resolve().parents[3]


def _games_directory(site_root: Path) -> Path | None:
    games = site_root / "games"
    return games if games.is_dir() else None


def resolve_pack_static_file(games_dir: Path, url_path: str) -> Path | None:
    """
    Map ``/pack/<pack_id>/<rel>`` to ``games/<pack_id>/resources/<rel>`` when safe.
    """
    decoded = unquote(url_path)
    if not decoded.startswith("/pack/"):
        return None
    parts = [p for p in decoded.split("/") if p]
    if len(parts) < 3:
        return None
    pack_id = parts[1]
    rel_parts = parts[2:]
    if ".." in rel_parts:
        return None
    candidate = (games_dir / pack_id / "resources" / Path(*rel_parts)).resolve()
    resources_root = (games_dir / pack_id / "resources").resolve()
    try:
        candidate.relative_to(resources_root)
    except ValueError:
        return None
    if candidate.is_file():
        return candidate
    return None


class PackAwareStaticHandler(http.server.SimpleHTTPRequestHandler):
    """Serve site files and pack resources under ``/pack/<pack_id>/``."""

    games_dir: Path | None = None

    def translate_path(self, path: str) -> str:
        if self.games_dir is not None:
            resolved = resolve_pack_static_file(self.games_dir, path)
            if resolved is not None:
                return str(resolved)
        return super().translate_path(path)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        if args and isinstance(args[0], str) and args[0].startswith("GET /pack/"):
            return
        super().log_message(format, *args)


def serve(
    directory: Path | str,
    *,
    host: str = "",
    port: int = 8000,
) -> None:
    """Run until interrupted."""
    root = Path(directory).resolve()
    games = _games_directory(root)

    PackAwareStaticHandler.games_dir = games

    class _Handler(PackAwareStaticHandler):
        pass

    with http.server.ThreadingHTTPServer(
        (host, port),
        partial(_Handler, directory=str(root)),
    ) as httpd:
        print(f"Serving {root} at http://localhost:{port}/")
        if games is not None:
            print(f"Pack assets: http://localhost:{port}/pack/<pack_id>/...")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Pack-aware static HTTP server")
    parser.add_argument(
        "--directory",
        "-d",
        type=Path,
        default=_repo_root_from_here(),
        help="HTTP site root (default: repo root)",
    )
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="")
    args = parser.parse_args(argv)
    serve(args.directory, host=args.host, port=args.port)


if __name__ == "__main__":
    main(sys.argv[1:])
