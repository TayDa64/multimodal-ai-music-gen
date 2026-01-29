"""
KrarAgent - Masterclass Ethiopian Lyre Performer

This module implements a professional krar (ክራር) player agent with deep knowledge of:
- Ethiopian Qenet (Modal) System: Tizita, Ambassel, Bati, Anchihoye scales
- Plucking Techniques: Arpeggios, tremolo, strumming, damping
- Ornaments: Grace notes, hammer-ons, pull-offs, harmonics
- Accompaniment Patterns: Chord arpeggios, drone strings, rhythmic ostinatos

The KrarAgent is designed to generate authentic Ethiopian lyre accompaniment
that complements traditional ensembles (masenqo, washint, kebero) or modern
Ethio-jazz arrangements.

Physical Instrument Reference:
    The krar is a 5-6 string bowl lyre central to Ethiopian secular music:
    - 5-6 nylon or gut strings
    - Wooden bowl body with goatskin membrane
    - Held against the chest while plucking
    - Range: Approximately G3-E5 (MIDI 55-76)
    
Musical Characteristics:
    - Bright, resonant plucked tone
    - Quick attack with body resonance
    - Sympathetic string vibration (shimmer)
    - Often provides harmonic foundation
    - Arpeggiated accompaniment patterns
    - Can double melody in heterophony

Architecture Notes:
    This is a Stage 1 (offline) implementation with comprehensive Ethiopian
    music theory. Stage 2 will add API-backed generation for creative variation.
    
    Imports QenetTheory from the masenqo module to share Ethiopian scale knowledge.

Example:
    ```python
    from multimodal_gen.agents.performers import KrarAgent
    from multimodal_gen.agents import PerformanceContext, KRAR_PRESETS
    
    krar = KrarAgent()
    krar.set_personality(KRAR_PRESETS['traditional_azmari'])
    
    result = krar.perform(context, section)
    print(f"Generated {len(result.notes)} krar notes")
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
# KRAR PERSONALITY PRESETS
# =============================================================================

KRAR_PRESETS: Dict[str, AgentPersonality] = {
    "traditional_azmari": AgentPersonality(
        aggressiveness=0.5,
        complexity=0.5,
        consistency=0.75,
        push_pull=0.0,
        swing_affinity=0.3,  # Ethiopian groove feel
        fill_frequency=0.3,
        ghost_note_density=0.4,  # Grace notes
        variation_tendency=0.5,
        signature_patterns=["arpeggio_pattern", "drone_accompaniment", "rhythmic_strum"]
    ),
    
    "ethio_jazz_fusion": AgentPersonality(
        aggressiveness=0.45,
        complexity=0.7,
        consistency=0.6,
        push_pull=-0.02,  # Slightly behind for jazz feel
        swing_affinity=0.45,
        fill_frequency=0.4,
        ghost_note_density=0.5,
        variation_tendency=0.65,
        signature_patterns=["jazz_voicing", "extended_arpeggio", "chromatic_approach"]
    ),
    
    "eskista_energetic": AgentPersonality(
        aggressiveness=0.7,
        complexity=0.4,
        consistency=0.85,
        push_pull=0.02,  # Push forward for dance energy
        swing_affinity=0.25,
        fill_frequency=0.5,
        ghost_note_density=0.35,
        variation_tendency=0.35,
        signature_patterns=["dance_ostinato", "accent_strum", "driving_arpeggio"]
    ),
    
    "meditative_tizita": AgentPersonality(
        aggressiveness=0.25,
        complexity=0.35,
        consistency=0.9,
        push_pull=-0.03,  # Laid back
        swing_affinity=0.1,
        fill_frequency=0.15,
        ghost_note_density=0.25,
        variation_tendency=0.2,
        signature_patterns=["slow_arpeggio", "sustained_drone", "sparse_melody"]
    ),
    
    "virtuoso_ornamental": AgentPersonality(
        aggressiveness=0.55,
        complexity=0.85,
        consistency=0.55,
        push_pull=0.0,
        swing_affinity=0.3,
        fill_frequency=0.55,
        ghost_note_density=0.75,  # Heavy ornamentation
        variation_tendency=0.75,
        signature_patterns=["rapid_tremolo", "cascading_arpeggio", "harmonic_touch"]
    ),
}


# =============================================================================
# KRAR TECHNIQUE CLASSES
# =============================================================================

class KrarTuning:
    """
    Krar tuning configurations for different qenet modes.
    
    The krar typically has 5-6 strings that can be tuned to match
    the qenet being played. Common tunings emphasize the tonic,
    fifth, and characteristic notes of each mode.
    """
    
    # Standard 5-string krar tunings (MIDI pitches)
    # Strings are numbered from highest to lowest pitch
    TIZITA_TUNING = [76, 71, 67, 64, 59]       # E5, B4, G4, E4, B3 (pentatonic)
    AMBASSEL_TUNING = [76, 72, 67, 64, 60]     # E5, C5, G4, E4, C4
    BATI_TUNING = [76, 71, 68, 64, 59]         # E5, B4, Ab4, E4, B3 (minor feel)
    ANCHIHOYE_TUNING = [76, 71, 67, 63, 59]    # E5, B4, G4, Eb4, B3
    
    TUNINGS = {
        "tizita_major": TIZITA_TUNING,
        "tizita_minor": BATI_TUNING,
        "ambassel": AMBASSEL_TUNING,
        "bati_major": BATI_TUNING,
        "bati_minor": BATI_TUNING,
        "anchihoye": ANCHIHOYE_TUNING,
    }
    
    @classmethod
    def get_tuning_for_qenet(cls, qenet: str) -> List[int]:
        """Get krar tuning for a qenet mode."""
        return cls.TUNINGS.get(qenet, cls.TIZITA_TUNING)
    
    @classmethod
    def transpose_tuning(cls, tuning: List[int], semitones: int) -> List[int]:
        """Transpose tuning by semitones."""
        return [pitch + semitones for pitch in tuning]


class KrarTechniques:
    """
    Krar playing technique patterns.
    
    These represent common ways of sounding the strings:
    - Arpeggios: Sequential plucking through strings
    - Strums: Rapid brush across all strings
    - Tremolo: Rapid repeated plucking of one string
    - Harmonics: Lightly touching string at node points
    """
    
    @staticmethod
    def generate_arpeggio(
        tuning: List[int],
        direction: str = "up",
        ticks_per_note: int = TICKS_PER_8TH,
        velocity_base: int = 80
    ) -> List[Tuple[int, int, int, int]]:
        """
        Generate an arpeggio pattern through the strings.
        
        Args:
            tuning: List of MIDI pitches for strings
            direction: "up" (low to high), "down" (high to low), "alternating"
            ticks_per_note: Duration between notes
            velocity_base: Base velocity
            
        Returns:
            List of (tick_offset, duration, pitch, velocity)
        """
        notes = []
        strings = tuning.copy()
        
        if direction == "up":
            strings = list(reversed(strings))  # Low to high
        elif direction == "alternating":
            # Up then down
            strings = list(reversed(strings)) + strings[1:-1]
        # "down" keeps highest to lowest
        
        for i, pitch in enumerate(strings):
            tick = i * ticks_per_note
            vel = humanize_velocity(velocity_base, variation=0.1)
            # Slight accent on first and last notes
            if i == 0 or i == len(strings) - 1:
                vel = min(127, vel + 10)
            notes.append((tick, ticks_per_note, pitch, vel))
        
        return notes
    
    @staticmethod
    def generate_strum(
        tuning: List[int],
        direction: str = "down",
        spread_ticks: int = TICKS_PER_16TH // 2,
        velocity_base: int = 90
    ) -> List[Tuple[int, int, int, int]]:
        """
        Generate a quick strum across all strings.
        
        Args:
            tuning: List of MIDI pitches
            direction: "down" (high to low) or "up" (low to high)
            spread_ticks: Time spread across the strum
            velocity_base: Base velocity
            
        Returns:
            List of (tick_offset, duration, pitch, velocity)
        """
        notes = []
        strings = tuning.copy()
        
        if direction == "up":
            strings = list(reversed(strings))
        
        tick_per_string = spread_ticks // len(strings)
        duration = TICKS_PER_BEAT  # Let strings ring
        
        for i, pitch in enumerate(strings):
            tick = i * tick_per_string
            vel = humanize_velocity(velocity_base, variation=0.08)
            notes.append((tick, duration, pitch, vel))
        
        return notes
    
    @staticmethod
    def generate_tremolo(
        pitch: int,
        duration_ticks: int,
        speed: str = "medium",
        velocity_base: int = 75
    ) -> List[Tuple[int, int, int, int]]:
        """
        Generate tremolo (rapid repeated plucking).
        
        Args:
            pitch: MIDI pitch to tremolo
            duration_ticks: Total duration
            speed: "slow", "medium", "fast"
            velocity_base: Base velocity
            
        Returns:
            List of (tick_offset, duration, pitch, velocity)
        """
        speed_map = {
            "slow": TICKS_PER_8TH,
            "medium": TICKS_PER_16TH,
            "fast": TICKS_PER_16TH // 2
        }
        tick_interval = speed_map.get(speed, TICKS_PER_16TH)
        
        notes = []
        tick = 0
        while tick < duration_ticks:
            vel = humanize_velocity(velocity_base, variation=0.12)
            notes.append((tick, tick_interval, pitch, vel))
            tick += tick_interval
        
        return notes
    
    @staticmethod
    def generate_drone_note(
        pitch: int,
        duration_ticks: int,
        velocity: int = 60
    ) -> Tuple[int, int, int, int]:
        """
        Generate a sustained drone note (open string ringing).
        
        Args:
            pitch: MIDI pitch for drone
            duration_ticks: How long to sustain
            velocity: Drone velocity (usually quieter)
            
        Returns:
            (tick_offset, duration, pitch, velocity)
        """
        return (0, duration_ticks, pitch, velocity)


# =============================================================================
# KRAR PATTERN VOCABULARY
# =============================================================================

class KrarPatterns:
    """
    Common krar accompaniment patterns used in Ethiopian music.
    
    Patterns are organized by function:
    - Accompaniment: Supporting chords and arpeggios
    - Melodic: Call phrases and heterophonic doubling
    - Rhythmic: Dance ostinatos and accents
    """
    
    @staticmethod
    def tizita_arpeggio_pattern(
        tuning: List[int],
        bars: int = 1,
        subdivision: str = "8th"
    ) -> List[Tuple[int, int, int, int]]:
        """
        Classic Tizita nostalgic arpeggio pattern.
        
        The pattern moves through the strings in a flowing,
        melancholic sequence typical of Tizita songs.
        """
        notes = []
        ticks_per_note = TICKS_PER_8TH if subdivision == "8th" else TICKS_PER_16TH
        
        # Pattern: 5-4-3-2-1-2-3-4 (string numbers, repeated)
        pattern_strings = [0, 1, 2, 3, 4, 3, 2, 1]  # Indices into tuning
        
        tick = 0
        for bar in range(bars):
            for idx in pattern_strings:
                if idx < len(tuning):
                    pitch = tuning[idx]
                    vel = humanize_velocity(75, 0.1)
                    notes.append((tick, ticks_per_note, pitch, vel))
                tick += ticks_per_note
        
        return notes
    
    @staticmethod
    def eskista_dance_pattern(
        tuning: List[int],
        bars: int = 1,
        energy: float = 0.7
    ) -> List[Tuple[int, int, int, int]]:
        """
        Energetic Eskista (shoulder dance) accompaniment.
        
        Features syncopated strums and accents that drive
        the fast 6/8 dance rhythm.
        """
        notes = []
        base_vel = int(70 + energy * 30)  # 70-100 based on energy
        
        # 6/8 feel: emphasis on beats 1 and 4 (in 8th notes: 1, 4)
        for bar in range(bars):
            bar_offset = bar * TICKS_PER_BAR_4_4
            
            # Beat 1: Strong downstroke strum
            strum = KrarTechniques.generate_strum(
                tuning, "down", TICKS_PER_16TH // 2, base_vel + 10
            )
            for tick, dur, pitch, vel in strum:
                notes.append((bar_offset + tick, dur, pitch, vel))
            
            # Beat 2.5: Light upstroke
            upstrum = KrarTechniques.generate_strum(
                tuning[:3], "up", TICKS_PER_16TH // 2, base_vel - 15
            )
            for tick, dur, pitch, vel in upstrum:
                notes.append((bar_offset + int(TICKS_PER_BEAT * 1.5) + tick, dur // 2, pitch, vel))
            
            # Beat 3: Medium strum
            strum2 = KrarTechniques.generate_strum(
                tuning, "down", TICKS_PER_16TH // 2, base_vel
            )
            for tick, dur, pitch, vel in strum2:
                notes.append((bar_offset + TICKS_PER_BEAT * 2 + tick, dur, pitch, vel))
            
            # Beat 4: Syncopated accent
            accent_pitch = tuning[0] if tuning else 72  # Top string
            notes.append((
                bar_offset + int(TICKS_PER_BEAT * 3.5),
                TICKS_PER_8TH,
                accent_pitch,
                base_vel + 5
            ))
        
        return notes
    
    @staticmethod
    def ambassel_meditative_pattern(
        tuning: List[int],
        bars: int = 1
    ) -> List[Tuple[int, int, int, int]]:
        """
        Slow, meditative pattern for Ambassel mode.
        
        Sparse notes with long sustains, emphasizing
        the contemplative character of Ambassel.
        """
        notes = []
        
        for bar in range(bars):
            bar_offset = bar * TICKS_PER_BAR_4_4
            
            # Bar structure: whole note drone + sparse arpeggio
            if tuning:
                # Drone on lowest string
                drone = KrarTechniques.generate_drone_note(
                    tuning[-1], TICKS_PER_BAR_4_4, velocity=55
                )
                notes.append((bar_offset, drone[1], drone[2], drone[3]))
                
                # Sparse melody notes on beats 2 and 4
                if len(tuning) > 2:
                    notes.append((
                        bar_offset + TICKS_PER_BEAT,
                        TICKS_PER_BEAT * 2,
                        tuning[1],
                        humanize_velocity(65, 0.1)
                    ))
                if len(tuning) > 0:
                    notes.append((
                        bar_offset + TICKS_PER_BEAT * 3,
                        TICKS_PER_BEAT,
                        tuning[0],
                        humanize_velocity(70, 0.1)
                    ))
        
        return notes
    
    @staticmethod
    def call_response_phrase(
        tuning: List[int],
        is_call: bool = True,
        qenet_scale: List[int] = None
    ) -> List[Tuple[int, int, int, int]]:
        """
        Generate call or response phrase for vocal accompaniment.
        
        In azmari tradition, the krar often doubles or responds
        to the singer's phrases.
        """
        notes = []
        scale = qenet_scale if qenet_scale else tuning
        
        if is_call:
            # Call: Rising phrase with emphasis on characteristic tones
            phrase_pitches = [scale[-1], scale[-2], scale[0], scale[1], scale[0]]
            durations = [TICKS_PER_8TH, TICKS_PER_8TH, TICKS_PER_BEAT, TICKS_PER_8TH, TICKS_PER_BEAT]
            velocities = [70, 75, 85, 80, 75]
        else:
            # Response: Answering phrase, often descending
            phrase_pitches = [scale[0], scale[1], scale[2], scale[1], scale[-1]]
            durations = [TICKS_PER_8TH, TICKS_PER_8TH, TICKS_PER_BEAT, TICKS_PER_8TH, TICKS_PER_BEAT * 2]
            velocities = [80, 75, 70, 75, 65]
        
        tick = 0
        for pitch, dur, vel in zip(phrase_pitches, durations, velocities):
            notes.append((tick, dur, pitch, humanize_velocity(vel, 0.1)))
            tick += dur
        
        return notes


# =============================================================================
# KRAR PERFORMER AGENT
# =============================================================================

class KrarAgent(IPerformerAgent):
    """
    Masterclass Ethiopian Krar (Lyre) performer agent.
    
    Generates authentic krar accompaniment patterns with deep knowledge
    of Ethiopian qenet modes, traditional playing techniques, and
    stylistic variations from azmari to Ethio-jazz.
    
    Attributes:
        role: Fixed as CHORDS (provides harmonic foundation)
        personality: Current personality settings
        qenet: QenetTheory instance for scale knowledge
        _current_tuning: Active krar tuning
        _decisions_made: Record of performance decisions
    """
    
    def __init__(self):
        """Initialize KrarAgent with Ethiopian music knowledge."""
        self._personality: Optional[AgentPersonality] = None
        self._qenet = QenetTheory()
        self._current_tuning = KrarTuning.TIZITA_TUNING
        self._decisions_made: List[str] = []
    
    @property
    def role(self) -> AgentRole:
        """Krar provides harmonic/chordal foundation."""
        return AgentRole.KEYS
    
    @property
    def name(self) -> str:
        """Human-readable name for this krar performer."""
        if self._personality:
            intensity = self._personality.intensity
            if intensity > 0.7:
                return "Virtuoso Krar"
            elif intensity > 0.4:
                return "Traditional Krar"
            else:
                return "Meditative Krar"
        return "Ethiopian Krar"
    
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
        Generate krar accompaniment for a song section.
        
        Args:
            context: Performance context with key, tempo, etc.
            section: Song section to perform
            personality: Optional override personality
            
        Returns:
            PerformanceResult with generated notes
        """
        active_personality = personality or self._personality or KRAR_PRESETS["traditional_azmari"]
        self._decisions_made = []
        
        # Determine qenet mode from context
        qenet_name = self._select_qenet(context)
        self._decisions_made.append(f"qenet_mode:{qenet_name}")
        
        # Get scale for the key
        root_pitch = self._get_root_pitch(context.key or "C")
        scale = self._qenet.get_scale_for_key(qenet_name, root_pitch)
        
        # Set tuning based on qenet
        self._current_tuning = KrarTuning.get_tuning_for_qenet(qenet_name)
        # Transpose to match key
        transpose = root_pitch - 64  # Relative to E4
        self._current_tuning = KrarTuning.transpose_tuning(self._current_tuning, transpose)
        self._decisions_made.append(f"tuning:transposed_{transpose}")
        
        # Select pattern based on section type and personality
        pattern_func = self._select_pattern(section, active_personality)
        self._decisions_made.append(f"pattern:{pattern_func.__name__}")
        
        # Generate notes
        notes = self._generate_section_notes(
            section, context, active_personality, pattern_func, scale
        )
        
        # Apply humanization
        notes = self._apply_humanization(notes, active_personality, context.bpm or 120)
        
        # Convert to NoteEvents
        note_events = self._convert_to_note_events(notes)
        
        return PerformanceResult(
            notes=note_events,
            decisions_made=self._decisions_made.copy(),
            confidence=0.85,
            metadata={
                "qenet": qenet_name,
                "tuning": self._current_tuning,
                "technique_count": len(set(self._decisions_made))
            }
        )
    
    def _select_qenet(self, context: PerformanceContext) -> str:
        """Select appropriate qenet mode based on context."""
        genre = (context.genre or "").lower()
        mood = (context.mood or "").lower()
        
        # Genre-based selection
        if "eskista" in genre:
            return random.choice(["tizita_major", "bati_major"])
        elif "ethio" in genre or "jazz" in genre:
            return random.choice(["tizita_major", "tizita_minor", "ambassel"])
        elif "traditional" in genre or "azmari" in genre:
            return "tizita_minor"  # Classic nostalgic sound
        
        # Mood-based selection
        if "sad" in mood or "melancholic" in mood or "nostalgic" in mood:
            return "tizita_minor"
        elif "happy" in mood or "uplifting" in mood or "energetic" in mood:
            return "bati_major"
        elif "meditative" in mood or "spiritual" in mood:
            return "ambassel"
        
        # Default to Tizita major (most common)
        return "tizita_major"
    
    def _get_root_pitch(self, key: str) -> int:
        """Convert key string to root MIDI pitch."""
        key_upper = key.upper().strip()
        
        # Handle flat/sharp notation
        key_map = {
            "C": 60, "C#": 61, "DB": 61,
            "D": 62, "D#": 63, "EB": 63,
            "E": 64, "F": 65, "F#": 66, "GB": 66,
            "G": 67, "G#": 68, "AB": 68,
            "A": 69, "A#": 70, "BB": 70,
            "B": 71
        }
        
        # Extract note name (strip minor/major)
        for suffix in ["MINOR", "MAJOR", "MIN", "MAJ", "M", " "]:
            key_upper = key_upper.replace(suffix, "")
        
        return key_map.get(key_upper.strip(), 60)
    
    def _select_pattern(
        self, 
        section: SongSection, 
        personality: AgentPersonality
    ) -> callable:
        """Select krar pattern based on section and personality."""
        section_type = section.type if hasattr(section, 'type') else SectionType.VERSE
        energy = personality.aggressiveness
        
        # High energy sections
        if section_type in [SectionType.CHORUS, SectionType.DROP]:
            if energy > 0.6:
                return KrarPatterns.eskista_dance_pattern
            else:
                return KrarPatterns.tizita_arpeggio_pattern
        
        # Low energy/meditative sections
        elif section_type in [SectionType.INTRO, SectionType.OUTRO, SectionType.BRIDGE]:
            if personality.complexity < 0.4:
                return KrarPatterns.ambassel_meditative_pattern
            else:
                return KrarPatterns.tizita_arpeggio_pattern
        
        # Default verse pattern
        if "drone" in personality.signature_patterns:
            return KrarPatterns.ambassel_meditative_pattern
        elif "dance" in str(personality.signature_patterns):
            return KrarPatterns.eskista_dance_pattern
        
        return KrarPatterns.tizita_arpeggio_pattern
    
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
        start_bar = section.start_bar if hasattr(section, 'start_bar') else 0
        num_bars = section.bars if hasattr(section, 'bars') else 4
        
        # Generate pattern for each bar
        for bar in range(num_bars):
            bar_offset = bar * TICKS_PER_BAR_4_4
            
            # Get pattern notes
            if pattern_func == KrarPatterns.eskista_dance_pattern:
                pattern_notes = pattern_func(self._current_tuning, 1, personality.aggressiveness)
            elif pattern_func == KrarPatterns.ambassel_meditative_pattern:
                pattern_notes = pattern_func(self._current_tuning, 1)
            else:
                pattern_notes = pattern_func(self._current_tuning, 1, "8th")
            
            # Add variation based on personality
            if random.random() < personality.variation_tendency:
                pattern_notes = self._add_variation(pattern_notes, personality, scale)
            
            # Add fill at end of phrases (every 4 bars)
            if (bar + 1) % 4 == 0 and random.random() < personality.fill_frequency:
                fill_notes = self._generate_fill(personality, scale)
                pattern_notes.extend(fill_notes)
            
            # Offset notes to bar position
            for tick, dur, pitch, vel in pattern_notes:
                notes.append((bar_offset + tick, dur, pitch, vel))
        
        return notes
    
    def _add_variation(
        self,
        notes: List[Tuple[int, int, int, int]],
        personality: AgentPersonality,
        scale: List[int]
    ) -> List[Tuple[int, int, int, int]]:
        """Add musical variation to pattern."""
        varied = []
        
        for tick, dur, pitch, vel in notes:
            # Occasionally substitute with scale tone
            if random.random() < personality.ghost_note_density * 0.3:
                # Add grace note before
                grace_pitch = random.choice(scale) if scale else pitch + 2
                varied.append((max(0, tick - TICKS_PER_16TH // 2), TICKS_PER_16TH // 2, grace_pitch, vel - 15))
            
            # Velocity variation
            vel = humanize_velocity(vel, personality.complexity * 0.15)
            
            # Occasional octave displacement
            if random.random() < personality.complexity * 0.1:
                pitch = pitch + (12 if random.random() > 0.5 else -12)
                pitch = max(36, min(96, pitch))  # Keep in range
            
            varied.append((tick, dur, pitch, vel))
        
        return varied
    
    def _generate_fill(
        self,
        personality: AgentPersonality,
        scale: List[int]
    ) -> List[Tuple[int, int, int, int]]:
        """Generate a fill pattern."""
        fill = []
        
        # Simple descending arpeggio fill
        fill_pitches = scale[:4] if len(scale) >= 4 else scale
        tick = TICKS_PER_BEAT * 3  # Start on beat 4
        
        for pitch in fill_pitches:
            vel = humanize_velocity(75, 0.1)
            fill.append((tick, TICKS_PER_16TH, pitch, vel))
            tick += TICKS_PER_16TH
        
        self._decisions_made.append("fill:descending_arpeggio")
        return fill
    
    def _apply_humanization(
        self,
        notes: List[Tuple[int, int, int, int]],
        personality: AgentPersonality,
        bpm: float
    ) -> List[Tuple[int, int, int, int]]:
        """Apply timing and velocity humanization."""
        humanized = []
        
        for tick, dur, pitch, vel in notes:
            # Timing variation
            timing_offset = humanize_timing(tick, variation=0.03 + personality.push_pull * 0.02)
            tick = max(0, int(timing_offset))
            
            # Velocity already humanized, but add personality push
            if personality.push_pull > 0:
                vel = min(127, vel + int(personality.push_pull * 10))
            
            humanized.append((tick, dur, pitch, vel))
        
        return humanized
    
    def react_to_cue(
        self,
        cue_type: str,
        context: PerformanceContext
    ) -> List[NoteEvent]:
        """
        React to a performance cue with appropriate krar response.
        
        Cue types:
            - "fill": Ornamental krar fill using trills and grace notes
            - "stop": Dampened strings, silence
            - "build": Increasing tremolo intensity
            - "drop": Sudden dynamic drop to soft strumming
            - "accent": Strong chord strum
        """
        tpb = context.ticks_per_beat
        notes = []
        
        # Get current qenet scale
        mode_map = {
            KrarTuning.TIZITA_TUNING: "tizita_major",
            KrarTuning.AMBASSEL_TUNING: "ambassel",
            KrarTuning.BATI_TUNING: "bati_major",
            KrarTuning.ANCHIHOYE_TUNING: "anchihoye",
        }
        mode_name = mode_map.get(self._current_tuning, "tizita_major")
        scale = self._qenet.get_scale(context.key, mode_name)
        
        # Base velocity from personality
        base_vel = 80
        if self._personality:
            base_vel = int(60 + self._personality.intensity * 50)
        
        if cue_type == "fill":
            # Ornamental fill: rapid trill on two adjacent scale tones
            if len(scale) >= 2:
                for i in range(8):
                    pitch = scale[i % 2] + 60
                    tick = i * (tpb // 8)
                    notes.append(NoteEvent(
                        tick=tick,
                        pitch=pitch,
                        velocity=base_vel - (i * 3),
                        duration=tpb // 8,
                        channel=0
                    ))
        
        elif cue_type == "stop":
            # Muted stop - short dampened chord
            for i, interval in enumerate(scale[:4]):
                notes.append(NoteEvent(
                    tick=0,
                    pitch=60 + interval,
                    velocity=40,
                    duration=tpb // 8,
                    channel=0
                ))
        
        elif cue_type == "build":
            # Building tremolo across beat
            for beat_div in range(16):
                tick = beat_div * (tpb // 4)
                vel = min(127, 50 + beat_div * 5)
                # Alternate between root and fifth
                pitch_idx = beat_div % 2
                pitches = [scale[0], scale[4] if len(scale) > 4 else scale[2]]
                notes.append(NoteEvent(
                    tick=tick,
                    pitch=60 + pitches[pitch_idx],
                    velocity=vel,
                    duration=tpb // 4,
                    channel=0
                ))
        
        elif cue_type == "drop":
            # Soft single chord
            for i, interval in enumerate(scale[:3]):
                notes.append(NoteEvent(
                    tick=i * 10,  # Slight spread
                    pitch=60 + interval,
                    velocity=35,
                    duration=tpb * 2,
                    channel=0
                ))
        
        elif cue_type == "accent":
            # Strong strummed chord
            for i, interval in enumerate(scale[:5]):
                notes.append(NoteEvent(
                    tick=i * 8,  # Fast strum
                    pitch=60 + interval,
                    velocity=min(127, base_vel + 20),
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
                channel=0  # Will be assigned during rendering
            )
            events.append(event)
        
        return events


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    "KrarAgent",
    "KrarTuning",
    "KrarTechniques",
    "KrarPatterns",
    "KRAR_PRESETS",
]
