import yaml
from pathlib import Path

class ConfigManager:
    def __init__(self, config_file='config.yaml'):
        self.config_file = Path(config_file)
        self.config = self.load_config()

    def load_config(self):
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                return yaml.safe_load(f)
        else:
            # Default config
            return {
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
                'manual_overwrite_default': True,
                'ocr_overwrite_default': False
            }

    def get(self, key):
        return self.config.get(key)
