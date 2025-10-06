import os
import threading
import numpy as np
from datetime import datetime
from PyQt5.QtCore import QTimer, Qt


class SynchronizedRecordingTimer:
    def __init__(self, timing_engine, sampling_rate: int = 125):
        self.engine = timing_engine
        self.sampling_rate = sampling_rate
        self.sample_interval_ms = int(1000 / max(self.sampling_rate, 1))
        self.recording_start_time_ms = None
        self.expected_sample_count = 0
        self.actual_sample_count = 0
        self._tick = None  # callback set by owner

    def start(self, on_tick_callback):
        """Start by subscribing to the engine's 8ms master tick."""
        if not getattr(self.engine, 'run_active', False):
            raise RuntimeError("TimingEngine not running; cannot start synchronized recording.")
        self._tick = on_tick_callback
        # Reset per-run baseline for recording timestamps
        self.recording_start_time_ms = 0
        self.expected_sample_count = 0
        self.actual_sample_count = 0
        try:
            # Connect to engine tick: now_ms, sched_ms
            self.engine.tick_8ms.connect(self._on_engine_tick)
        except Exception:
            pass

    def stop(self):
        try:
            self.engine.tick_8ms.disconnect(self._on_engine_tick)
        except Exception:
            pass

    def _on_engine_tick(self, now_ms: int, sched_ms: int):
        if self._tick is None:
            return
        # Use schedule time to avoid host-side latency bias
        expected_ms = self.recording_start_time_ms + (self.expected_sample_count * self.sample_interval_ms)
        drift_ms = now_ms - expected_ms  # optional for telemetry
        # Pass run-relative ms so each run starts at 0
        try:
            run_ms = int(self.engine.get_run_elapsed_ms())
        except Exception:
            run_ms = sched_ms
        self._tick(run_ms)
        self.expected_sample_count += 1
        self.actual_sample_count += 1

    def get_trial_relative_seconds(self) -> float:
        if not getattr(self.engine, 'run_active', False):
            return 0.0
        elapsed_trial_ms = self.engine.trial_timer.elapsed()
        return (elapsed_trial_ms / 1000.0)


class PreciseRecordingManager:
    """
    Collects EEG samples at 125 Hz for multiple data types simultaneously.
    Each data type gets its own file with datetime naming.
    
    Data structures:
    - muV: [ch1..ch8, global_s, trial_s] - time domain samples
    - FFT: [trial_s, global_s, ch1_bin1..ch1_binN, ch2_bin1..ch2_binN, ..., ch8_bin1..ch8_binN]
    - PSD: [trial_s, global_s, ch1_bin1..ch1_binN, ch2_bin1..ch2_binN, ..., ch8_bin1..ch8_binN]
    """

    def __init__(self, data_collector, timer_widget, timing_engine, export_status_label):
        self.data_collector = data_collector
        self.timer_widget = timer_widget
        self.engine = timing_engine
        self.export_status = export_status_label

        self.sync = SynchronizedRecordingTimer(timing_engine)
        self.is_recording = False
        self._data_lock = threading.Lock()
        try:
            # React to engine completing the run
            self.engine.run_completed.connect(self._on_run_completed)
        except Exception:
            pass
        
        # Separate data storage for each type
        self._muv_rows = []  # Shape: (N_samples, 10) -> [ch1..ch8, global_s, trial_s]
        # For FFT/PSD we store one row per timestamp with all channels concatenated
        # Shape: (N_samples, 2 + 8*num_freq_bins) -> [trial_s, global_s, ch1_bins..., ch2_bins..., ..., ch8_bins...]
        self._fft_rows = []
        self._psd_rows = []
        # Flags aligned to muV samples indicating engine was in buffer phase
        self._muv_is_buffer = []
        
        self._last_sample_index = -1  # guard against duplicates
        self._sample_rate = getattr(self.data_collector, 'sampling_rate', None) or 125
        self._recording_timestamp = None  # Set when recording starts
        
        # Store frequency information for FFT/PSD
        self._fft_freqs = None
        self._psd_freqs = None

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
        # Generate timestamp for this recording session
        self._recording_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        with self._data_lock:
            self._muv_rows = []
            self._muv_is_buffer = []
            self._fft_rows = []
            self._psd_rows = []
            self._last_sample_index = -1
        # Pre-warm collectors so first tick has data ready (non-fatal if unavailable)
        try:
            if self.selected_types.get('muV'):
                self.data_collector.collect_data_muV()
            if self.selected_types.get('FFT'):
                self.data_collector.collect_data_FFT()
            if self.selected_types.get('PSD'):
                self.data_collector.collect_data_PSD()
        except Exception:
            pass
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
            self._muv_rows = []
            self._fft_rows = []
            self._psd_rows = []

    def has_cached_data(self) -> bool:
        with self._data_lock:
            return (len(self._muv_rows) > 0 or 
                   len(self._fft_rows) > 0 or 
                   len(self._psd_rows) > 0)

    def get_cached_data_by_type(self) -> dict:
        """Return cached data separated by type with proper structures"""
        with self._data_lock:
            result = {}
            
            # muV: Keep original 10xN format [ch1..ch8, global_s, trial_s]
            if len(self._muv_rows) > 0:
                result['muV'] = {
                    'data': np.vstack(self._muv_rows).T,  # 10xN format
                    'structure': 'channels+time',
                    'columns': ['ch1', 'ch2', 'ch3', 'ch4', 'ch5', 'ch6', 'ch7', 'ch8', 'global_s', 'trial_s'],
                    'buffer_flags': list(self._muv_is_buffer)
                }
            
            # FFT: Frequency domain data with all channels per row
            if len(self._fft_rows) > 0:
                fft_matrix = np.vstack(self._fft_rows)
                result['FFT'] = {
                    'data': fft_matrix,  # rows = timestamps, cols = [trial_s, global_s, ch1_bins..., ..., ch8_bins...]
                    'structure': 'time_by_channel_bins',
                    'freqs': self._fft_freqs,
                    'columns': []
                }
            
            # PSD: Power spectral density with all channels per row
            if len(self._psd_rows) > 0:
                psd_matrix = np.vstack(self._psd_rows)
                result['PSD'] = {
                    'data': psd_matrix,  # rows = timestamps, cols = [trial_s, global_s, ch1_bins..., ..., ch8_bins...]
                    'structure': 'time_by_channel_bins',
                    'freqs': self._psd_freqs,
                    'columns': []
                }
            
            return result

    def _on_sample_tick(self, current_sched_ms: int):
        if not self.is_recording:
            return
        # If trials finished, stop and mark complete
        if not getattr(self.engine, 'run_active', False):
            was_recording = bool(self.is_recording)
            self.stop()
            # Only mark ready if we had been recording and at least one data type selected
            if was_recording and any(self.selected_types.values()):
                try:
                    if self.export_status is not None:
                        self.export_status.setText("Recording complete - Ready to export")
                except Exception:
                    pass
            return
        try:
            # Timestamps
            global_time_s = current_sched_ms / 1000.0
            # trial_time_s is schedule-aligned relative to trial start minus before window
            trial_time_s = (-float(self.timer_widget.time_before.value())
                            + self.sync.get_trial_relative_seconds())

            # De-duplication: compute sample index at sampling rate and skip duplicates
            sample_index = int(global_time_s * self._sample_rate + 1e-6)
            if sample_index <= self._last_sample_index:
                return

            # Collect samples for each selected data type
            with self._data_lock:
                # muV: Keep the working logic unchanged
                if self.selected_types.get('muV'):
                    muv_sample = self._collect_muv_sample()
                    if muv_sample is not None:
                        muv_row = np.append(muv_sample, [global_time_s, trial_time_s])
                        if muv_row.shape[0] == 10:
                            self._muv_rows.append(muv_row.astype(float))
                            # Track whether this sample occurred during buffer phase
                            try:
                                self._muv_is_buffer.append(self.engine.phase == 'buffer')
                            except Exception:
                                self._muv_is_buffer.append(False)
                
                # FFT: Store frequency data for all channels in a single row per timestamp
                if self.selected_types.get('FFT'):
                    fft_channel_data = self._collect_fft_sample()
                    if fft_channel_data is not None and len(fft_channel_data) > 0:
                        # Ensure channels are in order and flatten all bins across channels
                        channel_bins = []
                        for _, freq_amplitudes in fft_channel_data[:8]:
                            channel_bins.append(np.asarray(freq_amplitudes, dtype=float))
                        if len(channel_bins) > 0:
                            all_bins_flat = np.concatenate(channel_bins)
                            fft_row = np.concatenate(([trial_time_s, global_time_s], all_bins_flat))
                            self._fft_rows.append(fft_row.astype(float))
                
                # PSD: Store power data for all channels in a single row per timestamp
                if self.selected_types.get('PSD'):
                    psd_channel_data = self._collect_psd_sample()
                    if psd_channel_data is not None and len(psd_channel_data) > 0:
                        channel_bins = []
                        for _, freq_powers in psd_channel_data[:8]:
                            channel_bins.append(np.asarray(freq_powers, dtype=float))
                        if len(channel_bins) > 0:
                            all_bins_flat = np.concatenate(channel_bins)
                            psd_row = np.concatenate(([trial_time_s, global_time_s], all_bins_flat))
                            self._psd_rows.append(psd_row.astype(float))
                
                self._last_sample_index = sample_index
        except Exception:
            # Fail silently per tick; overall recording continues
            pass

    def _on_run_completed(self):
        # Engine signaled run completion; ensure recording stops and status updates
        was_recording = bool(self.is_recording)
        if was_recording:
            self.stop()
        # Only show completion ready status if we were actually recording
        if was_recording:
            try:
                if self.export_status is not None:
                    self.export_status.setText("Recording complete - Ready to export")
            except Exception:
                pass

    def _collect_muv_sample(self):
        """Collect muV data sample - using the working logic"""
        try:
            data = self.data_collector.collect_data_muV()
            if data:
                return self._extract_latest_from_channels(data)
        except Exception:
            pass
        return None

    def _collect_fft_sample(self):
        """Collect FFT data - returns list of rows for all channels"""
        try:
            fft_tuple = self.data_collector.collect_data_FFT()
            if fft_tuple:
                freqs, amplitudes = fft_tuple
                # Store frequency info on first collection
                if self._fft_freqs is None:
                    self._fft_freqs = freqs
                
                # Create one row per channel with all frequency bins
                channel_rows = []
                for ch_idx, amplitude_array in enumerate(amplitudes[:8]):
                    if amplitude_array is not None and len(amplitude_array) > 0:
                        # Row: [freq_bin_values..., global_s, trial_s, channel_id]
                        channel_rows.append((ch_idx + 1, amplitude_array))
                return channel_rows
        except Exception:
            pass
        return None

    def _collect_psd_sample(self):
        """Collect PSD data - returns list of rows for all channels"""
        try:
            psd_tuple = self.data_collector.collect_data_PSD()
            if psd_tuple:
                freqs, powers = psd_tuple
                # Store frequency info on first collection
                if self._psd_freqs is None:
                    self._psd_freqs = freqs
                
                # Create one row per channel with all frequency bins
                channel_rows = []
                for ch_idx, power_array in enumerate(powers[:8]):
                    if power_array is not None and len(power_array) > 0:
                        # Row: [freq_bin_values..., global_s, trial_s, channel_id]
                        channel_rows.append((ch_idx + 1, power_array))
                return channel_rows
        except Exception:
            pass
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
        """Export cached data to separate files by type with datetime naming."""
        cached_data = self.get_cached_data_by_type()
        if not cached_data:
            return False
        
        try:
            os.makedirs(directory_path, exist_ok=True)
            ext = file_type.lower()
            if ext.startswith("."):
                ext = ext[1:]
            
            exported_files = []
            
            # Export each data type to separate file
            for data_type, data_info in cached_data.items():
                filename = f"record{data_type}_{self._recording_timestamp}"
                matrix = data_info['data']
                columns = data_info['columns']
                
                if ext == "csv":
                    path = os.path.join(directory_path, f"{filename}.csv")
                    self._write_csv_file(path, matrix, columns, data_info)
                    exported_files.append(path)
                elif ext == "npy":
                    path = os.path.join(directory_path, f"{filename}.npy")
                    np.save(path, matrix)
                    exported_files.append(path)
                elif ext == "npz":
                    path = os.path.join(directory_path, f"{filename}.npz")
                    save_dict = {'data': matrix, 'columns': columns}
                    if 'freqs' in data_info:
                        save_dict['freqs'] = data_info['freqs']
                    np.savez(path, **save_dict)
                    exported_files.append(path)
            
            return len(exported_files) > 0
            
        except Exception:
            return False
    
    def _write_csv_file(self, path: str, matrix: np.ndarray, columns: list, data_info: dict):
        """Write CSV file with appropriate format for each data type"""
        num_cols = matrix.shape[1]
        
        with open(path, "w", encoding="utf-8") as f:
            # Special handling for FFT/PSD time-by-channel-bins structure
            if data_info.get('structure') == 'time_by_channel_bins' and 'freqs' in data_info:
                num_channels = 8
                freqs = list(data_info['freqs']) if data_info['freqs'] is not None else []
                num_freq_bins = len(freqs)

                # 1) Frequency header line: label + two blanks (trial_s, global_s) + freqs repeated per channel
                freq_header_line = ["# Frequencies (Hz)", ""]
                for _ in range(num_channels):
                    freq_header_line.extend([f"{f:.2f}" for f in freqs])
                f.write(",".join(freq_header_line) + "\n")

                # 2) First header: bin1..binN repeated per channel
                bin_labels = ["trial_s", "global_s"]
                bin_labels.extend([f"bin{i+1}" for _ in range(num_channels) for i in range(num_freq_bins)])
                f.write(",".join(bin_labels) + "\n")

                # 3) Second header: channel labels spanning each bin block
                ch_labels = ["", ""]
                for ch in range(num_channels):
                    ch_labels.extend([f"ch{ch+1}" for _ in range(num_freq_bins)])
                f.write(",".join(ch_labels) + "\n")

                # 4) Data rows (already row-oriented)
                for row in matrix:
                    f.write(",".join(f"{v:.10f}" for v in row) + "\n")
                return

            # Default generic writer, with special handling for muV to transpose for a long format
            is_muv = data_info.get('structure') == 'channels+time'
            buffer_flags = data_info.get('buffer_flags') if is_muv else None
            if is_muv:
                # matrix is 10 x N in current structure ([ch1..ch8, global_s, trial_s] rows)
                # Transpose to N x 10 so each row is a sample timestamp
                transposed = matrix.T  # shape: (N_samples, 10)
                # Header uses the provided columns order
                f.write(",".join(columns) + "\n")
                trial_col_index = None
                try:
                    trial_col_index = columns.index('trial_s')
                except Exception:
                    trial_col_index = None
                # Write each sample row, prefix trial_s with 'B - ' when buffer flag is True
                for i in range(transposed.shape[0]):
                    row_vals = []
                    for j, v in enumerate(transposed[i]):
                        if (trial_col_index is not None) and (j == trial_col_index) and buffer_flags is not None:
                            try:
                                is_buf = bool(buffer_flags[i])
                            except Exception:
                                is_buf = False
                            if is_buf:
                                row_vals.append(f"B - {float(v):.10f}")
                            else:
                                row_vals.append(f"{float(v):.10f}")
                        else:
                            row_vals.append(f"{float(v):.10f}")
                    f.write(",".join(row_vals) + "\n")
                return
            else:
                # Generic non-muV writer: Column headers: label,sample_0,sample_1,sample_2,...
                f.write("label," + ",".join(str(i) for i in range(num_cols)) + "\n")
                # Data rows (matrix expected row-oriented)
                for r, label in enumerate(columns):
                    if r < matrix.shape[0]:
                        row = matrix[r]
                        row_vals = ",".join(f"{v:.10f}" for v in row)
                        f.write(f"{label},{row_vals}\n")


