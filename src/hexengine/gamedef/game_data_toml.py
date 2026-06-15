"""Load `GameData` from TOML (pack manifest + optional `resources/game_data.toml`)."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .client_contract import client_contract_manifest_from_mapping
from .game_data import GameData

_MANIFEST_NAME = "hexengine_pack.toml"


def _deep_merge_gamedata(
    base: dict[str, Any], overlay: dict[str, Any]
) -> dict[str, Any]:
    """Recursively merge `overlay` onto `base` (overlay wins on conflicts)."""
    out: dict[str, Any] = dict(base)
    for k, v in overlay.items():
        if k == "file":
            continue
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge_gamedata(out[k], v)
        else:
            out[k] = v
    return out


def merged_gamedata_dict_from_manifest(
    pack_root: Path, manifest_data: Mapping[str, Any]
) -> dict[str, Any]:
    """
    Build a flat-ish mapping suitable for `game_data_from_mapping`.

    Reads optional `[gamedata]` from `manifest_data`:

    - `file` — path relative to `pack_root` to a TOML file whose top-level keys
      describe `GameData` (same shape as a dedicated game data file).
    - Any other keys/tables under `[gamedata]` override the file (manifest wins).
    """
    raw_gd = manifest_data.get("gamedata")
    if not isinstance(raw_gd, dict):
        return {}
    file_rel = raw_gd.get("file")
    base: dict[str, Any] = {}
    if isinstance(file_rel, str) and file_rel.strip():
        path = (pack_root / file_rel.strip()).resolve()
        if not path.is_file():
            raise ValueError(
                f"gamedata.file {file_rel!r} not found under pack {pack_root} (resolved {path})"
            )
        loaded = tomllib.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError(f"gamedata TOML must parse to a table: {path}")
        base = loaded
    inline = {k: v for k, v in raw_gd.items() if k != "file"}
    if not base and not inline:
        return {}
    if not base:
        return dict(inline)
    if not inline:
        return dict(base)
    return _deep_merge_gamedata(base, inline)


def load_game_data_for_pack_root(pack_root: Path) -> GameData:
    """
    Load `GameData` for a pack directory containing `hexengine_pack.toml`.

    If the manifest has no `[gamedata]` table, returns `GameData.empty`.
    """
    mf = (pack_root / _MANIFEST_NAME).resolve()
    if not mf.is_file():
        return GameData.empty()
    manifest_data = tomllib.loads(mf.read_text(encoding="utf-8"))
    merged = merged_gamedata_dict_from_manifest(pack_root.resolve(), manifest_data)
    return game_data_from_mapping(merged)


def game_data_from_mapping(data: Mapping[str, Any]) -> GameData:
    """
    Construct `GameData` from a TOML-root mapping (unknown keys ignored).

    Expected top-level keys match `GameData` fields; nested TOML tables map to
    `faction_display_names`, `faction_css_classes`, and `hex_highlight_ui`.
    """
    if not data:
        return GameData.empty()

    schema_raw = data.get("gamedata_schema", 1)
    try:
        schema = int(schema_raw)
    except (TypeError, ValueError):
        schema = 1
    if schema != 1:
        raise ValueError(
            f"Unsupported gamedata_schema {schema_raw!r} (only 1 is supported)"
        )

    mx: int | None = None
    if (
        "max_active_units_per_hex" in data
        and data["max_active_units_per_hex"] is not None
    ):
        try:
            n = int(data["max_active_units_per_hex"])
        except (TypeError, ValueError):
            n = 0
        mx = n if n > 0 else None

    mv_key = _optional_str(data.get("movement_budget_attribute_key"))
    title_key = _optional_str(data.get("session_state_key"))
    title_file = _optional_str(data.get("title_css_file"))
    title_css = _optional_str(data.get("title_css"))

    fd = _str_dict(data.get("faction_display_names"))
    fc = _str_dict(data.get("faction_css_classes"))
    hi = _highlight_dict(data.get("hex_highlight_ui"))
    shell = _shell_ui_dict(data.get("shell_ui"))
    kind_styles = _str_dict(data.get("interaction_kind_styles"))
    client_contract = client_contract_manifest_from_mapping(data.get("client_contract"))

    return GameData(
        gamedata_schema=1,
        max_active_units_per_hex=mx,
        movement_budget_attribute_key=mv_key,
        session_state_key=title_key,
        faction_display_names=fd,
        faction_css_classes=fc,
        title_css_file=title_file,
        title_css=title_css,
        hex_highlight_ui=hi,
        shell_ui=shell,
        interaction_kind_styles=kind_styles,
        client_contract=client_contract,
    )


def _optional_str(v: Any) -> str | None:
    if isinstance(v, str) and v.strip():
        return v.strip()
    return None


def _str_dict(v: Any) -> dict[str, str]:
    if not isinstance(v, dict):
        return {}
    out: dict[str, str] = {}
    for key, raw in v.items():
        sk = str(key).strip()
        if not sk or not isinstance(raw, str) or not raw.strip():
            continue
        out[sk] = raw.strip()
    return out


def _highlight_dict(v: Any) -> dict[str, Any]:
    if not isinstance(v, dict):
        return {}
    allowed = (
        "schema",
        "move_hex_class",
        "retreat_hex_class",
        "retreat_through_hex_class",
        "marker_hex_class",
    )
    out: dict[str, Any] = {}
    for k in allowed:
        if k not in v:
            continue
        raw = v.get(k)
        if k == "schema":
            try:
                out[k] = int(raw)
            except (TypeError, ValueError):
                continue
            continue
        if isinstance(raw, str) and raw.strip():
            out[k] = raw.strip()
    return out


def _shell_ui_dict(v: Any) -> dict[str, Any]:
    if not isinstance(v, dict):
        return {}
    allowed_str = (
        "advance_turn_button_label",
        "disrupt_instead_label",
        "disrupt_instead_title",
        "combat_advance_label",
        "combat_advance_title",
        "attack_pick_target_status",
        "attack_target_set_status",
        "attack_confirm_label",
        "attack_cancel_label",
        "dock_gate_panel_hint",
        "retreat_path_confirm_label",
        "retreat_path_cancel_label",
        "retreat_path_undo_label",
        "retreat_path_pick_hex_status",
        "retreat_path_ready_status",
        "retreat_path_confirm_title",
    )
    out: dict[str, Any] = {}
    for k in allowed_str:
        raw = v.get(k)
        if isinstance(raw, str) and raw.strip():
            out[k] = raw.strip()
    return out


__all__ = [
    "game_data_from_mapping",
    "load_game_data_for_pack_root",
    "merged_gamedata_dict_from_manifest",
]
