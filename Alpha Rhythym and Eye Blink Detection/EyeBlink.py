import argparse
import logging
import sys
import time


from PyQt5.QtWidgets import QMainWindow, QLabel, QVBoxLayout, QWidget, QPushButton, QHBoxLayout, QApplication
from PyQt5.QtCore import QTimer, pyqtSignal
from brainflow.board_shim import BoardShim, BrainFlowInputParams
from brainflow.data_filter import DataFilter, FilterTypes, DetrendOperations
import numpy as np
import pyqtgraph as pg

class BlinkDetector(QMainWindow):
    blink_detected = pyqtSignal()  # 🚨 Signal stub you can connect to external logic!

    def __init__(self, board_shim):
        super().__init__()
        self.board_shim = board_shim
        self.board_id = board_shim.get_board_id()
        self.eeg_channels = BoardShim.get_eeg_channels(self.board_id)[6:8]  # Only channels 7 and 8
        print("EEG Channels:", self.eeg_channels)

        self.sampling_rate = BoardShim.get_sampling_rate(self.board_id)
        self.num_points = int(2 * self.sampling_rate)
        self.threshold_uv = 200  # µV
        self.blink_count = 0

        self.setWindowTitle("Blink Detector")
        self.setGeometry(100, 100, 1000, 600)

        self.init_ui()
        self.timer = QTimer()
        self.timer.timeout.connect(self.detect_blink)

    def init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        layout = QVBoxLayout(self.central_widget)

        # ── Plot Area ──
        self.plots = []
        self.curves = []
        for i in range(2):
            plot = pg.PlotWidget(title=f"EEG Channel {self.eeg_channels[i]}")
            plot.setLabel('left', 'µV')
            plot.setYRange(-500, 500)
            curve = plot.plot(pen='c')
            layout.addWidget(plot)
            self.plots.append(plot)
            self.curves.append(curve)

        # ── Status + Counter ──
        label_layout = QHBoxLayout()
        self.status = QLabel("Waiting...")
        self.counter = QLabel("Blinks: 0")
        label_layout.addWidget(self.status)
        label_layout.addWidget(self.counter)
        layout.addLayout(label_layout)

        # ── Start/Stop Buttons ──
        self.start_btn = QPushButton("Start Detection")
        self.start_btn.clicked.connect(self.start_detection)
        layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop Detection")
        self.stop_btn.clicked.connect(self.stop_detection)
        layout.addWidget(self.stop_btn)

    def start_detection(self):
        self.status.setText("Detecting Blinks...")
        self.blink_count = 0
        self.counter.setText("Blinks: 0")
        self.timer.start(10)

    def stop_detection(self):
        self.status.setText("Stopped")
        self.timer.stop()

        # Reset blink count and label
        self.blink_count = 0
        self.counter.setText("Blinks: 0")

        # Clear plots
        for curve in self.curves:
            curve.clear()

    def detect_blink(self):
        if self.board_shim is None:
            return

        data = self.board_shim.get_current_board_data(self.num_points)

        # Extract channels 7 and 8 (indices 6 and 7)
        ch7, ch8 = self.eeg_channels
        sig7 = data[ch7][-self.num_points:]
        sig8 = data[ch8][-self.num_points:]

        if len(sig7) < self.num_points or len(sig8) < self.num_points:
            return

        # Apply filtering to both signals
        for signal in (sig7, sig8):
            DataFilter.detrend(signal, DetrendOperations.LINEAR.value)
            DataFilter.remove_environmental_noise(signal, self.sampling_rate, 2)
            DataFilter.perform_bandpass(signal, self.sampling_rate, 3.0, 45.0, 4,
                                        FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)
            DataFilter.perform_bandstop(signal, self.sampling_rate, 50.0, 65.0, 4,
                                        FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)

        # Update live plots for both channels
        self.curves[0].setData(sig7.tolist())
        self.curves[1].setData(sig8.tolist())

        # Average signal for blink detection
        avg_signal = (np.array(sig7) + np.array(sig8)) / 2.0

        # Blink detection logic (based on µV threshold)
        if np.any(np.abs(avg_signal) > self.threshold_uv):
            self.blink_count += 1
            self.counter.setText(f"Blinks: {self.blink_count}")
            self.status.setText("Blink Detected!")
            self.blink_detected.emit()
        else:
            self.status.setText("")


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

        # Send NeuroPawn Config Commands
        for cmd in commands:
            for sub_cmd in cmd.split(";"):
                board_shim.config_board(sub_cmd)
                logging.info(f"Sent command: {sub_cmd}")
                time.sleep(0.2)

        # Start Qt app and Blink Detector GUI
        app = QApplication(sys.argv)
        detector = BlinkDetector(board_shim)

        # Connect blink signal to terminal printout
        detector.blink_detected.connect(lambda: print("Blink detected!"))

        detector.show()
        sys.exit(app.exec_())

    except Exception as e:
        logging.error("Error during execution", exc_info=True)

    finally:
        logging.info("Releasing BrainFlow session...")
        if board_shim.is_prepared():
            board_shim.release_session()

if __name__ == "__main__":
    main()
