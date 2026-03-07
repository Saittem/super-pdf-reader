import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QFileDialog, QScrollArea, QLineEdit, 
                             QComboBox, QMessageBox)
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import Qt, QTimer
import settings_manager
from reader_engine import PDFEngine

class PDFReader(QMainWindow):
    def __init__(self):
        super().__init__()
        self.load_stylesheet()
        self.setWindowTitle("Pro PDF Reader")
        self.resize(1000, 800)

        self.engine = PDFEngine()
        self.current_page = 0
        self.total_pages = 0
        self.zoom = 1.0
        self.active_tool = "Pan"
        self.start_pos = None

        # 5-Second Auto-Save Timer
        self.save_timer = QTimer()
        self.save_timer.setInterval(5000)
        self.save_timer.timeout.connect(self.auto_save_position)

        self.init_ui()

    def load_stylesheet(self):
        """Reads the external CSS file and applies it to the app."""
        try:
            with open("style.qss", "r") as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            print("Style file not found, using default look.")

    def upload_image(self):
        """Allows user to pick an image and 'stamp' it on the current page."""
        img_path, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.png *.jpg *.jpeg)")
        if img_path:
            # We'll tell the engine to insert this image at the center of the current view
            # or you can set a 'Stamp' mode where the next click places it.
            self.engine.insert_custom_image(self.current_page, img_path, self.zoom)
            self.render_page()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # --- Toolbar ---
        toolbar_layout = QHBoxLayout()
        
        self.btn_open = QPushButton("Open PDF")
        self.btn_open.clicked.connect(self.open_file)
        
        self.btn_save = QPushButton("Save PDF")
        self.btn_save.clicked.connect(self.save_pdf)

        self.btn_prev = QPushButton("<")
        self.btn_prev.clicked.connect(lambda: self.change_page(-1))
        
        self.page_input = QLineEdit("0")
        self.page_input.setFixedWidth(40)
        self.page_input.returnPressed.connect(self.jump_to_page)
        
        self.btn_next = QPushButton(">")
        self.btn_next.clicked.connect(lambda: self.change_page(1))

        self.zoom_input = QLineEdit("1.0")
        self.zoom_input.setFixedWidth(40)
        self.zoom_input.returnPressed.connect(self.change_zoom)

        self.tool_selector = QComboBox()
        self.tool_selector.addItems(["Pan", "Line", "Rectangle", "Circle", "Eraser"])
        self.tool_selector.currentTextChanged.connect(self.change_tool)

        toolbar_layout.addWidget(self.btn_open)
        toolbar_layout.addWidget(self.btn_save)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(QLabel("Tool:"))
        toolbar_layout.addWidget(self.tool_selector)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.btn_prev)
        toolbar_layout.addWidget(self.page_input)
        toolbar_layout.addWidget(self.btn_next)
        toolbar_layout.addWidget(QLabel("Zoom:"))
        toolbar_layout.addWidget(self.zoom_input)

        layout.addLayout(toolbar_layout)

        # --- Canvas Area ---
        self.scroll_area = QScrollArea()
        self.canvas = QLabel("Open a PDF to begin.")
        self.canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.canvas)
        self.scroll_area.setWidgetResizable(True)
        layout.addWidget(self.scroll_area)

        # Connect mouse events for drawing
        self.canvas.mousePressEvent = self.mouse_press
        self.canvas.mouseReleaseEvent = self.mouse_release

    def open_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if filepath:
            self.total_pages = self.engine.load_pdf(filepath)
            
            # Load saved position
            saved_data = settings_manager.get_position(filepath)
            self.current_page = saved_data["page"]
            self.zoom = saved_data["zoom"]
            
            self.zoom_input.setText(str(self.zoom))
            self.render_page()

    def render_page(self):
        if not self.engine.doc: return
        self.page_input.setText(str(self.current_page + 1))
        
        img_bytes, width, height = self.engine.get_page_image(self.current_page, self.zoom)
        if img_bytes:
            q_img = QImage.fromData(img_bytes)
            pixmap = QPixmap.fromImage(q_img)
            self.canvas.setPixmap(pixmap)
            self.canvas.resize(width, height)
        
        # Restart the 5-second inactivity timer every time we move
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
            self.zoom = float(self.zoom_input.text())
            self.render_page()
        except ValueError:
            pass

    def change_tool(self, tool):
        self.active_tool = tool

    # --- Drawing Logic ---
    def mouse_press(self, event):
        if self.active_tool != "Pan":
            self.start_pos = (event.position().x(), event.position().y())

            if self.active_tool == "Eraser":
                if self.engine.erase_annotation(self.current_page, self.start_pos, self.zoom):
                    self.render_page() # Re-render to show erased shape

    def mouse_release(self, event):
        if self.active_tool in ["Line", "Rectangle", "Circle"] and self.start_pos:
            end_pos = (event.position().x(), event.position().y())
            self.engine.add_shape(self.current_page, self.active_tool, self.start_pos, end_pos, self.zoom)
            self.start_pos = None
            self.render_page() # Re-render to show new shape

    # --- Saving Logic ---
    def auto_save_position(self):
        if self.engine.filepath:
            settings_manager.save_position(self.engine.filepath, self.current_page, self.zoom)

    def save_pdf(self):
        self.engine.save_document()
        self.auto_save_position()

    def closeEvent(self, event):
        if self.engine.doc:
            reply = QMessageBox.question(self, 'Exit',
                                         "Do you want to save your drawings before quitting?",
                                         QMessageBox.StandardButton.Save | 
                                         QMessageBox.StandardButton.Discard | 
                                         QMessageBox.StandardButton.Cancel)

            if reply == QMessageBox.StandardButton.Save:
                self.save_pdf()
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                self.auto_save_position() # Still save reading position!
                event.accept()
            else:
                event.ignore() # Cancel
        else:
            event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    # If you saved ui_styles.py, uncomment the next two lines:
    # import ui_styles
    # app.setStyleSheet(ui_styles.get_stylesheet())
    
    window = PDFReader()
    window.show()
    sys.exit(app.exec())