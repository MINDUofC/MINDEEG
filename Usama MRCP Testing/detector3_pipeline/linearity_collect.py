# collect_continuous_with_markers.py
# Local avg ref → linear detrend (per chunk) → notch 59–61 → LP 45 → HP 5  => raw pipeline
# Alpha = 8–13 on the same ref+detrend
# Per-chunk powers = mean(x^2) within the chunk
# Normalized power per channel = alpha_power / (raw_power + eps)
# Derived features on per-chunk normalized powers. STEP_SAMPLES gates live chunking (min=2).

import os, time, random
import numpy as np
from brainflow.board_shim import BoardShim, BrainFlowInputParams
from scipy.signal import butter, sosfilt, sosfilt_zi, iirnotch, tf2sos, detrend

# ====== USER CONFIG ======
board_id            = 57
serial_port         = "COM3"
PROMPT_COUNTS       = False
TRIALS_PER_CLASS_DEFAULT = {'left': 5, 'right': 5, 'both': 5}
TRIAL_LENGTH_SECS   = 3.0
STEP_SAMPLES        = 32          # << you can change; min enforced to 2
EMA_TAU_S           = 0.6         # (metadata only)

output_dir = r"C:\Users\rashe\source\repos\MINDUofC\MINDEEG\Usama MRCP Testing\calibration_data"
os.makedirs(output_dir, exist_ok=True)
outfile = os.path.join(output_dir, "continuous_filtered_streams_with_markers.npz")

# Channel order (index 0..7)
chan_names  = ["FC4","C4","CP4","C2","C1","CP3","C3","FC3"]

labels = ['left', 'right', 'both']
label_to_code = {'left':0, 'right':1, 'both':3}

# Hemisphere groups for local average reference
name_to_idx = {n.upper(): i for i, n in enumerate(chan_names)}
RIGHT = [name_to_idx[x] for x in ["FC4","C4","CP4","C2"] if x in name_to_idx]
LEFT  = [name_to_idx[x] for x in ["FC3","C3","CP3","C1"] if x in name_to_idx]

# Required indices for combinations
def _need(*names):
    missing = [n for n in names if n not in name_to_idx]
    if missing:
        raise RuntimeError(f"Missing channels in chan_names: {missing}")
_need("C3","CP3","FC3","C4","CP4","FC4","C1","C2")
iC3, iCP3, iFC3, iC1 = name_to_idx["C3"], name_to_idx["CP3"], name_to_idx["FC3"], name_to_idx["C1"]
iC4, iCP4, iFC4, iC2 = name_to_idx["C4"], name_to_idx["CP4"], name_to_idx["FC4"], name_to_idx["C2"]

# ====== helpers ======
def estimate_fs_from_timestamps(ts: np.ndarray, fs_declared: float) -> float:
    if ts.size >= 2:
        dts = np.diff(ts); dts = dts[dts > 0]
        if dts.size: return float(1.0 / np.mean(dts))
    return float(fs_declared)

def _append_cols(A: np.ndarray, B: np.ndarray):
    if A is None or A.size == 0: return B.copy()
    return np.concatenate([A, B], axis=1)

def _append_vec(a: np.ndarray, b: np.ndarray):
    if a is None or a.size == 0: return b.copy()
    return np.concatenate([a, b], axis=0)

def _append_rowwise(buf: np.ndarray, x: np.ndarray):
    # buf: (n, T) or None; x: (n, m) to append in time
    return x.copy() if buf is None or buf.size == 0 else np.concatenate([buf, x], axis=1)

def _append_scalar(buf: np.ndarray, x):
    x = np.asarray(x, dtype=np.float64)[None, :]  # (1, m)
    return x.copy() if buf is None or buf.size == 0 else np.concatenate([buf, x], axis=1)

# ====== board setup ======
BoardShim.enable_dev_board_logger()
params = BrainFlowInputParams()
params.serial_port = serial_port
board = BoardShim(board_id, params)

print("🔌 Preparing board session…")
board.prepare_session()
board.start_stream()
time.sleep(3.0)

# (optional) per-channel commands
commands = [
    "chon_1_12", "rldadd_1", "chon_2_12", "rldadd_2",
    "chon_3_12", "rldadd_3", "chon_4_12", "rldadd_4",
    "chon_5_12", "rldadd_5", "chon_6_12", "rldadd_6",
    "chon_7_12", "rldadd_7", "chon_8_12", "rldadd_8"
]
for cmd in commands:
    board.config_board(cmd); time.sleep(1.0)

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
fs = float(sr_ts)

# enforce STEP_SAMPLES >= 2
if STEP_SAMPLES is None or STEP_SAMPLES < 2:
    print(f"⚠️ STEP_SAMPLES={STEP_SAMPLES} invalid; setting to 2.")
    STEP_SAMPLES = 2

print("EEG channel indices:", eeg_channels)
print("Assumed names:", chan_names)
print(f"Declared SR = {sr_decl} Hz | Estimated SR ≈ {fs:.2f} Hz")
print(f"Live chunk size (STEP_SAMPLES) = {STEP_SAMPLES} samples (~{STEP_SAMPLES/fs:.3f} s)")

# ====== Filter design ======
LINE_FREQ_HZ = 60.0
NOTCH_BW_HZ  = 2.0          # 59–61 Hz
LP_CUT_HZ    = 45.0
HP5_CUT_HZ   = 5.0
ALPHA_BAND   = (8.0, 13.0)
ORDER        = 4

nyq = 0.5 * fs
Q = LINE_FREQ_HZ / NOTCH_BW_HZ
b_notch, a_notch = iirnotch(w0=LINE_FREQ_HZ/nyq, Q=Q)
sos_notch = tf2sos(b_notch, a_notch)

def butter_sos_lowpass(cut_hz, fs, order=4):
    wp = (cut_hz / (0.5*fs))
    return butter(order, wp, btype='lowpass', output='sos')

def butter_sos_highpass(cut_hz, fs, order=4):
    wp = (cut_hz / (0.5*fs))
    return butter(order, wp, btype='highpass', output='sos')

def butter_sos_bandpass(low_hz, high_hz, fs, order=4):
    wp = [low_hz/(0.5*fs), high_hz/(0.5*fs)]
    return butter(order, wp, btype='bandpass', output='sos')

sos_lp45   = butter_sos_lowpass(LP_CUT_HZ, fs, ORDER)         # 0–45
sos_hp5    = butter_sos_highpass(HP5_CUT_HZ, fs, ORDER)       # remove 0–5
sos_alpha  = butter_sos_bandpass(ALPHA_BAND[0], ALPHA_BAND[1], fs, ORDER)

# zi states per filter per channel
n_ch = len(eeg_channels)
zi_notch = [sosfilt_zi(sos_notch) for _ in range(n_ch)]
zi_lp45  = [sosfilt_zi(sos_lp45)  for _ in range(n_ch)]
zi_hp5   = [sosfilt_zi(sos_hp5)   for _ in range(n_ch)]
zi_alpha = [sosfilt_zi(sos_alpha) for _ in range(n_ch)]

# ====== growing buffers (per-chunk outputs) ======
raw_power   = None   # (n_ch, Nchunks), mean(raw_chunk^2)
alpha_power = None   # (n_ch, Nchunks), mean(alpha_chunk^2)
norm_power  = None   # (n_ch, Nchunks) = alpha_power / (raw_power + eps)
ts_buf      = None   # (Nchunks,), mean timestamp per chunk
chunk_count = 0

# Derived features (1, Nchunks)
XRH_buf  = None
YRHU_buf = None
YRHL_buf = None
XLH_buf  = None
YLHU_buf = None
YLHL_buf = None

# Cue markers (index in chunk space)
event_indices, event_codes, event_labels = [], [], []

# pending accumulators for live chunking
pending_eeg = None    # (n_ch, T_pending)
pending_ts  = None    # (T_pending,)

EPS = 1e-20

def process_chunk(eeg_blk: np.ndarray, ts_blk: np.ndarray):
    """
    eeg_blk: (n_ch, m) raw (unreferenced) for one chunk (m == STEP_SAMPLES)
    ts_blk:  (m,)
    Produces one output sample per channel (mean power over chunk).
    """
    global raw_power, alpha_power, norm_power, ts_buf, chunk_count
    global XRH_buf, YRHU_buf, YRHL_buf, XLH_buf, YLHU_buf, YLHL_buf

    m = eeg_blk.shape[1]

    # ---------- LOCAL AVERAGE REFERENCE (hemisphere) ----------
    step_ref = eeg_blk.copy()
    if len(RIGHT) > 0:
        rmean = step_ref[RIGHT].mean(axis=0, keepdims=True)
    if len(LEFT) > 0:
        lmean = step_ref[LEFT].mean(axis=0, keepdims=True)
    step_ref[RIGHT] -= lmean
    step_ref[LEFT] -= rmean
    # ---------- LINEAR DETREND (per chunk) ----------
    step_dt = detrend(step_ref, axis=1, type='linear')

    # ---------- RAW FILTER PIPELINE: notch -> LP45 -> HP5 ----------
    raw_out = np.zeros_like(step_dt)
    for ci in range(n_ch):
        y, zi_notch[ci] = sosfilt(sos_notch, step_dt[ci], zi=zi_notch[ci])
        y, zi_lp45[ci]  = sosfilt(sos_lp45,  y,         zi=zi_lp45[ci])
        y, zi_hp5[ci]   = sosfilt(sos_hp5,   y,         zi=zi_hp5[ci])
        raw_out[ci] = y

    # ---------- ALPHA 8–13 (same ref+detrend path) ----------
    alpha_out = np.zeros_like(step_dt)
    for ci in range(n_ch):
        y, zi_alpha[ci] = sosfilt(sos_alpha, step_dt[ci], zi=zi_alpha[ci])
        alpha_out[ci] = y

    # ---------- PER-CHUNK MEAN POWERS ----------
    # mean of squared amplitude inside the chunk
    raw_pow   = np.mean(raw_out**2,   axis=1)   # (n_ch,)
    alpha_pow = np.mean(alpha_out**2, axis=1)   # (n_ch,)
    norm_pow  = alpha_pow / (raw_pow + EPS)     # (n_ch,)

    # append as one new column
    raw_power   = _append_rowwise(raw_power,   raw_pow[:, None])
    alpha_power = _append_rowwise(alpha_power, alpha_pow[:, None])
    globals()['norm_power']  = _append_rowwise(globals()['norm_power'],  norm_pow[:, None])

    # timestamp representative for the chunk
    t_mean = float(np.mean(ts_blk)) if ts_blk.size else (ts_buf[-1] + 1.0/fs) if ts_buf is not None and ts_buf.size else 0.0
    ts_buf = _append_vec(ts_buf, np.array([t_mean], dtype=np.float64))

    # ---------- DERIVED FEATURES ON PER-CHUNK NORMALIZED POWERS ----------
    c2  = norm_pow[iC2];  c4  = norm_pow[iC4];  fc4 = norm_pow[iFC4]; cp4 = norm_pow[iCP4]
    c1  = norm_pow[iC1];  c3  = norm_pow[iC3];  fc3 = norm_pow[iFC3]; cp3 = norm_pow[iCP3]

    XRH  = abs((c2  - c4)  / (c4  + EPS))
    YRHU = abs((fc4 - c4)  / (c4  + EPS))
    YRHL = abs((cp4 - c4)  / (c4  + EPS))
    XLH  = abs((c1  - c3)  / (c3  + EPS))
    YLHU = abs((fc3 - c3)  / (c3  + EPS))
    YLHL = abs((cp3 - c3)  / (c3  + EPS))

    XRH_buf  = _append_scalar(globals()['XRH_buf'],  np.array([XRH]))
    YRHU_buf = _append_scalar(globals()['YRHU_buf'], np.array([YRHU]))
    YRHL_buf = _append_scalar(globals()['YRHL_buf'], np.array([YRHL]))
    XLH_buf  = _append_scalar(globals()['XLH_buf'],  np.array([XLH]))
    YLHU_buf = _append_scalar(globals()['YLHU_buf'], np.array([YLHU]))
    YLHL_buf = _append_scalar(globals()['YLHL_buf'], np.array([YLHL]))
    globals()['XRH_buf'], globals()['YRHU_buf'], globals()['YRHL_buf'] = XRH_buf, YRHU_buf, YRHL_buf
    globals()['XLH_buf'], globals()['YLHU_buf'], globals()['YLHL_buf'] = XLH_buf, YLHU_buf, YLHL_buf

def pump_for(secs: float):
    global pending_eeg, pending_ts, chunk_count
    t_end = time.time() + secs
    while time.time() < t_end:
        new = board.get_board_data()
        if new.size == 0:
            time.sleep(0.002); continue

        eeg = new[eeg_channels]
        if eeg.ndim == 1: eeg = eeg[:, None]
        ts  = new[ts_ch]
        if ts.ndim == 0:  ts = ts[None]

        # accumulate
        pending_eeg = _append_cols(pending_eeg, eeg)
        pending_ts  = _append_vec(pending_ts,  ts)

        # process in contiguous blocks of STEP_SAMPLES
        while pending_eeg is not None and pending_eeg.shape[1] >= STEP_SAMPLES:
            blk_eeg = pending_eeg[:, :STEP_SAMPLES]
            blk_ts  = pending_ts[:STEP_SAMPLES]

            process_chunk(blk_eeg, blk_ts)
            chunk_count += 1

            # drop consumed
            if pending_eeg.shape[1] == STEP_SAMPLES:
                pending_eeg = None
                pending_ts  = None
            else:
                pending_eeg = pending_eeg[:, STEP_SAMPLES:]
                pending_ts  = pending_ts[STEP_SAMPLES:]

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

for k_lbl, v in trials_per_class_map.items():
    if v <= 0: raise ValueError(f"Trial count for '{k_lbl}' must be > 0 (got {v}).")

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

        print("1 ✊ CLENCH — marking cue (chunk index)…")
        # mark the *next* chunk start index (current chunk_count)
        event_indices.append(chunk_count)
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

# ====== Pack & Save (per-chunk series) ======
save_dict = {
    "chan_names": np.array(chan_names, dtype=object),
    "eeg_channels": np.array(eeg_channels, dtype=np.int32),
    "sr_decl": np.int32(sr_decl),
    "sr_ts": np.float32(fs),
    "step_samples": np.int32(STEP_SAMPLES),
    "ema_tau_s": np.float32(EMA_TAU_S),

    # per-chunk powers (n_ch, Nchunks)
    "raw_power":   (raw_power.astype(np.float32)   if raw_power   is not None else np.zeros((n_ch,0), np.float32)),
    "alpha_power": (alpha_power.astype(np.float32) if alpha_power is not None else np.zeros((n_ch,0), np.float32)),
    "norm_power":  (norm_power.astype(np.float32)  if norm_power  is not None else np.zeros((n_ch,0), np.float32)),

    # time: one per chunk
    "chunk_timestamps_s": (ts_buf.astype(np.float64) if ts_buf is not None else np.zeros((0,), np.float64)),

    # derived features (1 x Nchunks)
    "XRH":  (XRH_buf.astype(np.float32)  if XRH_buf  is not None else np.zeros((1,0), np.float32)),
    "YRHU": (YRHU_buf.astype(np.float32) if YRHU_buf is not None else np.zeros((1,0), np.float32)),
    "YRHL": (YRHL_buf.astype(np.float32) if YRHL_buf is not None else np.zeros((1,0), np.float32)),
    "XLH":  (XLH_buf.astype(np.float32)  if XLH_buf  is not None else np.zeros((1,0), np.float32)),
    "YLHU": (YLHU_buf.astype(np.float32) if YLHU_buf is not None else np.zeros((1,0), np.float32)),
    "YLHL": (YLHL_buf.astype(np.float32) if YLHL_buf is not None else np.zeros((1,0), np.float32)),

    # cue markers in chunk index space
    "event_indices": np.array(event_indices, dtype=np.int64),
    "event_codes":   np.array(event_codes,   dtype=np.int32),
    "event_labels":  np.array(event_labels,  dtype=object),
}

np.savez(outfile, **save_dict)
print(f"✅ Saved per-chunk RAW_POWER, ALPHA_POWER, NORM_POWER, features, and markers to:\n{outfile}")
print("   Each column is one processed chunk; markers index these chunk columns.")
