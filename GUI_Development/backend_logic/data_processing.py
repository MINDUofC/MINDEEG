import numpy as np
from brainflow.data_filter import DataFilter, FilterTypes, DetrendOperations
from scipy.interpolate import CubicSpline


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

        # **Apply preprocessing based on GUI selections**
        if preprocessing["DetrendOnOff"].isChecked():
            signal = detrend_signal(signal)

        if preprocessing["BandPassOnOff"].isChecked():
            pass# signal = bandpass_filters()

        if preprocessing["BandStopOnOff"].isChecked():
            pass# signal = bandstop_filters()

        if preprocessing["FastICA"].isChecked():
            pass # DO ICA when we know how to

        if preprocessing["BaselineCorrection"].isChecked():
            pass # DO Baseline Correct when we know how to

        processed_data[channel] = interpolate_signal(signal)  # Always interpolate

    return processed_data


def bandpass_filters(signal, ):

    return signal


def bandstop_filters(signal, ):
    """Applies a bandstop filter with user-defined start and end frequencies."""

    return signal


def detrend_signal(signal):
    """Removes linear trends from EEG data if enabled."""
    DataFilter.detrend(signal, DetrendOperations.LINEAR.value)
    return signal


def ICA(signal):
    pass

def Baseline(signal):
    pass


def interpolate_signal(data, upsample_factor=2):
    """Interpolates signal for smoother visualization."""
    x = np.arange(len(data))
    x_new = np.linspace(0, len(data) - 1, len(data) * upsample_factor)
    interpolator = CubicSpline(x, data)
    return interpolator(x_new)
