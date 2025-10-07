import os
import sys

# If you're using VSCode make sure to remove the comment from this
# however if you are using PyCharm leave it as a comment or don’t either way works

# BOARD ID : 57

# Add the parent directory of GUI_Development to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PyQt5.QtWidgets import (
    QApplication, QLabel, QDialog, QPushButton, QComboBox, QWidget,
    QSpinBox, QLineEdit, QCheckBox, QDial, QTabWidget, QVBoxLayout
)
from PyQt5.QtCore import Qt, QSize
import time
from PyQt5.QtGui import QIcon, QKeyEvent
from PyQt5 import uic
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices
import resources_rc  # Import resources to make images available
import frontend.frontend_design as fe
import GUI_Development.backend_logic.board_setup.backend_eeg as beeg
from brainflow.board_shim import BoardShim
from GUI_Development.backend_logic.visualizer.live_plot_muV import MuVGraphVispyStacked as MuVGraph
from GUI_Development.backend_logic.visualizer.live_plot_FFT import FFTGraph
from GUI_Development.backend_logic.visualizer.live_plot_PSD import PSDGraph
from GUI_Development.backend_logic.timing_and_recording.TimerGUI import TimelineWidget
from GUI_Development.backend_logic.data_handling.ica_manager import ICAManager
from GUI_Development.backend_logic.data_handling.data_collector import CentralizedDataCollector
from GUI_Development.backend_logic.timing_and_recording.export_manager import ExportDestinationManager
from GUI_Development.backend_logic.timing_and_recording.recording_manager import PreciseRecordingManager
from GUI_Development.backend_logic.timing_and_recording.timing_engine import TimingEngine
from frontend.chatbotFE import ChatbotFE
from frontend.menu_handler import MenuHandler
from GUI_Development.backend_logic.timing_and_recording.black_screen_timer import BlackScreenTimerWindow




class MainApp(QDialog):
    def __init__(self):
        super().__init__()

        # ─── Window Variables ──────────────────────────────────────────────
        self.was_fullscreen = self.isFullScreen()
        self.old_pos = None

        # ─── Load and configure the .ui file ─────────────────────────────
        ui_file = os.path.join(os.path.dirname(__file__), "GUI Design.ui")
        uic.loadUi(ui_file, self)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("MINDStream EEG Extraction Interface")
        self.setWindowIcon(QIcon(":/images/MIND LOGO Transparent.png"))
        # Debounce state for Record button
        self._last_record_click_ts = 0.0

        # ─── Custom frameless‐resize state ────────────────────────────
        self._resizing = False
        self._resize_dir = None
        self._resize_margin = 8  # how many pixels from the edge count as "grab" zone
        self._drag_pos = None
        self._orig_geom = None


        # ─── Bind all UI elements to instance variables ──────────────────
        # Taskbar controls for dragging/minimize/close/fullscreen
        self.taskbar           = self.findChild(QWidget, "taskbar")
        self.minimize_button   = self.findChild(QPushButton, "minimize_button")
        self.close_button      = self.findChild(QPushButton, "close_button")
        self.fullscreen_button = self.findChild(QPushButton, "fullscreen_button")

        # Logo (clickable)
        self.MindLogo = self.findChild(QLabel, "MindLogo")
        self.InstaLogo = self.findChild(QPushButton, "InstaLogo")
        self.LinkedInLogo = self.findChild(QPushButton, "LinkedInLogo")
        
        # Menu Options combo box
        self.MenuOptions = self.findChild(QComboBox, "MenuOptions")

        # Chatbot controls
        self.chatbot = ChatbotFE(self)
        self.chatbot.raise_()


        # Main tab widget (for µV, FFT, PSD, etc)
        self.Visualizer = self.findChild(QTabWidget, "Visualizer")
        self.muVPlot    = self.findChild(QWidget,  "muVPlot")
        self.FFTPlot    = self.findChild(QWidget,  "FFTPlot")
        self.PSDPlot    = self.findChild(QWidget,  "PSDPlot")
        self.NoPlot     = self.findChild(QWidget,  "NoPlot")

        # Add friendly guidance message to the NoPlot tab
        try:

            no_plot_layout = self.NoPlot.layout() if self.NoPlot is not None else None
            if self.NoPlot is not None and no_plot_layout is None:
                no_plot_layout = QVBoxLayout(self.NoPlot)
            if no_plot_layout is not None:
                msg = (
                    "Click another tab to see a visualization while running!\n\n"
                    "Note, some computers may not be able to handle live plots and the timer simultaneously, "
                    "if so, stay here to record data!\n"
                    "Click the dropdown to learn how to use this interface.\n\n"
                    "Enjoy! \n\n"
                    "- The MIND Team"
                )
                info_label = QLabel(msg, self.NoPlot)
                info_label.setWordWrap(True)
                info_label.setAlignment(Qt.AlignCenter)
                info_label.setStyleSheet(
                    "font-family: 'Montserrat SemiBold'; font-size: 12pt; color: #0A1F44; padding: 16px;"
                )
                no_plot_layout.addStretch(1)
                no_plot_layout.addWidget(info_label)
                no_plot_layout.addStretch(1)
        except Exception:
            pass

        # Preprocessing controls
        self.BandPassOnOff       = self.findChild(QCheckBox, "BandPassOnOff")
        self.BandStopOnOff       = self.findChild(QCheckBox, "BandStopOnOff")
        self.NumBandPass         = self.findChild(QSpinBox,  "NumBandPass")
        self.NumBandStop         = self.findChild(QSpinBox,  "NumBandStop")
        self.BPTypeFIR_IIR       = self.findChild(QComboBox,  "BPTypeFIR_IIR")
        self.BP1Start            = self.findChild(QLineEdit,  "BP1Start")
        self.BP1End              = self.findChild(QLineEdit,  "BP1End")
        self.BP2Start            = self.findChild(QLineEdit,  "BP2Start")
        self.BP2End              = self.findChild(QLineEdit,  "BP2End")
        self.FIRWindowType       = self.findChild(QComboBox,  "FIRWindowType")
        self.FIRWindowLabel      = self.findChild(QLabel,  "FIRWindowLabel")

        # FIR/IIR Combo Box Initialization, default is IIR
        if self.BPTypeFIR_IIR is not None:
            self.BPTypeFIR_IIR.clear()
            self.BPTypeFIR_IIR.addItem("IIR")
            self.BPTypeFIR_IIR.addItem("FIR")
            self.BPTypeFIR_IIR.setCurrentIndex(0)
            
        # FIR Window Type Combo Box Initialization, default is Hamming
        if self.FIRWindowType is not None:
            self.FIRWindowType.clear()
            self.FIRWindowType.addItem("Hamming",userData="hamming")
            self.FIRWindowType.addItem("Hann",userData="hann")
            self.FIRWindowType.addItem("Blackman",userData="blackman")
            self.FIRWindowType.addItem("Kaiser (β=8)", userData=("kaiser", 8.0)) #Beta value is 8.0 as its a safe default for most applications
            self.FIRWindowType.addItem("Flat Top", userData="flattop")
            self.FIRWindowType.setCurrentIndex(0)


        self.BStop1Start         = self.findChild(QLineEdit,  "BStop1Start")
        self.BStop1End           = self.findChild(QLineEdit,  "BStop1End")
        self.BStop2Start         = self.findChild(QLineEdit,  "BStop2Start")
        self.BStop2End           = self.findChild(QLineEdit,  "BStop2End")
        self.DetrendOnOff        = self.findChild(QCheckBox, "DetrendOnOff")
        self.FastICAOnOff        = self.findChild(QCheckBox, "FastICAOnOff")
        self.ICACalibSecs        = self.findChild(QSpinBox,  "ICACalibSecs")
        self.AverageOnOff        = self.findChild(QCheckBox, "AverageOnOff")
        self.MedianOnOff         = self.findChild(QCheckBox, "MedianOnOff")
        self.Window              = self.findChild(QSpinBox,  "Window")

        # Board and data-selection controls
        self.BoardOnOff          = self.findChild(QCheckBox, "BoardOnOff")
        self.BoardID             = self.findChild(QLineEdit,  "BoardID")
        self.ChannelDial         = self.findChild(QDial,"ChannelDial")
        self.CommonReferenceOnOff= self.findChild(QCheckBox, "CommonReferenceOnOff")
        self.Port                = self.findChild(QComboBox,  "Port")
        self.RawData             = self.findChild(QCheckBox, "RawData")
        self.FFTData             = self.findChild(QCheckBox, "FFTData")
        self.PSDData             = self.findChild(QCheckBox, "PSDData")
        self.FileType            = self.findChild(QComboBox, "FileType")
        # Populate FileType combo box on startup (required for visibility)
        if self.FileType is not None:
            self.FileType.clear()
            self.FileType.addItem("Select file type...")
            self.FileType.addItem("CSV")
            self.FileType.setCurrentIndex(0)
            
        self.ExportDestination   = self.findChild(QPushButton, "ExportDestination")
        self.ExportFile          = self.findChild(QPushButton, "ExportButton")
        self.ExportStatus        = self.findChild(QLabel, "ExportStatus")

        # Epoch/timing controls
        self.BeforeOnset         = self.findChild(QSpinBox, "BeforeOnset")
        self.AfterOnset          = self.findChild(QSpinBox, "AfterOnset")
        self.TimeBetweenTrials   = self.findChild(QSpinBox, "TimeBetweenTrials")
        self.NumOfTrials         = self.findChild(QLineEdit,  "NumOfTrials")

        # Status, record/stop buttons, timeline visualizer
        self.recordButton        = self.findChild(QPushButton, "recordButton")
        self.stopButton          = self.findChild(QPushButton, "stopButton")
        self.StatusBar           = self.findChild(QLabel,      "StatusBar")
        self.TimelineVisualizer  = self.findChild(QWidget,     "TimelineVisualizer")

        # ─── Package preprocessing controls in a dict for easy passing ──
        self.preprocessing_controls = {
            "BandPassOnOff":       self.BandPassOnOff,
            "BandStopOnOff":       self.BandStopOnOff,
            "DetrendOnOff":        self.DetrendOnOff,
            "FastICA":             self.FastICAOnOff,
            "ICACalibSecs":        self.ICACalibSecs,
            "NumberBandPass":      self.NumBandPass,
            "NumberBandStop":      self.NumBandStop,
            "BPTypeFIR_IIR":       self.BPTypeFIR_IIR,
            "FIRWindowType":       self.FIRWindowType,
            "BP1Start":            self.BP1Start,
            "BP1End":              self.BP1End,
            "BP2Start":            self.BP2Start,
            "BP2End":              self.BP2End,
            "BStop1Start":         self.BStop1Start,
            "BStop1End":           self.BStop1End,
            "BStop2Start":         self.BStop2Start,
            "BStop2End":           self.BStop2End,
            "Average":             self.AverageOnOff,
            "Median":              self.MedianOnOff,
            "Window":              self.Window,
        }

        # ─── Initialize board and graph placeholders ────────────────────
        self.board_shim = None
        self.muVGraph   = None
        self.FFTGraph   = None
        self.PSDGraph   = None

        # ─── Hide band-pass/stop settings panels until needed ───────────
        self.findChild(QWidget, "BandPassSettings").setVisible(False)
        self.findChild(QWidget, "BandPassSettings").setEnabled(False)
        self.findChild(QWidget, "BandStopSettings").setVisible(False)
        self.findChild(QWidget, "BandStopSettings").setEnabled(False)
        self.findChild(QWidget, "FIRWindowLabel").setVisible(False)
        self.findChild(QWidget, "FIRWindowLabel").setEnabled(False)
        self.findChild(QWidget, "FIRWindowType").setVisible(False)
        self.findChild(QWidget, "FIRWindowType").setEnabled(False)

        # ─── Initialize FastICA checkbox state ──────────────────────────
        # Start with FastICA disabled by default
        self.FastICAOnOff.setChecked(False)
        self.FastICAOnOff.setEnabled(False)

        # ─── Social‑media & site icons ─────────────────────────────────────

        # Instagram

        if self.InstaLogo:
            self.InstaLogo.setCursor(Qt.PointingHandCursor)
            self.InstaLogo.clicked.connect(lambda:
                                           QDesktopServices.openUrl(QUrl("https://www.instagram.com/mind.uofc/"))
                                           )

        # LinkedIn

        if self.LinkedInLogo:
            self.LinkedInLogo.setCursor(Qt.PointingHandCursor)
            self.LinkedInLogo.clicked.connect(lambda:
                                              QDesktopServices.openUrl(QUrl("https://ca.linkedin.com/company/mind-uofc"))
                                              )

        # MIND website

        if self.MindLogo:
            self.MindLogo.setCursor(Qt.PointingHandCursor)
            self.MindLogo.mousePressEvent = lambda eventParam: QDesktopServices.openUrl(
                QUrl("https://minduofc.ca/")
            )

        # Note: We no longer install a global event filter for Enter/Return.

        # ─── Connect UI interactions ────────────────────────────────────

        # Window controls
        self.minimize_button.clicked.connect(lambda: fe.minimize_window(self))
        self.close_button.clicked.connect(lambda: fe.close_window(self))
        self.fullscreen_button.clicked.connect(lambda: fe.toggle_fullscreen(self, self.chatbot))
        # Dragging - use proper event handling instead of direct assignment
        self.taskbar.mousePressEvent = self.handle_taskbar_mouse_press
        self.taskbar.mouseMoveEvent = self.handle_taskbar_mouse_move
        self.taskbar.mouseReleaseEvent = self.handle_taskbar_mouse_release
        # Show/hide band settings when counts change
        self.NumBandPass.valueChanged.connect(lambda: fe.toggle_settings_visibility(self))
        self.NumBandStop.valueChanged.connect(lambda: fe.toggle_settings_visibility(self))

        self.BPTypeFIR_IIR.currentTextChanged.connect(lambda: fe.toggle_settings_visibility(self))
        

        # Refresh serial ports dropdown on click
        self.Port.installEventFilter(self)
        # Board on/off
        self.BoardOnOff.clicked.connect(self.toggle_board)
        # Channel dial changes - update FastICA state
        self.ChannelDial.valueChanged.connect(self.on_channel_dial_changed)
        # FastICA checkbox manual toggle
        self.FastICAOnOff.toggled.connect(self.on_fastica_manual_toggle)
        # Connecting FileDestination Button so it shrinks when pressed
        self.ExportDestination.pressed.connect(self.on_export_destination_clicked)
        self.ExportDestination.released.connect(self.on_export_destination_released)
        
        # Initialize menu handler
        self.menu_handler = MenuHandler(self, self.MenuOptions)



        # Enable clickable links and text selection on all labels in the app
        self.enable_global_label_interactions()

        # ─── Enforce integer-only where appropriate ─────────────────────
        fe.set_integer_only(self.BoardID, 0, 57)
        fe.set_integer_only(self.NumOfTrials)
        for fld in (self.BP1Start, self.BP1End, self.BP2Start, self.BP2End,
                    self.BStop1Start, self.BStop1End, self.BStop2Start, self.BStop2End):
            fe.set_integer_only(fld, 0, 100)
        self.BeforeOnset.setMinimum(1)
        self.AfterOnset.setMinimum(1)

        # ─── Build and add the timeline widget ──────────────────────────
        # Centralized timing engine (125 Hz)
        self.timing_engine = TimingEngine()
        try:
            # Reflect completion on the main StatusBar
            self.timing_engine.run_completed.connect(lambda: self.safe_set_status_text("All Trials Completed!"))
        except Exception:
            pass

        tl_layout = QVBoxLayout(self.TimelineVisualizer)
        self.timeline_widget = TimelineWidget(
            self.recordButton, self.stopButton,
            self.BeforeOnset, self.AfterOnset,
            self.TimeBetweenTrials, self.NumOfTrials,
            self.StatusBar, self.timing_engine
        )
        tl_layout.addWidget(self.timeline_widget)

        # BlackScreenTimer hook + mutual exclusion safety (single instance)
        self.BlackScreenTimer = self.findChild(QPushButton, "BlackScreenTimer")
        self.black_screen_window = None
        if self.BlackScreenTimer is not None:
            def open_black_screen():
                # If already open, bring to front
                if self.black_screen_window and self.black_screen_window.isVisible():
                    self.black_screen_window.activateWindow()
                    self.black_screen_window.raise_()
                    return
                # If a run is active, cancel/reset before opening the dialog
                try:
                    if getattr(self.timing_engine, "run_active", False):
                        self.stop_all_and_reset()
                except Exception:
                    pass
                # Create new dialog
                self.black_screen_window = BlackScreenTimerWindow(
                    self.timing_engine,
                    before_spinbox=self.BeforeOnset,
                    timeline_widget=self.timeline_widget,
                    parent=self
                )
                self.black_screen_window.show()
            self.BlackScreenTimer.clicked.connect(open_black_screen)
            try:
                # Ensure this button sits above sibling widgets
                self.BlackScreenTimer.raise_()
            except Exception:
                pass

        # Ensure boolean-first: disconnect TimelineWidget's direct start hookup
        try:
            if self.recordButton is not None:
                self.recordButton.clicked.disconnect()
        except Exception:
            pass

        # Initialize ICA manager
        self.ica_manager = ICAManager(self.StatusBar, self.FastICAOnOff, self.ICACalibSecs, self.ChannelDial)
        
        # Initialize data collector and associated variables
        self.data_collector = None
        self.first_time_collecting = True

        # Export destination + recording managers
        self.export_dest_manager = ExportDestinationManager()
        self.recording_manager = None

        # Hook export controls
        if self.ExportDestination is not None:
            self.ExportDestination.clicked.connect(self.browse_export_destination)
        if self.ExportFile is not None:
            self.ExportFile.clicked.connect(self.export_button_clicked)

        # Add recording handlers in addition to TimerGUI wiring
        if self.recordButton is not None:
            self.recordButton.clicked.connect(self.handle_record_button)
        if self.stopButton is not None:
            self.stopButton.clicked.connect(self.handle_stop_button)

        # Load export destination on startup and reflect in UI
        self.load_export_destination_on_startup()

        # (Reverted FileType runtime population/sizing fixes)


        # ─── Ensure µV tab is selected on start & hook tab changes ─────
        self.Visualizer.setCurrentIndex(0)
        self.Visualizer.currentChanged.connect(self.handle_tab_change_on_Visualizer)

        # ─── Enforce mutual exclusivity between Average and Median ──────
        self.AverageOnOff.clicked.connect(self.on_average_toggled)
        self.MedianOnOff.clicked.connect(self.on_median_toggled)

    def setup_muV_live_plot(self):
        """Lazy-create and embed the µV live plot into its tab."""
        layout = QVBoxLayout(self.muVPlot)
        self.muVGraph = MuVGraph(self.board_shim, self.BoardOnOff, self.preprocessing_controls, self.ica_manager, self.data_collector)
        layout.addWidget(self.muVGraph)
        
        # Update data collector reference if it exists but wasn't available during creation
        if self.data_collector and self.muVGraph.data_collector is None:
            self.muVGraph.data_collector = self.data_collector

    def setup_FFT_live_plot(self):
        """Lazy-create and embed the FFT live plot into its tab."""
        layout = QVBoxLayout(self.FFTPlot)
        self.FFTGraph = FFTGraph(self.board_shim, self.BoardOnOff, self.preprocessing_controls, self.ica_manager, self.data_collector)
        layout.addWidget(self.FFTGraph)
        
        # Update data collector reference if it exists but wasn't available during creation
        if self.data_collector and self.FFTGraph.data_collector is None:
            self.FFTGraph.data_collector = self.data_collector

    def setup_PSDGraph(self):
        """Lazy-create and embed the PSD live plot into its tab."""
        layout = QVBoxLayout(self.PSDPlot)
        self.PSDGraph = PSDGraph(self.board_shim, self.BoardOnOff, self.preprocessing_controls, self.ica_manager, self.data_collector)
        layout.addWidget(self.PSDGraph)
        
        # Update data collector reference if it exists but wasn't available during creation
        if self.data_collector and self.PSDGraph.data_collector is None:
            self.PSDGraph.data_collector = self.data_collector

    def handle_tab_change_on_Visualizer(self, index):
        """
        Starts the timer for the newly selected plot tab and stops all others.
        Lazy-loads each graph the first time its tab is shown.
        """
        current = self.Visualizer.currentWidget()

        # µV tab
        if current is self.muVPlot:
            if self.muVGraph is None:
                self.setup_muV_live_plot()
            self.muVGraph.timer.start(self.muVGraph.update_speed_ms)
            if self.FFTGraph: self.FFTGraph.timer.stop()
            if self.PSDGraph: self.PSDGraph.timer.stop()

        # FFT tab
        elif current is self.FFTPlot:
            if self.FFTGraph is None:
                self.setup_FFT_live_plot()
            self.FFTGraph.timer.start(self.FFTGraph.update_speed_ms)
            if self.muVGraph: self.muVGraph.timer.stop()
            if self.PSDGraph: self.PSDGraph.timer.stop()

        # PSD tab
        elif current is self.PSDPlot:
            if self.PSDGraph is None:
                self.setup_PSDGraph()
            self.PSDGraph.timer.start(self.PSDGraph.update_speed_ms)
            if self.muVGraph: self.muVGraph.timer.stop()
            if self.FFTGraph: self.FFTGraph.timer.stop()

        # No-plot tab
        else:
            for graph in (self.muVGraph, self.FFTGraph, self.PSDGraph):
                if graph:
                    graph.timer.stop()

    def toggle_board(self):
        """
        Turn the board on or off. When turning on, attach the shim to each
        graph and start the current tab's timer. When turning off, stop all.
        """
        if self.BoardOnOff.isChecked():
            self.board_shim = beeg.turn_on_board(
                self.BoardID, self.Port, self.ChannelDial,
                self.CommonReferenceOnOff, self.StatusBar, False
            )
            if not self.board_shim:
                # Failed to connect: revert the toggle
                self.BoardOnOff.setChecked(False)
                return


            # Initialize or update centralized data collector
            if self.data_collector is None:
                # First time initialization
            
                eeg_channels = BoardShim.get_eeg_channels(self.board_shim.get_board_id())
                self.data_collector = CentralizedDataCollector(
                    self.board_shim, 
                    eeg_channels, 
                    self.preprocessing_controls, 
                    self.ica_manager
                )
            else:
                # Subsequent times - just update the board_shim
                self.data_collector.set_board_shim(self.board_shim)
    



            # Update ICA manager's board shim reference
            self.ica_manager.set_board_shim(self.board_shim)

            # Automatically enable FastICA if we have 2+ channels
            self.update_fastica_state()

            # Start the timer on whichever tab is active now (this may create graphs)
            self.handle_tab_change_on_Visualizer(self.Visualizer.currentIndex())
            
            # Update each graph's board_shim and data_collector reference AFTER they're created
            if self.muVGraph: 
                self.muVGraph.board_shim = self.board_shim
                self.muVGraph.data_collector = self.data_collector
            if self.FFTGraph: 
                self.FFTGraph.board_shim = self.board_shim
                self.FFTGraph.data_collector = self.data_collector
            if self.PSDGraph: 
                self.PSDGraph.board_shim = self.board_shim
                self.PSDGraph.data_collector = self.data_collector

            # Initialize precise recording manager when board is on and collector ready
            try:
                if self.data_collector and self.recording_manager is None:
                    self.recording_manager = PreciseRecordingManager(
                        self.data_collector,
                        self.timeline_widget,
                        self.timing_engine,
                        self.ExportStatus
                    )
            except Exception:
                pass

            # Set first_time_collecting to False since next time we turn on the board its no longer the first time
            self.first_time_collecting = False

        else:
            # Power off the board and stop all timers
            beeg.turn_off_board(
                self.board_shim, self.BoardID, self.Port,
                self.ChannelDial, self.CommonReferenceOnOff, self.StatusBar, False
            )
            # Clear ICA manager's board reference
            self.ica_manager.clear_board_shim()
            
            # Automatically disable FastICA when board is turned off
            self.disable_fastica()
            
            # Clear the board_shim reference to ensure fresh instance on next turn on
            self.board_shim = None
            
            # Clear the data collector's board reference but keep the collector
            if self.data_collector:
                self.data_collector.set_board_shim(None)
            # Stop any ongoing recording when board turns off
            if self.recording_manager and self.recording_manager.is_recording:
                try:
                    self.recording_manager.forfeit()
                except Exception:
                    pass
            
            for graph in (self.muVGraph, self.FFTGraph, self.PSDGraph):
                if graph:
                    graph.board_shim = None
                    # Keep the data_collector reference - it will handle the board_shim being None
                    graph.timer.stop()

    def load_export_destination_on_startup(self):
        saved_path, is_valid = self.export_dest_manager.load_destination_on_startup()
        if is_valid:
            try:
                base = os.path.basename(saved_path.rstrip(os.sep)) or saved_path
                self.ExportDestination.setText("")
                self.ExportDestination.setToolTip(saved_path)
                self.ExportStatus.setText("Export destination loaded")
            except Exception:
                pass
        else:
            try:
                self.ExportDestination.setText("")
                self.ExportDestination.setToolTip("No export destination selected")
                self.ExportStatus.setText("Select export destination before exporting")
            except Exception:
                pass

    # (Removed FileType configure/ensure methods)

    def browse_export_destination(self):
        try:
            from PyQt5.QtWidgets import QFileDialog
            path = QFileDialog.getExistingDirectory(self, "Select Export Destination Directory")
            if path:
                if self.export_dest_manager.save_destination(path):
                    base = os.path.basename(path.rstrip(os.sep)) or path
                    self.ExportDestination.setText("")
                    self.ExportDestination.setToolTip(path)
                    self.ExportStatus.setText("Export destination updated")
                else:
                    self.ExportStatus.setText("Failed to save export destination")
        except Exception:
            pass

    def validate_recording_controls(self):
        # Ensure a file type is chosen
        if (self.FileType is None) or (self.FileType.currentIndex() <= 0):
            return False, "File type not selected"
        # Ensure at least one data type is selected
        selected = any([
            self.RawData.isChecked() if self.RawData is not None else False,
            self.FFTData.isChecked() if self.FFTData is not None else False,
            self.PSDData.isChecked() if self.PSDData is not None else False,
        ])
        if not selected:
            return False, "No data types selected"
        return True, "OK"

    def handle_record_button(self):
        # Debounce: ignore rapid re-clicks within 200ms
        now_ts = time.monotonic()
        if (now_ts - getattr(self, '_last_record_click_ts', 0.0)) < 0.2:
            return
        self._last_record_click_ts = now_ts
        # Boolean-first: decide recording_enabled from validation & board state
        ok, msg = self.validate_recording_controls()
        board_on = bool(self.BoardOnOff and self.BoardOnOff.isChecked())
        recording_enabled = bool(ok and board_on)
        try:
            if not ok:
                self.ExportStatus.setText(f"Not recording: {msg}")
            elif not board_on:
                self.ExportStatus.setText("Board OFF: Not recording")
        except Exception:
            pass

        # Boolean-first: configure and start engine once; consumers react
        try:
            # Ensure recording_manager exists
            if self.data_collector and self.recording_manager is None:
                self.recording_manager = PreciseRecordingManager(
                    self.data_collector,
                    self.timeline_widget,
                    self.timing_engine,
                    self.ExportStatus
                )

            # Configure engine run from UI controls
            total_trials_val = 0
            try:
                total_trials_val = int(self.NumOfTrials.text())
            except Exception:
                total_trials_val = 0

            self.timing_engine.configure_run(
                before_s=self.BeforeOnset.value(),
                after_s=self.AfterOnset.value(),
                buffer_s=self.TimeBetweenTrials.value(),
                total_trials=total_trials_val,
            )

            # Configure selected types for recorder
            selected_types = {
                'muV': self.RawData.isChecked() if self.RawData else False,
                'FFT': self.FFTData.isChecked() if self.FFTData else False,
                'PSD': self.PSDData.isChecked() if self.PSDData else False,
            }
            if self.recording_manager:
                self.recording_manager.selected_types = selected_types

            # Start engine (emits immediate tick)
            self.timing_engine.start(recording_enabled=recording_enabled)
            try:
                # Update main screen StatusBar
                if recording_enabled:
                    self.safe_set_status_text("Recording started")
                else:
                    self.safe_set_status_text("Board OFF: Timer only (not recording)")
            except Exception:
                pass

            # Start recorder only when enabled; otherwise remain reactive but idle
            if recording_enabled and self.recording_manager:
                success, message = self.recording_manager.start(selected_types)
                if success:
                    self.ExportStatus.setText("Board ON: Recording in progress")
                else:
                    self.ExportStatus.setText(f"Recording failed: {message}")
        except Exception:
            try:
                self.ExportStatus.setText("Recording failed: Unexpected error")
            except Exception:
                pass

    def handle_stop_button(self):
        # Stop engine (UI and recorder react). Forfeit any in-progress data.
        try:
            run_active = bool(getattr(self, 'timing_engine', None) and self.timing_engine.run_active)
            rec_active = bool(self.recording_manager and self.recording_manager.is_recording)
            if not run_active and not rec_active:
                self.safe_set_status_text("Nothing to stop!")
                return

            if hasattr(self, 'timing_engine') and self.timing_engine:
                self.timing_engine.stop()
            if self.recording_manager and self.recording_manager.is_recording:
                self.recording_manager.forfeit()
            # Clear visual/labels immediately
            try:
                if hasattr(self, 'timeline_widget') and self.timeline_widget:
                    self.timeline_widget.sudden_stop(self.StatusBar)
            except Exception:
                pass
            # Update both statuses safely
            self.safe_set_status_text("Recording stopped")
            try:
                if self.ExportStatus is not None:
                    self.ExportStatus.setText("Recording stopped")
            except Exception:
                pass
        except Exception:
            pass

    def stop_all_and_reset(self):
        """Hard stop engine/recording and reset timeline visuals immediately."""
        was_run_active = bool(getattr(self, 'timing_engine', None) and self.timing_engine.run_active)
        was_recording = bool(self.recording_manager and self.recording_manager.is_recording)
        try:
            if hasattr(self, 'timing_engine') and self.timing_engine:
                self.timing_engine.stop()
        except Exception:
            pass
        try:
            if self.recording_manager and self.recording_manager.is_recording:
                self.recording_manager.forfeit()
        except Exception:
            pass
        try:
            if hasattr(self, 'timeline_widget') and self.timeline_widget:
                # Quiet clear so this behaves exactly like a normal stop for visuals/labels
                if hasattr(self.timeline_widget, 'clear_visuals_quiet'):
                    self.timeline_widget.clear_visuals_quiet()
                else:
                    self.timeline_widget.sudden_stop(self.StatusBar)
        except Exception:
            pass
        try:
            if was_run_active or was_recording:
                self.safe_set_status_text("Recording stopped")
                if self.ExportStatus is not None:
                    self.ExportStatus.setText("Recording stopped")
        except Exception:
            pass

    def safe_set_status_text(self, text: str):
        try:
            if hasattr(self, 'StatusBar') and self.StatusBar is not None:
                self.StatusBar.setText(text)
        except Exception:
            pass

    def export_button_clicked(self):
        try:
            if not self.recording_manager or not self.recording_manager.has_cached_data():
                self.ExportStatus.setText("Export failed: Record data beforehand")
                return
            dest = self.export_dest_manager.current_destination
            if not dest or not os.path.isdir(dest):
                self.ExportStatus.setText("Export failed: Destination not set")
                return
            # Require explicit file type selection (CSV only for now)
            if (self.FileType is None) or (self.FileType.currentIndex() <= 0):
                self.ExportStatus.setText("Export failed: Select file type")
                return
            file_type = self.FileType.currentText()
            if file_type.upper() != "CSV":
                self.ExportStatus.setText("Export failed: Unsupported file type")
                return
            
            # Get current UI selections
            selected_types = {
                'muV': self.RawData.isChecked() if self.RawData is not None else False,
                'FFT': self.FFTData.isChecked() if self.FFTData is not None else False,
                'PSD': self.PSDData.isChecked() if self.PSDData is not None else False,
            }
            
            # Check if no types are selected
            if not any(selected_types.values()):
                self.ExportStatus.setText("Export failed: No data types selected")
                return
            
            # Get available data types
            available_types = self.recording_manager.get_available_data_types()
            
            # Check if any selected types don't have recorded data
            unavailable_selected = []
            for data_type, is_selected in selected_types.items():
                if is_selected and not available_types.get(data_type, False):
                    unavailable_selected.append(data_type)
            
            if unavailable_selected:
                types_str = ", ".join(unavailable_selected)
                self.ExportStatus.setText(f"Export failed: {types_str} not recorded")
                return
            
            # Export with current selections
            success, message, exported_types = self.recording_manager.export_cached(dest, "csv", selected_types)
            self.ExportStatus.setText(message)
            
        except Exception:
            try:
                self.ExportStatus.setText("Export failed: Unexpected error")
            except Exception:
                pass

    def update_fastica_state(self):
        """
        Automatically enable/disable FastICA checkbox based on current channel count.
        Called when board is turned on or channel count changes.
        """
        if not self.board_shim:
            self.disable_fastica()
            return
        
        try:
            # Get current channel count from the dial
            channel_count = self.ChannelDial.value()
            
            if channel_count >= 2:
                # Enable FastICA checkbox
                self.FastICAOnOff.setEnabled(True)
                # Keep it unchecked initially - user must manually enable it
                self.FastICAOnOff.setChecked(False)
            else:
                # Disable FastICA checkbox if insufficient channels
                self.disable_fastica()
                
        except Exception as e:
            # If there's any error, disable FastICA for safety
            self.disable_fastica()
    
    def disable_fastica(self):
        """
        Disable FastICA checkbox and uncheck it.
        Called when board is turned off or when there are insufficient channels.
        """
        self.FastICAOnOff.setEnabled(False)
        self.FastICAOnOff.setChecked(False)

    def on_channel_dial_changed(self, value):
        """
        Handle channel dial value changes to automatically update FastICA state.
        Only affects FastICA if the board is currently on.
        """
        if self.BoardOnOff.isChecked() and self.board_shim:
            self.update_fastica_state()

    def on_fastica_manual_toggle(self, checked: bool):
        """
        Handle manual toggling of the FastICA checkbox.
        Updates the ICA manager's state accordingly.
        """
        if checked:
            self.ica_manager.enable_ica_manually()
        else:
            self.ica_manager.disable_ica_manually()

    def eventFilter(self, obj, event):
        """Refresh serial ports list when the Port combobox is clicked."""
        if obj is self.Port and event.type() == event.MouseButtonPress:
            beeg.refresh_ports_on_click(self.Port)
        return super().eventFilter(obj, event)

    def showEvent(self, event):
        """Restore window state (fullscreen/normal) when the dialog is shown."""
        super().showEvent(event)
        fe.restore_window(self, self.chatbot)
        # Re-apply interaction flags in case labels were re-created or updated
        self.enable_global_label_interactions()
        # Keep BlackScreenTimer button above other widgets after show/restore
        try:
            btn = getattr(self, 'BlackScreenTimer', None)
            if btn is not None:
                btn.raise_()
        except Exception:
            pass

    def paintEvent(self, event):
        """Custom painting (rounded corners, shadows) via backend helper."""
        fe.paintEvent(self, event)

    def on_average_toggled(self, checked: bool):
        """
        If Average smoothing is turned on, force Median smoothing off.
        """
        if checked:
            # Uncheck Median when Average is enabled
            self.MedianOnOff.setChecked(False)

    def on_median_toggled(self, checked: bool):
        """
        If Median smoothing is turned on, force Average smoothing off.
        """
        if checked:
            # Uncheck Average when Median is enabled
            self.AverageOnOff.setChecked(False)

    def keyPressEvent(self, event: QKeyEvent):
        # Intercept Esc to toggle fullscreen instead of closing
        if event.key() == Qt.Key_Escape:
            # if you're already fullscreen, go back to normal; otherwise go fullscreen
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            # Always consume Enter/Return at the dialog level so it never triggers accept/close
            # Child widgets (inputs) already received the key first and handled submission/newlines
            event.accept()
            return
        else:
            # all other keys behave normally
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        # look for clicks near the edges
        if event.button() == Qt.LeftButton:
            d = self.get_resize_direction(event.pos())
            if d:
                self._resizing   = True
                self._resize_dir = d
                self._drag_pos   = event.globalPos()
                self._orig_geom  = self.geometry()
                return  # start resizing
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.pos()
        if self._resizing:
            # perform the resize
            self.perform_resize(event.globalPos())
            self.chatbot.reposition()
        else:
            # update the cursor shape when hovering edges
            d = self.get_resize_direction(pos)
            cursors = {
                'left': Qt.SizeHorCursor, 'right': Qt.SizeHorCursor,
                'top': Qt.SizeVerCursor, 'bottom': Qt.SizeVerCursor,
                'top-left': Qt.SizeFDiagCursor, 'bottom-right': Qt.SizeFDiagCursor,
                'top-right': Qt.SizeBDiagCursor, 'bottom-left': Qt.SizeBDiagCursor,
            }
            self.setCursor(cursors.get(d, Qt.ArrowCursor))
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._resizing:
            self._resizing   = False
            self._resize_dir = None
            self.chatbot.reposition()
            return
        super().mouseReleaseEvent(event)

    def get_resize_direction(self, pos):
        """Return one of: 'left','right','top','bottom','top-left',… or None."""
        m = self._resize_margin
        r = self.rect()
        dirs = []
        if pos.x() <= r.left()   + m: dirs.append('left')
        elif pos.x() >= r.right() - m: dirs.append('right')
        if pos.y() <= r.top()    + m: dirs.append('top')
        elif pos.y() >= r.bottom() - m: dirs.append('bottom')
        if len(dirs) == 2:
            return f"{dirs[0]}-{dirs[1]}"
        return dirs[0] if dirs else None

    def perform_resize(self, global_pos):
        """Resize the window based on drag delta and direction."""
        delta_x = global_pos.x() - self._drag_pos.x()
        delta_y = global_pos.y() - self._drag_pos.y()
        x, y, w, h = (self._orig_geom.x(), self._orig_geom.y(),
                      self._orig_geom.width(), self._orig_geom.height())
        new_x, new_y, new_w, new_h = x, y, w, h

        d = self._resize_dir
        if 'right' in d:
            new_w = max(self.minimumWidth(), w + delta_x)
        if 'bottom' in d:
            new_h = max(self.minimumHeight(), h + delta_y)
        if 'left' in d:
            new_x = x + delta_x
            new_w = max(self.minimumWidth(), w - delta_x)
        if 'top' in d:
            new_y = y + delta_y
            new_h = max(self.minimumHeight(), h - delta_y)

        self.setGeometry(new_x, new_y, new_w, new_h)
        self.chatbot.reposition()


    def on_export_destination_clicked(self):
        self.ExportDestination.setIconSize(QSize(17,17))

    def on_export_destination_released(self):
        self.ExportDestination.setIconSize(QSize(20,20))

    def handle_taskbar_mouse_press(self, event):
        """Handle mouse press events on the taskbar for window dragging."""
        fe.start_drag(self, event)
        # Don't call super() here to prevent event propagation conflicts
        
    def handle_taskbar_mouse_move(self, event):
        """Handle mouse move events on the taskbar for window dragging."""
        fe.move_window(self, event, self.chatbot)
        # Don't call super() here to prevent event propagation conflicts
        
    def handle_taskbar_mouse_release(self, event):
        """Handle mouse release events on the taskbar to stop dragging."""
        fe.stop_drag(self, event)
        # Don't call super() here to prevent event propagation conflicts

    def enable_global_label_interactions(self):
        """Make all QLabel widgets allow link clicking and text selection app-wide."""
        try:
            for lbl in self.findChildren(QLabel):
                try:
                    lbl.setTextFormat(Qt.RichText)
                    lbl.setOpenExternalLinks(True)
                    lbl.setTextInteractionFlags(Qt.TextBrowserInteraction | Qt.TextSelectableByMouse)
                except Exception:
                    # Some labels may not support all flags; continue gracefully
                    pass
        except Exception:
            pass

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec_()) is not None