import numpy as np
from brainflow.data_filter import DataFilter, FilterTypes, DetrendOperations, NoiseTypes
from scipy.interpolate import CubicSpline
# Include this for manual implementation
#from scipy.signal import butter, filtfilt, lfilter


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
        signal = data[channel]

        DataFilter.remove_environmental_noise(signal,125,NoiseTypes.FIFTY_AND_SIXTY)


        # **Apply preprocessing based on GUI selections**
        if preprocessing["DetrendOnOff"].isChecked():
            signal = detrend_signal(signal)

        if preprocessing["BandPassOnOff"].isChecked():
            freq_ranges_bp = []
            # Default Values
            if preprocessing["NumberBandPass"].value() == 0:
                freq_ranges_bp.append((8.0, 13.0))
            # User-defined Values
            else:
                if preprocessing["NumberBandPass"].value() >= 1:
                    freq_ranges_bp.append((float(preprocessing["BP1Start"]. text()),
                                        float(preprocessing["BP1End"]. text())))
                if preprocessing["NumberBandPass"].value() >= 2:
                    freq_ranges_bp.append((float(preprocessing["BP2Start"]. text()),
                                        float(preprocessing["BP2End"]. text())))
            signal = bandpass_filters(signal, freq_ranges_bp) #pass

        if preprocessing["BandStopOnOff"].isChecked():
            freq_ranges_bs = []
            # Default Values
            if preprocessing["NumberBandStop"].value() == 0:
                freq_ranges_bs.append((58.0, 62.0))
            # User-defined Values
            else:
                if preprocessing["NumberBandStop"].value() >= 1:
                    freq_ranges_bs.append((float(preprocessing["BStop1Start"].text()),
                                           float(preprocessing["BStop1End"].text())))
                if preprocessing["NumberBandStop"].value() >= 2:
                    freq_ranges_bs.append((float(preprocessing["BStop2Start"].text()),
                                           float(preprocessing["BStop2End"].text())))
            signal = bandstop_filters(signal, freq_ranges_bs) #pass

        if preprocessing["FastICA"].isChecked():
            pass # DO ICA when we know how to

        if preprocessing["BaselineCorrection"].isChecked():
            pass # DO Baseline Correct when we know how to

        processed_data[channel] = signal  # Always interpolate

    return processed_data


def bandpass_filters(signal, freq_ranges, sampling_rate=128,order=4 ):
    """
    Applies multiple bandpass filters in sequence, one for each (start_freq, end_freq) pair,
    using BrainFlow's built-in bandpass filter.

    :param signal:         1D NumPy array of your EEG (or other) data
    :param sampling_rate:  Sampling rate in Hz
    :param freq_ranges:    List of tuples: [(start_freq1, end_freq1), (start_freq2, end_freq2), ...]
    :param order:          Filter order
    :return:               Filtered signal
    """
    for (start_freq, end_freq) in freq_ranges:
        DataFilter.perform_bandpass(
            signal,
            sampling_rate,
            start_freq,
            end_freq,
            order,
            FilterTypes.BUTTERWORTH.value,  # or FilterTypes.BUTTERWORTH_ZERO_PHASE.value if desired
            0  # ripple (used only for Chebyshev)
        )


        # Manual Implementation: LESS RELIABLE
        # nyquist = sampling_rate / 2
        # low = start_freq / nyquist
        # high = end_freq / nyquist
        # b, a = butter(order, [low, high], btype='band')
        # signal = lfilter(b, a, signal)

    return signal


def bandstop_filters(signal, freq_ranges, sampling_rate=128,  order=4 ):
    """
        Applies multiple bandstop filters in sequence, one for each (start_freq, end_freq) pair,
        using BrainFlow's built-in bandpass filter.

        :param signal:         1D NumPy array of your EEG (or other) data
        :param sampling_rate:  Sampling rate in Hz
        :param freq_ranges:    List of tuples: [(start_freq1, end_freq1), (start_freq2, end_freq2), ...]
        :param order:          Filter order
        :return:               Filtered signal
    """

    for (start_freq, end_freq) in freq_ranges:
        DataFilter.perform_bandstop(
            signal,
            sampling_rate,
            start_freq,
            end_freq,
            order,
            FilterTypes.BUTTERWORTH.value,  # or FilterTypes.BUTTERWORTH_ZERO_PHASE.value if desired
            0  # ripple (used only for Chebyshev)
        )


        # Manual Implementation: LESS RELIABLE
        # nyquist = sampling_rate / 2
        # low = start_freq / nyquist
        # high = end_freq / nyquist
        # b, a = butter(order, [low, high], btype='bandstop')
        # signal = lfilter(b, a, signal)

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
