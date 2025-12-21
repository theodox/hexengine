
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
    def __init__(self, factions: list[Faction], phases: list[Phase], order: TurnOrdering = TurnOrdering.INTERLEAVED):
        self.factions = factions
        self.phases = []
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
        
        self.pointer = 0


    def __next__(self):
        self.pointer = (self.pointer + 1) % len(self.phases)
        return self.phases[self.pointer % len(self.phases)]

    def current(self):
        return self.phases[self.pointer % len(self.phases)]    
    
    @classmethod
    def Ordered(cls, factions: list[str], phases: list[str, int]) -> "TurnManager":
        return cls(factions, phases, TurnOrdering.SEQUENTIAL)
    
    @classmethod
    def Interleaved(cls, factions: list[str], phases: list[str, int]) -> "TurnManager":
        return cls(factions, phases, TurnOrdering.INTERLEAVED)
