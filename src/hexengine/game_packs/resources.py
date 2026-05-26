"""Resolve pack-owned files under `<pack_root>/resources/`."""

from __future__ import annotations

import inspect
import re
from pathlib import Path
from typing import Any

# Browser URL prefix for pack-owned files under ``games/<pack_id>/resources/``.
PACK_ASSET_URL_PREFIX = "/pack"

_PACK_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")


def resolve_pack_resource_path(pack_root: Path, rel: str) -> Path | None:
    """
    Return an existing file under `pack_root/resources/` for a relative path.

    Rejects absolute paths and `..` segments (same convention as scenario assets).
    """
    raw = (rel or "").strip()
    if not raw:
        return None
    p = Path(raw)
    if p.is_absolute() or ".." in p.parts:
        return None
    candidate = (pack_root.resolve() / "resources" / p).resolve()
    try:
        candidate.relative_to(pack_root.resolve())
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    return candidate


def read_pack_resource_text(pack_root: Path, rel: str) -> str | None:
    """Read UTF-8 text from `pack_root/resources/<rel>` if present."""
    path = resolve_pack_resource_path(pack_root, rel)
    if path is None:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def pack_resource_site_href(
    pack_root: Path, rel: str, *, static_root: Path
) -> str | None:
    """Site-relative href for a pack resource file (HTTP static root)."""
    path = resolve_pack_resource_path(pack_root, rel)
    if path is None:
        return None
    try:
        rel_path = path.resolve().relative_to(static_root.resolve()).as_posix()
    except ValueError:
        return None
    return f"/{rel_path}" if rel_path else None


def pack_asset_base_url(
    pack_id: str,
    *,
    prefix: str = PACK_ASSET_URL_PREFIX,
) -> str | None:
    """Return ``/pack/<pack_id>/`` when ``pack_id`` is a safe manifest id."""
    pid = (pack_id or "").strip()
    if not pid or not _PACK_ID_RE.fullmatch(pid):
        return None
    base = (prefix or PACK_ASSET_URL_PREFIX).strip() or PACK_ASSET_URL_PREFIX
    if not base.startswith("/"):
        base = f"/{base}"
    return f"{base.rstrip('/')}/{pid}/"


def pack_asset_url(
    pack_root: Path,
    rel: str,
    *,
    asset_base_url: str | None = None,
    static_root: Path | None = None,
) -> str | None:
    """
    URL for a file under ``<pack_root>/resources/<rel>``.

    Prefer ``asset_base_url`` (``/pack/<id>/``); fall back to a path under
    ``static_root`` when no pack route is configured.
    """
    if resolve_pack_resource_path(pack_root, rel) is None:
        return None
    raw = (rel or "").strip().replace("\\", "/").lstrip("/")
    if not raw:
        return None
    base = (asset_base_url or "").strip()
    if base:
        return f"{base.rstrip('/')}/{raw}"
    if static_root is not None:
        return pack_resource_site_href(pack_root, rel, static_root=static_root)
    return None


def infer_pack_root_from_definition(game_definition: Any) -> Path | None:
    """Return ``games/<pack>/`` when the definition class lives in a pack tree."""
    mod = inspect.getmodule(game_definition.__class__)
    mod_file = getattr(mod, "__file__", None) if mod is not None else None
    if not isinstance(mod_file, str) or not mod_file:
        return None
    pack_dir = Path(mod_file).resolve().parent
    if (pack_dir / "hexengine_pack.toml").is_file():
        return pack_dir
    return None


def infer_pack_id_from_root(pack_root: Path) -> str | None:
    """Read ``[pack].id`` from ``hexengine_pack.toml`` when present."""
    manifest = pack_root / "hexengine_pack.toml"
    if not manifest.is_file():
        name = pack_root.name.strip()
        return name if name and _PACK_ID_RE.fullmatch(name) else None
    try:
        import tomllib

        raw = tomllib.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    pack = raw.get("pack")
    if not isinstance(pack, dict):
        return None
    pid = str(pack.get("id", "")).strip()
    if pid and _PACK_ID_RE.fullmatch(pid):
        return pid
    return None


__all__ = [
    "PACK_ASSET_URL_PREFIX",
    "infer_pack_id_from_root",
    "infer_pack_root_from_definition",
    "pack_asset_base_url",
    "pack_asset_url",
    "pack_resource_site_href",
    "read_pack_resource_text",
    "resolve_pack_resource_path",
]
