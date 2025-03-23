import numpy as np
from mne.decoding import CSP
from scipy.signal import detrend
from sklearn.preprocessing import StandardScaler
from joblib import dump

# ====== Load Preprocessed EEG ======
data = np.load("../calibration_data/single_clench_trials.npz")
csp_data = data["csp"]        # shape: (n_trials, 8, 375)
mrcp_data = data["mrcp"]      # shape: (n_trials, 8, 375)
labels = data["labels"]       # shape: (n_trials,)

# ====== CSP Feature Extraction ======
print("Extracting CSP features...")

# Optional: detrend CSP input to remove DC offset
csp_input = np.array([detrend(trial, axis=1) for trial in csp_data])

# Fit CSP
csp = CSP(n_components=4, log=True)
X_csp = csp.fit_transform(csp_input, labels)  # Output: (n_trials, 4)

# Save CSP model for live use
dump(csp, "../calibration_data/trained_csp.pkl")
print("💾 Trained CSP saved to calibration_data/trained_csp.pkl")

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

dump(scaler_csp, "../calibration_data/scaler_csp.pkl")
dump(scaler_mrcp, "../calibration_data/scaler_mrcp.pkl")

# ====== Combine CSP + MRCP Features ======
X_combined = np.hstack((X_csp, X_mrcp))  # shape: (n_trials, 8)

# ====== Final Output ======
print("✅ Features ready!")
print("X_csp shape:", X_csp.shape)
print("X_mrcp shape:", X_mrcp.shape)
print("X_combined shape:", X_combined.shape)
print("Labels shape:", labels.shape)

# Optional: save for training
np.savez("../calibration_data/features_ready.npz", X_csp=X_csp, X_mrcp=X_mrcp, X_combined=X_combined, labels=labels)
print("💾 Saved features to calibration_data/features_ready.npz")
