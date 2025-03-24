import argparse
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
from brainflow.data_filter import DataFilter, FilterTypes, DetrendOperations
import numpy as np
import matplotlib.pyplot as plt 
import time 

BoardShim.enable_dev_board_logger()

parser = argparse.ArgumentParser()
# Define the required and optional arguments
parser.add_argument('--timeout', type=int, help='timeout for device discovery or connection', required=False, default=0)
parser.add_argument('--ip-port', type=int, help='ip port', required=False, default=0)
parser.add_argument('--serial-port', type=str, help='serial port', required=False, default='COM3')
parser.add_argument('--board-id', type=int, help='board id, check docs to get a list of supported boards', required=False, default=57)
args = parser.parse_args()

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

params = BrainFlowInputParams()
params.ip_port = args.ip_port
params.serial_port = args.serial_port
params.timeout = args.timeout

# Initialize and configure the board
board = BoardShim(args.board_id, params)
print("Starting Stream")
board.prepare_session()
board.start_stream()
time.sleep(2)
for command in commands:
    board.config_board(command)  # Send the command to the board
    print(f"Sent command: {command}")
    time.sleep(1)  # Wait 1 second before sending the next command
print("START")
t = 60
num_samples = t * 125 
time.sleep(t)
data = board.get_current_board_data (num_samples)
print("Ending stream")
board.stop_stream()
board.release_session()

print(type(data))
print(data.shape)

eeg_channels = board.get_eeg_channels(args.board_id)
print(eeg_channels)
eeg_data = data[eeg_channels]

try:
    for i in range(eeg_data.shape[0]):  # Loop through all EEG channels
        # Ensure data is not empty
        if eeg_data[i].size == 0:
            print(f"Channel {i} has no data.")
            continue

        # Apply notch filter (60 Hz)
        DataFilter.perform_bandstop(eeg_data[i], BoardShim.get_sampling_rate(args.board_id), 58, 62, 4,FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)

        # Apply bandpass filter (8-13 Hz)
        DataFilter.perform_bandpass(eeg_data[i], BoardShim.get_sampling_rate(args.board_id), 8, 13, 4,FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)

    plt.figure(figsize=(10, 6))  # Set the figure size

    for i in range(eeg_data.shape[0]):  # Iterate through each channel
        plt.plot(np.arange(eeg_data.shape[1]), eeg_data[i], label=f"Channel {i+1}")

    plt.title("EEG Data for All Channels")
    plt.xlabel("Time (samples)")
    plt.ylabel("Amplitude (uV)")
    plt.legend(loc="upper right")  # Add a legend to distinguish channels
    plt.grid(True)  # Optional: Add a grid for better readability
    plt.show()
    # Save EEG data to a text file
    np.savetxt("eeg_data.txt", eeg_data, delimiter=",", header="EEG Data", comments='')
    print("EEG data saved to eeg_data.txt")


except Exception as e:
    print("Error occurred during filtering:", e)


