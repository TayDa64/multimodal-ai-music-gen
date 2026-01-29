"""
BegenaAgent - Masterclass Ethiopian Bass Lyre Performer

This module implements a professional begena (በገና) player agent with deep knowledge of:
- Ethiopian Qenet (Modal) System: Tizita, Ambassel, Bati, Anchihoye scales
- Sacred/Meditative Music: Zema (religious chant accompaniment)
- Playing Techniques: Drone bass, buzzing strings, sparse melodies
- Characteristic Sound: Deep resonance, leather-wrapped string buzz

The BegenaAgent is designed to generate authentic Ethiopian bass lyre parts
typically used in meditative, religious, or contemplative musical settings.

Physical Instrument Reference:
    The begena is a large 10-string lyre used for sacred and contemplative music:
    - 10 strings (gut or nylon) with leather wrappings
    - Large wooden frame (up to 1 meter tall)
    - Characteristic "buzzing" from leather wrappings
    - Range: Approximately E2-E4 (MIDI 40-64, bass register)
    
Musical Characteristics:
    - Deep, bass-heavy drone tones
    - Characteristic "buzz/rattle" from leather wrappings
    - Long sustained notes with slow decay
    - Sparse, meditative phrases
    - Often accompanies religious poetry (qene)
    - Contemplative, introspective quality

Architecture Notes:
    This is a Stage 1 (offline) implementation with comprehensive Ethiopian
    music theory. Stage 2 will add API-backed generation for creative variation.
    
    Imports QenetTheory from the masenqo module to share Ethiopian scale knowledge.

Example:
    ```python
    from multimodal_gen.agents.performers import BegenaAgent
    from multimodal_gen.agents import PerformanceContext, BEGENA_PRESETS
    
    begena = BegenaAgent()
    begena.set_personality(BEGENA_PRESETS['meditative_zema'])
    
    result = begena.perform(context, section)
    print(f"Generated {len(result.notes)} begena notes")
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
# BEGENA PERSONALITY PRESETS
# =============================================================================

BEGENA_PRESETS: Dict[str, AgentPersonality] = {
    "meditative_zema": AgentPersonality(
        aggressiveness=0.15,
        complexity=0.3,
        consistency=0.95,
        push_pull=-0.05,  # Behind the beat for meditative feel
        swing_affinity=0.0,
        fill_frequency=0.1,
        ghost_note_density=0.2,  # Sparse ornamentation
        variation_tendency=0.2,
        signature_patterns=["sustained_drone", "sparse_melody", "contemplative_phrase"]
    ),
    
    "spiritual_contemplation": AgentPersonality(
        aggressiveness=0.2,
        complexity=0.35,
        consistency=0.9,
        push_pull=-0.04,
        swing_affinity=0.0,
        fill_frequency=0.15,
        ghost_note_density=0.25,
        variation_tendency=0.25,
        signature_patterns=["bass_drone", "modal_movement", "reflective_pause"]
    ),
    
    "qene_accompaniment": AgentPersonality(
        aggressiveness=0.25,
        complexity=0.4,
        consistency=0.85,
        push_pull=-0.03,
        swing_affinity=0.05,
        fill_frequency=0.2,
        ghost_note_density=0.3,
        variation_tendency=0.3,
        signature_patterns=["responsive_phrase", "text_painting", "cadential_figure"]
    ),
    
    "ethio_ambient": AgentPersonality(
        aggressiveness=0.18,
        complexity=0.45,
        consistency=0.88,
        push_pull=-0.06,  # Very laid back
        swing_affinity=0.0,
        fill_frequency=0.12,
        ghost_note_density=0.35,
        variation_tendency=0.35,
        signature_patterns=["evolving_drone", "harmonic_shimmer", "bass_swell"]
    ),
    
    "ceremonial_solemn": AgentPersonality(
        aggressiveness=0.22,
        complexity=0.25,
        consistency=0.97,
        push_pull=-0.04,
        swing_affinity=0.0,
        fill_frequency=0.08,
        ghost_note_density=0.15,
        variation_tendency=0.1,
        signature_patterns=["ritual_drone", "modal_anchor", "solemn_cadence"]
    ),
}


# =============================================================================
# BEGENA TUNING AND TECHNIQUES
# =============================================================================

class BegenaTuning:
    """
    Begena tuning configurations.
    
    The begena has 10 strings, typically tuned in pairs with the
    characteristic low register providing bass foundation.
    Strings are paired for octaves or unisons with slight detuning
    that creates the characteristic "chorus" effect.
    """
    
    # Standard 10-string begena tuning (MIDI pitches, low to high)
    # Pairs: (low octave, high octave) creating rich timbre
    STANDARD_TUNING = [
        40, 40,   # E2 pair (bass drone)
        47, 47,   # B2 pair (fifth)
        52, 52,   # E3 pair (octave)
        55, 55,   # G3 pair (third)
        59, 59,   # B3 pair (fifth)
    ]
    
    # Ambassel mode tuning (more minor character)
    AMBASSEL_TUNING = [
        40, 40,   # E2 pair
        46, 46,   # Bb2 pair (flat fifth character)
        52, 52,   # E3 pair
        55, 55,   # G3 pair
        58, 58,   # Bb3 pair
    ]
    
    # Tizita tuning (pentatonic emphasis)
    TIZITA_TUNING = [
        40, 40,   # E2 pair
        47, 47,   # B2 pair
        52, 52,   # E3 pair
        56, 56,   # G#3 pair (raised third)
        59, 59,   # B3 pair
    ]
    
    TUNINGS = {
        "standard": STANDARD_TUNING,
        "ambassel": AMBASSEL_TUNING,
        "tizita_major": TIZITA_TUNING,
        "tizita_minor": STANDARD_TUNING,
        "bati_major": TIZITA_TUNING,
        "bati_minor": STANDARD_TUNING,
        "anchihoye": AMBASSEL_TUNING,
    }
    
    @classmethod
    def get_tuning_for_qenet(cls, qenet: str) -> List[int]:
        """Get begena tuning for a qenet mode."""
        return cls.TUNINGS.get(qenet, cls.STANDARD_TUNING)
    
    @classmethod
    def transpose_tuning(cls, tuning: List[int], semitones: int) -> List[int]:
        """Transpose tuning by semitones."""
        return [pitch + semitones for pitch in tuning]
    
    @classmethod
    def get_drone_pitches(cls, tuning: List[int]) -> List[int]:
        """Get the primary drone pitches (lowest pairs)."""
        # Return unique pitches from the bass pairs
        return list(set(tuning[:4]))
    
    @classmethod
    def get_melody_pitches(cls, tuning: List[int]) -> List[int]:
        """Get the melody-capable pitches (higher strings)."""
        return list(set(tuning[4:]))


class BegenaTechniques:
    """
    Begena playing technique patterns.
    
    The begena has distinct playing characteristics:
    - Long sustained drones
    - Buzzing overtones from leather wrappings
    - Paired string plucking (octaves/unisons)
    - Very sparse melodic movement
    """
    
    @staticmethod
    def generate_drone(
        pitches: List[int],
        duration_ticks: int,
        velocity_base: int = 55,
        with_swell: bool = False
    ) -> List[Tuple[int, int, int, int]]:
        """
        Generate sustained drone notes.
        
        Args:
            pitches: Drone pitches (usually bass pairs)
            duration_ticks: Total duration
            velocity_base: Base velocity (begena is typically quiet)
            with_swell: Add dynamic swell
            
        Returns:
            List of (tick_offset, duration, pitch, velocity)
        """
        notes = []
        
        for pitch in pitches:
            vel = humanize_velocity(velocity_base, variation=0.08)
            notes.append((0, duration_ticks, pitch, vel))
            
            # Add sympathetic resonance (quieter octave)
            if pitch + 12 <= 76:  # Keep in reasonable range
                sympathetic_vel = int(vel * 0.3)
                notes.append((TICKS_PER_BEAT // 2, duration_ticks - TICKS_PER_BEAT, pitch + 12, sympathetic_vel))
        
        return notes
    
    @staticmethod
    def generate_paired_pluck(
        pitch: int,
        duration_ticks: int,
        velocity: int = 60
    ) -> List[Tuple[int, int, int, int]]:
        """
        Generate paired string pluck (slight timing offset for chorus effect).
        
        The begena's paired strings are plucked almost simultaneously
        but with tiny timing differences creating richness.
        """
        notes = []
        
        # First of pair
        notes.append((0, duration_ticks, pitch, velocity))
        
        # Second of pair (slight delay and velocity variation)
        delay = random.randint(5, 15)  # Tiny timing offset
        vel2 = max(40, velocity - random.randint(3, 8))
        notes.append((delay, duration_ticks - delay, pitch, vel2))
        
        return notes
    
    @staticmethod
    def generate_buzz_accent(
        pitch: int,
        velocity: int = 65
    ) -> List[Tuple[int, int, int, int]]:
        """
        Generate the characteristic "buzz" accent.
        
        This simulates the leather-wrapped strings rattling,
        represented as a quick series of very short notes.
        """
        notes = []
        
        # Main note
        notes.append((0, TICKS_PER_8TH, pitch, velocity))
        
        # Buzz "rattle" - series of very quiet rapid retriggering
        buzz_ticks = TICKS_PER_16TH // 4
        for i in range(3):
            tick = TICKS_PER_16TH + (i * buzz_ticks)
            buzz_vel = max(30, velocity - 30 - (i * 5))
            notes.append((tick, buzz_ticks, pitch, buzz_vel))
        
        return notes
    
    @staticmethod
    def generate_meditative_phrase(
        scale_pitches: List[int],
        duration_beats: int = 4
    ) -> List[Tuple[int, int, int, int]]:
        """
        Generate a sparse, meditative melodic phrase.
        
        Begena melodies are extremely sparse, with long gaps
        and sustained notes emphasizing contemplation.
        """
        notes = []
        
        if not scale_pitches:
            return notes
        
        # Select 2-3 notes for the phrase
        num_notes = random.randint(2, 3)
        selected = random.sample(scale_pitches[:5], min(num_notes, len(scale_pitches[:5])))
        
        # Distribute across the duration with lots of space
        total_ticks = duration_beats * TICKS_PER_BEAT
        positions = sorted(random.sample(range(0, total_ticks - TICKS_PER_BEAT, TICKS_PER_BEAT), num_notes))
        
        for i, (tick, pitch) in enumerate(zip(positions, selected)):
            # Long durations
            dur = random.choice([TICKS_PER_BEAT * 2, TICKS_PER_BEAT * 3, TICKS_PER_BAR_4_4])
            dur = min(dur, total_ticks - tick)
            vel = humanize_velocity(55, 0.1)
            notes.append((tick, dur, pitch, vel))
        
        return notes


# =============================================================================
# BEGENA PATTERN VOCABULARY
# =============================================================================

class BegenaPatterns:
    """
    Common begena accompaniment patterns.
    
    Patterns are designed for meditative/sacred contexts:
    - Sustained drones providing modal anchor
    - Sparse melodic interjections
    - Ritual/ceremonial cadences
    """
    
    @staticmethod
    def zema_drone_pattern(
        tuning: List[int],
        bars: int = 4
    ) -> List[Tuple[int, int, int, int]]:
        """
        Classic Zema (religious chant) drone accompaniment.
        
        Very sustained, minimal movement, providing
        harmonic foundation for vocal chanting.
        """
        notes = []
        drone_pitches = BegenaTuning.get_drone_pitches(tuning)
        
        # One long drone for entire section
        total_ticks = bars * TICKS_PER_BAR_4_4
        
        for pitch in drone_pitches[:2]:  # Use lowest two unique pitches
            drone_notes = BegenaTechniques.generate_drone(
                [pitch], total_ticks, velocity_base=50
            )
            notes.extend(drone_notes)
        
        # Optional: add one high note at midpoint
        if bars >= 2 and len(tuning) > 6:
            mid_tick = (bars // 2) * TICKS_PER_BAR_4_4
            high_pitch = tuning[6] if len(tuning) > 6 else tuning[-1]
            notes.append((mid_tick, TICKS_PER_BEAT * 2, high_pitch, 45))
        
        return notes
    
    @staticmethod
    def contemplative_movement(
        tuning: List[int],
        scale: List[int],
        bars: int = 4
    ) -> List[Tuple[int, int, int, int]]:
        """
        Contemplative pattern with slow melodic movement.
        
        Drone bass with occasional sparse upper movement,
        suitable for meditative/ambient contexts.
        """
        notes = []
        drone_pitches = BegenaTuning.get_drone_pitches(tuning)
        
        # Continuous bass drone
        total_ticks = bars * TICKS_PER_BAR_4_4
        for pitch in drone_pitches[:1]:  # Single bass drone
            notes.extend(BegenaTechniques.generate_drone([pitch], total_ticks, 48))
        
        # Sparse upper movement (one note per bar or less)
        melody_pitches = scale[-4:] if len(scale) >= 4 else scale  # Upper scale tones
        
        for bar in range(bars):
            if random.random() < 0.5:  # 50% chance of note each bar
                bar_offset = bar * TICKS_PER_BAR_4_4
                beat_offset = random.choice([TICKS_PER_BEAT, TICKS_PER_BEAT * 2, TICKS_PER_BEAT * 3])
                
                pitch = random.choice(melody_pitches)
                duration = random.choice([TICKS_PER_BEAT * 2, TICKS_PER_BEAT * 3])
                vel = humanize_velocity(52, 0.1)
                
                notes.append((bar_offset + beat_offset, duration, pitch, vel))
        
        return notes
    
    @staticmethod
    def ritual_cadence(
        tuning: List[int],
        scale: List[int]
    ) -> List[Tuple[int, int, int, int]]:
        """
        Ceremonial cadence pattern for phrase endings.
        
        A solemn descending figure resolving to the tonic drone.
        """
        notes = []
        
        if len(scale) < 3:
            return notes
        
        # Descending figure (scale degree 3 -> 2 -> 1)
        cadence_pitches = [scale[2], scale[1], scale[0]]
        durations = [TICKS_PER_BEAT, TICKS_PER_BEAT, TICKS_PER_BEAT * 4]
        velocities = [55, 50, 58]
        
        tick = 0
        for pitch, dur, vel in zip(cadence_pitches, durations, velocities):
            # Add buzz accent on resolution
            if pitch == scale[0]:
                buzz_notes = BegenaTechniques.generate_buzz_accent(pitch, vel)
                for btick, bdur, bpitch, bvel in buzz_notes:
                    notes.append((tick + btick, bdur, bpitch, bvel))
            else:
                notes.append((tick, dur, pitch, vel))
            tick += dur
        
        # Final drone
        drone_pitch = tuning[0] if tuning else scale[0] - 12
        notes.append((tick, TICKS_PER_BAR_4_4, drone_pitch, 45))
        
        return notes
    
    @staticmethod
    def qene_response(
        tuning: List[int],
        scale: List[int],
        bars: int = 2
    ) -> List[Tuple[int, int, int, int]]:
        """
        Response pattern for Qene (religious poetry) accompaniment.
        
        The begena responds to vocal phrases with supportive
        bass movement and occasional melodic echoes.
        """
        notes = []
        
        # Bass support on downbeats
        bass_pitch = tuning[0] if tuning else 40
        for bar in range(bars):
            bar_offset = bar * TICKS_PER_BAR_4_4
            notes.extend([
                (bar_offset, TICKS_PER_BEAT * 2, bass_pitch, 50),
                (bar_offset + TICKS_PER_BEAT * 3, TICKS_PER_BEAT, bass_pitch + 7, 45),  # Fifth
            ])
        
        # Echo phrase in second bar
        if bars >= 2 and scale:
            echo_tick = TICKS_PER_BAR_4_4 + TICKS_PER_BEAT
            echo_pitches = scale[1:4] if len(scale) >= 4 else scale
            for i, pitch in enumerate(echo_pitches[:2]):
                notes.append((
                    echo_tick + (i * TICKS_PER_BEAT),
                    TICKS_PER_BEAT,
                    pitch,
                    humanize_velocity(48, 0.1)
                ))
        
        return notes


# =============================================================================
# BEGENA PERFORMER AGENT
# =============================================================================

class BegenaAgent(IPerformerAgent):
    """
    Masterclass Ethiopian Begena (Bass Lyre) performer agent.
    
    Generates authentic begena accompaniment with deep knowledge
    of Ethiopian qenet modes, sacred music traditions, and the
    instrument's characteristic meditative, buzzing sound.
    
    Attributes:
        role: Fixed as BASS (provides bass/drone foundation)
        personality: Current personality settings
        qenet: QenetTheory instance for scale knowledge
        _current_tuning: Active begena tuning
        _decisions_made: Record of performance decisions
    """
    
    def __init__(self):
        """Initialize BegenaAgent with Ethiopian music knowledge."""
        self._personality: Optional[AgentPersonality] = None
        self._qenet = QenetTheory()
        self._current_tuning = BegenaTuning.STANDARD_TUNING
        self._decisions_made: List[str] = []
    
    @property
    def role(self) -> AgentRole:
        """Begena provides bass/drone foundation."""
        return AgentRole.BASS
    
    @property
    def name(self) -> str:
        """Human-readable name for this begena performer."""
        if self._personality:
            intensity = self._personality.intensity
            if intensity > 0.7:
                return "Ceremonial Begena"
            elif intensity > 0.4:
                return "Traditional Begena"
            else:
                return "Meditative Begena"
        return "Ethiopian Begena"
    
    @property
    def personality(self) -> Optional[AgentPersonality]:
        """Current personality configuration."""
        return self._personality
    
    def set_personality(self, personality: AgentPersonality) -> None:
        """Set performer personality."""
        self._personality = deepcopy(personality)
    
    def perform(
        self,
        context: PerformanceContext,
        section: SongSection,
        personality: Optional[AgentPersonality] = None
    ) -> PerformanceResult:
        """
        Generate begena accompaniment for a song section.
        
        Args:
            context: Performance context with key, tempo, etc.
            section: Song section to perform
            personality: Optional override personality
            
        Returns:
            PerformanceResult with generated notes
        """
        active_personality = personality or self._personality or BEGENA_PRESETS["meditative_zema"]
        self._decisions_made = []
        
        # Determine qenet mode from context
        qenet_name = self._select_qenet(context)
        self._decisions_made.append(f"qenet_mode:{qenet_name}")
        
        # Get scale for the key
        root_pitch = self._get_root_pitch(context.key or "E")
        scale = self._qenet.get_scale_for_key(qenet_name, root_pitch - 12)  # Begena is bass register
        
        # Set tuning based on qenet
        self._current_tuning = BegenaTuning.get_tuning_for_qenet(qenet_name)
        # Transpose to match key
        transpose = (root_pitch - 12) - 40  # Relative to E2
        self._current_tuning = BegenaTuning.transpose_tuning(self._current_tuning, transpose)
        self._decisions_made.append(f"tuning:transposed_{transpose}")
        
        # Select pattern based on section type and personality
        pattern_func = self._select_pattern(section, active_personality)
        self._decisions_made.append(f"pattern:{pattern_func.__name__}")
        
        # Generate notes
        notes = self._generate_section_notes(
            section, context, active_personality, pattern_func, scale
        )
        
        # Apply humanization
        notes = self._apply_humanization(notes, active_personality, context.bpm or 60)
        
        # Convert to NoteEvents
        note_events = self._convert_to_note_events(notes)
        
        return PerformanceResult(
            notes=note_events,
            decisions_made=self._decisions_made.copy(),
            confidence=0.9,  # High confidence for meditative patterns
            metadata={
                "qenet": qenet_name,
                "tuning": self._current_tuning[:4],  # First 4 for summary
                "character": "meditative"
            }
        )
    
    def _select_qenet(self, context: PerformanceContext) -> str:
        """Select appropriate qenet mode based on context."""
        genre = (context.genre or "").lower()
        mood = (context.mood or "").lower()
        
        # Begena favors meditative/spiritual modes
        if "zema" in genre or "spiritual" in genre or "religious" in genre:
            return "ambassel"
        elif "traditional" in genre or "ethiopian" in genre:
            return "tizita_minor"
        
        # Mood-based selection
        if "meditative" in mood or "contemplative" in mood or "peaceful" in mood:
            return "ambassel"
        elif "sad" in mood or "melancholic" in mood:
            return "tizita_minor"
        elif "spiritual" in mood or "sacred" in mood:
            return "ambassel"
        
        # Default to Ambassel (most appropriate for begena)
        return "ambassel"
    
    def _get_root_pitch(self, key: str) -> int:
        """Convert key string to root MIDI pitch."""
        key_upper = key.upper().strip()
        
        key_map = {
            "C": 60, "C#": 61, "DB": 61,
            "D": 62, "D#": 63, "EB": 63,
            "E": 64, "F": 65, "F#": 66, "GB": 66,
            "G": 67, "G#": 68, "AB": 68,
            "A": 69, "A#": 70, "BB": 70,
            "B": 71
        }
        
        for suffix in ["MINOR", "MAJOR", "MIN", "MAJ", "M", " "]:
            key_upper = key_upper.replace(suffix, "")
        
        return key_map.get(key_upper.strip(), 64)  # Default E
    
    def _select_pattern(
        self, 
        section: SongSection, 
        personality: AgentPersonality
    ) -> callable:
        """Select begena pattern based on section and personality."""
        section_type = section.type if hasattr(section, 'type') else SectionType.VERSE
        
        # Begena patterns are generally meditative regardless of section
        if section_type in [SectionType.INTRO, SectionType.OUTRO]:
            return BegenaPatterns.zema_drone_pattern
        
        elif section_type == SectionType.BRIDGE:
            return BegenaPatterns.ritual_cadence
        
        # Check personality patterns
        if "drone" in str(personality.signature_patterns):
            return BegenaPatterns.zema_drone_pattern
        elif "responsive" in str(personality.signature_patterns):
            return BegenaPatterns.qene_response
        
        # Default to contemplative movement
        return BegenaPatterns.contemplative_movement
    
    def _generate_section_notes(
        self,
        section: SongSection,
        context: PerformanceContext,
        personality: AgentPersonality,
        pattern_func: callable,
        scale: List[int]
    ) -> List[Tuple[int, int, int, int]]:
        """Generate notes for the section using selected pattern."""
        notes = []
        
        # Get section parameters
        num_bars = section.bars if hasattr(section, 'bars') else 4
        
        # Begena patterns often span multiple bars
        if pattern_func == BegenaPatterns.zema_drone_pattern:
            notes = pattern_func(self._current_tuning, num_bars)
        elif pattern_func == BegenaPatterns.ritual_cadence:
            # Ritual cadence at end of section
            cadence_notes = pattern_func(self._current_tuning, scale)
            # Place at section end
            section_end_tick = (num_bars - 2) * TICKS_PER_BAR_4_4
            for tick, dur, pitch, vel in cadence_notes:
                notes.append((section_end_tick + tick, dur, pitch, vel))
            # Add drone for rest of section
            drone_notes = BegenaPatterns.zema_drone_pattern(self._current_tuning, num_bars - 2)
            notes.extend(drone_notes)
        elif pattern_func == BegenaPatterns.qene_response:
            # Qene pattern every 2 bars
            for phrase in range(num_bars // 2):
                phrase_offset = phrase * 2 * TICKS_PER_BAR_4_4
                pattern_notes = pattern_func(self._current_tuning, scale, 2)
                for tick, dur, pitch, vel in pattern_notes:
                    notes.append((phrase_offset + tick, dur, pitch, vel))
        else:
            # Contemplative movement
            notes = pattern_func(self._current_tuning, scale, num_bars)
        
        return notes
    
    def _apply_humanization(
        self,
        notes: List[Tuple[int, int, int, int]],
        personality: AgentPersonality,
        bpm: float
    ) -> List[Tuple[int, int, int, int]]:
        """Apply subtle humanization (begena is very consistent)."""
        humanized = []
        
        for tick, dur, pitch, vel in notes:
            # Very subtle timing variation (begena is meditative)
            timing_offset = humanize_timing(tick, variation=0.015 + personality.push_pull * 0.01)
            tick = max(0, int(timing_offset))
            
            # Velocity variation
            vel = humanize_velocity(vel, variation=0.06)
            
            humanized.append((tick, dur, pitch, vel))
        
        return humanized
    
    def react_to_cue(
        self,
        cue_type: str,
        context: PerformanceContext
    ) -> List[NoteEvent]:
        """
        React to a performance cue with appropriate begena response.
        
        The begena's meditative nature means reactions are subtle and sustained.
        
        Cue types:
            - "fill": Slow melodic phrase with buzz
            - "stop": Let strings ring out naturally
            - "build": Gradually intensifying drone
            - "drop": Fade to whisper-quiet drone
            - "accent": Strong bass note with sympathetic buzz
        """
        tpb = context.ticks_per_beat
        notes = []
        
        # Get current qenet scale
        mode_name = self._current_tuning.value.replace("_tuning", "")
        if mode_name == "tizita":
            mode_name = "tizita_major"
        elif mode_name == "bati":
            mode_name = "bati_major"
        scale = self._qenet.get_scale(context.key, mode_name)
        
        # Base velocity - begena is typically quiet
        base_vel = 55
        if self._personality:
            base_vel = int(40 + self._personality.intensity * 35)
        
        if cue_type == "fill":
            # Slow melodic descent with buzz notes
            for i, interval in enumerate(scale[:4]):
                tick = i * tpb
                notes.append(NoteEvent(
                    tick=tick,
                    pitch=48 + interval,  # Bass register
                    velocity=base_vel,
                    duration=tpb * 2,
                    channel=0
                ))
        
        elif cue_type == "stop":
            # Single sustained note allowed to ring
            notes.append(NoteEvent(
                tick=0,
                pitch=48 + scale[0],
                velocity=30,
                duration=tpb * 4,
                channel=0
            ))
        
        elif cue_type == "build":
            # Gradually intensifying repeated drone
            for i in range(8):
                tick = i * (tpb // 2)
                vel = min(90, 40 + i * 6)
                notes.append(NoteEvent(
                    tick=tick,
                    pitch=48 + scale[0],
                    velocity=vel,
                    duration=tpb // 2,
                    channel=0
                ))
        
        elif cue_type == "drop":
            # Whisper-quiet sustained drone
            notes.append(NoteEvent(
                tick=0,
                pitch=48 + scale[0],
                velocity=25,
                duration=tpb * 4,
                channel=0
            ))
            # Add subtle fifth
            if len(scale) > 4:
                notes.append(NoteEvent(
                    tick=tpb // 2,
                    pitch=48 + scale[4],
                    velocity=20,
                    duration=tpb * 3,
                    channel=0
                ))
        
        elif cue_type == "accent":
            # Strong bass with sympathetic resonance
            notes.append(NoteEvent(
                tick=0,
                pitch=36 + scale[0],  # Deep bass
                velocity=min(100, base_vel + 25),
                duration=tpb * 2,
                channel=0
            ))
            # Sympathetic buzz notes
            for i in range(1, 4):
                if i < len(scale):
                    notes.append(NoteEvent(
                        tick=20,
                        pitch=60 + scale[i],
                        velocity=25,
                        duration=tpb,
                        channel=0
                    ))
        
        return notes
    
    def _convert_to_note_events(
        self,
        notes: List[Tuple[int, int, int, int]]
    ) -> List[NoteEvent]:
        """Convert note tuples to NoteEvent objects."""
        events = []
        
        for tick, dur, pitch, vel in notes:
            event = NoteEvent(
                tick=tick,
                pitch=pitch,
                velocity=vel,
                duration=dur,
                channel=0
            )
            events.append(event)
        
        return events


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    "BegenaAgent",
    "BegenaTuning",
    "BegenaTechniques",
    "BegenaPatterns",
    "BEGENA_PRESETS",
]
