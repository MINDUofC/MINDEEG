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
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QKeyEvent
from PyQt5 import uic
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices
import resources_rc
import backend_design.backend_design as bed  # Backend window/control helpers
import backend_logic.backend_eeg as beeg
from backend_logic.live_plot_muV import MuVGraphVispyStacked as MuVGraph
from backend_logic.live_plot_FFT import FFTGraph
from backend_logic.live_plot_PSD import PSDGraph
from backend_logic.TimerGUI import TimelineWidget


class MainApp(QDialog):
    def __init__(self):
        super().__init__()

        self.was_fullscreen = self.isFullScreen()


        # ─── Load and configure the .ui file ─────────────────────────────
        ui_file = os.path.join(os.path.dirname(__file__), "GUI Design.ui")
        uic.loadUi(ui_file, self)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("MINDStream EEG Extraction Interface")
        self.setWindowIcon(QIcon(":/images/MIND LOGO Transparent.png"))

        # ─── Custom frameless‐resize state ────────────────────────────
        self._resizing = False
        self._resize_dir = None
        self._resize_margin = 8  # how many pixels from the edge count as “grab” zone
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

        # Main tab widget (for µV, FFT, PSD, etc)
        self.Visualizer = self.findChild(QTabWidget, "Visualizer")
        self.muVPlot    = self.findChild(QWidget,  "muVPlot")
        self.FFTPlot    = self.findChild(QWidget,  "FFTPlot")
        self.PSDPlot    = self.findChild(QWidget,  "PSDPlot")
        self.NoPlot     = self.findChild(QWidget,  "NoPlot")

        # Preprocessing controls
        self.BandPassOnOff       = self.findChild(QCheckBox, "BandPassOnOff")
        self.BandStopOnOff       = self.findChild(QCheckBox, "BandStopOnOff")
        self.NumBandPass         = self.findChild(QSpinBox,  "NumBandPass")
        self.NumBandStop         = self.findChild(QSpinBox,  "NumBandStop")
        self.BP1Start            = self.findChild(QLineEdit,  "BP1St")
        self.BP1End              = self.findChild(QLineEdit,  "BP1End")
        self.BP2Start            = self.findChild(QLineEdit,  "BP2St")
        self.BP2End              = self.findChild(QLineEdit,  "BP2End")
        self.BStop1Start         = self.findChild(QLineEdit,  "BStop1Start")
        self.BStop1End           = self.findChild(QLineEdit,  "BStop1End")
        self.BStop2Start         = self.findChild(QLineEdit,  "BStop2Start")
        self.BStop2End           = self.findChild(QLineEdit,  "BStop2End")
        self.DetrendOnOff        = self.findChild(QCheckBox, "DetrendOnOff")
        self.FastICAOnOff        = self.findChild(QCheckBox, "FastICAOnOff")
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
            "NumberBandPass":      self.NumBandPass,
            "NumberBandStop":      self.NumBandStop,
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
            "Window":              self.Window
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
                QUrl("https://mind-uofc.ca/")
            )

        # ─── Connect UI interactions ────────────────────────────────────

        # Window controls
        self.minimize_button.clicked.connect(lambda: bed.minimize_window(self))
        self.close_button.clicked.connect(lambda: bed.close_window(self))
        self.fullscreen_button.clicked.connect(lambda: bed.toggle_fullscreen(self))
        # Dragging
        self.taskbar.mousePressEvent = lambda e: bed.start_drag(self, e)
        self.taskbar.mouseMoveEvent  = lambda e: bed.move_window (self, e)
        # Show/hide band settings when counts change
        self.NumBandPass.valueChanged.connect(lambda: bed.toggle_settings_visibility(self))
        self.NumBandStop.valueChanged.connect(lambda: bed.toggle_settings_visibility(self))
        # Refresh serial ports dropdown on click
        self.Port.installEventFilter(self)
        # Board on/off
        self.BoardOnOff.clicked.connect(self.toggle_board)

        # ─── Enforce integer-only where appropriate ─────────────────────
        bed.set_integer_only(self.BoardID, 0, 57)
        bed.set_integer_only(self.NumOfTrials)
        for fld in (self.BP1Start, self.BP1End, self.BP2Start, self.BP2End,
                    self.BStop1Start, self.BStop1End, self.BStop2Start, self.BStop2End):
            bed.set_integer_only(fld, 0, 100)
        self.BeforeOnset.setMinimum(1)
        self.AfterOnset.setMinimum(1)

        # ─── Build and add the timeline widget ──────────────────────────
        tl_layout = QVBoxLayout(self.TimelineVisualizer)
        self.timeline_widget = TimelineWidget(
            self.recordButton, self.stopButton,
            self.BeforeOnset, self.AfterOnset,
            self.TimeBetweenTrials, self.NumOfTrials,
            self.StatusBar
        )
        tl_layout.addWidget(self.timeline_widget)

        # ─── Ensure µV tab is selected on start & hook tab changes ─────
        self.Visualizer.setCurrentIndex(0)
        self.Visualizer.currentChanged.connect(self.handle_tab_change_on_Visualizer)

        # ─── Enforce mutual exclusivity between Average and Median ──────
        self.AverageOnOff.clicked.connect(self._on_average_toggled)
        self.MedianOnOff.clicked.connect(self._on_median_toggled)

    def setup_muV_live_plot(self):
        """Lazy-create and embed the µV live plot into its tab."""
        layout = QVBoxLayout(self.muVPlot)
        self.muVGraph = MuVGraph(self.board_shim, self.BoardOnOff, self.preprocessing_controls)
        layout.addWidget(self.muVGraph)

    def setup_FFT_live_plot(self):
        """Lazy-create and embed the FFT live plot into its tab."""
        layout = QVBoxLayout(self.FFTPlot)
        self.FFTGraph = FFTGraph(self.board_shim, self.BoardOnOff, self.preprocessing_controls)
        layout.addWidget(self.FFTGraph)

    def setup_PSDGraph(self):
        """Lazy-create and embed the PSD live plot into its tab."""
        layout = QVBoxLayout(self.PSDPlot)
        self.PSDGraph = PSDGraph(self.board_shim, self.BoardOnOff, self.preprocessing_controls)
        layout.addWidget(self.PSDGraph)

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
        graph and start the current tab’s timer. When turning off, stop all.
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

            # Update each graph’s board_shim reference if they exist
            if self.muVGraph: self.muVGraph.board_shim = self.board_shim
            if self.FFTGraph: self.FFTGraph.board_shim = self.board_shim
            if self.PSDGraph: self.PSDGraph.board_shim = self.board_shim

            # Start the timer on whichever tab is active now
            self.handle_tab_change_on_Visualizer(self.Visualizer.currentIndex())

        else:
            # Power off the board and stop all timers
            beeg.turn_off_board(
                self.board_shim, self.BoardID, self.Port,
                self.ChannelDial, self.CommonReferenceOnOff, self.StatusBar, False
            )
            for graph in (self.muVGraph, self.FFTGraph, self.PSDGraph):
                if graph:
                    graph.board_shim = None
                    graph.timer.stop()

    def eventFilter(self, obj, event):
        """Refresh serial ports list when the Port combobox is clicked."""
        if obj is self.Port and event.type() == event.MouseButtonPress:
            beeg.refresh_ports_on_click(self.Port)
        return super().eventFilter(obj, event)

    def showEvent(self, event):
        """Restore window state (fullscreen/normal) when the dialog is shown."""
        super().showEvent(event)
        bed.restore_window(self)

    def paintEvent(self, event):
        """Custom painting (rounded corners, shadows) via backend helper."""
        bed.paintEvent(self, event)

    def _on_average_toggled(self, checked: bool):
        """
        If Average smoothing is turned on, force Median smoothing off.
        """
        if checked:
            # Uncheck Median when Average is enabled
            self.MedianOnOff.setChecked(False)

    def _on_median_toggled(self, checked: bool):
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
        else:
            # all other keys behave normally
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        # look for clicks near the edges
        if event.button() == Qt.LeftButton:
            d = self._get_resize_direction(event.pos())
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
            self._perform_resize(event.globalPos())
        else:
            # update the cursor shape when hovering edges
            d = self._get_resize_direction(pos)
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
            return
        super().mouseReleaseEvent(event)

    def _get_resize_direction(self, pos):
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

    def _perform_resize(self, global_pos):
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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec_())
