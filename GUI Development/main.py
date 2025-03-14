import sys

from PyQt5.QtWidgets import QApplication, QLabel, QDialog, QPushButton, QComboBox, QWidget, QSpinBox, QLineEdit, \
    QCheckBox, QDial, QTabWidget
from PyQt5.QtCore import Qt, QUrl, QPoint
from PyQt5.QtGui import QDesktopServices, QIcon
from PyQt5 import uic

import backend_design as bed  # Import backend functions
import backend_eeg as beeg
import resources_rc  # Ensure this is generated from .qrc file


class MainApp(QDialog):
    def __init__(self):
        super().__init__()

 # Load UI File & Configure Window
        uic.loadUi("GUI Design.ui", self)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("MIND EEG Extraction Interface")
        self.setWindowIcon(QIcon(":/images/TaskbarIcon.png"))  # Ensure this is in your .qrc file

# UI Elements (Widgets, Buttons, etc) as Variables ⌄

        # Taskbar & Window Controls
        self.taskbar = self.findChild(QWidget, "taskbar")  # Taskbar (for dragging)
        self.minimize_button = self.findChild(QPushButton, "minimize_button")
        self.close_button = self.findChild(QPushButton, "close_button")
        self.fullscreen_button = self.findChild(QPushButton, "fullscreen_button")

        # Other UI Elements
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
