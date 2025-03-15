import logging
import numpy as np
import pyqtgraph as pg
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PyQt5.QtCore import QTimer
from brainflow.board_shim import BoardShim
from GUI_Development.backend_logic.data_processing import get_filtered_data

class MuVGraph(QWidget):
    def __init__(self, board_shim, BoardOnCheckBox, preprocessing_controls, parent=None):
        """
        :param board_shim: BrainFlow BoardShim instance.
        :param BoardOnCheckBox: QCheckBox controlling EEG board state.
        :param preprocessing_controls: Dictionary of GUI elements for preprocessing.
        """
        super().__init__(parent)

        self.board_shim = board_shim
        self.BoardOnCheckBox = BoardOnCheckBox
        self.preprocessing_controls = preprocessing_controls

        # Initialize Board Attributes as None (Lazy Initialization)
        self.eeg_channels = None
        self.sampling_rate = None
        self.num_points = None

        self.update_speed_ms = 50  # Plot update speed

        self.init_ui()
        self.init_timer()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.plots = []
        self.curves = []

        for i in range(8):  # Always create 8 plots, even if the board isn't on yet
            plot = pg.PlotWidget()
            plot.showGrid(x=False, y=False)
            plot.getAxis("left").setLabel(f"Ch {i + 1}", color="white", size="8pt")  # Smaller font
            plot.getAxis("bottom").setVisible(False)  # Hide X-axis for compactness
            layout.addWidget(plot)

            curve = plot.plot(pen="c")
            self.plots.append(plot)
            self.curves.append(curve)

        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.toggle_pause)
        layout.addWidget(self.pause_button)

    def init_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_plot)

    def toggle_pause(self):
        self.timer.stop() if self.timer.isActive() else self.timer.start(self.update_speed_ms)

    def update_plot(self):
        """ Fetches EEG data and updates plots only when board is ON. """
        if not self.board_shim or not self.BoardOnCheckBox.isChecked():
            return

        # Lazy Initialization: Fetch Board Attributes Only When Needed**
        if self.eeg_channels is None or self.sampling_rate is None or self.num_points is None:
            self.eeg_channels = BoardShim.get_eeg_channels(self.board_shim.get_board_id())
            self.sampling_rate = BoardShim.get_sampling_rate(self.board_shim.get_board_id())
            self.num_points = int(6 * self.sampling_rate)  # 6-second window
            print(f"Board Attributes Initialized: {len(self.eeg_channels)} channels, {self.sampling_rate} Hz")

        # Fetch and filter EEG data
        filtered_data = get_filtered_data(self.board_shim, self.num_points, self.eeg_channels, self.preprocessing_controls)

        for count, channel in enumerate(self.eeg_channels):
            self.curves[count].setData(filtered_data[channel].tolist())
