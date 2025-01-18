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
        self.update_speed_ms = 100  # Update interval in milliseconds

        # Custom Montage Setup
        channels_to_keep = ['Fc3.', 'C3..', 'C1..', 'Fcz.', 'Cz..', 'C2..', 'C4..', 'Fc4.']
        self.channel_positions = {
            "Fc3.": (-0.5, 0.3, 0.0), "C3..": (-0.5, 0.0, 0.0), "C1..": (-0.25, 0.0, 0.0),
            "Fcz.": (0.0, 0.3, 0.0), "Cz..": (0.0, 0.0, 0.0), "C2..": (0.25, 0.0, 0.0),
            "C4..": (0.5, 0.0, 0.0), "Fc4.": (0.5, 0.3, 0.0)
        }
        self.custom_montage = mne.channels.make_dig_montage(ch_pos=self.channel_positions, coord_frame='head')

        # MNE info object for the selected channels
        self.raw_info = mne.create_info(
            ch_names=channels_to_keep,
            sfreq=self.sampling_rate,
            ch_types=["eeg"] * len(channels_to_keep)
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
        self.current_data = np.zeros(len(channels_to_keep))

        # Start the timer for updates
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(self.update_speed_ms)

        # Start the application
        self.app.exec_()

    # def update(self):

    #     # Get live data
    #     data = self.board_shim.get_current_board_data(256)  # Buffer size of 256 samples
    #     #self.current_data = np.mean(data[self.exg_channels], axis=1)  # Average over samples
    #     for count, channel in enumerate(self.exg_channels):
    #         # plot timeseries
    #         DataFilter.detrend(data[channel], DetrendOperations.CONSTANT.value)
    #         DataFilter.perform_bandpass(data[channel], self.sampling_rate, 8, 13, 4, FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)
    #         DataFilter.perform_bandstop(data[channel], self.sampling_rate, 58.0, 62.0, 4, FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)
    #         self.curves[count].setData(data[channel].tolist())

    #     self.app.processEvents()

    #     # Clear and redraw topomap
    #     self.ax.clear()
    #     im, cm = mne.viz.plot_topomap(
    #         self.current_data, self.raw_info, axes=self.ax, show=False, cmap="rainbow", sensors=True, sphere=(0, 0, 0, 1.2),  # Adjust sphere radius
    #     )

    #     if self.cbar is None:
    #         self.cbar = self.fig.colorbar(im, ax=self.ax)
    #     else:
    #         self.cbar.update_normal(im)
    #     plt.pause(0.001)  # Pause to allow matplotlib to update
    def update(self):
        # Get live data from the board
        data = self.board_shim.get_current_board_data(256)  # Buffer size of 256 samples

        # Initialize an empty list to store filtered signals for topomap
        filtered_signals = []

        for channel in self.eeg_channels:
            # Extract raw data for the current channel
            channel_data = data[channel]

            # Detrend the signal to remove DC offset
            DataFilter.detrend(channel_data, DetrendOperations.CONSTANT.value)

            # Apply a bandpass filter (e.g., for alpha band: 8-13 Hz)
            DataFilter.perform_bandpass(
                channel_data,
                self.sampling_rate,
                8.0,   # Lower cutoff frequency (Hz)
                13.0,  # Upper cutoff frequency (Hz)
                4,     # Filter order
                FilterTypes.BUTTERWORTH_ZERO_PHASE.value,
                0
            )

            # Apply a notch filter to remove powerline noise (e.g., 60 Hz)
            DataFilter.perform_bandstop(
                channel_data,
                self.sampling_rate,
                58.0,  # Notch center frequency (Hz)
                62.0,  # Notch bandwidth (Hz)
                4,     # Filter order
                FilterTypes.BUTTERWORTH_ZERO_PHASE.value,
                0
            )

            # Compute the average of the filtered signal for this channel
            filtered_signals.append(np.mean(channel_data))

        # Update the topomap with the filtered signals
        self.current_data = np.array(filtered_signals)

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

        # Refresh the matplotlib figure
        plt.pause(0.001)  # Pause briefly to allow updates


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







