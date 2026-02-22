#!/usr/bin/env python3
"""I2C device scanner - detect connected sensors."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.utils.i2c_scanner import scan_i2c_devices

if __name__ == "__main__":
    devices = scan_i2c_devices()
    sys.exit(0 if devices else 1)
