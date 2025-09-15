import pyqtgraph as pg
import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.signal import welch, windows
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton
from brainflow.board_shim import BoardShim
from GUI_Development.backend_logic.data_collector import CentralizedDataCollector


class PSDGraph(QWidget):
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

        self.update_speed_ms = 30  # Fast update every ~224ms

        self.init_ui()
        self.init_timer()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.plot = pg.PlotWidget(title="Power Spectral Density (PSD)")
        self.plot.setLabel("bottom", "Frequency (Hz)")
        self.plot.setLabel("left", "ln(1 + Power) (µV²/Hz)")
        self.plot.showGrid(x=True, y=True)
        self.plot.setLogMode(y=False)  # Keep linear scale
        self.plot.setXRange(0, 65, padding=0.01)
        self.plot.setYRange(0, 9, padding=0.05)
        self.plot.addLegend(offset=(-20, 10))
        layout.addWidget(self.plot)

        self.curves = []
        self.colors = ['r', 'g', 'b', 'c', 'm', 'y', 'w', 'orange']
        for i in range(8):  # Assuming 8 EEG channels
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

            # ─────────────────────────────────────────────────────
            # 📐 PSD Theory & Resolution Explanation:
            #
            # Frequency Resolution = fs / N
            # For 1.5 Hz resolution at fs = 125 Hz:
            #     N = fs / 1.5 = 83.33 ≈ 84 samples needed
            # Time required for 84 samples: 84 / 125 = 0.672 seconds
            #
            # ➤ We're using a 0.672 second window (N = 84) (0.008 seconds a sample * 84 samples = 0.672
            # ➤ We update the plot every 0.672 / 3 = 224ms (smoother updates)
            # ➤ Using Welch method to average overlapping FFT windows for stability
            # ─────────────────────────────────────────────────────

            self.num_points = 84  # for 1.5 Hz resolution
            print(f"PSD Init: {len(self.eeg_channels)} channels, {self.sampling_rate} Hz")

        # Use centralized data collector
        psd_data = self.data_collector.collect_data_PSD() if self.data_collector else None
        
        if psd_data is None:
            return
            
        freqs = psd_data[0]
        powers = psd_data[1]

        for idx, ch in enumerate(self.eeg_channels):
            if idx < len(powers):
                log_power = powers[idx]
            self.curves[idx].setData(freqs, log_power)
            # if you switch to linear scale, just use the power variable instead of log_power

