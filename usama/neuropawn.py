# import numpy as np
# from brainflow.data_filter import DataFilter, FilterTypes
# from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
# import matplotlib.pyplot as plt
# import time

# # Set up parameters
# params = BrainFlowInputParams()
# params.serial_port = "COM5"
# knight_board = BoardIds.NEUROPAWN_KNIGHT_BOARD

# try:
#     board = BoardShim(knight_board, params)
#     board.prepare_session()
#     print("Successfully Prepared physical board")
#     board_id = board.get_board_id()
#     print("Connected Board ID:", board_id)
#     sampling_rate = BoardShim.get_sampling_rate(board_id)
#     print("Sampling Rate:", sampling_rate)
# except Exception as e:
#     print(e)
#     print("Error")
#     exit()

# # Get EEG channels
# eeg_channels = board.get_eeg_channels(board_id)
# print("EEG Channels:", eeg_channels)


# # Start streaming
# print("Starting Stream")
# board.start_stream()
# t = 10 
# time.sleep(t)  # Allow time for data accumulation

# # Get data
# num_smaples = t * 125
# data = board.get_current_board_data(num_smaples)
# print("Data Snapshot (10 seconds):", data)

# # Stop stream
# board.stop_stream()
# board.release_session()

# # Extract EEG data and filter
# eeg_data = data[eeg_channels]

# # Save EEG data to a text file
# np.savetxt("eeg_data.txt", eeg_data, delimiter=",", header="EEG Data", comments='')
# print("EEG data saved to eeg_data.txt")

# # Plot EEG data from the first channel
# plt.plot(np.arange(eeg_data.shape[1]), eeg_data[0])
# plt.title("EEG Channel 1 (Filtered)")
# plt.xlabel("Time (samples)")
# plt.ylabel("Amplitude (uV)")
# plt.show()

import numpy as np
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
import time

params = BrainFlowInputParams()
params.serial_port = "COM5"  #change this value on laptop
board = BoardShim(BoardIds.NEUROPAWN_KNIGHT_BOARD, params)
eeg_channels = board.get_eeg_channels(BoardIds.NEUROPAWN_KNIGHT_BOARD)
print("EEG Channels:", eeg_channels)

try:
    board.prepare_session()
    board.start_stream()
    time.sleep(5)
    print("Collecting data for 5 seconds...")
    board_data = board.get_current_board_data(625)  # 5 seconds of data at 125 Hz
    eeg_data = board_data[eeg_channels]
    print("EEG Data Shape:", eeg_data.shape)
    print("EEG Data Sample:", eeg_data)
    print("Data collected:")
    print(board_data)
    board.stop_stream()
    board.release_session()
except Exception as e:
    print("Error:", e)










