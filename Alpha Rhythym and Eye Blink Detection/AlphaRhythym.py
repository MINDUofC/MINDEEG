import argparse  # For parsing command-line arguments
import logging   # For logging informational and error messages
import sys       # For interacting with the Python runtime environment
import time      # For adding delays when configuring the board

import numpy as np  # For numerical operations
import pyqtgraph as pg  # For real-time plotting of EEG data
from PyQt5.QtWidgets import (
    QApplication,   # Qt application handler
    QMainWindow,    # Main window widget
    QVBoxLayout,    # Layout manager (vertical)
    QWidget,        # Generic container widget
    QPushButton,    # Clickable button widget
    QLabel,         # Display text
    QHBoxLayout     # Layout manager (horizontal)
)
from PyQt5.QtCore import QTimer, Qt  # Timer for scheduling updates, Qt namespace for style constants
from brainflow.board_shim import BoardShim, BrainFlowInputParams  # For interfacing with EEG hardware
from brainflow.data_filter import DataFilter, FilterTypes, DetrendOperations  # For preprocessing EEG data


def _ensure_even_length(arr):
    """
    Helper function that trims the last sample if the array length is odd,
    because many FFT implementations require an even number of points.
    Input:
      arr: 1D numpy array of signal samples
    Returns:
      A numpy array with even length
    """
    return arr if len(arr) % 2 == 0 else arr[:-1]


class AlphaFFTVisualizer(QMainWindow):
    """
    Main application window that handles:
      - Calibration phase (computing mean and std of alpha power)
      - Continuous FFT-based alpha power computation
      - Real-time plotting of alpha power
      - Threshold-based detection of "Alpha ON" states
    """
    def __init__(self, board_shim):
        super().__init__()
        # === Initialize board parameters ===
        self.board_shim = board_shim
        self.board_id = board_shim.get_board_id()

        # Obtain EEG channel indices and sampling rate from BrainFlow
        self.eeg_channels = BoardShim.get_eeg_channels(self.board_id)
        self.sampling_rate = BoardShim.get_sampling_rate(self.board_id)

        # === Define FFT window parameters ===
        # We will use a 6-second sliding window for spectral estimation
        self.num_points_fft = int(6 * self.sampling_rate)
        # Ensure window length is even
        self.num_points_fft -= self.num_points_fft % 2
        # Timer interval in milliseconds for updating the plot
        self.update_speed_ms = 200

        # === Calibration / detection state variables ===
        self.state = 'idle'            # Can be 'idle', 'calibrating', or 'detecting'
        self.is_calibrated = False     # Flag: has calibration completed successfully?
        self.calibration_time = 20     # Calibration duration in seconds
        self.calibration_buffers = []  # Store mean power from each calibration window
        self.alpha_mean = None         # Mean alpha power after calibration
        self.alpha_std = None          # Std deviation of alpha power after calibration
        self.z_threshold = 1.0         # Threshold in z-score units for detecting alpha on/off

        # === Plot data history ===
        self.power_history = []        # Circular buffer for live mean power values
        self.history_length = 500      # Maximum number of points to display

        # === Build the user interface ===
        self.setWindowTitle("Alpha FFT Visualizer & Detector")
        self.resize(1200, 800)  # Set default window size
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)  # Vertical layout for stacking widgets

        # --- Plot widget configuration ---
        self.plot = pg.PlotWidget(title="Mean Alpha Power Over Time")
        self.plot.setLabel('bottom', 'Time (updates)')
        self.plot.setLabel('left', 'Alpha Power (µV²)')
        self.plot.showGrid(x=True, y=True)  # Display grid lines
        self.plot.enableAutoRange(axis='y', enable=True)  # Auto-scale y-axis
        layout.addWidget(self.plot)  # Add plot to layout

        # Create a curve to show live alpha power data
        self.power_curve = self.plot.plot(pen=pg.mkPen('c', width=2), name='AlphaPower')

        # Create horizontal lines for thresholds but hide initially
        self.mean_line = pg.InfiniteLine(angle=0, pen=pg.mkPen('y', style=Qt.DashLine))
        self.std_plus  = pg.InfiniteLine(angle=0, pen=pg.mkPen('m', style=Qt.DashLine))
        self.std_minus = pg.InfiniteLine(angle=0, pen=pg.mkPen('m', style=Qt.DashLine))
        for line in (self.mean_line, self.std_plus, self.std_minus):
            line.hide()
            self.plot.addItem(line)

        # --- Status and information labels ---
        self.status_label = QLabel("Status: Ready")  # Shows current app state
        layout.addWidget(self.status_label)
        self.info_label = QLabel(self._info_text())  # Shows calibration stats
        layout.addWidget(self.info_label)

        # --- Control buttons ---
        btn_layout = QHBoxLayout()  # Horizontal layout for buttons
        # Pause/resume FFT updates
        self.pause_btn = QPushButton("Pause FFT")
        self.pause_btn.clicked.connect(self._toggle_pause)
        btn_layout.addWidget(self.pause_btn)

        # Start calibration process
        self.calib_btn = QPushButton("Calibrate")
        self.calib_btn.clicked.connect(self._start_calibration)
        btn_layout.addWidget(self.calib_btn)

        # Toggle detection on/off (enabled after calibration)
        self.detect_btn = QPushButton("Start Detection")
        self.detect_btn.setEnabled(False)
        self.detect_btn.clicked.connect(self._toggle_detection)
        btn_layout.addWidget(self.detect_btn)

        # Immediately stop all operations and reset
        self.hard_stop_btn = QPushButton("Hard Stop")
        self.hard_stop_btn.clicked.connect(self._hard_stop)
        btn_layout.addWidget(self.hard_stop_btn)

        layout.addLayout(btn_layout)

        # === Timer for continuous FFT updates ===
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_fft)
        self.timer.start(self.update_speed_ms)
        self.is_paused = False  # Flag: is plotting paused?

    def _info_text(self):
        """
        Returns a formatted string showing current calibration mean, std, and threshold.
        """
        m = f"{self.alpha_mean:.2f}" if self.alpha_mean is not None else "N/A"
        s = f"{self.alpha_std:.2f}" if self.alpha_std is not None else "N/A"
        return f"Mean Power: {m}    Std Dev: {s}    Z-threshold: {self.z_threshold:.1f}"

    def _toggle_pause(self):
        """
        Pause or resume live FFT updates without resetting any buffers.
        """
        self.is_paused = not self.is_paused
        # Update button label to reflect current action
        self.pause_btn.setText("Resume FFT" if self.is_paused else "Pause FFT")

    def _update_fft(self):
        """
        Core routine that:
          1. Grabs the latest EEG block (6 seconds)
          2. Preprocesses each channel (detrend, remove noise, bandpass)
          3. Computes FFT, normalizes, and extracts power in 8–12 Hz
          4. Averages across channels to get a single mean power
          5. Appends to history, updates plot, and checks z-threshold
        """
        # Only run when calibrating or detecting, and not paused
        if self.state not in ('calibrating', 'detecting') or self.is_paused:
            return

        # Retrieve most recent samples from the board
        data = self.board_shim.get_current_board_data(self.num_points_fft)
        if data.shape[1] < self.num_points_fft:
            # Not enough data yet
            return

        # List to collect per-channel alpha power estimates
        powers = []
        for ch in self.eeg_channels[:6]:  # Use first 6 EEG channels
            sig = np.copy(data[ch, -self.num_points_fft:])  # Last N samples

            # === Preprocessing steps ===
            DataFilter.detrend(sig, DetrendOperations.LINEAR.value)  # Remove linear trend
            DataFilter.remove_environmental_noise(sig, self.sampling_rate, 2)  # Notch filter 50/60 Hz
            DataFilter.perform_bandpass(
                sig,
                self.sampling_rate,
                8.0,    # Low cutoff (Hz)
                12.0,   # High cutoff (Hz)
                4,      # Filter order
                FilterTypes.BUTTERWORTH,
                0       # No additional parameter
            )

            # Ensure even length for FFT
            sig = _ensure_even_length(sig)

            try:
                # Compute FFT (complex values)
                fft_vals = DataFilter.perform_fft(sig, 2)
            except Exception:
                # Skip this channel if FFT fails
                continue

            # Normalize FFT by number of points for consistent scaling
            fft_vals = fft_vals / len(sig)

            # Get frequency bins corresponding to 8–12 Hz
            freqs = np.fft.rfftfreq(len(sig), 1 / self.sampling_rate)
            idx = np.where((freqs >= 8) & (freqs <= 12))[0]

            # Compute power = squared magnitude of FFT coefficients in the band
            power_band = np.abs(fft_vals[idx])**2
            # Average power across the band for this channel
            powers.append(np.mean(power_band))

        if not powers:
            # If no channel succeeded, skip updating
            return

        # Average power across channels for a single scalar metric
        mean_power = np.mean(powers)

        # === Update the live plot buffer ===
        self.power_history.append(mean_power)
        if len(self.power_history) > self.history_length:
            # Maintain fixed buffer size
            self.power_history.pop(0)
        self.power_curve.setData(self.power_history)

        # === Draw threshold lines if calibration is done ===
        if self.is_calibrated:
            for line, val in zip(
                (self.mean_line, self.std_plus, self.std_minus),
                (
                    self.alpha_mean,
                    self.alpha_mean + self.alpha_std * self.z_threshold,
                    self.alpha_mean - self.alpha_std * self.z_threshold
                )
            ):
                line.setValue(val)
                line.show()

        # === During detection mode, update status label ===
        if self.state == 'detecting':
            z = (mean_power - self.alpha_mean) / self.alpha_std  # Compute z-score
            st = (
                f"Alpha ON (z={z:.2f})"
                if z > self.z_threshold
                else f"Alpha OFF (z={z:.2f})"
            )
            self.status_label.setText(f"Status: {st}")

    def _start_calibration(self):
        """
        Begin calibration:
          - Reset previous state (unless re-calibrating)
          - Collect successive power estimates for `calibration_time` seconds
          - Compute mean and std deviation
        """
        self._hard_stop(clear_calib=False)  # Stop any running detection but keep old calib if re-calibrating
        self.state = 'calibrating'
        self.status_label.setText(f"Calibrating for {self.calibration_time}s...")
        self.calibration_buffers = []
        self.count = self.calibration_time

        # Use a separate timer firing every second for calibration steps
        self.calibration_timer = QTimer()
        self.calibration_timer.timeout.connect(self._calibration_step)
        self.calibration_timer.start(1000)

    def _calibration_step(self):
        """
        Called once per second during calibration:
          - Grab one 6-second window
          - Compute mean alpha power (same as in _update_fft)
          - Append to calibration_buffers
          - After `calibration_time` iterations, compute final statistics
        """
        data = self.board_shim.get_current_board_data(self.num_points_fft)
        if data.shape[1] >= self.num_points_fft:
            powers = []
            for ch in self.eeg_channels[:6]:
                sig = np.copy(data[ch, -self.num_points_fft:])
                DataFilter.detrend(sig, DetrendOperations.LINEAR.value)
                DataFilter.remove_environmental_noise(sig, self.sampling_rate, 2)
                DataFilter.perform_bandpass(
                    sig, self.sampling_rate, 8.0, 12.0, 4,
                    FilterTypes.BUTTERWORTH, 0
                )
                sig = _ensure_even_length(sig)
                try:
                    fft_vals = DataFilter.perform_fft(sig, 2)
                except:
                    continue
                fft_vals = fft_vals / len(sig)
                freqs = np.fft.rfftfreq(len(sig), 1 / self.sampling_rate)
                idx = np.where((freqs >= 8) & (freqs <= 12))[0]
                power_band = np.abs(fft_vals[idx])**2
                powers.append(np.mean(power_band))
            if powers:
                # Compute average across channels for this calibration window
                self.calibration_buffers.append(np.mean(powers))

        # Decrement countdown and check for end of calibration
        self.count -= 1
        if self.count <= 0:
            self.calibration_timer.stop()  # Stop calibration timer
            if self.calibration_buffers:
                # Compute overall statistics
                self.alpha_mean = float(np.mean(self.calibration_buffers))
                self.alpha_std  = float(np.std(self.calibration_buffers))
                self.is_calibrated = True
                self.calib_btn.setText("Recalibrate")  # Change button for subsequent calibrations
                self.detect_btn.setEnabled(True)  # Enable detection now that we have stats
            # Update status/info text
            self.status_label.setText("Calibration complete." if self.is_calibrated else "Calibration failed.")
            self.info_label.setText(self._info_text())
            self.state = 'idle'

    def _toggle_detection(self):
        """
        Start or stop detection, which overlays running-mode updates on the graph.
        Requires calibration to have succeeded first.
        """
        if not self.is_calibrated:
            self.status_label.setText("Please calibrate first.")
            return
        if self.state != 'detecting':
            # Begin detection mode
            self.state = 'detecting'
            self.status_label.setText("Detection running...")
            self.detect_btn.setText("Stop Detection")
        else:
            # Return to idle
            self.state = 'idle'
            self.status_label.setText("Detection stopped.")
            self.detect_btn.setText("Start Detection")

    def _hard_stop(self, clear_calib=True):
        """
        Immediately stops both calibration and detection,
        clears plot and optionally resets calibration stats.
        """
        # Stop calibration timer if active
        if hasattr(self, 'calibration_timer') and self.calibration_timer.isActive():
            self.calibration_timer.stop()
        # Reset state
        self.state = 'idle'
        self.is_paused = False
        # Clear plot data
        self.power_history.clear()
        self.power_curve.clear()
        # Hide threshold lines
        for line in (self.mean_line, self.std_plus, self.std_minus):
            line.hide()
        # Reset buttons
        self.pause_btn.setText("Pause FFT")
        self.detect_btn.setText("Start Detection")
        self.detect_btn.setEnabled(False)
        # Optionally clear calibration statistics
        if clear_calib:
            self.is_calibrated = False
            self.alpha_mean = None
            self.alpha_std  = None
            self.calib_btn.setText("Calibrate")
        # Update info/status labels
        self.info_label.setText(self._info_text())
        self.status_label.setText("Status: Ready")


if __name__ == '__main__':
    # === Entry point for standalone execution ===
    BoardShim.enable_dev_board_logger()  # Detailed logs from BrainFlow
    logging.basicConfig(level=logging.INFO)

    # Parse optional command-line parameters
    parser = argparse.ArgumentParser()
    parser.add_argument('--serial-port', type=str, default='COM4',
                        help="Serial port for the EEG board")
    parser.add_argument('--board-id', type=int, default=57,
                        help="BrainFlow board ID (e.g., NeuroShield=57)")
    args = parser.parse_args()

    # Set up BrainFlow parameters and session
    params = BrainFlowInputParams()
    params.serial_port = args.serial_port
    board = BoardShim(args.board_id, params)
    try:
        logging.info(f"Preparing session for board ID {args.board_id}...")
        board.prepare_session()
        logging.info("Session prepared.")
        board.start_stream(450000)  # Start streaming with large buffer
        logging.info("Stream started.")

        # Configure all 8 channels for data acquisition
        for i in range(1, 9):
            for cmd in (f"chon_{i}_12", f"rldadd_{i}"):
                board.config_board(cmd)
                logging.info(f"Config: {cmd}")
                time.sleep(0.5)  # brief pause after each command
        time.sleep(2)  # wait for settings to take effect

        # Launch Qt application
        app = QApplication(sys.argv)
        win = AlphaFFTVisualizer(board)
        win.show()
        sys.exit(app.exec_())

    except Exception:
        logging.error("Error during execution", exc_info=True)

    finally:
        logging.info("Releasing board session...")
        if board.is_prepared():
            board.release_session()
