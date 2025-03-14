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
from scipy.interpolate import CubicSpline


class Graph(QMainWindow):
    def __init__(self, board_shim):
        super().__init__()

        self.board_id = board_shim.get_board_id()
        self.board_shim = board_shim
        self.eeg_channels = BoardShim.get_eeg_channels(self.board_id)
        self.sampling_rate = BoardShim.get_sampling_rate(self.board_id)

        self.update_speed_ms = 1  # Update every 1ms for near real-time response
        self.window_size = 6  # Display 4 seconds of EEG data
        self.num_points = int(self.window_size * self.sampling_rate)

        self.init_ui()
        self.init_timer()

    def init_ui(self):
        self.setWindowTitle("NeuroPawn EEG Live Stream")
        self.setGeometry(50, 50, 1000, 600)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        layout = QVBoxLayout(self.central_widget)

        self.plots = []
        self.curves = []
        for i in range(len(self.eeg_channels)):
            plot = pg.PlotWidget()
            plot.showGrid(x=False, y=False)

            plot.getAxis("left").setLabel(f"Channel {i + 1}", color="white", size="10pt")

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
        if self.is_paused:
            return

        data = self.board_shim.get_current_board_data(self.num_points)

        for count, channel in enumerate(self.eeg_channels):
            DataFilter.detrend(data[channel], DetrendOperations.LINEAR.value)
            DataFilter.perform_bandpass(data[channel], self.sampling_rate, 8, 13, 4, FilterTypes.BUTTERWORTH_ZERO_PHASE,
                                        0)
            DataFilter.perform_bandstop(data[channel], self.sampling_rate, 58.0, 62.0, 4,
                                        FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)

            interpolated_signal = self.interpolate_signal(data[channel])
            self.curves[count].setData(interpolated_signal.tolist())

        QApplication.processEvents()

    @staticmethod
    def interpolate_signal(data, upsample_factor=2):
        x = np.arange(len(data))
        x_new = np.linspace(0, len(data) - 1, len(data) * upsample_factor)
        interpolator = CubicSpline(x, data)
        return interpolator(x_new)


def main():
    BoardShim.enable_dev_board_logger()
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

    parser = argparse.ArgumentParser(description="NeuroPawn EEG Streaming and Visualization")
    parser.add_argument("--timeout", type=int, default=15, help="Timeout for device connection")
    parser.add_argument("--ip-port", type=int, default=0, help="IP port")
    parser.add_argument("--ip-protocol", type=int, default=0, help="IP protocol")
    parser.add_argument("--ip-address", type=str, default="", help="IP address")
    parser.add_argument("--serial-port", type=str, default="COM4", help="Serial port for NeuroPawn")
    parser.add_argument("--mac-address", type=str, default="", help="MAC address")
    parser.add_argument("--other-info", type=str, default="", help="Other info")
    parser.add_argument("--streamer-params", type=str, default="", help="Streamer parameters")
    parser.add_argument("--serial-number", type=str, default="", help="Serial number")
    parser.add_argument("--board-id", type=int, default=57, help="Board ID for NeuroPawn")
    parser.add_argument("--file", type=str, default="", help="File for playback mode")
    parser.add_argument("--master-board", type=int, default=BoardIds.NO_BOARD, help="Master board ID")

    args = parser.parse_args()

    params = BrainFlowInputParams()
    params.ip_port = args.ip_port
    params.serial_port = args.serial_port
    params.mac_address = args.mac_address
    params.other_info = args.other_info
    params.serial_number = args.serial_number
    params.ip_address = args.ip_address
    params.ip_protocol = args.ip_protocol
    params.timeout = args.timeout
    params.file = args.file
    params.master_board = args.master_board

    # **NeuroPawn Board Configuration Commands**
    neuro_pawn_commands = [
        "chon_1_12",  # Enable channel 1 with gain 12
        "rldadd_1",  # Toggle right leg drive for channel 1  (THIS IS THE EARLOBE REFERENCE FOR CHANNEL 1)
        "chon_2_12",  # Enable channel 2 with gain 12
        "rldadd_2",  # Toggle right leg drive for channel 2  (THIS IS THE EARLOBE REFERENCE FOR CHANNEL 2)
        "chon_3_12",  # ...
        "rldadd_3",
        "chon_4_12",
        "rldadd_4",
        "chon_5_12",
        "rldadd_5",
        "chon_6_12",
        "rldadd_6",
        "chon_7_12",
        "rldadd_7",
        "chon_8_12",
        "rldadd_8",
    ]

    board_shim = BoardShim(args.board_id, params)

    try:
        board_shim.prepare_session()
        eeg_channels = board_shim.get_eeg_channels(args.board_id)
        logging.info(f"Sampling rate: {board_shim.get_sampling_rate(args.board_id)} Hz")
        logging.info(f"EEG Channels: {eeg_channels}")

        board_shim.start_stream(450000, args.streamer_params)
        time.sleep(2)  # Allow time for board to start streaming

        # Send configuration commands to NeuroPawn board
        for command in neuro_pawn_commands:
            board_shim.config_board(command)
            logging.info(f"Sent command: {command}")
            time.sleep(0.25)  # Wait between commands for stability

        # Start the GUI and EEG plotting
        app = QApplication(sys.argv)
        graph = Graph(board_shim)
        graph.show()
        sys.exit(app.exec_())

    except Exception as e:
        logging.error("Exception occurred", exc_info=True)
    finally:
        logging.info("Shutting down NeuroPawn EEG session...")
        if board_shim.is_prepared():
            board_shim.release_session()


if __name__ == "__main__":
    main()
