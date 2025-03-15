import logging
import numpy as np
import pyqtgraph as pg
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PyQt5.QtCore import QTimer
from brainflow.board_shim import BoardShim
from data_processing_collection import get_filtered_data


class MuVGraph(QWidget):
    def __init__(self, board_shim, BoardOnCheckBox, preprocessing_controls, parent=None):
        """
        :param board_shim: BrainFlow BoardShim instance.
        :param BoardOnCheckBox: QCheckBox controlling EEG board state.
        :param preprocessing_controls: Dictionary of GUI elements for preprocessing.
        """
        super().__init__(parent)

        self.board_shim = board_shim
        self.eeg_channels = BoardShim.get_eeg_channels(self.board_shim.get_board_id())
        self.sampling_rate = BoardShim.get_sampling_rate(self.board_shim.get_board_id())

        self.update_speed_ms = 50  # Adjust update rate
        self.window_size = 6  # Display last 6 seconds of EEG data
        self.num_points = int(self.window_size * self.sampling_rate)

        # **Pass GUI controls**
        self.BoardOnCheckBox = BoardOnCheckBox
        self.preprocessing_controls = preprocessing_controls  # Now using checkboxes and spinboxes

        self.init_ui()
        self.init_timer()

    def init_ui(self):
        self.setFixedSize(800, 500)  # Optional fixed size

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
        if self.is_paused or not self.BoardOnCheckBox.isChecked():  # **Only update when BoardOn is checked**
            return

        filtered_data = get_filtered_data(self.board_shim, self.num_points, self.eeg_channels, self.preprocessing_controls)

        for count, channel in enumerate(self.eeg_channels):
            self.curves[count].setData(filtered_data[channel].tolist())
