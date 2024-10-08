# monstim_analysis/__init__.py

# Version
from .version import __version__  # noqa: F401

# Metadata
__title__ = 'monstim_analysis'
__description__ = 'Main module for MonStim analysis tools'
__author__ = 'Andrew Worthy'
__email__ = 'aeworth@emory.edu'

# Import functions
from .Analyze_EMG import EMGData, EMGSession, EMGDataset, EMGExperiment

# Define __all__ for module
__all__ = ['EMGData', 'EMGSession', 'EMGDataset', 'EMGExperiment']