# collect_continuous_with_markers.py
# 8–13 Hz only. Build X/Y combos, signed power = |v|*v, EMA on powers,
# and angles from EMA powers: RH_theta = atan2(YRH_P, XRH_P), LH_theta = atan2(YLH_P, XLH_P) in [0, 360).

import os, time, random
import numpy as np
from brainflow.board_shim import BoardShim, BrainFlowInputParams
from scipy.signal import butter, sosfilt, sosfilt_zi

# ====== USER CONFIG ======
board_id            = 57
serial_port         = "COM3"
PROMPT_COUNTS       = False
TRIALS_PER_CLASS_DEFAULT = {'left': 5, 'right': 5, 'both': 5}
TRIAL_LENGTH_SECS   = 3.0           # pacing only
STEP_SAMPLES        = 1             # stateful filter step
EMA_TAU_S           = 0.6           # time constant for EMA of powers (seconds)

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

# Required indices for combinations (will raise if missing)
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

def append_chunk(buf: np.ndarray, chunk: np.ndarray) -> np.ndarray:
    if buf is None or buf.size == 0: return chunk.copy()
    return np.concatenate([buf, chunk], axis=1)

# Adaptive EMA: alpha = 1 - exp(-dt / tau)
def ema_update(prev, x, dt, tau):
    alpha = 1.0 - np.exp(-max(dt, 0.0) / max(tau, 1e-9))
    return x if prev is None else (1.0 - alpha) * prev + alpha * x

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
sr_avg = float(sr_ts)
print("EEG channel indices:", eeg_channels)
print("Assumed names:", chan_names)
print(f"Declared SR = {sr_decl} Hz | Estimated SR ≈ {sr_avg:.2f} Hz")
print(f"Live step size = {STEP_SAMPLES} samples")

# ====== Filter: only 8–13 Hz (alpha) ======
BAND = (8.0, 13.0)
FILTER_ORDER = 4
n_ch = len(eeg_channels)

def design_band_sos(low, high, fs, order=4):
    low = max(low, 0.001)
    nyq = 0.5 * fs
    wp = [low/nyq, high/nyq]
    return butter(order, wp, btype='bandpass', output='sos')

sos_alpha = design_band_sos(BAND[0], BAND[1], sr_avg, FILTER_ORDER)
zi_alpha  = [sosfilt_zi(sos_alpha) for _ in range(n_ch)]

# ====== growing buffers ======
raw_buf     = None       # (n_ch, T) raw (unreferenced)
ts_buf      = None       # (1, T) seconds
filt_alpha  = None       # (n_ch, T) 8–13 filtered (after hemisphere ref)
total_samples = 0

# Cue markers
event_indices = []
event_codes   = []
event_labels  = []

# Derived POWER signals (EMA-filtered), stored as (1, T)
XLH_P_buf = None
XRH_P_buf = None
YLH_P_buf = None
YRH_P_buf = None

# Theta signals (degrees, 0..360), stored as (1, T)
RH_theta_buf = None
LH_theta_buf = None

# EMA states for each power
ema_states = {"XLH": None, "XRH": None, "YLH": None, "YRH": None}
# last timestamp to compute dt for EMA
last_t_for_ema = None

def _append_scalar(buf, x):
    # buf: (1, T) or None; x: (m,) vector to append along time
    x = np.asarray(x, dtype=np.float64)[None, :]  # (1, m)
    return x.copy() if buf is None or buf.size == 0 else np.concatenate([buf, x], axis=1)

def process_live_chunk(eeg_chunk: np.ndarray, ts_chunk: np.ndarray):
    """Append and filter incoming chunk (n_ch,k), timestamps (1,k)."""
    global raw_buf, ts_buf, filt_alpha, total_samples
    global XLH_P_buf, XRH_P_buf, YLH_P_buf, YRH_P_buf, RH_theta_buf, LH_theta_buf
    global ema_states, last_t_for_ema

    # keep raw & timestamps
    raw_buf = append_chunk(raw_buf, eeg_chunk)
    ts_buf  = append_chunk(ts_buf, ts_chunk[None, :])

    # step in STEP_SAMPLES
    k = eeg_chunk.shape[1]
    start = 0
    while start < k:
        end = min(start + STEP_SAMPLES, k)
        step = eeg_chunk[:, start:end]   # (n_ch, m)
        ts_step = ts_chunk[start:end]    # (m,)
        m = step.shape[1]

        # ---------- LOCAL AVERAGE REFERENCE ----------
        step_ref = step.copy()
        if len(RIGHT) > 0:
            rmean = step_ref[RIGHT].mean(axis=0, keepdims=True)
            step_ref[RIGHT] -= rmean
        if len(LEFT) > 0:
            lmean = step_ref[LEFT].mean(axis=0, keepdims=True)
            step_ref[LEFT] -= lmean

        # ---------- FILTER 8–13 ----------
        out_alpha = np.zeros_like(step_ref)
        for ci in range(n_ch):
            y, zi_alpha[ci] = sosfilt(sos_alpha, step_ref[ci], zi=zi_alpha[ci])
            out_alpha[ci] = y
        filt_alpha = append_chunk(filt_alpha, out_alpha)

        # ---------- COMBOS -> SIGNED POWER -> EMA -> THETA ----------
        XLH_P = np.empty(m, dtype=np.float64)
        XRH_P = np.empty(m, dtype=np.float64)
        YLH_P = np.empty(m, dtype=np.float64)
        YRH_P = np.empty(m, dtype=np.float64)
        RH_th = np.empty(m, dtype=np.float64)
        LH_th = np.empty(m, dtype=np.float64)

        for j in range(m):
            t0 = float(ts_step[j])
            # aliases
            c3, cp3, fc3 = out_alpha[iC3, j], out_alpha[iCP3, j], out_alpha[iFC3, j]
            c4, cp4, fc4 = out_alpha[iC4, j], out_alpha[iCP4, j], out_alpha[iFC4, j]
            c1, c2       = out_alpha[iC1, j], out_alpha[iC2, j]

            # Your latest X/Y definitions (from your last snippet):
            XLH_val = (c1 - c3) + 0.5*(c1 - cp3) + 0.5*(c1 - fc3)
            XRH_val = -(c2 - c4) - 0.5*(c2 - cp4) - 0.5*(c2 - fc4)
            YLH_val = (fc3 - c3) - (cp3 - c3) - 0.5*(c1 - fc3) + 0.5*(c1 - cp3)
            YRH_val = (fc4 - c4) - (cp4 - c4) - 0.5*(c2 - fc4) + 0.5*(c2 - cp4)

            # Signed "power" (|v|*v)
            XLH_pow = abs(XLH_val) * XLH_val
            XRH_pow = abs(XRH_val) * XRH_val
            YLH_pow = abs(YLH_val) * YLH_val
            YRH_pow = abs(YRH_val) * YRH_val

            # # EMA update with adaptive alpha from dt
            # if last_t_for_ema is None:
            #     dt = 0.0
            # else:
            #     dt = max(t0 - last_t_for_ema, 0.0)

            # ema_states["XLH"] = ema_update(ema_states["XLH"], XLH_pow, dt, EMA_TAU_S)
            # ema_states["XRH"] = ema_update(ema_states["XRH"], XRH_pow, dt, EMA_TAU_S)
            # ema_states["YLH"] = ema_update(ema_states["YLH"], YLH_pow, dt, EMA_TAU_S)
            # ema_states["YRH"] = ema_update(ema_states["YRH"], YRH_pow, dt, EMA_TAU_S)
            # last_t_for_ema = t0

            # Store EMA powers
            # XLH_P[j] = ema_states["XLH"]
            # XRH_P[j] = ema_states["XRH"]
            # YLH_P[j] = ema_states["YLH"]
            # YRH_P[j] = ema_states["YRH"]

            XLH_P[j] = XLH_pow
            XRH_P[j] = XRH_pow
            YLH_P[j] = YLH_pow
            YRH_P[j] = YRH_pow

            # Angles in degrees 0..360 (atan2 handles quadrants)
            RH_deg = np.degrees(np.arctan2(YRH_P[j], XRH_P[j]))
            LH_deg = np.degrees(np.arctan2(YLH_P[j], XLH_P[j]))
            RH_th[j] = (RH_deg + 360.0) % 360.0
            LH_th[j] = (LH_deg + 360.0) % 360.0

        # append vectors to buffers
        XLH_P_buf = _append_scalar(XLH_P_buf, XLH_P)
        XRH_P_buf = _append_scalar(XRH_P_buf, XRH_P)
        YLH_P_buf = _append_scalar(YLH_P_buf, YLH_P)
        YRH_P_buf = _append_scalar(YRH_P_buf, YRH_P)
        RH_theta_buf = _append_scalar(RH_theta_buf, RH_th)
        LH_theta_buf = _append_scalar(LH_theta_buf, LH_th)
        # -------------------------------------------------------------

        total_samples += m
        start = end

def pump_for(secs: float):
    t_end = time.time() + secs
    while time.time() < t_end:
        new = board.get_board_data()
        if new.size == 0:
            time.sleep(0.002); continue
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
    if v <= 0: raise ValueError(f"Trial count for '{k}' must be > 0 (got {v}).")

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
save_dict = {
    "chan_names": np.array(chan_names, dtype=object),
    "eeg_channels": np.array(eeg_channels, dtype=np.int32),
    "sr_decl": np.int32(sr_decl),
    "sr_ts": np.float32(sr_avg),
    "step_samples": np.int32(STEP_SAMPLES),
    "ema_tau_s": np.float32(EMA_TAU_S),

    # continuous signals
    "filt_8_13":   (filt_alpha.astype(np.float32) if filt_alpha is not None else np.zeros((n_ch,0), np.float32)),
    "raw":         (raw_buf.astype(np.float32)    if raw_buf is not None    else np.zeros((n_ch,0), np.float32)),
    "timestamps_s": (ts_buf.astype(np.float64)    if ts_buf is not None     else np.zeros((1,0), np.float64)),

    # EMA-filtered powers (1 x T)
    "XLH_P": (XLH_P_buf.astype(np.float32) if XLH_P_buf is not None else np.zeros((1,0), np.float32)),
    "XRH_P": (XRH_P_buf.astype(np.float32) if XRH_P_buf is not None else np.zeros((1,0), np.float32)),
    "YLH_P": (YLH_P_buf.astype(np.float32) if YLH_P_buf is not None else np.zeros((1,0), np.float32)),
    "YRH_P": (YRH_P_buf.astype(np.float32) if YRH_P_buf is not None else np.zeros((1,0), np.float32)),

    # Thetas (degrees in 0..360) (1 x T)
    "RH_theta": (RH_theta_buf.astype(np.float32) if RH_theta_buf is not None else np.zeros((1,0), np.float32)),
    "LH_theta": (LH_theta_buf.astype(np.float32) if LH_theta_buf is not None else np.zeros((1,0), np.float32)),

    # cue markers
    "event_indices": np.array(event_indices, dtype=np.int64),
    "event_codes":   np.array(event_codes,   dtype=np.int32),
    "event_labels":  np.array(event_labels,  dtype=object),
}

np.savez(outfile, **save_dict)
print(f"✅ Saved continuous alpha, EMA powers, thetas, and markers to:\n{outfile}")
