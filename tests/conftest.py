"""CPython test runs: stub Pyodide-only modules so ``hexengine`` imports succeed."""

from __future__ import annotations

import sys
import types


def _install_pyodide_stubs() -> None:
    if "js" in sys.modules:
        return

    js_mod = types.ModuleType("js")

    class _JsNull:
        pass

    jsnull = _JsNull()

    class _Document:
        def getElementById(self, _id: str):
            return jsnull

    js_mod.document = _Document()
    js_mod.HTMLElement = object
    js_mod.window = types.SimpleNamespace(addEventListener=lambda *a, **k: None)
    sys.modules["js"] = js_mod

    ffi_mod = types.ModuleType("pyodide.ffi")
    ffi_mod.jsnull = jsnull
    ffi_mod.create_proxy = lambda fn: fn
    sys.modules["pyodide.ffi"] = ffi_mod

    pyodide_pkg = types.ModuleType("pyodide")
    pyodide_pkg.ffi = ffi_mod
    sys.modules["pyodide"] = pyodide_pkg


_install_pyodide_stubs()
