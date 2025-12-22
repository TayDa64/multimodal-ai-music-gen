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
)
from .prompt_parser import ParsedPrompt
from .arranger import Arrangement, SongSection, SectionType


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
    add_ghost_notes: bool = True
) -> List[Tuple[int, int, int]]:
    """Generate trap-style snare/clap pattern (on beats 2 and 4)."""
    pattern = []
    ticks_per_bar = TICKS_PER_BAR_4_4
    
    for bar in range(bars):
        bar_offset = bar * ticks_per_bar
        
        # Main snares on 2 and 4
        for beat in [2, 4]:
            tick = bar_offset + beats_to_ticks(beat - 1)  # 0-indexed
            vel = humanize_velocity(base_velocity, variation=0.1)
            pattern.append((tick, TICKS_PER_8TH, vel))
        
        # Ghost notes (soft snare hits between main hits)
        if add_ghost_notes and random.random() < 0.5:
            ghost_positions = [1.5, 2.5, 3.5]
            ghost_pos = random.choice(ghost_positions)
            tick = bar_offset + beats_to_ticks(ghost_pos - 1)
            ghost_vel = humanize_velocity(50, variation=0.15)
            pattern.append((tick, TICKS_PER_16TH, ghost_vel))
    
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
    """
    ticks_per_bar = TICKS_PER_BAR_4_4
    
    kicks = []
    snares = []
    hihats = []
    
    for bar in range(bars):
        bar_offset = bar * ticks_per_bar
        
        # Simple kick pattern
        kick_positions = [0, 2.5] if bar % 2 == 0 else [0, 2.75]
        for pos in kick_positions:
            tick = bar_offset + beats_to_ticks(pos)
            tick = humanize_timing(tick, swing=0, timing_variation=0.03)
            vel = humanize_velocity(base_velocity, variation=0.1)
            kicks.append((tick, TICKS_PER_8TH, vel))
        
        # Snare on 2 and 4
        for beat in [2, 4]:
            tick = bar_offset + beats_to_ticks(beat - 1)
            tick = humanize_timing(tick, swing=0, timing_variation=0.04)
            vel = humanize_velocity(base_velocity - 10, variation=0.12)
            snares.append((tick, TICKS_PER_8TH, vel))
        
        # Swung hi-hats
        for eighth in range(8):
            tick = bar_offset + (eighth * TICKS_PER_8TH)
            is_offbeat = eighth % 2 == 1
            tick = humanize_timing(tick, swing=swing, timing_variation=0.02, is_offbeat=is_offbeat)
            
            # Accent pattern
            if eighth % 2 == 0:
                vel = humanize_velocity(base_velocity - 15, variation=0.1)
            else:
                vel = humanize_velocity(base_velocity - 30, variation=0.15)
            
            hihats.append((tick, TICKS_PER_8TH // 2, vel))
    
    return {'kick': kicks, 'snare': snares, 'hihat': hihats}


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


# =============================================================================
# MELODIC GENERATORS
# =============================================================================

def generate_808_bass_pattern(
    bars: int,
    root: str,
    scale_type: ScaleType,
    octave: int = 1,
    base_velocity: int = 100
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
    
    for bar in range(bars):
        bar_offset = bar * ticks_per_bar
        
        # 808 pattern following kick pattern roughly
        # Long sustained notes with occasional pitch changes
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
    rhythm_style: str = 'block'
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
    if progression is None:
        # Default progressions by mood
        if scale_type == ScaleType.MINOR:
            progression = [1, 6, 3, 7]  # i VI III VII
        else:
            progression = [1, 5, 6, 4]  # I V vi IV
    
    pattern = []
    ticks_per_bar = TICKS_PER_BAR_4_4
    chords = get_chord_progression(key, scale_type, progression, octave)
    
    # How many bars per chord
    bars_per_chord = max(1, bars // len(progression))
    
    chord_index = 0
    for bar in range(bars):
        bar_offset = bar * ticks_per_bar
        
        # Change chord every N bars
        if bar > 0 and bar % bars_per_chord == 0:
            chord_index = (chord_index + 1) % len(chords)
        
        chord_notes = chords[chord_index]
        
        if rhythm_style == 'block':
            # Play full chord at start of bar, hold for bar
            for pitch in chord_notes:
                vel = humanize_velocity(base_velocity, variation=0.1)
                pattern.append((bar_offset, ticks_per_bar, pitch, vel))
        
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


# =============================================================================
# MAIN MIDI GENERATOR CLASS
# =============================================================================

class MidiGenerator:
    """
    Main class for generating humanized MIDI from arrangements.
    
    Orchestrates drum, bass, chord, and melody generation with
    professional-level humanization.
    """
    
    def __init__(
        self,
        velocity_variation: float = 0.12,
        timing_variation: float = 0.03,
        swing: float = 0.0
    ):
        self.velocity_variation = velocity_variation
        self.timing_variation = timing_variation
        self.swing = swing
    
    def generate(
        self,
        arrangement: Arrangement,
        parsed: ParsedPrompt
    ) -> MidiFile:
        """
        Generate complete MIDI file from arrangement.
        
        Args:
            arrangement: Song arrangement
            parsed: Parsed prompt with musical parameters
        
        Returns:
            mido.MidiFile ready to save
        """
        # Create MIDI file
        mid = MidiFile(ticks_per_beat=TICKS_PER_BEAT)
        
        # Track 0: Tempo/time signature (meta track)
        meta_track = self._create_meta_track(arrangement, parsed)
        mid.tracks.append(meta_track)
        
        # Track 1: Drums (channel 10)
        drum_track = self._create_drum_track(arrangement, parsed)
        mid.tracks.append(drum_track)
        
        # Track 2: Bass/808
        if '808' in parsed.instruments or 'bass' in parsed.instruments:
            bass_track = self._create_bass_track(arrangement, parsed)
            mid.tracks.append(bass_track)
        
        # Track 3: Chords
        if any(inst in parsed.instruments for inst in ['piano', 'rhodes', 'pad', 'strings']):
            chord_track = self._create_chord_track(arrangement, parsed)
            mid.tracks.append(chord_track)
        
        # Track 4: Melody (optional)
        if parsed.genre not in ['ambient', 'lofi']:  # These often don't have melody
            melody_track = self._create_melody_track(arrangement, parsed)
            if len(melody_track) > 1:  # Has notes beyond track name
                mid.tracks.append(melody_track)
        
        return mid
    
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
        key_str = parsed.key
        if parsed.scale_type == ScaleType.MINOR:
            key_str = f"{parsed.key}m"
        track.append(MetaMessage('key_signature', key=key_str, time=0))
        
        # End of track
        track.append(MetaMessage('end_of_track', time=arrangement.total_ticks))
        
        return track
    
    def _create_drum_track(
        self,
        arrangement: Arrangement,
        parsed: ParsedPrompt
    ) -> MidiTrack:
        """Generate drum track with humanized patterns."""
        track = MidiTrack()
        track.append(MetaMessage('track_name', name='Drums', time=0))
        
        all_notes = []
        
        for section in arrangement.sections:
            section_notes = self._generate_drums_for_section(section, parsed)
            all_notes.extend(section_notes)
        
        # Convert to MIDI messages
        self._notes_to_track(all_notes, track, channel=GM_DRUM_CHANNEL)
        
        return track
    
    def _generate_drums_for_section(
        self,
        section: SongSection,
        parsed: ParsedPrompt
    ) -> List[NoteEvent]:
        """Generate drums for a single section."""
        notes = []
        config = section.config
        
        # Determine pattern type based on genre and section
        if parsed.genre in ['trap', 'trap_soul']:
            # Generate trap-style drums
            if config.enable_kick:
                kicks = generate_trap_kick_pattern(
                    section.bars,
                    variation=section.pattern_variation,
                    base_velocity=int(100 * config.drum_density)
                )
                for tick, dur, vel in kicks:
                    notes.append(NoteEvent(
                        pitch=GM_DRUM_NOTES['kick'],
                        start_tick=section.start_tick + tick,
                        duration_ticks=dur,
                        velocity=vel,
                        channel=GM_DRUM_CHANNEL
                    ))
            
            if config.enable_snare:
                snares = generate_trap_snare_pattern(
                    section.bars,
                    variation=section.pattern_variation,
                    base_velocity=int(95 * config.drum_density),
                    add_ghost_notes=config.drum_density > 0.5
                )
                for tick, dur, vel in snares:
                    notes.append(NoteEvent(
                        pitch=GM_DRUM_NOTES['snare'],
                        start_tick=section.start_tick + tick,
                        duration_ticks=dur,
                        velocity=vel,
                        channel=GM_DRUM_CHANNEL
                    ))
            
            if config.enable_hihat:
                include_rolls = (
                    'hihat_roll' in parsed.drum_elements and 
                    section.section_type in [SectionType.DROP, SectionType.CHORUS]
                )
                hihats = generate_trap_hihat_pattern(
                    section.bars,
                    variation=section.pattern_variation,
                    base_velocity=int(75 * config.drum_density),
                    include_rolls=include_rolls,
                    swing=parsed.swing_amount
                )
                for tick, dur, vel in hihats:
                    notes.append(NoteEvent(
                        pitch=GM_DRUM_NOTES['hihat_closed'],
                        start_tick=section.start_tick + tick,
                        duration_ticks=dur,
                        velocity=vel,
                        channel=GM_DRUM_CHANNEL
                    ))
        
        elif parsed.genre == 'lofi':
            # Lo-fi swing pattern
            patterns = generate_lofi_drum_pattern(
                section.bars,
                swing=parsed.swing_amount or 0.12,
                base_velocity=int(85 * config.drum_density)
            )
            
            if config.enable_kick:
                for tick, dur, vel in patterns['kick']:
                    notes.append(NoteEvent(
                        pitch=GM_DRUM_NOTES['kick'],
                        start_tick=section.start_tick + tick,
                        duration_ticks=dur,
                        velocity=vel,
                        channel=GM_DRUM_CHANNEL
                    ))
            
            if config.enable_snare:
                for tick, dur, vel in patterns['snare']:
                    notes.append(NoteEvent(
                        pitch=GM_DRUM_NOTES['snare'],
                        start_tick=section.start_tick + tick,
                        duration_ticks=dur,
                        velocity=vel,
                        channel=GM_DRUM_CHANNEL
                    ))
            
            if config.enable_hihat:
                for tick, dur, vel in patterns['hihat']:
                    notes.append(NoteEvent(
                        pitch=GM_DRUM_NOTES['hihat_closed'],
                        start_tick=section.start_tick + tick,
                        duration_ticks=dur,
                        velocity=vel,
                        channel=GM_DRUM_CHANNEL
                    ))
        
        elif parsed.genre == 'house':
            # Four-on-the-floor
            patterns = generate_house_drum_pattern(
                section.bars,
                base_velocity=int(100 * config.drum_density)
            )
            
            for drum_type, note_num in [('kick', 'kick'), ('clap', 'clap'), 
                                         ('hihat', 'hihat_closed'), ('hihat_open', 'hihat_open')]:
                if drum_type in patterns:
                    for tick, dur, vel in patterns[drum_type]:
                        notes.append(NoteEvent(
                            pitch=GM_DRUM_NOTES[note_num],
                            start_tick=section.start_tick + tick,
                            duration_ticks=dur,
                            velocity=vel,
                            channel=GM_DRUM_CHANNEL
                        ))
        
        else:
            # Default boom-bap style
            patterns = generate_lofi_drum_pattern(section.bars, swing=0.08)
            for pattern_type, note_name in [('kick', 'kick'), ('snare', 'snare'), ('hihat', 'hihat_closed')]:
                for tick, dur, vel in patterns.get(pattern_type, []):
                    notes.append(NoteEvent(
                        pitch=GM_DRUM_NOTES[note_name],
                        start_tick=section.start_tick + tick,
                        duration_ticks=dur,
                        velocity=vel,
                        channel=GM_DRUM_CHANNEL
                    ))
        
        return notes
    
    def _create_bass_track(
        self,
        arrangement: Arrangement,
        parsed: ParsedPrompt
    ) -> MidiTrack:
        """Generate bass/808 track."""
        track = MidiTrack()
        track.append(MetaMessage('track_name', name='Bass', time=0))
        
        # Program change: Synth Bass (38) for 808 feel
        track.append(Message('program_change', program=38, channel=1, time=0))
        
        all_notes = []
        
        for section in arrangement.sections:
            if section.config.enable_bass:
                bass_pattern = generate_808_bass_pattern(
                    section.bars,
                    parsed.key,
                    parsed.scale_type,
                    octave=1,
                    base_velocity=int(100 * section.config.energy_level)
                )
                
                for tick, dur, pitch, vel in bass_pattern:
                    all_notes.append(NoteEvent(
                        pitch=pitch,
                        start_tick=section.start_tick + tick,
                        duration_ticks=dur,
                        velocity=vel,
                        channel=1
                    ))
        
        self._notes_to_track(all_notes, track, channel=1)
        
        return track
    
    def _create_chord_track(
        self,
        arrangement: Arrangement,
        parsed: ParsedPrompt
    ) -> MidiTrack:
        """Generate chord track."""
        track = MidiTrack()
        track.append(MetaMessage('track_name', name='Chords', time=0))
        
        # Program change based on instrument
        if 'rhodes' in parsed.instruments:
            program = 4  # Electric Piano 1
        elif 'piano' in parsed.instruments:
            program = 0  # Acoustic Grand
        elif 'pad' in parsed.instruments:
            program = 89  # Pad 2 (warm)
        elif 'strings' in parsed.instruments:
            program = 48  # String Ensemble
        else:
            program = 4  # Default to Rhodes
        
        track.append(Message('program_change', program=program, channel=2, time=0))
        
        all_notes = []
        
        # Determine chord style based on genre
        if parsed.genre in ['trap', 'trap_soul']:
            rhythm_style = 'block'
        elif parsed.genre == 'lofi':
            rhythm_style = 'arpeggiate'
        elif parsed.genre == 'house':
            rhythm_style = 'stab'
        else:
            rhythm_style = 'block'
        
        for section in arrangement.sections:
            if section.config.enable_chords:
                chord_pattern = generate_chord_progression_midi(
                    section.bars,
                    parsed.key,
                    parsed.scale_type,
                    octave=4,
                    base_velocity=int(85 * section.config.instrument_density),
                    rhythm_style=rhythm_style
                )
                
                for tick, dur, pitch, vel in chord_pattern:
                    all_notes.append(NoteEvent(
                        pitch=pitch,
                        start_tick=section.start_tick + tick,
                        duration_ticks=dur,
                        velocity=vel,
                        channel=2
                    ))
        
        self._notes_to_track(all_notes, track, channel=2)
        
        return track
    
    def _create_melody_track(
        self,
        arrangement: Arrangement,
        parsed: ParsedPrompt
    ) -> MidiTrack:
        """Generate optional melody track."""
        track = MidiTrack()
        track.append(MetaMessage('track_name', name='Melody', time=0))
        
        # Use lead synth
        track.append(Message('program_change', program=80, channel=3, time=0))  # Lead 1 (square)
        
        all_notes = []
        
        for section in arrangement.sections:
            if section.config.enable_melody and section.section_type in [
                SectionType.CHORUS, SectionType.DROP, SectionType.VARIATION
            ]:
                melody = generate_melody(
                    section.bars,
                    parsed.key,
                    parsed.scale_type,
                    octave=5,
                    density=section.config.instrument_density * 0.5,
                    base_velocity=int(90 * section.config.energy_level)
                )
                
                for tick, dur, pitch, vel in melody:
                    all_notes.append(NoteEvent(
                        pitch=pitch,
                        start_tick=section.start_tick + tick,
                        duration_ticks=dur,
                        velocity=vel,
                        channel=3
                    ))
        
        self._notes_to_track(all_notes, track, channel=3)
        
        return track
    
    def _notes_to_track(
        self,
        notes: List[NoteEvent],
        track: MidiTrack,
        channel: int
    ):
        """
        Convert list of NoteEvents to MIDI track messages.
        
        Handles delta time calculation and proper note-off ordering.
        """
        if not notes:
            track.append(MetaMessage('end_of_track', time=0))
            return
        
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
