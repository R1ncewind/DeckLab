import unittest

from file_io.decklist_parser import parse_decklist


class TestDecklistParser(unittest.TestCase):

    # --- Variant A: "Sideboard" keyword ---

    def test_variant_a_basic(self):
        text = "4 Lightning Bolt\n2 Counterspell\nSideboard\n3 Path to Exile\n1 Disdainful Stroke"
        deck = parse_decklist(text)
        self.assertEqual([(c.name, c.count) for c in deck.maindeck],
                         [("Lightning Bolt", 4), ("Counterspell", 2)])
        self.assertEqual([(c.name, c.count) for c in deck.sideboard],
                         [("Path to Exile", 3), ("Disdainful Stroke", 1)])

    def test_variant_a_case_insensitive(self):
        for keyword in ("SIDEBOARD", "sideboard", "Sideboard", "SiDeBoArD"):
            with self.subTest(keyword=keyword):
                deck = parse_decklist(f"4 Lightning Bolt\n{keyword}\n3 Path to Exile")
                self.assertEqual(len(deck.maindeck), 1)
                self.assertEqual(len(deck.sideboard), 1)

    def test_variant_a_empty_sideboard(self):
        deck = parse_decklist("4 Lightning Bolt\nSideboard\n")
        self.assertEqual(len(deck.maindeck), 1)
        self.assertEqual(deck.sideboard, [])

    # --- Variant B: blank line separator ---

    def test_variant_b_basic(self):
        text = "4 Lightning Bolt\n2 Counterspell\n\n3 Path to Exile\n1 Disdainful Stroke"
        deck = parse_decklist(text)
        self.assertEqual([(c.name, c.count) for c in deck.maindeck],
                         [("Lightning Bolt", 4), ("Counterspell", 2)])
        self.assertEqual([(c.name, c.count) for c in deck.sideboard],
                         [("Path to Exile", 3), ("Disdainful Stroke", 1)])

    def test_variant_b_only_first_blank_line_splits(self):
        text = "4 Lightning Bolt\n\n3 Path to Exile\n\n1 Disdainful Stroke"
        deck = parse_decklist(text)
        self.assertEqual(len(deck.maindeck), 1)
        self.assertEqual(len(deck.sideboard), 2)

    # --- No sideboard ---

    def test_no_sideboard_no_blank_line(self):
        deck = parse_decklist("4 Lightning Bolt\n2 Counterspell")
        self.assertEqual(len(deck.maindeck), 2)
        self.assertEqual(deck.sideboard, [])

    # --- Edge cases ---

    def test_empty_input(self):
        deck = parse_decklist("")
        self.assertEqual(deck.maindeck, [])
        self.assertEqual(deck.sideboard, [])

    def test_non_matching_lines_skipped(self):
        text = "Deck\n4 Lightning Bolt\nsome header\n2 Counterspell"
        deck = parse_decklist(text)
        self.assertEqual([(c.name, c.count) for c in deck.maindeck],
                         [("Lightning Bolt", 4), ("Counterspell", 2)])

    def test_multiword_card_name(self):
        deck = parse_decklist("4 Teferi, Hero of Dominaria")
        self.assertEqual(deck.maindeck[0].name, "Teferi, Hero of Dominaria")
        self.assertEqual(deck.maindeck[0].count, 4)

    def test_leading_trailing_whitespace_in_lines(self):
        deck = parse_decklist("  4 Lightning Bolt  \n  2 Counterspell  ")
        self.assertEqual(len(deck.maindeck), 2)
        self.assertEqual(deck.maindeck[0].name, "Lightning Bolt")


if __name__ == "__main__":
    unittest.main()
