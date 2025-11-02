import os, time, json, numpy as np
from typing import Dict, Tuple
from collections import deque

from brainflow.board_shim import BoardShim, BrainFlowInputParams
from joblib import load
from scipy.signal import butter, sosfilt, sosfilt_zi

# --- PyQt5 / PyQtGraph ---
from PyQt5 import QtCore, QtWidgets
import pyqtgraph as pg

# Project utils
from csp_bank_shared import BandTaskCSP
from feature_extraction_utilities_3 import (
    lw_cov, tangent_space, mrcp_features, CHAN_NAMES
)

# ---------- CONFIG ----------
IDX_C4 = CHAN_NAMES.index("C4")
IDX_C3 = CHAN_NAMES.index("C3")
FBCSP_BANDS = ["8-12", "12-16", "16-20", "20-26", "26-30"]

WINDOW_SEC   = 1.0                  # features: last 1 s
HISTORY_SEC  = 5.0                  # UI plot window
MAX_KEEP_S   = 5.0                  # keep only last 5 s in memory
LABELS       = ["left", "right", "rest", "both"]

board_id   = 57
serial_port= "COM3"

STEP_SAMPLES = 1         # filter/predict cadence gate

ROOT = r"C:\Users\rashe\source\repos\MINDUofC\MINDEEG\Usama MRCP Testing\calibration_data\models" # -_-_-_-_-_-_-_-_CHANGE-_-_-_-_-_-_-_-_-

PATH_CSP   = os.path.join(ROOT, "csp_models.joblib")
PATH_RMEAN = os.path.join(ROOT, "riem_mean.npy")
PATH_A     = os.path.join(ROOT, "baseA_fbcsp_lda.joblib")
PATH_B     = os.path.join(ROOT, "baseB_riem_lr.joblib")
PATH_C     = os.path.join(ROOT, "baseC_mrcp_active_lr.joblib")
PATH_META  = os.path.join(ROOT, "meta_lr.joblib")
PATH_META_JSON = os.path.join(ROOT, "ensemble_meta.json")

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

# ---------- CSP wrapper ----------
class CSPBank:
    def __init__(self, joblib_path: str):
        self.models = load(joblib_path)
        self.bands = ["8-12", "12-16", "16-20", "20-26", "26-30"]
        self.tasks = ["L_vs_R", "B_vs_LR", "Act_vs_Rest"]
        any_key = next(iter(self.models))
        self.n_components = self.models[any_key].csp.n_components
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

# ========================= PyQtGraph UI =========================
class ProbUIQt(QtWidgets.QMainWindow):
    sig_request_thresholds = QtCore.pyqtSignal()  # (not used externally, here for symmetry)
    # thread-safe data push from worker:
    sig_new_sample = QtCore.pyqtSignal(float, tuple, tuple, str)

    COLORS = {"left": (255,0,0), "right": (0,122,255), "rest": (0,150,0), "both": (255,0,255)}

    def __init__(self, history_sec=HISTORY_SEC):
        super().__init__()
        self.setWindowTitle("Meta & EMA Controls + Live Probabilities (PyQtGraph)")
        self.history_sec = float(history_sec)

        # thresholds + EMA state
        self._alpha = 0.70; self._beta = 0.70; self._gamma = 0.75; self._delta = 0.50
        self._ema_L = 0.80; self._ema_R = 0.80; self._ema_Rest = 0.80; self._ema_Both = 0.80
        self._last_decision = "rest"

        # deques sized to history window @ ~200 Hz UI
        self._n_plot = int(round(self.history_sec * 200))
        self._tq      = deque([0.0]*self._n_plot, maxlen=self._n_plot)
        self._rawL    = deque([0.0]*self._n_plot, maxlen=self._n_plot)
        self._rawR    = deque([0.0]*self._n_plot, maxlen=self._n_plot)
        self._rawRest = deque([0.0]*self._n_plot, maxlen=self._n_plot)
        self._rawBoth = deque([0.0]*self._n_plot, maxlen=self._n_plot)
        self._sL      = deque([0.0]*self._n_plot, maxlen=self._n_plot)
        self._sR      = deque([0.0]*self._n_plot, maxlen=self._n_plot)
        self._sRest   = deque([0.0]*self._n_plot, maxlen=self._n_plot)
        self._sBoth   = deque([0.0]*self._n_plot, maxlen=self._n_plot)

        self._build_ui()
        self.sig_new_sample.connect(self._on_new_sample)

        # repaint timer ~200 Hz
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._repaint)
        self._timer.start(5)

        self._t0 = time.time()

    # ------ public getters ------
    def get_thresholds(self) -> Tuple[float,float,float,float]:
        return self._alpha, self._beta, self._gamma, self._delta
    def get_ema(self) -> Tuple[float,float,float,float]:
        return self._ema_L, self._ema_R, self._ema_Rest, self._ema_Both

    # ------ UI build ------
    def _mk_slider(self, title, init, parent_layout, callback, maxv=100, decimals=2):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        label = QtWidgets.QLabel(f"{title}: {init:.2f}")
        s = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        s.setMinimum(0); s.setMaximum(maxv)  # map 0..100 => 0..1
        s.setValue(int(round(init*maxv)))
        def on_change(v):
            val = v/maxv
            label.setText(f"{title}: {val:.2f}")
            callback(val)
        s.valueChanged.connect(on_change)
        lay.addWidget(label); lay.addWidget(s)
        parent_layout.addWidget(w)

    def _build_ui(self):
        central = QtWidgets.QWidget(); self.setCentralWidget(central)
        H = QtWidgets.QVBoxLayout(central)

        # --- sliders ---
        sliders = QtWidgets.QHBoxLayout()
        H.addLayout(sliders)

        # thresholds
        self._mk_slider("α Left",  self._alpha, sliders, lambda v: setattr(self, "_alpha", v))
        self._mk_slider("β Right", self._beta,  sliders, lambda v: setattr(self, "_beta", v))
        self._mk_slider("γ Both",  self._gamma, sliders, lambda v: setattr(self, "_gamma", v))
        self._mk_slider("Δ Active≥", self._delta, sliders, lambda v: setattr(self, "_delta", v))

        # EMA
        self._mk_slider("EMA L α",    self._ema_L,    sliders, lambda v: setattr(self, "_ema_L", v), maxv=99)
        self._mk_slider("EMA R α",    self._ema_R,    sliders, lambda v: setattr(self, "_ema_R", v), maxv=99)
        self._mk_slider("EMA Rest α", self._ema_Rest, sliders, lambda v: setattr(self, "_ema_Rest", v), maxv=99)
        self._mk_slider("EMA Both α", self._ema_Both, sliders, lambda v: setattr(self, "_ema_Both", v), maxv=99)

        # --- plot ---
        self.plot = pg.PlotWidget()
        self.plot.setYRange(0.0, 1.0)
        self.plot.setXRange(0.0, self.history_sec)
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.plot.setLabel('bottom', 'Time (s)')
        self.plot.setLabel('left', 'Probability')

        # curves
        self.cur_rawL    = self.plot.plot([], [], pen=pg.mkPen(self.COLORS["left"],  style=QtCore.Qt.DotLine),  name="pL raw")
        self.cur_rawR    = self.plot.plot([], [], pen=pg.mkPen(self.COLORS["right"], style=QtCore.Qt.DotLine), name="pR raw")
        self.cur_rawRest = self.plot.plot([], [], pen=pg.mkPen(self.COLORS["rest"],  style=QtCore.Qt.DotLine),  name="pRest raw")
        self.cur_rawBoth = self.plot.plot([], [], pen=pg.mkPen(self.COLORS["both"],  style=QtCore.Qt.DotLine),  name="pBoth raw")
        self.cur_sL      = self.plot.plot([], [], pen=pg.mkPen(self.COLORS["left"],  width=2))
        self.cur_sR      = self.plot.plot([], [], pen=pg.mkPen(self.COLORS["right"], width=2))
        self.cur_sRest   = self.plot.plot([], [], pen=pg.mkPen(self.COLORS["rest"],  width=2))
        self.cur_sBoth   = self.plot.plot([], [], pen=pg.mkPen(self.COLORS["both"],  width=2))

        H.addWidget(self.plot)

    # ------ data ingest from worker ------
    @QtCore.pyqtSlot(float, tuple, tuple, str)
    def _on_new_sample(self, t_now, raw, smooth, decision):
        # push while keeping fixed length (deques already fixed)
        self._tq.append(t_now)
        rL, rR, rRest, rBoth = raw
        sL, sR, sRest, sBoth = smooth
        self._rawL.append(rL); self._rawR.append(rR)
        self._rawRest.append(rRest); self._rawBoth.append(rBoth)
        self._sL.append(sL); self._sR.append(sR); self._sRest.append(sRest); self._sBoth.append(sBoth)
        self._last_decision = decision

    # ------ repaint ------
    def _repaint(self):
        if len(self._tq) < 2:
            return
        history_sec = self.history_sec
        t_now = self._tq[-1]
        t0 = t_now - history_sec
        # right-align newest point to history_sec
        tx = [max(0.0, ti - t0) for ti in self._tq]
        if tx:
            shift = history_sec - tx[-1]
            tx = [v + shift for v in tx]
        self.cur_rawL.setData(tx, list(self._rawL))
        self.cur_rawR.setData(tx, list(self._rawR))
        self.cur_rawRest.setData(tx, list(self._rawRest))
        self.cur_rawBoth.setData(tx, list(self._rawBoth))
        self.cur_sL.setData(tx, list(self._sL))
        self.cur_sR.setData(tx, list(self._sR))
        self.cur_sRest.setData(tx, list(self._sRest))
        self.cur_sBoth.setData(tx, list(self._sBoth))
        # set border color to decision
        c = self.COLORS.get(self._last_decision, (0,150,0))
        self.plot.getAxis('left').setPen(c)
        self.plot.getAxis('bottom').setPen(c)
        for item in self.plot.items():
            if isinstance(item, pg.ViewBox):
                item.setBorder(c)

# ========================= Worker (EEG + prediction) =========================
class LiveWorker(QtCore.QThread):
    sig_ui_sample = QtCore.pyqtSignal(float, tuple, tuple, str)

    def __init__(self, ui: ProbUIQt):
        super().__init__()
        self.ui = ui
        self._stop = False

        # Models
        self.csp_bank = CSPBank(PATH_CSP)
        self.G = np.load(PATH_RMEAN)
        self.baseA = load(PATH_A); self.baseB = load(PATH_B); self.baseC = load(PATH_C); self.meta = load(PATH_META)

        # fs from JSON (fallback to declared)
        try:
            with open(PATH_META_JSON, "r") as f:
                cfg = json.load(f)
            self.sr_ts = float(cfg["fs_from_npz"])
            print(f"fs_from_npz: {self.sr_ts:.2f} Hz")
        except Exception as e:
            print(f"fs_from_npz missing ({e}); fallback to declared.")
            self.sr_ts = float(BoardShim.get_sampling_rate(board_id))

        self.samples_per_trial = int(round(WINDOW_SEC * self.sr_ts))
        self.MAX_KEEP = int(round(MAX_KEEP_S * self.sr_ts))

        # Filters
        self.band_sos = {name: design_band_sos(lo, hi, self.sr_ts, FILTER_ORDER)
                         for name,(lo,hi) in BANDS.items()}

        # Board
        BoardShim.enable_dev_board_logger()
        params = BrainFlowInputParams(); params.serial_port = serial_port
        self.board = BoardShim(board_id, params)

        # buffers
        self.raw_buf = None
        self.filt_bufs = {name: None for name in BANDS.keys()}
        self.total_samples = 0
        self.eeg_channels = None
        self.n_ch = 0
        self.band_zi = None

        # EMA
        self.sL = self.sR = self.sRest = self.sBoth = None

        self.sig_ui_sample.connect(self.ui.sig_new_sample)

    def append_and_cap(self, buf: np.ndarray, chunk: np.ndarray) -> np.ndarray:
        if buf is None or buf.size == 0:
            out = chunk.copy()
        else:
            out = np.concatenate([buf, chunk], axis=1)
        if out.shape[1] > self.MAX_KEEP:
            out = out[:, -self.MAX_KEEP:]
        return out

    def process_live_chunk(self, eeg_chunk: np.ndarray):
        # append raw (capped)
        self.raw_buf = self.append_and_cap(self.raw_buf, eeg_chunk)

        # process in STEP_SAMPLES (stateful)
        k = eeg_chunk.shape[1]
        start = 0
        while start < k:
            end = min(start + STEP_SAMPLES, k)
            step = eeg_chunk[:, start:end]
            m = step.shape[1]

            for bname in BANDS.keys():
                sos = self.band_sos[bname]
                out_step = np.empty_like(step)
                for ci in range(self.n_ch):
                    y, self.band_zi[bname][ci] = sosfilt(sos, step[ci], zi=self.band_zi[bname][ci])
                    out_step[ci] = y
                self.filt_bufs[bname] = self.append_and_cap(self.filt_bufs[bname], out_step)

            self.total_samples += m
            start = end

    def get_filtered_window(self) -> Dict[str, np.ndarray]:
        any_band = next(iter(self.filt_bufs))
        buf_len = 0 if self.filt_bufs[any_band] is None else self.filt_bufs[any_band].shape[1]
        s1 = buf_len
        s0 = max(0, buf_len - self.samples_per_trial)
        return {name: self.filt_bufs[name][:, s0:s1].copy() for name in BANDS.keys()}

    def run(self):
        print("🔌 Preparing board session…")
        self.board.prepare_session(); self.board.start_stream(); time.sleep(3.0)

        for cmd in ["chon_1_12",
                    "rldadd_1",
                    "chon_2_12",
                    "rldadd_2",
                    "chon_3_12",
                    "rldadd_3",
                    "chon_4_12",
                    "rldadd_4",
                    "chon_5_12",
                    "rldadd_5",
                    "chon_6_12",
                    "rldadd_6",
                    "chon_7_12",
                    "rldadd_7",
                    "chon_8_12",
                    "rldadd_8"]:

            self.board.config_board(cmd); 
            time.sleep(1)

        self.board.get_board_data(); 
        time.sleep(2)

        self.eeg_channels = self.board.get_eeg_channels(board_id)
        self.n_ch = len(self.eeg_channels)
        self.band_zi  = {name: [sosfilt_zi(self.band_sos[name]) for _ in range(self.n_ch)]
                         for name in BANDS.keys()}
        print(f"EEG idx: {self.eeg_channels}")
        print(f"Using SR≈{self.sr_ts:.2f} Hz | N/window={self.samples_per_trial} | buffer cap={MAX_KEEP_S:.1f}s")

        # Warm-up to 1 s
        while True:
            new = self.board.get_board_data()
            if new.size:
                eeg = new[self.eeg_channels]; eeg = eeg if eeg.ndim == 2 else eeg[:, None]
                self.process_live_chunk(eeg)
                any_band = next(iter(self.filt_bufs))
                if self.filt_bufs[any_band] is not None and self.filt_bufs[any_band].shape[1] >= self.samples_per_trial:
                    break
            else:
                time.sleep(0.002)

        last_pred_idx = self.total_samples

        try:
            print("Predicting every STEP_SAMPLES. Ctrl+C to stop.")
            while not self._stop:
                new = self.board.get_board_data()
                if new.size:
                    eeg = new[self.eeg_channels];  eeg = eeg if eeg.ndim == 2 else eeg[:, None]
                    self.process_live_chunk(eeg)
                else:
                    time.sleep(0.001)

                if (self.total_samples - last_pred_idx) >= STEP_SAMPLES:
                    last_pred_idx = self.total_samples

                    bands = self.get_filtered_window()

                    # Features
                    band_trials = {b: bands[b][None, ...] for b in FBCSP_BANDS}
                    X_fbcsp = self.csp_bank.transform_all(band_trials)

                    C = lw_cov(bands["8-30"])
                    x_riem = tangent_space(C, self.G)[None, :]

                    x_mrcp, _ = mrcp_features(bands["0.05-5"][None, ...], int(self.sr_ts))

                    # Base + meta
                    pA = self.baseA.predict_proba(X_fbcsp)[0]
                    pB = self.baseB.predict_proba(x_riem)[0]
                    pC_active = self.baseC.predict_proba(x_mrcp)[0, 1]

                    x_meta = np.hstack([pA, pB, [pC_active]])[None, :]
                    p_meta = self.meta.predict_proba(x_meta)[0]
                    pL, pR, pRest, pBoth = p_meta

                    alpha, beta, gamma, delta = self.ui.get_thresholds()
                    eL, eR, eRest, eBoth = self.ui.get_ema()

                    if self.sL is None:
                        self.sL, self.sR, self.sRest, self.sBoth = pL, pR, pRest, pBoth
                    else:
                        self.sL    = eL    * self.sL    + (1.0 - eL)    * pL
                        self.sR    = eR    * self.sR    + (1.0 - eR)    * pR
                        self.sRest = eRest * self.sRest + (1.0 - eRest) * pRest
                        self.sBoth = eBoth * self.sBoth + (1.0 - eBoth) * pBoth

                    dec_idx = int(np.argmax([self.sL, self.sR, self.sRest, self.sBoth]))
                    if   dec_idx == 0 and self.sL    >= alpha:                        dec_name = LABELS[0]
                    elif dec_idx == 1 and self.sR    >= beta:                         dec_name = LABELS[1]
                    elif dec_idx == 3 and self.sBoth >= gamma and pC_active >= delta: dec_name = LABELS[3]
                    else:                                                             dec_name = LABELS[2]

                    # emit to UI
                    self.sig_ui_sample.emit(time.time(),
                                            (pL, pR, pRest, pBoth),
                                            (self.sL, self.sR, self.sRest, self.sBoth),
                                            dec_name)

                    def fmt(a): return " ".join(f"{v:0.2f}" for v in a)
                    print(f"[{time.strftime('%H:%M:%S')}] "
                          f"A[{fmt(pA)}]  B[{fmt(pB)}]  act={pC_active:0.2f}  "
                          f"meta[{fmt(p_meta)}]  "
                          f"EMA[L={self.sL:0.2f} R={self.sR:0.2f} Rest={self.sRest:0.2f} Both={self.sBoth:0.2f}]  "
                          f"⇒ {dec_name.upper()}")

        except KeyboardInterrupt:
            pass
        finally:
            self.board.stop_stream(); self.board.release_session()
            print("🧠 Board session ended.")

    def stop(self):
        self._stop = True

# ========================= main =========================
def main():
    app = QtWidgets.QApplication([])
    ui = ProbUIQt(history_sec=HISTORY_SEC)
    ui.resize(1200, 600)
    time.sleep(5)
    ui.show()
    time.sleep(5)
    worker = LiveWorker(ui)
    worker.start()

    # Clean exit
    def on_about_to_quit():
        worker.stop()
        worker.wait(2000)
    app.aboutToQuit.connect(on_about_to_quit)

    app.exec_()

if __name__ == "__main__":
    main()
