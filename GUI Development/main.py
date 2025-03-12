import sys
from PyQt5.QtWidgets import QApplication, QLabel, QDialog, QPushButton, QComboBox, QWidget
from PyQt5.QtCore import Qt, QUrl, QPoint
from PyQt5.QtGui import QDesktopServices, QIcon
from PyQt5 import uic

import backend_design as bed # Import backend functions
import backend_eeg as beeg
import resources_rc  # Ensure this is generated from .qrc file


class MainApp(QDialog):
    def __init__(self):
        super().__init__()

        # Load UI file
        uic.loadUi("GUI Design.ui", self)

        # REMOVE Default Window Border & Title Bar
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Set Window Title & Taskbar Icon
        self.setWindowTitle("MIND EEG Extraction Interface")
        self.setWindowIcon(QIcon(":/images/TaskbarIcon.png"))  # Ensure this is in your .qrc file

        # Find QLabel using the correct object name "logo"
        self.logo_label = self.findChild(QLabel, "logo")
        if self.logo_label:
            self.logo_label.setCursor(Qt.PointingHandCursor)
            self.logo_label.mousePressEvent = bed.open_link  # Use function from backend.py

        # === ️ Taskbar Buttons ===
        self.minimize_button = self.findChild(QPushButton, "minimize_button")
        self.close_button = self.findChild(QPushButton, "close_button")
        self.fullscreen_button = self.findChild(QPushButton, "fullscreen_button")
        self.taskbar = self.findChild(QWidget, "taskbar")  # Taskbar for dragging

        self.was_fullscreen = False  # Track if window was fullscreen

        if self.minimize_button:
            self.minimize_button.clicked.connect(lambda: bed.minimize_window(self))

        if self.close_button:
            self.close_button.clicked.connect(lambda: bed.close_window(self))

        if self.fullscreen_button:
            self.fullscreen_button.clicked.connect(lambda: bed.toggle_fullscreen(self))

        # === Initialize Dropdown Menu ===
        self.menu_options = self.findChild(QComboBox, "MenuOptions")

        # === Enable Window Dragging (ONLY ON TASKBAR) ===
        if self.taskbar:
            self.taskbar.mousePressEvent = lambda event: bed.start_drag(self, event)
            self.taskbar.mouseMoveEvent = lambda event: bed.move_window(self, event)
        else:
            print("Warning: Taskbar widget not found in UI file.")

        # Restrict dragging to only the taskbar (Disable dragging from anywhere else)
        self.setMouseTracking(False)

    def showEvent(self, event):
        """Restore the window state when shown again."""
        super().showEvent(event)  # Ensure PyQt handles the event properly
        bed.restore_window(self)  # Restore previous state (fullscreen or normal)

    # === 🎨 Use Backend Paint Event ===
    def paintEvent(self, event):
        bed.paintEvent(self, event)  # Call the paintEvent from backend.py


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec_())
