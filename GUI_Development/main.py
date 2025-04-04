import os
import sys

# If you're using VSCode make sure to remove the comment from this
# however if you are using pycharm leave it as a Comment or dont either way works

# BOARD ID : 57

# Add the parent directory of GUI_Development to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PyQt5.QtWidgets import QApplication, QLabel, QDialog, QPushButton, QComboBox, QWidget, QSpinBox, QLineEdit, \
    QCheckBox, QDial, QTabWidget, QVBoxLayout, QSizePolicy
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5 import uic
import resources_rc
import backend_design.backend_design as bed  # Import backend functions
import backend_logic.backend_eeg as beeg
from backend_logic.live_plot_muV import MuVGraph
from backend_logic.live_plot_FFT import FFTGraph
from backend_logic.live_plot_PSD import PSDGraph
from backend_logic.TimerGUI import TimelineWidget


class MainApp(QDialog):
    def __init__(self):
        super().__init__()

        # Load UI File & Configure Window
        ui_file = os.path.join(os.path.dirname(__file__), "GUI Design.ui")
        uic.loadUi(ui_file, self)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("MIND EEG Extraction Interface")
        self.setWindowIcon(QIcon(":/images/MIND LOGO Transparent.png"))


        # TASKBAR ELEMENTS (Widgets, Buttons, etc.) as Variables ⌄
        self.taskbar = self.findChild(QWidget, "taskbar")  # Taskbar (for dragging)
        self.minimize_button = self.findChild(QPushButton, "minimize_button")
        self.close_button = self.findChild(QPushButton, "close_button")
        self.fullscreen_button = self.findChild(QPushButton, "fullscreen_button")

        # OTHER UI ELEMENTS
        self.logo_label = self.findChild(QLabel, "logo")  # Logo for clickable link
        self.menu_options = self.findChild(QComboBox, "MenuOptions")  # Dropdown Menu

        # PREPROCESSING SECTION
        self.BandPassOnOff = self.findChild(QCheckBox, "BandPassOnOff")
        self.BandStopOnOff = self.findChild(QCheckBox, "BandStopOnOff")
        self.BandPassSettings = self.findChild(QWidget, "BandPassSettings")
        self.BandStopSettings = self.findChild(QWidget, "BandStopSettings")
        self.NumBandPass = self.findChild(QSpinBox, "NumBandPass")
        self.NumBandStop = self.findChild(QSpinBox, "NumBandStop")
        self.BP1Start = self.findChild(QLineEdit, "BP1St")
        self.BP1End = self.findChild(QLineEdit, "BP1End")
        self.BP2Start = self.findChild(QLineEdit, "BP2St")
        self.BP2End = self.findChild(QLineEdit, "BP2End")
        self.BStop1Start = self.findChild(QLineEdit, "BStop1Start")
        self.BStop1End = self.findChild(QLineEdit, "BStop1End")
        self.BStop2Start = self.findChild(QLineEdit, "BStop2Start")
        self.BStop2End = self.findChild(QLineEdit, "BStop2End")

        # Initializing Detrend, Baseline and FastICA
        self.DetrendOnOff = self.findChild(QCheckBox, "DetrendOnOff")
        self.BaselineCorrOnOff = self.findChild(QCheckBox, "BaselineCorrOnOff")
        self.FastICAOnOff = self.findChild(QCheckBox, "FastICAOnOff")

        # Initializing Data Smoothing and Aggregation Filters
        self.AverageOnOff = self.findChild(QCheckBox, "AverageOnOff")
        self.MedianOnOff = self.findChild(QCheckBox, "MedianOnOff")
        self.Window = self.findChild(QSpinBox, "Window")

        # Dictionary to store all importance controls
        self.preprocessing_controls = {

            "BandPassOnOff": self.BandPassOnOff,
            "BandStopOnOff": self.BandStopOnOff,
            "DetrendOnOff": self.DetrendOnOff,
            "BP1Start": self.BP1Start,
            "BP1End": self.BP1End,
            "BP2Start": self.BP2Start,
            "BP2End": self.BP2End,
            "BStop1Start": self.BStop1Start,
            "BStop1End": self.BStop1End,
            "BStop2Start": self.BStop2Start,
            "BStop2End": self.BStop2End,
            "FastICA": self.FastICAOnOff,
            "BaselineCorrection": self.BaselineCorrOnOff,
            "NumberBandPass": self.NumBandPass,
            "NumberBandStop": self.NumBandStop,
            "Average": self.AverageOnOff,
            "Median": self.MedianOnOff,
            "Window": self.Window

        }

        # DATA FILE SELECTION
        self.RawData = self.findChild(QCheckBox, "RawData")
        self.FFTData = self.findChild(QCheckBox, "FFTData")
        self.PSDData = self.findChild(QCheckBox, "PSDData")

        # BOARD CONFIGURATION
        self.board_shim = None
        self.BoardOnOff = self.findChild(QCheckBox, "BoardOnOff")
        self.BoardOn = False
        self.BoardID = self.findChild(QLineEdit, "BoardID")
        self.ChannelDial = self.findChild(QDial, "ChannelDial")
        self.CommonReferenceOnOff = self.findChild(QCheckBox, "CommonReferenceOnOff")
        self.Port = self.findChild(QComboBox, "Port")

        # EPOCH/TIMING
        self.BeforeOnset = self.findChild(QSpinBox, "BeforeOnset")
        self.AfterOnset = self.findChild(QSpinBox, "AfterOnset")
        self.TimeBetweenTrials = self.findChild(QSpinBox, "TimeBetweenTrials")
        self.NumOfTrials = self.findChild(QLineEdit, "NumOfTrials")

        # TIMER, VISUALIZER, RECORD AND STATUS
        self.TimelineVisualizer = self.findChild(QWidget, "TimelineVisualizer")
        self.Visualizer = self.findChild(QTabWidget, "Visualizer")
        self.NoPlot = self.findChild(QWidget, "NoPlot")
        self.muVPlot = self.findChild(QWidget, "muVPlot")
        self.FFTPlot = self.findChild(QWidget, "FFTPlot")
        self.PSDPlot = self.findChild(QWidget, "PSDPlot")
        self.recordButton = self.findChild(QPushButton, "recordButton")
        self.stopButton = self.findChild(QPushButton,"stopButton")
        self.StatusBar = self.findChild(QLabel, "StatusBar")

        # UI Setup ⌄
        self.was_fullscreen = False  # Track if window was fullscreen before minimizing, starts as not fullscreen

        # Hide & Disable Settings by Default for BandPass/Stop
        self.BandPassSettings.setVisible(False)
        self.BandPassSettings.setEnabled(False)
        self.BandStopSettings.setVisible(False)
        self.BandStopSettings.setEnabled(False)

        # Connect Fundamental UI components to Functions, taskbar, logo, close, etc
        if self.logo_label:
            self.logo_label.setCursor(Qt.PointingHandCursor)
            self.logo_label.mousePressEvent = bed.open_link  # Logo opens MIND Website

        if self.minimize_button:
            self.minimize_button.clicked.connect(lambda: bed.minimize_window(self))
        if self.close_button:
            self.close_button.clicked.connect(lambda: bed.close_window(self))
        if self.fullscreen_button:
            self.fullscreen_button.clicked.connect(lambda: bed.toggle_fullscreen(self))

        if self.taskbar:
            self.taskbar.mousePressEvent = lambda event: bed.start_drag(self, event)
            self.taskbar.mouseMoveEvent = lambda event: bed.move_window(self, event)
        else:
            print("Warning: Taskbar widget not found in UI file.")

        # Checks if bandPass and bandStop amounts are >0, if so, we show the settings, if not, we hide it
        self.NumBandPass.valueChanged.connect(lambda: bed.toggle_settings_visibility(self))
        self.NumBandStop.valueChanged.connect(lambda: bed.toggle_settings_visibility(self))

        # Connect the port to the device serial and allows connection, dynamically updating
        self.Port.installEventFilter(self)

        # Embed the live muV plot into`muVPlot` widget and do the same for FFT and PSD
        self.muVGraph = None
        self.setup_muV_live_plot()

        self.FFTGraph = None
        self.setup_FFT_live_plot()

        self.PSDGraph = None
        self.setup_PSDGraph()

        self.Visualizer.setCurrentIndex(0)  # 0 for muVPlot, 1 for FFT, 2 for PSD, so just showing the muVPlot on start

        # When the tab is not showing the livePlot, don't update live plot, for better optimization
        self.Visualizer.currentChanged.connect(self.handle_tab_change_on_Visualizer)  # Detect tab change

        # Connecting the BoardConfig area to actually control the settings with the board internally
        self.BoardOnOff.clicked.connect(self.toggle_board)

        # Setting safety inputs so no invalid inputs are given, only integers
        bed.set_integer_only(self.BoardID, 0, 57)
        bed.set_integer_only(self.NumOfTrials)
        bed.set_integer_only(self.BP1Start, 0, 100)
        bed.set_integer_only(self.BP1End, 0, 100)
        bed.set_integer_only(self.BP2Start, 0, 100)
        bed.set_integer_only(self.BP2End, 0, 100)
        bed.set_integer_only(self.BStop1Start, 0, 100)
        bed.set_integer_only(self.BStop1End, 0, 100)
        bed.set_integer_only(self.BStop2Start, 0, 100)
        bed.set_integer_only(self.BStop2End, 0, 100)
        self.BeforeOnset.setMinimum(1)
        self.AfterOnset.setMinimum(1)

        # Timeline Visualizer Integration

        # Get the layout of TimelineVisualizer and clear it first
        layout = QVBoxLayout(self.TimelineVisualizer)
        self.timeline_widget = TimelineWidget(self.recordButton, self.stopButton, self.BeforeOnset, self.AfterOnset,
                                              self.TimeBetweenTrials, self.NumOfTrials, self.StatusBar)
        layout.addWidget(self.timeline_widget)  # Ensures centering without breaking layout


    def setup_muV_live_plot(self):
        """ Sets up the live EEG plot inside the muVPlot tab. """
        layout = QVBoxLayout(self.muVPlot)
        self.muVGraph = MuVGraph(self.board_shim, self.BoardOnOff, self.preprocessing_controls)
        layout.addWidget(self.muVGraph)

    def setup_FFT_live_plot(self):
        """Sets up the live FFT Plot for Frequency Domain analysis, within the FFTPlot Tab"""
        layout = QVBoxLayout(self.FFTPlot)
        self.FFTGraph = FFTGraph(self.board_shim, self.BoardOnOff, self.preprocessing_controls)
        layout.addWidget(self.FFTGraph)

    # Temp Funct not done yet
    def setup_PSDGraph(self):
        """Sets up the live PSD Plot for more precise Frequency analysis, within the PSDPlot Tab"""
        layout = QVBoxLayout(self.PSDPlot)
        self.PSDGraph = PSDGraph(self.board_shim, self.BoardOnOff, self.preprocessing_controls)
        layout.addWidget(self.PSDGraph)

    def handle_tab_change_on_Visualizer(self, index):
        """Turns the live plot on/off when switching tabs."""

        current_tab = self.Visualizer.currentWidget()

        if current_tab == self.muVPlot:
            self.muVGraph.timer.start(self.muVGraph.update_speed_ms)
            self.FFTGraph.timer.stop()
            self.PSDGraph.timer.stop()

        elif current_tab == self.FFTPlot:
            self.FFTGraph.timer.start(self.FFTGraph.update_speed_ms)
            self.muVGraph.timer.stop()
            self.PSDGraph.timer.stop()

        elif current_tab == self.PSDPlot:
            self.PSDGraph.timer.start(self.PSDGraph.update_speed_ms)
            self.muVGraph.timer.stop()
            self.FFTGraph.timer.stop()

        elif current_tab == self.NoPlot:
            # ⛔ Stop all plots if on NoPlot tab
            self.muVGraph.timer.stop()
            self.FFTGraph.timer.stop()
            self.PSDGraph.timer.stop()

    def toggle_board(self):
        if self.BoardOnOff.isChecked():  # Turn ON
            self.board_shim = beeg.turn_on_board(
                self.BoardID,
                self.Port,
                self.ChannelDial,
                self.CommonReferenceOnOff,
                self.StatusBar,
                self.BoardOn
            )

            if self.board_shim:
                self.muVGraph.board_shim = self.board_shim
                self.FFTGraph.board_shim = self.board_shim
                self.PSDGraph.board_shim = self.board_shim

                # 🔹 Only start timer if NOT on NoPlot
                current_tab = self.Visualizer.currentWidget()
                if current_tab == self.muVPlot:
                    self.muVGraph.timer.start(self.muVGraph.update_speed_ms)
                elif current_tab == self.FFTPlot:
                    self.FFTGraph.timer.start(self.FFTGraph.update_speed_ms)
                elif current_tab == self.PSDPlot:
                    self.PSDGraph.timer.start(self.PSDGraph.update_speed_ms)
                else:
                    # NoPlot is showing → nothing should run
                    pass

            else:
                self.BoardOnOff.setChecked(False)

        else:  # Turn OFF
            beeg.turn_off_board(
                self.board_shim,
                self.BoardID,
                self.Port,
                self.ChannelDial,
                self.CommonReferenceOnOff,
                self.StatusBar,
                self.BoardOn
            )
            for graph in [self.muVGraph, self.FFTGraph, self.PSDGraph]:
                graph.board_shim = None
                graph.timer.stop()

    def eventFilter(self, obj, event):
        """Refresh port list only when QComboBox is clicked."""
        if obj == self.Port and event.type() == event.MouseButtonPress:
            beeg.refresh_ports_on_click(self.Port)
        return super().eventFilter(obj, event)

    def showEvent(self, event):
        """Restore the window state when shown again."""
        super().showEvent(event)  # Ensure PyQt handles the event properly
        bed.restore_window(self)  # Restore previous state (fullscreen or normal)

    def paintEvent(self, event):
        bed.paintEvent(self, event)  # Call the paintEvent from backend.py

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec_())
