import numpy as np
import pyqtgraph as pg
from scipy.signal import welch, windows
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PyQt5.QtCore import QTimer
from brainflow.board_shim import BoardShim
from GUI_Development.backend_logic.data_processing import get_filtered_data


class PSDGraph(QWidget):
    def __init__(self, board_shim, BoardOnCheckBox, preprocessing_controls, parent=None):
        super().__init__(parent)

        self.board_shim = board_shim
        self.BoardOnCheckBox = BoardOnCheckBox
        self.preprocessing_controls = preprocessing_controls

        self.eeg_channels = None
        self.sampling_rate = None
        self.num_points = None

        self.update_speed_ms = 672/3  # Fast update every ~224ms

        self.init_ui()
        self.init_timer()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.plot = pg.PlotWidget(title="Power Spectral Density (PSD)")
        self.plot.setLabel("bottom", "Frequency (Hz)")
        self.plot.setLabel("left", "Power (\u00b5V\u00b2/Hz)")  # µV²/Hz for power spectral density
        self.plot.showGrid(x=True, y=True)
        self.plot.setLogMode(y=True)  # Log scale for better visibility of frequency spikes
        self.plot.setYRange(1e-1, 1e4, padding=0.1)
        self.plot.addLegend(offset=(10, 10))
        layout.addWidget(self.plot)

        self.curves = []
        self.colors = ['r', 'g', 'b', 'c', 'm', 'y', 'w', 'orange']
        for i in range(8):  # Assuming 8 EEG channels
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

        data = get_filtered_data(self.board_shim, self.num_points, self.eeg_channels, self.preprocessing_controls)

        # Welch window and overlap
        nperseg = self.num_points  # Full window size for Welch = 84 samples
        noverlap = int(0.5 * nperseg)  # 50% overlap for smoother averaging
        window = windows.hamming(nperseg)  # Tapered window to reduce spectral leakage

        for idx, ch in enumerate(self.eeg_channels):
            signal = data[ch][-self.num_points:] * window  # Apply window to signal
            freqs, power = welch(
                signal,
                fs=self.sampling_rate,
                window=window,
                nperseg=nperseg,
                noverlap=noverlap,
                scaling='density'
            )
            self.curves[idx].setData(freqs, power)
