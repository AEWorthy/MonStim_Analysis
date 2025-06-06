# emg_transformer.py
# Created 2024-05-31 by Andrew Worthy
# Last updated 2024-05-31 by Andrew Worthy
# Version 1.0

"""
Functions for calculations and transformations of EMG data.

This module provides various functions for processing and analyzing EMG (electromyography) data. 
It includes functions for bandpass filtering, baseline correction, rectification, 
and calculating different types of EMG amplitudes such as RMS (root mean square), average rectified, and peak-to-trough amplitudes. 
Additionally, it includes a function for calculating the mean and standard deviation of M-wave amplitudes and H-reflex amplitudes 
over multiple sessions, given specific parameters.

Functions:
- butter_bandpass: Butterworth bandpass filter design.
- butter_bandpass_filter: Apply Butterworth bandpass filter to data.
- correct_emg_to_baseline: Correct EMG data relative to pre-stimulus baseline amplitude.
- rectify_emg: Rectify EMG data by taking the absolute value.
- calculate_average_amplitude_rectified: Calculate the average rectified EMG amplitude between start and end times.
- calculate_peak_to_trough_amplitude: Calculate the peak-to-trough EMG amplitude between start and end times.
- calculate_rms_amplitude: Calculate the average RMS EMG amplitude between start and end times.
- calculate_average_amplitude_unrectified: Calculate the average unrectified EMG amplitude between start and end times.
- savgol_filter_y: Smoothen the data using Savitzky-Golay filtering.
- detect_plateau: Detect the plateau region in a reflex curve.
- get_avg_mmax: Get the M-wave amplitude and stimulus voltage at M-max. 

Note: This module requires the numpy and scipy libraries to be installed.
"""
import logging

import numpy as np
from scipy import signal


def butter_bandpass(lowcut, highcut, fs, order):
    """
    Design a Butterworth bandpass filter.

    Parameters:
    lowcut (float): The lower cutoff frequency of the filter.
    highcut (float): The upper cutoff frequency of the filter.
    fs (float): The sampling frequency of the input signal.
    order (int): The order of the filter.

    Returns:
    b (ndarray): The numerator coefficients of the filter transfer function.
    a (ndarray): The denominator coefficients of the filter transfer function.
    """
    nyquist = 0.5 * fs # Nyquist frequency is half the sampling rate
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = signal.butter(order, [low, high], btype='band')
    return b, a

def butter_bandpass_filter(data, fs, lowcut=100, highcut=3500, order=4):
    """
    Apply a Butterworth bandpass filter to the input data.

    Parameters:
    - data: array-like
        The input data to be filtered.
    - fs: float
        The sampling frequency of the input data.
    - lowcut: float, optional
        The lower cutoff frequency of the bandpass filter (default: 100 Hz).
    - highcut: float, optional
        The upper cutoff frequency of the bandpass filter (default: 3500 Hz).
    - order: int, optional
        The order of the Butterworth filter (default: 4).

    Returns:
    - y: array-like
        The filtered data.
    """
    b, a = butter_bandpass(lowcut, highcut, fs, order)
    y = signal.filtfilt(b, a, data)
    return y

def correct_emg_to_baseline(recording, scan_rate, stim_delay):
    """
    Corrects EMG absolute amplitude relative to pre-stim baseline amplitude.

    Parameters:
    recording (list): A list of EMG channel data.
    scan_rate (float): The scan rate of the EMG recording.
    stim_delay (float): The delay between the start of the recording and the stimulation.

    Returns:
    list: A list of EMG channel data with the baseline amplitude corrected.
    """
    adjusted_recording = []
    for channel in recording:
        baseline_emg = _calculate_average_amplitude_unrectified(channel, 0, stim_delay, scan_rate)
        adjusted_channel = channel - baseline_emg
        adjusted_recording.append(adjusted_channel)

    return adjusted_recording

def rectify_emg(emg_array):
    """
    Rectify EMG data by taking the absolute value.
    """
    return np.abs(emg_array)

def _calculate_average_amplitude_rectified(emg_data, start_ms, end_ms, scan_rate):
    """
    Calculate the average rectified EMG amplitude between start_ms and end_ms.

    Parameters:
    - emg_data: numpy array
        The EMG data.
    - start_ms: float
        The start time in milliseconds.
    - end_ms: float
        The end time in milliseconds.
    - scan_rate: int
        The scan rate in samples per second.

    Returns:
    - average_amplitude: float
        The average rectified EMG amplitude between start_ms and end_ms.
    """
    start_index = int(start_ms * scan_rate / 1000)
    end_index = int(end_ms * scan_rate / 1000)
    emg_window = emg_data[start_index:end_index]
    rectified_emg_window = rectify_emg(emg_window)
    return np.mean(rectified_emg_window)

def _calculate_peak_to_trough_amplitude(emg_data, start_ms, end_ms, scan_rate):
    """
    Calculate the peak-to-trough EMG amplitude between start_ms and end_ms.

    Parameters:
    - emg_data: numpy array
        The EMG data.
    - start_ms: float
        The start time in milliseconds.
    - end_ms: float
        The end time in milliseconds.
    - scan_rate: int
        The scan rate in samples per second.

    Returns:
    - peak_to_trough_amplitude: float
        The peak-to-trough amplitude of the EMG data between start_ms and end_ms.
    """
    # Convert start and end times from milliseconds to sample indices
    start_index = int(start_ms * scan_rate / 1000)
    end_index = int(end_ms * scan_rate / 1000)
    
    # Extract the relevant window of EMG data
    emg_window = emg_data[start_index:end_index]
    
    # Find the peak (maximum) and trough (minimum) values in the window
    peak_value = np.max(emg_window)
    trough_value = np.min(emg_window)
    
    # Calculate the peak-to-trough amplitude
    peak_to_trough_amplitude = peak_value - trough_value
    
    return peak_to_trough_amplitude

def _calculate_rms_amplitude(emg_data, start_ms, end_ms, scan_rate):
    """
    Calculate the average RMS EMG amplitude between start_ms and end_ms.
    """
    # Convert start and end times from milliseconds to sample indices
    start_index = int(start_ms * scan_rate / 1000)
    end_index = int(end_ms * scan_rate / 1000)
    
    # Extract the relevant window of EMG data
    emg_window = emg_data[start_index:end_index]
    
    # Square each value in the EMG window
    squared_emg_window = np.square(emg_window)
    
    # Calculate the mean of the squared values
    mean_squared_value = np.mean(squared_emg_window)
    
    # Take the square root of the mean squared value to get the RMS
    rms_value = np.sqrt(mean_squared_value)
    
    return rms_value

def _calculate_average_amplitude_unrectified(emg_data, start_ms, end_ms, scan_rate):
    """
    Calculate the average unrectified EMG amplitude between start_ms and end_ms.

    Parameters:
    - emg_data (array-like): The EMG data.
    - start_ms (float): The start time in milliseconds.
    - end_ms (float): The end time in milliseconds.
    - scan_rate (float): The scan rate in samples per second.

    Returns:
    - average_amplitude (float): The average unrectified EMG amplitude.
    """
    start_index = int(start_ms * scan_rate / 1000)
    end_index = int(end_ms * scan_rate / 1000)
    emg_window = emg_data[start_index:end_index]
    rectified_emg_window = emg_window
    return np.mean(rectified_emg_window)

def calculate_emg_amplitude(emg_data, start_ms, end_ms, scan_rate, method):
    """
    Calculate the EMG amplitude using the specified method.

    Parameters:
    - emg_data: numpy array
        The EMG data.
    - start_ms: float
        The start time in milliseconds.
    - end_ms: float
        The end time in milliseconds.
    - scan_rate: int
        The scan rate in samples per second.
    - method: str
        The calculation method to use. Must be one of 'average_rectified',
        'peak_to_trough', 'rms', or 'average_unrectified'.

    Returns:
    - amplitude: float
        The calculated EMG amplitude based on the specified method.
    """
    methods = {
        'average_rectified': _calculate_average_amplitude_rectified,
        'peak_to_trough': _calculate_peak_to_trough_amplitude,
        'rms': _calculate_rms_amplitude,
        'average_unrectified': _calculate_average_amplitude_unrectified,
    }

    if method not in methods:
        raise ValueError(f"Invalid method '{method}'. Must be one of {', '.join(methods.keys())}")

    calculation_function = methods[method]
    amplitude = calculation_function(emg_data, start_ms, end_ms, scan_rate)

    return amplitude

def savgol_filter_y (y, polyorder=3):
    # Smoothen the data using Savitzky-Golay filtering
    window_length = int((len(y) / 100) * 25)
    y_filtered = signal.savgol_filter(y, window_length, min(polyorder, window_length-1))
    return y_filtered

def detect_plateau(x, y, max_window_size, min_window_size, threshold):
    """
    Detects the plateau region in a reflex curve.

    Args:
        x (array-like): The x-coordinates of the data points.
        y (array-like): The y-coordinates of the data points.
        max_window_size (int): The maximum size of the sliding window used for plateau detection.
        min_window_size (int): The minimum size of the sliding window used for plateau detection.
        threshold (float): The threshold value used to determine if the standard deviation of the window is below the threshold.
        report (bool, optional): Whether to print a report when a plateau region is detected. Defaults to True.

    Returns:
        tuple or None: A tuple containing the start and end indices of the plateau region, or None if no plateau region is detected.
    """
    plateau_start_idx = None
    plateau_end_idx = None

    y_filtered = savgol_filter_y(y)

    for i in range(len(y_filtered) - max_window_size):
        window = y_filtered[i:i+max_window_size]
        if np.std(window) < threshold:
            # Calculate the slope of the window
            if plateau_start_idx is None:
                plateau_start_idx = i
            plateau_end_idx = i + max_window_size
        else:
            plateau_start_idx = None
            plateau_end_idx = None

    if plateau_start_idx is not None and plateau_end_idx is not None:
        logging.info(f"Plateau region detected with window size {max_window_size}. Threshold: {threshold} times SD.")
        return plateau_start_idx, plateau_end_idx
    # Shrink the window size and retry if no plateau region is detected.
    elif max_window_size > min_window_size:
        return detect_plateau(x, y, max_window_size-1, min_window_size, threshold)
    else:
        logging.warning("No plateau region detected.")
        return None, None

def get_avg_mmax (stimulus_voltages, m_wave_amplitudes, max_window_size=20, min_window_size=3, threshold=0.3, return_mmax_stim_range=False):
    """
    Get the M-wave amplitude and stimulus voltage at M-max for an EMG session.
    """
    # Convert the lists to numpy arrays.
    m_wave_amplitudes = np.array(m_wave_amplitudes)

    # Detect the plateau region in the reflex curve.
    plateau_start_idx, plateau_end_idx = detect_plateau(stimulus_voltages, m_wave_amplitudes, max_window_size, min_window_size, threshold)

    # Calculate the M-max amplitude using the plateau region m_wave_amplitudes.
    if plateau_start_idx is not None and plateau_end_idx is not None:
        plateau_data = m_wave_amplitudes[plateau_start_idx:plateau_end_idx]
        plateau_data = np.array(plateau_data)
        
        m_max = np.mean(plateau_data)
        
        # Adjust the M-max amplitude by adding the average difference between the plateau data and the outlier data.
        if m_max < max(m_wave_amplitudes):
            m_max = m_max + np.mean(m_wave_amplitudes[m_wave_amplitudes > m_max]) - np.mean(plateau_data[plateau_data < np.max(plateau_data)])
            logging.info(f"\tM-max corrected by: {np.mean(m_wave_amplitudes[m_wave_amplitudes > m_max]) - np.mean(plateau_data)}")
        
        # Return (and optionally print) the M-max amplitude.
        logging.info(f"\tM-max amplitude: {m_max}")
        if return_mmax_stim_range:
            return m_max, stimulus_voltages[plateau_start_idx], stimulus_voltages[plateau_end_idx]
        else:
            return m_max
    else:
        raise NoCalculableMmaxError()

class NoCalculableMmaxError(Exception):
    def __init__(self, message="No calculable M-max. Try adjusting the threshold values."):
        self.message = message
        super().__init__(self.message)



