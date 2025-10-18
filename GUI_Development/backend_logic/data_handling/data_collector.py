import numpy as np
from brainflow import AggOperations
from brainflow.data_filter import DataFilter, FilterTypes, DetrendOperations, NoiseTypes
from scipy.interpolate import CubicSpline
from scipy.signal import windows
from PyQt5.QtCore import QTimer
import backend_logic.data_handling.data_processing as dp
from scipy.ndimage import uniform_filter1d
from scipy.signal import welch, windows


class CentralizedDataCollector:
    def __init__(self, board_shim, eeg_channels, preprocessing, ica_manager=None):
        self.board_shim = board_shim
        self.eeg_channels = eeg_channels
        self.preprocessing = preprocessing
        self.ica_manager = ica_manager
        
        # Initialize board parameters
        self.sampling_rate = None
        if board_shim:
            from brainflow.board_shim import BoardShim
            self.sampling_rate = BoardShim.get_sampling_rate(board_shim.get_board_id())
        
        # Init 3 different num_points for different plots
        # Reduced to 4 seconds for better performance (33% less processing per frame)
        if self.sampling_rate:
            self.nump_muV = int(4 * self.sampling_rate)
            self.nump_FFT = int(4 * self.sampling_rate)
        else:
            self.nump_muV = 500  # Default for 125Hz * 4 seconds
            self.nump_FFT = 500
        
            # ─────────────────────────────────────────────────────
            # 📐 PSD Theory & Resolution Explanation:
            #
            # Frequency Resolution = fs / N
            # For 1.5 Hz resolution at fs = 125 Hz:
            #     N = fs / 1.5 = 83.33 ≈ 84 samples needed
            # Time required for 84 samples: 84 / 125 = 0.672 seconds
            #
            # ➤ We're using a 0.672 second window (N = 84) (0.008 seconds a sample * 84 samples = 0.672
            # ➤ We update the plot every 0.672 / 3 = 224ms (smoother updates)
            # ➤ Using Welch method to average overlapping FFT windows for stability
            # ─────────────────────────────────────────────────────

        self.nump_PSD = 84  # for 1.5 Hz resolution

        # Set board_on status based on whether we have a valid board_shim
        self.board_on = board_shim is not None
        self.data = None
        self.data_FFT = None
        self.data_PSD = None
        
        # Cache windows for performance - compute once, reuse every frame
        self._hamming_window_FFT = None
        self._hamming_window_PSD = None
        
        # Pre-allocate arrays for performance
        self._freq_array_FFT = None
        self._freq_array_PSD = None

    


    def collect_data_muV(self):
        self.data = None
        if self.board_on:
            self.data = dp.get_filtered_data_with_ica(self.board_shim, self.nump_muV, self.eeg_channels, self.preprocessing, self.ica_manager)
            return self.data
        return None


    def collect_data_FFT(self):

        self.data_FFT = None  # Will be a 2D array of shape [[freqs], [Amplitude 1, Amplitude 2, Amplitude 3, etc.]]

        if self.board_on:
            data_for_FFT = dp.get_filtered_data_with_ica(self.board_shim, self.nump_FFT, self.eeg_channels, self.preprocessing, self.ica_manager)
            
            # Pre-allocate amplitude list for performance
            num_channels = len(self.eeg_channels)
            amplitudes = [None] * num_channels

            # Cache frequency array - compute once, reuse every frame
            if self._freq_array_FFT is None:
                self._freq_array_FFT = np.fft.rfftfreq(self.nump_FFT, d=1.0 / self.sampling_rate)
            freqs = self._freq_array_FFT
            
            # Cache Hamming window - compute once, reuse every frame
            if self._hamming_window_FFT is None:
                self._hamming_window_FFT = windows.hamming(self.nump_FFT)
            window = self._hamming_window_FFT

            for idx, ch in enumerate(self.eeg_channels):
                # Apply the window to the latest slice of EEG data
                signal = data_for_FFT[ch]
                if len(signal) < self.nump_FFT:
                    return None  # Not enough data yet — skip this frame

                signal = signal[-self.nump_FFT:]  # Now we can safely slice
                windowed_signal = signal * window

                # Perform FFT on windowed signal
                fft_vals = np.fft.rfft(windowed_signal)
                amplitude = np.abs(fft_vals)
                # Use index assignment instead of append for pre-allocated list
                amplitudes[idx] = amplitude


            # Return as tuple: (freqs, list_of_amplitudes)
            self.data_FFT = (freqs, amplitudes)
            return self.data_FFT
            
        return None



    def collect_data_PSD(self):

        self.data_PSD = None    


        if self.board_on:
            data_for_PSD = dp.get_filtered_data_with_ica(
                self.board_shim, 
                self.nump_PSD, 
                self.eeg_channels, 
                self.preprocessing,
                self.ica_manager
            )

            # Pre-allocate power list for performance
            num_channels = len(self.eeg_channels)
            powers = [None] * num_channels

            # Cache frequency array - compute once, reuse every frame
            if self._freq_array_PSD is None:
                self._freq_array_PSD = np.fft.rfftfreq(self.nump_PSD, d=1.0 / self.sampling_rate)
            freqs = self._freq_array_PSD

            # Cache Hamming window - compute once, reuse every frame
            nperseg = self.nump_PSD  # Full window size for Welch = 84 samples
            noverlap = int(0.5 * nperseg)  # 50% overlap for smoother averaging
            if self._hamming_window_PSD is None:
                self._hamming_window_PSD = windows.hamming(nperseg)
            window = self._hamming_window_PSD

            for idx, ch in enumerate(self.eeg_channels):
                signal = data_for_PSD[ch]
                if len(signal) < self.nump_PSD:
                    return None

                signal = signal[-self.nump_PSD:] * window
                freqs_welch, power = welch(
                    signal,
                    fs=self.sampling_rate,  # Ensure this is 125 Hz or as configured
                    window=window,
                    nperseg=self.nump_PSD,  # Should be high enough for clear frequency resolution
                    noverlap=int(0.5 * self.nump_PSD),
                    scaling='density'
                )

                log_power = np.log1p(power)  # Safe log
                log_power = uniform_filter1d(log_power, size=4)  # Smooth
                # Use index assignment instead of append for pre-allocated list
                powers[idx] = log_power

            # Return as tuple: (freqs, list_of_powers)
            self.data_PSD = (freqs, powers)
            return self.data_PSD

        return None

    
    def get_data(self):
        return self.data
    
    def set_board_shim(self, board_shim):
        """Update the board_shim reference and reinitialize sampling rate if needed."""
        self.board_shim = board_shim
        if board_shim:
            from brainflow.board_shim import BoardShim
            self.sampling_rate = BoardShim.get_sampling_rate(board_shim.get_board_id())
            # Update EEG channels in case board changed
            self.eeg_channels = BoardShim.get_eeg_channels(board_shim.get_board_id())
            # Recalculate num_points based on new sampling rate (4 seconds for performance)
            self.nump_muV = int(4 * self.sampling_rate)
            self.nump_FFT = int(4 * self.sampling_rate)
            # Clear cached arrays since num_points changed
            self._hamming_window_FFT = None
            self._hamming_window_PSD = None
            self._freq_array_FFT = None
            self._freq_array_PSD = None
            self.board_on = True
        else:
            self.sampling_rate = None
            self.board_on = False
    
    def get_board_shim(self):
        """Get the current board_shim reference."""
        return self.board_shim
        
    # HIGH LEVEL PLAN FOR RECORDING: 
    # I am going to need to send out a signal from each of the plots to a recorder file/manager, likely a function call that will have the same data it grabs from this file, and then it will also grab the time from GUI_timer, and then write it.    