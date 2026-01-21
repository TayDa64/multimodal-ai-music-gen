"""
BassistAgent - Masterclass Bass Performer

This module implements a professional bassist agent with deep knowledge of:
- 808 Sub-bass: Pitch slides/glides, long sustain, sub frequencies (C1-C2)
- Synth bass: Reese bass (detuned oscillators), FM bass, wobble patterns
- Acoustic/fingered bass: Walking bass lines, chromatic approaches, ghost notes
- Kick-lock technique: Bass notes on kick hits for pocket groove
- Root-fifth patterns: Following chord roots, occasional fifths, passing tones
- Genre-specific styles: Trap 808s, G-funk rolling bass, boom bap stabs, house pumping bass

The BassistAgent wraps existing bass pattern generators while adding:
- Personality-driven timing adjustments (push_pull)
- Kick-drum synchronization for pocket groove
- Harmonic awareness from chord progressions
- Decision logging for transparency and debugging

Architecture Notes:
    This is a Stage 1 (offline) implementation that combines existing
    pattern generators with advanced musical intelligence.
    Stage 2 will add API-backed generation capabilities.

Musical Reference:
    Bass Octave Ranges:
    - Sub-bass: C0-C2 (20-65Hz) - 808s, synth subs
    - Bass: C2-C3 (65-130Hz) - Bass guitar low range
    - Low-mid: C3-C4 (130-260Hz) - Upper bass, transitions to midrange

Example:
    ```python
    from multimodal_gen.agents.performers import BassistAgent
    from multimodal_gen.agents import PerformanceContext, BASSIST_PRESETS
    
    bassist = BassistAgent()
    bassist.set_personality(BASSIST_PRESETS['808_specialist'])
    
    result = bassist.perform(context, section)
    print(f"Generated {len(result.notes)} bass notes")
    print(f"Decisions: {result.decisions_made}")
    ```
"""

from typing import List, Optional, Dict, Any, Tuple
import random
import logging

from ..base import IPerformerAgent, AgentRole, PerformanceResult
from ..context import PerformanceContext
from ..personality import AgentPersonality, BASSIST_PRESETS, get_personality_for_role

# Import existing infrastructure
from ...arranger import SongSection, SectionType
from ...midi_generator import NoteEvent
from ...utils import (
    TICKS_PER_BEAT,
    TICKS_PER_8TH,
    TICKS_PER_16TH,
    TICKS_PER_BAR_4_4,
    ScaleType,
    humanize_velocity,
    humanize_timing,
    beats_to_ticks,
    get_scale_notes,
    note_name_to_midi,
    midi_to_note_name,
)

logger = logging.getLogger(__name__)


# =============================================================================
# BASS THEORY KNOWLEDGE BASE
# =============================================================================

class BassTheory:
    """
    Masterclass bass theory knowledge.
    
    Documents musical theory fundamentals for bass performance:
    - Common intervals and their function
    - Slide/glide techniques for 808
    - Walking bass note choices
    - Genre-specific rhythm patterns
    """
    
    # Octave ranges (MIDI note numbers)
    SUB_BASS_RANGE = (24, 36)    # C1-C2: Sub frequencies, 808 territory
    BASS_RANGE = (36, 48)        # C2-C3: Standard bass range
    LOW_MID_RANGE = (48, 60)     # C3-C4: Upper bass for fills/runs
    
    # Common bass intervals (semitones from root)
    INTERVALS = {
        'root': 0,           # Foundation, always safe
        'minor_2nd': 1,      # Chromatic approach, tension
        'major_2nd': 2,      # Whole step, passing tone
        'minor_3rd': 3,      # Minor color
        'major_3rd': 4,      # Major color
        'perfect_4th': 5,    # Strong, suspended feel
        'tritone': 6,        # Maximum tension (dominant)
        'perfect_5th': 7,    # Power, stability after root
        'minor_6th': 8,      # Darker color
        'major_6th': 9,      # Walking bass favorite
        'minor_7th': 10,     # Dominant/minor feel
        'major_7th': 11,     # Jazz voicing, approach to octave
        'octave': 12,        # Power, punch, G-funk staple
    }
    
    # Preferred intervals for different contexts
    STRONG_BEATS = ['root', 'perfect_5th', 'octave']
    PASSING_TONES = ['major_2nd', 'minor_3rd', 'major_3rd', 'major_6th', 'minor_7th']
    APPROACH_NOTES = ['minor_2nd', 'major_7th']  # Chromatic approaches
    
    # 808 Slide Techniques
    SLIDE_TYPES = {
        'glide_up': {'direction': 1, 'semitones': range(1, 5), 'duration_ratio': 0.25},
        'glide_down': {'direction': -1, 'semitones': range(1, 5), 'duration_ratio': 0.25},
        'portamento': {'direction': 0, 'semitones': range(1, 3), 'duration_ratio': 0.15},
        'dive_bomb': {'direction': -1, 'semitones': range(7, 13), 'duration_ratio': 0.5},
        'scoop': {'direction': 1, 'semitones': range(2, 4), 'duration_ratio': 0.1},
    }
    
    # Genre-specific rhythm patterns (beat positions in a bar)
    RHYTHM_PATTERNS = {
        'trap': {
            'description': 'Sparse 808s with long sustain and slides',
            'typical_positions': [0, 2.5, 3.5],  # Downbeat anchor + syncopation
            'sustain': 'long',
            'slide_frequency': 0.3,
        },
        'boom_bap': {
            'description': 'Sampled bass stabs with swing',
            'typical_positions': [0, 1.5, 2, 3.5],
            'sustain': 'short',
            'slide_frequency': 0.0,
        },
        'house': {
            'description': 'Pumping octave bass with sidechain feel',
            'typical_positions': [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5],  # 8th notes
            'sustain': 'short',
            'slide_frequency': 0.1,
        },
        'g_funk': {
            'description': 'Rolling Moog-style synth bass with octave jumps',
            'typical_positions': [0, 1.5, 2, 2.5, 3, 3.5],
            'sustain': 'medium',
            'slide_frequency': 0.15,
        },
        'lofi': {
            'description': 'Dusty, muted bass with relaxed timing',
            'typical_positions': [0, 2.5],
            'sustain': 'medium',
            'slide_frequency': 0.05,
        },
        'ethiopian': {
            'description': 'Pentatonic bass with drone elements',
            'typical_positions': [0, 3],  # Emphasize pulse in compound meter
            'sustain': 'long',
            'slide_frequency': 0.0,
        },
        'rnb': {
            'description': 'Smooth pocket bass locked to kick',
            'typical_positions': [0, 2.5, 3.5],
            'sustain': 'medium',
            'slide_frequency': 0.05,
        },
    }
    
    # Walking bass note selection weights
    WALKING_WEIGHTS = {
        'root': 0.35,
        'perfect_5th': 0.25,
        'major_3rd': 0.15,
        'minor_3rd': 0.15,
        'octave': 0.10,
    }
    
    @classmethod
    def get_interval_semitones(cls, interval_name: str) -> int:
        """Get semitones for an interval name."""
        return cls.INTERVALS.get(interval_name, 0)
    
    @classmethod
    def get_genre_pattern(cls, genre: str) -> Dict[str, Any]:
        """Get rhythm pattern info for a genre, with default fallback."""
        genre_key = genre.lower().strip()
        
        # Handle aliases
        aliases = {
            'trap_soul': 'trap',
            'drill': 'trap',
            'lo_fi': 'lofi',
            'lo-fi': 'lofi',
            'r&b': 'rnb',
            'ethio_jazz': 'ethiopian',
            'eskista': 'ethiopian',
            'ethiopian_traditional': 'ethiopian',
        }
        genre_key = aliases.get(genre_key, genre_key)
        
        return cls.RHYTHM_PATTERNS.get(genre_key, cls.RHYTHM_PATTERNS.get('trap', {}))
    
    @classmethod
    def select_passing_tone(cls, root: int, scale_notes: List[int], direction: int = 1) -> int:
        """
        Select an appropriate passing tone for walking bass.
        
        Args:
            root: Current root note MIDI number
            scale_notes: Available scale notes
            direction: 1 for ascending, -1 for descending
            
        Returns:
            MIDI note number for the passing tone
        """
        candidates = []
        for interval in cls.PASSING_TONES:
            semitones = cls.INTERVALS[interval]
            candidate = root + (semitones * direction)
            if candidate in scale_notes or abs(candidate - root) <= 4:
                candidates.append(candidate)
        
        if candidates:
            return random.choice(candidates)
        return root + (2 * direction)  # Default to whole step
    
    @classmethod
    def get_approach_note(cls, target: int, from_below: bool = True) -> int:
        """
        Get a chromatic approach note to the target.
        
        Args:
            target: Target note MIDI number
            from_below: Approach from below (True) or above (False)
            
        Returns:
            MIDI note number for the approach note
        """
        return target - 1 if from_below else target + 1


# =============================================================================
# 808 SLIDE GENERATOR
# =============================================================================

class SlideGenerator:
    """
    Generates 808-style pitch slides and glides.
    
    808 slides are achieved by:
    1. Short grace notes before the target pitch
    2. Pitch bend messages (for true portamento, handled at rendering)
    3. Quick chromatic runs
    
    For MIDI output, we simulate slides with rapid note sequences.
    """
    
    @staticmethod
    def generate_slide_up(
        target_tick: int,
        target_pitch: int,
        semitones: int = 3,
        base_velocity: int = 90,
        duration_ticks: int = TICKS_PER_8TH
    ) -> List[NoteEvent]:
        """
        Generate an upward slide into the target note.
        
        Args:
            target_tick: The tick where the target note lands
            target_pitch: Target note MIDI number
            semitones: How many semitones to slide up
            base_velocity: Velocity for target note
            duration_ticks: Duration of the target note
            
        Returns:
            List of NoteEvents (grace notes + target)
        """
        notes = []
        
        # Grace notes (quick ascending)
        grace_duration = TICKS_PER_16TH // 2
        slide_duration = grace_duration * semitones
        
        for i in range(semitones):
            grace_tick = target_tick - slide_duration + (i * grace_duration)
            grace_pitch = target_pitch - semitones + i
            grace_vel = int(base_velocity * 0.6 + (i * (base_velocity * 0.1)))
            
            notes.append(NoteEvent(
                pitch=max(0, grace_pitch),
                start_tick=max(0, grace_tick),
                duration_ticks=grace_duration,
                velocity=min(127, grace_vel),
                channel=1
            ))
        
        # Target note
        notes.append(NoteEvent(
            pitch=target_pitch,
            start_tick=target_tick,
            duration_ticks=duration_ticks,
            velocity=base_velocity,
            channel=1
        ))
        
        return notes
    
    @staticmethod
    def generate_slide_down(
        start_tick: int,
        start_pitch: int,
        semitones: int = 5,
        base_velocity: int = 90,
        total_duration: int = TICKS_PER_BEAT
    ) -> List[NoteEvent]:
        """
        Generate a downward slide (dive bomb) from the start note.
        
        Args:
            start_tick: The tick where the slide starts
            start_pitch: Starting note MIDI number
            semitones: How many semitones to slide down
            base_velocity: Starting velocity
            total_duration: Total duration for the slide
            
        Returns:
            List of NoteEvents representing the slide
        """
        notes = []
        
        # Divide total duration among slide notes
        notes_count = min(semitones + 1, 8)  # Cap at 8 notes
        note_duration = total_duration // notes_count
        
        for i in range(notes_count):
            tick = start_tick + (i * note_duration)
            pitch = start_pitch - int((semitones * i) / (notes_count - 1)) if notes_count > 1 else start_pitch
            vel = int(base_velocity * (1.0 - (0.3 * i / notes_count)))
            
            notes.append(NoteEvent(
                pitch=max(0, pitch),
                start_tick=tick,
                duration_ticks=note_duration,
                velocity=max(40, vel),
                channel=1
            ))
        
        return notes
    
    @staticmethod
    def generate_portamento(
        from_pitch: int,
        to_pitch: int,
        start_tick: int,
        transition_ticks: int = TICKS_PER_16TH * 2,
        target_duration: int = TICKS_PER_BEAT,
        base_velocity: int = 90
    ) -> List[NoteEvent]:
        """
        Generate a portamento (smooth glide) between two notes.
        
        Args:
            from_pitch: Starting pitch
            to_pitch: Ending pitch
            start_tick: When the portamento starts
            transition_ticks: Duration of the glide
            target_duration: Duration of the final note
            base_velocity: Velocity
            
        Returns:
            List of NoteEvents
        """
        notes = []
        
        # Quick transition note(s)
        semitone_diff = to_pitch - from_pitch
        direction = 1 if semitone_diff > 0 else -1
        steps = min(abs(semitone_diff), 4)
        step_duration = transition_ticks // max(steps, 1)
        
        for i in range(steps):
            tick = start_tick + (i * step_duration)
            pitch = from_pitch + (direction * i * (abs(semitone_diff) // steps))
            vel = int(base_velocity * 0.7)
            
            notes.append(NoteEvent(
                pitch=max(0, pitch),
                start_tick=tick,
                duration_ticks=step_duration,
                velocity=vel,
                channel=1
            ))
        
        # Final target note
        notes.append(NoteEvent(
            pitch=to_pitch,
            start_tick=start_tick + transition_ticks,
            duration_ticks=target_duration,
            velocity=base_velocity,
            channel=1
        ))
        
        return notes


# =============================================================================
# BASS RUN GENERATOR
# =============================================================================

class BassRunGenerator:
    """
    Generates bass runs and fills for transitions and cue responses.
    
    Run Types:
    - Ascending scalar: Climb up the scale to next chord root
    - Descending chromatic: Walk down chromatically for tension
    - Octave jump: Quick octave for energy
    - Approach pattern: Chromatic approach to target
    """
    
    @staticmethod
    def generate_ascending_run(
        start_tick: int,
        start_pitch: int,
        target_pitch: int,
        scale_notes: List[int],
        duration_beats: float = 1.0,
        base_velocity: int = 85
    ) -> List[NoteEvent]:
        """
        Generate an ascending bass run to the target pitch.
        
        Args:
            start_tick: Starting tick position
            start_pitch: Starting note MIDI number
            target_pitch: Target note to reach
            scale_notes: Available scale notes
            duration_beats: Total duration in beats
            base_velocity: Base velocity
            
        Returns:
            List of NoteEvents for the run
        """
        notes = []
        
        # Find scale notes between start and target
        path_notes = [n for n in sorted(scale_notes) if start_pitch <= n <= target_pitch]
        
        if not path_notes:
            # Generate chromatic path if no scale notes available
            path_notes = list(range(start_pitch, target_pitch + 1))
        
        # Limit to 4-8 notes
        if len(path_notes) > 8:
            # Keep every Nth note
            step = len(path_notes) // 6
            path_notes = path_notes[::step] + [target_pitch]
            path_notes = sorted(set(path_notes))
        
        num_notes = len(path_notes)
        total_ticks = int(duration_beats * TICKS_PER_BEAT)
        note_duration = total_ticks // max(num_notes, 1)
        
        for i, pitch in enumerate(path_notes):
            tick = start_tick + (i * note_duration)
            # Slight crescendo
            vel = base_velocity + int(10 * (i / max(1, num_notes - 1)))
            vel = humanize_velocity(min(127, vel), variation=0.08)
            
            notes.append(NoteEvent(
                pitch=pitch,
                start_tick=tick,
                duration_ticks=note_duration,
                velocity=vel,
                channel=1
            ))
        
        return notes
    
    @staticmethod
    def generate_descending_chromatic(
        start_tick: int,
        start_pitch: int,
        semitones: int = 5,
        duration_beats: float = 1.0,
        base_velocity: int = 85
    ) -> List[NoteEvent]:
        """
        Generate a descending chromatic bass run.
        
        Args:
            start_tick: Starting tick position
            start_pitch: Starting note MIDI number
            semitones: Number of semitones to descend
            duration_beats: Total duration in beats
            base_velocity: Base velocity
            
        Returns:
            List of NoteEvents for the chromatic descent
        """
        notes = []
        
        total_ticks = int(duration_beats * TICKS_PER_BEAT)
        note_duration = total_ticks // (semitones + 1)
        
        for i in range(semitones + 1):
            tick = start_tick + (i * note_duration)
            pitch = start_pitch - i
            vel = humanize_velocity(base_velocity, variation=0.1)
            
            notes.append(NoteEvent(
                pitch=max(24, pitch),  # Don't go below C1
                start_tick=tick,
                duration_ticks=note_duration,
                velocity=vel,
                channel=1
            ))
        
        return notes
    
    @staticmethod
    def generate_octave_climb(
        start_tick: int,
        root_pitch: int,
        duration_beats: float = 2.0,
        base_velocity: int = 90
    ) -> List[NoteEvent]:
        """
        Generate an octave-based climb for build sections.
        
        Pattern: root -> 5th -> octave -> (high 5th)
        
        Args:
            start_tick: Starting tick position
            root_pitch: Root note MIDI number
            duration_beats: Total duration in beats
            base_velocity: Base velocity
            
        Returns:
            List of NoteEvents for the octave climb
        """
        notes = []
        
        # Pattern: root, 5th, octave, high 5th
        pattern = [
            (0, root_pitch, 1.0),
            (0.5, root_pitch + 7, 0.9),  # 5th
            (1.0, root_pitch + 12, 1.1),  # Octave
            (1.5, root_pitch + 19, 0.95),  # High 5th
        ]
        
        total_ticks = int(duration_beats * TICKS_PER_BEAT)
        
        for beat_offset, pitch, vel_mult in pattern:
            tick = start_tick + int(beat_offset * TICKS_PER_BEAT)
            if tick >= start_tick + total_ticks:
                break
                
            vel = humanize_velocity(int(base_velocity * vel_mult), variation=0.08)
            duration = TICKS_PER_8TH
            
            notes.append(NoteEvent(
                pitch=pitch,
                start_tick=tick,
                duration_ticks=duration,
                velocity=min(127, vel),
                channel=1
            ))
        
        return notes


# =============================================================================
# BASSIST AGENT
# =============================================================================

class BassistAgent(IPerformerAgent):
    """
    Masterclass bassist performer agent.
    
    A professional-level bassist that understands:
    - 808 sub-bass techniques (slides, glides, sustain)
    - Synth bass styles (Reese, FM, Moog)
    - Kick-lock technique for pocket groove
    - Root-fifth patterns with passing tones
    - Genre-specific rhythm patterns
    - Harmonic awareness from chord progressions
    
    The agent generates musically-informed bass lines while respecting
    the performance context (tempo, key, tension) and personality settings.
    
    Attributes:
        _name: Human-readable agent name
        _bass_theory: Reference to bass theory knowledge base
        _decisions: Log of creative decisions per perform call
        
    Example:
        ```python
        bassist = BassistAgent()
        bassist.set_personality(BASSIST_PRESETS['808_specialist'])
        
        result = bassist.perform(context, section)
        # result.notes contains the bass MIDI events
        # result.decisions_made contains reasoning log
        ```
    """
    
    def __init__(self, name: str = "Master Bassist"):
        """
        Initialize the bassist agent.
        
        Args:
            name: Human-readable name for this agent instance
        """
        super().__init__()
        self._name = name
        self._bass_theory = BassTheory
        self._decisions: List[str] = []
    
    @property
    def role(self) -> AgentRole:
        """This agent fulfills the BASS role."""
        return AgentRole.BASS
    
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
        Generate bass notes for the given section.
        
        This is the main entry point for bass generation. The agent:
        1. Analyzes context (tempo, key, tension, chord progression)
        2. Determines genre-appropriate pattern style
        3. Applies personality adjustments
        4. Generates base pattern with kick-lock when available
        5. Adds slides/glides based on genre and personality
        6. Applies push/pull timing adjustments
        7. Logs all creative decisions
        
        Args:
            context: Shared performance state (tempo, key, tension, etc.)
            section: The song section to generate for
            personality: Optional personality override
            
        Returns:
            PerformanceResult containing generated notes and metadata
        """
        # Reset decision log for this performance
        self._decisions = []
        
        # Resolve personality
        effective_personality = personality or self._personality
        if effective_personality is None:
            genre = self._extract_genre_from_context(context)
            effective_personality = get_personality_for_role(genre, AgentRole.BASS)
            self._log_decision(f"Using default personality for genre '{genre}'")
        else:
            self._log_decision(f"Using provided personality (aggr={effective_personality.aggressiveness:.2f})")
        
        # Scale personality by tension
        scaled_personality = effective_personality.apply_tension_scaling(context.tension)
        self._log_decision(f"Applied tension scaling ({context.tension:.2f}) to personality")
        
        # Get genre and pattern info
        genre = self._extract_genre_from_context(context)
        pattern_info = self._bass_theory.get_genre_pattern(genre)
        self._log_decision(f"Pattern style: {pattern_info.get('description', 'unknown')}")
        
        # Get harmonic information
        root_note = self._get_root_note(context.key, octave=1)
        scale_notes = self._get_extended_scale_notes(context.key, context.scale_notes, octave=1)
        
        # Generate base pattern
        base_notes = self._generate_genre_pattern(
            section,
            context,
            scaled_personality,
            pattern_info,
            root_note,
            scale_notes
        )
        self._log_decision(f"Generated {len(base_notes)} base notes")
        
        patterns_used = [pattern_info.get('description', 'standard').split()[0]]
        
        # Add slides based on genre and personality
        slide_frequency = pattern_info.get('slide_frequency', 0.1)
        if slide_frequency > 0 and scaled_personality.complexity > 0.3:
            slide_notes = self._add_slides(
                base_notes,
                slide_frequency * scaled_personality.complexity,
                scaled_personality.aggressiveness
            )
            self._log_decision(f"Added {len(slide_notes)} slide notes (freq={slide_frequency:.2f})")
            base_notes.extend(slide_notes)
            if slide_notes:
                patterns_used.append('slides')
        
        # Determine fill locations and add fills
        fill_locations = []
        if context.fill_opportunity or self._should_add_fill(section, scaled_personality):
            fill_notes, fill_tick = self._generate_section_fill(
                section,
                context,
                scaled_personality,
                root_note,
                scale_notes
            )
            if fill_notes:
                base_notes.extend(fill_notes)
                fill_locations.append(fill_tick)
                self._log_decision(f"Added fill at tick {fill_tick} ({len(fill_notes)} notes)")
                patterns_used.append('fill')
        
        # Apply push/pull timing adjustments
        if abs(scaled_personality.push_pull) > 0.01:
            base_notes = self._apply_push_pull(base_notes, scaled_personality.push_pull)
            self._log_decision(f"Applied push/pull timing: {scaled_personality.push_pull:+.3f}")
        
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
        
        Supported cues:
        - "fill": Bass run up/down to next chord root
        - "stop": Return empty (silence/break)
        - "build": Ascending chromatic or octave climb
        - "drop": Big sub hit with slide down
        
        Args:
            cue_type: The type of cue to react to
            context: Current performance context
            
        Returns:
            List of NoteEvent for the cue response
        """
        cue_type = cue_type.lower().strip()
        genre = self._extract_genre_from_context(context)
        
        # Get current tick from context
        current_tick = int(context.section_position_beats * TICKS_PER_BEAT)
        
        personality = self._personality or get_personality_for_role(genre, AgentRole.BASS)
        root_note = self._get_root_note(context.key, octave=1)
        scale_notes = self._get_extended_scale_notes(context.key, context.scale_notes, octave=1)
        
        base_velocity = int(95 * (0.8 + 0.4 * personality.aggressiveness))
        
        if cue_type == 'fill':
            # Generate bass run to next chord root
            return self._generate_cue_fill(current_tick, root_note, scale_notes, base_velocity)
        
        elif cue_type == 'stop':
            # Return empty for silence/break
            return []
        
        elif cue_type == 'build':
            # Ascending octave climb
            return BassRunGenerator.generate_octave_climb(
                current_tick, root_note, duration_beats=2.0, base_velocity=base_velocity
            )
        
        elif cue_type == 'drop':
            # Big sub hit with slide down
            return self._generate_drop_cue(current_tick, root_note, base_velocity)
        
        else:
            logger.warning(f"Unknown cue type: {cue_type}")
            return []
    
    # =========================================================================
    # PRIVATE HELPER METHODS
    # =========================================================================
    
    def _log_decision(self, decision: str) -> None:
        """Log a creative decision for transparency."""
        self._decisions.append(decision)
        logger.debug(f"[{self.name}] {decision}")
    
    def _extract_genre_from_context(self, context: PerformanceContext) -> str:
        """Extract genre string from context, with fallback."""
        if context.reference_features and 'genre' in context.reference_features:
            return context.reference_features['genre']
        return 'trap_soul'
    
    def _get_root_note(self, key: str, octave: int = 1) -> int:
        """Convert key to MIDI root note at specified octave."""
        return note_name_to_midi(key, octave)
    
    def _get_extended_scale_notes(
        self,
        key: str,
        scale_notes: List[int],
        octave: int = 1
    ) -> List[int]:
        """Get scale notes extended to bass range."""
        if scale_notes:
            # Transpose provided scale notes to bass octave
            root_offset = note_name_to_midi(key, octave) - note_name_to_midi(key, 4)
            return [n + root_offset for n in scale_notes]
        
        # Generate default minor scale in bass range
        try:
            return get_scale_notes(key, ScaleType.MINOR, octave=octave, num_octaves=2)
        except Exception:
            # Fallback to chromatic
            root = note_name_to_midi(key, octave)
            return [root + i for i in range(13)]
    
    def _generate_genre_pattern(
        self,
        section: SongSection,
        context: PerformanceContext,
        personality: AgentPersonality,
        pattern_info: Dict[str, Any],
        root_note: int,
        scale_notes: List[int]
    ) -> List[NoteEvent]:
        """
        Generate bass pattern appropriate for the genre.
        
        Args:
            section: Song section
            context: Performance context
            personality: Scaled personality
            pattern_info: Genre-specific pattern knowledge
            root_note: Root note MIDI number
            scale_notes: Available scale notes
            
        Returns:
            List of NoteEvent objects
        """
        notes = []
        
        # Get key notes
        fifth_note = root_note + 7
        octave_note = root_note + 12
        flat_seven = root_note + 10
        
        # Get pattern parameters
        typical_positions = pattern_info.get('typical_positions', [0, 2.5])
        sustain_type = pattern_info.get('sustain', 'medium')
        
        # Determine note duration based on sustain type and personality
        if sustain_type == 'long':
            base_duration = TICKS_PER_BEAT * 2
        elif sustain_type == 'short':
            base_duration = TICKS_PER_8TH
        else:  # medium
            base_duration = TICKS_PER_BEAT
        
        # Adjust duration by aggressiveness (more aggressive = shorter, punchier)
        duration_mult = 1.0 - (personality.aggressiveness * 0.3)
        note_duration = int(base_duration * duration_mult)
        
        # Base velocity from personality
        base_velocity = int(100 * (0.7 + 0.3 * personality.aggressiveness))
        
        for bar in range(section.bars):
            bar_offset = section.start_tick + (bar * TICKS_PER_BAR_4_4)
            
            # Determine chord for this bar from context
            bar_root = self._get_chord_root_for_bar(context, bar, root_note, scale_notes)
            bar_fifth = bar_root + 7
            bar_octave = bar_root + 12
            
            # Check for kick-lock opportunities
            kick_positions = self._get_kick_positions_in_bar(context, bar, section.start_tick)
            
            for pos in typical_positions:
                tick = bar_offset + beats_to_ticks(pos)
                
                # Skip if we're past the section end
                if tick >= section.end_tick:
                    continue
                
                # Decide which note to play
                if pos == 0:
                    # Downbeat: always root for foundation
                    pitch = bar_root
                    vel = base_velocity
                elif pos in [2, 3]:
                    # Mid-bar: could be root, fifth, or octave
                    if personality.complexity > 0.6 and random.random() < 0.3:
                        pitch = random.choice([bar_fifth, bar_octave, flat_seven + (bar_root - root_note)])
                    else:
                        pitch = bar_root
                    vel = base_velocity - 5
                else:
                    # Syncopated positions: add variation
                    if personality.variation_tendency > 0.4 and random.random() < personality.variation_tendency:
                        pitch = random.choice([bar_root, bar_fifth, bar_octave])
                    else:
                        pitch = bar_root
                    vel = base_velocity - 10
                
                # Kick-lock: if close to a kick, snap to it
                if kick_positions and personality.consistency > 0.5:
                    closest_kick = min(kick_positions, key=lambda k: abs(k - tick))
                    if abs(closest_kick - tick) < TICKS_PER_16TH:
                        tick = closest_kick
                        vel = min(127, vel + 10)  # Boost velocity when locked
                        self._log_decision(f"Kick-locked bass at tick {tick}")
                
                # Apply humanization
                vel = humanize_velocity(vel, variation=0.1 * (1.0 - personality.consistency))
                
                notes.append(NoteEvent(
                    pitch=pitch,
                    start_tick=tick,
                    duration_ticks=note_duration,
                    velocity=min(127, vel),
                    channel=1
                ))
        
        return notes
    
    def _get_chord_root_for_bar(
        self,
        context: PerformanceContext,
        bar: int,
        default_root: int,
        scale_notes: List[int]
    ) -> int:
        """Get the chord root for a specific bar from context."""
        if not context.chord_progression:
            return default_root
        
        # Simple: cycle through chord progression
        chord_idx = bar % len(context.chord_progression)
        chord = context.chord_progression[chord_idx]
        
        # Parse chord root (e.g., "Cm7" -> "C")
        if chord:
            root_name = chord[0]
            if len(chord) > 1 and chord[1] in '#b':
                root_name += chord[1]
            
            try:
                return note_name_to_midi(root_name, 1)
            except Exception:
                pass
        
        return default_root
    
    def _get_kick_positions_in_bar(
        self,
        context: PerformanceContext,
        bar: int,
        section_start: int
    ) -> List[int]:
        """Get kick drum positions for a bar (for kick-lock)."""
        # This would ideally come from the drummer's output
        # For now, generate typical kick positions based on genre
        kick_positions = []
        bar_offset = section_start + (bar * TICKS_PER_BAR_4_4)
        
        # Use last_kick_tick from context if available
        if context.last_kick_tick is not None:
            # Calculate relative position
            if bar_offset <= context.last_kick_tick < bar_offset + TICKS_PER_BAR_4_4:
                kick_positions.append(context.last_kick_tick)
        
        # Add typical kick positions
        typical_kicks = [0, beats_to_ticks(2.5)]  # Common trap/hip-hop
        for pos in typical_kicks:
            kick_positions.append(bar_offset + pos)
        
        return kick_positions
    
    def _add_slides(
        self,
        notes: List[NoteEvent],
        slide_probability: float,
        aggressiveness: float
    ) -> List[NoteEvent]:
        """
        Add slide effects to existing notes.
        
        Args:
            notes: Existing bass notes
            slide_probability: Probability of adding slide to each note
            aggressiveness: Affects slide intensity
            
        Returns:
            List of additional slide notes (not replacing originals)
        """
        slide_notes = []
        
        for note in notes:
            if random.random() < slide_probability:
                # Determine slide type based on aggressiveness
                if aggressiveness > 0.7 and random.random() < 0.3:
                    # Dive bomb
                    slides = SlideGenerator.generate_slide_down(
                        note.start_tick,
                        note.pitch + 12,  # Start an octave higher
                        semitones=7,
                        base_velocity=note.velocity,
                        total_duration=TICKS_PER_BEAT
                    )
                    slide_notes.extend(slides)
                elif random.random() < 0.5:
                    # Slide up into note
                    slides = SlideGenerator.generate_slide_up(
                        note.start_tick,
                        note.pitch,
                        semitones=random.randint(2, 4),
                        base_velocity=note.velocity,
                        duration_ticks=note.duration_ticks
                    )
                    # Replace the original note timing with slide
                    slide_notes.extend(slides[:-1])  # Add grace notes only
        
        return slide_notes
    
    def _should_add_fill(
        self,
        section: SongSection,
        personality: AgentPersonality
    ) -> bool:
        """Decide if a fill should be added based on section and personality."""
        # Always add fill before high-energy sections
        if section.section_type in [SectionType.DROP, SectionType.CHORUS]:
            return True
        
        # Personality-based random chance
        fill_chance = personality.fill_frequency * 0.6
        
        # Boost chance for transition sections
        if section.section_type in [SectionType.PRE_CHORUS, SectionType.BUILDUP]:
            fill_chance += 0.3
        
        return random.random() < fill_chance
    
    def _generate_section_fill(
        self,
        section: SongSection,
        context: PerformanceContext,
        personality: AgentPersonality,
        root_note: int,
        scale_notes: List[int]
    ) -> Tuple[List[NoteEvent], int]:
        """
        Generate a fill for the end of the section.
        
        Args:
            section: Current section
            context: Performance context
            personality: Scaled personality
            root_note: Root note MIDI number
            scale_notes: Available scale notes
            
        Returns:
            Tuple of (fill notes, fill start tick)
        """
        fill_duration = 1.0 if personality.complexity < 0.5 else 2.0
        fill_start = section.end_tick - int(fill_duration * TICKS_PER_BEAT)
        
        base_velocity = int(90 * (0.8 + 0.4 * personality.aggressiveness))
        
        # Select fill type based on complexity
        if personality.complexity > 0.7:
            # Complex: ascending run
            target = root_note + 12  # Octave above
            notes = BassRunGenerator.generate_ascending_run(
                fill_start, root_note, target, scale_notes,
                duration_beats=fill_duration, base_velocity=base_velocity
            )
        elif personality.complexity > 0.4:
            # Medium: chromatic descent
            notes = BassRunGenerator.generate_descending_chromatic(
                fill_start, root_note + 7, semitones=5,
                duration_beats=fill_duration, base_velocity=base_velocity
            )
        else:
            # Simple: octave climb
            notes = BassRunGenerator.generate_octave_climb(
                fill_start, root_note,
                duration_beats=fill_duration, base_velocity=base_velocity
            )
        
        return notes, fill_start
    
    def _apply_push_pull(
        self,
        notes: List[NoteEvent],
        push_pull: float
    ) -> List[NoteEvent]:
        """
        Apply push/pull timing adjustment to all notes.
        
        Push (positive): Playing ahead of the beat (driving)
        Pull (negative): Playing behind the beat (laid back, groove)
        
        Args:
            notes: List of notes to adjust
            push_pull: Amount from -1 to 1 (typically -0.1 to 0.1)
            
        Returns:
            Notes with adjusted timing
        """
        max_offset = TICKS_PER_16TH // 2  # ±30 ticks
        offset = int(push_pull * max_offset)
        
        for note in notes:
            note.start_tick = max(0, note.start_tick + offset)
        
        return notes
    
    def _generate_cue_fill(
        self,
        start_tick: int,
        root_note: int,
        scale_notes: List[int],
        base_velocity: int
    ) -> List[NoteEvent]:
        """Generate a fill for the 'fill' cue."""
        # Ascending run for 2 beats
        target = root_note + 12
        return BassRunGenerator.generate_ascending_run(
            start_tick, root_note, target, scale_notes,
            duration_beats=2.0, base_velocity=base_velocity
        )
    
    def _generate_drop_cue(
        self,
        start_tick: int,
        root_note: int,
        base_velocity: int
    ) -> List[NoteEvent]:
        """Generate a big hit for the 'drop' cue."""
        notes = []
        
        # Big sub hit
        notes.append(NoteEvent(
            pitch=root_note,
            start_tick=start_tick,
            duration_ticks=TICKS_PER_BEAT * 2,
            velocity=min(127, base_velocity + 15),
            channel=1
        ))
        
        # Optional: slide down after initial hit
        slide_notes = SlideGenerator.generate_slide_down(
            start_tick + TICKS_PER_BEAT,
            root_note,
            semitones=5,
            base_velocity=base_velocity - 10,
            total_duration=TICKS_PER_BEAT
        )
        notes.extend(slide_notes)
        
        return notes
