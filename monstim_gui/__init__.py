# monstim_gui/__init__.py

__version__ = '0.3.2'

# Metadata
__title__ = 'monstim_gui'
__description__ = 'Main module for MonStim GUI'
__author__ = 'Andrew Worthy'
__email__ = 'aeworth@emory.edu'

# Import functions
from .gui_main import EMGAnalysisGUI
from .splash import SplashScreen

# Define __all__ for module
__all__ = ['EMGAnalysisGUI', 'SplashScreen']