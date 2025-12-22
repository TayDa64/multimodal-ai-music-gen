"""
Utility functions and constants for the music generator.

Provides:
- MIDI timing calculations (480 PPQ standard)
- Music theory helpers (scales, note conversions)
- UUID generation for MPC compatibility
- Default configuration values
"""

import uuid
import random
from typing import List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


# =============================================================================
# MIDI CONSTANTS (Industry Standard: 480 PPQ)
# =============================================================================

TICKS_PER_BEAT = 480  # PPQ - Pulses Per Quarter note (MPC standard)
TICKS_PER_16TH = TICKS_PER_BEAT // 4  # 120 ticks
TICKS_PER_8TH = TICKS_PER_BEAT // 2   # 240 ticks
TICKS_PER_BAR_4_4 = TICKS_PER_BEAT * 4  # 1920 ticks per bar in 4/4

# General MIDI drum channel
GM_DRUM_CHANNEL = 9  # Channel 10 in 1-indexed (0-indexed = 9)

# General MIDI drum note numbers
GM_DRUM_NOTES = {
    'kick': 36,       # Bass Drum 1
    'kick2': 35,      # Acoustic Bass Drum
    'snare': 38,      # Acoustic Snare
    'snare_rim': 37,  # Side Stick
    'clap': 39,       # Hand Clap
    'snare2': 40,     # Electric Snare
    'tom_low': 41,    # Low Floor Tom
    'hihat_closed': 42,  # Closed Hi-Hat
    'tom_low2': 43,   # High Floor Tom
    'hihat_pedal': 44,   # Pedal Hi-Hat
    'tom_mid': 45,    # Low Tom
    'hihat_open': 46, # Open Hi-Hat
    'tom_mid2': 47,   # Low-Mid Tom
    'tom_high': 48,   # Hi-Mid Tom
    'crash': 49,      # Crash Cymbal 1
    'tom_high2': 50,  # High Tom
    'ride': 51,       # Ride Cymbal 1
    'crash2': 57,     # Crash Cymbal 2
    'ride_bell': 53,  # Ride Bell
    'tambourine': 54, # Tambourine
    'cowbell': 56,    # Cowbell
    'perc_808': 36,   # Map 808 kick to bass drum
    # African/Ethiopian percussion mappings
    'conga_high': 62,     # High Conga - for kebero slap
    'conga_low': 63,      # Low Conga - for kebero bass
    'bongo_high': 60,     # High Bongo - for atamo
    'bongo_low': 61,      # Low Bongo
    'shaker': 70,         # Maracas - for shaker sounds
    'agogo_high': 67,     # High Agogo
    'agogo_low': 68,      # Low Agogo  
    'cabasa': 69,         # Cabasa - texture percussion
    'guiro': 73,          # Guiro
    'woodblock_high': 76, # Hi Wood Block
    'woodblock_low': 77,  # Low Wood Block
}

# 808 specific (for trap/hip-hop, often use different mappings)
TRAP_808_NOTES = {
    'kick': 36,
    '808': 36,        # 808 bass often same as kick in trap
    'snare': 38,
    'clap': 39,
    'hihat': 42,
    'hihat_open': 46,
    'perc': 56,
    'crash': 49,
}


# =============================================================================
# AUDIO CONSTANTS
# =============================================================================

SAMPLE_RATE = 44100  # Hz - CD quality, MPC standard
BIT_DEPTH = 16       # bits
CHANNELS = 2         # Stereo

# Loudness targets (EBU R128 / streaming)
TARGET_LUFS = -14.0          # Integrated loudness
TARGET_TRUE_PEAK = -1.0      # dBTP ceiling
HEADROOM_DB = -6.0           # Peak headroom for stems


# =============================================================================
# MUSIC THEORY
# =============================================================================

class ScaleType(Enum):
    """Common scale types with semitone intervals from root."""
    MAJOR = [0, 2, 4, 5, 7, 9, 11]
    MINOR = [0, 2, 3, 5, 7, 8, 10]  # Natural minor
    DORIAN = [0, 2, 3, 5, 7, 9, 10]
    PHRYGIAN = [0, 1, 3, 5, 7, 8, 10]
    LYDIAN = [0, 2, 4, 6, 7, 9, 11]
    MIXOLYDIAN = [0, 2, 4, 5, 7, 9, 10]
    LOCRIAN = [0, 1, 3, 5, 6, 8, 10]
    HARMONIC_MINOR = [0, 2, 3, 5, 7, 8, 11]
    MELODIC_MINOR = [0, 2, 3, 5, 7, 9, 11]
    PENTATONIC_MAJOR = [0, 2, 4, 7, 9]
    PENTATONIC_MINOR = [0, 3, 5, 7, 10]
    BLUES = [0, 3, 5, 6, 7, 10]
    
    # Ethiopian Qenet (modes) - Traditional Ethiopian scales
    # These pentatonic scales are fundamental to Ethiopian music
    TIZITA_MAJOR = [0, 2, 5, 7, 9]      # Nostalgic/melancholic feel, major variant
    TIZITA_MINOR = [0, 3, 5, 7, 10]     # Nostalgic/melancholic feel, minor variant
    BATI_MAJOR = [0, 2, 4, 7, 9]        # Joyful, celebratory (similar to major pentatonic)
    BATI_MINOR = [0, 3, 5, 7, 10]       # Joyful minor variant
    AMBASSEL = [0, 2, 5, 7, 10]         # Spiritual, meditative, often used for slow songs
    ANCHIHOYE = [0, 2, 4, 5, 7, 9, 11]  # Playful, dance-like (similar to major but distinct phrasing)
    
    # Additional Ethiopian scales
    ETHIOPIAN_PENTATONIC = [0, 2, 5, 7, 9]  # Common Ethiopian pentatonic base
    ETHIO_JAZZ = [0, 2, 3, 5, 7, 9, 10]     # Ethio-jazz fusion (minor with raised 6th)


# Note name to MIDI number mapping (C4 = 60 = Middle C)
NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
NOTE_NAMES_FLAT = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']


# =============================================================================
# TIMING / CONVERSION FUNCTIONS
# =============================================================================

def bpm_to_microseconds_per_beat(bpm: float) -> int:
    """Convert BPM to microseconds per beat (for MIDI tempo meta events)."""
    return int(60_000_000 / bpm)


def microseconds_to_bpm(us_per_beat: int) -> float:
    """Convert microseconds per beat back to BPM."""
    return 60_000_000 / us_per_beat


def bars_to_ticks(bars: float, time_signature: Tuple[int, int] = (4, 4)) -> int:
    """
    Convert bars to MIDI ticks.
    
    Args:
        bars: Number of bars (can be fractional)
        time_signature: Tuple of (beats_per_bar, beat_unit)
    
    Returns:
        Number of ticks
    """
    beats_per_bar, beat_unit = time_signature
    # Adjust for beat unit (4 = quarter, 8 = eighth, etc.)
    ticks_per_bar = TICKS_PER_BEAT * beats_per_bar * (4 / beat_unit)
    return int(bars * ticks_per_bar)


def ticks_to_bars(ticks: int, time_signature: Tuple[int, int] = (4, 4)) -> float:
    """Convert MIDI ticks to bars."""
    beats_per_bar, beat_unit = time_signature
    ticks_per_bar = TICKS_PER_BEAT * beats_per_bar * (4 / beat_unit)
    return ticks / ticks_per_bar


def beats_to_ticks(beats: float) -> int:
    """Convert beats to MIDI ticks."""
    return int(beats * TICKS_PER_BEAT)


def ticks_to_seconds(ticks: int, bpm: float) -> float:
    """Convert MIDI ticks to seconds at given BPM."""
    beats = ticks / TICKS_PER_BEAT
    seconds_per_beat = 60.0 / bpm
    return beats * seconds_per_beat


def seconds_to_ticks(seconds: float, bpm: float) -> int:
    """Convert seconds to MIDI ticks at given BPM."""
    beats_per_second = bpm / 60.0
    beats = seconds * beats_per_second
    return int(beats * TICKS_PER_BEAT)


# =============================================================================
# NOTE / SCALE FUNCTIONS
# =============================================================================

def midi_note_to_name(midi_note: int) -> str:
    """
    Convert MIDI note number to note name with octave.
    
    Args:
        midi_note: MIDI note number (0-127)
    
    Returns:
        Note name with octave like 'C4', 'F#5'
    
    Examples:
        midi_note_to_name(60) -> 'C4'
        midi_note_to_name(69) -> 'A4'
    """
    octave = (midi_note // 12) - 1
    note_index = midi_note % 12
    return f"{NOTE_NAMES[note_index]}{octave}"


def note_name_to_midi(note_name: str, octave: int = 4) -> int:
    """
    Convert note name to MIDI note number.
    
    Args:
        note_name: Note name like 'C', 'C#', 'Db', 'F#'
        octave: Octave number (4 = middle C octave)
    
    Returns:
        MIDI note number (0-127)
    
    Examples:
        note_name_to_midi('C', 4) -> 60
        note_name_to_midi('A', 4) -> 69
    """
    # Normalize note name
    note_upper = note_name.upper().strip()
    
    # Handle flats by converting to sharps
    flat_to_sharp = {'DB': 'C#', 'EB': 'D#', 'GB': 'F#', 'AB': 'G#', 'BB': 'A#'}
    if note_upper in flat_to_sharp:
        note_upper = flat_to_sharp[note_upper]
    
    # Find in note names
    try:
        note_index = NOTE_NAMES.index(note_upper)
    except ValueError:
        # Try just the letter
        note_index = NOTE_NAMES.index(note_upper[0])
    
    return (octave + 1) * 12 + note_index


def midi_to_note_name(midi_note: int, use_flats: bool = False) -> Tuple[str, int]:
    """
    Convert MIDI note number to note name and octave.
    
    Args:
        midi_note: MIDI note number (0-127)
        use_flats: If True, use flat names (Db) instead of sharps (C#)
    
    Returns:
        Tuple of (note_name, octave)
    """
    octave = (midi_note // 12) - 1
    note_index = midi_note % 12
    names = NOTE_NAMES_FLAT if use_flats else NOTE_NAMES
    return (names[note_index], octave)


def get_scale_notes(
    root: str,
    scale_type: ScaleType,
    octave: int = 4,
    num_octaves: int = 2
) -> List[int]:
    """
    Get MIDI note numbers for a scale.
    
    Args:
        root: Root note name (e.g., 'C', 'F#')
        scale_type: Type of scale
        octave: Starting octave
        num_octaves: Number of octaves to generate
    
    Returns:
        List of MIDI note numbers
    """
    root_midi = note_name_to_midi(root, octave)
    intervals = scale_type.value
    
    notes = []
    for oct_offset in range(num_octaves):
        for interval in intervals:
            note = root_midi + interval + (oct_offset * 12)
            if 0 <= note <= 127:
                notes.append(note)
    
    return notes


def get_chord_notes(
    root: str,
    chord_type: str = 'minor',
    octave: int = 4
) -> List[int]:
    """
    Get MIDI note numbers for a chord.
    
    Args:
        root: Root note name
        chord_type: 'major', 'minor', 'dim', 'aug', '7', 'm7', 'maj7', etc.
        octave: Octave for root note
    
    Returns:
        List of MIDI note numbers
    """
    root_midi = note_name_to_midi(root, octave)
    
    chord_intervals = {
        'major': [0, 4, 7],
        'minor': [0, 3, 7],
        'dim': [0, 3, 6],
        'aug': [0, 4, 8],
        '7': [0, 4, 7, 10],
        'm7': [0, 3, 7, 10],
        'maj7': [0, 4, 7, 11],
        'dim7': [0, 3, 6, 9],
        'sus2': [0, 2, 7],
        'sus4': [0, 5, 7],
        'add9': [0, 4, 7, 14],
        'm9': [0, 3, 7, 10, 14],
        '9': [0, 4, 7, 10, 14],
    }
    
    intervals = chord_intervals.get(chord_type.lower(), chord_intervals['minor'])
    return [root_midi + i for i in intervals]


def get_chord_progression(
    key: str,
    scale_type: ScaleType,
    progression: List[int],
    octave: int = 3
) -> List[List[int]]:
    """
    Generate chord progression based on scale degrees.
    
    Args:
        key: Root key (e.g., 'C')
        scale_type: Major or minor
        progression: List of scale degrees (1-7)
        octave: Base octave
    
    Returns:
        List of chords (each chord is a list of MIDI notes)
    """
    scale_notes = get_scale_notes(key, scale_type, octave, 1)
    
    # Determine chord quality for each degree based on scale type
    if scale_type in [ScaleType.MAJOR, ScaleType.MIXOLYDIAN, ScaleType.LYDIAN]:
        # Major: I ii iii IV V vi vii°
        qualities = ['major', 'minor', 'minor', 'major', 'major', 'minor', 'dim']
    else:
        # Minor: i ii° III iv v VI VII
        qualities = ['minor', 'dim', 'major', 'minor', 'minor', 'major', 'major']
    
    chords = []
    for degree in progression:
        if 1 <= degree <= 7:
            root_note = scale_notes[degree - 1]
            root_name, _ = midi_to_note_name(root_note)
            quality = qualities[degree - 1]
            chord = get_chord_notes(root_name, quality, octave)
            chords.append(chord)
    
    return chords


# =============================================================================
# HUMANIZATION FUNCTIONS (Based on Sound On Sound research)
# =============================================================================

def humanize_velocity(
    base_velocity: int,
    variation: float = 0.1,
    min_vel: int = 40,
    max_vel: int = 127
) -> int:
    """
    Add realistic velocity variation to a note.
    
    Args:
        base_velocity: Target velocity (0-127)
        variation: Variation amount (0.0-1.0, typically 0.05-0.15)
        min_vel: Minimum allowed velocity
        max_vel: Maximum allowed velocity
    
    Returns:
        Humanized velocity
    """
    # Ensure base_velocity is reasonable
    base_velocity = max(min_vel, min(max_vel, base_velocity))
    range_amount = max(1, int(base_velocity * variation))  # At least 1
    offset = random.randint(-range_amount, range_amount)
    return max(min_vel, min(max_vel, base_velocity + offset))


def humanize_timing(
    base_ticks: int,
    swing: float = 0.0,
    timing_variation: float = 0.02,
    is_offbeat: bool = False
) -> int:
    """
    Add realistic timing variation with optional swing.
    
    Swing shifts every other 8th/16th note slightly late to create
    a "shuffled" feel common in jazz, hip-hop, and soul.
    
    Args:
        base_ticks: Original tick position
        swing: Swing amount (0.0 = straight, 0.5 = triplet feel)
                Values 0.05-0.15 are subtle, 0.2+ is obvious
        timing_variation: Random timing jitter (typically 0.01-0.05)
        is_offbeat: True if this is an offbeat note (for swing application)
    
    Returns:
        Humanized tick position
    """
    result = base_ticks
    
    # Apply swing to offbeats
    if swing > 0 and is_offbeat:
        swing_offset = int(TICKS_PER_16TH * swing)
        result += swing_offset
    
    # Add random timing variation
    if timing_variation > 0:
        max_jitter = int(TICKS_PER_16TH * timing_variation)
        jitter = random.randint(-max_jitter, max_jitter)
        result += jitter
    
    return max(0, result)


def apply_drummer_physics(
    velocity: int,
    is_strong_hand: bool = True,
    accent: bool = False
) -> int:
    """
    Apply realistic drummer physics to velocity.
    
    Real drummers hit harder with their dominant hand and emphasize
    certain beats naturally.
    
    Args:
        velocity: Base velocity
        is_strong_hand: True if dominant hand hit
        accent: True if this is an accented beat
    
    Returns:
        Adjusted velocity
    """
    result = velocity
    
    # Weak hand is typically 10-20% softer
    if not is_strong_hand:
        result = int(result * random.uniform(0.80, 0.90))
    
    # Accents are 10-20% louder
    if accent:
        result = int(result * random.uniform(1.10, 1.20))
    
    return max(30, min(127, result))


# =============================================================================
# UUID / ID GENERATION
# =============================================================================

def generate_uuid() -> str:
    """Generate a UUID string for MPC compatibility."""
    return str(uuid.uuid4()).upper()


def generate_short_id(length: int = 8) -> str:
    """Generate a short alphanumeric ID."""
    chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    return ''.join(random.choice(chars) for _ in range(length))


# =============================================================================
# DEFAULT CONFIGURATIONS
# =============================================================================

@dataclass
class DefaultConfig:
    """Default configuration values for the generator."""
    
    # Timing
    default_bpm: float = 87.0
    default_time_signature: Tuple[int, int] = (4, 4)
    default_duration_seconds: int = 150  # 2:30
    
    # Key/Scale
    default_key: str = 'C'
    default_scale: ScaleType = ScaleType.MINOR
    
    # Humanization
    velocity_variation: float = 0.12      # 12% variation
    timing_variation: float = 0.03        # 3% jitter
    swing_amount: float = 0.0             # No swing by default
    
    # MIDI
    ticks_per_beat: int = TICKS_PER_BEAT
    
    # Audio
    sample_rate: int = SAMPLE_RATE
    bit_depth: int = BIT_DEPTH


# Global default config
DEFAULT_CONFIG = DefaultConfig()


# =============================================================================
# GENRE-SPECIFIC DEFAULTS
# =============================================================================

GENRE_DEFAULTS = {
    'trap': {
        'bpm_range': (130, 150),
        'default_bpm': 140,
        'scale': ScaleType.MINOR,
        'swing': 0.0,
        'hihat_rolls': True,
        'emphasis': '808',
    },
    'trap_soul': {
        'bpm_range': (80, 100),
        'default_bpm': 87,
        'scale': ScaleType.MINOR,
        'swing': 0.08,
        'hihat_rolls': True,
        'emphasis': 'chords',
    },
    'lofi': {
        'bpm_range': (70, 95),
        'default_bpm': 85,
        'scale': ScaleType.MINOR,
        'swing': 0.12,
        'vinyl_texture': True,
        'emphasis': 'chords',
    },
    'boom_bap': {
        'bpm_range': (85, 100),
        'default_bpm': 92,
        'scale': ScaleType.MINOR,
        'swing': 0.10,
        'emphasis': 'drums',
    },
    'house': {
        'bpm_range': (120, 130),
        'default_bpm': 124,
        'scale': ScaleType.MINOR,
        'swing': 0.0,
        'four_on_floor': True,
        'emphasis': 'kick',
    },
    'ambient': {
        'bpm_range': (60, 90),
        'default_bpm': 72,
        'scale': ScaleType.MAJOR,
        'swing': 0.0,
        'sparse_drums': True,
        'emphasis': 'pads',
    },
    # Ethiopian music genres
    'ethiopian': {
        'bpm_range': (100, 130),
        'default_bpm': 115,
        'scale': ScaleType.TIZITA_MAJOR,
        'swing': 0.15,
        'time_signature': (6, 8),  # 6/8 or 12/8 common in Ethiopian music
        'emphasis': 'melody',
        'syncopation': True,
        'call_response': True,
    },
    'ethio_jazz': {
        'bpm_range': (90, 120),
        'default_bpm': 105,
        'scale': ScaleType.ETHIO_JAZZ,
        'swing': 0.12,
        'emphasis': 'brass',
        'syncopation': True,
        'funk_elements': True,
    },
    'ethiopian_traditional': {
        'bpm_range': (80, 130),
        'default_bpm': 110,
        'scale': ScaleType.AMBASSEL,
        'swing': 0.10,
        'time_signature': (12, 8),
        'emphasis': 'melody',
        'pentatonic': True,
        'ornamental': True,
    },
    'eskista': {
        'bpm_range': (100, 140),
        'default_bpm': 120,
        'scale': ScaleType.BATI_MAJOR,
        'swing': 0.18,
        'time_signature': (6, 8),
        'emphasis': 'drums',
        'dance_rhythm': True,
    },
}
