import json
from typing import Literal

from models.deck import Card
from models.mapping import (
    MappingState, SBCandidate,
    MinorVersion, MajorVersion, VersionedMapping,
)

_SCHEMA_VERSION = 2

SaveAction = Literal["new_major", "new_minor", "overwrite_minor", "no_change"]


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------

def _maindeck_eq(a: list[Card], b: list[Card]) -> bool:
    return [(c.name, c.count) for c in a] == [(c.name, c.count) for c in b]


def _sb_candidates_eq(a: list[SBCandidate], b: list[SBCandidate]) -> bool:
    return [(c.name, c.count) for c in a] == [(c.name, c.count) for c in b]


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def latest_version_key(vm: VersionedMapping) -> tuple[int, int]:
    """Return (major, minor) of the newest version."""
    maj = max(vm.versions)
    min_ = max(vm.versions[maj].minor_versions)
    return maj, min_


def version_labels(vm: VersionedMapping) -> list[str]:
    """Return sorted labels like ['1.0', '1.1', '2.0'] for the combobox."""
    labels = []
    for maj in sorted(vm.versions):
        for min_ in sorted(vm.versions[maj].minor_versions):
            labels.append(f"{maj}.{min_}")
    return labels


def version_to_state(vm: VersionedMapping, major: int, minor: int) -> MappingState:
    """Reconstruct a MappingState from a specific version."""
    maj_v = vm.versions[major]
    min_v = maj_v.minor_versions[minor]
    return MappingState(
        name=vm.name,
        matchups=list(min_v.matchups),
        maindeck=[Card(c.name, c.count) for c in maj_v.maindeck],
        board_outs={k: dict(v) for k, v in min_v.board_outs.items()},
        sb_candidates=[SBCandidate(c.name, c.count) for c in min_v.sb_candidates],
        sb_checks={k: dict(v) for k, v in min_v.sb_checks.items()},
        hidden_cards=list(min_v.hidden_cards),
    )


def state_to_minor_version(state: MappingState) -> MinorVersion:
    """Convert the mapping/sideboard part of a MappingState to a MinorVersion."""
    return MinorVersion(
        matchups=list(state.matchups),
        sb_candidates=[SBCandidate(c.name, c.count) for c in state.sb_candidates],
        hidden_cards=list(state.hidden_cards),
        board_outs={k: dict(v) for k, v in state.board_outs.items()},
        sb_checks={k: dict(v) for k, v in state.sb_checks.items()},
    )


def new_versioned_from_state(state: MappingState) -> VersionedMapping:
    """Create a brand-new VersionedMapping at version 1.0 from a MappingState."""
    minor_v = state_to_minor_version(state)
    maj_v = MajorVersion(maindeck=list(state.maindeck), minor_versions={0: minor_v})
    return VersionedMapping(name=state.name, versions={1: maj_v})


def determine_save_action(vm: VersionedMapping, state: MappingState) -> SaveAction:
    """Compare state against the latest version; return what save should do."""
    maj, min_ = latest_version_key(vm)
    latest_maj = vm.versions[maj]
    latest_min = latest_maj.minor_versions[min_]

    if not _maindeck_eq(state.maindeck, latest_maj.maindeck):
        return "new_major"
    if not _sb_candidates_eq(state.sb_candidates, latest_min.sb_candidates):
        return "new_minor"
    if (
        state.matchups != latest_min.matchups
        or state.board_outs != latest_min.board_outs
        or state.sb_checks != latest_min.sb_checks
        or state.hidden_cards != latest_min.hidden_cards
    ):
        return "overwrite_minor"
    return "no_change"


def versions_to_delete(vm: VersionedMapping, major: int, minor: int) -> list[tuple[int, int]]:
    """Return the (maj, min) pairs that will be removed when deleting (major, minor).

    Rules:
    - minor > 0 (not first minor): delete (major, minor) and all later minors in that major.
    - minor == 0 (first minor = "major version"): delete all minors of this major PLUS
      all minors of the immediately following major (if it exists).
    """
    maj_v = vm.versions[major]
    all_minors = sorted(maj_v.minor_versions.keys())

    if minor == 0:
        result: list[tuple[int, int]] = [(major, m) for m in all_minors]
        sorted_majors = sorted(vm.versions.keys())
        idx = sorted_majors.index(major)
        if idx + 1 < len(sorted_majors):
            next_maj = sorted_majors[idx + 1]
            result += [(next_maj, m) for m in sorted(vm.versions[next_maj].minor_versions.keys())]
        return result
    else:
        return [(major, m) for m in all_minors if m >= minor]


def apply_delete(vm: VersionedMapping, major: int, minor: int) -> None:
    """Delete the version(s) implied by (major, minor) from vm in-place."""
    to_delete = versions_to_delete(vm, major, minor)
    majors_affected: dict[int, list[int]] = {}
    for maj, min_ in to_delete:
        majors_affected.setdefault(maj, []).append(min_)
    for maj, minors in majors_affected.items():
        maj_v = vm.versions[maj]
        for min_ in minors:
            del maj_v.minor_versions[min_]
        if not maj_v.minor_versions:
            del vm.versions[maj]


def apply_save_action(
    vm: VersionedMapping, state: MappingState, action: SaveAction
) -> tuple[int, int]:
    """Mutate vm in-place, return (major, minor) of the resulting saved version."""
    vm.name = state.name
    minor_v = state_to_minor_version(state)
    maj, min_ = latest_version_key(vm)

    if action == "new_major":
        new_maj = maj + 1
        vm.versions[new_maj] = MajorVersion(
            maindeck=[Card(c.name, c.count) for c in state.maindeck],
            minor_versions={0: minor_v},
        )
        return new_maj, 0
    elif action == "new_minor":
        new_min = min_ + 1
        vm.versions[maj].minor_versions[new_min] = minor_v
        return maj, new_min
    else:  # overwrite_minor
        vm.versions[maj].minor_versions[min_] = minor_v
        return maj, min_


# ---------------------------------------------------------------------------
# JSON serialization
# ---------------------------------------------------------------------------

def _serialize_minor(minor_v: MinorVersion) -> dict:
    mapping = {}
    for matchup in minor_v.matchups:
        board_outs = {
            card: val
            for card, mu_map in minor_v.board_outs.items()
            if (val := mu_map.get(matchup, 0))
        }
        sb_checks = {
            card: val
            for card, mu_map in minor_v.sb_checks.items()
            if (val := mu_map.get(matchup, False))
        }
        mapping[matchup] = {"board_outs": board_outs, "sb_checks": sb_checks}
    return {
        "sb_candidates": [{"name": c.name, "count": c.count} for c in minor_v.sb_candidates],
        "hidden_cards": minor_v.hidden_cards,
        "mapping": mapping,
    }


def save_versioned(vm: VersionedMapping, path: str) -> None:
    versions_data = {}
    for maj_key in sorted(vm.versions):
        maj_v = vm.versions[maj_key]
        minor_versions_data = {}
        for min_key in sorted(maj_v.minor_versions):
            minor_versions_data[str(min_key)] = _serialize_minor(maj_v.minor_versions[min_key])
        versions_data[str(maj_key)] = {
            "maindeck": [{"name": c.name, "count": c.count} for c in maj_v.maindeck],
            "minor_versions": minor_versions_data,
        }
    data = {
        "schema_version": _SCHEMA_VERSION,
        "name": vm.name,
        "versions": versions_data,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _deserialize_minor(data: dict) -> MinorVersion:
    mapping = data.get("mapping", {})
    matchups = list(mapping.keys())
    board_outs: dict[str, dict[str, int]] = {}
    sb_checks: dict[str, dict[str, bool]] = {}
    for matchup, entry in mapping.items():
        for card, val in entry.get("board_outs", {}).items():
            board_outs.setdefault(card, {})[matchup] = int(val)
        for card, val in entry.get("sb_checks", {}).items():
            sb_checks.setdefault(card, {})[matchup] = int(val)
    return MinorVersion(
        matchups=matchups,
        sb_candidates=[SBCandidate(**c) for c in data.get("sb_candidates", [])],
        hidden_cards=data.get("hidden_cards", []),
        board_outs=board_outs,
        sb_checks=sb_checks,
    )


def load_versioned(path: str) -> VersionedMapping:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if data.get("schema_version") != _SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported schema version: {data.get('schema_version')}. "
            "Run migrate_v1_to_v2.py to upgrade."
        )

    versions: dict[int, MajorVersion] = {}
    for maj_key, maj_data in data.get("versions", {}).items():
        minor_versions: dict[int, MinorVersion] = {}
        for min_key, min_data in maj_data.get("minor_versions", {}).items():
            minor_versions[int(min_key)] = _deserialize_minor(min_data)
        versions[int(maj_key)] = MajorVersion(
            maindeck=[Card(**c) for c in maj_data.get("maindeck", [])],
            minor_versions=minor_versions,
        )

    return VersionedMapping(name=data.get("name", ""), versions=versions)
