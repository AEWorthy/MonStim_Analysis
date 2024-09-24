"""
Classes to analyze and plot EMG data from individual sessions or an entire dataset of sessions.
"""

import os
import sys
import pickle
import copy
import re
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import List, Union
from dataclasses import dataclass
from packaging.version import parse as parse_version
from abc import ABC, abstractmethod

from PyQt6.QtWidgets import QApplication, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget
import numpy as np
from matplotlib.lines import Line2D

from monstim_analysis.Plot_EMG import EMGSessionPlotter, EMGDatasetPlotter, EMGExperimentPlotter
import monstim_analysis.Transform_EMG as Transform_EMG
from monstim_utils import load_config, get_output_bin_path, deep_equal, get_output_path
from monstim_analysis.version import __version__ as DATA_VERSION

# To do: Add a method to create dataset latency window objects for each session in the dataset. Make the default windows be the m-wave and h-reflex windows.

@dataclass
class LatencyWindow:
    name: str
    color: str
    start_times: List[float]
    durations: List[float]
    linestyle: str = '--'

    @property
    def end_times(self):
        return [start + dur for start, dur in zip(self.start_times, self.durations)]

    def plot(self, ax, channel_index):
        start_exists = end_exists = False
        
        for line in ax.lines:
            if isinstance(line, Line2D):
                if line.get_xdata()[0] == self.start_times[channel_index] and line.get_color() == self.color:
                    start_exists = True
                elif line.get_xdata()[0] == self.end_times[channel_index] and line.get_color() == self.color:
                    end_exists = True
                
                if start_exists and end_exists:
                    break
        
        if not start_exists:
            ax.axvline(self.start_times[channel_index], color=self.color, linestyle=self.linestyle)
        
        if not end_exists:
            ax.axvline(self.end_times[channel_index], color=self.color, linestyle=self.linestyle)

    def get_legend_element(self, stylized=True):
        if stylized:
            return Line2D([0], [0], color=self.color, linestyle=self.linestyle, label=self.name)
        else:
            return Line2D([0], [0], color=self.color, linestyle='-', label=self.name)
    
# Parent EMG data class. Mainly for loading config settings.
class EMGData(ABC):
    def __init__(self):
        self.version = DATA_VERSION
        self.latency_windows: List[LatencyWindow] = []
        self.channel_names : List[str] = []
        self.num_channels : int = 0
        self.formatted_name : str = 'EMGData'
        self.m_start : List[float] = []
        self.m_duration : List[float] = []
        self.h_start : List[float] = []
        self.h_duration : List[float] = []
        self._load_config_settings()

    def _load_config_settings(self):
        _config = load_config()
        self.default_m_start : List[float] = _config['m_start']
        self.default_m_duration : List[float] = [_config['m_duration'] for _ in range(len(self.default_m_start))]
        self.default_h_start : List[float] = _config['h_start']
        self.default_h_duration : List[float] = [_config['h_duration'] for _ in range(len(self.default_h_start))]
        
        self.time_window_ms : float = _config['time_window']
        self.bin_size : float = _config['bin_size']
        self.latency_window_style : str = _config['latency_window_style']
        self.m_color : str = _config['m_color']
        self.h_color : str = _config['h_color']
        self.title_font_size : int = _config['title_font_size']
        self.axis_label_font_size : int = _config['axis_label_font_size']
        self.tick_font_size : int = _config['tick_font_size']
        self.subplot_adjust_args = _config['subplot_adjust_args']
        self.m_max_args = _config['m_max_args']
        self.butter_filter_args = _config['butter_filter_args']
        self.default_method : str = _config['default_method']
        self.default_channel_names : List[str] = _config['default_channel_names']     

    def __getstate__(self) -> object: # Called when an EMGData object is pickled.
        state = self.__dict__.copy()
        state['version'] = self.version
        return state
    
    def __setstate__(self, state: object) -> None: # Called when an EMGData object is unpickled.
        self.__dict__.update(state)
        if 'version' not in self.__dict__:
            self.version = '1.0.0' # Default version for older datasets.
        try:
            self._upgrade_from_version(self.version)
        except Exception as e:
            logging.error(f"Error upgrading dataset from version {self.version}: {str(e)}")
            raise e

    def add_latency_window(self, name: str, color: str, start_times: List[float], durations: List[float], linestyle: str = '--'):
        """
        Add a new latency window.
        
        Args:
            name (str): Name of the latency window.
            color (str): Color of the latency window markers.
            start_times (list): List of start times for each channel.
            durations (list): List of durations for each channel.
            linestyle (str, optional): Line style for the markers. Defaults to '--'.
        """
        new_window = LatencyWindow(name, color, start_times, durations, linestyle)
        self.latency_windows.append(new_window)
  
    @abstractmethod
    def _upgrade_from_version(self, old_version):
        pass

    @abstractmethod
    def update_reflex_latency_windows(self, m_start, m_duration, h_start, h_duration):
        pass

    @abstractmethod
    def update_reflex_parameters(self):
        pass

    @abstractmethod
    def reset_properties(self, recalculate : bool = False):
        pass

    @staticmethod
    def unpackPickleOutput (output_path):
        """
        Unpacks a list of EMG session Pickle files and outputs a dictionary with k/v pairs of session names and the session Pickle location.

        Args:
            output_path (str): location of the output folder containing dataset directories/Pickle files.
        """
        expt_pickles_dict = {} #k=experiment_name, v=(dataset_pickles_dict, dataset_names)

        # get every experiment folder. Ignores a folder if the folder is named 'bin'
        expts = [file for file in os.listdir(output_path) if file != 'bin']

        for expt in expts:
            dataset_pickles_dict = {} #k=dataset_name, v=pickle_filepath(s)
            for dataset in os.listdir(os.path.join(output_path, expt)):
                if os.path.isdir(os.path.join(output_path, expt, dataset)):
                    pickles = os.listdir(os.path.join(output_path, expt, dataset))
                    pickle_paths = [os.path.join(output_path, expt, dataset, pickle).replace('\\', '/') for pickle in pickles]
                    dataset_pickles_dict[dataset] = pickle_paths
                else: # if this is a single session instead...
                    split_parts = dataset.split('-') # Split the string at the hyphens
                    session_name = '-'.join(split_parts[:-1]) # Select the portion before the last hyphen to drop the "-SessionData.pickle" portion.
                    dataset_pickles_dict[session_name] = os.path.join(output_path, expt, dataset).replace('\\', '/')
            # Add the dataset data to the experiment dictionary.
            dataset_names = list(dataset_pickles_dict.keys())
            expt_pickles_dict[expt] = (dataset_pickles_dict, dataset_names)
        return expt_pickles_dict

    @staticmethod
    def parse_date(date_string, preferred_format=None):
        
        def is_valid_date(year, month, day):
            try:
                datetime(year, month, day)
                return True
            except ValueError:
                return False
            
        if len(date_string) == 6:
            formats = [
                ('%y%m%d', 'YYMMDD'),
                ('%d%m%y', 'DDMMYY'),
                ('%m%d%y', 'MMDDYY')
            ]
        elif len(date_string) == 8:
            formats = [
                ('%Y%m%d', 'YYYYMMDD'),
                ('%d%m%Y', 'DDMMYYYY'),
                ('%m%d%Y', 'MMDDYYYY')
            ]
        else:
            return None, f"Invalid date string length ('{date_string}'): must be 6 or 8 characters."
        
        valid_formats = []
        for date_format, format_name in formats:
            try:
                parsed_date = datetime.strptime(date_string, date_format)
                if is_valid_date(parsed_date.year, parsed_date.month, parsed_date.day):
                    valid_formats.append((parsed_date, format_name))
            except ValueError:
                continue

        if not valid_formats:
            return None, f"No valid date format found: please check the date string ('{date_string}')."
        
        if len(valid_formats) == 1:
            return valid_formats[0]
        
        if preferred_format:
            for parsed_date, format_name in valid_formats:
                if format_name == preferred_format:
                    return parsed_date, format_name
                
        # If we reach here, we have multiple valid formats and no preferred format
        logging.warning(f"Ambiguous date. Please specify preferred format: {[f for _, f in valid_formats]}. Returning first valid format: {valid_formats[0][1]}.")
        return valid_formats[0]

# Three main classes for EMG analysis. Children of the EMGData class.
class EMGSession(EMGData):
    """
    Class for analyzing and plotting data from a single recording session of variable channel numbers for within-session analyses and plotting.
    One session contains multiple recordings that will make up, for example, a single M-curve.

    This module provides functions for analyzing data stored in Pickle files from a single EMG recording session.
    It includes functions to extract session parameters, plot all EMG data, and plot EMG data from suspected H-reflex recordings.
    Class must be instantiated with the Pickled session data file.

    Attributes:
        - plotter (EMGSessionPlotter): An instance of the EMGSessionPlotter class for plotting EMG data. 
            - Types of plotting commands include: plot_emg, plot_susectedH, and plot_reflexCurves, and plot_mmax.
            - See the EMGSessionPlotter class in Plot_EMG.py for more details.
        - session_name (str): The name of the recording session.
        - num_channels (int): The number of channels in the EMG recordings.
        - scan_rate (int): The scan rate of the EMG recordings (Hz).
        - num_samples (int): The number of samples per channel in the EMG recordings.
        - stim_start (float): The stimulus delay from recording start (in ms) in the EMG recordings.
        - stim_duration (float): The stimulus duration (in ms) in the EMG recordings.
        - stim_interval (float): The stimulus interval (in s) in the EMG recordings.
        - emg_amp_gains (list): The amplifier gains for each channel in the EMG recordings.
        - recordings_raw (list): A list of dictionaries containing the raw EMG recordings.
        - recordings_processed (list): A list of dictionaries containing the processed EMG recordings.
        - m_max (list): A list of M-wave amplitudes for each channel in the session.

    Methods:
        load_session_data(pickled_data): Loads the session data from the pickle file.
        update_window_settings(): Opens a GUI to manually update the M-wave and H-reflex window settings for each channel.
        process_emg_data(apply_filter=False, rectify=False): Processes EMG data by applying a bandpass filter and/or rectifying the data.
        session_parameters(): Prints EMG recording session parameters from a Pickle file.
    """
    def __init__(self, pickled_raw_data=None, session_data=None):
        super().__init__()
        if pickled_raw_data:
            self.pickled_raw_data = pickled_raw_data
            with open(pickled_raw_data, 'rb') as pickle_file:
                session_data = pickle.load(pickle_file)
            self._initialize_from_data(session_data)
        elif session_data:
            self._initialize_from_data(session_data)
        else:
            raise ValueError("Either pickled_raw_data or session_data must be provided.")

    def _initialize_from_data(self, session_data):
        # Access session-wide information
        session_info : dict = session_data['session_info']
        self.session_id : str = session_info['session_id']
        self.num_channels : int = int(session_info['num_channels'])
        self.channel_names : List[str] = [self.default_channel_names[i] if i < len(self.default_channel_names) 
                                          else 'Channel ' + str(i) for i in range(self.num_channels)]
        self.scan_rate : int = int(session_info['scan_rate'])
        self.num_samples : int = int(session_info['num_samples'])
        self.pre_stim_acquired : float = session_info['pre_stim_acquired']
        self.post_stim_acquired : float = session_info['post_stim_acquired']
        self.stim_delay : float = session_info['stim_delay']
        self.stim_start : float = self.stim_delay + self.pre_stim_acquired
        self.stim_duration : float = session_info['stim_duration']
        self.stim_interval : float = session_info['stim_interval']
        self.emg_amp_gains : List[int] = [int(gain) for index, gain in enumerate(session_info['emg_amp_gains']) 
                                          if index < self.num_channels] # only include gains for the number of recorded channels.
        
        # Access the raw EMG recordings. Sort by stimulus voltage and assign a unique recording ID to each recording.
        self.recordings_raw = sorted(session_data['recordings'], key=lambda x: x['stimulus_v'])
        for index, item in enumerate(self.recordings_raw):
            item['recording_id'] = index
        self._original_recordings = copy.deepcopy(self.recordings_raw)
        self.num_recordings = len(self.recordings_raw) # Number of recordings in the session, including excluded recordings.
        self.excluded_recordings = set()

        # Initialize the EMGSessionPlotter object and other attributes.      
        self.plotter = EMGSessionPlotter(self)
        self.formatted_name = self.session_id.replace('_', ' ').title()
        self._recordings_processed = None
        self._m_max = None

        # Add default M-wave and H-reflex latency windows for each channel
        self.add_latency_window( # M-wave latency window
            name="M-wave",
            color="red",
            start_times=self.default_m_start,  # start times for each channel
            durations=self.default_m_duration  # end times for each channel
        )
        self.add_latency_window( # H-reflex latency window
            name="H-reflex",
            color="blue",
            start_times=self.default_h_start,  # start times for each channel
            durations=self.default_h_duration # end times for each channel
        )

        # Updated reflex windows for each channel
        self.update_reflex_parameters()
        logging.info(f"Session {self.session_id} initialized with {self.num_recordings} recordings.")
    
    def _upgrade_from_version(self, old_version):
        old_version_parsed = parse_version(old_version)
        try:
            if old_version_parsed < parse_version('1.6.0'): # Upgrade from version 1.5.0 or older to 1.6.0.
                # If no latency windows attribute, then throw an error (version is likely too old to handle safely).
                if not hasattr(self, 'latency_windows'):
                    # if the data has a formatted name, try to use that for the error message.
                    if hasattr(self, 'formatted_name'):
                        raise ValueError(f"Dataset '{self.formatted_name}' is too old to upgrade. Delete the bin file and re-import the data.")
                    else:
                        raise ValueError("Dataset version is too old to upgrade. Delete the bin file and re-import the data.")
                
                # Store the current state of the object
                current_state = self.__dict__.copy()
                
                # Reinitialize the object
                session_data = {
                    'session_info': {
                        'session_id': current_state['session_id'],
                        'num_channels': current_state['num_channels'],
                        'scan_rate': current_state['scan_rate'],
                        'num_samples': current_state['num_samples'],
                        'pre_stim_acquired': current_state['pre_stim_acquired'],
                        'post_stim_acquired': current_state['post_stim_acquired'],
                        'stim_delay': current_state['stim_delay'],
                        'stim_duration': current_state['stim_duration'],
                        'stim_interval': current_state['stim_interval'],
                        'emg_amp_gains': current_state['emg_amp_gains']
                    },
                    'recordings': current_state['recordings_raw']
                }

                self.__init__(session_data=session_data)
                default_state = self.__dict__.copy()

                # Update the new state with the old values
                ignore_keys = {'plotter', 'version', 'm_end', 'h_end', '_original_recordings', '_recordings_processed', '_m_max'}
                for key, value in current_state.items():
                    if (key not in ignore_keys) and (key not in default_state):
                            self.__dict__[key] = value
                            logging.info(f"Retained old key '{key}' during upgrade that was not in default state.")
                    else:
                        try:
                            if (key not in ignore_keys) and (key not in default_state or not deep_equal(default_state[key], value)):
                                self.__dict__[key] = value
                                logging.info(f"Retained old key '{key}' during upgrade.")
                        except Exception as e:
                            logging.error(f"Error comparing key '{key}' to default value. Error: {str(e)}")
                            raise e
                
                self.reset_properties(recalculate=False)
        except Exception as e:
            logging.error(f"Error upgrading session from version {old_version}. If this problem persists, try to delete and re-import this experiment: {str(e)}")
            raise e
        # Add any other version upgrade checks below.

    def _process_emg_data(self, recordings, apply_filter=False, rectify=False):
        """
        Process EMG data by applying a bandpass filter and/or rectifying the data.

        Args:
            apply_filter (bool, optional): Whether to apply a bandpass filter to the data. Defaults to False.
            rectify (bool, optional): Whether to rectify the data. Defaults to False.

        Returns:
            list: List of processed recordings.

        Raises:
            None

        Examples:
            # Process EMG data without applying any filters or rectification
            processed_data = process_emg_data()

            # Process EMG data with bandpass filter applied
            processed_data = process_emg_data(apply_filter=True)

            # Process EMG data with rectification applied
            processed_data = process_emg_data(rectify=True)

            # Process EMG data with both bandpass filter and rectification applied
            processed_data = process_emg_data(apply_filter=True, rectify=True)
        """
        def __process_single_recording(recording):
            if apply_filter:
                for i, channel_emg in enumerate(recording['channel_data']):
                    filtered_emg = Transform_EMG.butter_bandpass_filter(channel_emg, self.scan_rate, **self.butter_filter_args)
                    recording['channel_data'][i] = filtered_emg
            if rectify:
                recording['channel_data'] = np.abs(recording['channel_data'])
                
                #!# I decided to remove the baseline correction code for now. It's best not to transform the data more than necessary.
                
                # # Code to apply baseline correction to the processed data if a filter was applied.
                # if apply_filter:
                #     recording['channel_data'] = EMG_Transformer.correct_emg_to_baseline(recording['channel_data'], self.scan_rate, self.stim_start)
            
            return recording
        
        # Copy recordings if deep copy is needed.
        processed_recordings = copy.deepcopy(recordings) if apply_filter or rectify else recordings

        with ThreadPoolExecutor() as executor:
            processed_recordings = list(executor.map(__process_single_recording, processed_recordings))

        return processed_recordings

    def rename_channels(self, new_names : dict[str]):
        """
        Renames a channel in the session.
    
        Args:
            new_names (dict[str]): A dictionary mapping old channel names to new channel names.
        """
        try:
            # Rename the channels in the session.
            for i, new_name in enumerate(new_names.values()):
                self.channel_names[i] = new_name
        except IndexError:
            logging.warning("Error: The number of new names does not match the number of channels in the session.")

    def apply_preferences(self, reset_properties=True):
        """
        Applies the preferences set in the config file to the dataset.
        """
        self._load_config_settings() # Load the config settings from file.

        # Re-create the plotter object with the new preferences.
        self.plotter = EMGSessionPlotter(self)
        for latency_window in self.latency_windows:
            latency_window.linestyle = self.latency_window_style

        if reset_properties:
            self.reset_properties(recalculate=True)

    def exclude_recording(self, original_recording_index: int):
        """
        Removes a recording from the session.

        Args:
            original_recording_index (int): The original index of the recording to remove.
        """
        if original_recording_index in self.excluded_recordings:
            raise ValueError("Recording is already excluded.")

        self.reset_properties()

        # Add the recording to the list of excluded recordings and remove it from the active list of raw recordings.
        self.excluded_recordings.add(original_recording_index)
        self.recordings_raw = [recording for recording in self.recordings_raw if recording['recording_id'] != original_recording_index]
        logging.info(f"Recording {original_recording_index} has been excluded.")
        
    def restore_recording(self, original_recording_index: int):
        """
        Restores a removed recording to the session.

        Args:
            original_recording_index (int, optional): The original index of the recording to restore.
        """
        if original_recording_index not in self.excluded_recordings:
            raise ValueError("Recording is not excluded.")
        
        self.reset_properties(recalculate=False)
        
        recording = self._original_recordings.copy().pop(original_recording_index)
        self.recordings_raw.append(recording)
        self.excluded_recordings.remove(original_recording_index)

        self.recordings_raw = sorted(self.recordings_raw, key=lambda x: x['recording_id'])
        self.reset_properties(recalculate=False)

        logging.info(f"Recording {original_recording_index} has been restored.")
        return original_recording_index

    def reload_recordings(self):
        """
        Reloads all recordings to the original state.
        """
        self.recordings_raw = copy.deepcopy(self._original_recordings)
        self.excluded_recordings = set()
        self.reset_properties(recalculate=True)
        logging.info("All recordings have been reloaded from the original state.")

    def invert_channel_polarity(self, channel_index):
        """
        Inverts the polarity of a recording channel.

        Args:
            channel_index (int): The index of the channel to invert.
        """
        for recording in self.recordings_raw:
            recording['channel_data'][channel_index] *= -1
        self.reset_properties(recalculate=True)
    
    def reset_properties(self, recalculate : bool = False):
        """
        Resets the processed recordings and M-max properties. 
        This should be called after any changes to the raw recordings so that the properties are recalculated.
        """
        self._recordings_processed = None
        self._m_max = None
        
        # remove 'rectified_raw' or 'rectified_filtered' data if it exists.
        if hasattr(self, 'recordings_rectified_raw'):
            del self.recordings_rectified_raw
        if hasattr(self, 'recordings_rectified_filtered'):
            del self.recordings_rectified_filtered

        if recalculate:
            self.recordings_processed
            self.m_max
    
    @property
    def recordings_processed (self):
        if self._recordings_processed is None:
            self._recordings_processed = self._process_emg_data(self.recordings_raw, apply_filter=True, rectify=False)
        return self._recordings_processed

    @property
    def m_max(self):
        # uses default method to calculate m_max if not already calculated.
        if self._m_max is None:
            m_max = []
            
            for channel_idx in range(self.num_channels):
                stimulus_voltages = [recording['stimulus_v'] for recording in self.recordings_processed]
                m_wave_amplitudes = [Transform_EMG.calculate_emg_amplitude(recording['channel_data'][channel_idx], 
                                                                            (self.m_start[channel_idx] + self.stim_start),
                                                                            (self.m_start[channel_idx] + self.stim_start + self.m_duration[channel_idx]), 
                                                                            self.scan_rate, 
                                                                            method=self.default_method) 
                                                                            for recording in self.recordings_processed]                
                try: # Check if the channel has a valid M-max amplitude.
                    channel_mmax = Transform_EMG.get_avg_mmax(stimulus_voltages, m_wave_amplitudes, **self.m_max_args)
                    m_max.append(channel_mmax)
                except Transform_EMG.NoCalculableMmaxError:
                    logging.info(f"Channel {channel_idx} does not have a valid M-max amplitude.")
                    m_max.append(None)
                except ValueError as e:
                    logging.error(f"Error in calculating M-max amplitude for channel {channel_idx}. Error: {str(e)}")
                    m_max.append(None)
            
            self._m_max = m_max
        return self._m_max

    # User methods for EMGSession class
    def m_max_report(self):
        """
        Logs the M-wave amplitudes for each channel in the session.
        """
        report = []
        for i, channel_m_max in enumerate(self.m_max):
            try:
                line = f"- {self.channel_names[i]}: M-max amplitude = {channel_m_max:.2f} V"
                report.append(line)
            except TypeError:
                line = f"- Channel {i} does not have a valid M-max amplitude."
                report.append(line)

        for line in report:
            logging.info(line)
        return report

    def get_m_max(self, method, channel_index):
        """
        Calculates the M-wave amplitude for a specific channel in the session.

        Args:
            method (str): The method to use for calculating the M-wave amplitude. Options include 'average_rectified', 'rms', 'peak_to_trough', and 'average_unrectified'.
            channel_index (int): The index of the channel to calculate the M-wave amplitude for.

        Returns:
            float: The M-wave amplitude for the specified channel.
        """
        stimulus_voltages = [recording['stimulus_v'] for recording in self.recordings_processed]
        m_wave_amplitudes = [Transform_EMG.calculate_emg_amplitude(recording['channel_data'][channel_index], 
                                                                    (self.m_start[channel_index] + self.stim_start),
                                                                    (self.m_start[channel_index] + self.stim_start + self.m_duration[channel_index]), 
                                                                    self.scan_rate, 
                                                                    method=method) 
                                                                    for recording in self.recordings_processed]
        return Transform_EMG.get_avg_mmax(stimulus_voltages, m_wave_amplitudes, **self.m_max_args)
    
    def update_reflex_latency_windows(self, m_start, m_duration, h_start, h_duration):
        for window in self.latency_windows:
            if window.name == "M-wave":
                window.start_times = m_start
                window.durations = m_duration
            elif window.name == "H-reflex":
                window.start_times = h_start
                window.durations = h_duration

    def update_reflex_parameters(self):
        for window in self.latency_windows:
            if window.name == "M-wave":
                self.m_start = window.start_times
                self.m_duration = window.durations
            elif window.name == "H-reflex":
                self.h_start = window.start_times
                self.h_duration = window.durations

    def update_window_settings(self):
        """
        ***ONLY FOR USE IN JUPYTER NOTEBOOKS OR INTERACTIVE PYTHON ENVIRONMENTS***

        Opens a GUI to manually update the M-wave and H-reflex window settings for each channel using PyQt.

        This function should only be used if you are working in a Jupyter notebook or an interactive Python environment. Do not call this function in any other GUI environment.
        """
        class ReflexSettingsDialog(QWidget):
            def __init__(self, emg_parent : EMGSession):
                super().__init__()
                self.emg_parent = emg_parent
                self.initUI()

            def initUI(self):
                self.setWindowTitle(f"Update Reflex Window Settings: Session {self.emg_parent.session_id}")
                layout = QVBoxLayout()

                duration_layout = QHBoxLayout()
                duration_layout.addWidget(QLabel("m_duration:"))
                self.m_duration_entry = QLineEdit(str(self.emg_parent.m_duration[0]))
                duration_layout.addWidget(self.m_duration_entry)

                duration_layout.addWidget(QLabel("h_duration:"))
                self.h_duration_entry = QLineEdit(str(self.emg_parent.h_duration[0]))
                duration_layout.addWidget(self.h_duration_entry)

                layout.addLayout(duration_layout)

                self.entries = []
                for i in range(self.emg_parent.num_channels):
                    channel_layout = QHBoxLayout()
                    channel_layout.addWidget(QLabel(f"Channel {i}:"))

                    channel_layout.addWidget(QLabel("m_start:"))
                    m_start_entry = QLineEdit(str(self.emg_parent.m_start[i]))
                    channel_layout.addWidget(m_start_entry)

                    channel_layout.addWidget(QLabel("h_start:"))
                    h_start_entry = QLineEdit(str(self.emg_parent.h_start[i]))
                    channel_layout.addWidget(h_start_entry)

                    layout.addLayout(channel_layout)
                    self.entries.append((m_start_entry, h_start_entry))

                save_button = QPushButton("Confirm")
                save_button.clicked.connect(self.save_settings)
                layout.addWidget(save_button)

                self.setLayout(layout)

            def save_settings(self):
                try:
                    m_duration = float(self.m_duration_entry.text())
                    h_duration = float(self.h_duration_entry.text())
                except ValueError:
                    logging.error("Invalid input for durations. Please enter valid numbers.")
                    return

                m_start = []
                h_start = []
                for i, (m_start_entry, h_start_entry) in enumerate(self.entries):
                    try:
                        m_start.append(float(m_start_entry.text()))
                        h_start.append(float(h_start_entry.text()))
                    except ValueError:
                        logging.error(f"Invalid input for channel {i}. Skipping.")
                
                # Update the reflex windows in the parent object based on the new windows.
                try:           
                    self.emg_parent.update_reflex_latency_windows(m_start, m_duration, h_start, h_duration)
                except Exception as e:
                    logging.error(f"Error saving the following reflex settings: m_start: {m_start}\n\tm_duration: {m_duration}\n\th_start: {h_start}\n\th_duration: {h_duration}")
                    logging.error(f"Error: {str(e)}")
                    return
                self.emg_parent.update_reflex_parameters()
                self.emg_parent.reset_properties(recalculate=True)
                
                self.close()

        app = QApplication.instance()  # Check if there's an existing QApplication instance
        if not app:
            app = QApplication(sys.argv)
            window = ReflexSettingsDialog(self)
            window.show()
            app.exec()
        else:
            window = ReflexSettingsDialog(self)
            window.show()

    def session_parameters (self):
        """
        Logs EMG recording session parameters from a Pickle file.
        """
        report = [f"Session ID: {self.session_id}",
                  f"# of Recordings (including any excluded ones): {self.num_recordings}", 
                  f"# of Channels: {self.num_channels}",
                  f"Scan Rate (Hz): {self.scan_rate}",
                  f"Samples/Channel: {self.num_samples}",
                  f"Pre-Stim Acq. time (ms): {self.pre_stim_acquired}",
                  f"Post-Stim Acq. time (ms): {self.post_stim_acquired}",
                  f"Stimulus Delay (ms): {self.stim_delay}",
                  f"Stimulus Duration (ms): {self.stim_duration}",
                  f"Stimulus Interval (s): {self.stim_interval}",
                  f"EMG Amp Gains: {self.emg_amp_gains}"]        
        
        for line in report:
            logging.info(line)
        return report

    def plot(self, plot_type: str = None, **kwargs):
        """
        Plots EMG data from a single session using the specified plot_type.

        Args:
            - plot_type (str): The type of plot to generate. Options include 'emg', 'suspectedH', 'mmax', and 'reflexCurves', and 'mCurvesSmoothened'.
                Plot types are defined in the EMGSessionPlotter class in Plot_EMG.py.
            - channel_names (list): A list of channel names to plot. If None, all channels will be plotted.
            - **kwargs: Additional keyword arguments to pass to the plotting function.
                
                The most common keyword arguments include:
                - 'data_type' (str): The type of data to plot. Options are 'filtered', 'raw', 'rectified_raw', or 'rectified_filtered'. Default is 'filtered'.
                - 'method' (str): The method to use for calculating the M-wave/reflex amplitudes. Options include 'average_rectified', 'rms', 'peak_to_trough', and 'average_unrectified'. Default method is set in config.yml under 'default_method'.
                - 'relative_to_mmax' (bool): Whether to plot the data proportional to the M-wave amplitude (True) or as the actual recorded amplitude (False). Default is False.
                - 'all_flags' (bool): Whether to plot flags at all windows (True) or not (False). Default is False.
                
                Less common keyword arguments include:
                - 'm_flags' (bool): Whether to plot flags at the M-wave window (True) or not (False). Default is False.
                - 'h_flags' (bool): Whether to plot flags at the H-reflex window (True) or not (False). Default is False.
                - 'h_threshold' (float): The threshold for detecting the H-reflex in the suspectedH plot. Default is 0.3.
                - 'mmax_report' (bool): Whether to print the details of the M-max calculations (True) or not (False). Default is False.
                - 'manual_mmax' (float): The manually set M-wave amplitude to use for plotting the reflex curves. Default is None.

        Example Usages:
            # Plot filtered EMG data
                session.plot()

            # Plot raw EMG data with flags at the M-wave and H-reflex windows
            session.plot(data_type='raw', all_flags=True)

            # Plot all EMG data with the M-wave and H-reflex windows highlighted
            session.plot(plot_type='suspectedH')

            # Plot M-wave amplitudes for each channel
            session.plot(plot_type='mmax')

            # Plot the reflex curves for each channel
            session.plot(plot_type='reflexCurves')
        """

        # Call the appropriate plotting method from the plotter object
        raw_data = getattr(self.plotter, f'plot_{"emg" if not plot_type else plot_type}')(**kwargs)
        return raw_data

class EMGDataset(EMGData):
    """
    Class for a dataset of EMGSession instances for multi-session analyses and plotting.

    This module provides functions for analyzing a full dataset of EMGSessions. This code assumes all session have the same recording parameters and number of channels.
    The class must be instantiated with a list of EMGSession instances.

    Attributes:
        - plotter (EMGDatasetPlotter): An instance of the EMGDatasetPlotter class for plotting EMG data. 
            - Types of plotting commands include: plot_reflexCurves, plot_mmax, and plot_maxH.
            - See the EMGDatasetPlotter class in Plot_EMG.py for more details.
        - emg_sessions (list): A list of instances of the class EMGSession that make up the dataset.
        - date (str): The date of the dataset.
        - animal_id (str): The animal ID of the dataset.
        - condition (str): The experimental condition of the dataset.
        - scan_rate (int): The scan rate of the EMG recordings (Hz).
        - num_channels (int): The number of channels in the EMG recordings.
    """
    
    def __init__(self, emg_sessions, date, animal_id, condition, emg_sessions_to_exclude=[], save_path=None, temp=False):
        """
        Initialize an EMGDataset instance from a list of EMGSession instances for multi-session analyses and plotting.

        Args:
            emg_sessions (list): A list of instances of the class EMGSession, or a list of Pickle file locations that you want to use for the dataset.
            emg_sessions_to_exclude (list, optional): A list of session names to exclude from the dataset. Defaults to an empty list.
        """
        # Set dataset parameters
        self.date : str = date
        self.animal_id : str = animal_id
        self.condition : str = condition
        self.save_path = os.path.join(get_output_bin_path(),(save_path or f"{self.date}_{self.animal_id}_{self.condition}.pickle"))
        self.temp = temp

        # Saving was disabled for now. It's better to save the dataset inside of the experiment class.
        if os.path.exists(self.save_path) and not temp:
            raise FileExistsError(self.save_path)
        else:
            logging.info(f"Creating new dataset: {self.date} {self.animal_id} {self.condition}.")
            super().__init__()
            self.plotter = EMGDatasetPlotter(self)
            self.formatted_name = f"{self.date} {self.animal_id} {self.condition}"
            self.dataset_id = f"{self.date}_{self.animal_id}_{self.condition.replace(' ', '-')}"
            self._m_max = None    
            
            # Unpack the EMG sessions and exclude any sessions if needed.
            if isinstance(emg_sessions, str) or isinstance(emg_sessions, EMGSession):
                emg_sessions = [emg_sessions]
            self.original_emg_sessions = emg_sessions
            self.emg_sessions: List[EMGSession] = []

            logging.info(f"Unpacking {len(emg_sessions)} EMG sessions...")
            self.emg_sessions = self.__unpackEMGSessions(emg_sessions) # Convert file location strings into a list of EMGSession instances.
            
            # Exclude any sessions if needed.
            if len(emg_sessions_to_exclude) > 0:
                logging.warning(f"Excluding the following sessions from the dataset: {emg_sessions_to_exclude}")
                self.emg_sessions = [session for session in self.emg_sessions if session.session_id not in emg_sessions_to_exclude]
                self._num_sessions_excluded = len(emg_sessions) - len(self.emg_sessions)
            else:
                self._num_sessions_excluded = 0

            # Check that all sessions have the same parameters and set dataset parameters.
            consistent, message = self.__check_session_consistency()
            if not consistent:
                logging.error(f"Error: {message}")
            else:
                self.scan_rate : int = self.emg_sessions[0].scan_rate
                self.num_channels : int = self.emg_sessions[0].num_channels
                self.stim_start : float = self.emg_sessions[0].stim_start
                self.channel_names : List[str] = self.emg_sessions[0].channel_names # not checked for consistency, but should be the same for all sessions.
                self.latency_windows : LatencyWindow = copy.deepcopy(self.emg_sessions[0].latency_windows)
                self.update_reflex_parameters()
                logging.info(f"Dataset {self.dataset_id} initialized with {len(self.emg_sessions)} sessions.")
                # if not temp:
                #     self.save_dataset(self.save_path)

    def _upgrade_from_version(self, old_version):
        old_version_parsed = parse_version(old_version)
        try:
            if old_version_parsed < parse_version('1.6.0'): # Upgrade from version 1.5.0 or older to 1.6.0.
                # If no latency windows attribute, then throw an error (version is likely too old to handle safely).
                if not hasattr(self, 'latency_windows'):
                    # if the data has a formatted name, try to use that for the error message.
                    if hasattr(self, 'formatted_name'):
                        raise ValueError(f"Dataset '{self.formatted_name}' is too old to upgrade. Delete the bin file and re-import the data.")
                    else:
                        raise ValueError("Dataset version is too old to upgrade. Delete the bin file and re-import the data.")
                
                # Store the current state of the object
                current_state = self.__dict__.copy()

                # Update the EMGSession instances in the dataset.
                for session in self.emg_sessions:
                    session._upgrade_from_version(old_version)
                    session.reset_properties(recalculate=False)
                
                # Reinitialize the object
                dataset_info = {
                    'emg_sessions': current_state['emg_sessions'],
                    'date': current_state['date'],
                    'animal_id': current_state['animal_id'],
                    'condition': current_state['condition'],
                    }
                try:
                    dataset_info['emg_sessions_to_exclude'] = current_state['emg_sessions_to_exclude']
                except KeyError:
                    dataset_info['emg_sessions_to_exclude'] = []
                dataset_info['save_path'] = None
                dataset_info['temp'] = True

                self.__init__(**dataset_info)
                default_state = self.__dict__.copy()

                # Update the new state with the old values
                ignore_keys = {'plotter', 'version', 'm_end', 'h_end'}
                for key, value in current_state.items():
                    if (key not in ignore_keys) and (key not in default_state):
                            self.__dict__[key] = value
                            logging.info(f"Retained old key '{key}' during upgrade that was not in default state.")
                    else:
                        try:
                            if (key not in ignore_keys) and (key not in default_state or not deep_equal(default_state[key], value)):
                                self.__dict__[key] = value
                                logging.info(f"Retained old key '{key}' during upgrade.")
                        except Exception as e:
                            logging.error(f"Error comparing key '{key}' to default value. Error: {str(e)}")
                            raise e
                
                # Save the dataset if it was not a temporary dataset.
                try:
                    if not current_state['temp']:
                        self.save_dataset(self.save_path)
                except KeyError:
                    pass  
        except Exception as e:
            logging.error(f"Error upgrading dataset from version {old_version}. If this problem persists, try to delete and re-import this experiment: {str(e)}")
            raise e
        # Add any other version upgrade checks below.

    def dataset_parameters(self):
        """
        Logs EMG dataset parameters.
        """
        report = [f"EMG Sessions ({len(self.emg_sessions)}): {[session.session_id for session in self.emg_sessions]}.",
                    f"Date: {self.date}",
                    f"Animal ID: {self.animal_id}",
                    f"Condition: {self.condition}"]

        for line in report:
            logging.info(line)
        return report

    def plot(self, plot_type: str = None, **kwargs):
        """
        Plots EMG data from a single session using the specified plot_type.

        Args:
            - plot_type (str): The type of plot to generate. Options include 'reflexCurves', 'mmax', and 'maxH'. Default is 'reflexCurves'.
                Plot types are defined in the EMGDatasetPlotter class in Plot_EMG.py.
            - channel_names (list): A list of channel names to plot. If None, all channels will be plotted.
            - **kwargs: Additional keyword arguments to pass to the plotting function.
                
                The most common keyword arguments include:
                - 'method' (str): The method to use for calculating the M-wave/reflex amplitudes. Options include 'average_rectified', 'rms', 'peak_to_trough', and 'average_unrectified'. Default method is set in config.yml under 'default_method'.
                - 'relative_to_mmax' (bool): Whether to plot the data proportional to the M-wave amplitude (True) or as the actual recorded amplitude (False). Default is False.
                - 'mmax_report' (bool): Whether to print the details of the M-max calculations (True) or not (False). Default is False.
                - 'manual_mmax' (float): The manually set M-wave amplitude to use for plotting the reflex curves. Default is None.

        Example Usages:
            # Plot the reflex curves for each channel.
            dataset.plot()

            # Plot M-wave amplitudes for each channel.
            dataset.plot(plot_type='mmax')

            # Plot the reflex curves for each channel.
            dataset.plot(plot_type='reflexCurves')

            # Plot the reflex curves for each channel and print the M-max details.
            dataset.plot(plot_type='reflexCurves', mmax_report=True)
        """

        # Call the appropriate plotting method from the plotter object
        raw_data = getattr(self.plotter, f'plot_{"reflexCurves" if not plot_type else plot_type}')(**kwargs)
        return raw_data

    def get_avg_m_max(self, method, channel_index):
        """
        Calculates the average M-wave amplitude for a specific channel in the dataset.

        Args:
            method (str): The method to use for calculating the M-wave amplitude. Options include 'average_rectified', 'rms', 'peak_to_trough', and 'average_unrectified'.
            channel_index (int): The index of the channel to calculate the M-wave amplitude for.

        Returns:
            float: The average M-wave amplitude for the specified channel.
        """
        m_wave_amplitudes = [session.get_m_max(method, channel_index) for session in self.emg_sessions if session.m_max[channel_index] is not None]
        return np.mean(m_wave_amplitudes)

    def invert_channel_polarity(self, channel_index):
        """
        Inverts the polarity of a recording channel.

        Args:
            channel_index (int): The index of the channel to invert.
        """
        for session in self.emg_sessions:
            session.invert_channel_polarity(channel_index)
        logging.info(f"Channel {channel_index} polarity has been inverted for all sessions in dataset {self.dataset_id}.")

    def reset_properties(self, recalculate : bool = False):
        """
        Resets the processed recordings and M-max properties. 
        This should be called after any changes to the raw recordings so that the properties are recalculated.
        """
        for session in self.emg_sessions:
            session.reset_properties(recalculate=recalculate)
        self._m_max = None

    #Properties for the EMGDataset class.
    @property
    def m_max(self):
        if self._m_max is None:
            session_m_maxes = [session.m_max for session in self.emg_sessions]
            m_max = []
            # separate each channel's m_max into separate arrays and average them.
            for channel_index in range(self.num_channels):
                channel_m_maxes = [m_max[channel_index] for m_max in session_m_maxes if m_max[channel_index] is not None]
                if len(channel_m_maxes) == 0:
                    raise ValueError(f"Error: No valid M-max values found for channel {channel_index}.")
                channel_m_max = np.mean(channel_m_maxes)
                m_max.append(float(channel_m_max))
            self._m_max = m_max
            logging.info(f"Average M-max values created for dataset {self.formatted_name}: {self._m_max}")
        return self._m_max

    # User methods for manipulating the EMGSession instances in the dataset.
    def add_session(self, session : Union[EMGSession, str]):
        """
        Adds an EMGSession to the emg_sessions list of this EMGDataset.

        Parameters:
            session (EMGSession or str): The session to be added. It can be an instance of EMGSession or a file path to a pickled EMGSession.

        Raises:
            TypeError: If the session is neither an instance of EMGSession nor a valid file path to a pickled EMGSession.
        """
        if session in [session.session_id for session in self.emg_sessions]:
            logging.warn(f"Session {session.session_id} is already in the dataset. It will not be re-added.")
        else:
            if isinstance(session, EMGSession):
                # Add the session to the dataset.
                self.emg_sessions.append(session)
                self.emg_sessions = sorted(self.emg_sessions, key=lambda x: x.session_id)
                
            else:
                try:
                    self.emg_sessions.append(EMGSession(session))
                except:  # noqa: E722
                    raise TypeError("Expected an instance of EMGSession or a file path to a pickled EMGSession.")
            
            # Check that all sessions have the same parameters.
            self.__check_session_consistency()
            consistent, message = self.__check_session_consistency()
            if not consistent:
                logging.error(f"Error: {message}")
            else:
                self.scan_rate = self.emg_sessions[0].scan_rate
                self.num_channels = self.emg_sessions[0].num_channels
                self.stim_start = self.emg_sessions[0].stim_start
            self.reset_properties(recalculate=True)

    def remove_session(self, session_id : str):
        """
        Removes a session from the dataset.

        Args:
            session_id (str): The session_id of the session to be removed.
        """
        if session_id not in [session.session_id for session in self.emg_sessions]:
            logging.warning(f">! Error: session {session_id} not found in the dataset.")
        else:
            self.emg_sessions = [session for session in self.emg_sessions if session.session_id != session_id]
            self.reset_properties(recalculate=True)
    
    def reload_dataset_sessions(self):
        """
        Reloads the dataset, adding any removed sessions back to the dataset.
        """
        fresh_temp_dataset = EMGDataset(self.original_emg_sessions, self.date, self.animal_id, self.condition, temp=True)
        self.emg_sessions = fresh_temp_dataset.emg_sessions
        channel_name_dict = {fresh_temp_dataset.channel_names[i]: self.channel_names[i] for i in range(self.num_channels)}
        self.rename_channels(channel_name_dict)
        self.update_reflex_latency_windows(self.m_start, self.m_duration, self.h_start, self.h_duration)
        self.update_reflex_parameters()
        self.apply_preferences(reset_properties=False)
        self.reset_properties(recalculate=True)
    
    def reload_session(self, session_id : str):
        """
        Reloads a session that was removed from the dataset.

        Args:
            session_id (str): The session_id of the session to be reloaded.
        """
        session_reloaded = False
        sessions_reloaded = 0

        for session in self.emg_sessions:
            if session_id == session.session_id:
                session.reload_recordings()
                session.channel_names = self.channel_names
                session.apply_preferences()
                session_reloaded = True
                sessions_reloaded += 1
        
        if not session_reloaded:
            raise ValueError(f"Error: Session {session_id} could not be found in the dataset. The session cannot be reloaded.")
        elif sessions_reloaded > 1:
            logging.warn(f"Warning: Multiple sessions with the ID {session_id} were found in the dataset. All sessions were reloaded.")
        
        self.reset_properties(recalculate=True)

    def get_session(self, session_idx: int) -> EMGSession:
        """
        Returns the EMGSession object at the specified index.
        """
        return self.emg_sessions[session_idx]

    def update_reflex_latency_windows(self, m_start, m_duration, h_start, h_duration):
        for window in self.latency_windows:
            if window.name == "M-wave":
                window.start_times = m_start
                window.durations = m_duration
            elif window.name == "H-reflex":
                window.start_times = h_start
                window.durations = h_duration
        for session in self.emg_sessions:
            session.update_reflex_latency_windows(m_start, m_duration, h_start, h_duration)

    def update_reflex_parameters(self):
        for window in self.latency_windows:
            if window.name == "M-wave":
                self.m_start = window.start_times
                self.m_duration = window.durations
            elif window.name == "H-reflex":
                self.h_start = window.start_times
                self.h_duration = window.durations
        for session in self.emg_sessions:
            session.update_reflex_parameters()

    def rename_channels(self, new_names : dict[str]):
        """
        Renames a channel in the dataset.

        Args:
            new_names (dict[str]): A dictionary mapping old channel names to new channel names.
        """
        # Rename the channels in each session.
        for session in self.emg_sessions:
            session.rename_channels(new_names)
        # Rename the channels in the dataset.
        for i, new_name in enumerate(new_names.values()):
            try:
                self.channel_names[i] = new_name
            except IndexError:
                logging.warning("Error: The number of new names does not match the number of channels in this dataset.")
    
    def apply_preferences(self, reset_properties=True):
        """
        Applies the preferences set in the config file to the dataset.
        """
        self._load_config_settings() # Load the config settings from file.

        # Apply preferences to the session objects.
        for session in self.emg_sessions:
            session.apply_preferences(reset_properties=False)

        # Re-create the plotter object with the new preferences.
        self.plotter = EMGDatasetPlotter(self)
        for latency_window in self.latency_windows:
            latency_window.linestyle = self.latency_window_style
        
        if reset_properties:
            self.reset_properties(recalculate=True)
        
    # Save and load the dataset object.
    def save_dataset(self, save_path=None):
        """
        Save the curated dataset object to disk.

        Args:
            save_path (str): The filename/save path to use for saving the dataset object.
        """        
        if save_path is None:
            save_path = self.save_path
        logging.info(f"Saving dataset '{self.formatted_name}' to {save_path}.")
            
        with open(save_path, 'wb') as file:
            pickle.dump(self, file)

    @staticmethod
    def load_dataset(save_path):
        """
        Load a previously saved dataset object from disk.

        Args:
            save_path (str): The filename/save path of the saved dataset object.

        Returns:
            EMGDataset: The loaded dataset object.
        """
        logging.info(f"Loading dataset from {save_path}.")
        with open(save_path, 'rb') as file:
            dataset = pickle.load(file) # type: EMGDataset
            dataset.apply_preferences(reset_properties=False)
        return dataset
    
    # Static methods for extracting information from dataset names and dataset dictionaries.
    @staticmethod
    def getDatasetInfo(dataset_name : str, preferred_date_format : str = None) -> tuple:
        """
        Extracts information from a dataset' directory name.

        Args:
            dataset_name (str): The name of the dataset in the format '[YYMMDD] [AnimalID] [Condition]'.

        Returns:
            tuple: A tuple containing the extracted information in the following order: (date, animal_id, condition).
                If the dataset name does not match the expected format, returns (None, None, None).
        """
        # Define the regex pattern
        pattern = r'^(\d{6,8})\s([A-Z0-9.]+)\s(.+)$'
        
        # Match the pattern
        match = re.match(pattern, dataset_name)
        
        if match:
            date_string = match.group(1)
            animal_id = match.group(2)
            condition = match.group(3)

            parsed_date, format_info = EMGData.parse_date(date_string, preferred_date_format)
            
            if isinstance(parsed_date, datetime):
                formatted_date = parsed_date.strftime('%Y-%m-%d')
                logging.info(f'Date: {formatted_date}, Format: {format_info}, Animal ID: {animal_id}, Condition: {condition}')
                return formatted_date, animal_id, condition
            else:
                logging.error(f"Error: {format_info}\n\n Make the neccessary changes to the dataset name, re-import your data, and try again.")
                # return 'DATE_ERROR', animal_id, condition
                raise ValueError(f"Error: {format_info}")
            
        else:
            logging.error(f"Error: Dataset ID '{dataset_name}' does not match the expected format: '[YYMMDD] [AnimalID] [Condition]'.")
            raise ValueError(f"Error: Dataset ID '{dataset_name}' does not match the expected format: '[YYMMDD] [AnimalID] [Condition]'.")

    @classmethod
    def dataset_from_dataset_dict(cls, dataset_dict: dict, dataset_idx: int, emg_sessions_to_exclude: List[str] = [], temp=True) -> 'EMGDataset':
        """
        Instantiates an EMGDataset from a dataset dictionary for downstream analysis.

        Args:
            dataset_dict (dict): A dictionary containing dataset information (keys = dataset names, values = dataset filepaths).
            datasets (list): A list of dataset names (keys).
            dataset_idx (int): The index of the dataset to be used.
            emg_sessions_to_exclude (list, optional): A list of EMG sessions to exclude. Defaults to an empty list.
            temp (bool, optional): Whether to create a temporary dataset object or save to the bin folder. Defaults to True.

        Returns:
            EMGDataset: The session of interest for downstream analysis.
        """
        try: 
            datasets = list(dataset_dict.keys())
            date, animal_id, condition = cls.getDatasetInfo(datasets[dataset_idx])
            # Future: Add a check to see if the dataset is already saved as a pickle file. If it is, load the pickle file instead of re-creating the dataset.
            dataset_oi = EMGDataset(dataset_dict[datasets[dataset_idx]], date, animal_id, condition, 
                                    emg_sessions_to_exclude=emg_sessions_to_exclude, temp=temp)
            return dataset_oi
        except FileExistsError as e:
            save_path = str(e)
            dataset_oi = EMGDataset.load_dataset(save_path)
            return dataset_oi

    # Private methods for the EMGDataset class.
    def __unpackEMGSessions(self, emg_sessions):
        """
        Unpacks a list of EMG session Pickle files and outputs a list of EMGSession instances for those pickles.
        If a list of EMGSession instances is passed, will return that same list.

        Args:
            emg_sessions (list): a list of instances of the class EMGSession, or a list of Pickle file locations that you want to use for the dataset.

        Returns:
            list: a list of EMGSession instances.

        Raises:
            TypeError: if an object in the 'emg_sessions' list was not properly converted to an EMGSession.
        """
        # Check if list dtype is EMGSession. If it is, convert it to a new EMGSession instance and replace the string in the list.
        pickled_sessions = []
        for session in emg_sessions:
            if isinstance(session, str): # If list object is dtype(string), then convert to an EMGSession.
                session = EMGSession(session) # replace the string with an actual session object.
                pickled_sessions.append(session)
            elif isinstance(session, EMGSession):
                logging.info(f"Session {session.session_id} is already an EMGSession instance with {session.num_recordings} recordings.")
                pickled_sessions.append(session)
            else:
                raise TypeError(f"An object in the 'emg_sessions' list was not properly converted to an EMGSession. Object: {session}, {type(session)}")
            
            pickled_sessions = sorted(pickled_sessions, key=lambda x: x.session_id)
        
        return pickled_sessions

    def __check_session_consistency(self):
        """
        Checks if all sessions in the dataset have the same parameters (scan rate, num_channels, stim_start).

        Returns:
            tuple: A tuple containing a boolean value indicating whether all sessions have consistent parameters and a message indicating the result.
        """
        reference_session = self.emg_sessions[0]
        reference_scan_rate = reference_session.scan_rate
        reference_num_channels = reference_session.num_channels
        reference_stim_start = reference_session.stim_start

        for session in self.emg_sessions[1:]:
            if session.scan_rate != reference_scan_rate:
                return False, f"Inconsistent scan_rate for {session.session_id}: {session.scan_rate} != {reference_scan_rate}."
            if session.num_channels != reference_num_channels:
                return False, f"Inconsistent num_channels for {session.session_id}: {session.num_channels} != {reference_num_channels}."
            if session.stim_start != reference_stim_start:
                return False, f"Inconsistent stim_start for {session.session_id}: {session.stim_start} != {reference_stim_start}."

        return True, "All sessions have consistent parameters"

class EMGExperiment(EMGData):
    def __init__(self, expt_id, expts_dict: List[str] = None, save_path: str = None, temp: bool = False):
            try:
                if expts_dict:
                    self.dataset_dict, dataset_dict_keys = expts_dict[expt_id]
                else:
                    logging.info("Attempting to load experiment by making a new experiment dictionary from the output path.")
                    expts_dict = EMGData.unpackPickleOutput(output_path=get_output_path())
                    self.dataset_dict, dataset_dict_keys = expts_dict[expt_id]
            except KeyError:
                raise KeyError(f"Error: Experiment '{expt_id}' not found in the dataset dictionary.")
            
            self.expt_id = expt_id.replace(' ', '_')
            self.save_path = os.path.join(get_output_bin_path(),(save_path or f"{self.expt_id}.pickle")) if save_path is None else save_path
            self.temp = temp
                
            if os.path.exists(self.save_path) and not temp:
                raise FileExistsError(f"Experiment already exists at {self.save_path}.")
            else:
                logging.info(f"Creating new experiment: {self.expt_id}.")
                super().__init__()
                self.formatted_name = expt_id
                self.plotter = EMGExperimentPlotter(self)

                # Create a list of EMGDataset instances from the dataset dictionary.
                emg_datasets_list = [EMGDataset.dataset_from_dataset_dict(self.dataset_dict, i, temp=True) for i in range(len(dataset_dict_keys))] # Type: List[EMGDataset]
                
                # Handle the case where only one dataset is passed as a string or an EMGDataset instance.
                if isinstance(emg_datasets_list, EMGDataset) or isinstance(emg_datasets_list, str):
                    emg_datasets_list = [emg_datasets_list]
                
                # Unpack the EMG datasets and exclude any datasets if needed.
                self.original_emg_datasets = emg_datasets_list # Save the original list of EMG datasets for reloading purposes.
                self.emg_datasets: List[EMGDataset] = []
                logging.info(f"Unpacking {len(emg_datasets_list)} EMG datasets.")
                self.emg_datasets = self.__unpackEMGDatasets(emg_datasets_list) # Convert file location strings into a list of EMGDataset instances.

                # Check that all sessions have the same parameters and set dataset parameters.
                consistent, message = True, ''
                # consistent, message = self.__check_dataset_consistency()
                if not consistent:
                    logging.error(f"Error: {message}")
                else:
                    # self.scan_rate : int = self.emg_datasets[0].scan_rate
                    # self.num_channels : int = self.emg_datasets[0].num_channels
                    # self.stim_start : float = self.emg_datasets[0].stim_start

                    # Get channel names and latency windows from the dataset with the longest list of channel names.
                    self.channel_names : List[str] = self.emg_datasets[0].channel_names # not checked for consistency, but should be the same for all sessions.
                    self.latency_windows : List[LatencyWindow] = copy.deepcopy(self.emg_datasets[0].latency_windows)
                    # for dataset in self.emg_datasets:
                    #     if len(dataset.channel_names) > len(self.channel_names):
                    #         self.channel_names = dataset.channel_names
                    #         self.latency_windows = dataset.latency_windows.copy()
                    
                    # Save the experiment if it is not a temporary experiment.
                    self.update_reflex_parameters()
                    self.apply_preferences(reset_properties=False)
                    if not temp:
                        self.save_experiment(self.save_path)
                        logging.info(f"Experiment saved to {self.save_path}")
                    logging.info(f"Experiment {self.expt_id} created successfully.")

    def _upgrade_from_version(self, old_version):
        old_version_parsed = parse_version(old_version)
        try:
            if old_version_parsed < parse_version('1.6.0'): # Upgrade from version 1.5.0 or older to 1.6.0.
                # If no latency windows attribute, then throw an error (version is likely too old to handle safely).
                if not hasattr(self, 'latency_windows'):
                    # if the data has a formatted name, try to use that for the error message.
                    if hasattr(self, 'formatted_name'):
                        raise ValueError(f"Dataset '{self.formatted_name}' is too old to upgrade. Delete the bin file and re-import the data.")
                    else:
                        raise ValueError("Dataset version is too old to upgrade. Delete the bin file and re-import the data.")
                
                # Store the current state of the object
                current_state = self.__dict__.copy()

                # Update the EMGExperiment's EMGDataset objects.
                for dataset in self.emg_datasets:
                    dataset._upgrade_from_version(old_version)
                    dataset.reset_properties(recalculate=False)
                
                # Reinitialize a temp object
                expt_info = {
                    'expt_id': current_state['formatted_name'],
                    'expts_dict': [],
                    'save_path': None,
                    'temp': True
                    }

                self.__init__(**expt_info)
                default_state = self.__dict__.copy()

                # Update the new state with the old values
                ignore_keys = {'plotter', 'version', 'm_end', 'h_end'}
                for key, value in current_state.items():
                    if (key not in ignore_keys) and (key not in default_state):
                            self.__dict__[key] = value
                            logging.info(f"Retained old key '{key}' during upgrade that was not in default state.")
                    else:
                        try:
                            if (key not in ignore_keys) and (key not in default_state or not deep_equal(default_state[key], value)):
                                self.__dict__[key] = value
                                logging.info(f"Retained old key '{key}' during upgrade.")
                        except Exception as e:
                            logging.error(f"Error comparing key '{key}' to default value. Error: {str(e)}")
                            raise e

                self.update_reflex_parameters()
                try:
                    if not current_state['temp']:
                        self.save_experiment(self.save_path)
                        logging.info(f"Experiment saved to {self.save_path}")
                except KeyError:
                    # Save the experiment anyway... it's better to have a saved version than not.
                    self.save_experiment(self.save_path)
                    logging.info(f"Experiment saved to {self.save_path}")
        except Exception as e:
            logging.error(f"Error upgrading dataset from version {old_version}. If this problem persists, try to delete and re-import this experiment: {str(e)}")
            raise e
        # Add any other version upgrade checks below.

    def experiment_parameters(self):
        """
        Logs EMG dataset parameters.
        """
        report = [f"Experiment ID: {self.expt_id}",
                  f"Datasets ({len(self.emg_datasets)}): {[dataset.dataset_id for dataset in self.emg_datasets]}."]

        for line in report:
            logging.info(line)
        return report

    def invert_channel_polarity(self, channel_index):
        """
        Inverts the polarity of a recording channel.

        Args:
            channel_index (int): The index of the channel to invert.
        """
        try:
            for dataset in self.emg_datasets:
                dataset.invert_channel_polarity(channel_index)
            logging.info(f"Channel {channel_index} polarity has been inverted for all datasets in experiment {self.expt_id}.")
        except IndexError:
            logging.error(f"Error: Channel index {channel_index} is out of range for the number of channels in the dataset.")
            
    def apply_preferences(self, reset_properties=True):
        """
        Applies the preferences set in the config file to the dataset.
        """
        self._load_config_settings() # Load the config settings from file.

        # Apply preferences to the session objects.
        for dataset in self.emg_datasets:
            dataset.apply_preferences(reset_properties=reset_properties)

        # Re-create the plotter object with the new preferences.
        self.plotter = EMGExperimentPlotter(self)
        for latency_window in self.latency_windows:
            latency_window.linestyle = self.latency_window_style

    def rename_channels(self, new_names : dict[str]):
        # Rename the channels in the experiment.
        for i, new_name in enumerate(new_names.values()):
            try:
                self.channel_names[i] = new_name
            except IndexError:
                self.channel_names.append(new_name)
        
        # Rename the channels in each dataset.
        for dataset in self.emg_datasets:
            try:
                dataset.rename_channels(new_names)
            except IndexError:
                logging.error("Error: The number of new names does not match the number of channels in the dataset.")

    def rename_experiment(self, new_name : str):
        """
        Renames the experiment and updates the formatted_name attribute.

        Args:
            new_name (str): The new name for the experiment.
        """
        self.save_path = os.path.join(get_output_bin_path(), f"{new_name}.pickle")
        self.expt_id = new_name.replace(' ', '_')
        self.formatted_name = new_name
        logging.info(f"Experiment renamed to '{new_name}'.")

    def update_reflex_latency_windows(self, m_start, m_duration, h_start, h_duration):
        for window in self.latency_windows:
            if window.name == "M-wave":
                window.start_times = m_start
                window.durations = m_duration
            elif window.name == "H-reflex":
                window.start_times = h_start
                window.durations = h_duration
        for dataset in self.emg_datasets:
            dataset.update_reflex_latency_windows(m_start, m_duration, h_start, h_duration)

    def update_reflex_parameters(self):
        for window in self.latency_windows:
            if window.name == "M-wave":
                self.m_start = window.start_times
                self.m_duration = window.durations
            elif window.name == "H-reflex":
                self.h_start = window.start_times
                self.h_duration = window.durations
        for dataset in self.emg_datasets:
            dataset.update_reflex_parameters()

    def reset_properties(self, recalculate: bool = False):
        for dataset in self.emg_datasets:
            dataset.reset_properties(recalculate=recalculate)

    def get_dataset(self, dataset_idx: int) -> EMGDataset:
        """
        Returns the EMGDataset object at the specified index.
        """
        return self.emg_datasets[dataset_idx]

    @property
    def dataset_names(self):
        return [dataset.formatted_name for dataset in self.emg_datasets]
    
    def save_experiment(self, save_path=None):
        """
        Save the curated dataset object to disk.

        Args:
            save_path (str): The filename/save path to use for saving the dataset object.
        """
        if save_path is None:
            save_path = self.save_path

        logging.info(f"Saving experiment '{self.expt_id}' to {save_path}.")
            
        with open(save_path, 'wb') as file:
            pickle.dump(self, file)
    
    @staticmethod
    def load_experiment(save_path):
        """
        Load a previously saved experiment object from disk.

        Args:
            save_path (str): The filename/save path of the saved experiment object.

        Returns:
            EMGExperiment: The loaded experiment object.
        """
        logging.info(f"Reloading experiment from file: {save_path}.")
        with open(save_path, 'rb') as file:
            experiment = pickle.load(file) # type: EMGExperiment
            experiment.apply_preferences(reset_properties=False)
            return experiment

    @staticmethod
    def getExperimentInfo(experiment_name : str) -> tuple:
        pass

    def __unpackEMGDatasets(self, emg_datasets):
        """
        Unpacks a list of EMG dataset Pickle files and outputs a list of EMGDataset instances for those pickles.
        If a list of EMGDataset instances is passed, will return that same list.

        Args:
            emg_datasets (list): a list of instances of the class EMGDataset, or a list of Pickle file locations that you want to use for the dataset.

        Returns:
            list: a list of EMGDataset instances.

        Raises:
            TypeError: if an object in the 'emg_datasets' list was not properly converted to an EMGDataset.
        """
        # Check if list dtype is EMGDataset. If it is, convert it to a new EMGDataset instance and replace the string in the list.
        pickled_datasets = []
        for dataset in emg_datasets:
            if isinstance(dataset, str): # If list object is dtype(string), then convert to an EMGDataset.
                logging.info(f"Unpacking dataset: {dataset}")
                dataset = EMGDataset(dataset) # replace the string with an actual dataset object.
                pickled_datasets.append(dataset)
            elif isinstance(dataset, EMGDataset):
                pickled_datasets.append(dataset)
            else:
                raise TypeError(f"An object in the 'emg_datasets' list was not properly converted to an EMGDataset. Object: {dataset}, {type(dataset)}")
            
            logging.info("Sorting datasets by dataset_id.")
            pickled_datasets = sorted(pickled_datasets, key=lambda x: x.dataset_id)
        
        return pickled_datasets

    def __check_dataset_consistency(self):
        """
        Checks if all datasets in the experiment have the same parameters (scan rate, num_channels, stim_start).

        Returns:
            tuple: A tuple containing a boolean value indicating whether all datasets have consistent parameters and a message indicating the result.
        """
        reference_dataset = self.emg_datasets[0]
        reference_num_channels = reference_dataset.num_channels

        for dataset in self.emg_datasets[1:]:
            if dataset.num_channels != reference_num_channels:
                return False, f"Inconsistent num_channels for {dataset.formatted_name}: {dataset.num_channels} != {reference_num_channels}."

        return True, "All datasets have consistent parameters"


if __name__ == '__main__':
    from monstim_converter import pickle_data  # noqa: F401
    from Analyze_EMG import EMGData,EMGDataset

    #Process CSVs into Pickle files: 'files_to_analyze' --> 'output'
    # pickle_data(DATA_PATH, OUTPUT_PATH) # If pickles are already created, comment this line out.

    # Create dictionaries of Pickle datasets and single sessions that are in the 'output' directory.
    dataset_dict, datasets = EMGData.unpackPickleOutput(get_output_bin_path())
    for idx, dataset in enumerate(datasets):
        print(f'dataset index {idx}: {dataset}')

    # Define dataset of interest for downstream analysis.
    sessions_to_exclude = [] # Add any sessions to exclude from the dataset here.
    dataset_idx = int(input('Dataset of Interest (index):')) # pick the dataset index of interest from the generate list above.
    dataset_oi = EMGDataset.dataset_from_dataset_dict(dataset_dict, dataset_idx, sessions_to_exclude)
    
    # Display dataset parameters.
    dataset_oi.dataset_parameters()

    # Define session of interest for downstream analysis.
    session_idx = int(input('Session of Interest (index):')) # pick the session index of interest from the generate list above
    session_oi = dataset_oi.get_session(session_idx)

    # Display session parameters.
    session_oi.session_parameters()

    # Visualize single EMG session raw and filtered
    session_oi.plot(plot_type = 'emg', m_flags=True, h_flags=True, data_type='filtered')
    # session_oi.plot(plot_type = 'emg', m_flags=True, h_flags=True, data_type='raw')
    session_oi.plot(plot_type = 'emg', m_flags=True, h_flags=True, data_type='rectified_filtered')
    # session_oi.plot(plot_type = 'emg', m_flags=True, h_flags=True, data_type='rectified_raw')

    # Use the update_window_settings method to temporarily change the reflex window settings and then replot. Otherwise comment out.
    # session_oi.update_window_settings()
    # session_oi.plot(plot_type = 'emg', m_flags=True, h_flags=True, data_type='filtered')

    # Inspect session reflex curves and suspected H-reflex trials with these methods.
    session_oi.plot(plot_type='reflexCurves')
    session_oi.plot(plot_type='reflexCurves', relative_to_mmax=True)

    # M-max analysis and visualization.
    session_oi.m_max_report()
    session_oi.plot(plot_type = 'mmax')

    # Visualize the entire dataset's avereaged reflex curves with these methods of the dataset object.
    dataset_oi.plot(plot_type = 'reflexCurves', relative_to_mmax=True, mmax_report=True)

    # Visualize the entire dataset's avereaged reflex values at H-max with this method of the dataset object.
    dataset_oi.plot(plot_type = 'maxH', relative_to_mmax=True)

    print('Done!')