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


def _ensure_even_length(arr):
    # Ensure data length is even for FFT
    return arr if len(arr) % 2 == 0 else arr[:-1]


class AlphaFFTVisualizer(QMainWindow):
    def __init__(self, board_shim):
        super().__init__()
        # Board parameters
        self.board_shim = board_shim
        self.board_id = board_shim.get_board_id()
        # EEG channels and sampling rate
        self.eeg_channels = BoardShim.get_eeg_channels(self.board_id)
        self.sampling_rate = BoardShim.get_sampling_rate(self.board_id)

        # FFT window: 6 seconds (ensure even)
        self.num_points_fft = int(6 * self.sampling_rate)
        self.num_points_fft -= self.num_points_fft % 2
        self.update_speed_ms = 200  # update interval

        # Calibration / detection state
        self.state = 'idle'            # 'idle', 'calibrating', 'detecting'
        self.is_calibrated = False
        self.calibration_time = 20     # seconds
        self.calibration_buffers = []  # stores per-window mean power
        self.alpha_mean = None
        self.alpha_std = None
        self.z_threshold = 1.0

        # Plot history
        self.power_history = []        # live mean power
        self.history_length = 500     # number of points to keep

        # UI setup
        self.setWindowTitle("Alpha FFT Visualizer & Detector")
        self.resize(1200, 800)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Plot widget
        self.plot = pg.PlotWidget(title="Mean Alpha Power Over Time")
        self.plot.setLabel('bottom', 'Time (updates)')
        self.plot.setLabel('left', 'Alpha Power (µV²)')
        self.plot.showGrid(x=True, y=True)
        self.plot.enableAutoRange(axis='y', enable=True)
        layout.addWidget(self.plot)
        # Live power curve
        self.power_curve = self.plot.plot(pen=pg.mkPen('c', width=2), name='AlphaPower')
        # Threshold lines (hidden initially)
        self.mean_line = pg.InfiniteLine(angle=0, pen=pg.mkPen('y', style=Qt.DashLine))
        self.std_plus  = pg.InfiniteLine(angle=0, pen=pg.mkPen('m', style=Qt.DashLine))
        self.std_minus = pg.InfiniteLine(angle=0, pen=pg.mkPen('m', style=Qt.DashLine))
        for line in (self.mean_line, self.std_plus, self.std_minus):
            line.hide()
            self.plot.addItem(line)

        # Status and info labels
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

        self.hard_stop_btn = QPushButton("Hard Stop")
        self.hard_stop_btn.clicked.connect(self._hard_stop)
        btn_layout.addWidget(self.hard_stop_btn)

        layout.addLayout(btn_layout)

        # FFT update timer
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_fft)
        self.timer.start(self.update_speed_ms)
        self.is_paused = False

    def _info_text(self):
        m = f"{self.alpha_mean:.2f}" if self.alpha_mean is not None else "N/A"
        s = f"{self.alpha_std:.2f}" if self.alpha_std is not None else "N/A"
        return f"Mean Power: {m}    Std Dev: {s}    Z-threshold: {self.z_threshold:.1f}"

    def _toggle_pause(self):
        self.is_paused = not self.is_paused
        self.pause_btn.setText("Resume FFT" if self.is_paused else "Pause FFT")

    def _update_fft(self):
        if self.state not in ('calibrating', 'detecting') or self.is_paused:
            return
        data = self.board_shim.get_current_board_data(self.num_points_fft)
        if data.shape[1] < self.num_points_fft:
            return

        # Compute mean alpha power for first 6 channels (8–12 Hz)
        powers = []
        for ch in self.eeg_channels[:6]:
            sig = np.copy(data[ch, -self.num_points_fft:])
            DataFilter.detrend(sig, DetrendOperations.LINEAR.value)
            DataFilter.remove_environmental_noise(sig, self.sampling_rate, 2)
            DataFilter.perform_bandpass(sig, self.sampling_rate, 8.0, 12.0, 4,
                                        FilterTypes.BUTTERWORTH, 0)
            sig = _ensure_even_length(sig)
            try:
                fft_vals = DataFilter.perform_fft(sig, 2)
            except:
                continue
            # Normalize and compute power
            fft_vals = fft_vals / len(sig)
            freqs = np.fft.rfftfreq(len(sig), 1/self.sampling_rate)
            idx = np.where((freqs >= 8) & (freqs <= 12))[0]
            power_band = np.abs(fft_vals[idx])**2
            powers.append(np.mean(power_band))
        if not powers:
            return

        mean_power = np.mean(powers)
        # Update live plot
        self.power_history.append(mean_power)
        if len(self.power_history) > self.history_length:
            self.power_history.pop(0)
        self.power_curve.setData(self.power_history)

        # Show threshold lines once calibrated
        if self.is_calibrated:
            for line, val in zip(
                (self.mean_line, self.std_plus, self.std_minus),
                (self.alpha_mean,
                 self.alpha_mean + self.alpha_std * self.z_threshold,
                 self.alpha_mean - self.alpha_std * self.z_threshold)
            ):
                line.setValue(val)
                line.show()

        # Update status during detection
        if self.state == 'detecting':
            z = (mean_power - self.alpha_mean) / self.alpha_std
            st = f"Alpha ON (z={z:.2f})" if z > self.z_threshold else f"Alpha OFF (z={z:.2f})"
            self.status_label.setText(f"Status: {st}")

    def _start_calibration(self):
        self._hard_stop(clear_calib=False)
        self.state = 'calibrating'
        self.status_label.setText(f"Calibrating for {self.calibration_time}s...")
        self.calibration_buffers = []
        self.count = self.calibration_time
        self.calibration_timer = QTimer()
        self.calibration_timer.timeout.connect(self._calibration_step)
        self.calibration_timer.start(1000)

    def _calibration_step(self):
        # Use the same FFT window length for calibration
        data = self.board_shim.get_current_board_data(self.num_points_fft)
        if data.shape[1] >= self.num_points_fft:
            powers = []
            for ch in self.eeg_channels[:6]:
                sig = np.copy(data[ch, -self.num_points_fft:])
                DataFilter.detrend(sig, DetrendOperations.LINEAR.value)
                DataFilter.remove_environmental_noise(sig, self.sampling_rate, 2)
                DataFilter.perform_bandpass(sig, self.sampling_rate, 8.0, 12.0, 4,
                                            FilterTypes.BUTTERWORTH, 0)
                sig = _ensure_even_length(sig)
                try:
                    fft_vals = DataFilter.perform_fft(sig, 2)
                except:
                    continue
                fft_vals = fft_vals / len(sig)
                freqs = np.fft.rfftfreq(len(sig), 1/self.sampling_rate)
                idx = np.where((freqs >= 8) & (freqs <= 12))[0]
                power_band = np.abs(fft_vals[idx])**2
                powers.append(np.mean(power_band))
            if powers:
                self.calibration_buffers.append(np.mean(powers))
        self.count -= 1
        if self.count <= 0:
            self.calibration_timer.stop()
            if self.calibration_buffers:
                self.alpha_mean = float(np.mean(self.calibration_buffers))
                self.alpha_std  = float(np.std(self.calibration_buffers))
                self.is_calibrated = True
                self.calib_btn.setText("Recalibrate")
                self.detect_btn.setEnabled(True)
            self.status_label.setText("Calibration complete." if self.is_calibrated else "Calibration failed.")
            self.info_label.setText(self._info_text())
            self.state = 'idle'

    def _toggle_detection(self):
        if not self.is_calibrated:
            self.status_label.setText("Please calibrate first.")
            return
        if self.state != 'detecting':
            self.state = 'detecting'
            self.status_label.setText("Detection running...")
            self.detect_btn.setText("Stop Detection")
        else:
            self.state = 'idle'
            self.status_label.setText("Detection stopped.")
            self.detect_btn.setText("Start Detection")

    def _hard_stop(self, clear_calib=True):
        if hasattr(self, 'calibration_timer') and self.calibration_timer.isActive():
            self.calibration_timer.stop()
        self.state = 'idle'
        self.is_paused = False
        self.power_history.clear()
        self.power_curve.clear()
        for line in (self.mean_line, self.std_plus, self.std_minus):
            line.hide()
        self.pause_btn.setText("Pause FFT")
        self.detect_btn.setText("Start Detection")
        self.detect_btn.setEnabled(False)
        if clear_calib:
            self.is_calibrated = False
            self.alpha_mean = None
            self.alpha_std  = None
            self.calib_btn.setText("Calibrate")
        self.info_label.setText(self._info_text())
        self.status_label.setText("Status: Ready")


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
        logging.info(f"Preparing session for board ID {args.board_id}...")
        board.prepare_session()
        logging.info("Session prepared.")
        board.start_stream(450000)
        logging.info("Stream started.")
        # Configure all 8 EEG channels
        for i in range(1, 9):
            for cmd in (f"chon_{i}_12", f"rldadd_{i}"):
                board.config_board(cmd)
                logging.info(f"Config: {cmd}")
                time.sleep(0.5)
        time.sleep(2)
        app = QApplication(sys.argv)
        win = AlphaFFTVisualizer(board)
        win.show()
        sys.exit(app.exec_())
    except Exception:
        logging.error("Error during execution", exc_info=True)
    finally:
        logging.info("Releasing board session...")
        if board.is_prepared():
            board.release_session()
