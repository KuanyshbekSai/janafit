import sys
import os

# Add root directory to sys.path so modules like web, services, config can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.server import app
