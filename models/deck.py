from dataclasses import dataclass, field


@dataclass
class Card:
    name: str
    count: int


@dataclass
class Deck:
    maindeck: list[Card] = field(default_factory=list)
    sideboard: list[Card] = field(default_factory=list)
