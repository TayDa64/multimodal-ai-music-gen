"""
Sample Loader - Import and manage audio samples from MPC libraries

Supports:
- Loading .wav samples from directories
- Parsing MPC .xpm drum programs to extract sample mappings
- Auto-detecting sample types (kick, snare, hihat, etc.)
- Organizing samples into usable drum kits
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET
import re

import numpy as np

try:
    import soundfile as sf
    HAS_SOUNDFILE = True
except ImportError:
    HAS_SOUNDFILE = False


# Sample type detection keywords
SAMPLE_KEYWORDS = {
    'kick': ['kick', 'kik', 'kck', 'bd', 'bass_drum', 'bassdrum', '808'],
    'snare': ['snare', 'snr', 'sd', 'sn'],
    'clap': ['clap', 'clp', 'cp'],
    'hihat_closed': ['hihat', 'hh', 'hat', 'closed', 'chh'],
    'hihat_open': ['open', 'ohh', 'open_hat'],
    'rim': ['rim', 'rimshot', 'stick'],
    'tom': ['tom', 'tm'],
    'crash': ['crash', 'crsh'],
    'ride': ['ride', 'rd'],
    'perc': ['perc', 'shaker', 'tamb', 'conga', 'bongo'],
    '808': ['808', 'sub', 'bass'],
}


@dataclass
class LoadedSample:
    """Represents a loaded audio sample."""
    path: str
    name: str
    sample_type: str  # kick, snare, hihat, etc.
    audio: Optional[np.ndarray] = None
    sample_rate: int = 44100
    duration_sec: float = 0.0
    midi_note: int = 36  # Default to C1
    
    @property
    def filename(self) -> str:
        return Path(self.path).stem


@dataclass
class SampleKit:
    """Collection of samples organized as a kit."""
    name: str
    samples: Dict[str, LoadedSample] = field(default_factory=dict)
    source_path: str = ""
    
    def get_sample(self, sample_type: str) -> Optional[LoadedSample]:
        """Get sample by type."""
        return self.samples.get(sample_type)
    
    def list_types(self) -> List[str]:
        """List available sample types."""
        return list(self.samples.keys())


def detect_sample_type(filename: str) -> str:
    """
    Detect sample type from filename.
    
    Args:
        filename: Sample filename
        
    Returns:
        Detected sample type or 'unknown'
    """
    name_lower = filename.lower()
    
    for sample_type, keywords in SAMPLE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in name_lower:
                return sample_type
    
    return 'unknown'


def load_wav_sample(
    path: str,
    target_sample_rate: int = 44100
) -> Optional[LoadedSample]:
    """
    Load a WAV file as a sample.
    
    Args:
        path: Path to WAV file
        target_sample_rate: Target sample rate for resampling
        
    Returns:
        LoadedSample object or None if failed
    """
    if not HAS_SOUNDFILE:
        print("Warning: soundfile not available, cannot load samples")
        return None
    
    try:
        audio, sr = sf.read(path)
        
        # Convert stereo to mono if needed
        if len(audio.shape) > 1:
            audio = np.mean(audio, axis=1)
        
        # Resample if needed (simple decimation/interpolation)
        if sr != target_sample_rate:
            ratio = target_sample_rate / sr
            new_length = int(len(audio) * ratio)
            indices = np.linspace(0, len(audio) - 1, new_length)
            audio = np.interp(indices, np.arange(len(audio)), audio)
        
        # Normalize to prevent clipping
        peak = np.max(np.abs(audio))
        if peak > 0:
            audio = audio / peak * 0.9
        
        filename = Path(path).stem
        sample_type = detect_sample_type(filename)
        
        return LoadedSample(
            path=path,
            name=filename,
            sample_type=sample_type,
            audio=audio,
            sample_rate=target_sample_rate,
            duration_sec=len(audio) / target_sample_rate,
        )
        
    except Exception as e:
        print(f"Error loading {path}: {e}")
        return None


def load_samples_from_directory(
    directory: str,
    recursive: bool = True,
    extensions: List[str] = ['.wav', '.WAV', '.aif', '.aiff']
) -> List[LoadedSample]:
    """
    Load all audio samples from a directory.
    
    Args:
        directory: Path to sample directory
        recursive: Whether to search subdirectories
        extensions: File extensions to include
        
    Returns:
        List of loaded samples
    """
    samples = []
    directory = Path(directory)
    
    if not directory.exists():
        print(f"Directory not found: {directory}")
        return samples
    
    # Find all audio files
    pattern = '**/*' if recursive else '*'
    for ext in extensions:
        for path in directory.glob(pattern + ext):
            sample = load_wav_sample(str(path))
            if sample:
                samples.append(sample)
    
    print(f"Loaded {len(samples)} samples from {directory}")
    return samples


def organize_samples_as_kit(
    samples: List[LoadedSample],
    kit_name: str = "Imported Kit"
) -> SampleKit:
    """
    Organize samples into a kit by type.
    
    If multiple samples of same type, keeps the first one.
    
    Args:
        samples: List of loaded samples
        kit_name: Name for the kit
        
    Returns:
        Organized SampleKit
    """
    kit = SampleKit(name=kit_name)
    
    for sample in samples:
        if sample.sample_type not in kit.samples:
            kit.samples[sample.sample_type] = sample
        else:
            # Append number to create variants
            i = 2
            variant_type = f"{sample.sample_type}_{i}"
            while variant_type in kit.samples:
                i += 1
                variant_type = f"{sample.sample_type}_{i}"
            kit.samples[variant_type] = sample
    
    return kit


def parse_mpc_xpm(xpm_path: str) -> Optional[Dict]:
    """
    Parse an MPC .xpm drum program file.
    
    Args:
        xpm_path: Path to .xpm file
        
    Returns:
        Dictionary with pad mappings or None if failed
    """
    try:
        tree = ET.parse(xpm_path)
        root = tree.getroot()
        
        program_info = {
            'name': '',
            'pads': {},
        }
        
        # Get program name
        meta = root.find('Metadata')
        if meta is not None:
            name_elem = meta.find('Name')
            if name_elem is not None:
                program_info['name'] = name_elem.text
        
        # Parse pad banks
        banks = root.find('PadBanks')
        if banks is not None:
            for bank in banks.findall('Bank'):
                bank_name = bank.get('Name', 'A')
                
                for pad in bank.findall('Pad'):
                    pad_num = int(pad.get('Number', 0))
                    pad_id = f"{bank_name}{pad_num + 1}"
                    
                    pad_info = {
                        'bank': bank_name,
                        'number': pad_num,
                        'name': '',
                        'midi_note': 36 + pad_num,
                        'sample_path': None,
                    }
                    
                    name_elem = pad.find('Name')
                    if name_elem is not None:
                        pad_info['name'] = name_elem.text
                    
                    note_elem = pad.find('MidiNote')
                    if note_elem is not None:
                        pad_info['midi_note'] = int(note_elem.text)
                    
                    # Get sample layer
                    layers = pad.find('Layers')
                    if layers is not None:
                        layer = layers.find('Layer')
                        if layer is not None:
                            path_elem = layer.find('FilePath')
                            if path_elem is not None:
                                pad_info['sample_path'] = path_elem.text
                    
                    program_info['pads'][pad_id] = pad_info
        
        return program_info
        
    except Exception as e:
        print(f"Error parsing XPM: {e}")
        return None


def load_kit_from_xpm(
    xpm_path: str,
    samples_base_dir: Optional[str] = None
) -> Optional[SampleKit]:
    """
    Load a sample kit from an MPC .xpm drum program.
    
    Args:
        xpm_path: Path to .xpm file
        samples_base_dir: Base directory for sample paths (if relative)
        
    Returns:
        SampleKit or None if failed
    """
    program = parse_mpc_xpm(xpm_path)
    if not program:
        return None
    
    # Determine samples directory
    if samples_base_dir is None:
        # Look in [ProjectData]/Samples relative to xpm
        xpm_dir = Path(xpm_path).parent
        samples_base_dir = xpm_dir / "Samples"
        if not samples_base_dir.exists():
            samples_base_dir = xpm_dir
    
    kit = SampleKit(
        name=program['name'] or Path(xpm_path).stem,
        source_path=xpm_path,
    )
    
    for pad_id, pad_info in program['pads'].items():
        if pad_info['sample_path']:
            # Resolve sample path
            sample_path = pad_info['sample_path']
            
            # Handle [ProjectData] paths
            if '[ProjectData]' in sample_path:
                sample_path = sample_path.replace('[ProjectData]/', '')
                sample_path = sample_path.replace('[ProjectData]\\', '')
            
            # Try to find the sample
            full_path = Path(samples_base_dir) / sample_path
            
            if not full_path.exists():
                # Try just the filename
                full_path = Path(samples_base_dir) / Path(sample_path).name
            
            if full_path.exists():
                sample = load_wav_sample(str(full_path))
                if sample:
                    sample.name = pad_info['name'] or sample.name
                    sample.midi_note = pad_info['midi_note']
                    
                    # Use pad name for type detection if sample type unknown
                    if sample.sample_type == 'unknown' and pad_info['name']:
                        sample.sample_type = detect_sample_type(pad_info['name'])
                    
                    kit.samples[pad_id] = sample
    
    return kit


class SampleLibrary:
    """
    Manages a collection of sample kits.
    
    Allows importing from directories, MPC programs, and individual files.
    """
    
    def __init__(self):
        self.kits: Dict[str, SampleKit] = {}
        self.all_samples: List[LoadedSample] = []
    
    def import_directory(
        self,
        directory: str,
        kit_name: Optional[str] = None
    ) -> Optional[SampleKit]:
        """Import samples from a directory as a kit."""
        samples = load_samples_from_directory(directory)
        if not samples:
            return None
        
        if kit_name is None:
            kit_name = Path(directory).name
        
        kit = organize_samples_as_kit(samples, kit_name)
        kit.source_path = directory
        
        self.kits[kit_name] = kit
        self.all_samples.extend(samples)
        
        return kit
    
    def import_xpm(
        self,
        xpm_path: str,
        samples_dir: Optional[str] = None
    ) -> Optional[SampleKit]:
        """Import samples from an MPC .xpm file."""
        kit = load_kit_from_xpm(xpm_path, samples_dir)
        if kit:
            self.kits[kit.name] = kit
            self.all_samples.extend(kit.samples.values())
        return kit
    
    def import_single_sample(
        self,
        path: str,
        sample_type: Optional[str] = None
    ) -> Optional[LoadedSample]:
        """Import a single sample file."""
        sample = load_wav_sample(path)
        if sample and sample_type:
            sample.sample_type = sample_type
        if sample:
            self.all_samples.append(sample)
        return sample
    
    def get_sample_by_type(
        self,
        sample_type: str,
        kit_name: Optional[str] = None
    ) -> Optional[LoadedSample]:
        """Get a sample by type, optionally from a specific kit."""
        if kit_name and kit_name in self.kits:
            return self.kits[kit_name].get_sample(sample_type)
        
        # Search all kits
        for kit in self.kits.values():
            sample = kit.get_sample(sample_type)
            if sample:
                return sample
        
        return None
    
    def list_kits(self) -> List[str]:
        """List available kit names."""
        return list(self.kits.keys())
    
    def get_kit(self, name: str) -> Optional[SampleKit]:
        """Get a kit by name."""
        return self.kits.get(name)


# Convenience functions
def quick_load_samples(path: str) -> SampleKit:
    """
    Quickly load samples from a path.
    
    Automatically detects if path is:
    - Directory: Load all WAV files
    - .xpm file: Parse MPC program
    - .wav file: Load as single-sample kit
    """
    path = Path(path)
    
    if path.is_dir():
        samples = load_samples_from_directory(str(path))
        return organize_samples_as_kit(samples, path.name)
    
    elif path.suffix.lower() == '.xpm':
        kit = load_kit_from_xpm(str(path))
        return kit or SampleKit(name="Empty")
    
    elif path.suffix.lower() in ['.wav', '.aif', '.aiff']:
        sample = load_wav_sample(str(path))
        if sample:
            kit = SampleKit(name=path.stem)
            kit.samples[sample.sample_type] = sample
            return kit
    
    return SampleKit(name="Empty")
