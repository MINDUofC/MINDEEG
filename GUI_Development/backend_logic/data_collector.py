import numpy as np
from brainflow import AggOperations
from brainflow.data_filter import DataFilter, FilterTypes, DetrendOperations, NoiseTypes
from scipy.interpolate import CubicSpline
from scipy.signal import windows
from PyQt5.QtCore import QTimer
import data_processing as dp


class CentralizedDataCollector:
    def __init__(self, board_shim, eeg_channels, preprocessing):
        self.board_shim = board_shim
        self.eeg_channels = eeg_channels
        self.preprocessing = preprocessing

        # Init 3 different num_points for different plots
        self.nump_muV = int(6 * self.sampling_rate)
        self.nump_FFT = int(6 * self.sampling_rate)
        
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






        self.board_on = False
        self.data = None
        self.data_FFT = None
        self.data_PSD = None

    


    def collect_data_muV(self):
        self.data = None
        if self.board_on:
            self.data = dp.get_filtered_data_with_ica(self.board_shim, self.nump_muV, self.eeg_channels, self.preprocessing)
            return self.data
        return


    def collect_data_FFT(self):

        self.data_FFT = None  # Will be a 2D array of shape [[freqs], [Amplitude 1, Amplitude 2, Amplitude 3, etc.]]

        if self.board_on:
            data_for_FFT = dp.get_filtered_data_with_ica(self.board_shim, self.nump_FFT, self.eeg_channels, self.preprocessing)
            
            # Init temp amplitude array
            amplitudes = []

            # Calculate freqs
            freqs = np.fft.rfftfreq(self.num_points, d=1.0 / self.sampling_rate)
            

            # Create the window only once
            window = windows.hamming(self.num_points)

            for idx, ch in enumerate(self.eeg_channels):
                # Apply the window to the latest slice of EEG data
                signal = data_for_FFT[ch]
                if len(signal) < self.num_points:
                    return  # Not enough data yet — skip this frame

                signal = signal[-self.num_points:]  # Now we can safely slice
                windowed_signal = signal * window

                # Perform FFT on windowed signal
                fft_vals = np.fft.rfft(windowed_signal)
                amplitude = np.abs(fft_vals)
                amplitudes.append(amplitude)

                self.data_FFT = np.array([freqs, amplitudes])

            # Return the data_FFT array
            return self.data_FFT
            
        return



    def collect_data_PSD(self):
        self.data = None
        if self.board_on:
            self.data = dp.get_filtered_data_with_ica(self.board_shim, self.nump_PSD, self.eeg_channels, self.preprocessing)
            return self.data
        return

    
    def get_data(self):
        return self.data
    
        
    