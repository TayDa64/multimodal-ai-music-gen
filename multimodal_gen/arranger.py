"""
Song Arranger Module

Generates song structure with section timing, texture automation,
and arrangement intelligence. Converts parsed prompts into a
timeline of musical sections.

Professional arrangement techniques:
- Intro with filtered/reduced elements
- Drop/Chorus with full instrumentation
- Variation with added/changed elements  
- Breakdown with sparse arrangement
- Outro with gradual reduction/fade
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
import random

from .prompt_parser import ParsedPrompt
from .motif_engine import Motif, MotifGenerator, MotifLibrary
from .tension_arc import TensionArc, TensionArcGenerator, ArcShape, TensionConfig
from .utils import (
    TICKS_PER_BEAT,
    TICKS_PER_BAR_4_4,
    bars_to_ticks,
    ticks_to_seconds,
    GENRE_DEFAULTS,
)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class SectionType(Enum):
    """Types of song sections with typical characteristics."""
    INTRO = 'intro'           # Low energy, filtered, sparse
    VERSE = 'verse'           # Medium energy, foundation elements
    PRE_CHORUS = 'pre_chorus' # Building energy
    CHORUS = 'chorus'         # High energy, full arrangement
    DROP = 'drop'             # Maximum energy (electronic)
    BREAKDOWN = 'breakdown'   # Reduced, atmospheric
    BUILDUP = 'buildup'       # Rising tension
    BRIDGE = 'bridge'         # Contrast section
    OUTRO = 'outro'           # Decreasing energy, fade
    VARIATION = 'variation'   # Modified repeat of previous


@dataclass
class MotifAssignment:
    """Defines which motif variant to use for a section."""
    motif_index: int                    # Which motif (0, 1, 2...)
    transformation: str = "original"    # "original", "invert", "retrograde", "augment", "diminish", "sequence"
    transform_params: Optional[Dict] = None  # e.g., {"pivot": 60} for invert, {"steps": 3} for sequence
    
    def __post_init__(self):
        """Initialize transform_params to empty dict if None."""
        if self.transform_params is None:
            self.transform_params = {}


@dataclass
class SectionConfig:
    """Configuration for a section type."""
    typical_bars: int = 8
    energy_level: float = 0.5        # 0.0-1.0
    drum_density: float = 0.5        # 0.0-1.0
    instrument_density: float = 0.5  # 0.0-1.0
    texture_amount: float = 0.5      # 0.0-1.0
    filter_cutoff: float = 1.0       # 0.0-1.0 (1.0 = fully open)
    
    # Which elements are active
    enable_kick: bool = True
    enable_snare: bool = True
    enable_hihat: bool = True
    enable_bass: bool = True
    enable_chords: bool = True
    enable_melody: bool = False
    enable_textures: bool = False


# Default configurations for each section type
SECTION_CONFIGS: Dict[SectionType, SectionConfig] = {
    SectionType.INTRO: SectionConfig(
        typical_bars=8,
        energy_level=0.4,
        drum_density=0.4,
        instrument_density=0.4,
        texture_amount=0.8,
        filter_cutoff=0.5,
        enable_kick=True,    # Sparse kick to establish groove early
        enable_snare=False,
        enable_hihat=True,
        enable_bass=True,    # Subtle bass intro
        enable_chords=True,
        enable_melody=False,
        enable_textures=True,
    ),
    SectionType.VERSE: SectionConfig(
        typical_bars=8,
        energy_level=0.5,
        drum_density=0.6,
        instrument_density=0.5,
        texture_amount=0.3,
        filter_cutoff=0.8,
        enable_kick=True,
        enable_snare=True,
        enable_hihat=True,
        enable_bass=True,
        enable_chords=True,
    ),
    SectionType.PRE_CHORUS: SectionConfig(
        typical_bars=4,
        energy_level=0.7,
        drum_density=0.7,
        instrument_density=0.6,
        texture_amount=0.4,
        filter_cutoff=0.9,
        enable_kick=True,
        enable_snare=True,
        enable_hihat=True,
        enable_bass=True,
        enable_chords=True,
        enable_melody=True,
    ),
    SectionType.CHORUS: SectionConfig(
        typical_bars=8,
        energy_level=0.9,
        drum_density=0.9,
        instrument_density=0.9,
        texture_amount=0.2,
        filter_cutoff=1.0,
        enable_kick=True,
        enable_snare=True,
        enable_hihat=True,
        enable_bass=True,
        enable_chords=True,
        enable_melody=True,
    ),
    SectionType.DROP: SectionConfig(
        typical_bars=8,
        energy_level=1.0,
        drum_density=1.0,
        instrument_density=1.0,
        texture_amount=0.1,
        filter_cutoff=1.0,
        enable_kick=True,
        enable_snare=True,
        enable_hihat=True,
        enable_bass=True,
        enable_chords=True,
        enable_melody=True,
    ),
    SectionType.BREAKDOWN: SectionConfig(
        typical_bars=8,
        energy_level=0.3,
        drum_density=0.3,
        instrument_density=0.5,
        texture_amount=0.9,
        filter_cutoff=0.6,
        enable_kick=True,    # Keep sparse kick for groove
        enable_snare=False,  # No snare for tension
        enable_hihat=True,   # Light hi-hats for continuity
        enable_bass=True,    # Keep bass for foundation
        enable_chords=True,
        enable_textures=True,
    ),
    SectionType.BUILDUP: SectionConfig(
        typical_bars=4,
        energy_level=0.6,
        drum_density=0.6,
        instrument_density=0.5,
        texture_amount=0.5,
        filter_cutoff=0.7,
        enable_kick=True,
        enable_snare=True,   # Snare rolls for tension
        enable_hihat=True,
        enable_bass=True,    # Keep bass during buildup
        enable_chords=True,
    ),
    SectionType.BRIDGE: SectionConfig(
        typical_bars=8,
        energy_level=0.5,
        drum_density=0.5,
        instrument_density=0.6,
        texture_amount=0.4,
        filter_cutoff=0.85,
        enable_kick=True,
        enable_snare=True,
        enable_hihat=True,
        enable_bass=True,
        enable_chords=True,
    ),
    SectionType.OUTRO: SectionConfig(
        typical_bars=8,
        energy_level=0.4,
        drum_density=0.4,
        instrument_density=0.4,
        texture_amount=0.7,
        filter_cutoff=0.5,
        enable_kick=True,
        enable_snare=True,   # Keep snare for groove
        enable_hihat=True,
        enable_bass=True,    # Keep bass to the end
        enable_chords=True,
        enable_textures=True,
    ),
    SectionType.VARIATION: SectionConfig(
        typical_bars=8,
        energy_level=0.85,
        drum_density=0.85,
        instrument_density=0.9,
        texture_amount=0.2,
        filter_cutoff=1.0,
        enable_kick=True,
        enable_snare=True,
        enable_hihat=True,
        enable_bass=True,
        enable_chords=True,
        enable_melody=True,
    ),
}


@dataclass
class SongSection:
    """
    Represents a section in the song arrangement.
    
    Contains all information needed to generate MIDI for this section.
    """
    section_type: SectionType
    start_tick: int
    end_tick: int
    bars: int
    config: SectionConfig
    
    # Variation control
    variation_seed: int = 0
    pattern_variation: int = 0  # Which pattern variant to use
    
    # Automation points (normalized 0-1)
    filter_automation: List[Tuple[int, float]] = field(default_factory=list)
    volume_automation: List[Tuple[int, float]] = field(default_factory=list)
    
    @property
    def duration_ticks(self) -> int:
        return self.end_tick - self.start_tick
    
    def duration_seconds(self, bpm: float) -> float:
        return ticks_to_seconds(self.duration_ticks, bpm)


@dataclass
class Arrangement:
    """Complete song arrangement with all sections."""
    sections: List[SongSection]
    total_bars: int
    total_ticks: int
    bpm: float
    time_signature: Tuple[int, int]
    
    # NEW: Motif fields for thematic coherence
    motifs: List[Motif] = field(default_factory=list)
    motif_assignments: Dict[str, MotifAssignment] = field(default_factory=dict)
    # Key is section name like "verse_1", "chorus_1", etc.

    # NEW: Tension arc for emotional narrative shaping
    tension_arc: Optional[TensionArc] = None
    
    def duration_seconds(self) -> float:
        return ticks_to_seconds(self.total_ticks, self.bpm)
    
    def get_section_at_tick(self, tick: int) -> Optional[SongSection]:
        """Get the section containing a given tick position."""
        for section in self.sections:
            if section.start_tick <= tick < section.end_tick:
                return section
        return None


# =============================================================================
# GENRE-SPECIFIC MOTIF MAPPINGS
# =============================================================================

# Genre-specific motif mapping presets
GENRE_MOTIF_MAPPINGS: Dict[str, Dict[str, MotifAssignment]] = {
    "pop": {
        "intro": MotifAssignment(0, "original", {}),
        "verse": MotifAssignment(0, "original", {}),
        "pre_chorus": MotifAssignment(0, "sequence", {"steps": 2}),
        "chorus": MotifAssignment(1, "original", {}),
        "bridge": MotifAssignment(0, "invert", {}),
        "outro": MotifAssignment(0, "original", {}),
    },
    "hip_hop": {
        "intro": MotifAssignment(0, "original", {}),
        "verse": MotifAssignment(0, "original", {}),
        "hook": MotifAssignment(1, "original", {}),
        "bridge": MotifAssignment(0, "sequence", {"steps": -2}),
        "outro": MotifAssignment(0, "original", {}),
    },
    "trap": {
        "intro": MotifAssignment(0, "diminish", {"factor": 2.0}),
        "drop": MotifAssignment(0, "original", {}),
        "breakdown": MotifAssignment(0, "retrograde", {}),
        "buildup": MotifAssignment(0, "sequence", {"steps": 2}),
        "outro": MotifAssignment(0, "augment", {"factor": 2.0}),
    },
    "trap_soul": {
        "intro": MotifAssignment(0, "diminish", {"factor": 2.0}),
        "verse": MotifAssignment(0, "original", {}),
        "chorus": MotifAssignment(1, "original", {}),
        "breakdown": MotifAssignment(0, "invert", {}),
        "outro": MotifAssignment(0, "retrograde", {}),
    },
    "jazz": {
        "intro": MotifAssignment(0, "diminish", {"factor": 0.5}),
        "head": MotifAssignment(0, "original", {}),
        "solo": MotifAssignment(0, "invert", {}),
        "bridge": MotifAssignment(1, "retrograde", {}),
        "outro": MotifAssignment(0, "augment", {"factor": 2.0}),
    },
    "classical": {
        "exposition": MotifAssignment(0, "original", {}),
        "development": MotifAssignment(0, "invert", {}),
        "recapitulation": MotifAssignment(0, "retrograde", {}),
        "coda": MotifAssignment(0, "augment", {"factor": 2.0}),
    },
    "lofi": {
        "intro": MotifAssignment(0, "original", {}),
        "verse": MotifAssignment(0, "original", {}),
        "breakdown": MotifAssignment(0, "diminish", {"factor": 2.0}),
        "variation": MotifAssignment(0, "sequence", {"steps": 2}),
        "outro": MotifAssignment(0, "retrograde", {}),
    },
    "boom_bap": {
        "intro": MotifAssignment(0, "original", {}),
        "verse": MotifAssignment(0, "original", {}),
        "chorus": MotifAssignment(1, "original", {}),
        "bridge": MotifAssignment(0, "invert", {}),
        "outro": MotifAssignment(0, "original", {}),
    },
    "house": {
        "intro": MotifAssignment(0, "diminish", {"factor": 2.0}),
        "buildup": MotifAssignment(0, "sequence", {"steps": 2}),
        "drop": MotifAssignment(0, "original", {}),
        "breakdown": MotifAssignment(1, "original", {}),
        "outro": MotifAssignment(0, "augment", {"factor": 2.0}),
    },
    "rnb": {
        "intro": MotifAssignment(0, "original", {}),
        "verse": MotifAssignment(0, "original", {}),
        "chorus": MotifAssignment(1, "original", {}),
        "bridge": MotifAssignment(0, "invert", {}),
        "outro": MotifAssignment(0, "retrograde", {}),
    },
}


# =============================================================================
# GENRE-SPECIFIC ARRANGEMENTS
# =============================================================================

# Common arrangement templates by genre
ARRANGEMENT_TEMPLATES: Dict[str, List[Tuple[SectionType, int]]] = {
    'trap_soul': [
        (SectionType.INTRO, 4),
        (SectionType.DROP, 8),
        (SectionType.VARIATION, 8),
        (SectionType.BREAKDOWN, 8),
        (SectionType.BUILDUP, 4),
        (SectionType.DROP, 8),
        (SectionType.OUTRO, 4),
    ],
    'rnb': [
        # R&B arrangement - continuous, flowing sections without big gaps
        (SectionType.INTRO, 4),
        (SectionType.VERSE, 8),
        (SectionType.CHORUS, 8),
        (SectionType.VERSE, 8),
        (SectionType.CHORUS, 8),
        (SectionType.BRIDGE, 4),
        (SectionType.CHORUS, 8),
        (SectionType.OUTRO, 4),
    ],
    'trap': [
        (SectionType.INTRO, 4),
        (SectionType.DROP, 8),
        (SectionType.DROP, 8),
        (SectionType.BREAKDOWN, 4),
        (SectionType.BUILDUP, 4),
        (SectionType.DROP, 8),
        (SectionType.OUTRO, 4),
    ],
    'lofi': [
        (SectionType.INTRO, 4),
        (SectionType.VERSE, 8),
        (SectionType.VERSE, 8),
        (SectionType.BREAKDOWN, 4),
        (SectionType.VERSE, 8),
        (SectionType.VARIATION, 8),
        (SectionType.OUTRO, 4),
    ],
    'boom_bap': [
        (SectionType.INTRO, 4),
        (SectionType.VERSE, 16),
        (SectionType.CHORUS, 8),
        (SectionType.VERSE, 16),
        (SectionType.CHORUS, 8),
        (SectionType.OUTRO, 4),
    ],
    'house': [
        (SectionType.INTRO, 8),
        (SectionType.BUILDUP, 8),
        (SectionType.DROP, 16),
        (SectionType.BREAKDOWN, 8),
        (SectionType.BUILDUP, 8),
        (SectionType.DROP, 16),
        (SectionType.OUTRO, 8),
    ],
    'ambient': [
        (SectionType.INTRO, 8),
        (SectionType.VERSE, 16),
        (SectionType.BREAKDOWN, 8),
        (SectionType.VERSE, 16),
        (SectionType.OUTRO, 8),
    ],
    # Ethiopian arrangements - typically feature call-and-response patterns
    'ethiopian': [
        (SectionType.INTRO, 4),
        (SectionType.VERSE, 8),
        (SectionType.CHORUS, 8),
        (SectionType.VERSE, 8),
        (SectionType.BREAKDOWN, 4),
        (SectionType.CHORUS, 8),
        (SectionType.VARIATION, 8),
        (SectionType.OUTRO, 4),
    ],
    'ethio_jazz': [
        (SectionType.INTRO, 8),
        (SectionType.VERSE, 8),
        (SectionType.VARIATION, 8),  # Solo/improvisation section
        (SectionType.CHORUS, 8),
        (SectionType.BREAKDOWN, 8),
        (SectionType.VARIATION, 8),
        (SectionType.CHORUS, 8),
        (SectionType.OUTRO, 8),
    ],
    'ethiopian_traditional': [
        (SectionType.INTRO, 4),
        (SectionType.VERSE, 8),  # Call section
        (SectionType.CHORUS, 4),  # Response
        (SectionType.VERSE, 8),
        (SectionType.CHORUS, 4),
        (SectionType.VARIATION, 8),
        (SectionType.OUTRO, 4),
    ],
    'eskista': [
        # Eskista (shoulder dance) - energetic with build-ups
        (SectionType.INTRO, 4),
        (SectionType.BUILDUP, 4),
        (SectionType.DROP, 8),  # Main dance section
        (SectionType.VARIATION, 8),
        (SectionType.BREAKDOWN, 4),
        (SectionType.BUILDUP, 4),
        (SectionType.DROP, 8),
        (SectionType.OUTRO, 4),
    ],
}


# =============================================================================
# ARRANGER CLASS
# =============================================================================

class Arranger:
    """
    Generates song arrangements from parsed prompts.
    
    Creates a timeline of sections with appropriate configurations
    for each section type, respecting genre conventions.
    """
    
    # Default duration: 3 minutes (~180 seconds) for a complete song feel
    DEFAULT_DURATION_SECONDS = 180.0
    
    def __init__(
        self,
        target_duration_seconds: Optional[float] = None,
        min_bars: int = 48,   # ~2 minutes at 90 BPM
        max_bars: int = 128,  # ~4.5 minutes at 90 BPM
    ):
        """
        Initialize the arranger.
        
        Args:
            target_duration_seconds: Target song length (None = use DEFAULT_DURATION_SECONDS)
            min_bars: Minimum arrangement length in bars
            max_bars: Maximum arrangement length in bars
        """
        # Use default duration if not specified
        self.target_duration = target_duration_seconds if target_duration_seconds is not None else self.DEFAULT_DURATION_SECONDS
        self.min_bars = min_bars
        self.max_bars = max_bars
    
    def create_arrangement(self, parsed: ParsedPrompt) -> Arrangement:
        """
        Create a complete song arrangement from parsed prompt.
        
        Args:
            parsed: ParsedPrompt from the prompt parser
        
        Returns:
            Arrangement with all sections configured
        """
        # Get template for genre
        template = self._get_template(parsed.genre, parsed.section_hints)
        
        # Adjust template to meet target duration
        template = self._adjust_to_duration(template, parsed.bpm)
        
        # Build sections
        sections = []
        current_tick = 0
        variation_counter = 0
        
        for section_type, bars in template:
            # Get base config
            config = self._get_section_config(section_type, parsed)
            
            # Calculate ticks
            ticks = bars_to_ticks(bars)
            
            # Create section
            section = SongSection(
                section_type=section_type,
                start_tick=current_tick,
                end_tick=current_tick + ticks,
                bars=bars,
                config=config,
                variation_seed=random.randint(0, 10000),
                pattern_variation=variation_counter % 4,
            )
            
            # Add automation for intro/outro
            if section_type == SectionType.INTRO:
                section.filter_automation = self._create_intro_automation(ticks)
                section.volume_automation = self._create_fade_in(ticks)
            elif section_type == SectionType.OUTRO:
                section.filter_automation = self._create_outro_automation(ticks)
                section.volume_automation = self._create_fade_out(ticks)
            elif section_type == SectionType.BUILDUP:
                section.filter_automation = self._create_buildup_automation(ticks)
            
            sections.append(section)
            current_tick += ticks
            
            # Track variations
            if section_type in [SectionType.DROP, SectionType.CHORUS, SectionType.VERSE]:
                variation_counter += 1
        
        # Calculate totals
        total_ticks = current_tick
        total_bars = sum(s.bars for s in sections)
        
        tension_arc = None
        try:
            generator = TensionArcGenerator()
            shape_override = getattr(parsed, "tension_arc_shape", None)
            intensity = getattr(parsed, "tension_intensity", None)

            if shape_override:
                shape_key = str(shape_override).strip().lower()
                shape_aliases = {
                    "gradual_build": "linear_build",
                    "build": "linear_build",
                    "linear": "linear_build",
                    "plateau": "flat",
                    "swell": "peak_middle",
                }
                shape_key = shape_aliases.get(shape_key, shape_key)

                arc_shape = ArcShape(shape_key)
                config = TensionConfig()
                if intensity is not None:
                    try:
                        it = max(0.0, min(1.0, float(intensity)))
                        # Expand/compress the tension range around base tension.
                        min_t = max(0.0, 0.5 - 0.3 * it)
                        max_t = min(1.0, 0.5 + 0.5 * it)
                        config.tension_range = (min_t, max_t)
                    except Exception:
                        pass

                tension_arc = generator.create_arc(
                    arc_shape,
                    num_sections=len(sections),
                    config=config,
                )

                # Label points with section names for UI/debugging.
                for pt, sec in zip(tension_arc.points, sections):
                    pt.label = sec.section_type.value
            else:
                tension_arc = generator.create_arc_for_sections(
                    [s.section_type.value for s in sections],
                    genre=(parsed.genre or "pop")
                )
        except Exception:
            # Keep tension arc optional and never block generation.
            tension_arc = None

        return Arrangement(
            sections=sections,
            total_bars=total_bars,
            total_ticks=total_ticks,
            bpm=parsed.bpm,
            time_signature=parsed.time_signature,
            tension_arc=tension_arc,
        )
    
    def _get_template(
        self,
        genre: str,
        section_hints: List[str]
    ) -> List[Tuple[SectionType, int]]:
        """Get arrangement template for genre, with hint modifications."""
        # Start with genre template
        template = ARRANGEMENT_TEMPLATES.get(
            genre,
            ARRANGEMENT_TEMPLATES['trap_soul']
        ).copy()
        
        # Apply section hints
        if 'switch' in section_hints or 'switch-up' in ''.join(section_hints):
            # Add extra variation section
            insert_pos = len(template) // 2
            template.insert(insert_pos, (SectionType.VARIATION, 8))
        
        if 'breakdown' in section_hints:
            # Ensure we have a breakdown
            has_breakdown = any(s[0] == SectionType.BREAKDOWN for s in template)
            if not has_breakdown:
                insert_pos = len(template) * 2 // 3
                template.insert(insert_pos, (SectionType.BREAKDOWN, 8))
        
        return template
    
    def _adjust_to_duration(
        self,
        template: List[Tuple[SectionType, int]],
        bpm: float
    ) -> List[Tuple[SectionType, int]]:
        """Adjust template bars to meet target duration."""
        if self.target_duration is None:
            return template
        
        # Calculate current duration
        total_bars = sum(bars for _, bars in template)
        current_duration = ticks_to_seconds(bars_to_ticks(total_bars), bpm)
        
        # Scale factor
        scale = self.target_duration / current_duration
        
        # Apply scaling (round to nearest 4 bars)
        adjusted = []
        for section_type, bars in template:
            new_bars = max(4, round(bars * scale / 4) * 4)
            adjusted.append((section_type, new_bars))
        
        # Ensure within limits
        total = sum(b for _, b in adjusted)
        if total < self.min_bars:
            # Extend main sections
            for i, (st, b) in enumerate(adjusted):
                if st in [SectionType.DROP, SectionType.VERSE, SectionType.CHORUS]:
                    adjusted[i] = (st, b + 8)
                    total += 8
                    if total >= self.min_bars:
                        break
        
        return adjusted
    
    def _get_section_config(
        self,
        section_type: SectionType,
        parsed: ParsedPrompt
    ) -> SectionConfig:
        """Get section config with genre/prompt-specific modifications."""
        # Start with base config
        base = SECTION_CONFIGS.get(section_type, SectionConfig())
        
        # Create modified copy
        config = SectionConfig(
            typical_bars=base.typical_bars,
            energy_level=base.energy_level,
            drum_density=base.drum_density,
            instrument_density=base.instrument_density,
            texture_amount=base.texture_amount,
            filter_cutoff=base.filter_cutoff,
            enable_kick=base.enable_kick,
            enable_snare=base.enable_snare,
            enable_hihat=base.enable_hihat,
            enable_bass=base.enable_bass,
            enable_chords=base.enable_chords,
            enable_melody=base.enable_melody,
            enable_textures=base.enable_textures,
        )
        
        # Apply genre modifications
        genre_config = GENRE_DEFAULTS.get(parsed.genre, {})
        
        # Lo-fi has more textures
        if parsed.genre == 'lofi':
            config.texture_amount = min(1.0, config.texture_amount + 0.2)
        
        # House has higher drum density
        if parsed.genre == 'house':
            config.drum_density = min(1.0, config.drum_density + 0.1)
        
        # Ambient has lower drum density
        if parsed.genre == 'ambient':
            config.drum_density = max(0.0, config.drum_density - 0.2)
        
        # Apply mood modifications
        if parsed.mood == 'dark':
            config.filter_cutoff = max(0.3, config.filter_cutoff - 0.1)
        elif parsed.mood == 'bright':
            config.filter_cutoff = min(1.0, config.filter_cutoff + 0.1)
        
        # Enable textures if specified in prompt
        if parsed.textures:
            config.enable_textures = True
            config.texture_amount = max(0.5, config.texture_amount)
        
        return config
    
    def _create_intro_automation(self, duration_ticks: int) -> List[Tuple[int, float]]:
        """Create filter sweep automation for intro (low to high)."""
        points = []
        num_points = 8
        for i in range(num_points + 1):
            tick = int(duration_ticks * i / num_points)
            value = 0.3 + (0.7 * (i / num_points))  # 0.3 to 1.0
            points.append((tick, value))
        return points
    
    def _create_outro_automation(self, duration_ticks: int) -> List[Tuple[int, float]]:
        """Create filter sweep automation for outro (high to low)."""
        points = []
        num_points = 8
        for i in range(num_points + 1):
            tick = int(duration_ticks * i / num_points)
            value = 1.0 - (0.7 * (i / num_points))  # 1.0 to 0.3
            points.append((tick, value))
        return points
    
    def _create_buildup_automation(self, duration_ticks: int) -> List[Tuple[int, float]]:
        """Create filter sweep automation for buildup."""
        points = []
        num_points = 8
        for i in range(num_points + 1):
            tick = int(duration_ticks * i / num_points)
            # Exponential curve for more dramatic buildup
            progress = i / num_points
            value = 0.4 + (0.6 * (progress ** 2))
            points.append((tick, value))
        return points
    
    def _create_fade_in(self, duration_ticks: int) -> List[Tuple[int, float]]:
        """Create volume fade in automation."""
        return [
            (0, 0.0),
            (duration_ticks // 4, 0.5),
            (duration_ticks // 2, 0.8),
            (duration_ticks, 1.0),
        ]
    
    def _create_fade_out(self, duration_ticks: int) -> List[Tuple[int, float]]:
        """Create volume fade out automation."""
        return [
            (0, 1.0),
            (duration_ticks // 2, 0.8),
            (duration_ticks * 3 // 4, 0.4),
            (duration_ticks, 0.0),
        ]


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_arrangement(parsed: ParsedPrompt, **kwargs) -> Arrangement:
    """Create an arrangement from a parsed prompt."""
    arranger = Arranger(**kwargs)
    return arranger.create_arrangement(parsed)


def get_default_arrangement(bpm: float = 87.0, genre: str = 'trap_soul') -> Arrangement:
    """Get a default arrangement for testing."""
    from .prompt_parser import ParsedPrompt
    
    parsed = ParsedPrompt(
        bpm=bpm,
        genre=genre,
        key='C',
    )
    return create_arrangement(parsed)


# =============================================================================
# MOTIF-AWARE ARRANGEMENT FUNCTIONS
# =============================================================================

def get_default_motif_mapping(genre: str) -> Dict[str, MotifAssignment]:
    """
    Get genre-appropriate default motif assignments for sections.
    
    Different genres use motifs differently:
    - Classical: Heavy use of inversion, retrograde, augmentation
    - Pop/Hip-hop: Simpler - mostly original and sequence
    - Jazz: More variation with diminution and complex sequences
    
    Args:
        genre: Genre name
        
    Returns:
        Dict mapping section types to MotifAssignments
    """
    # Return genre-specific mapping or default to pop-style
    return GENRE_MOTIF_MAPPINGS.get(genre, GENRE_MOTIF_MAPPINGS.get("pop", {}))


def generate_arrangement_with_motifs(
    parsed: ParsedPrompt,
    num_motifs: int = 2,
    seed: Optional[int] = None,
    target_duration_seconds: Optional[float] = None
) -> Arrangement:
    """
    Generate arrangement with thematic coherence through motifs.
    
    Creates 1-3 motifs and assigns transformations to each section:
    - intro: motif[0] fragment (first half)
    - verse: motif[0] original
    - pre_chorus: motif[0] sequence(+3) - transposed up
    - chorus: motif[1] original (contrast motif)
    - bridge: motif[0] inversion + motif[1] diminution
    - outro: motif[0] retrograde (callback to intro)
    
    Args:
        parsed: ParsedPrompt with key, scale, tempo, genre info
        num_motifs: Number of distinct motifs to generate (1-3)
        seed: Random seed for reproducibility
        
    Returns:
        Arrangement with motifs and section assignments
    """
    # Set random seed if provided
    if seed is not None:
        random.seed(seed)
    
    # Clamp num_motifs to valid range
    num_motifs = max(1, min(3, num_motifs))
    
    # Create base arrangement
    arranger = Arranger(target_duration_seconds=target_duration_seconds)
    arrangement = arranger.create_arrangement(parsed)
    
    # Generate motifs using MotifGenerator
    generator = MotifGenerator()
    motifs = []
    
    for i in range(num_motifs):
        # Generate motif appropriate for the genre
        context = {
            'chord_type': 'minor7' if parsed.scale_type.name == 'MINOR' else 'major7',
            'scale': parsed.scale_type.name.lower(),
            'mood': parsed.mood if hasattr(parsed, 'mood') and parsed.mood else 'neutral',
        }
        motif = generator.generate_motif(parsed.genre, context)
        # Rename for clarity
        motif.name = f"{parsed.genre.capitalize()} Motif {i+1}"
        motifs.append(motif)
    
    arrangement.motifs = motifs
    
    # Get genre-specific motif mappings
    mapping_template = get_default_motif_mapping(parsed.genre)
    
    # Assign motifs to sections
    motif_assignments = {}
    section_counters = {}  # Track how many times each section type appears
    
    for i, section in enumerate(arrangement.sections):
        section_type = section.section_type.value
        
        # Track section occurrences for unique naming
        if section_type not in section_counters:
            section_counters[section_type] = 0
        section_counters[section_type] += 1
        
        # Create section name like "verse_1", "chorus_2"
        section_name = f"{section_type}_{section_counters[section_type]}"
        
        # Get assignment from template or use defaults
        if section_type in mapping_template:
            assignment = mapping_template[section_type]
        else:
            # Default: use motif 0 with original transformation
            assignment = MotifAssignment(
                motif_index=0,
                transformation="original",
                transform_params={}
            )
        
        # Ensure motif_index is valid
        if assignment.motif_index >= len(motifs):
            assignment = MotifAssignment(
                motif_index=0,
                transformation=assignment.transformation,
                transform_params=assignment.transform_params
            )
        
        motif_assignments[section_name] = assignment
    
    arrangement.motif_assignments = motif_assignments
    
    return arrangement


def get_section_motif(
    arrangement: Arrangement,
    section_name: str
) -> Optional[Motif]:
    """
    Get the transformed motif for a specific section.
    
    Args:
        arrangement: Arrangement with motifs and assignments
        section_name: e.g., "verse_1", "chorus_2"
        
    Returns:
        Transformed Motif for the section, or None if not assigned
    """
    # Check if section has an assignment
    if section_name not in arrangement.motif_assignments:
        return None
    
    assignment = arrangement.motif_assignments[section_name]
    
    # Check if motif index is valid
    if assignment.motif_index >= len(arrangement.motifs):
        return None
    
    # Get base motif
    base_motif = arrangement.motifs[assignment.motif_index]
    
    # Apply transformation
    transformation = assignment.transformation.lower()
    params = assignment.transform_params or {}
    
    if transformation == "original":
        return base_motif
    elif transformation == "invert":
        pivot = params.get("pivot", 0)
        return base_motif.invert(pivot)
    elif transformation == "retrograde":
        return base_motif.retrograde()
    elif transformation == "augment":
        factor = params.get("factor", 2.0)
        return base_motif.augment(factor)
    elif transformation == "diminish":
        factor = params.get("factor", 2.0)
        return base_motif.diminish(factor)
    elif transformation == "sequence":
        steps = params.get("steps", 2)
        # For sequence, return the transposed version at the specified step
        # Create a simple sequence of [0, steps] and return the transposed motif
        sequences = base_motif.sequence([0, steps])
        return sequences[1] if len(sequences) > 1 else base_motif
    else:
        # Unknown transformation, return original
        return base_motif


if __name__ == '__main__':
    # Quick test
    from .prompt_parser import parse_prompt
    
    test_prompts = [
        "dark trap soul at 87 BPM in C minor with sidechained 808",
        "lofi hip hop beat with rhodes and vinyl at 85bpm",
        "house beat at 124 BPM with breakdown",
    ]
    
    for prompt in test_prompts:
        print(f"\nPrompt: {prompt}")
        parsed = parse_prompt(prompt)
        arrangement = create_arrangement(parsed)
        
        print(f"  Total: {arrangement.total_bars} bars ({arrangement.duration_seconds():.1f}s)")
        print("  Sections:")
        for section in arrangement.sections:
            print(f"    - {section.section_type.value}: {section.bars} bars")
