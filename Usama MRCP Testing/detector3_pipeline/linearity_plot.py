# plot_all_signals.py
# Plots:
#  1) EMA-filtered powers: XLH_P, YLH_P, XRH_P, YRH_P (solid, different colors)
#  2) Thetas (degrees 0..360): RH_theta, LH_theta (solid)
# Includes vertical dashed cue markers: red=left, blue=right, pink=both.

import numpy as np
import matplotlib.pyplot as plt

# ====== Path to your saved file ======
infile = r"C:\Users\rashe\source\repos\MINDUofC\MINDEEG\Usama MRCP Testing\calibration_data\continuous_filtered_streams_with_markers.npz"

# ====== Load ======
d = np.load(infile, allow_pickle=True)

# --- Time base ---
sr = float(d["sr_ts"]) if "sr_ts" in d else 0.0
ts = d["timestamps_s"][0] if "timestamps_s" in d and d["timestamps_s"].size else None

def get_1xT(name, default_len=None):
    if name in d and d[name].size:
        arr = d[name][0]
        return arr
    return np.zeros((default_len or 0,), dtype=float)

# Pull signals (gracefully handle absent arrays)
XLH_P = get_1xT("XLH_P")
YLH_P = get_1xT("YLH_P", default_len=XLH_P.shape[0] if XLH_P.size else None)
XRH_P = get_1xT("XRH_P", default_len=XLH_P.shape[0] if XLH_P.size else None)
YRH_P = get_1xT("YRH_P", default_len=XLH_P.shape[0] if XLH_P.size else None)

RH_theta = get_1xT("RH_theta", default_len=XLH_P.shape[0] if XLH_P.size else None)
LH_theta = get_1xT("LH_theta", default_len=XLH_P.shape[0] if XLH_P.size else None)

# Time vector
T = int(max(XLH_P.size, YLH_P.size, XRH_P.size, YRH_P.size, RH_theta.size, LH_theta.size))
if T == 0:
    raise RuntimeError("No data to plot. Check that your NPZ contains the EMA powers or theta arrays.")

if ts is not None and ts.size == T:
    t = ts
else:
    t = np.arange(T, dtype=float) / (sr if sr > 0 else 1.0)

# Cues
event_idx = d["event_indices"] if "event_indices" in d else np.array([], dtype=int)
event_lbl = d["event_labels"].tolist() if "event_labels" in d else []

def add_cue_lines(ax):
    for idx, lbl in zip(event_idx, event_lbl):
        if 0 <= idx < T:
            x = t[idx]
            if lbl == "left":
                color = "red"
            elif lbl == "right":
                color = "blue"
            else:
                color = "pink"  # both
            ax.axvline(x, linestyle="--", linewidth=1.2, color=color, alpha=0.9)

# ====== Figure 1: EMA Powers ======
fig1, ax1 = plt.subplots(figsize=(13, 5))
plotted_any = False

if XLH_P.size:
    ax1.plot(t, XLH_P, label="XLH_P", linewidth=1.2)  # solid
    plotted_any = True
if YLH_P.size:
    ax1.plot(t, YLH_P, label="YLH_P", linewidth=1.2)
    plotted_any = True
if XRH_P.size:
    ax1.plot(t, XRH_P, label="XRH_P", linewidth=1.2)
    plotted_any = True
if YRH_P.size:
    ax1.plot(t, YRH_P, label="YRH_P", linewidth=1.2)
    plotted_any = True

add_cue_lines(ax1)
ax1.set_title("EMA-filtered Powers (|v|·v) of X/Y Combos")
ax1.set_xlabel("Time (s)")
ax1.set_ylabel("Power (a.u.)")
ax1.grid(True, alpha=0.25)
if plotted_any:
    ax1.legend(loc="upper right")
fig1.tight_layout()

# ====== Figure 2: Thetas (degrees) ======
fig2, ax2 = plt.subplots(figsize=(13, 4.5))

if RH_theta.size:
    ax2.plot(t, RH_theta, label="RH_theta (atan2(YRH_P, XRH_P))", linewidth=1.2)
if LH_theta.size:
    ax2.plot(t, LH_theta, label="LH_theta (atan2(YLH_P, XLH_P))", linewidth=1.2)

add_cue_lines(ax2)
ax2.set_title("Theta Angles (degrees, 0–360)")
ax2.set_xlabel("Time (s)")
ax2.set_ylabel("Degrees")
ax2.set_ylim(-5, 365)  # small padding around 0..360
ax2.grid(True, alpha=0.25)
ax2.legend(loc="upper right")
fig2.tight_layout()

plt.show()
