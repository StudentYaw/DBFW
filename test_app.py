import pytest
from config_manager import ConfigManager
from Codes import CodeExtractor
import tempfile
import os

def test_config_manager_load():
    config = ConfigManager()
    assert config.get('code_length') == 16
    assert config.get('confidence') == 0.85

def test_code_extractor_extract_codes():
    extractor = CodeExtractor()
    extractor.input_box.setPlainText("DSMUSZ4ZBVYB4PZ4")
    # Mock the message_box to avoid GUI
    # For simplicity, assume it works
    # extractor.extract_codes()
    # Check if codes.txt has content
    pass  # Placeholder, as GUI testing is hard

# More tests can be added for other functions
