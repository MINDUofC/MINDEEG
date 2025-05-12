#DATA_COLLECT
import os
import time
import numpy as np
from brainflow.board_shim import BoardShim, BrainFlowInputParams
from brainflow.data_filter import DataFilter, FilterTypes, DetrendOperations

# ====== CONFIG ======
fs = 125
window_sec = 3
samples_per_trial = fs * window_sec
pre_clench_sec = 2
post_clench_sec = 2
pause_rest_sec = 4
trials_per_class = 20
labels = ['left', 'right']

label_to_class = {'left': 0, 'right': 1, 'rest': 2}


output_dir = r"C:\Users\rashe\source\repos\MINDUofC\MINDEEG\Usama MRCP Testing\calibration_data"
os.makedirs(output_dir, exist_ok=True)

# ====== INIT BOARD ======
BoardShim.enable_dev_board_logger()
params = BrainFlowInputParams()
params.serial_port = "COM3"
board_id = 57
board = BoardShim(board_id, params)

print("🔌 Preparing board session...")
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
print("📡 EEG Channels:", eeg_channels)

# ====== COLLECT TRIALS ======
trials = []
total_trials = trials_per_class * len(labels)
trial_counter = 1
start_time = time.time()

for label in labels:
    print(f"\n========== STARTING {label.upper()} TRIALS ==========")
    time.sleep(2)

    for i in range(trials_per_class):
        print(f"\nTrial {trial_counter}/{total_trials} — {label.upper()}")

        print("Reset... Next trial in:")
        for t in reversed(range(1, 4)):
            print(f"{t}...")
            time.sleep(1)

        print("🧘‍♂️ Relax and stay still...")
        time.sleep(pre_clench_sec)

        print("✊ CLENCH NOW!")
        time.sleep(post_clench_sec)

        # Collect movement EEG
        while board.get_board_data_count() < samples_per_trial:
            time.sleep(0.1)
        data = board.get_current_board_data(samples_per_trial)
        eeg = data[eeg_channels]

        trials.append({
            "label": label,
            "class_type": label_to_class[label],
            "raw_eeg": eeg
        })
        print(f"✔️ {label.upper()} trial {i+1} recorded")

        # ========== REST TRIAL from pause ==========
        print("😴 Collecting rest from inter-trial pause...")
        time.sleep(pause_rest_sec)

        while board.get_board_data_count() < samples_per_trial:
            time.sleep(0.1)
        rest_data = board.get_current_board_data(samples_per_trial)
        rest_eeg = rest_data[eeg_channels]

        trials.append({
            "label": "rest",
            "class_type": label_to_class["rest"],
            "raw_eeg": rest_eeg
        })
        print(f"✔️ REST trial {i+1} recorded from pause")

        trial_counter += 1

# ====== CLEANUP ======
board.stop_stream()
board.release_session()
print("🧠 Board session ended.")

# ====== FILTER & SAVE ======
filtered_data = {
    "labels": [],
    "class_types": [],
    "mrcp": [],
    "csp": []
}

for trial in trials:
    label = trial["label"]
    class_type = trial["class_type"]
    raw = np.copy(trial["raw_eeg"])
    mrcp_filtered = np.copy(raw)
    csp_filtered = np.copy(raw)

    for ch in range(raw.shape[0]):
        # Detrend (remove linear trend)
        DataFilter.detrend(mrcp_filtered[ch], DetrendOperations.LINEAR)
        DataFilter.detrend(csp_filtered[ch], DetrendOperations.LINEAR)
        DataFilter.perform_bandstop(mrcp_filtered[ch],BoardShim.get_sampling_rate(board_id), 58.0, 62.0, 4, FilterTypes.BUTTERWORTH_ZERO_PHASE.value,0)
        DataFilter.perform_bandstop(csp_filtered[ch],BoardShim.get_sampling_rate(board_id), 58.0, 62.0, 4, FilterTypes.BUTTERWORTH_ZERO_PHASE.value,0)
        DataFilter.perform_bandpass(mrcp_filtered[ch], fs, 0.05, 5.0, 4, FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)
        DataFilter.perform_bandpass(csp_filtered[ch], fs, 8.0, 30.0, 4, FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)

    filtered_data["labels"].append(label)
    filtered_data["class_types"].append(class_type)
    filtered_data["mrcp"].append(mrcp_filtered)
    filtered_data["csp"].append(csp_filtered)

filtered_data["labels"] = np.array(filtered_data["labels"])
filtered_data["class_types"] = np.array(filtered_data["class_types"])
filtered_data["mrcp"] = np.array(filtered_data["mrcp"])
filtered_data["csp"] = np.array(filtered_data["csp"])

filename = os.path.join(output_dir, "three_class_clench_trials_from_pause.npz")
np.savez(filename, **filtered_data)
print(f"✅ Saved filtered EEG data to: {filename}")

elapsed = time.time() - start_time
print(f"\n🕒 Calibration completed in {elapsed:.1f} seconds (~{elapsed/60:.1f} min)")


