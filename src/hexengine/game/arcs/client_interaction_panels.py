"""
Turn action dock: HTML shell + wired actions on host ``#user-controls``.

Title ``html`` is display-only; buttons delegate to ``action_request``. Preview
``panel_actions`` merge into the ``turn_actions`` panel when
``map_selection_previews`` is active.
"""

# ruff: noqa: I001
from __future__ import annotations

import re
from typing import Any

from ...document import create_proxy, element, js
from ...ui.dom import apply_css_classes
from .client_panel_actions import dispatch_panel_action_route, resolve_panel_action_route

TURN_ACTIONS_PANEL_ID = "turn_actions"
USER_CONTROLS_HOST_ID = "user-controls"
_LEGACY_ADVANCE_HOST_ID = "advance"
_DOCK_ARC_CSS_RE = re.compile(
    r"\b(hexdemo-turn-dock|hexengine-turn-dock)--[a-z0-9_]+\b"
)


def effective_turn_dock_arc(
    server_arc: str,
    *,
    attack_draft: bool,
    retreat_path_draft: bool,
    place_marker_draft: bool,
) -> str:
    """Client SEQUENCE step override; falls back to the server ``dock_arc``."""
    if attack_draft:
        return "attack_draft"
    if retreat_path_draft:
        return "retreat_path_draft"
    if place_marker_draft:
        return "place_marker_draft"
    return str(server_arc or "").strip()


def replace_dock_arc_css_class(css_class: str, effective_arc: str) -> str:
    """Swap ``--<arc>`` modifiers on turn-dock panel roots."""
    arc = str(effective_arc or "").strip()
    css = str(css_class or "").strip()
    if not arc:
        return css
    if _DOCK_ARC_CSS_RE.search(css):
        return _DOCK_ARC_CSS_RE.sub(rf"\1--{arc}", css)
    if "hexdemo-turn-dock" in css.split():
        return f"{css} hexdemo-turn-dock--{arc}".strip()
    if "hexengine-turn-dock" in css.split():
        return f"{css} hexengine-turn-dock--{arc}".strip()
    return css


def turn_dock_sequence_headline(
    *,
    server_headline: str,
    server_arc: str,
    preview_status: str,
    attack_draft: bool,
    retreat_path_draft: bool,
    place_marker_draft: bool,
    attack_ready_idle: bool,
    attack_pick_target_status: str,
    attack_target_set_status: str,
) -> str:
    """Headline for the active SEQUENCE step (preview status or idle coaching copy)."""
    status = str(preview_status or "").strip()
    if attack_draft:
        if status:
            return status
        return str(attack_target_set_status or "").strip() or str(server_headline or "")
    if retreat_path_draft and status:
        return status
    if place_marker_draft and status:
        return status
    if attack_ready_idle:
        idle = str(attack_pick_target_status or "").strip()
        if idle:
            return idle
    return str(server_headline or "").strip()


def _mount_panel_on_advance_host(host: Any, root: Any) -> None:
    """Last child on the host = top of the column-reverse stack (most visible)."""
    host.appendChild(root)


class ClientInteractionPanelsMixin:
    """Rich panel sync mixed into ``Game``."""

    _interaction_panel_roots: dict[str, Any]
    _interaction_panel_action_buttons: dict[str, dict[str, Any]]
    _interaction_panel_input_elements: dict[str, dict[str, Any]]
    _interaction_panel_wire_specs: dict[str, dict[str, Any]]

    def _attack_plan_draft_active(self) -> bool:
        if not getattr(self, "_client_has_attack_planning_ui", lambda: False)():
            return False
        if getattr(self, "attack_plan_target_hex", None) is not None:
            return True
        return bool(getattr(self, "attack_plan_attacker_ids", None))

    def _merged_turn_action_dock_actions(
        self, server_actions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Merge server dock rows with preview ``panel_actions`` (override by ``id``)."""
        order: list[str] = []
        by_id: dict[str, dict[str, Any]] = {}
        for row in server_actions:
            oid = str(row.get("id", "")).strip()
            if not oid:
                continue
            order.append(oid)
            by_id[oid] = dict(row)

        prev = getattr(self, "_map_selection_preview", None)
        if isinstance(prev, dict):
            extra = prev.get("panel_actions")
            if isinstance(extra, list):
                for row in extra:
                    if not isinstance(row, dict):
                        continue
                    oid = str(row.get("id", "")).strip()
                    if not oid:
                        continue
                    if oid not in by_id:
                        order.append(oid)
                    by_id[oid] = dict(row)

        if self._attack_plan_draft_active() and "end_phase" in by_id:
            ep = dict(by_id["end_phase"])
            ep["enabled"] = False
            by_id["end_phase"] = ep

        if self._retreat_path_draft_active() and "end_phase" in by_id:
            ep = dict(by_id["end_phase"])
            ep["enabled"] = False
            by_id["end_phase"] = ep

        if self._place_marker_relocate_active() and "end_phase" in by_id:
            ep = dict(by_id["end_phase"])
            ep["enabled"] = False
            by_id["end_phase"] = ep

        return [by_id[oid] for oid in order if oid in by_id]

    def _ensure_turn_action_dock_panel_for_preview(self) -> None:
        """Mount ``turn_actions`` when preview supplies ``panel_actions`` but wire has no panel yet."""
        pid = TURN_ACTIONS_PANEL_ID
        if self._interaction_panel_roots.get(pid) is not None:
            return
        prev = getattr(self, "_map_selection_preview", None)
        if not isinstance(prev, dict):
            return
        extra = prev.get("panel_actions")
        if not isinstance(extra, list) or not extra:
            return
        host = element(USER_CONTROLS_HOST_ID)
        if host is None:
            return
        stxt = str(prev.get("status_text") or "").strip()
        spec: dict[str, Any] = {
            "schema": 1,
            "id": pid,
            "host": USER_CONTROLS_HOST_ID,
            "dock_arc": "preview",
            "headline": stxt,
            "css_class": "hexengine-turn-dock hexengine-turn-dock--preview",
            "actions": [],
            "inputs": [],
        }
        self._interaction_panel_wire_specs[pid] = spec
        self._render_interaction_panel(host, pid, spec)
    def _retreat_path_draft_active(self) -> bool:
        fn = getattr(self, "_retreat_path_active", None)
        if callable(fn):
            try:
                return bool(fn())
            except Exception:
                return False
        return False

    def _client_turn_dock_sequence_arc(self, server_arc: str) -> str:
        return effective_turn_dock_arc(
            server_arc,
            attack_draft=self._attack_plan_draft_active(),
            retreat_path_draft=self._retreat_path_draft_active(),
            place_marker_draft=self._place_marker_relocate_active(),
        )

    def _shell_ui_status_copy(self, key: str, default: str) -> str:
        if hasattr(self, "_shell_attack_copy"):
            return self._shell_attack_copy(key, default)  # type: ignore[attr-defined]
        su = self._client_title_data().shell_ui
        raw = getattr(su, key, None)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
        return default

    def _client_turn_dock_sequence_headline(
        self, server_headline: str, server_arc: str
    ) -> str:
        prev = getattr(self, "_map_selection_preview", None)
        preview_status = ""
        if isinstance(prev, dict):
            preview_status = str(prev.get("status_text") or "").strip()
        attack_draft = self._attack_plan_draft_active()
        retreat_draft = self._retreat_path_draft_active()
        place_draft = self._place_marker_relocate_active()
        attack_ready_idle = (
            str(server_arc or "").strip() == "attack_ready"
            and not attack_draft
            and getattr(self, "_client_has_attack_planning_ui", lambda: False)()
        )
        return turn_dock_sequence_headline(
            server_headline=server_headline,
            server_arc=server_arc,
            preview_status=preview_status,
            attack_draft=attack_draft,
            retreat_path_draft=retreat_draft,
            place_marker_draft=place_draft,
            attack_ready_idle=attack_ready_idle,
            attack_pick_target_status=self._shell_ui_status_copy(
                "attack_pick_target_status",
                "Combat: select target hex and attackers, then confirm.",
            ),
            attack_target_set_status=self._shell_ui_status_copy(
                "attack_target_set_status",
                "Target set — adjust attackers or confirm.",
            ),
        )

    def _sync_turn_action_dock_sequence_skin(self) -> None:
        """Apply client SEQUENCE ``dock_arc`` + headline overrides on ``turn_actions``."""
        pid = TURN_ACTIONS_PANEL_ID
        spec = self._interaction_panel_wire_specs.get(pid)
        root = self._interaction_panel_roots.get(pid)
        if spec is None or root is None:
            return
        server_arc = str(spec.get("dock_arc", "")).strip()
        effective_arc = self._client_turn_dock_sequence_arc(server_arc)
        css = replace_dock_arc_css_class(str(spec.get("css_class", "")), effective_arc)
        apply_css_classes(root, css, base="hexengine-interaction-panel")
        try:
            root.dataset.dockArc = effective_arc
        except Exception:
            pass

        headline_host = getattr(root, "_hexengine_panel_headline", None)
        if headline_host is not None:
            server_hl = str(spec.get("headline", "") or "").strip()
            headline = self._client_turn_dock_sequence_headline(server_hl, server_arc)
            try:
                headline_host.textContent = headline
                headline_host.style.display = "" if headline else "none"
            except Exception:
                pass

    def _refresh_turn_action_dock_actions(self) -> None:
        self._ensure_turn_action_dock_panel_for_preview()
        spec = self._interaction_panel_wire_specs.get(TURN_ACTIONS_PANEL_ID)
        root = self._interaction_panel_roots.get(TURN_ACTIONS_PANEL_ID)
        if spec is None or root is None:
            return
        self._sync_turn_action_dock_sequence_skin()
        actions_host = getattr(root, "_hexengine_panel_actions", None)
        if actions_host is None:
            return
        raw = spec.get("actions")
        server_rows = (
            [dict(a) for a in raw if isinstance(a, dict)] if isinstance(raw, list) else []
        )
        merged = self._merged_turn_action_dock_actions(server_rows)
        self._sync_panel_actions(actions_host, TURN_ACTIONS_PANEL_ID, merged)

    def _sync_interaction_panels(self) -> None:
        """Render ``StateUpdate.interaction_panels`` on the user controls host."""
        client = getattr(self, "client", None)
        raw = getattr(client, "interaction_panels", None) if client is not None else None
        panels = [dict(p) for p in raw if isinstance(p, dict)] if isinstance(raw, list) else []
        advance_panels = [
            p
            for p in panels
            if str(p.get("host", USER_CONTROLS_HOST_ID)).strip().lower()
            in ("", USER_CONTROLS_HOST_ID, _LEGACY_ADVANCE_HOST_ID)
        ]

        if not advance_panels:
            self._clear_interaction_panels()
            return

        host = element(USER_CONTROLS_HOST_ID)
        if host is None:
            return

        self._interaction_panel_wire_specs = {}
        want: set[str] = set()
        for spec in advance_panels:
            pid = str(spec.get("id", "")).strip()
            if not pid:
                continue
            want.add(pid)
            self._interaction_panel_wire_specs[pid] = spec
            self._render_interaction_panel(host, pid, spec)

        for pid in list(self._interaction_panel_roots.keys()):
            if pid not in want:
                self._remove_interaction_panel(pid)

        if TURN_ACTIONS_PANEL_ID in want:
            self._refresh_turn_action_dock_actions()

    def _clear_interaction_panels(self) -> None:
        for pid in list(getattr(self, "_interaction_panel_roots", {}).keys()):
            self._remove_interaction_panel(pid)
        self._interaction_panel_wire_specs = {}

    def _remove_interaction_panel(self, panel_id: str) -> None:
        root = self._interaction_panel_roots.pop(panel_id, None)
        if root is not None:
            try:
                root.remove()
            except Exception:
                pass
        self._interaction_panel_action_buttons.pop(panel_id, None)
        self._interaction_panel_input_elements.pop(panel_id, None)
        self._interaction_panel_wire_specs.pop(panel_id, None)

    def _render_interaction_panel(self, host, panel_id: str, spec: dict[str, Any]) -> None:
        root = self._interaction_panel_roots.get(panel_id)
        if root is None:
            root = js.document.createElement("div")
            root.className = "hexengine-interaction-panel"
            root.dataset.panelId = panel_id
            self._interaction_panel_roots[panel_id] = root
            self._interaction_panel_action_buttons[panel_id] = {}
            self._interaction_panel_input_elements[panel_id] = {}

        _mount_panel_on_advance_host(host, root)

        css = str(spec.get("css_class", "")).strip()
        apply_css_classes(root, css, base="hexengine-interaction-panel")

        headline_host = getattr(root, "_hexengine_panel_headline", None)
        if headline_host is None:
            headline_host = js.document.createElement("div")
            headline_host.className = "hexengine-panel__headline"
            root.insertBefore(headline_host, root.firstChild)
            root._hexengine_panel_headline = headline_host

        html_host = getattr(root, "_hexengine_panel_html", None)
        if html_host is None:
            html_host = js.document.createElement("div")
            html_host.className = "hexengine-panel__html"
            if headline_host.nextSibling is not None:
                root.insertBefore(html_host, headline_host.nextSibling)
            else:
                root.appendChild(html_host)
            root._hexengine_panel_html = html_host

        inputs_host = getattr(root, "_hexengine_panel_inputs", None)
        if inputs_host is None:
            inputs_host = js.document.createElement("div")
            inputs_host.className = "hexengine-panel__inputs"
            root.appendChild(inputs_host)
            root._hexengine_panel_inputs = inputs_host

        actions_host = getattr(root, "_hexengine_panel_actions", None)
        if actions_host is None:
            actions_host = js.document.createElement("div")
            actions_host.className = "hexengine-panel__actions"
            root.appendChild(actions_host)
            root._hexengine_panel_actions = actions_host

        raw_headline = spec.get("headline")
        headline = "" if raw_headline is None else str(raw_headline).strip()
        if headline:
            headline_host.textContent = headline
            headline_host.style.display = ""
        else:
            headline_host.textContent = ""
            headline_host.style.display = "none"

        raw_html = spec.get("html")
        html = "" if raw_html is None else str(raw_html).strip()
        if html:
            html_host.innerHTML = html
            html_host.style.display = ""
        else:
            html_host.innerHTML = ""
            html_host.style.display = "none"

        actions = spec.get("actions")
        action_rows = (
            [dict(a) for a in actions if isinstance(a, dict)] if isinstance(actions, list) else []
        )
        if panel_id == TURN_ACTIONS_PANEL_ID:
            action_rows = self._merged_turn_action_dock_actions(action_rows)
        self._sync_panel_actions(actions_host, panel_id, action_rows)

        if panel_id == TURN_ACTIONS_PANEL_ID:
            self._sync_turn_action_dock_sequence_skin()

        inputs = spec.get("inputs")
        input_rows = [dict(i) for i in inputs if isinstance(i, dict)] if isinstance(inputs, list) else []
        self._sync_panel_inputs(inputs_host, panel_id, input_rows)

    def _sync_panel_actions(
        self, container, panel_id: str, actions: list[dict[str, Any]]
    ) -> None:
        registry = self._interaction_panel_action_buttons.setdefault(panel_id, {})
        want: dict[str, dict[str, Any]] = {}
        for a in actions:
            oid = str(a.get("id", "")).strip()
            if oid:
                want[oid] = a

        for oid in list(registry.keys()):
            if oid not in want:
                try:
                    registry.pop(oid).remove()
                except Exception:
                    pass
                registry.pop(oid, None)

        for oid, spec in want.items():
            btn = registry.get(oid)
            label = str(spec.get("label", oid)).strip() or oid
            title = spec.get("title")
            css = str(spec.get("css_class", "")).strip()
            enabled = bool(spec.get("enabled", True))
            payload = spec.get("payload")
            if not isinstance(payload, dict):
                payload = {}

            if btn is None:
                btn = js.document.createElement("button")
                btn.type = "button"
                apply_css_classes(btn, css, base="hexengine-primary-action")
                container.appendChild(btn)
                registry[oid] = btn

            btn.textContent = label
            if isinstance(title, str) and title.strip():
                btn.title = title.strip()
            btn.disabled = not enabled
            btn.style.display = "" if enabled or label else "none"
            spec_copy = dict(spec)
            btn.onclick = create_proxy(
                lambda _evt=None, _spec=spec_copy, _pid=panel_id: self._handle_panel_action_click(
                    _spec, _pid
                )
            )

    def _handle_panel_action_click(
        self, spec: dict[str, Any], panel_id: str
    ) -> None:
        route = resolve_panel_action_route(spec)
        if route is not None and dispatch_panel_action_route(self, spec, route):
            return

        action_type = str(spec.get("action_type", "")).strip()
        payload = spec.get("payload")
        if not isinstance(payload, dict):
            payload = {}

        merged = {**payload, **self._collect_panel_input_payload(panel_id)}
        self.execute_action_request(action_type, merged)  # type: ignore[attr-defined]

    def _sync_panel_inputs(
        self, container, panel_id: str, inputs: list[dict[str, Any]]
    ) -> None:
        registry = self._interaction_panel_input_elements.setdefault(panel_id, {})
        want: dict[str, dict[str, Any]] = {}
        for row in inputs:
            iid = str(row.get("id", "")).strip()
            if iid:
                want[iid] = row

        for iid in list(registry.keys()):
            if iid not in want:
                try:
                    registry.pop(iid).remove()
                except Exception:
                    pass
                registry.pop(iid, None)

        for iid, spec in want.items():
            block = registry.get(iid)
            if block is None:
                block = js.document.createElement("label")
                block.className = "hexengine-panel-input"
                block.dataset.inputId = iid
                caption = js.document.createElement("span")
                caption.className = "hexengine-panel-input__label"
                block.appendChild(caption)
                control_slot = js.document.createElement("span")
                control_slot.className = "hexengine-panel-input__control"
                block.appendChild(control_slot)
                container.appendChild(block)
                registry[iid] = block

            caption = block.querySelector(".hexengine-panel-input__label")
            control_slot = block.querySelector(".hexengine-panel-input__control")
            if caption is None or control_slot is None:
                continue

            label = str(spec.get("label", iid)).strip() or iid
            caption.textContent = label
            name = str(spec.get("name", iid)).strip() or iid
            block.dataset.inputName = name

            kind = str(spec.get("kind", "text")).strip().lower()
            control = getattr(block, "_hexengine_control", None)
            if control is None or str(getattr(control, "dataset", {}).get("kind", "")) != kind:
                if control is not None:
                    try:
                        control.remove()
                    except Exception:
                        pass
                if kind == "select":
                    control = js.document.createElement("select")
                    for opt in spec.get("options") or []:
                        if not isinstance(opt, dict):
                            continue
                        o = js.document.createElement("option")
                        o.value = str(opt.get("value", ""))
                        o.textContent = str(opt.get("label", o.value))
                        control.appendChild(o)
                elif kind == "checkbox":
                    control = js.document.createElement("input")
                    control.type = "checkbox"
                else:
                    control = js.document.createElement("input")
                    control.type = "text"
                control.dataset.kind = kind
                control_slot.appendChild(control)
                block._hexengine_control = control

            default = spec.get("default")
            if kind == "checkbox":
                control.checked = bool(default)
            elif kind == "select":
                if default is not None:
                    control.value = str(default)
            elif default is not None:
                control.value = str(default)

    def _collect_panel_input_payload(self, panel_id: str) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for iid, block in self._interaction_panel_input_elements.get(panel_id, {}).items():
            control = getattr(block, "_hexengine_control", None)
            if control is None:
                continue
            name = str(getattr(block, "dataset", {}).get("inputName", iid)).strip() or iid
            kind = str(getattr(control, "dataset", {}).get("kind", "text"))
            if kind == "checkbox":
                out[name] = bool(control.checked)
            else:
                out[name] = str(control.value)
        return out
