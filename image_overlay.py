from PyQt6.QtWidgets import QWidget, QApplication, QPushButton, QHBoxLayout
from PyQt6.QtGui import QPixmap, QPainter, QPen, QBrush, QColor, QCursor
from PyQt6.QtCore import Qt, QRect, QPoint, QSize, pyqtSignal


# Names for each of the 8 resize handles
HANDLES = ["tl", "tm", "tr", "ml", "mr", "bl", "bm", "br"]

# Which cursor to show for each handle
HANDLE_CURSORS = {
    "tl": Qt.CursorShape.SizeFDiagCursor,
    "br": Qt.CursorShape.SizeFDiagCursor,
    "tr": Qt.CursorShape.SizeBDiagCursor,
    "bl": Qt.CursorShape.SizeBDiagCursor,
    "tm": Qt.CursorShape.SizeVerCursor,
    "bm": Qt.CursorShape.SizeVerCursor,
    "ml": Qt.CursorShape.SizeHorCursor,
    "mr": Qt.CursorShape.SizeHorCursor,
}

HANDLE_SIZE = 8      # px — side length of each square handle
MIN_SIZE    = 20     # px — minimum width/height when resizing


class ImageOverlay(QWidget):
    """
    A draggable, resizable image widget that sits on top of the PDF canvas.

    - Drag the body to move.
    - Drag any of the 8 handles to resize.
    - Hold Shift while resizing to lock the aspect ratio.
    - Click ✓ to confirm (bakes into PDF in memory, removes overlay).
    - Click ✗ to discard (removes overlay without touching the PDF).
    """

    # Emitted when the user clicks ✓ — carries (image_path, x, y, w, h) in canvas px
    confirmed = pyqtSignal(str, int, int, int, int)
    # Emitted when the user clicks ✗
    discarded = pyqtSignal(object)   # passes self so the parent can remove it

    def __init__(self, image_path: str, parent: QWidget):
        super().__init__(parent)

        self.image_path  = image_path
        self.pixmap      = QPixmap(image_path)

        # Default size: original image size capped at 200px wide
        w = min(self.pixmap.width(), 200)
        h = int(self.pixmap.height() * w / max(self.pixmap.width(), 1))
        self.resize(w, h)

        # Keep original ratio for Shift-constrained resizing
        self._aspect_ratio = self.pixmap.width() / max(self.pixmap.height(), 1)

        # Drag state
        self._dragging    = False
        self._drag_offset = QPoint()

        # Resize state
        self._resizing         = None
        self._resize_origin    = QPoint()
        self._resize_start_geo = QRect()

        self._build_buttons()
        self.setMouseTracking(True)
        self.raise_()

    def _build_buttons(self):
        """Create the ✓ / ✗ confirm-discard buttons pinned to the top-right."""
        self._btn_confirm = QPushButton("✓", self)
        self._btn_discard = QPushButton("✗", self)
        for btn in (self._btn_confirm, self._btn_discard):
            btn.setFixedSize(22, 22)
            btn.setStyleSheet(
                "QPushButton { border-radius: 11px; font-size: 13px; font-weight: bold; }"
            )
        self._btn_confirm.setStyleSheet(
            self._btn_confirm.styleSheet() +
            "QPushButton { background: #27ae60; color: white; }"
            "QPushButton:hover { background: #2ecc71; }"
        )
        self._btn_discard.setStyleSheet(
            self._btn_discard.styleSheet() +
            "QPushButton { background: #c0392b; color: white; }"
            "QPushButton:hover { background: #e74c3c; }"
        )
        self._btn_confirm.clicked.connect(self._on_confirm)
        self._btn_discard.clicked.connect(self._on_discard)
        self._reposition_buttons()

    def _reposition_buttons(self):
        """Keep buttons pinned to the top-right corner of the overlay."""
        margin = 4
        self._btn_discard.move(self.width() - 22 - margin, margin)
        self._btn_confirm.move(self.width() - 22 * 2 - margin * 2, margin)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition_buttons()

    def _on_confirm(self):
        self.confirmed.emit(self.image_path, self.x(), self.y(), self.width(), self.height())
        self.deleteLater()

    def _on_discard(self):
        self.discarded.emit(self)
        self.deleteLater()

    # ------------------------------------------------------------------ #
    #  Handle geometry helpers
    # ------------------------------------------------------------------ #

    def _handle_rects(self) -> dict:
        """Return a {name: QRect} dict for the 8 resize handles."""
        w, h = self.width(), self.height()
        s = HANDLE_SIZE
        hs = s // 2

        positions = {
            "tl": QPoint(0,        0),
            "tm": QPoint(w // 2,   0),
            "tr": QPoint(w,        0),
            "ml": QPoint(0,        h // 2),
            "mr": QPoint(w,        h // 2),
            "bl": QPoint(0,        h),
            "bm": QPoint(w // 2,   h),
            "br": QPoint(w,        h),
        }
        return {
            name: QRect(pt.x() - hs, pt.y() - hs, s, s)
            for name, pt in positions.items()
        }

    def _handle_at(self, pos: QPoint):
        """Return the handle name under `pos`, or None."""
        for name, rect in self._handle_rects().items():
            if rect.contains(pos):
                return name
        return None

    # ------------------------------------------------------------------ #
    #  Mouse events
    # ------------------------------------------------------------------ #

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return

        handle = self._handle_at(event.position().toPoint())
        if handle:
            self._resizing         = handle
            self._resize_origin    = event.globalPosition().toPoint()
            self._resize_start_geo = self.geometry()
        else:
            self._dragging    = True
            self._drag_offset = event.position().toPoint()
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()

        # --- Resize ---
        if self._resizing:
            self._do_resize(event)
            return

        # --- Drag ---
        if self._dragging:
            new_pos = self.mapToParent(pos) - self._drag_offset
            self.move(new_pos)
            return

        # --- Hover: update cursor ---
        handle = self._handle_at(pos)
        if handle:
            self.setCursor(QCursor(HANDLE_CURSORS[handle]))
        else:
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))

    def mouseReleaseEvent(self, event):
        self._dragging  = False
        self._resizing  = None
        # Revert to open-hand unless hovering a handle
        handle = self._handle_at(event.position().toPoint())
        if handle:
            self.setCursor(QCursor(HANDLE_CURSORS[handle]))
        else:
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))

    # ------------------------------------------------------------------ #
    #  Resize logic
    # ------------------------------------------------------------------ #

    def _do_resize(self, event):
        shift_held = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        delta      = event.globalPosition().toPoint() - self._resize_origin
        geo        = QRect(self._resize_start_geo)  # copy
        h          = self._resizing

        dx, dy = delta.x(), delta.y()

        # Apply deltas to the correct edges
        if "l" in h:
            geo.setLeft(geo.left() + dx)
        if "r" in h:
            geo.setRight(geo.right() + dx)
        if "t" in h:
            geo.setTop(geo.top() + dy)
        if "b" in h:
            geo.setBottom(geo.bottom() + dy)

        # Enforce minimum size
        if geo.width() < MIN_SIZE:
            if "l" in h:
                geo.setLeft(geo.right() - MIN_SIZE)
            else:
                geo.setRight(geo.left() + MIN_SIZE)
        if geo.height() < MIN_SIZE:
            if "t" in h:
                geo.setTop(geo.bottom() - MIN_SIZE)
            else:
                geo.setBottom(geo.top() + MIN_SIZE)

        # Shift = lock aspect ratio
        if shift_held:
            new_w = geo.width()
            new_h = geo.height()
            # Decide which dimension to follow based on which edges are moving
            if h in ("tm", "bm"):
                # Only vertical handle — derive width from height
                new_w = int(new_h * self._aspect_ratio)
            elif h in ("ml", "mr"):
                # Only horizontal handle — derive height from width
                new_h = int(new_w / self._aspect_ratio)
            else:
                # Corner — follow whichever dimension changed more
                if abs(dx) >= abs(dy):
                    new_h = int(new_w / self._aspect_ratio)
                else:
                    new_w = int(new_h * self._aspect_ratio)

            # Reapply constrained size, anchored to the stationary corner
            if "l" in h:
                geo.setLeft(geo.right() - new_w)
            else:
                geo.setRight(geo.left() + new_w)
            if "t" in h:
                geo.setTop(geo.bottom() - new_h)
            else:
                geo.setBottom(geo.top() + new_h)

        self.setGeometry(geo)
        self.update()

    # ------------------------------------------------------------------ #
    #  Painting
    # ------------------------------------------------------------------ #

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # Draw the image scaled to the widget size
        painter.drawPixmap(self.rect(), self.pixmap)

        # Blue selection border
        pen = QPen(QColor("#0078d4"))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self.rect().adjusted(1, 1, -1, -1))

        # Draw the 8 white handles with blue border
        handle_pen   = QPen(QColor("#0078d4"))
        handle_brush = QBrush(QColor("#ffffff"))
        handle_pen.setWidth(1)
        painter.setPen(handle_pen)
        painter.setBrush(handle_brush)
        for rect in self._handle_rects().values():
            painter.drawRect(rect)

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    def pdf_rect(self, zoom: float):
        """
        Returns the widget's current geometry converted to PDF coordinate space.
        Use this when baking the image into the PDF on save.

        Returns a plain tuple (x1, y1, x2, y2) in PDF points.

        NOTE: We use x/y + width/height instead of QRect.right()/bottom() because
        Qt's inclusive rect means right() = x + width - 1, which silently shrinks
        the image by 1px per edge and produces wrong dimensions in PDF space.
        """
        x = self.x()
        y = self.y()
        w = self.width()
        h = self.height()
        return (
            x       / zoom,
            y       / zoom,
            (x + w) / zoom,
            (y + h) / zoom,
        )
