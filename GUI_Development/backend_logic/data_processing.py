import numpy as np
from brainflow.data_filter import DataFilter, FilterTypes, DetrendOperations, NoiseTypes
from scipy.interpolate import CubicSpline
# Include this for manual implementation
import scipy.signal as signal_lib
    #butter, filtfilt, lfilter

def get_filtered_data(board_shim, num_points, eeg_channels, preprocessing):
    """
    Retrieves and applies signal processing to EEG data based on GUI selections.

    :param board_shim: The BoardShim object to fetch data from.
    :param num_points: Number of data points to retrieve.
    :param eeg_channels: List of EEG channels to process.
    :param preprocessing: Dictionary containing GUI elements for preprocessing.
    :return: Processed EEG data dictionary {channel: filtered_signal}
    """
    data = board_shim.get_current_board_data(num_points)
    processed_data = {}

    for channel in eeg_channels:
        signal = data[channel].copy()  # work on a copy

        # remove mains noise first
        DataFilter.remove_environmental_noise(signal, 125, NoiseTypes.FIFTY_AND_SIXTY)

        # 1) Detrend
        if preprocessing["DetrendOnOff"].isChecked():
            signal = detrend_signal(signal)

        # 2) Band-pass
        if preprocessing["BandPassOnOff"].isChecked():
            num_bp = preprocessing["NumberBandPass"].value()
            bp_ranges = []
            for i in range(1, num_bp + 1):
                # dynamically look up the start/end widgets
                start = float(preprocessing[f"BP{i}Start"].text())
                end   = float(preprocessing[f"BP{i}End"].text())
                # only accept strictly positive, ascending ranges
                if 0 < start < end:
                    bp_ranges.append((start, end))
            # only filter if we got at least one valid band
            if bp_ranges:
                signal = bandpass_filters(signal, bp_ranges)

        # 3) Band-stop
        if preprocessing["BandStopOnOff"].isChecked():
            num_bs = preprocessing["NumberBandStop"].value()
            bs_ranges = []
            for i in range(1, num_bs + 1):
                start = float(preprocessing[f"BStop{i}Start"].text())
                end   = float(preprocessing[f"BStop{i}End"].text())
                if 0 < start < end:
                    bs_ranges.append((start, end))
            if bs_ranges:
                signal = bandstop_filters(signal, bs_ranges)

        # 4) (Stub) FastICA
        if preprocessing["FastICA"].isChecked():
            # TODO: implement ICA
            pass

        # 5) Baseline correction
        if preprocessing["BaselineCorrection"].isChecked():
            signal = Baseline(signal)

        # 6) Smoothing
        window_size = preprocessing["Window"].value()
        if preprocessing["Average"].isChecked():
            signal = mean_smoothing(signal, window_size)
        if preprocessing["Median"].isChecked():
            signal = median_smoothing(signal, window_size)

        processed_data[channel] = signal

    return processed_data


def bandpass_filters(signal, freq_ranges, sampling_rate=125, order=4):
    """
    Applies each valid band-pass in freq_ranges, ignoring any invalid ones.
    """
    # filter out any bad ranges just in case
    valid = [(s, e) for s, e in freq_ranges if 0 < s < e]
    for start_freq, end_freq in valid:
        DataFilter.perform_bandpass(
            signal,
            sampling_rate,
            start_freq,
            end_freq,
            order,
            FilterTypes.BUTTERWORTH.value,
            0
        )
    return signal


def bandstop_filters(signal, freq_ranges, sampling_rate=125, order=4):
    """
    Applies each valid band-stop in freq_ranges, ignoring any invalid ones.
    """
    valid = [(s, e) for s, e in freq_ranges if 0 < s < e]
    for start_freq, end_freq in valid:
        DataFilter.perform_bandstop(
            signal,
            sampling_rate,
            start_freq,
            end_freq,
            order,
            FilterTypes.BUTTERWORTH.value,
            0
        )
    return signal


def detrend_signal(signal):
    """Removes linear trends from EEG data if enabled."""
    DataFilter.detrend(signal, DetrendOperations.LINEAR.value)
    return signal


def ICA(signal):
    pass

def Baseline(signal):
    """
       Real-time baseline correction: subtracts the mean from the signal.
       Handles empty signals safely.

       :param signal: 1D NumPy array of EEG data
       :return:       Baseline-corrected signal (or original if empty)
       """
    if signal is None or len(signal) == 0:
        return signal  # return unchanged if empty or None

    # One way of implementing a basic form of baseline correction for each new window of data.
    # Subtracts the mean of the signal, effectively removing any DC offset.
    #DataFilter.detrend(signal, DetrendOperations.CONSTANT.value)

    return signal - np.mean(signal)


def interpolate_signal(data, upsample_factor=2):
    """Interpolates signal for smoother visualization."""
    x = np.arange(len(data))
    x_new = np.linspace(0, len(data) - 1, len(data) * upsample_factor)
    interpolator = CubicSpline(x, data)
    return interpolator(x_new)


def mean_smoothing(signal, window_size):
    """Applies a moving average filter."""

    # MANUAL IMPLEMENTATION
    # if window_size < 1:
    #     return signal
    # return np.convolve(signal, np.ones(window_size), 'valid') / window_size

    """Applies moving average smoothing using BrainFlow's built-in rolling filter."""
    if window_size < 1:
        return signal
    DataFilter.perform_rolling_filter(signal, window_size, NoiseTypes.MOVING_AVERAGE.value)

    return signal


def median_smoothing(signal, window_size):
    """Applies a moving median filter."""

    # MANUAL IMPLEMENTATION
    # if window_size < 1:
    #     return signal
    # if window_size % 2 == 0:
    #     window_size += 1
    #
    # half = window_size // 2
    # padded = np.pad(signal, (half, half), mode='edge')  # pad signal to handle boundaries
    # smoothed = []
    #
    # for i in range(len(signal)):
    #     window = padded[i:i + window_size]
    #     smoothed.append(np.median(window))
    #
    # return np.array(smoothed)

    if window_size < 1:
        return signal
    if window_size % 2 == 0:
        window_size += 1  # median filter kernel size must be odd
    return signal_lib.medfilt(signal, kernel_size=window_size)



