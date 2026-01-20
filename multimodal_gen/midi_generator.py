"""
MIDI Generator Module

Generates humanized MIDI sequences for drums, bass, chords, and melody.
Implements professional producer techniques:

1. Velocity Humanization
   - ±10-15% random variation
   - Strong/weak hand simulation for drums
   - Accent emphasis on strong beats

2. Timing Humanization (based on Sound On Sound research)
   - Swing (offbeat delay, typically 5-20% of 16th note)
   - Random timing jitter (±1-5% of 16th note)
   - Drummer physics (no impossible simultaneous hits)

3. Pattern Variation
   - "Double-up" technique: vary every 2/4/8 bars
   - Ghost notes on snare
   - Fill placement at section boundaries

4. MIDI Best Practices
   - 480 PPQ (ticks per beat) - MPC standard
   - Channel 10 for drums (GM standard)
   - Proper note-off handling
"""

import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Callable
from enum import Enum
import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage

from .utils import (
    TICKS_PER_BEAT,
    TICKS_PER_16TH,
    TICKS_PER_8TH,
    TICKS_PER_BAR_4_4,
    GM_DRUM_CHANNEL,
    GM_DRUM_NOTES,
    TRAP_808_NOTES,
    ScaleType,
    GENRE_DEFAULTS,
    normalize_genre,
    bpm_to_microseconds_per_beat,
    bars_to_ticks,
    beats_to_ticks,
    humanize_velocity,
    humanize_timing,
    apply_drummer_physics,
    get_scale_notes,
    get_chord_progression,
    get_chord_notes,
    note_name_to_midi,
    midi_to_note_name,
    get_ticks_per_bar,
)

from .ethio_melody import embellish_melody_qenet
from .prompt_parser import ParsedPrompt
from .arranger import Arrangement, SongSection, SectionType, get_section_motif
from .groove_templates import GrooveTemplate, GrooveApplicator, get_groove_for_genre
from .strategies.registry import StrategyRegistry

# Optional instrument resolution service for expansion instrument support
try:
    from .instrument_resolution import InstrumentResolutionService
    HAS_INSTRUMENT_SERVICE = True
except ImportError:
    HAS_INSTRUMENT_SERVICE = False
    InstrumentResolutionService = None  # type: ignore


def _nearest_note_in_scale(pitch: int, scale_notes: List[int]) -> int:
    if not scale_notes:
        return max(0, min(127, int(pitch)))
    pitch = max(0, min(127, int(pitch)))
    best = scale_notes[0]
    best_dist = abs(best - pitch)
    for candidate in scale_notes[1:]:
        dist = abs(candidate - pitch)
        if dist < best_dist or (dist == best_dist and candidate < best):
            best = candidate
            best_dist = dist
    return best

# Physics-aware humanization for realistic performances
try:
    from .humanize_physics import (
        PhysicsHumanizer,
        HumanizeConfig,
        Note as PhysicsNote,
        humanize_drums,
        humanize_bass,
        humanize_keys
    )
    HAS_PHYSICS_HUMANIZER = True
except ImportError:
    HAS_PHYSICS_HUMANIZER = False

# Style policy for coherent producer decisions
try:
    from .style_policy import PolicyContext
    HAS_STYLE_POLICY = True
except ImportError:
    HAS_STYLE_POLICY = False
    PolicyContext = None


# =============================================================================
# NOTE EVENT DATA STRUCTURE
# =============================================================================

@dataclass
class NoteEvent:
    """Represents a single MIDI note event."""
    pitch: int              # MIDI note number (0-127)
    start_tick: int         # Start time in ticks
    duration_ticks: int     # Duration in ticks
    velocity: int           # Velocity (0-127)
    channel: int = 0        # MIDI channel (0-15)
    
    @property
    def end_tick(self) -> int:
        return self.start_tick + self.duration_ticks


@dataclass
class TrackData:
    """Contains all note events for a single track."""
    name: str
    notes: List[NoteEvent] = field(default_factory=list)
    channel: int = 0
    program: int = 0  # MIDI program change (instrument)
    
    def add_note(
        self,
        pitch: int,
        start_tick: int,
        duration_ticks: int,
        velocity: int
    ):
        """Add a note event to the track."""
        self.notes.append(NoteEvent(
            pitch=pitch,
            start_tick=start_tick,
            duration_ticks=duration_ticks,
            velocity=velocity,
            channel=self.channel,
        ))
    
    def sort_notes(self):
        """Sort notes by start time."""
        self.notes.sort(key=lambda n: (n.start_tick, n.pitch))


# =============================================================================
# DRUM PATTERN GENERATORS
# =============================================================================

class DrumPatternType(Enum):
    """Types of drum patterns."""
    TRAP_MAIN = 'trap_main'
    TRAP_MINIMAL = 'trap_minimal'
    LOFI_SWING = 'lofi_swing'
    BOOM_BAP = 'boom_bap'
    HOUSE_4x4 = 'house_4x4'
    SPARSE = 'sparse'


def generate_trap_kick_pattern(
    bars: int,
    variation: int = 0,
    base_velocity: int = 110
) -> List[Tuple[int, int, int]]:
    """
    Generate trap-style kick pattern.
    
    Returns:
        List of (tick_offset, duration, velocity) tuples
    """
    pattern = []
    ticks_per_bar = TICKS_PER_BAR_4_4
    
    # Base pattern: kick on 1, ghost on 2.5, kick on 3.5
    base_kicks = [
        (0, TICKS_PER_8TH, base_velocity),                    # Beat 1
        (beats_to_ticks(2.5), TICKS_PER_16TH, base_velocity - 20),  # Ghost
        (beats_to_ticks(3.5), TICKS_PER_8TH, base_velocity - 5),    # Beat 3.5
    ]
    
    # Variation patterns
    variations = [
        base_kicks,
        # Variation 1: extra kick on beat 4
        base_kicks + [(beats_to_ticks(3.75), TICKS_PER_16TH, base_velocity - 15)],
        # Variation 2: simpler pattern
        [(0, TICKS_PER_8TH, base_velocity), (beats_to_ticks(3), TICKS_PER_8TH, base_velocity - 5)],
        # Variation 3: syncopated
        [(0, TICKS_PER_8TH, base_velocity), (beats_to_ticks(1.5), TICKS_PER_16TH, base_velocity - 20),
         (beats_to_ticks(3), TICKS_PER_8TH, base_velocity - 5)],
    ]
    
    selected = variations[variation % len(variations)]
    
    # Apply pattern to each bar with slight variations
    for bar in range(bars):
        bar_offset = bar * ticks_per_bar
        for tick, dur, vel in selected:
            # Add humanization
            actual_vel = humanize_velocity(vel, variation=0.08)
            # Every other bar, slightly vary pattern
            if bar % 2 == 1 and random.random() < 0.3:
                continue  # Skip occasional notes for variation
            pattern.append((bar_offset + tick, dur, actual_vel))
    
    return pattern


def generate_trap_snare_pattern(
    bars: int,
    variation: int = 0,
    base_velocity: int = 100,
    add_ghost_notes: bool = True,
    half_time: bool = True
) -> List[Tuple[int, int, int]]:
    """Generate trap-style snare/clap pattern.

    Default is half-time (primary hit on beat 3), which is common for modern
    trap at ~130-170 BPM.
    """
    pattern = []
    ticks_per_bar = TICKS_PER_BAR_4_4
    
    for bar in range(bars):
        bar_offset = bar * ticks_per_bar

        # Main snares
        if half_time:
            # Beat 3 (0-indexed beat start = 2)
            tick = bar_offset + beats_to_ticks(2)
            vel = humanize_velocity(base_velocity, variation=0.1)
            pattern.append((tick, TICKS_PER_8TH, vel))

            # Optional late-clap / secondary hit for variation
            if variation % 4 == 1 and random.random() < 0.35:
                tick2 = bar_offset + beats_to_ticks(3)
                vel2 = humanize_velocity(max(60, base_velocity - 15), variation=0.12)
                pattern.append((tick2, TICKS_PER_16TH, vel2))
        else:
            # Backbeat (beats 2 and 4)
            for beat in [2, 4]:
                tick = bar_offset + beats_to_ticks(beat - 1)  # 0-indexed
                vel = humanize_velocity(base_velocity, variation=0.1)
                pattern.append((tick, TICKS_PER_8TH, vel))
        
        # Ghost notes (soft snare hits around the main hit)
        if add_ghost_notes and random.random() < 0.55:
            if half_time:
                ghost_positions = [2.5, 2.75, 3.5]  # around beat 3
                ghost_pos = random.choice(ghost_positions)
                tick = bar_offset + beats_to_ticks(ghost_pos)
            else:
                ghost_positions = [1.5, 2.5, 3.5]
                ghost_pos = random.choice(ghost_positions)
                tick = bar_offset + beats_to_ticks(ghost_pos - 1)

            ghost_vel = humanize_velocity(48, variation=0.18)
            pattern.append((tick, TICKS_PER_16TH, ghost_vel))
    
    return pattern


def generate_standard_hihat_pattern(
    bars: int,
    density: str = '8th',  # '8th', '16th', or 'sparse'
    base_velocity: int = 75,
    swing: float = 0.0,
    include_rolls: bool = False
) -> List[Tuple[int, int, int]]:
    """
    Generate standard hi-hat pattern with configurable density.
    
    This is the DEFAULT hi-hat generator for most genres.
    Only use generate_trap_hihat_pattern for trap/drill specific needs.
    
    NOTE: This function applies MINIMAL timing variation to avoid collision
    with other drum elements that may be generated separately. The main
    collision resolution happens in _resolve_drum_collisions().
    
    Args:
        density: '8th' (default, clean), '16th' (busier), 'sparse' (minimal)
        include_rolls: Only adds rolls if True AND genre specifically needs them
    """
    pattern = []
    ticks_per_bar = TICKS_PER_BAR_4_4
    
    for bar in range(bars):
        bar_offset = bar * ticks_per_bar
        
        if density == 'sparse':
            # Very minimal - just on beats 2 and 4
            for beat in [1, 3]:  # 0-indexed
                tick = bar_offset + beats_to_ticks(beat)
                vel = humanize_velocity(base_velocity - 10, variation=0.1)
                pattern.append((tick, TICKS_PER_8TH, vel))
        
        elif density == '8th':
            # Clean 8th note pattern - professional standard for most genres
            for eighth in range(8):
                base_tick = bar_offset + (eighth * TICKS_PER_8TH)
                is_offbeat = eighth % 2 == 1
                
                # Apply swing only to offbeats, no additional timing jitter
                # This reduces collisions with separately-generated kicks/snares
                if swing > 0 and is_offbeat:
                    swing_offset = int(TICKS_PER_8TH * swing)
                    tick = base_tick + swing_offset
                else:
                    tick = base_tick
                
                # Accent on beats, lighter on offbeats
                if eighth % 2 == 0:
                    vel = humanize_velocity(base_velocity, variation=0.08)
                else:
                    vel = humanize_velocity(base_velocity - 15, variation=0.12)
                
                pattern.append((tick, TICKS_PER_8TH // 2, vel))
        
        elif density == '16th':
            # 16th notes - only for very specific genres (handled by trap pattern)
            for sixteenth in range(16):
                base_tick = bar_offset + (sixteenth * TICKS_PER_16TH)
                is_offbeat = sixteenth % 2 == 1
                
                # Apply swing deterministically, no random jitter
                if swing > 0 and is_offbeat:
                    swing_offset = int(TICKS_PER_16TH * swing)
                    tick = base_tick + swing_offset
                else:
                    tick = base_tick
                
                if sixteenth % 4 == 0:
                    vel = humanize_velocity(base_velocity, variation=0.08)
                elif sixteenth % 2 == 0:
                    vel = humanize_velocity(base_velocity - 15, variation=0.1)
                else:
                    vel = humanize_velocity(base_velocity - 25, variation=0.12)
                
                pattern.append((tick, TICKS_PER_16TH // 2, vel))
        
        # Only add rolls if explicitly requested AND it makes sense
        if include_rolls and density == '16th' and random.random() < 0.25:
            roll_start_beat = random.choice([2, 3])  # More musical placement
            roll_start_tick = bar_offset + beats_to_ticks(roll_start_beat)
            roll_length = random.choice([3, 6])  # Shorter rolls
            
            ticks_per_triplet = TICKS_PER_8TH // 3
            for i in range(roll_length):
                roll_tick = roll_start_tick + (i * ticks_per_triplet)
                roll_vel = humanize_velocity(55 + (i * 4), variation=0.1)
                pattern.append((roll_tick, ticks_per_triplet // 2, roll_vel))
    
    return pattern


def generate_trap_hihat_pattern(
    bars: int,
    variation: int = 0,
    base_velocity: int = 80,
    include_rolls: bool = True,
    swing: float = 0.0
) -> List[Tuple[int, int, int]]:
    """
    Generate trap-style hi-hat pattern with rolls.
    
    Hi-hat rolls are a signature of trap music - rapid triplet or
    32nd note patterns that create rhythmic tension.
    """
    pattern = []
    ticks_per_bar = TICKS_PER_BAR_4_4
    
    for bar in range(bars):
        bar_offset = bar * ticks_per_bar
        
        # 16th note base pattern
        for sixteenth in range(16):
            tick = bar_offset + (sixteenth * TICKS_PER_16TH)
            
            # Apply swing to offbeats
            is_offbeat = sixteenth % 2 == 1
            if swing > 0 and is_offbeat:
                tick = humanize_timing(tick, swing=swing, is_offbeat=True)
            
            # Determine velocity (accents on beats)
            if sixteenth % 4 == 0:  # On beat
                vel = humanize_velocity(base_velocity, variation=0.08)
            elif sixteenth % 2 == 0:  # 8th note
                vel = humanize_velocity(base_velocity - 15, variation=0.1)
            else:  # 16th note
                vel = humanize_velocity(base_velocity - 25, variation=0.12)
            
            pattern.append((tick, TICKS_PER_16TH // 2, vel))
        
        # Add hi-hat rolls (randomly placed)
        if include_rolls and random.random() < 0.3:
            roll_start_beat = random.choice([1, 2, 3])  # Beat to start roll
            roll_start_tick = bar_offset + beats_to_ticks(roll_start_beat)
            roll_length = random.choice([3, 6, 9])  # Triplet-based
            
            ticks_per_triplet = TICKS_PER_8TH // 3
            for i in range(roll_length):
                roll_tick = roll_start_tick + (i * ticks_per_triplet)
                # Rolls typically crescendo
                roll_vel = humanize_velocity(
                    60 + (i * 5),  # Increasing velocity
                    variation=0.1
                )
                pattern.append((roll_tick, ticks_per_triplet // 2, roll_vel))
    
    return pattern


def generate_rnb_drum_pattern(
    bars: int,
    swing: float = 0.08,
    base_velocity: int = 80
) -> Dict[str, List[Tuple[int, int, int]]]:
    """
    Generate R&B style drum pattern.
    
    Characteristics:
    - Smoother, groove-oriented feel
    - No hi-hat rolls (clean, understated)
    - Emphasis on the pocket/groove
    - Lighter touch on drums
    - Occasional rim shots for texture
    
    IMPORTANT: Uses shared groove timing to prevent "flamming" effects
    where kick/snare/hihat land at slightly different times.
    """
    ticks_per_bar = TICKS_PER_BAR_4_4
    
    kicks = []
    snares = []
    hihats = []
    rims = []
    
    for bar in range(bars):
        bar_offset = bar * ticks_per_bar
        
        # Pre-calculate groove offsets for each 8th note position
        # This ensures all drums hitting at the same time share the same groove
        groove_offsets = {}
        for eighth in range(8):
            base_tick = bar_offset + (eighth * TICKS_PER_8TH)
            is_offbeat = eighth % 2 == 1
            # Calculate humanized tick ONCE per grid position
            humanized = humanize_timing(base_tick, swing=swing, timing_variation=0.02, is_offbeat=is_offbeat)
            groove_offsets[eighth] = humanized
        
        # R&B kick pattern - simpler, groove-focused
        # Pattern varies every 2 bars for interest
        if bar % 4 < 2:
            kick_positions = [0, 2.5]  # Basic groove
        else:
            kick_positions = [0, 2.25, 3.5]  # Slight variation
        
        for pos in kick_positions:
            # Map to nearest 8th note position for groove alignment
            eighth_pos = int(pos * 2)  # Convert beats to 8th note index
            if eighth_pos in groove_offsets:
                tick = groove_offsets[eighth_pos]
            else:
                tick = bar_offset + beats_to_ticks(pos)
            vel = humanize_velocity(base_velocity, variation=0.08)
            kicks.append((tick, TICKS_PER_8TH, vel))
        
        # Snare on 2 and 4 - classic R&B backbeat
        for beat in [2, 4]:
            eighth_pos = (beat - 1) * 2  # Beat 2 = 8th position 2, Beat 4 = 8th position 6
            tick = groove_offsets.get(eighth_pos, bar_offset + beats_to_ticks(beat - 1))
            vel = humanize_velocity(base_velocity - 5, variation=0.1)
            snares.append((tick, TICKS_PER_8TH, vel))
        
        # Clean 8th note hi-hats - use pre-calculated groove
        for eighth in range(8):
            tick = groove_offsets[eighth]
            
            # Subtle accent pattern - lighter touch
            if eighth % 2 == 0:
                vel = humanize_velocity(base_velocity - 20, variation=0.1)
            else:
                vel = humanize_velocity(base_velocity - 30, variation=0.12)
            
            hihats.append((tick, TICKS_PER_8TH // 2, vel))
        
        # Occasional rim shot for R&B texture (every 4 bars)
        if bar % 4 == 2:
            # Rim on the "and" of beat 2 (8th position 3)
            rim_tick = groove_offsets.get(3, bar_offset + beats_to_ticks(1.5))
            rim_vel = humanize_velocity(55, variation=0.15)
            rims.append((rim_tick, TICKS_PER_16TH, rim_vel))
    
    return {'kick': kicks, 'snare': snares, 'hihat': hihats, 'rim': rims}


def generate_lofi_drum_pattern(
    bars: int,
    swing: float = 0.12,
    base_velocity: int = 85
) -> Dict[str, List[Tuple[int, int, int]]]:
    """
    Generate lo-fi hip hop style drum pattern.
    
    Characteristics:
    - Strong swing feel
    - Softer, more relaxed velocities
    - Simpler patterns
    
    IMPORTANT: Uses shared groove timing to prevent "flamming" effects
    where kick/snare/hihat land at slightly different times.
    """
    ticks_per_bar = TICKS_PER_BAR_4_4
    
    kicks = []
    snares = []
    hihats = []
    
    for bar in range(bars):
        bar_offset = bar * ticks_per_bar
        
        # Pre-calculate groove offsets for each 8th note position
        # This ensures all drums hitting at the same time share the same groove
        groove_offsets = {}
        for eighth in range(8):
            base_tick = bar_offset + (eighth * TICKS_PER_8TH)
            is_offbeat = eighth % 2 == 1
            # Calculate humanized tick ONCE per grid position
            humanized = humanize_timing(base_tick, swing=swing, timing_variation=0.02, is_offbeat=is_offbeat)
            groove_offsets[eighth] = humanized
        
        # Simple kick pattern - use groove from 8th note grid
        kick_positions = [(0, 0), (2.5, 5)] if bar % 2 == 0 else [(0, 0), (2.75, 5)]  # (beat_pos, nearest_8th)
        for beat_pos, eighth_pos in kick_positions:
            tick = groove_offsets.get(eighth_pos, bar_offset + beats_to_ticks(beat_pos))
            vel = humanize_velocity(base_velocity, variation=0.1)
            kicks.append((tick, TICKS_PER_8TH, vel))
        
        # Snare on 2 and 4 - use groove from 8th note grid
        for beat, eighth_pos in [(2, 2), (4, 6)]:
            tick = groove_offsets.get(eighth_pos, bar_offset + beats_to_ticks(beat - 1))
            vel = humanize_velocity(base_velocity - 10, variation=0.12)
            snares.append((tick, TICKS_PER_8TH, vel))
        
        # Swung hi-hats - use pre-calculated groove
        for eighth in range(8):
            tick = groove_offsets[eighth]
            
            # Accent pattern
            if eighth % 2 == 0:
                vel = humanize_velocity(base_velocity - 15, variation=0.1)
            else:
                vel = humanize_velocity(base_velocity - 30, variation=0.15)
            
            hihats.append((tick, TICKS_PER_8TH // 2, vel))
    
    return {'kick': kicks, 'snare': snares, 'hihat': hihats}


def generate_gfunk_drum_pattern(
    bars: int,
    swing: float = 0.15,
    base_velocity: int = 85
) -> Dict[str, List[Tuple[int, int, int]]]:
    """
    Generate G-Funk style drum pattern.
    
    Characteristics:
    - Bouncy, laid-back west coast feel
    - Clean 8th note hi-hats (NO rapid rolls)
    - Strong swing/shuffle
    - Emphasis on the groove pocket
    - Influenced by funk and P-Funk
    - Think Dr. Dre's "The Chronic" era
    
    IMPORTANT: Uses shared groove timing to prevent "flamming" effects
    where kick/snare/hihat land at slightly different times.
    """
    ticks_per_bar = TICKS_PER_BAR_4_4
    
    kicks = []
    snares = []
    hihats = []
    claps = []
    
    for bar in range(bars):
        bar_offset = bar * ticks_per_bar
        
        # Pre-calculate groove offsets for each 8th note position
        # This ensures all drums hitting at the same time share the same groove
        groove_offsets = {}
        for eighth in range(8):
            base_tick = bar_offset + (eighth * TICKS_PER_8TH)
            is_offbeat = eighth % 2 == 1
            # Calculate humanized tick ONCE per grid position
            humanized = humanize_timing(base_tick, swing=swing, timing_variation=0.02, is_offbeat=is_offbeat)
            groove_offsets[eighth] = humanized
        
        # G-Funk kick pattern - funky, syncopated
        # Classic west coast bounce pattern
        if bar % 4 < 2:
            # Pattern A: Standard funk-influenced
            kick_eighths = [0, 3, 4, 6]  # Beat 1, "and" of 2, Beat 3, Beat 4
        else:
            # Pattern B: Variation for movement
            kick_eighths = [0, 2, 3, 6]  # Beat 1, Beat 2, "and" of 2, Beat 4
        
        for eighth in kick_eighths:
            tick = groove_offsets.get(eighth, bar_offset + (eighth * TICKS_PER_8TH))
            vel = humanize_velocity(base_velocity + 5, variation=0.08)
            kicks.append((tick, TICKS_PER_8TH, vel))
        
        # Snare on 2 and 4 (classic backbeat)
        for eighth_pos in [2, 6]:  # Beat 2 and Beat 4
            tick = groove_offsets.get(eighth_pos, bar_offset + (eighth_pos * TICKS_PER_8TH))
            vel = humanize_velocity(base_velocity, variation=0.1)
            snares.append((tick, TICKS_PER_8TH, vel))
        
        # Clap layered on beat 4 for extra punch (every other bar)
        if bar % 2 == 1:
            tick = groove_offsets.get(6, bar_offset + beats_to_ticks(3))
            vel = humanize_velocity(base_velocity - 10, variation=0.12)
            claps.append((tick, TICKS_PER_8TH, vel))
        
        # G-Funk hi-hats: CLEAN 8th notes with swing (NOT 16th notes!)
        # This is the key difference from trap - laid back, groovy, not busy
        for eighth in range(8):
            tick = groove_offsets[eighth]
            
            # Accent pattern: stronger on downbeats
            if eighth % 2 == 0:  # Downbeat
                vel = humanize_velocity(base_velocity - 10, variation=0.1)
            else:  # Offbeat (swung)
                vel = humanize_velocity(base_velocity - 25, variation=0.12)
            
            hihats.append((tick, TICKS_PER_8TH // 2, vel))
        
        # Occasional open hi-hat on the "and" of 4 for G-Funk flavor
        if random.random() < 0.4:
            tick = groove_offsets.get(7, bar_offset + beats_to_ticks(3.5))
            vel = humanize_velocity(base_velocity - 15, variation=0.15)
            # Mark as open (will be processed separately)
            hihats.append((tick, TICKS_PER_8TH, vel))
    
    return {'kick': kicks, 'snare': snares, 'hihat': hihats, 'clap': claps}


def generate_house_drum_pattern(
    bars: int,
    base_velocity: int = 100
) -> Dict[str, List[Tuple[int, int, int]]]:
    """Generate four-on-the-floor house drum pattern."""
    ticks_per_bar = TICKS_PER_BAR_4_4
    
    kicks = []
    claps = []
    hihats_closed = []
    hihats_open = []
    
    for bar in range(bars):
        bar_offset = bar * ticks_per_bar
        
        # Four on the floor kick
        for beat in range(4):
            tick = bar_offset + beats_to_ticks(beat)
            vel = humanize_velocity(base_velocity, variation=0.05)
            kicks.append((tick, TICKS_PER_8TH, vel))
        
        # Clap on 2 and 4
        for beat in [1, 3]:  # 0-indexed
            tick = bar_offset + beats_to_ticks(beat)
            vel = humanize_velocity(base_velocity - 10, variation=0.08)
            claps.append((tick, TICKS_PER_8TH, vel))
        
        # Hi-hats: closed on beats, open on off-beats
        for sixteenth in range(16):
            tick = bar_offset + (sixteenth * TICKS_PER_16TH)
            
            if sixteenth % 4 == 2:  # Off-beat 8th notes
                vel = humanize_velocity(base_velocity - 20, variation=0.1)
                hihats_open.append((tick, TICKS_PER_8TH, vel))
            elif sixteenth % 2 == 0:  # On-beat
                vel = humanize_velocity(base_velocity - 25, variation=0.1)
                hihats_closed.append((tick, TICKS_PER_16TH, vel))
    
    return {
        'kick': kicks,
        'clap': claps,
        'hihat': hihats_closed,
        'hihat_open': hihats_open,
    }


def generate_ethiopian_drum_pattern(
    bars: int,
    style: str = 'ethiopian',
    base_velocity: int = 95,
    time_signature: Tuple[int, int] = (6, 8)
) -> Dict[str, List[Tuple[int, int, int]]]:
    """
    Generate authentic Ethiopian-style drum patterns.
    
    Ethiopian music is characterized by:
    - Compound meters (6/8, 12/8) creating a "triplet" or "shuffle" feel
    - The kebero drum with interlocking bass (doom) and slap (tek) patterns
    - Polyrhythmic layering with atamo (small drum) and shakers
    - Call-and-response between different drums
    
    Styles:
    - 'eskista': Fast shoulder dance rhythm - energetic 6/8 with strong accents
    - 'ethiopian_traditional': Traditional kebero patterns (12/8)
    - 'ethio_jazz': Fusion with jazz kit while keeping Ethiopian feel
    - 'ethiopian': Modern Ethiopian pop
    
    Key rhythmic concept: Ethiopian 6/8 divides each bar into TWO groups of THREE
    (1-2-3, 4-5-6) rather than THREE groups of TWO like Western 6/8.
    
    In 12/8: FOUR groups of THREE (1-2-3, 4-5-6, 7-8-9, 10-11-12)
    with primary pulse on 1, 4, 7, 10.
    
    Args:
        bars: Number of bars to generate
        style: Ethiopian substyle ('ethiopian', 'eskista', 'ethiopian_traditional', 'ethio_jazz')
        base_velocity: Base velocity for drum hits
        time_signature: Time signature tuple (numerator, denominator)
                       Default (6, 8) for most Ethiopian styles
    
    Returns:
        Dict mapping drum element names to lists of (tick, duration, velocity) tuples
    """
    from .utils import get_ticks_per_bar
    
    # Calculate ticks per bar based on actual time signature
    # This is crucial for authentic 6/8 and 12/8 feel
    ticks_per_bar = get_ticks_per_bar(time_signature)
    
    # Determine pulse count based on time signature
    # 6/8 = 6 eighth-note pulses, 12/8 = 12 eighth-note pulses
    numerator, denominator = time_signature
    if denominator == 8:
        num_pulses = numerator  # 6 for 6/8, 12 for 12/8
    else:
        # Fallback to 12 pulses for 4/4 (treated as 12/8 subdivision)
        num_pulses = 12
    
    # Each "pulse" is one eighth note in compound meter
    pulse = ticks_per_bar // num_pulses
    
    kebero_bass = []      # Deep "doom" sounds
    kebero_slap = []      # Higher "tek" sounds  
    atamo = []            # Small drum fills
    shaker = []           # Continuous texture
    
    for bar in range(bars):
        bar_offset = bar * ticks_per_bar
        
        if style == 'eskista':
            # ESKISTA: Fast, energetic shoulder dance
            # Characteristic: Strong accents on 1, 4, 7, 10 (of 12)
            # with syncopated slaps creating the "bounce" for shoulder movement
            
            # Kebero bass - the foundation groove
            # For 6/8: pulses 0, 3 (beat 1 and beat 2 in compound duple)
            # For 12/8: pulses 0, 3, 6, 9 (every 3rd pulse = strong beats)
            bass_pulses = [0, 3] if num_pulses == 6 else [0, 3, 6, 9]
            for pulse_num in bass_pulses:
                tick = bar_offset + (pulse_num * pulse)
                tick = humanize_timing(tick, swing=0.03, timing_variation=0.015)
                # Accent first beat (and seventh in 12/8) more
                if pulse_num == 0 or (num_pulses == 12 and pulse_num == 6):
                    vel = humanize_velocity(base_velocity, variation=0.08)
                else:
                    vel = humanize_velocity(base_velocity - 12, variation=0.1)
                kebero_bass.append((tick, pulse * 2, vel))
            
            # Kebero slap - creates the characteristic bounce
            # Syncopated pattern between bass hits
            # For 6/8: pulses 1, 2, 4, 5
            # For 12/8: pulses 1, 2, 4, 5, 7, 8, 10, 11
            slap_pulses = [1, 2, 4, 5] if num_pulses == 6 else [1, 2, 4, 5, 7, 8, 10, 11]
            for pulse_num in slap_pulses:
                tick = bar_offset + (pulse_num * pulse)
                tick = humanize_timing(tick, swing=0.05, timing_variation=0.025)
                # Alternate accent pattern for movement feel
                # Off-pulse accents: 2, 5 in 6/8; 2, 5, 8, 11 in 12/8
                off_pulse_accents = [2, 5] if num_pulses == 6 else [2, 5, 8, 11]
                if pulse_num in off_pulse_accents:
                    vel = humanize_velocity(base_velocity - 8, variation=0.1)
                else:
                    vel = humanize_velocity(base_velocity - 20, variation=0.12)
                kebero_slap.append((tick, pulse, vel))
            
            # Atamo - fills and accents
            # Fast triplet fills on every other bar for variation
            if bar % 2 == 1:
                # Fill at end of bar: last 3 pulses
                fill_pulses = list(range(num_pulses - 3, num_pulses))
                for pulse_num in fill_pulses:
                    tick = bar_offset + (pulse_num * pulse)
                    vel = humanize_velocity(base_velocity - 15, variation=0.15)
                    atamo.append((tick, pulse // 2, vel))
            
            # Shaker - continuous compound meter texture
            for pulse_num in range(num_pulses):
                tick = bar_offset + (pulse_num * pulse)
                tick = humanize_timing(tick, swing=0.02, timing_variation=0.02)
                # Accent main beats (every 3rd pulse in compound meter)
                if pulse_num % 3 == 0:
                    vel = humanize_velocity(base_velocity - 25, variation=0.1)
                else:
                    vel = humanize_velocity(base_velocity - 40, variation=0.15)
                shaker.append((tick, pulse // 2, vel))
                
        elif style in ['ethiopian_traditional']:
            # Traditional slower kebero pattern
            # More call-and-response, less continuous
            
            # Bass on main beats: pulse 0 and midpoint
            # In 6/8: pulses 0, 3 (beat 1 and beat 2)
            # In 12/8: pulses 0, 6 (beat 1 and beat 3)
            trad_bass_pulses = [0, 3] if num_pulses == 6 else [0, 6]
            for pulse_num in trad_bass_pulses:
                tick = bar_offset + (pulse_num * pulse)
                tick = humanize_timing(tick, swing=0, timing_variation=0.02)
                vel = humanize_velocity(base_velocity, variation=0.1)
                kebero_bass.append((tick, pulse * 3, vel))
            
            # Slaps creating the "response" 
            # Traditional pattern: bass-slap-slap, bass-slap-slap
            # In 6/8: pulses 2, 4 (responses after each bass)
            # In 12/8: pulses 2, 4, 8, 10
            trad_slap_pulses = [2, 4] if num_pulses == 6 else [2, 4, 8, 10]
            for pulse_num in trad_slap_pulses:
                tick = bar_offset + (pulse_num * pulse)
                tick = humanize_timing(tick, swing=0.04, timing_variation=0.03)
                vel = humanize_velocity(base_velocity - 15, variation=0.12)
                kebero_slap.append((tick, pulse, vel))
            
            # Occasional atamo accent
            if random.random() < 0.5:
                # Accent on off-beat positions
                atamo_choices = [2, 5] if num_pulses == 6 else [3, 9]
                pulse_num = random.choice(atamo_choices)
                tick = bar_offset + (pulse_num * pulse)
                vel = humanize_velocity(base_velocity - 20, variation=0.15)
                atamo.append((tick, pulse, vel))
            
            # Light shaker on main pulses only (every 3rd pulse)
            main_pulses = list(range(0, num_pulses, 3))
            for pulse_num in main_pulses:
                tick = bar_offset + (pulse_num * pulse)
                vel = humanize_velocity(base_velocity - 35, variation=0.12)
                shaker.append((tick, pulse * 2, vel))
        
        elif style == 'ethio_jazz':
            # Ethio-jazz: jazz kit with Ethiopian rhythmic influence
            # Think Mulatu Astatke - ride cymbal with 12/8 feel
            
            # Kick with Ethiopian accent pattern (syncopated)
            # In 6/8: pulses 0, 4 (beat 1 and syncopated before beat 2)
            # In 12/8: pulses 0, 5, 9
            jazz_kick_pulses = [0, 4] if num_pulses == 6 else [0, 5, 9]
            for pulse_num in jazz_kick_pulses:
                tick = bar_offset + (pulse_num * pulse)
                vel = humanize_velocity(base_velocity, variation=0.08)
                kebero_bass.append((tick, pulse * 2, vel))
            
            # Snare backbeat with ghost notes
            # In 6/8: pulse 3 (beat 2)
            # In 12/8: pulses 3, 9 ("2" and "4" feel)
            snare_pulses = [3] if num_pulses == 6 else [3, 9]
            for pulse_num in snare_pulses:
                tick = bar_offset + (pulse_num * pulse)
                vel = humanize_velocity(base_velocity - 5, variation=0.1)
                kebero_slap.append((tick, pulse, vel))
            
            # Ghost notes for jazz feel
            # In 6/8: pulses 1, 4
            # In 12/8: pulses 1, 4, 7, 10
            ghost_pulses = [1, 4] if num_pulses == 6 else [1, 4, 7, 10]
            for pulse_num in ghost_pulses:
                if random.random() < 0.6:
                    tick = bar_offset + (pulse_num * pulse)
                    vel = humanize_velocity(40, variation=0.2)
                    atamo.append((tick, pulse // 2, vel))
            
            # Ride cymbal in compound meter
            for pulse_num in range(num_pulses):
                tick = bar_offset + (pulse_num * pulse)
                tick = humanize_timing(tick, swing=0.06, timing_variation=0.015)
                if pulse_num % 3 == 0:
                    vel = humanize_velocity(base_velocity - 15, variation=0.1)
                else:
                    vel = humanize_velocity(base_velocity - 30, variation=0.15)
                shaker.append((tick, pulse // 2, vel))
        
        else:  # Default 'ethiopian' modern style
            # Modern Ethiopian pop - blend of styles
            
            # Kick with compound feel
            # In 6/8: pulses 0, 4 (beat 1 and syncopated)
            # In 12/8: pulses 0, 5, 8
            modern_kick_pulses = [0, 4] if num_pulses == 6 else [0, 5, 8]
            for pulse_num in modern_kick_pulses:
                tick = bar_offset + (pulse_num * pulse)
                vel = humanize_velocity(base_velocity, variation=0.08)
                kebero_bass.append((tick, pulse * 2, vel))
            
            # Snare/clap on backbeats
            # In 6/8: pulse 3 (beat 2)
            # In 12/8: pulses 3 and 9
            modern_snare_pulses = [3] if num_pulses == 6 else [3, 9]
            for pulse_num in modern_snare_pulses:
                tick = bar_offset + (pulse_num * pulse)
                vel = humanize_velocity(base_velocity - 10, variation=0.1)
                kebero_slap.append((tick, pulse, vel))
            
            # Hihat in compound meter with swing
            # Use the pulse grid for proper 6/8 or 12/8 feel
            for pulse_num in range(num_pulses):
                tick = bar_offset + (pulse_num * pulse)
                is_offbeat = pulse_num % 3 != 0  # Off-beat in compound meter
                tick = humanize_timing(tick, swing=0.08, timing_variation=0.02, is_offbeat=is_offbeat)
                # Accent main beats (every 3rd pulse)
                if pulse_num % 3 == 0:
                    vel = humanize_velocity(base_velocity - 15, variation=0.08)
                else:
                    vel = humanize_velocity(base_velocity - 30, variation=0.12)
                shaker.append((tick, pulse // 2, vel))
            
            # Percussion texture
            for pulse_num in range(num_pulses):
                if random.random() < 0.5:
                    tick = bar_offset + (pulse_num * pulse)
                    vel = humanize_velocity(base_velocity - 35, variation=0.15)
                    atamo.append((tick, pulse // 2, vel))
    
    # Return with semantic names for proper mapping
    return {
        'kebero_bass': kebero_bass,
        'kebero_slap': kebero_slap,
        'atamo': atamo,
        'shaker': shaker,
    }


# =============================================================================
# MELODIC GENERATORS
# =============================================================================

def generate_808_bass_pattern(
    bars: int,
    root: str,
    scale_type: ScaleType,
    octave: int = 1,
    base_velocity: int = 100,
    genre: Optional[str] = None
) -> List[Tuple[int, int, int, int]]:
    """
    Generate 808 bass pattern.
    
    Returns:
        List of (tick, duration, pitch, velocity) tuples
    """
    pattern = []
    ticks_per_bar = TICKS_PER_BAR_4_4
    
    # Get scale notes for bass
    scale_notes = get_scale_notes(root, scale_type, octave=octave, num_octaves=1)
    root_note = scale_notes[0]
    fifth_note = scale_notes[4] if len(scale_notes) > 4 else root_note
    seventh_note = scale_notes[6] if len(scale_notes) > 6 else fifth_note
    
    for bar in range(bars):
        bar_offset = bar * ticks_per_bar

        is_trap_like = (genre in ['trap', 'drill'])

        if is_trap_like:
            # Trap 808: half-time oriented, more syncopated + occasional approach notes.
            # Always anchor the downbeat.
            events: List[Tuple[float, int, int]] = []  # (beat_pos, duration_ticks, pitch)

            # Downbeat sustain (1-2 beats)
            down_dur = random.choice([TICKS_PER_BEAT, TICKS_PER_BEAT * 2])
            events.append((0.0, down_dur, root_note))

            # Mid-bar hits (typical trap placements)
            candidate_beats = [1.5, 1.75, 2.0, 2.5, 3.0, 3.25, 3.5]
            random.shuffle(candidate_beats)
            num_extra = random.randint(2, 4)
            for b in candidate_beats[:num_extra]:
                dur = random.choice([TICKS_PER_16TH * 3, TICKS_PER_8TH, TICKS_PER_BEAT])
                pitch = random.choices(
                    [root_note, fifth_note, seventh_note],
                    weights=[0.65, 0.25, 0.10],
                    k=1
                )[0]
                events.append((b, dur, pitch))

            # Sort by time
            events.sort(key=lambda x: x[0])

            # Emit notes, with occasional approach "slides" (chromatic 16th before the note)
            for beat_pos, duration, pitch in events:
                tick_offset = beats_to_ticks(beat_pos)

                if random.random() < 0.22 and tick_offset >= TICKS_PER_16TH:
                    approach_tick = tick_offset - TICKS_PER_16TH
                    approach_pitch = pitch + random.choice([-1, 1])
                    approach_vel = humanize_velocity(max(45, base_velocity - 35), variation=0.15)
                    pattern.append((bar_offset + approach_tick, TICKS_PER_16TH, approach_pitch, approach_vel))

                vel = humanize_velocity(base_velocity, variation=0.08)
                pattern.append((bar_offset + tick_offset, duration, pitch, vel))

        else:
            # Simpler 808 pattern (legacy)
            positions = [
                (0, TICKS_PER_BEAT * 2, root_note),  # Hold for 2 beats
                (beats_to_ticks(2.5), TICKS_PER_BEAT, root_note),  # Short hit
            ]

            # Add variation every other bar
            if bar % 2 == 1:
                positions.append((beats_to_ticks(3.5), TICKS_PER_8TH, fifth_note))

            for tick_offset, duration, pitch in positions:
                vel = humanize_velocity(base_velocity, variation=0.08)
                pattern.append((bar_offset + tick_offset, duration, pitch, vel))
    
    return pattern


def generate_chord_progression_midi(
    bars: int,
    key: str,
    scale_type: ScaleType,
    progression: List[int] = None,
    octave: int = 4,
    base_velocity: int = 85,
    rhythm_style: str = 'block',
    chord_color: bool = False,
    complexity: float = 0.5,
    genre: Optional[str] = None,
    section_type: Optional[str] = None
) -> List[Tuple[int, int, int, int]]:
    """
    Generate chord progression MIDI.
    
    Args:
        bars: Number of bars
        key: Root key
        scale_type: Scale type
        progression: Scale degrees (e.g., [1, 4, 6, 5])
        octave: Base octave
        base_velocity: Base velocity
        rhythm_style: 'block', 'arpeggiate', or 'stab'
    
    Returns:
        List of (tick, duration, pitch, velocity) tuples
    """
    complexity = max(0.0, min(1.0, float(complexity)))
    genre_lower = (genre or "").lower().strip()

    def _base_degree_qualities() -> List[str]:
        if scale_type in [ScaleType.MAJOR, ScaleType.MIXOLYDIAN, ScaleType.LYDIAN]:
            return ['major', 'minor', 'minor', 'major', 'major', 'minor', 'dim']
        return ['minor', 'dim', 'major', 'minor', 'minor', 'major', 'major']

    def _color_quality_for_degree(base_quality: str, degree: int) -> str:
        """Map triad quality to 7th/9th/sus/add9 flavor based on complexity + genre."""
        # Always keep diminished stable.
        if base_quality == 'dim':
            return 'dim7' if complexity >= 0.7 else 'dim'

        # Conservative genres: keep chord vocabulary simpler.
        conservative = genre_lower in ['trap', 'trap_soul', 'g_funk', 'ethiopian_traditional', 'eskista']
        jazzier = genre_lower in ['jazz', 'ethio_jazz']

        # Base probability of richer chords.
        # 0.0 -> almost always triads, 1.0 -> mostly 7ths/9ths
        p_color = 0.10 + 0.80 * max(0.0, complexity - 0.30) / 0.70
        if conservative:
            p_color *= 0.6
        if jazzier:
            p_color *= 1.15

        use_color = chord_color or (random.random() < p_color)
        if not use_color:
            # Add occasional sus at medium complexity for movement without "jazzy" harmony.
            if complexity >= 0.45 and random.random() < (0.08 if conservative else 0.12):
                return random.choice(['sus2', 'sus4'])
            return base_quality

        # Choose 7ths vs 9ths.
        wants_9 = complexity >= 0.78 and random.random() < (0.30 if jazzier else 0.18)

        # Dominant on V (degree 5) reads "pro" in many genres.
        if degree == 5:
            return '9' if wants_9 and not conservative else '7'

        if base_quality == 'major':
            if wants_9 and not conservative:
                return random.choice(['add9', 'maj7'])
            return 'maj7'

        # Minor
        if wants_9 and jazzier:
            return 'm9'
        return 'm7'

    def _voice_lead(prev: Optional[List[int]], chord_notes: List[int]) -> List[int]:
        """Very small voice-leading: choose inversions to minimize distance to previous chord."""
        if not prev or len(chord_notes) < 3 or complexity < 0.55:
            return chord_notes

        best = chord_notes
        best_cost = float('inf')

        # Try up to 3 inversions (rotate lowest note up an octave)
        candidate = chord_notes[:]
        for _ in range(3):
            prev_center = sum(prev) / len(prev)
            cand_center = sum(candidate) / len(candidate)
            # cost: distance between centers + summed nearest-note distances
            center_cost = abs(cand_center - prev_center)
            nn_cost = 0.0
            for n in candidate:
                nn_cost += min(abs(n - p) for p in prev)
            cost = center_cost + 0.15 * nn_cost
            if cost < best_cost:
                best_cost = cost
                best = candidate[:]

            # Next inversion
            candidate = candidate[1:] + [candidate[0] + 12]

        return best

    if progression is None:
        # Default progressions by mood
        if scale_type == ScaleType.MINOR:
            progression = [1, 6, 3, 7]  # i VI III VII
        else:
            progression = [1, 5, 6, 4]  # I V vi IV
    
    pattern = []
    ticks_per_bar = TICKS_PER_BAR_4_4

    # Build scale degrees to chord notes with complexity-aware qualities.
    scale_notes = get_scale_notes(key, scale_type, octave, 1)
    base_qualities = _base_degree_qualities()
    chords = []
    for degree in progression:
        if 1 <= degree <= 7:
            root_note = scale_notes[degree - 1]
            root_name, _ = midi_to_note_name(root_note)
            base_quality = base_qualities[degree - 1]
            quality = _color_quality_for_degree(base_quality, degree)
            chords.append(get_chord_notes(root_name, quality, octave))
    
    # How many bars per chord
    bars_per_chord = max(1, bars // len(progression))
    
    chord_index = 0
    prev_chord_notes: Optional[List[int]] = None
    for bar in range(bars):
        bar_offset = bar * ticks_per_bar
        
        # Change chord every N bars
        if bar > 0 and bar % bars_per_chord == 0:
            chord_index = (chord_index + 1) % len(chords)
        
        chord_notes = chords[chord_index]
        chord_notes = _voice_lead(prev_chord_notes, chord_notes)
        prev_chord_notes = chord_notes
        
        if rhythm_style == 'block':
            # Play full chord at start of bar, hold for bar
            for pitch in chord_notes:
                vel = humanize_velocity(base_velocity, variation=0.1)
                pattern.append((bar_offset, ticks_per_bar, pitch, vel))

            # Optional passing/approach hit near bar end for jazzier contexts.
            # Keep it subtle and only at higher complexity.
            if complexity >= 0.82 and genre_lower in ['jazz', 'ethio_jazz', 'rnb'] and random.random() < 0.22:
                next_index = (chord_index + 1) % len(chords)
                next_chord = chords[next_index]
                # Use a sus/add9 color on the next root for a tasteful push.
                passing_root_name, _ = midi_to_note_name(next_chord[0])
                passing_quality = random.choice(['sus2', 'sus4', 'add9'])
                passing = get_chord_notes(passing_root_name, passing_quality, octave)
                passing = _voice_lead(chord_notes, passing)
                passing_tick = bar_offset + beats_to_ticks(3.5)
                for pitch in passing[: min(4, len(passing))]:
                    vel = humanize_velocity(int(base_velocity * 0.92), variation=0.12)
                    pattern.append((passing_tick, TICKS_PER_8TH, pitch, vel))
        
        elif rhythm_style == 'arpeggiate':
            # Arpeggiate through chord notes
            notes_per_bar = 4
            for i, pitch in enumerate(chord_notes[:notes_per_bar]):
                tick = bar_offset + (i * TICKS_PER_BEAT)
                duration = TICKS_PER_BEAT
                vel = humanize_velocity(base_velocity - (i * 5), variation=0.12)
                pattern.append((tick, duration, pitch, vel))
        
        elif rhythm_style == 'stab':
            # Short chord stabs
            stab_positions = [0, 1.5, 3]
            for pos in stab_positions:
                tick = bar_offset + beats_to_ticks(pos)
                for pitch in chord_notes:
                    vel = humanize_velocity(base_velocity, variation=0.08)
                    pattern.append((tick, TICKS_PER_8TH, pitch, vel))

        elif rhythm_style == 'trap_staccato':
            # Trap/church keys: staccato hits with a bit of syncopation.
            # Keep it sparse so it reads like a pianist riffing, not pads.
            hit_positions = [0.0, 0.5, 1.5, 2.5, 3.25, 3.5]
            # Pick 3-4 hits per bar
            random.shuffle(hit_positions)
            chosen = sorted(hit_positions[:random.randint(3, 4)])
            for pos in chosen:
                tick = bar_offset + beats_to_ticks(pos)
                dur = random.choice([TICKS_PER_16TH * 3, TICKS_PER_8TH])
                for pitch in chord_notes:
                    vel = humanize_velocity(base_velocity, variation=0.10)
                    pattern.append((tick, dur, pitch, vel))
    
    return pattern


def generate_melody(
    bars: int,
    key: str,
    scale_type: ScaleType,
    octave: int = 5,
    density: float = 0.5,
    base_velocity: int = 90
) -> List[Tuple[int, int, int, int]]:
    """
    Generate simple melodic line.
    
    Uses pentatonic scale for safer melody generation.
    """
    pattern = []
    ticks_per_bar = TICKS_PER_BAR_4_4
    
    # Use pentatonic for simpler melodies
    if scale_type == ScaleType.MINOR:
        penta_scale = ScaleType.PENTATONIC_MINOR
    else:
        penta_scale = ScaleType.PENTATONIC_MAJOR
    
    scale_notes = get_scale_notes(key, penta_scale, octave=octave, num_octaves=1)
    
    prev_note = scale_notes[2]  # Start on 3rd scale degree
    
    for bar in range(bars):
        bar_offset = bar * ticks_per_bar
        
        # Generate notes based on density
        num_notes = int(4 * density) + 1
        positions = sorted(random.sample(range(8), min(num_notes, 8)))
        
        for pos in positions:
            tick = bar_offset + (pos * TICKS_PER_8TH)
            
            # Melodic motion: prefer stepwise, occasional leaps
            if random.random() < 0.7:
                # Step
                step = random.choice([-1, 1])
                prev_idx = scale_notes.index(prev_note) if prev_note in scale_notes else 0
                new_idx = max(0, min(len(scale_notes) - 1, prev_idx + step))
            else:
                # Leap
                new_idx = random.randint(0, len(scale_notes) - 1)
            
            pitch = scale_notes[new_idx]
            prev_note = pitch
            
            duration = random.choice([TICKS_PER_8TH, TICKS_PER_BEAT])
            vel = humanize_velocity(base_velocity, variation=0.12)
            
            pattern.append((tick, duration, pitch, vel))
    
    return pattern


def generate_gfunk_bass_pattern(
    bars: int,
    root: str,
    scale_type: ScaleType,
    octave: int = 1,
    base_velocity: int = 100
) -> List[Tuple[int, int, int, int]]:
    """
    Generate G-Funk style bass pattern.
    
    Characteristics:
    - Deep, rolling, legato feel
    - Octave jumps (low root -> high octave -> slide down)
    - Syncopated 16th notes but always anchoring the 1
    - Funk influence (Bootsy Collins / Parliament style adapted for synth)
    """
    pattern = []
    ticks_per_bar = TICKS_PER_BAR_4_4
    
    scale_notes = get_scale_notes(root, scale_type, octave=octave, num_octaves=2)
    root_low = scale_notes[0]
    root_high = scale_notes[7] if len(scale_notes) > 7 else root_low + 12
    fifth = scale_notes[4] if len(scale_notes) > 4 else root_low + 7
    flat_seven = scale_notes[6] if len(scale_notes) > 6 else root_low + 10
    
    for bar in range(bars):
        bar_offset = bar * ticks_per_bar
        
        # G-Funk bass usually anchors the downbeat heavily
        # Pattern A: The "One"
        pattern.append((bar_offset, TICKS_PER_8TH * 3, root_low, humanize_velocity(base_velocity, variation=0.05)))
        
        # Variation per bar
        if bar % 4 == 0:
            # Classic rolling line
            # Beat 2.5 (and of 2)
            pattern.append((bar_offset + beats_to_ticks(2.5), TICKS_PER_16TH, root_high, humanize_velocity(base_velocity - 10, variation=0.1)))
            # Beat 3
            pattern.append((bar_offset + beats_to_ticks(3), TICKS_PER_8TH, flat_seven, humanize_velocity(base_velocity - 5, variation=0.1)))
            # Beat 4
            pattern.append((bar_offset + beats_to_ticks(4), TICKS_PER_8TH, fifth, humanize_velocity(base_velocity - 5, variation=0.1)))
            
        elif bar % 4 == 1:
            # Octave jump focus
            pattern.append((bar_offset + beats_to_ticks(1.5), TICKS_PER_16TH, root_low, humanize_velocity(base_velocity - 15, variation=0.1)))
            pattern.append((bar_offset + beats_to_ticks(2), TICKS_PER_8TH, root_high, humanize_velocity(base_velocity, variation=0.08)))
            pattern.append((bar_offset + beats_to_ticks(3.5), TICKS_PER_8TH, fifth, humanize_velocity(base_velocity - 10, variation=0.1)))
            
        elif bar % 4 == 2:
            # Syncopated funk
            pattern.append((bar_offset + beats_to_ticks(1.75), TICKS_PER_16TH, root_low, humanize_velocity(base_velocity - 10, variation=0.1)))
            pattern.append((bar_offset + beats_to_ticks(2), TICKS_PER_16TH, root_low, humanize_velocity(base_velocity - 10, variation=0.1)))
            pattern.append((bar_offset + beats_to_ticks(2.5), TICKS_PER_8TH, flat_seven, humanize_velocity(base_velocity - 5, variation=0.1)))
            pattern.append((bar_offset + beats_to_ticks(3.5), TICKS_PER_8TH, root_high, humanize_velocity(base_velocity, variation=0.08)))
            
        else:
            # Turnaround / Fill
            pattern.append((bar_offset + beats_to_ticks(2), TICKS_PER_16TH, fifth, humanize_velocity(base_velocity - 10, variation=0.1)))
            pattern.append((bar_offset + beats_to_ticks(2.25), TICKS_PER_16TH, flat_seven, humanize_velocity(base_velocity - 5, variation=0.1)))
            pattern.append((bar_offset + beats_to_ticks(2.5), TICKS_PER_16TH, root_high, humanize_velocity(base_velocity, variation=0.05)))
            pattern.append((bar_offset + beats_to_ticks(3), TICKS_PER_8TH, flat_seven, humanize_velocity(base_velocity - 10, variation=0.1)))
            pattern.append((bar_offset + beats_to_ticks(3.5), TICKS_PER_8TH, fifth, humanize_velocity(base_velocity - 10, variation=0.1)))

    return pattern


def generate_gfunk_lead_pattern(
    bars: int,
    key: str,
    scale_type: ScaleType,
    octave: int = 5,
    base_velocity: int = 95
) -> List[Tuple[int, int, int, int]]:
    """
    Generate G-Funk high synth lead (whine).
    
    Characteristics:
    - High pitch (octave 5/6)
    - Long sustained notes (whole notes, tied notes)
    - Portamento/Gliding feel (simulated by overlapping or close notes)
    - Simple melodic contour (often just Root, 7th, 5th)
    - Call and response
    """
    pattern = []
    ticks_per_bar = TICKS_PER_BAR_4_4
    
    scale_notes = get_scale_notes(key, scale_type, octave=octave, num_octaves=2)
    root = scale_notes[0]
    fifth = scale_notes[4] if len(scale_notes) > 4 else root + 7
    flat_seven = scale_notes[6] if len(scale_notes) > 6 else root + 10
    high_root = scale_notes[7] if len(scale_notes) > 7 else root + 12
    
    # G-Funk leads are sparse. Usually one long phrase every 2 or 4 bars.
    
    for bar in range(0, bars, 4): # Process in 4-bar chunks
        bar_offset = bar * ticks_per_bar
        remaining_bars = min(4, bars - bar)
        
        if remaining_bars < 2:
            continue
            
        # Phrase 1: The "Whine" - High sustained root or fifth
        # Start on beat 2 of first bar, hold for 2 bars
        start_tick = bar_offset + beats_to_ticks(1)
        duration = TICKS_PER_BAR_4_4 * 1.5
        pitch = random.choice([high_root, fifth])
        
        pattern.append((start_tick, int(duration), pitch, humanize_velocity(base_velocity, variation=0.05)))
        
        # Phrase 2: The "Comedown" - Descending line in 3rd/4th bar
        if remaining_bars >= 4:
            descent_start = bar_offset + (2 * TICKS_PER_BAR_4_4) + beats_to_ticks(2)
            
            # Simple descending motif
            motif = [
                (0, TICKS_PER_BEAT, flat_seven),
                (1, TICKS_PER_BEAT, fifth),
                (2, TICKS_PER_BEAT * 2, root)
            ]
            
            for beat_offset, dur, p in motif:
                tick = descent_start + beats_to_ticks(beat_offset)
                pattern.append((tick, int(dur), p, humanize_velocity(base_velocity - 5, variation=0.1)))

    return pattern


# =============================================================================
# MAIN MIDI GENERATOR CLASS
# =============================================================================

class MidiGenerator:
    """
    Main class for generating humanized MIDI from arrangements.
    
    Orchestrates drum, bass, chord, and melody generation with
    professional-level humanization including physics-aware drum modeling.
    
    Supports optional InstrumentResolutionService for dynamic instrument
    resolution from expansion packs.
    """
    
    def __init__(
        self,
        velocity_variation: float = 0.12,
        timing_variation: float = 0.03,
        swing: float = 0.0,
        use_physics_humanization: bool = True,
        instrument_service: Optional['InstrumentResolutionService'] = None
    ):
        """
        Initialize the MIDI generator.
        
        Args:
            velocity_variation: Velocity randomization factor (0-1)
            timing_variation: Timing jitter factor (0-1)
            swing: Swing amount for offbeats (0-1)
            use_physics_humanization: Enable physics-aware humanization
                                     (fatigue, limb conflicts, ghost notes)
            instrument_service: Optional InstrumentResolutionService for
                               dynamic instrument resolution from expansions
        """
        self.velocity_variation = velocity_variation
        self.timing_variation = timing_variation
        self.swing = swing
        self.use_physics_humanization = use_physics_humanization and HAS_PHYSICS_HUMANIZER
        self.groove_applicator = GrooveApplicator()
        
        # Store instrument resolution service
        self._instrument_service = instrument_service
        
        if self.use_physics_humanization:
            print("  [*] Physics humanization enabled")
        elif use_physics_humanization and not HAS_PHYSICS_HUMANIZER:
            print("  [!] Physics humanization requested but module not available")
        
        if instrument_service:
            print("  [*] Instrument resolution service enabled")
    
    def generate(
        self,
        arrangement: Arrangement,
        parsed: ParsedPrompt,
        groove_template: Optional[GrooveTemplate] = None,
        policy_context: Optional['PolicyContext'] = None
    ) -> MidiFile:
        """
        Generate complete MIDI file from arrangement.
        
        Args:
            arrangement: Song arrangement
            parsed: Parsed prompt with musical parameters
            groove_template: Optional groove template to apply
            policy_context: Optional PolicyContext from StylePolicy for 
                           coherent producer-level decisions
        
        Returns:
            mido.MidiFile ready to save
        """
        # Store policy context for use in sub-methods
        self._policy_context = policy_context
        
        # If policy context provided, extract timing parameters
        if policy_context:
            # Override groove-related settings from policy
            self.swing = policy_context.timing.swing_amount
            self.velocity_variation = policy_context.timing.velocity_variation
            self.timing_variation = policy_context.timing.timing_jitter
        
        # Resolve groove template
        if groove_template is None and parsed.genre:
            groove_template = get_groove_for_genre(parsed.genre)
            
        # Create MIDI file
        mid = MidiFile(ticks_per_beat=TICKS_PER_BEAT)
        
        # Track 0: Tempo/time signature (meta track)
        meta_track = self._create_meta_track(arrangement, parsed)
        mid.tracks.append(meta_track)
        
        # Track 1: Drums (channel 10)
        drum_track = self._create_drum_track(arrangement, parsed, groove_template)
        mid.tracks.append(drum_track)
        
        # Track 2: Bass/808
        if '808' in parsed.instruments or 'bass' in parsed.instruments:
            bass_track = self._create_bass_track(arrangement, parsed, groove_template)
            mid.tracks.append(bass_track)
        
        # Track 3: Chords - includes both standard and Ethiopian instruments
        chord_instruments = [
            'piano', 'rhodes', 'pad', 'strings', 'organ', 'brass',
            # Ethiopian instruments
            'krar', 'masenqo', 'begena'
        ]
        if any(inst in parsed.instruments for inst in chord_instruments):
            chord_track = self._create_chord_track(arrangement, parsed, groove_template)
            mid.tracks.append(chord_track)

        # Optional: Organ bed for churchy trap keys
        wants_church = any(m in parsed.style_modifiers for m in ['church', 'gospel', 'zaytoven']) or ('zaytoven' in (parsed.raw_prompt or '').lower())
        if parsed.genre in ['trap', 'trap_soul'] and wants_church:
            organ_track = self._create_organ_track(arrangement, parsed, groove_template)
            if len(organ_track) > 1:
                mid.tracks.append(organ_track)
        
        # Track 4: Melody (optional) - especially for Ethiopian flute/lead
        melody_instruments = ['washint', 'flute', 'synth_lead', 'synth']
        has_melody_inst = any(inst in parsed.instruments for inst in melody_instruments)
        if parsed.genre not in ['ambient', 'lofi'] or has_melody_inst:
            melody_track = self._create_melody_track(arrangement, parsed, groove_template)
            if len(melody_track) > 1:  # Has notes beyond track name
                mid.tracks.append(melody_track)
        
        return mid

    def _tension_multiplier(self, tension: float, min_mult: float, max_mult: float) -> float:
        tension = max(0.0, min(1.0, float(tension)))
        return min_mult + (max_mult - min_mult) * tension

    def _get_section_tension(self, arrangement: Arrangement, section: SongSection) -> float:
        """Return tension (0-1) at the section midpoint, if available."""
        arc = getattr(arrangement, "tension_arc", None)
        if not arc or arrangement.total_ticks <= 0:
            return 0.5

        mid_tick = (section.start_tick + section.end_tick) / 2.0
        position = mid_tick / float(arrangement.total_ticks)
        try:
            value = arc.get_tension_at(position)
            if value is None:
                return 0.5
            return max(0.0, min(1.0, float(value)))
        except Exception:
            return 0.5

    def _get_section_complexity(self, arrangement: Arrangement, section: SongSection, genre: str) -> float:
        """Derive a 0-1 complexity target from tension + genre defaults."""
        base_by_genre = {
            'g_funk': 0.45,
            'trap': 0.40,
            'trap_soul': 0.45,
            'rnb': 0.55,
            'lofi': 0.50,
            'house': 0.55,
            'ethiopian_traditional': 0.35,
            'eskista': 0.40,
            'ethiopian': 0.45,
            'ethio_jazz': 0.70,
            'jazz': 0.75,
            'classical': 0.70,
            'pop': 0.50,
            'hip_hop': 0.50,
        }
        genre_key = (genre or 'pop').lower()
        base = base_by_genre.get(genre_key, 0.50)

        tension = self._get_section_tension(arrangement, section)
        arc = getattr(arrangement, "tension_arc", None)
        influence = 0.5
        try:
            influence = float(getattr(getattr(arc, 'config', None), 'complexity_influence', 0.5)) if arc else 0.5
        except Exception:
            influence = 0.5

        # Section-type shaping (small): choruses/drops can tolerate more.
        if section.section_type in [SectionType.CHORUS, SectionType.DROP, SectionType.VARIATION]:
            base += 0.05
        if section.section_type in [SectionType.INTRO, SectionType.BREAKDOWN, SectionType.OUTRO]:
            base -= 0.05

        # Convert tension (0-1) into a signed modulation around base.
        mod = (tension - 0.5) * 0.90 * influence
        return max(0.0, min(1.0, base + mod))
    
    def _resolve_instrument_program(
        self,
        instrument_name: str,
        genre: str = "",
        default_program: int = 0
    ) -> int:
        """
        Resolve an instrument name to a MIDI program number.
        
        Uses InstrumentResolutionService if available, otherwise falls back
        to hardcoded defaults.
        
        Args:
            instrument_name: The instrument to resolve
            genre: The genre context for resolution
            default_program: Fallback program if resolution fails
            
        Returns:
            MIDI program number (0-127)
        """
        if self._instrument_service:
            resolved = self._instrument_service.resolve_instrument(
                instrument_name, 
                genre=genre
            )
            return resolved.program
        
        return default_program
    
    def _create_meta_track(
        self,
        arrangement: Arrangement,
        parsed: ParsedPrompt
    ) -> MidiTrack:
        """Create track 0 with tempo and time signature."""
        track = MidiTrack()
        
        # Track name
        track.append(MetaMessage('track_name', name='Meta', time=0))
        
        # Time signature
        num, denom = arrangement.time_signature
        # MIDI time sig: denominator is log2
        denom_log2 = {1: 0, 2: 1, 4: 2, 8: 3, 16: 4}.get(denom, 2)
        track.append(MetaMessage(
            'time_signature',
            numerator=num,
            denominator=denom_log2,
            clocks_per_click=24,
            notated_32nd_notes_per_beat=8,
            time=0
        ))
        
        # Tempo
        tempo_us = bpm_to_microseconds_per_beat(arrangement.bpm)
        track.append(MetaMessage('set_tempo', tempo=tempo_us, time=0))
        
        # Key signature
        # In mido, key_signature just takes 'key' as a string like 'C', 'Am', 'F#m'
        # Valid keys: C, D, E, F, G, A, B with optional # or b, plus 'm' for minor
        # Strip "major" or "minor" suffix if present, as mido only wants the note
        key_str = parsed.key.replace(' major', '').replace(' minor', '').strip()
        
        # MIDI key signatures use circle of fifths: flats from F to Cb, sharps from G to C#
        # Convert sharp keys that don't exist in MIDI to their flat equivalents
        key_mapping = {
            'G#': 'Ab', 'D#': 'Eb', 'A#': 'Bb',  # Sharp to flat (these sharps aren't valid MIDI keys)
            'E#': 'F', 'B#': 'C',                 # Enharmonic simplification
        }
        key_str = key_mapping.get(key_str, key_str)
        
        if parsed.scale_type == ScaleType.MINOR:
            key_str = f"{key_str}m"
        
        # Valid MIDI key signatures (circle of fifths)
        valid_keys = [
            # Major keys: Cb(-7) to C#(+7)
            'C', 'G', 'D', 'A', 'E', 'B', 'F#', 'C#',  # Sharp keys
            'F', 'Bb', 'Eb', 'Ab', 'Db', 'Gb', 'Cb',   # Flat keys
            # Minor keys
            'Am', 'Em', 'Bm', 'F#m', 'C#m', 'G#m', 'D#m', 'A#m',  # Sharp-side minors
            'Dm', 'Gm', 'Cm', 'Fm', 'Bbm', 'Ebm', 'Abm',          # Flat-side minors
        ]
        if key_str in valid_keys:
            track.append(MetaMessage('key_signature', key=key_str, time=0))
        
        # End of track
        track.append(MetaMessage('end_of_track', time=arrangement.total_ticks))
        
        return track
    
    def _create_drum_track(
        self,
        arrangement: Arrangement,
        parsed: ParsedPrompt,
        groove_template: Optional[GrooveTemplate] = None
    ) -> MidiTrack:
        """Generate drum track with humanized patterns."""
        track = MidiTrack()
        track.append(MetaMessage('track_name', name='Drums', time=0))
        
        all_notes = []
        
        for section in arrangement.sections:
            tension = self._get_section_tension(arrangement, section)
            section_notes = self._generate_drums_for_section(section, parsed, tension)
            all_notes.extend(section_notes)
        
        # Convert to MIDI messages with physics humanization
        self._notes_to_track(
            all_notes, track, 
            channel=GM_DRUM_CHANNEL, 
            groove_template=groove_template,
            bpm=arrangement.bpm,
            genre=parsed.genre or "default",
            role="drums"
        )
        
        return track
    
    def _generate_drums_for_section(
        self,
        section: SongSection,
        parsed: ParsedPrompt,
        tension: float = 0.5
    ) -> List[NoteEvent]:
        """
        Generate drums for a single section using genre strategy.
        
        This method uses the Strategy Pattern to delegate drum generation
        to genre-specific strategy classes. This allows adding new genres
        without modifying this method (Open/Closed Principle).
        
        To add a new genre:
        1. Create a new strategy class in multimodal_gen/strategies/
        2. Implement the GenreStrategy interface
        3. Register it in the StrategyRegistry
        
        Args:
            section: The song section to generate drums for
            parsed: The parsed prompt with musical parameters
            tension: Tension value from 0.0 to 1.0 for dynamics
            
        Returns:
            List of NoteEvent objects for the drum pattern
        """
        # Get strategy for genre (falls back to default if not found)
        strategy = StrategyRegistry.get_or_default(parsed.genre or "default")
        
        # Use strategy to generate drums
        return strategy.generate_drums(section, parsed, tension)
    
    def _create_bass_track(
        self,
        arrangement: Arrangement,
        parsed: ParsedPrompt,
        groove_template: Optional[GrooveTemplate] = None
    ) -> MidiTrack:
        """Generate bass/808 track."""
        track = MidiTrack()
        track.append(MetaMessage('track_name', name='Bass', time=0))
        
        # Program change: Synth Bass (38) for 808 feel
        track.append(Message('program_change', program=38, channel=1, time=0))
        
        all_notes = []
        
        for section in arrangement.sections:
            tension = self._get_section_tension(arrangement, section)
            vel_mult = self._tension_multiplier(tension, 0.90, 1.12)
            if section.config.enable_bass:
                if parsed.genre == 'g_funk':
                    bass_pattern = generate_gfunk_bass_pattern(
                        section.bars,
                        parsed.key,
                        parsed.scale_type,
                        octave=1,
                        base_velocity=int(100 * section.config.energy_level * vel_mult)
                    )
                else:
                    bass_pattern = generate_808_bass_pattern(
                        section.bars,
                        parsed.key,
                        parsed.scale_type,
                        octave=1,
                        base_velocity=int(100 * section.config.energy_level * vel_mult),
                        genre=parsed.genre
                    )
                
                for tick, dur, pitch, vel in bass_pattern:
                    all_notes.append(NoteEvent(
                        pitch=pitch,
                        start_tick=section.start_tick + tick,
                        duration_ticks=dur,
                        velocity=vel,
                        channel=1
                    ))
        
        self._notes_to_track(all_notes, track, channel=1, groove_template=groove_template)
        
        return track
    
    def _create_chord_track(
        self,
        arrangement: Arrangement,
        parsed: ParsedPrompt,
        groove_template: Optional[GrooveTemplate] = None
    ) -> MidiTrack:
        """Generate chord track."""
        track = MidiTrack()
        track.append(MetaMessage('track_name', name='Chords', time=0))
        
        # Program change based on instrument
        # Priority: Ethiopian genres should prefer Ethiopian instruments
        is_ethiopian = parsed.genre in ['ethiopian', 'ethio_jazz', 'ethiopian_traditional', 'eskista']
        
        # Try to resolve instrument via service first (if available)
        program = None
        resolved_instrument = None
        
        if self._instrument_service:
            # Determine which instrument to resolve based on parsed instruments
            instrument_to_resolve = None
            
            # Ethiopian instruments first (if Ethiopian genre or explicitly requested)
            if 'krar' in parsed.instruments and (is_ethiopian or 'piano' not in parsed.instruments):
                instrument_to_resolve = 'krar'
            elif 'masenqo' in parsed.instruments and (is_ethiopian or 'strings' not in parsed.instruments):
                instrument_to_resolve = 'masenqo'
            elif 'begena' in parsed.instruments:
                instrument_to_resolve = 'begena'
            elif 'washint' in parsed.instruments:
                instrument_to_resolve = 'washint'
            elif 'rhodes' in parsed.instruments:
                instrument_to_resolve = 'rhodes'
            elif 'piano' in parsed.instruments:
                instrument_to_resolve = 'piano'
            elif 'pad' in parsed.instruments:
                instrument_to_resolve = 'pad'
            elif 'strings' in parsed.instruments:
                instrument_to_resolve = 'strings'
            elif 'organ' in parsed.instruments:
                instrument_to_resolve = 'organ'
            elif 'brass' in parsed.instruments:
                instrument_to_resolve = 'brass'
            else:
                instrument_to_resolve = 'krar' if is_ethiopian else 'rhodes'
            
            resolved = self._instrument_service.resolve_instrument(
                instrument_to_resolve,
                genre=parsed.genre or ""
            )
            program = resolved.program
            resolved_instrument = resolved.name
        
        # Fallback to hardcoded mappings if no service or resolution failed
        if program is None:
            # Ethiopian instruments first (if Ethiopian genre or explicitly requested)
            if 'krar' in parsed.instruments and (is_ethiopian or 'piano' not in parsed.instruments):
                program = 110  # Custom: Krar (Ethiopian lyre)
            elif 'masenqo' in parsed.instruments and (is_ethiopian or 'strings' not in parsed.instruments):
                program = 111  # Custom: Masenqo (Ethiopian fiddle)
            elif 'begena' in parsed.instruments:
                program = 113  # Custom: Begena (Ethiopian harp)
            elif 'washint' in parsed.instruments:
                program = 112  # Custom: Washint (Ethiopian flute)
            # Standard GM instruments
            elif 'rhodes' in parsed.instruments:
                program = 4  # Electric Piano 1
            elif 'piano' in parsed.instruments:
                program = 0  # Acoustic Grand
            elif 'pad' in parsed.instruments:
                program = 89  # Pad 2 (warm)
            elif 'strings' in parsed.instruments:
                program = 48  # String Ensemble
            elif 'organ' in parsed.instruments:
                program = 16  # Drawbar Organ
            elif 'brass' in parsed.instruments:
                program = 61  # Brass Section
            else:
                # Default based on genre
                if is_ethiopian:
                    program = 110  # Krar for Ethiopian
                else:
                    program = 4  # Rhodes for others
        
        track.append(Message('program_change', program=program, channel=2, time=0))
        
        all_notes = []
        
        # Determine chord style based on genre
        wants_church = any(m in parsed.style_modifiers for m in ['church', 'gospel', 'zaytoven']) or ('zaytoven' in (parsed.raw_prompt or '').lower())
        if parsed.genre in ['trap', 'trap_soul']:
            rhythm_style = 'trap_staccato' if wants_church else 'block'
        elif parsed.genre == 'lofi':
            rhythm_style = 'arpeggiate'
        elif parsed.genre == 'house':
            rhythm_style = 'stab'
        else:
            rhythm_style = 'block'
        
        for section in arrangement.sections:
            tension = self._get_section_tension(arrangement, section)
            vel_mult = self._tension_multiplier(tension, 0.90, 1.10)
            complexity = self._get_section_complexity(arrangement, section, parsed.genre or "pop")
            if section.config.enable_chords:
                chord_pattern = generate_chord_progression_midi(
                    section.bars,
                    parsed.key,
                    parsed.scale_type,
                    octave=4,
                    base_velocity=int(85 * section.config.instrument_density * vel_mult),
                    rhythm_style=rhythm_style,
                    chord_color=wants_church,
                    complexity=complexity,
                    genre=parsed.genre,
                    section_type=section.section_type.value
                )
                
                for tick, dur, pitch, vel in chord_pattern:
                    all_notes.append(NoteEvent(
                        pitch=pitch,
                        start_tick=section.start_tick + tick,
                        duration_ticks=dur,
                        velocity=vel,
                        channel=2
                    ))
        
        self._notes_to_track(all_notes, track, channel=2, groove_template=groove_template)
        
        return track

    def _create_organ_track(
        self,
        arrangement: Arrangement,
        parsed: ParsedPrompt,
        groove_template: Optional[GrooveTemplate] = None
    ) -> MidiTrack:
        """Generate an organ bed (church feel) under the piano."""
        track = MidiTrack()
        track.append(MetaMessage('track_name', name='Organ', time=0))
        track.append(Message('program_change', program=16, channel=4, time=0))

        all_notes = []
        for section in arrangement.sections:
            tension = self._get_section_tension(arrangement, section)
            vel_mult = self._tension_multiplier(tension, 0.90, 1.08)
            complexity = self._get_section_complexity(arrangement, section, parsed.genre or "pop")
            # Keep organ mostly in drops/choruses; avoid clutter in intro/breakdown
            if section.section_type not in [SectionType.DROP, SectionType.CHORUS, SectionType.VARIATION]:
                continue
            if not section.config.enable_chords:
                continue

            chord_pattern = generate_chord_progression_midi(
                section.bars,
                parsed.key,
                parsed.scale_type,
                octave=3,
                base_velocity=int(55 * section.config.instrument_density * vel_mult),
                rhythm_style='block',
                chord_color=True,
                complexity=min(1.0, complexity + 0.10),
                genre=parsed.genre,
                section_type=section.section_type.value
            )
            for tick, dur, pitch, vel in chord_pattern:
                # Reduce density: only keep lower notes to avoid masking piano
                if pitch > note_name_to_midi(parsed.key, 4):
                    continue
                all_notes.append(NoteEvent(
                    pitch=pitch,
                    start_tick=section.start_tick + tick,
                    duration_ticks=dur,
                    velocity=max(35, int(vel * 0.75)),
                    channel=4
                ))

        self._notes_to_track(all_notes, track, channel=4, groove_template=groove_template)
        return track
    
    def _create_melody_track(
        self,
        arrangement: Arrangement,
        parsed: ParsedPrompt,
        groove_template: Optional[GrooveTemplate] = None
    ) -> MidiTrack:
        """Generate optional melody track."""
        track = MidiTrack()
        track.append(MetaMessage('track_name', name='Melody', time=0))
        
        # Try to resolve instrument via service first (if available)
        program = None
        
        if self._instrument_service:
            # Determine which instrument to resolve based on parsed instruments
            instrument_to_resolve = None
            
            if 'washint' in parsed.instruments:
                instrument_to_resolve = 'washint'
            elif 'masenqo' in parsed.instruments:
                instrument_to_resolve = 'masenqo'
            elif 'krar' in parsed.instruments:
                instrument_to_resolve = 'krar'
            elif 'flute' in parsed.instruments:
                instrument_to_resolve = 'flute'
            elif 'brass' in parsed.instruments:
                instrument_to_resolve = 'brass'
            elif 'synth_lead' in parsed.instruments or 'synth' in parsed.instruments:
                instrument_to_resolve = 'synth_lead'
            else:
                instrument_to_resolve = 'synth_lead'
            
            resolved = self._instrument_service.resolve_instrument(
                instrument_to_resolve,
                genre=parsed.genre or ""
            )
            program = resolved.program
        
        # Fallback to hardcoded mappings if no service
        if program is None:
            if 'washint' in parsed.instruments:
                program = 112  # Custom: Washint (Ethiopian flute) - great for melodies
            elif 'masenqo' in parsed.instruments:
                program = 111  # Custom: Masenqo (Ethiopian fiddle)
            elif 'krar' in parsed.instruments:
                program = 110  # Custom: Krar
            elif 'flute' in parsed.instruments:
                program = 73  # Flute
            elif 'brass' in parsed.instruments:
                program = 56  # Trumpet
            elif 'synth_lead' in parsed.instruments or 'synth' in parsed.instruments:
                program = 80  # Lead 1 (square)
            else:
                program = 80  # Lead 1 (square) - default
        
        track.append(Message('program_change', program=program, channel=3, time=0))
        
        all_notes = []

        normalized_genre = normalize_genre(parsed.genre or '')
        is_ethiopian_genre = normalized_genre in [
            'ethiopian', 'ethio_jazz', 'ethiopian_traditional', 'eskista'
        ]
        genre_cfg = GENRE_DEFAULTS.get(normalized_genre, {})
        wants_call_response = bool(genre_cfg.get('call_response', False))
        
        section_counters: Dict[str, int] = {}

        for section in arrangement.sections:
            tension = self._get_section_tension(arrangement, section)
            vel_mult = self._tension_multiplier(tension, 0.90, 1.12)
            density_mult = self._tension_multiplier(tension, 0.85, 1.15)
            complexity = self._get_section_complexity(arrangement, section, parsed.genre or "pop")
            if section.config.enable_melody and section.section_type in [
                SectionType.CHORUS, SectionType.DROP, SectionType.VARIATION
            ]:
                # Section name convention matches arranger.generate_arrangement_with_motifs:
                # "chorus_1", "drop_1", etc.
                st = section.section_type.value
                section_counters[st] = section_counters.get(st, 0) + 1
                section_name = f"{st}_{section_counters[st]}"

                motif = None
                if getattr(arrangement, 'motifs', None) and getattr(arrangement, 'motif_assignments', None):
                    try:
                        motif = get_section_motif(arrangement, section_name)
                    except Exception:
                        motif = None

                if motif is not None:
                    # Build motif melody and snap pitches to the active scale.
                    root_pitch = note_name_to_midi(parsed.key, 5)
                    base_velocity = int(90 * section.config.energy_level * vel_mult)
                    motif_notes = motif.to_midi_notes(
                        root_pitch=root_pitch,
                        start_tick=0,
                        ticks_per_beat=TICKS_PER_BEAT,
                        base_velocity=base_velocity,
                    )

                    # Determine motif length in ticks.
                    motif_len_ticks = 0
                    if motif_notes:
                        last_tick, last_dur, _, _ = motif_notes[-1]
                        motif_len_ticks = int(last_tick + last_dur)
                    motif_len_ticks = max(motif_len_ticks, TICKS_PER_BEAT)

                    section_ticks = int(bars_to_ticks(section.bars, arrangement.time_signature))
                    density = min(1.0, section.config.instrument_density * 0.5 * density_mult)

                    scale_notes = get_scale_notes(parsed.key, parsed.scale_type, octave=1, num_octaves=8)
                    melody = []
                    # Repeat count scales with density (theme-first, not constant noodling).
                    max_repeats = max(1, int(1 + density * 3))
                    gap = int(TICKS_PER_BEAT * (0.5 + (1.0 - density)))

                    offset = 0
                    repeats = 0
                    while offset < section_ticks and repeats < max_repeats:
                        for tick, dur, pitch, vel in motif_notes:
                            abs_tick = offset + int(tick)
                            if abs_tick >= section_ticks:
                                continue
                            dur = int(dur)
                            if abs_tick + dur > section_ticks:
                                dur = max(1, section_ticks - abs_tick)
                            snapped_pitch = _nearest_note_in_scale(int(pitch), scale_notes)
                            melody.append((abs_tick, dur, snapped_pitch, int(vel)))
                        offset += motif_len_ticks + gap
                        repeats += 1
                else:
                    # Fallback generators when motifs are not available.
                    if normalize_genre(parsed.genre or '') == 'g_funk':
                        melody = generate_gfunk_lead_pattern(
                            section.bars,
                            parsed.key,
                            parsed.scale_type,
                            octave=5,
                            base_velocity=int(95 * section.config.energy_level * vel_mult)
                        )
                    else:
                        melody = generate_melody(
                            section.bars,
                            parsed.key,
                            parsed.scale_type,
                            octave=5,
                            density=min(1.0, section.config.instrument_density * 0.5 * density_mult),
                            base_velocity=int(90 * section.config.energy_level * vel_mult)
                        )

                # Ethiopian / ethio-jazz mode-aware embellishment.
                # This avoids chromatic approach tones and instead uses neighbor/grace ornaments
                # constrained to the selected mode (qenet or ethio-jazz scale).
                if melody and is_ethiopian_genre:
                    effective_scale = parsed.scale_type
                    if isinstance(parsed.scale_type, ScaleType) and parsed.scale_type in (ScaleType.MAJOR, ScaleType.MINOR):
                        effective_scale = genre_cfg.get('scale', parsed.scale_type)
                    try:
                        melody = embellish_melody_qenet(
                            melody,
                            key=parsed.key,
                            scale_type=effective_scale,
                            time_signature=arrangement.time_signature,
                            section_bars=section.bars,
                            complexity=complexity,
                            call_response=wants_call_response,
                        )
                    except Exception:
                        # Fail open: never break generation due to embellishment.
                        pass

                # Complexity ornamentation: occasional 16th-note approach tones.
                # Keep for non-Ethiopian styles.
                if melody and (not is_ethiopian_genre) and complexity >= 0.78:
                    allow = (parsed.genre or '').lower() in ['jazz', 'rnb', 'g_funk']
                    if allow:
                        embellished = []
                        for tick, dur, pitch, vel in melody:
                            embellished.append((tick, dur, pitch, vel))
                            if tick >= TICKS_PER_16TH and random.random() < (0.10 + 0.12 * (complexity - 0.78) / 0.22):
                                step = random.choice([-1, 1])
                                approach_pitch = max(0, min(127, pitch + step))
                                approach_tick = max(0, tick - TICKS_PER_16TH)
                                approach_vel = max(20, int(vel * 0.55))
                                embellished.append((approach_tick, TICKS_PER_16TH, approach_pitch, approach_vel))
                        melody = embellished
                
                for tick, dur, pitch, vel in melody:
                    all_notes.append(NoteEvent(
                        pitch=pitch,
                        start_tick=section.start_tick + tick,
                        duration_ticks=dur,
                        velocity=vel,
                        channel=3
                    ))
        
        self._notes_to_track(all_notes, track, channel=3, groove_template=groove_template)
        
        return track
    
    def _notes_to_track(
        self,
        notes: List[NoteEvent],
        track: MidiTrack,
        channel: int,
        groove_template: Optional[GrooveTemplate] = None,
        bpm: float = 90.0,
        genre: str = "default",
        role: str = "drums"
    ):
        """
        Convert list of NoteEvents to MIDI track messages.
        
        Handles delta time calculation, proper note-off ordering,
        collision resolution, and physics-aware humanization.
        
        For drum tracks (channel 9), notes within a small timing window
        are snapped to the same tick to prevent rapid-fire triggering.
        Physics humanization adds realistic limb constraints and fatigue.
        """
        if not notes:
            track.append(MetaMessage('end_of_track', time=0))
            return
        
        # Apply groove if provided
        if groove_template:
            # Convert to dicts for applicator
            note_dicts = [
                {'tick': n.start_tick, 'velocity': n.velocity, 'note_event': n}
                for n in notes
            ]
            
            # Apply groove
            grooved_dicts = self.groove_applicator.apply(
                note_dicts, 
                groove_template,
                preserve_original=True
            )
            
            # Update NoteEvents
            for d in grooved_dicts:
                n = d['note_event']
                n.start_tick = d['tick']
                n.velocity = d['velocity']
        
        # Apply physics-aware humanization for drums
        if HAS_PHYSICS_HUMANIZER and channel == GM_DRUM_CHANNEL and self.use_physics_humanization:
            notes = self._apply_physics_humanization(notes, bpm, genre, "drums")
        
        # For drum channel, apply collision resolution
        if channel == GM_DRUM_CHANNEL:
            notes = self._resolve_drum_collisions(notes)
        
        # Create note-on and note-off events
        events = []
        for note in notes:
            events.append(('note_on', note.start_tick, note.pitch, note.velocity))
            events.append(('note_off', note.end_tick, note.pitch, 0))
        
        # Sort by time, with note-offs before note-ons at same time
        events.sort(key=lambda e: (e[1], 0 if e[0] == 'note_off' else 1))
        
        # Convert to delta times
        prev_time = 0
        for event_type, abs_time, pitch, velocity in events:
            delta = abs_time - prev_time
            
            if event_type == 'note_on':
                track.append(Message(
                    'note_on',
                    note=pitch,
                    velocity=velocity,
                    channel=channel,
                    time=delta
                ))
            else:
                track.append(Message(
                    'note_off',
                    note=pitch,
                    velocity=0,
                    channel=channel,
                    time=delta
                ))
            
            prev_time = abs_time
        
        # End of track
        track.append(MetaMessage('end_of_track', time=0))
    
    def _apply_physics_humanization(
        self,
        notes: List[NoteEvent],
        bpm: float,
        genre: str,
        role: str = "drums"
    ) -> List[NoteEvent]:
        """
        Apply physics-aware humanization to notes.
        
        Implements realistic performance modeling:
        - Fatigue: Velocity reduction at high BPM/dense passages
        - Limb conflicts: Timing adjustments for physical impossibilities
        - Ghost notes: Genre-appropriate soft hits for feel
        
        If self._policy_context is set, uses its dynamics/timing policies
        to override default humanization parameters.
        
        Args:
            notes: List of NoteEvents to humanize
            bpm: Tempo in beats per minute
            genre: Genre for policy selection
            role: Instrument role (drums, bass, keys)
        
        Returns:
            Humanized list of NoteEvents
        """
        if not HAS_PHYSICS_HUMANIZER or not notes:
            return notes
        
        # Map MIDI pitches to drum element names for physics modeling
        pitch_to_element = {
            36: 'kick', 35: 'kick',      # Bass drums
            38: 'snare', 40: 'snare',    # Snares
            42: 'hihat', 44: 'hihat', 46: 'hihat_open',  # Hi-hats
            39: 'clap',                  # Clap
            49: 'crash', 51: 'ride',     # Cymbals
            41: 'tom_low', 43: 'tom_low', 45: 'tom_mid', 47: 'tom_high', 48: 'tom_high',  # Toms
        }
        
        # Convert NoteEvents to PhysicsNotes
        physics_notes = []
        for note in notes:
            element = pitch_to_element.get(note.pitch, "perc")
            physics_notes.append(PhysicsNote(
                pitch=note.pitch,
                start_tick=note.start_tick,
                duration_ticks=note.duration_ticks,
                velocity=note.velocity,
                channel=note.channel,
                element=element
            ))
        
        # Build HumanizeConfig from policy context if available
        humanize_config = None
        if self._policy_context:
            policy = self._policy_context
            
            # Create config from policy decisions
            config_kwargs = {}
            
            # Extract dynamics policy - use hihat range as general reference
            if hasattr(policy, 'dynamics'):
                dyn = policy.dynamics
                config_kwargs['ghost_note_probability'] = dyn.ghost_note_probability
                # Use hihat velocity range for ghost notes (they're usually soft)
                config_kwargs['ghost_note_velocity_min'] = 25
                config_kwargs['ghost_note_velocity_max'] = int(dyn.hihat_velocity_range[0] * dyn.ghost_note_velocity_factor)
            
            # Extract timing policy
            if hasattr(policy, 'timing'):
                tim = policy.timing
                config_kwargs['timing_variation'] = tim.timing_jitter
                config_kwargs['swing_amount'] = tim.swing_amount
            
            # Create HumanizeConfig with overrides
            humanize_config = HumanizeConfig(**config_kwargs)
        
        # Apply physics humanization
        humanizer = PhysicsHumanizer(
            role=role,
            bpm=bpm,
            genre=genre,
            config=humanize_config
        )
        humanized_physics = humanizer.apply(physics_notes)
        
        # Convert back to NoteEvents
        result = []
        for pn in humanized_physics:
            result.append(NoteEvent(
                pitch=pn.pitch,
                start_tick=pn.start_tick,
                duration_ticks=pn.duration_ticks,
                velocity=pn.velocity,
                channel=pn.channel
            ))
        
        # Log summary
        summary = humanizer.get_summary()
        policy_note = " (policy-driven)" if self._policy_context else ""
        if summary.get('ghost_notes_added', 0) > 0:
            print(f"    [+] Physics humanization{policy_note}: {summary['notes_processed']} notes, "
                  f"{summary['ghost_notes_added']} ghosts, "
                  f"{summary['limb_conflicts_resolved']} limb conflicts")
        
        return result
    
    def _resolve_drum_collisions(
        self,
        notes: List[NoteEvent],
        collision_window: int = 30  # ~1/64th note at 480 ticks/beat
    ) -> List[NoteEvent]:
        """
        Resolve timing collisions between different drum sounds.
        
        When different drum elements (kick, snare, hihat) land within
        a small time window of each other due to independent humanization,
        snap them to the same tick to prevent the "machine gun" / "flamming" effect.
        
        Args:
            notes: List of drum NoteEvents
            collision_window: Maximum ticks apart for notes to be considered "same beat"
        
        Returns:
            Corrected list of NoteEvents with resolved collisions
        """
        if not notes:
            return notes
        
        # Sort by start tick
        sorted_notes = sorted(notes, key=lambda n: n.start_tick)
        
        # Group notes that should play together (within collision window)
        # and snap them to a common time
        result = []
        i = 0
        
        while i < len(sorted_notes):
            # Start a new group with this note
            group_start = sorted_notes[i].start_tick
            group = [sorted_notes[i]]
            
            # Find all notes within the collision window
            j = i + 1
            while j < len(sorted_notes):
                if sorted_notes[j].start_tick - group_start <= collision_window:
                    group.append(sorted_notes[j])
                    j += 1
                else:
                    break
            
            # If group has multiple drum types, snap to common time
            if len(group) > 1:
                # Find unique pitches in the group
                unique_pitches = set(n.pitch for n in group)
                
                # Only snap if we have DIFFERENT drum sounds colliding
                # (same pitch collision = intentional roll or repeat)
                if len(unique_pitches) > 1:
                    # Snap all to the earliest tick (preserves groove feel)
                    snap_tick = min(n.start_tick for n in group)
                    for note in group:
                        result.append(NoteEvent(
                            pitch=note.pitch,
                            start_tick=snap_tick,
                            duration_ticks=note.duration_ticks,
                            velocity=note.velocity,
                            channel=note.channel
                        ))
                else:
                    # Same pitch - keep original timing (intentional repetition)
                    result.extend(group)
            else:
                result.extend(group)
            
            i = j
        
        return result


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def generate_midi(arrangement: Arrangement, parsed: ParsedPrompt) -> MidiFile:
    """Generate MIDI file from arrangement and parsed prompt."""
    generator = MidiGenerator(
        swing=parsed.swing_amount
    )
    return generator.generate(arrangement, parsed)


def save_midi(midi_file: MidiFile, path: str):
    """Save MIDI file to disk."""
    midi_file.save(path)


def overdub_midi_track(
    existing_midi_path: str,
    new_track_data: TrackData,
    track_name: str = "Overdub",
    output_path: Optional[str] = None
) -> MidiFile:
    """
    Overdub (merge) new MIDI notes onto an existing MIDI file.
    
    This implements the "Overdub (Merge)" mode where new performances
    are layered onto existing MIDI tracks without erasing previous data.
    
    Args:
        existing_midi_path: Path to existing MIDI file
        new_track_data: TrackData containing new notes to add
        track_name: Name for the new track
        output_path: Optional output path (if None, returns MidiFile object)
        
    Returns:
        MidiFile object with merged tracks
    """
    # Load existing MIDI file
    existing_midi = MidiFile(existing_midi_path)
    
    # Create new track from track data
    new_track = MidiTrack()
    new_track.append(MetaMessage('track_name', name=track_name, time=0))
    
    # Add program change if specified
    if new_track_data.program > 0:
        new_track.append(Message(
            'program_change',
            program=new_track_data.program,
            channel=new_track_data.channel,
            time=0
        ))
    
    # Convert notes to MIDI messages
    events = []
    for note in new_track_data.notes:
        events.append(('note_on', note.start_tick, note.pitch, note.velocity, note.channel))
        events.append(('note_off', note.end_tick, note.pitch, 0, note.channel))
    
    # Sort by time
    events.sort(key=lambda e: (e[1], 0 if e[0] == 'note_off' else 1))
    
    # Convert to delta times
    prev_time = 0
    for event_type, abs_time, pitch, velocity, channel in events:
        delta = abs_time - prev_time
        
        if event_type == 'note_on':
            new_track.append(Message(
                'note_on',
                note=pitch,
                velocity=velocity,
                channel=channel,
                time=delta
            ))
        else:
            new_track.append(Message(
                'note_off',
                note=pitch,
                velocity=0,
                channel=channel,
                time=delta
            ))
        
        prev_time = abs_time
    
    # End of track
    new_track.append(MetaMessage('end_of_track', time=0))
    
    # Add new track to existing MIDI
    existing_midi.tracks.append(new_track)
    
    # Save if output path specified
    if output_path:
        existing_midi.save(output_path)
    
    return existing_midi


def create_midi_version(
    original_midi_path: str,
    version_suffix: Optional[str] = None
) -> str:
    """
    Create a versioned copy of a MIDI file.
    
    This implements the "Record (New Version)" mode where initiating
    a standard "Record" creates a new MIDI sequence while preserving
    the original state in the output/ folder.
    
    Args:
        original_midi_path: Path to original MIDI file
        version_suffix: Optional version suffix (default: timestamp)
        
    Returns:
        Path to versioned MIDI file
    """
    from pathlib import Path
    from datetime import datetime
    
    original_path = Path(original_midi_path)
    
    # Generate version suffix if not provided
    if version_suffix is None:
        version_suffix = datetime.now().strftime("v%Y%m%d_%H%M%S")
    
    # Create versioned filename
    versioned_name = f"{original_path.stem}_{version_suffix}{original_path.suffix}"
    versioned_path = original_path.parent / versioned_name
    
    # Load and save as new version
    midi_file = MidiFile(original_midi_path)
    midi_file.save(str(versioned_path))
    
    return str(versioned_path)


def load_and_merge_midi_tracks(
    *midi_paths: str,
    output_path: Optional[str] = None
) -> MidiFile:
    """
    Load multiple MIDI files and merge all their tracks.
    
    Useful for combining multiple recordings or overdubs.
    
    Args:
        *midi_paths: Variable number of MIDI file paths
        output_path: Optional output path
        
    Returns:
        MidiFile with all merged tracks
    """
    if not midi_paths:
        raise ValueError("At least one MIDI path required")
    
    # Load first file as base
    merged = MidiFile(midi_paths[0])
    
    # Merge additional files
    for midi_path in midi_paths[1:]:
        midi = MidiFile(midi_path)
        # Skip tempo track (track 0), add all others
        for track in midi.tracks[1:]:
            merged.tracks.append(track)
    
    # Save if output path specified
    if output_path:
        merged.save(output_path)
    
    return merged


if __name__ == '__main__':
    # Test generation
    from .prompt_parser import parse_prompt
    from .arranger import create_arrangement
    
    prompt = "dark trap soul at 87 BPM in C minor with 808 and rhodes"
    parsed = parse_prompt(prompt)
    arrangement = create_arrangement(parsed)
    
    midi = generate_midi(arrangement, parsed)
    
    print(f"Generated MIDI:")
    print(f"  Tracks: {len(midi.tracks)}")
    print(f"  Duration: {arrangement.duration_seconds():.1f}s")
    
    # Save test file
    midi.save('test_output.mid')
    print(f"  Saved to test_output.mid")
