"""Phase names and which rules apply (movement, combat, …)."""

from .movement_arc import MOVEMENT_INTERRUPT_PHASE


def phase_allows_unit_move(phase: str) -> bool:
    """True when the active phase is one where units may change hex via MoveUnit."""
    p = str(phase).casefold()
    return p in ("movement", "move")


def phase_allows_movement_interrupt_pass(phase: str) -> bool:
    """True during server-driven micro-turns between stepwise move steps."""
    return str(phase) == MOVEMENT_INTERRUPT_PHASE
