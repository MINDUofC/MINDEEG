import logging
import numpy as np

import pyqtgraph as pg
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PyQt5.QtCore import QTimer

from brainflow.board_shim import BoardShim
from brainflow.data_filter import DataFilter, FilterTypes, DetrendOperations
from scipy.interpolate import CubicSpline


class MuVGraph(QWidget):  #
    def __init__(self, board_shim, parent=None):
        super().__init__(parent)  # **Allows embedding in another window**

        self.board_id = board_shim.get_board_id()
        self.board_shim = board_shim
        self.eeg_channels = BoardShim.get_eeg_channels(self.board_id)
        self.sampling_rate = BoardShim.get_sampling_rate(self.board_id)

        self.update_speed_ms = 50  # Adjust update rate
        self.window_size = 6  # Display last 6 seconds of EEG data
        self.num_points = int(self.window_size * self.sampling_rate)

        self.init_ui()
        self.init_timer()

    def init_ui(self):
        # **Optionally set a fixed size (remove if embedding in a layout)**
        self.setFixedSize(800, 500)

        layout = QVBoxLayout(self)

        self.plots = []
        self.curves = []
        for i in range(len(self.eeg_channels)):
            plot = pg.PlotWidget()
            plot.showGrid(x=False, y=False)
            plot.getAxis("left").setLabel(f"Channel {i + 1}", color="white", size="10pt")
            plot.getAxis("bottom").setVisible(False)  # **Hides X-axis**
            layout.addWidget(plot)

            curve = plot.plot(pen="c")
            self.plots.append(plot)
            self.curves.append(curve)

        self.is_paused = False
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.toggle_pause)
        layout.addWidget(self.pause_button)

    def init_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(self.update_speed_ms)

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        self.pause_button.setText("Resume" if self.is_paused else "Pause")

    def update_plot(self):
        if self.is_paused:
            return

        data = self.board_shim.get_current_board_data(self.num_points)

        for count, channel in enumerate(self.eeg_channels):
            DataFilter.detrend(data[channel], DetrendOperations.LINEAR.value)
            DataFilter.perform_bandpass(data[channel], self.sampling_rate, 8, 13, 4, FilterTypes.BUTTERWORTH_ZERO_PHASE,
                                        0)
            DataFilter.perform_bandstop(data[channel], self.sampling_rate, 58.0, 62.0, 4,
                                        FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)

            interpolated_signal = self.interpolate_signal(data[channel])
            self.curves[count].setData(interpolated_signal.tolist())

    @staticmethod
    def interpolate_signal(data, upsample_factor=2):
        x = np.arange(len(data))
        x_new = np.linspace(0, len(data) - 1, len(data) * upsample_factor)
        interpolator = CubicSpline(x, data)
        return interpolator(x_new)
