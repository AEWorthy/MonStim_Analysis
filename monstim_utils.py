# Utility functions/scripts for the project
import os
import sys
from typing import List
import yaml

from PyQt6.QtWidgets import QApplication
import numpy as np

DIST_PATH = 'dist'
OUTPUT_PATH = 'data'
SAVED_DATASETS_PATH = 'datasets'
BIN_EXTENSION = '.pkl'

def to_camel_case(text : str):
    words = text.split()
    camel_case_text = words[0].lower() + ''.join(word.capitalize() for word in words[1:])
    return camel_case_text

def format_report(report : List[str]):
    formatted_report = ''
    for line in report:
        if line == report[-1]:
            formatted_report += line
        else:
            formatted_report += line + '\n'   
    return formatted_report

def get_base_path():
    if getattr(sys, 'frozen', False):
        if sys.platform == 'darwin':
            # macOS .app bundle
            exe_path = os.path.dirname(sys.executable)
            base_path = os.path.abspath(os.path.join(exe_path, '..', '..', '..'))
        else:
            # Windows .exe or other platforms
            base_path = os.path.dirname(sys.executable)
    else:
        # Running in a normal Python environment
        base_path = os.path.dirname(os.path.abspath(__file__))

    return base_path

def get_bundle_path():
    if getattr(sys, 'frozen', False):
        bundle_path = sys._MEIPASS
    else:
        # Running in a normal Python environment
        bundle_path = os.path.dirname(os.path.abspath(__file__))

    return bundle_path

def get_output_path():
    output_path = os.path.join(get_base_path(), OUTPUT_PATH)
    if not os.path.exists(output_path):
        os.makedirs(output_path)
    return output_path

def get_source_path():
    if getattr(sys, 'frozen', False):
        source_path = os.path.join(get_bundle_path(), 'src')
    else:
        source_path = os.path.join(get_base_path(), 'src')
    return source_path

def get_docs_path():
    if getattr(sys, 'frozen', False):
        docs_path = os.path.join(get_bundle_path(), 'docs')
    else:
        docs_path = os.path.join(get_base_path(), 'docs')
    return docs_path

def get_config_path():
    # later, config will be in the bundle path once I implement the preferences window.
    return os.path.join(get_docs_path(), 'config.yml')

def get_output_bin_path():
    output_bin_path = os.path.join(get_output_path(), 'bin')
    if not os.path.exists(output_bin_path):
        os.makedirs(output_bin_path)
    return output_bin_path

def get_data_path():
    if getattr(sys, 'frozen', False):
        data_path = get_base_path()
    else:
        data_path = os.path.join(get_base_path(), DIST_PATH)
    return data_path

def get_main_window():
    from monstim_gui.gui_main import EMGAnalysisGUI
    
    active_window = QApplication.activeWindow()

    if isinstance(active_window, EMGAnalysisGUI):
        return active_window
    elif active_window.__class__.__name__ == 'EMGAnalysisGUI': # for special case when running gui_main.py directly.
        return active_window
    else:
        return None

def deep_equal(val1, val2):
    if isinstance(val1, np.ndarray) and isinstance(val2, np.ndarray):
        return np.array_equal(val1, val2)
    elif isinstance(val1, dict) and isinstance(val2, dict):
        if val1.keys() != val2.keys():
            return False
        return all(deep_equal(val1[k], val2[k]) for k in val1)
    elif isinstance(val1, list) and isinstance(val2, list):
        if len(val1) != len(val2):
            return False
        return all(deep_equal(v1, v2) for v1, v2 in zip(val1, val2))
    else:
        return val1 == val2

def load_config(config_file=None):
        """
        Loads the config.yaml file into a YAML object that can be used to reference hard-coded configurable constants.

        Args:
            config_file (str): location of the 'config.yaml' file.
        """
        if config_file is None:
            defualt_config_file = get_config_path()
            user_config_file = os.path.join(os.path.dirname(defualt_config_file), 'config-user.yml')
            # if it exists, get user config file
            if os.path.exists(user_config_file):
                config_file = user_config_file
            else:
                config_file = defualt_config_file
        with open(config_file, 'r') as file:
            config = yaml.safe_load(file)
        return config

# Custom YAML loader to handle tuples
class CustomLoader(yaml.SafeLoader):
    def construct_python_tuple(self, node):
        return tuple(self.construct_sequence(node))

CustomLoader.add_constructor(
    u'tag:yaml.org,2002:python/tuple',
    CustomLoader.construct_python_tuple)

