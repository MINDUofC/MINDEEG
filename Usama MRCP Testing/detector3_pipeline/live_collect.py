# collect_continuous_with_markers.py
# Live, parallel SciPy Butterworth (stateful). Store full continuous signals + cue markers only.

import os, time, random
import numpy as np
from brainflow.board_shim import BoardShim, BrainFlowInputParams
from scipy.signal import butter, sosfilt, sosfilt_zi

# ====== USER CONFIG ======
board_id            = 57
serial_port         = "COM3"
PROMPT_COUNTS       = False
TRIALS_PER_CLASS_DEFAULT = {'left': 5, 'right': 5, 'both': 5}
TRIAL_LENGTH_SECS   = 3          # only used for countdown pacing
STEP_SAMPLES        = 1            # stateful filter update granularity

output_dir = r"C:\Users\rashe\source\repos\MINDUofC\MINDEEG\Usama MRCP Testing\calibration_data"
os.makedirs(output_dir, exist_ok=True)
outfile = os.path.join(output_dir, "continuous_filtered_streams_with_markers.npz")

chan_names  = ["FC4","C4","CP4","C2","C1","CP3","C3","FC3"]
labels = ['left', 'right', 'both']
label_to_code = {'left':0, 'right':1, 'both':3}

# Build name->index map and hemisphere groups
name_to_idx = {n: i for i, n in enumerate(chan_names)}
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
    if buf is None: return chunk.copy()
    if buf.size == 0: return chunk.copy()
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
sr_avg = float(sr_ts)
print("EEG channel indices:", eeg_channels)
print("Assumed names:", chan_names)
print(f"Declared SR = {sr_decl} Hz | Estimated SR ≈ {sr_avg:.2f} Hz")
print(f"Live step size = {STEP_SAMPLES} samples")

# ====== Filter bank (only the 3 bands you requested) ======
BANDS = {
    "0.05-5":  (0.05, 5.0),
    "8-13":    (8.0, 13.0),   # alpha
    "14-30":   (14.0, 30.0),  # beta
}
FILTER_ORDER = 4
n_ch = len(eeg_channels)

def design_band_sos(low, high, fs, order=4):
    low = max(low, 0.001)
    nyq = 0.5 * fs
    wp = [low/nyq, high/nyq]
    return butter(order, wp, btype='bandpass', output='sos')

band_sos = {name: design_band_sos(lo, hi, sr_avg, FILTER_ORDER) for name,(lo,hi) in BANDS.items()}
band_zi  = {name: [sosfilt_zi(band_sos[name]) for _ in range(n_ch)] for name in BANDS.keys()}

# ====== growing buffers for continuous signals ======
raw_buf     = None       # (n_ch, T)
ts_buf      = None       # (1, T) seconds
filt_bufs   = {name: None for name in BANDS.keys()}  # each (n_ch, T)
total_samples = 0

# cue markers (sample index + label code + label str)
event_indices = []
event_codes   = []
event_labels  = []

def process_live_chunk(eeg_chunk: np.ndarray, ts_chunk: np.ndarray):
    """Append and filter incoming chunk (n_ch,k), timestamps (1,k)."""
    global raw_buf, ts_buf, filt_bufs, total_samples

    # keep raw as-is
    raw_buf = append_chunk(raw_buf, eeg_chunk)
    ts_buf  = append_chunk(ts_buf, ts_chunk[None, :])

    # stateful: step in STEP_SAMPLES
    k = eeg_chunk.shape[1]
    start = 0
    while start < k:
        end = min(start + STEP_SAMPLES, k)
        step = eeg_chunk[:, start:end]   # (n_ch, m)

        # ---------- LOCAL AVERAGE REFERENCE (per hemisphere) ----------
        # Work on a referenced copy that feeds the filters
        step_ref = step.copy()
        if len(RIGHT) > 0:
            rmean = step_ref[RIGHT].mean(axis=0, keepdims=True)   # (1, m)
            step_ref[RIGHT] = step_ref[RIGHT] - rmean
        if len(LEFT) > 0:
            lmean = step_ref[LEFT].mean(axis=0, keepdims=True)    # (1, m)
            step_ref[LEFT] = step_ref[LEFT] - lmean
        # --------------------------------------------------------------

        m = step_ref.shape[1]

        # filter each band using the referenced step
        for bname in BANDS.keys():
            sos = band_sos[bname]
            out_step = np.zeros_like(step_ref)
            for ci in range(n_ch):
                y, band_zi[bname][ci] = sosfilt(sos, step_ref[ci], zi=band_zi[bname][ci])
                out_step[ci] = y
            filt_bufs[bname] = append_chunk(filt_bufs[bname], out_step)

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

        # Mark cue at the onset (start of the TRIAL_LENGTH window)

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
# Continuous arrays: (n_ch, T); timestamps seconds (1, T)
save_dict = {
    "chan_names": np.array(chan_names, dtype=object),
    "eeg_channels": np.array(eeg_channels, dtype=np.int32),
    "sr_decl": np.int32(sr_decl),
    "sr_ts": np.float32(sr_avg),
    "step_samples": np.int32(STEP_SAMPLES),
    "bands": np.array(list(BANDS.keys()), dtype=object),

    "filt_0p05_5":  filt_bufs["0.05-5"].astype(np.float32) if filt_bufs["0.05-5"] is not None else np.zeros((n_ch,0),np.float32),
    "filt_8_13":    filt_bufs["8-13"].astype(np.float32)    if filt_bufs["8-13"] is not None    else np.zeros((n_ch,0),np.float32),
    "filt_14_30":   filt_bufs["14-30"].astype(np.float32)   if filt_bufs["14-30"] is not None   else np.zeros((n_ch,0),np.float32),
    "raw":          raw_buf.astype(np.float32)              if raw_buf is not None              else np.zeros((n_ch,0),np.float32),
    "timestamps_s": ts_buf.astype(np.float64)               if ts_buf is not None               else np.zeros((1,0),np.float64),

    "event_indices": np.array(event_indices, dtype=np.int64),
    "event_codes":   np.array(event_codes,   dtype=np.int32),
    "event_labels":  np.array(event_labels,  dtype=object),
}

np.savez(outfile, **save_dict)
print(f"✅ Saved continuous filtered streams + markers to:\n{outfile}")

