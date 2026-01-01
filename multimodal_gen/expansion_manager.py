"""
Expansion Manager - Intelligent Instrument Expansion System

This module provides a comprehensive system for managing instrument expansions,
enabling AI to intelligently select and substitute instruments based on:
- Direct name matching (exact)
- Genre-specific mappings (mapped)
- Semantic role matching (role-based)
- Spectral similarity analysis (sonic)

Key Components:
1. ExpansionLoader - Scans and loads expansion packs
2. InstrumentIndex - Fast lookup across all sources
3. IntelligentMatcher - Multi-tier instrument resolution
4. ExpansionManager - Unified API for the system

Usage:
    from multimodal_gen.expansion_manager import ExpansionManager
    
    manager = ExpansionManager()
    manager.scan_expansions("./expansions")
    
    # Resolve instrument with intelligent fallback
    result = manager.resolve_instrument("krar", genre="eskista")
    print(result.path, result.match_type, result.note)
"""

import os
import json
import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Set, Any, Union
from enum import Enum
import re

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import soundfile as sf
    HAS_SOUNDFILE = True
except ImportError:
    HAS_SOUNDFILE = False

try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False


# =============================================================================
# CONSTANTS & ENUMS
# =============================================================================

SAMPLE_RATE = 44100

class MatchType(Enum):
    """How an instrument was resolved."""
    EXACT = "exact"           # Direct name match
    MAPPED = "mapped"         # Genre-specific mapping
    SEMANTIC = "semantic"     # Role-based matching
    SPECTRAL = "spectral"     # Sonic similarity
    DEFAULT = "default"       # Fallback to default library


class InstrumentRole(Enum):
    """Semantic roles instruments can fulfill."""
    # Drums
    KICK = "kick"
    SNARE = "snare"
    HIHAT = "hihat"
    CLAP = "clap"
    PERCUSSION = "percussion"
    CYMBAL = "cymbal"
    
    # Bass
    BASS_SUB = "bass_sub"           # 808, sub bass
    BASS_MELODIC = "bass_melodic"   # Bass guitar, synth bass
    
    # Melodic
    MELODIC_KEYS = "melodic_keys"       # Piano, rhodes, organ
    MELODIC_STRING = "melodic_string"   # Guitar, krar, masenqo
    MELODIC_SYNTH = "melodic_synth"     # Synth leads
    MELODIC_WIND = "melodic_wind"       # Flute, washint, sax
    
    # Texture
    PAD = "pad"
    TEXTURE = "texture"
    FX = "fx"
    
    # Ethnic specific
    ETHIOPIAN_STRING = "ethiopian_string"   # Krar, masenqo, begena
    ETHIOPIAN_WIND = "ethiopian_wind"       # Washint
    ETHIOPIAN_DRUM = "ethiopian_drum"       # Kebero


# Instrument name to role mapping
INSTRUMENT_ROLES = {
    # Standard drums
    "kick": InstrumentRole.KICK,
    "snare": InstrumentRole.SNARE,
    "hihat": InstrumentRole.HIHAT,
    "clap": InstrumentRole.CLAP,
    "perc": InstrumentRole.PERCUSSION,
    "percussion": InstrumentRole.PERCUSSION,
    "cymbal": InstrumentRole.CYMBAL,
    "crash": InstrumentRole.CYMBAL,
    "ride": InstrumentRole.CYMBAL,
    "rim": InstrumentRole.PERCUSSION,
    "tom": InstrumentRole.PERCUSSION,
    
    # Bass
    "808": InstrumentRole.BASS_SUB,
    "sub": InstrumentRole.BASS_SUB,
    "bass": InstrumentRole.BASS_MELODIC,
    "dark_bass": InstrumentRole.BASS_SUB,
    "deep_bass": InstrumentRole.BASS_SUB,
    "phatty": InstrumentRole.BASS_MELODIC,
    
    # Keys
    "piano": InstrumentRole.MELODIC_KEYS,
    "keys": InstrumentRole.MELODIC_KEYS,
    "rhodes": InstrumentRole.MELODIC_KEYS,
    "organ": InstrumentRole.MELODIC_KEYS,
    "clavinet": InstrumentRole.MELODIC_KEYS,
    
    # Strings/Guitar
    "guitar": InstrumentRole.MELODIC_STRING,
    "strings": InstrumentRole.MELODIC_STRING,
    
    # Synths
    "synth": InstrumentRole.MELODIC_SYNTH,
    "lead": InstrumentRole.MELODIC_SYNTH,
    "pluck": InstrumentRole.MELODIC_SYNTH,
    
    # Wind
    "flute": InstrumentRole.MELODIC_WIND,
    "sax": InstrumentRole.MELODIC_WIND,
    "brass": InstrumentRole.MELODIC_WIND,
    "horn": InstrumentRole.MELODIC_WIND,
    
    # Textures
    "pad": InstrumentRole.PAD,
    "stab": InstrumentRole.PAD,
    "fx": InstrumentRole.FX,
    "riser": InstrumentRole.FX,
    "sweep": InstrumentRole.FX,
    
    # Ethiopian
    "krar": InstrumentRole.ETHIOPIAN_STRING,
    "masenqo": InstrumentRole.ETHIOPIAN_STRING,
    "begena": InstrumentRole.ETHIOPIAN_STRING,
    "washint": InstrumentRole.ETHIOPIAN_WIND,
    "kebero": InstrumentRole.ETHIOPIAN_DRUM,
}

# Role compatibility for substitution (role -> list of compatible roles)
ROLE_COMPATIBILITY = {
    InstrumentRole.ETHIOPIAN_STRING: [
        InstrumentRole.MELODIC_STRING,
        InstrumentRole.MELODIC_KEYS,
        InstrumentRole.MELODIC_SYNTH,
    ],
    InstrumentRole.ETHIOPIAN_WIND: [
        InstrumentRole.MELODIC_WIND,
        InstrumentRole.MELODIC_SYNTH,
    ],
    InstrumentRole.ETHIOPIAN_DRUM: [
        InstrumentRole.PERCUSSION,
        InstrumentRole.KICK,
    ],
    InstrumentRole.MELODIC_STRING: [
        InstrumentRole.MELODIC_KEYS,
        InstrumentRole.MELODIC_SYNTH,
    ],
    InstrumentRole.MELODIC_WIND: [
        InstrumentRole.MELODIC_SYNTH,
        InstrumentRole.MELODIC_STRING,
    ],
    InstrumentRole.BASS_SUB: [
        InstrumentRole.BASS_MELODIC,  # 808 can use synth bass as fallback
    ],
    InstrumentRole.BASS_MELODIC: [
        InstrumentRole.BASS_SUB,
    ],
}

# Genre affinity scores for instrument sources
GENRE_AFFINITY = {
    "rnb": {"funk": 0.9, "soul": 0.9, "jazz": 0.7, "pop": 0.6},
    "trap_soul": {"rnb": 0.9, "trap": 0.7, "soul": 0.8},
    "g_funk": {"funk": 0.95, "rnb": 0.8, "west_coast": 0.9},
    "trap": {"trap": 1.0, "drill": 0.7, "hip_hop": 0.8},
    "eskista": {"ethiopian": 1.0, "african": 0.8, "world": 0.7, "folk": 0.6},
    "ethiopian_traditional": {"ethiopian": 1.0, "african": 0.8, "world": 0.7},
    "lofi": {"jazz": 0.7, "soul": 0.6, "chill": 0.8},
    "boom_bap": {"hip_hop": 0.9, "jazz": 0.7, "soul": 0.6},
    "house": {"electronic": 0.9, "dance": 0.8, "disco": 0.7},
    "drill": {"trap": 0.8, "grime": 0.7, "uk": 0.6},
}


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class SonicFingerprint:
    """Spectral characteristics for similarity matching."""
    brightness: float = 0.5      # 0=dark, 1=bright
    warmth: float = 0.5          # Low-frequency presence
    punch: float = 0.5           # Transient sharpness
    decay_ms: float = 200.0      # Average decay time
    pluck_character: float = 0.0 # 0=sustained, 1=plucky
    noise_level: float = 0.0     # Amount of noise
    
    # Advanced (MFCC-based)
    mfcc_mean: List[float] = field(default_factory=list)
    
    def similarity_to(self, other: 'SonicFingerprint') -> float:
        """Compute similarity score (0-1)."""
        if not HAS_NUMPY:
            # Simple fallback without numpy
            diffs = [
                abs(self.brightness - other.brightness),
                abs(self.warmth - other.warmth),
                abs(self.punch - other.punch),
                abs(self.pluck_character - other.pluck_character),
            ]
            return 1.0 - (sum(diffs) / len(diffs))
        
        weights = {
            'brightness': 1.0,
            'warmth': 1.0,
            'punch': 1.2,
            'pluck_character': 0.8,
        }
        
        weighted_diff = 0.0
        total_weight = sum(weights.values())
        
        for attr, weight in weights.items():
            v1 = getattr(self, attr)
            v2 = getattr(other, attr)
            weighted_diff += abs(v1 - v2) * weight
        
        return 1.0 - (weighted_diff / total_weight)
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SonicFingerprint':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ExpansionInstrument:
    """An instrument within an expansion pack."""
    id: str                              # Unique identifier
    name: str                            # Display name
    path: str                            # Path to WAV/XPM file
    expansion_id: str                    # Parent expansion ID
    
    category: str = ""                   # drums, bass, keys, etc.
    subcategory: str = ""                # kick, snare, piano, etc.
    role: Optional[InstrumentRole] = None
    
    tags: List[str] = field(default_factory=list)
    
    # For multisampled instruments (XPM)
    is_program: bool = False             # True if XPM with multiple samples
    sample_paths: List[str] = field(default_factory=list)
    
    # Sonic profile for similarity matching
    fingerprint: Optional[SonicFingerprint] = None
    
    # MPC-specific
    midi_note: int = 60
    velocity_layers: int = 1
    
    def matches_name(self, query: str) -> bool:
        """Check if this instrument matches a name query."""
        query_lower = query.lower()
        return (
            query_lower in self.id.lower() or
            query_lower in self.name.lower() or
            query_lower in self.subcategory.lower() or
            any(query_lower in tag.lower() for tag in self.tags)
        )


@dataclass
class ExpansionPack:
    """An expansion pack containing instruments."""
    id: str                              # Unique identifier (folder name)
    name: str                            # Display name
    path: str                            # Absolute path
    version: str = "1.0"
    author: str = ""
    description: str = ""
    
    # Genre targeting
    target_genres: List[str] = field(default_factory=list)
    priority: int = 100                  # Higher = preferred
    
    # Instruments
    instruments: Dict[str, ExpansionInstrument] = field(default_factory=dict)
    
    # Genre-specific mappings (e.g., krar -> guitar)
    instrument_mappings: Dict[str, List[str]] = field(default_factory=dict)
    
    # Category index
    by_category: Dict[str, List[ExpansionInstrument]] = field(default_factory=dict)
    by_role: Dict[InstrumentRole, List[ExpansionInstrument]] = field(default_factory=dict)
    
    # State
    enabled: bool = True
    manifest_path: Optional[str] = None


@dataclass
class ResolvedInstrument:
    """Result of instrument resolution."""
    path: str                            # Path to audio file
    name: str = ""
    source: str = ""                     # Expansion name or "default"
    
    match_type: MatchType = MatchType.DEFAULT
    confidence: float = 0.5              # 0-1 confidence score
    
    note: str = ""                       # Human-readable explanation
    
    # Original request
    requested: str = ""
    genre: str = ""
    
    # Additional files for multisampled instruments
    sample_paths: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            'path': self.path,
            'name': self.name,
            'source': self.source,
            'match_type': self.match_type.value,
            'confidence': self.confidence,
            'note': self.note,
            'requested': self.requested,
            'genre': self.genre,
        }


# =============================================================================
# EXPANSION LOADER
# =============================================================================

class ExpansionLoader:
    """
    Loads and parses expansion packs from directories.
    
    Supports:
    - Auto-generated manifests from folder structure
    - Custom manifest.json files
    - MPC .xpm program files
    """
    
    def __init__(self, analyzer: 'SimpleAudioAnalyzer' = None):
        self.analyzer = analyzer or SimpleAudioAnalyzer()
    
    def load_expansion(self, path: str) -> Optional[ExpansionPack]:
        """
        Load an expansion from a directory.
        
        Args:
            path: Path to expansion directory
            
        Returns:
            ExpansionPack or None if failed
        """
        path = Path(path)
        if not path.exists():
            print(f"Expansion path not found: {path}")
            return None
        
        # Try to find manifest
        manifest_path = path / "expansion.json"
        if manifest_path.exists():
            return self._load_from_manifest(manifest_path)
        
        # Auto-generate manifest from folder structure
        return self._auto_discover(path)
    
    def _load_from_manifest(self, manifest_path: Path) -> Optional[ExpansionPack]:
        """Load expansion from a manifest file."""
        try:
            with open(manifest_path, 'r') as f:
                data = json.load(f)
            
            expansion = ExpansionPack(
                id=data.get('id', manifest_path.parent.name),
                name=data.get('name', manifest_path.parent.name),
                path=str(manifest_path.parent),
                version=data.get('version', '1.0'),
                author=data.get('author', ''),
                description=data.get('description', ''),
                target_genres=data.get('target_genres', []),
                priority=data.get('priority', 100),
                instrument_mappings=data.get('instrument_mappings', {}),
                manifest_path=str(manifest_path),
            )
            
            # Load instruments defined in manifest
            for inst_id, inst_data in data.get('instruments', {}).items():
                instrument = ExpansionInstrument(
                    id=inst_id,
                    name=inst_data.get('name', inst_id),
                    path=str(manifest_path.parent / inst_data.get('path', '')),
                    expansion_id=expansion.id,
                    category=inst_data.get('category', ''),
                    subcategory=inst_data.get('subcategory', ''),
                    tags=inst_data.get('tags', []),
                )
                
                # Determine role
                instrument.role = self._detect_role(instrument)
                
                expansion.instruments[inst_id] = instrument
                self._index_instrument(expansion, instrument)
            
            # Also scan for additional WAV files
            self._scan_wav_files(expansion, manifest_path.parent)
            
            return expansion
            
        except Exception as e:
            print(f"Error loading manifest {manifest_path}: {e}")
            return None
    
    def _auto_discover(self, path: Path) -> ExpansionPack:
        """Auto-discover instruments from folder structure."""
        expansion = ExpansionPack(
            id=path.name.lower().replace(" ", "_").replace("-", "_"),
            name=path.name,
            path=str(path),
        )
        
        # Scan for WAV and XPM files
        self._scan_wav_files(expansion, path)
        self._scan_xpm_files(expansion, path)
        self._scan_xpj_files(expansion, path)
        
        # Infer target genres from naming
        expansion.target_genres = self._infer_genres(expansion)
        
        return expansion
    
    def _scan_wav_files(self, expansion: ExpansionPack, path: Path):
        """Scan for WAV files and add as instruments."""
        extensions = ['.wav', '.WAV', '.aif', '.aiff']
        
        for ext in extensions:
            for wav_path in path.rglob(f"*{ext}"):
                # Skip preview files
                if "[Previews]" in str(wav_path) or "[Preview]" in str(wav_path):
                    continue
                
                # Create instrument
                inst_id = wav_path.stem.lower().replace(" ", "_")
                
                # Skip if already loaded
                if inst_id in expansion.instruments:
                    continue
                
                instrument = ExpansionInstrument(
                    id=inst_id,
                    name=wav_path.stem,
                    path=str(wav_path),
                    expansion_id=expansion.id,
                )
                
                # Parse category from name/path
                self._parse_instrument_metadata(instrument, wav_path)
                
                # Determine role
                instrument.role = self._detect_role(instrument)
                
                expansion.instruments[inst_id] = instrument
                self._index_instrument(expansion, instrument)
    
    def _scan_xpm_files(self, expansion: ExpansionPack, path: Path):
        """Scan for MPC .xpm program files."""
        for xpm_path in path.rglob("*.xpm"):
            # Skip previews
            if "[Previews]" in str(xpm_path):
                continue
            
            program = self._parse_xpm(xpm_path)
            if program:
                inst_id = xpm_path.stem.lower().replace(" ", "_")
                
                instrument = ExpansionInstrument(
                    id=inst_id,
                    name=program.get('name', xpm_path.stem),
                    path=str(xpm_path),
                    expansion_id=expansion.id,
                    is_program=True,
                    sample_paths=program.get('sample_paths', []),
                )
                
                # Parse category from name
                self._parse_instrument_metadata(instrument, xpm_path)
                
                # Determine role
                instrument.role = self._detect_role(instrument)
                
                expansion.instruments[inst_id] = instrument
                self._index_instrument(expansion, instrument)
    
    def _scan_xpj_files(self, expansion: ExpansionPack, path: Path):
        """Scan for MPC .xpj project files."""
        for xpj_path in path.rglob("*.xpj"):
            # Skip previews
            if "[Previews]" in str(xpj_path):
                continue
            
            inst_id = xpj_path.stem.lower().replace(" ", "_")
            
            # Check if already added
            if inst_id in expansion.instruments:
                continue

            instrument = ExpansionInstrument(
                id=inst_id,
                name=xpj_path.stem,
                path=str(xpj_path),
                expansion_id=expansion.id,
                category="projects",
                subcategory="mpc_project",
                tags=['project', 'mpc', 'kit'],
                is_program=True
            )
            
            # Parse metadata
            self._parse_instrument_metadata(instrument, xpj_path)
            
            expansion.instruments[inst_id] = instrument
            self._index_instrument(expansion, instrument)

    def _parse_xpm(self, xpm_path: Path) -> Optional[Dict]:
        """Parse an MPC .xpm file for sample paths."""
        try:
            tree = ET.parse(xpm_path)
            root = tree.getroot()
            
            program_info = {
                'name': xpm_path.stem,
                'sample_paths': [],
                'type': 'drum' if 'Kit' in xpm_path.name else 'keygroup',
            }
            
            # Get program name
            program = root.find('Program')
            if program is not None:
                name_elem = program.find('ProgramName')
                if name_elem is not None:
                    program_info['name'] = name_elem.text
            
            # Find sample references - they can be in various elements
            # Look for FilePath elements
            for filepath in root.iter('FilePath'):
                if filepath.text:
                    sample_path = filepath.text
                    # Handle [ProjectData] paths
                    if '[ProjectData]' in sample_path:
                        sample_path = sample_path.replace('[ProjectData]/', '')
                        sample_path = sample_path.replace('[ProjectData]\\', '')
                    program_info['sample_paths'].append(sample_path)
            
            return program_info
            
        except Exception as e:
            print(f"Error parsing XPM {xpm_path}: {e}")
            return None
    
    def _parse_instrument_metadata(self, instrument: ExpansionInstrument, path: Path):
        """Parse category and tags from instrument path/name."""
        name = path.stem
        name_lower = name.lower()
        
        # Funk o Rama naming: Inst-Bass-Amphi Bass, RnB-Kit-Adventurous
        # Split by dash
        parts = name.split('-')
        
        if len(parts) >= 2:
            prefix = parts[0].lower()
            type_hint = parts[1].lower() if len(parts) > 1 else ""
            
            # Map prefix to category
            if prefix in ['inst', 'rnb']:
                if type_hint == 'bass':
                    instrument.category = 'bass'
                    instrument.subcategory = 'synth_bass'
                    instrument.tags.extend(['bass', 'synth', 'funky'])
                elif type_hint == 'keys':
                    instrument.category = 'keys'
                    instrument.subcategory = 'piano'
                    instrument.tags.extend(['keys', 'piano'])
                elif type_hint == 'synth':
                    instrument.category = 'synths'
                    instrument.subcategory = 'lead'
                    instrument.tags.extend(['synth', 'lead'])
                elif type_hint == 'pad':
                    instrument.category = 'synths'
                    instrument.subcategory = 'pad'
                    instrument.tags.extend(['pad', 'atmosphere'])
                elif type_hint == 'kit':
                    instrument.category = 'drums'
                    instrument.subcategory = 'kit'
                    instrument.tags.extend(['drums', 'kit'])
                elif type_hint == 'kick':
                    instrument.category = 'drums'
                    instrument.subcategory = 'kick'
                    instrument.tags.extend(['drums', 'kick'])
                elif type_hint == 'snare':
                    instrument.category = 'drums'
                    instrument.subcategory = 'snare'
                    instrument.tags.extend(['drums', 'snare'])
                elif type_hint == 'hat':
                    instrument.category = 'drums'
                    instrument.subcategory = 'hihat'
                    instrument.tags.extend(['drums', 'hihat'])
                elif type_hint == 'clap':
                    instrument.category = 'drums'
                    instrument.subcategory = 'clap'
                    instrument.tags.extend(['drums', 'clap'])
                elif type_hint == 'perc':
                    instrument.category = 'drums'
                    instrument.subcategory = 'percussion'
                    instrument.tags.extend(['drums', 'percussion'])
                elif type_hint == 'guitar':
                    instrument.category = 'strings'
                    instrument.subcategory = 'guitar'
                    instrument.tags.extend(['guitar', 'strings'])
                elif type_hint == 'stab':
                    instrument.category = 'synths'
                    instrument.subcategory = 'stab'
                    instrument.tags.extend(['stab', 'synth'])
                elif type_hint == 'vocal':
                    instrument.category = 'fx'
                    instrument.subcategory = 'vocal'
                    instrument.tags.extend(['vocal', 'chop'])
                elif type_hint == 'fx':
                    instrument.category = 'fx'
                    instrument.subcategory = 'fx'
                    instrument.tags.extend(['fx', 'effect'])
        
        # Fallback to keyword detection
        if not instrument.category:
            for keyword, category in [
                ('kick', 'drums'), ('snare', 'drums'), ('hat', 'drums'),
                ('clap', 'drums'), ('bass', 'bass'), ('808', 'bass'),
                ('piano', 'keys'), ('keys', 'keys'), ('organ', 'keys'),
                ('synth', 'synths'), ('lead', 'synths'), ('pad', 'synths'),
                ('guitar', 'strings'), ('string', 'strings'),
                ('fx', 'fx'), ('riser', 'fx'),
            ]:
                if keyword in name_lower:
                    instrument.category = category
                    instrument.subcategory = keyword
                    instrument.tags.append(keyword)
                    break
        
        # Add expansion-related tags
        if 'funk' in name_lower or 'rnb' in str(path).lower():
            instrument.tags.extend(['funk', 'rnb'])
    
    def _detect_role(self, instrument: ExpansionInstrument) -> Optional[InstrumentRole]:
        """Detect the semantic role of an instrument."""
        # Check subcategory first
        if instrument.subcategory:
            sub_lower = instrument.subcategory.lower()
            for name, role in INSTRUMENT_ROLES.items():
                if name in sub_lower:
                    return role
        
        # Check name
        name_lower = instrument.name.lower()
        for name, role in INSTRUMENT_ROLES.items():
            if name in name_lower:
                return role
        
        # Check tags
        for tag in instrument.tags:
            tag_lower = tag.lower()
            for name, role in INSTRUMENT_ROLES.items():
                if name in tag_lower:
                    return role
        
        return None
    
    def _index_instrument(self, expansion: ExpansionPack, instrument: ExpansionInstrument):
        """Add instrument to category and role indices."""
        # By category
        if instrument.category:
            if instrument.category not in expansion.by_category:
                expansion.by_category[instrument.category] = []
            expansion.by_category[instrument.category].append(instrument)
        
        # By role
        if instrument.role:
            if instrument.role not in expansion.by_role:
                expansion.by_role[instrument.role] = []
            expansion.by_role[instrument.role].append(instrument)
    
    def _infer_genres(self, expansion: ExpansionPack) -> List[str]:
        """Infer target genres from expansion content."""
        genres = set()
        
        name_lower = expansion.name.lower()
        
        # Check name
        if 'funk' in name_lower:
            genres.add('g_funk')
            genres.add('rnb')
        if 'rnb' in name_lower or 'r&b' in name_lower:
            genres.add('rnb')
            genres.add('trap_soul')
        if 'trap' in name_lower:
            genres.add('trap')
        if 'lofi' in name_lower or 'lo-fi' in name_lower:
            genres.add('lofi')
        if 'ethiopian' in name_lower:
            genres.add('ethiopian_traditional')
            genres.add('eskista')
        
        # Check instrument names
        for inst in expansion.instruments.values():
            inst_name = inst.name.lower()
            if 'funk' in inst_name:
                genres.add('g_funk')
            if '808' in inst_name:
                genres.add('trap')
                genres.add('drill')
        
        return list(genres) if genres else ['general']


# =============================================================================
# SIMPLE AUDIO ANALYZER (Fallback without librosa)
# =============================================================================

class SimpleAudioAnalyzer:
    """
    Lightweight audio analyzer for sonic fingerprinting.
    
    Works without librosa using basic numpy operations.
    """
    
    def __init__(self, sample_rate: int = SAMPLE_RATE):
        self.sample_rate = sample_rate
    
    def analyze_file(self, path: str) -> Optional[SonicFingerprint]:
        """Analyze an audio file and return its sonic fingerprint."""
        if not HAS_SOUNDFILE or not HAS_NUMPY:
            return SonicFingerprint()
        
        try:
            audio, sr = sf.read(path)
            
            # Convert stereo to mono
            if len(audio.shape) > 1:
                audio = np.mean(audio, axis=1)
            
            return self.analyze_audio(audio, sr)
            
        except Exception as e:
            print(f"Error analyzing {path}: {e}")
            return SonicFingerprint()
    
    def analyze_audio(self, audio: np.ndarray, sr: int) -> SonicFingerprint:
        """Analyze audio array and return fingerprint."""
        if not HAS_NUMPY:
            return SonicFingerprint()
        
        fp = SonicFingerprint()
        
        # Compute basic spectrum
        n_fft = min(2048, len(audio))
        spectrum = np.abs(np.fft.rfft(audio, n_fft))
        freqs = np.fft.rfftfreq(n_fft, 1/sr)
        
        if len(spectrum) == 0 or np.sum(spectrum) == 0:
            return fp
        
        # Normalize
        spectrum_norm = spectrum / (np.sum(spectrum) + 1e-10)
        
        # Brightness: spectral centroid
        centroid = np.sum(freqs * spectrum_norm)
        fp.brightness = min(1.0, centroid / 8000.0)
        
        # Warmth: energy below 500Hz
        low_mask = freqs < 500
        fp.warmth = np.sum(spectrum_norm[low_mask])
        
        # Punch: from attack time
        envelope = np.abs(audio)
        peak_idx = np.argmax(envelope)
        if peak_idx > 0:
            attack_time_ms = (peak_idx / sr) * 1000
            fp.punch = min(1.0, 50.0 / (attack_time_ms + 1))
        
        # Pluck character: fast decay = plucky
        if len(audio) > 100:
            half_point = len(audio) // 2
            first_half_energy = np.mean(np.abs(audio[:half_point]))
            second_half_energy = np.mean(np.abs(audio[half_point:]))
            if first_half_energy > 0:
                decay_ratio = second_half_energy / first_half_energy
                fp.pluck_character = 1.0 - min(1.0, decay_ratio)
        
        # Decay time estimate
        peak_val = np.max(envelope)
        if peak_val > 0:
            decay_threshold = peak_val * 0.1
            decay_indices = np.where(envelope[peak_idx:] < decay_threshold)[0]
            if len(decay_indices) > 0:
                fp.decay_ms = (decay_indices[0] / sr) * 1000
        
        # Noise level (spectral flatness approximation)
        geometric_mean = np.exp(np.mean(np.log(spectrum + 1e-10)))
        arithmetic_mean = np.mean(spectrum)
        fp.noise_level = geometric_mean / (arithmetic_mean + 1e-10)
        
        return fp


# =============================================================================
# INTELLIGENT MATCHER
# =============================================================================

class IntelligentMatcher:
    """
    Multi-tier instrument resolution with intelligent fallback.
    
    Resolution order:
    1. EXACT: Direct name match in expansions
    2. MAPPED: Genre-specific mapping (krar -> guitar)
    3. SEMANTIC: Role-based matching (melodic_string -> any string)
    4. SPECTRAL: Sonic similarity matching
    5. DEFAULT: Fall back to default library
    """
    
    def __init__(
        self,
        expansions: List[ExpansionPack],
        default_instruments_dir: str = None
    ):
        self.expansions = expansions
        self.default_dir = default_instruments_dir
        self.analyzer = SimpleAudioAnalyzer()
        
        # Build global index
        self._build_index()
    
    def _build_index(self):
        """Build searchable indices across all expansions."""
        self.all_instruments: List[ExpansionInstrument] = []
        self.by_name: Dict[str, List[ExpansionInstrument]] = {}
        self.by_role: Dict[InstrumentRole, List[ExpansionInstrument]] = {}
        self.by_category: Dict[str, List[ExpansionInstrument]] = {}
        
        for expansion in self.expansions:
            if not expansion.enabled:
                continue
            
            for instrument in expansion.instruments.values():
                self.all_instruments.append(instrument)
                
                # Index by name (lowercase for matching)
                name_lower = instrument.name.lower()
                if name_lower not in self.by_name:
                    self.by_name[name_lower] = []
                self.by_name[name_lower].append(instrument)
                
                # Index by role
                if instrument.role:
                    if instrument.role not in self.by_role:
                        self.by_role[instrument.role] = []
                    self.by_role[instrument.role].append(instrument)
                
                # Index by category
                if instrument.category:
                    if instrument.category not in self.by_category:
                        self.by_category[instrument.category] = []
                    self.by_category[instrument.category].append(instrument)
    
    def resolve(
        self,
        requested: str,
        genre: str = "",
        prefer_expansion: str = None
    ) -> ResolvedInstrument:
        """
        Resolve an instrument request with intelligent fallback.
        
        Args:
            requested: Instrument name/type requested
            genre: Target genre for affinity scoring
            prefer_expansion: Prefer instruments from this expansion
            
        Returns:
            ResolvedInstrument with path and match info
        """
        requested_lower = requested.lower().strip()
        
        # Tier 1: Exact match
        exact = self._find_exact(requested_lower, prefer_expansion)
        if exact:
            return ResolvedInstrument(
                path=exact.path,
                name=exact.name,
                source=exact.expansion_id,
                match_type=MatchType.EXACT,
                confidence=1.0,
                requested=requested,
                genre=genre,
                sample_paths=exact.sample_paths,
            )
        
        # Tier 2: Genre-specific mapping
        mapped = self._find_mapped(requested_lower, genre, prefer_expansion)
        if mapped:
            return ResolvedInstrument(
                path=mapped.path,
                name=mapped.name,
                source=mapped.expansion_id,
                match_type=MatchType.MAPPED,
                confidence=0.85,
                note=f"Using '{mapped.name}' as substitute for '{requested}'",
                requested=requested,
                genre=genre,
                sample_paths=mapped.sample_paths,
            )
        
        # Tier 3: Semantic role matching
        role = self._get_role(requested_lower)
        if role:
            semantic = self._find_by_role(role, genre, prefer_expansion)
            if semantic:
                return ResolvedInstrument(
                    path=semantic.path,
                    name=semantic.name,
                    source=semantic.expansion_id,
                    match_type=MatchType.SEMANTIC,
                    confidence=0.7,
                    note=f"Role match ({role.value}): {semantic.name}",
                    requested=requested,
                    genre=genre,
                    sample_paths=semantic.sample_paths,
                )
        
        # Tier 4: Spectral similarity (if we have a target profile)
        target_profile = self._get_ideal_profile(requested_lower, genre)
        if target_profile:
            spectral = self._find_spectrally_similar(target_profile, genre)
            if spectral:
                return ResolvedInstrument(
                    path=spectral[0].path,
                    name=spectral[0].name,
                    source=spectral[0].expansion_id,
                    match_type=MatchType.SPECTRAL,
                    confidence=spectral[1],
                    note=f"Sonic similarity: {spectral[1]:.0%}",
                    requested=requested,
                    genre=genre,
                    sample_paths=spectral[0].sample_paths,
                )
        
        # Tier 5: Default fallback - return empty with guidance
        return ResolvedInstrument(
            path="",
            name="",
            source="none",
            match_type=MatchType.DEFAULT,
            confidence=0.0,
            note=f"No match found for '{requested}'. Consider importing an expansion with this instrument.",
            requested=requested,
            genre=genre,
        )
    
    def _find_exact(
        self,
        name: str,
        prefer_expansion: str = None
    ) -> Optional[ExpansionInstrument]:
        """Find exact name match."""
        # Direct lookup
        if name in self.by_name:
            matches = self.by_name[name]
            if prefer_expansion:
                for m in matches:
                    if m.expansion_id == prefer_expansion:
                        return m
            return matches[0]
        
        # Partial match
        for inst_name, instruments in self.by_name.items():
            if name in inst_name or inst_name in name:
                if prefer_expansion:
                    for inst in instruments:
                        if inst.expansion_id == prefer_expansion:
                            return inst
                return instruments[0]
        
        return None
    
    def _find_mapped(
        self,
        requested: str,
        genre: str,
        prefer_expansion: str = None
    ) -> Optional[ExpansionInstrument]:
        """Find via genre-specific mappings."""
        for expansion in self.expansions:
            if not expansion.enabled:
                continue
            
            if prefer_expansion and expansion.id != prefer_expansion:
                continue
            
            if requested in expansion.instrument_mappings:
                alternatives = expansion.instrument_mappings[requested]
                for alt in alternatives:
                    alt_lower = alt.lower()
                    if alt_lower in self.by_name:
                        return self.by_name[alt_lower][0]
        
        return None
    
    def _find_by_role(
        self,
        role: InstrumentRole,
        genre: str,
        prefer_expansion: str = None
    ) -> Optional[ExpansionInstrument]:
        """Find by semantic role with genre affinity scoring."""
        # Get direct role matches
        candidates = list(self.by_role.get(role, []))
        
        # Also get compatible role matches
        if role in ROLE_COMPATIBILITY:
            for compat_role in ROLE_COMPATIBILITY[role]:
                candidates.extend(self.by_role.get(compat_role, []))
        
        if not candidates:
            return None
        
        # Score by genre affinity
        scored = []
        for inst in candidates:
            score = self._compute_genre_affinity(inst, genre)
            if prefer_expansion and inst.expansion_id == prefer_expansion:
                score += 0.5  # Boost preferred expansion
            scored.append((score, inst))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]
    
    def _find_spectrally_similar(
        self,
        target: SonicFingerprint,
        genre: str
    ) -> Optional[Tuple[ExpansionInstrument, float]]:
        """Find instruments with similar sonic characteristics."""
        scored = []
        
        for inst in self.all_instruments:
            if inst.fingerprint:
                similarity = target.similarity_to(inst.fingerprint)
                # Apply genre affinity boost
                affinity = self._compute_genre_affinity(inst, genre)
                combined = similarity * 0.7 + affinity * 0.3
                scored.append((combined, inst))
        
        if not scored:
            return None
        
        scored.sort(key=lambda x: x[0], reverse=True)
        return (scored[0][1], scored[0][0])
    
    def _get_role(self, name: str) -> Optional[InstrumentRole]:
        """Get the semantic role for an instrument name."""
        for keyword, role in INSTRUMENT_ROLES.items():
            if keyword in name:
                return role
        return None
    
    def _get_ideal_profile(self, name: str, genre: str) -> Optional[SonicFingerprint]:
        """Get ideal sonic profile for instrument + genre combination."""
        # Define ideal profiles for common instruments
        profiles = {
            # Ethiopian instruments - map to characteristics we want
            'krar': SonicFingerprint(brightness=0.7, warmth=0.5, punch=0.6, pluck_character=0.8),
            'masenqo': SonicFingerprint(brightness=0.5, warmth=0.7, punch=0.3, pluck_character=0.2),
            'washint': SonicFingerprint(brightness=0.6, warmth=0.5, punch=0.2, pluck_character=0.1),
            'kebero': SonicFingerprint(brightness=0.4, warmth=0.8, punch=0.9, pluck_character=0.0),
            
            # Standard instruments
            'kick': SonicFingerprint(brightness=0.3, warmth=0.8, punch=0.9, pluck_character=0.0),
            'snare': SonicFingerprint(brightness=0.6, warmth=0.4, punch=0.85, pluck_character=0.0),
            'hihat': SonicFingerprint(brightness=0.9, warmth=0.1, punch=0.7, pluck_character=0.0),
            '808': SonicFingerprint(brightness=0.2, warmth=0.95, punch=0.6, pluck_character=0.0),
            'piano': SonicFingerprint(brightness=0.5, warmth=0.6, punch=0.5, pluck_character=0.6),
            'guitar': SonicFingerprint(brightness=0.6, warmth=0.5, punch=0.5, pluck_character=0.7),
        }
        
        for keyword, profile in profiles.items():
            if keyword in name:
                return profile
        
        return None
    
    def _compute_genre_affinity(self, inst: ExpansionInstrument, genre: str) -> float:
        """Compute how well an instrument fits a genre."""
        if not genre:
            return 0.5
        
        # Get expansion's target genres
        for expansion in self.expansions:
            if expansion.id == inst.expansion_id:
                if genre in expansion.target_genres:
                    return 1.0
                
                # Check affinity map
                if genre in GENRE_AFFINITY:
                    for target in expansion.target_genres:
                        if target in GENRE_AFFINITY[genre]:
                            return GENRE_AFFINITY[genre][target]
        
        # Check instrument tags
        genre_keywords = {
            'trap': ['trap', '808', 'drill'],
            'g_funk': ['funk', 'rnb', 'soul'],
            'rnb': ['rnb', 'soul', 'funk'],
            'lofi': ['lofi', 'jazz', 'chill'],
            'eskista': ['ethiopian', 'african', 'world'],
        }
        
        if genre in genre_keywords:
            for keyword in genre_keywords[genre]:
                if any(keyword in tag.lower() for tag in inst.tags):
                    return 0.8
        
        return 0.3


# =============================================================================
# EXPANSION MANAGER (Main API)
# =============================================================================

class ExpansionManager:
    """
    Unified API for managing instrument expansions.
    
    Usage:
        manager = ExpansionManager()
        manager.scan_expansions("./expansions")
        
        # Resolve with intelligent fallback
        result = manager.resolve_instrument("krar", genre="eskista")
        print(result.path, result.note)
        
        # List available instruments
        print(manager.list_instruments(category="bass"))
    """
    
    def __init__(
        self,
        expansions_dir: str = None,
        default_instruments_dir: str = None,
        cache_dir: str = None
    ):
        """
        Initialize the ExpansionManager.
        
        Args:
            expansions_dir: Path to expansions directory
            default_instruments_dir: Path to default instruments folder
            cache_dir: Path for caching analysis results
        """
        self.expansions_dir = Path(expansions_dir) if expansions_dir else None
        self.default_dir = Path(default_instruments_dir) if default_instruments_dir else None
        self.cache_dir = Path(cache_dir) if cache_dir else None
        
        self.expansions: Dict[str, ExpansionPack] = {}
        self.loader = ExpansionLoader()
        self.matcher: Optional[IntelligentMatcher] = None
        
        # Auto-scan if directories provided
        if self.expansions_dir:
            self.scan_expansions(str(self.expansions_dir))
    
    def scan_expansions(self, directory: str, max_depth: int = 5) -> int:
        """
        Scan a directory for expansion packs recursively.
        
        This handles nested directory structures like:
        expansions/funk_o_rama/Funk o Rama-1.0.5/Funk o Rama/expansion.json
        
        Args:
            directory: Path to scan
            max_depth: Maximum depth to search for expansion.json files
            
        Returns:
            Number of expansions loaded
        """
        directory = Path(directory)
        if not directory.exists():
            print(f"Expansions directory not found: {directory}")
            return 0
        
        count = 0
        
        # First, look for expansion.json files recursively to find actual expansion directories
        expansion_dirs = set()
        
        def find_expansion_dirs(path: Path, depth: int = 0):
            """Recursively find directories containing expansion.json."""
            if depth > max_depth:
                return
            
            try:
                for item in path.iterdir():
                    if item.is_file() and item.name == "expansion.json":
                        # Found an expansion - use parent directory
                        expansion_dirs.add(item.parent)
                    elif item.is_dir() and not item.name.startswith('.') and not item.name.startswith('['):
                        find_expansion_dirs(item, depth + 1)
            except PermissionError:
                pass
        
        find_expansion_dirs(directory)
        
        # If no expansion.json files found, fall back to scanning immediate subdirectories
        if not expansion_dirs:
            print(f"  No expansion.json files found, scanning subdirectories...")
            for item in directory.iterdir():
                if item.is_dir():
                    expansion = self.loader.load_expansion(str(item))
                    if expansion and expansion.instruments:
                        self.expansions[expansion.id] = expansion
                        count += 1
                        print(f"  [+] Loaded expansion: {expansion.name} ({len(expansion.instruments)} instruments)")
        else:
            # Load each discovered expansion
            for exp_dir in expansion_dirs:
                expansion = self.loader.load_expansion(str(exp_dir))
                if expansion and expansion.instruments:
                    self.expansions[expansion.id] = expansion
                    count += 1
                    print(f"  [+] Loaded expansion: {expansion.name} ({len(expansion.instruments)} instruments)")
        
        # Load persisted enable state
        self._load_expansion_state()
        
        # Rebuild matcher
        self._rebuild_matcher()
        
        return count
    
    def add_expansion(self, path: str) -> bool:
        """
        Add a single expansion pack.
        
        Args:
            path: Path to expansion directory
            
        Returns:
            True if successful
        """
        expansion = self.loader.load_expansion(path)
        if expansion:
            self.expansions[expansion.id] = expansion
            self._rebuild_matcher()
            return True
        return False
    
    def remove_expansion(self, expansion_id: str) -> bool:
        """Remove an expansion pack."""
        if expansion_id in self.expansions:
            del self.expansions[expansion_id]
            self._rebuild_matcher()
            return True
        return False
    
    def enable_expansion(self, expansion_id: str, enabled: bool = True):
        """Enable or disable an expansion and persist the state."""
        if expansion_id in self.expansions:
            self.expansions[expansion_id].enabled = enabled
            self._rebuild_matcher()
            # Persist enable state to disk
            self._save_expansion_state()
    
    def _save_expansion_state(self):
        """Save expansion enable states to a JSON config file."""
        try:
            state = {
                exp_id: {"enabled": exp.enabled}
                for exp_id, exp in self.expansions.items()
            }
            config_path = Path(self.cache_dir) / "expansion_state.json" if self.cache_dir else None
            if not config_path:
                # Try to save next to first expansion or in user home
                for exp in self.expansions.values():
                    if exp.path:
                        config_path = Path(exp.path).parent / "expansion_state.json"
                        break
            if config_path:
                config_path.parent.mkdir(parents=True, exist_ok=True)
                with open(config_path, 'w') as f:
                    json.dump(state, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save expansion state: {e}")
    
    def _load_expansion_state(self):
        """Load expansion enable states from config file."""
        try:
            config_path = Path(self.cache_dir) / "expansion_state.json" if self.cache_dir else None
            if not config_path:
                for exp in self.expansions.values():
                    if exp.path:
                        config_path = Path(exp.path).parent / "expansion_state.json"
                        break
            if config_path and config_path.exists():
                with open(config_path, 'r') as f:
                    state = json.load(f)
                for exp_id, exp_state in state.items():
                    if exp_id in self.expansions:
                        self.expansions[exp_id].enabled = exp_state.get("enabled", True)
                self._rebuild_matcher()
        except Exception as e:
            print(f"Warning: Could not load expansion state: {e}")
    
    def resolve_instrument(
        self,
        requested: str,
        genre: str = "",
        prefer_expansion: str = None
    ) -> ResolvedInstrument:
        """
        Resolve an instrument request with intelligent fallback.
        
        Args:
            requested: Instrument name/type
            genre: Target genre for affinity scoring
            prefer_expansion: Prefer this expansion
            
        Returns:
            ResolvedInstrument with path and match info
        """
        if not self.matcher:
            return ResolvedInstrument(
                path="",
                source="none",
                match_type=MatchType.DEFAULT,
                confidence=0.0,
                note="No expansions loaded",
                requested=requested,
                genre=genre,
            )
        
        return self.matcher.resolve(requested, genre, prefer_expansion)
    
    def resolve_instrument_set(
        self,
        instruments: List[str],
        genre: str = ""
    ) -> Dict[str, ResolvedInstrument]:
        """
        Resolve multiple instruments at once.
        
        Args:
            instruments: List of instrument names
            genre: Target genre
            
        Returns:
            Dict mapping instrument name to ResolvedInstrument
        """
        return {
            inst: self.resolve_instrument(inst, genre)
            for inst in instruments
        }
    
    def list_expansions(self) -> List[Dict]:
        """List all loaded expansions."""
        return [
            {
                'id': exp.id,
                'name': exp.name,
                'path': exp.path,
                'instruments_count': len(exp.instruments),
                'target_genres': exp.target_genres,
                'enabled': exp.enabled,
            }
            for exp in self.expansions.values()
        ]
    
    def list_instruments(
        self,
        expansion_id: str = None,
        category: str = None,
        role: InstrumentRole = None
    ) -> List[Dict]:
        """
        List available instruments.
        
        Args:
            expansion_id: Filter by expansion
            category: Filter by category
            role: Filter by role
            
        Returns:
            List of instrument info dicts
        """
        results = []
        
        for exp in self.expansions.values():
            if expansion_id and exp.id != expansion_id:
                continue
            
            for inst in exp.instruments.values():
                if category and inst.category != category:
                    continue
                if role and inst.role != role:
                    continue
                
                results.append({
                    'id': inst.id,
                    'name': inst.name,
                    'path': inst.path,
                    'expansion': exp.name,
                    'category': inst.category,
                    'subcategory': inst.subcategory,
                    'role': inst.role.value if inst.role else None,
                    'tags': inst.tags,
                })
        
        return results
    
    def get_categories(self) -> Dict[str, int]:
        """Get available categories with counts."""
        categories = {}
        for exp in self.expansions.values():
            for category, instruments in exp.by_category.items():
                categories[category] = categories.get(category, 0) + len(instruments)
        return categories
    
    def generate_manifest(self, expansion_id: str) -> Optional[str]:
        """
        Generate a manifest.json for an expansion.
        
        Useful for user customization.
        """
        if expansion_id not in self.expansions:
            return None
        
        exp = self.expansions[expansion_id]
        
        manifest = {
            'id': exp.id,
            'name': exp.name,
            'version': '1.0',
            'author': '',
            'description': f'Auto-generated manifest for {exp.name}',
            'target_genres': exp.target_genres,
            'priority': exp.priority,
            'instrument_mappings': exp.instrument_mappings,
            'instruments': {
                inst.id: {
                    'name': inst.name,
                    'path': os.path.relpath(inst.path, exp.path),
                    'category': inst.category,
                    'subcategory': inst.subcategory,
                    'tags': inst.tags,
                }
                for inst in exp.instruments.values()
            }
        }
        
        # Save to expansion directory
        manifest_path = Path(exp.path) / 'expansion.json'
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        return str(manifest_path)
    
    def _rebuild_matcher(self):
        """Rebuild the intelligent matcher with current expansions."""
        enabled = [exp for exp in self.expansions.values() if exp.enabled]
        if enabled:
            self.matcher = IntelligentMatcher(
                enabled,
                str(self.default_dir) if self.default_dir else None
            )
        else:
            self.matcher = None
    
    def to_json(self) -> str:
        """Export expansion info as JSON."""
        return json.dumps({
            'expansions': self.list_expansions(),
            'categories': self.get_categories(),
        }, indent=2)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_expansion_manager(
    project_root: str = None,
    auto_scan: bool = True
) -> ExpansionManager:
    """
    Create and configure an ExpansionManager.
    
    Args:
        project_root: Project root directory
        auto_scan: Automatically scan for expansions
        
    Returns:
        Configured ExpansionManager
    """
    if project_root is None:
        project_root = Path(__file__).parent.parent
    else:
        project_root = Path(project_root)
    
    # Look for expansions in common locations
    expansions_dirs = [
        project_root / "expansions",
        project_root.parent / "expansions",
        Path.home() / ".aitk" / "expansions",
        Path.home() / "Documents" / "Expansions",
        Path.home() / "Documents" / "MPC Expansions",
    ]
    
    # On Windows, also check common MPC/Akai install locations
    import platform
    if platform.system() == "Windows":
        expansions_dirs.extend([
            Path.home() / "Documents" / "Akai" / "Expansions",
            Path("C:/Users/Public/Documents/Akai/Expansions"),
        ])
    
    default_instruments = project_root / "instruments"
    
    manager = ExpansionManager(
        default_instruments_dir=str(default_instruments) if default_instruments.exists() else None
    )
    
    if auto_scan:
        for exp_dir in expansions_dirs:
            if exp_dir.exists():
                print(f"Scanning expansions in: {exp_dir}")
                manager.scan_expansions(str(exp_dir))
    
    return manager


def resolve_genre_instruments(
    genre: str,
    required_instruments: List[str],
    manager: ExpansionManager
) -> Dict[str, ResolvedInstrument]:
    """
    Resolve all required instruments for a genre.
    
    Args:
        genre: Target genre
        required_instruments: List of required instrument types
        manager: ExpansionManager instance
        
    Returns:
        Dict mapping instrument to resolution result
    """
    return manager.resolve_instrument_set(required_instruments, genre)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'ExpansionManager',
    'ExpansionPack',
    'ExpansionInstrument',
    'ResolvedInstrument',
    'MatchType',
    'InstrumentRole',
    'SonicFingerprint',
    'create_expansion_manager',
    'resolve_genre_instruments',
]
