import pyqtgraph as pg
import numpy as np
from joblib.numpy_pickle_utils import xrange
from scipy.signal import windows
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton
from brainflow.board_shim import BoardShim
from backend_logic.data_handling.data_collector import CentralizedDataCollector

class FFTGraph(QWidget):
    def __init__(self, board_shim, BoardOnCheckBox, preprocessing_controls, ica_manager=None, data_collector=None, parent=None):
        super().__init__(parent)

        self.board_shim = board_shim
        self.BoardOnCheckBox = BoardOnCheckBox
        self.preprocessing_controls = preprocessing_controls
        self.ica_manager = ica_manager
        self.data_collector = data_collector

        self.eeg_channels = None
        self.sampling_rate = None
        self.num_points = None

        self.update_speed_ms = 30

        self.init_ui()
        self.init_timer()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.plot = pg.PlotWidget(title="FFT - Frequency Domain")
        self.plot.setLabel("bottom", "Frequency (Hz)")
        self.plot.setLabel("left", "Amplitude (µV) ")
        self.plot.showGrid(x=True, y=True)
        self.plot.setYRange(0, 100, padding=0)  # <- Set Y-axis from 0 to max expected
        self.plot.setXRange(0, 65, padding=0.01)
        self.plot.addLegend(offset=(-20, 10))
        self.plot.enableAutoRange(axis='y', enable=True)

        layout.addWidget(self.plot)

        self.curves = []
        self.colors = ['r', 'g', 'b', 'c', 'm', 'y', 'w', 'orange']
        for i in range(8):  # Assuming max 8 EEG channels
            curve = self.plot.plot(pen=pg.mkPen(self.colors[i % len(self.colors)], width=1.5),
                                   name=f"Ch {i + 1}")
            self.curves.append(curve)

        self.pause_button = QPushButton("Pause")
        self.pause_button.setStyleSheet("font-family: 'Montserrat ExtraBold';")
        self.pause_button.clicked.connect(self.toggle_pause)
        layout.addWidget(self.pause_button)

    def init_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(self.update_speed_ms)

    def toggle_pause(self):
        if self.timer.isActive():
            self.timer.stop()
            self.pause_button.setText("Resume")
        else:
            self.timer.start(self.update_speed_ms)
            self.pause_button.setText("Pause")

    def update_plot(self):
        if not self.board_shim or not self.BoardOnCheckBox.isChecked():
            return

        if self.eeg_channels is None or self.sampling_rate is None or self.num_points is None:
            self.eeg_channels = BoardShim.get_eeg_channels(self.board_shim.get_board_id())
            self.sampling_rate = BoardShim.get_sampling_rate(self.board_shim.get_board_id())
            self.num_points = int(6 * self.sampling_rate)
            print(f"FFT Init: {len(self.eeg_channels)} channels, {self.sampling_rate} Hz")

        # Use centralized data collector
        fft_data = self.data_collector.collect_data_FFT() if self.data_collector else None
        
        if fft_data is None:
            return
            
        freqs = fft_data[0]
        amplitudes = fft_data[1]

        for idx, ch in enumerate(self.eeg_channels):
            if idx < len(amplitudes):
                amplitude = amplitudes[idx]

                self.curves[idx].setData(freqs, amplitude)
