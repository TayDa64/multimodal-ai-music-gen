"""
Audio Renderer Module

Renders MIDI to audio using:
1. FluidSynth (if available) - uses SoundFont files for high-quality output
2. Procedural synthesis (fallback) - CPU-based synthesis for offline capability
3. InstrumentLibrary (optional) - uses analyzed custom samples for best fit

Features:
- Per-track stem rendering
- Stereo mix with panning
- Sidechain compression simulation
- Texture layer mixing (vinyl, rain, etc.)
- Loudness normalization (-14 LUFS target)
- Intelligent instrument selection via InstrumentMatcher
"""

import os
import subprocess
import logging
import numpy as np
import json
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

logger = logging.getLogger(__name__)
from dataclasses import dataclass, field
import tempfile

try:
    import soundfile as sf
    HAS_SOUNDFILE = True
except ImportError:
    HAS_SOUNDFILE = False
    import wave

from .utils import (
    SAMPLE_RATE,
    BIT_DEPTH,
    TARGET_LUFS,
    TARGET_TRUE_PEAK,
    HEADROOM_DB,
    ticks_to_seconds,
    midi_to_note_name,
    note_name_to_midi,
)
from .prompt_parser import ParsedPrompt
from .arranger import Arrangement, SectionType
from .assets_gen import (
    generate_808_kick,
    generate_kick,
    generate_snare,
    generate_clap,
    generate_hihat,
    generate_vinyl_crackle,
    generate_rain,
    generate_fm_pluck,
    generate_piano_tone,
    generate_lead_tone,
    generate_pad_tone,
    generate_sine_tone,
    # Ethiopian instruments
    generate_krar_tone,
    generate_masenqo_tone,
    generate_washint_tone,
    generate_begena_tone,
    generate_brass_tone,
    generate_organ_tone,
    lowpass_filter,
    highpass_filter,
    normalize_audio,
    save_wav,
)

from .mix_chain import (
    MixChain,
    create_drum_bus_chain,
    create_master_chain,
    create_lofi_chain,
    create_bass_chain,
    EffectType,
    EffectParams,
    SaturationParams,
    CompressorParams,
    ReverbParams
)

# Import InstrumentLibrary for custom sample support
if TYPE_CHECKING:
    from .instrument_manager import InstrumentLibrary, InstrumentMatcher
    from .synthesizers import ISynthesizer
    from .expansion_manager import ExpansionManager
    from .instrument_resolution import InstrumentResolutionService

# Optional instrument resolution service for expansion instrument support
try:
    from .instrument_resolution import InstrumentResolutionService as _IRS
    HAS_INSTRUMENT_SERVICE = True
except ImportError:
    HAS_INSTRUMENT_SERVICE = False
    _IRS = None  # type: ignore

# Convolution reverb for master bus processing (Sprint 7)
try:
    from .reverb import ConvolutionReverb, ReverbConfig, IR_PRESETS
    _HAS_CONVOLUTION_REVERB = True
except ImportError:
    _HAS_CONVOLUTION_REVERB = False

# Multiband dynamics for master bus processing (Sprint 7.5)
try:
    from .multiband_dynamics import MultibandDynamics, multiband_compress, MULTIBAND_PRESETS, MultibandDynamicsParams
    _HAS_MULTIBAND_DYNAMICS = True
except ImportError:
    _HAS_MULTIBAND_DYNAMICS = False

# Spectral processing for master bus (Sprint 7.5)
try:
    from .spectral_processing import (
        HarmonicExciter, ResonanceSuppressor, apply_spectral_preset,
        HarmonicExciterParams, ResonanceSuppressorParams, SPECTRAL_PRESETS
    )
    _HAS_SPECTRAL_PROCESSING = True
except ImportError:
    _HAS_SPECTRAL_PROCESSING = False

# Reference matching for master bus (Sprint 7.5)
try:
    from .reference_matching import ReferenceMatcher, ReferenceAnalyzer
    _HAS_REFERENCE_MATCHING = True
except ImportError:
    _HAS_REFERENCE_MATCHING = False

# Track processor for per-stem channel strip (Sprint 8)
try:
    from .track_processor import TrackProcessor, TRACK_PRESETS
    _HAS_TRACK_PROCESSOR = True
except ImportError:
    _HAS_TRACK_PROCESSOR = False


# =============================================================================
# AUDIO PROCESSING UTILITIES
# =============================================================================

def calculate_rms(audio: np.ndarray) -> float:
    """Calculate RMS level of audio."""
    return np.sqrt(np.mean(audio ** 2))


def calculate_peak(audio: np.ndarray) -> float:
    """Calculate peak level of audio."""
    return np.max(np.abs(audio))


def estimate_lufs(audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> float:
    """
    Rough LUFS estimation.
    
    Note: This is a simplified approximation. For accurate LUFS,
    use a dedicated library like pyloudnorm.
    """
    # Apply K-weighting (simplified)
    # High-shelf filter approximation
    audio_weighted = highpass_filter(audio, 60, sample_rate)
    
    # Calculate mean square
    ms = np.mean(audio_weighted ** 2)
    
    if ms > 0:
        return -0.691 + 10 * np.log10(ms)
    return -70  # Very quiet


def apply_gain(audio: np.ndarray, gain_db: float) -> np.ndarray:
    """Apply gain in dB to audio."""
    linear_gain = 10 ** (gain_db / 20)
    return audio * linear_gain


def apply_sidechain_ducking(
    audio: np.ndarray,
    trigger: np.ndarray,
    attack_ms: float = 5.0,
    release_ms: float = 100.0,
    ratio: float = 6.0,
    threshold: float = 0.3,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Apply sidechain ducking effect.
    
    Ducks audio signal based on trigger signal level.
    Used to create the "pumping" effect when 808/kick hits.
    """
    # Calculate envelope from trigger
    attack_samples = int(attack_ms * sample_rate / 1000)
    release_samples = int(release_ms * sample_rate / 1000)
    
    # Get trigger envelope
    trigger_abs = np.abs(trigger)
    envelope = np.zeros_like(trigger_abs)
    
    for i in range(len(trigger_abs)):
        if i == 0:
            envelope[i] = trigger_abs[i]
        else:
            if trigger_abs[i] > envelope[i-1]:
                # Attack
                coef = 1 - np.exp(-1 / attack_samples)
                envelope[i] = envelope[i-1] + coef * (trigger_abs[i] - envelope[i-1])
            else:
                # Release
                coef = 1 - np.exp(-1 / release_samples)
                envelope[i] = envelope[i-1] + coef * (trigger_abs[i] - envelope[i-1])
    
    # Calculate gain reduction
    gain_reduction = np.ones_like(envelope)
    above_threshold = envelope > threshold
    
    # Apply ratio-based gain reduction
    if np.any(above_threshold):
        excess = envelope[above_threshold] - threshold
        reduced = threshold + excess / ratio
        gain_reduction[above_threshold] = reduced / envelope[above_threshold]
    
    # Apply to audio (ensure lengths match)
    min_len = min(len(audio), len(gain_reduction))
    output = audio[:min_len] * gain_reduction[:min_len]
    
    if len(audio) > min_len:
        output = np.concatenate([output, audio[min_len:]])
    
    return output


def apply_stereo_pan(
    audio: np.ndarray,
    pan: float = 0.0
) -> np.ndarray:
    """
    Apply stereo panning to mono audio.
    
    Args:
        audio: Mono audio array
        pan: Pan position (-1.0 = left, 0.0 = center, 1.0 = right)
    
    Returns:
        Stereo audio array (N, 2)
    """
    # Calculate channel gains (constant power panning)
    pan_norm = (pan + 1) / 2  # 0 to 1
    left_gain = np.cos(pan_norm * np.pi / 2)
    right_gain = np.sin(pan_norm * np.pi / 2)
    
    left = audio * left_gain
    right = audio * right_gain
    
    return np.column_stack([left, right])


def remove_dc_offset(audio: np.ndarray) -> np.ndarray:
    """
    Remove DC offset from audio.
    
    DC offset causes asymmetric waveforms which waste headroom.
    """
    if len(audio.shape) > 1:
        # Stereo - process each channel
        return audio - np.mean(audio, axis=0, keepdims=True)
    else:
        return audio - np.mean(audio)


def mix_stereo_tracks(
    tracks: List[np.ndarray],
    levels: Optional[List[float]] = None,
    pans: Optional[List[float]] = None,
    headroom_db: float = -3.0
) -> np.ndarray:
    """
    Mix multiple stereo tracks with proper gain staging.
    
    Args:
        tracks: List of stereo audio arrays (N, 2)
        levels: Optional dB levels for each track
        pans: Optional pan positions for each track
        headroom_db: Target headroom to prevent clipping (default -3dB)
    
    Returns:
        Mixed stereo audio
    """
    if not tracks:
        return np.zeros((0, 2))
    
    # Get max length
    max_len = max(len(t) for t in tracks)
    
    # Default levels and pans
    if levels is None:
        levels = [0.0] * len(tracks)
    if pans is None:
        pans = [0.0] * len(tracks)
    
    # Initialize mix
    mix = np.zeros((max_len, 2))
    
    # Calculate auto-gain based on track count to prevent summing clipping
    # Each additional track adds ~3dB of potential level increase
    num_tracks = len(tracks)
    auto_gain_reduction = 10 ** (-3.0 * np.log2(max(num_tracks, 1)) / 20) if num_tracks > 1 else 1.0
    
    for track, level_db, pan in zip(tracks, levels, pans):
        # Ensure stereo
        if len(track.shape) == 1:
            track = apply_stereo_pan(track, pan)
        elif track.shape[1] == 1:
            track = apply_stereo_pan(track.flatten(), pan)
        
        # Remove DC offset from each track before mixing
        track = remove_dc_offset(track)
        
        # Apply level with auto-gain reduction
        gain = 10 ** (level_db / 20) * auto_gain_reduction
        track = track * gain
        
        # Add to mix
        track_len = len(track)
        mix[:track_len] += track
    
    return mix


def limit_audio(
    audio: np.ndarray,
    ceiling_db: float = -1.0,
    release_ms: float = 100.0,
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Apply brickwall limiter.
    
    Prevents audio from exceeding ceiling level.
    """
    ceiling = 10 ** (ceiling_db / 20)
    release_samples = int(release_ms * sample_rate / 1000)
    
    # Calculate peak envelope
    audio_abs = np.abs(audio)
    if len(audio.shape) > 1:
        audio_abs = np.max(audio_abs, axis=1)
    
    # Find peaks above ceiling
    envelope = np.ones_like(audio_abs)
    
    for i in range(len(audio_abs)):
        if audio_abs[i] > ceiling:
            envelope[i] = ceiling / audio_abs[i]
        elif i > 0:
            # Smooth release
            envelope[i] = min(1.0, envelope[i-1] + 1.0 / release_samples)
    
    # Apply gain reduction
    if len(audio.shape) > 1:
        return audio * envelope[:, np.newaxis]
    return audio * envelope


def soft_clip(
    audio: np.ndarray,
    threshold: float = 0.7,
    knee: float = 0.3,
    ceiling: float = 0.95
) -> np.ndarray:
    """
    Apply soft clipping to audio to prevent harsh distortion.
    
    Uses tanh-based saturation above threshold for musical clipping.
    The output is guaranteed to not exceed the ceiling level.
    
    Args:
        audio: Input audio array
        threshold: Level where soft clipping begins (0-1)
        knee: Softness of the knee (higher = softer transition)
        ceiling: Maximum output level (default 0.95 to leave headroom)
        
    Returns:
        Soft-clipped audio with peak <= ceiling
    """
    if len(audio) == 0:
        return audio
    
    peak = np.max(np.abs(audio))
    if peak == 0:
        return audio
    
    # If already under threshold, no clipping needed
    if peak <= threshold:
        return audio
    
    # Apply tanh soft clipping - this naturally limits output to asymptote
    # Scale input so that threshold maps to tanh input of 1
    # tanh(1) ≈ 0.76, so we adjust for desired ceiling
    scale_factor = 1.5 / knee  # Adjust saturation curve steepness
    
    output = np.where(
        np.abs(audio) < threshold,
        audio,
        np.sign(audio) * (threshold + (ceiling - threshold) * np.tanh(
            (np.abs(audio) - threshold) * scale_factor
        ))
    )
    
    # Final safety clamp - ensure no sample exceeds ceiling
    output = np.clip(output, -ceiling, ceiling)
    
    return output


# =============================================================================
# FLUIDSYNTH INTERFACE
# =============================================================================

def check_fluidsynth_available() -> bool:
    """Check if FluidSynth is installed and available."""
    try:
        result = subprocess.run(
            ['fluidsynth', '--version'],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def get_fluidsynth_version() -> Optional[str]:
    """Return the FluidSynth version string if available, else None."""
    try:
        result = subprocess.run(
            ['fluidsynth', '--version'],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            return None
        # Typical output: "FluidSynth 2.3.3"
        return (result.stdout or result.stderr).strip() or None
    except FileNotFoundError:
        return None
    except Exception:
        return None


def find_soundfont() -> Optional[str]:
    """Try to find a SoundFont file."""
    # Common locations
    search_paths = [
        # Project assets
        './assets/soundfonts/',
        # User home
        os.path.expanduser('~/.fluidsynth/'),
        # Linux common
        '/usr/share/sounds/sf2/',
        '/usr/share/soundfonts/',
        # macOS
        '/Library/Audio/Sounds/Banks/',
    ]
    
    soundfont_names = [
        'default_sound_font.sf2',
        'FluidR3_GM.sf2',
        'GeneralUser_GS.sf2',
        'default.sf2',
    ]
    
    for path in search_paths:
        for name in soundfont_names:
            full_path = os.path.join(path, name)
            if os.path.exists(full_path):
                return full_path
    
    return None


def render_midi_with_fluidsynth(
    midi_path: str,
    output_path: str,
    soundfont_path: Optional[str] = None,
    sample_rate: int = SAMPLE_RATE
) -> bool:
    """
    Render MIDI file to audio using FluidSynth.
    
    Returns:
        True if successful
    """
    if soundfont_path is None:
        soundfont_path = find_soundfont()
        if soundfont_path is None:
            return False
    
    try:
        cmd = [
            'fluidsynth',
            '-ni',                      # No interactive mode
            soundfont_path,             # SoundFont
            midi_path,                  # Input MIDI
            '-F', output_path,          # Output file
            '-r', str(sample_rate),     # Sample rate
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0 and os.path.exists(output_path)
    
    except Exception:
        return False


# =============================================================================
# PROCEDURAL SYNTHESIS RENDERER
# =============================================================================

@dataclass
class SynthNote:
    """Note to be synthesized."""
    pitch: int
    start_sample: int
    duration_samples: int
    velocity: float  # 0-1
    channel: int
    program: int = 0


class ProceduralRenderer:
    """
    Renders MIDI to audio using procedural synthesis.
    
    Fallback when FluidSynth is not available.
    Supports custom samples via InstrumentLibrary for intelligent selection.
    Also supports ExpansionManager for Ethiopian and other specialized instruments.
    
    Now supports optional InstrumentResolutionService for dynamic program-to-instrument
    mapping from expansion packs.
    """
    
    # Ethiopian instruments that should use procedural synthesis, not generic samples
    ETHIOPIAN_INSTRUMENTS = {'krar', 'masenqo', 'washint', 'begena', 'kebero', 'atamo'}
    
    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        instrument_library: 'InstrumentLibrary' = None,
        expansion_manager: 'ExpansionManager' = None,
        instrument_service: 'InstrumentResolutionService' = None,
        genre: str = None,
        mood: str = None,
        parsed_instruments: list = None,  # NEW: Explicit instruments from prompt
    ):
        self.sample_rate = sample_rate
        self.instrument_library = instrument_library
        self.expansion_manager = expansion_manager
        self._instrument_service = instrument_service
        self.genre = genre or "trap"
        self.mood = mood
        self._parsed_instruments = set(parsed_instruments) if parsed_instruments else set()
        
        # Check if Ethiopian instruments are requested
        self._has_ethiopian_instruments = bool(self._parsed_instruments & self.ETHIOPIAN_INSTRUMENTS)
        
        # Matcher for intelligent instrument selection
        self._matcher = None
        self._intelligence = None  # NEW: Semantic instrument intelligence
        
        if instrument_library:
            try:
                from .instrument_manager import InstrumentMatcher
                self._matcher = InstrumentMatcher(instrument_library)
                
                # Initialize InstrumentIntelligence for semantic filtering
                try:
                    from .instrument_intelligence import InstrumentIntelligence
                    self._intelligence = InstrumentIntelligence()
                    
                    # Index instruments directory - use instruments_dir attribute (not base_path)
                    instruments_dir = getattr(instrument_library, 'instruments_dir', None)
                    if instruments_dir:
                        instruments_path = str(instruments_dir)
                        count = self._intelligence.index_directory(instruments_path)
                        if count > 0:
                            print(f"  [IntelligenceEngine] Indexed {count} instruments for semantic filtering")
                            self._matcher.set_intelligence(self._intelligence)
                            # Log exclusions for this genre
                            excluded = self._intelligence.get_excluded_samples(self.genre)
                            if excluded:
                                print(f"  [IntelligenceEngine] {len(excluded)} samples excluded for {self.genre}")
                        else:
                            print(f"  [IntelligenceEngine] Warning: No instruments indexed from {instruments_path}")
                    else:
                        print(f"  [IntelligenceEngine] Warning: No instruments_dir attribute found")
                except ImportError as e:
                    print(f"  [!] InstrumentIntelligence not available: {e}")
                except Exception as e:
                    print(f"  [!] InstrumentIntelligence setup failed: {e}")
                    import traceback
                    traceback.print_exc()
                    
            except ImportError:
                pass
        
        # Pre-generate drum samples (fallback)
        self._drum_cache: Dict[str, np.ndarray] = {}
        self._custom_drum_cache: Dict[str, np.ndarray] = {}  # From library
        self._custom_melodic_cache: Dict[str, List[Dict]] = {}  # Melodic samples from library
        self._expansion_sample_cache: Dict[str, np.ndarray] = {}  # From expansions
        self._init_drum_cache()
        
        # Load custom instruments if available
        if instrument_library:
            self._load_custom_instruments()
        
        # Load expansion instruments for this genre
        if expansion_manager:
            self._load_expansion_instruments()
    
    def _init_drum_cache(self):
        """Pre-generate common drum sounds (procedural fallback)."""
        self._drum_cache['kick'] = generate_kick()
        self._drum_cache['808'] = generate_808_kick()
        self._drum_cache['snare'] = generate_snare()
        self._drum_cache['clap'] = generate_clap()
        self._drum_cache['hihat'] = generate_hihat(is_open=False)
        self._drum_cache['hihat_open'] = generate_hihat(is_open=True)
    
    def _load_custom_instruments(self):
        """Load best-fit instruments from library based on genre/mood.
        
        When Ethiopian instruments are explicitly requested, skip generic melodic
        instrument loading to ensure procedural Ethiopian synthesis is used.
        """
        if not self.instrument_library or not self._matcher:
            return
        
        try:
            from .instrument_manager import InstrumentCategory
            
            # Map drum types to categories
            drum_mappings = {
                'kick': InstrumentCategory.KICK,
                '808': InstrumentCategory.BASS_808,
                'snare': InstrumentCategory.SNARE,
                'clap': InstrumentCategory.CLAP,
                'hihat': InstrumentCategory.HIHAT,
                'hihat_open': InstrumentCategory.HIHAT,
            }
            
            for drum_name, category in drum_mappings.items():
                # Get best match for this drum type and genre
                best = self._matcher.get_best_match(
                    category.value,
                    genre=self.genre,
                    mood=self.mood
                )
                
                if best:
                    # Load audio if not already loaded
                    if best.audio is None:
                        self.instrument_library.load_audio(best)
                    
                    if best.audio is not None:
                        # Resample if needed
                        audio = best.audio
                        if best.sample_rate != self.sample_rate:
                            try:
                                import librosa
                                audio = librosa.resample(
                                    audio,
                                    orig_sr=best.sample_rate,
                                    target_sr=self.sample_rate
                                )
                            except ImportError:
                                # Simple linear interpolation
                                ratio = self.sample_rate / best.sample_rate
                                new_len = int(len(audio) * ratio)
                                audio = np.interp(
                                    np.linspace(0, len(audio) - 1, new_len),
                                    np.arange(len(audio)),
                                    audio
                                )
                        
                        self._custom_drum_cache[drum_name] = audio
                        print(f"  [*] Loaded custom {drum_name}: {best.name}")
            
            if self._custom_drum_cache:
                print(f"  [+] Using {len(self._custom_drum_cache)} custom drum samples")
            
            # ===============================================================
            # MELODIC INSTRUMENTS - Genre-intelligent selection
            # ===============================================================
            # Load melodic instruments (synth, bass, keys, pad, brass, strings)
            # These are used by _synthesize_note for varied, genre-appropriate sounds
            
            # CRITICAL: Skip generic melodic loading when Ethiopian instruments requested
            # This ensures krar/masenqo/washint use authentic procedural synthesis
            if self._has_ethiopian_instruments:
                print(f"  [*] Ethiopian instruments requested ({', '.join(self._parsed_instruments & self.ETHIOPIAN_INSTRUMENTS)}) - using procedural synthesis")
                return  # Skip generic sample loading
            
            melodic_mappings = {
                'synth': InstrumentCategory.SYNTH,
                'bass': InstrumentCategory.BASS,
                'keys': InstrumentCategory.KEYS,
                'pad': InstrumentCategory.SYNTH,  # Pads fallback to synth since no pad category
                'brass': InstrumentCategory.BRASS,
                'strings': InstrumentCategory.STRINGS,
            }
            
            loaded_melodic = []
            for inst_name, category in melodic_mappings.items():
                # Get multiple candidates for variety using top_n parameter
                candidates = self._matcher.get_best_match(
                    category.value,
                    genre=self.genre,
                    mood=self.mood,
                    top_n=3  # Get top 3 matches for variety
                )
                
                # Ensure we have a list
                if candidates and not isinstance(candidates, list):
                    candidates = [candidates]
                
                if candidates:
                    # Store all candidates for variety during playback
                    self._custom_melodic_cache[inst_name] = []
                    for candidate in candidates:
                        if candidate.audio is None:
                            self.instrument_library.load_audio(candidate)
                        
                        if candidate.audio is not None:
                            audio = candidate.audio
                            # Resample if needed
                            if candidate.sample_rate != self.sample_rate:
                                try:
                                    import librosa
                                    audio = librosa.resample(
                                        audio,
                                        orig_sr=candidate.sample_rate,
                                        target_sr=self.sample_rate
                                    )
                                except ImportError:
                                    ratio = self.sample_rate / candidate.sample_rate
                                    new_len = int(len(audio) * ratio)
                                    audio = np.interp(
                                        np.linspace(0, len(audio) - 1, new_len),
                                        np.arange(len(audio)),
                                        audio
                                    )
                            
                            # Store with metadata for pitch-shifting
                            self._custom_melodic_cache[inst_name].append({
                                'audio': audio,
                                'name': candidate.name,
                                'root_note': getattr(candidate, 'root_note', 60),  # Default C4
                                'sample_rate': self.sample_rate
                            })
                    
                    if self._custom_melodic_cache[inst_name]:
                        loaded_melodic.append(inst_name)
                        print(f"  [*] Loaded custom {inst_name}: {self._custom_melodic_cache[inst_name][0]['name']}")
            
            if loaded_melodic:
                print(f"  [+] Using {len(loaded_melodic)} custom melodic instruments: {', '.join(loaded_melodic)}")
                
        except Exception as e:
            print(f"  [!] Custom instrument loading failed: {e}")
    
    def _load_expansion_instruments(self):
        """Load instruments from expansion packs for specialized genres."""
        if not self.expansion_manager:
            return
        
        try:
            # Use InstrumentResolutionService if available for genre instruments
            if self._instrument_service:
                instruments_to_load = self._instrument_service.get_instruments_for_genre(self.genre)
            else:
                # Fallback: Define instruments to pre-load based on genre
                genre_instruments = {
                    'eskista': ['krar', 'masenqo', 'washint', 'kebero'],
                    'tizita': ['krar', 'masenqo', 'washint', 'begena'],
                    'ethiopian': ['krar', 'masenqo', 'washint', 'kebero'],
                    'ethio_jazz': ['krar', 'masenqo', 'washint', 'piano', 'bass'],
                    'g_funk': ['synth', 'bass', 'piano'],
                    'trap': ['808', 'piano', 'synth'],
                    'rnb': ['piano', 'guitar', 'bass', 'synth'],
                }
                
                # Get instruments for current genre
                instruments_to_load = genre_instruments.get(self.genre, [])
            
            for inst_name in instruments_to_load:
                result = self.expansion_manager.resolve_instrument(inst_name, genre=self.genre)
                if result and result.sample_paths:
                    # Load the first available sample
                    sample_path = result.sample_paths[0] if result.sample_paths else None
                    if not sample_path:
                        continue
                    
                    try:
                        audio, sr = sf.read(sample_path)
                        if len(audio.shape) > 1:
                            audio = np.mean(audio, axis=1)  # Convert to mono
                        
                        # Resample if needed
                        if sr != self.sample_rate:
                            try:
                                import librosa
                                audio = librosa.resample(audio, orig_sr=sr, target_sr=self.sample_rate)
                            except ImportError:
                                ratio = self.sample_rate / sr
                                new_len = int(len(audio) * ratio)
                                audio = np.interp(
                                    np.linspace(0, len(audio) - 1, new_len),
                                    np.arange(len(audio)),
                                    audio
                                )
                        
                        # Store with original name and resolved name for lookup
                        self._expansion_sample_cache[inst_name] = audio
                        self._expansion_sample_cache[result.resolved_name.lower()] = audio
                        
                        print(f"  [*] Expansion: {inst_name} -> {result.resolved_name} ({result.match_type.name})")
                        
                    except Exception as e:
                        print(f"  [!] Failed to load expansion sample {inst_name}: {e}")
            
            if self._expansion_sample_cache:
                print(f"  [+] Using {len(self._expansion_sample_cache) // 2} expansion instruments")
                
        except Exception as e:
            print(f"  [!] Expansion instrument loading failed: {e}")
    
    def set_genre_mood(self, genre: str, mood: str = None):
        """Update genre/mood and reload instruments."""
        self.genre = genre
        self.mood = mood
        self._custom_drum_cache.clear()
        self._expansion_sample_cache.clear()
        if self.instrument_library:
            self._load_custom_instruments()
        if self.expansion_manager:
            self._load_expansion_instruments()
    
    def render_notes(
        self,
        notes: List[SynthNote],
        total_samples: int,
        is_drums: bool = False
    ) -> np.ndarray:
        """Render list of notes to audio."""
        audio = np.zeros(total_samples)
        
        for note in notes:
            if is_drums:
                sample = self._get_drum_sample(note.pitch)
                # Apply velocity only for drums (synthesis functions already apply it)
                sample = sample * note.velocity
            else:
                # Melodic synthesis functions already apply velocity internally
                sample = self._synthesize_note(note)
            
            # Mix into output
            end_sample = min(note.start_sample + len(sample), total_samples)
            available_len = end_sample - note.start_sample
            
            if available_len > 0:
                audio[note.start_sample:end_sample] += sample[:available_len]
        
        return audio
    
    def _get_drum_sample(self, pitch: int) -> np.ndarray:
        """Get drum sample for MIDI note number - prefers custom instruments."""
        # GM drum map (simplified)
        drum_map = {
            35: 'kick',     # Acoustic Bass Drum
            36: 'kick',     # Bass Drum 1 / 808
            37: 'snare',    # Side Stick
            38: 'snare',    # Acoustic Snare
            39: 'clap',     # Hand Clap
            40: 'snare',    # Electric Snare
            42: 'hihat',    # Closed Hi-Hat
            44: 'hihat',    # Pedal Hi-Hat
            46: 'hihat_open',  # Open Hi-Hat
            49: 'hihat_open',  # Crash
            # Ethiopian drums (custom kebero range)
            50: 'kebero',      # Kebero bass
            51: 'kebero_slap', # Kebero slap
            52: 'kebero_mute', # Kebero muted
            # GM Latin percussion (used for Ethiopian approximation)
            60: 'bongo_high',  # High Bongo - Atamo
            61: 'bongo_low',   # Low Bongo
            62: 'conga_high',  # High Conga - Kebero slap
            63: 'conga_low',   # Low Conga - Kebero bass
            70: 'shaker',      # Maracas/Shaker
        }
        
        drum_name = drum_map.get(pitch, 'kick')
        
        # Handle Ethiopian/Latin percussion with procedural synthesis
        if drum_name.startswith('kebero') or drum_name in ['conga_high', 'conga_low', 'bongo_high', 'bongo_low', 'shaker']:
            from .assets_gen import generate_kebero_hit, generate_shaker_hit
            velocity = 0.8
            if drum_name == 'shaker':
                return generate_shaker_hit(velocity, self.sample_rate)
            else:
                # Map conga/bongo to kebero-like sounds
                return generate_kebero_hit(pitch, velocity, self.sample_rate)
        
        # Prefer custom instruments from library
        if drum_name in self._custom_drum_cache:
            return self._custom_drum_cache[drum_name].copy()
        
        # Fallback to procedural
        return self._drum_cache.get(drum_name, self._drum_cache['kick']).copy()
    
    def _synthesize_note(self, note: SynthNote) -> np.ndarray:
        """Synthesize a melodic note based on MIDI program number.
        
        Priority:
        1. Custom melodic samples from InstrumentLibrary (genre-intelligent)
        2. Expansion samples (Ethiopian, etc.)
        3. Procedural synthesis fallback
        """
        # Convert MIDI pitch to frequency
        freq = 440 * (2 ** ((note.pitch - 69) / 12))
        duration = note.duration_samples / self.sample_rate
        velocity = note.velocity  # Already normalized 0-1 by _render_track_procedural
        
        # Map MIDI program to instrument type for custom sample lookup
        program_to_type = {
            # Pianos and Keys (0-7)
            **{p: 'keys' for p in range(0, 8)},
            # Chromatic Percussion (12-15)
            **{p: 'keys' for p in range(12, 16)},
            # Organ (16-23)
            **{p: 'keys' for p in range(16, 24)},
            # Guitar (24-31)
            **{p: 'keys' for p in range(24, 32)},
            # Bass (32-39)
            **{p: 'bass' for p in range(32, 40)},
            # Strings (40-51): GM Strings (40-47) + String Ensembles & Synth Strings (48-51)
            **{p: 'strings' for p in range(40, 52)},
            # Choir/Voice (52-55)
            **{p: 'pad' for p in range(52, 56)},
            # Brass (56-63)
            **{p: 'brass' for p in range(56, 64)},
            # Flute/Wind (72-79)
            **{p: 'synth' for p in range(72, 80)},  # Use synth as fallback
            # Synth Lead (80-87)
            **{p: 'synth' for p in range(80, 88)},
            # Synth Pad (88-95)
            **{p: 'pad' for p in range(88, 96)},
        }
        
        inst_type = program_to_type.get(note.program)
        
        # TRY CUSTOM MELODIC SAMPLES FIRST (genre-intelligent selection)
        if inst_type and inst_type in self._custom_melodic_cache and self._custom_melodic_cache[inst_type]:
            return self._pitch_shift_sample(
                self._custom_melodic_cache[inst_type],
                note.pitch,
                duration,
                velocity
            )
        
        # Check for expansion samples (for Ethiopian and specialized instruments)
        expansion_sample = self._get_expansion_sample_for_program(note.program, freq, duration, velocity)
        if expansion_sample is not None:
            return expansion_sample
        
        # PROCEDURAL FALLBACK - only if no custom samples available
        # Choose synthesis method based on program
        # Standard GM instruments
        if note.program in [0, 1, 2, 3]:  # Acoustic/bright/honky-tonk
            return generate_piano_tone(freq, duration, velocity, self.sample_rate)
        elif note.program in [4, 5, 6, 7]:  # Electric pianos
            return generate_fm_pluck(freq, duration)
        elif 80 <= note.program <= 87:  # Synth leads
            return generate_lead_tone(freq, duration, velocity, self.sample_rate)
        elif 12 <= note.program <= 15:  # Chromatic percussion (vibe/marimba/xylophone)
            # Avoid toy mallet timbres in procedural mode; render as soft keys instead.
            return generate_piano_tone(freq, duration, velocity * 0.75, self.sample_rate)
        elif note.program in [38, 39]:  # Synth Bass
            return generate_808_kick(duration, freq * 4, freq)
        elif note.program >= 88 and note.program <= 95:  # Pads
            return generate_pad_tone(freq, duration)
        elif note.program == 16 or note.program == 17:  # Organ
            return generate_organ_tone(freq, duration, velocity)
        elif note.program >= 56 and note.program <= 63:  # Brass
            return generate_brass_tone(freq, duration, velocity)
        elif note.program >= 40 and note.program <= 51:  # Strings (40-47) + String Ensembles (48-51)
            # Use masenqo for strings (bowed sound)
            return generate_masenqo_tone(freq, duration, velocity)
        elif note.program >= 72 and note.program <= 79:  # Flute/Wind
            return generate_washint_tone(freq, duration, velocity)
        # Ethiopian instruments (custom program numbers 110-119)
        elif note.program == 110:  # Krar
            # Use Ethiopian tuning, optionally add ornaments on accented notes
            add_ornament = velocity > 0.7 and duration > 0.15
            return generate_krar_tone(freq, duration, velocity, self.sample_rate, 'tizita', add_ornament)
        elif note.program == 111:  # Masenqo
            # High expressiveness for authentic Azmari sound
            expressiveness = 0.6 + velocity * 0.3
            add_ornament = velocity > 0.6 and duration > 0.25
            return generate_masenqo_tone(freq, duration, velocity, self.sample_rate, expressiveness, add_ornament)
        elif note.program == 112:  # Washint
            return generate_washint_tone(freq, duration, velocity, self.sample_rate)
        elif note.program == 113:  # Begena
            return generate_begena_tone(freq, duration, velocity, self.sample_rate)
        else:
            # Default to FM pluck
            return generate_fm_pluck(freq, duration)
    
    def _pitch_shift_sample(
        self,
        sample_variants: List[Dict],
        target_pitch: int,
        duration: float,
        velocity: float
    ) -> np.ndarray:
        """
        Pitch-shift a sample to match the target MIDI pitch.
        
        Uses resampling for pitch shifting. Selects a random variant for variety.
        
        Args:
            sample_variants: List of sample dicts with 'audio', 'root_note', 'sample_rate'
            target_pitch: Target MIDI note number
            duration: Duration in seconds
            velocity: Note velocity (0-1)
            
        Returns:
            Pitch-shifted audio
        """
        import random
        
        # Select a random variant for variety (weighted toward first for consistency)
        weights = [0.6, 0.25, 0.15][:len(sample_variants)]
        weights = [w / sum(weights) for w in weights]  # Normalize
        variant = random.choices(sample_variants, weights=weights)[0]
        
        audio = variant['audio'].copy()
        root_note = variant.get('root_note', 60)  # Default C4
        
        # Calculate pitch shift ratio
        # Higher ratio = higher pitch (more samples per second = faster playback)
        semitones = target_pitch - root_note
        shift_ratio = 2 ** (semitones / 12)
        
        # Calculate target length
        target_samples = int(duration * self.sample_rate)
        
        # Pitch shift by resampling
        if abs(shift_ratio - 1.0) > 0.001:  # Only if significant shift needed
            try:
                import librosa
                # Use librosa's resample for quality pitch shifting
                # To pitch UP, we need to resample DOWN (fewer samples = faster playback)
                shifted_sr = int(self.sample_rate / shift_ratio)
                audio = librosa.resample(audio, orig_sr=shifted_sr, target_sr=self.sample_rate)
            except ImportError:
                # Simple linear interpolation fallback
                new_len = int(len(audio) / shift_ratio)
                if new_len > 0:
                    audio = np.interp(
                        np.linspace(0, len(audio) - 1, new_len),
                        np.arange(len(audio)),
                        audio
                    )
        
        # Adjust to target duration
        if len(audio) > target_samples:
            # Truncate with fade out
            audio = audio[:target_samples]
            fade_len = min(int(0.05 * self.sample_rate), len(audio) // 4)
            if fade_len > 0:
                fade = np.linspace(1, 0, fade_len)
                audio[-fade_len:] *= fade
        elif len(audio) < target_samples:
            # Pad with zeros (one-shot samples)
            audio = np.pad(audio, (0, target_samples - len(audio)))
        
        # Apply velocity
        audio *= velocity
        
        return audio
    
    def _get_expansion_sample_for_program(
        self,
        program: int,
        freq: float,
        duration: float,
        velocity: float
    ) -> Optional[np.ndarray]:
        """
        Check if we have an expansion sample for this program number.
        
        Maps MIDI program numbers to instrument names and looks up in expansion cache.
        Uses InstrumentResolutionService if available, falls back to hardcoded mapping.
        Performs pitch-shifting if needed to match the requested frequency.
        """
        if not self._expansion_sample_cache:
            return None
        
        # Try InstrumentResolutionService first for dynamic mapping
        inst_name = None
        if self._instrument_service:
            inst_name = self._instrument_service.get_instrument_for_program(program)
        
        # Fallback to hardcoded mapping
        if not inst_name:
            program_to_instrument = {
                110: 'krar',
                111: 'masenqo',
                112: 'washint',
                113: 'begena',
                0: 'piano',
                4: 'piano',  # Electric piano
                25: 'guitar',
                38: 'bass',
                39: 'bass',
                80: 'synth', # Lead 1 (square)
                81: 'synth', # Lead 2 (sawtooth)
                87: 'synth', # Lead 8 (bass+lead)
            }
            inst_name = program_to_instrument.get(program)
        
        if not inst_name or inst_name not in self._expansion_sample_cache:
            return None
        
        # Get the sample
        sample = self._expansion_sample_cache[inst_name].copy()
        
        # Calculate required length
        target_samples = int(duration * self.sample_rate)
        
        # If sample is shorter than needed, we need to loop or extend
        if len(sample) < target_samples:
            # For one-shot samples, just pad with zeros
            sample = np.pad(sample, (0, target_samples - len(sample)))
        elif len(sample) > target_samples:
            # Truncate and apply fade out
            sample = sample[:target_samples]
            fade_len = min(int(0.05 * self.sample_rate), len(sample) // 4)
            if fade_len > 0:
                fade = np.linspace(1, 0, fade_len)
                sample[-fade_len:] *= fade
        
        # Apply velocity
        sample *= velocity
        
        return sample


# =============================================================================
# MAIN AUDIO RENDERER CLASS
# =============================================================================

class AudioRenderer:
    """
    Main audio rendering class.
    
    Handles MIDI-to-audio conversion with mixing, effects, and export.
    Now supports intelligent instrument selection via InstrumentLibrary,
    ExpansionManager for specialized instruments (Ethiopian, etc.),
    and BWF (Broadcast Wave Format) with AI provenance metadata.
    
    Synthesizer Architecture:
    - Accepts optional ISynthesizer for pluggable synth backends
    - Falls back to auto-detection via SynthesizerFactory
    - Maintains backward compatibility with existing code
    
    InstrumentResolutionService support:
    - Accepts optional InstrumentResolutionService for dynamic program-to-instrument mapping
    - Service bridges expansion instruments to the generation pipeline
    - Falls back to hardcoded mappings when service not available
    """
    
    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        use_fluidsynth: bool = True,
        soundfont_path: Optional[str] = None,
        require_soundfont: bool = False,
        instrument_library: 'InstrumentLibrary' = None,
        expansion_manager: 'ExpansionManager' = None,
        instrument_service: 'InstrumentResolutionService' = None,
        genre: str = None,
        mood: str = None,
        use_bwf: bool = True,
        ai_metadata: Optional[Dict] = None,
        tail_seconds: float = 2.0,
        synthesizer: Optional['ISynthesizer'] = None,
        parsed_instruments: list = None,  # NEW: Explicit instruments from prompt
    ):
        """
        Initialize AudioRenderer.
        
        Args:
            sample_rate: Output sample rate
            use_fluidsynth: Whether to prefer FluidSynth when available
            soundfont_path: Path to SoundFont file for FluidSynth
            require_soundfont: Fail if no SoundFont available
            instrument_library: Optional InstrumentLibrary for intelligent selection
            expansion_manager: Optional ExpansionManager for specialized instruments
            instrument_service: Optional InstrumentResolutionService for dynamic mapping
            genre: Target genre for instrument selection
            mood: Mood modifier for instrument selection
            use_bwf: Write BWF format with AI provenance metadata
            ai_metadata: Additional AI metadata for BWF
            tail_seconds: Extra seconds to add for reverb tail
            synthesizer: Optional ISynthesizer instance (overrides auto-detection)
        """
        self.sample_rate = sample_rate
        self.fluidsynth_available = check_fluidsynth_available()
        self.fluidsynth_version = get_fluidsynth_version() if self.fluidsynth_available else None
        self.use_fluidsynth = use_fluidsynth and self.fluidsynth_available
        self.soundfont_path = soundfont_path or find_soundfont()
        self.require_soundfont = require_soundfont
        self.instrument_library = instrument_library
        self.expansion_manager = expansion_manager
        self._instrument_service = instrument_service
        self.genre = genre
        self.mood = mood
        self.use_bwf = use_bwf
        self.ai_metadata = ai_metadata or {}
        self.tail_seconds = tail_seconds
        self._parsed_instruments = set(parsed_instruments) if parsed_instruments else set()

        self._last_render_report: Optional[Dict] = None
        self._pipeline_stages: Dict[str, str] = {}  # Sprint 10.5: Track which DSP stages fired

        # Convolution reverb for master bus (Sprint 7)
        self._reverb = ConvolutionReverb(sample_rate=sample_rate) if _HAS_CONVOLUTION_REVERB else None

        # Multiband dynamics for master bus (Sprint 7.5)
        # NOTE: We use the multiband_compress() convenience function in the
        # render pipeline (which creates its own MultibandDynamics per genre
        # preset). The flag is kept as the gate.
        # self._multiband is no longer stored — _HAS_MULTIBAND_DYNAMICS is the gate.

        # Spectral processing for master bus (Sprint 7.5)
        if _HAS_SPECTRAL_PROCESSING:
            self._resonance_suppressor = ResonanceSuppressor(
                SPECTRAL_PRESETS.get('harsh_tamer', ResonanceSuppressorParams()),
                sample_rate=sample_rate
            )
        else:
            self._resonance_suppressor = None
        # NOTE: Harmonic exciter is applied via apply_spectral_preset() in the
        # render pipeline (which selects the correct preset per genre).
        # No instance is stored — _HAS_SPECTRAL_PROCESSING is the gate.

        # Reference matching for master bus (Sprint 7.5) — dormant until profile provided
        self._reference_analyzer = ReferenceAnalyzer(sample_rate=sample_rate) if _HAS_REFERENCE_MATCHING else None
        self._reference_matcher = None  # Created via set_reference_profile()
        self._reference_profile = None

        # Per-stem track processor (Sprint 8)
        self._track_processor = TrackProcessor(sample_rate=sample_rate) if _HAS_TRACK_PROCESSOR else None

        # Mix policy panning (Sprint 8.4) — set via set_mix_policy()
        self._mix_policy = None

        # Production preset values (Sprint 8.7) — set via set_preset_values()
        self._preset_values: dict = {}

        # Initialize mix chains
        self.mix_chains = {
            'drums': create_drum_bus_chain(),
            'master': create_master_chain(),
            'lofi': create_lofi_chain(),
            'bass': create_bass_chain(),
        }
        
        # Synthesizer abstraction layer
        # Use provided synthesizer or auto-detect via factory
        if synthesizer is not None:
            self.synthesizer = synthesizer
        else:
            # Auto-detect best available synthesizer
            from .synthesizers import SynthesizerFactory
            self.synthesizer = SynthesizerFactory.get_best_available(
                prefer_soundfont=use_fluidsynth,
                sample_rate=sample_rate,
                soundfont_path=soundfont_path,
                instrument_library=instrument_library,
                expansion_manager=expansion_manager,
                genre=genre,
                mood=mood
            )
        
        # Procedural fallback with optional instrument library and expansion manager
        # Kept for backward compatibility and direct track rendering
        self.procedural = ProceduralRenderer(
            sample_rate,
            instrument_library=instrument_library,
            expansion_manager=expansion_manager,
            instrument_service=instrument_service,
            genre=genre,
            mood=mood,
            parsed_instruments=parsed_instruments,  # Pass instruments for Ethiopian detection
        )
    
    def set_instrument_library(
        self,
        library: 'InstrumentLibrary',
        genre: str = None,
        mood: str = None
    ):
        """
        Update the instrument library and reload instruments.
        
        Args:
            library: InstrumentLibrary with analyzed samples
            genre: Target genre for intelligent selection
            mood: Mood modifier for selection
        """
        self.instrument_library = library
        self.genre = genre or self.genre
        self.mood = mood or self.mood
        
        # Recreate procedural renderer with new library
        self.procedural = ProceduralRenderer(
            self.sample_rate,
            instrument_library=library,
            expansion_manager=self.expansion_manager,
            instrument_service=self._instrument_service,
            genre=self.genre,
            mood=self.mood
        )
        
        # Update synthesizer if it supports configuration
        if self.synthesizer is not None:
            self.synthesizer.configure(
                instrument_library=library,
                genre=self.genre,
                mood=self.mood
            )
    
    def get_synthesizer_info(self) -> Dict:
        """
        Get information about the current synthesizer.
        
        Returns:
            Dict with synthesizer details and capabilities
        """
        if self.synthesizer is None:
            return {
                'name': 'None',
                'available': False,
                'capabilities': {},
            }
        return self.synthesizer.get_info()
    
    def set_synthesizer(self, synthesizer: 'ISynthesizer') -> None:
        """
        Set a custom synthesizer backend.
        
        Args:
            synthesizer: ISynthesizer instance to use
        """
        self.synthesizer = synthesizer
    
    def set_reference_profile(self, profile) -> None:
        """Store a reference profile to activate reference matching in the render pipeline.

        Args:
            profile: A ReferenceProfile object (from reference_matching module).
                     Pass None to deactivate reference matching.
        """
        self._reference_profile = profile
        if _HAS_REFERENCE_MATCHING and profile is not None:
            self._reference_matcher = ReferenceMatcher(profile, sample_rate=self.sample_rate)
        else:
            self._reference_matcher = None

    def set_mix_policy(self, mix_policy) -> None:
        """Store a MixPolicy to use genre-specific panning in the render pipeline.

        Args:
            mix_policy: A MixPolicy object (from style_policy module).
                        Pass None to use default hardcoded panning.
        """
        self._mix_policy = mix_policy

    def set_preset_values(self, preset_values: dict) -> None:
        """Store production preset values to influence the render pipeline.

        Args:
            preset_values: Dict of preset field→value pairs from PresetManager.
                           Keys include humanize_amount, velocity_range, accent_strength, etc.
                           Pass None or {} to use defaults.
        """
        self._preset_values = preset_values or {}

    def _get_preset_target_rms(self) -> float:
        """Compute target RMS based on preset values.

        Returns 0.25 (default) when no preset is active.
        """
        target = 0.25
        if self._preset_values:
            try:
                _ha = self._preset_values.get('humanize_amount')
                if _ha is not None:
                    # More humanized/rough → slightly lower RMS; polished → higher
                    # Range: 0.16 (ha=1.0) to 0.30 (ha=0.0)
                    target = 0.30 - 0.14 * max(0.0, min(1.0, float(_ha)))
            except Exception:
                pass
        return target

    def _get_preset_reverb_send(self) -> float:
        """Compute reverb send level based on preset values.

        Returns 0.15 (default) when no preset is active.
        """
        send = 0.15
        if self._preset_values:
            try:
                _ha = self._preset_values.get('humanize_amount')
                if _ha is not None:
                    send = 0.10 + 0.12 * max(0.0, min(1.0, float(_ha)))
                _ti = self._preset_values.get('tension_intensity')
                if _ti is not None:
                    send = min(0.30, send + 0.05 * max(0.0, min(1.0, float(_ti))))
            except Exception:
                pass
        return send

    def _normalize_genre(self) -> str:
        """Normalize genre string for consistent lookup across pipeline blocks.

        Returns lowercase, underscore-separated genre string.
        Handles None, hyphens, and spaces.
        """
        return (self.genre or '').lower().replace(' ', '_').replace('-', '_')

    def _compute_pan(self, name: str, is_drums: bool, index: int) -> float:
        """Compute panning value for a track.

        Args:
            name: Track name
            is_drums: Whether this is a drum track (MIDI ch9)
            index: Track index for alternating spread

        Returns:
            Pan value from -1.0 (left) to 1.0 (right)
        """
        if is_drums:
            # Sprint 10.2: Per-drum-element panning from MixPolicy
            # NOTE: MIDI ch9 is a single track — can't pan individual drum elements
            # without per-note stem separation. For mixed drum bus, honor hihat_pan
            # as a slight stereo offset for variety.
            if self._mix_policy:
                _hihat_pan = getattr(self._mix_policy, 'hihat_pan', 0.0)
                return _hihat_pan * 0.3  # Subtle offset, not full pan
            return 0
        name_lower = (name or '').lower()
        if self._mix_policy:
            if 'bass' in name_lower or '808' in name_lower:
                return getattr(self._mix_policy, 'bass_pan', 0.0)
            if 'kick' in name_lower:
                return getattr(self._mix_policy, 'kick_pan', 0.0)
            if 'snare' in name_lower:
                return getattr(self._mix_policy, 'snare_pan', 0.0)
            if 'hihat' in name_lower or 'hi-hat' in name_lower or 'hi_hat' in name_lower:
                return getattr(self._mix_policy, 'hihat_pan', 0.0)
            return 0.2 if index % 2 == 0 else -0.2
        return 0.2 if index % 2 == 0 else -0.2
    
    def render_midi_file(
        self,
        midi_path: str,
        output_path: str,
        parsed: Optional[ParsedPrompt] = None
    ) -> bool:
        """
        Render MIDI file to audio.
        
        Args:
            midi_path: Path to input MIDI file
            output_path: Path for output WAV file
            parsed: Optional parsed prompt for additional processing
        
        Returns:
            True if successful
        """
        # Update genre/mood from parsed prompt if available
        if parsed:
            new_genre = parsed.genre if parsed.genre else self.genre
            new_mood = parsed.mood if parsed.mood else self.mood
            
            if new_genre != self.procedural.genre or new_mood != self.procedural.mood:
                self.procedural.set_genre_mood(new_genre, new_mood)
        
        warnings: List[str] = []

        if self.require_soundfont:
            if not self.fluidsynth_available:
                warnings.append("FluidSynth not available but --require-soundfont enabled")
            if not self.soundfont_path:
                warnings.append("No SoundFont (.sf2) found but --require-soundfont enabled")

            if warnings:
                self._last_render_report = self._build_render_report(
                    midi_path=midi_path,
                    output_path=output_path,
                    parsed=parsed,
                    renderer_path="none",
                    fluidsynth_allowed=bool(self.use_fluidsynth and self.soundfont_path),
                    fluidsynth_attempted=False,
                    fluidsynth_success=False,
                    fluidsynth_skip_reason="require_soundfont",
                    warnings=warnings,
                )
                return False

        custom_drums_loaded = len(getattr(self.procedural, '_custom_drum_cache', {}) or {})
        has_ethiopian = getattr(self.procedural, '_has_ethiopian_instruments', False)

        fluidsynth_allowed = bool(self.use_fluidsynth and self.soundfont_path)
        fluidsynth_skip_reason: Optional[str] = None
        fluidsynth_attempted = False
        fluidsynth_success = False

        # Try FluidSynth first (only if no custom drums loaded AND no Ethiopian instruments)
        if fluidsynth_allowed and custom_drums_loaded == 0 and not has_ethiopian:
            fluidsynth_attempted = True
            fluidsynth_success = render_midi_with_fluidsynth(
                midi_path,
                output_path,
                self.soundfont_path,
                self.sample_rate
            )

            if fluidsynth_success:
                if parsed:
                    self._post_process(output_path, parsed)

                self._last_render_report = self._build_render_report(
                    midi_path=midi_path,
                    output_path=output_path,
                    parsed=parsed,
                    renderer_path="fluidsynth",
                    fluidsynth_allowed=fluidsynth_allowed,
                    fluidsynth_attempted=True,
                    fluidsynth_success=True,
                    fluidsynth_skip_reason=fluidsynth_skip_reason,
                    warnings=warnings,
                )
                return True

            warnings.append("FluidSynth render failed; falling back to procedural")
        elif fluidsynth_allowed and has_ethiopian:
            warnings.append(
                "FluidSynth skipped because Ethiopian instruments requested - using procedural synthesis"
            )
            fluidsynth_skip_reason = "ethiopian_instruments"
        elif fluidsynth_allowed and custom_drums_loaded > 0:
            warnings.append(
                f"FluidSynth skipped because custom drum samples are loaded (count={custom_drums_loaded})"
            )
            fluidsynth_skip_reason = f"custom_drums_loaded:{custom_drums_loaded}"
        elif self.use_fluidsynth and not self.soundfont_path:
            warnings.append("FluidSynth available but no SoundFont (.sf2) found; using procedural")
            fluidsynth_skip_reason = "no_soundfont"
        elif not self.fluidsynth_available:
            warnings.append("FluidSynth not available; using procedural")
            fluidsynth_skip_reason = "not_available"
        elif not self.use_fluidsynth:
            fluidsynth_skip_reason = "disabled"

        # Fall back to procedural rendering (uses custom instruments if available)
        procedural_success = self._render_procedural(midi_path, output_path, parsed)
        self._last_render_report = self._build_render_report(
            midi_path=midi_path,
            output_path=output_path,
            parsed=parsed,
            renderer_path="procedural" if procedural_success else "none",
            fluidsynth_allowed=fluidsynth_allowed,
            fluidsynth_attempted=fluidsynth_attempted,
            fluidsynth_success=fluidsynth_success,
            fluidsynth_skip_reason=fluidsynth_skip_reason,
            warnings=warnings,
        )
        return procedural_success

    def _build_render_report(
        self,
        midi_path: str,
        output_path: str,
        parsed: Optional[ParsedPrompt],
        renderer_path: str,
        fluidsynth_allowed: bool,
        fluidsynth_attempted: bool,
        fluidsynth_success: bool,
        fluidsynth_skip_reason: Optional[str],
        warnings: List[str],
    ) -> Dict:
        """Build a stable diagnostics payload for this render."""
        # Instrument library stats (best-effort, keep it robust)
        instrument_stats: Dict[str, object] = {
            "loaded": self.instrument_library is not None,
            "total_instruments": None,
            "categories": None,
            "sources": None,
        }
        if self.instrument_library is not None:
            try:
                instrument_stats["total_instruments"] = len(getattr(self.instrument_library, 'instruments', []) or [])
            except Exception:
                pass
            try:
                if hasattr(self.instrument_library, 'list_categories'):
                    instrument_stats["categories"] = self.instrument_library.list_categories()
            except Exception:
                pass
            try:
                if hasattr(self.instrument_library, 'get_source_summary'):
                    instrument_stats["sources"] = self.instrument_library.get_source_summary()
            except Exception:
                pass

        # Expansion stats
        expansion_stats: Dict[str, object] = {
            "loaded": self.expansion_manager is not None,
            "count": None,
            "expansions": None,
            "categories": None,
        }
        if self.expansion_manager is not None:
            try:
                if hasattr(self.expansion_manager, 'list_expansions'):
                    expansion_stats["expansions"] = self.expansion_manager.list_expansions()
                    expansion_stats["count"] = len(expansion_stats["expansions"]) if expansion_stats["expansions"] else 0
            except Exception:
                pass
            try:
                if hasattr(self.expansion_manager, 'get_categories'):
                    expansion_stats["categories"] = self.expansion_manager.get_categories()
            except Exception:
                pass

        custom_drums_loaded = len(getattr(self.procedural, '_custom_drum_cache', {}) or {})
        custom_melodic_loaded = {}
        try:
            melodic_cache = getattr(self.procedural, '_custom_melodic_cache', {}) or {}
            custom_melodic_loaded = {k: len(v) for k, v in melodic_cache.items()}
        except Exception:
            custom_melodic_loaded = {}

        prompt_meta = {
            "genre": getattr(parsed, 'genre', None) if parsed else self.genre,
            "bpm": getattr(parsed, 'bpm', None) if parsed else None,
            "key": getattr(parsed, 'key', None) if parsed else None,
        }

        report = {
            "schema_version": 1,
            "renderer_path": renderer_path,
            "midi_path": midi_path,
            "output_path": output_path,
            "prompt_meta": prompt_meta,
            "fluidsynth": {
                "available": bool(self.fluidsynth_available),
                "version": self.fluidsynth_version,
                "enabled": bool(self.use_fluidsynth),
                "allowed": bool(fluidsynth_allowed),
                "attempted": bool(fluidsynth_attempted),
                "success": bool(fluidsynth_success),
                "skip_reason": fluidsynth_skip_reason,
            },
            "soundfont_path": self.soundfont_path,
            "require_soundfont": bool(self.require_soundfont),
            "custom_audio": {
                "custom_drums_loaded": custom_drums_loaded,
                "custom_melodic_loaded": custom_melodic_loaded,
            },
            "instrument_library": instrument_stats,
            "expansions": expansion_stats,
            "warnings": warnings,
            "production_preset": {
                "preset_values": getattr(self, '_preset_values', None),
                "target_rms": self._get_preset_target_rms() if hasattr(self, '_get_preset_target_rms') else None,
                "reverb_send": self._get_preset_reverb_send() if hasattr(self, '_get_preset_reverb_send') else None,
            },
            "mix_policy": {
                "active": bool(getattr(self, '_mix_policy', None)),
                "saturation_type": getattr(self._mix_policy, 'saturation_type', None) if getattr(self, '_mix_policy', None) else None,
                "saturation_amount": getattr(self._mix_policy, 'saturation_amount', None) if getattr(self, '_mix_policy', None) else None,
                "brightness_target": getattr(self._mix_policy, 'brightness_target', None) if getattr(self, '_mix_policy', None) else None,
                "warmth_target": getattr(self._mix_policy, 'warmth_target', None) if getattr(self, '_mix_policy', None) else None,
                "drum_bus_fx": getattr(self._mix_policy, 'drum_bus_fx', None) if getattr(self, '_mix_policy', None) else None,
                "bass_fx": getattr(self._mix_policy, 'bass_fx', None) if getattr(self, '_mix_policy', None) else None,
                "master_fx_chain": getattr(self._mix_policy, 'master_fx_chain', None) if getattr(self, '_mix_policy', None) else None,
            },
            "genre_normalized": self._normalize_genre() if hasattr(self, '_normalize_genre') else None,
            "pipeline_stages": dict(getattr(self, '_pipeline_stages', {})),
        }

        # Sprint 10.4: Add LUFS estimate from rendered audio (if available)
        try:
            import os
            if output_path and os.path.exists(output_path):
                from scipy.io import wavfile as _wf
                _sr, _audio = _wf.read(output_path)
                _audio_f = _audio.astype(float) / (32768.0 if _audio.dtype == np.int16 else 1.0)
                if len(_audio_f.shape) > 1:
                    _audio_f = np.mean(_audio_f, axis=1)
                report["estimated_lufs"] = round(estimate_lufs(_audio_f, _sr), 1)
                report["peak_dbfs"] = round(20 * np.log10(max(np.max(np.abs(_audio_f)), 1e-10)), 1)
        except Exception:
            pass

        return report

    def get_last_render_report(self) -> Optional[Dict]:
        """Return the most recent render report (if any)."""
        return self._last_render_report

    def write_last_render_report(self, report_path: str) -> bool:
        """Write the most recent render report to a JSON file."""
        if not self._last_render_report:
            return False

        try:
            os.makedirs(os.path.dirname(report_path) or '.', exist_ok=True)
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(self._last_render_report, f, indent=2)
            return True
        except Exception:
            return False
    
    def _get_chain_for_track(self, track_name: str, is_drums: bool) -> Optional[MixChain]:
        """Get appropriate mix chain for a track."""
        if is_drums:
            return self.mix_chains.get('drums')
        
        # Check for other roles based on name
        name_lower = (track_name or '').lower()
        if 'bass' in name_lower or '808' in name_lower:
            # Sprint 9.3: Activate bass chain; Sprint 10.3: modulate sub boost from policy
            _bass_chain = self.mix_chains.get('bass')
            if _bass_chain and self._mix_policy:
                try:
                    _sub_target = getattr(self._mix_policy, 'sub_bass_target', 0.5)
                    # Scale the sub EQ boost: 0.5→+2dB (default), 0.8→+4dB, 0.2→+0dB
                    _sub_boost_db = max(0.0, (_sub_target - 0.2) * 6.67)  # 0.2→0, 0.5→2, 0.8→4, 1.0→5.3
                    if hasattr(_bass_chain, 'effects') and len(_bass_chain.effects) > 0:
                        _first_fx = _bass_chain.effects[0]
                        _fx_params = _first_fx[1] if isinstance(_first_fx, tuple) else _first_fx
                        if hasattr(_fx_params, 'bands'):
                            for band in _fx_params.bands:
                                if isinstance(band, dict) and band.get('frequency') == 60:
                                    band['gain_db'] = round(_sub_boost_db, 1)
                except Exception:
                    pass
            return _bass_chain
        
        _genre_lower = self._normalize_genre()
        if 'lofi' in _genre_lower and ('piano' in name_lower or 'keys' in name_lower):
            return self.mix_chains.get('lofi')
            
        return None
    
    def _infer_program_from_track_name(self, track_name: str) -> Optional[int]:
        """
        Infer MIDI program number from track name.
        
        This ensures different tracks get different sounds even when the MIDI
        file doesn't include program change messages.
        
        Returns:
            MIDI program number (0-127) or None if unknown
        """
        name = track_name.lower()
        
        # Bass instruments (programs 32-39)
        if 'bass' in name:
            return 38  # Synth Bass 1
        
        # Lead/Melody instruments (programs 80-87 - synth leads)
        if 'lead' in name or 'melody' in name:
            return 81  # Lead 2 (sawtooth)
        
        # Chord/Pad instruments (programs 88-95 - synth pads)
        if 'chord' in name or 'pad' in name:
            return 89  # Pad 2 (warm)
        
        # Keys/Piano (programs 0-7)
        if 'piano' in name or 'keys' in name:
            return 4  # Electric Piano 1
        
        # Synth (programs 80-87)
        if 'synth' in name:
            return 81  # Lead 2 (sawtooth)
        
        # Brass (programs 56-63)
        if 'brass' in name or 'horn' in name:
            return 61  # Brass Section
        
        # Strings (programs 40-47)
        if 'string' in name:
            return 48  # String Ensemble
        
        # Guitar (programs 24-31)
        if 'guitar' in name:
            return 25  # Acoustic Guitar (steel)
        
        # Organ (programs 16-23)
        if 'organ' in name:
            return 16  # Drawbar Organ
        
        return None

    def _render_procedural(
        self,
        midi_path: str,
        output_path: str,
        parsed: Optional[ParsedPrompt] = None
    ) -> bool:
        """Render MIDI using procedural synthesis."""
        import mido
        
        try:
            midi = mido.MidiFile(midi_path)
        except Exception:
            return False
        
        # Calculate total duration
        total_seconds = midi.length
        total_samples = int(total_seconds * self.sample_rate) + int(self.tail_seconds * self.sample_rate)
        
        # Render each track
        tracks_audio = []
        track_infos = []  # (name, is_drums) for each track
        
        for track in midi.tracks:
            # Detect if drum track
            is_drums = any(
                hasattr(msg, 'channel') and msg.channel == 9 
                for msg in track if msg.type == 'note_on'
            )
            
            track_audio = self._render_track_procedural(
                track,
                midi.ticks_per_beat,
                total_samples
            )
            if track_audio is not None:
                tracks_audio.append(track_audio)
                track_infos.append((track.name, is_drums))
        
        if not tracks_audio:
            return False
        
        # RMS-based mixing for balanced sound
        # Calculate RMS for each track
        rms_values = [np.sqrt(np.mean(audio**2)) for audio in tracks_audio]
        
        # Target RMS levels for hot, modern mix
        # Increased from 0.15 to 0.25 for more punch
        # Sprint 8.7: Let production presets influence target RMS
        target_rms = self._get_preset_target_rms()
        
        stereo_tracks = []
        for i, (audio, (name, is_drums)) in enumerate(zip(tracks_audio, track_infos)):
            # Apply track FX chain
            chain = self._get_chain_for_track(name, is_drums)
            if chain:
                audio = chain.process(audio, self.sample_rate)

            # Per-stem channel strip processing (Sprint 8)
            _track_process_genres = {'trap', 'drill', 'boom_bap', 'house', 'phonk', 'edm', 'lofi', 'lo_fi', 'hip_hop', 'rnb', 'g_funk'}
            _genre_norm = self._normalize_genre()
            if self._track_processor and _HAS_TRACK_PROCESSOR and _genre_norm in _track_process_genres:
                try:
                    if is_drums:
                        _stem_preset = {
                            'trap': 'punchy_kick', 'drill': 'punchy_kick',
                            'boom_bap': 'boom_bap_drums',
                            'house': 'punchy_kick', 'phonk': 'punchy_kick',
                            'edm': 'punchy_kick',
                        }.get(_genre_norm, 'boom_bap_drums')
                    else:
                        name_lower = (name or '').lower()
                        if 'bass' in name_lower or '808' in name_lower:
                            _stem_preset = {
                                'trap': 'trap_808', 'drill': 'trap_808',
                                'boom_bap': 'boom_bap_bass', 'phonk': 'trap_808',
                                'edm': 'trap_808',
                            }.get(_genre_norm, 'clean_bass')
                        elif 'pad' in name_lower:
                            _stem_preset = 'warm_pad'
                        elif 'lead' in name_lower or 'melody' in name_lower:
                            _stem_preset = 'bright_synth'
                        else:
                            _stem_preset = {
                                'lofi': 'lofi_keys', 'lo_fi': 'lofi_keys',
                            }.get(_genre_norm, 'bright_synth')
                    
                    if _stem_preset in TRACK_PRESETS:
                        audio = self._track_processor.process_with_preset(audio, _stem_preset)
                except Exception:
                    pass  # Graceful degradation

            rms = calculate_rms(audio)
            
            if rms > 0.001:  # Avoid division by zero
                if is_drums:
                    # Drums at -3dB relative to melodic (was -6dB, too quiet)
                    target = target_rms * 0.7
                    gain = target / rms
                else:
                    # Melodic at full level
                    gain = target_rms / rms
                
                # Limit gain to avoid extreme amplification
                gain = min(gain, 4.0)  # Max +12dB
                # Sprint 8.7: Respect MixPolicy stem headroom when available
                if self._mix_policy:
                    try:
                        _headroom_db = getattr(self._mix_policy, 'stem_headroom_db', -6.0)
                        # Convert headroom to max allowed peak: target_rms * headroom_factor
                        # -6dB headroom means peak can be ~2x (6dB above) target
                        _headroom_linear = 10 ** (-_headroom_db / 20.0)  # -6dB → 2.0, -3dB → 1.41
                        # NOTE: This cap interacts with preset-driven target_rms. At -6dB headroom,
                        # quiet tracks may not reach target. This is intentional — headroom preserves
                        # dynamic range at the expense of level targeting.
                        gain = min(gain, _headroom_linear)
                    except Exception:
                        pass
                audio = audio * gain
            
            # Apply panning — use MixPolicy if available, else default spread (Sprint 8.4)
            # NOTE: Drum tracks (MIDI ch9) always center. Per-drum-instrument panning
            # requires per-note stem separation — future enhancement.
            pan = self._compute_pan(name, is_drums, i)
            stereo = apply_stereo_pan(audio, pan)
            stereo_tracks.append(stereo)

        # Sidechain ducking for bass tracks (Sprint 8)
        # Duck bass when kick/808 hits for that pumping effect
        _sidechain_genres = {'trap', 'drill', 'house', 'edm', 'hip_hop', 'phonk'}
        if self._normalize_genre() in _sidechain_genres:
            try:
                kick_idx = None
                bass_indices = []
                for idx, (name, is_drums) in enumerate(track_infos):
                    name_lower = (name or '').lower()
                    if is_drums:
                        kick_idx = idx  # Use drum track as sidechain trigger
                    elif 'bass' in name_lower or '808' in name_lower:
                        bass_indices.append(idx)

                if kick_idx is not None and bass_indices:
                    # Extract mono trigger from kick/drum track
                    kick_audio = stereo_tracks[kick_idx]
                    if len(kick_audio.shape) > 1:
                        trigger = np.mean(kick_audio, axis=-1)
                    else:
                        trigger = kick_audio

                    for bi in bass_indices:
                        bass_audio = stereo_tracks[bi]
                        if len(bass_audio.shape) > 1:
                            # Process each channel
                            for ch in range(bass_audio.shape[-1]):
                                min_len = min(len(trigger), len(bass_audio[:, ch]))
                                bass_audio[:min_len, ch] = apply_sidechain_ducking(
                                    bass_audio[:min_len, ch], trigger[:min_len],
                                    attack_ms=5.0, release_ms=100.0, ratio=6.0, threshold=0.3
                                )
                        else:
                            min_len = min(len(trigger), len(bass_audio))
                            bass_audio[:min_len] = apply_sidechain_ducking(
                                bass_audio[:min_len], trigger[:min_len],
                                attack_ms=5.0, release_ms=100.0, ratio=6.0, threshold=0.3
                            )
                        stereo_tracks[bi] = bass_audio
            except Exception:
                self._pipeline_stages['sidechain_ducking'] = 'error'

        mix = mix_stereo_tracks(stereo_tracks)

        # Sprint 10.5: Reset pipeline stage tracking for this render
        self._pipeline_stages = {}
        
        # Apply master bus processing
        master_chain = self.mix_chains.get('master')
        if master_chain:
            mix = master_chain.process(mix, self.sample_rate)

        # Convolution reverb send (Sprint 7)
        if self._reverb and _HAS_CONVOLUTION_REVERB:
            try:
                genre_reverb_map = {
                    'jazz': 'hall', 'classical': 'hall', 'ambient': 'hall',
                    'trap': 'room', 'drill': 'room', 'hip_hop': 'room',
                    'lofi': 'lofi_room', 'lo_fi': 'lofi_room',
                    'house': 'plate', 'rock': 'plate', 'funk': 'plate',
                    'ethiopian': 'room', 'ethio_jazz': 'hall',
                }
                preset = genre_reverb_map.get(self._normalize_genre(), 'room')
                # Pure wet signal for send mixing
                reverb_cfg = ReverbConfig(wet_dry=1.0)
                wet = self._reverb.process(mix, preset=preset, config=reverb_cfg)
                # Sprint 8.7: Let production presets influence reverb send
                send_level = self._get_preset_reverb_send()
                # Sprint 9.7: Modulate reverb send with warmth target
                if self._mix_policy:
                    try:
                        _warmth = getattr(self._mix_policy, 'warmth_target', 0.5)
                        send_level *= (0.8 + 0.4 * _warmth)  # 0.5→1.0x, 0.8→1.12x, 0.2→0.88x
                    except Exception:
                        pass
                if wet is not None and len(wet) > 0:
                    # Trim/pad to match mix length
                    if len(wet) > len(mix):
                        wet = wet[:len(mix)]
                    elif len(wet) < len(mix):
                        pad_shape = [(0, len(mix) - len(wet))]
                        if len(wet.shape) > 1:
                            pad_shape.append((0, 0))
                        wet = np.pad(wet, pad_shape)
                    mix = mix + wet * send_level
                    self._pipeline_stages['convolution_reverb'] = preset
            except Exception:
                self._pipeline_stages['convolution_reverb'] = 'error'

        # Multiband dynamics on master bus (Sprint 7.5)
        if _HAS_MULTIBAND_DYNAMICS:
            try:
                _genre_mb_map = {
                    'trap': 'loudness_maximize', 'drill': 'loudness_maximize',
                    'lofi': 'gentle_control', 'lo_fi': 'gentle_control',
                    'ambient': 'gentle_control',
                }
                _mb_preset = _genre_mb_map.get(self._normalize_genre(), 'mastering_glue')
                mix = multiband_compress(mix, preset=_mb_preset, sample_rate=self.sample_rate)
                self._pipeline_stages['multiband_dynamics'] = _mb_preset
            except Exception:
                self._pipeline_stages['multiband_dynamics'] = 'error'

        # Spectral processing (Sprint 7.5) — resonance suppression + harmonic excitement
        if _HAS_SPECTRAL_PROCESSING and self._resonance_suppressor:
            try:
                # Step 1: Suppress harsh resonances / de-essing
                mix = self._resonance_suppressor.process(mix)
                # Step 2: Harmonic exciter — genre-appropriate preset
                _genre_exciter_map = {
                    'trap': 'tape_warmth', 'drill': 'tape_warmth',
                    'lofi': 'analog_warmth', 'lo_fi': 'analog_warmth',
                    'jazz': 'master_air', 'house': 'master_air',
                    'classical': 'master_air', 'ambient': 'master_air',
                }
                _exciter_preset = _genre_exciter_map.get(
                    self._normalize_genre(), 'radio_ready'
                )
                # Sprint 9.2: Let MixPolicy saturation influence exciter choice
                if self._mix_policy:
                    try:
                        _sat_type = getattr(self._mix_policy, 'saturation_type', 'tape')
                        _sat_amt = getattr(self._mix_policy, 'saturation_amount', 0.2)
                        if _sat_type == 'tube' and _sat_amt > 0.3:
                            _exciter_preset = 'analog_warmth'
                        elif _sat_type == 'tape' and _sat_amt > 0.3:
                            _exciter_preset = 'tape_warmth'
                        elif _sat_type == 'digital' and _sat_amt < 0.15:
                            _exciter_preset = 'master_air'
                    except Exception:
                        pass
                    # Sprint 9.7: Brightness target biases exciter toward air or warmth
                    try:
                        _bright = getattr(self._mix_policy, 'brightness_target', 0.5)
                        if _bright > 0.7:
                            _exciter_preset = 'master_air'
                        elif _bright < 0.3:
                            _exciter_preset = 'tape_warmth'
                    except Exception:
                        pass
                mix = apply_spectral_preset(mix, _exciter_preset, sample_rate=self.sample_rate)
                self._pipeline_stages['spectral_processing'] = _exciter_preset
            except Exception:
                self._pipeline_stages['spectral_processing'] = 'error'

        # Reference matching (Sprint 7.5) — activated when reference_profile is supplied
        if _HAS_REFERENCE_MATCHING and self._reference_matcher:
            try:
                if getattr(self, '_reference_profile', None) is not None:
                    mix = self._reference_matcher.process(mix)
                    self._pipeline_stages['reference_matching'] = 'active'
            except Exception:
                self._pipeline_stages['reference_matching'] = 'error'

        # Soft clip to prevent harsh distortion
        mix = soft_clip(mix, threshold=0.7)
        
        # Normalize to louder level - 0.95 peak for modern loudness expectations
        # Previous 0.85 was too quiet for pleasant listening
        # Sprint 8.7: Respect MixPolicy master_ceiling_db when available
        _norm_target = 0.95
        if self._mix_policy:
            try:
                _ceil_db = getattr(self._mix_policy, 'master_ceiling_db', -1.0)
                _norm_target = min(0.98, max(0.5, 10 ** (_ceil_db / 20.0)))
            except Exception:
                pass
        mix = normalize_audio(mix, _norm_target)
        mix = limit_audio(mix, TARGET_TRUE_PEAK)
        
        # Save with BWF format if enabled
        # Master bit-depth policy: 16-bit with TPDF dither for delivery
        if self.use_bwf:
            try:
                from .bwf_writer import save_wav_with_ai_provenance
                
                # Prepare AI metadata
                ai_metadata = self.ai_metadata.copy()
                if parsed:
                    ai_metadata.update({
                        'prompt': getattr(parsed, 'prompt', ''),
                        'bpm': parsed.bpm,
                        'key': parsed.key,
                        'genre': parsed.genre,
                    })
                
                save_wav_with_ai_provenance(
                    mix,
                    output_path,
                    ai_metadata=ai_metadata,
                    sample_rate=self.sample_rate,
                    description=f"AI-generated music: {parsed.genre if parsed else 'unknown'} at {parsed.bpm if parsed else 0} BPM",
                    bit_depth=16  # Master delivery format
                )
            except Exception as e:
                # Fall back to standard WAV if BWF fails
                print(f"BWF save failed, falling back to standard WAV: {e}")
                save_wav(mix, output_path, self.sample_rate, stereo=True, 
                        bit_depth=16, apply_dither=True)
        else:
            # Standard master: 16-bit with dither
            save_wav(mix, output_path, self.sample_rate, stereo=True,
                    bit_depth=16, apply_dither=True)
        
        # Post-process
        if parsed:
            self._post_process(output_path, parsed)
        
        return True
    
    def _render_track_procedural(
        self,
        track,
        ticks_per_beat: int,
        total_samples: int
    ) -> Optional[np.ndarray]:
        """Render a single MIDI track using procedural synthesis."""
        import mido
        
        notes: List[SynthNote] = []
        current_tick = 0
        current_program = 0
        is_drum_track = False
        
        # Infer program from track name for better instrument selection
        # This ensures different tracks get different sounds even without program changes
        track_name_lower = track.name.lower() if track.name else ""
        inferred_program = self._infer_program_from_track_name(track_name_lower)
        if inferred_program is not None:
            current_program = inferred_program
        
        # Tempo (default 120 BPM)
        tempo = 500000  # microseconds per beat
        
        # Collect note events
        pending_notes: Dict[int, Tuple[int, int]] = {}  # pitch -> (start_tick, velocity)
        
        for msg in track:
            current_tick += msg.time
            
            if msg.type == 'set_tempo':
                tempo = msg.tempo
            
            elif msg.type == 'program_change':
                current_program = msg.program
            
            elif msg.type == 'note_on' and msg.velocity > 0:
                # Check if drum channel (channel 9 in 0-indexed)
                if hasattr(msg, 'channel') and msg.channel == 9:
                    is_drum_track = True
                
                pending_notes[msg.note] = (current_tick, msg.velocity)
            
            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                if msg.note in pending_notes:
                    start_tick, velocity = pending_notes.pop(msg.note)
                    duration_ticks = current_tick - start_tick
                    
                    # Convert to samples
                    us_per_tick = tempo / ticks_per_beat
                    start_us = start_tick * us_per_tick
                    duration_us = duration_ticks * us_per_tick
                    
                    start_sample = int(start_us / 1_000_000 * self.sample_rate)
                    duration_samples = int(duration_us / 1_000_000 * self.sample_rate)
                    
                    notes.append(SynthNote(
                        pitch=msg.note,
                        start_sample=start_sample,
                        duration_samples=max(duration_samples, 100),
                        velocity=velocity / 127.0,
                        channel=msg.channel if hasattr(msg, 'channel') else 0,
                        program=current_program,
                    ))
        
        if not notes:
            return None
        
        return self.procedural.render_notes(notes, total_samples, is_drum_track)
    
    def _post_process(self, audio_path: str, parsed: ParsedPrompt):
        """Apply post-processing based on prompt parameters."""
        # Load audio
        if HAS_SOUNDFILE:
            audio, sr = sf.read(audio_path)
        else:
            # Basic WAV reading fallback
            return
        
        modified = False
        
        # Add textures
        if 'vinyl' in parsed.textures:
            duration = len(audio) / sr
            vinyl = generate_vinyl_crackle(duration, density=0.3)
            if len(vinyl) > len(audio):
                vinyl = vinyl[:len(audio)]
            elif len(vinyl) < len(audio):
                vinyl = np.pad(vinyl, (0, len(audio) - len(vinyl)))
            
            # Mix vinyl at low level
            vinyl_stereo = apply_stereo_pan(vinyl, 0)
            vinyl_stereo = apply_gain(vinyl_stereo, -18)  # -18dB
            
            if len(audio.shape) == 1:
                audio = apply_stereo_pan(audio, 0)
            
            audio = audio + vinyl_stereo
            modified = True
        
        if 'rain' in parsed.textures:
            duration = len(audio) / sr
            rain = generate_rain(duration, intensity=0.4)
            if len(rain) > len(audio):
                rain = rain[:len(audio)]
            elif len(rain) < len(audio):
                rain = np.pad(rain, (0, len(audio) - len(rain)))
            
            rain_stereo = apply_stereo_pan(rain, 0)
            rain_stereo = apply_gain(rain_stereo, -15)  # -15dB
            
            if len(audio.shape) == 1:
                audio = apply_stereo_pan(audio, 0)
            
            audio = audio + rain_stereo
            modified = True
        
        if modified:
            # Re-normalize and limit
            audio = normalize_audio(audio, 0.9)
            audio = limit_audio(audio, TARGET_TRUE_PEAK)
            
            # Save
            if HAS_SOUNDFILE:
                sf.write(audio_path, audio, sr)
    
    def render_stems(
        self,
        midi_path: str,
        output_dir: str,
        parsed: Optional[ParsedPrompt] = None,
        bit_depth: int = 24
    ) -> Dict[str, str]:
        """
        Render individual track stems.
        
        Professional bit-depth policy: 24-bit stems by default.
        24-bit preserves maximum dynamic range for mixing/mastering workflows.
        
        Args:
            midi_path: Path to MIDI file to render
            output_dir: Directory to save stems
            parsed: Optional parsed prompt for metadata
            bit_depth: Bit depth for stems (default 24 for professional use)
        
        Returns:
            Dict mapping track name to output file path
        """
        import mido
        import re
        
        os.makedirs(output_dir, exist_ok=True)
        stems = {}
        stem_metadata = {}
        
        try:
            midi = mido.MidiFile(midi_path)
        except Exception:
            return stems
        
        total_seconds = midi.length
        total_samples = int(total_seconds * self.sample_rate) + int(self.tail_seconds * self.sample_rate)
        
        for i, track in enumerate(midi.tracks):
            # Get track name
            track_name = f'track_{i}'
            for msg in track:
                if msg.type == 'track_name':
                    track_name = msg.name
                    break

            display_name = str(track_name)
            safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", display_name.strip().replace(" ", "_"))
            safe_name = re.sub(r"_+", "_", safe_name).strip("_")
            track_name = (safe_name or f"track_{i}").lower()
            
            # Skip meta track
            if track_name.lower() == 'meta':
                continue
            
            # Render track
            audio = self._render_track_procedural(
                track,
                midi.ticks_per_beat,
                total_samples
            )
            
            if audio is not None:
                # Apply track FX chain
                is_drums = (i == 9) # Rough guess if channel info lost, but usually track name helps
                # Better check:
                is_drums = 'drum' in track_name.lower()

                role = "other"
                name_l = track_name.lower()
                if 'drum' in name_l or 'perc' in name_l:
                    role = "drums"
                elif 'bass' in name_l or '808' in name_l:
                    role = "bass"
                elif 'chord' in name_l or 'pad' in name_l or 'keys' in name_l or 'piano' in name_l or 'organ' in name_l:
                    role = "melodic"
                elif 'melody' in name_l or 'lead' in name_l or 'flute' in name_l:
                    role = "melodic"
                elif 'fx' in name_l or 'sfx' in name_l:
                    role = "fx"
                
                chain = self._get_chain_for_track(track_name, is_drums)
                if chain:
                    audio = chain.process(audio, self.sample_rate)

                # Calculate stats before stereo conversion (on mono signal)
                peak_level = float(calculate_peak(audio))
                rms_level = float(calculate_rms(audio))
                
                # Convert to stereo
                stereo = apply_stereo_pan(audio, 0)
                stereo = normalize_audio(stereo, 0.9)
                
                # Save stem as 24-bit (professional standard)
                stem_filename = f'{track_name}.wav'
                stem_path = os.path.join(output_dir, stem_filename)
                save_wav(stereo, stem_path, self.sample_rate, stereo=True, 
                        bit_depth=bit_depth, apply_dither=False)
                stems[track_name] = stem_path
                
                # Store metadata
                stem_metadata[track_name] = {
                    "file": stem_filename,
                    "display_name": display_name,
                    "role": role,
                    "peak": peak_level,
                    "rms": rms_level,
                    "is_drums": is_drums,
                    "duration_seconds": total_seconds + self.tail_seconds,
                    "bit_depth": bit_depth,
                    "sample_rate": self.sample_rate
                }
        
        # Save manifest
        manifest_path = os.path.join(output_dir, 'stems_manifest.json')
        try:
            manifest = {
                "format": {
                    "bit_depth": bit_depth,
                    "sample_rate": self.sample_rate,
                    "channels": 2,
                    "note": "24-bit stems for professional mixing; 16-bit for delivery"
                },
                "stems": stem_metadata
            }
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)
        except Exception as e:
            print(f"Failed to save stems manifest: {e}")
            
        return stems


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def render_midi_to_audio(
    midi_path: str,
    output_path: str,
    parsed: Optional[ParsedPrompt] = None
) -> bool:
    """
    Quick function to render MIDI to audio (16-bit master).
    
    For professional stem export, use render_stems() instead.
    """
    renderer = AudioRenderer()
    return renderer.render_midi_file(midi_path, output_path, parsed)


def render_stems(
    midi_path: str,
    output_dir: str,
    parsed: Optional[ParsedPrompt] = None,
    bit_depth: int = 24
) -> Dict[str, str]:
    """
    Quick function to render stems.
    
    Professional bit-depth policy:
    - Default: 24-bit stems for mixing/mastering
    - Set bit_depth=16 for delivery-ready stems
    """
    renderer = AudioRenderer()
    return renderer.render_stems(midi_path, output_dir, parsed, bit_depth=bit_depth)


if __name__ == '__main__':
    # Test
    print(f"FluidSynth available: {check_fluidsynth_available()}")
    print(f"SoundFont found: {find_soundfont()}")
    
    # Test procedural rendering
    renderer = AudioRenderer(use_fluidsynth=False)
    print("Procedural renderer initialized")
    print(f"Bit-depth policy: 24-bit stems, 16-bit master with dither")
