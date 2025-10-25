# plot_filtered_with_markers.py
# Show three separate graphs (0.05–5, 8–13, 14–30).
# Each: thin solid lines per electrode (different colors),
# right-hemisphere channels (FC4,C4,CP4,C2) are dotted.
# Dashed vertical lines mark cues: red=left, blue=right, pink=both.

import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.cm import get_cmap

# ====== USER: point to saved NPZ ======
infile = r"C:\Users\rashe\source\repos\MINDUofC\MINDEEG\Usama MRCP Testing\calibration_data\continuous_filtered_streams_with_markers.npz"

d = np.load(infile, allow_pickle=True)

chan_names   = d["chan_names"].tolist()
sr           = float(d["sr_ts"])
timestamps_s = d["timestamps_s"][0] if d["timestamps_s"].size else None
f005_5       = d["filt_0p05_5"]
f8_13        = d["filt_8_13"]
f14_30       = d["filt_14_30"]

event_idx = d["event_indices"]
event_lbl = d["event_labels"].tolist()

# time axis (prefer device timestamps if present, else derive from sr)
if timestamps_s is not None and timestamps_s.size == f8_13.shape[1]:
    t = timestamps_s
else:
    T = f8_13.shape[1]
    t = np.arange(T, dtype=float) / (sr if sr > 0 else 1.0)

# per-electrode coloring
n_ch = f8_13.shape[0]
cmap = get_cmap("tab10") if n_ch <= 10 else get_cmap("tab20")
colors = [cmap(i % cmap.N) for i in range(n_ch)]

# right-hemisphere channels → dotted
right_hemi = {"FC4", "C4", "CP4", "C2"}

def plot_band(ax, sig, title):
    for ci, name in enumerate(chan_names):
        style = ":" if name.upper() in right_hemi else "-"   # dotted vs solid
        ax.plot(t, sig[ci], style, linewidth=0.8,
                label=name, color=colors[ci])
    ax.set_title(title)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Amplitude (a.u.)")

    # vertical dashed cue markers
    for idx, lbl in zip(event_idx, event_lbl):
        if idx < 0 or idx >= sig.shape[1]:
            continue
        x = t[idx]
        if lbl == "left":   color = "red"
        elif lbl == "right": color = "blue"
        else:                color = "pink"  # both
        ax.axvline(x, linestyle="--", linewidth=1.2, color=color, alpha=0.9)

    # compact legend
    if n_ch <= 10:
        ax.legend(loc="upper right", fontsize=8)
    else:
        ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=7, ncol=1)

fig1, ax1 = plt.subplots(figsize=(12, 4))
plot_band(ax1, f005_5, "0.05–5 Hz")

fig2, ax2 = plt.subplots(figsize=(12, 4))
plot_band(ax2, f8_13, "8–13 Hz (Alpha)")

fig3, ax3 = plt.subplots(figsize=(12, 4))
plot_band(ax3, f14_30, "14–30 Hz (Beta)")

plt.show()

