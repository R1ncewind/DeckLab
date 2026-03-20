from PyQt6.QtGui import QImage, QPainter, QColor, QFont, QFontMetrics, QPen
from PyQt6.QtCore import Qt, QRect, QSize

from models.mapping import MappingState

# Layout constants
ROW_H      = 28   # body row height (px)
COL_W      = 32   # matchup column width (px)
PAD        = 12   # outer padding (px)
SEP_H      = 4    # separator line height (px)
HEADER_PAD = 8    # padding inside rotated header

# Print target: 300 DPI × 5" × 7"  (double a Magic card, folds twice to card size)
PRINT_DPI    = 300
MAX_W_INCHES = 5.0
MAX_H_INCHES = 7.0
MAX_W_PX = int(MAX_W_INCHES * PRINT_DPI)   # 1500
MAX_H_PX = int(MAX_H_INCHES * PRINT_DPI)   # 2100
DOTS_PER_METER = int(PRINT_DPI / 0.0254)   # ≈ 11811

# Colors
COLOR_BAND_A = QColor("#ffffff")
COLOR_BAND_B = QColor("#ececec")
COLOR_GRID   = QColor("#cccccc")
COLOR_SEP      = QColor("#666666")
COLOR_BOARD_OUT = QColor("#cce5ff")   # light blue board-out summary row
COLOR_TEXT   = QColor("#000000")


def render_guide_image(state: MappingState, version_label: str = "") -> QImage | None:
    if not state.matchups:
        return None

    md_rows = [c for c in state.maindeck
               if any(state.board_outs.get(c.name, {}).get(m, 0) != 0
                      for m in state.matchups)]

    sb_rows = [c for c in state.sb_candidates
               if c.count > 0
               and any(state.sb_checks.get(c.name, {}).get(m, 0)
                       for m in state.matchups)]

    if not md_rows and not sb_rows:
        return None

    font = QFont()
    fm = QFontMetrics(font)

    all_names = [c.name for c in md_rows] + [c.name for c in sb_rows]
    name_col_w = max((fm.horizontalAdvance(n) for n in all_names), default=0) + 20
    if state.name:
        name_col_w = max(name_col_w, fm.horizontalAdvance(state.name) + 20)
    if version_label:
        name_col_w = max(name_col_w, fm.horizontalAdvance(f"v{version_label}") + 20)
    name_col_w = max(name_col_w, 120)

    header_row_h = max((fm.horizontalAdvance(m) for m in state.matchups), default=0) + HEADER_PAD * 2
    header_row_h = max(header_row_h, 50)

    n_md   = len(md_rows)
    n_sb   = len(sb_rows)
    n_cols = len(state.matchups)
    has_sep = n_md > 0 and n_sb > 0

    total_w = PAD + name_col_w + COL_W * n_cols + PAD
    total_h = (PAD + header_row_h
               + n_md * ROW_H
               + (ROW_H if has_sep else 0)
               + n_sb * ROW_H
               + PAD)

    img = QImage(total_w, total_h, QImage.Format.Format_RGB32)
    img.fill(QColor("#ffffff"))

    painter = QPainter(img)
    painter.setFont(font)

    x_origin = PAD + name_col_w  # left edge of first matchup column

    # 1. Column bands
    for j in range(n_cols):
        color = COLOR_BAND_A if j % 2 == 0 else COLOR_BAND_B
        painter.fillRect(x_origin + j * COL_W, 0, COL_W, total_h, color)

    # 2. Rotated column headers
    painter.setPen(COLOR_TEXT)
    for j, matchup in enumerate(state.matchups):
        x_center = x_origin + j * COL_W + COL_W // 2
        painter.save()
        painter.translate(x_center, PAD + header_row_h - HEADER_PAD)
        painter.rotate(-90)
        painter.drawText(
            QRect(0, -fm.height(), header_row_h, fm.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            matchup,
        )
        painter.restore()

    # Deck name and version label in header
    line_h = fm.height()
    y_text = PAD
    if state.name:
        painter.drawText(
            QRect(PAD, y_text, name_col_w, line_h),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            state.name,
        )
        y_text += line_h
    if version_label:
        painter.drawText(
            QRect(PAD, y_text, name_col_w, line_h),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"v{version_label}",
        )

    y_body = PAD + header_row_h  # top of first body row

    # 3. Maindeck rows (board-out counts, no sign prefix)
    for i, card in enumerate(md_rows):
        y = y_body + i * ROW_H
        painter.setPen(COLOR_TEXT)
        painter.drawText(
            QRect(PAD, y, name_col_w, ROW_H),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            card.name,
        )
        for j, m in enumerate(state.matchups):
            val = state.board_outs.get(card.name, {}).get(m, 0)
            if val:
                painter.drawText(
                    QRect(x_origin + j * COL_W, y, COL_W, ROW_H),
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                    str(val),
                )

    y_after_md = y_body + n_md * ROW_H

    # 4. Board-out summary row
    y_sep_row = y_after_md
    if has_sep:
        painter.fillRect(PAD, y_sep_row, name_col_w + COL_W * n_cols, ROW_H, COLOR_BOARD_OUT)
        painter.setPen(COLOR_TEXT)
        for j, m in enumerate(state.matchups):
            total = sum(state.board_outs.get(c.name, {}).get(m, 0) for c in state.maindeck)
            if total:
                painter.drawText(
                    QRect(x_origin + j * COL_W, y_sep_row, COL_W, ROW_H),
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                    str(total),
                )

    y_sb = y_after_md + (ROW_H if has_sep else 0)

    # 5. SB rows (bring-in counts, no sign prefix)
    for i, cand in enumerate(sb_rows):
        y = y_sb + i * ROW_H
        painter.setPen(COLOR_TEXT)
        painter.drawText(
            QRect(PAD, y, name_col_w, ROW_H),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            cand.name,
        )
        for j, m in enumerate(state.matchups):
            val = state.sb_checks.get(cand.name, {}).get(m, 0)
            if val:
                painter.drawText(
                    QRect(x_origin + j * COL_W, y, COL_W, ROW_H),
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                    str(val),
                )

    # 6. Grid lines
    painter.setPen(QPen(COLOR_GRID, 1))

    content_right = PAD + name_col_w + COL_W * n_cols

    # Horizontal: below header
    painter.drawLine(PAD, PAD + header_row_h, content_right, PAD + header_row_h)

    # Horizontal: between body rows
    for i in range(1, n_md):
        y_grid = y_body + i * ROW_H
        painter.drawLine(PAD, y_grid, content_right, y_grid)
    for i in range(1, n_sb):
        y_grid = y_sb + i * ROW_H
        painter.drawLine(PAD, y_grid, content_right, y_grid)

    # Horizontal: borders around board-out row
    if has_sep:
        painter.drawLine(PAD, y_after_md,         content_right, y_after_md)
        painter.drawLine(PAD, y_after_md + ROW_H, content_right, y_after_md + ROW_H)

    # Vertical: after name column
    painter.drawLine(PAD + name_col_w, PAD, PAD + name_col_w, total_h - PAD)

    # Vertical: after each matchup column
    for j in range(1, n_cols + 1):
        x_vert = PAD + name_col_w + j * COL_W
        painter.drawLine(x_vert, PAD, x_vert, total_h - PAD)

    painter.end()

    # Scale to fit print target (1500 × 2100 px at 300 DPI = 5" × 7")
    # Try both portrait and landscape orientations; pick whichever wastes less space.
    def scale_factor(img_w, img_h, box_w, box_h) -> float:
        return min(box_w / img_w, box_h / img_h)

    sf_portrait  = scale_factor(total_w, total_h, MAX_W_PX, MAX_H_PX)
    sf_landscape = scale_factor(total_w, total_h, MAX_H_PX, MAX_W_PX)

    if sf_portrait >= sf_landscape:
        target_w = min(total_w, MAX_W_PX)
        target_h = min(total_h, MAX_H_PX)
    else:
        target_w = min(total_w, MAX_H_PX)
        target_h = min(total_h, MAX_W_PX)

    if total_w != target_w or total_h != target_h:
        img = img.scaled(
            QSize(target_w, target_h),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    # Stamp 300 DPI so the printer knows the physical size
    img.setDotsPerMeterX(DOTS_PER_METER)
    img.setDotsPerMeterY(DOTS_PER_METER)

    return img
