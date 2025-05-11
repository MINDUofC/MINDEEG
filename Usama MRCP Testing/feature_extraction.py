import numpy as np
from mne.decoding import CSP
from scipy.signal import detrend
from sklearn.preprocessing import StandardScaler
from joblib import dump


# ====== Load Preprocessed EEG ======
import os

# Always get the real directory of the current script
script_dir = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(script_dir, "three_class_clench_trials_from_pause.npz")

print("🔍 Loading from:", file_path)
data = np.load(file_path)

csp_data = data["csp"]        # shape: (n_trials, 8, 375)
mrcp_data = data["mrcp"]      # shape: (n_trials, 8, 375)
labels = data["class_types"]  # shape: (n_trials,) → values: 0 (left), 1 (right), 2 (rest)

print(f"Classes present: {np.unique(labels, return_counts=True)}")

# ====== CSP Feature Extraction ======
print("Extracting CSP features...")

csp_input = np.array([detrend(trial, axis=1) for trial in csp_data])

# Fit CSP (1-vs-rest by default in MNE)
csp = CSP(n_components=4, log=True)
X_csp = csp.fit_transform(csp_input, labels)  # shape: (n_trials, 4)

# Save CSP model for real-time use
dump(csp, "trained_csp.pkl")
print("💾 Trained CSP saved to calibration_data/trained_csp.pkl")

# ====== MRCP Feature Extraction ======
print("Extracting MRCP features...")

C3_idx, C4_idx, Cz_idx = 0, 1, 2
fs = 125

X_mrcp = []
for trial in mrcp_data:
    c3 = trial[C3_idx]
    c4 = trial[C4_idx]
    cz = trial[Cz_idx]
    avg_signal = (c3 + c4 + cz) / 3.0

    min_val = np.min(avg_signal)
    min_idx = np.argmin(avg_signal)
    time_to_peak = min_idx / fs
    slope = (avg_signal[min_idx] - avg_signal[0]) / (min_idx + 1e-5)
    auc = np.trapezoid(avg_signal)

    X_mrcp.append([min_val, time_to_peak, slope, auc])

X_mrcp = np.array(X_mrcp)

# ====== Normalize Features ======
scaler_csp = StandardScaler()
scaler_mrcp = StandardScaler()

X_csp = scaler_csp.fit_transform(X_csp)
X_mrcp = scaler_mrcp.fit_transform(X_mrcp)

dump(scaler_csp, "scaler_csp.pkl")
dump(scaler_mrcp, "scaler_mrcp.pkl")

# ====== Combine Features ======
X_combined = np.hstack((X_csp, X_mrcp))  # shape: (n_trials, 8)

# ====== Save Final Features ======
print("✅ Features ready!")
print("X_csp shape:", X_csp.shape)
print("X_mrcp shape:", X_mrcp.shape)
print("X_combined shape:", X_combined.shape)
print("Labels shape:", labels.shape)

np.savez("features_ready.npz", 
         X_csp=X_csp, 
         X_mrcp=X_mrcp, 
         X_combined=X_combined, 
         labels=labels)

print("💾 Saved features to calibration_data/features_ready.npz")

