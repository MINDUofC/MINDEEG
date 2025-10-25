# plot_normalized_powers_with_cues.py
# Load the NPZ saved by collect_continuous_with_markers.py
# Plot all channels' normalized alpha power on ONE plot,
# and overlay cue markers with colors:
#   Right = blue, Left = red, Both = pink

import argparse
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

CUE_COLOR_MAP = {
    "right": "blue",
    "left":  "red",
    "both":  "pink",
}
CODE_TO_LABEL = {0: "left", 1: "right", 3: "both"}  # fallback if labels missing

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", dest="npz_path", type=str, default=r"C:\Users\rashe\source\repos\MINDUofC\MINDEEG\Usama MRCP Testing\calibration_data\continuous_filtered_streams_with_markers.npz",
                help="Path to the NPZ (default points to your calibration_data file)")
    ap.add_argument("--ch-alpha", type=float, default=0.9, help="Line alpha for channels")
    ap.add_argument("--cue-alpha", type=float, default=0.6, help="Line alpha for cue markers")
    ap.add_argument("--lw", type=float, default=0.9, help="Line width for channel traces")
    ap.add_argument("--cue-lw", type=float, default=1.2, help="Line width for cue lines")
    ap.add_argument("--title", type=str, default="Normalized α power (8–13 Hz) with cues")
    ap.add_argument("--save", type=str, default="", help="Optional path to save the figure (e.g., plot.png)")
    args = ap.parse_args()

    d = np.load(args.npz_path, allow_pickle=True)

    # ----- Required arrays -----
    pn = d.get("power_norm", None)         # (n_ch, T)
    if pn is None or pn.size == 0:
        raise RuntimeError("power_norm not found or empty in NPZ.")

    T = pn.shape[1]
    fs = float(d.get("sr_ts", 0.0)) or 0.0
    t_arr = d.get("timestamps_s", None)
    if t_arr is not None and t_arr.size == T:
        t = t_arr.ravel()
    else:
        # fallback to uniform time if timestamps missing
        if fs <= 0:
            raise RuntimeError("No timestamps and sr_ts <= 0; cannot build time axis.")
        t = np.arange(T, dtype=float) / fs

    chan_names = d.get("chan_names", None)
    if chan_names is None or chan_names.size != pn.shape[0]:
        # Fallback generic names
        chan_names = np.array([f"ch{i}" for i in range(pn.shape[0])], dtype=object)

    # ----- Cue arrays -----
    event_indices = d.get("event_indices", np.array([], dtype=int))
    event_labels  = d.get("event_labels",  np.array([], dtype=object))
    event_codes   = d.get("event_codes",   np.array([], dtype=int))

    # Normalize/resolve labels
    labels_resolved = []
    if event_labels is not None and event_labels.size == event_indices.size:
        labels_resolved = [str(x).lower() for x in event_labels.tolist()]
    elif event_codes is not None and event_codes.size == event_indices.size:
        labels_resolved = [CODE_TO_LABEL.get(int(c), "unknown") for c in event_codes.tolist()]
    else:
        labels_resolved = []

    # ----- Plot -----
    fig, ax = plt.subplots(figsize=(12, 6))

    # Color each channel distinctly
    n_ch = pn.shape[0]
    # tab10 is good up to 10 distinct hues; for more, use tab20 or hsv as a fallback
    cmap = plt.cm.get_cmap("tab10", max(10, n_ch))
    colors = [cmap(i % cmap.N) for i in range(n_ch)]

    for i in range(n_ch):
        ax.plot(t, pn[i], label=str(chan_names[i]), lw=args.lw, alpha=args.ch_alpha, color=colors[i])

    # Cues as vertical dashed lines with requested colors
    if event_indices is not None and event_indices.size > 0:
        for k, idx in enumerate(event_indices):
            if 0 <= idx < T:
                x = t[idx]
                lbl = labels_resolved[k] if k < len(labels_resolved) else "unknown"
                color = CUE_COLOR_MAP.get(lbl, "gray")
                ax.axvline(x, color=color, ls="--", lw=args.cue_lw, alpha=args.cue_alpha)

        # Add cue legend entries (proxies)
        cue_handles = [
            Line2D([0], [0], color=CUE_COLOR_MAP["right"], lw=args.cue_lw, ls="--", alpha=args.cue_alpha, label="Right cue"),
            Line2D([0], [0], color=CUE_COLOR_MAP["left"],  lw=args.cue_lw, ls="--", alpha=args.cue_alpha, label="Left cue"),
            Line2D([0], [0], color=CUE_COLOR_MAP["both"],  lw=args.cue_lw, ls="--", alpha=args.cue_alpha, label="Both cue"),
        ]
        # Combine with channel legend
        ch_legend = ax.legend(loc="upper left", ncols=2, fontsize=9, title="Channels")
        ax.add_artist(ch_legend)
        ax.legend(handles=cue_handles, loc="upper right", fontsize=9, title="Cues")
    else:
        ax.legend(loc="upper left", ncols=2, fontsize=9, title="Channels")

    ax.set_title(args.title)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Normalized α power (α_power / baseline_power)")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    if args.save:
        fig.savefig(args.save, dpi=150, bbox_inches="tight")
        print(f"Saved figure to: {args.save}")
    else:
        plt.show()

if __name__ == "__main__":
    main()
