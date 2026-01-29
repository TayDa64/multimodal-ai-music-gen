"""
KeberoAgent - Masterclass Ethiopian Drum Performer

This module implements a professional kebero (ከበሮ) player agent with deep knowledge of:
- Ethiopian Rhythmic Systems: Eskista (6/8), traditional 12/8, Ethio-jazz patterns
- Playing Techniques: Bass hit, slap, muted, edge tones, rolls
- Ensemble Patterns: Lead kebero vs support patterns
- Dance Accompaniment: Shoulder dance (eskista), folk dances

The KeberoAgent is designed to generate authentic Ethiopian drum patterns
that drive traditional ensembles and modern Ethio-jazz/funk arrangements.

Physical Instrument Reference:
    The kebero is a double-headed conical drum central to Ethiopian music:
    - Double-headed with goatskin membranes
    - Conical wooden body
    - Played with hands (no sticks)
    - Bass side: Large head, deep tone
    - Slap side: Smaller head, higher pitch
    
Musical Characteristics:
    - Polyrhythmic patterns (layered rhythms)
    - 6/8 and 12/8 time signatures common
    - Call-and-response with dancers
    - Bass provides downbeat anchor
    - Slaps drive rhythmic complexity
    - Muted hits for texture

Architecture Notes:
    This is a Stage 1 (offline) implementation with comprehensive Ethiopian
    rhythm theory. Stage 2 will add API-backed generation for creative variation.

Example:
    ```python
    from multimodal_gen.agents.performers import KeberoAgent
    from multimodal_gen.agents import PerformanceContext, KEBERO_PRESETS
    
    kebero = KeberoAgent()
    kebero.set_personality(KEBERO_PRESETS['eskista_lead'])
    
    result = kebero.perform(context, section)
    print(f"Generated {len(result.notes)} kebero hits")
    print(f"Rhythm style: {result.decisions_made[0]}")
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
)

logger = logging.getLogger(__name__)


# =============================================================================
# KEBERO MIDI MAPPING
# =============================================================================

# MIDI pitches for kebero sounds (matching assets_gen.py)
KEBERO_BASS = 50       # Deep bass hit
KEBERO_SLAP = 51       # Higher pitched slap
KEBERO_MUTED = 52      # Muted/dampened hit
KEBERO_EDGE = 53       # Edge tone (rim-like)
ATAMO_HIT = 54         # Atamo (small drum) for ensemble


# =============================================================================
# KEBERO PERSONALITY PRESETS
# =============================================================================

KEBERO_PRESETS: Dict[str, AgentPersonality] = {
    "eskista_lead": AgentPersonality(
        aggressiveness=0.75,
        complexity=0.65,
        consistency=0.8,
        push_pull=0.03,  # Slightly ahead driving the dance
        swing_affinity=0.4,  # Ethiopian groove feel
        fill_frequency=0.5,
        ghost_note_density=0.5,
        variation_tendency=0.45,
        signature_patterns=["eskista_6_8", "shoulder_accent", "dance_drive"]
    ),
    
    "traditional_support": AgentPersonality(
        aggressiveness=0.5,
        complexity=0.4,
        consistency=0.9,
        push_pull=0.0,
        swing_affinity=0.35,
        fill_frequency=0.25,
        ghost_note_density=0.3,
        variation_tendency=0.25,
        signature_patterns=["steady_pulse", "bass_anchor", "supportive_slap"]
    ),
    
    "ethio_jazz_groove": AgentPersonality(
        aggressiveness=0.6,
        complexity=0.7,
        consistency=0.75,
        push_pull=-0.02,  # Slightly behind for jazz pocket
        swing_affinity=0.5,
        fill_frequency=0.4,
        ghost_note_density=0.6,
        variation_tendency=0.55,
        signature_patterns=["jazz_swing", "syncopated_slap", "dynamic_bass"]
    ),
    
    "ceremonial_ritualistic": AgentPersonality(
        aggressiveness=0.45,
        complexity=0.35,
        consistency=0.95,
        push_pull=-0.01,
        swing_affinity=0.2,
        fill_frequency=0.15,
        ghost_note_density=0.25,
        variation_tendency=0.15,
        signature_patterns=["ritual_pulse", "sacred_accent", "processional"]
    ),
    
    "energetic_folk": AgentPersonality(
        aggressiveness=0.8,
        complexity=0.55,
        consistency=0.85,
        push_pull=0.04,  # Pushing forward
        swing_affinity=0.3,
        fill_frequency=0.55,
        ghost_note_density=0.45,
        variation_tendency=0.4,
        signature_patterns=["folk_drive", "call_response", "celebration"]
    ),
}


# =============================================================================
# KEBERO TECHNIQUE CLASSES
# =============================================================================

class KeberoHitTypes:
    """
    Different hit types on the kebero drum.
    
    Each hit type has distinct characteristics:
    - Bass: Deep, resonant, long decay
    - Slap: Sharp, high, quick decay
    - Muted: Dampened, short, textural
    - Edge: Rim tone, woody character
    """
    
    BASS = "bass"
    SLAP = "slap"
    MUTED = "muted"
    EDGE = "edge"
    
    MIDI_MAP = {
        BASS: KEBERO_BASS,
        SLAP: KEBERO_SLAP,
        MUTED: KEBERO_MUTED,
        EDGE: KEBERO_EDGE,
    }
    
    # Typical velocity ranges for each hit type
    VELOCITY_RANGES = {
        BASS: (70, 110),      # Bass is strong
        SLAP: (75, 127),      # Slaps can be very loud
        MUTED: (50, 85),      # Muted is softer
        EDGE: (55, 90),       # Edge is moderate
    }
    
    @classmethod
    def get_pitch(cls, hit_type: str) -> int:
        """Get MIDI pitch for hit type."""
        return cls.MIDI_MAP.get(hit_type, KEBERO_BASS)
    
    @classmethod
    def get_velocity(cls, hit_type: str, intensity: float = 0.7) -> int:
        """Get velocity for hit type at given intensity (0-1)."""
        low, high = cls.VELOCITY_RANGES.get(hit_type, (60, 100))
        return int(low + (high - low) * intensity)


class KeberoTechniques:
    """
    Kebero playing technique patterns.
    
    These represent common playing techniques:
    - Single hits: Bass, slap, muted
    - Rolls: Rapid alternating hits
    - Flams: Grace note before main hit
    - Accents: Emphasized beats
    """
    
    @staticmethod
    def generate_bass_hit(
        tick: int,
        velocity: int = 90,
        duration: int = TICKS_PER_8TH
    ) -> Tuple[int, int, int, int]:
        """Generate single bass hit."""
        return (tick, duration, KEBERO_BASS, velocity)
    
    @staticmethod
    def generate_slap_hit(
        tick: int,
        velocity: int = 95,
        duration: int = TICKS_PER_16TH
    ) -> Tuple[int, int, int, int]:
        """Generate single slap hit."""
        return (tick, duration, KEBERO_SLAP, velocity)
    
    @staticmethod
    def generate_muted_hit(
        tick: int,
        velocity: int = 70,
        duration: int = TICKS_PER_16TH
    ) -> Tuple[int, int, int, int]:
        """Generate single muted hit."""
        return (tick, duration, KEBERO_MUTED, velocity)
    
    @staticmethod
    def generate_roll(
        start_tick: int,
        duration_ticks: int,
        hit_type: str = "slap",
        velocity_start: int = 80,
        velocity_end: int = 100,
        crescendo: bool = True
    ) -> List[Tuple[int, int, int, int]]:
        """
        Generate a roll (rapid repeated hits).
        
        Args:
            start_tick: Starting tick
            duration_ticks: Total duration
            hit_type: Type of hit for roll
            velocity_start/end: Velocity envelope
            crescendo: If True, build up; if False, decay
            
        Returns:
            List of (tick, duration, pitch, velocity)
        """
        notes = []
        pitch = KeberoHitTypes.get_pitch(hit_type)
        
        # Roll uses 32nd notes typically
        roll_interval = TICKS_PER_16TH // 2
        num_hits = duration_ticks // roll_interval
        
        for i in range(num_hits):
            tick = start_tick + (i * roll_interval)
            
            # Velocity envelope
            progress = i / max(1, num_hits - 1)
            if crescendo:
                vel = int(velocity_start + (velocity_end - velocity_start) * progress)
            else:
                vel = int(velocity_end + (velocity_start - velocity_end) * progress)
            
            vel = humanize_velocity(vel, 0.08)
            notes.append((tick, roll_interval, pitch, vel))
        
        return notes
    
    @staticmethod
    def generate_flam(
        tick: int,
        main_hit_type: str = "bass",
        velocity: int = 90
    ) -> List[Tuple[int, int, int, int]]:
        """
        Generate a flam (grace note before main hit).
        
        Args:
            tick: Main hit tick
            main_hit_type: Type of main hit
            velocity: Main hit velocity
            
        Returns:
            List of (tick, duration, pitch, velocity) - grace + main
        """
        notes = []
        main_pitch = KeberoHitTypes.get_pitch(main_hit_type)
        
        # Grace note (quieter, just before main)
        grace_tick = max(0, tick - TICKS_PER_16TH // 2)
        grace_vel = int(velocity * 0.6)
        grace_pitch = KEBERO_SLAP if main_hit_type == "bass" else KEBERO_MUTED
        notes.append((grace_tick, TICKS_PER_16TH // 2, grace_pitch, grace_vel))
        
        # Main hit
        notes.append((tick, TICKS_PER_8TH, main_pitch, velocity))
        
        return notes
    
    @staticmethod
    def generate_accent_pattern(
        tick: int,
        pattern: List[str],
        velocity_base: int = 85
    ) -> List[Tuple[int, int, int, int]]:
        """
        Generate a quick accent pattern.
        
        Args:
            tick: Starting tick
            pattern: List of hit types (e.g., ["bass", "slap", "slap"])
            velocity_base: Base velocity
            
        Returns:
            List of (tick, duration, pitch, velocity)
        """
        notes = []
        interval = TICKS_PER_16TH
        
        for i, hit_type in enumerate(pattern):
            hit_tick = tick + (i * interval)
            pitch = KeberoHitTypes.get_pitch(hit_type)
            vel = humanize_velocity(velocity_base, 0.1)
            # Accent first beat
            if i == 0:
                vel = min(127, vel + 10)
            notes.append((hit_tick, interval, pitch, vel))
        
        return notes


# =============================================================================
# KEBERO RHYTHM PATTERNS
# =============================================================================

class KeberoPatterns:
    """
    Common kebero rhythm patterns from Ethiopian music.
    
    Patterns organized by style:
    - Eskista: Fast 6/8 shoulder dance
    - Traditional: 12/8 ceremonial patterns
    - Ethio-jazz: Syncopated groove patterns
    - Folk: Regional dance patterns
    """
    
    @staticmethod
    def eskista_basic(
        bars: int = 1,
        energy: float = 0.7
    ) -> List[Tuple[int, int, int, int]]:
        """
        Basic Eskista (shoulder dance) pattern in 6/8.
        
        Eskista is characterized by its driving 6/8 feel
        with emphasis on beats 1 and 4 (in 8th notes).
        """
        notes = []
        vel = KeberoHitTypes.get_velocity("bass", energy)
        
        # 6/8 pattern: |B . S . s . |
        # B=bass on 1, S=slap on 4, s=ghost slap on 6
        for bar in range(bars):
            bar_offset = bar * TICKS_PER_BAR_4_4
            
            # Beat 1: Bass (strong downbeat)
            notes.append((bar_offset, TICKS_PER_8TH, KEBERO_BASS, vel))
            
            # Beat 3 (compound beat 2): Light slap
            notes.append((
                bar_offset + TICKS_PER_8TH * 2,
                TICKS_PER_16TH,
                KEBERO_SLAP,
                humanize_velocity(vel - 20, 0.1)
            ))
            
            # Beat 4 (compound beat 2.5): Accented slap
            notes.append((
                bar_offset + TICKS_PER_8TH * 3,
                TICKS_PER_8TH,
                KEBERO_SLAP,
                humanize_velocity(vel, 0.08)
            ))
            
            # Beat 5: Ghost muted
            if energy > 0.5:
                notes.append((
                    bar_offset + TICKS_PER_8TH * 4,
                    TICKS_PER_16TH,
                    KEBERO_MUTED,
                    humanize_velocity(vel - 30, 0.1)
                ))
            
            # Beat 6: Setup for next bar
            notes.append((
                bar_offset + TICKS_PER_8TH * 5,
                TICKS_PER_16TH,
                KEBERO_SLAP,
                humanize_velocity(vel - 15, 0.1)
            ))
        
        return notes
    
    @staticmethod
    def eskista_intense(
        bars: int = 1,
        energy: float = 0.85
    ) -> List[Tuple[int, int, int, int]]:
        """
        Intense Eskista pattern with more complexity.
        
        Used during peak dance moments with rapid slaps
        and driving bass.
        """
        notes = []
        vel = KeberoHitTypes.get_velocity("bass", energy)
        
        for bar in range(bars):
            bar_offset = bar * TICKS_PER_BAR_4_4
            
            # Strong bass on 1
            flam = KeberoTechniques.generate_flam(bar_offset, "bass", vel + 5)
            notes.extend(flam)
            
            # Rapid slap pattern on 2-3
            slap_pattern = [
                (TICKS_PER_8TH, KEBERO_SLAP, vel - 10),
                (TICKS_PER_8TH + TICKS_PER_16TH, KEBERO_SLAP, vel - 15),
                (TICKS_PER_8TH * 2, KEBERO_MUTED, vel - 20),
            ]
            for offset, pitch, v in slap_pattern:
                notes.append((bar_offset + offset, TICKS_PER_16TH, pitch, humanize_velocity(v, 0.1)))
            
            # Strong accent on 4
            notes.append((bar_offset + TICKS_PER_8TH * 3, TICKS_PER_8TH, KEBERO_BASS, vel))
            
            # Rapid ghost slaps 5-6
            for i in range(3):
                tick = bar_offset + TICKS_PER_8TH * 4 + (i * TICKS_PER_16TH)
                notes.append((tick, TICKS_PER_16TH, KEBERO_SLAP, humanize_velocity(vel - 25, 0.1)))
        
        return notes
    
    @staticmethod
    def traditional_12_8(
        bars: int = 1,
        energy: float = 0.6
    ) -> List[Tuple[int, int, int, int]]:
        """
        Traditional Ethiopian 12/8 pattern.
        
        Used in ceremonial and religious contexts,
        with steady bass and supportive slaps.
        """
        notes = []
        vel = KeberoHitTypes.get_velocity("bass", energy)
        
        # 12/8: 4 groups of 3 eighth notes
        # Pattern: |B . . S . . B . . S . . |
        eighth_duration = TICKS_PER_BEAT // 3  # Compound time
        
        for bar in range(bars):
            bar_offset = bar * TICKS_PER_BAR_4_4
            
            # Group 1: Bass
            notes.append((bar_offset, eighth_duration, KEBERO_BASS, vel))
            notes.append((bar_offset + eighth_duration * 2, eighth_duration, KEBERO_MUTED, vel - 25))
            
            # Group 2: Slap
            notes.append((bar_offset + eighth_duration * 3, eighth_duration, KEBERO_SLAP, vel - 10))
            notes.append((bar_offset + eighth_duration * 5, eighth_duration, KEBERO_MUTED, vel - 30))
            
            # Group 3: Bass
            notes.append((bar_offset + eighth_duration * 6, eighth_duration, KEBERO_BASS, vel - 5))
            
            # Group 4: Slap to setup
            notes.append((bar_offset + eighth_duration * 9, eighth_duration, KEBERO_SLAP, vel - 15))
            notes.append((bar_offset + eighth_duration * 11, eighth_duration, KEBERO_SLAP, vel - 20))
        
        return notes
    
    @staticmethod
    def ethio_jazz_groove(
        bars: int = 1,
        energy: float = 0.65
    ) -> List[Tuple[int, int, int, int]]:
        """
        Ethio-jazz influenced groove pattern.
        
        Combines Ethiopian rhythm with jazz pocket,
        featuring syncopation and ghost notes.
        """
        notes = []
        vel = KeberoHitTypes.get_velocity("bass", energy)
        
        for bar in range(bars):
            bar_offset = bar * TICKS_PER_BAR_4_4
            
            # Beat 1: Bass with slight delay (pocket)
            notes.append((bar_offset + TICKS_PER_16TH // 2, TICKS_PER_8TH, KEBERO_BASS, vel))
            
            # Syncopated slap before beat 2
            notes.append((
                bar_offset + TICKS_PER_BEAT - TICKS_PER_16TH,
                TICKS_PER_16TH,
                KEBERO_SLAP,
                humanize_velocity(vel - 15, 0.1)
            ))
            
            # Beat 2: Ghost bass
            notes.append((bar_offset + TICKS_PER_BEAT, TICKS_PER_16TH, KEBERO_MUTED, vel - 30))
            
            # "&" of 2: Accented slap
            notes.append((
                bar_offset + TICKS_PER_BEAT + TICKS_PER_8TH,
                TICKS_PER_8TH,
                KEBERO_SLAP,
                vel
            ))
            
            # Beat 3: Strong bass
            notes.append((bar_offset + TICKS_PER_BEAT * 2, TICKS_PER_8TH, KEBERO_BASS, vel + 5))
            
            # Syncopated ghost notes
            notes.append((
                bar_offset + TICKS_PER_BEAT * 2 + TICKS_PER_8TH + TICKS_PER_16TH,
                TICKS_PER_16TH,
                KEBERO_MUTED,
                vel - 35
            ))
            
            # Beat 4: Light slap
            notes.append((bar_offset + TICKS_PER_BEAT * 3, TICKS_PER_16TH, KEBERO_SLAP, vel - 20))
            
            # "&" of 4: Setup slap
            notes.append((
                bar_offset + TICKS_PER_BEAT * 3 + TICKS_PER_8TH,
                TICKS_PER_8TH,
                KEBERO_SLAP,
                vel - 10
            ))
        
        return notes
    
    @staticmethod
    def processional_steady(
        bars: int = 1,
        energy: float = 0.5
    ) -> List[Tuple[int, int, int, int]]:
        """
        Steady processional pattern for ceremonies.
        
        Simple, dignified pulse suitable for
        religious processions and solemn events.
        """
        notes = []
        vel = KeberoHitTypes.get_velocity("bass", energy)
        
        for bar in range(bars):
            bar_offset = bar * TICKS_PER_BAR_4_4
            
            # Simple 4/4: Bass on 1 and 3, slap on 2 and 4
            notes.append((bar_offset, TICKS_PER_BEAT, KEBERO_BASS, vel))
            notes.append((bar_offset + TICKS_PER_BEAT, TICKS_PER_8TH, KEBERO_SLAP, vel - 15))
            notes.append((bar_offset + TICKS_PER_BEAT * 2, TICKS_PER_BEAT, KEBERO_BASS, vel - 5))
            notes.append((bar_offset + TICKS_PER_BEAT * 3, TICKS_PER_8TH, KEBERO_SLAP, vel - 15))
        
        return notes
    
    @staticmethod
    def fill_energetic(energy: float = 0.8) -> List[Tuple[int, int, int, int]]:
        """
        Energetic fill pattern (1 beat).
        
        Used at phrase endings to build energy.
        """
        notes = []
        vel = KeberoHitTypes.get_velocity("slap", energy)
        
        # Rapid slap roll building to bass hit
        roll = KeberoTechniques.generate_roll(
            0, TICKS_PER_BEAT - TICKS_PER_16TH,
            "slap", vel - 20, vel, crescendo=True
        )
        notes.extend(roll)
        
        # Final bass hit
        notes.append((TICKS_PER_BEAT - TICKS_PER_16TH, TICKS_PER_16TH, KEBERO_BASS, vel + 10))
        
        return notes
    
    @staticmethod
    def fill_transitional(energy: float = 0.7) -> List[Tuple[int, int, int, int]]:
        """
        Transitional fill (2 beats).
        
        Used for section transitions.
        """
        notes = []
        vel = KeberoHitTypes.get_velocity("bass", energy)
        
        # Beat 1: Bass with flam
        flam = KeberoTechniques.generate_flam(0, "bass", vel)
        notes.extend(flam)
        
        # Beat 2: Descending pattern
        pattern = KeberoTechniques.generate_accent_pattern(
            TICKS_PER_BEAT,
            ["slap", "slap", "muted", "bass"],
            vel - 5
        )
        notes.extend(pattern)
        
        return notes


# =============================================================================
# KEBERO PERFORMER AGENT
# =============================================================================

class KeberoAgent(IPerformerAgent):
    """
    Masterclass Ethiopian Kebero (Drum) performer agent.
    
    Generates authentic kebero patterns with deep knowledge
    of Ethiopian rhythm systems, playing techniques, and
    stylistic variations from eskista to Ethio-jazz.
    
    Attributes:
        role: Fixed as DRUMS (rhythm foundation)
        personality: Current personality settings
        _decisions_made: Record of performance decisions
    """
    
    def __init__(self):
        """Initialize KeberoAgent with Ethiopian rhythm knowledge."""
        self._personality: Optional[AgentPersonality] = None
        self._decisions_made: List[str] = []
    
    @property
    def role(self) -> AgentRole:
        """Kebero provides rhythm foundation."""
        return AgentRole.DRUMS
    
    @property
    def name(self) -> str:
        """Human-readable name for this kebero performer."""
        if self._personality:
            intensity = self._personality.intensity
            if intensity > 0.7:
                return "Eskista Kebero"
            elif intensity > 0.4:
                return "Traditional Kebero"
            else:
                return "Ceremonial Kebero"
        return "Ethiopian Kebero"
    
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
        Generate kebero pattern for a song section.
        
        Args:
            context: Performance context with tempo, genre, etc.
            section: Song section to perform
            personality: Optional override personality
            
        Returns:
            PerformanceResult with generated notes
        """
        active_personality = personality or self._personality or KEBERO_PRESETS["traditional_support"]
        self._decisions_made = []
        
        # Determine rhythm style from context
        rhythm_style = self._select_rhythm_style(context)
        self._decisions_made.append(f"rhythm_style:{rhythm_style}")
        
        # Select pattern based on section and personality
        pattern_func = self._select_pattern(section, active_personality, rhythm_style)
        self._decisions_made.append(f"pattern:{pattern_func.__name__}")
        
        # Determine energy level
        energy = self._calculate_energy(section, active_personality)
        self._decisions_made.append(f"energy:{energy:.2f}")
        
        # Generate notes
        notes = self._generate_section_notes(
            section, context, active_personality, pattern_func, energy
        )
        
        # Apply humanization
        notes = self._apply_humanization(notes, active_personality, context.bpm or 120)
        
        # Convert to NoteEvents
        note_events = self._convert_to_note_events(notes)
        
        return PerformanceResult(
            notes=note_events,
            decisions_made=self._decisions_made.copy(),
            confidence=0.88,
            metadata={
                "rhythm_style": rhythm_style,
                "energy": energy,
                "hit_count": len(note_events)
            }
        )
    
    def _select_rhythm_style(self, context: PerformanceContext) -> str:
        """Select rhythm style based on context."""
        genre = (context.genre or "").lower()
        mood = (context.mood or "").lower()
        bpm = context.bpm or 120
        
        # Genre-based selection
        if "eskista" in genre:
            return "eskista"
        elif "ethio" in genre and ("jazz" in genre or "funk" in genre):
            return "ethio_jazz"
        elif "traditional" in genre or "ceremonial" in genre or "religious" in genre:
            return "traditional_12_8"
        
        # BPM-based inference
        if bpm >= 130:
            return "eskista"  # Fast = dance
        elif bpm <= 80:
            return "processional"  # Slow = ceremonial
        
        # Mood-based
        if "energetic" in mood or "dance" in mood or "uplifting" in mood:
            return "eskista"
        elif "contemplative" in mood or "spiritual" in mood:
            return "processional"
        elif "groovy" in mood or "funky" in mood:
            return "ethio_jazz"
        
        # Default based on moderate tempo
        return "traditional_12_8"
    
    def _select_pattern(
        self,
        section: SongSection,
        personality: AgentPersonality,
        rhythm_style: str
    ) -> callable:
        """Select kebero pattern based on section and personality."""
        section_type = section.type if hasattr(section, 'type') else SectionType.VERSE
        
        # Map rhythm styles to pattern functions
        pattern_map = {
            "eskista": KeberoPatterns.eskista_basic,
            "eskista_intense": KeberoPatterns.eskista_intense,
            "traditional_12_8": KeberoPatterns.traditional_12_8,
            "ethio_jazz": KeberoPatterns.ethio_jazz_groove,
            "processional": KeberoPatterns.processional_steady,
        }
        
        # Section-based adjustments
        if section_type in [SectionType.CHORUS, SectionType.DROP]:
            if rhythm_style == "eskista":
                return KeberoPatterns.eskista_intense
            elif personality.aggressiveness > 0.7:
                return KeberoPatterns.eskista_intense
        
        elif section_type in [SectionType.INTRO, SectionType.OUTRO]:
            if personality.complexity < 0.4:
                return KeberoPatterns.processional_steady
        
        # Use rhythm style pattern
        return pattern_map.get(rhythm_style, KeberoPatterns.traditional_12_8)
    
    def _calculate_energy(
        self,
        section: SongSection,
        personality: AgentPersonality
    ) -> float:
        """Calculate energy level for the section."""
        base_energy = personality.aggressiveness
        
        section_type = section.type if hasattr(section, 'type') else SectionType.VERSE
        
        # Section-based modifiers
        section_energy_map = {
            SectionType.INTRO: -0.15,
            SectionType.VERSE: 0.0,
            SectionType.PRECHORUS: 0.1,
            SectionType.CHORUS: 0.2,
            SectionType.DROP: 0.25,
            SectionType.BRIDGE: -0.1,
            SectionType.OUTRO: -0.2,
        }
        
        modifier = section_energy_map.get(section_type, 0.0)
        energy = max(0.3, min(1.0, base_energy + modifier))
        
        return energy
    
    def _generate_section_notes(
        self,
        section: SongSection,
        context: PerformanceContext,
        personality: AgentPersonality,
        pattern_func: callable,
        energy: float
    ) -> List[Tuple[int, int, int, int]]:
        """Generate notes for the section."""
        notes = []
        
        num_bars = section.bars if hasattr(section, 'bars') else 4
        
        for bar in range(num_bars):
            bar_offset = bar * TICKS_PER_BAR_4_4
            
            # Get pattern for this bar
            pattern_notes = pattern_func(1, energy)
            
            # Add variation on some bars
            if random.random() < personality.variation_tendency * 0.5:
                # Slight variation in pattern
                pattern_notes = self._add_variation(pattern_notes, personality)
            
            # Add fill at phrase endings (every 4 bars)
            if (bar + 1) % 4 == 0 and random.random() < personality.fill_frequency:
                fill_notes = self._generate_fill(personality, energy)
                # Place fill at end of bar
                fill_offset = bar_offset + TICKS_PER_BEAT * 3
                for tick, dur, pitch, vel in fill_notes:
                    notes.append((fill_offset + tick, dur, pitch, vel))
                self._decisions_made.append(f"fill:bar_{bar+1}")
            
            # Offset pattern notes to bar position
            for tick, dur, pitch, vel in pattern_notes:
                notes.append((bar_offset + tick, dur, pitch, vel))
        
        return notes
    
    def _add_variation(
        self,
        notes: List[Tuple[int, int, int, int]],
        personality: AgentPersonality
    ) -> List[Tuple[int, int, int, int]]:
        """Add musical variation to pattern."""
        varied = []
        
        for tick, dur, pitch, vel in notes:
            # Occasionally add ghost note
            if random.random() < personality.ghost_note_density * 0.3:
                ghost_vel = max(30, vel - 30)
                varied.append((max(0, tick - TICKS_PER_16TH), TICKS_PER_16TH // 2, KEBERO_MUTED, ghost_vel))
            
            # Velocity variation
            vel = humanize_velocity(vel, personality.complexity * 0.12)
            
            varied.append((tick, dur, pitch, vel))
        
        return varied
    
    def _generate_fill(
        self,
        personality: AgentPersonality,
        energy: float
    ) -> List[Tuple[int, int, int, int]]:
        """Generate a fill pattern."""
        if personality.aggressiveness > 0.6:
            return KeberoPatterns.fill_energetic(energy)
        else:
            return KeberoPatterns.fill_transitional(energy)
    
    def _apply_humanization(
        self,
        notes: List[Tuple[int, int, int, int]],
        personality: AgentPersonality,
        bpm: float
    ) -> List[Tuple[int, int, int, int]]:
        """Apply timing and velocity humanization."""
        humanized = []
        
        for tick, dur, pitch, vel in notes:
            # Timing variation (drums are usually tight but with groove)
            timing_var = 0.02 + (personality.push_pull * 0.015)
            timing_offset = humanize_timing(tick, variation=timing_var)
            tick = max(0, int(timing_offset))
            
            # Velocity humanization
            vel = humanize_velocity(vel, 0.08)
            
            humanized.append((tick, dur, pitch, vel))
        
        return humanized
    
    def react_to_cue(
        self,
        cue_type: str,
        context: PerformanceContext
    ) -> List[NoteEvent]:
        """
        React to a performance cue with appropriate kebero response.
        
        Kebero responds with energetic drum fills and rhythmic variations.
        
        Cue types:
            - "fill": Rapid drum fill leading to next section
            - "stop": Short muted hit or silence
            - "build": Accelerating pattern towards climax
            - "drop": Sparse, minimal hits
            - "accent": Strong coordinated hit
        """
        tpb = context.ticks_per_beat
        notes = []
        
        # Define pitches for different drum sounds
        BASS_HIT = 36     # Deep bass drum center
        SLAP_HIT = 38     # Slap on edge
        MUTED_HIT = 37    # Muted press
        RIM_HIT = 39      # Rim hit
        
        # Base velocity from personality
        base_vel = 90
        if self._personality:
            base_vel = int(70 + self._personality.intensity * 50)
        
        if cue_type == "fill":
            # Rapid fill alternating bass and slap
            subdivisions = 16
            for i in range(subdivisions):
                tick = i * (tpb // 4)
                # Alternate between bass and slap
                pitch = BASS_HIT if i % 2 == 0 else SLAP_HIT
                # Accent pattern
                vel = base_vel if i % 4 == 0 else base_vel - 15
                notes.append(NoteEvent(
                    tick=tick,
                    pitch=pitch,
                    velocity=vel,
                    duration=tpb // 4,
                    channel=9  # Drums channel
                ))
        
        elif cue_type == "stop":
            # Single muted hit
            notes.append(NoteEvent(
                tick=0,
                pitch=MUTED_HIT,
                velocity=60,
                duration=tpb // 8,
                channel=9
            ))
        
        elif cue_type == "build":
            # Accelerating pattern - increasing density
            positions = [0, tpb, tpb + tpb//2, tpb*2 - tpb//4, 
                        tpb*2, tpb*2 + tpb//4, tpb*2 + tpb//2, 
                        tpb*3 - tpb//4, tpb*3 - tpb//8, tpb*3]
            for i, tick in enumerate(positions):
                vel = min(127, 60 + i * 7)
                pitch = BASS_HIT if i % 3 == 0 else SLAP_HIT
                notes.append(NoteEvent(
                    tick=tick,
                    pitch=pitch,
                    velocity=vel,
                    duration=tpb // 4,
                    channel=9
                ))
        
        elif cue_type == "drop":
            # Sparse - just beats 1 and 3
            notes.append(NoteEvent(
                tick=0,
                pitch=BASS_HIT,
                velocity=50,
                duration=tpb // 2,
                channel=9
            ))
            notes.append(NoteEvent(
                tick=tpb * 2,
                pitch=MUTED_HIT,
                velocity=40,
                duration=tpb // 4,
                channel=9
            ))
        
        elif cue_type == "accent":
            # Strong unison hit - bass and slap together
            notes.append(NoteEvent(
                tick=0,
                pitch=BASS_HIT,
                velocity=min(127, base_vel + 20),
                duration=tpb // 2,
                channel=9
            ))
            notes.append(NoteEvent(
                tick=10,  # Slight flam
                pitch=SLAP_HIT,
                velocity=min(127, base_vel + 15),
                duration=tpb // 4,
                channel=9
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
                channel=9  # Drum channel
            )
            events.append(event)
        
        return events


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    "KeberoAgent",
    "KeberoHitTypes",
    "KeberoTechniques",
    "KeberoPatterns",
    "KEBERO_PRESETS",
    "KEBERO_BASS",
    "KEBERO_SLAP",
    "KEBERO_MUTED",
    "ATAMO_HIT",
]
