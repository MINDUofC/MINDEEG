import numpy as np
from brainflow import AggOperations
from brainflow.data_filter import DataFilter, FilterTypes, DetrendOperations, NoiseTypes
from scipy.interpolate import CubicSpline
# Include this for manual implementation
import scipy.signal as signal_lib
    #butter, filtfilt, lfilter

def get_filtered_data(board_shim, num_points, eeg_channels, preprocessing):
    """
    Retrieves raw EEG data and applies optional preprocessing steps,
    delegating all BP/BS logic to the helper functions.
    """
    data = board_shim.get_current_board_data(num_points)
    processed_data = {}

    for channel in eeg_channels:
        signal = data[channel].copy()

        # 1) Remove mains hum (50/60 Hz)
        DataFilter.remove_environmental_noise(
            data=signal,
            sampling_rate=125,
            noise_type=NoiseTypes.FIFTY_AND_SIXTY
        )

        # 2) Detrend if requested
        if preprocessing["DetrendOnOff"].isChecked():
            signal = detrend_signal(signal)

        # 3) Band-pass / low-pass / high-pass (all logic inside bandpass_filters)
        if preprocessing["BandPassOnOff"].isChecked():
            signal = bandpass_filters(
                signal,
                preprocessing,
                sampling_rate=125,
                order=4
            )

        # 4) Band-stop / low-cut / high-cut (all logic inside bandstop_filters)
        if preprocessing["BandStopOnOff"].isChecked():
            signal = bandstop_filters(
                signal,
                preprocessing,
                sampling_rate=125,
                order=4
            )

        processed_data[channel] = signal


    # 5) Smoothing (applied to each channel individually)
    for channel in eeg_channels:
        if channel in processed_data:
            signal = processed_data[channel]
            window_size = preprocessing["Window"].value()
            if preprocessing["Average"].isChecked():
                signal = mean_smoothing(signal, window_size)
            if preprocessing["Median"].isChecked():
                signal = median_smoothing(signal, window_size)
            processed_data[channel] = signal

    return processed_data


def bandpass_filters(signal, preprocessing, sampling_rate=125, order=4):
    """
    Applies each user-configured filter slot as either:
      • Low-pass   (blank/zero start, valid end)
      • High-pass  (valid start, blank/zero end)
      • Band-pass  (both present, start < end)
    Invalid or nonsensical entries are skipped.
    """
    num_bp = preprocessing["NumberBandPass"].value()

    # Determine FIR/IIR mode once and read window (for FIR only) from combo userData
    try:
        fir_iir_mode = preprocessing["BPTypeFIR_IIR"].currentText().strip().upper()
    except Exception:
        fir_iir_mode = "IIR"
    window = None
    if fir_iir_mode == "FIR":
        try:
            window = preprocessing["FIRWindowType"].currentData()
            if window is None:
                window = "hamming"
        except Exception:
            window = "hamming"

    for i in range(1, num_bp + 1):
        raw_start = preprocessing[f"BP{i}Start"].text().strip()
        raw_end   = preprocessing[f"BP{i}End"].text().strip()

        # Skip completely empty slots
        if not raw_start and not raw_end:
            continue

        # Parse floats (or None on failure/blank)
        try:
            start = float(raw_start) if raw_start else None
        except ValueError:
            start = None
        try:
            end   = float(raw_end)   if raw_end   else None
        except ValueError:
            end = None

        if fir_iir_mode == "FIR":
            # FIR branch: windowed FIR with 101 taps, zero-phase via filtfilt
            try:
                # 1) True band-pass
                if start and end and start < end:
                    taps = signal_lib.firwin(
                        numtaps=101,
                        cutoff=[start, end],
                        pass_zero=False,
                        window=window,
                        fs=sampling_rate
                    )
                    signal = signal_lib.filtfilt(taps, [1.0], signal, axis=-1)

                # 2) Low-pass only (no valid start ⇒ pass all below `end`)
                elif end and (not start or start <= 0):
                    taps = signal_lib.firwin(
                        numtaps=101,
                        cutoff=end,
                        pass_zero=True,
                        window=window,
                        fs=sampling_rate
                    )
                    signal = signal_lib.filtfilt(taps, [1.0], signal, axis=-1)

                # 3) High-pass only (no valid end ⇒ pass all above `start`)
                elif start and (not end or end <= 0):
                    taps = signal_lib.firwin(
                        numtaps=101,
                        cutoff=start,
                        pass_zero=False,
                        window=window,
                        fs=sampling_rate
                    )
                    signal = signal_lib.filtfilt(taps, [1.0], signal, axis=-1)
                # else: invalid combination → skip
            except Exception:
                # Skip slot on FIR failure rather than raising
                pass
        else:
            # IIR branch (existing behavior via BrainFlow Butterworth)
            # 1) True band-pass
            if start and end and start < end:
                DataFilter.perform_bandpass(
                    data=signal,
                    sampling_rate=sampling_rate,
                    start_freq=start,
                    stop_freq=end,
                    order=order,
                    filter_type=FilterTypes.BUTTERWORTH.value,
                    ripple=0
                )

            # 2) Low-pass only (no valid start ⇒ pass all below `end`)
            elif end and (not start or start <= 0):
                DataFilter.perform_lowpass(
                    data=signal,
                    sampling_rate=sampling_rate,
                    cutoff=end,
                    order=order,
                    filter_type=FilterTypes.BUTTERWORTH.value,
                    ripple=0
                )

            # 3) High-pass only (no valid end ⇒ pass all above `start`)
            elif start and (not end or end <= 0):
                DataFilter.perform_highpass(
                    data=signal,
                    sampling_rate=sampling_rate,
                    cutoff=start,
                    order=order,
                    filter_type=FilterTypes.BUTTERWORTH.value,
                    ripple=0
                )

        # else: invalid combination → skip

    return signal


def bandstop_filters(signal, preprocessing, sampling_rate=125, order=4):
    """
    Applies each user-configured slot as either:
      • Band-stop  (both present, start < end)
      • High-pass  (blank/zero start ⇒ cut below `end`)
      • Low-pass   (blank/zero end   ⇒ cut above `start`)
    Invalid entries are skipped silently.
    """
    num_bs = preprocessing["NumberBandStop"].value()

    for i in range(1, num_bs + 1):
        raw_start = preprocessing[f"BStop{i}Start"].text().strip()
        raw_end   = preprocessing[f"BStop{i}End"].text().strip()

        if not raw_start and not raw_end:
            continue

        try:
            start = float(raw_start) if raw_start else None
        except ValueError:
            start = None
        try:
            end   = float(raw_end)   if raw_end   else None
        except ValueError:
            end = None

        # 1) True band-stop
        if start and end and start < end:
            DataFilter.perform_bandstop(
                data=signal,
                sampling_rate=sampling_rate,
                start_freq=start,
                stop_freq=end,
                order=order,
                filter_type=FilterTypes.BUTTERWORTH.value,
                ripple=0
            )

        # 2) High-pass style (remove below `end`) when start missing
        elif end and (not start or start <= 0):
            DataFilter.perform_highpass(
                data=signal,
                sampling_rate=sampling_rate,
                cutoff=end,
                order=order,
                filter_type=FilterTypes.BUTTERWORTH.value,
                ripple=0
            )

        # 3) Low-pass style (remove above `start`) when end missing
        elif start and (not end or end <= 0):
            DataFilter.perform_lowpass(
                data=signal,
                sampling_rate=sampling_rate,
                cutoff=start,
                order=order,
                filter_type=FilterTypes.BUTTERWORTH.value,
                ripple=0
            )

        # else: skip invalid slots

    return signal


def detrend_signal(signal):
    """Removes linear trends from EEG data if enabled."""
    DataFilter.detrend(signal, DetrendOperations.LINEAR.value)
    return signal


def get_filtered_data_with_ica(board_shim, num_points, eeg_channels, preprocessing, ica_manager=None):
    """
    Retrieves raw EEG data and applies preprocessing steps including ICA if enabled.
    This function integrates with the ICA manager for real-time ICA processing.
    """
    # Get preprocessed data without ICA
    processed_data = get_filtered_data(board_shim, num_points, eeg_channels, preprocessing)
    
    # Apply ICA if enabled and manager is provided
    if preprocessing["FastICA"].isChecked() and ica_manager is not None:
        try:
            # Process through ICA manager
            processed_data = ica_manager.process_data(processed_data)
        except Exception as e:
            print(f"ICA processing failed: {e}")
            # Continue with non-ICA data if ICA fails
    
    return processed_data

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
    DataFilter.perform_rolling_filter(signal, window_size, AggOperations.MEAN)

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
    DataFilter.perform_rolling_filter(signal, window_size, AggOperations.MEDIAN)

    return signal
