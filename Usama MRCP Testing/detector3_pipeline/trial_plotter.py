# plot_21_band_class_channels.py
# - Loads four_class_clench_trials_from_pause.npz
# - For each band x class (Right, Left, Both), opens a separate window.
# - Dashed lines: each trial per channel (color-coded by channel).
# - Solid line: mean across trials for that channel (same color).
# - Legend shows 8 channel names (color → channel).

import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

# ====== Path to your saved file ======
NPZ_PATH = r"C:\Users\rashe\source\repos\MINDUofC\MINDEEG\Usama MRCP Testing\calibration_data\four_class_clench_trials_from_pause.npz"

# Bands to plot (must match keys in the NPZ)
BANDS = ["0.05-5", "8-30", "8-12", "12-16", "16-20", "20-26", "26-30"]

# Classes to plot (active classes only)
CLASSES = ["right", "left", "both"]

# Channel names (your wiring order)
CHAN_NAMES = ["FC4","C4","CP4","C2","C1","CP3","C3","FC3"]

# Line appearance
TRIAL_LS      = "--"   # dashed for individual trials
TRIAL_ALPHA   = 0.2
MEAN_LS       = "-"    # solid for per-channel mean
MEAN_LW       = 2.5

def main():
    if not os.path.exists(NPZ_PATH):
        raise FileNotFoundError(f"NPZ not found:\n{NPZ_PATH}")

    data = np.load(NPZ_PATH, allow_pickle=True)

    # Basic arrays
    labels = data["labels"]               # (n_trials,)
    sr_ts  = float(data["sr_ts"])         # sampling rate for time axis

    # Use first available band to get sample length
    first_band = next((b for b in BANDS if b in data.files), None)
    if first_band is None:
        raise KeyError("None of the requested bands were found in the NPZ.")
    n_samples = data[first_band].shape[-1]
    t = np.arange(n_samples) / sr_ts

    # Colors: take 8 distinct colors (tab10 colormap provides 10)
    tab10 = plt.get_cmap("tab10")
    ch_colors = [tab10(i) for i in range(8)]  # 8 channels → 8 colors

    # Safety check on channel dimension
    # Expect band arrays shaped: (n_trials_total, 8, N)
    for band in BANDS:
        if band not in data.files:
            print(f"[WARN] Band '{band}' not in NPZ. Skipping.")
            continue

        band_arr = data[band]
        if band_arr.ndim != 3 or band_arr.shape[1] != 8:
            raise ValueError(
                f"Band '{band}' has unexpected shape {band_arr.shape}; expected (n_trials, 8, N)."
            )

        for cls in CLASSES:
            mask = (labels == cls)
            if not np.any(mask):
                print(f"[INFO] No trials for class '{cls}' in band '{band}'. Skipping.")
                continue

            X = band_arr[mask]             # (n_trials_cls, 8, N)
            n_trials_cls = X.shape[0]
            n_channels   = X.shape[1]
            assert n_channels == 8, "Expected 8 EEG channels."

            # New window per (band, class)
            fig = plt.figure()
            ax  = fig.add_subplot(111)

            # Plot all trials per channel as dashed (same color per channel)
            for ch in range(n_channels):
                ch_trials = X[:, ch, :]    # (n_trials_cls, N)
                for i in range(n_trials_cls):
                    ax.plot(t, ch_trials[i], TRIAL_LS, alpha=TRIAL_ALPHA, color=ch_colors[ch])

                # Mean across trials for this channel
                ch_mean = ch_trials.mean(axis=0)
                ax.plot(t, ch_mean, MEAN_LS, linewidth=MEAN_LW, color=ch_colors[ch])

            # Axis labels, title, grid
            ax.set_xlabel("Time (s)")
            ax.set_ylabel("Amplitude (a.u.)")
            title = f"{band} — {cls.capitalize()}  |  Trials: {n_trials_cls}  |  fs≈{sr_ts:.2f} Hz"
            ax.set_title(title)
            ax.grid(True, alpha=0.3)

            # Legend: 8 entries mapping color → channel
            legend_handles = [
                Line2D([0], [0], color=ch_colors[ch], lw=MEAN_LW, linestyle=MEAN_LS, label=CHAN_NAMES[ch])
                for ch in range(n_channels)
            ]
            ax.legend(handles=legend_handles, title="Channels", ncol=4, frameon=True)

    # Show all windows (up to 21)
    plt.show()


if __name__ == "__main__":
    main()
