# collect_continuous_with_markers.py
# Live, stateful SciPy filters. Store per-electrode baseline power (notch60 + low-pass),
# alpha-band power (8–13 Hz), and normalized power = alpha_power / baseline_power.
# After collection, plot normalized power for each electrode.

import os, time, random
import numpy as np
import matplotlib.pyplot as plt
from brainflow.board_shim import BoardShim, BrainFlowInputParams
from scipy.signal import butter, sosfilt, sosfilt_zi, iirnotch, tf2sos

# ====== USER CONFIG ======
board_id            = 57
serial_port         = "COM3"
PROMPT_COUNTS       = False
TRIALS_PER_CLASS_DEFAULT = {'left': 5, 'right': 5, 'both': 5}
TRIAL_LENGTH_SECS   = 3
STEP_SAMPLES        = 1

# Cleaning/filtering
LINE_FREQ_HZ = 60.0     # notch target
NOTCH_Q      = 30.0     # quality factor for iirnotch (higher = narrower)
LP_CUT_HZ    = 45.0     # low-pass cutoff for baseline path (Butterworth)
BP_BAND_HZ   = (8.0, 13.0)  # alpha band (Butterworth)
FILTER_ORDER = 4

# Paths
output_dir = r"C:\Users\rashe\source\repos\MINDUofC\MINDEEG\Usama MRCP Testing\calibration_data"
os.makedirs(output_dir, exist_ok=True)
outfile = os.path.join(output_dir, "continuous_filtered_streams_with_markers.npz")

# Channel order (index 0..7)
chan_names  = ["FC4","C4","CP4","C2","C1","CP3","C3","FC3"]

labels = ['left', 'right', 'both']
label_to_code = {'left':0, 'right':1, 'both':3}

# Build name->index + hemisphere groups (for local average reference)
name_to_idx = {n.upper(): i for i, n in enumerate(chan_names)}
RIGHT = [name_to_idx[x] for x in ["FC4","C4","CP4","C2"] if x in name_to_idx]
LEFT  = [name_to_idx[x] for x in ["FC3","C3","CP3","C1"] if x in name_to_idx]

# ====== helpers ======
def estimate_fs_from_timestamps(ts: np.ndarray, fs_declared: float) -> float:
    if ts.size >= 2:
        dts = np.diff(ts)
        dts = dts[dts > 0]
        if dts.size:
            return float(1.0 / np.mean(dts))
    return float(fs_declared)

def append_chunk(buf: np.ndarray, chunk: np.ndarray) -> np.ndarray:
    if buf is None or buf.size == 0: return chunk.copy()
    return np.concatenate([buf, chunk], axis=1)

# ====== board setup ======
BoardShim.enable_dev_board_logger()
params = BrainFlowInputParams()
params.serial_port = serial_port
board = BoardShim(board_id, params)

print("🔌 Preparing board session…")
board.prepare_session()
board.start_stream()
time.sleep(3.0)

# (optional) your per-channel commands
commands = [
    "chon_1_12", "rldadd_1", "chon_2_12", "rldadd_2",
    "chon_3_12", "rldadd_3", "chon_4_12", "rldadd_4",
    "chon_5_12", "rldadd_5", "chon_6_12", "rldadd_6",
    "chon_7_12", "rldadd_7", "chon_8_12", "rldadd_8"
]
for cmd in commands:
    board.config_board(cmd)
    time.sleep(1.0)

time.sleep(2.0)
board.get_board_data()  # clear buffer after cfg
time.sleep(2.0)

# ====== channels & SR ======
sr_decl = BoardShim.get_sampling_rate(board_id)
ts_ch   = BoardShim.get_timestamp_channel(board_id)
eeg_channels = board.get_eeg_channels(board_id)

buf = board.get_current_board_data(sr_decl * 5)
ts = buf[ts_ch] if buf.size and ts_ch < buf.shape[0] else np.array([])
sr_ts = estimate_fs_from_timestamps(ts, sr_decl)
fs = float(sr_ts)  # use timestamp-estimated fs
print("EEG channel indices:", eeg_channels)
print("Assumed names:", chan_names)
print(f"Declared SR = {sr_decl} Hz | Estimated SR ≈ {fs:.2f} Hz")
print(f"Live step size = {STEP_SAMPLES} samples")

n_ch = len(eeg_channels)
nyq = 0.5 * fs

# ====== Design filters (SOS) ======
def butter_sos_lowpass(cut_hz, order=4):
    wp = cut_hz / nyq
    return butter(order, wp, btype='lowpass', output='sos')

def butter_sos_bandpass(lo_hz, hi_hz, order=4):
    wp = [max(lo_hz, 0.001)/nyq, min(hi_hz, nyq*0.9999)/nyq]
    return butter(order, wp, btype='bandpass', output='sos')

# 60 Hz notch via iirnotch -> SOS
b_notch, a_notch = iirnotch(w0=LINE_FREQ_HZ/nyq, Q=NOTCH_Q)
sos_notch = tf2sos(b_notch, a_notch)

sos_lp    = butter_sos_lowpass(LP_CUT_HZ, FILTER_ORDER)
sos_alpha = butter_sos_bandpass(BP_BAND_HZ[0], BP_BAND_HZ[1], FILTER_ORDER)

# Per-channel IIR states
zi_notch  = [sosfilt_zi(sos_notch) for _ in range(n_ch)]
zi_lp     = [sosfilt_zi(sos_lp)    for _ in range(n_ch)]
zi_alpha  = [sosfilt_zi(sos_alpha) for _ in range(n_ch)]

# ====== growing buffers ======
raw_buf        = None       # (n_ch, T) raw (unreferenced)
ts_buf         = None       # (1, T) seconds

# cleaned signal (after notch+LP) if you want to inspect later (optional)
clean_buf      = None       # (n_ch, T)
alpha_buf      = None       # (n_ch, T)

# powers
power_baseline = None       # (n_ch, T)  (after notch+LP)**2
power_alpha    = None       # (n_ch, T)  (alpha-band)**2
power_norm     = None       # (n_ch, T)  alpha_power / (baseline_power+eps)

total_samples = 0

# Cue markers
event_indices, event_codes, event_labels = [], [], []

EPS = 1e-12

def process_live_chunk(eeg_chunk: np.ndarray, ts_chunk: np.ndarray):
    """Append and filter incoming chunk (n_ch,k), timestamps (1,k)."""
    global raw_buf, ts_buf, clean_buf, alpha_buf
    global power_baseline, power_alpha, power_norm, total_samples
    global zi_notch, zi_lp, zi_alpha

    # keep raw
    raw_buf = append_chunk(raw_buf, eeg_chunk)
    ts_buf  = append_chunk(ts_buf, ts_chunk[None, :])

    k = eeg_chunk.shape[1]
    start = 0
    while start < k:
        end = min(start + STEP_SAMPLES, k)
        step = eeg_chunk[:, start:end]   # (n_ch, m)
        ts_step = ts_chunk[start:end]    # (m,)
        m = step.shape[1]

        # ---------- LOCAL AVERAGE REFERENCE (per hemisphere) ----------
        step_ref = step.copy()
        if len(RIGHT) > 0:
            rmean = step_ref[RIGHT].mean(axis=0, keepdims=True)
            step_ref[RIGHT] = step_ref[RIGHT] - rmean
        if len(LEFT) > 0:
            lmean = step_ref[LEFT].mean(axis=0, keepdims=True)
            step_ref[LEFT] = step_ref[LEFT] - lmean
        # --------------------------------------------------------------

        # ---------- CLEAN PATH: notch 60 -> low-pass ----------
        out_clean = np.zeros_like(step_ref)
        for ci in range(n_ch):
            y1, zi_notch[ci] = sosfilt(sos_notch, step_ref[ci], zi=zi_notch[ci])
            y2, zi_lp[ci]    = sosfilt(sos_lp,    y1,           zi=zi_lp[ci])
            out_clean[ci]    = y2
        clean_buf = append_chunk(clean_buf, out_clean)

        # baseline instantaneous power (square)
        p_base = out_clean**2

        # ---------- ALPHA PATH: band-pass 8–13 applied to cleaned ----------
        out_alpha = np.zeros_like(out_clean)
        for ci in range(n_ch):
            ya, zi_alpha[ci] = sosfilt(sos_alpha, out_clean[ci], zi=zi_alpha[ci])
            out_alpha[ci]    = ya
        alpha_buf = append_chunk(alpha_buf, out_alpha)

        p_alpha = out_alpha**2

        # normalize (per sample, per channel)
        p_norm = p_alpha / (p_base + EPS)

        power_baseline = append_chunk(power_baseline, p_base)
        power_alpha    = append_chunk(power_alpha,    p_alpha)
        power_norm     = append_chunk(power_norm,     p_norm)

        total_samples += m
        start = end

def pump_for(secs: float):
    t_end = time.time() + secs
    while time.time() < t_end:
        new = board.get_board_data()
        if new.size == 0:
            time.sleep(0.002)
            continue
        eeg = new[eeg_channels]
        if eeg.ndim == 1: eeg = eeg[:, None]
        ts  = new[ts_ch]
        if ts.ndim == 0:  ts = ts[None]
        process_live_chunk(eeg, ts)

# ====== trial pacing / cue logging only ======
trials_per_class_map = dict(TRIALS_PER_CLASS_DEFAULT)
if PROMPT_COUNTS:
    print("\n=== Per-class trial counts ===")
    for lbl in labels:
        try:
            s = input(f"Number of {lbl.upper()} trials [{trials_per_class_map[lbl]}]: ").strip()
            if s != "": trials_per_class_map[lbl] = int(s)
        except Exception:
            print("  (Using default)")
    print("==============================\n")

for k, v in trials_per_class_map.items():
    if v <= 0:
        raise ValueError(f"Trial count for '{k}' must be > 0 (got {v}).")

# Warmup
pump_for(2.0)

remaining = {lbl: trials_per_class_map[lbl] for lbl in labels}
done      = {lbl: 0 for lbl in labels}
print(f"\nPlanned cues by class: {trials_per_class_map}")
print(f"Total cues: {sum(remaining.values())}")
print("Randomized schedule with ~4-second cadence per cue.")

try:
    while sum(remaining.values()) > 0:
        choices = [lbl for lbl in labels if remaining[lbl] > 0]
        lbl = random.choice(choices)

        print(f"\n➡️  Get ready: {lbl.upper()} — in 4…"); pump_for(1.0)
        print("3…"); pump_for(1.0)
        print("2…"); pump_for(1.0)

        print("1 ✊ CLENCH — marking cue (no slicing)…")
        start_idx = total_samples
        event_indices.append(start_idx)
        event_codes.append(label_to_code[lbl])
        event_labels.append(lbl)

        pump_for(TRIAL_LENGTH_SECS)

        remaining[lbl] -= 1
        done[lbl] += 1
        tgt = trials_per_class_map
        print("✔️  Marked:", lbl.upper())
        print(f"Progress — Right {done['right']}/{tgt['right']} | Left {done['left']}/{tgt['left']} | Both {done['both']}/{tgt['both']}")

finally:
    board.stop_stream()
    board.release_session()
    print("🧠 Board session ended.")

# ====== Pack & Save ======
n_ch = len(eeg_channels)
save_dict = {
    "chan_names":   np.array(chan_names, dtype=object),
    "eeg_channels": np.array(eeg_channels, dtype=np.int32),
    "sr_decl":      np.int32(sr_decl),
    "sr_ts":        np.float32(fs),
    "step_samples": np.int32(STEP_SAMPLES),

    # continuous raw + timestamps
    "raw":          (raw_buf.astype(np.float32) if raw_buf is not None else np.zeros((n_ch,0), np.float32)),
    "timestamps_s": (ts_buf.astype(np.float64)  if ts_buf is not None  else np.zeros((1,0), np.float64)),

    # cleaned & alpha (optional inspect)
    "clean":        (clean_buf.astype(np.float32) if clean_buf is not None else np.zeros((n_ch,0), np.float32)),
    "alpha":        (alpha_buf.astype(np.float32) if alpha_buf is not None else np.zeros((n_ch,0), np.float32)),

    # powers
    "power_baseline": (power_baseline.astype(np.float32) if power_baseline is not None else np.zeros((n_ch,0), np.float32)),
    "power_alpha":    (power_alpha.astype(np.float32)    if power_alpha is not None    else np.zeros((n_ch,0), np.float32)),
    "power_norm":     (power_norm.astype(np.float32)     if power_norm is not None     else np.zeros((n_ch,0), np.float32)),

    # cue markers
    "event_indices": np.array(event_indices, dtype=np.int64),
    "event_codes":   np.array(event_codes,   dtype=np.int32),
    "event_labels":  np.array(event_labels,  dtype=object),
}

np.savez(outfile, **save_dict)
print(f"✅ Saved per-electrode powers + markers to:\n{outfile}")

# ====== Plot normalized power per electrode ======
try:
    if power_norm is not None and power_norm.shape[1] > 0:
        t = ts_buf.ravel() if ts_buf is not None else np.arange(power_norm.shape[1]) / fs
        fig, axes = plt.subplots(4, 2, figsize=(12, 10), sharex=True)
        axes = axes.ravel()
        for i, ax in enumerate(axes[:n_ch]):
            ax.plot(t, power_norm[i], linewidth=0.8)
            ax.set_title(chan_names[i])
            ax.set_ylabel('Norm α power')
            ax.grid(True, alpha=0.3)
        axes[-2].set_xlabel('Time (s)')
        axes[-1].set_xlabel('Time (s)')
        fig.suptitle('Per-electrode normalized α-band power (8–13 Hz) = α_power / baseline_power')
        fig.tight_layout()
        plt.show()
    else:
        print("No data to plot.")
except Exception as e:
    print("Plot error:", e)
