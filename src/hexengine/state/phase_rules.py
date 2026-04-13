"""Phase names and which rules apply (movement, combat, …)."""


def phase_allows_unit_move(phase: str) -> bool:
    """True when the active phase is one where units may change hex via MoveUnit."""
    p = str(phase).casefold()
    return p in ("movement", "move")
