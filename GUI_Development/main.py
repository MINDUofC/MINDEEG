import sys

from PyQt5.QtWidgets import QApplication, QLabel, QDialog, QPushButton, QComboBox, QWidget, QSpinBox, QLineEdit, \
    QCheckBox, QDial, QTabWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5 import uic

import backend_design.backend_design as bed  # Import backend functions
import GUI_Development.backend_logic.backend_eeg as beeg


class MainApp(QDialog):
    def __init__(self):
        super().__init__()

# Load UI File & Configure Window
        uic.loadUi("GUI Design.ui", self)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("MIND EEG Extraction Interface")
        self.setWindowIcon(QIcon(":/images/TaskbarIcon.png"))  # Ensure this is in your .qrc file

# TASKBAR ELEMENTS (Widgets, Buttons, etc) as Variables ⌄

        # Taskbar & Window Controls
        self.taskbar = self.findChild(QWidget, "taskbar")  # Taskbar (for dragging)
        self.minimize_button = self.findChild(QPushButton, "minimize_button")
        self.close_button = self.findChild(QPushButton, "close_button")
        self.fullscreen_button = self.findChild(QPushButton, "fullscreen_button")

# OTHER UI ELEMENTS
        self.logo_label = self.findChild(QLabel, "logo")  # Logo for clickable link
        self.menu_options = self.findChild(QComboBox, "MenuOptions")  # Dropdown Menu

#PREPROCESSING SECTION
        # Initializing everything for BandPas/Stops Filters
        self.BandPassOnOff = self.findChild(QCheckBox, "BandPassOnOff")
        self.BandStopOnOff = self.findChild(QCheckBox, "BandStopOnOff")

        self.BandPassSettings = self.findChild(QWidget, "BandPassSettings")
        self.BandStopSettings = self.findChild(QWidget, "BandStopSettings")
        self.NumBandPass = self.findChild(QSpinBox, "NumBandPass")
        self.NumBandStop = self.findChild(QSpinBox, "NumBandStop")

        self.BP1Start = self.findChild(QLineEdit,"BP1St")
        self.BP1End = self.findChild(QLineEdit,"BP1End")
        self.BP2Start = self.findChild(QLineEdit,"BP2St")
        self.BP2End = self.findChild(QLineEdit,"BP2End")

        self.BStop1Start = self.findChild(QLineEdit,"BStop1Start")
        self.BStop1End = self.findChild(QLineEdit,"BStop1End")
        self.BStop2Start = self.findChild(QLineEdit,"BStop2Start")
        self.BStop2End = self.findChild(QLineEdit,"BStop2End")

        # Initializing Detrend, Baseline and FastICA
        self.DetrendOnOff = self.findChild(QCheckBox, "DetrendOnOff")
        self.BaselineCorrOnOff = self.findChild(QCheckBox, "BaselineCorrOnOff")
        self.FastICAOnOff = self.findChild(QCheckBox, "FastICAOnOff")

        #Initializing Data Smoothing and Aggregation Filters
        self.AverageOnOff = self.findChild(QCheckBox, "AverageOnOff")
        self.MedianOnOff = self.findChild(QCheckBox, "MedianOnOff")
        self.Window = self.findChild(QSpinBox, "Window")

#DATA FILE SELECTION

        self.RawData = self.findChild(QCheckBox, "RawData")
        self.FFTData = self.findChild(QCheckBox, "FFTData")
        self.PSDData = self.findChild(QCheckBox, "PSDData")


#BOARD CONFIGURATION
        # Store the active board instance
        self.board_shim = None
        self.BoardOnOff = self.findChild(QCheckBox,"BoardOnOff")
        self.BoardID = self.findChild(QLineEdit, "BoardID")
        self.ChannelDial = self.findChild(QDial, "ChannelDial")
        self.CommonReferenceOnOff = self.findChild(QCheckBox, "CommonReferenceOnOff")
        self.Port = self.findChild(QComboBox, "Port")

#EPOCH/TIMING

        self.BeforeOnset = self.findChild(QSpinBox, "BeforeOnset")
        self.AfterOnset = self.findChild(QSpinBox, "AfterOnset")
        self.TimeBetweenTrials = self.findChild(QSpinBox, "TimeBetweenTrials")
        self.NumOfTrials = self.findChild(QLineEdit, "NumOfTrials")


#TIMER, VISUALIZER, RECORD AND STATUS

        self.TimelineVisualizer = self.findChild(QWidget, "TimelineVisualizer")

        self.Visualizer = self.findChild(QTabWidget, "Visualizer")
        self.muVPlot = self.findChild(QWidget, "muVPlot")
        self.PSDPlot = self.findChild(QWidget, "PSDPlot")

        self.recordButton = self.findChild(QPushButton, "recordButton")
        self.StatusBar = self.findChild(QLabel, "StatusBar")

# UI Setup ⌄

        self.was_fullscreen = False  # Track if window was fullscreen before minimizing, starts as not fullscreen

        # Hide & Disable Settings by Default for BandPass/Stop
        self.BandPassSettings.setVisible(False)
        self.BandPassSettings.setEnabled(False)
        self.BandStopSettings.setVisible(False)
        self.BandStopSettings.setEnabled(False)

        # Connect UI Elements to Functions ⌄

        #  Click Events
        if self.logo_label:
            self.logo_label.setCursor(Qt.PointingHandCursor)
            self.logo_label.mousePressEvent = bed.open_link  # Logo opens MIND Website

        # Taskbar & Window Controls (Close, Minimize, Fullscreen)
        if self.minimize_button:
            self.minimize_button.clicked.connect(lambda: bed.minimize_window(self))
        if self.close_button:
            self.close_button.clicked.connect(lambda: bed.close_window(self))
        if self.fullscreen_button:
            self.fullscreen_button.clicked.connect(lambda: bed.toggle_fullscreen(self))

        # Enable Window Dragging (ONLY ON TASKBAR)
        if self.taskbar:
            self.taskbar.mousePressEvent = lambda event: bed.start_drag(self, event)
            self.taskbar.mouseMoveEvent = lambda event: bed.move_window(self, event)
        else:
            print("Warning: Taskbar widget not found in UI file.")

        # Toggle Visibility Based on BandPass and BandStop Spinbox Values
        self.NumBandPass.valueChanged.connect(lambda: bed.toggle_settings_visibility(self))
        self.NumBandStop.valueChanged.connect(lambda: bed.toggle_settings_visibility(self))

        # Restrict dragging to only the taskbar (Disable dragging from anywhere else)
        self.setMouseTracking(False)

        # Auto-refresh port list when ComboBox is clicked**
        self.Port.installEventFilter(self)

        # Allowing Integers only for various LineBoxes, to avoid letters in an area only for numbers/integers
        bed.set_integer_only(self.BoardID,0,57)
        bed.set_integer_only(self.NumOfTrials)

        bed.set_integer_only(self.BP1Start,0,100)
        bed.set_integer_only(self.BP1End, 0, 100)
        bed.set_integer_only(self.BP2Start, 0, 100)
        bed.set_integer_only(self.BP2End, 0, 100)
        bed.set_integer_only(self.BStop1Start, 0, 100)
        bed.set_integer_only(self.BStop1End, 0, 100)
        bed.set_integer_only(self.BStop2Start, 0, 100)
        bed.set_integer_only(self.BStop2End, 0, 100)

        # Board Turn On/Off Functionality

        # Connect BoardOnOff state change to toggle function**
        self.BoardOnOff.stateChanged.connect(self.toggle_board)

    def toggle_board(self):
        """
        Handles turning the EEG board ON/OFF based on the BoardOnOff checkbox state.
        """
        if self.BoardOnOff.isChecked():  # **Turn ON the board**
            self.board_shim = beeg.turn_on_board(
                self.BoardID,
                self.Port,
                self.ChannelDial,
                self.CommonReferenceOnOff,
                self.StatusBar
            )
            if not self.board_shim:  # If board failed to start, uncheck the box
                self.BoardOnOff.setChecked(False)
        else:  # **Turn OFF the board**
            beeg.turn_off_board(
                self.board_shim,
                self.BoardID,
                self.Port,
                self.ChannelDial,
                self.CommonReferenceOnOff,
                self.StatusBar
            )

    def eventFilter(self, obj, event):
        """Refresh port list only when QComboBox is clicked."""
        if obj == self.Port and event.type() == event.MouseButtonPress:
            beeg.refresh_ports_on_click(self.Port)
        return super().eventFilter(obj, event)


    def showEvent(self, event):
        """Restore the window state when shown again."""
        super().showEvent(event)  # Ensure PyQt handles the event properly
        bed.restore_window(self)  # Restore previous state (fullscreen or normal)

    # Use Backend Paint Event
    def paintEvent(self, event):
        bed.paintEvent(self, event)  # Call the paintEvent from backend.py


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec_())
