import argparse
import logging
import time
import numpy as np
import pyqtgraph as pg
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
from brainflow.data_filter import DataFilter, FilterTypes, DetrendOperations
from pyqtgraph.Qt import QtWidgets, QtCore
import mne
import matplotlib.pyplot as plt


class LiveTopomap:
    def __init__(self, board_shim):
        self.board_shim = board_shim
        self.board_id = board_shim.get_board_id()
        self.eeg_channels = BoardShim.get_eeg_channels(self.board_id)
        self.sampling_rate = BoardShim.get_sampling_rate(self.board_id)
        self.update_speed_ms = 500  # Update interval in milliseconds

        # Define the 10-10 system montage
        eeg_positions_10_10 = {
        "Fp1.": (-0.5, 1.0), "Fp2.": (0.5, 1.0), "Fpz.": (0.0, 1.0),
        "Af7.": (-0.75, 0.75), "Af3.": (-0.25, 0.75), "Afz.": (0.0, 0.75), "Af4.": (0.25, 0.75), "Af8.": (0.75, 0.75),
        "F7..": (-1.0, 0.5), "F5..": (-0.75, 0.5), "F3..": (-0.5, 0.5), "F1..": (-0.25, 0.5),
        "Fz..": (0.0, 0.5), "F2..": (0.25, 0.5), "F4..": (0.5, 0.5), "F6..": (0.75, 0.5), "F8..": (1.0, 0.5), 
        "Ft7.": (-1.0, 0.3), "Fc5.": (-0.75, 0.3), "Fc3.": (-0.5, 0.3), "Fc1.": (-0.25, 0.3),
        "Fcz.": (0.0, 0.3), "Fc2.": (0.25, 0.3), "Fc4.": (0.5, 0.3), "Fc6.": (0.75, 0.3), "Ft8.": (1.0, 0.3),
        "T9..": (-1.2, 0.0), "T7..": (-1.0, 0.0), "C5..": (-0.75, 0.0), "C3..": (-0.5, 0.0), "C1..": (-0.25, 0.0),
        "Cz..": (0.0, 0.0), "C2..": (0.25, 0.0), "C4..": (0.5, 0.0), "C6..": (0.75, 0.0), "T8..": (1.0, 0.0), "T10.": (1.2, 0.0),
        "Tp7.": (-1.0, -0.3), "Cp5.": (-0.75, -0.3), "Cp3.": (-0.5, -0.3), "Cp1.": (-0.25, -0.3),
        "Cpz.": (0.0, -0.3), "Cp2.": (0.25, -0.3), "Cp4.": (0.5, -0.3), "Cp6.": (0.75, -0.3), "Tp8.": (1.0, -0.3),
        "P7..": (-1.0, -0.5), "P5..": (-0.75, -0.5), "P3..": (-0.5, -0.5), "P1..": (-0.25, -0.5),
        "Pz..": (0.0, -0.5), "P2..": (0.25, -0.5), "P4..": (0.5, -0.5), "P6..": (0.75, -0.5), "P8..": (1.0, -0.5),
        "Po7.": (-0.75, -0.75), "Po3.": (-0.25, -0.75), "Poz.": (0.0, -0.75), "Po4.": (0.25, -0.75), "Po8.": (0.75, -0.75),
        "O1..": (-0.5, -1.0), "Oz..": (0.0, -1.0), "O2..": (0.5, -1.0), "Iz..": (0.0, -1.2)
        }
        self.ch_pos = {ch: (x, y, 0.0) for ch, (x, y) in eeg_positions_10_10.items()}
        self.custom_montage = mne.channels.make_dig_montage(ch_pos=self.ch_pos, coord_frame='head')

        # Define channel names for the active channels
        self.active_channel_names = ["Fc3.", "C3..", "C1..", "Fcz.", "Cz..", "C2..", "C4..", "Fc4."]

        # MNE info object for all 10-10 channels
        self.raw_info = mne.create_info(
            ch_names=list(eeg_positions_10_10.keys()),
            sfreq=self.sampling_rate,
            ch_types=["eeg"] * len(eeg_positions_10_10)
        )
        self.raw_info.set_montage(self.custom_montage)

        # PyQtGraph application setup
        self.app = QtWidgets.QApplication.instance()
        if self.app is None:
            self.app = QtWidgets.QApplication([])

        self.win = pg.GraphicsLayoutWidget()
        self.win.setWindowTitle("Live EEG Topomap")
        self.win.resize(800, 800)
        self.win.show()

        # Initialize live topographical map
        self.fig, self.ax = plt.subplots()
        self.cbar = None

        # Initialize data with zeros
        self.current_data = np.zeros(len(eeg_positions_10_10))

        # Start the timer for updates
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(self.update_speed_ms)

        # Start the application
        self.app.exec_()

    def update(self):
        # Get live data from the board
        data = self.board_shim.get_current_board_data(62)

        # Extract and process live data for the active channels
        filtered_signals = []
        for channel in self.eeg_channels:
            channel_data = data[channel]
            DataFilter.detrend(channel_data, DetrendOperations.CONSTANT.value)
            DataFilter.perform_bandstop(
                channel_data,
                self.sampling_rate,
                58.0, 62.0, 4,
                FilterTypes.BUTTERWORTH_ZERO_PHASE.value,
                0
            )
            DataFilter.perform_bandpass(
                channel_data,
                self.sampling_rate,
                8.0, 13.0, 4,
                FilterTypes.BUTTERWORTH_ZERO_PHASE.value,
                0
            )
            filtered_signals.append(np.mean(channel_data))

        # Update the corresponding positions in the full montage
        for i, ch_name in enumerate(self.raw_info["ch_names"]):
            if ch_name in self.active_channel_names:
                # Map live data to the appropriate channel in the montage
                self.current_data[i] = filtered_signals[self.active_channel_names.index(ch_name)]
            else:
                self.current_data[i] = 0.0  # Set inactive channels to zero

        # Clear and redraw the topomap
        self.ax.clear()
        im, cm = mne.viz.plot_topomap(
            self.current_data, self.raw_info, axes=self.ax, show=False, cmap="rainbow", sensors=True, sphere=(0, 0, 0, 1.2)
        )

        # Update the color bar
        if self.cbar is None:
            self.cbar = self.fig.colorbar(im, ax=self.ax)
        else:
            self.cbar.update_normal(im)

        plt.pause(0.1)  # Pause briefly to allow updates




def main():
    BoardShim.enable_dev_board_logger()
    logging.basicConfig(level=logging.DEBUG)

    parser = argparse.ArgumentParser()
    # use docs to check which parameters are required for specific board, e.g. for Cyton - set serial port
    parser.add_argument('--timeout', type=int, help='timeout for device discovery or connection', required=False, default=0)
    parser.add_argument('--ip-port', type=int, help='ip port', required=False, default=0)
    parser.add_argument('--ip-protocol', type=int, help='ip protocol, check IpProtocolType enum', required=False,
                        default=0)
    parser.add_argument('--ip-address', type=str, help='ip address', required=False, default='')
    parser.add_argument('--serial-port', type=str, help='serial port', required=False, default='COM5')
    parser.add_argument('--mac-address', type=str, help='mac address', required=False, default='')
    parser.add_argument('--other-info', type=str, help='other info', required=False, default='')
    parser.add_argument('--streamer-params', type=str, help='streamer params', required=False, default='')
    parser.add_argument('--serial-number', type=str, help='serial number', required=False, default='')
    parser.add_argument('--board-id', type=int, help='board id, check docs to get a list of supported boards', required=False, default=57)
    parser.add_argument('--file', type=str, help='file', required=False, default='')
    parser.add_argument('--master-board', type=int, help='master board id for streaming and playback boards',
                        required=False, default=BoardIds.NO_BOARD)
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

    board_shim = BoardShim(args.board_id, params)
    commands = [
    "chon_1_12",  # Enable channel 1 with gain 12
    "rldadd_1",   # Toggle right leg drive for channel 1
    "chon_2_12",  # Enable channel 2 with gain 12
    "rldadd_2",    # Toggle right leg drive for channel 2
    "chon_3_12",
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
    try:
        board_shim.prepare_session()
        board_shim.start_stream(450000)
        for command in commands:
            board_shim.config_board(command)  # Send the command to the board
            print(f"Sent command: {command}")
            time.sleep(1)  # Wait 1 second before sending the next command
        time.sleep(2)
        LiveTopomap(board_shim)
    except Exception as e:
        logging.warning("Exception occurred", exc_info=True)
    finally:
        if board_shim.is_prepared():
            board_shim.release_session()

if __name__ == '__main__':
    main()







