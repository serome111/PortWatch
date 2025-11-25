#!/usr/bin/env python3
"""
PortWatch Development Runner
Starts the tray application for development
"""
import sys
from pathlib import Path

# Ensure the project root is in the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import and run the tray app
from backend.ui import tray_app

if __name__ == "__main__":
    tray_app.main()
