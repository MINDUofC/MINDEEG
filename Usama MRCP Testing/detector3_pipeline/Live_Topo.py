# -*- coding: utf-8 -*-
import argparse
import logging
import time
import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets, QtCore
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
from scipy.signal import butter, sosfilt, sosfilt_zi

import mne
import matplotlib as mpl
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

# Display order (top -> bottom) and channel names expected on the board
LABELS = ["FC4", "C4", "CP4", "C2", "C1", "CP3", "C3", "FC3"]


# ──────────────────────────────────────────────────────────────────────────────
# Graph: multi-strip time series (band-passed), filter passed in from main
# ──────────────────────────────────────────────────────────────────────────────
class Graph:
    def __init__(self, app, board_shim, sos):
        # References
        self.app = app
        self.board_shim = board_shim
        self.sos = sos  # predesigned SOS from main()

        # Board metadata
        self.board_id = board_shim.get_board_id()
        self.sampling_rate = BoardShim.get_sampling_rate(self.board_id)
        eeg_channels = BoardShim.get_eeg_channels(self.board_id)
        self.ordered_indices = eeg_channels[:len(LABELS)]
        self.ordered_names = LABELS[:len(self.ordered_indices)]
        self.n_ch = len(self.ordered_indices)

        # Buffers / timing
        self.update_speed_ms = 50
        self.window_size_s = 4
        self.num_points = int(self.window_size_s * self.sampling_rate)

        # UI
        self.win = pg.GraphicsLayoutWidget(title='EEG Time Series', size=(1000, 700), show=True)
        self._init_timeseries()

        # Y-limits smoothing (reduces visual flicker in autoscale)
        self._ylims_ema = [None] * self.n_ch
        self._ema_alpha = 0.25

        # Stateful IIR filter state per channel (initialized from passed SOS)
        self.zi = [sosfilt_zi(self.sos) * 0.0 for _ in range(self.n_ch)]

        # QTimer must be stored as an attribute to avoid GC
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(self.update_speed_ms)

    def _init_timeseries(self):
        self.plots, self.curves = [], []

        title_plot = self.win.addPlot(row=0, col=0)
        title_plot.hideAxis('left')
        title_plot.hideAxis('bottom')
        title_plot.setTitle('Band-pass 8–12 Hz', size='12pt')
        title_plot.setMaximumHeight(30)

        for i, ch_name in enumerate(self.ordered_names, start=1):
            p = self.win.addPlot(row=i, col=0)
            p.showAxis('left', True)
            p.getAxis('left').setTicks([])
            p.setLabel('left', ch_name)

            if i != len(self.ordered_names):
                p.showAxis('bottom', False)
            else:
                p.setLabel('bottom', f'Samples ({self.sampling_rate} Hz)')

            p.setXRange(0, self.num_points - 1, padding=0)
            p.enableAutoRange('y', False)
            p.enableAutoRange('x', False)

            self.plots.append(p)
            self.curves.append(p.plot())

    def update(self):
        # Acquire most recent window
        data = self.board_shim.get_current_board_data(self.num_points)
        X = data[self.ordered_indices, :].astype(np.float64)  # shape: (n_ch, n)

        # Stateful 8–12 Hz band-pass per channel
        for i in range(self.n_ch):
            y, self.zi[i] = sosfilt(self.sos, X[i], zi=self.zi[i])
            X[i] = y

        # Plot + dynamic y-limits (robust to outliers)
        for ch in range(self.n_ch):
            y = X[ch]
            self.curves[ch].setData(y.tolist())

            q1, q99 = np.percentile(y, [1, 99])
            span = max(q99 - q1, 1e-6)
            pad = 0.15 * span
            y_lo, y_hi = q1 - pad, q99 + pad

            prev = self._ylims_ema[ch]
            if prev is None:
                lo_s, hi_s = y_lo, y_hi
            else:
                a = self._ema_alpha
                lo_s = a * y_lo + (1 - a) * prev[0]
                hi_s = a * y_hi + (1 - a) * prev[1]
                if hi_s - lo_s < 1e-6:
                    lo_s -= 1.0
                    hi_s += 1.0

            self._ylims_ema[ch] = (lo_s, hi_s)
            self.plots[ch].setYRange(lo_s, hi_s, padding=0)

        self.app.processEvents()


# ──────────────────────────────────────────────────────────────────────────────
# LiveTopomap: computes per-channel Power on filtered window; plots topomap
# ──────────────────────────────────────────────────────────────────────────────
class LiveTopomap:
    def __init__(self, app, board_shim, sos, rest_power):
        # References
        self.app = app
        self.board_shim = board_shim
        self.sos = sos
        self.rest_power = np.asarray(rest_power, float) if rest_power is not None else None

        # Board / timing
        self.board_id = board_shim.get_board_id()
        self.sampling_rate = BoardShim.get_sampling_rate(self.board_id)
        self.update_speed_ms = 50
        self.window_size_s = 0.25
        self.num_points = int(self.window_size_s * self.sampling_rate)

        # Channel mapping
        eeg_channels = BoardShim.get_eeg_channels(self.board_id)
        self.ordered_names = LABELS[:len(eeg_channels)]
        self.row_by_name = {name: row for name, row in zip(self.ordered_names, eeg_channels)}
        self.active_channel_names = self.ordered_names[:]
        self.n_active = len(self.active_channel_names)

        self.tau_s = 0.4                       # smoothing time constant
        self.dt = self.update_speed_ms / 1000.0
        self.alpha_power = 1.0 - np.exp(-self.dt / self.tau_s)
        self.power_ema = np.zeros(self.n_active, dtype=float)

        # Filter state (one zi per active channel)
        self.zi = [sosfilt_zi(self.sos) * 0.0 for _ in range(self.n_active)]

        # Montage / plotting env
        self._montage = mne.channels.make_standard_montage('brainproducts-RNP-BA-128')
        avail = set(self._montage.ch_names)
        self._plot_names = [n for n in self.active_channel_names if n in avail]
        self._plot_info = mne.create_info(self._plot_names, sfreq=self.sampling_rate, ch_types='eeg')
        self._plot_info.set_montage(self._montage, match_case=True, on_missing='ignore')

        self.win = pg.GraphicsLayoutWidget(title='Topomap (Power 8–12 Hz)', show=True)
        self.win.resize(520, 520)
        self.win.clear()
        self.win.setBackground('w')

        mpl.use("Qt5Agg")
        self.fig = Figure(figsize=(5.2, 5.2), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        self.fig.patch.set_facecolor('white')

        self.ax = self.fig.add_axes([0.05, 0.05, 0.72, 0.90])
        self.ax.set_axis_off()
        self.ax.set_facecolor('white')

        self.cax = self.fig.add_axes([0.83, 0.15, 0.03, 0.70])
        self.cbar = None

        proxy = QtWidgets.QGraphicsProxyWidget()
        proxy.setWidget(self.canvas)
        self.win.addItem(proxy)

        self.cmap = plt.get_cmap('rainbow').copy()
        self.cmap.set_bad('white')

        # Progress ticker
        self._print_every_n = int(1.0 / (self.update_speed_ms / 1000.0))
        self._tick = 0

        # Timer
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(self.update_speed_ms)

    def update(self):
        # Acquire window in board order, select active rows in the configured order
        data = self.board_shim.get_current_board_data(self.num_points)
        X = np.array([data[self.row_by_name[n], :] for n in self.active_channel_names], dtype=np.float64)

        # Stateful 8–12 Hz filter per channel
        for i in range(self.n_active):
            y, self.zi[i] = sosfilt(self.sos, X[i], zi=self.zi[i])
            X[i] = y

        # Block power per channel
        block_power = np.mean(X**2, axis=1)

        # EMA on power, then sqrt for Power (µV^2)
        self.power_ema = (1.0 - self.alpha_power)*self.power_ema + self.alpha_power*block_power
        vals_active = (self.power_ema - self.rest_power)/ self.rest_power

        # Align to plotting order
        name_to_ix = {n: i for i, n in enumerate(self.active_channel_names)}
        kept = [n for n in self._plot_names if n in name_to_ix]
        if len(kept) < 3:
            return  # insufficient channels for interpolation

        plot_vals = np.array([vals_active[name_to_ix[n]] for n in kept], dtype=float)

        # Draw topomap of Power (µV)
        self.ax.clear()
        sel_idx = mne.pick_channels(self._plot_info['ch_names'], include=kept, ordered=True)
        info_subset = mne.pick_info(self._plot_info, sel_idx, copy=True)


        with mpl.rc_context({'font.size': 25,'font.weight': 'heavy'}):
            im, _ = mne.viz.plot_topomap(
                plot_vals, info_subset, axes=self.ax, show=False, names=kept,
                cmap=self.cmap, sensors=True, extrapolate='head', contours=0, res=128,
                image_interp='cubic', sphere=(0, 0, 0, 0.08)
            )
            im.set_interpolation('bilinear')

        # Robust color limits from 5th–95th percentiles
        finite = plot_vals[np.isfinite(plot_vals)]

        if finite.size:
            vmin = np.nanpercentile(finite, 5)
            vmax = np.nanpercentile(finite, 95)

            # Safety guards
            if not np.isfinite(vmin): vmin = 0.0; print("vmin values not right")
                
            if not np.isfinite(vmax): vmax = 1.0; print("vmax values not right")

            # Ensure a usable span (handle flat/degenerate cases)
            if vmax <= vmin:
                span = abs(vmax) if vmax != 0 else 1.0
                vmin = vmin - 0.5 * span
                vmax = vmax + 0.5 * span
                print("min/max values not right")
        else:
            vmin, vmax = 0.0, 1.0  # sane fallback

        im.set_clim(vmin, vmax)


        self.ax.set_axis_off()
        self.ax.set_aspect('equal')
        self.ax.set_title('Power (µV^2) in 8–12 Hz')

        if self.cbar is None:
            self.cbar = self.fig.colorbar(im, cax=self.cax)
            self.cbar.set_label('µV^2', rotation=90)
        else:
            self.cbar.update_normal(im)

        # Optional periodic stats
        self._tick += 1
        if (self._tick % self._print_every_n) == 0:
            print(f"[Topomap] window samples={X.shape[1]}  fs={self.sampling_rate} Hz  "
                  f"Power min/max: {float(np.nanmin(plot_vals)):.2f} / {float(np.nanmax(plot_vals)):.2f} µV^2")

        self.canvas.draw_idle()
        self.app.processEvents()


# ──────────────────────────────────────────────────────────────────────────────
# Utilities performed in main(): fs estimate, baseline acquisition, baseline Power
# ──────────────────────────────────────────────────────────────────────────────
def estimate_fs(board_shim, seconds=5):
    """Median-delta estimate from timestamp channel."""
    board_id = board_shim.get_board_id()
    fs_decl = BoardShim.get_sampling_rate(board_id)
    ts_ch = BoardShim.get_timestamp_channel(board_id)

    buf = board_shim.get_current_board_data(int(fs_decl * seconds))
    ts = buf[ts_ch]
    if ts.size >= 2:
        dts = np.diff(ts)
        dts = dts[dts > 0]
        return float(1.0 / np.median(dts)) if dts.size else float(fs_decl)

    return float(fs_decl)


def collect_rest_power(board_shim, sos, fs, duration_s=15, tau_s=0.4, block_s=0.05):
    eeg_rows = BoardShim.get_eeg_channels(board_shim.get_board_id())[:len(LABELS)]
    n_ch = len(eeg_rows)

    board_shim.get_board_data()
    time.sleep(1)

    alpha = 1.0 - np.exp(-(block_s / float(tau_s)))
    power_ema = np.zeros(n_ch, dtype=np.float64)
    zi = [sosfilt_zi(sos) * 0.0 for _ in range(n_ch)]

    n_blocks = max(1, int(round(duration_s / block_s)))
    n_block_samp = max(1, int(round(fs * block_s)))
    time.sleep(block_s)

    for _ in range(n_blocks):
        buf = board_shim.get_current_board_data(n_block_samp).astype(np.float64)
        if buf.shape[1] == 0:
            time.sleep(block_s * 0.5)
            continue

        X = buf[eeg_rows, :]
        for i in range(n_ch):
            X[i], zi[i] = sosfilt(sos, X[i], zi=zi[i])

        block_power = np.mean(X**2, axis=1)  # µV²
        power_ema = (1.0 - alpha) * power_ema + alpha * block_power
        time.sleep(block_s)

    # Optional rounding (vector-safe)
    return np.round(power_ema, 14)  # µV² per channel



# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────
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

    board_shim = BoardShim(args.board_id, params)

    try:
        board_shim.prepare_session()
        # Large ring buffer supports both views without data starvation
        board_shim.start_stream(450000, args.streamer_params)
        time.sleep(2.0)

        # Optional per-board configuration (kept from prior versions)
        commands = [
            "chon_1_12","rldadd_1","chon_2_12","rldadd_2","chon_3_12","rldadd_3","chon_4_12","rldadd_4",
            "chon_5_12","rldadd_5","chon_6_12","rldadd_6","chon_7_12","rldadd_7","chon_8_12","rldadd_8"
        ]
        for cmd in commands:
            try:
                board_shim.config_board(cmd)
                time.sleep(0.5)
            except Exception as e:
                logging.warning(f"config_board failed for {cmd}: {e}")

        # Clear residuals after config and settle
        board_shim.get_board_data()
        time.sleep(2.0)

        # Declared and estimated sampling rates
        fs_decl = BoardShim.get_sampling_rate(args.board_id)
        fs_est = estimate_fs(board_shim, seconds=5)
        print(f"Declared fs: {fs_decl} Hz | Estimated fs: {fs_est:.2f} Hz")

        # Design 8–12 Hz Butterworth once in main
        sos = butter(4, (8.0, 12.0), fs=fs_est, btype='bandpass', output='sos')

        # Baseline (rest) power from filtered window
        rest_secs = 15
        print(f"\nCollecting rest baseline for {rest_secs}s ...")
        rest_power = collect_rest_power(board_shim, sos, fs_est, duration_s=rest_secs, tau_s=0.4, block_s=0.05)
        print("Rest Power per channel (µV):", np.round(rest_power, 2))

        # Launch views – both receive the same SOS and baseline
        graph = Graph(app, board_shim, sos)
        topo = LiveTopomap(app, board_shim, sos, rest_power)

        app.exec()

    except BaseException:
        logging.exception('Exception')
    finally:
        if board_shim.is_prepared():
            try:
                board_shim.stop_stream()
            except Exception:
                pass
            board_shim.release_session()


if __name__ == '__main__':
    main()
