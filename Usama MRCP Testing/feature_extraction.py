#FEATURE EXTRACTION
import numpy as np
from mne.decoding import CSP
from scipy.signal import detrend
from sklearn.preprocessing import StandardScaler
from joblib import dump

# ====== Load Preprocessed EEG ======

import os

# Always get the real directory of the current script
#script_dir = os.path.dirname(os.path.abspath(__file__))
script_dir = r"C:\Users\rashe\source\repos\MINDUofC\MINDEEG\Usama MRCP Testing\calibration_data"
file_path = os.path.join(script_dir, "three_class_clench_trials_from_pause.npz")

print("🔍 Loading from:", file_path)
data = np.load(file_path)



csp_data = data["csp"]        # shape: (n_trials, 8, 375)
mrcp_data = data["mrcp"]      # shape: (n_trials, 8, 375)
labels = data["labels"]       # shape: (n_trials,)

# ====== CSP Feature Extraction ======
print("Extracting CSP features...")

# Fit CSP (1-vs-rest by default in MNE)
csp = CSP(n_components=4, log=True)
X_csp = csp.fit_transform(csp_data, labels)  # shape: (n_trials, 4)


# ====== MRCP Feature Extraction ======
print("Extracting MRCP features...")

C3_idx, C4_idx, Cz_idx = 0, 1, 2
fs = 125  # Sampling rate

X_mrcp = []
for trial in mrcp_data:
    c3 = trial[C3_idx]
    c4 = trial[C4_idx]
    cz = trial[Cz_idx]
    avg_signal = (c3 + c4 + cz) / 3.0

    # Feature 1: Peak negativity
    min_val = np.min(avg_signal)

    # Feature 2: Time to peak (sec)
    min_idx = np.argmin(avg_signal)
    time_to_peak = min_idx / fs

    # Feature 3: Slope to peak
    slope = (avg_signal[min_idx] - avg_signal[0]) / (min_idx + 1e-5)

    # Feature 4: Area under curve (AUC)
    auc = np.trapz(avg_signal)

    X_mrcp.append([min_val, time_to_peak, slope, auc])

X_mrcp = np.array(X_mrcp)  # shape: (n_trials, 4)

# ====== Normalize Features (Recommended) ======
scaler_csp = StandardScaler()
scaler_mrcp = StandardScaler()

X_csp = scaler_csp.fit_transform(X_csp)
X_mrcp = scaler_mrcp.fit_transform(X_mrcp)


# Save CSP model and scalers
dump(csp, os.path.join(script_dir, "trained_csp.pkl"))
dump(scaler_csp, os.path.join(script_dir, "scaler_csp.pkl"))
dump(scaler_mrcp, os.path.join(script_dir, "scaler_mrcp.pkl"))


# ====== Combine CSP + MRCP Features ======
X_combined = np.hstack((X_csp, X_mrcp))  # shape: (n_trials, 8)

# ====== Final Output ======
print("✅ Features ready!")
print("X_csp shape:", X_csp.shape)
print("X_mrcp shape:", X_mrcp.shape)
print("X_combined shape:", X_combined.shape)
print("Labels shape:", labels.shape)


# Save features
np.savez(os.path.join(script_dir, "features_ready.npz"),
         X_csp=X_csp,
         X_mrcp=X_mrcp,
         X_combined=X_combined,
         labels=labels)

print("💾 All files saved to:", script_dir)

