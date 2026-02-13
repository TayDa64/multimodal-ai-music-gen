"""
DrummerAgent - Masterclass Drummer Performer

This module implements a professional drummer agent with deep knowledge of:
- Kit topology (kick, snare, hi-hats, cymbals, toms)
- Genre-specific patterns (trap, boom bap, house, lofi, R&B, G-funk)
- Fill theory (8th note fills, 16th note rolls, tom cascades, snare builds)
- Dynamic control (ghost notes, accents, velocity curves)
- Groove concepts (swing, push/pull timing, pocket)
- Section awareness (intro sparsity, verse groove, chorus energy, drop impact)

The DrummerAgent wraps existing strategy-based pattern generators while adding:
- Personality-driven timing adjustments (push_pull)
- Personality-driven fill frequency
- Personality-driven ghost note density
- Decision logging for transparency and debugging

Architecture Notes:
    This is a Stage 1 (offline) implementation that delegates to existing
    genre strategies. Stage 2 will add API-backed generation capabilities.

Musical Reference:
    MIDI Drum Kit Mapping (General MIDI Standard):
    - Kick: 36 (Bass Drum 1)
    - Snare: 38 (Acoustic Snare)
    - Closed Hi-Hat: 42
    - Open Hi-Hat: 46
    - Crash: 49 (Crash Cymbal 1)
    - Ride: 51 (Ride Cymbal 1)
    - Low Tom: 45
    - Mid Tom: 47
    - High Tom: 48
    - Clap: 39 (Hand Clap)
    - Side Stick/Rim: 37 (Side Stick)

Example:
    ```python
    from multimodal_gen.agents.performers import DrummerAgent
    from multimodal_gen.agents import PerformanceContext, DRUMMER_PRESETS
    
    drummer = DrummerAgent()
    drummer.set_personality(DRUMMER_PRESETS['trap_producer'])
    
    result = drummer.perform(context, section)
    print(f"Generated {len(result.notes)} drum notes")
    print(f"Decisions: {result.decisions_made}")
    ```
"""

from typing import List, Optional, Dict, Any, Tuple
import random
import logging

# Guarded import: GenreDNA for subdivision adjustments
try:
    from multimodal_gen.intelligence.genre_dna import get_genre_dna, GenreDNAVector
    _HAS_GENRE_DNA = True
except ImportError:
    _HAS_GENRE_DNA = False

from ..base import IPerformerAgent, AgentRole, PerformanceResult
from ..context import PerformanceContext
from ..personality import AgentPersonality, DRUMMER_PRESETS, get_personality_for_role

# Import existing infrastructure
from ...arranger import SongSection, SectionType
from ...strategies.registry import StrategyRegistry
from ...midi_generator import NoteEvent
from ...utils import (
    GM_DRUM_NOTES,
    GM_DRUM_CHANNEL,
    TICKS_PER_BEAT,
    TICKS_PER_8TH,
    TICKS_PER_16TH,
    TICKS_PER_BAR_4_4,
    humanize_velocity,
    humanize_timing,
    beats_to_ticks,
)

logger = logging.getLogger(__name__)


# =============================================================================
# DRUM KIT KNOWLEDGE BASE
# =============================================================================

class DrumKit:
    """
    Masterclass drum kit knowledge.
    
    Contains MIDI mappings and musical characteristics of each kit piece.
    This knowledge base informs the agent's decisions about when and how
    to use each drum sound.
    """
    
    # Core kit pieces with MIDI numbers
    KICK = 36           # Foundation, downbeat anchor
    SNARE = 38          # Backbeat, accent
    HIHAT_CLOSED = 42   # Time-keeper, subdivision
    HIHAT_OPEN = 46     # Accent, energy lift
    HIHAT_PEDAL = 44    # Foot control, ghost hits
    
    # Cymbals
    CRASH = 49          # Impact, section markers
    CRASH_2 = 57        # Secondary crash
    RIDE = 51           # Sustained time-keeping (jazz, rock)
    RIDE_BELL = 53      # Accent pattern (latin, jazz)
    
    # Toms (descending pitch)
    TOM_HIGH = 48       # Fill element, fast decay
    TOM_MID = 47        # Fill element, medium decay
    TOM_LOW = 45        # Fill element, low punch
    TOM_FLOOR = 41      # Low floor tom, dramatic fills
    
    # Percussion extras
    CLAP = 39           # Layered with snare in hip-hop
    RIM = 37            # Side stick, ghost hits, R&B texture
    COWBELL = 56        # Accent in funk/latin
    TAMBOURINE = 54     # Energy layer
    
    # Velocity ranges for expressive dynamics
    GHOST_VELOCITY = (30, 50)       # Subtle, felt not heard
    NORMAL_VELOCITY = (70, 95)      # Standard playing
    ACCENT_VELOCITY = (110, 127)    # Strong emphasis
    
    # Fill tom cascade order (high to low)
    TOM_CASCADE = [TOM_HIGH, TOM_MID, TOM_LOW, TOM_FLOOR]
    
    @classmethod
    def get_fill_toms(cls, length: int = 4) -> List[int]:
        """Get tom sequence for fill, ordered high to low."""
        return cls.TOM_CASCADE[:length]


# =============================================================================
# GENRE PATTERN KNOWLEDGE
# =============================================================================

class GenrePatternKnowledge:
    """
    Encyclopedic knowledge of drum patterns across genres.
    
    This class documents the characteristic rhythmic DNA of each genre,
    informing the agent's pattern selection and execution decisions.
    """
    
    PATTERNS = {
        'trap': {
            'description': 'Modern hip-hop with rolling hi-hats and half-time snare',
            'kick_style': 'sparse_syncopated',  # Sparse with 808 emphasis
            'snare_position': 'half_time',       # Beat 3 (half-time feel)
            'hihat_density': '16th_with_rolls',  # Dense 16ths, triplet rolls
            'swing': 0.0,                        # Straight, quantized feel
            'ghost_notes': 'minimal',            # Occasional snare ghosts
            'typical_bpm': (130, 170),
            'fills': ['hihat_roll', 'snare_buildup', 'minimal_tom'],
        },
        'boom_bap': {
            'description': 'Classic 90s hip-hop with swing and ghost snares',
            'kick_style': 'syncopated_heavy',    # Emphasized kick patterns
            'snare_position': 'backbeat',        # Beats 2 and 4
            'hihat_density': '8th',              # Clean 8th notes
            'swing': 0.15,                       # Strong swing feel
            'ghost_notes': 'heavy',              # Classic ghost snares
            'typical_bpm': (85, 105),
            'fills': ['tom_cascade', 'snare_roll', 'kick_stutter'],
        },
        'house': {
            'description': 'Four-on-the-floor with off-beat hi-hats',
            'kick_style': 'four_on_floor',       # Every beat
            'snare_position': 'clap_2_4',        # Clap on 2 and 4
            'hihat_density': '8th_offbeat',      # Open on offbeats
            'swing': 0.0,                        # Straight
            'ghost_notes': 'none',               # Clean and simple
            'typical_bpm': (118, 130),
            'fills': ['snare_roll', 'hihat_buildup', 'kick_drop'],
        },
        'lofi': {
            'description': 'Laid-back hip-hop with lazy swing',
            'kick_style': 'simple_groove',       # Basic pattern
            'snare_position': 'backbeat',        # 2 and 4
            'hihat_density': '8th',              # Simple 8ths
            'swing': 0.12,                       # Lazy swing
            'ghost_notes': 'subtle',             # Occasional
            'typical_bpm': (70, 90),
            'fills': ['minimal', 'hihat_choke', 'rim_accent'],
        },
        'rnb': {
            'description': 'Smooth groove with pocket feel',
            'kick_style': 'pocket_groove',       # In the pocket
            'snare_position': 'backbeat',        # 2 and 4
            'hihat_density': '8th',              # Clean
            'swing': 0.08,                       # Subtle swing
            'ghost_notes': 'musical',            # Tasteful ghosts
            'typical_bpm': (65, 90),
            'fills': ['rim_roll', 'tom_accent', 'snare_drag'],
        },
        'g_funk': {
            'description': 'West coast bounce with funk influence',
            'kick_style': 'funk_syncopated',     # Funky patterns
            'snare_position': 'backbeat',        # Classic 2 and 4
            'hihat_density': '8th',              # Clean 8ths (NOT 16ths)
            'swing': 0.15,                       # Strong shuffle
            'ghost_notes': 'moderate',           # Funk influence
            'typical_bpm': (88, 100),
            'fills': ['tom_funk', 'hihat_open', 'kick_stutter'],
        },
        'ethiopian': {
            'description': 'Compound meter with kebero patterns',
            'kick_style': 'compound_pulse',      # 6/8 or 12/8 feel
            'snare_position': 'call_response',   # Slap patterns
            'hihat_density': 'compound',         # Triplet subdivisions
            'swing': 0.03,                       # Subtle
            'ghost_notes': 'traditional',        # Cultural patterns
            'typical_bpm': (90, 130),
            'fills': ['kebero_roll', 'atamo_accent', 'compound_cascade'],
        },
        'neo_soul': {
            'description': 'Broken beat with ghost snares and open hi-hat accents',
            'kick_style': 'broken_beat',         # Kick on 1 and and-of-3
            'snare_position': 'ghost_heavy',     # Ghost snares on e-and-a
            'hihat_density': '16th_open_accent',  # Open hi-hat accents
            'swing': 0.15,                       # Moderate swing
            'ghost_notes': 'heavy',              # Lots of ghost snares
            'typical_bpm': (68, 95),
            'fills': ['rim_roll', 'snare_drag', 'hihat_choke'],
        },
        'gospel': {
            'description': 'Shuffle with strong backbeat and tom turnarounds',
            'kick_style': 'shuffle_drive',       # Gospel drive
            'snare_position': 'backbeat_strong',  # Very strong 2 and 4
            'hihat_density': '8th',              # Clean 8ths
            'swing': 0.30,                       # Shuffle feel
            'ghost_notes': 'moderate',           # Musical ghosts
            'typical_bpm': (85, 140),
            'fills': ['tom_cascade', 'snare_roll', '8th_fill'],
        },
        'jazz': {
            'description': 'Ride pattern with brush snare and light kick comping',
            'kick_style': 'comping',             # Light kick comping
            'snare_position': 'brush_2_4',       # Brush on 2 and 4
            'hihat_density': 'ride_quarter',     # Ride cymbal keeps time
            'swing': 0.45,                       # Strong swing
            'ghost_notes': 'heavy',              # Jazz ghost notes
            'typical_bpm': (100, 220),
            'fills': ['tom_cascade', 'snare_roll', 'hihat_roll'],
        },
        'lo_fi': {
            'description': 'Lo-fi hip-hop with heavy Dilla-style swing',
            'kick_style': 'sparse, offbeat',
            'snare_position': '2, 4 with ghost',
            'hihat_density': '8th',
            'swing': 0.5,                        # heavy Dilla-style swing
            'ghost_notes': 'moderate',
            'typical_bpm': (70, 90),
            'fills': ['hihat_roll'],              # minimal fills
        },
        'ambient': {
            'description': 'Sparse atmospheric percussion with minimal density',
            'kick_style': 'sparse, atmospheric',
            'snare_position': 'minimal',
            'hihat_density': 'quarter',
            'swing': 0.1,
            'ghost_notes': 'none',
            'typical_bpm': (80, 120),
            'fills': ['hihat_roll'],
        },
        'funk': {
            'description': 'Syncopated grooves with heavy ghost notes and busy kick',
            'kick_style': 'syncopated, busy',
            'snare_position': '2, 4 with ghosts between',
            'hihat_density': '16th',
            'swing': 0.3,
            'ghost_notes': 'heavy',
            'typical_bpm': (95, 120),
            'fills': ['16th_roll', 'tom_cascade', 'snare_build'],
        },
        'drill': {
            'description': 'Sliding 808 kicks with offbeat snare rolls and rapid hi-hats',
            'kick_style': 'sliding 808',
            'snare_position': 'offbeat, rolls',
            'hihat_density': '32nd',
            'swing': 0.1,
            'ghost_notes': 'none',
            'typical_bpm': (140, 145),
            'fills': ['hihat_roll', 'snare_build'],
        },
        'deep_house': {
            'description': 'Muted four-on-the-floor with rimshot and offbeat hi-hats',
            'kick_style': 'four_on_floor muted',
            'snare_position': '2, 4 rimshot',
            'hihat_density': '16th_offbeat',
            'swing': 0.2,
            'ghost_notes': 'subtle',
            'typical_bpm': (118, 124),
            'fills': ['hihat_roll'],
        },
        'afrobeat': {
            'description': 'Polyrhythmic kick with cross-rhythm snare and busy hi-hats',
            'kick_style': 'polyrhythmic',
            'snare_position': '2, 4 with cross-rhythm',
            'hihat_density': '16th',
            'swing': 0.35,
            'ghost_notes': 'traditional',
            'typical_bpm': (100, 130),
            'fills': ['tom_cascade', '16th_roll'],
        },
    }
    
    @classmethod
    def get_pattern_info(cls, genre: str) -> Dict[str, Any]:
        """Get pattern knowledge for a genre, with default fallback."""
        genre_key = genre.lower().strip()
        
        # Handle aliases
        aliases = {
            'trap_soul': 'trap',
            'lo-fi': 'lofi',
            'chillhop': 'lofi',
            'r&b': 'rnb',
            'ethio_jazz': 'ethiopian',
            'eskista': 'ethiopian',
            'ethiopian_traditional': 'ethiopian',
        }
        genre_key = aliases.get(genre_key, genre_key)
        
        return cls.PATTERNS.get(genre_key, cls.PATTERNS.get('rnb', {}))


# =============================================================================
# FILL GENERATOR
# =============================================================================

class FillGenerator:
    """
    Generates drum fills based on musical context.
    
    Fill Types:
    - 8th Note Fill: Simple, musical, versatile
    - 16th Note Roll: Energy builder, tension
    - Tom Cascade: Dramatic, section transition
    - Snare Build: Crescendo, anticipation
    - Hi-Hat Roll: Trap signature, triplet energy
    """
    
    @staticmethod
    def generate_8th_note_fill(
        start_tick: int,
        duration_beats: float = 1.0,
        base_velocity: int = 90,
        use_toms: bool = True
    ) -> List[NoteEvent]:
        """
        Generate a musical 8th note fill.
        
        Classic drum fill with alternating hands, often using toms
        for melodic interest. Works in any genre.
        
        Args:
            start_tick: Starting tick position
            duration_beats: Fill length in beats (default 1 beat)
            base_velocity: Starting velocity
            use_toms: Include toms for melodic contour
            
        Returns:
            List of NoteEvent for the fill
        """
        notes = []
        num_8ths = int(duration_beats * 2)
        
        # Choose sounds for the fill
        if use_toms:
            sounds = [DrumKit.SNARE, DrumKit.TOM_HIGH, DrumKit.TOM_MID, DrumKit.TOM_LOW]
        else:
            sounds = [DrumKit.SNARE]
        
        for i in range(num_8ths):
            tick = start_tick + (i * TICKS_PER_8TH)
            # Crescendo towards end
            vel = base_velocity + int(10 * (i / max(1, num_8ths - 1)))
            vel = humanize_velocity(min(127, vel), variation=0.08)
            
            # Choose sound (cycle through for toms, or just snare)
            if use_toms:
                sound = sounds[i % len(sounds)]
            else:
                sound = DrumKit.SNARE
            
            notes.append(NoteEvent(
                pitch=sound,
                start_tick=tick,
                duration_ticks=TICKS_PER_8TH // 2,
                velocity=vel,
                channel=GM_DRUM_CHANNEL
            ))
        
        return notes
    
    @staticmethod
    def generate_16th_note_roll(
        start_tick: int,
        duration_beats: float = 1.0,
        base_velocity: int = 80,
        instrument: int = DrumKit.SNARE
    ) -> List[NoteEvent]:
        """
        Generate a 16th note roll.
        
        Creates tension and energy, commonly used for builds.
        Velocity typically crescendos through the roll.
        
        Args:
            start_tick: Starting tick position
            duration_beats: Roll length in beats
            base_velocity: Starting velocity (crescendos up)
            instrument: Drum to roll (default snare)
            
        Returns:
            List of NoteEvent for the roll
        """
        notes = []
        num_16ths = int(duration_beats * 4)
        
        for i in range(num_16ths):
            tick = start_tick + (i * TICKS_PER_16TH)
            # Strong crescendo
            vel_progress = i / max(1, num_16ths - 1)
            vel = int(base_velocity + (40 * vel_progress))
            vel = humanize_velocity(min(127, vel), variation=0.05)
            
            notes.append(NoteEvent(
                pitch=instrument,
                start_tick=tick,
                duration_ticks=TICKS_PER_16TH // 2,
                velocity=vel,
                channel=GM_DRUM_CHANNEL
            ))
        
        return notes
    
    @staticmethod
    def generate_tom_cascade(
        start_tick: int,
        duration_beats: float = 1.0,
        base_velocity: int = 95,
        descending: bool = True
    ) -> List[NoteEvent]:
        """
        Generate a tom cascade fill.
        
        Classic fill moving through the toms, typically high to low
        (descending) for dramatic effect. Used at section transitions.
        
        Args:
            start_tick: Starting tick position
            duration_beats: Fill length in beats
            base_velocity: Base velocity
            descending: High to low (True) or low to high (False)
            
        Returns:
            List of NoteEvent for the cascade
        """
        notes = []
        toms = DrumKit.get_fill_toms(4)
        if not descending:
            toms = list(reversed(toms))
        
        num_hits = int(duration_beats * 4)  # 16th note subdivision
        
        for i in range(num_hits):
            tick = start_tick + (i * TICKS_PER_16TH)
            # Pick tom based on position (cycle through)
            tom = toms[min(i, len(toms) - 1)]
            
            # Slight crescendo
            vel = base_velocity + int(15 * (i / max(1, num_hits - 1)))
            vel = humanize_velocity(min(127, vel), variation=0.08)
            
            notes.append(NoteEvent(
                pitch=tom,
                start_tick=tick,
                duration_ticks=TICKS_PER_16TH // 2,
                velocity=vel,
                channel=GM_DRUM_CHANNEL
            ))
        
        return notes
    
    @staticmethod
    def generate_snare_build(
        start_tick: int,
        duration_beats: float = 2.0,
        base_velocity: int = 60,
        accelerate: bool = True
    ) -> List[NoteEvent]:
        """
        Generate a snare build (crescendo roll).
        
        Starts sparse and accelerates, building tension. Common
        before drops in electronic and hip-hop. Can be combined
        with hi-hat rolls for extra energy.
        
        Args:
            start_tick: Starting tick position
            duration_beats: Build length in beats
            base_velocity: Starting velocity (increases)
            accelerate: If True, notes get closer together
            
        Returns:
            List of NoteEvent for the build
        """
        notes = []
        
        if accelerate:
            # Accelerating pattern: 8ths -> 16ths -> 32nds
            # Phase 1: 8th notes (first half)
            half_dur = duration_beats / 2
            num_8ths = int(half_dur * 2)
            for i in range(num_8ths):
                tick = start_tick + (i * TICKS_PER_8TH)
                vel = humanize_velocity(base_velocity + (i * 5), variation=0.1)
                notes.append(NoteEvent(
                    pitch=DrumKit.SNARE,
                    start_tick=tick,
                    duration_ticks=TICKS_PER_8TH // 2,
                    velocity=min(127, vel),
                    channel=GM_DRUM_CHANNEL
                ))
            
            # Phase 2: 16th notes (second half)
            phase2_start = start_tick + int(half_dur * TICKS_PER_BEAT)
            num_16ths = int(half_dur * 4)
            for i in range(num_16ths):
                tick = phase2_start + (i * TICKS_PER_16TH)
                vel = humanize_velocity(base_velocity + 30 + (i * 3), variation=0.08)
                notes.append(NoteEvent(
                    pitch=DrumKit.SNARE,
                    start_tick=tick,
                    duration_ticks=TICKS_PER_16TH // 2,
                    velocity=min(127, vel),
                    channel=GM_DRUM_CHANNEL
                ))
        else:
            # Straight 16th note build with crescendo
            notes = FillGenerator.generate_16th_note_roll(
                start_tick, duration_beats, base_velocity, DrumKit.SNARE
            )
        
        return notes
    
    @staticmethod
    def generate_hihat_roll(
        start_tick: int,
        duration_beats: float = 0.5,
        base_velocity: int = 70,
        triplet: bool = True
    ) -> List[NoteEvent]:
        """
        Generate a hi-hat roll (trap signature).
        
        Fast hi-hat patterns, typically triplets, that create
        rhythmic tension. Signature sound of trap music.
        
        Args:
            start_tick: Starting tick position
            duration_beats: Roll length in beats
            base_velocity: Base velocity
            triplet: Use triplet subdivision (True) or 32nds (False)
            
        Returns:
            List of NoteEvent for the roll
        """
        notes = []
        
        if triplet:
            # Triplet roll (3 per 8th note)
            ticks_per_triplet = TICKS_PER_8TH // 3
            num_notes = int(duration_beats * 6)  # 6 triplets per beat
        else:
            # 32nd note roll
            ticks_per_32nd = TICKS_PER_BEAT // 8
            ticks_per_triplet = ticks_per_32nd  # Reuse var
            num_notes = int(duration_beats * 8)
        
        for i in range(num_notes):
            tick = start_tick + (i * ticks_per_triplet)
            # Crescendo
            vel_progress = i / max(1, num_notes - 1)
            vel = int(base_velocity + (25 * vel_progress))
            vel = humanize_velocity(min(127, vel), variation=0.1)
            
            notes.append(NoteEvent(
                pitch=DrumKit.HIHAT_CLOSED,
                start_tick=tick,
                duration_ticks=ticks_per_triplet // 2,
                velocity=vel,
                channel=GM_DRUM_CHANNEL
            ))
        
        return notes


# =============================================================================
# DRUMMER AGENT
# =============================================================================

class DrummerAgent(IPerformerAgent):
    """
    Masterclass drummer performer agent.
    
    A professional-level drummer that understands:
    - Kit topology and sound selection
    - Genre-specific patterns and feel
    - Fill theory and placement
    - Dynamic control and expression
    - Groove concepts (swing, push/pull)
    - Section-aware density and energy
    
    The agent wraps existing strategy-based generators while adding
    personality-driven adjustments and decision logging for transparency.
    
    Attributes:
        _name: Human-readable agent name
        _genre_knowledge: Reference to pattern knowledge base
        
    Example:
        ```python
        drummer = DrummerAgent()
        drummer.set_personality(DRUMMER_PRESETS['jazz_master'])
        
        result = drummer.perform(context, section)
        # result.notes contains the drum MIDI events
        # result.decisions_made contains reasoning log
        ```
    """
    
    def __init__(self, name: str = "Master Drummer"):
        """
        Initialize the drummer agent.
        
        Args:
            name: Human-readable name for this agent instance
        """
        super().__init__()
        self._name = name
        self._genre_knowledge = GenrePatternKnowledge
        self._decisions: List[str] = []  # Track decisions per perform call
    
    @property
    def role(self) -> AgentRole:
        """This agent fulfills the DRUMS role."""
        return AgentRole.DRUMS
    
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
        Generate drum notes for the given section.
        
        This is the main entry point for drum generation. The agent:
        1. Analyzes the context (tempo, energy, tension)
        2. Selects appropriate genre strategy
        3. Applies personality adjustments
        4. Generates base pattern
        5. Adds fills based on personality and section type
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
            # Get default personality for genre
            genre = self._extract_genre_from_context(context)
            effective_personality = get_personality_for_role(genre, AgentRole.DRUMS)
            self._log_decision(f"Using default personality for genre '{genre}'")
        else:
            self._log_decision(f"Using provided personality (aggr={effective_personality.aggressiveness:.2f})")
        
        # Scale personality by tension
        scaled_personality = effective_personality.apply_tension_scaling(context.tension)
        self._log_decision(f"Applied tension scaling ({context.tension:.2f}) to personality")
        
        # Get genre strategy
        genre = self._extract_genre_from_context(context)
        strategy = StrategyRegistry.get_or_default(genre)
        self._log_decision(f"Selected strategy: {strategy.genre_name}")
        
        # Get pattern knowledge for decision-making
        pattern_info = self._genre_knowledge.get_pattern_info(genre)
        self._log_decision(f"Pattern style: {pattern_info.get('description', 'unknown')}")
        
        # Generate base pattern using strategy
        # Create a minimal ParsedPrompt for the strategy
        parsed = self._create_parsed_prompt(context, section, scaled_personality)
        
        base_notes = strategy.generate_drums(section, parsed, context.tension)
        self._log_decision(f"Generated {len(base_notes)} base notes from strategy")
        
        patterns_used = [pattern_info.get('kick_style', 'standard')]
        
        # Apply GenreDNA subdivisions when available
        if _HAS_GENRE_DNA and context.genre_dna is not None:
            try:
                # Accept both dict and GenreDNAVector
                if isinstance(context.genre_dna, dict):
                    dna = GenreDNAVector(**{k: v for k, v in context.genre_dna.items()
                                           if hasattr(GenreDNAVector, k)})
                else:
                    dna = context.genre_dna  # type: ignore[assignment]
                base_notes = self._apply_genre_dna_subdivision(
                    base_notes, dna, TICKS_PER_BEAT
                )
                self._log_decision("Applied GenreDNA subdivision adjustments")
                patterns_used.append('genre_dna')
            except Exception as exc:
                logger.warning("GenreDNA subdivision failed: %s", exc)
        
        # Apply personality-based ghost note adjustments
        if scaled_personality.ghost_note_density > 0.3:
            ghost_notes = self._add_ghost_notes(
                section,
                scaled_personality.ghost_note_density,
                pattern_info
            )
            base_notes.extend(ghost_notes)
            self._log_decision(f"Added {len(ghost_notes)} ghost notes (density={scaled_personality.ghost_note_density:.2f})")
            patterns_used.append('ghost_notes')
        
        # Determine fill locations and add fills
        fill_locations = []
        if context.fill_opportunity or self._should_add_fill(section, scaled_personality):
            fill_notes, fill_tick = self._generate_section_fill(
                section,
                scaled_personality,
                pattern_info
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
        
        # Collect kick ticks for bass-kick alignment
        kick_ticks = sorted([
            n.start_tick for n in base_notes
            if n.pitch == DrumKit.KICK
        ])
        context.kick_ticks = kick_ticks
        
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
        - "fill": Generate a 1-2 bar drum fill appropriate to genre
        - "stop": Return empty (silence/break)
        - "build": Generate snare roll or hi-hat acceleration
        - "drop": Crash + kick impact for drop moment
        
        Args:
            cue_type: The type of cue to react to
            context: Current performance context
            
        Returns:
            List of NoteEvent for the cue response
        """
        cue_type = cue_type.lower().strip()
        genre = self._extract_genre_from_context(context)
        pattern_info = self._genre_knowledge.get_pattern_info(genre)
        
        # Get current tick from context (use section position or default to 0)
        current_tick = int(context.section_position_beats * TICKS_PER_BEAT)
        
        personality = self._personality or get_personality_for_role(genre, AgentRole.DRUMS)
        base_velocity = int(90 * (0.8 + 0.4 * personality.aggressiveness))
        
        if cue_type == 'fill':
            # Generate genre-appropriate fill
            return self._generate_cue_fill(current_tick, pattern_info, base_velocity)
        
        elif cue_type == 'stop':
            # Return empty for silence/break
            return []
        
        elif cue_type == 'build':
            # Snare roll or hi-hat acceleration
            return self._generate_build_cue(current_tick, pattern_info, base_velocity)
        
        elif cue_type == 'drop':
            # Impact moment: crash + kick
            return self._generate_drop_cue(current_tick, base_velocity)
        
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
        # Check reference features for genre
        if context.reference_features and 'genre' in context.reference_features:
            return context.reference_features['genre']
        
        # Check current section
        if context.current_section and hasattr(context.current_section, 'config'):
            # Some sections might store genre info
            pass
        
        # Default fallback
        return 'trap_soul'
    
    def _create_parsed_prompt(
        self,
        context: PerformanceContext,
        section: SongSection,
        personality: AgentPersonality
    ) -> Any:
        """
        Create a minimal ParsedPrompt-like object for strategy compatibility.
        
        The existing strategies expect a ParsedPrompt, so we create a
        compatible object from the context and personality.
        """
        from ...prompt_parser import ParsedPrompt
        from ...utils import ScaleType
        
        genre = self._extract_genre_from_context(context)
        
        # Map personality swing_affinity to actual swing amount
        swing_amount = personality.swing_affinity * 0.2  # Max 0.2 swing
        
        # Determine drum elements based on section type and personality
        drum_elements = ['kick', 'snare', 'hihat']
        if personality.aggressiveness > 0.6:
            drum_elements.append('clap')
        if section.section_type in [SectionType.DROP, SectionType.CHORUS]:
            drum_elements.append('crash')
        if personality.fill_frequency > 0.3:
            drum_elements.append('hihat_roll')
        
        return ParsedPrompt(
            bpm=context.bpm,
            genre=genre,
            key=context.key,
            scale_type=ScaleType.MINOR if 'm' in context.key.lower() else ScaleType.MAJOR,
            swing_amount=swing_amount,
            drum_elements=drum_elements,
            time_signature=context.time_signature,
        )
    
    def _should_add_fill(
        self,
        section: SongSection,
        personality: AgentPersonality
    ) -> bool:
        """
        Decide if a fill should be added based on section and personality.
        
        Fill placement is informed by:
        - Section type (fills before drops/choruses)
        - Personality fill_frequency
        - Random chance for variation
        """
        # Always add fill before high-energy sections
        if section.section_type in [SectionType.DROP, SectionType.CHORUS]:
            return True
        
        # Personality-based random chance
        fill_chance = personality.fill_frequency * 0.8
        
        # Boost chance for transition sections
        if section.section_type in [SectionType.PRE_CHORUS, SectionType.BUILDUP]:
            fill_chance += 0.3
        
        return random.random() < fill_chance
    
    def _add_ghost_notes(
        self,
        section: SongSection,
        density: float,
        pattern_info: Dict[str, Any]
    ) -> List[NoteEvent]:
        """
        Add ghost notes based on personality density.
        
        Ghost notes are soft snare/rim hits that add groove and
        humanization without changing the main beat.
        
        Args:
            section: Current section
            density: Ghost note density from personality (0-1)
            pattern_info: Genre pattern knowledge
            
        Returns:
            List of ghost note NoteEvents
        """
        notes = []
        
        # Skip if genre doesn't use ghost notes
        if pattern_info.get('ghost_notes', 'none') == 'none':
            return notes
        
        # Determine ghost positions based on pattern style
        # Ghost notes typically fall on 16th note subdivisions
        ghost_positions_per_bar = [
            (0.5, 0.4),   # After beat 1
            (1.5, 0.3),   # After beat 2
            (2.5, 0.5),   # After beat 3
            (3.5, 0.3),   # After beat 4
        ]
        
        # Adjust for genre
        if pattern_info.get('ghost_notes') == 'heavy':
            # Boom bap: more ghost notes
            ghost_positions_per_bar = [
                (0.5, 0.6), (1.25, 0.4), (1.5, 0.5),
                (2.5, 0.6), (3.25, 0.4), (3.5, 0.5),
            ]
        
        for bar in range(section.bars):
            bar_offset = section.start_tick + (bar * TICKS_PER_BAR_4_4)
            
            for beat_pos, base_prob in ghost_positions_per_bar:
                # Scale probability by density
                prob = base_prob * density
                
                if random.random() < prob:
                    tick = bar_offset + beats_to_ticks(beat_pos)
                    
                    # Ghost note velocity (very soft)
                    vel = random.randint(
                        DrumKit.GHOST_VELOCITY[0],
                        DrumKit.GHOST_VELOCITY[1]
                    )
                    
                    # Choose between snare and rim for variety
                    pitch = DrumKit.SNARE if random.random() < 0.7 else DrumKit.RIM
                    
                    notes.append(NoteEvent(
                        pitch=pitch,
                        start_tick=tick,
                        duration_ticks=TICKS_PER_16TH // 2,
                        velocity=vel,
                        channel=GM_DRUM_CHANNEL
                    ))
        
        return notes
    
    def _generate_section_fill(
        self,
        section: SongSection,
        personality: AgentPersonality,
        pattern_info: Dict[str, Any]
    ) -> Tuple[List[NoteEvent], int]:
        """
        Generate a fill for the end of the section.
        
        Fill type is selected based on genre and personality.
        
        Args:
            section: Current section
            personality: Scaled personality
            pattern_info: Genre pattern knowledge
            
        Returns:
            Tuple of (fill notes, fill start tick)
        """
        # Fill at end of section (last 1-2 beats)
        fill_duration = 1.0 if personality.complexity < 0.5 else 2.0
        fill_start = section.end_tick - int(fill_duration * TICKS_PER_BEAT)
        
        # Select fill type based on genre and complexity
        available_fills = pattern_info.get('fills', ['tom_cascade'])
        
        # Weight fill selection by personality
        if personality.complexity > 0.7:
            preferred = ['tom_cascade', '16th_roll', 'snare_buildup']
        elif personality.complexity > 0.4:
            preferred = ['8th_fill', 'snare_roll']
        else:
            preferred = ['minimal', '8th_fill']
        
        # Find best match
        fill_type = None
        for pref in preferred:
            for avail in available_fills:
                if pref in avail:
                    fill_type = avail
                    break
            if fill_type:
                break
        
        if fill_type is None:
            fill_type = random.choice(available_fills) if available_fills else '8th_fill'
        
        base_velocity = int(80 * (0.8 + 0.4 * personality.aggressiveness))
        
        # Generate the fill
        if 'tom' in fill_type or fill_type == 'tom_cascade':
            notes = FillGenerator.generate_tom_cascade(
                fill_start, fill_duration, base_velocity
            )
        elif '16th' in fill_type or 'roll' in fill_type:
            notes = FillGenerator.generate_16th_note_roll(
                fill_start, fill_duration, base_velocity
            )
        elif 'hihat' in fill_type:
            notes = FillGenerator.generate_hihat_roll(
                fill_start, fill_duration, base_velocity
            )
        elif 'build' in fill_type:
            notes = FillGenerator.generate_snare_build(
                fill_start, fill_duration, base_velocity
            )
        else:
            # Default: 8th note fill
            notes = FillGenerator.generate_8th_note_fill(
                fill_start, fill_duration, base_velocity
            )
        
        return notes, fill_start
    
    def _apply_push_pull(
        self,
        notes: List[NoteEvent],
        push_pull: float
    ) -> List[NoteEvent]:
        """
        Apply push/pull timing adjustment to all notes.
        
        Push (positive): Playing ahead of the beat (eager, driving)
        Pull (negative): Playing behind the beat (laid back, groove)
        
        Args:
            notes: List of notes to adjust
            push_pull: Amount from -1 to 1 (typically -0.1 to 0.1)
            
        Returns:
            Notes with adjusted timing
        """
        # Calculate tick offset (max ±30 ticks, about a 32nd note)
        max_offset = TICKS_PER_16TH // 2  # ±30 ticks
        offset = int(push_pull * max_offset)
        
        for note in notes:
            # Apply offset, ensuring we don't go negative
            note.start_tick = max(0, note.start_tick + offset)
        
        return notes
    
    # =========================================================================
    # GENRE DNA SUBDIVISION (Task 2.2)
    # =========================================================================

    def _apply_genre_dna_subdivision(
        self,
        base_pattern: List[NoteEvent],
        genre_dna: 'GenreDNAVector',
        ticks_per_beat: int,
    ) -> List[NoteEvent]:
        """
        Adjust a base drum pattern according to GenreDNA dimensions.

        Modifications applied in order:

        Hi-hat complexity (rhythmic_density):
        - density > 0.8: add 32nd-note hi-hat runs in last beat of every 2 bars
        - density > 0.6: add 16th-note hi-hat subdivisions
        - density < 0.3: thin hi-hat pattern (remove ~40 % of hits)

        Swing:
        - swing > 0.3: apply swing offset to every other 8th note

        Kick syncopation (syncopation):
        - syncopation > 0.6: add off-beat kick on "and" of beat 3 (40 % chance)
        - syncopation > 0.4: displace some existing kicks by a 16th note

        Snare ghost displacement:
        - syncopation > 0.5: shift soft snare hits by ±16th note

        Dynamic range:
        - dynamic_range > 0.6: widen velocity spread (floor 40, cap 127)
        - dynamic_range < 0.3: compress velocities to tight range (75-105)

        Args:
            base_pattern: Existing drum NoteEvent list.
            genre_dna: A :class:`GenreDNAVector` instance.
            ticks_per_beat: Ticks per beat (typically 480).

        Returns:
            Adjusted list of NoteEvents (may include added events).
        """
        result = list(base_pattern)

        tpb = ticks_per_beat
        ticks_per_16 = tpb // 4   # 120
        ticks_per_8 = tpb // 2    # 240
        ticks_per_32 = tpb // 8   # 60

        # -----------------------------------------------------------------
        # 1. Hi-hat complexity based on rhythmic_density
        # -----------------------------------------------------------------
        if genre_dna.rhythmic_density > 0.8:
            # Add 32nd-note hi-hat run in the last beat of every 2 bars
            if result:
                min_tick = min(n.start_tick for n in result)
                max_tick = max(n.start_tick for n in result)
                bar_len = tpb * 4  # TICKS_PER_BAR_4_4
                total_bars = max(1, (max_tick - min_tick) // bar_len + 1)
                for bar_idx in range(1, total_bars, 2):  # every 2nd bar
                    run_start = min_tick + bar_idx * bar_len + 3 * tpb  # last beat
                    run_end = run_start + tpb
                    tick = run_start
                    while tick < run_end:
                        vel = random.randint(50, 75)
                        result.append(NoteEvent(
                            pitch=DrumKit.HIHAT_CLOSED,
                            start_tick=tick,
                            duration_ticks=ticks_per_32 // 2,
                            velocity=vel,
                            channel=GM_DRUM_CHANNEL,
                        ))
                        tick += ticks_per_32

        if genre_dna.rhythmic_density > 0.6:
            # Add 16th-note hi-hat subdivisions where missing
            existing_hh_ticks = {
                n.start_tick for n in result
                if n.pitch in (DrumKit.HIHAT_CLOSED, DrumKit.HIHAT_OPEN)
            }
            if result:
                min_tick = min(n.start_tick for n in result)
                max_tick = max(n.start_tick for n in result)
                tick = min_tick
                while tick <= max_tick:
                    if tick not in existing_hh_ticks:
                        vel = random.randint(45, 70)
                        result.append(NoteEvent(
                            pitch=DrumKit.HIHAT_CLOSED,
                            start_tick=tick,
                            duration_ticks=ticks_per_16 // 2,
                            velocity=vel,
                            channel=GM_DRUM_CHANNEL,
                        ))
                    tick += ticks_per_16

        elif genre_dna.rhythmic_density < 0.3:
            # Thin the hi-hat pattern – remove ~40 % of hits
            thinned: List[NoteEvent] = []
            for note in result:
                if note.pitch in (DrumKit.HIHAT_CLOSED, DrumKit.HIHAT_OPEN):
                    if random.random() < 0.4:
                        continue  # drop this hit
                thinned.append(note)
            result = thinned

        # -----------------------------------------------------------------
        # 2. Swing → shift every other 8th note forward
        # -----------------------------------------------------------------
        if genre_dna.swing > 0.3:
            swing_offset = int(30 + 30 * min(genre_dna.swing, 1.0))  # 30-60 ticks
            for note in result:
                pos_in_beat = note.start_tick % tpb
                if abs(pos_in_beat - ticks_per_8) < 20:
                    note.start_tick += swing_offset

        # -----------------------------------------------------------------
        # 3. Kick syncopation based on syncopation
        # -----------------------------------------------------------------
        if genre_dna.syncopation > 0.6:
            # Add off-beat kick on the "and" of beat 3 with 40 % probability
            if result:
                min_tick = min(n.start_tick for n in result)
                max_tick = max(n.start_tick for n in result)
                bar_len = tpb * 4
                bar = 0
                while True:
                    bar_start = min_tick + bar * bar_len
                    if bar_start > max_tick:
                        break
                    if random.random() < 0.4:
                        kick_tick = bar_start + 2 * tpb + ticks_per_8  # "and" of beat 3
                        result.append(NoteEvent(
                            pitch=DrumKit.KICK,
                            start_tick=kick_tick,
                            duration_ticks=ticks_per_8,
                            velocity=random.randint(80, 100),
                            channel=GM_DRUM_CHANNEL,
                        ))
                    bar += 1

        if genre_dna.syncopation > 0.4:
            # Displace some existing kicks by a 16th note
            for note in result:
                if note.pitch == DrumKit.KICK:
                    if random.random() < 0.25:
                        direction = random.choice([-1, 1])
                        note.start_tick = max(0, note.start_tick + direction * ticks_per_16)

        # -----------------------------------------------------------------
        # 4. Snare ghost displacement (syncopation > 0.5)
        # -----------------------------------------------------------------
        if genre_dna.syncopation > 0.5:
            for note in result:
                if note.pitch == DrumKit.SNARE and note.velocity < 80:
                    if random.random() < 0.35:
                        direction = random.choice([-1, 1])
                        note.start_tick = max(0, note.start_tick + direction * ticks_per_16)

        # -----------------------------------------------------------------
        # 5. Dynamic range application
        # -----------------------------------------------------------------
        if genre_dna.dynamic_range > 0.6:
            # Widen velocity spread (floor 40, cap 127)
            for note in result:
                if note.velocity < 60:
                    note.velocity = max(40, note.velocity - random.randint(0, 15))
                elif note.velocity >= 100:
                    note.velocity = min(127, note.velocity + random.randint(0, 15))
        elif genre_dna.dynamic_range < 0.3:
            # Compress velocities to tight range (75-105)
            for note in result:
                note.velocity = max(75, min(105, note.velocity))

        return result

    def _generate_cue_fill(
        self,
        start_tick: int,
        pattern_info: Dict[str, Any],
        base_velocity: int
    ) -> List[NoteEvent]:
        """Generate a fill for the 'fill' cue."""
        # 1 bar fill
        fill_duration = 2.0  # 2 beats
        
        fills = pattern_info.get('fills', ['tom_cascade'])
        fill_type = random.choice(fills) if fills else 'tom_cascade'
        
        if 'tom' in fill_type:
            return FillGenerator.generate_tom_cascade(start_tick, fill_duration, base_velocity)
        elif 'hihat' in fill_type:
            return FillGenerator.generate_hihat_roll(start_tick, fill_duration, base_velocity)
        else:
            return FillGenerator.generate_8th_note_fill(start_tick, fill_duration, base_velocity)
    
    def _generate_build_cue(
        self,
        start_tick: int,
        pattern_info: Dict[str, Any],
        base_velocity: int
    ) -> List[NoteEvent]:
        """Generate a build for the 'build' cue."""
        build_duration = 4.0  # 4 beats (1 bar)
        
        # Snare build is most common
        return FillGenerator.generate_snare_build(
            start_tick, build_duration, base_velocity - 20, accelerate=True
        )
    
    def _generate_drop_cue(
        self,
        start_tick: int,
        base_velocity: int
    ) -> List[NoteEvent]:
        """Generate an impact for the 'drop' cue."""
        notes = []
        
        # Crash cymbal
        notes.append(NoteEvent(
            pitch=DrumKit.CRASH,
            start_tick=start_tick,
            duration_ticks=TICKS_PER_BEAT,
            velocity=min(127, base_velocity + 20),
            channel=GM_DRUM_CHANNEL
        ))
        
        # Hard kick
        notes.append(NoteEvent(
            pitch=DrumKit.KICK,
            start_tick=start_tick,
            duration_ticks=TICKS_PER_8TH,
            velocity=min(127, base_velocity + 15),
            channel=GM_DRUM_CHANNEL
        ))
        
        # Optional: second crash for stereo effect
        notes.append(NoteEvent(
            pitch=DrumKit.CRASH_2,
            start_tick=start_tick + 5,  # Tiny offset for width
            duration_ticks=TICKS_PER_BEAT,
            velocity=min(127, base_velocity + 10),
            channel=GM_DRUM_CHANNEL
        ))
        
        return notes
