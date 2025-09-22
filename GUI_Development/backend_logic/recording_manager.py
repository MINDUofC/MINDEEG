import os
import threading
import numpy as np
from PyQt5.QtCore import QTimer, Qt


class SynchronizedRecordingTimer:
    def __init__(self, timer_widget, sampling_rate: int = 125):
        self.timer_widget = timer_widget
        self.sampling_rate = sampling_rate
        self.sample_interval_ms = int(1000 / max(self.sampling_rate, 1))
        self.recording_timer = QTimer()
        self.recording_timer.setTimerType(Qt.PreciseTimer)
        self.recording_start_time_ms = None
        self.expected_sample_count = 0
        self.actual_sample_count = 0
        self._tick = None  # callback set by owner

    def start(self, on_tick_callback):
        """Start precise 125 Hz timer. Owner passes a callback to receive ticks."""
        if not self.timer_widget.in_trial:
            raise RuntimeError("TimerGUI not running; cannot start synchronized recording.")
        self._tick = on_tick_callback
        self.recording_start_time_ms = self.timer_widget.global_timer.elapsed()
        self.expected_sample_count = 0
        self.actual_sample_count = 0
        self.recording_timer.timeout.connect(self._on_timeout)
        self.recording_timer.start(self.sample_interval_ms)

    def stop(self):
        if self.recording_timer.isActive():
            self.recording_timer.stop()
        try:
            self.recording_timer.timeout.disconnect(self._on_timeout)
        except Exception:
            pass

    def _on_timeout(self):
        if self._tick is None:
            return
        current_global_ms = self.timer_widget.global_timer.elapsed()
        expected_ms = self.recording_start_time_ms + (self.expected_sample_count * self.sample_interval_ms)
        drift_ms = current_global_ms - expected_ms
        # We could log drift_ms if needed
        self._tick(current_global_ms)
        self.expected_sample_count += 1
        self.actual_sample_count += 1

    def get_trial_relative_seconds(self) -> float:
        if not self.timer_widget.in_trial:
            return 0.0
        elapsed_trial_ms = self.timer_widget.trial_timer.elapsed()
        before = self.timer_widget.time_before.value()
        return -float(before) + (elapsed_trial_ms / 1000.0)


class PreciseRecordingManager:
    """
    Collects EEG samples at 125 Hz and appends aligned timestamps:
    columns: [ch1..ch8, global_time_s, trial_time_s]
    """

    def __init__(self, data_collector, timer_widget, export_status_label):
        self.data_collector = data_collector
        self.timer_widget = timer_widget
        self.export_status = export_status_label

        self.sync = SynchronizedRecordingTimer(timer_widget)
        self.is_recording = False
        self._data_lock = threading.Lock()
        self._rows = []  # each row is np.ndarray shape (10,)
        self._last_sample_index = -1  # guard against duplicates
        self._sample_rate = getattr(self.data_collector, 'sampling_rate', None) or 125

        self.selected_types = {
            'muV': False,
            'FFT': False,
            'PSD': False,
        }

    def start(self, selected_types: dict):
        if self.is_recording:
            return False, "Already recording"
        if not self.data_collector or not self.data_collector.board_on:
            return False, "Board is off"
        self.selected_types = selected_types.copy()
        with self._data_lock:
            self._rows = []
            self._last_sample_index = -1
        try:
            self.sync.start(self._on_sample_tick)
            self.is_recording = True
            return True, "Recording started"
        except Exception as e:
            return False, str(e)

    def stop(self):
        self.sync.stop()
        self.is_recording = False

    def forfeit(self):
        self.stop()
        with self._data_lock:
            self._rows = []

    def has_cached_data(self) -> bool:
        with self._data_lock:
            return len(self._rows) > 0

    def get_cached_matrix(self) -> np.ndarray:
        with self._data_lock:
            if not self._rows:
                return np.empty((0, 10), dtype=float)
            return np.vstack(self._rows)

    def _on_sample_tick(self, current_global_ms: int):
        if not self.is_recording:
            return
        # If trials finished, stop and mark complete
        if not self.timer_widget.in_trial:
            self.stop()
            try:
                if self.export_status is not None:
                    self.export_status.setText("Recording complete - Ready to export")
            except Exception:
                pass
            return
        try:
            # Timestamps
            global_time_s = current_global_ms / 1000.0
            trial_time_s = self.sync.get_trial_relative_seconds()

            # De-duplication: compute sample index at sampling rate and skip duplicates
            sample_index = int(global_time_s * self._sample_rate + 1e-6)
            if sample_index <= self._last_sample_index:
                return

            # Acquire one sample vector for 8 channels from selected source
            sample = self._collect_single_sample()
            if sample is None:
                return
            row = np.append(sample, [global_time_s, trial_time_s])
            if row.shape[0] != 10:
                return
            with self._data_lock:
                self._rows.append(row.astype(float))
                self._last_sample_index = sample_index
        except Exception:
            # Fail silently per tick; overall recording continues
            pass

    def _collect_single_sample(self):
        """Return np.array of 8 channel values, or None if not available."""
        # Priority: muV > FFT > PSD based on selection
        if self.selected_types.get('muV'):
            data = self.data_collector.collect_data_muV()
            if data:
                return self._extract_latest_from_channels(data)
        if self.selected_types.get('FFT'):
            fft_tuple = self.data_collector.collect_data_FFT()
            if fft_tuple:
                freqs, amplitudes = fft_tuple
                return self._extract_peak_from_amplitudes(amplitudes)
        if self.selected_types.get('PSD'):
            psd_tuple = self.data_collector.collect_data_PSD()
            if psd_tuple:
                freqs, powers = psd_tuple
                return self._extract_sum_from_powers(powers)
        return None

    def _extract_latest_from_channels(self, channel_dict) -> np.ndarray:
        values = np.zeros(8, dtype=float)
        for i, ch in enumerate(self.data_collector.eeg_channels[:8]):
            sig = channel_dict.get(ch)
            if sig is not None and len(sig) > 0:
                values[i] = float(sig[-1])
        return values

    def _extract_peak_from_amplitudes(self, amplitudes_list) -> np.ndarray:
        values = np.zeros(8, dtype=float)
        for i, amp in enumerate(amplitudes_list[:8]):
            if amp is not None and len(amp) > 0:
                values[i] = float(np.max(amp))
        return values

    def _extract_sum_from_powers(self, powers_list) -> np.ndarray:
        values = np.zeros(8, dtype=float)
        for i, pwr in enumerate(powers_list[:8]):
            if pwr is not None and len(pwr) > 0:
                values[i] = float(np.sum(pwr))
        return values

    def export_cached(self, directory_path: str, file_type: str) -> bool:
        """Export cached matrix to directory as chosen file type.
        Output shape is (10, N): rows = 8 channels + global_s + trial_s; columns = samples.
        """
        matrix = self.get_cached_matrix()  # shape (N, 10)
        if matrix.size == 0:
            return False
        # Transpose to (10, N) to match required format
        data_10xN = matrix.T
        try:
            os.makedirs(directory_path, exist_ok=True)
            fname = "recording"
            # Simple unique suffix
            suffix = str(int(np.random.randint(10000, 99999)))
            ext = file_type.lower()
            if ext.startswith("."):
                ext = ext[1:]
            if ext in ("npz",):
                path = os.path.join(directory_path, f"{fname}_{suffix}.npz")
                # Save with explicit key names for clarity
                np.savez(
                    path,
                    ch1=data_10xN[0], ch2=data_10xN[1], ch3=data_10xN[2], ch4=data_10xN[3],
                    ch5=data_10xN[4], ch6=data_10xN[5], ch7=data_10xN[6], ch8=data_10xN[7],
                    global_s=data_10xN[8], trial_s=data_10xN[9],
                    data=data_10xN
                )
                return True
            elif ext in ("npy",):
                path = os.path.join(directory_path, f"{fname}_{suffix}.npy")
                np.save(path, data_10xN)
                return True
            elif ext in ("csv",):
                path = os.path.join(directory_path, f"{fname}_{suffix}.csv")
                # Write CSV with row labels, columns are sample indices
                labels = [f"ch{i+1}" for i in range(8)] + ["global_s", "trial_s"]
                num_cols = data_10xN.shape[1]
                with open(path, "w", encoding="utf-8") as f:
                    # header row: label,0,1,2,...
                    f.write("label," + ",".join(str(i) for i in range(num_cols)) + "\n")
                    for r, label in enumerate(labels):
                        row_vals = ",".join(f"{v:.10f}" for v in data_10xN[r])
                        f.write(f"{label},{row_vals}\n")
                return True
            else:
                # default to npz
                path = os.path.join(directory_path, f"{fname}_{suffix}.npz")
                np.savez(
                    path,
                    ch1=data_10xN[0], ch2=data_10xN[1], ch3=data_10xN[2], ch4=data_10xN[3],
                    ch5=data_10xN[4], ch6=data_10xN[5], ch7=data_10xN[6], ch8=data_10xN[7],
                    global_s=data_10xN[8], trial_s=data_10xN[9],
                    data=data_10xN
                )
                return True
        except Exception:
            return False


