"""Resolve pack-owned files under `<pack_root>/resources/`."""

from __future__ import annotations

from pathlib import Path


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
        return path.resolve().relative_to(static_root.resolve()).as_posix()
    except ValueError:
        return None


__all__ = [
    "pack_resource_site_href",
    "read_pack_resource_text",
    "resolve_pack_resource_path",
]
