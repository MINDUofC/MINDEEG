import sys
from PyQt5.QtWidgets import QApplication, QLabel, QDialog
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices, QIcon
from PyQt5 import uic
import resources_rc
import os

class MainApp(QDialog):
    def __init__(self):
        super().__init__()
        uic.loadUi("GUI Design.ui", self)  # Load UI file

        # Set Window Title
        self.setWindowTitle("MIND EEG Extraction Interface")

        # Set Taskbar & Window Icon (Ensure path is correct)
        self.setWindowIcon(QIcon(":/images/TaskbarIcon.png"))  # Uses resources.qrc


        # Find QLabel using the correct object name "logo"
        self.logo_label = self.findChild(QLabel, "logo")

        if self.logo_label:
            # Make QLabel clickable
            self.logo_label.setCursor(Qt.PointingHandCursor)  # Change cursor to hand
            self.logo_label.mousePressEvent = self.open_link  # Connect click event

    def open_link(self, event):
        """Opens a URL when the logo is clicked."""
        QDesktopServices.openUrl(QUrl("https://mind-uofc.ca/"))  # Replace with your actual URL

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec_())
