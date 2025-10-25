# -*- coding: utf-8 -*-
import argparse
import logging
import time
from typing import List, Optional, Tuple

import numpy as np
import matplotlib as mpl

from PyQt5 import QtCore, QtWidgets
import pyqtgraph as pg

from scipy.signal import butter, sosfilt, sosfilt_zi

from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds


# ---------------------------- Configuration ----------------------------------

# Display order (top -> bottom) and channel names expected on the board
LABELS = ["FC4", "C4", "CP4", "C2", "C1", "CP3", "C3", "FC3"]

NEON = ['#FF0000', '#3cb44b', '#ffe119', '#4363d8',
        '#f58231', '#FFFFFF', '#469990', '#f032e6']            # curve colors


# ----------------------------- Utilities -------------------------------------

def design_bandpass_sos(fs: float,
                        lo: float = 8.0,
                        hi: float = 30.0,
                        order: int = 4):
    """Return Butterworth band-pass filter as SOS for stable streaming."""
    return butter(order, (lo, hi), btype='bandpass', fs=fs, output='sos')


def estimate_fs_from_timestamps(ts: np.ndarray, fs_declared: float) -> float:
    """
    Estimate sampling rate from timestamp differences (median of positive diffs).
    Falls back to declared rate if not enough samples.
    """
    if ts.size >= 2:
        dts = np.diff(ts)
        dts = dts[dts > 0]
        if dts.size:
            return float(1.0 / np.median(dts))
    return float(fs_declared)


# ------------------------------ UI Class -------------------------------------

class LiveEEGViewer(QtWidgets.QWidget):
    """
    PyQt widget that:
      - Plots streaming EEG channels with pan/zoom and optional follow-live.
      - Provides per-channel visibility and LP+CAR toggles.
      - Maintains filter state and bounded signal history.
    """

    def __init__(self,
                 board: BoardShim,
                 eeg_ch: List[int],
                 ts_ch: int,
                 fs_est: float,
                 fs_decl: float,
                 window_sec: float,
                 max_history_sec: float,
                 decim: int = 1,
                 parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)

        # Runtime/stream state
        self.board = board
        self.eeg_ch = eeg_ch
        self.ts_ch = ts_ch
        self.n_ch = len(eeg_ch)

        self.fs_est = float(fs_est)
        self.fs_decl = float(fs_decl)
        self.window_sec = float(window_sec)
        self.max_history_sec = float(max_history_sec)
        self.decim = max(1, int(decim))

        # History buffers (numpy arrays for pyqtgraph efficiency)
        self.t0: Optional[float] = None
        self.last_ts_seen: Optional[float] = None
        self.t_hist = np.array([], dtype=float)
        self.y_hist = [np.array([], dtype=float) for _ in range(self.n_ch)]

        # Stateful filter (per-channel zi)
        self.sos = design_bandpass_sos(self.fs_est)
        base_zi = sosfilt_zi(self.sos)
        self.zi = [base_zi.copy() * 0.0 for _ in range(self.n_ch)]  # zero-init

        # UI setup
        self.setWindowTitle("Live EEG")
        self.resize(1550, 780)
        outer = QtWidgets.QHBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(10)

        # Plot area
        self.graphics = pg.GraphicsLayoutWidget()
        outer.addWidget(self.graphics, stretch=1)
        self.plot = self.graphics.addPlot(row=0, col=0)
        self._configure_plot()

        # Control panel
        self.panel = QtWidgets.QFrame()
        self.panel.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.panel.setStyleSheet("QFrame { background-color: #111; color: #eee; }")
        outer.addWidget(self.panel, stretch=0)
        self._build_panel()

        # Timer
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_stream)
        self.timer.start(5)

        # Vertical markers for filter calls 
        self.filter_mark_pen = pg.mkPen('w', width=1)
        self.filter_marks: List[pg.InfiniteLine] = []
        self.max_filter_marks = 150

    # ----- UI construction helpers -----

    def _configure_plot(self) -> None:
        """Configure plot appearance and behavior."""
        pg.setConfigOption('background', 'k')
        pg.setConfigOption('foreground', 'w')

        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.plot.setLabel('bottom', 'Time', units='s')
        self.plot.setLabel('left', 'Amplitude', units='µV')
        self.plot.setTitle('Scope')
        self.plot.setMouseEnabled(x=True, y=True)
        self.plot.addItem(pg.InfiniteLine(pos=0.0, angle=0,
                                          pen=pg.mkPen('#555', width=1)))
        self.plot.enableAutoRange(x=False, y=True)
        self.plot.setXRange(0, self.window_sec, padding=0)

    def _build_panel(self) -> None:
        """Assemble control panel with channel rows and global controls."""
        lay = QtWidgets.QVBoxLayout(self.panel)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        # Follow / Jump controls
        self.follow_cb = QtWidgets.QCheckBox("Follow live")
        self.follow_cb.setStyleSheet("QCheckBox { font-weight: 600; font-size: 15px; color: #FFFFFF; }")
        self.follow_cb.setChecked(True)
        self.jump_btn = QtWidgets.QPushButton("Jump to Live")

        top_row = QtWidgets.QHBoxLayout()
        top_row.addWidget(self.follow_cb)
        top_row.addWidget(self.jump_btn)

        wrap_top = QtWidgets.QWidget()
        wrap_top.setLayout(top_row)
        lay.addWidget(wrap_top)

        # Channels header
        header = QtWidgets.QLabel("Channels")
        header.setStyleSheet("QLabel { font-weight: 600; font-size: 15px; color: #FFFFFF; }")
        lay.addWidget(header)

        # Channel rows
        self.curves: List[pg.PlotDataItem] = []
        self.show_boxes: List[QtWidgets.QCheckBox] = []
        self.lp_boxes: List[QtWidgets.QCheckBox] = []

        for i in range(self.n_ch):
            lbl = LABELS[i] if i < len(LABELS) else f"Ch{i}"
            color = NEON[i % len(NEON)]
            pen = pg.mkPen(color, width=2)

            # Plot curve
            curve = self.plot.plot([], [], pen=pen, name=lbl)
            self.curves.append(curve)

            # Row widget
            row_w, cb_show, cb_lp = self._make_channel_row(lbl, color)
            lay.addWidget(row_w)
            self.show_boxes.append(cb_show)
            self.lp_boxes.append(cb_lp)

        # Connect visibility after creation to capture correct indices
        for idx, cb in enumerate(self.show_boxes):
            cb.stateChanged.connect(
                lambda state, i=idx: self.curves[i].setVisible(state == QtCore.Qt.Checked)
            )
            self.curves[idx].setVisible(cb.isChecked())

        # Global show/hide
        btn_row = QtWidgets.QHBoxLayout()
        btn_all = QtWidgets.QPushButton("Show All")
        btn_none = QtWidgets.QPushButton("Hide All")
        btn_row.addWidget(btn_all)
        btn_row.addWidget(btn_none)

        wrap_btns = QtWidgets.QWidget()
        wrap_btns.setLayout(btn_row)
        lay.addSpacing(6)
        lay.addWidget(wrap_btns)

        btn_all.clicked.connect(lambda: self._set_all_visibility(True))
        btn_none.clicked.connect(lambda: self._set_all_visibility(False))
        self.jump_btn.clicked.connect(self._snap_to_live)

        # FS label
        fs_label = QtWidgets.QLabel(f"fs est: {self.fs_est:0.2f} Hz (declared {self.fs_decl})")
        fs_label.setStyleSheet("QLabel { color: #FFFFFF; }")
        lay.addSpacing(10)
        lay.addWidget(fs_label)

        lay.addStretch(1)

    def _make_channel_row(self, name: str, color: str) -> Tuple[QtWidgets.QWidget,
                                                                QtWidgets.QCheckBox,
                                                                QtWidgets.QCheckBox]:
        """
        Build a single channel row with:
          - color swatch
          - visibility checkbox
          - LP+CAR toggle
        """
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(10)

        swatch = QtWidgets.QLabel()
        swatch.setFixedSize(14, 14)
        swatch.setStyleSheet(f"background-color: {color}; border: 1px solid #444; border-radius: 2px;")

        cb_show = QtWidgets.QCheckBox(name)
        cb_show.setChecked(True)
        cb_show.setStyleSheet("QCheckBox { spacing: 6px; color: #FFFFFF; }")

        cb_lp = QtWidgets.QCheckBox("8–30 BW + CAR")
        cb_lp.setChecked(False)
        cb_lp.setStyleSheet("QCheckBox { spacing: 6px; color: #AAAAFF; }")

        row.addWidget(swatch, 0)
        row.addWidget(cb_show, 1)
        row.addStretch(1)
        row.addWidget(cb_lp, 0)

        container = QtWidgets.QWidget()
        container.setLayout(row)
        return container, cb_show, cb_lp

    def _set_all_visibility(self, visible: bool) -> None:
        """Set all channel curves visible/invisible to match toggle."""
        for i, cb in enumerate(self.show_boxes):
            if cb.isChecked() != visible:
                cb.setChecked(visible)
            self.curves[i].setVisible(visible)

    def _snap_to_live(self) -> None:
        """Move viewport to most recent segment."""
        if self.t_hist.size:
            tmax = self.t_hist[-1]
            self.plot.setXRange(max(0.0, tmax - self.window_sec), tmax, padding=0)

    # ----- Streaming/update loop -----

    def update_stream(self) -> None:
        """Fetch new samples, apply optional filtering and CAR, update plot."""
        data = self.board.get_board_data()
        if data.size == 0 or data.shape[1] == 0:
            return

        ts = data[self.ts_ch, :]
        if ts.size == 0:
            return

        # Select new samples based on timestamp monotonicity
        if self.last_ts_seen is not None:
            mask = ts > self.last_ts_seen
            if not np.any(mask):
                return
            ts = ts[mask]
            ch_stack = [data[ch, :][mask].astype(float, copy=False) for ch in self.eeg_ch]
        else:
            ch_stack = [data[ch, :].astype(float, copy=False) for ch in self.eeg_ch]

        if self.t0 is None:
            self.t0 = ts[0]
        t_new = ts - self.t0

        # Optional per-channel band-pass (stateful)
        filter_called = False
        for ch in range(self.n_ch):
            x = ch_stack[ch]
            if x.size and self.lp_boxes[ch].isChecked():
                y, self.zi[ch] = sosfilt(self.sos, x, zi=self.zi[ch])
                ch_stack[ch] = y
                filter_called = False

        # Channel-selectable CAR
        ref_mask = np.array([cb.isChecked() for cb in self.lp_boxes], dtype=bool)
        X = np.vstack(ch_stack)  # shape: (n_ch, n_new)
        # if X.size:
        #     ref = np.mean(X[ref_mask, :], axis=0, keepdims=True) if ref_mask.any() \
        #           else np.mean(X, axis=0, keepdims=True)
        #     Xc = X.copy()
        #     Xc[ref_mask, :] = Xc[ref_mask, :] - ref  # apply CAR only to selected channels
        # else:
        #     Xc = X
        Xc = X
        # Append to history (bounded)
        self.t_hist = np.concatenate((self.t_hist, t_new))
        for i in range(self.n_ch):
            self.y_hist[i] = np.concatenate((self.y_hist[i], Xc[i]))

        # Optional filter call marker (visual cue)
        if filter_called and t_new.size:
            x_pos = float(self.t_hist[-1])
            vline = pg.InfiniteLine(pos=x_pos, angle=90, pen=self.filter_mark_pen)
            self.plot.addItem(vline)
            self.filter_marks.append(vline)
            if len(self.filter_marks) > self.max_filter_marks:
                old = self.filter_marks.pop(0)
                self.plot.removeItem(old)

        # Trim history
        self.last_ts_seen = ts[-1]
        tmax = self.t_hist[-1]
        tmin_keep = max(0.0, tmax - self.max_history_sec)
        start_idx = np.searchsorted(self.t_hist, tmin_keep, side='left')
        if start_idx > 0:
            self.t_hist = self.t_hist[start_idx:]
            for i in range(self.n_ch):
                self.y_hist[i] = self.y_hist[i][start_idx:]

        # Follow/scroll behavior
        if self.follow_cb.isChecked():
            self.plot.setXRange(max(0.0, tmax - self.window_sec), tmax, padding=0)
        else:
            xr = self.plot.viewRange()[0]
            if abs(xr[1] - tmax) < 0.2 * self.window_sec:
                self.plot.setXRange(max(0.0, tmax - self.window_sec), tmax, padding=0)

        # Draw
        if self.decim > 1:
            t_draw = self.t_hist[::self.decim]
            for i, c in enumerate(self.curves):
                c.setData(t_draw, self.y_hist[i][::self.decim])
        else:
            for i, c in enumerate(self.curves):
                c.setData(self.t_hist, self.y_hist[i])


# ------------------------------- Main ----------------------------------------

def configure_board(board: BoardShim, commands: List[str]) -> None:
    """Apply optional per-board configuration commands with logging."""
    for cmd in commands:
        try:
            board.config_board(cmd)
            time.sleep(1.0)
        except Exception as e:
            logging.warning(f"config_board failed for {cmd}: {e}")
            


def main():
    BoardShim.enable_dev_board_logger()
    logging.basicConfig(level=logging.DEBUG)
    mpl.set_loglevel("warning")

    parser = argparse.ArgumentParser()
    parser.add_argument('--timeout', type=int, default=0)
    parser.add_argument('--ip-port', type=int, default=0)
    parser.add_argument('--ip-protocol', type=int, default=0)
    parser.add_argument('--ip-address', type=str, default='')
    parser.add_argument('--serial-port', type=str, default='COM3')
    parser.add_argument('--mac-address', type=str, default='')
    parser.add_argument('--other-info', type=str, default='')
    parser.add_argument('--streamer-params', type=str, default='')
    parser.add_argument('--serial-number', type=str, default='')
    parser.add_argument('--board-id', type=int, default=57)
    parser.add_argument('--file', type=str, default='')
    parser.add_argument('--master-board', type=int, default=BoardIds.NO_BOARD)
    parser.add_argument('--decim', type=int, default=1)
    parser.add_argument('--window-sec', type=float, default=3)
    parser.add_argument('--max-history-sec', type=float, default=3600.0)
    args = parser.parse_args()

    params = BrainFlowInputParams()
    params.ip_port = args.ip_port
    params.serial_port = args.serial_port
    params.mac_address = args.mac_address
    params.other_info = args.other_info
    params.serial_number = args.serial_number
    params.ip_address = args.ip_address
    params.ip_protocol = args.ip_protocol
    params.timeout = args.timeout
    params.file = args.file
    params.master_board = args.master_board

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    board = BoardShim(args.board_id, params)
    try:
        # Session start
        board.prepare_session()
        board.start_stream(1625, args.streamer_params)

        # Settle and optional config
        time.sleep(3.0)
        cfg_cmds = [
            "chon_1_12", 
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
            "rldadd_8"
        ]
        configure_board(board, cfg_cmds)
        
        # Flush post-config
        time.sleep(2.0)
        board.get_board_data()
        time.sleep(2.0)

        # Channel indices and fs
        fs_decl = BoardShim.get_sampling_rate(args.board_id)
        eeg_ch = BoardShim.get_eeg_channels(args.board_id)
        ts_ch = BoardShim.get_timestamp_channel(args.board_id)

        # Brief buffer to estimate fs
        buf = board.get_current_board_data(int(fs_decl * 10))
        ts = buf[ts_ch] if buf.size and ts_ch < buf.shape[0] else np.array([])
        fs_est = estimate_fs_from_timestamps(ts, fs_decl)

        # UI + viewer
        viewer = LiveEEGViewer(board=board,
                               eeg_ch=eeg_ch,
                               ts_ch=ts_ch,
                               fs_est=fs_est,
                               fs_decl=fs_decl,
                               window_sec=args.window_sec,
                               max_history_sec=args.max_history_sec,
                               decim=args.decim)
        viewer.show()

        # Optional: print board description (helpful during development)
        descr = BoardShim.get_board_descr(args.board_id)
        for k, v in descr.items():
            print(f"{k}: {v}")

        app.exec_()

    finally:
        # Graceful shutdown
        try:
            board.stop_stream()
        except Exception:
            pass
        try:
            board.release_session()
        except Exception:
            pass


if __name__ == "__main__":
    main()
