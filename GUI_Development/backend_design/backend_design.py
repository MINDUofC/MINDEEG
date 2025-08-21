from PyQt5.QtGui import QIntValidator, QGradient
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtCore import Qt, QUrl, QPointF
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
    self.chatBotGeometryChanged(self.chatbot)



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
    self.chatBotGeometryChanged(self.chatbot)


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
        self.chatBotGeometryChanged(self.chatbot)



def paintEvent(self, event):
    """ Custom Paint Event to Draw a Rounded Window with Gradient Background & Border """
    painter = QPainter(self)
    painter.setRenderHint(QPainter.Antialiasing)

    # Define gradient in relative coords (0,1) → (1,0)
    gradient = QLinearGradient(QPointF(0, 1), QPointF(1, 0))
    gradient.setCoordinateMode(QGradient.ObjectBoundingMode)
    gradient.setColorAt(0.00, QColor("#FFFFFF"))
    gradient.setColorAt(0.25, QColor("#85C7F2"))
    gradient.setColorAt(0.50, QColor("#5C8FFF"))
    gradient.setColorAt(0.75, QColor("#85C7F2"))
    gradient.setColorAt(1.00, QColor("#FFFFFF"))

    painter.setBrush(QBrush(gradient))
    painter.setPen(QPen(QColor("#0047B2"), 3))

    # Draw the full widget rect
    painter.drawRect(self.rect().adjusted(1, 1, -1, -1))

def toggle_settings_visibility(self):
    """Toggles visibility of BandPassSettings & BandStopSettings based on spinbox values."""

    # Get values from spinboxes
    bandpass_value = self.NumBandPass.value()
    bandstop_value = self.NumBandStop.value()

    # BandPassSettings visibility toggle
    if bandpass_value > 0:
        self.BandPassSettings.setVisible(True)
        self.BandPassSettings.setEnabled(True)
    else:
        self.BandPassSettings.setVisible(False)
        self.BandPassSettings.setEnabled(False)

    # BandStopSettings visibility toggle
    if bandstop_value > 0:
        self.BandStopSettings.setVisible(True)
        self.BandStopSettings.setEnabled(True)
    else:
        self.BandStopSettings.setVisible(False)
        self.BandStopSettings.setEnabled(False)




def set_integer_only(line_edit: QLineEdit, min_value: int = None, max_value: int = None):
    """
    Restricts a QLineEdit to accept only integer values.

    :param line_edit: The QLineEdit object to modify.
    :param min_value: (Optional) Minimum value allowed.
    :param max_value: (Optional) Maximum value allowed.
    """
    if min_value is not None and max_value is not None:
        validator = QIntValidator(min_value, max_value)
    elif min_value is not None:
        validator = QIntValidator(min_value, 2147483647)  # Max value for a 32-bit integer
    elif max_value is not None:
        validator = QIntValidator(-2147483648, max_value)  # Min value for a 32-bit integer
    else:
        validator = QIntValidator()

    line_edit.setValidator(validator)
