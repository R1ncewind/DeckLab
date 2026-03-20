import re
from models.deck import Card, Deck


def parse_decklist(text: str) -> Deck:
    """Parse an MTGO-style decklist into a Deck.

    Supports two variants:
    - Variant A: 'Sideboard' keyword on its own line separates maindeck from sideboard
    - Variant B: first blank line separates maindeck from sideboard
    """
    lines = text.splitlines()

    # Detect variant A: 'Sideboard' as its own line (case-insensitive)
    sideboard_line_idx = None
    for i, line in enumerate(lines):
        if line.strip().lower() == "sideboard":
            sideboard_line_idx = i
            break

    if sideboard_line_idx is not None:
        main_lines = lines[:sideboard_line_idx]
        sb_lines = lines[sideboard_line_idx + 1:]
    else:
        # Variant B: split on first blank line
        first_blank = None
        for i, line in enumerate(lines):
            if line.strip() == "":
                first_blank = i
                break
        if first_blank is not None:
            main_lines = lines[:first_blank]
            sb_lines = lines[first_blank + 1:]
        else:
            main_lines = lines
            sb_lines = []

    return Deck(
        maindeck=_parse_card_lines(main_lines),
        sideboard=_parse_card_lines(sb_lines),
    )


def _parse_card_lines(lines: list[str]) -> list[Card]:
    cards = []
    pattern = re.compile(r"^(\d+)\s+(.+)$")
    for line in lines:
        line = line.strip()
        if not line:
            continue
        m = pattern.match(line)
        if m:
            cards.append(Card(name=m.group(2).strip(), count=int(m.group(1))))
    return cards
