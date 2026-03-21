from math import sqrt, sin, acos, hypot, degrees, radians

from PyQt6.QtWidgets import (
    QTableWidget, QTableWidgetItem,
    QHeaderView, QMenu, QStyle, QStyleOptionHeader,
)
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QRectF, QPoint, QTimer
from PyQt6.QtGui import QBrush, QColor, QAction, QFont, QTransform, QPainter

from models.mapping import MappingState, SBCandidate
from models.deck import Card


class AngledHeader(QHeaderView):
    """Horizontal header that draws matchup columns at 45° using paintEvent.

    fixed_left:  number of normal (non-angled) columns on the left  (e.g. 2: # and Card)
    fixed_right: number of normal (non-angled) columns on the right (e.g. 1: +)
    """

    def __init__(self, fixed_left: int = 0, fixed_right: int = 0, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._fixed_left = fixed_left
        self._fixed_right = fixed_right
        self._pressed_section = -1
        self._deck_name: str = ""
        self.setSectionsClickable(True)

    def set_deck_name(self, name: str) -> None:
        self._deck_name = name
        self.viewport().update()

    def _is_angled(self, logical_index: int) -> bool:
        total = self.count()
        return self._fixed_left <= logical_index < total - self._fixed_right

    # ------------------------------------------------------------------
    # Height: tall enough for the longest angled label
    # ------------------------------------------------------------------

    def sizeHint(self):
        hint = super().sizeHint()
        if not self.model():
            return hint
        fm = self.fontMetrics()
        min_size = self.defaultSectionSize()
        max_diag = max_w = max_h = 1
        for s in range(self.count()):
            if not self._is_angled(s) or self.isSectionHidden(s):
                continue
            label = self.model().headerData(s, Qt.Orientation.Horizontal,
                                            Qt.ItemDataRole.DisplayRole)
            if not label:
                continue
            rect = fm.boundingRect(str(label) + '    ')
            diag = max(1.0, hypot(rect.width(), rect.height()))
            if diag > max_diag:
                max_diag = diag
                max_w = max(1, rect.width())
                max_h = max(1, rect.height())
        if max_diag > 1:
            angle = degrees(acos(
                (max_diag**2 + max_w**2 - max_h**2) / (2.0 * max_diag * max_w)
            ))
            min_size = max(min_size, sin(radians(angle + 45)) * max_diag)
        hint.setHeight(min(self.maximumHeight(), int(min_size)))
        return hint

    # ------------------------------------------------------------------
    # Click detection: shear-polygon for angled cols, rect for normal cols
    # ------------------------------------------------------------------

    def _section_at(self, pos: QPoint) -> int:
        """Return the logical section index hit by pos, or -1."""
        h = self.height()
        for s in range(self.count()):
            if self.isSectionHidden(s):
                continue
            x = self.sectionViewportPosition(s)
            w = self.sectionSize(s)
            if self._is_angled(s):
                rect = QRect(x, 0, w, -h)
                transform = QTransform().translate(0, h).shear(-1, 0)
                if transform.mapToPolygon(rect).containsPoint(
                        pos, Qt.FillRule.WindingFill):
                    return s
            else:
                if QRect(x, 0, w, h).contains(pos):
                    return s
        return -1

    def mousePressEvent(self, event) -> None:
        s = self._section_at(event.position().toPoint())
        if s != -1:
            self._pressed_section = s
            self.sectionPressed.emit(s)

    def mouseReleaseEvent(self, event) -> None:
        s = self._section_at(event.position().toPoint())
        if s != -1 and s == self._pressed_section:
            self.sectionClicked.emit(s)
        self._pressed_section = -1

    # ------------------------------------------------------------------
    # Painting: one painter over the full header viewport
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:
        qp = QPainter(self.viewport())
        qp.setRenderHint(QPainter.RenderHint.Antialiasing)
        h = self.height()
        fm = self.fontMetrics()
        fm_delta = (fm.height() - fm.descent()) * 0.5

        for s in range(self.count()):
            if self.isSectionHidden(s):
                continue
            x = self.sectionViewportPosition(s)
            w = self.sectionSize(s)
            label = str(self.model().headerData(
                s, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) or "")

            if self._is_angled(s):
                # --- parallelogram background via shear transform ---
                rect = QRectF(x, 0, w, -h)
                qp.save()
                qp.setPen(self.palette().mid().color())
                qp.setTransform(
                    qp.transform().translate(0, h).shear(-1, 0)
                )
                qp.drawRect(rect)
                qp.setPen(Qt.PenStyle.NoPen)
                qp.setBrush(self.palette().button())
                qp.drawRect(rect.adjusted(1, -1, -1, 1))
                qp.restore()

                # --- rotated text ---
                diagonal = hypot(h, h)
                elided = fm.elidedText(
                    label,
                    Qt.TextElideMode.ElideRight,
                    int(diagonal * 0.9),
                )
                qp.save()
                qp.translate(x + w, h)
                qp.rotate(-45)
                qp.drawText(0, int(-fm_delta), elided)
                qp.restore()

            else:
                # --- normal horizontal section ---
                opt = QStyleOptionHeader()
                self.initStyleOption(opt)
                opt.rect = QRect(x, 0, w, h)
                opt.section = s
                vis = self.visualIndex(s)
                total = self.count()
                if vis == 0:
                    opt.position = QStyleOptionHeader.SectionPosition.Beginning
                elif vis == total - 1:
                    opt.position = QStyleOptionHeader.SectionPosition.End
                else:
                    opt.position = QStyleOptionHeader.SectionPosition.Middle

                if s in (_COL_NAME, _COL_COUNT):
                    # Always draw label bottom-aligned; deck name at top when set
                    opt.text = ""
                    self.style().drawControl(QStyle.ControlElement.CE_Header, opt, qp, self)
                    inset = 3
                    rect = QRect(x + inset, inset, w - 2 * inset, h - 2 * inset)
                    if s == _COL_NAME:
                        if self._deck_name:
                            qp.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, self._deck_name)
                        qp.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, "Card")
                    else:  # _COL_COUNT
                        qp.drawText(rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom, "#")
                else:
                    opt.text = label
                    self.style().drawControl(QStyle.ControlElement.CE_Header, opt, qp, self)


def _coverage_color(coverage: int) -> QColor:
    t = min(abs(coverage) / 10.0, 1.0)
    if t <= 0.5:
        r = int(255 * (t * 2))
        g = 255
    else:
        r = 255
        g = int(255 * (1 - (t - 0.5) * 2))
    return QColor(r, g, 0)


# Column indices for fixed columns
_COL_COUNT = 0
_COL_NAME = 1
_FIXED_COLS = 2


class MappingTable(QTableWidget):
    add_sb_requested = pyqtSignal()
    add_matchup_requested = pyqtSignal()
    add_maindeck_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state: MappingState = MappingState()
        self._rebuilding = False
        self._matchup_widths: dict[str, int] = {}
        self._highlighted_sb_indices: set[int] = set()

        # Install custom angled header before wiring signals
        self.setHorizontalHeader(
            AngledHeader(fixed_left=_FIXED_COLS, fixed_right=0, parent=self)
        )

        self.setAlternatingRowColors(True)
        self.horizontalHeader().setStretchLastSection(False)
        self.verticalHeader().setVisible(False)

        self.cellChanged.connect(self._on_cell_changed)
        self.cellClicked.connect(self._on_cell_clicked)
        self.horizontalHeader().sectionClicked.connect(self._on_header_clicked)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.horizontalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.horizontalHeader().customContextMenuRequested.connect(self._show_header_context_menu)
        self.selectionModel().selectionChanged.connect(self._on_selection_changed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_state(self, state: MappingState) -> None:
        self._state = state
        self._rebuild()

    def get_state(self) -> MappingState:
        return self._state

    def add_matchup(self, name: str) -> None:
        if name in self._state.matchups:
            return
        self._state.matchups.append(name)
        for card in self._state.maindeck:
            self._state.board_outs.setdefault(card.name, {})[name] = 0
        for cand in self._state.sb_candidates:
            self._state.sb_checks.setdefault(cand.name, {})[name] = 0
        self._rebuild()

    def remove_matchup(self, name: str) -> None:
        if name not in self._state.matchups:
            return
        self._state.matchups.remove(name)
        for d in self._state.board_outs.values():
            d.pop(name, None)
        for d in self._state.sb_checks.values():
            d.pop(name, None)
        self._rebuild()

    def add_sb_candidate(self, name: str, count: int) -> None:
        self._state.sb_candidates.append(SBCandidate(name=name, count=count))
        self._state.sb_checks[name] = {m: 0 for m in self._state.matchups}
        self._rebuild()

    def add_maindeck_card(self, name: str, count: int) -> None:
        self._state.maindeck.append(Card(name, count))
        self._state.board_outs[name] = {m: 0 for m in self._state.matchups}
        self._rebuild()

    def delete_maindeck_cards(self, card_names: list[str]) -> None:
        name_set = set(card_names)
        self._state.maindeck = [c for c in self._state.maindeck if c.name not in name_set]
        for name in name_set:
            self._state.board_outs.pop(name, None)
        self._state.hidden_cards = [n for n in self._state.hidden_cards if n not in name_set]
        self._rebuild()

    def remove_sb_candidate(self, row: int) -> None:
        """Remove an SB candidate by absolute table row index."""
        sb_start = self._sb_start_row()
        sb_idx = row - sb_start
        if sb_idx < 0 or sb_idx >= len(self._state.sb_candidates):
            return
        cand = self._state.sb_candidates.pop(sb_idx)
        self._state.sb_checks.pop(cand.name, None)
        self._rebuild()

    def hide_maindeck_card(self, card_name: str) -> None:
        if card_name not in self._state.hidden_cards:
            self._state.hidden_cards.append(card_name)
        self._rebuild()

    def unhide_maindeck_card(self, card_name: str) -> None:
        if card_name in self._state.hidden_cards:
            self._state.hidden_cards.remove(card_name)
        self._rebuild()

    def unhide_maindeck_cards(self, card_names: list[str]) -> None:
        for name in card_names:
            if name in self._state.hidden_cards:
                self._state.hidden_cards.remove(name)
        self._rebuild()

    def selected_sb_row(self) -> int:
        """Return the table row of the currently selected SB candidate, or -1."""
        rows = self.selectionModel().selectedRows()
        if not rows:
            cells = self.selectionModel().selectedIndexes()
            if cells:
                row = cells[0].row()
            else:
                return -1
        else:
            row = rows[0].row()

        sb_start = self._sb_start_row()
        add_sb = self._add_sb_row()
        if sb_start <= row < add_sb:
            return row
        return -1

    def get_matchup_names(self) -> list[str]:
        return list(self._state.matchups)

    def sort_matchups_by_coverage(self) -> None:
        visible = self._visible_maindeck()

        def coverage(matchup: str) -> int:
            board_out = sum(
                self._state.board_outs.get(c.name, {}).get(matchup, 0)
                for c in visible
            )
            sb_in = sum(
                self._state.sb_checks.get(cand.name, {}).get(matchup, 0)
                for cand in self._state.sb_candidates
            )
            return sb_in - board_out

        self._state.matchups.sort(key=coverage)
        self._rebuild()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _visible_maindeck(self) -> list[Card]:
        hidden = set(self._state.hidden_cards)
        return [c for c in self._state.maindeck if c.name not in hidden]

    def _add_maindeck_row(self) -> int:
        return len(self._visible_maindeck())

    def _separator_row(self) -> int:
        return self._add_maindeck_row() + 1

    def _sb_start_row(self) -> int:
        return self._separator_row() + 1

    def _add_sb_row(self) -> int:
        return self._sb_start_row() + len(self._state.sb_candidates)

    def _coverage_row(self) -> int:
        return self._add_sb_row() + 1

    def _total_rows(self) -> int:
        return self._coverage_row() + 1

    def _total_cols(self) -> int:
        return _FIXED_COLS + len(self._state.matchups) + 1  # +1 for "＋" column

    def _plus_col(self) -> int:
        return _FIXED_COLS + len(self._state.matchups)

    # ------------------------------------------------------------------
    # Column sizing
    # ------------------------------------------------------------------

    def _apply_column_modes(self) -> None:
        hh = self.horizontalHeader()
        fm = hh.fontMetrics()
        angled_width = int(sqrt((fm.height() + 4) ** 2 * 2))
        plus_col = self._plus_col()
        for col in range(self._total_cols()):
            if col in (_COL_COUNT, _COL_NAME):
                hh.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
            else:
                hh.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
                hh.resizeSection(col, angled_width)
        hh.updateGeometry()
        self._fix_scrollbar()

    # ------------------------------------------------------------------
    # Rebuild the entire table from state
    # ------------------------------------------------------------------

    def _rebuild(self) -> None:
        self._highlighted_sb_indices.clear()
        self._rebuilding = True
        try:
            # Reset any column spans from the previous build before changing row count
            for r in range(self.rowCount()):
                if self.columnSpan(r, 0) > 1:
                    self.setSpan(r, 0, 1, 1)

            self.clearContents()
            self.setRowCount(self._total_rows())
            self.setColumnCount(self._total_cols())

            headers = ["#", "Card"] + self._state.matchups + ["＋"]
            self.setHorizontalHeaderLabels(headers)

            self._populate_maindeck_rows()
            self._populate_add_maindeck_row()
            self._populate_separator_row()
            self._populate_sb_rows()
            self._populate_add_sb_row()
            self._populate_coverage_row()
            self._apply_column_modes()
            self.horizontalHeader().set_deck_name(self._state.name)
        finally:
            self._rebuilding = False

    def _make_readonly_item(self, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item

    def _populate_maindeck_rows(self) -> None:
        visible = self._visible_maindeck()
        for i, card in enumerate(visible):
            count_item = QTableWidgetItem(str(card.count))
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(i, _COL_COUNT, count_item)
            self.setItem(i, _COL_NAME, QTableWidgetItem(card.name))
            for j, matchup in enumerate(self._state.matchups):
                col = _FIXED_COLS + j
                val = self._state.board_outs.get(card.name, {}).get(matchup, 0)
                item = QTableWidgetItem("" if val == 0 else str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.setItem(i, col, item)
            self.setItem(i, self._plus_col(), self._make_readonly_item(""))

    def _populate_add_maindeck_row(self) -> None:
        row = self._add_maindeck_row()
        self.setSpan(row, 0, 1, 2)
        label = self._make_readonly_item("＋ Add card…")
        label.setForeground(QColor("#888888"))
        font = self.font()
        font.setItalic(True)
        label.setFont(font)
        self.setItem(row, _COL_COUNT, label)
        for j in range(len(self._state.matchups)):
            self.setItem(row, _FIXED_COLS + j, self._make_readonly_item(""))
        self.setItem(row, self._plus_col(), self._make_readonly_item(""))

    def _populate_separator_row(self) -> None:
        row = self._separator_row()
        visible = self._visible_maindeck()
        total_count = sum(c.count for c in self._state.maindeck)
        count_item = self._make_readonly_item(str(total_count))
        count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        count_item.setBackground(QColor("#d0d0d0"))
        self.setItem(row, _COL_COUNT, count_item)
        label = self._make_readonly_item("Board Out")
        label.setBackground(QColor("#d0d0d0"))
        self.setItem(row, _COL_NAME, label)
        for j, matchup in enumerate(self._state.matchups):
            col = _FIXED_COLS + j
            total = sum(
                self._state.board_outs.get(c.name, {}).get(matchup, 0)
                for c in visible
            )
            item = self._make_readonly_item(str(total))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setBackground(QColor("#d0d0d0"))
            self.setItem(row, col, item)
        self.setItem(row, self._plus_col(), self._make_readonly_item(""))

    def _populate_sb_rows(self) -> None:
        sb_start = self._sb_start_row()
        for idx, cand in enumerate(self._state.sb_candidates):
            row = sb_start + idx
            count_item = QTableWidgetItem(str(cand.count))
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row, _COL_COUNT, count_item)
            self.setItem(row, _COL_NAME, QTableWidgetItem(cand.name))
            for j, matchup in enumerate(self._state.matchups):
                col = _FIXED_COLS + j
                val = self._state.sb_checks.get(cand.name, {}).get(matchup, 0)
                item = QTableWidgetItem("" if val == 0 else str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.setItem(row, col, item)
            self.setItem(row, self._plus_col(), self._make_readonly_item(""))

    def _populate_add_sb_row(self) -> None:
        row = self._add_sb_row()
        self.setSpan(row, 0, 1, 2)
        label = self._make_readonly_item("＋ Add card…")
        label.setForeground(QColor("#888888"))
        font = self.font()
        font.setItalic(True)
        label.setFont(font)
        self.setItem(row, _COL_COUNT, label)
        for j in range(len(self._state.matchups)):
            self.setItem(row, _FIXED_COLS + j, self._make_readonly_item(""))
        self.setItem(row, self._plus_col(), self._make_readonly_item(""))

    def _populate_coverage_row(self) -> None:
        row = self._coverage_row()
        visible = self._visible_maindeck()
        sb_total = sum(cand.count for cand in self._state.sb_candidates)
        count_item = self._make_readonly_item(str(sb_total))
        count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        count_item.setBackground(QColor("#d0d0d0"))
        self.setItem(row, _COL_COUNT, count_item)
        label = self._make_readonly_item("Coverage ↕")
        label.setBackground(QColor("#d0d0d0"))
        self.setItem(row, _COL_NAME, label)
        for j, matchup in enumerate(self._state.matchups):
            col = _FIXED_COLS + j
            board_out_total = sum(
                self._state.board_outs.get(c.name, {}).get(matchup, 0)
                for c in visible
            )
            sb_in_total = sum(
                self._state.sb_checks.get(cand.name, {}).get(matchup, 0)
                for cand in self._state.sb_candidates
            )
            coverage = sb_in_total - board_out_total
            display = "✓" if coverage == 0 else str(coverage)
            item = self._make_readonly_item(display)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setBackground(_coverage_color(coverage))
            self.setItem(row, col, item)
        self.setItem(row, self._plus_col(), self._make_readonly_item(""))

    # ------------------------------------------------------------------
    # Recompute only the summary rows (faster than full rebuild)
    # ------------------------------------------------------------------

    def _recompute_summaries(self) -> None:
        self._rebuilding = True
        try:
            self._populate_separator_row()
            self._populate_coverage_row()
        finally:
            self._rebuilding = False

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_cell_changed(self, row: int, col: int) -> None:
        if self._rebuilding:
            return

        # Maindeck name/count edit
        if row < self._add_maindeck_row() and col in (_COL_COUNT, _COL_NAME):
            visible = self._visible_maindeck()
            if row >= len(visible):
                return
            card = visible[row]
            item = self.item(row, col)
            text = item.text().strip() if item else ""
            if col == _COL_COUNT:
                try:
                    new_count = max(1, int(text))
                except ValueError:
                    new_count = card.count
                card.count = new_count
                # Re-clamp any board-out values that now exceed the new count
                for matchup, val in self._state.board_outs.get(card.name, {}).items():
                    if val > new_count:
                        self._state.board_outs[card.name][matchup] = new_count
                if item and item.text() != str(new_count):
                    self._rebuilding = True
                    try:
                        item.setText(str(new_count))
                    finally:
                        self._rebuilding = False
                self._recompute_summaries()
            elif col == _COL_NAME:
                old_name = card.name
                card.name = text
                if old_name in self._state.board_outs:
                    self._state.board_outs[text] = self._state.board_outs.pop(old_name)
                if old_name in self._state.hidden_cards:
                    idx = self._state.hidden_cards.index(old_name)
                    self._state.hidden_cards[idx] = text
            return

        # Maindeck board-out cell
        if row < self._add_maindeck_row() and col >= _FIXED_COLS:
            matchup_idx = col - _FIXED_COLS
            if matchup_idx >= len(self._state.matchups):
                return
            matchup = self._state.matchups[matchup_idx]
            visible = self._visible_maindeck()
            card = visible[row]
            item = self.item(row, col)
            text = item.text().strip() if item else "0"
            try:
                val = int(text)
            except ValueError:
                val = 0
            val = max(0, min(val, card.count))
            self._state.board_outs.setdefault(card.name, {})[matchup] = val
            display = "" if val == 0 else str(val)
            if item and item.text() != display:
                self._rebuilding = True
                try:
                    item.setText(display)
                finally:
                    self._rebuilding = False
            self._recompute_summaries()
            return

        # SB candidate rows
        sb_start = self._sb_start_row()
        add_sb_row = self._add_sb_row()
        if sb_start <= row < add_sb_row:
            sb_idx = row - sb_start
            cand = self._state.sb_candidates[sb_idx]
            item = self.item(row, col)
            text = item.text().strip() if item else ""
            if col == _COL_COUNT:
                try:
                    new_count = max(1, int(text))
                except ValueError:
                    new_count = cand.count
                cand.count = new_count
                # Re-clamp any sb_checks values that now exceed the new count
                for matchup, val in self._state.sb_checks.get(cand.name, {}).items():
                    if val > new_count:
                        self._state.sb_checks[cand.name][matchup] = new_count
                if item and item.text() != str(new_count):
                    self._rebuilding = True
                    try:
                        item.setText(str(new_count))
                    finally:
                        self._rebuilding = False
                self._recompute_summaries()
            elif col == _COL_NAME:
                old_name = cand.name
                cand.name = text
                if old_name in self._state.sb_checks:
                    self._state.sb_checks[text] = self._state.sb_checks.pop(old_name)
            elif col >= _FIXED_COLS:
                matchup_idx = col - _FIXED_COLS
                if matchup_idx >= len(self._state.matchups):
                    return
                matchup = self._state.matchups[matchup_idx]
                try:
                    val = int(text)
                except ValueError:
                    val = 0
                val = max(0, min(val, cand.count))
                self._state.sb_checks.setdefault(cand.name, {})[matchup] = val
                display = "" if val == 0 else str(val)
                if item and item.text() != display:
                    self._rebuilding = True
                    try:
                        item.setText(display)
                    finally:
                        self._rebuilding = False
                self._recompute_summaries()

    def _on_selection_changed(self, selected=None, deselected=None) -> None:
        if self._rebuilding:
            return

        # Show/hide zeros in maindeck board-out and SB cells based on selection
        add_md = self._add_maindeck_row()
        sb_start = self._sb_start_row()
        add_sb = self._add_sb_row()
        plus_col = self._plus_col()
        visible = self._visible_maindeck()

        def _set_zero_display(indexes, show: bool) -> None:
            for idx in indexes:
                r, c = idx.row(), idx.column()
                if _FIXED_COLS <= c < plus_col:
                    mi_idx = c - _FIXED_COLS
                    if mi_idx >= len(self._state.matchups):
                        continue
                    mi = self._state.matchups[mi_idx]
                    if r < add_md:
                        if r >= len(visible):
                            continue
                        val = self._state.board_outs.get(visible[r].name, {}).get(mi, 0)
                    elif sb_start <= r < add_sb:
                        sb_idx = r - sb_start
                        cand = self._state.sb_candidates[sb_idx]
                        val = self._state.sb_checks.get(cand.name, {}).get(mi, 0)
                    else:
                        continue
                    if val != 0:
                        continue
                    item = self.item(r, c)
                    if item:
                        self._rebuilding = True
                        try:
                            item.setText("0" if show else "")
                        finally:
                            self._rebuilding = False

        if deselected is not None:
            _set_zero_display(deselected.indexes(), show=False)
        if selected is not None:
            _set_zero_display(selected.indexes(), show=True)

        # Clear current highlights
        for sb_idx in self._highlighted_sb_indices:
            for col in (_COL_COUNT, _COL_NAME):
                item = self.item(sb_start + sb_idx, col)
                if item:
                    item.setBackground(QBrush())
        self._highlighted_sb_indices.clear()

        # Collect selected matchup columns that are in the coverage row
        coverage_row = self._coverage_row()
        selected_matchups = [
            self._state.matchups[idx.column() - _FIXED_COLS]
            for idx in self.selectionModel().selectedIndexes()
            if idx.row() == coverage_row
            and _FIXED_COLS <= idx.column() < self._plus_col()
        ]

        if len(selected_matchups) < 2:
            return

        # Count matchups with a non-zero sb_in per sb candidate
        counts = [
            sum(
                1 for m in selected_matchups
                if self._state.sb_checks.get(cand.name, {}).get(m, 0)
            )
            for cand in self._state.sb_candidates
        ]

        if not counts:
            return
        max_count = max(counts)
        if max_count == 0:
            return

        highlight = QColor("#ffe066")
        for sb_idx, count in enumerate(counts):
            if count == max_count:
                for col in (_COL_COUNT, _COL_NAME):
                    item = self.item(sb_start + sb_idx, col)
                    if item:
                        item.setBackground(highlight)
                self._highlighted_sb_indices.add(sb_idx)

    def _on_cell_clicked(self, row: int, col: int) -> None:
        if row == self._add_maindeck_row():
            self.add_maindeck_requested.emit()
        elif row == self._add_sb_row():
            self.add_sb_requested.emit()
        elif row == self._coverage_row() and col == _COL_NAME:
            self.sort_matchups_by_coverage()

    def _on_header_clicked(self, logical_index: int) -> None:
        if logical_index == self._plus_col():
            self.add_matchup_requested.emit()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        QTimer.singleShot(0, self._fix_scrollbar)

    def _fix_scrollbar(self) -> None:
        hh = self.horizontalHeader()
        if not hh.isVisible():
            return
        bar = self.horizontalScrollBar()
        bar.blockSignals(True)
        step = bar.singleStep() * (hh.height() / max(1, hh.defaultSectionSize()))
        bar.setMaximum(bar.maximum() + int(step))
        bar.blockSignals(False)

    def _show_context_menu(self, pos) -> None:
        clicked_index = self.indexAt(pos)
        if not clicked_index.isValid():
            return
        clicked_row = clicked_index.row()

        selected_rows = {idx.row() for idx in self.selectionModel().selectedIndexes()}
        selected_rows.add(clicked_row)

        add_md_row = self._add_maindeck_row()
        sb_start = self._sb_start_row()
        add_sb = self._add_sb_row()

        maindeck_rows = sorted(r for r in selected_rows if 0 <= r < add_md_row)
        sb_rows = sorted(r for r in selected_rows if sb_start <= r < add_sb)

        if not maindeck_rows and not sb_rows:
            return

        menu = QMenu(self)

        if maindeck_rows:
            visible = self._visible_maindeck()
            names = [visible[r].name for r in maindeck_rows if r < len(visible)]
            label = "Hide selected row" if len(names) == 1 else f"Hide {len(names)} selected rows"
            act = QAction(label, self)
            act.triggered.connect(lambda checked=False, ns=names: [self.hide_maindeck_card(n) for n in ns])
            menu.addAction(act)
            del_label = "Delete selected row" if len(names) == 1 else f"Delete {len(names)} selected rows"
            del_act = QAction(del_label, self)
            del_act.triggered.connect(lambda checked=False, ns=names: self.delete_maindeck_cards(ns))
            menu.addAction(del_act)

        if sb_rows:
            label = "Remove selected candidate" if len(sb_rows) == 1 else f"Remove {len(sb_rows)} selected candidates"
            act = QAction(label, self)
            rows_desc = sorted(sb_rows, reverse=True)
            act.triggered.connect(lambda checked=False, rs=rows_desc: [self.remove_sb_candidate(r) for r in rs])
            menu.addAction(act)

        if maindeck_rows or sb_rows:
            menu.addSeparator()
            act = QAction("Swap one card", self)
            act.triggered.connect(lambda checked=False: self._swap_cards(1))
            menu.addAction(act)
            act = QAction("Swap all cards", self)
            act.triggered.connect(lambda checked=False: self._swap_cards(None))
            menu.addAction(act)

        menu.exec(self.viewport().mapToGlobal(pos))

    def _move_maindeck_to_sb(self, card_name: str, n: int) -> None:
        state = self._state

        cand = next((c for c in state.sb_candidates if c.name == card_name), None)
        if cand is None:
            state.sb_candidates.append(SBCandidate(name=card_name, count=0))
            state.sb_checks[card_name] = {m: 0 for m in state.matchups}
            cand = state.sb_candidates[-1]
        cand.count += n
        for m in state.matchups:
            board_out = state.board_outs.get(card_name, {}).get(m, 0)
            state.sb_checks[card_name][m] = (
                state.sb_checks[card_name].get(m, 0) + max(0, n - board_out)
            )

        md_card = next((c for c in state.maindeck if c.name == card_name), None)
        if md_card is None:
            return
        md_card.count -= n
        if md_card.count <= 0:
            state.maindeck = [c for c in state.maindeck if c.name != card_name]
            state.board_outs.pop(card_name, None)
            if card_name in state.hidden_cards:
                state.hidden_cards.remove(card_name)
        else:
            for m in state.matchups:
                old = state.board_outs.get(card_name, {}).get(m, 0)
                state.board_outs.setdefault(card_name, {})[m] = max(0, old - n)

    def _move_sb_to_maindeck(self, card_name: str, n: int) -> None:
        state = self._state

        md_card = next((c for c in state.maindeck if c.name == card_name), None)
        if md_card is None:
            state.maindeck.append(Card(name=card_name, count=0))
            state.board_outs[card_name] = {m: 0 for m in state.matchups}
            md_card = state.maindeck[-1]
        md_card.count += n
        for m in state.matchups:
            sb_in = state.sb_checks.get(card_name, {}).get(m, 0)
            to_board_out = max(0, n - sb_in)
            if to_board_out > 0:
                state.board_outs.setdefault(card_name, {})[m] = (
                    state.board_outs.get(card_name, {}).get(m, 0) + to_board_out
                )

        cand = next((c for c in state.sb_candidates if c.name == card_name), None)
        if cand is None:
            return
        cand.count -= n
        if cand.count <= 0:
            state.sb_candidates = [c for c in state.sb_candidates if c.name != card_name]
            state.sb_checks.pop(card_name, None)
        else:
            for m in state.matchups:
                old = state.sb_checks.get(card_name, {}).get(m, 0)
                state.sb_checks[card_name][m] = max(0, old - n)

    def _swap_cards(self, n_per_row: int | None) -> None:
        selected_rows = {idx.row() for idx in self.selectionModel().selectedIndexes()}
        add_md_row = self._add_maindeck_row()
        sb_start   = self._sb_start_row()
        add_sb     = self._add_sb_row()
        visible    = self._visible_maindeck()

        md_ops: list[tuple[str, int]] = []
        for r in sorted(r for r in selected_rows if 0 <= r < add_md_row):
            if r < len(visible):
                card = visible[r]
                n = min(n_per_row, card.count) if n_per_row is not None else card.count
                if n > 0:
                    md_ops.append((card.name, n))

        sb_ops: list[tuple[str, int]] = []
        for r in sorted(r for r in selected_rows if sb_start <= r < add_sb):
            sb_idx = r - sb_start
            if sb_idx < len(self._state.sb_candidates):
                cand = self._state.sb_candidates[sb_idx]
                n = min(n_per_row, cand.count) if n_per_row is not None else cand.count
                if n > 0:
                    sb_ops.append((cand.name, n))

        for name, n in md_ops:
            self._move_maindeck_to_sb(name, n)
        for name, n in sb_ops:
            self._move_sb_to_maindeck(name, n)

        self._rebuild()

    def _show_header_context_menu(self, pos) -> None:
        logical_index = self.horizontalHeader().logicalIndexAt(pos)
        if _FIXED_COLS <= logical_index < _FIXED_COLS + len(self._state.matchups):
            matchup_name = self._state.matchups[logical_index - _FIXED_COLS]
            menu = QMenu(self)
            act = QAction(f"Remove matchup '{matchup_name}'", self)
            act.triggered.connect(lambda checked=False, mn=matchup_name: self.remove_matchup(mn))
            menu.addAction(act)
            menu.exec(self.horizontalHeader().mapToGlobal(pos))
