import argparse
import logging
import time
import numpy as np
import pyqtgraph as pg
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
from brainflow.data_filter import DataFilter, FilterTypes, DetrendOperations
from pyqtgraph.Qt import QtGui, QtCore, QtWidgets


class Graph:

        def __init__(self, board_shim):
            # Get the board ID of the connected board (used to identify board-specific features)
            self.board_id = board_shim.get_board_id()

            # Store the board_shim object for accessing EEG data and board methods
            self.board_shim = board_shim

            # Get the list of EEG channel indices for the connected board
            self.eeg_channels = BoardShim.get_eeg_channels(self.board_id)

            # Retrieve the sampling rate of the board (samples per second per channel)
            self.sampling_rate = BoardShim.get_sampling_rate(self.board_id)

            # Define how often the plot updates (in milliseconds) (The update function is triggered every 8 ms)
            self.update_speed_ms = 8

            # Define the time window (in seconds) to display on the plot (Shows data from the last X seconds)
            self.window_size = 3

            # Calculate the total number of data points to display in the time window
            self.num_points = self.window_size * self.sampling_rate

            # Initialize the Qt application (create or use an existing instance if it exists)
            self.app = QtWidgets.QApplication.instance()
            if self.app is None:
                self.app = QtWidgets.QApplication([])

            # Create the main GUI window using pyqtgraph
            self.win = pg.GraphicsLayoutWidget()
            self.win.setWindowTitle('BrainFlow Plot')   # Set the window title
            self.win.resize(800, 600)               # Set the window size in pixels
            self.win.show()                             # Display the window on the screen

            # Initialize time-series plots for each EEG channel
            self._init_timeseries()

            # Create a QTimer to periodically call the update function
            timer = QtCore.QTimer()
            timer.timeout.connect(self.update)      # Connect the timer to the update method
            timer.start(self.update_speed_ms)       # Start the timer with the defined interval (8 ms)


            # Create the main layout (combining the plot and button)
            self.main_widget = QtWidgets.QWidget()  # Create a main container widget
            self.layout = QtWidgets.QVBoxLayout()  # Create a vertical layout
            self.main_widget.setLayout(self.layout)

            # Add the pyqtgraph plot widget to the layout
            self.layout.addWidget(self.win)

            # Create a pause/resume button and add it to the layout
            self.is_paused = False  # State to track if the plot is paused
            self.pause_button = QtWidgets.QPushButton("Pause")
            self.pause_button.clicked.connect(self.toggle_pause)  # Connect the button to the toggle function
            self.layout.addWidget(self.pause_button)  # Add the button to the vertical layout

            # Show the main widget
            self.main_widget.show()


            # Start the Qt event loop (keeps the application running and responsive)
            self.app.exec()

        def toggle_pause(self):
            """Toggle the pause state of the plot."""
            self.is_paused = not self.is_paused  #if pause is true, then pause turns false, and if pause is false, it turns true

            self.pause_button.setText("Resume" if self.is_paused else "Pause")  # Update button text


        def _init_timeseries(self):


            # Initialize lists to store plot and curve objects for each channel
            self.plots = list()
            self.curves = list()

            #LEFT SIDE PLOT

            plt_left_side = self.win.addPlot(row=0, col=0)  # Add a new plot in a separate row (row is a channel)

            plt_left_side.showAxis('left', True)  # Enable the left axis
            plt_left_side.getAxis('left').setLabel(f"Channel {"Left"}", color='white', size='10pt')
            plt_left_side.setMenuEnabled("left",False)

            # plt_left_side.setMouseEnabled(x=True, y=False)

            plt_left_side.setYRange(-1000, +1000)  # Lock the Y-axis range

            plt_left_side.showAxis('bottom', False)         # Hide the bottom axis to simplify the display
            plt_left_side.setMenuEnabled('bottom', False)   # Disable the bottom axis context menu

            plt_left_side.setTitle('TimeSeries Plot')       # Set the title for the first plot only

            self.plots.append(plt_left_side)  # Store the plot object in the list
            curve1 = plt_left_side.plot()  # Create a curve object for plotting data
            self.curves.append(curve1)  # Store the curve object in the list
            #left hand plot is now at index 0 of these lists


            #RIGHT SIDE PLOT

            plt_right_side = self.win.addPlot(row=2, col=0)  # Add a new plot in a separate row (row is a channel)

            plt_right_side.showAxis('left', True)  # Enable the left axis
            plt_right_side.getAxis('left').setLabel(f"Channel {"Right"}", color='white', size='10pt')
            plt_right_side.setMenuEnabled("left", False)

            # plt_right_side.setMouseEnabled(x=True, y=False)

            plt_right_side.setYRange(-1000, +1000)  # Lock the Y-axis range

            plt_right_side.showAxis('bottom', False)  # Hide the bottom axis to simplify the display
            plt_right_side.setMenuEnabled('bottom', False)  # Disable the bottom axis context menu



            self.plots.append(plt_right_side)                # Store the plot object in the list
            curve2 = plt_right_side.plot()                    # Create a curve object for plotting data
            self.curves.append(curve2)                       # Store the curve object in the list
            # right hand plot is now at index 1 of these lists


        def update(self):

            # Skip updates if the plot is paused
            if self.is_paused:
                return


            # Retrieve the most recent `num_points` data samples from the board's buffer
            # This ensures we always have a sliding window of the latest data
            data = self.board_shim.get_current_board_data(self.num_points)



            # Loop through each EEG channel to update its corresponding plot
            for count, channel in enumerate(self.eeg_channels):
                # Detrend the data to remove constant offsets (DC components)
                DataFilter.detrend(data[channel], DetrendOperations.CONSTANT.value)

                # Apply a bandpass filter to isolate brainwave activity in the alpha band (8-13 Hz)
                DataFilter.perform_bandpass(
                    data[channel], self.sampling_rate, 8, 13, 4, FilterTypes.BUTTERWORTH_ZERO_PHASE, 0
                )

                # Apply a bandstop filter to remove powerline interference (e.g., 60 Hz noise)
                DataFilter.perform_bandstop(
                    data[channel], self.sampling_rate, 58.0, 62.0, 4, FilterTypes.BUTTERWORTH_ZERO_PHASE, 0

                )

            # Assuming left hand is C5,C3,C1 are channels 1,2,3 respectively
            right_hand_data = data[1] + data[2] + data[3]
            # right_hand_data = np.sum(data[0:3], axis=0)


            # Assuming right hand is C2,C4,C6 are channels 4,5,6 respectively
            left_hand_data = data[4] + data[5] + data[6]
            # left_hand_data = np.sum(data[3:6], axis=0)


            self.curves[0].setData( left_hand_data.tolist())


            self.curves[1].setData( right_hand_data.tolist())



            self.app.processEvents()


def main():
    BoardShim.enable_dev_board_logger()
    logging.basicConfig(level=logging.DEBUG)   #ALL THIS IS, IS ENABLING LOG FILES, FOR IF SOMETHING GOES WRONG, IT SHOWS THE LOG OF WHAT HAPPEND


    # Essentially a allows you to run custom parameters of the board from command line, otherwise you can set this up with the parser,
    # Keep this as this allows for better flexibility by changing commands via cmd rather than changing the internal code each time
    parser = argparse.ArgumentParser()


    # use docs to check which parameters are required for specific board, e.g. for Cyton - set serial port
    parser.add_argument('--timeout', type=int, help='timeout for device discovery or connection', required=False, default=15)
    parser.add_argument('--ip-port', type=int, help='ip port', required=False, default=0)
    parser.add_argument('--ip-protocol', type=int, help='ip protocol, check IpProtocolType enum', required=False,
                        default=0)
    parser.add_argument('--ip-address', type=str, help='ip address', required=False, default='')
    parser.add_argument('--serial-port', type=str, help='serial port', required=False, default='COM4')
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

    all_commands = [
    "chon_1_12",  # Enable channel 1 with gain 12
    "rldadd_1",   # Toggle right leg drive for channel 1  (THIS IS THE EARLOBE REFERENCE FOR CHANNEL 1)
    "chon_2_12",  # Enable channel 2 with gain 12
    "rldadd_2",   # Toggle right leg drive for channel 2  (THIS IS THE EARLOBE REFERENCE FOR CHANNEL 2)
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


    board = BoardShim(args.board_id, params)
    try:

        board.prepare_session()                               #this is just starting turning on board to read
        eeg_channels = board.get_eeg_channels(args.board_id)
        print(board.get_sampling_rate(board.board_id))
        print("EEG Channels:", eeg_channels)

        board.start_stream(450000, args.streamer_params)
        time.sleep(2)

        for command in all_commands:
                board.config_board(command)  # Send the command to the board
                print(f"Sent command: {command}")
                time.sleep(0.5)  # Wait 0.5 second before sending the next command

        Graph(board)


    except BaseException:
        logging.warning('Exception', exc_info=True)
    finally:
        logging.info('End')
        if board.is_prepared():
            logging.info('Releasing session')
            board.release_session()


if __name__ == '__main__':
    main()


