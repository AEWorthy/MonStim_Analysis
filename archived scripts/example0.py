# MonStim_CSV_Analysis - example0.py

import csv_to_pickle_05242024 as csv_to_pickle_05242024
import Analyze_EMG

DATA_PATH = 'files_to_analyze'
OUTPUT_PATH = 'output'

pickled_test_session = 'output/240404-4_data.pickle' #'output/040224rec1_data.pickle'
pickled_test_dataset = ['output/240404-1_data.pickle','output/240404-2_data.pickle','output/240404-3_data.pickle','output/240404-4_data.pickle','output/240404-5_data.pickle']

## Process CSV files in "\files_to_analyze" into pickle files formatted for downstream analysis.
csv_to_pickle_05242024.pickle_single_session(DATA_PATH, OUTPUT_PATH)

## Analysis for a single session using class-based method
session = Analyze_EMG.EMGSession(pickled_test_session)
session.session_parameters()
session.plot_emg(channel_names=["LG", "TA"])
session.plot_emg_rectified(channel_names=["LG", "TA"])
session.plot_emg_suspectedH(channel_names=["LG", "TA"], h_threshold=0.05)
session.plot_reflex_curves(channel_names=["LG", "TA"])

## Analysis for multiple sessions.
sessions = []
for session in pickled_test_dataset:
    sessions.append(Analyze_EMG.EMGSession(session))

dataset = Analyze_EMG.EMGDataset(sessions)
dataset.plot_reflex_curves(channel_names=["LG", "TA"])