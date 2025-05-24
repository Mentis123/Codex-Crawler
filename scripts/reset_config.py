#!/usr/bin/env python3
"""Reset configuration to archived defaults."""
from utils.config_manager import reset_config

if __name__ == "__main__":
    reset_config()
    print("Configuration reset to defaults.")
