import argparse
import logging
import sys
import time
import numpy as np
import pyqtgraph as pg

from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton
from PyQt5.QtCore import QTimer

from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
from brainflow.data_filter import DataFilter, FilterTypes, DetrendOperations
from scipy.signal import windows


class FFTWindow(QMainWindow):
    def __init__(self, board_shim):
        super().__init__()

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
        self.plot.setLabel("bottom", "Frequency (Hz)")
        self.plot.setLabel("left", "Amplitude (µV)")
        self.plot.setXRange(0, 65)
        self.plot.enableAutoRange(axis='y', enable=True)
        self.plot.addLegend(offset=(-20, 10))
        self.plot.showGrid(x=True, y=True)
        self.layout.addWidget(self.plot)

        for i in range(len(self.eeg_channels)):
            curve = self.plot.plot(pen=pg.mkPen(self.colors[i % len(self.colors)], width=1.5),
                                   name=f"Ch {i + 1}")
            self.curves.append(curve)

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
        freqs = np.fft.rfftfreq(self.num_points, d=1.0 / self.sampling_rate)
        window = windows.hamming(self.num_points)

        for idx, ch in enumerate(self.eeg_channels):
            signal = data[ch]
            if len(signal) < self.num_points:
                continue

            signal = signal[-self.num_points:]
            DataFilter.detrend(signal, DetrendOperations.LINEAR.value)
            # DataFilter.perform_bandpass(signal, self.sampling_rate, 8, 13, 4, FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)
            DataFilter.remove_environmental_noise(signal,self.sampling_rate,2)
            # DataFilter.perform_bandstop(signal, self.sampling_rate, 58.0, 62.0, 4, FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)

            windowed = signal * window
            fft_vals = np.fft.rfft(windowed)
            amplitude = np.abs(fft_vals)
            self.curves[idx].setData(freqs, amplitude)




class AlphaDetector():
    def __init__(self, board_shim):
        self.board_shim = board_shim
        self.board_id = board_shim.get_board_id()
        self.eeg_channels = BoardShim.get_eeg_channels(self.board_id)
        self.sampling_rate = BoardShim.get_sampling_rate(self.board_id)
        self.num_points = int(6 * self.sampling_rate)
        self.update_speed_ms = 30







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

    commands = [f"chon_{i}_12;rldadd_{i}" for i in range(1, 9)]
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
