"""Dev console optional mirror for INFORM ui_popup payloads."""

from __future__ import annotations

from hexengine.dev_console import repeat_ui_popup_to_status, ui_popup_plain_line


def test_ui_popup_plain_line_prefers_text() -> None:
    assert ui_popup_plain_line({"text": "No enemy.", "html": "<b>x</b>"}) == "No enemy."


def test_ui_popup_plain_line_html_only() -> None:
    assert ui_popup_plain_line({"html": "<div>x</div>"}) == "(rich html popup)"


def test_repeat_ui_popup_to_status_noop_without_text() -> None:
    repeat_ui_popup_to_status({})
