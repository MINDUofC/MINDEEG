# plot_norm_powers_and_features.py
# Plot all normalized powers per channel + cue markers
# Plot derived features (XRH, YRHU, YRHL, XLH, YLHU, YLHL) + markers

import numpy as np
import matplotlib.pyplot as plt

# ====== Path to your saved file ======
infile = r"C:\Users\rashe\source\repos\MINDUofC\MINDEEG\Usama MRCP Testing\calibration_data\continuous_filtered_streams_with_markers.npz"

d = np.load(infile, allow_pickle=True)

chan_names   = [str(x) for x in d["chan_names"]]
norm_power   = d["raw_power"]      # (n_ch, T)
timestamps_s = d["timestamps_s"][0] if "timestamps_s" in d and d["timestamps_s"].size else np.arange(norm_power.shape[1])
event_idx    = d["event_indices"]
event_labels = [str(x) for x in d["event_labels"]]

# ====== Figure 1: normalized power per channel ======
plt.figure(figsize=(14, 7))
T = norm_power.shape[1]
for ci, nm in enumerate(chan_names):
    plt.plot(timestamps_s, norm_power[ci], label=nm)

# Markers
for idx, lbl in zip(event_idx, event_labels):
    t = timestamps_s[idx] if idx < len(timestamps_s) else timestamps_s[-1]
    color = {'right':'blue','left':'red','both':'pink'}.get(lbl, 'k')
    plt.axvline(t, color=color, alpha=0.4, linewidth=1.5)

plt.title("Normalized Power per Channel (alpha^2 / raw^2)")
plt.xlabel("Time (s)")
plt.ylabel("Normalized Power")
plt.legend(ncol=4, fontsize=9)
plt.grid(True, alpha=0.3)

# ====== Figure 2: derived features ======
def get(name):
    return d[name][0] if name in d and d[name].size else np.zeros_like(timestamps_s, dtype=np.float32)

XRH  = get("XRH")
YRHU = get("YRHU")
YRHL = get("YRHL")
XLH  = get("XLH")
YLHU = get("YLHU")
YLHL = get("YLHL")

plt.figure(figsize=(14, 7))
plt.plot(timestamps_s, XRH,  label="XRH  = |(C2−C4)/C4|")
plt.plot(timestamps_s, YRHU, label="YRHU = |(FC4−C4)/C4|")
plt.plot(timestamps_s, YRHL, label="YRHL = |(CP4−C4)/C4|")
plt.plot(timestamps_s, XLH,  label="XLH  = |(C1−C3)/C3|")
plt.plot(timestamps_s, YLHU, label="YLHU = |(FC3−C3)/C3|")
plt.plot(timestamps_s, YLHL, label="YLHL = |(CP3−C3)/C3|")

for idx, lbl in zip(event_idx, event_labels):
    t = timestamps_s[idx] if idx < len(timestamps_s) else timestamps_s[-1]
    color = {'right':'blue','left':'red','both':'pink'}.get(lbl, 'k')
    plt.axvline(t, color=color, alpha=0.4, linewidth=1.5)

plt.title("Derived Features (normalized power contrasts)")
plt.xlabel("Time (s)")
plt.ylabel("Absolute Ratio")
plt.legend(ncol=3, fontsize=9)
plt.grid(True, alpha=0.3)

plt.tight_layout()
plt.show()
