"""
MasenqoAgent - Masterclass Ethiopian Bowed Fiddle Performer

This module implements a professional masenqo (ማሰንቆ) player agent with deep knowledge of:
- Ethiopian Qenet (Modal) System: Tizita, Ambassel, Bati, Anchihoye scales
- Bowing Techniques: Continuous bow, vibrato, tremolo, drone strings
- Ornaments: Grace notes, trills, slides (portamento), melismatic runs
- Azmari Tradition: Call-and-response phrases, improvisation, vocal accompaniment

The MasenqoAgent is designed to generate authentic Ethiopian string melodies
that complement traditional ensembles (krar, washint, kebero) or modern
Ethio-jazz arrangements.

Physical Instrument Reference:
    The masenqo is a single-stringed bowed lute used by azmari (wandering minstrels):
    - Single string (traditionally horsehair)
    - Diamond-shaped resonator with goatskin membrane
    - Bowed with a curved horsehair stick
    - Range: Approximately A3-E5 (57-76 MIDI, centered around 440Hz region)
    
Musical Characteristics:
    - Continuous bowing (rarely lifted during phrases)
    - Rich vibrato on sustained notes
    - Nasal, voice-like timbre
    - Often doubles or responds to singer's melody
    - Drone notes (open string rings continuously)
    - Heterophonic variations of main melody

Architecture Notes:
    This is a Stage 1 (offline) implementation with comprehensive Ethiopian
    music theory. Stage 2 will add API-backed generation for creative variation.

Example:
    ```python
    from multimodal_gen.agents.performers import MasenqoAgent
    from multimodal_gen.agents import PerformanceContext, MASENQO_PRESETS
    
    masenqo = MasenqoAgent()
    masenqo.set_personality(MASENQO_PRESETS['traditional_azmari'])
    
    result = masenqo.perform(context, section)
    print(f"Generated {len(result.notes)} masenqo notes")
    print(f"Qenet mode: {result.decisions_made[0]}")
    ```
"""

from typing import List, Optional, Dict, Any, Tuple
import random
import logging
from copy import deepcopy

from ..base import IPerformerAgent, AgentRole, PerformanceResult
from ..context import PerformanceContext
from ..personality import AgentPersonality, get_personality_for_role

# Import existing infrastructure
from ...arranger import SongSection, SectionType
from ...midi_generator import NoteEvent
from ...utils import (
    TICKS_PER_BEAT,
    TICKS_PER_8TH,
    TICKS_PER_16TH,
    TICKS_PER_BAR_4_4,
    get_ticks_per_bar,
    humanize_velocity,
    humanize_timing,
    beats_to_ticks,
    note_name_to_midi,
    midi_to_note_name,
)

logger = logging.getLogger(__name__)


# =============================================================================
# MASENQO PERSONALITY PRESETS
# =============================================================================

MASENQO_PRESETS: Dict[str, AgentPersonality] = {
    "traditional_azmari": AgentPersonality(
        aggressiveness=0.5,
        complexity=0.6,
        consistency=0.7,
        push_pull=0.0,
        swing_affinity=0.2,  # Ethiopian music has groove but not swing
        fill_frequency=0.4,
        ghost_note_density=0.5,  # Ornamentation density
        variation_tendency=0.6,
        signature_patterns=["melismatic_run", "call_phrase", "drone_accompaniment"]
    ),
    
    "ethio_jazz_fusion": AgentPersonality(
        aggressiveness=0.45,
        complexity=0.7,
        consistency=0.6,
        push_pull=-0.03,  # Slightly behind for jazz feel
        swing_affinity=0.4,
        fill_frequency=0.35,
        ghost_note_density=0.6,
        variation_tendency=0.7,
        signature_patterns=["jazz_phrase", "pentatonic_run", "chromatic_approach"]
    ),
    
    "eskista_energetic": AgentPersonality(
        aggressiveness=0.7,
        complexity=0.5,
        consistency=0.8,
        push_pull=0.02,  # Slightly ahead for dance energy
        swing_affinity=0.15,
        fill_frequency=0.5,
        ghost_note_density=0.4,
        variation_tendency=0.4,
        signature_patterns=["dance_pattern", "rhythmic_ostinato", "accent_phrase"]
    ),
    
    "meditative_ambassel": AgentPersonality(
        aggressiveness=0.25,
        complexity=0.4,
        consistency=0.85,
        push_pull=-0.05,  # Behind the beat for meditative feel
        swing_affinity=0.0,
        fill_frequency=0.2,
        ghost_note_density=0.3,
        variation_tendency=0.3,
        signature_patterns=["sustained_drone", "slow_melody", "vibrato_emphasis"]
    ),
    
    "virtuoso_ornamental": AgentPersonality(
        aggressiveness=0.55,
        complexity=0.9,
        consistency=0.6,
        push_pull=0.0,
        swing_affinity=0.25,
        fill_frequency=0.6,
        ghost_note_density=0.8,  # Heavy ornamentation
        variation_tendency=0.8,
        signature_patterns=["rapid_ornament", "trill", "melismatic_flourish"]
    ),
}


# =============================================================================
# QENET (ETHIOPIAN MODAL) THEORY
# =============================================================================

class QenetTheory:
    """
    Ethiopian Qenet (ቄነት) modal system knowledge.
    
    The qenet system defines the characteristic scales (modes) used in 
    Ethiopian traditional music. Each qenet has distinct emotional 
    associations and melodic characteristics.
    
    Primary Qenet Modes:
        - Tizita Major (ትዝታ): Nostalgic, longing - pentatonic major feel
        - Tizita Minor: Melancholic variant
        - Ambassel (አምባሰል): Spiritual, meditative, religious music
        - Anchihoye (አንጭሆዬ): Playful, dance-like, fuller scale
        - Bati Major (ባቲ): Bright, celebratory
        - Bati Minor: Mysterious, modal mixture
    
    Musical Characteristics:
        - All modes are fundamentally pentatonic or hexatonic
        - Strong emphasis on the tonal center
        - Characteristic phrases define each mode beyond just notes
        - Modes often associated with specific emotions/occasions
    """
    
    # Qenet scale intervals (semitones from root)
    QENET_MODES = {
        # Tizita Major (ትዝታ ዋና) - Nostalgic/longing, major pentatonic variant
        # Often compared to Western major pentatonic but with unique phrasing
        'tizita_major': {
            'intervals': [0, 2, 4, 7, 9],  # C-D-E-G-A
            'character': 'nostalgic, longing, bittersweet',
            'emphasis_degrees': [0, 2, 4],  # Root, 2nd, 3rd emphasized
            'approach_notes': [1, 6, 11],  # Chromatic approaches
            'typical_range_semitones': (0, 14),  # Just over an octave
        },
        
        # Tizita Minor - Melancholic variant
        'tizita_minor': {
            'intervals': [0, 2, 3, 7, 8],  # C-D-Eb-G-Ab
            'character': 'melancholic, sad, introspective',
            'emphasis_degrees': [0, 3, 7],  # Root, minor 3rd, 5th
            'approach_notes': [1, 6, 11],
            'typical_range_semitones': (0, 12),
        },
        
        # Ambassel (አምባሰል) - Spiritual, meditative, church music
        'ambassel': {
            'intervals': [0, 1, 5, 7, 8],  # C-Db-F-G-Ab
            'character': 'spiritual, meditative, reverent',
            'emphasis_degrees': [0, 5, 7],  # Root, 4th, 5th
            'approach_notes': [6, 11],
            'typical_range_semitones': (-5, 12),  # Extends below tonic
        },
        
        # Anchihoye (አንጭሆዬ) - Playful, dance-like, festive
        'anchihoye': {
            'intervals': [0, 2, 3, 5, 7, 8, 11],  # C-D-Eb-F-G-Ab-B (fuller scale)
            'character': 'playful, dance, festive, eskista',
            'emphasis_degrees': [0, 3, 5, 7],  # Active scale degrees
            'approach_notes': [1, 4, 6],
            'typical_range_semitones': (0, 14),
        },
        
        # Bati Major (ባቲ ዋና) - Bright, celebratory, joyful
        'bati_major': {
            'intervals': [0, 2, 4, 6, 7],  # C-D-E-F#-G (Lydian-ish pentatonic)
            'character': 'bright, joyful, celebratory',
            'emphasis_degrees': [0, 4, 7],  # Major feel with raised 4th
            'approach_notes': [1, 5, 11],
            'typical_range_semitones': (0, 12),
        },
        
        # Bati Minor - Mysterious, modal mixture
        'bati_minor': {
            'intervals': [0, 2, 3, 6, 7],  # C-D-Eb-F#-G
            'character': 'mysterious, haunting, modal',
            'emphasis_degrees': [0, 3, 6],  # Minor with tritone
            'approach_notes': [1, 5, 11],
            'typical_range_semitones': (0, 12),
        },
    }
    
    # Characteristic melodic phrases for each qenet
    # Expressed as (relative_pitch, duration_mult, velocity_mult, is_ornament)
    CHARACTERISTIC_PHRASES = {
        'tizita_major': [
            # Descending nostalgic phrase (common tizita gesture)
            [(9, 1.0, 1.0, False), (7, 0.5, 0.9, False), (4, 1.0, 0.85, False), (2, 0.5, 0.8, False), (0, 2.0, 0.9, False)],
            # Ascending with ornament
            [(0, 0.5, 0.9, False), (2, 0.5, 0.85, False), (4, 1.0, 1.0, False), (5, 0.25, 0.7, True), (4, 1.5, 0.95, False)],
            # Call phrase (higher register)
            [(7, 0.5, 0.95, False), (9, 1.0, 1.0, False), (7, 0.5, 0.85, False), (4, 1.0, 0.9, False)],
        ],
        
        'tizita_minor': [
            # Melancholic descent
            [(8, 0.5, 0.95, False), (7, 1.0, 0.9, False), (3, 1.5, 0.85, False), (2, 0.5, 0.8, False), (0, 2.0, 0.9, False)],
            # Minor lament
            [(0, 1.0, 0.9, False), (3, 1.5, 1.0, False), (2, 0.5, 0.85, False), (0, 2.0, 0.9, False)],
        ],
        
        'ambassel': [
            # Spiritual ascending
            [(0, 1.5, 0.85, False), (1, 0.5, 0.7, True), (0, 0.5, 0.8, False), (5, 2.0, 0.9, False), (7, 1.5, 0.95, False)],
            # Meditative drone return
            [(8, 1.0, 0.9, False), (7, 1.5, 0.85, False), (5, 1.0, 0.8, False), (0, 3.0, 0.9, False)],
        ],
        
        'anchihoye': [
            # Dance phrase (rhythmic)
            [(0, 0.5, 0.95, False), (3, 0.5, 0.9, False), (5, 0.5, 0.95, False), (7, 0.5, 1.0, False), 
             (5, 0.5, 0.9, False), (3, 0.5, 0.85, False), (0, 1.0, 0.9, False)],
            # Eskista accent
            [(7, 0.25, 1.0, False), (5, 0.25, 0.9, False), (7, 0.5, 1.0, False), (8, 0.5, 0.95, False), (7, 1.0, 0.9, False)],
        ],
        
        'bati_major': [
            # Bright ascending
            [(0, 0.5, 0.9, False), (2, 0.5, 0.85, False), (4, 0.5, 0.9, False), (6, 0.5, 0.95, False), (7, 1.5, 1.0, False)],
            # Celebratory
            [(7, 0.5, 1.0, False), (6, 0.5, 0.9, False), (4, 1.0, 0.95, False), (2, 0.5, 0.85, False), (0, 1.5, 0.9, False)],
        ],
        
        'bati_minor': [
            # Mysterious
            [(0, 1.0, 0.85, False), (3, 1.0, 0.9, False), (6, 1.5, 0.95, False), (7, 1.0, 0.9, False), (6, 0.5, 0.85, False), (3, 1.5, 0.9, False)],
        ],
    }
    
    # Key/chord to qenet mapping hints
    KEY_TO_QENET_MAP = {
        # Minor keys tend toward tizita minor, ambassel
        'minor': ['tizita_minor', 'ambassel', 'bati_minor'],
        # Major keys tend toward tizita major, bati major
        'major': ['tizita_major', 'bati_major', 'anchihoye'],
        # Specific key contexts
        'spiritual': ['ambassel'],
        'dance': ['anchihoye', 'bati_major'],
        'nostalgic': ['tizita_major', 'tizita_minor'],
        'celebratory': ['bati_major', 'anchihoye'],
    }
    
    @classmethod
    def get_mode_info(cls, mode_name: str) -> Dict[str, Any]:
        """Get full information for a qenet mode."""
        mode_key = mode_name.lower().strip().replace(' ', '_').replace('-', '_')
        return cls.QENET_MODES.get(mode_key, cls.QENET_MODES['tizita_major'])
    
    @classmethod
    def get_scale_notes(
        cls,
        root_midi: int,
        mode_name: str,
        octaves: int = 2
    ) -> List[int]:
        """
        Get MIDI note numbers for a qenet scale.
        
        Args:
            root_midi: Root note MIDI number
            mode_name: Name of the qenet mode
            octaves: Number of octaves to generate
            
        Returns:
            List of MIDI note numbers in the scale
        """
        mode_info = cls.get_mode_info(mode_name)
        intervals = mode_info['intervals']
        
        notes = []
        for octave in range(octaves):
            for interval in intervals:
                note = root_midi + interval + (octave * 12)
                if 0 <= note <= 127:
                    notes.append(note)
        
        return sorted(set(notes))
    
    @classmethod
    def get_characteristic_phrase(cls, mode_name: str) -> List[Tuple]:
        """
        Get a characteristic melodic phrase for the qenet mode.
        
        Returns:
            List of (relative_pitch, duration_mult, velocity_mult, is_ornament)
        """
        mode_key = mode_name.lower().strip().replace(' ', '_').replace('-', '_')
        phrases = cls.CHARACTERISTIC_PHRASES.get(mode_key, cls.CHARACTERISTIC_PHRASES['tizita_major'])
        return random.choice(phrases)
    
    @classmethod
    def suggest_qenet_for_context(
        cls,
        key: str,
        tension: float,
        energy_level: float,
        genre: str = 'ethiopian'
    ) -> str:
        """
        Suggest the best qenet mode based on musical context.
        
        Args:
            key: Musical key (e.g., 'C', 'Gm')
            tension: Tension level (0-1)
            energy_level: Energy level (0-1)
            genre: Genre context
            
        Returns:
            Suggested qenet mode name
        """
        # Determine key quality
        is_minor = 'm' in key.lower() or 'minor' in key.lower()
        
        # Base selection on key quality
        if is_minor:
            candidates = cls.KEY_TO_QENET_MAP['minor']
        else:
            candidates = cls.KEY_TO_QENET_MAP['major']
        
        # Refine based on energy/tension
        if energy_level > 0.7:
            # High energy: prefer dance modes
            if 'anchihoye' in candidates:
                return 'anchihoye'
            return 'bati_major' if not is_minor else 'tizita_minor'
        
        elif tension < 0.3:
            # Low tension: meditative
            return 'ambassel'
        
        elif tension > 0.7:
            # High tension: minor/mysterious
            return 'bati_minor' if random.random() < 0.5 else 'tizita_minor'
        
        # Default selection
        return random.choice(candidates)
    
    @classmethod
    def get_approach_note(cls, target_note: int, mode_name: str, direction: int = 1) -> int:
        """
        Get a chromatic approach note for the target.
        
        Args:
            target_note: Target MIDI note
            mode_name: Current qenet mode
            direction: 1 for below, -1 for above
            
        Returns:
            Approach note MIDI number
        """
        mode_info = cls.get_mode_info(mode_name)
        approach_intervals = mode_info.get('approach_notes', [1, 11])
        
        if direction > 0:  # Approach from below
            return target_note - random.choice([1, 2])
        else:  # Approach from above
            return target_note + random.choice([1, 2])


# =============================================================================
# MASENQO TECHNIQUES
# =============================================================================

class MasenqoTechniques:
    """
    Playing techniques specific to the masenqo.
    
    The masenqo has unique performance characteristics:
    - Single string with continuous bowing
    - Wide vibrato (vocal-like quality)
    - Pitch slides between notes
    - Drone accompaniment on open string
    - Grace note ornaments (appoggiatura)
    - Trills for emphasis
    
    Note Generation:
        Each technique returns a list of NoteEvents that together
        create the desired musical effect.
    """
    
    # Masenqo physical characteristics
    STANDARD_RANGE = (57, 76)  # A3 to E5 (centered around vocal range)
    OPEN_STRING_DEFAULT = 57   # A3 is typical open string tuning
    TYPICAL_VIBRATO_RATE = 5.5  # Hz (5-6 Hz typical for masenqo)
    
    @staticmethod
    def generate_grace_note(
        main_tick: int,
        main_pitch: int,
        base_velocity: int = 85,
        approach_from_below: bool = True
    ) -> List[NoteEvent]:
        """
        Generate a grace note (appoggiatura) before the main note.
        
        Grace notes are quick ornamental notes that lead into the main note.
        In masenqo playing, they add expressiveness and "cry" to the melody.
        
        Args:
            main_tick: Tick position of main note
            main_pitch: MIDI note of main note
            base_velocity: Base velocity
            approach_from_below: Approach from semitone below (vs above)
            
        Returns:
            List with grace note and main note
        """
        notes = []
        
        # Grace note duration: very short (1/32 or less)
        grace_duration = TICKS_PER_16TH // 2  # 60 ticks at 480 PPQ
        grace_pitch = main_pitch - 1 if approach_from_below else main_pitch + 1
        grace_tick = main_tick - grace_duration
        
        # Grace note (lighter, quick)
        notes.append(NoteEvent(
            pitch=grace_pitch,
            start_tick=max(0, grace_tick),
            duration_ticks=grace_duration,
            velocity=int(base_velocity * 0.7),
            channel=0
        ))
        
        return notes
    
    @staticmethod
    def generate_trill(
        start_tick: int,
        main_pitch: int,
        duration_ticks: int,
        base_velocity: int = 85,
        upper_neighbor: bool = True
    ) -> List[NoteEvent]:
        """
        Generate a trill (rapid alternation between two notes).
        
        Masenqo trills add intensity and expression, often used on
        sustained notes or at phrase endings.
        
        Args:
            start_tick: Starting tick position
            main_pitch: Primary note
            duration_ticks: Total duration for the trill
            base_velocity: Base velocity
            upper_neighbor: Trill to upper note (vs lower)
            
        Returns:
            List of alternating notes forming the trill
        """
        notes = []
        
        # Trill note (neighbor tone)
        trill_pitch = main_pitch + 2 if upper_neighbor else main_pitch - 2
        
        # Each trill oscillation duration
        trill_note_dur = TICKS_PER_16TH // 2  # Very quick alternation
        num_alternations = max(4, duration_ticks // (trill_note_dur * 2))
        
        for i in range(num_alternations):
            tick_offset = i * (trill_note_dur * 2)
            if start_tick + tick_offset >= start_tick + duration_ticks:
                break
            
            # Main note
            notes.append(NoteEvent(
                pitch=main_pitch,
                start_tick=start_tick + tick_offset,
                duration_ticks=trill_note_dur,
                velocity=humanize_velocity(base_velocity, variation=0.1),
                channel=0
            ))
            
            # Trill note
            notes.append(NoteEvent(
                pitch=trill_pitch,
                start_tick=start_tick + tick_offset + trill_note_dur,
                duration_ticks=trill_note_dur,
                velocity=humanize_velocity(int(base_velocity * 0.9), variation=0.1),
                channel=0
            ))
        
        return notes
    
    @staticmethod
    def generate_slide(
        start_tick: int,
        from_pitch: int,
        to_pitch: int,
        duration_ticks: int,
        base_velocity: int = 85
    ) -> List[NoteEvent]:
        """
        Generate a pitch slide (portamento) between two notes.
        
        Masenqo slides are smooth, voice-like transitions that
        give the instrument its characteristic "singing" quality.
        
        Args:
            start_tick: Starting tick position
            from_pitch: Starting pitch
            to_pitch: Ending pitch
            duration_ticks: Total duration for the slide
            base_velocity: Base velocity
            
        Returns:
            List of notes creating the slide effect
        """
        notes = []
        
        # Calculate number of intermediate steps
        semitone_diff = abs(to_pitch - from_pitch)
        direction = 1 if to_pitch > from_pitch else -1
        
        # For short slides, use fewer steps
        num_steps = min(semitone_diff + 1, max(3, duration_ticks // TICKS_PER_16TH))
        step_duration = duration_ticks // num_steps
        
        for i in range(num_steps):
            # Calculate intermediate pitch (linear interpolation)
            progress = i / max(1, num_steps - 1)
            pitch = from_pitch + int(semitone_diff * progress * direction)
            
            tick = start_tick + (i * step_duration)
            
            # Velocity curve: slightly louder at the end of slide
            vel_curve = 0.85 + (0.15 * progress)
            vel = humanize_velocity(int(base_velocity * vel_curve), variation=0.05)
            
            notes.append(NoteEvent(
                pitch=pitch,
                start_tick=tick,
                duration_ticks=step_duration + 20,  # Slight overlap for smoothness
                velocity=vel,
                channel=0
            ))
        
        return notes
    
    @staticmethod
    def generate_vibrato_note(
        start_tick: int,
        pitch: int,
        duration_ticks: int,
        base_velocity: int = 85,
        vibrato_depth: int = 1,  # Semitones
        delay_ratio: float = 0.15  # Vibrato starts after this fraction
    ) -> List[NoteEvent]:
        """
        Generate a note with simulated vibrato.
        
        Masenqo vibrato is wide and expressive (5-6 Hz), starting
        after the initial attack. This simulates it with pitch oscillation.
        
        Args:
            start_tick: Starting tick position
            pitch: Base pitch
            duration_ticks: Total note duration
            base_velocity: Base velocity
            vibrato_depth: Pitch variation in semitones
            delay_ratio: Fraction of note before vibrato starts
            
        Returns:
            List of notes simulating vibrato
        """
        notes = []
        
        # Initial attack (no vibrato)
        attack_duration = int(duration_ticks * delay_ratio)
        
        notes.append(NoteEvent(
            pitch=pitch,
            start_tick=start_tick,
            duration_ticks=attack_duration,
            velocity=base_velocity,
            channel=0
        ))
        
        # Vibrato section
        vibrato_start = start_tick + attack_duration
        vibrato_duration = duration_ticks - attack_duration
        
        if vibrato_duration <= TICKS_PER_16TH * 2:
            # Too short for vibrato, just extend the note
            notes[-1].duration_ticks = duration_ticks
            return notes
        
        # Oscillation period (roughly 5.5 Hz at 120 BPM means ~half beat per cycle)
        cycle_ticks = TICKS_PER_BEAT // 2  # ~240 ticks
        num_cycles = max(1, vibrato_duration // cycle_ticks)
        
        for i in range(num_cycles * 2):
            # Alternate between base pitch ± depth
            direction = 1 if i % 2 == 0 else -1
            vibrato_pitch = pitch + (vibrato_depth * direction)
            
            tick = vibrato_start + (i * (cycle_ticks // 2))
            if tick >= start_tick + duration_ticks:
                break
            
            seg_duration = cycle_ticks // 2
            vel = humanize_velocity(int(base_velocity * 0.95), variation=0.05)
            
            notes.append(NoteEvent(
                pitch=vibrato_pitch,
                start_tick=tick,
                duration_ticks=seg_duration,
                velocity=vel,
                channel=0
            ))
        
        return notes
    
    @staticmethod
    def generate_drone(
        start_tick: int,
        end_tick: int,
        drone_pitch: int,
        base_velocity: int = 65
    ) -> List[NoteEvent]:
        """
        Generate a continuous drone (open string accompaniment).
        
        The masenqo often has the open string ringing as a drone
        while the stopped notes play the melody above it.
        
        Args:
            start_tick: Starting tick
            end_tick: Ending tick
            drone_pitch: Drone note MIDI number (typically open string)
            base_velocity: Base velocity (softer than melody)
            
        Returns:
            List of drone notes (long sustains with slight restarts)
        """
        notes = []
        
        total_duration = end_tick - start_tick
        
        # Drone notes: long sustains with periodic "re-bowing"
        rearticulation_interval = TICKS_PER_BAR_4_4 * 2  # Every 2 bars
        
        current_tick = start_tick
        while current_tick < end_tick:
            remaining = end_tick - current_tick
            duration = min(rearticulation_interval, remaining)
            
            # Slight velocity variation for natural bowing
            vel = humanize_velocity(base_velocity, variation=0.15)
            
            notes.append(NoteEvent(
                pitch=drone_pitch,
                start_tick=current_tick,
                duration_ticks=duration,
                velocity=vel,
                channel=0  # Could use separate channel for drone
            ))
            
            current_tick += duration
        
        return notes
    
    @staticmethod
    def generate_double_stop(
        tick: int,
        melody_pitch: int,
        open_string_pitch: int,
        duration_ticks: int,
        melody_velocity: int = 90,
        open_velocity: int = 70
    ) -> List[NoteEvent]:
        """
        Generate a double-stop (melody note with open string).
        
        A characteristic masenqo technique where the stopped melody
        note sounds together with the ringing open string.
        
        Args:
            tick: Tick position
            melody_pitch: Melody note pitch
            open_string_pitch: Open string pitch
            duration_ticks: Note duration
            melody_velocity: Melody note velocity
            open_velocity: Open string velocity
            
        Returns:
            List with both notes sounding together
        """
        return [
            NoteEvent(
                pitch=melody_pitch,
                start_tick=tick,
                duration_ticks=duration_ticks,
                velocity=melody_velocity,
                channel=0
            ),
            NoteEvent(
                pitch=open_string_pitch,
                start_tick=tick,
                duration_ticks=duration_ticks,
                velocity=open_velocity,
                channel=0
            )
        ]


# =============================================================================
# AZMARI PHRASES (Traditional Melodic Patterns)
# =============================================================================

class AzmariPhrases:
    """
    Traditional azmari melodic patterns and phrases.
    
    The azmari (wandering minstrel) tradition has established 
    melodic vocabulary for different musical situations:
    - Call phrases (opening, getting attention)
    - Response phrases (answering singer or other instruments)
    - Dance accompaniment (rhythmic ostinatos)
    - Melismatic runs (ornamental flourishes)
    - Transition phrases (connecting sections)
    
    Each phrase type is expressed as relative scale degrees with
    rhythm and dynamics, to be transposed to the current key.
    """
    
    # Call phrases - opening gestures to start or lead
    CALL_PHRASES = [
        # Ascending call (getting attention)
        [(0, 0.5, 0.9), (2, 0.5, 0.85), (4, 0.75, 0.95), (7, 1.0, 1.0), (9, 1.25, 0.95)],
        # Emphatic call (strong accent)
        [(7, 0.25, 1.0), (4, 0.25, 0.9), (7, 1.0, 1.0), (9, 0.5, 0.95), (7, 1.5, 0.9)],
        # Questioning call (rising)
        [(0, 0.75, 0.9), (4, 0.5, 0.85), (7, 0.75, 0.95), (9, 1.0, 1.0)],
    ]
    
    # Response phrases - answering/completing musical statement
    RESPONSE_PHRASES = [
        # Descending response (resolution)
        [(9, 0.5, 0.95), (7, 0.5, 0.9), (4, 0.75, 0.85), (2, 0.5, 0.8), (0, 1.5, 0.9)],
        # Echo response
        [(7, 0.5, 0.9), (4, 0.75, 0.85), (2, 0.5, 0.8), (0, 1.5, 0.9)],
        # Affirming response
        [(4, 0.5, 0.9), (2, 0.5, 0.85), (4, 0.5, 0.9), (0, 1.5, 0.95)],
    ]
    
    # Dance patterns - rhythmic, repeated ostinatos for eskista
    DANCE_PATTERNS = [
        # Bouncy eskista pattern
        [(0, 0.33, 0.9), (4, 0.33, 0.85), (7, 0.33, 0.95), (4, 0.33, 0.85), (0, 0.33, 0.9), (4, 0.33, 0.85)],
        # Syncopated dance
        [(0, 0.5, 0.95), (7, 0.25, 0.9), (4, 0.5, 0.85), (0, 0.25, 0.9), (7, 0.5, 0.95)],
        # Accent pattern (shoulder shaking)
        [(7, 0.25, 1.0), (4, 0.25, 0.85), (7, 0.5, 1.0), (9, 0.25, 0.95), (7, 0.25, 0.9), (4, 0.5, 0.85)],
    ]
    
    # Melismatic runs - ornamental flourishes
    MELISMATIC_RUNS = [
        # Rapid descending run
        [(12, 0.125, 0.95), (11, 0.125, 0.9), (9, 0.125, 0.9), (7, 0.125, 0.85), 
         (4, 0.125, 0.85), (2, 0.125, 0.8), (0, 0.5, 0.9)],
        # Ascending flourish
        [(0, 0.125, 0.85), (2, 0.125, 0.85), (4, 0.125, 0.9), (7, 0.125, 0.9),
         (9, 0.125, 0.95), (12, 0.25, 1.0)],
        # Turn figure
        [(4, 0.125, 0.9), (7, 0.125, 0.85), (4, 0.125, 0.9), (2, 0.125, 0.85), (4, 0.5, 0.95)],
    ]
    
    # Build/transition phrases
    BUILD_PHRASES = [
        # Ascending build (increasing intensity)
        [(0, 0.5, 0.8), (2, 0.5, 0.85), (4, 0.5, 0.9), (7, 0.5, 0.95), (9, 0.5, 1.0), (12, 1.0, 1.0)],
        # Oscillating build
        [(4, 0.25, 0.85), (7, 0.25, 0.9), (4, 0.25, 0.85), (7, 0.25, 0.95), 
         (4, 0.25, 0.9), (9, 0.25, 1.0), (7, 0.5, 0.95), (9, 0.5, 1.0)],
    ]
    
    # Drop phrases (for impactful moments)
    DROP_PHRASES = [
        # Strong drone hit
        [(0, 2.0, 1.0)],
        # Octave drop
        [(12, 0.5, 1.0), (0, 2.0, 0.95)],
        # Fifth emphasis
        [(7, 1.0, 1.0), (0, 2.0, 0.95)],
    ]
    
    @classmethod
    def get_phrase(
        cls,
        phrase_type: str,
        root_midi: int,
        scale_notes: List[int]
    ) -> List[Tuple[int, int, int]]:
        """
        Get a phrase with actual MIDI notes.
        
        Args:
            phrase_type: Type of phrase ('call', 'response', 'dance', 'melismatic', 'build', 'drop')
            root_midi: Root note MIDI number
            scale_notes: Available scale notes
            
        Returns:
            List of (midi_pitch, duration_ticks, velocity)
        """
        phrase_collections = {
            'call': cls.CALL_PHRASES,
            'response': cls.RESPONSE_PHRASES,
            'dance': cls.DANCE_PATTERNS,
            'melismatic': cls.MELISMATIC_RUNS,
            'build': cls.BUILD_PHRASES,
            'drop': cls.DROP_PHRASES,
        }
        
        collection = phrase_collections.get(phrase_type, cls.CALL_PHRASES)
        pattern = random.choice(collection)
        
        result = []
        for degree, dur_mult, vel_mult in pattern:
            # Find nearest scale note to the degree
            target_pitch = root_midi + degree
            
            # Snap to nearest scale note if available
            if scale_notes:
                nearest = min(scale_notes, key=lambda n: abs(n - target_pitch))
                if abs(nearest - target_pitch) <= 2:
                    target_pitch = nearest
            
            duration_ticks = int(TICKS_PER_BEAT * dur_mult)
            velocity = int(90 * vel_mult)
            
            result.append((target_pitch, duration_ticks, velocity))
        
        return result
    
    @classmethod
    def generate_phrase_notes(
        cls,
        start_tick: int,
        phrase_type: str,
        root_midi: int,
        scale_notes: List[int],
        base_velocity: int = 85
    ) -> List[NoteEvent]:
        """
        Generate NoteEvents for a phrase.
        
        Args:
            start_tick: Starting tick position
            phrase_type: Type of phrase
            root_midi: Root note MIDI number
            scale_notes: Available scale notes
            base_velocity: Base velocity
            
        Returns:
            List of NoteEvents for the phrase
        """
        phrase = cls.get_phrase(phrase_type, root_midi, scale_notes)
        notes = []
        
        current_tick = start_tick
        for pitch, duration, vel in phrase:
            adjusted_vel = int(vel * (base_velocity / 90))
            adjusted_vel = humanize_velocity(adjusted_vel, variation=0.1)
            
            notes.append(NoteEvent(
                pitch=max(36, min(96, pitch)),  # Clamp to reasonable range
                start_tick=current_tick,
                duration_ticks=duration,
                velocity=min(127, adjusted_vel),
                channel=0
            ))
            
            current_tick += duration
        
        return notes


# =============================================================================
# MASENQO AGENT
# =============================================================================

class MasenqoAgent(IPerformerAgent):
    """
    Masterclass Ethiopian masenqo performer agent.
    
    A professional-level masenqo player that understands:
    - Ethiopian qenet (modal) system for scale selection
    - Bowing techniques: continuous bow, vibrato, slides
    - Ornaments: grace notes, trills, melismatic runs
    - Azmari phrase vocabulary for call-and-response
    - Drone accompaniment (open string technique)
    - Genre context (traditional, ethio-jazz, eskista)
    
    The agent generates musically-informed masenqo melodies that
    complement Ethiopian ensembles while respecting the unique
    character of this voice-like bowed instrument.
    
    Attributes:
        _name: Human-readable agent name
        _qenet_theory: Reference to qenet theory knowledge
        _techniques: Reference to masenqo techniques
        _azmari_phrases: Reference to phrase library
        _decisions: Log of creative decisions
        
    Example:
        ```python
        masenqo = MasenqoAgent()
        masenqo.set_personality(MASENQO_PRESETS['traditional_azmari'])
        
        result = masenqo.perform(context, section)
        # result.notes contains the masenqo MIDI events
        # result.decisions_made contains reasoning log
        ```
    """
    
    # Standard masenqo range (A3 to E5)
    RANGE_LOW = 57   # A3
    RANGE_HIGH = 76  # E5
    TYPICAL_OPEN_STRING = 57  # A3
    
    # MIDI channel for masenqo (strings group)
    MIDI_CHANNEL = 0
    
    def __init__(self, name: str = "Azmari Masenqo Player"):
        """
        Initialize the masenqo agent.
        
        Args:
            name: Human-readable name for this agent instance
        """
        super().__init__()
        self._name = name
        self._qenet_theory = QenetTheory
        self._techniques = MasenqoTechniques
        self._azmari_phrases = AzmariPhrases
        self._decisions: List[str] = []
    
    @property
    def role(self) -> AgentRole:
        """This agent fulfills the STRINGS role."""
        return AgentRole.STRINGS
    
    @property
    def name(self) -> str:
        """Human-readable agent name."""
        return self._name
    
    def perform(
        self,
        context: PerformanceContext,
        section: SongSection,
        personality: Optional[AgentPersonality] = None
    ) -> PerformanceResult:
        """
        Generate masenqo notes for the given section.
        
        This is the main entry point for masenqo generation. The agent:
        1. Analyzes context (key, tension, energy) to select qenet mode
        2. Determines appropriate melodic density and ornamentation
        3. Generates base melodic line using characteristic phrases
        4. Adds ornaments (grace notes, trills, slides) based on personality
        5. Optionally adds drone accompaniment
        6. Applies vibrato to sustained notes
        7. Logs all creative decisions
        
        Args:
            context: Shared performance state (tempo, key, tension, etc.)
            section: The song section to generate for
            personality: Optional personality override
            
        Returns:
            PerformanceResult containing generated notes and metadata
        """
        # Reset decision log
        self._decisions = []
        
        # Resolve personality
        effective_personality = personality or self._personality
        if effective_personality is None:
            genre = self._extract_genre_from_context(context)
            effective_personality = self._select_preset_for_genre(genre)
            self._log_decision(f"Using preset personality for genre '{genre}'")
        else:
            self._log_decision(f"Using provided personality (complexity={effective_personality.complexity:.2f})")
        
        # Scale personality by tension
        scaled_personality = effective_personality.apply_tension_scaling(context.tension)
        self._log_decision(f"Applied tension scaling ({context.tension:.2f})")
        
        # Determine qenet mode
        qenet_mode = self._select_qenet_mode(context, scaled_personality)
        self._log_decision(f"Selected qenet mode: {qenet_mode}")
        
        # Get root note and scale
        root_midi = self._get_root_note(context.key)
        scale_notes = self._qenet_theory.get_scale_notes(root_midi, qenet_mode, octaves=2)
        
        # Extend scale to masenqo range
        extended_scale = self._extend_scale_to_range(scale_notes)
        self._log_decision(f"Scale notes: {len(extended_scale)} notes in range")
        
        # Determine time signature for proper bar duration
        time_sig = getattr(context, 'time_signature', (4, 4))
        if hasattr(context, 'reference_features') and context.reference_features:
            ref_time_sig = context.reference_features.get('time_signature')
            if ref_time_sig:
                time_sig = ref_time_sig
        
        ticks_per_bar = get_ticks_per_bar(time_sig)
        self._log_decision(f"Time signature: {time_sig[0]}/{time_sig[1]}")
        
        # Generate base melodic line
        base_notes = self._generate_melodic_line(
            section,
            context,
            scaled_personality,
            qenet_mode,
            root_midi,
            extended_scale,
            ticks_per_bar
        )
        self._log_decision(f"Generated {len(base_notes)} melodic notes")
        
        patterns_used = [qenet_mode]
        
        # Add ornaments based on personality
        ornament_density = scaled_personality.ghost_note_density  # Repurposed for ornaments
        if ornament_density > 0.2:
            ornament_notes = self._add_ornaments(
                base_notes,
                ornament_density,
                extended_scale,
                scaled_personality
            )
            base_notes.extend(ornament_notes)
            if ornament_notes:
                self._log_decision(f"Added {len(ornament_notes)} ornament notes")
                patterns_used.append('ornamented')
        
        # Add drone if appropriate
        if self._should_add_drone(section, scaled_personality):
            drone_pitch = self._get_drone_pitch(root_midi, scale_notes)
            drone_notes = self._techniques.generate_drone(
                section.start_tick,
                section.end_tick,
                drone_pitch,
                base_velocity=int(70 * scaled_personality.aggressiveness)
            )
            base_notes.extend(drone_notes)
            self._log_decision(f"Added drone on {midi_to_note_name(drone_pitch)}")
            patterns_used.append('drone')
        
        # Determine fill locations
        fill_locations = []
        if context.fill_opportunity or self._should_add_fill(section, scaled_personality):
            fill_notes, fill_tick = self._generate_section_fill(
                section,
                context,
                scaled_personality,
                root_midi,
                extended_scale
            )
            if fill_notes:
                base_notes.extend(fill_notes)
                fill_locations.append(fill_tick)
                self._log_decision(f"Added fill at tick {fill_tick}")
                patterns_used.append('fill')
        
        # Apply push/pull timing
        if abs(scaled_personality.push_pull) > 0.01:
            base_notes = self._apply_push_pull(base_notes, scaled_personality.push_pull)
            self._log_decision(f"Applied push/pull: {scaled_personality.push_pull:+.3f}")
        
        # Sort notes by time
        base_notes.sort(key=lambda n: (n.start_tick, n.pitch))
        
        # Build result
        result = PerformanceResult(
            notes=base_notes,
            agent_role=self.role,
            agent_name=self.name,
            personality_applied=scaled_personality,
            decisions_made=self._decisions.copy(),
            patterns_used=patterns_used,
            fill_locations=fill_locations
        )
        
        self._log_decision(f"Performance complete: {len(base_notes)} total notes")
        
        return result
    
    def react_to_cue(
        self,
        cue_type: str,
        context: PerformanceContext
    ) -> List[NoteEvent]:
        """
        React to a performance cue with an immediate response.
        
        Supported cues for masenqo:
        - "fill": Melismatic run
        - "call": Opening phrase (for call-and-response)
        - "response": Answering phrase
        - "build": Ascending run with increasing intensity
        - "drop": Strong drone note
        
        Args:
            cue_type: The type of cue to react to
            context: Current performance context
            
        Returns:
            List of NoteEvent for the cue response
        """
        cue_type = cue_type.lower().strip()
        
        # Get current state
        current_tick = int(context.section_position_beats * TICKS_PER_BEAT)
        personality = self._personality or MASENQO_PRESETS['traditional_azmari']
        
        # Determine scale context
        root_midi = self._get_root_note(context.key)
        qenet_mode = self._qenet_theory.suggest_qenet_for_context(
            context.key,
            context.tension,
            context.energy_level
        )
        scale_notes = self._qenet_theory.get_scale_notes(root_midi, qenet_mode, octaves=2)
        extended_scale = self._extend_scale_to_range(scale_notes)
        
        base_velocity = int(90 * (0.8 + 0.4 * personality.aggressiveness))
        
        if cue_type == 'fill':
            # Melismatic run
            return self._azmari_phrases.generate_phrase_notes(
                current_tick, 'melismatic', root_midi, extended_scale, base_velocity
            )
        
        elif cue_type == 'call':
            # Opening call phrase
            return self._azmari_phrases.generate_phrase_notes(
                current_tick, 'call', root_midi, extended_scale, base_velocity
            )
        
        elif cue_type == 'response':
            # Answering phrase
            return self._azmari_phrases.generate_phrase_notes(
                current_tick, 'response', root_midi, extended_scale, base_velocity
            )
        
        elif cue_type == 'build':
            # Ascending build phrase
            return self._azmari_phrases.generate_phrase_notes(
                current_tick, 'build', root_midi, extended_scale, base_velocity
            )
        
        elif cue_type == 'drop':
            # Strong drone hit
            notes = self._azmari_phrases.generate_phrase_notes(
                current_tick, 'drop', root_midi, extended_scale, base_velocity + 10
            )
            # Add vibrato to the sustained note
            if notes:
                main_note = notes[0]
                vibrato_notes = self._techniques.generate_vibrato_note(
                    main_note.start_tick,
                    main_note.pitch,
                    main_note.duration_ticks,
                    main_note.velocity
                )
                return vibrato_notes
            return notes
        
        else:
            logger.warning(f"Unknown cue type for masenqo: {cue_type}")
            return []
    
    # =========================================================================
    # PRIVATE HELPER METHODS
    # =========================================================================
    
    def _log_decision(self, decision: str) -> None:
        """Log a creative decision for transparency."""
        self._decisions.append(decision)
        logger.debug(f"[{self.name}] {decision}")
    
    def _extract_genre_from_context(self, context: PerformanceContext) -> str:
        """Extract genre string from context."""
        if context.reference_features and 'genre' in context.reference_features:
            return context.reference_features['genre']
        return 'ethiopian'
    
    def _select_preset_for_genre(self, genre: str) -> AgentPersonality:
        """Select appropriate personality preset for genre."""
        genre_lower = genre.lower()
        
        if 'jazz' in genre_lower or 'ethio_jazz' in genre_lower:
            return MASENQO_PRESETS['ethio_jazz_fusion']
        elif 'eskista' in genre_lower or 'dance' in genre_lower:
            return MASENQO_PRESETS['eskista_energetic']
        elif 'spiritual' in genre_lower or 'church' in genre_lower:
            return MASENQO_PRESETS['meditative_ambassel']
        elif 'traditional' in genre_lower:
            return MASENQO_PRESETS['traditional_azmari']
        else:
            return MASENQO_PRESETS['traditional_azmari']
    
    def _get_root_note(self, key: str) -> int:
        """Convert key to MIDI root note in masenqo range."""
        # Place root in the middle of masenqo range
        try:
            root_base = note_name_to_midi(key.replace('m', '').replace('M', ''), 4)
            # Adjust to masenqo range (A3-E5, centered around D4-A4)
            while root_base < self.RANGE_LOW:
                root_base += 12
            while root_base > self.RANGE_LOW + 12:
                root_base -= 12
            return root_base
        except Exception:
            return 62  # Default to D4
    
    def _select_qenet_mode(
        self,
        context: PerformanceContext,
        personality: AgentPersonality
    ) -> str:
        """Select appropriate qenet mode based on context."""
        return self._qenet_theory.suggest_qenet_for_context(
            context.key,
            context.tension,
            context.energy_level,
            self._extract_genre_from_context(context)
        )
    
    def _extend_scale_to_range(self, scale_notes: List[int]) -> List[int]:
        """Extend scale notes to cover full masenqo range."""
        extended = set()
        
        for note in scale_notes:
            # Add note and octave transpositions within range
            for octave_offset in range(-2, 3):
                transposed = note + (octave_offset * 12)
                if self.RANGE_LOW <= transposed <= self.RANGE_HIGH:
                    extended.add(transposed)
        
        return sorted(extended)
    
    def _get_drone_pitch(self, root_midi: int, scale_notes: List[int]) -> int:
        """Determine the best drone pitch (typically root or fifth)."""
        # Prefer the lowest scale note in range as drone
        candidates = [root_midi]
        
        # Add fifth below root if in range
        fifth_below = root_midi - 5
        if fifth_below >= self.RANGE_LOW:
            candidates.append(fifth_below)
        
        # Default to open string pitch
        if self.TYPICAL_OPEN_STRING in scale_notes:
            candidates.append(self.TYPICAL_OPEN_STRING)
        
        return min(candidates)
    
    def _generate_melodic_line(
        self,
        section: SongSection,
        context: PerformanceContext,
        personality: AgentPersonality,
        qenet_mode: str,
        root_midi: int,
        scale_notes: List[int],
        ticks_per_bar: int
    ) -> List[NoteEvent]:
        """
        Generate the main melodic line for the section.
        
        Uses a combination of:
        - Characteristic qenet phrases
        - Azmari melodic vocabulary
        - Contextual density adjustments
        """
        notes = []
        
        # Base velocity from personality
        base_velocity = int(90 * (0.75 + 0.25 * personality.aggressiveness))
        
        # Determine phrase density based on section type and personality
        if section.section_type in [SectionType.INTRO, SectionType.OUTRO]:
            phrase_density = 0.4 * personality.complexity
        elif section.section_type in [SectionType.DROP, SectionType.CHORUS]:
            phrase_density = 0.8 + (0.2 * personality.complexity)
        elif section.section_type == SectionType.VERSE:
            phrase_density = 0.5 + (0.3 * personality.complexity)
        else:
            phrase_density = 0.6
        
        # Generate phrases bar by bar
        current_tick = section.start_tick
        phrase_cooldown = 0
        
        while current_tick < section.end_tick:
            remaining_ticks = section.end_tick - current_tick
            
            # Decide what to play
            if phrase_cooldown <= 0 and random.random() < phrase_density:
                # Play a phrase
                phrase_type = self._select_phrase_type(section.section_type, personality)
                phrase_notes = self._azmari_phrases.generate_phrase_notes(
                    current_tick,
                    phrase_type,
                    root_midi,
                    scale_notes,
                    base_velocity
                )
                
                if phrase_notes:
                    # Check if phrase fits in remaining time
                    phrase_end = phrase_notes[-1].start_tick + phrase_notes[-1].duration_ticks
                    if phrase_end <= section.end_tick:
                        notes.extend(phrase_notes)
                        phrase_duration = phrase_end - current_tick
                        current_tick = phrase_end
                        # Set cooldown based on variation tendency (more variation = shorter cooldown)
                        phrase_cooldown = int(ticks_per_bar * (0.5 + 0.5 * (1 - personality.variation_tendency)))
                    else:
                        # Phrase too long, play single sustained note instead
                        notes.append(self._create_sustained_note(
                            current_tick, root_midi, remaining_ticks, base_velocity
                        ))
                        current_tick += remaining_ticks
            else:
                # Rest or sustained note
                if random.random() < 0.3:
                    # Play a sustained note with vibrato
                    sustain_duration = min(ticks_per_bar, remaining_ticks)
                    sustain_pitch = random.choice(scale_notes) if scale_notes else root_midi
                    
                    vibrato_notes = self._techniques.generate_vibrato_note(
                        current_tick,
                        sustain_pitch,
                        sustain_duration,
                        base_velocity - 10,
                        vibrato_depth=1 if personality.complexity > 0.5 else 0
                    )
                    notes.extend(vibrato_notes)
                    current_tick += sustain_duration
                else:
                    # Rest
                    rest_duration = min(ticks_per_bar // 2, remaining_ticks)
                    current_tick += rest_duration
                
                phrase_cooldown -= ticks_per_bar // 2
        
        return notes
    
    def _select_phrase_type(
        self,
        section_type: SectionType,
        personality: AgentPersonality
    ) -> str:
        """Select appropriate phrase type for section context."""
        if section_type == SectionType.INTRO:
            return random.choice(['call', 'melismatic'])
        elif section_type == SectionType.OUTRO:
            return random.choice(['response', 'drop'])
        elif section_type in [SectionType.CHORUS, SectionType.DROP]:
            if personality.aggressiveness > 0.6:
                return random.choice(['dance', 'call', 'build'])
            return random.choice(['call', 'dance'])
        elif section_type == SectionType.VERSE:
            return random.choice(['call', 'response', 'melismatic'])
        elif section_type == SectionType.BUILDUP:
            return 'build'
        elif section_type == SectionType.BREAKDOWN:
            return random.choice(['response', 'melismatic'])
        else:
            return random.choice(['call', 'response'])
    
    def _create_sustained_note(
        self,
        tick: int,
        pitch: int,
        duration: int,
        velocity: int
    ) -> NoteEvent:
        """Create a simple sustained note."""
        return NoteEvent(
            pitch=pitch,
            start_tick=tick,
            duration_ticks=duration,
            velocity=humanize_velocity(velocity, variation=0.1),
            channel=self.MIDI_CHANNEL
        )
    
    def _add_ornaments(
        self,
        notes: List[NoteEvent],
        density: float,
        scale_notes: List[int],
        personality: AgentPersonality
    ) -> List[NoteEvent]:
        """
        Add ornamental notes (grace notes, trills) to existing melody.
        
        Args:
            notes: Existing melodic notes
            density: Ornament density (0-1)
            scale_notes: Available scale notes
            personality: Current personality
            
        Returns:
            List of additional ornament notes
        """
        ornament_notes = []
        
        for note in notes:
            # Skip very short notes
            if note.duration_ticks < TICKS_PER_8TH:
                continue
            
            # Probability of adding ornament
            if random.random() > density:
                continue
            
            # Select ornament type
            ornament_roll = random.random()
            
            if ornament_roll < 0.4:
                # Grace note
                grace_notes = self._techniques.generate_grace_note(
                    note.start_tick,
                    note.pitch,
                    note.velocity,
                    approach_from_below=random.random() < 0.6
                )
                ornament_notes.extend(grace_notes)
            
            elif ornament_roll < 0.6 and note.duration_ticks >= TICKS_PER_BEAT:
                # Trill (only on longer notes)
                trill_duration = min(note.duration_ticks // 2, TICKS_PER_BEAT)
                trill_notes = self._techniques.generate_trill(
                    note.start_tick,
                    note.pitch,
                    trill_duration,
                    note.velocity
                )
                ornament_notes.extend(trill_notes)
            
            elif ornament_roll < 0.75 and personality.complexity > 0.5:
                # Slide to next note (if there's a next note)
                note_idx = notes.index(note)
                if note_idx < len(notes) - 1:
                    next_note = notes[note_idx + 1]
                    pitch_diff = abs(next_note.pitch - note.pitch)
                    
                    if 2 <= pitch_diff <= 5:
                        # Good candidate for slide
                        slide_start = note.start_tick + (note.duration_ticks // 2)
                        slide_duration = note.duration_ticks // 2
                        
                        slide_notes = self._techniques.generate_slide(
                            slide_start,
                            note.pitch,
                            next_note.pitch,
                            slide_duration,
                            note.velocity
                        )
                        ornament_notes.extend(slide_notes)
        
        return ornament_notes
    
    def _should_add_drone(
        self,
        section: SongSection,
        personality: AgentPersonality
    ) -> bool:
        """Decide if drone should be added based on context."""
        # Drones suit slower, more meditative sections
        if section.section_type in [SectionType.INTRO, SectionType.BREAKDOWN]:
            return random.random() < 0.6
        
        if section.section_type == SectionType.VERSE:
            return random.random() < 0.3
        
        # Less likely in high-energy sections
        if section.section_type in [SectionType.DROP, SectionType.CHORUS]:
            return random.random() < 0.15
        
        # Default based on consistency (more consistent = more drone)
        return random.random() < personality.consistency * 0.3
    
    def _should_add_fill(
        self,
        section: SongSection,
        personality: AgentPersonality
    ) -> bool:
        """Decide if a fill should be added."""
        # Always add fill at section transitions
        if section.section_type in [SectionType.BUILDUP, SectionType.PRE_CHORUS]:
            return True
        
        # Personality-based chance
        fill_chance = personality.fill_frequency * 0.5
        
        if section.section_type in [SectionType.CHORUS, SectionType.DROP]:
            fill_chance += 0.2
        
        return random.random() < fill_chance
    
    def _generate_section_fill(
        self,
        section: SongSection,
        context: PerformanceContext,
        personality: AgentPersonality,
        root_midi: int,
        scale_notes: List[int]
    ) -> Tuple[List[NoteEvent], int]:
        """
        Generate a fill for the end of section.
        
        Returns:
            Tuple of (fill notes, fill start tick)
        """
        fill_duration = 1.0 if personality.complexity < 0.5 else 2.0
        fill_start = section.end_tick - int(fill_duration * TICKS_PER_BEAT)
        
        base_velocity = int(90 * (0.8 + 0.4 * personality.aggressiveness))
        
        # Select fill type
        if personality.complexity > 0.7:
            # Complex: melismatic run
            notes = self._azmari_phrases.generate_phrase_notes(
                fill_start, 'melismatic', root_midi, scale_notes, base_velocity
            )
        elif personality.complexity > 0.4:
            # Medium: build phrase
            notes = self._azmari_phrases.generate_phrase_notes(
                fill_start, 'build', root_midi, scale_notes, base_velocity
            )
        else:
            # Simple: ascending slide
            notes = self._techniques.generate_slide(
                fill_start,
                root_midi,
                root_midi + 7,
                int(fill_duration * TICKS_PER_BEAT),
                base_velocity
            )
        
        return notes, fill_start
    
    def _apply_push_pull(
        self,
        notes: List[NoteEvent],
        push_pull: float
    ) -> List[NoteEvent]:
        """Apply push/pull timing adjustment to all notes."""
        max_offset = TICKS_PER_16TH // 2
        offset = int(push_pull * max_offset)
        
        for note in notes:
            note.start_tick = max(0, note.start_tick + offset)
        
        return notes
