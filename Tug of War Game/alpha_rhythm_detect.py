import argparse  # For parsing command-line arguments
import logging   # For logging informational and error messages
import sys       # For interacting with the Python runtime environment
import time      # For adding delays when configuring the board
import threading  # For creating a separate thread for data processing
from queue import Queue  # For inter-thread communication
import numpy as np  # For numerical operations
from brainflow.board_shim import BoardShim, BrainFlowInputParams  # For interfacing with EEG hardware
from brainflow.data_filter import DataFilter, FilterTypes, DetrendOperations  # For preprocessing EEG data


def _ensure_even_length(arr: np.ndarray) -> np.ndarray:
    """
    Helper function that trims the last sample if the array length is odd,
    because many FFT implementations require an even number of points.
    Input:
      arr: 1D numpy array of signal samples
    Returns:
      A numpy array with even length
    """
    return arr if len(arr) % 2 == 0 else arr[:-1]

class AlphaRhythmDetector(threading.Thread):
    def __init__(self, board_shim):
        super().__init__()


        # TODO: ADD THE IMPLEMENTATION OF MAKING USE OF MULTIPLE BOARDS FOR PLAYER 1 AND PLAYER 2
        # Store the board shim and retrieve board information
        self.board_shim = board_shim
        self.board_id = board_shim.get_board_id()

        # Retrieve the EEG channel indices for the given board
        self.eeg_channels = BoardShim.get_eeg_channels(self.board_id)
        self.sampling_rate = BoardShim.get_sampling_rate(self.board_id)

        # Define FFT Window Parameters
        self.window_points = int(6 * self.sampling_rate)
        self.window_points = self.window_points if self.window_points % 2 == 0 else self.window_points - 1
        
        self.z_threshold = float(1.0)


        # Calibration/ Detection States
        self.state = "IDLE"  # Can be "IDLE", "CALIBRATING", "DETECTING"
        self._is_calibrating = False
        self._calib_end_time = 0.0 # Timestamp when calibration ends

        # Calibration Data - Player 1
        self._P1_calibe =  [] # Store calibration data for Player 1
        self._P1_mean = None
        self._P1_std = None

        # Calibration Data - Player 2
        self._P2_calibe =  [] # Store calibration data for Player 2
        self._P2_mean = None
        self._P2_std = None

        # Detection State - Player 1 
        self._P1_active = False

        # Detection State - Player 2
        self._P2_active = False

        self._stop_event = threading.Event()
        self.events_queue: Queue ()

    def calibrated(self) -> bool:
        return (
            self._P1_mean is not None and self._P1_std and self.P1_std > 0 and
            self._P2_mean is not None and self._P2_std and self.P2_std > 0
        )

    def start_callibration (self, duration_sec: float) -> None:
        """Begin calibration process for both players over the specified duration.
        
        Parameters:
          duration_sec: Duration in seconds for calibration data collection.
        
        Returns:
          None
        
        """
        # Clear previous calibration data
        self._P1_calibe.clear()
        self._P2_calibe.clear()

        self._P1_mean = self._P1_std = None
        self._P2_mean = self._P2_std = None

        self._is_calibrating = True
        self._calib_end_time = time.time() + max(3, int(duration_sec))  # Minimum 3 seconds

    def stop(self) -> None:
        """ Stop the detector thread """
        self._stop_event.set()


    def determine_alpha_power(self, data: np.ndarray, channel: int) -> float:
        """Calculate alpha band power from EEG data segment.
        
        Parameters:
          data: 1D numpy array of EEG signal samples.
            channel: Index of the EEG channel to analyze.

        Returns:
            Alpha band power value.
            """
        if data is None or data.size == 0 or data.shape[0] <= self.window_points:
            return None
        
        powers = []
        for ch in self.eeg_channels[:6]:  # Use first 6 EEG channels
            signal = np.copy(data[ch, -self.window_points:])

            # Preprocessing of the signals for alpha power calculation
            DataFilter.detrend(signal, DetrendOperations.LINEAR.value) # Remove linear trend
            DataFilter.remove_environmental_noise(signal, self.sampling_rate, 2) # Notch filter at 50Hz

            DataFilter.perform_bandpass(
                signal,
                self.sampling_rate,
                8.0,
                12.0,
                4,
                FilterTypes.BUTTERWORTH_ZERO_PHASE,
                0
            )


            signal = _ensure_even_length(signal)
            if len(signal) < 4:
                continue
            try:
                fft_values = DataFilter.perform_fft(signal, 2)
            except Exception as e:
                logging.error(f"FFT computation failed: {e}")
                continue

            # Normalize FFT values by number of points
            fft_values = fft_values / len(signal)
            # Frequency resolution
            freq_res = np.fft.rfftfreq(len(signal), 1/self.sampling_rate)
            idx = np.where((freq_res >= 8.0) & (freq_res <= 12.0))[0]
            if idx.size == 0:
                continue

            # Compute power = squared magnitude of FFT coefficients in the band
            power_band = np.abs(fft_values[idx]) ** 2
            # Average power in the alpha band for this channel
            powers.append(np.mean(power_band))

        if len(powers) == 0:
            # If no valid channels, return None
            return None
        
        # Average power across channels for a single scalar metric
        mean_alpha_power = np.mean(powers)
        return mean_alpha_power

    def _emit(self, event_type: str, player: int) -> None:
        """Helper to enqueue detection events."""
        try: 
            self.events_queue.put_nowait((event_type, player))
        except Exception as e:
            logging.error(f"Failed to enqueue event {event_type} for player {player}: {e}")
        
        # Call the on_event callback if provided 
        if self.on_event:
            try:
                self.on_event(event_type, player)
            except Exception as e:
                logging.error(f"on_event callback failed for event {event_type} player {player}: {e}")

    def run(self) -> None:
        last_calib_sample = 0.0
        while not self._stop_event.is_set():
            try:
                data = self.board_shim.get_current_board_data(self.window_points)

                if self._is_calibrating:
                    now = time.time()
                    if now - last_calib_sample >= 1.0:
                        last_calib_sample = now
                        P1_alpha_power = self.determine_alpha_power(data, self.eeg_channels[0:6])
                        P2_alpah_power = self.determine_alpha_power(data, self.eeg_channels[6:12])
                        if P1_alpha_power is not None:
                            self._P1_calibe.append(P1_alpha_power)
                        if P2_alpah_power is not None:
                            self._P2_calibe.append(P2_alpah_power)
                    if time.time() >= self._calib_end_time:
                        self._is_calibrating = False
                        # Compute calibration stats for Player 1
                        if len(self._P1_calibe) > 0:
                            self._P1_mean = float(np.mean(self._P1_calibe))
                            self._P1_std = float(np.std(self._P1_calibe)) or 1.0

                        # Compute calibration stats for Player 2
                        if len(self._P2_calibe) > 0:
                            self._P2_mean = float(np.mean(self._P2_calibe))
                            self._P2_std = float(np.std(self._P2_calibe)) or 1.0
                        logging.info(f"Calibration complete. P1 Mean: {self._P1_mean}, Std: {self._P1_std}; "
                                     f"P2 Mean: {self._P2_mean}, Std: {self._P2_std}")
                else:
                    if not self.calibrated():
                        time.sleep(0.1)
                        continue  # Wait until calibration is done
                    # Detection Phase
                    P1_alpha_power = self.determine_alpha_power(data, self.eeg_channels[0:6])
                    P2_alpha_power = self.determine_alpha_power(data, self.eeg_channels[6:12])
                    if P1_alpha_power is not None and self._P1_std and self._P1_std > 0:
                        P1_z_score = (P1_alpha_power - self._P1_mean) / self._P1_std
                        if not self._P1_active and P1_z_score > self.z_threshold:
                            self._P1_active = True
                            self._emit("P1_start", player=1)
                        elif self._P1_active and P1_z_score <= self.z_threshold:
                            self._P1_active = False
                            self._emit("P1_stop", player=1)
                    if P2_alpha_power is not None and self._P2_std and self._P2_std > 0:
                        P2_z_score = (P2_alpha_power - self._P2_mean) / self._P2_std
                        if not self._P2_active and P2_z_score > self.z_threshold:
                            self._P2_active = True
                            self._emit("P2_start", player=2)
                        elif self._P2_active and P2_z_score <= self.z_threshold:
                            self._P2_active = False
                            self._emit("P2_stop", player=2)
                time.sleep(0.1)
            except Exception as e:
                logging.error(f"AlphaRhythmDetector encountered an error: {e}")
                time.sleep(0.5)


