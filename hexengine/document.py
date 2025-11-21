import js # pyright: ignore[reportMissingImports]

def element(id: str) -> js.HTMLElement:
    return js.document.getElementById(id)

