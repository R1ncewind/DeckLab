from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QFileDialog, QInputDialog, QMessageBox,
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QListWidget, QListWidgetItem, QDialogButtonBox, QLabel, QComboBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

from models.mapping import MappingState, SBCandidate, VersionedMapping
from models.deck import Card
from file_io.decklist_parser import parse_decklist
from file_io.mapping_file import (
    save_versioned, load_versioned,
    latest_version_key, version_labels, version_to_state,
    new_versioned_from_state, determine_save_action, apply_save_action,
    versions_to_delete, apply_delete,
)
from ui.mapping_table import MappingTable
from ui.export_image import render_guide_image

_DECKS_DIR = Path(__file__).resolve().parent.parent / "decks"
_DECKS_DIR.mkdir(exist_ok=True)


class UnhideCardsDialog(QDialog):
    def __init__(self, hidden_cards: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Unhide Cards")
        self.setMinimumWidth(300)

        layout = QVBoxLayout(self)

        self._list = QListWidget()
        for name in hidden_cards:
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._list.addItem(item)
        layout.addWidget(self._list)

        btn_row = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self._select_all)
        btn_row.addWidget(select_all_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _select_all(self) -> None:
        for i in range(self._list.count()):
            self._list.item(i).setCheckState(Qt.CheckState.Checked)

    def selected_cards(self) -> list[str]:
        result = []
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                result.append(item.text())
        return result


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DeckLab")
        self.resize(1100, 700)

        self._table = MappingTable(self)
        self.setCentralWidget(self._table)
        self._mapping_path: str | None = None
        self._versioned_mapping: VersionedMapping | None = None
        self._version_combo_updating = False

        self._table.add_sb_requested.connect(self._add_sb_candidate)
        self._table.add_matchup_requested.connect(self._add_matchup)
        self._table.add_maindeck_requested.connect(self._add_maindeck_card)

        self._build_menu()
        self._build_toolbar()

    # ------------------------------------------------------------------
    # Toolbar
    # ------------------------------------------------------------------

    def _build_toolbar(self) -> None:
        tb = self.addToolBar("Version")
        tb.setMovable(False)
        tb.addWidget(QLabel("  Version: "))
        self._version_combo = QComboBox()
        self._version_combo.setMinimumWidth(80)
        self._version_combo.setEnabled(False)
        self._version_combo.currentTextChanged.connect(self._on_version_changed)
        tb.addWidget(self._version_combo)

    def _on_version_changed(self, label: str) -> None:
        if self._version_combo_updating or self._versioned_mapping is None or not label:
            return
        maj, min_ = (int(x) for x in label.split("."))
        state = version_to_state(self._versioned_mapping, maj, min_)
        self._table.load_state(state)

    def _refresh_version_combo(self, select_label: str) -> None:
        self._version_combo_updating = True
        self._version_combo.blockSignals(True)
        self._version_combo.clear()
        if self._versioned_mapping:
            for lbl in version_labels(self._versioned_mapping):
                self._version_combo.addItem(lbl)
            self._version_combo.setCurrentText(select_label)
            self._version_combo.setEnabled(True)
        else:
            self._version_combo.setEnabled(False)
        self._version_combo.blockSignals(False)
        self._version_combo_updating = False

    # ------------------------------------------------------------------
    # Menu construction
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        act = QAction("Save Mapping…", self)
        act.setShortcut("Ctrl+S")
        act.triggered.connect(self._save_mapping)
        file_menu.addAction(act)

        act = QAction("Save Mapping As…", self)
        act.triggered.connect(self._save_mapping_as)
        file_menu.addAction(act)

        act = QAction("Load Mapping…", self)
        act.setShortcut("Ctrl+O")
        act.triggered.connect(self._load_mapping)
        file_menu.addAction(act)

        act = QAction("Delete Version…", self)
        act.triggered.connect(self._delete_version)
        file_menu.addAction(act)

        file_menu.addSeparator()

        act = QAction("Export Guide as PNG…", self)
        act.setShortcut("Ctrl+Shift+E")
        act.triggered.connect(self._export_guide_image)
        file_menu.addAction(act)

        act = QAction("Export Guide as New PNG…", self)
        act.triggered.connect(self._export_guide_image_as)
        file_menu.addAction(act)

        # Decklist menu
        maindeck_menu = menubar.addMenu("&Decklist")

        act = QAction("Set Deck Name…", self)
        act.triggered.connect(self._set_deck_name)
        maindeck_menu.addAction(act)

        maindeck_menu.addSeparator()

        act = QAction("Load Decklist…", self)
        act.triggered.connect(self._load_decklist_file)
        maindeck_menu.addAction(act)

        act = QAction("Load Decklist from Clipboard…", self)
        act.triggered.connect(self._paste_decklist)
        maindeck_menu.addAction(act)

        maindeck_menu.addSeparator()

        act = QAction("Export Decklist to File…", self)
        act.triggered.connect(self._export_decklist_file)
        maindeck_menu.addAction(act)

        act = QAction("Copy Decklist to Clipboard", self)
        act.triggered.connect(self._export_decklist_clipboard)
        maindeck_menu.addAction(act)

        maindeck_menu.addSeparator()

        act = QAction("Unhide Cards…", self)
        act.triggered.connect(self._unhide_cards)
        maindeck_menu.addAction(act)

        # Matchups menu
        matchup_menu = menubar.addMenu("&Matchups")

        act = QAction("Add Matchup…", self)
        act.triggered.connect(self._add_matchup)
        matchup_menu.addAction(act)

        act = QAction("Remove Matchup…", self)
        act.triggered.connect(self._remove_matchup)
        matchup_menu.addAction(act)

        act = QAction("Load Matchups from File…", self)
        act.triggered.connect(self._load_matchups_file)
        matchup_menu.addAction(act)

        act = QAction("Export Matchups…", self)
        act.triggered.connect(self._export_matchups_file)
        matchup_menu.addAction(act)

        act = QAction("Sort by Coverage", self)
        act.triggered.connect(self._table.sort_matchups_by_coverage)
        matchup_menu.addAction(act)

        # Sideboard menu
        sb_menu = menubar.addMenu("&Sideboard")

        act = QAction("Add Candidate…", self)
        act.triggered.connect(self._add_sb_candidate)
        sb_menu.addAction(act)

        act = QAction("Remove Selected Row", self)
        act.triggered.connect(self._remove_sb_candidate)
        sb_menu.addAction(act)

    # ------------------------------------------------------------------
    # File actions
    # ------------------------------------------------------------------

    def _load_decklist_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Decklist", str(_DECKS_DIR), "Text Files (*.txt);;All Files (*)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
            self._apply_decklist(text)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load decklist:\n{e}")

    def _paste_decklist(self) -> None:
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if not text.strip():
            QMessageBox.warning(self, "Empty Clipboard", "Clipboard does not contain text.")
            return
        self._apply_decklist(text)

    def _apply_decklist(self, text: str) -> None:
        deck = parse_decklist(text)
        state = self._table.get_state()
        state.maindeck = deck.maindeck

        # Replace sb_candidates from the pasted deck's sideboard when present
        if deck.sideboard:
            state.sb_candidates = [SBCandidate(c.name, c.count) for c in deck.sideboard]

        # Re-initialise board_outs for new maindeck
        new_board_outs: dict[str, dict[str, int]] = {}
        for card in deck.maindeck:
            existing = state.board_outs.get(card.name, {})
            new_board_outs[card.name] = {m: existing.get(m, 0) for m in state.matchups}
        state.board_outs = new_board_outs

        # Re-initialise sb_checks for sb_candidates
        new_sb_checks: dict[str, dict[str, bool]] = {}
        for cand in state.sb_candidates:
            existing = state.sb_checks.get(cand.name, {})
            new_sb_checks[cand.name] = {m: existing.get(m, 0) for m in state.matchups}
        state.sb_checks = new_sb_checks

        self._table.load_state(state)

    def _save_mapping(self) -> None:
        if not self._mapping_path:
            self._save_mapping_as()
            return
        state = self._table.get_state()
        if self._versioned_mapping is None:
            self._save_mapping_as()
            return
        self._versioned_mapping.name = state.name
        action = determine_save_action(self._versioned_mapping, state)
        if action == "no_change":
            QMessageBox.information(self, "No Changes", "No changes found since the last saved version.")
            return
        maj, min_ = apply_save_action(self._versioned_mapping, state, action)
        try:
            save_versioned(self._versioned_mapping, self._mapping_path)
            self._refresh_version_combo(f"{maj}.{min_}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save mapping:\n{e}")

    def _save_mapping_as(self) -> None:
        state = self._table.get_state()
        suggested = state.name.replace(" ", "_") + ".json" if state.name else ""
        start_dir = str(Path(self._mapping_path).parent) if self._mapping_path else str(_DECKS_DIR)
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Mapping As", str(Path(start_dir) / suggested),
            "JSON Files (*.json);;All Files (*)"
        )
        if not path:
            return
        try:
            vm = new_versioned_from_state(state)
            save_versioned(vm, path)
            self._mapping_path = path
            self._versioned_mapping = vm
            self._refresh_version_combo("1.0")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save mapping:\n{e}")

    def _load_mapping(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Mapping", str(_DECKS_DIR), "JSON Files (*.json);;All Files (*)"
        )
        if not path:
            return
        try:
            vm = load_versioned(path)
            maj, min_ = latest_version_key(vm)
            state = version_to_state(vm, maj, min_)
            self._versioned_mapping = vm
            self._mapping_path = path
            self._table.load_state(state)
            self._refresh_version_combo(f"{maj}.{min_}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load mapping:\n{e}")

    def _delete_version(self) -> None:
        if self._versioned_mapping is None:
            QMessageBox.information(self, "No Mapping", "No mapping is loaded.")
            return
        vm = self._versioned_mapping
        labels = version_labels(vm)
        if len(labels) == 1:
            QMessageBox.information(self, "Cannot Delete", "Cannot delete the only version.")
            return
        label, ok = QInputDialog.getItem(
            self, "Delete Version", "Select version to delete:", labels, 0, False
        )
        if not ok or not label:
            return
        major, minor = (int(x) for x in label.split("."))
        to_delete = versions_to_delete(vm, major, minor)
        # Check that deletion would leave at least one version
        all_pairs = [
            (maj, min_)
            for maj in vm.versions
            for min_ in vm.versions[maj].minor_versions
        ]
        if len(all_pairs) - len(to_delete) < 1:
            QMessageBox.information(self, "Cannot Delete", "Cannot delete the only version.")
            return
        needs_confirmation = (minor == 0) or (len(to_delete) > 1)
        if needs_confirmation:
            delete_labels = [f"{maj}.{min_}" for maj, min_ in to_delete]
            msg = (
                "The following versions will be permanently deleted:\n\n"
                + "\n".join(f"  \u2022 {lbl}" for lbl in delete_labels)
                + "\n\nThis cannot be undone. Continue?"
            )
            reply = QMessageBox.warning(
                self, "Confirm Deletion", msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        apply_delete(vm, major, minor)
        new_maj, new_min = latest_version_key(vm)
        new_label = f"{new_maj}.{new_min}"
        state = version_to_state(vm, new_maj, new_min)
        self._table.load_state(state)
        self._refresh_version_combo(new_label)
        if self._mapping_path:
            try:
                save_versioned(vm, self._mapping_path)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save mapping:\n{e}")

    def _export_guide_image(self) -> None:
        if self._mapping_path:
            img = render_guide_image(self._table.get_state(), self._version_combo.currentText())
            if img is None:
                QMessageBox.information(self, "Nothing to Export",
                    "No board-out or sideboard data to export.")
                return
            path = str(Path(self._mapping_path).with_suffix(".png"))
            if not img.save(path, "PNG"):
                QMessageBox.critical(self, "Error", f"Failed to save image:\n{path}")
        else:
            self._export_guide_image_as()

    def _export_guide_image_as(self) -> None:
        img = render_guide_image(self._table.get_state(), self._version_combo.currentText())
        if img is None:
            QMessageBox.information(self, "Nothing to Export",
                "No board-out or sideboard data to export.")
            return
        state = self._table.get_state()
        suggested = state.name.replace(" ", "_") + ".png" if state.name else ""
        start_dir = str(Path(self._mapping_path).parent) if self._mapping_path else str(_DECKS_DIR)
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Guide as New PNG", str(Path(start_dir) / suggested),
            "PNG Images (*.png);;All Files (*)"
        )
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        if not img.save(path, "PNG"):
            QMessageBox.critical(self, "Error", f"Failed to save image:\n{path}")

    def _set_deck_name(self) -> None:
        current = self._table.get_state().name
        name, ok = QInputDialog.getText(self, "Set Deck Name", "Deck name:", text=current)
        if ok:
            self._table.get_state().name = name.strip()
            self._table.horizontalHeader().set_deck_name(self._table.get_state().name)

    # ------------------------------------------------------------------
    # Matchup actions
    # ------------------------------------------------------------------

    def _add_matchup(self) -> None:
        name, ok = QInputDialog.getText(self, "Add Matchup", "Matchup name:")
        if ok and name.strip():
            self._table.add_matchup(name.strip())

    def _remove_matchup(self) -> None:
        matchups = self._table.get_matchup_names()
        if not matchups:
            QMessageBox.information(self, "No Matchups", "There are no matchups to remove.")
            return
        name, ok = QInputDialog.getItem(
            self, "Remove Matchup", "Select matchup to remove:", matchups, 0, False
        )
        if ok and name:
            self._table.remove_matchup(name)

    def _export_matchups_file(self) -> None:
        matchups = self._table.get_matchup_names()
        if not matchups:
            QMessageBox.information(self, "No Matchups", "There are no matchups to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Matchups", str(_DECKS_DIR), "Text Files (*.txt);;All Files (*)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(matchups) + "\n")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export matchups:\n{e}")

    def _load_matchups_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Matchups", str(_DECKS_DIR), "Text Files (*.txt);;All Files (*)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                names = [line.strip() for line in f if line.strip()]
            for name in names:
                self._table.add_matchup(name)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load matchups:\n{e}")

    # ------------------------------------------------------------------
    # Sideboard actions
    # ------------------------------------------------------------------

    def _add_maindeck_card(self) -> None:
        name, ok = QInputDialog.getText(self, "Add Card", "Card name:")
        if not ok or not name.strip():
            return
        count_str, ok = QInputDialog.getText(self, "Add Card", "Count:", text="1")
        if not ok:
            return
        try:
            count = int(count_str.strip())
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Count must be an integer.")
            return
        self._table.add_maindeck_card(name.strip(), count)

    def _add_sb_candidate(self) -> None:
        name, ok = QInputDialog.getText(self, "Add SB Candidate", "Card name:")
        if not ok or not name.strip():
            return
        count_str, ok = QInputDialog.getText(self, "Add SB Candidate", "Count:", text="1")
        if not ok:
            return
        try:
            count = int(count_str.strip())
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Count must be an integer.")
            return
        self._table.add_sb_candidate(name.strip(), count)

    def _unhide_cards(self) -> None:
        hidden = self._table.get_state().hidden_cards
        if not hidden:
            QMessageBox.information(self, "No Hidden Cards", "No maindeck cards are currently hidden.")
            return
        dlg = UnhideCardsDialog(list(hidden), self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            names = dlg.selected_cards()
            if names:
                self._table.unhide_maindeck_cards(names)

    def _decklist_text(self) -> str:
        state = self._table.get_state()
        lines = []
        for card in state.maindeck:
            if card.count > 0:
                lines.append(f"{card.count} {card.name}")
        sb_cards = [c for c in state.sb_candidates if c.count > 0]
        if sb_cards:
            lines.append("")
            lines.append("Sideboard")
            for cand in sb_cards:
                lines.append(f"{cand.count} {cand.name}")
        return "\n".join(lines) + "\n"

    def _export_decklist_file(self) -> None:
        state = self._table.get_state()
        if not state.maindeck:
            QMessageBox.information(self, "Empty Decklist", "No maindeck cards to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Decklist", str(_DECKS_DIR), "Text Files (*.txt);;All Files (*)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._decklist_text())
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export decklist:\n{e}")

    def _export_decklist_clipboard(self) -> None:
        state = self._table.get_state()
        if not state.maindeck:
            QMessageBox.information(self, "Empty Decklist", "No maindeck cards to copy.")
            return
        QApplication.clipboard().setText(self._decklist_text())

    def _remove_sb_candidate(self) -> None:
        row = self._table.selected_sb_row()
        if row == -1:
            QMessageBox.information(
                self, "No Selection", "Please select a sideboard candidate row to remove."
            )
            return
        self._table.remove_sb_candidate(row)
