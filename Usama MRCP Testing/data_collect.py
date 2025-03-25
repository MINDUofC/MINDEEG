import os
import time
import numpy as np
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
from brainflow.data_filter import DataFilter, FilterTypes

# ====== CONFIG ======
fs = 125
window_sec = 3               # Total trial window: 2s before + 1s after
samples_per_trial = fs * window_sec
pre_clench_sec = 2
post_clench_sec = 1
pause_between_trials = 2     # Pause after each trial
trials_per_class = 50
labels = ['left', 'right']
output_dir = "../calibration_data"
os.makedirs(output_dir, exist_ok=True)

# ====== INIT BOARD ======
BoardShim.enable_dev_board_logger()
params = BrainFlowInputParams()
params.serial_port = "COM3"
board_id = 57
board = BoardShim(board_id, params)

print("Preparing session...")
board.prepare_session()
board.start_stream()
time.sleep(2)

# ====== CONFIGURE EEG CHANNELS ======
commands = [
    "chon_1_12", "rldadd_1", "chon_2_12", "rldadd_2",
    "chon_3_12", "rldadd_3", "chon_4_12", "rldadd_4",
    "chon_5_12", "rldadd_5", "chon_6_12", "rldadd_6",
    "chon_7_12", "rldadd_7", "chon_8_12", "rldadd_8"
]
for cmd in commands:
    board.config_board(cmd)
    time.sleep(1)

eeg_channels = board.get_eeg_channels(board_id)
print("EEG Channels:", eeg_channels)

# ====== COLLECT TRIALS ======
trials = []

total_trials = trials_per_class * len(labels)
trial_counter = 1
start_time = time.time()

for label in labels:
    print(f"\n========== STARTING {label.upper()} HAND TRIALS ==========")
    time.sleep(2)

    for i in range(trials_per_class):
        print(f"\nTrial {trial_counter}/{total_trials} — {label.upper()} HAND")

        # Optional: inter-trial pause
        print(f"Reset... Next trial in:")
        for t in reversed(range(1, 4)):
            print(f"{t}...")
            time.sleep(1)

        # Pre-clench baseline collection (this is included in EEG window)
        print("🧘‍♂️ Relax and stay still...")
        time.sleep(pre_clench_sec)

        print("✊ CLENCH NOW!")
        time.sleep(post_clench_sec)

        # Collect EEG (whole 3-second window: 2s before + 1s after)
        data = board.get_current_board_data(samples_per_trial)
        eeg = data[eeg_channels]

        trials.append({
            "label": label,
            "raw_eeg": eeg
        })

        print(f"✔️ {label} hand trial {i+1} recorded")

        # Optional pause
        print("...pausing before next trial...")
        time.sleep(pause_between_trials)
        trial_counter += 1

# ====== CLEANUP ======
board.stop_stream()
board.release_session()

# ====== FILTER & SAVE ======
filtered_data = {
    "labels": [],
    "mrcp": [],
    "csp": []
}

for trial in trials:
    label = trial["label"]
    raw = np.copy(trial["raw_eeg"])
    mrcp_filtered = np.copy(raw)
    csp_filtered = np.copy(raw)

    for ch in range(raw.shape[0]):
        # MRCP: 0.05–5 Hz
        DataFilter.perform_bandpass(mrcp_filtered[ch], fs, 0.05, 5.0, 4, FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)
        # CSP/ERD: 8–30 Hz
        DataFilter.perform_bandpass(csp_filtered[ch], fs, 8.0, 30.0, 4, FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)

    filtered_data["labels"].append(0 if label == "left" else 1)
    filtered_data["mrcp"].append(mrcp_filtered)
    filtered_data["csp"].append(csp_filtered)

filtered_data["labels"] = np.array(filtered_data["labels"])
filtered_data["mrcp"] = np.array(filtered_data["mrcp"])  # shape: (n_trials, n_channels, 375)
filtered_data["csp"] = np.array(filtered_data["csp"])    # shape: (n_trials, n_channels, 375)

filename = os.path.join(output_dir, "single_clench_trials.npz")
np.savez(filename, **filtered_data)
print(f"✅ Saved EEG data to: {filename}")

# Print total time
elapsed = time.time() - start_time
print(f"\n🕒 Calibration complete in {elapsed:.1f} seconds (~{elapsed/60:.1f} min)")


