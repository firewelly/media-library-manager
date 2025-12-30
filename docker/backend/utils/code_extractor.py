import sys
import os

# Add the project root to sys.path to allow importing the root module
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import everything from the root code_extractor module
from code_extractor import *
