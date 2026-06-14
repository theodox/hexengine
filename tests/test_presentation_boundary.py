"""Charter phase 6: engine presentation boundary (no pack-named CSS in engine)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GAMES = str(REPO_ROOT / "games")
SRC = str(REPO_ROOT / "src")
for p in (GAMES, SRC):
    if p not in sys.path:
        sys.path.insert(0, p)

_ENGINE_GAME = REPO_ROOT / "src" / "hexengine" / "game"
_FORBIDDEN_IN_ENGINE_GAME = (
    "hexdemo-turn-dock",
    "hexdemo-retreat-hex",
    "hexdemo-marker-hex",
)


def test_engine_game_modules_avoid_hexdemo_css_tokens() -> None:
    violations: list[str] = []
    for path in _ENGINE_GAME.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in _FORBIDDEN_IN_ENGINE_GAME:
            if token in text:
                rel = path.relative_to(REPO_ROOT).as_posix()
                violations.append(f"{rel}: {token}")
    assert not violations, "Pack CSS tokens in engine game code:\n" + "\n".join(
        violations
    )


def test_hexdemo_registry_covers_all_declared_ui_modes() -> None:
    from games.hexdemo.hooks import build_hooks
    from games.hexdemo.ui.segment_registry import PRESENTATION_BY_UI_MODE

    from hexengine.authoring.segment_ui_validate import collect_declared_ui_modes

    declared = collect_declared_ui_modes(build_hooks())
    registered = frozenset(PRESENTATION_BY_UI_MODE.keys())
    missing = sorted(declared - registered)
    assert not missing, f"segment_registry missing ui_modes: {missing}"


def test_template_segment_registry_covers_declared_ui_modes() -> None:
    from games.template.hooks import build_hooks
    from games.template.segment_ui import PRESENTATION_BY_UI_MODE

    from hexengine.authoring.segment_ui_validate import collect_declared_ui_modes

    declared = collect_declared_ui_modes(build_hooks())
    registered = frozenset(PRESENTATION_BY_UI_MODE.keys())
    assert declared <= registered
