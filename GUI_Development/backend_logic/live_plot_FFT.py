import numpy as np
import pyqtgraph as pg
from scipy.signal import windows
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PyQt5.QtCore import QTimer
from brainflow.board_shim import BoardShim
from GUI_Development.backend_logic.data_processing import get_filtered_data


class FFTGraph(QWidget):
    def __init__(self, board_shim, BoardOnCheckBox, preprocessing_controls, parent=None):
        super().__init__(parent)

        self.board_shim = board_shim
        self.BoardOnCheckBox = BoardOnCheckBox
        self.preprocessing_controls = preprocessing_controls

        self.eeg_channels = None
        self.sampling_rate = None
        self.num_points = None

        self.update_speed_ms = 500  # Slightly slower for FFT to stabilize

        self.init_ui()
        self.init_timer()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.plot = pg.PlotWidget(title="FFT - Frequency Domain")
        self.plot.setLabel("bottom", "Frequency (Hz)")
        self.plot.setLabel("left", "Amplitude (µV) ")
        self.plot.showGrid(x=True, y=True)
        self.plot.setYRange(0, 100, padding=0)  # <- Set Y-axis from 0 to max expected
        self.plot.addLegend(offset=(10, 10))
        layout.addWidget(self.plot)

        self.curves = []
        self.colors = ['r', 'g', 'b', 'c', 'm', 'y', 'w', 'orange']
        for i in range(8):  # Assuming max 8 EEG channels
            curve = self.plot.plot(pen=pg.mkPen(self.colors[i % len(self.colors)], width=1.5),
                                   name=f"Ch {i + 1}")
            self.curves.append(curve)

        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.toggle_pause)
        layout.addWidget(self.pause_button)

    def init_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(self.update_speed_ms)

    def toggle_pause(self):
        self.timer.stop() if self.timer.isActive() else self.timer.start(self.update_speed_ms)

    def update_plot(self):
        if not self.board_shim or not self.BoardOnCheckBox.isChecked():
            return

        if self.eeg_channels is None or self.sampling_rate is None or self.num_points is None:
            self.eeg_channels = BoardShim.get_eeg_channels(self.board_shim.get_board_id())
            self.sampling_rate = BoardShim.get_sampling_rate(self.board_shim.get_board_id())
            self.num_points = int(6 * self.sampling_rate)
            print(f"FFT Init: {len(self.eeg_channels)} channels, {self.sampling_rate} Hz")

        data = get_filtered_data(self.board_shim, self.num_points, self.eeg_channels, self.preprocessing_controls)

        freqs = np.fft.rfftfreq(self.num_points, d=1.0 / self.sampling_rate)

        # Create the window only once
        window = windows.hamming(self.num_points)

        for idx, ch in enumerate(self.eeg_channels):
            # Apply the window to the latest slice of EEG data
            signal = data[ch][-self.num_points:]  # Ensure same length
            windowed_signal = signal * window

            # Perform FFT on windowed signal
            fft_vals = np.fft.rfft(windowed_signal)
            amplitude = np.abs(fft_vals)

            self.curves[idx].setData(freqs, amplitude)
