import argparse
import logging
import sys
import time
from turtledemo.penrose import start

import numpy as np
import pyqtgraph as pg

from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel
from PyQt5.QtCore import QTimer

from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
from brainflow.data_filter import DataFilter, FilterTypes, DetrendOperations
from scipy.signal import windows
from scipy.stats import alpha


class FFTWindow(QMainWindow):
    def __init__(self, board_shim):
        super().__init__()
        self.alpha_history = []
        self.alpha_plot_length = 5000  # Show last 100 updates


        self.board_shim = board_shim
        self.board_id = board_shim.get_board_id()
        self.eeg_channels = BoardShim.get_eeg_channels(self.board_id)
        self.sampling_rate = BoardShim.get_sampling_rate(self.board_id)
        self.num_points = int(6 * self.sampling_rate)
        self.update_speed_ms = 30

        self.setWindowTitle("Alpha Rhythm FFT Visualizer")
        self.setGeometry(100, 100, 1000, 600)

        self.curves = []
        self.colors = ['r', 'g', 'b', 'c', 'm', 'y', 'w', 'orange']

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self.plot = pg.PlotWidget(title="FFT - Alpha Band")
        self.plot.setLabel("bottom", "Time (Updates)")
        self.plot.setLabel("left", "Mean Alpha Amplitude (µV)")
        self.plot.setXRange(0, self.alpha_plot_length)
        self.plot.enableAutoRange(axis='y', enable=True)
        self.plot.addLegend(offset=(-20, 10))
        self.plot.showGrid(x=True, y=True)
        self.layout.addWidget(self.plot)

        self.alpha_curve = self.plot.plot(pen=pg.mkPen('c', width=2), name="Mean Alpha Amplitude")


        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.toggle_pause)
        self.layout.addWidget(self.pause_button)
        self.is_paused = False

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(self.update_speed_ms)

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        self.pause_button.setText("Resume" if self.is_paused else "Pause")

    def update_plot(self):
        if self.is_paused or self.board_shim is None:
            return

        data = self.board_shim.get_current_board_data(self.num_points)
        if data.shape[1] < self.num_points:
            return

        overall_alpha_amplitudes = []

        for i in range(len(self.eeg_channels) - 2):
            signal = data[i][-self.num_points:]
            DataFilter.detrend(signal, DetrendOperations.LINEAR.value)
            DataFilter.remove_environmental_noise(signal, self.sampling_rate, 2)

            fft = DataFilter.perform_fft(signal, 2)  # Hamming
            freq_bins = np.fft.rfftfreq(len(signal), d=1.0 / self.sampling_rate)

            alpha_indices = np.where((freq_bins >= 8) & (freq_bins <= 13))
            alpha_fft_values = fft[alpha_indices]
            avg_alpha = np.mean(np.abs(alpha_fft_values))
            overall_alpha_amplitudes.append(avg_alpha)

        mean_alpha = np.mean(overall_alpha_amplitudes)

        self.alpha_history.append(mean_alpha)
        if len(self.alpha_history) > self.alpha_plot_length:
            self.alpha_history.pop(0)

        self.alpha_curve.setData(self.alpha_history)


class AlphaDetector(QMainWindow):

    def __init__(self, board_shim):
        super().__init__()
        self.board_shim = board_shim
        self.board_id = board_shim.get_board_id()
        self.eeg_channels = BoardShim.get_eeg_channels(self.board_id)
        self.sampling_rate = BoardShim.get_sampling_rate(self.board_id)
        self.num_points = int(15 * self.sampling_rate)
        self.update_speed_ms = 30
        self.isCalibrated = False
        self.calibration_data = None

        self.all_channels_alpha = []
        self.overall_alpha_mean = None
        self.overall_alpha_standard_deviation = None

        self.setWindowTitle("Alpha Rhythm Detector")
        self.setGeometry(50, 50, 500, 300)
        self.status = QLabel()
        self.status.setText("Start Detector or Calibrate")
        self.Cbutton = QPushButton("Start Calibration")
        self.Sbutton = QPushButton("Start Alpha Wave Detector")
        self.layout = QVBoxLayout(self.Cbutton)
        self.layout.addWidget(self.status)
        self.layout.addWidget(self.Cbutton)
        self.layout.addWidget(self.Sbutton)

        self.calibrationTimer = None
        self.countDown = 20

        self.gameplay_timer = QTimer()
        self.gameplay_timer.timeout.connect(self.update_alpha_detection) # Connect detector timer to detector function
        self.alpha_buffer = []  # Stores sliding window of alpha amplitudes
        self.window_duration = 1  # seconds per FFT window
        self.window_points = int(self.window_duration * self.sampling_rate)
        self.threshold = 1  # z-score threshold for activation

        self.RecordCtimer = None


        self.Cbutton.clicked.connect(self.init_calibrator())

        self.Sbutton.clicked.connect(self.start())


    def init_calibrator(self):
        self.status.setText("Starting Calibration....")
        self.calibrationTimer = QTimer()
        self.calibrationTimer.timeout.connect(self.update_calibrator())
        self.calibrationTimer.start(1000)



    def update_calibrator(self):

        if self.countDown > 15:
            time_until_start = self.countDown - 15
            self.status.setText(f"Starting in {time_until_start} seconds")

        elif self.countDown == 15:
            self.status.setText("Calibrating...")
            self.calibration_data = self.board_shim.get_current_board_data(self.num_points)
            for i in range(len(self.eeg_channels)):
                DataFilter.detrend(self.calibration_data[i], DetrendOperations.LINEAR.value)
                DataFilter.remove_environmental_noise(self.calibration_data[i],self.sampling_rate,2)
                DataFilter.perform_bandpass(self.calibration_data[i],self.sampling_rate,2,30,4,FilterTypes.BUTTERWORTH_ZERO_PHASE,0)


        elif self.countDown < 15:
            self.status.setText(f"Calibrating... {self.countDown} sec remaining")

        self.countDown -= 1

        if self.countDown < 0:
            self.calibrationTimer.stop()

            self.all_channels_alpha = []  # Clear previous values

            for i in range(len(self.eeg_channels)-2):
                signal = self.calibration_data[i]
                fft = DataFilter.perform_fft(signal, 2)  # 2 = Hamming Window
                freq_bins = np.fft.rfftfreq(len(signal), d=1.0 / self.sampling_rate)

                alpha_indices = np.where((freq_bins >= 8) & (freq_bins <= 13))
                alpha_fft_values = fft[alpha_indices]
                alpha_avg_amplitude = np.mean(np.abs(alpha_fft_values))  # Amplitude, not power

                self.all_channels_alpha.append(alpha_avg_amplitude)

            # Compute stats across all channels
            self.overall_alpha_mean = np.mean(self.all_channels_alpha)
            self.overall_alpha_standard_deviation = np.std(self.all_channels_alpha)

            self.status.setText("Done!")
            self.isCalibrated = True

    def start(self):
        if not self.isCalibrated:
            self.status.setText("Please calibrate first!")
            return

        self.status.setText("Alpha Detection Started!")
        self.gameplay_timer.start(self.update_speed_ms)

    def update_alpha_detection(self):
        if not self.board_shim:
            return

        data = self.board_shim.get_current_board_data(self.window_points)

        alpha_values = []
        for i in range(len(self.eeg_channels) - 2):
            signal = data[i]
            if len(signal) < self.window_points:
                return

            DataFilter.detrend(signal, DetrendOperations.LINEAR.value)
            DataFilter.remove_environmental_noise(signal, self.sampling_rate, 2)
            DataFilter.perform_bandpass(signal, self.sampling_rate, 2, 30, 4, FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)

            fft = DataFilter.perform_fft(signal, 2)
            freqs = np.fft.rfftfreq(len(signal), d=1.0 / self.sampling_rate)

            alpha_band = fft[(freqs >= 8) & (freqs <= 13)]
            alpha_amplitude = np.mean(np.abs(alpha_band))
            alpha_values.append(alpha_amplitude)

        mean_alpha = np.mean(alpha_values)
        self.alpha_buffer.append(mean_alpha)

        # Optional smoothing
        if len(self.alpha_buffer) > 10:
            self.alpha_buffer.pop(0)
        smoothed_alpha = np.mean(self.alpha_buffer)

        # Normalize
        z_score = (smoothed_alpha - self.overall_alpha_mean) / self.overall_alpha_standard_deviation

        # Detection logic
        if z_score > self.threshold:
            self.status.setText(f"Alpha ON! (z = {z_score:.2f})  → Multiplier: {1 + (z_score - 1):.2f}")
        else:
            self.status.setText(f"Alpha OFF (z = {z_score:.2f})  → Multiplier: 1.00")



def main():
    BoardShim.enable_dev_board_logger()
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument("--serial-port", type=str, default="COM4")
    parser.add_argument("--board-id", type=int, default=57)
    args = parser.parse_args()

    params = BrainFlowInputParams()
    params.serial_port = args.serial_port
    board_shim = BoardShim(args.board_id, params)

    commands = [f"chon_{i}_12;rldadd_{i}" for i in range(1, 7)]
    try:
        board_shim.prepare_session()
        board_shim.start_stream(450000)

        time.sleep(2)
        for cmd in commands:
            for sub_cmd in cmd.split(";"):
                board_shim.config_board(sub_cmd)
                logging.info(f"Sent command: {sub_cmd}")
                time.sleep(0.2)

        app = QApplication(sys.argv)
        window = FFTWindow(board_shim)
        window.show()
        sys.exit(app.exec_())

    except Exception as e:
        logging.error("Error during execution", exc_info=True)

    finally:
        logging.info("Releasing session...")
        if board_shim.is_prepared():
            board_shim.release_session()


if __name__ == "__main__":
    main()
