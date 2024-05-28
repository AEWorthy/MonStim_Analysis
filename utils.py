"""
Misc. helper functions.
"""

import os
import yaml
from Analyze_EMG import EMGSession as MakeSession
from Analyze_EMG import EMGDataset as MakeDataset

def load_config(config_file):
    """
    Loads the config.yaml file into a YAML object that can be used to reference hard-coded configurable constants.

    Args:
        config_file (str): location of the 'config.yaml' file.
    """
    with open(config_file, 'r') as file:
        config = yaml.safe_load(file)
    return config

def unpackPickleOutput (output_path):
    """
    Unpacks a list of EMG session Pickle files and outputs a dictionary with k/v pairs of session names and the session Pickle location.

    Args:
        output_path (str): location of the output folder containing dataset directories/Pickle files.
    """
    dataset_pickles_dict = {} #k=datasets, v=pickle_filepath(s)

    for dataset in os.listdir(output_path):
        if os.path.isdir(os.path.join(output_path, dataset)):
            pickles = os.listdir(os.path.join(output_path, dataset))
            pickle_paths = [os.path.join(output_path, dataset, pickle).replace('\\', '/') for pickle in pickles]
            dataset_pickles_dict[dataset] = pickle_paths
        else: # if this is a single session instead...
            split_parts = dataset.split('-') # Split the string at the hyphens
            session_name = '-'.join(split_parts[:-1]) # Select the portion before the last hyphen to drop the "-SessionData.pickle" portion.
            dataset_pickles_dict[session_name] = os.path.join(output_path, dataset).replace('\\', '/')
    # Get dict keys
    dataset_dict_keys = list(dataset_pickles_dict.keys())
    return dataset_pickles_dict, dataset_dict_keys

def dataset_oi (dataset_dict, datasets, dataset_idx):
    """
    Defines a session of interest for downstream analysis.

    Args:
        output_path (str): location of the output folder containing dataset directories/Pickle files.
    """
    dataset_oi = MakeDataset(dataset_dict[datasets[dataset_idx]])
    return dataset_oi

def session_oi (dataset_dict, datasets, dataset_idx, session_idx):
    """
    Defines a dataset of interest for downstream analysis.

    Args:
        output_path (str): location of the output folder containing dataset directories/Pickle files.
    """
    dataset_oi = dataset_dict[datasets[dataset_idx]]
    session_oi = MakeSession(dataset_oi[session_idx])
    return session_oi