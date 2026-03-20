# DeckLab

DeckLab is a desktop tool for Magic: The Gathering players who want to build their sideboards methodically. It lets you map out exactly which cards you board in and out against each matchup, then shows at a glance whether your sideboard has enough cards to cover your plans.

---

## Getting started

### Prerequisites

- Python 3.10 or later

### Installation

**Linux / macOS**
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

**Windows**
```bat
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

### Launching

**Linux / macOS**
```bash
./run.sh
```

**Windows**
Double-click `run.bat`. No console window will appear.

---

## The concept: sideboard mapping

The idea is to treat sideboarding as a numbers problem.

For each matchup you play, you have some cards you want to cut from your maindeck ("board out") and some sideboard cards you want to bring in ("board in"). If the number of cards you bring in equals the number you take out, the 60-card count stays correct.

DeckLab tracks this for every matchup simultaneously. The **Coverage** row at the bottom shows `sb_in − board_out` per matchup:

- **Green** (zero): your board-in count exactly matches your board-out count for that matchup.
- **Yellow / Red**: there is an imbalance in either direction — either you are boarding out more than you are bringing in, or bringing in more than you are taking out. Both result in an illegal 60-card count, so both are flagged. The colour intensifies with the size of the gap.

---

## Workflow

### 1. Load your decklist

Go to **Decklist → Load Decklist…** to open a `.txt` file, or use **Load Decklist from Clipboard…** if you have copied a list from a website or client.

DeckLab accepts standard MTGO export format:

```
4 Lightning Bolt
4 Monastery Swiftspear
...

Sideboard
4 Smash to Smithereens
...
```

If your decklist includes a sideboard section, those cards are automatically imported as sideboard candidates.

You can give the deck a name via **Decklist → Set Deck Name…** — this appears in the column header and on exported images.

### 2. Define your matchups

Go to **Matchups → Add Matchup…** or click the **＋** column header on the far right of the table. Name the matchup (e.g. "Burn", "Control", "Mirror").

Repeat for every matchup you care about. Matchups become columns in the table.

You can also save a list of matchup names to a `.txt` file and reload it later via **Matchups → Export Matchups…** and **Load Matchups from File…**.

### 3. Enter board-out counts

Each maindeck card is a row. Click a cell at the intersection of a card row and a matchup column, then type the number of copies you plan to cut in that matchup.

- Cells are blank when the value is zero; a zero appears while the cell is selected to make editing easier.
- Values are clamped to `[0, card count]` automatically.
- The **Board Out** separator row totals the board-out count per matchup.

### 4. Add sideboard candidates

Sideboard candidates appear below the Board Out separator. You can add them by:

- Clicking the **＋ Add card…** row at the bottom of the maindeck section (for maindeck additions) or the row below the sideboard section.
- Going to **Sideboard → Add Candidate…**.
- Loading a decklist that already has a sideboard section (step 1).

For each candidate, enter the number of copies you intend to bring in for each matchup — just like the board-out cells above.

### 5. Read the Coverage row

The **Coverage ↕** row at the very bottom shows `sb_in − board_out` for each matchup, colour-coded:

| Colour        | Meaning |
|---------------|---------|
| Green         | Perfectly balanced — board-in equals board-out |
| Yellow / Red  | Imbalance in either direction. Too few cards coming in (deficit) or too many (surplus) both leave you with the wrong deck size. Intensity scales with the size of the gap. |

Clicking the **Coverage ↕** label sorts matchup columns by their coverage value: deficit matchups (negative) move to the left, balanced matchups (zero) settle in the middle, and surplus matchups (positive) move to the right. Both extremes are imbalanced; the ideal matchups naturally cluster in the centre.

### 6. Multi-matchup candidate analysis

Select two or more cells in the **Coverage** row (hold Ctrl or Shift to multi-select). DeckLab highlights in yellow the sideboard candidate(s) that cover the most of those selected matchups — useful for finding the most versatile card to fill a gap across several matchups at once.

---

## Saving and loading your work

Mappings are saved as JSON files (**File → Save Mapping…** / **Ctrl+S**, or **Save Mapping As…**).

### Versioning

Every save creates a new version rather than overwriting. If your maindeck or sideboard candidates change, a new **major** version is created (e.g. 1.0 → 2.0). If only counts or board-out values change, a new **minor** version is added (e.g. 1.0 → 1.1).

The **Version** drop-down in the toolbar lets you switch between all saved versions of a mapping. This makes it easy to compare how your sideboard plan evolved as you refined the deck.

To remove old versions you no longer need, use **File → Delete Version…**. Deleting a major version removes all its minor versions.

---

## Exporting a guide image

**File → Export Guide as PNG…** (or **Ctrl+Shift+E**) renders the current mapping as a high-resolution image (300 DPI, up to 5×7 inches) suitable for printing. The image is sized to fold down to roughly a Magic card — handy to keep in your deckbox during a tournament.

The image includes:
- The deck name and version label
- All visible maindeck cards and their board-out counts
- All sideboard candidates and their board-in counts
- Coverage totals per matchup

---

## Managing rows and columns

### Hiding maindeck cards

If your maindeck has cards you never board out (lands, for example), you can hide them to keep the table tidy. Right-click any maindeck row and choose **Hide selected row(s)**. The card's board-out data is preserved; it simply disappears from view.

To restore hidden cards: **Decklist → Unhide Cards…**.

### Deleting maindeck cards

Right-click a maindeck row and choose **Delete selected row**. This permanently removes the card and its board-out data.

### Removing sideboard candidates

Right-click a sideboard candidate row and choose **Remove selected candidate(s)**, or use **Sideboard → Remove Selected Row**.

### Removing matchups

Right-click a matchup column header and choose **Remove matchup '…'**, or use **Matchups → Remove Matchup…**.

---

## Exporting the decklist

**Decklist → Export Decklist to File…** saves the current maindeck and sideboard candidates as a `.txt` file in standard MTGO format.

**Decklist → Copy Decklist to Clipboard** does the same but copies to the clipboard so you can paste directly into a client or website.

---

## Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+S | Save Mapping |
| Ctrl+O | Load Mapping |
| Ctrl+Shift+E | Export Guide as PNG |

---

## Feedback

If you find a bug or have a suggestion, please open an issue on the project repository or contact the developer directly. Thank you for testing!
