import sys
from PyQt5.QtWidgets import QApplication, QDialog
from PyQt5 import uic
import backend  # Backend module

# Load the UI file
UI_FILE = "GUI Design.ui"


class MainApp(QDialog):  # Use QDialog if your .ui is based on QDialog
    def __init__(self):
        super().__init__()

        uic.loadUi(UI_FILE, self)  # Load the UI

        self.show()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApp()
    sys.exit(app.exec_())
