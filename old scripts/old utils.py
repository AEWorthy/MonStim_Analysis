"""
Misc. helper functions.
"""

import json
import yaml

# def load_config(config_file):
#     with open(config_file, 'r') as file:
#         config = json.load(file)
#     return config

def load_config(config_file):
    with open(config_file, 'r') as file:
        config = yaml.safe_load(file)
    return config