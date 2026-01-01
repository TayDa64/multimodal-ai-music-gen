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
import numpy as np
import json
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
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
    EffectType,
    EffectParams,
    SaturationParams,
    CompressorParams,
    ReverbParams
)

# Import InstrumentLibrary for custom sample support
if TYPE_CHECKING:
    from .instrument_manager import InstrumentLibrary, InstrumentMatcher


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
    """
    
    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        instrument_library: 'InstrumentLibrary' = None,
        expansion_manager: 'ExpansionManager' = None,
        genre: str = None,
        mood: str = None
    ):
        self.sample_rate = sample_rate
        self.instrument_library = instrument_library
        self.expansion_manager = expansion_manager
        self.genre = genre or "trap"
        self.mood = mood
        
        # Matcher for intelligent instrument selection
        self._matcher = None
        if instrument_library:
            try:
                from .instrument_manager import InstrumentMatcher
                self._matcher = InstrumentMatcher(instrument_library)
            except ImportError:
                pass
        
        # Pre-generate drum samples (fallback)
        self._drum_cache: Dict[str, np.ndarray] = {}
        self._custom_drum_cache: Dict[str, np.ndarray] = {}  # From library
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
        """Load best-fit instruments from library based on genre/mood."""
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
                print(f"  [+] Using {len(self._custom_drum_cache)} custom instruments")
                
        except Exception as e:
            print(f"  [!] Custom instrument loading failed: {e}")
    
    def _load_expansion_instruments(self):
        """Load instruments from expansion packs for specialized genres."""
        if not self.expansion_manager:
            return
        
        try:
            # Define instruments to pre-load based on genre
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
        """Synthesize a melodic note based on MIDI program number."""
        # Convert MIDI pitch to frequency
        freq = 440 * (2 ** ((note.pitch - 69) / 12))
        duration = note.duration_samples / self.sample_rate
        velocity = note.velocity  # Already normalized 0-1 by _render_track_procedural
        
        # Check for expansion samples first (for Ethiopian and specialized instruments)
        expansion_sample = self._get_expansion_sample_for_program(note.program, freq, duration, velocity)
        if expansion_sample is not None:
            return expansion_sample
        
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
        elif note.program >= 40 and note.program <= 47:  # Strings
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
        Performs pitch-shifting if needed to match the requested frequency.
        """
        if not self._expansion_sample_cache:
            return None
        
        # Map program numbers to instrument names
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
    """
    
    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        use_fluidsynth: bool = True,
        soundfont_path: Optional[str] = None,
        instrument_library: 'InstrumentLibrary' = None,
        expansion_manager: 'ExpansionManager' = None,
        genre: str = None,
        mood: str = None,
        use_bwf: bool = True,
        ai_metadata: Optional[Dict] = None,
        tail_seconds: float = 2.0
    ):
        self.sample_rate = sample_rate
        self.use_fluidsynth = use_fluidsynth and check_fluidsynth_available()
        self.soundfont_path = soundfont_path or find_soundfont()
        self.instrument_library = instrument_library
        self.expansion_manager = expansion_manager
        self.genre = genre
        self.mood = mood
        self.use_bwf = use_bwf
        self.ai_metadata = ai_metadata or {}
        self.tail_seconds = tail_seconds
        
        # Initialize mix chains
        self.mix_chains = {
            'drums': create_drum_bus_chain(),
            'master': create_master_chain(),
            'lofi': create_lofi_chain()
        }
        
        # Procedural fallback with optional instrument library and expansion manager
        self.procedural = ProceduralRenderer(
            sample_rate,
            instrument_library=instrument_library,
            expansion_manager=expansion_manager,
            genre=genre,
            mood=mood
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
            genre=self.genre,
            mood=self.mood
        )
    
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
        
        # Try FluidSynth first (only if no custom instruments loaded)
        if self.use_fluidsynth and self.soundfont_path and not self.procedural._custom_drum_cache:
            success = render_midi_with_fluidsynth(
                midi_path,
                output_path,
                self.soundfont_path,
                self.sample_rate
            )
            
            if success:
                # Post-process if needed
                if parsed:
                    self._post_process(output_path, parsed)
                return True
        
        # Fall back to procedural rendering (uses custom instruments if available)
        return self._render_procedural(midi_path, output_path, parsed)
    
    def _get_chain_for_track(self, track_name: str, is_drums: bool) -> Optional[MixChain]:
        """Get appropriate mix chain for a track."""
        if is_drums:
            return self.mix_chains.get('drums')
        
        # Check for other roles based on name
        name_lower = track_name.lower()
        if 'bass' in name_lower:
            # Could add bass chain
            pass
        elif 'lofi' in self.genre.lower() and ('piano' in name_lower or 'keys' in name_lower):
            return self.mix_chains.get('lofi')
            
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
        
        # Target RMS levels: drums lower, melodic higher
        # Drums typically at -10dB relative to melodic
        target_rms = 0.15  # Target RMS for melodic
        
        stereo_tracks = []
        for i, (audio, (name, is_drums)) in enumerate(zip(tracks_audio, track_infos)):
            # Apply track FX chain
            chain = self._get_chain_for_track(name, is_drums)
            if chain:
                audio = chain.process(audio, self.sample_rate)

            rms = calculate_rms(audio)
            
            if rms > 0.001:  # Avoid division by zero
                if is_drums:
                    # Drums at lower level (-6dB relative to melodic)
                    target = target_rms * 0.5
                    gain = target / rms
                else:
                    # Melodic at full level
                    gain = target_rms / rms
                
                # Limit gain to avoid extreme amplification
                gain = min(gain, 4.0)  # Max +12dB
                audio = audio * gain
            
            # Apply panning - drums center, melodic slightly spread
            pan = 0 if is_drums else (0.2 if i % 2 == 0 else -0.2)
            stereo = apply_stereo_pan(audio, pan)
            stereo_tracks.append(stereo)
        
        mix = mix_stereo_tracks(stereo_tracks)
        
        # Apply master bus processing
        master_chain = self.mix_chains.get('master')
        if master_chain:
            mix = master_chain.process(mix, self.sample_rate)
        
        # Soft clip to prevent harsh distortion
        mix = soft_clip(mix, threshold=0.7)
        
        # Normalize and limit with more headroom
        mix = normalize_audio(mix, 0.85)
        mix = limit_audio(mix, TARGET_TRUE_PEAK)
        
        # Save with BWF format if enabled
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
                    description=f"AI-generated music: {parsed.genre if parsed else 'unknown'} at {parsed.bpm if parsed else 0} BPM"
                )
            except Exception as e:
                # Fall back to standard WAV if BWF fails
                print(f"BWF save failed, falling back to standard WAV: {e}")
                save_wav(mix, output_path, self.sample_rate, stereo=True)
        else:
            save_wav(mix, output_path, self.sample_rate, stereo=True)
        
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
        parsed: Optional[ParsedPrompt] = None
    ) -> Dict[str, str]:
        """
        Render individual track stems.
        
        Returns:
            Dict mapping track name to output file path
        """
        import mido
        
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
                    track_name = msg.name.replace(' ', '_').lower()
                    break
            
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
                
                chain = self._get_chain_for_track(track_name, is_drums)
                if chain:
                    audio = chain.process(audio, self.sample_rate)

                # Calculate stats before stereo conversion (on mono signal)
                peak_level = float(calculate_peak(audio))
                rms_level = float(calculate_rms(audio))
                
                # Convert to stereo
                stereo = apply_stereo_pan(audio, 0)
                stereo = normalize_audio(stereo, 0.9)
                
                # Save stem
                stem_filename = f'{track_name}.wav'
                stem_path = os.path.join(output_dir, stem_filename)
                save_wav(stereo, stem_path, self.sample_rate, stereo=True)
                stems[track_name] = stem_path
                
                # Store metadata
                stem_metadata[track_name] = {
                    "file": stem_filename,
                    "peak": peak_level,
                    "rms": rms_level,
                    "is_drums": is_drums,
                    "duration_seconds": total_seconds + self.tail_seconds
                }
        
        # Save manifest
        manifest_path = os.path.join(output_dir, 'stems_manifest.json')
        try:
            with open(manifest_path, 'w') as f:
                json.dump(stem_metadata, f, indent=2)
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
    """Quick function to render MIDI to audio."""
    renderer = AudioRenderer()
    return renderer.render_midi_file(midi_path, output_path, parsed)


def render_stems(
    midi_path: str,
    output_dir: str,
    parsed: Optional[ParsedPrompt] = None
) -> Dict[str, str]:
    """Quick function to render stems."""
    renderer = AudioRenderer()
    return renderer.render_stems(midi_path, output_dir, parsed)


if __name__ == '__main__':
    # Test
    print(f"FluidSynth available: {check_fluidsynth_available()}")
    print(f"SoundFont found: {find_soundfont()}")
    
    # Test procedural rendering
    renderer = AudioRenderer(use_fluidsynth=False)
    print("Procedural renderer initialized")
