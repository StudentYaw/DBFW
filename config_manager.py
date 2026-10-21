from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# Single source of truth for defaults. config.yaml only needs to contain
# overrides; any key missing there (or the whole file) falls back to this.
DEFAULT_CONFIG: dict[str, Any] = {
    # Matched case-insensitively against window titles (Windows) or app and
    # window names (macOS); `python game_window.py` lists the open windows.
    'window_title': 'DBSCGFW',
    'codes_file': 'codes.txt',
    'codes_err_file': 'codes_with_errors.txt',
    'code_length': 16,
    'confidence': 0.85,
    'sleep': 0.5,
    'sleep_confirm': 5,
    'write_interval': 0.03,
    'original_resolution': [1920, 1080],
    'tolerance': 100,
    'max_errors': 5,
    # Append by default: after an aborted round codes.txt still holds the
    # codes that were not entered yet, and overwriting would lose them.
    'manual_overwrite_default': False,
    'ocr_overwrite_default': False,
}

class ConfigManager:
    def __init__(self, config_file: str | Path = 'config.yaml') -> None:
        self.config_file = Path(config_file)
        self.config: dict[str, Any] = self.load_config()

    def load_config(self) -> dict[str, Any]:
        config = dict(DEFAULT_CONFIG)
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                loaded = yaml.safe_load(f) or {}
            config.update(loaded)
        return config

    def get(self, key: str) -> Any:
        return self.config.get(key)
