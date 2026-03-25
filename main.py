import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QFileDialog, QScrollArea, QLineEdit,
                             QComboBox, QMessageBox)
from PyQt6.QtGui import QImage, QPixmap, QCursor, QIcon
from PyQt6.QtCore import Qt, QTimer
import settings_manager
from reader_engine import PDFEngine


class PDFReader(QMainWindow):
    def __init__(self):
        super().__init__()
        self.load_stylesheet()
        self.setWindowTitle("Super PDF Reader")
        self.resize(1000, 800)

        self.engine = PDFEngine()
        self.current_page = 0
        self.total_pages = 0
        self.zoom = 1.0
        self.active_tool = "None"
        self.start_pos = None
        self.pan_origin = None
        self.current_path = []

        # 5-Second Auto-Save Timer
        self.save_timer = QTimer()
        self.save_timer.setInterval(5000)
        self.save_timer.timeout.connect(self.auto_save_position)

        self.init_ui()

    def load_stylesheet(self):
        """Reads the external QSS file relative to this script's location."""
        qss_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "style.qss")
        try:
            with open(qss_path, "r") as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            print(f"Style file not found at {qss_path}, using default look.")

    def upload_image(self):
        img_path, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "", "Images (*.png *.jpg *.jpeg)"
        )
        if img_path:
            self.engine.insert_custom_image(self.current_page, img_path, self.zoom)
            self.render_page()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # --- Toolbar ---
        toolbar_layout = QHBoxLayout()

        self.btn_open = QPushButton("Open PDF")
        self.btn_open.setIcon(QIcon("assets/icon_open.svg"))
        self.btn_open.clicked.connect(self.open_file)

        self.btn_save = QPushButton("Save PDF")
        self.btn_save.setIcon(QIcon("assets/icon_save.svg"))
        self.btn_save.clicked.connect(self.save_pdf)

        self.btn_upload_img = QPushButton("Insert Image")
        self.btn_upload_img.setIcon(QIcon("assets/icon_insert_image.svg"))
        self.btn_upload_img.clicked.connect(self.upload_image)

        self.btn_prev = QPushButton()
        self.btn_prev.setIcon(QIcon("assets/icon_prev.svg"))
        self.btn_prev.clicked.connect(lambda: self.change_page(-1))

        self.page_input = QLineEdit("1")
        self.page_input.setFixedWidth(40)
        self.page_input.returnPressed.connect(self.jump_to_page)

        self.page_count_label = QLabel("/ 0")

        self.btn_next = QPushButton()
        self.btn_next.setIcon(QIcon("assets/icon_next.svg"))
        self.btn_next.clicked.connect(lambda: self.change_page(1))

        self.btn_zoom_out = QPushButton()
        self.btn_zoom_out.setFixedWidth(28)
        self.btn_zoom_out.setIcon(QIcon("assets/icon_zoom_out.svg"))
        self.btn_zoom_out.clicked.connect(lambda: self.step_zoom(-0.1))

        self.zoom_input = QLineEdit("1.0")
        self.zoom_input.setFixedWidth(45)
        self.zoom_input.returnPressed.connect(self.change_zoom)

        self.btn_zoom_in = QPushButton()
        self.btn_zoom_in.setFixedWidth(28)
        self.btn_zoom_in.setIcon(QIcon("assets/icon_zoom_in.svg"))
        self.btn_zoom_in.clicked.connect(lambda: self.step_zoom(0.1))

        self.tool_selector = QComboBox()
        self.tool_selector.addItem(QIcon("assets/icon_none.svg"), "None")
        self.tool_selector.addItem(QIcon("assets/icon_pen.svg"), "Pen")
        self.tool_selector.addItem(QIcon("assets/icon_line.svg"), "Line")
        self.tool_selector.addItem(QIcon("assets/icon_rectangle.svg"), "Rectangle")
        self.tool_selector.addItem(QIcon("assets/icon_circle.svg"), "Circle")
        self.tool_selector.addItem(QIcon("assets/icon_eraser.svg"), "Eraser")
        self.tool_selector.currentTextChanged.connect(self.change_tool)

        toolbar_layout.addWidget(self.btn_open)
        toolbar_layout.addWidget(self.btn_save)
        toolbar_layout.addWidget(self.btn_upload_img)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(QLabel("Tool:"))
        toolbar_layout.addWidget(self.tool_selector)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.btn_prev)
        toolbar_layout.addWidget(self.page_input)
        toolbar_layout.addWidget(self.page_count_label)
        toolbar_layout.addWidget(self.btn_next)
        toolbar_layout.addWidget(QLabel("Zoom:"))
        toolbar_layout.addWidget(self.btn_zoom_out)
        toolbar_layout.addWidget(self.zoom_input)
        toolbar_layout.addWidget(self.btn_zoom_in)

        layout.addLayout(toolbar_layout)

        # --- Canvas Area ---
        self.scroll_area = QScrollArea()

        self.scroll_area.setMouseTracking(True)

        self.canvas = QLabel("Open a PDF to begin.")
        self.canvas.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.canvas.setMouseTracking(True)

        self.scroll_area.setWidget(self.canvas)
        self.scroll_area.setWidgetResizable(True)
        layout.addWidget(self.scroll_area)

        self.canvas.mousePressEvent = self.mouse_press
        self.canvas.mouseMoveEvent = self.mouse_move
        self.canvas.mouseReleaseEvent = self.mouse_release

        self.change_tool(self.tool_selector.currentText())

    def open_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if filepath:
            self.total_pages = self.engine.load_pdf(filepath)

            saved_data = settings_manager.get_position(filepath)
            self.current_page = saved_data["page"]
            self.zoom = saved_data["zoom"]

            self.zoom_input.setText(f"{self.zoom:.1f}")
            self.page_count_label.setText(f"/ {self.total_pages}")
            self.render_page()

    def render_page(self):
        if not self.engine.doc:
            return
        self.page_input.setText(str(self.current_page + 1))

        img_bytes, width, height = self.engine.get_page_image(self.current_page, self.zoom)
        if img_bytes:
            q_img = QImage.fromData(img_bytes)
            pixmap = QPixmap.fromImage(q_img)
            self.canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.canvas.setPixmap(pixmap)
            self.canvas.resize(width, height)
            #self.canvas.setPixmap(pixmap)
            #self.canvas.setFixedSize(width, height)

        self.save_timer.start()

    def change_page(self, delta):
        new_page = self.current_page + delta
        if 0 <= new_page < self.total_pages:
            self.current_page = new_page
            self.render_page()

    def jump_to_page(self):
        try:
            page = int(self.page_input.text()) - 1
            if 0 <= page < self.total_pages:
                self.current_page = page
                self.render_page()
        except ValueError:
            pass

    def change_zoom(self):
        try:
            new_zoom = float(self.zoom_input.text())
            self.zoom = max(0.1, min(new_zoom, 5.0))
            self.zoom_input.setText(f"{self.zoom:.1f}")
            self.render_page()
        except ValueError:
            pass

    def step_zoom(self, delta):
        self.zoom = round(max(0.1, min(self.zoom + delta, 5.0)), 1)
        self.zoom_input.setText(f"{self.zoom:.1f}")
        self.render_page()

    def change_tool(self, tool):
        self.active_tool = tool
        if tool == "None":
            self.canvas.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        elif tool == "Eraser":
            self.canvas.setCursor(QCursor(Qt.CursorShape.ForbiddenCursor))
        else:
            self.canvas.setCursor(QCursor(Qt.CursorShape.CrossCursor))

    # --- Drawing Logic ---
    def mouse_press(self, event):
        if self.active_tool == "None":
            self.pan_origin = event.position()
            self.canvas.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            return
        if self.active_tool != "None":
            self.start_pos = (float(event.position().x()), float(event.position().y()))

            if self.active_tool == "Pen":
                self.current_path = [self.start_pos]
            elif self.active_tool == "Eraser":
                if self.engine.erase_annotation(self.current_page, self.start_pos, self.zoom):
                    self.render_page()

    def mouse_move(self, event):
        if self.active_tool == "None" and self.pan_origin:
            delta = event.position() - self.pan_origin
            self.pan_origin = event.position()
            self.scroll_area.horizontalScrollBar().setValue(
                self.scroll_area.horizontalScrollBar().value() - int(delta.x())
            )
            self.scroll_area.verticalScrollBar().setValue(
                self.scroll_area.verticalScrollBar().value() - int(delta.y())
            )
            return
        if self.active_tool == "Pen" and self.start_pos:
            pos = (float(event.position().x()), float(event.position().y()))
            self.current_path.append(pos)

    def mouse_release(self, event):
        if self.active_tool == "None" and self.pan_origin:
            self.pan_origin = None
            self.canvas.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
            return
        if self.active_tool == "Pen" and self.start_pos:
            if len(self.current_path) >= 2:
                self.engine.add_pen_stroke(self.current_page, self.current_path, self.zoom)
                self.render_page()
            self.start_pos = None
            self.current_path = []

        elif self.active_tool in ["Line", "Rectangle", "Circle"] and self.start_pos:
            end_pos = (float(event.position().x()), float(event.position().y()))
            if end_pos != self.start_pos:
                self.engine.add_shape(
                    self.current_page, self.active_tool, self.start_pos, end_pos, self.zoom
                )
                self.render_page()
            self.start_pos = None

    # --- Saving Logic ---
    def auto_save_position(self):
        if self.engine.filepath:
            settings_manager.save_position(self.engine.filepath, self.current_page, self.zoom)

    def save_pdf(self):
        self.engine.save_document()
        self.auto_save_position()

    def closeEvent(self, event):
        if self.engine.doc:
            reply = QMessageBox.question(
                self, 'Exit',
                "Do you want to save your drawings before quitting?",
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Save:
                self.save_pdf()
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                self.auto_save_position()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = PDFReader()
    window.show()
    sys.exit(app.exec())
