import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication(sys.argv)

from models.deck import Card
from models.mapping import MappingState, SBCandidate
from ui.mapping_table import MappingTable


def _make_table(maindeck, sb_candidates, matchups, board_outs=None, sb_checks=None):
    state = MappingState(
        maindeck=[Card(n, c) for n, c in maindeck],
        sb_candidates=[SBCandidate(n, c) for n, c in sb_candidates],
        matchups=list(matchups),
        board_outs=board_outs or {},
        sb_checks=sb_checks or {},
    )
    table = MappingTable()
    table.load_state(state)
    return table


class TestMoveMaindeckToSb(unittest.TestCase):

    def test_creates_new_sb_candidate(self):
        t = _make_table([("Lightning Bolt", 4)], [], ["vs Aggro"])
        t._move_maindeck_to_sb("Lightning Bolt", 4)
        names = [c.name for c in t._state.sb_candidates]
        self.assertIn("Lightning Bolt", names)
        cand = next(c for c in t._state.sb_candidates if c.name == "Lightning Bolt")
        self.assertEqual(cand.count, 4)

    def test_full_move_removes_from_maindeck(self):
        t = _make_table([("Lightning Bolt", 4)], [], ["vs Aggro"])
        t._move_maindeck_to_sb("Lightning Bolt", 4)
        names = [c.name for c in t._state.maindeck]
        self.assertNotIn("Lightning Bolt", names)

    def test_partial_move_decrements_maindeck_count(self):
        t = _make_table([("Lightning Bolt", 4)], [], ["vs Aggro"])
        t._move_maindeck_to_sb("Lightning Bolt", 1)
        card = next(c for c in t._state.maindeck if c.name == "Lightning Bolt")
        self.assertEqual(card.count, 3)

    def test_partial_move_decrements_board_outs(self):
        t = _make_table(
            [("Lightning Bolt", 4)], [], ["vs Aggro"],
            board_outs={"Lightning Bolt": {"vs Aggro": 2}},
        )
        t._move_maindeck_to_sb("Lightning Bolt", 1)
        self.assertEqual(t._state.board_outs["Lightning Bolt"]["vs Aggro"], 1)

    def test_sb_checks_reflect_non_boarded_out_copies(self):
        # 4x in main, 2 boarded out vs Aggro → move all 4 → 2 copies were not going out
        t = _make_table(
            [("Lightning Bolt", 4)], [], ["vs Aggro"],
            board_outs={"Lightning Bolt": {"vs Aggro": 2}},
        )
        t._move_maindeck_to_sb("Lightning Bolt", 4)
        self.assertEqual(t._state.sb_checks.get("Lightning Bolt", {}).get("vs Aggro"), 2)

    def test_sb_checks_zero_when_all_were_boarded_out(self):
        # 4x in main, all 4 boarded out vs Control → move all 4 → 0 copies to check in
        t = _make_table(
            [("Lightning Bolt", 4)], [], ["vs Control"],
            board_outs={"Lightning Bolt": {"vs Control": 4}},
        )
        t._move_maindeck_to_sb("Lightning Bolt", 4)
        self.assertEqual(t._state.sb_checks.get("Lightning Bolt", {}).get("vs Control"), 0)

    def test_sb_checks_all_when_none_boarded_out(self):
        # 4x in main, 0 boarded out vs Aggro → move all 4 → all 4 to check in
        t = _make_table(
            [("Lightning Bolt", 4)], [], ["vs Aggro"],
            board_outs={"Lightning Bolt": {"vs Aggro": 0}},
        )
        t._move_maindeck_to_sb("Lightning Bolt", 4)
        self.assertEqual(t._state.sb_checks.get("Lightning Bolt", {}).get("vs Aggro"), 4)

    def test_increments_existing_sb_candidate(self):
        t = _make_table(
            [("Path to Exile", 2)],
            [("Path to Exile", 1)],
            ["vs Aggro"],
            sb_checks={"Path to Exile": {"vs Aggro": 1}},
        )
        t._move_maindeck_to_sb("Path to Exile", 2)
        cand = next(c for c in t._state.sb_candidates if c.name == "Path to Exile")
        self.assertEqual(cand.count, 3)

    def test_board_outs_cleared_when_card_removed_from_maindeck(self):
        t = _make_table(
            [("Lightning Bolt", 4)], [], ["vs Aggro"],
            board_outs={"Lightning Bolt": {"vs Aggro": 2}},
        )
        t._move_maindeck_to_sb("Lightning Bolt", 4)
        self.assertNotIn("Lightning Bolt", t._state.board_outs)


class TestMoveSbToMaindeck(unittest.TestCase):

    def test_creates_new_maindeck_entry(self):
        t = _make_table([], [("Path to Exile", 3)], ["vs Aggro"],
                        sb_checks={"Path to Exile": {"vs Aggro": 3}})
        t._move_sb_to_maindeck("Path to Exile", 3)
        names = [c.name for c in t._state.maindeck]
        self.assertIn("Path to Exile", names)
        card = next(c for c in t._state.maindeck if c.name == "Path to Exile")
        self.assertEqual(card.count, 3)

    def test_full_move_removes_from_sb(self):
        t = _make_table([], [("Path to Exile", 3)], ["vs Aggro"],
                        sb_checks={"Path to Exile": {"vs Aggro": 3}})
        t._move_sb_to_maindeck("Path to Exile", 3)
        names = [c.name for c in t._state.sb_candidates]
        self.assertNotIn("Path to Exile", names)

    def test_partial_move_decrements_sb_count(self):
        t = _make_table([], [("Path to Exile", 3)], ["vs Aggro"],
                        sb_checks={"Path to Exile": {"vs Aggro": 3}})
        t._move_sb_to_maindeck("Path to Exile", 1)
        cand = next(c for c in t._state.sb_candidates if c.name == "Path to Exile")
        self.assertEqual(cand.count, 2)

    def test_board_outs_zero_when_all_copies_were_checked_in(self):
        # 3x in sb, all 3 checked in vs Aggro → move all to main → board_outs vs Aggro = 0
        t = _make_table([], [("Path to Exile", 3)], ["vs Aggro"],
                        sb_checks={"Path to Exile": {"vs Aggro": 3}})
        t._move_sb_to_maindeck("Path to Exile", 3)
        self.assertEqual(t._state.board_outs.get("Path to Exile", {}).get("vs Aggro", 0), 0)

    def test_board_outs_all_when_none_checked_in(self):
        # 3x in sb, none checked in vs Control → move all to main → board_outs vs Control = 3
        t = _make_table([], [("Path to Exile", 3)], ["vs Control"],
                        sb_checks={"Path to Exile": {"vs Control": 0}})
        t._move_sb_to_maindeck("Path to Exile", 3)
        self.assertEqual(t._state.board_outs.get("Path to Exile", {}).get("vs Control", 0), 3)

    def test_board_outs_partial_when_some_checked_in(self):
        # 3x in sb, 2 checked in vs Aggro → move all 3 to main → board_outs vs Aggro = 1
        t = _make_table([], [("Path to Exile", 3)], ["vs Aggro"],
                        sb_checks={"Path to Exile": {"vs Aggro": 2}})
        t._move_sb_to_maindeck("Path to Exile", 3)
        self.assertEqual(t._state.board_outs.get("Path to Exile", {}).get("vs Aggro", 0), 1)

    def test_sb_checks_decremented_on_partial_move(self):
        t = _make_table([], [("Path to Exile", 3)], ["vs Aggro"],
                        sb_checks={"Path to Exile": {"vs Aggro": 3}})
        t._move_sb_to_maindeck("Path to Exile", 1)
        self.assertEqual(t._state.sb_checks.get("Path to Exile", {}).get("vs Aggro"), 2)

    def test_sb_checks_floored_at_zero(self):
        # Move more copies than sb_checks, resulting check must not go negative
        t = _make_table([], [("Path to Exile", 3)], ["vs Control"],
                        sb_checks={"Path to Exile": {"vs Control": 1}})
        t._move_sb_to_maindeck("Path to Exile", 3)
        # Card fully removed from sb, so sb_checks entry is gone
        self.assertNotIn("Path to Exile", t._state.sb_checks)

    def test_multiple_matchups_independent(self):
        # 3x sb: checked in vs Aggro=3, vs Control=0 → board_outs: Aggro=0, Control=3
        t = _make_table(
            [], [("Thoughtseize", 3)], ["vs Aggro", "vs Control"],
            sb_checks={"Thoughtseize": {"vs Aggro": 3, "vs Control": 0}},
        )
        t._move_sb_to_maindeck("Thoughtseize", 3)
        bo = t._state.board_outs.get("Thoughtseize", {})
        self.assertEqual(bo.get("vs Aggro", 0), 0)
        self.assertEqual(bo.get("vs Control", 0), 3)


class TestSwapCards(unittest.TestCase):
    """Test _swap_cards end-to-end through the full method."""

    def test_swap_all_moves_main_to_sb(self):
        t = _make_table([("Lightning Bolt", 4)], [], ["vs Aggro"])
        # Select row 0 (the maindeck card)
        t.selectRow(0)
        t._swap_cards(None)
        self.assertEqual([c.name for c in t._state.maindeck], [])
        self.assertEqual(t._state.sb_candidates[0].name, "Lightning Bolt")
        self.assertEqual(t._state.sb_candidates[0].count, 4)

    def test_swap_one_moves_single_copy(self):
        t = _make_table([("Lightning Bolt", 4)], [], ["vs Aggro"])
        t.selectRow(0)
        t._swap_cards(1)
        card = next(c for c in t._state.maindeck if c.name == "Lightning Bolt")
        self.assertEqual(card.count, 3)
        cand = next(c for c in t._state.sb_candidates if c.name == "Lightning Bolt")
        self.assertEqual(cand.count, 1)

    def test_swap_all_moves_sb_to_main(self):
        t = _make_table([], [("Path to Exile", 3)], ["vs Aggro"],
                        sb_checks={"Path to Exile": {"vs Aggro": 3}})
        sb_start = t._sb_start_row()
        t.selectRow(sb_start)
        t._swap_cards(None)
        self.assertEqual([c.name for c in t._state.sb_candidates], [])
        card = next(c for c in t._state.maindeck if c.name == "Path to Exile")
        self.assertEqual(card.count, 3)


if __name__ == "__main__":
    unittest.main()
