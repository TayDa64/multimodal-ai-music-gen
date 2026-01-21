"""
WashintAgent - Masterclass Ethiopian Bamboo Flute Performer

This module implements a professional washint (ዋሽንት) player agent with deep knowledge of:
- Ethiopian Qenet (Modal) System: Tizita, Ambassel, Bati, Anchihoye scales
- Breath Techniques: Long phrases, breath accents, crescendos, overblowing
- Ornaments: Grace notes, trills, flutter tongue, pitch bends, microtones
- Melodic Vocabulary: Call phrases, response phrases, melismatic runs, traditional licks

The WashintAgent is designed to generate authentic Ethiopian flute melodies
that complement traditional ensembles (masenqo, krar, kebero) or modern
Ethio-jazz arrangements, while serving as the lead melodic voice.

Physical Instrument Reference:
    The washint is an end-blown bamboo or metal flute central to Ethiopian music:
    - End-blown tube (bamboo or metal)
    - 4-5 finger holes
    - Range: Approximately D4-D6 (MIDI 62-86, roughly 294Hz-1175Hz)
    - Various sizes for different ranges (soprano, alto, bass)
    
Musical Characteristics:
    - Breath-controlled dynamics (natural crescendo through phrases)
    - Overblowing for octave jumps (increased breath pressure)
    - Rich vibrato from diaphragm control
    - Flutter tonguing for rapid articulation
    - Pitch bending through partial hole coverage (microtones)
    - Long melodic phrases with natural breath points
    - Often doubles or embellishes vocal melody

Architecture Notes:
    This is a Stage 1 (offline) implementation with comprehensive Ethiopian
    flute music theory. Stage 2 will add API-backed generation for creative variation.
    
    Imports QenetTheory from the masenqo module to share Ethiopian scale knowledge.

Example:
    ```python
    from multimodal_gen.agents.performers import WashintAgent
    from multimodal_gen.agents import PerformanceContext, WASHINT_PRESETS
    
    washint = WashintAgent()
    washint.set_personality(WASHINT_PRESETS['traditional_shepherd'])
    
    result = washint.perform(context, section)
    print(f"Generated {len(result.notes)} washint notes")
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

# Import Ethiopian scale theory from masenqo
from .masenqo import QenetTheory

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
# WASHINT PERSONALITY PRESETS
# =============================================================================

WASHINT_PRESETS: Dict[str, AgentPersonality] = {
    "traditional_shepherd": AgentPersonality(
        aggressiveness=0.4,
        complexity=0.5,
        consistency=0.7,
        push_pull=0.0,
        swing_affinity=0.2,  # Ethiopian music has groove but not swing
        fill_frequency=0.3,
        ghost_note_density=0.4,  # Ornamentation density
        variation_tendency=0.5,
        signature_patterns=["pastoral_phrase", "long_breath", "ascending_call"]
    ),
    
    "ethio_jazz_virtuoso": AgentPersonality(
        aggressiveness=0.5,
        complexity=0.8,
        consistency=0.6,
        push_pull=-0.02,  # Slightly behind for jazz feel
        swing_affinity=0.35,
        fill_frequency=0.4,
        ghost_note_density=0.7,
        variation_tendency=0.7,
        signature_patterns=["jazz_phrase", "chromatic_run", "flutter_ornament"]
    ),
    
    "eskista_dancer": AgentPersonality(
        aggressiveness=0.65,
        complexity=0.5,
        consistency=0.75,
        push_pull=0.03,  # Slightly ahead for dance energy
        swing_affinity=0.15,
        fill_frequency=0.45,
        ghost_note_density=0.5,
        variation_tendency=0.4,
        signature_patterns=["dance_melody", "rhythmic_accent", "call_response"]
    ),
    
    "spiritual_meditator": AgentPersonality(
        aggressiveness=0.2,
        complexity=0.35,
        consistency=0.85,
        push_pull=-0.04,  # Behind the beat for meditative feel
        swing_affinity=0.0,
        fill_frequency=0.15,
        ghost_note_density=0.3,
        variation_tendency=0.25,
        signature_patterns=["sustained_breath", "slow_vibrato", "contemplative"]
    ),
    
    "ornamental_master": AgentPersonality(
        aggressiveness=0.5,
        complexity=0.9,
        consistency=0.55,
        push_pull=0.0,
        swing_affinity=0.2,
        fill_frequency=0.55,
        ghost_note_density=0.85,  # Heavy ornamentation
        variation_tendency=0.75,
        signature_patterns=["rapid_trill", "flutter_tongue", "melismatic_cascade"]
    ),
    
    "ensemble_collaborator": AgentPersonality(
        aggressiveness=0.4,
        complexity=0.55,
        consistency=0.8,
        push_pull=0.0,
        swing_affinity=0.25,
        fill_frequency=0.3,
        ghost_note_density=0.45,
        variation_tendency=0.45,
        signature_patterns=["call_phrase", "response_phrase", "doubling"]
    ),
}


# =============================================================================
# WASHINT PHYSICAL CONSTRAINTS
# =============================================================================

class WashintRange:
    """
    Physical instrument constraints for the washint.
    
    The washint's range depends on the size of the instrument and
    the player's skill with overblowing. Different sizes exist:
    - Small (soprano): Higher range, brighter tone
    - Medium (alto): Standard range, most common
    - Large (bass): Lower range, richer tone
    
    Overblowing allows jumping to the upper register (roughly an
    octave above the fundamental range).
    
    Attributes:
        RANGE_LOW: Lowest playable note (D4 typically)
        RANGE_HIGH: Highest playable note (D6 with overblowing)
        COMFORTABLE_LOW: Lower bound of comfortable range
        COMFORTABLE_HIGH: Upper bound of comfortable range
        OVERBLOW_THRESHOLD: Notes above this require overblowing
    """
    
    # Standard medium washint range
    RANGE_LOW = 62   # D4 - lowest fundamental
    RANGE_HIGH = 86  # D6 - highest with overblowing
    
    # Comfortable playing range (sweet spot)
    COMFORTABLE_LOW = 65   # F4
    COMFORTABLE_HIGH = 79  # G5
    
    # Overblowing threshold (notes above require more breath pressure)
    OVERBLOW_THRESHOLD = 74  # D5 - above this enters overblow register
    
    # Hz reference for tuning
    FUNDAMENTAL_FREQ = 294  # D4 in Hz
    
    @classmethod
    def is_in_range(cls, pitch: int) -> bool:
        """Check if a pitch is within the washint's playable range."""
        return cls.RANGE_LOW <= pitch <= cls.RANGE_HIGH
    
    @classmethod
    def is_comfortable(cls, pitch: int) -> bool:
        """Check if a pitch is in the comfortable playing range."""
        return cls.COMFORTABLE_LOW <= pitch <= cls.COMFORTABLE_HIGH
    
    @classmethod
    def requires_overblowing(cls, pitch: int) -> bool:
        """Check if a pitch requires overblowing technique."""
        return pitch > cls.OVERBLOW_THRESHOLD
    
    @classmethod
    def clamp_to_range(cls, pitch: int) -> int:
        """Clamp a pitch to the washint's playable range."""
        return max(cls.RANGE_LOW, min(cls.RANGE_HIGH, pitch))
    
    @classmethod
    def get_octave_equivalent(cls, pitch: int, target_octave: str = 'middle') -> int:
        """
        Get the octave equivalent of a pitch within the washint range.
        
        Args:
            pitch: Original MIDI pitch
            target_octave: 'low', 'middle', or 'high'
            
        Returns:
            Pitch transposed to target octave within range
        """
        # Get pitch class (0-11)
        pitch_class = pitch % 12
        
        if target_octave == 'low':
            base_octave = 5  # Octave 5 for MIDI (60-71 is C4-B4)
            result = pitch_class + (base_octave * 12)
        elif target_octave == 'high':
            base_octave = 6
            result = pitch_class + (base_octave * 12)
        else:  # middle
            base_octave = 5
            result = pitch_class + (base_octave * 12)
            # Adjust to comfortable range
            while result < cls.COMFORTABLE_LOW:
                result += 12
            while result > cls.COMFORTABLE_HIGH:
                result -= 12
        
        return cls.clamp_to_range(result)


# =============================================================================
# BREATH PHRASING SYSTEM
# =============================================================================

class BreathPhrasing:
    """
    Breath-aware melody generation for the washint.
    
    The washint is a wind instrument that requires careful breath
    management. This class models:
    - Phrase lengths based on breath capacity (typically 4-8 beats)
    - Natural breath points (rests between phrases)
    - Breath accents (stronger attacks on downbeats)
    - Crescendo through phrases (natural breath pressure increase)
    
    Musical Characteristics:
        - Phrases typically end with natural tapering
        - Longer notes consume more breath
        - Higher notes require more breath pressure
        - Fast passages require quick breaths between
    
    Example:
        ```python
        phrase_length = BreathPhrasing.get_phrase_length(energy=0.6)
        rest_duration = BreathPhrasing.get_breath_rest_duration(phrase_length)
        velocities = BreathPhrasing.apply_breath_dynamics(notes, crescendo=True)
        ```
    """
    
    # Breath capacity constants (in beats)
    MIN_PHRASE_LENGTH = 2.0   # Minimum phrase before breath needed
    MAX_PHRASE_LENGTH = 8.0   # Maximum sustained phrase
    TYPICAL_PHRASE_LENGTH = 4.0  # Common phrase length
    
    # Breath rest durations (in beats)
    QUICK_BREATH = 0.25   # Quarter beat (16th note)
    NORMAL_BREATH = 0.5   # Half beat (8th note)
    DEEP_BREATH = 1.0     # Full beat
    
    # Dynamics (velocity multipliers through phrase)
    PHRASE_START_VELOCITY = 0.85   # Start of phrase (lighter attack)
    PHRASE_PEAK_VELOCITY = 1.0     # Peak of phrase (full breath)
    PHRASE_END_VELOCITY = 0.75     # End of phrase (breath depleting)
    
    @classmethod
    def get_phrase_length(cls, energy: float, complexity: float = 0.5) -> float:
        """
        Calculate appropriate phrase length based on energy/complexity.
        
        Higher energy music typically has shorter, more frequent phrases.
        Higher complexity allows for longer, more elaborate phrases.
        
        Args:
            energy: Energy level (0-1)
            complexity: Complexity level (0-1)
            
        Returns:
            Phrase length in beats
        """
        # Base phrase length
        base = cls.TYPICAL_PHRASE_LENGTH
        
        # Energy shortens phrases (more frequent breaths)
        energy_factor = 1.0 - (0.3 * energy)
        
        # Complexity allows longer phrases
        complexity_factor = 0.8 + (0.4 * complexity)
        
        length = base * energy_factor * complexity_factor
        
        # Add some randomness
        length *= random.uniform(0.85, 1.15)
        
        return max(cls.MIN_PHRASE_LENGTH, min(cls.MAX_PHRASE_LENGTH, length))
    
    @classmethod
    def get_breath_rest_duration(
        cls,
        previous_phrase_length: float,
        energy: float = 0.5
    ) -> float:
        """
        Calculate rest duration for breathing between phrases.
        
        Longer phrases require longer rests to recover breath.
        Higher energy uses quicker breaths.
        
        Args:
            previous_phrase_length: Length of preceding phrase in beats
            energy: Current energy level (0-1)
            
        Returns:
            Rest duration in beats
        """
        # Longer phrases need longer rests
        if previous_phrase_length > 6:
            base_rest = cls.DEEP_BREATH
        elif previous_phrase_length > 4:
            base_rest = cls.NORMAL_BREATH
        else:
            base_rest = cls.QUICK_BREATH
        
        # Higher energy = quicker breaths
        energy_factor = 1.0 - (0.4 * energy)
        
        rest = base_rest * energy_factor
        
        return max(cls.QUICK_BREATH, rest)
    
    @classmethod
    def calculate_breath_velocity_curve(
        cls,
        note_position_in_phrase: float,
        phrase_length: float,
        crescendo: bool = True,
        base_velocity: int = 85
    ) -> int:
        """
        Calculate velocity based on position within breath phrase.
        
        Models natural breath dynamics:
        - Crescendo: Builds through phrase (typical in ascending lines)
        - Decrescendo: Tapers at end (typical ending gesture)
        
        Args:
            note_position_in_phrase: Position from start (0 = start)
            phrase_length: Total phrase length
            crescendo: Whether dynamics build or taper
            base_velocity: Starting velocity
            
        Returns:
            Velocity adjusted for breath position
        """
        progress = note_position_in_phrase / max(0.1, phrase_length)
        progress = max(0.0, min(1.0, progress))
        
        if crescendo:
            # Build from start to 80% of phrase, then slight taper
            if progress < 0.8:
                multiplier = cls.PHRASE_START_VELOCITY + (
                    (cls.PHRASE_PEAK_VELOCITY - cls.PHRASE_START_VELOCITY) * (progress / 0.8)
                )
            else:
                # Slight taper at end
                taper_progress = (progress - 0.8) / 0.2
                multiplier = cls.PHRASE_PEAK_VELOCITY - (0.1 * taper_progress)
        else:
            # Decrescendo: start full, taper through phrase
            multiplier = cls.PHRASE_PEAK_VELOCITY - (
                (cls.PHRASE_PEAK_VELOCITY - cls.PHRASE_END_VELOCITY) * progress
            )
        
        return int(base_velocity * multiplier)
    
    @classmethod
    def apply_breath_dynamics(
        cls,
        notes: List[NoteEvent],
        phrase_start_tick: int,
        phrase_length_ticks: int,
        crescendo: bool = True
    ) -> List[NoteEvent]:
        """
        Apply breath dynamics to a list of notes in a phrase.
        
        Args:
            notes: List of NoteEvents to modify (in place)
            phrase_start_tick: Tick where phrase begins
            phrase_length_ticks: Total phrase length in ticks
            crescendo: Whether to apply crescendo (True) or decrescendo (False)
            
        Returns:
            Modified notes list (same list, modified in place)
        """
        for note in notes:
            position = note.start_tick - phrase_start_tick
            position_beats = position / TICKS_PER_BEAT
            phrase_beats = phrase_length_ticks / TICKS_PER_BEAT
            
            new_velocity = cls.calculate_breath_velocity_curve(
                position_beats,
                phrase_beats,
                crescendo,
                note.velocity
            )
            note.velocity = max(40, min(127, new_velocity))
        
        return notes
    
    @classmethod
    def get_breath_accent_positions(cls, bar_start: int, time_sig: Tuple[int, int] = (4, 4)) -> List[int]:
        """
        Get tick positions that should have breath accents.
        
        Breath accents typically fall on strong beats (downbeats)
        where the player naturally gives more breath support.
        
        Args:
            bar_start: Tick of bar start
            time_sig: Time signature tuple
            
        Returns:
            List of tick positions for accents
        """
        num, denom = time_sig
        accents = []
        
        if num == 4:  # 4/4 time
            # Accent beats 1 and 3
            accents = [bar_start, bar_start + (2 * TICKS_PER_BEAT)]
        elif num == 3:  # 3/4 or 6/8
            # Accent beat 1
            accents = [bar_start]
        elif num == 6:  # 6/8
            # Accent beats 1 and 4
            accents = [bar_start, bar_start + (3 * TICKS_PER_BEAT)]
        else:
            # Default: accent beat 1
            accents = [bar_start]
        
        return accents


# =============================================================================
# WASHINT PLAYING TECHNIQUES
# =============================================================================

class WashintTechniques:
    """
    Playing techniques specific to the washint bamboo flute.
    
    The washint has unique performance characteristics:
    - Breath-powered sound production
    - Overblowing for octave jumps
    - Vibrato from diaphragm control (not finger vibrato)
    - Flutter tonguing for rapid articulation
    - Pitch bending through partial hole coverage
    - Grace notes for ornamental expression
    - Trills using finger alternation
    
    Note Generation:
        Each technique returns a list of NoteEvents that together
        create the desired musical effect.
    """
    
    @staticmethod
    def generate_grace_note(
        main_tick: int,
        main_pitch: int,
        base_velocity: int = 85,
        approach_from_below: bool = True,
        interval: int = 2
    ) -> List[NoteEvent]:
        """
        Generate a grace note (appoggiatura) before the main note.
        
        Grace notes add expressive "sighs" or "lifts" to the melody.
        In washint playing, they're typically quick and light.
        
        Args:
            main_tick: Tick position of main note
            main_pitch: MIDI note of main note
            base_velocity: Base velocity
            approach_from_below: Approach from below (vs above)
            interval: Semitone interval from main note (1-3)
            
        Returns:
            List with grace note NoteEvent
        """
        notes = []
        
        # Grace note duration: very short (1/32 note or less)
        grace_duration = TICKS_PER_16TH // 2
        
        if approach_from_below:
            grace_pitch = main_pitch - interval
        else:
            grace_pitch = main_pitch + interval
        
        grace_tick = main_tick - grace_duration
        
        # Grace note: lighter velocity, very quick
        grace_pitch = WashintRange.clamp_to_range(grace_pitch)
        notes.append(NoteEvent(
            pitch=grace_pitch,
            start_tick=max(0, grace_tick),
            duration_ticks=grace_duration,
            velocity=int(base_velocity * 0.65),
            channel=0
        ))
        
        return notes
    
    @staticmethod
    def generate_trill(
        start_tick: int,
        main_pitch: int,
        duration_ticks: int,
        base_velocity: int = 85,
        trill_interval: int = 2
    ) -> List[NoteEvent]:
        """
        Generate a trill (rapid finger alternation between two notes).
        
        Washint trills are created by rapidly lifting and lowering
        a finger. They add brilliance and excitement to sustained notes.
        
        Args:
            start_tick: Starting tick position
            main_pitch: Primary note pitch
            duration_ticks: Total duration for the trill
            base_velocity: Base velocity
            trill_interval: Semitone interval (1-3)
            
        Returns:
            List of alternating notes forming the trill
        """
        notes = []
        
        # Trill note (upper neighbor)
        upper_pitch = WashintRange.clamp_to_range(main_pitch + trill_interval)
        
        # Each trill alternation duration (very fast)
        trill_note_dur = TICKS_PER_16TH // 2
        num_alternations = max(4, duration_ticks // (trill_note_dur * 2))
        
        # Start with main note
        for i in range(num_alternations):
            tick_offset = i * (trill_note_dur * 2)
            if start_tick + tick_offset >= start_tick + duration_ticks:
                break
            
            # Main pitch
            notes.append(NoteEvent(
                pitch=main_pitch,
                start_tick=start_tick + tick_offset,
                duration_ticks=trill_note_dur,
                velocity=humanize_velocity(base_velocity, variation=0.08),
                channel=0
            ))
            
            # Upper pitch
            notes.append(NoteEvent(
                pitch=upper_pitch,
                start_tick=start_tick + tick_offset + trill_note_dur,
                duration_ticks=trill_note_dur,
                velocity=humanize_velocity(int(base_velocity * 0.9), variation=0.08),
                channel=0
            ))
        
        return notes
    
    @staticmethod
    def generate_flutter_tongue(
        start_tick: int,
        pitch: int,
        duration_ticks: int,
        base_velocity: int = 85
    ) -> List[NoteEvent]:
        """
        Generate flutter tonguing effect (rapid articulation).
        
        Flutter tongue is created by rolling the tongue while blowing,
        producing a tremolo-like rapid articulation. It adds intensity
        and drama to a note.
        
        Args:
            start_tick: Starting tick
            pitch: Note pitch
            duration_ticks: Total duration
            base_velocity: Base velocity
            
        Returns:
            List of rapid notes simulating flutter tongue
        """
        notes = []
        
        # Flutter speed (very rapid)
        flutter_interval = TICKS_PER_16TH // 3
        num_flutters = max(3, duration_ticks // flutter_interval)
        
        for i in range(num_flutters):
            tick = start_tick + (i * flutter_interval)
            if tick >= start_tick + duration_ticks:
                break
            
            # Slight velocity variation for flutter effect
            vel = humanize_velocity(base_velocity, variation=0.15)
            
            notes.append(NoteEvent(
                pitch=pitch,
                start_tick=tick,
                duration_ticks=flutter_interval,
                velocity=vel,
                channel=0
            ))
        
        return notes
    
    @staticmethod
    def generate_vibrato(
        start_tick: int,
        pitch: int,
        duration_ticks: int,
        base_velocity: int = 85,
        vibrato_depth: int = 1,
        delay_ratio: float = 0.2
    ) -> List[NoteEvent]:
        """
        Generate a note with simulated vibrato.
        
        Washint vibrato is produced by diaphragm pulsation, not
        finger movement. It's wider and more expressive than
        Western flute vibrato, starting after the initial attack.
        
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
        
        # Vibrato oscillation period (around 5-6 Hz for washint)
        cycle_ticks = TICKS_PER_BEAT // 2
        num_cycles = max(1, vibrato_duration // cycle_ticks)
        
        for i in range(num_cycles * 2):
            direction = 1 if i % 2 == 0 else -1
            vibrato_pitch = WashintRange.clamp_to_range(pitch + (vibrato_depth * direction))
            
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
    def generate_pitch_bend(
        start_tick: int,
        from_pitch: int,
        to_pitch: int,
        duration_ticks: int,
        base_velocity: int = 85
    ) -> List[NoteEvent]:
        """
        Generate a pitch bend (sliding between notes).
        
        Washint pitch bends are created by partially covering holes,
        allowing for microtonal slides and expressive glissandos.
        
        Args:
            start_tick: Starting tick
            from_pitch: Starting pitch
            to_pitch: Target pitch
            duration_ticks: Duration of bend
            base_velocity: Base velocity
            
        Returns:
            List of notes creating the bend effect
        """
        notes = []
        
        semitone_diff = abs(to_pitch - from_pitch)
        direction = 1 if to_pitch > from_pitch else -1
        
        # More steps for smoother bends
        num_steps = min(semitone_diff * 2 + 1, max(3, duration_ticks // (TICKS_PER_16TH // 2)))
        step_duration = duration_ticks // num_steps
        
        for i in range(num_steps):
            progress = i / max(1, num_steps - 1)
            intermediate_pitch = from_pitch + int(semitone_diff * progress * direction)
            intermediate_pitch = WashintRange.clamp_to_range(intermediate_pitch)
            
            tick = start_tick + (i * step_duration)
            
            # Velocity curve: slight crescendo through bend
            vel_curve = 0.9 + (0.1 * progress)
            vel = humanize_velocity(int(base_velocity * vel_curve), variation=0.05)
            
            notes.append(NoteEvent(
                pitch=intermediate_pitch,
                start_tick=tick,
                duration_ticks=step_duration + 15,  # Slight overlap for smoothness
                velocity=vel,
                channel=0
            ))
        
        return notes
    
    @staticmethod
    def generate_overblow_octave_jump(
        start_tick: int,
        low_pitch: int,
        duration_before_jump: int,
        duration_after_jump: int,
        base_velocity: int = 85
    ) -> List[NoteEvent]:
        """
        Generate an overblow octave jump.
        
        Overblowing is achieved by increasing breath pressure,
        causing the flute to jump to the upper register (roughly
        an octave higher). This is a characteristic washint technique.
        
        Args:
            start_tick: Starting tick
            low_pitch: Lower pitch (before overblow)
            duration_before_jump: Duration of lower note
            duration_after_jump: Duration of upper note
            base_velocity: Base velocity
            
        Returns:
            List of two notes (low then high)
        """
        notes = []
        
        high_pitch = WashintRange.clamp_to_range(low_pitch + 12)
        low_pitch = WashintRange.clamp_to_range(low_pitch)
        
        # Lower note (building breath)
        notes.append(NoteEvent(
            pitch=low_pitch,
            start_tick=start_tick,
            duration_ticks=duration_before_jump,
            velocity=int(base_velocity * 0.85),
            channel=0
        ))
        
        # Upper note (overblow - stronger)
        notes.append(NoteEvent(
            pitch=high_pitch,
            start_tick=start_tick + duration_before_jump,
            duration_ticks=duration_after_jump,
            velocity=int(base_velocity * 1.05),  # Louder from more breath
            channel=0
        ))
        
        return notes
    
    @staticmethod
    def generate_breath_accent(
        tick: int,
        pitch: int,
        duration_ticks: int,
        base_velocity: int = 85
    ) -> NoteEvent:
        """
        Generate a breath-accented note.
        
        Breath accents are stronger attacks created by explosive
        breath at the start of a note. Used on strong beats.
        
        Args:
            tick: Note tick position
            pitch: Note pitch
            duration_ticks: Note duration
            base_velocity: Base velocity
            
        Returns:
            Single accented NoteEvent
        """
        # Accent: louder attack
        accent_velocity = min(127, int(base_velocity * 1.15))
        
        return NoteEvent(
            pitch=WashintRange.clamp_to_range(pitch),
            start_tick=tick,
            duration_ticks=duration_ticks,
            velocity=accent_velocity,
            channel=0
        )


# =============================================================================
# ETHIOPIAN MELODY VOCABULARY FOR WASHINT
# =============================================================================

class EthiopianMelody:
    """
    Ethiopian melodic vocabulary for the washint.
    
    This class contains characteristic melodic patterns, phrases,
    and ornamental figures used in traditional Ethiopian music.
    The washint often serves as the lead melodic instrument,
    doubling or embellishing the singer's melody.
    
    Melodic Characteristics:
        - Scale-based runs (ascending/descending)
        - Characteristic intervals (4ths and 5ths are prominent)
        - Call-and-response patterns
        - Melismatic ornaments
        - Traditional licks and clichés
        
    Each phrase type is designed to work with the qenet modal system
    and can be transposed to any key.
    """
    
    # Call phrases - opening gestures, getting attention
    CALL_PHRASES = [
        # Ascending call with octave reach
        [(0, 0.5, 0.9), (2, 0.5, 0.85), (4, 0.5, 0.9), (7, 0.75, 0.95), (12, 1.0, 1.0)],
        # Emphatic high register call
        [(7, 0.25, 0.95), (9, 0.5, 1.0), (12, 0.75, 1.0), (9, 0.5, 0.9), (7, 1.0, 0.95)],
        # Questioning call (rising interrogative)
        [(0, 0.5, 0.85), (4, 0.5, 0.9), (7, 0.75, 0.95), (9, 0.5, 1.0), (12, 1.0, 1.0)],
        # Gentle call (softer approach)
        [(4, 0.75, 0.85), (7, 0.5, 0.9), (4, 0.5, 0.85), (7, 1.0, 0.95)],
    ]
    
    # Response phrases - answering, completing
    RESPONSE_PHRASES = [
        # Descending response (classic resolution)
        [(12, 0.5, 0.95), (9, 0.5, 0.9), (7, 0.5, 0.85), (4, 0.75, 0.8), (0, 1.5, 0.9)],
        # Echo response (partial)
        [(9, 0.5, 0.9), (7, 0.5, 0.85), (4, 0.75, 0.8), (0, 1.5, 0.9)],
        # Affirming response (cadential)
        [(7, 0.5, 0.9), (4, 0.5, 0.85), (2, 0.5, 0.8), (0, 1.5, 0.95)],
        # Lingering response (sustained ending)
        [(7, 0.75, 0.9), (4, 1.0, 0.85), (0, 2.0, 0.9)],
    ]
    
    # Dance patterns - rhythmic, energetic for eskista
    DANCE_PATTERNS = [
        # Bouncy pattern
        [(0, 0.33, 0.9), (4, 0.33, 0.85), (7, 0.33, 0.95), (9, 0.33, 1.0), 
         (7, 0.33, 0.9), (4, 0.33, 0.85)],
        # Syncopated dance
        [(7, 0.25, 0.95), (4, 0.25, 0.85), (7, 0.5, 1.0), (9, 0.25, 0.95), 
         (7, 0.25, 0.9), (4, 0.5, 0.85)],
        # Rhythmic ostinato
        [(0, 0.5, 0.9), (4, 0.25, 0.85), (7, 0.25, 0.9), (4, 0.5, 0.85), 
         (0, 0.5, 0.9)],
        # Accent pattern (eskista shoulder)
        [(7, 0.25, 1.0), (7, 0.25, 0.85), (9, 0.25, 0.95), (7, 0.25, 0.9)],
    ]
    
    # Melismatic runs - ornamental flourishes
    MELISMATIC_RUNS = [
        # Rapid descending cascade
        [(14, 0.125, 0.95), (12, 0.125, 0.9), (9, 0.125, 0.9), (7, 0.125, 0.85),
         (4, 0.125, 0.85), (2, 0.125, 0.8), (0, 0.5, 0.9)],
        # Ascending flourish
        [(0, 0.125, 0.8), (2, 0.125, 0.85), (4, 0.125, 0.9), (7, 0.125, 0.9),
         (9, 0.125, 0.95), (12, 0.125, 0.95), (14, 0.25, 1.0)],
        # Turn figure (ornamental turn)
        [(7, 0.125, 0.9), (9, 0.125, 0.85), (7, 0.125, 0.9), (4, 0.125, 0.85), 
         (7, 0.5, 0.95)],
        # Cascading thirds
        [(12, 0.125, 0.95), (9, 0.125, 0.9), (7, 0.125, 0.9), (4, 0.125, 0.85),
         (2, 0.125, 0.8), (0, 0.5, 0.9)],
    ]
    
    # Build phrases - ascending tension
    BUILD_PHRASES = [
        # Ascending build with overblow
        [(0, 0.5, 0.8), (2, 0.5, 0.85), (4, 0.5, 0.9), (7, 0.5, 0.95), 
         (9, 0.5, 0.95), (12, 0.5, 1.0), (14, 1.0, 1.0)],
        # Oscillating build
        [(4, 0.25, 0.85), (7, 0.25, 0.9), (4, 0.25, 0.85), (9, 0.25, 0.95),
         (7, 0.25, 0.9), (12, 0.25, 1.0), (9, 0.25, 0.95), (14, 0.5, 1.0)],
        # Stepwise ascent
        [(0, 0.33, 0.85), (2, 0.33, 0.85), (4, 0.33, 0.9), (7, 0.33, 0.9),
         (9, 0.33, 0.95), (12, 0.5, 1.0)],
    ]
    
    # Drop phrases - for impactful moments
    DROP_PHRASES = [
        # Strong low register emphasis
        [(0, 2.0, 1.0)],
        # Octave drop
        [(12, 0.5, 1.0), (0, 2.0, 0.95)],
        # Fifth emphasis
        [(7, 0.5, 1.0), (0, 2.0, 0.95)],
        # Two-note descent
        [(7, 0.75, 1.0), (4, 0.75, 0.95), (0, 1.5, 0.9)],
    ]
    
    # Traditional licks - characteristic Ethiopian patterns
    TRADITIONAL_LICKS = [
        # Tizita signature lick
        [(9, 0.5, 0.9), (7, 0.5, 0.85), (4, 0.75, 0.9), (2, 0.5, 0.85), (0, 1.0, 0.9)],
        # Ambassel meditation
        [(5, 0.75, 0.85), (7, 0.75, 0.9), (8, 0.5, 0.85), (7, 1.0, 0.9), (5, 1.0, 0.85)],
        # Bati brightness
        [(0, 0.33, 0.9), (4, 0.33, 0.9), (6, 0.33, 0.95), (7, 0.5, 1.0), (4, 0.5, 0.9), (0, 1.0, 0.95)],
        # Anchihoye dance
        [(0, 0.25, 0.9), (3, 0.25, 0.85), (5, 0.25, 0.9), (7, 0.25, 0.95), 
         (5, 0.25, 0.9), (3, 0.25, 0.85), (0, 0.5, 0.9)],
    ]
    
    @classmethod
    def get_phrase(
        cls,
        phrase_type: str,
        root_midi: int,
        scale_notes: List[int]
    ) -> List[Tuple[int, int, int]]:
        """
        Get a phrase pattern with actual MIDI notes.
        
        Args:
            phrase_type: Type of phrase
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
            'lick': cls.TRADITIONAL_LICKS,
        }
        
        collection = phrase_collections.get(phrase_type, cls.CALL_PHRASES)
        pattern = random.choice(collection)
        
        result = []
        for degree, dur_mult, vel_mult in pattern:
            target_pitch = root_midi + degree
            
            # Snap to nearest scale note if available
            if scale_notes:
                nearest = min(scale_notes, key=lambda n: abs(n - target_pitch))
                if abs(nearest - target_pitch) <= 2:
                    target_pitch = nearest
            
            # Clamp to washint range
            target_pitch = WashintRange.clamp_to_range(target_pitch)
            
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
                pitch=pitch,
                start_tick=current_tick,
                duration_ticks=duration,
                velocity=min(127, adjusted_vel),
                channel=0
            ))
            
            current_tick += duration
        
        return notes
    
    @classmethod
    def generate_scale_run(
        cls,
        start_tick: int,
        scale_notes: List[int],
        ascending: bool = True,
        start_pitch: Optional[int] = None,
        num_notes: int = 5,
        base_velocity: int = 85
    ) -> List[NoteEvent]:
        """
        Generate a scale-based run.
        
        Scale runs are fundamental to Ethiopian melody - both
        ascending (building energy) and descending (releasing tension).
        
        Args:
            start_tick: Starting tick
            scale_notes: Available scale notes
            ascending: Direction of run
            start_pitch: Starting pitch (None = auto-select)
            num_notes: Number of notes in run
            base_velocity: Base velocity
            
        Returns:
            List of NoteEvents for the run
        """
        notes = []
        
        if not scale_notes:
            return notes
        
        # Filter to washint range
        playable = [n for n in scale_notes if WashintRange.is_in_range(n)]
        if not playable:
            return notes
        
        # Determine starting position
        if start_pitch is None:
            if ascending:
                start_pitch = random.choice(playable[:len(playable)//2])
            else:
                start_pitch = random.choice(playable[len(playable)//2:])
        
        # Find starting index
        playable_sorted = sorted(playable)
        if ascending:
            candidates = [n for n in playable_sorted if n >= start_pitch]
            if not candidates:
                candidates = playable_sorted
        else:
            candidates = [n for n in reversed(playable_sorted) if n <= start_pitch]
            if not candidates:
                candidates = list(reversed(playable_sorted))
        
        # Generate run
        note_duration = TICKS_PER_16TH
        current_tick = start_tick
        
        for i, pitch in enumerate(candidates[:num_notes]):
            # Velocity curve through run
            if ascending:
                vel_mult = 0.85 + (0.15 * (i / num_notes))
            else:
                vel_mult = 1.0 - (0.2 * (i / num_notes))
            
            vel = humanize_velocity(int(base_velocity * vel_mult), variation=0.08)
            
            notes.append(NoteEvent(
                pitch=pitch,
                start_tick=current_tick,
                duration_ticks=note_duration,
                velocity=vel,
                channel=0
            ))
            
            current_tick += note_duration
        
        return notes


# =============================================================================
# WASHINT AGENT
# =============================================================================

class WashintAgent(IPerformerAgent):
    """
    Masterclass Ethiopian washint (bamboo flute) performer agent.
    
    A professional-level washint player that understands:
    - Ethiopian qenet (modal) system for scale selection
    - Breath techniques: long phrases, accents, crescendos
    - Ornaments: grace notes, trills, flutter tongue, pitch bends
    - Overblowing for octave register changes
    - Ethiopian melodic vocabulary for calls, responses, runs
    - Genre context (traditional, ethio-jazz, eskista)
    
    The agent generates musically-informed washint melodies that
    serve as the lead voice in Ethiopian ensembles while respecting
    the unique breath-driven character of this instrument.
    
    Attributes:
        _name: Human-readable agent name
        _qenet_theory: Reference to qenet theory knowledge
        _techniques: Reference to washint techniques
        _melody_vocab: Reference to Ethiopian melody patterns
        _breath_system: Reference to breath phrasing system
        _decisions: Log of creative decisions
        
    Example:
        ```python
        washint = WashintAgent()
        washint.set_personality(WASHINT_PRESETS['traditional_shepherd'])
        
        result = washint.perform(context, section)
        # result.notes contains the washint MIDI events
        # result.decisions_made contains reasoning log
        ```
    """
    
    # MIDI channel for washint (wind instruments)
    MIDI_CHANNEL = 0
    
    def __init__(self, name: str = "Ethiopian Washint Player"):
        """
        Initialize the washint agent.
        
        Args:
            name: Human-readable name for this agent instance
        """
        super().__init__()
        self._name = name
        self._qenet_theory = QenetTheory
        self._techniques = WashintTechniques
        self._melody_vocab = EthiopianMelody
        self._breath_system = BreathPhrasing
        self._range = WashintRange
        self._decisions: List[str] = []
    
    @property
    def role(self) -> AgentRole:
        """This agent fulfills the LEAD role (melodic lead instrument)."""
        return AgentRole.LEAD
    
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
        Generate washint notes for the given section.
        
        This is the main entry point for washint generation. The agent:
        1. Analyzes context (key, tension, energy) to select qenet mode
        2. Determines appropriate phrase lengths based on breath capacity
        3. Generates breath-aware melodic phrases
        4. Adds ornaments (grace notes, trills, bends) based on personality
        5. Applies breath dynamics (crescendos, accents)
        6. Handles overblow register transitions
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
        
        # Extend scale to washint range
        extended_scale = self._extend_scale_to_range(scale_notes)
        self._log_decision(f"Scale notes: {len(extended_scale)} notes in washint range")
        
        # Determine time signature
        time_sig = getattr(context, 'time_signature', (4, 4))
        if hasattr(context, 'reference_features') and context.reference_features:
            ref_time_sig = context.reference_features.get('time_signature')
            if ref_time_sig:
                time_sig = ref_time_sig
        
        ticks_per_bar = get_ticks_per_bar(time_sig)
        self._log_decision(f"Time signature: {time_sig[0]}/{time_sig[1]}")
        
        # Generate breath-aware melodic line
        base_notes = self._generate_breath_aware_melody(
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
        ornament_density = scaled_personality.ghost_note_density
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
        
        # Add fills if appropriate
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
        
        Supported cues for washint:
        - "fill": Melismatic run
        - "call": Opening phrase (lead melody statement)
        - "response": Answering phrase (to masenqo or voice)
        - "build": Ascending run with overblow to high register
        - "drop": Descending cascade to low register
        
        Args:
            cue_type: The type of cue to react to
            context: Current performance context
            
        Returns:
            List of NoteEvent for the cue response
        """
        cue_type = cue_type.lower().strip()
        
        # Get current state
        current_tick = int(context.section_position_beats * TICKS_PER_BEAT)
        personality = self._personality or WASHINT_PRESETS['traditional_shepherd']
        
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
            return self._melody_vocab.generate_phrase_notes(
                current_tick, 'melismatic', root_midi, extended_scale, base_velocity
            )
        
        elif cue_type == 'call':
            # Opening call phrase (lead statement)
            notes = self._melody_vocab.generate_phrase_notes(
                current_tick, 'call', root_midi, extended_scale, base_velocity
            )
            # Apply breath crescendo
            if notes:
                phrase_length = notes[-1].start_tick + notes[-1].duration_ticks - current_tick
                self._breath_system.apply_breath_dynamics(
                    notes, current_tick, phrase_length, crescendo=True
                )
            return notes
        
        elif cue_type == 'response':
            # Answering phrase
            return self._melody_vocab.generate_phrase_notes(
                current_tick, 'response', root_midi, extended_scale, base_velocity
            )
        
        elif cue_type == 'build':
            # Ascending build with potential overblow
            notes = self._melody_vocab.generate_phrase_notes(
                current_tick, 'build', root_midi, extended_scale, base_velocity
            )
            # Add overblow octave jump at the end
            if notes and personality.complexity > 0.5:
                last_note = notes[-1]
                overblow_notes = self._techniques.generate_overblow_octave_jump(
                    last_note.start_tick + last_note.duration_ticks,
                    last_note.pitch - 12,  # Jump from octave below
                    TICKS_PER_8TH,
                    TICKS_PER_BEAT
                )
                notes.extend(overblow_notes)
            return notes
        
        elif cue_type == 'drop':
            # Descending cascade
            notes = self._melody_vocab.generate_scale_run(
                current_tick,
                extended_scale,
                ascending=False,
                start_pitch=self._range.COMFORTABLE_HIGH,
                num_notes=7,
                base_velocity=base_velocity + 5
            )
            # Add final low note with vibrato
            if notes:
                final_tick = notes[-1].start_tick + notes[-1].duration_ticks
                low_note_pitch = self._range.clamp_to_range(root_midi)
                vibrato_notes = self._techniques.generate_vibrato(
                    final_tick,
                    low_note_pitch,
                    TICKS_PER_BEAT * 2,
                    base_velocity,
                    vibrato_depth=1
                )
                notes.extend(vibrato_notes)
            return notes
        
        else:
            logger.warning(f"Unknown cue type for washint: {cue_type}")
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
            return WASHINT_PRESETS['ethio_jazz_virtuoso']
        elif 'eskista' in genre_lower or 'dance' in genre_lower:
            return WASHINT_PRESETS['eskista_dancer']
        elif 'spiritual' in genre_lower or 'church' in genre_lower:
            return WASHINT_PRESETS['spiritual_meditator']
        elif 'traditional' in genre_lower or 'pastoral' in genre_lower:
            return WASHINT_PRESETS['traditional_shepherd']
        else:
            return WASHINT_PRESETS['traditional_shepherd']
    
    def _get_root_note(self, key: str) -> int:
        """Convert key to MIDI root note in washint range."""
        try:
            root_base = note_name_to_midi(key.replace('m', '').replace('M', ''), 4)
            # Adjust to washint comfortable range
            while root_base < self._range.COMFORTABLE_LOW:
                root_base += 12
            while root_base > self._range.COMFORTABLE_LOW + 12:
                root_base -= 12
            return self._range.clamp_to_range(root_base)
        except Exception:
            return 67  # Default to G4
    
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
        """Extend scale notes to cover full washint range."""
        extended = set()
        
        for note in scale_notes:
            # Add note and octave transpositions within washint range
            for octave_offset in range(-2, 3):
                transposed = note + (octave_offset * 12)
                if self._range.is_in_range(transposed):
                    extended.add(transposed)
        
        return sorted(extended)
    
    def _generate_breath_aware_melody(
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
        Generate melodic line with breath phrasing awareness.
        
        Generates phrases with natural breath points, applying
        breath dynamics (crescendos) and respecting breath capacity.
        """
        notes = []
        
        # Base velocity from personality
        base_velocity = int(90 * (0.75 + 0.25 * personality.aggressiveness))
        
        # Determine phrase density based on section type
        if section.section_type in [SectionType.INTRO, SectionType.OUTRO]:
            phrase_density = 0.5 * personality.complexity
        elif section.section_type in [SectionType.DROP, SectionType.CHORUS]:
            phrase_density = 0.85 + (0.15 * personality.complexity)
        elif section.section_type == SectionType.VERSE:
            phrase_density = 0.6 + (0.25 * personality.complexity)
        elif section.section_type == SectionType.BUILDUP:
            phrase_density = 0.7 + (0.2 * personality.complexity)
        else:
            phrase_density = 0.6
        
        # Generate phrases with breath phrasing
        current_tick = section.start_tick
        phrase_cooldown = 0
        
        while current_tick < section.end_tick:
            remaining_ticks = section.end_tick - current_tick
            
            if phrase_cooldown <= 0 and random.random() < phrase_density:
                # Calculate breath-appropriate phrase length
                phrase_length_beats = self._breath_system.get_phrase_length(
                    context.energy_level,
                    personality.complexity
                )
                phrase_length_ticks = int(phrase_length_beats * TICKS_PER_BEAT)
                
                # Don't exceed remaining time
                phrase_length_ticks = min(phrase_length_ticks, remaining_ticks - TICKS_PER_8TH)
                
                if phrase_length_ticks > TICKS_PER_8TH:
                    # Select phrase type based on section
                    phrase_type = self._select_phrase_type(section.section_type, personality)
                    
                    # Generate phrase
                    phrase_notes = self._melody_vocab.generate_phrase_notes(
                        current_tick,
                        phrase_type,
                        root_midi,
                        scale_notes,
                        base_velocity
                    )
                    
                    if phrase_notes:
                        # Check if phrase fits
                        phrase_end = phrase_notes[-1].start_tick + phrase_notes[-1].duration_ticks
                        
                        if phrase_end <= section.end_tick:
                            # Apply breath dynamics (crescendo for most phrases)
                            apply_crescendo = phrase_type in ['call', 'build', 'dance']
                            self._breath_system.apply_breath_dynamics(
                                phrase_notes,
                                current_tick,
                                phrase_end - current_tick,
                                crescendo=apply_crescendo
                            )
                            
                            notes.extend(phrase_notes)
                            
                            # Calculate breath rest
                            rest_beats = self._breath_system.get_breath_rest_duration(
                                phrase_length_beats,
                                context.energy_level
                            )
                            rest_ticks = int(rest_beats * TICKS_PER_BEAT)
                            
                            current_tick = phrase_end + rest_ticks
                            phrase_cooldown = int(ticks_per_bar * (0.3 + 0.4 * (1 - personality.variation_tendency)))
                        else:
                            # Generate a simple sustained note instead
                            notes.extend(self._generate_sustained_note(
                                current_tick, root_midi, remaining_ticks // 2, base_velocity
                            ))
                            current_tick += remaining_ticks // 2
                else:
                    # Very short remaining time - rest or single note
                    if random.random() < 0.5 and remaining_ticks > TICKS_PER_8TH:
                        notes.extend(self._generate_sustained_note(
                            current_tick, scale_notes[0] if scale_notes else root_midi,
                            remaining_ticks, base_velocity - 10
                        ))
                    current_tick = section.end_tick
            else:
                # Rest or sustained note for breath recovery
                if random.random() < 0.25:
                    # Sustained note with vibrato
                    sustain_duration = min(ticks_per_bar, remaining_ticks)
                    sustain_pitch = random.choice(scale_notes) if scale_notes else root_midi
                    sustain_pitch = self._range.clamp_to_range(sustain_pitch)
                    
                    vibrato_notes = self._techniques.generate_vibrato(
                        current_tick,
                        sustain_pitch,
                        sustain_duration,
                        base_velocity - 10,
                        vibrato_depth=1 if personality.complexity > 0.5 else 0
                    )
                    notes.extend(vibrato_notes)
                    current_tick += sustain_duration
                else:
                    # Breath rest
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
            return random.choice(['call', 'lick'])
        elif section_type == SectionType.OUTRO:
            return random.choice(['response', 'drop'])
        elif section_type in [SectionType.CHORUS, SectionType.DROP]:
            if personality.aggressiveness > 0.6:
                return random.choice(['dance', 'call', 'build'])
            return random.choice(['call', 'dance'])
        elif section_type == SectionType.VERSE:
            return random.choice(['call', 'response', 'lick'])
        elif section_type == SectionType.BUILDUP:
            return 'build'
        elif section_type == SectionType.BREAKDOWN:
            return random.choice(['response', 'melismatic'])
        elif section_type == SectionType.PRE_CHORUS:
            return random.choice(['build', 'call'])
        else:
            return random.choice(['call', 'response'])
    
    def _generate_sustained_note(
        self,
        tick: int,
        pitch: int,
        duration: int,
        velocity: int
    ) -> List[NoteEvent]:
        """Generate a sustained note, optionally with vibrato."""
        pitch = self._range.clamp_to_range(pitch)
        
        # Add vibrato to longer sustained notes
        if duration > TICKS_PER_BEAT:
            return self._techniques.generate_vibrato(
                tick, pitch, duration, velocity, vibrato_depth=1
            )
        else:
            return [NoteEvent(
                pitch=pitch,
                start_tick=tick,
                duration_ticks=duration,
                velocity=humanize_velocity(velocity, variation=0.1),
                channel=self.MIDI_CHANNEL
            )]
    
    def _add_ornaments(
        self,
        notes: List[NoteEvent],
        density: float,
        scale_notes: List[int],
        personality: AgentPersonality
    ) -> List[NoteEvent]:
        """
        Add ornamental notes based on personality.
        
        Ornaments include grace notes, trills, flutter tongue,
        and pitch bends - all characteristic washint techniques.
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
            
            if ornament_roll < 0.35:
                # Grace note
                grace_notes = self._techniques.generate_grace_note(
                    note.start_tick,
                    note.pitch,
                    note.velocity,
                    approach_from_below=random.random() < 0.65,
                    interval=random.choice([1, 2])
                )
                ornament_notes.extend(grace_notes)
            
            elif ornament_roll < 0.55 and note.duration_ticks >= TICKS_PER_BEAT:
                # Trill on longer notes
                trill_duration = min(note.duration_ticks // 2, TICKS_PER_BEAT)
                trill_notes = self._techniques.generate_trill(
                    note.start_tick,
                    note.pitch,
                    trill_duration,
                    note.velocity,
                    trill_interval=random.choice([1, 2])
                )
                ornament_notes.extend(trill_notes)
            
            elif ornament_roll < 0.7 and personality.complexity > 0.6:
                # Flutter tongue for high complexity
                flutter_duration = min(note.duration_ticks // 3, TICKS_PER_8TH * 2)
                flutter_notes = self._techniques.generate_flutter_tongue(
                    note.start_tick,
                    note.pitch,
                    flutter_duration,
                    note.velocity
                )
                ornament_notes.extend(flutter_notes)
            
            elif ornament_roll < 0.85 and personality.complexity > 0.5:
                # Pitch bend to next note
                note_idx = notes.index(note)
                if note_idx < len(notes) - 1:
                    next_note = notes[note_idx + 1]
                    pitch_diff = abs(next_note.pitch - note.pitch)
                    
                    if 2 <= pitch_diff <= 5:
                        # Good candidate for pitch bend
                        bend_start = note.start_tick + (note.duration_ticks * 2 // 3)
                        bend_duration = note.duration_ticks // 3
                        
                        bend_notes = self._techniques.generate_pitch_bend(
                            bend_start,
                            note.pitch,
                            next_note.pitch,
                            bend_duration,
                            note.velocity
                        )
                        ornament_notes.extend(bend_notes)
        
        return ornament_notes
    
    def _should_add_fill(
        self,
        section: SongSection,
        personality: AgentPersonality
    ) -> bool:
        """Decide if a fill should be added."""
        # Always add fill at buildup sections
        if section.section_type in [SectionType.BUILDUP, SectionType.PRE_CHORUS]:
            return True
        
        # Personality-based chance
        fill_chance = personality.fill_frequency * 0.5
        
        if section.section_type in [SectionType.CHORUS, SectionType.DROP]:
            fill_chance += 0.15
        
        return random.random() < fill_chance
    
    def _generate_section_fill(
        self,
        section: SongSection,
        context: PerformanceContext,
        personality: AgentPersonality,
        root_midi: int,
        scale_notes: List[int]
    ) -> Tuple[List[NoteEvent], int]:
        """Generate a fill for the end of section."""
        fill_duration = 1.0 if personality.complexity < 0.5 else 2.0
        fill_start = section.end_tick - int(fill_duration * TICKS_PER_BEAT)
        
        base_velocity = int(90 * (0.8 + 0.4 * personality.aggressiveness))
        
        # Select fill type based on complexity
        if personality.complexity > 0.7:
            # Complex: melismatic run or ascending scale
            if random.random() < 0.6:
                notes = self._melody_vocab.generate_phrase_notes(
                    fill_start, 'melismatic', root_midi, scale_notes, base_velocity
                )
            else:
                notes = self._melody_vocab.generate_scale_run(
                    fill_start, scale_notes, ascending=True,
                    start_pitch=self._range.COMFORTABLE_LOW,
                    num_notes=6, base_velocity=base_velocity
                )
        elif personality.complexity > 0.4:
            # Medium: build phrase or traditional lick
            notes = self._melody_vocab.generate_phrase_notes(
                fill_start,
                random.choice(['build', 'lick']),
                root_midi, scale_notes, base_velocity
            )
        else:
            # Simple: ascending run
            notes = self._melody_vocab.generate_scale_run(
                fill_start, scale_notes, ascending=True,
                num_notes=4, base_velocity=base_velocity
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
