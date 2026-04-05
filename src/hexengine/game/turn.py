import logging
from enum import Enum


class Faction:
    "Class representing a faction in the game."

    def __init__(self, name: str):
        self.name = name

    def __repr__(self):
        return f"Faction(name={self.name})"


class Phase:
    "Class representing the current phase of the game."

    def __init__(self, name: str, max_actions: int):
        self.name = name
        self.max_actions = max_actions

    def __repr__(self):
        return f"Phase(name={self.name})"


class TurnOrdering(Enum):
    INTERLEAVED = 1
    SEQUENTIAL = 2


class TurnManager:
    def __init__(
        self,
        factions: list[Faction],
        phases: list[Phase],
        order: TurnOrdering = TurnOrdering.INTERLEAVED,
    ):
        self.factions = factions
        self.phases = []
        self.handlers = []
        if order == TurnOrdering.INTERLEAVED:
            # A:a, B:a, A:b, B:b
            for phase in phases:
                for faction in factions:
                    self.phases.append((faction, phase))

        else:
            # A:a, A:b, B:a, B:b
            for faction in factions:
                for phase in phases:
                    self.phases.append((faction, phase))

        self.pointer = -1
        self.logger = logging.getLogger("turns")
        self.logger.info(
            f"TurnManager initialized with order {order}, phases: {self.phases}"
        )
        self.max_actions = -1
        next(self)

    def __next__(self):
        self.pointer = (self.pointer + 1) % len(self.phases)
        f, p = self.current
        self.max_actions = p.max_actions
        self.logger.info(
            f"Starting turn: {f.name} - {p.name} with {p.max_actions} actions"
        )
        for handler in self.handlers:
            handler(f, p)
        return self.current

    def spend_action(self, amount: int = 1) -> None:
        faction, phase = self.current
        self.max_actions -= amount
        for handler in self.handlers:
            handler(faction, phase)
        if self.max_actions <= 0:
            self.logger.info(
                f"Phase {phase.name} for faction {faction.name} completed, advancing turn"
            )
            next(self)

    @property
    def current(self):
        return self.phases[self.pointer % len(self.phases)]

    @property
    def active_faction(self):
        f, _ = self.current
        return f

    @property
    def inactive_faction(self):
        f, _ = self.current
        for faction in self.factions:
            if faction != f:
                return faction
        return None

    def prospective_phase(self):

        this_faction, this_phase = self.current

        for i, (faction, phase) in enumerate(self.phases):
            if faction.name == this_faction.name and phase.name == this_phase.name:
                # Get the next phase in sequence
                next_index = (i + 1) % len(self.phases)
                return self.phases[next_index]

    @property
    def actions(self):
        return self.max_actions

    @classmethod
    def Ordered(cls, factions: list[str], phases: list[str, int]) -> "TurnManager":
        return cls(factions, phases, TurnOrdering.SEQUENTIAL)

    @classmethod
    def Interleaved(cls, factions: list[str], phases: list[str, int]) -> "TurnManager":
        return cls(factions, phases, TurnOrdering.INTERLEAVED)
