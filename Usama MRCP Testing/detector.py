import time
import numpy as np
import joblib
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
from brainflow.data_filter import DataFilter, FilterTypes
from scipy.signal import detrend

# ====== Load Trained Models ======
model = joblib.load("trained_model_1.pkl")
csp = joblib.load("../calibration_data/trained_csp.pkl")

# ====== Config ======
fs = 125
window_sec = 3
samples = fs * window_sec
C3_idx, C4_idx, Cz_idx = 0, 1, 2
serial_port = "COM3"
board_id = 57

params = BrainFlowInputParams()
params.serial_port = serial_port
board = BoardShim(board_id, params)

print("🔌 Preparing board...")
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

print("✅ Starting guided prediction loop... Press Ctrl+C to stop.")

try:
    trial_num = 1
    while True:
        print(f"\n🧠 Trial {trial_num}")
        print("⏳ Get ready...")

        for t in reversed(range(1, 4)):
            print(f"  Clench in {t}...")
            time.sleep(1)

        print("✊ CLENCH NOW!")
        clench_start = time.time()

        # Wait until enough samples are collected (3 seconds)
        while board.get_board_data_count() < samples:
            time.sleep(0.1)

        data = board.get_current_board_data(samples)
        eeg_channels = board.get_eeg_channels(board_id)
        raw = data[eeg_channels]

        # ====== Filter EEG ======
        csp_input = np.copy(raw)
        mrcp_input = np.copy(raw)

        for ch in range(raw.shape[0]):
            DataFilter.perform_bandpass(csp_input[ch], fs, 8, 30, 4, FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)
            DataFilter.perform_bandpass(mrcp_input[ch], fs, 0.05, 5.0, 4, FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)

        # ====== Extract Features ======
        csp_input = detrend(csp_input, axis=1)
        X_csp = csp.transform(csp_input[np.newaxis, :, :])[0]

        c3, c4, cz = mrcp_input[C3_idx], mrcp_input[C4_idx], mrcp_input[Cz_idx]
        avg_signal = (c3 + c4 + cz) / 3.0

        min_val = np.min(avg_signal)
        min_idx = np.argmin(avg_signal)
        time_to_peak = min_idx / fs
        slope = (avg_signal[min_idx] - avg_signal[0]) / (min_idx + 1e-5)
        auc = np.trapezoid(avg_signal)

        X_mrcp = [min_val, time_to_peak, slope, auc]

        # Combine features and predict
        X_live = np.hstack((X_csp, X_mrcp)).reshape(1, -1)
        pred = model.predict(X_live)[0]
        label = "🟥 LEFT HAND" if pred == 0 else "🟦 RIGHT HAND"
        print(f"🤖 Prediction: {label}")

        trial_num += 1
        time.sleep(2)  # short pause before next trial

except KeyboardInterrupt:
    print("\n🛑 Stopped by user.")

finally:
    board.stop_stream()
    board.release_session()
    print("🔌 Board session closed.")


