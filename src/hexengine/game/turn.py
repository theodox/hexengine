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
    def actions(self):
        return self.max_actions

    @classmethod
    def Ordered(cls, factions: list[str], phases: list[str, int]) -> "TurnManager":
        return cls(factions, phases, TurnOrdering.SEQUENTIAL)

    @classmethod
    def Interleaved(cls, factions: list[str], phases: list[str, int]) -> "TurnManager":
        return cls(factions, phases, TurnOrdering.INTERLEAVED)
