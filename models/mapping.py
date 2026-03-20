from dataclasses import dataclass, field
from models.deck import Card


@dataclass
class SBCandidate:
    name: str
    count: int


@dataclass
class MappingState:
    matchups: list[str] = field(default_factory=list)
    maindeck: list[Card] = field(default_factory=list)
    board_outs: dict[str, dict[str, int]] = field(default_factory=dict)
    sb_candidates: list[SBCandidate] = field(default_factory=list)
    sb_checks: dict[str, dict[str, int]] = field(default_factory=dict)
    hidden_cards: list[str] = field(default_factory=list)
    name: str = ""


@dataclass
class MinorVersion:
    matchups: list[str] = field(default_factory=list)
    sb_candidates: list[SBCandidate] = field(default_factory=list)
    hidden_cards: list[str] = field(default_factory=list)
    board_outs: dict[str, dict[str, int]] = field(default_factory=dict)
    sb_checks: dict[str, dict[str, int]] = field(default_factory=dict)


@dataclass
class MajorVersion:
    maindeck: list[Card] = field(default_factory=list)
    minor_versions: dict[int, MinorVersion] = field(default_factory=dict)


@dataclass
class VersionedMapping:
    name: str = ""
    versions: dict[int, MajorVersion] = field(default_factory=dict)
