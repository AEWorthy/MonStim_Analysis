# emg_transform.py

"""
Helper functions for EMG calculations and transformations.

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
- calculate_mean_std: Calculate the mean and standard deviation of M-wave amplitudes and H-reflex amplitudes over multiple sessions.

Note: This module requires the numpy and scipy libraries to be installed.
"""

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
    nyquist = 0.5 * fs
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
        baseline_emg = calculate_average_amplitude_unrectified(channel, 0, stim_delay, scan_rate)
        adjusted_channel = channel - baseline_emg
        adjusted_recording.append(adjusted_channel)

    return adjusted_recording

def rectify_emg(emg_array):
    """
    Rectify EMG data by taking the absolute value.
    """
    return np.abs(emg_array)

def calculate_average_amplitude_rectified(emg_data, start_ms, end_ms, scan_rate):
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

def calculate_peak_to_trough_amplitude(emg_data, start_ms, end_ms, scan_rate):
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

def calculate_rms_amplitude(emg_data, start_ms, end_ms, scan_rate):
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

def calculate_average_amplitude_unrectified(emg_data, start_ms, end_ms, scan_rate):
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

def calculate_mean_std(recordings, stimulus_value, channel_index, m_start_ms, m_end_ms, h_start_ms, h_end_ms, bin_size, scan_rate, method='rms'):
    """
    Calculate the M-responses and H-reflexes over multiple sessions for a given stimulus voltage, binning the stimulus voltages.

    Parameters:
    recordings (list): A list of recordings containing stimulus voltages and channel data.
    stimulus_value (float): The stimulus voltage to calculate M-responses and H-reflexes for.
    channel_index (int): The index of the channel to analyze in the recordings.
    m_start_ms (float): The start time (in milliseconds) for calculating the M-wave amplitude.
    m_end_ms (float): The end time (in milliseconds) for calculating the M-wave amplitude.
    h_start_ms (float): The start time (in milliseconds) for calculating the H-reflex amplitude.
    h_end_ms (float): The end time (in milliseconds) for calculating the H-reflex amplitude.
    bin_size (float): The bin size for grouping stimulus voltages.
    scan_rate (float): The scan rate (samples per second) of the recorded data.
    method (str): The method to use for calculating the reflex amplitude. Options are 'rms', 'avg_rectified', or 'peak_to_trough'.

    Returns:
    tuple: A tuple containing the mean and standard deviation of the M-wave amplitudes, and the mean and standard deviation of the H-reflex amplitudes.
    """
    m_wave_amplitudes = []
    h_response_amplitudes = []
    for recording in recordings:
        binned_stimulus_v = round(recording['stimulus_v'] / bin_size) * bin_size
        if binned_stimulus_v == stimulus_value:
            channel_data = recording['channel_data'][channel_index]

            if method == 'rms':
                m_wave_amplitude = calculate_rms_amplitude(channel_data, m_start_ms, m_end_ms, scan_rate)
                h_response_amplitude = calculate_rms_amplitude(channel_data, h_start_ms, h_end_ms, scan_rate)
            elif method == 'avg_rectified':
                m_wave_amplitude = calculate_average_amplitude_rectified(channel_data, m_start_ms, m_end_ms, scan_rate)
                h_response_amplitude = calculate_average_amplitude_rectified(channel_data, h_start_ms, h_end_ms, scan_rate)
            elif method == 'peak_to_trough':
                m_wave_amplitude = calculate_peak_to_trough_amplitude(channel_data, m_start_ms, m_end_ms, scan_rate)
                h_response_amplitude = calculate_peak_to_trough_amplitude(channel_data, h_start_ms, h_end_ms, scan_rate)
            else:
                print(f">! Error: method {method} is not supported. Please use 'rms', 'avg_rectified', or 'peak_to_trough'.")
                return

            m_wave_amplitudes.append(m_wave_amplitude)
            h_response_amplitudes.append(h_response_amplitude)    
    
    m_wave_mean = np.mean(m_wave_amplitudes)
    m_wave_std = np.std(m_wave_amplitudes)
    h_response_mean = np.mean(h_response_amplitudes)
    h_response_std = np.std(h_response_amplitudes)
    return m_wave_mean, m_wave_std, h_response_mean, h_response_std