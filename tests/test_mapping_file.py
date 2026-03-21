import json
import os
import tempfile
import unittest

from models.deck import Card
from models.mapping import MappingState, SBCandidate, MinorVersion, MajorVersion, VersionedMapping
from file_io.mapping_file import (
    new_versioned_from_state,
    version_to_state,
    determine_save_action,
    apply_save_action,
    versions_to_delete,
    apply_delete,
    save_versioned,
    load_versioned,
    latest_version_key,
    version_labels,
)


def _make_state(maindeck=None, sb_candidates=None, matchups=None,
                board_outs=None, sb_checks=None, hidden_cards=None, name="Test"):
    return MappingState(
        name=name,
        maindeck=maindeck or [],
        sb_candidates=sb_candidates or [],
        matchups=matchups or [],
        board_outs=board_outs or {},
        sb_checks=sb_checks or {},
        hidden_cards=hidden_cards or [],
    )


class TestNewVersionedFromState(unittest.TestCase):

    def test_creates_version_1_0(self):
        state = _make_state(maindeck=[Card("Lightning Bolt", 4)])
        vm = new_versioned_from_state(state)
        self.assertEqual(sorted(vm.versions.keys()), [1])
        self.assertEqual(sorted(vm.versions[1].minor_versions.keys()), [0])

    def test_roundtrip_via_version_to_state(self):
        state = _make_state(
            maindeck=[Card("Lightning Bolt", 4), Card("Counterspell", 2)],
            sb_candidates=[SBCandidate("Path to Exile", 3)],
            matchups=["vs Aggro", "vs Control"],
            board_outs={"Lightning Bolt": {"vs Aggro": 2, "vs Control": 0}},
            sb_checks={"Path to Exile": {"vs Aggro": 3, "vs Control": 0}},
            hidden_cards=["Counterspell"],
        )
        vm = new_versioned_from_state(state)
        restored = version_to_state(vm, 1, 0)
        self.assertEqual([(c.name, c.count) for c in restored.maindeck],
                         [(c.name, c.count) for c in state.maindeck])
        self.assertEqual([(c.name, c.count) for c in restored.sb_candidates],
                         [(c.name, c.count) for c in state.sb_candidates])
        self.assertEqual(restored.matchups, state.matchups)
        self.assertEqual(restored.board_outs, state.board_outs)
        self.assertEqual(restored.sb_checks, state.sb_checks)
        self.assertEqual(restored.hidden_cards, state.hidden_cards)


class TestVersionLabels(unittest.TestCase):

    def test_single_version(self):
        state = _make_state()
        vm = new_versioned_from_state(state)
        self.assertEqual(version_labels(vm), ["1.0"])

    def test_multiple_versions(self):
        state = _make_state(maindeck=[Card("A", 4)])
        vm = new_versioned_from_state(state)
        apply_save_action(vm, _make_state(matchups=["vs Aggro"]), "overwrite_minor")
        apply_save_action(vm, _make_state(matchups=["vs Aggro", "vs Control"]), "new_minor")
        self.assertEqual(version_labels(vm), ["1.0", "1.1"])


class TestDetermineSaveAction(unittest.TestCase):

    def _vm_with_state(self, state):
        return new_versioned_from_state(state)

    def test_no_change(self):
        state = _make_state(matchups=["vs Aggro"])
        vm = self._vm_with_state(state)
        self.assertEqual(determine_save_action(vm, state), "no_change")

    def test_overwrite_minor_matchup_change(self):
        state = _make_state(maindeck=[Card("A", 4)], matchups=["vs Aggro"])
        vm = self._vm_with_state(state)
        changed = _make_state(maindeck=[Card("A", 4)], matchups=["vs Aggro", "vs Control"])
        self.assertEqual(determine_save_action(vm, changed), "overwrite_minor")

    def test_new_minor_sb_candidates_change(self):
        state = _make_state(maindeck=[Card("A", 4)])
        vm = self._vm_with_state(state)
        changed = _make_state(
            maindeck=[Card("A", 4)],
            sb_candidates=[SBCandidate("Path to Exile", 3)],
        )
        self.assertEqual(determine_save_action(vm, changed), "new_minor")

    def test_new_major_maindeck_change(self):
        state = _make_state(maindeck=[Card("A", 4)])
        vm = self._vm_with_state(state)
        changed = _make_state(maindeck=[Card("A", 4), Card("B", 2)])
        self.assertEqual(determine_save_action(vm, changed), "new_major")


class TestApplySaveAction(unittest.TestCase):

    def test_overwrite_minor(self):
        state = _make_state(maindeck=[Card("A", 4)], matchups=["vs Aggro"])
        vm = new_versioned_from_state(state)
        new_state = _make_state(maindeck=[Card("A", 4)], matchups=["vs Aggro", "vs Control"])
        maj, min_ = apply_save_action(vm, new_state, "overwrite_minor")
        self.assertEqual((maj, min_), (1, 0))
        self.assertEqual(version_to_state(vm, 1, 0).matchups, ["vs Aggro", "vs Control"])

    def test_new_minor(self):
        state = _make_state(maindeck=[Card("A", 4)])
        vm = new_versioned_from_state(state)
        new_state = _make_state(
            maindeck=[Card("A", 4)],
            sb_candidates=[SBCandidate("Path to Exile", 3)],
        )
        maj, min_ = apply_save_action(vm, new_state, "new_minor")
        self.assertEqual((maj, min_), (1, 1))
        self.assertIn(1, vm.versions[1].minor_versions)

    def test_new_major(self):
        state = _make_state(maindeck=[Card("A", 4)])
        vm = new_versioned_from_state(state)
        new_state = _make_state(maindeck=[Card("A", 4), Card("B", 2)])
        maj, min_ = apply_save_action(vm, new_state, "new_major")
        self.assertEqual((maj, min_), (2, 0))
        self.assertIn(2, vm.versions)
        self.assertEqual([(c.name, c.count) for c in vm.versions[2].maindeck],
                         [("A", 4), ("B", 2)])


class TestVersionsToDelete(unittest.TestCase):

    def _vm(self):
        state = _make_state(maindeck=[Card("A", 4)])
        vm = new_versioned_from_state(state)
        apply_save_action(vm, _make_state(maindeck=[Card("A", 4)], matchups=["x"]), "new_minor")
        apply_save_action(vm, _make_state(maindeck=[Card("A", 4), Card("B", 2)]), "new_major")
        return vm  # versions: 1.0, 1.1, 2.0

    def test_delete_non_first_minor(self):
        vm = self._vm()
        to_delete = versions_to_delete(vm, 1, 1)
        self.assertEqual(to_delete, [(1, 1)])

    def test_delete_first_minor_cascades_to_next_major(self):
        vm = self._vm()
        to_delete = versions_to_delete(vm, 1, 0)
        self.assertIn((1, 0), to_delete)
        self.assertIn((1, 1), to_delete)
        self.assertIn((2, 0), to_delete)

    def test_delete_last_major_no_cascade(self):
        vm = self._vm()
        to_delete = versions_to_delete(vm, 2, 0)
        self.assertEqual(to_delete, [(2, 0)])


class TestApplyDelete(unittest.TestCase):

    def test_delete_minor_version(self):
        state = _make_state(maindeck=[Card("A", 4)])
        vm = new_versioned_from_state(state)
        apply_save_action(vm, _make_state(maindeck=[Card("A", 4)], matchups=["x"]), "new_minor")
        apply_delete(vm, 1, 1)
        self.assertNotIn(1, vm.versions[1].minor_versions)
        self.assertIn(0, vm.versions[1].minor_versions)

    def test_delete_major_removes_entry(self):
        state = _make_state(maindeck=[Card("A", 4)])
        vm = new_versioned_from_state(state)
        apply_save_action(vm, _make_state(maindeck=[Card("A", 4), Card("B", 2)]), "new_major")
        apply_delete(vm, 1, 0)
        self.assertNotIn(1, vm.versions)


class TestSaveLoadRoundtrip(unittest.TestCase):

    def test_roundtrip(self):
        state = _make_state(
            name="Test Deck",
            maindeck=[Card("Lightning Bolt", 4), Card("Counterspell", 2)],
            sb_candidates=[SBCandidate("Path to Exile", 3)],
            matchups=["vs Aggro", "vs Control"],
            board_outs={"Lightning Bolt": {"vs Aggro": 2, "vs Control": 0}},
            sb_checks={"Path to Exile": {"vs Aggro": 3, "vs Control": 0}},
            hidden_cards=["Counterspell"],
        )
        vm = new_versioned_from_state(state)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            save_versioned(vm, path)
            loaded = load_versioned(path)
        finally:
            os.unlink(path)

        self.assertEqual(loaded.name, "Test Deck")
        maj, min_ = latest_version_key(loaded)
        restored = version_to_state(loaded, maj, min_)
        self.assertEqual([(c.name, c.count) for c in restored.maindeck],
                         [("Lightning Bolt", 4), ("Counterspell", 2)])
        self.assertEqual(restored.matchups, ["vs Aggro", "vs Control"])
        self.assertEqual(restored.board_outs.get("Lightning Bolt", {}).get("vs Aggro"), 2)
        self.assertEqual(restored.sb_checks.get("Path to Exile", {}).get("vs Aggro"), 3)
        self.assertEqual(restored.hidden_cards, ["Counterspell"])

    def test_wrong_schema_version_raises(self):
        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w", encoding="utf-8"
        ) as f:
            json.dump({"schema_version": 99, "name": "", "versions": {}}, f)
            path = f.name
        try:
            with self.assertRaises(ValueError):
                load_versioned(path)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
