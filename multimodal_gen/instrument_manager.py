"""
Instrument Manager - Intelligent Sample Selection System

This module provides 3 complementary approaches for AI to select and use instruments:

1. **Instrument Analysis (InstrumentAnalyzer)**
   - Analyzes audio characteristics: brightness, punch, warmth, decay, pitch
   - Uses librosa for spectral features (MFCC, spectral centroid, rolloff)
   - Builds a "sonic fingerprint" for each sample

2. **Intelligent Matching (InstrumentMatcher)** 
   - Matches instruments to genres/moods using sonic profiles
   - Genre-specific ideal characteristics (trap = punchy 808s, lofi = warm drums)
   - Similarity scoring based on spectral features

3. **Dynamic Library (InstrumentLibrary)**
   - Auto-discovers instruments from the instruments/ directory
   - Caches analysis results for fast lookups
   - Integrates with AudioRenderer for actual sound generation

Usage:
    from multimodal_gen import InstrumentLibrary, InstrumentMatcher
    
    # Load and analyze instruments
    library = InstrumentLibrary("./instruments")
    library.discover_and_analyze()
    
    # Get best instruments for a genre
    matcher = InstrumentMatcher(library)
    best_kick = matcher.get_best_match("kick", genre="trap", mood="dark")
    
    # Render using selected instruments
    renderer = AudioRenderer(instrument_library=library)
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any, Union, TYPE_CHECKING
from enum import Enum
import numpy as np
import hashlib

# Type hints for InstrumentIntelligence (avoid circular imports)
if TYPE_CHECKING:
    from .instrument_intelligence import InstrumentIntelligence

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

class InstrumentCategory(Enum):
    """Categories of instruments."""
    KICK = "kick"
    SNARE = "snare"
    HIHAT = "hihat"
    CLAP = "clap"
    TOM = "tom"
    PERC = "perc"
    BASS_808 = "808"
    BASS = "bass"
    KEYS = "keys"
    SYNTH = "synth"
    PAD = "pad"
    BRASS = "brass"
    STRINGS = "strings"
    FX = "fx"
    # Ethiopian instruments
    KRAR = "krar"
    MASENQO = "masenqo"
    WASHINT = "washint"
    BEGENA = "begena"
    KEBERO = "kebero"
    UNKNOWN = "unknown"


# Mapping from directory names to categories
DIR_TO_CATEGORY = {
    "kicks": InstrumentCategory.KICK,
    "kick": InstrumentCategory.KICK,
    "snares": InstrumentCategory.SNARE,
    "snare": InstrumentCategory.SNARE,
    "hihats": InstrumentCategory.HIHAT,
    "hihat": InstrumentCategory.HIHAT,
    "hats": InstrumentCategory.HIHAT,
    "claps": InstrumentCategory.CLAP,
    "clap": InstrumentCategory.CLAP,
    "808s": InstrumentCategory.BASS_808,
    "808": InstrumentCategory.BASS_808,
    "toms": InstrumentCategory.TOM,
    "tom": InstrumentCategory.TOM,
    "perc": InstrumentCategory.PERC,
    "percussion": InstrumentCategory.PERC,
    "bass": InstrumentCategory.BASS,
    "keys": InstrumentCategory.KEYS,
    "piano": InstrumentCategory.KEYS,
    "synths": InstrumentCategory.SYNTH,
    "synth": InstrumentCategory.SYNTH,
    "pads": InstrumentCategory.PAD,
    "pad": InstrumentCategory.PAD,
    "brass": InstrumentCategory.BRASS,
    "strings": InstrumentCategory.STRINGS,
    "fx": InstrumentCategory.FX,
    "effects": InstrumentCategory.FX,
    # Ethiopian instruments
    "krar": InstrumentCategory.KRAR,
    "masenqo": InstrumentCategory.MASENQO,
    "washint": InstrumentCategory.WASHINT,
    "begena": InstrumentCategory.BEGENA,
    "kebero": InstrumentCategory.KEBERO,
    "ethiopian": InstrumentCategory.KRAR,  # fallback for ethiopian folder
}

# Filename keywords for category detection (fallback)
KEYWORD_TO_CATEGORY = {
    InstrumentCategory.KICK: ["kick", "kik", "kck", "bd", "bass_drum"],
    InstrumentCategory.SNARE: ["snare", "snr", "sd", "sn"],
    InstrumentCategory.HIHAT: ["hihat", "hh", "hat", "chh", "ohh"],
    InstrumentCategory.CLAP: ["clap", "clp", "cp"],
    InstrumentCategory.BASS_808: ["808", "sub"],
    InstrumentCategory.TOM: ["tom", "tm"],
    InstrumentCategory.PERC: ["perc", "shaker", "tamb", "conga", "bongo", "rim"],
    InstrumentCategory.BASS: ["bass", "bs"],
    InstrumentCategory.KEYS: ["piano", "keys", "rhodes", "wurli", "organ"],
    InstrumentCategory.SYNTH: ["synth", "lead", "pluck"],
    InstrumentCategory.PAD: ["pad", "atmosphere", "ambient"],
    InstrumentCategory.BRASS: ["brass", "trumpet", "horn", "sax"],
    InstrumentCategory.STRINGS: ["string", "violin", "cello", "orchestra"],
    InstrumentCategory.FX: ["fx", "riser", "sweep", "impact", "transition"],
    # Ethiopian instruments
    InstrumentCategory.KRAR: ["krar", "lyre", "ethiopian_lyre"],
    InstrumentCategory.MASENQO: ["masenqo", "masinko", "fiddle_ethiopian"],
    InstrumentCategory.WASHINT: ["washint", "bamboo_flute", "ethiopian_flute"],
    InstrumentCategory.BEGENA: ["begena", "bass_lyre"],
    InstrumentCategory.KEBERO: ["kebero", "ethiopian_drum"],
}


# =============================================================================
# SONIC PROFILE DATA STRUCTURE
# =============================================================================

@dataclass
class SonicProfile:
    """
    Acoustic/spectral characteristics of a sample.
    
    These features allow AI to understand what an instrument "sounds like"
    without needing to actually play it.
    """
    # Core identifiers
    sample_path: str = ""
    sample_name: str = ""
    category: str = "unknown"
    
    # Temporal characteristics
    duration_sec: float = 0.0
    attack_time_ms: float = 0.0    # Time to reach peak
    decay_time_ms: float = 0.0     # Time from peak to sustain
    release_time_ms: float = 0.0   # Time to silence after note off
    
    # Spectral characteristics (0-1 normalized)
    brightness: float = 0.5        # Spectral centroid (high = bright)
    warmth: float = 0.5            # Low-frequency energy
    punch: float = 0.5             # Transient sharpness
    richness: float = 0.5          # Spectral complexity/harmonics
    noise_level: float = 0.0       # Amount of noise vs tonal content
    
    # Pitch information
    has_pitch: bool = False        # Is it tonal?
    fundamental_hz: float = 0.0    # Detected fundamental frequency
    midi_note: int = 0             # Estimated MIDI note
    
    # Energy characteristics
    rms_energy: float = 0.0        # Overall loudness
    peak_db: float = -60.0         # Peak level in dB
    dynamic_range_db: float = 0.0  # Difference between peak and RMS
    
    # Advanced features (for similarity matching)
    mfcc_mean: List[float] = field(default_factory=list)  # First 13 MFCCs
    spectral_contrast: List[float] = field(default_factory=list)
    
    # Metadata
    file_hash: str = ""            # For cache invalidation
    analysis_version: str = "1.0"
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SonicProfile':
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    def similarity_vector(self) -> np.ndarray:
        """Get feature vector for similarity comparison."""
        return np.array([
            self.brightness,
            self.warmth,
            self.punch,
            self.richness,
            self.attack_time_ms / 100.0,  # Normalize to 0-1 range
            self.decay_time_ms / 500.0,
            self.noise_level,
            self.dynamic_range_db / 40.0,
        ])


@dataclass 
class AnalyzedInstrument:
    """An instrument with its loaded audio and analysis."""
    path: str
    name: str
    category: InstrumentCategory
    profile: SonicProfile
    audio: Optional[np.ndarray] = None
    sample_rate: int = SAMPLE_RATE
    
    @property
    def is_loaded(self) -> bool:
        return self.audio is not None


# =============================================================================
# APPROACH 1: INSTRUMENT ANALYZER
# =============================================================================

class InstrumentAnalyzer:
    """
    Analyzes audio samples to extract sonic characteristics.
    
    Uses librosa for spectral analysis to create a "fingerprint"
    that describes how the instrument sounds.
    """
    
    def __init__(self, sample_rate: int = SAMPLE_RATE):
        self.sample_rate = sample_rate
        
    def analyze_file(self, path: str, load_audio: bool = True) -> Optional[SonicProfile]:
        """
        Analyze an audio file and return its sonic profile.
        
        Args:
            path: Path to audio file
            load_audio: Whether to load audio data
            
        Returns:
            SonicProfile with extracted characteristics
        """
        if not HAS_SOUNDFILE:
            print("Warning: soundfile not available for analysis")
            return None
            
        try:
            # Load audio
            audio, sr = sf.read(path)
            
            # Convert stereo to mono
            if len(audio.shape) > 1:
                audio = np.mean(audio, axis=1)
            
            # Resample if needed
            if sr != self.sample_rate and HAS_LIBROSA:
                audio = librosa.resample(audio, orig_sr=sr, target_sr=self.sample_rate)
                sr = self.sample_rate
            
            # Get file hash for cache
            file_hash = self._compute_hash(path)
            
            # Create profile
            profile = SonicProfile(
                sample_path=path,
                sample_name=Path(path).stem,
                file_hash=file_hash,
                duration_sec=len(audio) / sr,
            )
            
            # Extract features
            self._analyze_temporal(audio, sr, profile)
            self._analyze_spectral(audio, sr, profile)
            self._analyze_energy(audio, sr, profile)
            self._analyze_pitch(audio, sr, profile)
            
            if HAS_LIBROSA:
                self._analyze_advanced(audio, sr, profile)
            
            return profile
            
        except Exception as e:
            print(f"Error analyzing {path}: {e}")
            return None
    
    def analyze_audio(self, audio: np.ndarray, sr: int = None) -> SonicProfile:
        """Analyze audio array directly."""
        sr = sr or self.sample_rate
        
        profile = SonicProfile(
            duration_sec=len(audio) / sr,
        )
        
        self._analyze_temporal(audio, sr, profile)
        self._analyze_spectral(audio, sr, profile)
        self._analyze_energy(audio, sr, profile)
        self._analyze_pitch(audio, sr, profile)
        
        if HAS_LIBROSA:
            self._analyze_advanced(audio, sr, profile)
        
        return profile
    
    def _compute_hash(self, path: str) -> str:
        """Compute file hash for cache validation."""
        hasher = hashlib.md5()
        with open(path, 'rb') as f:
            hasher.update(f.read(8192))  # First 8KB
        return hasher.hexdigest()[:16]
    
    def _analyze_temporal(self, audio: np.ndarray, sr: int, profile: SonicProfile):
        """Analyze attack, decay, release times."""
        # Compute envelope using RMS
        frame_length = int(sr * 0.01)  # 10ms frames
        hop_length = frame_length // 2
        
        # Simple envelope from absolute values
        envelope = np.abs(audio)
        
        # Smooth with moving average
        kernel_size = int(sr * 0.005)  # 5ms smoothing
        if kernel_size > 0:
            kernel = np.ones(kernel_size) / kernel_size
            envelope = np.convolve(envelope, kernel, mode='same')
        
        if len(envelope) == 0:
            return
            
        # Find peak
        peak_idx = np.argmax(envelope)
        peak_val = envelope[peak_idx]
        
        if peak_val == 0:
            return
        
        # Attack time: from start to peak
        attack_samples = peak_idx
        profile.attack_time_ms = (attack_samples / sr) * 1000
        
        # Find decay point (where level drops to 37% of peak - 1 time constant)
        decay_threshold = peak_val * 0.37
        post_peak = envelope[peak_idx:]
        
        decay_indices = np.where(post_peak < decay_threshold)[0]
        if len(decay_indices) > 0:
            decay_samples = decay_indices[0]
            profile.decay_time_ms = (decay_samples / sr) * 1000
        else:
            profile.decay_time_ms = (len(post_peak) / sr) * 1000
        
        # Release time: from 37% to 10% of peak
        release_threshold = peak_val * 0.1
        release_indices = np.where(post_peak < release_threshold)[0]
        if len(release_indices) > 0:
            release_samples = release_indices[0] - decay_indices[0] if len(decay_indices) > 0 else release_indices[0]
            profile.release_time_ms = max(0, (release_samples / sr) * 1000)
    
    def _analyze_spectral(self, audio: np.ndarray, sr: int, profile: SonicProfile):
        """Analyze spectral characteristics."""
        # Use simple FFT analysis
        n_fft = min(2048, len(audio))
        
        # Compute spectrum
        spectrum = np.abs(np.fft.rfft(audio, n_fft))
        freqs = np.fft.rfftfreq(n_fft, 1/sr)
        
        if len(spectrum) == 0:
            return
        
        # Normalize spectrum
        spectrum_norm = spectrum / (np.sum(spectrum) + 1e-10)
        
        # Spectral centroid (brightness)
        centroid = np.sum(freqs * spectrum_norm)
        # Normalize to 0-1 (assuming max interesting centroid ~10kHz)
        profile.brightness = min(1.0, centroid / 10000.0)
        
        # Warmth: energy below 500Hz
        low_mask = freqs < 500
        profile.warmth = np.sum(spectrum_norm[low_mask])
        
        # Punch: ratio of attack energy to sustain (transient sharpness)
        # Estimate from attack time and spectral energy
        if profile.attack_time_ms > 0:
            profile.punch = min(1.0, 50.0 / (profile.attack_time_ms + 1))
        
        # Richness: spectral spread/complexity
        spectral_spread = np.sqrt(np.sum(((freqs - centroid) ** 2) * spectrum_norm))
        profile.richness = min(1.0, spectral_spread / 5000.0)
        
        # Noise level: spectral flatness approximation
        geometric_mean = np.exp(np.mean(np.log(spectrum + 1e-10)))
        arithmetic_mean = np.mean(spectrum)
        profile.noise_level = geometric_mean / (arithmetic_mean + 1e-10)
    
    def _analyze_energy(self, audio: np.ndarray, sr: int, profile: SonicProfile):
        """Analyze energy/loudness characteristics."""
        # RMS energy
        profile.rms_energy = np.sqrt(np.mean(audio ** 2))
        
        # Peak level in dB
        peak = np.max(np.abs(audio))
        if peak > 0:
            profile.peak_db = 20 * np.log10(peak)
        
        # Dynamic range
        if profile.rms_energy > 0:
            rms_db = 20 * np.log10(profile.rms_energy + 1e-10)
            profile.dynamic_range_db = profile.peak_db - rms_db
    
    def _analyze_pitch(self, audio: np.ndarray, sr: int, profile: SonicProfile):
        """Analyze pitch/fundamental frequency."""
        if not HAS_LIBROSA:
            # Simple zero-crossing based pitch estimation
            zero_crossings = np.where(np.diff(np.signbit(audio)))[0]
            if len(zero_crossings) > 2:
                avg_period = np.mean(np.diff(zero_crossings)) * 2
                if avg_period > 0:
                    freq = sr / avg_period
                    if 20 < freq < 2000:  # Reasonable pitch range
                        profile.has_pitch = True
                        profile.fundamental_hz = freq
                        profile.midi_note = int(round(69 + 12 * np.log2(freq / 440)))
            return
        
        # Use librosa for better pitch detection
        try:
            # Use piptrack for pitch detection
            pitches, magnitudes = librosa.piptrack(y=audio, sr=sr)
            
            # Get most prominent pitch
            max_mag_idx = magnitudes.argmax(axis=0)
            pitch_track = pitches[max_mag_idx, np.arange(pitches.shape[1])]
            
            # Filter out zeros and get median
            valid_pitches = pitch_track[pitch_track > 0]
            if len(valid_pitches) > 0:
                median_pitch = np.median(valid_pitches)
                if 20 < median_pitch < 4000:
                    profile.has_pitch = True
                    profile.fundamental_hz = median_pitch
                    profile.midi_note = int(round(69 + 12 * np.log2(median_pitch / 440)))
        except Exception:
            pass
    
    def _analyze_advanced(self, audio: np.ndarray, sr: int, profile: SonicProfile):
        """Analyze advanced features using librosa."""
        if not HAS_LIBROSA:
            return
        
        try:
            # MFCCs (timbre fingerprint)
            mfccs = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=13)
            profile.mfcc_mean = np.mean(mfccs, axis=1).tolist()
            
            # Spectral contrast (peaks vs valleys)
            contrast = librosa.feature.spectral_contrast(y=audio, sr=sr)
            profile.spectral_contrast = np.mean(contrast, axis=1).tolist()
            
        except Exception as e:
            print(f"Advanced analysis failed: {e}")


# =============================================================================
# APPROACH 2: INSTRUMENT MATCHER
# =============================================================================

# Genre-specific ideal characteristics
GENRE_PROFILES = {
    "trap": {
        "kick": SonicProfile(punch=0.9, warmth=0.8, brightness=0.3, decay_time_ms=150),
        "snare": SonicProfile(punch=0.8, brightness=0.6, noise_level=0.4),
        "hihat": SonicProfile(brightness=0.9, punch=0.7, decay_time_ms=50),
        "808": SonicProfile(warmth=0.95, punch=0.6, brightness=0.1, decay_time_ms=800),
        "clap": SonicProfile(brightness=0.7, noise_level=0.5, punch=0.6),
    },
    "lofi": {
        "kick": SonicProfile(punch=0.5, warmth=0.7, brightness=0.3, decay_time_ms=200),
        "snare": SonicProfile(punch=0.4, brightness=0.4, noise_level=0.6, warmth=0.6),
        "hihat": SonicProfile(brightness=0.5, punch=0.4, decay_time_ms=80, noise_level=0.3),
        "808": SonicProfile(warmth=0.8, punch=0.4, brightness=0.2),
    },
    "boom_bap": {
        "kick": SonicProfile(punch=0.7, warmth=0.6, brightness=0.4, decay_time_ms=180),
        "snare": SonicProfile(punch=0.7, brightness=0.5, noise_level=0.5),
        "hihat": SonicProfile(brightness=0.7, punch=0.5),
    },
    "house": {
        "kick": SonicProfile(punch=0.9, warmth=0.5, brightness=0.4, decay_time_ms=100),
        "snare": SonicProfile(punch=0.6, brightness=0.6),
        "hihat": SonicProfile(brightness=0.8, punch=0.6, decay_time_ms=40),
    },
    "g_funk": {
        "kick": SonicProfile(punch=0.7, warmth=0.75, brightness=0.35, decay_time_ms=160),
        "snare": SonicProfile(punch=0.65, brightness=0.5, noise_level=0.4),
        "hihat": SonicProfile(brightness=0.75, punch=0.5, decay_time_ms=60),
        "808": SonicProfile(warmth=0.85, punch=0.5, brightness=0.15, decay_time_ms=600),
    },
    "drill": {
        "kick": SonicProfile(punch=0.85, warmth=0.7, brightness=0.35),
        "snare": SonicProfile(punch=0.75, brightness=0.55, noise_level=0.45),
        "hihat": SonicProfile(brightness=0.85, punch=0.8, decay_time_ms=30),
        "808": SonicProfile(warmth=0.9, punch=0.7, brightness=0.15, decay_time_ms=700),
    },
    # Ethiopian traditional music profiles
    "ethiopian_traditional": {
        "krar": SonicProfile(brightness=0.75, warmth=0.6, punch=0.5, richness=0.7),
        "masenqo": SonicProfile(brightness=0.6, warmth=0.7, richness=0.8, noise_level=0.3),
        "washint": SonicProfile(brightness=0.8, warmth=0.4, richness=0.5, noise_level=0.2),
        "begena": SonicProfile(brightness=0.3, warmth=0.9, richness=0.8, decay_time_ms=600),
        "kebero": SonicProfile(punch=0.8, warmth=0.7, brightness=0.4, decay_time_ms=200),
    },
    "eskista": {
        "krar": SonicProfile(brightness=0.8, warmth=0.5, punch=0.6, richness=0.7),
        "washint": SonicProfile(brightness=0.85, warmth=0.35, richness=0.5),
        "kebero": SonicProfile(punch=0.85, warmth=0.65, brightness=0.45),
    },
    # Cinematic / orchestral music profiles
    "cinematic": {
        "kick": SonicProfile(punch=0.7, warmth=0.7, brightness=0.4, decay_time_ms=250),
        "snare": SonicProfile(punch=0.6, brightness=0.5, noise_level=0.3),
        "hihat": SonicProfile(brightness=0.5, punch=0.3, decay_time_ms=120),
        "keys": SonicProfile(warmth=0.7, brightness=0.5, richness=0.8, decay_time_ms=600),
        "strings": SonicProfile(warmth=0.7, brightness=0.5, richness=0.9, decay_time_ms=800),
        "brass": SonicProfile(brightness=0.6, warmth=0.6, punch=0.5, richness=0.7),
    },
    # Classical music profiles
    "classical": {
        "kick": SonicProfile(punch=0.5, warmth=0.7, brightness=0.3, decay_time_ms=300),
        "snare": SonicProfile(punch=0.4, brightness=0.4, noise_level=0.2),
        "keys": SonicProfile(warmth=0.7, brightness=0.6, richness=0.9, decay_time_ms=700),
        "strings": SonicProfile(warmth=0.8, brightness=0.5, richness=0.9, decay_time_ms=900),
        "brass": SonicProfile(brightness=0.5, warmth=0.7, punch=0.4, richness=0.8),
    },
}

# Mood modifiers for characteristics
MOOD_MODIFIERS = {
    "dark": {"brightness": -0.2, "warmth": 0.1},
    "bright": {"brightness": 0.2, "warmth": -0.1},
    "aggressive": {"punch": 0.2, "brightness": 0.1},
    "chill": {"punch": -0.2, "brightness": -0.1, "warmth": 0.1},
    "heavy": {"warmth": 0.2, "punch": 0.1},
    "light": {"warmth": -0.1, "brightness": 0.1},
    "crispy": {"brightness": 0.15, "punch": 0.1},
    "warm": {"warmth": 0.2, "brightness": -0.1},
    "punchy": {"punch": 0.25},
    "soft": {"punch": -0.2, "attack_time_ms": 20},
}


class InstrumentMatcher:
    """
    Matches instruments to production needs based on sonic characteristics.
    
    Uses the analyzed profiles to find the best-fitting samples
    for a given genre, mood, and instrument type.
    
    Now integrates with InstrumentIntelligence for semantic filtering:
    - First, filters out inappropriate instruments (e.g., whistles for G-Funk)
    - Then, scores remaining candidates by sonic similarity
    """
    
    def __init__(self, library: 'InstrumentLibrary' = None):
        self.library = library
        self._cache: Dict[str, AnalyzedInstrument] = {}
        self._intelligence = None  # InstrumentIntelligence instance
        self._excluded_samples: Dict[str, set] = {}  # genre -> set of excluded filenames
    
    def set_library(self, library: 'InstrumentLibrary'):
        """Set or update the instrument library."""
        self.library = library
    
    def set_intelligence(self, intelligence: 'InstrumentIntelligence'):
        """
        Set the InstrumentIntelligence for semantic filtering.
        
        This enables the matcher to exclude inappropriate instruments
        based on genre/mood context (e.g., no whistles in G-Funk).
        """
        self._intelligence = intelligence
        # Pre-compute exclusions for common genres
        for genre in ['g_funk', 'lofi', 'jazz', 'rnb', 'trap', 'boom_bap']:
            self._excluded_samples[genre] = set(
                intelligence.get_excluded_samples(genre)
            )
    
    def _is_excluded(self, instrument: 'AnalyzedInstrument', genre: str) -> bool:
        """Check if an instrument should be excluded for a genre."""
        if not self._intelligence:
            return False
        
        genre_key = genre.lower().replace(" ", "_").replace("-", "_")
        
        # Check pre-computed exclusions
        if genre_key in self._excluded_samples:
            # Check if instrument name is in the exclusion list (exact match)
            if instrument.name in self._excluded_samples[genre_key]:
                return True
            # Also check if the path contains any excluded filename
            inst_path_lower = instrument.path.lower()
            inst_name_lower = instrument.name.lower()
            for excluded_filename in self._excluded_samples[genre_key]:
                exc_lower = excluded_filename.lower()
                if exc_lower in inst_path_lower or exc_lower in inst_name_lower:
                    return True
        
        # Also do direct keyword check from GENRE_PROFILES for robustness
        # This catches cases where the instrument wasn't indexed properly
        from .instrument_intelligence import GENRE_PROFILES
        profile = GENRE_PROFILES.get(genre_key, {})
        excluded_sounds = profile.get('excluded_sounds', [])
        
        inst_path_lower = instrument.path.lower()
        inst_name_lower = instrument.name.lower()
        for keyword in excluded_sounds:
            if keyword in inst_path_lower or keyword in inst_name_lower:
                return True
        
        return False
    
    def set_library(self, library: 'InstrumentLibrary'):
        """Set or update the instrument library."""
        self.library = library
    
    def get_ideal_profile(
        self,
        category: str,
        genre: str = "trap",
        mood: str = None,
        **kwargs
    ) -> SonicProfile:
        """
        Get the ideal sonic profile for an instrument category.
        
        Args:
            category: Instrument category (kick, snare, etc.)
            genre: Target genre
            mood: Optional mood modifier
            **kwargs: Direct overrides for profile attributes
            
        Returns:
            Ideal SonicProfile for the given parameters
        """
        # Normalize genre
        genre_key = genre.lower().replace(" ", "_").replace("-", "_")
        
        # Start with default profile
        profile = SonicProfile(
            brightness=0.5,
            warmth=0.5,
            punch=0.5,
            richness=0.5,
            decay_time_ms=100,
        )
        
        # Apply genre profile if available
        if genre_key in GENRE_PROFILES:
            genre_profiles = GENRE_PROFILES[genre_key]
            if category in genre_profiles:
                ideal = genre_profiles[category]
                profile.brightness = ideal.brightness
                profile.warmth = ideal.warmth
                profile.punch = ideal.punch
                profile.richness = ideal.richness
                profile.decay_time_ms = ideal.decay_time_ms
                profile.noise_level = ideal.noise_level
        
        # Apply mood modifiers
        if mood:
            mood_key = mood.lower()
            for mood_word, modifiers in MOOD_MODIFIERS.items():
                if mood_word in mood_key:
                    for attr, mod in modifiers.items():
                        current = getattr(profile, attr, 0.5)
                        setattr(profile, attr, np.clip(current + mod, 0, 1))
        
        # Apply direct overrides
        for key, value in kwargs.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
        
        return profile
    
    def compute_similarity(
        self,
        profile1: SonicProfile,
        profile2: SonicProfile,
        weights: Dict[str, float] = None
    ) -> float:
        """
        Compute similarity between two sonic profiles.
        
        Returns a score from 0 (completely different) to 1 (identical).
        """
        default_weights = {
            "brightness": 1.0,
            "warmth": 1.0,
            "punch": 1.5,  # Punch is important for drums
            "richness": 0.8,
            "decay_time_ms": 0.8,
            "noise_level": 0.5,
        }
        
        weights = weights or default_weights
        
        total_weight = sum(weights.values())
        weighted_diff = 0.0
        
        for attr, weight in weights.items():
            v1 = getattr(profile1, attr, 0.5)
            v2 = getattr(profile2, attr, 0.5)
            
            # Normalize decay time to 0-1 range
            if attr == "decay_time_ms":
                v1 = min(v1 / 1000.0, 1.0)
                v2 = min(v2 / 1000.0, 1.0)
            
            diff = abs(v1 - v2)
            weighted_diff += diff * weight
        
        # Convert to similarity (0 diff = 1 similarity)
        max_possible_diff = total_weight
        similarity = 1.0 - (weighted_diff / max_possible_diff)
        
        return max(0.0, min(1.0, similarity))
    
    def get_best_match(
        self,
        category: str,
        genre: str = "trap",
        mood: str = None,
        top_n: int = 1,
        **kwargs
    ) -> Union[Optional[AnalyzedInstrument], List[AnalyzedInstrument]]:
        """
        Find the best matching instrument(s) for the given criteria.
        
        Args:
            category: Instrument category
            genre: Target genre
            mood: Optional mood
            top_n: Number of matches to return
            **kwargs: Additional profile requirements
            
        Returns:
            Best matching instrument(s) or None
        """
        if not self.library:
            return None if top_n == 1 else []
        
        # Get ideal profile
        ideal = self.get_ideal_profile(category, genre, mood, **kwargs)
        
        # Get all instruments in category
        category_enum = InstrumentCategory(category) if category in [e.value for e in InstrumentCategory] else InstrumentCategory.UNKNOWN
        candidates = self.library.get_by_category(category_enum)
        
        if not candidates:
            return None if top_n == 1 else []
        
        # INTELLIGENT FILTERING: Remove excluded instruments for this genre
        # This is where we prevent inappropriate sounds (whistles in G-Funk, etc.)
        filtered_candidates = []
        excluded_count = 0
        for instrument in candidates:
            if self._is_excluded(instrument, genre):
                excluded_count += 1
            else:
                filtered_candidates.append(instrument)
        
        if excluded_count > 0:
            print(f"    [IntelligentFilter] Excluded {excluded_count} inappropriate samples for {genre}")
        
        candidates = filtered_candidates
        
        if not candidates:
            return None if top_n == 1 else []
        
        # Score each candidate based on sonic similarity
        scored = []
        for instrument in candidates:
            if instrument.profile:
                score = self.compute_similarity(ideal, instrument.profile)
                scored.append((score, instrument))
        
        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)
        
        if top_n == 1:
            return scored[0][1] if scored else None
        
        return [inst for _, inst in scored[:top_n]]
    
    def get_recommendations(
        self,
        genre: str,
        mood: str = None
    ) -> Dict[str, List[Tuple[AnalyzedInstrument, float]]]:
        """
        Get instrument recommendations for a full production.
        
        Returns dict mapping categories to list of (instrument, score) tuples.
        """
        recommendations = {}
        
        categories = ["kick", "snare", "hihat", "clap", "808"]
        
        for cat in categories:
            matches = self.get_best_match(cat, genre, mood, top_n=3)
            if matches:
                ideal = self.get_ideal_profile(cat, genre, mood)
                recommendations[cat] = [
                    (inst, self.compute_similarity(ideal, inst.profile))
                    for inst in matches
                ]
        
        return recommendations
    
    def explain_match(
        self,
        instrument: AnalyzedInstrument,
        genre: str,
        mood: str = None
    ) -> str:
        """
        Generate human-readable explanation of why an instrument matches.
        """
        if not instrument.profile:
            return "No profile available for analysis."
        
        ideal = self.get_ideal_profile(instrument.category.value, genre, mood)
        profile = instrument.profile
        score = self.compute_similarity(ideal, profile)
        
        explanations = []
        
        # Brightness
        if abs(profile.brightness - ideal.brightness) < 0.15:
            if profile.brightness > 0.6:
                explanations.append("bright and cutting")
            elif profile.brightness < 0.4:
                explanations.append("warm and dark")
            else:
                explanations.append("balanced tone")
        
        # Punch
        if profile.punch > 0.7:
            explanations.append("punchy attack")
        elif profile.punch < 0.4:
            explanations.append("soft attack")
        
        # Warmth
        if profile.warmth > 0.7:
            explanations.append("rich low-end")
        
        # Decay
        if profile.decay_time_ms < 100:
            explanations.append("tight decay")
        elif profile.decay_time_ms > 500:
            explanations.append("long sustain")
        
        explanation = f"'{instrument.name}' (match: {score:.0%}) - "
        explanation += ", ".join(explanations) if explanations else "suitable characteristics"
        
        return explanation


# =============================================================================
# APPROACH 3: DYNAMIC INSTRUMENT LIBRARY
# =============================================================================

class InstrumentLibrary:
    """
    Manages the instruments directory with auto-discovery and caching.
    
    Integrates with AudioRenderer to provide actual samples for playback.
    """
    
    def __init__(
        self,
        instruments_dir: str = None,
        cache_file: str = None,
        auto_load_audio: bool = False
    ):
        """
        Initialize the instrument library.
        
        Args:
            instruments_dir: Path to instruments directory
            cache_file: Path to cache file for analysis results
            auto_load_audio: Whether to load audio data on discovery
        """
        self.instruments_dir = Path(instruments_dir) if instruments_dir else None
        self.cache_file = cache_file
        self.auto_load_audio = auto_load_audio
        
        self.instruments: Dict[str, AnalyzedInstrument] = {}
        self.by_category: Dict[InstrumentCategory, List[AnalyzedInstrument]] = {
            cat: [] for cat in InstrumentCategory
        }
        
        self._analyzer = InstrumentAnalyzer()
        self._cache: Dict[str, SonicProfile] = {}
        
        # Load cache if available
        if cache_file:
            self._load_cache()
    
    def discover_and_analyze(self, progress_callback: callable = None) -> int:
        """
        Discover all instruments in the directory and analyze them.
        
        Args:
            progress_callback: Optional callback(current, total, name) for progress
            
        Returns:
            Number of instruments discovered
        """
        if not self.instruments_dir or not self.instruments_dir.exists():
            print(f"Instruments directory not found: {self.instruments_dir}")
            return 0
        
        # Find all audio files
        extensions = ['.wav', '.WAV', '.aif', '.aiff', '.mp3', '.flac']
        audio_files = []
        
        for ext in extensions:
            audio_files.extend(self.instruments_dir.rglob(f"*{ext}"))
        
        total = len(audio_files)
        print(f"Found {total} audio files in {self.instruments_dir}")
        
        for i, path in enumerate(audio_files):
            if progress_callback:
                progress_callback(i + 1, total, path.name)
            
            self.add_instrument(str(path))
        
        # Save cache
        if self.cache_file:
            self._save_cache()
        
        return len(self.instruments)
    
    def add_instrument(
        self,
        path: str,
        category: InstrumentCategory = None,
        load_audio: bool = None
    ) -> Optional[AnalyzedInstrument]:
        """
        Add an instrument to the library.
        
        Args:
            path: Path to audio file
            category: Override category detection
            load_audio: Override auto_load_audio setting
            
        Returns:
            AnalyzedInstrument or None if failed
        """
        path = str(path)
        load = load_audio if load_audio is not None else self.auto_load_audio
        
        # Detect category from path
        if category is None:
            category = self._detect_category(path)
        
        # Check cache
        profile = self._get_cached_profile(path)
        
        # Analyze if not cached
        if profile is None:
            profile = self._analyzer.analyze_file(path, load_audio=load)
            if profile:
                profile.category = category.value
                self._cache[path] = profile

        # If analysis isn't available (e.g., optional deps missing), still index the file
        # so the UI can browse instruments. Matching will be less intelligent.
        if profile is None:
            try:
                file_hash = self._analyzer._compute_hash(path)
            except Exception:
                file_hash = ""
            profile = SonicProfile(
                sample_path=path,
                sample_name=Path(path).stem,
                category=category.value,
                duration_sec=0.0,
                file_hash=file_hash,
            )
        
        # Load audio if requested
        audio = None
        if load and HAS_SOUNDFILE:
            try:
                audio, sr = sf.read(path)
                if len(audio.shape) > 1:
                    audio = np.mean(audio, axis=1)
            except Exception:
                pass
        
        instrument = AnalyzedInstrument(
            path=path,
            name=Path(path).stem,
            category=category,
            profile=profile,
            audio=audio,
        )
        
        self.instruments[path] = instrument
        self.by_category[category].append(instrument)
        
        return instrument
    
    def add_from_directory(
        self,
        directory: str,
        category: InstrumentCategory = None
    ) -> int:
        """Add all instruments from a directory."""
        directory = Path(directory)
        if not directory.exists():
            return 0
        
        count = 0
        extensions = ['.wav', '.WAV', '.aif', '.aiff']
        
        for ext in extensions:
            for path in directory.rglob(f"*{ext}"):
                if self.add_instrument(str(path), category):
                    count += 1
        
        return count
    
    def get_by_category(
        self,
        category: InstrumentCategory
    ) -> List[AnalyzedInstrument]:
        """Get all instruments in a category."""
        return self.by_category.get(category, [])
    
    def get_instrument(self, path: str) -> Optional[AnalyzedInstrument]:
        """Get instrument by path."""
        return self.instruments.get(path)
    
    def get_random(
        self,
        category: InstrumentCategory
    ) -> Optional[AnalyzedInstrument]:
        """Get a random instrument from category."""
        candidates = self.by_category.get(category, [])
        if candidates:
            import random
            return random.choice(candidates)
        return None
    
    def load_audio(self, instrument: AnalyzedInstrument) -> bool:
        """Load audio for an instrument (lazy loading)."""
        if instrument.audio is not None:
            return True
        
        if not HAS_SOUNDFILE:
            return False
        
        try:
            audio, sr = sf.read(instrument.path)
            if len(audio.shape) > 1:
                audio = np.mean(audio, axis=1)
            
            # Resample if needed
            if sr != self.instruments[instrument.path].sample_rate and HAS_LIBROSA:
                audio = librosa.resample(
                    audio, orig_sr=sr, target_sr=instrument.sample_rate
                )
            
            instrument.audio = audio
            return True
            
        except Exception:
            return False
    
    def get_audio(
        self,
        category: InstrumentCategory,
        name: str = None
    ) -> Optional[np.ndarray]:
        """
        Get audio data for an instrument.
        
        Args:
            category: Instrument category
            name: Optional specific instrument name
            
        Returns:
            Audio array or None
        """
        instruments = self.by_category.get(category, [])
        
        if not instruments:
            return None
        
        # Find by name if specified
        if name:
            for inst in instruments:
                if name.lower() in inst.name.lower():
                    self.load_audio(inst)
                    return inst.audio
        
        # Return first available with loaded audio
        for inst in instruments:
            if inst.audio is not None:
                return inst.audio
        
        # Load first one
        if instruments:
            self.load_audio(instruments[0])
            return instruments[0].audio
        
        return None
    
    def list_categories(self) -> Dict[str, int]:
        """List categories and their instrument counts."""
        return {
            cat.value: len(instruments)
            for cat, instruments in self.by_category.items()
            if instruments
        }
    
    def list_instruments(
        self,
        category: InstrumentCategory = None
    ) -> List[str]:
        """List instrument names, optionally filtered by category."""
        if category:
            return [inst.name for inst in self.by_category.get(category, [])]
        return [inst.name for inst in self.instruments.values()]
    
    def _detect_category(self, path: str) -> InstrumentCategory:
        """Detect instrument category from file path."""
        path_lower = path.lower()
        
        # Check directory names
        for dir_name, category in DIR_TO_CATEGORY.items():
            if f"/{dir_name}/" in path_lower or f"\\{dir_name}\\" in path_lower:
                return category
        
        # Check filename keywords
        filename = Path(path).stem.lower()
        for category, keywords in KEYWORD_TO_CATEGORY.items():
            for keyword in keywords:
                if keyword in filename:
                    return category
        
        return InstrumentCategory.UNKNOWN
    
    def _get_cached_profile(self, path: str) -> Optional[SonicProfile]:
        """Get profile from cache if valid."""
        if path not in self._cache:
            return None
        
        profile = self._cache[path]
        
        # Validate cache by checking file hash
        if os.path.exists(path):
            current_hash = self._analyzer._compute_hash(path)
            if profile.file_hash == current_hash:
                return profile
        
        return None
    
    def _load_cache(self):
        """Load analysis cache from file."""
        if not self.cache_file or not os.path.exists(self.cache_file):
            return
        
        try:
            with open(self.cache_file, 'r') as f:
                data = json.load(f)
                for path, profile_data in data.items():
                    self._cache[path] = SonicProfile.from_dict(profile_data)
            print(f"Loaded {len(self._cache)} cached profiles")
        except Exception as e:
            print(f"Failed to load cache: {e}")
    
    def _save_cache(self):
        """Save analysis cache to file."""
        if not self.cache_file:
            return
        
        try:
            data = {
                path: profile.to_dict()
                for path, profile in self._cache.items()
            }
            
            # Ensure directory exists
            Path(self.cache_file).parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.cache_file, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"Saved {len(data)} profiles to cache")
        except Exception as e:
            print(f"Failed to save cache: {e}")
    
    def merge(self, other: 'InstrumentLibrary') -> 'InstrumentLibrary':
        """
        Merge another library into this one.
        
        Args:
            other: Another InstrumentLibrary to merge
            
        Returns:
            Self (for chaining)
        """
        # Merge instruments dict
        for path, instrument in other.instruments.items():
            if path not in self.instruments:
                self.instruments[path] = instrument
        
        # Merge by_category
        for category, instruments in other.by_category.items():
            for inst in instruments:
                if inst not in self.by_category[category]:
                    self.by_category[category].append(inst)
        
        # Merge cache
        self._cache.update(other._cache)
        
        return self
    
    def get_source_summary(self) -> Dict[str, int]:
        """Get count of instruments by source directory."""
        sources = {}
        for inst in self.instruments.values():
            # Get parent directory name as source
            source = Path(inst.path).parent.parent.name
            if not source or source == ".":
                source = Path(inst.path).parent.name
            sources[source] = sources.get(source, 0) + 1
        return sources


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def load_multiple_libraries(
    paths: List[str],
    cache_dir: str = None,
    auto_load_audio: bool = True,
    verbose: bool = False,
    progress_callback: callable = None,
) -> InstrumentLibrary:
    """
    Load and merge multiple instrument sources into one library.
    
    Args:
        paths: List of paths to instrument directories
        cache_dir: Directory to store cache files (uses output dir if None)
        auto_load_audio: Whether to load audio data
        verbose: Print progress info
        
    Returns:
        Merged InstrumentLibrary with all sources
    """
    if not paths:
        return InstrumentLibrary()
    
    merged_library = None

    num_sources = len(paths)

    def make_source_progress_callback(source_index: int, source_name: str):
        def _cb(current: int, total: int, name: str):
            if not progress_callback:
                return
            try:
                source_fraction = 1.0 / max(1, num_sources)
                within_source = (float(current) / float(max(1, total))) if total else 0.0
                overall = (source_index * source_fraction) + (within_source * source_fraction)
                progress_callback(overall, f"Scanning {source_name}: {name} ({current}/{total})")
            except Exception:
                pass
        return _cb

    for i, path in enumerate(paths):
        path_obj = Path(path)
        if not path_obj.exists():
            if verbose:
                print(f"  ⚠ Source not found: {path}")
            continue
        
        # Determine cache file location
        if cache_dir:
            cache_name = path_obj.name.replace("[", "").replace("]", "").replace(" ", "_")
            cache_file = str(Path(cache_dir) / f".instrument_cache_{cache_name}.json")
        else:
            # Try to use cache in source directory
            try:
                test_file = path_obj / ".write_test"
                test_file.touch()
                test_file.unlink()
                cache_file = str(path_obj / ".instrument_cache.json")
            except (PermissionError, OSError):
                # Source is read-only, skip cache for now
                cache_file = None
        
        if verbose:
            source_name = path_obj.name[:30] + "..." if len(path_obj.name) > 30 else path_obj.name
            print(f"  📁 Loading source {i+1}/{len(paths)}: {source_name}")
        
        library = InstrumentLibrary(
            instruments_dir=str(path),
            cache_file=cache_file,
            auto_load_audio=auto_load_audio
        )

        count = library.discover_and_analyze(
            progress_callback=make_source_progress_callback(i, path_obj.name)
        )
        
        if verbose:
            print(f"     Found {count} instruments")
        
        if merged_library is None:
            merged_library = library
        else:
            merged_library.merge(library)
    
    if merged_library is None:
        return InstrumentLibrary()
    
    if verbose:
        total = len(merged_library.instruments)
        sources = merged_library.get_source_summary()
        print(f"  ✓ Total: {total} instruments from {len(sources)} sources")
    
    return merged_library


def discover_instruments(
    instruments_dir: str = None
) -> InstrumentLibrary:
    """
    Quick function to discover and analyze instruments.
    
    Args:
        instruments_dir: Path to instruments folder
        
    Returns:
        Populated InstrumentLibrary
    """
    # Default to ./instruments relative to this file
    if instruments_dir is None:
        module_dir = Path(__file__).parent.parent
        instruments_dir = module_dir / "instruments"
    
    cache_file = str(Path(instruments_dir) / ".instrument_cache.json")
    
    library = InstrumentLibrary(
        instruments_dir=str(instruments_dir),
        cache_file=cache_file,
        auto_load_audio=True
    )
    
    library.discover_and_analyze()
    
    return library


def get_best_instruments_for_genre(
    genre: str,
    library: InstrumentLibrary,
    mood: str = None
) -> Dict[str, AnalyzedInstrument]:
    """
    Get the best instruments for a production.
    
    Args:
        genre: Target genre
        library: Instrument library to search
        mood: Optional mood modifier
        
    Returns:
        Dict mapping categories to best instruments
    """
    matcher = InstrumentMatcher(library)
    
    result = {}
    for category in ["kick", "snare", "hihat", "clap", "808"]:
        best = matcher.get_best_match(category, genre, mood)
        if best:
            result[category] = best
    
    return result


def analyze_sample(path: str) -> Optional[SonicProfile]:
    """Quick function to analyze a single sample."""
    analyzer = InstrumentAnalyzer()
    return analyzer.analyze_file(path)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'InstrumentCategory',
    'SonicProfile',
    'AnalyzedInstrument',
    'InstrumentAnalyzer',
    'InstrumentMatcher',
    'InstrumentLibrary',
    'discover_instruments',
    'load_multiple_libraries',
    'get_best_instruments_for_genre',
    'analyze_sample',
    'GENRE_PROFILES',
    'MOOD_MODIFIERS',
]
