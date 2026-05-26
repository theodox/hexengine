"""Tests for hexengine.ui.dom helpers."""

from __future__ import annotations

from hexengine.ui.dom import apply_css_classes


class _FakeClassList:
    def __init__(self) -> None:
        self.tokens: list[str] = []

    def add(self, token: str) -> None:
        if " " in token:
            raise ValueError("space in token")
        self.tokens.append(token)


class _FakeElement:
    def __init__(self) -> None:
        self.className = ""
        self.classList = _FakeClassList()


def test_apply_css_classes_splits_tokens() -> None:
    el = _FakeElement()
    apply_css_classes(
        el,
        "hexengine-interaction-panel--primary-actions hexdemo-primary-panel-wrap",
        base="hexengine-interaction-panel",
    )
    assert el.className == "hexengine-interaction-panel"
    assert el.classList.tokens == [
        "hexengine-interaction-panel--primary-actions",
        "hexdemo-primary-panel-wrap",
    ]
