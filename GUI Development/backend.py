# backend.py

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices, QPainter, QLinearGradient, QColor, QBrush, QPen


def open_link(event):
    """Opens the MIND website when the logo is clicked."""
    QDesktopServices.openUrl(QUrl("https://mind-uofc.ca/"))


def minimize_window(self):
    """Minimizes the GUI and remembers whether it was fullscreen or normal."""
    self.was_fullscreen = self.isFullScreen()  # Store state before minimizing
    self.setWindowState(Qt.WindowMinimized)


def restore_window(self):
    """Restores the GUI to its previous state before minimization."""
    self.setWindowState(Qt.WindowNoState)  # Ensure window is restored
    if self.was_fullscreen:  # Restore fullscreen if it was previously fullscreen
        self.showFullScreen()
    else:
        self.showNormal()


def close_window(self):
    """Closes the application."""
    self.close()


def toggle_fullscreen(self):
    """Toggles between fullscreen and normal window mode, keeping minimize state in sync."""
    if self.isFullScreen():
        self.showNormal()
    else:
        self.showFullScreen()

    self.was_fullscreen = self.isFullScreen()  # Update state


def start_drag(self, event):
    """Stores the cursor position when clicking the taskbar."""
    if event.button() == Qt.LeftButton and not self.isFullScreen():
        self.old_pos = event.globalPos()


def move_window(self, event):
    """Moves the window when dragging the taskbar."""
    if self.old_pos and not self.isFullScreen():
        delta = event.globalPos() - self.old_pos
        self.move(self.x() + delta.x(), self.y() + delta.y())
        self.old_pos = event.globalPos()


def paintEvent(self, event):
    """ Custom Paint Event to Draw a Rounded Window with Gradient Background & Border """
    painter = QPainter(self)
    painter.setRenderHint(QPainter.Antialiasing)

    gradient = QLinearGradient(0, 0, self.width(), self.height())
    gradient.setColorAt(0.00, QColor("#FFFFFF"))  # White - Top Left
    gradient.setColorAt(0.25, QColor("#85C7F2"))  # Mind Blue
    gradient.setColorAt(0.50, QColor("#5C8FFF"))  # Flower Blue
    gradient.setColorAt(0.75, QColor("#85C7F2"))  # Mind Blue
    gradient.setColorAt(1.00, QColor("#FFFFFF"))  # White - Bottom Right

    brush = QBrush(gradient)
    painter.setBrush(brush)

    border_color = QColor("#0047B2")  # Updated Deep Blue Border
    border_pen = QPen(border_color, 3)

    painter.setPen(border_pen)
    painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 15, 15)
