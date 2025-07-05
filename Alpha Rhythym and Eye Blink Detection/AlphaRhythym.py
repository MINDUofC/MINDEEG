import argparse
import logging
import sys
import time

import numpy as np
import pyqtgraph as pg
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QWidget,
                             QPushButton, QLabel, QHBoxLayout)
from PyQt5.QtCore import QTimer, Qt
from brainflow.board_shim import BoardShim, BrainFlowInputParams
from brainflow.data_filter import DataFilter, FilterTypes, DetrendOperations


class AlphaFFTVisualizer(QMainWindow):
    def __init__(self, board_shim):
        super().__init__()
        # Board parameters
        self.board_shim = board_shim
        self.board_id = board_shim.get_board_id()
        self.eeg_channels = BoardShim.get_eeg_channels(self.board_id)
        self.sampling_rate = BoardShim.get_sampling_rate(self.board_id)
        self.num_points_fft = int(6 * self.sampling_rate)
        self.window_duration = 1  # seconds per detection window
        self.window_points = int(self.window_duration * self.sampling_rate)
        self.update_speed_ms = 200  # FFT update interval

        # State management: 'idle', 'calibrating', 'detecting'
        self.state = 'idle'
        self.is_calibrated = False
        self.calibration_timer = None
        self.calibration_time = 20  # seconds
        self.alpha_mean = None
        self.alpha_std = None

        # Data history for plotting
        self.alpha_history = []
        self.alpha_plot_length = 500
        self.z_threshold = 1.0

        # UI setup
        self.setWindowTitle("Alpha FFT Visualizer & Detector")
        self.setGeometry(100, 100, 1200, 800)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Plot widget
        self.plot = pg.PlotWidget(title="Mean Alpha Amplitude Over Time")
        self.plot.setLabel('bottom', 'Time (updates)')
        self.plot.setLabel('left', 'Alpha Amplitude (µV)')
        self.plot.addLegend()
        self.plot.showGrid(x=True, y=True)
        layout.addWidget(self.plot)

        self.alpha_curve = self.plot.plot(pen=pg.mkPen('c', width=2), name='Alpha')
        # Threshold lines
        self.mean_line = pg.InfiniteLine(angle=0, pen=pg.mkPen('y', style=Qt.DashLine), movable=False)
        self.std_plus = pg.InfiniteLine(angle=0, pen=pg.mkPen('m', style=Qt.DashLine), movable=False)
        self.std_minus = pg.InfiniteLine(angle=0, pen=pg.mkPen('m', style=Qt.DashLine), movable=False)
        self.plot.addItem(self.mean_line)
        self.plot.addItem(self.std_plus)
        self.plot.addItem(self.std_minus)

        # Status/info labels
        self.status_label = QLabel("Status: Ready")
        layout.addWidget(self.status_label)
        self.info_label = QLabel(self._info_text())
        layout.addWidget(self.info_label)

        # Control buttons
        btn_layout = QHBoxLayout()
        self.pause_btn = QPushButton("Pause FFT")
        self.pause_btn.clicked.connect(self._toggle_pause)
        btn_layout.addWidget(self.pause_btn)

        self.calib_btn = QPushButton("Calibrate")
        self.calib_btn.clicked.connect(self._start_calibration)
        btn_layout.addWidget(self.calib_btn)

        self.detect_btn = QPushButton("Start Detection")
        self.detect_btn.setEnabled(False)
        self.detect_btn.clicked.connect(self._toggle_detection)
        btn_layout.addWidget(self.detect_btn)

        layout.addLayout(btn_layout)

        # Timer for FFT updates
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_fft)
        self.timer.start(self.update_speed_ms)
        self.is_paused = False

    def _info_text(self):
        mean_str = f"{self.alpha_mean:.2f}" if self.alpha_mean is not None else "N/A"
        std_str = f"{self.alpha_std:.2f}" if self.alpha_std is not None else "N/A"
        return f"Mean: {mean_str}    Std: {std_str}    Z-threshold: {self.z_threshold:.1f}"

    def _toggle_pause(self):
        self.is_paused = not self.is_paused
        self.pause_btn.setText("Resume FFT" if self.is_paused else "Pause FFT")

    def _update_fft(self):
        # Only plot during calibration or detection
        if self.state == 'idle' or self.is_paused:
            return
        data = self.board_shim.get_current_board_data(self.num_points_fft)
        if data.shape[1] < self.num_points_fft:
            return
        # Compute mean alpha across channels
        alpha_vals = []
        for ch in self.eeg_channels[:-2]:
            sig = np.copy(data[ch, -self.num_points_fft:])
            DataFilter.detrend(sig, DetrendOperations.LINEAR.value)
            DataFilter.remove_environmental_noise(sig, self.sampling_rate, 2)
            fft_vals = DataFilter.perform_fft(sig, 2)
            freqs = np.fft.rfftfreq(len(sig), 1.0/self.sampling_rate)
            idx = np.where((freqs >= 8) & (freqs <= 13))[0]
            alpha_vals.append(np.mean(np.abs(fft_vals[idx])))
        mean_alpha = np.mean(alpha_vals)
        # Update history
        self.alpha_history.append(mean_alpha)
        if len(self.alpha_history) > self.alpha_plot_length:
            self.alpha_history.pop(0)
        self.alpha_curve.setData(self.alpha_history)
        # Update threshold lines if calibrated
        if self.is_calibrated:
            self.mean_line.setValue(self.alpha_mean)
            self.std_plus.setValue(self.alpha_mean + self.alpha_std * self.z_threshold)
            self.std_minus.setValue(self.alpha_mean - self.alpha_std * self.z_threshold)
        # Detection logic
        if self.state == 'detecting' and self.is_calibrated:
            z = (mean_alpha - self.alpha_mean) / self.alpha_std
            status = f"Alpha ON (z={z:.2f})" if z > self.z_threshold else f"Alpha OFF (z={z:.2f})"
            self.status_label.setText(f"Status: {status}")

    def _start_calibration(self):
        if self.state == 'calibrating':
            return
        # Enter calibration state
        self.state = 'calibrating'
        self.is_paused = False
        self.alpha_history.clear()
        self.alpha_curve.clear()
        self.status_label.setText(f"Calibrating for {self.calibration_time}s...")
        # Timer for calibration steps
        self.count = self.calibration_time
        self.calibration_timer = QTimer()
        self.calibration_timer.timeout.connect(self._calibration_step)
        self.calibration_timer.start(1000)

    def _calibration_step(self):
        if self.count <= 0:
            # Finish calibration
            self.calibration_timer.stop()
            # Compute stats from collected buffers
            all_alpha = []
            for buf in self.calibration_buffers:
                freqs = np.fft.rfftfreq(len(buf), 1.0/self.sampling_rate)
                fft_vals = DataFilter.perform_fft(buf, 2)
                idx = np.where((freqs >= 8) & (freqs <= 13))[0]
                all_alpha.append(np.mean(np.abs(fft_vals[idx])))
            self.alpha_mean = np.mean(all_alpha)
            self.alpha_std = np.std(all_alpha)
            self.is_calibrated = True
            self.info_label.setText(self._info_text())
            self.detect_btn.setEnabled(True)
            self.status_label.setText("Calibration complete. Ready for detection.")
            # Reset to idle state, clear graph
            self.state = 'idle'
            self.alpha_history.clear()
            self.alpha_curve.clear()
            return
        # Collect buffer of filtered signal average across channels
        data = self.board_shim.get_current_board_data(self.window_points)
        if data.shape[1] >= self.window_points:
            channel_buffers = []
            for ch in self.eeg_channels[:-2]:
                sig = np.copy(data[ch, -self.window_points:])
                DataFilter.detrend(sig, DetrendOperations.LINEAR.value)
                DataFilter.remove_environmental_noise(sig, self.sampling_rate, 2)
                DataFilter.perform_bandpass(sig, self.sampling_rate, 8.0, 13.0, 4, FilterTypes.BUTTERWORTH, 0)
                channel_buffers.append(np.abs(sig))
            # average across channels per sample then flatten to a single series
            avg_buf = np.mean(np.array(channel_buffers), axis=0)
            # store a single summary statistic per step
            if not hasattr(self, 'calibration_buffers'):
                self.calibration_buffers = []
            self.calibration_buffers.append(avg_buf)
        self.status_label.setText(f"Calibrating... {self.count}s remaining")
        self.count -= 1

    def _toggle_detection(self):
        if not self.is_calibrated:
            self.status_label.setText("Please calibrate first.")
            return
        if self.state != 'detecting':
            # Start detection
            self.state = 'detecting'
            self.alpha_history.clear()
            self.alpha_curve.clear()
            self.status_label.setText("Detection running...")
            self.detect_btn.setText("Stop Detection")
        else:
            # Stop detection
            self.state = 'idle'
            self.status_label.setText("Detection stopped.")
            self.detect_btn.setText("Start Detection")
            self.alpha_history.clear()
            self.alpha_curve.clear()


if __name__ == '__main__':
    BoardShim.enable_dev_board_logger()
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument('--serial-port', type=str, default='COM4')
    parser.add_argument('--board-id', type=int, default=57)
    args = parser.parse_args()
    params = BrainFlowInputParams()
    params.serial_port = args.serial_port
    board = BoardShim(args.board_id, params)
    try:
        board.prepare_session()
        board.start_stream(450000)
        time.sleep(2)
        app = QApplication(sys.argv)
        win = AlphaFFTVisualizer(board)
        win.show()
        sys.exit(app.exec_())
    finally:
        if board.is_prepared():
            board.release_session()
