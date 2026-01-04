"""
Unified Instrument Index - Single Source of Truth for Instrument Selection

This module unifies the instrument fingerprint concepts from:
- instrument_manager.py (SonicProfile, InstrumentAnalyzer)
- expansion_manager.py (SonicFingerprint, ExpansionInstrument)

Per likuTasks.md Milestone C:
- "Make the AI choose instruments like a producer: expansion instruments first,
   falling back to built-ins only when no match exists"
- Single shared fingerprint type referenced by both systems
- Unified query API with expansion-first resolution

Key Features:
1. UnifiedFingerprint - Shared spectral/sonic representation
2. InstrumentEntry - Unified instrument metadata
3. InstrumentIndex - Fast lookup across all sources
4. Resolution Policy - Expansion-first with fallback

Usage:
    from multimodal_gen.instrument_index import InstrumentIndex, create_instrument_index
    
    # Create unified index from multiple sources
    index = create_instrument_index(
        stock_path="./instruments",
        expansions_path="./expansions"
    )
    
    # Query with expansion-first policy
    result = index.resolve("rhodes", genre="trap_soul", mood="warm")
    print(result.path, result.source, result.confidence)
    
    # Get all instruments for a role
    keys = index.query_by_role("melodic_keys", genre="g_funk")
"""

from __future__ import annotations
import json
import hashlib
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Set, Any, Union
from enum import Enum
import numpy as np

logger = logging.getLogger(__name__)

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
FINGERPRINT_VERSION = "2.0"  # Increment when fingerprint format changes


class InstrumentSource(Enum):
    """Source of an instrument."""
    STOCK = "stock"           # Built-in /instruments directory
    EXPANSION = "expansion"   # Expansion pack
    PLUGIN = "plugin"         # VST/AU plugin (future)
    USER = "user"             # User-added instruments


class InstrumentRole(Enum):
    """Semantic roles instruments can fulfill (unified)."""
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
    ETHIOPIAN_STRING = "ethiopian_string"
    ETHIOPIAN_WIND = "ethiopian_wind"
    ETHIOPIAN_DRUM = "ethiopian_drum"
    
    # Unknown
    UNKNOWN = "unknown"


class MatchType(Enum):
    """How an instrument was resolved."""
    EXACT = "exact"           # Direct name match
    MAPPED = "mapped"         # Genre-specific mapping
    SEMANTIC = "semantic"     # Role-based matching
    SPECTRAL = "spectral"     # Sonic similarity
    TAG = "tag"               # Tag-based matching
    DEFAULT = "default"       # Fallback


# Role mapping from instrument names
INSTRUMENT_TO_ROLE: Dict[str, InstrumentRole] = {
    # Drums
    "kick": InstrumentRole.KICK,
    "snare": InstrumentRole.SNARE,
    "hihat": InstrumentRole.HIHAT,
    "clap": InstrumentRole.CLAP,
    "perc": InstrumentRole.PERCUSSION,
    "percussion": InstrumentRole.PERCUSSION,
    "cymbal": InstrumentRole.CYMBAL,
    "crash": InstrumentRole.CYMBAL,
    "rim": InstrumentRole.PERCUSSION,
    "tom": InstrumentRole.PERCUSSION,
    
    # Bass
    "808": InstrumentRole.BASS_SUB,
    "sub": InstrumentRole.BASS_SUB,
    "bass": InstrumentRole.BASS_MELODIC,
    
    # Keys
    "piano": InstrumentRole.MELODIC_KEYS,
    "keys": InstrumentRole.MELODIC_KEYS,
    "rhodes": InstrumentRole.MELODIC_KEYS,
    "organ": InstrumentRole.MELODIC_KEYS,
    
    # Strings
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
    
    # Textures
    "pad": InstrumentRole.PAD,
    "fx": InstrumentRole.FX,
    
    # Ethiopian
    "krar": InstrumentRole.ETHIOPIAN_STRING,
    "masenqo": InstrumentRole.ETHIOPIAN_STRING,
    "begena": InstrumentRole.ETHIOPIAN_STRING,
    "washint": InstrumentRole.ETHIOPIAN_WIND,
    "kebero": InstrumentRole.ETHIOPIAN_DRUM,
}

# Role compatibility for substitution
ROLE_COMPATIBILITY: Dict[InstrumentRole, List[InstrumentRole]] = {
    InstrumentRole.ETHIOPIAN_STRING: [
        InstrumentRole.MELODIC_STRING,
        InstrumentRole.MELODIC_KEYS,
    ],
    InstrumentRole.ETHIOPIAN_WIND: [
        InstrumentRole.MELODIC_WIND,
        InstrumentRole.MELODIC_SYNTH,
    ],
    InstrumentRole.ETHIOPIAN_DRUM: [
        InstrumentRole.PERCUSSION,
    ],
    InstrumentRole.BASS_SUB: [
        InstrumentRole.BASS_MELODIC,
    ],
    InstrumentRole.BASS_MELODIC: [
        InstrumentRole.BASS_SUB,
    ],
    InstrumentRole.MELODIC_STRING: [
        InstrumentRole.MELODIC_KEYS,
        InstrumentRole.MELODIC_SYNTH,
    ],
    InstrumentRole.MELODIC_WIND: [
        InstrumentRole.MELODIC_SYNTH,
    ],
}


# =============================================================================
# UNIFIED FINGERPRINT (Shared Spectral Representation)
# =============================================================================

@dataclass
class UnifiedFingerprint:
    """
    Unified spectral/sonic fingerprint for similarity matching.
    
    This consolidates SonicProfile and SonicFingerprint into a single
    representation that can be used by both instrument_manager and
    expansion_manager systems.
    """
    # Core spectral characteristics (0.0 - 1.0 normalized)
    brightness: float = 0.5      # Spectral centroid (high = bright)
    warmth: float = 0.5          # Low-frequency energy presence
    punch: float = 0.5           # Transient sharpness (attack)
    richness: float = 0.5        # Harmonic complexity
    pluck_character: float = 0.0 # 0=sustained, 1=plucky
    noise_level: float = 0.0     # Noise vs tonal content
    
    # Temporal characteristics
    duration_sec: float = 0.0
    attack_time_ms: float = 0.0
    decay_time_ms: float = 0.0
    release_time_ms: float = 0.0
    
    # Energy characteristics
    rms_energy: float = 0.0
    peak_db: float = -60.0
    dynamic_range_db: float = 0.0
    
    # Pitch information
    has_pitch: bool = False
    fundamental_hz: float = 0.0
    midi_note: int = 0
    
    # Advanced features (MFCC-based)
    mfcc_mean: List[float] = field(default_factory=list)
    spectral_contrast: List[float] = field(default_factory=list)
    
    # Cache metadata
    file_hash: str = ""
    version: str = FINGERPRINT_VERSION
    
    def similarity_to(self, other: 'UnifiedFingerprint') -> float:
        """
        Compute similarity score (0-1) to another fingerprint.
        
        Uses weighted distance across key characteristics.
        """
        weights = {
            'brightness': 1.0,
            'warmth': 1.0,
            'punch': 1.2,
            'richness': 0.8,
            'pluck_character': 0.8,
            'noise_level': 0.5,
        }
        
        weighted_diff = 0.0
        total_weight = sum(weights.values())
        
        for attr, weight in weights.items():
            v1 = getattr(self, attr)
            v2 = getattr(other, attr)
            weighted_diff += abs(v1 - v2) * weight
        
        # Include MFCC similarity if both have them
        if self.mfcc_mean and other.mfcc_mean and len(self.mfcc_mean) == len(other.mfcc_mean):
            mfcc_diff = sum(abs(a - b) for a, b in zip(self.mfcc_mean, other.mfcc_mean))
            mfcc_sim = max(0, 1 - mfcc_diff / 10)  # Normalize
            weighted_diff -= mfcc_sim * 0.5  # Bonus for MFCC similarity
        
        return max(0.0, min(1.0, 1.0 - (weighted_diff / total_weight)))
    
    def feature_vector(self) -> np.ndarray:
        """Get feature vector for ML-based similarity."""
        return np.array([
            self.brightness,
            self.warmth,
            self.punch,
            self.richness,
            self.pluck_character,
            self.noise_level,
            self.attack_time_ms / 100.0,
            self.decay_time_ms / 500.0,
            self.dynamic_range_db / 40.0,
        ])
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'UnifiedFingerprint':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    @classmethod
    def from_sonic_profile(cls, profile: Any) -> 'UnifiedFingerprint':
        """Convert from instrument_manager.SonicProfile."""
        return cls(
            brightness=getattr(profile, 'brightness', 0.5),
            warmth=getattr(profile, 'warmth', 0.5),
            punch=getattr(profile, 'punch', 0.5),
            richness=getattr(profile, 'richness', 0.5),
            noise_level=getattr(profile, 'noise_level', 0.0),
            duration_sec=getattr(profile, 'duration_sec', 0.0),
            attack_time_ms=getattr(profile, 'attack_time_ms', 0.0),
            decay_time_ms=getattr(profile, 'decay_time_ms', 0.0),
            release_time_ms=getattr(profile, 'release_time_ms', 0.0),
            rms_energy=getattr(profile, 'rms_energy', 0.0),
            peak_db=getattr(profile, 'peak_db', -60.0),
            dynamic_range_db=getattr(profile, 'dynamic_range_db', 0.0),
            has_pitch=getattr(profile, 'has_pitch', False),
            fundamental_hz=getattr(profile, 'fundamental_hz', 0.0),
            midi_note=getattr(profile, 'midi_note', 0),
            mfcc_mean=getattr(profile, 'mfcc_mean', []),
            spectral_contrast=getattr(profile, 'spectral_contrast', []),
            file_hash=getattr(profile, 'file_hash', ''),
        )
    
    @classmethod
    def from_sonic_fingerprint(cls, fp: Any) -> 'UnifiedFingerprint':
        """Convert from expansion_manager.SonicFingerprint."""
        return cls(
            brightness=getattr(fp, 'brightness', 0.5),
            warmth=getattr(fp, 'warmth', 0.5),
            punch=getattr(fp, 'punch', 0.5),
            pluck_character=getattr(fp, 'pluck_character', 0.0),
            noise_level=getattr(fp, 'noise_level', 0.0),
            decay_time_ms=getattr(fp, 'decay_ms', 200.0),
            mfcc_mean=getattr(fp, 'mfcc_mean', []),
        )


# =============================================================================
# UNIFIED INSTRUMENT ENTRY
# =============================================================================

@dataclass
class InstrumentEntry:
    """
    Unified instrument entry that can represent any instrument source.
    
    This replaces both AnalyzedInstrument and ExpansionInstrument with
    a single format for the unified index.
    """
    # Identity
    id: str                              # Unique identifier
    name: str                            # Display name
    path: str                            # Path to audio file
    
    # Source information
    source: InstrumentSource = InstrumentSource.STOCK
    source_name: str = ""                # Expansion name, plugin name, etc.
    source_id: str = ""                  # Expansion ID, plugin ID
    
    # Classification
    role: InstrumentRole = InstrumentRole.UNKNOWN
    category: str = ""                   # drums, bass, keys, etc.
    subcategory: str = ""                # kick, snare, piano, etc.
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    target_genres: List[str] = field(default_factory=list)
    priority: int = 100                  # Higher = preferred
    
    # Sonic characteristics
    fingerprint: Optional[UnifiedFingerprint] = None
    
    # For multisampled instruments
    is_multisampled: bool = False
    sample_paths: List[str] = field(default_factory=list)
    velocity_layers: int = 1
    
    # MIDI info
    midi_note: int = 60
    pitch_range: Tuple[int, int] = (0, 127)
    
    # License/attribution
    license: str = ""
    attribution: str = ""
    
    def matches_query(self, query: str) -> Tuple[bool, float]:
        """
        Check if this instrument matches a query.
        
        Returns:
            Tuple of (matches, confidence)
        """
        query_lower = query.lower().strip()
        confidence = 0.0
        
        # Exact name match
        if query_lower == self.name.lower():
            return (True, 1.0)
        
        # ID match
        if query_lower == self.id.lower():
            return (True, 0.95)
        
        # Subcategory match
        if query_lower == self.subcategory.lower():
            return (True, 0.9)
        
        # Partial name match
        if query_lower in self.name.lower():
            confidence = 0.7
        elif self.name.lower() in query_lower:
            confidence = 0.6
        
        # Tag match
        for tag in self.tags:
            if query_lower == tag.lower():
                confidence = max(confidence, 0.8)
            elif query_lower in tag.lower():
                confidence = max(confidence, 0.5)
        
        return (confidence > 0, confidence)
    
    def matches_role(self, role: InstrumentRole) -> bool:
        """Check if this instrument can fulfill a role."""
        if self.role == role:
            return True
        
        # Check compatibility
        compatible = ROLE_COMPATIBILITY.get(role, [])
        return self.role in compatible
    
    def matches_genre(self, genre: str) -> float:
        """
        Check genre compatibility.
        
        Returns:
            Score 0.0-1.0 indicating genre match
        """
        if not self.target_genres:
            return 0.5  # Neutral if no genre targeting
        
        genre_lower = genre.lower()
        
        for target in self.target_genres:
            if target.lower() == genre_lower:
                return 1.0
            if target.lower() in genre_lower or genre_lower in target.lower():
                return 0.8
        
        return 0.2  # Low match if genres don't align
    
    def to_dict(self) -> Dict:
        result = {
            'id': self.id,
            'name': self.name,
            'path': self.path,
            'source': self.source.value,
            'source_name': self.source_name,
            'source_id': self.source_id,
            'role': self.role.value,
            'category': self.category,
            'subcategory': self.subcategory,
            'tags': self.tags,
            'target_genres': self.target_genres,
            'priority': self.priority,
            'is_multisampled': self.is_multisampled,
            'sample_paths': self.sample_paths,
            'velocity_layers': self.velocity_layers,
            'midi_note': self.midi_note,
            'pitch_range': list(self.pitch_range),
        }
        
        if self.fingerprint:
            result['fingerprint'] = self.fingerprint.to_dict()
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'InstrumentEntry':
        fingerprint = None
        if 'fingerprint' in data:
            fingerprint = UnifiedFingerprint.from_dict(data['fingerprint'])
        
        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            path=data.get('path', ''),
            source=InstrumentSource(data.get('source', 'stock')),
            source_name=data.get('source_name', ''),
            source_id=data.get('source_id', ''),
            role=InstrumentRole(data.get('role', 'unknown')),
            category=data.get('category', ''),
            subcategory=data.get('subcategory', ''),
            tags=data.get('tags', []),
            target_genres=data.get('target_genres', []),
            priority=data.get('priority', 100),
            fingerprint=fingerprint,
            is_multisampled=data.get('is_multisampled', False),
            sample_paths=data.get('sample_paths', []),
            velocity_layers=data.get('velocity_layers', 1),
            midi_note=data.get('midi_note', 60),
            pitch_range=tuple(data.get('pitch_range', [0, 127])),
        )


# =============================================================================
# RESOLUTION RESULT
# =============================================================================

@dataclass
class ResolutionResult:
    """Result of instrument resolution."""
    instrument: InstrumentEntry
    match_type: MatchType
    confidence: float
    
    note: str = ""                       # Human-readable explanation
    fallback_chain: List[str] = field(default_factory=list)  # Resolution path
    
    # Original query
    requested: str = ""
    genre: str = ""
    mood: str = ""
    
    @property
    def path(self) -> str:
        return self.instrument.path
    
    @property
    def name(self) -> str:
        return self.instrument.name
    
    @property
    def source(self) -> str:
        return self.instrument.source_name or self.instrument.source.value
    
    def to_dict(self) -> Dict:
        return {
            'path': self.path,
            'name': self.name,
            'source': self.source,
            'match_type': self.match_type.value,
            'confidence': self.confidence,
            'note': self.note,
            'fallback_chain': self.fallback_chain,
            'requested': self.requested,
            'genre': self.genre,
            'mood': self.mood,
            'instrument': self.instrument.to_dict(),
        }


# =============================================================================
# UNIFIED INSTRUMENT INDEX
# =============================================================================

class InstrumentIndex:
    """
    Unified index for all instrument sources.
    
    Implements the "expansion-first" resolution policy from likuTasks.md:
    1. Try exact match in expansions
    2. Try genre-mapped match in expansions
    3. Try semantic role match in expansions
    4. Try spectral similarity in expansions
    5. Fallback to stock instruments
    
    Usage:
        index = InstrumentIndex()
        index.add_stock_instruments("./instruments")
        index.add_expansion("./expansions/funk_o_rama")
        
        result = index.resolve("rhodes", genre="trap_soul")
    """
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize unified index.
        
        Args:
            cache_dir: Directory for caching fingerprints
        """
        self._instruments: Dict[str, InstrumentEntry] = {}
        self._by_role: Dict[InstrumentRole, List[InstrumentEntry]] = {}
        self._by_source: Dict[InstrumentSource, List[InstrumentEntry]] = {}
        self._by_genre: Dict[str, List[InstrumentEntry]] = {}
        
        self._cache_dir = Path(cache_dir) if cache_dir else None
        self._cache: Dict[str, UnifiedFingerprint] = {}
        
        self._expansion_ids: Set[str] = set()
    
    @property
    def instruments(self) -> Dict[str, InstrumentEntry]:
        """Public access to instruments dictionary."""
        return self._instruments
    
    # =========================================================================
    # Index Building
    # =========================================================================
    
    def add_instrument(self, instrument: InstrumentEntry) -> None:
        """Add a single instrument to the index."""
        self._instruments[instrument.id] = instrument
        
        # Index by role
        if instrument.role not in self._by_role:
            self._by_role[instrument.role] = []
        self._by_role[instrument.role].append(instrument)
        
        # Index by source
        if instrument.source not in self._by_source:
            self._by_source[instrument.source] = []
        self._by_source[instrument.source].append(instrument)
        
        # Index by genre
        for genre in instrument.target_genres:
            genre_lower = genre.lower()
            if genre_lower not in self._by_genre:
                self._by_genre[genre_lower] = []
            self._by_genre[genre_lower].append(instrument)
    
    def add_stock_instruments(self, instruments_path: str, analyze: bool = True) -> int:
        """
        Add instruments from stock /instruments directory.
        
        Args:
            instruments_path: Path to instruments folder
            analyze: Whether to analyze fingerprints
            
        Returns:
            Number of instruments added
        """
        try:
            from .instrument_manager import DIR_TO_CATEGORY
        except ImportError:
            # Fallback for direct script execution
            DIR_TO_CATEGORY = {
                "kicks": "kick", "kick": "kick",
                "snares": "snare", "snare": "snare",
                "hihats": "hihat", "hihat": "hihat",
                "claps": "clap", "clap": "clap",
                "808s": "808", "808": "808",
                "bass": "bass",
                "keys": "keys", "piano": "keys",
                "synths": "synth", "synth": "synth",
                "pads": "pad", "pad": "pad",
                "brass": "brass",
                "strings": "strings",
                "fx": "fx",
            }
        
        path = Path(instruments_path)
        if not path.exists():
            logger.warning(f"Instruments path not found: {instruments_path}")
            return 0
        
        count = 0
        audio_exts = {'.wav', '.mp3', '.ogg', '.flac', '.aif', '.aiff'}
        
        for audio_path in path.rglob('*'):
            if audio_path.suffix.lower() not in audio_exts:
                continue
            
            # Determine category from directory structure
            rel_path = audio_path.relative_to(path)
            category = "unknown"
            subcategory = ""
            
            if len(rel_path.parts) > 1:
                cat_name = rel_path.parts[0].lower()
                for dir_name, cat_enum in DIR_TO_CATEGORY.items():
                    if dir_name in cat_name:
                        category = cat_enum.value
                        break
                
                if len(rel_path.parts) > 2:
                    subcategory = rel_path.parts[1].lower()
            
            # Create instrument entry
            inst_id = f"stock_{hashlib.md5(str(audio_path).encode()).hexdigest()[:8]}"
            
            entry = InstrumentEntry(
                id=inst_id,
                name=audio_path.stem,
                path=str(audio_path),
                source=InstrumentSource.STOCK,
                source_name="stock",
                category=category,
                subcategory=subcategory,
                role=self._infer_role(audio_path.stem, category),
                priority=50,  # Lower than expansions
            )
            
            # Analyze fingerprint if requested
            if analyze and HAS_LIBROSA:
                entry.fingerprint = self._analyze_audio(str(audio_path))
            
            self.add_instrument(entry)
            count += 1
        
        logger.info(f"Added {count} stock instruments from {instruments_path}")
        return count
    
    def add_expansion(self, expansion_path: str) -> int:
        """
        Add instruments from an expansion pack.
        
        Args:
            expansion_path: Path to expansion folder
            
        Returns:
            Number of instruments added
        """
        path = Path(expansion_path)
        if not path.exists():
            logger.warning(f"Expansion path not found: {expansion_path}")
            return 0
        
        # Try to load manifest
        manifest_path = path / "manifest.json"
        manifest = {}
        if manifest_path.exists():
            try:
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load manifest: {e}")
        
        expansion_id = manifest.get('id', path.name)
        expansion_name = manifest.get('name', path.name)
        target_genres = manifest.get('target_genres', [])
        priority = manifest.get('priority', 100)
        
        self._expansion_ids.add(expansion_id)
        
        count = 0
        audio_exts = {'.wav', '.mp3', '.ogg', '.flac', '.aif', '.aiff'}
        
        # Scan for audio files
        samples_path = path / "Samples"
        scan_path = samples_path if samples_path.exists() else path
        
        for audio_path in scan_path.rglob('*'):
            if audio_path.suffix.lower() not in audio_exts:
                continue
            
            # Parse instrument info from path/name
            rel_path = audio_path.relative_to(scan_path)
            category, subcategory = self._parse_expansion_path(rel_path)
            
            inst_id = f"{expansion_id}_{hashlib.md5(str(audio_path).encode()).hexdigest()[:8]}"
            
            entry = InstrumentEntry(
                id=inst_id,
                name=audio_path.stem,
                path=str(audio_path),
                source=InstrumentSource.EXPANSION,
                source_name=expansion_name,
                source_id=expansion_id,
                category=category,
                subcategory=subcategory,
                role=self._infer_role(audio_path.stem, category),
                target_genres=target_genres,
                priority=priority,
            )
            
            self.add_instrument(entry)
            count += 1
        
        logger.info(f"Added {count} instruments from expansion '{expansion_name}'")
        return count
    
    def add_from_expansion_manager(self, expansion_manager: Any) -> int:
        """
        Import instruments from an existing ExpansionManager.
        
        Args:
            expansion_manager: ExpansionManager instance
            
        Returns:
            Number of instruments added
        """
        count = 0
        
        # ExpansionManager uses .expansions dict
        packs = getattr(expansion_manager, 'expansions', {})
        if not packs:
            packs = getattr(expansion_manager, '_packs', {})
        
        for pack in packs.values():
            self._expansion_ids.add(pack.id)
            
            for inst in pack.instruments.values():
                # Convert ExpansionInstrument to InstrumentEntry
                fingerprint = None
                if inst.fingerprint:
                    fingerprint = UnifiedFingerprint.from_sonic_fingerprint(inst.fingerprint)
                
                entry = InstrumentEntry(
                    id=f"{pack.id}_{inst.id}",
                    name=inst.name,
                    path=inst.path,
                    source=InstrumentSource.EXPANSION,
                    source_name=pack.name,
                    source_id=pack.id,
                    role=inst.role if inst.role else InstrumentRole.UNKNOWN,
                    category=inst.category,
                    subcategory=inst.subcategory,
                    tags=inst.tags,
                    target_genres=pack.target_genres,
                    priority=pack.priority,
                    fingerprint=fingerprint,
                    is_multisampled=inst.is_program,
                    sample_paths=inst.sample_paths,
                    midi_note=inst.midi_note,
                    velocity_layers=inst.velocity_layers,
                )
                
                self.add_instrument(entry)
                count += 1
        
        logger.info(f"Imported {count} instruments from ExpansionManager")
        return count
    
    def add_from_instrument_library(self, library: Any) -> int:
        """
        Import instruments from an existing InstrumentLibrary.
        
        Args:
            library: InstrumentLibrary instance
            
        Returns:
            Number of instruments added
        """
        count = 0
        
        for inst in library.instruments.values():
            # Convert AnalyzedInstrument to InstrumentEntry
            fingerprint = None
            if inst.profile:
                fingerprint = UnifiedFingerprint.from_sonic_profile(inst.profile)
            
            entry = InstrumentEntry(
                id=f"lib_{hashlib.md5(inst.path.encode()).hexdigest()[:8]}",
                name=inst.name,
                path=inst.path,
                source=InstrumentSource.STOCK,
                source_name=getattr(inst, 'source', 'library'),
                category=inst.category.value if hasattr(inst.category, 'value') else str(inst.category),
                role=self._category_to_role(inst.category),
                fingerprint=fingerprint,
                priority=50,
            )
            
            self.add_instrument(entry)
            count += 1
        
        logger.info(f"Imported {count} instruments from InstrumentLibrary")
        return count
    
    # =========================================================================
    # Resolution (Expansion-First Policy)
    # =========================================================================
    
    def resolve(
        self,
        name: str,
        genre: str = "",
        mood: str = "",
        role: Optional[InstrumentRole] = None,
        prefer_expansion: bool = True,
    ) -> Optional[ResolutionResult]:
        """
        Resolve an instrument with expansion-first policy.
        
        Resolution order:
        1. Exact name match in expansions (if prefer_expansion)
        2. Genre-specific match in expansions
        3. Semantic role match in expansions
        4. Spectral similarity in expansions
        5. Any match in stock instruments
        
        Args:
            name: Instrument name to resolve
            genre: Target genre for context
            mood: Target mood for context
            role: Optional role to match
            prefer_expansion: If True, prefer expansion instruments
            
        Returns:
            ResolutionResult or None if not found
        """
        fallback_chain = []
        
        # Infer role from name if not provided
        if not role:
            role = INSTRUMENT_TO_ROLE.get(name.lower())
        
        # 1. Exact match in expansions
        if prefer_expansion:
            result = self._try_exact_match(name, InstrumentSource.EXPANSION)
            if result:
                result.requested = name
                result.genre = genre
                result.mood = mood
                return result
            fallback_chain.append("exact_expansion")
        
        # 2. Genre-specific match
        if genre:
            result = self._try_genre_match(name, genre, InstrumentSource.EXPANSION)
            if result:
                result.requested = name
                result.genre = genre
                result.fallback_chain = fallback_chain.copy()
                return result
            fallback_chain.append("genre_expansion")
        
        # 3. Semantic role match
        if role:
            result = self._try_role_match(role, genre, InstrumentSource.EXPANSION)
            if result:
                result.requested = name
                result.genre = genre
                result.fallback_chain = fallback_chain.copy()
                return result
            fallback_chain.append("role_expansion")
        
        # 4. Spectral similarity (if we have a reference fingerprint)
        # TODO: Implement spectral matching when descriptors are parsed
        
        # 5. Fallback to stock
        result = self._try_exact_match(name, InstrumentSource.STOCK)
        if result:
            result.requested = name
            result.genre = genre
            result.fallback_chain = fallback_chain.copy()
            result.note = "Fell back to stock instrument"
            return result
        fallback_chain.append("exact_stock")
        
        # 6. Role match in stock
        if role:
            result = self._try_role_match(role, genre, InstrumentSource.STOCK)
            if result:
                result.requested = name
                result.genre = genre
                result.fallback_chain = fallback_chain.copy()
                return result
        
        # 7. No match found
        logger.warning(f"No instrument found for '{name}' (genre={genre}, role={role})")
        return None
    
    def query_by_role(
        self,
        role: Union[str, InstrumentRole],
        genre: str = "",
        source: Optional[InstrumentSource] = None,
        limit: int = 10,
    ) -> List[InstrumentEntry]:
        """
        Get all instruments that can fulfill a role.
        
        Args:
            role: Role to query
            genre: Optional genre for ranking
            source: Optional source filter
            limit: Maximum results
            
        Returns:
            List of matching instruments, sorted by relevance
        """
        if isinstance(role, str):
            try:
                role = InstrumentRole(role)
            except ValueError:
                role = INSTRUMENT_TO_ROLE.get(role.lower(), InstrumentRole.UNKNOWN)
        
        candidates = self._by_role.get(role, []).copy()
        
        # Include compatible roles
        for compat_role in ROLE_COMPATIBILITY.get(role, []):
            candidates.extend(self._by_role.get(compat_role, []))
        
        # Filter by source
        if source:
            candidates = [c for c in candidates if c.source == source]
        
        # Score and sort
        scored = []
        for inst in candidates:
            score = inst.priority / 100.0
            
            if genre:
                score += inst.matches_genre(genre) * 0.5
            
            # Prefer expansions
            if inst.source == InstrumentSource.EXPANSION:
                score += 0.3
            
            scored.append((inst, score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return [inst for inst, _ in scored[:limit]]
    
    def query_by_tags(
        self,
        tags: List[str],
        genre: str = "",
        limit: int = 10,
    ) -> List[InstrumentEntry]:
        """
        Find instruments matching tags.
        
        Args:
            tags: Tags to match
            genre: Optional genre for context
            limit: Maximum results
            
        Returns:
            List of matching instruments
        """
        scored = []
        tags_lower = [t.lower() for t in tags]
        
        for inst in self._instruments.values():
            score = 0.0
            inst_tags = [t.lower() for t in inst.tags]
            
            for tag in tags_lower:
                if tag in inst_tags:
                    score += 1.0
                elif any(tag in t for t in inst_tags):
                    score += 0.5
                
                # Also check name
                if tag in inst.name.lower():
                    score += 0.3
            
            if score > 0:
                if genre:
                    score += inst.matches_genre(genre) * 0.5
                scored.append((inst, score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return [inst for inst, _ in scored[:limit]]
    
    # =========================================================================
    # Statistics & Export
    # =========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        return {
            'total_instruments': len(self._instruments),
            'by_source': {
                source.value: len(instruments)
                for source, instruments in self._by_source.items()
            },
            'by_role': {
                role.value: len(instruments)
                for role, instruments in self._by_role.items()
            },
            'expansion_ids': list(self._expansion_ids),
            'genres_indexed': list(self._by_genre.keys()),
        }
    
    def to_json(self, pretty: bool = False) -> str:
        """Export index as JSON."""
        data = {
            'version': FINGERPRINT_VERSION,
            'stats': self.get_stats(),
            'instruments': [inst.to_dict() for inst in self._instruments.values()],
        }
        
        if pretty:
            return json.dumps(data, indent=2)
        return json.dumps(data, separators=(',', ':'))
    
    def save_cache(self, path: str) -> None:
        """Save index cache to file."""
        with open(path, 'w') as f:
            f.write(self.to_json(pretty=True))
    
    @classmethod
    def load_cache(cls, path: str) -> 'InstrumentIndex':
        """Load index from cache file."""
        index = cls()
        
        with open(path, 'r') as f:
            data = json.load(f)
        
        for inst_data in data.get('instruments', []):
            entry = InstrumentEntry.from_dict(inst_data)
            index.add_instrument(entry)
        
        return index
    
    # =========================================================================
    # Private Methods
    # =========================================================================
    
    def _try_exact_match(
        self,
        name: str,
        source: InstrumentSource,
    ) -> Optional[ResolutionResult]:
        """Try exact name match in a source."""
        name_lower = name.lower()
        
        candidates = self._by_source.get(source, [])
        
        for inst in candidates:
            matches, confidence = inst.matches_query(name)
            if matches and confidence >= 0.7:
                return ResolutionResult(
                    instrument=inst,
                    match_type=MatchType.EXACT,
                    confidence=confidence,
                    note=f"Exact match: {inst.name}",
                )
        
        return None
    
    def _try_genre_match(
        self,
        name: str,
        genre: str,
        source: InstrumentSource,
    ) -> Optional[ResolutionResult]:
        """Try genre-specific match."""
        genre_instruments = self._by_genre.get(genre.lower(), [])
        
        if not genre_instruments:
            return None
        
        # Filter by source
        candidates = [i for i in genre_instruments if i.source == source]
        
        for inst in candidates:
            matches, confidence = inst.matches_query(name)
            if matches:
                return ResolutionResult(
                    instrument=inst,
                    match_type=MatchType.MAPPED,
                    confidence=confidence * inst.matches_genre(genre),
                    note=f"Genre-specific match for {genre}: {inst.name}",
                )
        
        return None
    
    def _try_role_match(
        self,
        role: InstrumentRole,
        genre: str,
        source: InstrumentSource,
    ) -> Optional[ResolutionResult]:
        """Try role-based match."""
        candidates = self.query_by_role(role, genre, source, limit=5)
        
        if not candidates:
            return None
        
        best = candidates[0]
        return ResolutionResult(
            instrument=best,
            match_type=MatchType.SEMANTIC,
            confidence=0.7 * best.matches_genre(genre) if genre else 0.7,
            note=f"Role-based match for {role.value}: {best.name}",
        )
    
    def _infer_role(self, name: str, category: str) -> InstrumentRole:
        """Infer instrument role from name and category."""
        name_lower = name.lower()
        
        # Check name first
        for keyword, role in INSTRUMENT_TO_ROLE.items():
            if keyword in name_lower:
                return role
        
        # Then category
        if category:
            return INSTRUMENT_TO_ROLE.get(category.lower(), InstrumentRole.UNKNOWN)
        
        return InstrumentRole.UNKNOWN
    
    def _category_to_role(self, category: Any) -> InstrumentRole:
        """Convert category enum to role."""
        if hasattr(category, 'value'):
            cat_value = category.value
        else:
            cat_value = str(category).lower()
        
        mapping = {
            'kick': InstrumentRole.KICK,
            'snare': InstrumentRole.SNARE,
            'hihat': InstrumentRole.HIHAT,
            'clap': InstrumentRole.CLAP,
            '808': InstrumentRole.BASS_SUB,
            'bass': InstrumentRole.BASS_MELODIC,
            'keys': InstrumentRole.MELODIC_KEYS,
            'synth': InstrumentRole.MELODIC_SYNTH,
            'pad': InstrumentRole.PAD,
            'fx': InstrumentRole.FX,
        }
        
        return mapping.get(cat_value, InstrumentRole.UNKNOWN)
    
    def _parse_expansion_path(self, rel_path: Path) -> Tuple[str, str]:
        """Parse category and subcategory from expansion path."""
        parts = rel_path.parts
        
        category = ""
        subcategory = ""
        
        if len(parts) >= 1:
            category = parts[0].lower()
        if len(parts) >= 2:
            subcategory = parts[1].lower()
        
        return (category, subcategory)
    
    def _analyze_audio(self, path: str) -> Optional[UnifiedFingerprint]:
        """Analyze audio file and return fingerprint."""
        if not HAS_LIBROSA or not HAS_SOUNDFILE:
            return None
        
        # Check cache
        cache_key = hashlib.md5(path.encode()).hexdigest()
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            from .instrument_manager import InstrumentAnalyzer
            
            analyzer = InstrumentAnalyzer()
            profile = analyzer.analyze_file(path)
            
            if profile:
                fingerprint = UnifiedFingerprint.from_sonic_profile(profile)
                self._cache[cache_key] = fingerprint
                return fingerprint
        except Exception as e:
            logger.warning(f"Failed to analyze {path}: {e}")
        
        return None


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_instrument_index(
    stock_path: Optional[str] = None,
    expansions_path: Optional[str] = None,
    expansion_manager: Any = None,
    instrument_library: Any = None,
    cache_dir: Optional[str] = None,
    analyze: bool = True,
) -> InstrumentIndex:
    """
    Create a unified instrument index from multiple sources.
    
    Args:
        stock_path: Path to stock instruments folder
        expansions_path: Path to expansions folder
        expansion_manager: Existing ExpansionManager to import
        instrument_library: Existing InstrumentLibrary to import
        cache_dir: Directory for caching
        analyze: Whether to analyze fingerprints
        
    Returns:
        InstrumentIndex with all instruments loaded
    """
    index = InstrumentIndex(cache_dir=cache_dir)
    
    # Add from existing managers first (they may already have analysis)
    if expansion_manager:
        index.add_from_expansion_manager(expansion_manager)
    
    if instrument_library:
        index.add_from_instrument_library(instrument_library)
    
    # Add from paths
    if stock_path:
        index.add_stock_instruments(stock_path, analyze=analyze)
    
    if expansions_path:
        exp_path = Path(expansions_path)
        if exp_path.exists():
            for item in exp_path.iterdir():
                if item.is_dir():
                    index.add_expansion(str(item))
    
    return index


def resolve_instrument(
    index: InstrumentIndex,
    name: str,
    genre: str = "",
    mood: str = "",
) -> Optional[ResolutionResult]:
    """
    Resolve an instrument with expansion-first policy.
    
    Convenience wrapper for InstrumentIndex.resolve()
    """
    return index.resolve(name, genre=genre, mood=mood)


# =============================================================================
# INSTRUMENT RESOLVER - Intelligent Selection with Sonic Adjectives
# =============================================================================

@dataclass
class ScoredInstrument:
    """An instrument with a relevance score."""
    instrument: InstrumentEntry
    score: float
    match_reasons: List[str] = field(default_factory=list)
    
    def __lt__(self, other: "ScoredInstrument") -> bool:
        return self.score < other.score


class InstrumentResolver:
    """
    Intelligent instrument selection using sonic adjectives.
    
    This class bridges the prompt parser's sonic adjectives with the 
    instrument index to select the most appropriate instruments from
    expansion packs.
    
    Usage:
        resolver = InstrumentResolver(index)
        best_rhodes = resolver.resolve_with_adjectives(
            name="rhodes",
            adjectives=["warm", "vintage", "analog"],
            genre="g_funk"
        )
    
    Scoring factors:
    1. Name/tag match (base score)
    2. Sonic adjective match (bonus per match)
    3. Genre affinity (expansion targeting)
    4. Source priority (expansion > stock)
    """
    
    # Adjective synonyms for flexible matching
    # Maps our canonical adjectives to common tags found in expansion packs
    ADJECTIVE_TAG_MAP: Dict[str, List[str]] = {
        # Temperature
        'warm': ['warm', 'warmth', 'mellow', 'soft', 'cozy', 'smooth'],
        'cold': ['cold', 'icy', 'sterile', 'clinical', 'digital'],
        
        # Age/Character
        'vintage': ['vintage', 'retro', 'classic', '70s', '80s', 'old', 'oldschool'],
        'modern': ['modern', 'contemporary', 'new', 'fresh', 'current'],
        'analog': ['analog', 'analogue', 'tape', 'tube', 'valve', 'hardware'],
        'digital': ['digital', 'crisp', 'clean', 'precise'],
        
        # Texture
        'dusty': ['dusty', 'lofi', 'lo-fi', 'dirty', 'gritty', 'vinyl'],
        'clean': ['clean', 'pristine', 'crystal', 'clear', 'pure'],
        'crunchy': ['crunchy', 'crispy', 'bit', 'crushed', 'distorted'],
        'smooth': ['smooth', 'silky', 'buttery', 'creamy'],
        
        # Weight
        'fat': ['fat', 'thick', 'heavy', 'big', 'massive', 'huge'],
        'thin': ['thin', 'light', 'airy', 'delicate'],
        'deep': ['deep', 'sub', 'low', 'bass', 'rumble'],
        'punchy': ['punchy', 'tight', 'snap', 'attack', 'transient'],
        
        # Brightness
        'bright': ['bright', 'sparkle', 'shimmer', 'glitter', 'air'],
        'dark': ['dark', 'murky', 'shadow', 'dim', 'moody'],
        
        # Space
        'dry': ['dry', 'close', 'intimate', 'direct'],
        'wet': ['wet', 'reverb', 'spacious', 'ambient', 'hall'],
        
        # Character
        'soulful': ['soulful', 'soul', 'emotional', 'expressive', 'gospel'],
        'funky': ['funky', 'funk', 'groove', 'groovy', 'bounce'],
        'jazzy': ['jazzy', 'jazz', 'swing', 'bebop'],
        'organic': ['organic', 'natural', 'acoustic', 'live', 'real'],
        'synthetic': ['synthetic', 'synth', 'electronic', 'digital'],
        
        # Specific
        'plucky': ['plucky', 'pluck', 'staccato', 'short'],
        'sustained': ['sustained', 'pad', 'long', 'held', 'legato'],
        'glassy': ['glassy', 'glass', 'bell', 'crystal', 'chime'],
        'woody': ['woody', 'wood', 'acoustic', 'natural'],
    }
    
    # Genre -> preferred adjectives (implicit matching)
    GENRE_ADJECTIVE_AFFINITY: Dict[str, List[str]] = {
        'g_funk': ['warm', 'analog', 'funky', 'smooth', 'vintage', 'soulful'],
        'trap_soul': ['warm', 'dark', 'deep', 'smooth', 'soulful'],
        'trap': ['dark', 'deep', 'punchy', 'modern', 'synthetic'],
        'lofi': ['dusty', 'warm', 'vintage', 'analog', 'organic'],
        'boom_bap': ['dusty', 'punchy', 'vintage', 'organic', 'funky'],
        'neo_soul': ['warm', 'smooth', 'soulful', 'organic', 'jazzy'],
        'jazz': ['warm', 'organic', 'jazzy', 'smooth', 'vintage'],
        'house': ['punchy', 'deep', 'warm', 'modern'],
        'techno': ['cold', 'dark', 'synthetic', 'punchy', 'modern'],
    }
    
    def __init__(self, index: InstrumentIndex):
        """Initialize with an instrument index."""
        self.index = index
    
    def resolve_with_adjectives(
        self,
        name: str,
        adjectives: List[str],
        genre: str = "",
        role: Optional[InstrumentRole] = None,
        limit: int = 5,
    ) -> List[ScoredInstrument]:
        """
        Resolve instrument with sonic adjective matching.
        
        Args:
            name: Instrument name to search for (rhodes, 808, piano, etc.)
            adjectives: Sonic adjectives from prompt (warm, vintage, etc.)
            genre: Genre context for affinity scoring
            role: Optional role filter (melodic_keys, bass_sub, etc.)
            limit: Maximum results to return
        
        Returns:
            List of ScoredInstrument sorted by relevance (highest first)
        """
        candidates: List[ScoredInstrument] = []
        
        # Get all potential matches
        for inst in self.index.instruments.values():
            score, reasons = self._score_instrument(inst, name, adjectives, genre, role)
            
            if score > 0:
                candidates.append(ScoredInstrument(
                    instrument=inst,
                    score=score,
                    match_reasons=reasons,
                ))
        
        # Sort by score (highest first)
        candidates.sort(reverse=True)
        
        return candidates[:limit]
    
    def get_best_instrument(
        self,
        name: str,
        adjectives: List[str],
        genre: str = "",
        role: Optional[InstrumentRole] = None,
    ) -> Optional[InstrumentEntry]:
        """Get the single best matching instrument."""
        results = self.resolve_with_adjectives(name, adjectives, genre, role, limit=1)
        return results[0].instrument if results else None
    
    def _score_instrument(
        self,
        inst: InstrumentEntry,
        name: str,
        adjectives: List[str],
        genre: str,
        role: Optional[InstrumentRole],
    ) -> Tuple[float, List[str]]:
        """
        Score an instrument for relevance.
        
        Returns:
            Tuple of (score, list of match reasons)
        """
        score = 0.0
        reasons: List[str] = []
        name_lower = name.lower()
        
        # 1. Name match (required - if no name match, score stays 0)
        name_match = False
        if name_lower in inst.name.lower():
            score += 1.0
            name_match = True
            reasons.append(f"name_contains:{name}")
        elif name_lower in inst.id.lower():
            score += 0.8
            name_match = True
            reasons.append(f"id_contains:{name}")
        elif any(name_lower in tag.lower() for tag in inst.tags):
            score += 0.6
            name_match = True
            reasons.append(f"tag_match:{name}")
        
        if not name_match:
            return 0.0, []
        
        # 2. Role match (bonus)
        if role and inst.role == role:
            score += 0.3
            reasons.append(f"role_match:{role.value}")
        
        # 3. Source priority (expansion > stock)
        if inst.source == InstrumentSource.EXPANSION:
            score += 0.2
            reasons.append("expansion_source")
        
        # 4. Sonic adjective matching
        inst_tags_lower = [t.lower() for t in inst.tags]
        inst_name_lower = inst.name.lower()
        
        for adj in adjectives:
            tag_variants = self.ADJECTIVE_TAG_MAP.get(adj, [adj])
            
            for variant in tag_variants:
                variant_lower = variant.lower()
                
                # Check tags
                if any(variant_lower in tag for tag in inst_tags_lower):
                    score += 0.15
                    reasons.append(f"tag_adj:{adj}")
                    break
                
                # Check name
                if variant_lower in inst_name_lower:
                    score += 0.1
                    reasons.append(f"name_adj:{adj}")
                    break
        
        # 5. Genre affinity (implicit adjective bonus)
        if genre:
            genre_adjs = self.GENRE_ADJECTIVE_AFFINITY.get(genre, [])
            for gadj in genre_adjs:
                tag_variants = self.ADJECTIVE_TAG_MAP.get(gadj, [gadj])
                for variant in tag_variants:
                    if any(variant.lower() in tag for tag in inst_tags_lower):
                        score += 0.05
                        reasons.append(f"genre_affinity:{gadj}")
                        break
        
        # 6. Fingerprint quality bonus (has been analyzed)
        if inst.fingerprint:
            score += 0.05
            reasons.append("has_fingerprint")
        
        return score, reasons
    
    def explain_selection(self, scored: ScoredInstrument) -> str:
        """Generate human-readable explanation of why instrument was selected."""
        inst = scored.instrument
        reasons = scored.match_reasons
        
        lines = [
            f"Selected: {inst.name}",
            f"  Source: {inst.source.value}",
            f"  Score: {scored.score:.2f}",
            f"  Reasons:"
        ]
        
        for r in reasons:
            lines.append(f"    - {r}")
        
        return "\n".join(lines)


# =============================================================================
# CLI TESTING
# =============================================================================

if __name__ == "__main__":
    import sys
    
    print("🎸 Unified Instrument Index")
    print("=" * 60)
    
    # Create test index
    index = InstrumentIndex()
    
    # Try to load expansions
    expansions_dir = Path(__file__).parent.parent / "expansions"
    if expansions_dir.exists():
        for item in expansions_dir.iterdir():
            if item.is_dir():
                count = index.add_expansion(str(item))
                print(f"  Loaded expansion: {item.name} ({count} instruments)")
    
    # Try to load stock instruments
    stock_dir = Path(__file__).parent.parent / "instruments"
    if stock_dir.exists():
        count = index.add_stock_instruments(str(stock_dir), analyze=False)
        print(f"  Loaded stock instruments: {count}")
    
    stats = index.get_stats()
    print(f"\n📊 Index Stats:")
    print(f"  Total: {stats['total_instruments']} instruments")
    print(f"  By source: {stats['by_source']}")
    print(f"  Expansions: {stats['expansion_ids']}")
    
    # Test resolution
    print("\n🔍 Resolution Tests:")
    
    test_cases = [
        ("rhodes", "trap_soul"),
        ("808", "trap"),
        ("krar", "eskista"),
        ("piano", "g_funk"),
    ]
    
    for name, genre in test_cases:
        result = index.resolve(name, genre=genre)
        if result:
            print(f"\n  '{name}' (genre={genre}):")
            print(f"    → {result.name} ({result.source})")
            print(f"    → Match: {result.match_type.value}, Confidence: {result.confidence:.2f}")
            if result.note:
                print(f"    → Note: {result.note}")
        else:
            print(f"\n  '{name}' (genre={genre}): NOT FOUND")
    
    print("\n✅ Unified Instrument Index ready!")
