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




def main():
    param = BrainFlowInputParams()
    param.serial_port = "COM4"
    param.timeout = 15



    board_id = BoardIds.NEUROPAWN_KNIGHT_BOARD.value

    board = BoardShim(board_id,param)
    board.get_eeg_channels(board_id)

    board.prepare_session(1000)
    board.start_stream()
    # Number of data points to retrieve
    num_samples = 30  # For 1 second at 30 Hz

    # Fetch the data
    data = board.get_current_board_data(num_samples)
    print(data)
    # The 'data' variable is a 2D NumPy array with shape (num_channels, num_samples)


main()







