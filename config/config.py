#!/usr/bin/env python3
"""
Configuration management for wds-metrics.
Handles loading and saving the code base path from a gitignored config file.
"""

import json
from pathlib import Path
from typing import Optional


CONFIG_FILE = Path(__file__).parent / "config.json"


def load_config() -> dict:
    """Load configuration from config.json."""
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {CONFIG_FILE}\n"
            "Please run 'npm run init' to set up your configuration."
        )
    
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)


def save_config(config: dict) -> None:
    """Save configuration to config.json."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


def get_code_base_path() -> Path:
    """Get the code base path from configuration."""
    config = load_config()
    path_str = config.get('code_base_path')
    
    if not path_str:
        raise ValueError(
            "code_base_path not found in configuration.\n"
            "Please run 'npm run init' to set up your configuration."
        )
    
    path = Path(path_str).expanduser().resolve()
    
    if not path.exists():
        raise ValueError(f"Configured code base path does not exist: {path}")
    
    if not path.is_dir():
        raise ValueError(f"Configured code base path is not a directory: {path}")
    
    return path


def set_code_base_path(path: str) -> None:
    """Set the code base path in configuration."""
    path_obj = Path(path).expanduser().resolve()
    
    if not path_obj.exists():
        raise ValueError(f"Path does not exist: {path_obj}")
    
    if not path_obj.is_dir():
        raise ValueError(f"Path is not a directory: {path_obj}")
    
    config = {}
    if CONFIG_FILE.exists():
        config = load_config()
    
    config['code_base_path'] = str(path_obj)
    save_config(config)
    
    print(f"✅ Configuration saved: code_base_path = {path_obj}")
