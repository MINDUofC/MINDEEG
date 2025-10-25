import os, time, numpy as np
from typing import Dict, Tuple
from collections import deque
import threading
import tkinter as tk

from brainflow.board_shim import BoardShim, BrainFlowInputParams
from joblib import load
from scipy.signal import butter, sosfilt, sosfilt_zi
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from csp_bank_shared import BandTaskCSP
from feature_extraction_utilities_3 import (
    lw_cov, tangent_space, mrcp_features, CHAN_NAMES
)

# ---------- CONFIG ----------
IDX_C4 = CHAN_NAMES.index("C4")
IDX_C3 = CHAN_NAMES.index("C3")
FBCSP_BANDS = ["8-12", "12-16", "16-20", "20-26", "26-30"]

WINDOW_SEC = 1.0
LABELS = ["left", "right", "rest", "both"]

board_id = 57
serial_port = "COM3"

# Your knob: filter step == prediction cadence gate
STEP_SAMPLES = 1         # try 1–10
# Safety knobs to prevent freeze
MAX_CHUNK_STEPS = 8      # process at most 8*STEP_SAMPLES samples per loop
PREDICT_MIN_INTERVAL_SEC = 0.02  # ≥20 ms between predictions

ROOT = r"C:\Users\rashe\source\repos\MINDUofC\MINDEEG\Usama MRCP Testing\calibration_data\models"
PATH_CSP   = os.path.join(ROOT, "csp_models.joblib")
PATH_RMEAN = os.path.join(ROOT, "riem_mean.npy")
PATH_A     = os.path.join(ROOT, "baseA_fbcsp_lda.joblib")
PATH_B     = os.path.join(ROOT, "baseB_riem_lr.joblib")
PATH_C     = os.path.join(ROOT, "baseC_mrcp_active_lr.joblib")
PATH_META  = os.path.join(ROOT, "meta_lr.joblib")

BANDS = {
    "0.05-5":  (0.05, 5.0),
    "8-30":    (8.0, 30.0),
    "8-12":    (8.0, 12.0),
    "12-16":   (12.0, 16.0),
    "16-20":   (16.0, 20.0),
    "20-26":   (20.0, 26.0),
    "26-30":   (26.0, 30.0),
}
FILTER_ORDER = 4

# ============================== UI (Tk) =======================================
class ProbUI:
    COLORS = {"left": "red", "right": "blue", "rest": "green", "both": "magenta"}

    def __init__(self, thr_init=(0.70,0.70,0.75,0.50), ema_init=(0.80,0.80,0.80,0.80),
                 history_sec: float = 5.0):
        self._lock = threading.Lock()
        self._alpha, self._beta, self._gamma, self._delta = thr_init
        self._ema_L, self._ema_R, self._ema_Rest, self._ema_Both = ema_init

        maxlen = max(10, int(round(history_sec / 0.04)) + 5)
        self._tq   = deque(maxlen=maxlen)
        self._rawL = deque(maxlen=maxlen); self._rawR = deque(maxlen=maxlen)
        self._rawRest = deque(maxlen=maxlen); self._rawBoth = deque(maxlen=maxlen)
        self._sL  = deque(maxlen=maxlen); self._sR = deque(maxlen=maxlen)
        self._sRest = deque(maxlen=maxlen); self._sBoth = deque(maxlen=maxlen)
        self._last_decision = "rest"

        self._thread = threading.Thread(target=self._run_ui,
                                        args=(history_sec,),
                                        daemon=True)
        self._thread.start()

    def get_thresholds(self) -> Tuple[float, float, float, float]:
        with self._lock: return self._alpha, self._beta, self._gamma, self._delta

    def get_ema(self) -> Tuple[float, float, float, float]:
        with self._lock: return self._ema_L, self._ema_R, self._ema_Rest, self._ema_Both

    def push_sample(self, t: float,
                    raw: Tuple[float, float, float, float],
                    smooth: Tuple[float, float, float, float],
                    decision: str) -> None:
        with self._lock:
            self._tq.append(t)
            rL, rR, rRest, rBoth = raw
            sL, sR, sRest, sBoth = smooth
            self._rawL.append(rL);     self._rawR.append(rR)
            self._rawRest.append(rRest); self._rawBoth.append(rBoth)
            self._sL.append(sL); self._sR.append(sR)
            self._sRest.append(sRest); self._sBoth.append(sBoth)
            self._last_decision = decision

    def _run_ui(self, history_sec: float):
        root = tk.Tk(); root.title("Meta & EMA Controls + Live Probabilities")
        ctrl = tk.Frame(root); ctrl.pack(side=tk.TOP, fill=tk.X, padx=8, pady=6)

        def mk_slider(parent, text, init, cb, col):
            s = tk.Scale(parent, from_=0.00, to=1.00, resolution=0.01,
                         orient='horizontal', length=220, label=text,
                         command=lambda v: cb(float(v)))
            s.set(init); s.grid(row=0, column=col, padx=6); return s
        def set_alpha(v): self._set_attr('_alpha', v)
        def set_beta(v):  self._set_attr('_beta', v)
        def set_gamma(v): self._set_attr('_gamma', v)
        def set_delta(v): self._set_attr('_delta', v)
        mk_slider(ctrl, "α Left",  self._alpha, set_alpha, 0)
        mk_slider(ctrl, "β Right", self._beta,  set_beta,  1)
        mk_slider(ctrl, "γ Both",  self._gamma, set_gamma, 2)
        mk_slider(ctrl, "Δ Active≥", self._delta, set_delta, 3)

        ema = tk.Frame(root); ema.pack(side=tk.TOP, fill=tk.X, padx=8, pady=2)
        def mk_ema(parent, text, init, cb, col):
            s = tk.Scale(parent, from_=0.00, to=0.99, resolution=0.01,
                         orient='horizontal', length=220, label=text,
                         command=lambda v: cb(float(v)))
            s.set(init); s.grid(row=0, column=col, padx=6); return s
        def set_eL(v):    self._set_attr('_ema_L', v)
        def set_eR(v):    self._set_attr('_ema_R', v)
        def set_eRest(v): self._set_attr('_ema_Rest', v)
        def set_eBoth(v): self._set_attr('_ema_Both', v)
        mk_ema(ema, "EMA L α",   self._ema_L,    set_eL,    0)
        mk_ema(ema, "EMA R α",   self._ema_R,    set_eR,    1)
        mk_ema(ema, "EMA Rest α",self._ema_Rest, set_eRest, 2)
        mk_ema(ema, "EMA Both α",self._ema_Both, set_eBoth, 3)

        fig = Figure(figsize=(9.5, 3.4), dpi=100)
        ax  = fig.add_subplot(111)
        ax.set_ylim(0.0, 1.0); ax.set_xlim(0, history_sec)
        ax.set_xlabel("Time (s)"); ax.set_ylabel("Probability")
        ax.grid(True, alpha=0.25)
        (rawL,)  = ax.plot([], [], linestyle=":", color=self.COLORS["left"],  label="pL raw")
        (rawR,)  = ax.plot([], [], linestyle=":", color=self.COLORS["right"], label="pR raw")
        (rawRest,) = ax.plot([], [], linestyle=":", color=self.COLORS["rest"], label="pRest raw")
        (rawBoth,) = ax.plot([], [], linestyle=":", color=self.COLORS["both"], label="pBoth raw")
        (sL,) = ax.plot([], [], color=self.COLORS["left"],  label="pL EMA")
        (sR,) = ax.plot([], [], color=self.COLORS["right"], label="pR EMA")
        (sRest,) = ax.plot([], [], color=self.COLORS["rest"], label="pRest EMA")
        (sBoth,) = ax.plot([], [], color=self.COLORS["both"], label="pBoth EMA")
        ax.legend(loc="upper left", ncol=4, fontsize=8, framealpha=0.2)

        canvas = FigureCanvasTkAgg(fig, master=root)
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        def repaint():
            with self._lock:
                if len(self._tq) >= 2:
                    t_now = self._tq[-1]; t0 = t_now - history_sec
                    tx = [max(0.0, ti - t0) for ti in self._tq]
                    rawL.set_data(tx, list(self._rawL)); rawR.set_data(tx, list(self._rawR))
                    rawRest.set_data(tx, list(self._rawRest)); rawBoth.set_data(tx, list(self._rawBoth))
                    sL.set_data(tx, list(self._sL)); sR.set_data(tx, list(self._sR))
                    sRest.set_data(tx, list(self._sRest)); sBoth.set_data(tx, list(self._sBoth))
                    ax.set_xlim(0, history_sec)
                    border_color = self.COLORS.get(self._last_decision, "green")
                    for sp in ax.spines.values():
                        sp.set_edgecolor(border_color); sp.set_linewidth(2.0)
            canvas.draw_idle()
            root.after(50, repaint)  # ~20 Hz (stable)

        repaint(); root.mainloop()

    def _set_attr(self, name: str, value: float):
        with self._lock: setattr(self, name, value)

# ---------- Lightweight CSP bank wrapper ----------
class CSPBank:
    def __init__(self, joblib_path: str):
        self.models = load(joblib_path)
        self.bands = ["8-12", "12-16", "16-20", "20-26", "26-30"]
        self.tasks = ["L_vs_R", "B_vs_LR", "Act_vs_Rest"]
        any_key = next(iter(self.models)); self.n_components = self.models[any_key].csp.n_components
    def transform_all(self, band2trials: Dict[str, np.ndarray]) -> np.ndarray:
        feats = []
        for band in self.bands:
            Xb = band2trials[band]
            for task in self.tasks:
                mdl: BandTaskCSP = self.models[(band, task)]
                feats.append(mdl.transform(Xb))
        return np.concatenate(feats, axis=1)

# ---------- Filters ----------
def design_band_sos(low, high, fs, order=4):
    low = max(low, 0.001)
    nyq = 0.5 * fs
    wp = [low/nyq, high/nyq]
    return butter(order, wp, btype='bandpass', output='sos')

# ================================ MAIN =======================================
def main():
    # Models
    csp_bank = CSPBank(PATH_CSP)
    G = np.load(PATH_RMEAN)
    baseA = load(PATH_A); baseB = load(PATH_B); baseC = load(PATH_C); meta = load(PATH_META)

    # Board
    BoardShim.enable_dev_board_logger()
    params = BrainFlowInputParams(); params.serial_port = serial_port
    board = BoardShim(board_id, params)
    print("🔌 Preparing board session…")
    board.prepare_session(); board.start_stream(127); time.sleep(3.0)

    # Optional board config
    for cmd in ["chon_1_12","rldadd_1","chon_2_12","rldadd_2","chon_3_12","rldadd_3",
                "chon_4_12","rldadd_4","chon_5_12","rldadd_5","chon_6_12","rldadd_6",
                "chon_7_12","rldadd_7","chon_8_12","rldadd_8"]:
        board.config_board(cmd); time.sleep(0.2)
    board.get_board_data(); time.sleep(0.5)

    # SR from timestamps
    sr_decl = BoardShim.get_sampling_rate(board_id)
    sr_ts = 125.46
    fs = float(sr_ts)
    samples_per_trial = int(round(WINDOW_SEC * fs))

    eeg_channels = board.get_eeg_channels(board_id)
    n_ch = len(eeg_channels)
    print(f"EEG idx: {eeg_channels}")
    print(f"SR declared={sr_decl} Hz | estimated≈{fs:.2f} Hz | N/window={samples_per_trial}")
    print(f"Live filter step = {STEP_SAMPLES} samples; max backlog per loop = {MAX_CHUNK_STEPS*STEP_SAMPLES}")

    # Filters + states
    band_sos = {name: design_band_sos(lo, hi, fs, FILTER_ORDER) for name,(lo,hi) in BANDS.items()}
    band_zi  = {name: [sosfilt_zi(band_sos[name]) for _ in range(n_ch)] for name in BANDS.keys()}

    # Growing buffers
    raw_buf   = None
    filt_bufs = {name: None for name in BANDS.keys()}
    total_samples = 0

    def append_chunk(buf: np.ndarray, chunk: np.ndarray) -> np.ndarray:
        if buf is None or buf.size == 0: return chunk.copy()
        return np.concatenate([buf, chunk], axis=1)

    def process_live_chunk(eeg_chunk: np.ndarray):
        nonlocal raw_buf, filt_bufs, total_samples
        # backlog guard: keep only the newest portion
        max_cols = MAX_CHUNK_STEPS * STEP_SAMPLES
        if eeg_chunk.shape[1] > max_cols:
            eeg_chunk = eeg_chunk[:, -max_cols:]

        raw_buf = append_chunk(raw_buf, eeg_chunk)

        k = eeg_chunk.shape[1]
        start = 0
        while start < k:
            end = min(start + STEP_SAMPLES, k)
            step = eeg_chunk[:, start:end]
            m = step.shape[1]

            for bname in BANDS.keys():
                sos = band_sos[bname]
                out_step = np.empty_like(step)
                for ci in range(n_ch):
                    y, band_zi[bname][ci] = sosfilt(sos, step[ci], zi=band_zi[bname][ci])
                    out_step[ci] = y
                filt_bufs[bname] = append_chunk(filt_bufs[bname], out_step)

            total_samples += m
            start = end

    def get_filtered_window() -> Dict[str, np.ndarray]:
        s0 = max(0, total_samples - samples_per_trial); s1 = total_samples
        return {name: filt_bufs[name][:, s0:s1].copy() for name in BANDS.keys()}

    # Warm-up to 1 s
    while total_samples < samples_per_trial:
        new = board.get_board_data()
        if new.size:
            eeg = new[eeg_channels];  eeg = eeg if eeg.ndim == 2 else eeg[:, None]
            process_live_chunk(eeg)
        else:
            time.sleep(0.002)

    # UI
    ui = ProbUI(thr_init=(0.70,0.70,0.75,0.50), ema_init=(0.80,0.80,0.80,0.80), history_sec=5.0)

    sL = sR = sRest = sBoth = None
    last_pred_idx = total_samples
    last_pred_t = time.time()

    try:
        print("Predicting every STEP_SAMPLES (and ≥PREDICT_MIN_INTERVAL_SEC). Press Ctrl+C to stop.\n")
        while True:
            new = board.get_board_data()
            if new.size:
                eeg = new[eeg_channels];  eeg = eeg if eeg.ndim == 2 else eeg[:, None]
                process_live_chunk(eeg)
            else:
                time.sleep(0.001)

            # Gate: step + wall-clock throttle
            now = time.time()
            if (total_samples - last_pred_idx) >= STEP_SAMPLES and (now - last_pred_t) >= PREDICT_MIN_INTERVAL_SEC:
                last_pred_idx = total_samples
                last_pred_t = now

                bands = get_filtered_window()  # dict of (8,N)

                # Features
                band_trials = {b: bands[b][None, ...] for b in FBCSP_BANDS}
                X_fbcsp = csp_bank.transform_all(band_trials)

                C = lw_cov(bands["8-30"])
                x_riem = tangent_space(C, G)[None, :]

                x_mrcp, _ = mrcp_features(bands["0.05-5"][None, ...], int(fs))

                # Base + meta
                pA = baseA.predict_proba(X_fbcsp)[0]
                pB = baseB.predict_proba(x_riem)[0]
                pC_active = baseC.predict_proba(x_mrcp)[0, 1]

                x_meta = np.hstack([pA, pB, [pC_active]])[None, :]
                p_meta = meta.predict_proba(x_meta)[0]
                pL, pR, pRest, pBoth = p_meta

                alpha, beta, gamma, delta = ui.get_thresholds()
                eL, eR, eRest, eBoth = ui.get_ema()

                if sL is None:
                    sL, sR, sRest, sBoth = pL, pR, pRest, pBoth
                else:
                    sL    = eL    * sL    + (1.0 - eL)    * pL
                    sR    = eR    * sR    + (1.0 - eR)    * pR
                    sRest = eRest * sRest + (1.0 - eRest) * pRest
                    sBoth = eBoth * sBoth + (1.0 - eBoth) * pBoth

                dec_idx = int(np.argmax([sL, sR, sRest, sBoth]))
                if   dec_idx == 0 and sL    >= alpha:                        dec_name = LABELS[0]
                elif dec_idx == 1 and sR    >= beta:                         dec_name = LABELS[1]
                elif dec_idx == 3 and sBoth >= gamma and pC_active >= delta: dec_name = LABELS[3]
                else:                                                        dec_name = LABELS[2]

                ui.push_sample(now, (pL, pR, pRest, pBoth), (sL, sR, sRest, sBoth), dec_name)

                def fmt(a): return " ".join(f"{v:0.2f}" for v in a)
                print(f"[{time.strftime('%H:%M:%S')}] "
                      f"A[{fmt(pA)}]  B[{fmt(pB)}]  act={pC_active:0.2f}  "
                      f"meta[{fmt(p_meta)}]  "
                      f"EMA[L={sL:0.2f} R={sR:0.2f} Rest={sRest:0.2f} Both={sBoth:0.2f}]  "
                      f"⇒ {dec_name.upper()}")

    except KeyboardInterrupt:
        print("\nStopping…")
    finally:
        board.stop_stream(); board.release_session()
        print("🧠 Board session ended.")

if __name__ == "__main__":
    main()
