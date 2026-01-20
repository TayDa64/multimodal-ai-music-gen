"""
Pytest fixtures for multimodal_gen tests.
"""
import pytest
import sys
import os
from pathlib import Path
import tempfile
import shutil

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def sample_rate():
    """Standard sample rate for tests."""
    return 48000


@pytest.fixture
def temp_dir():
    """Create temporary directory for test outputs."""
    tmp = tempfile.mkdtemp()
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def temp_yaml_file(temp_dir):
    """Create temporary YAML file for config tests."""
    yaml_path = Path(temp_dir) / "test_config.yaml"
    return yaml_path


@pytest.fixture
def mock_midi_note():
    """Sample MIDI note data."""
    return {
        'pitch': 60,
        'velocity': 0.8,
        'duration_samples': 24000,
        'channel': 0,
        'program': 0,
    }


@pytest.fixture
def trap_pattern():
    """Sample trap drum pattern for strategy tests."""
    return {
        'genre': 'trap',
        'bpm': 140,
        'section': 'verse',
        'time_signature': (4, 4),
    }


@pytest.fixture
def project_config_dir():
    """Get the configs/arrangements directory."""
    return PROJECT_ROOT / 'configs' / 'arrangements'
