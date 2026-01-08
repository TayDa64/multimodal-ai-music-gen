"""
Pattern Library - Comprehensive musical pattern collections by genre.

Provides drum patterns, bass lines, chord voicings, and melodic fragments
for multiple genres that can be combined and varied during generation.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set
from enum import Enum
import random


class PatternType(Enum):
    """Types of musical patterns."""
    DRUM = "drum"
    BASS = "bass"
    CHORD = "chord"
    MELODY = "melody"
    ARPEGGIO = "arpeggio"
    FILL = "fill"
    TRANSITION = "transition"


class PatternIntensity(Enum):
    """Intensity level of pattern."""
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    INTENSE = "intense"


@dataclass
class Pattern:
    """A musical pattern that can be used in generation."""
    name: str
    pattern_type: PatternType
    genre: str
    notes: List[Tuple[int, int, int, int]]  # (tick, duration, pitch, velocity)
    length_beats: int = 4
    intensity: PatternIntensity = PatternIntensity.MEDIUM
    tags: Set[str] = field(default_factory=set)
    variations: List[str] = field(default_factory=list)  # Names of related patterns
    
    # Musical characteristics
    time_signature: Tuple[int, int] = (4, 4)
    swing_amount: float = 0.0  # 0-1
    syncopation_level: float = 0.5  # 0-1
    
    # Metadata
    description: str = ""
    section_types: Set[str] = field(default_factory=lambda: {"verse", "chorus"})


@dataclass
class DrumPattern(Pattern):
    """Drum-specific pattern with instrument mapping."""
    instrument_map: Dict[int, str] = field(default_factory=dict)
    # MIDI note -> instrument name (kick=36, snare=38, hihat=42, etc.)
    
    has_ghost_notes: bool = False
    fill_points: List[int] = field(default_factory=list)  # Ticks where fills can go


@dataclass
class BassPattern(Pattern):
    """Bass-specific pattern with root-relative notation."""
    root_relative: bool = True  # Notes relative to chord root
    octave: int = 2  # Default octave
    follows_kick: bool = False  # Locks to kick drum


@dataclass
class ChordPattern(Pattern):
    """Chord voicing pattern."""
    voicing_type: str = "basic"  # basic, spread, drop2, drop3, cluster
    inversion: int = 0  # 0=root, 1=first, 2=second, etc.


@dataclass 
class MelodyPattern(Pattern):
    """Melodic fragment pattern."""
    scale_degrees: List[int] = field(default_factory=list)  # 1-7 scale degrees
    contour: str = "ascending"  # ascending, descending, arch, wave


# Pattern constants (MIDI ticks per beat = 480)
TICKS_PER_BEAT = 480
TICKS_PER_BAR = TICKS_PER_BEAT * 4

# Standard drum MIDI mapping
DRUM_MAP = {
    "kick": 36,
    "snare": 38,
    "rimshot": 37,
    "clap": 39,
    "hihat_closed": 42,
    "hihat_open": 46,
    "hihat_pedal": 44,
    "tom_low": 45,
    "tom_mid": 47,
    "tom_high": 50,
    "crash": 49,
    "ride": 51,
    "ride_bell": 53,
}


class PatternLibrary:
    """
    Central repository for all musical patterns.
    
    Usage:
        library = PatternLibrary()
        
        # Get all hip-hop drum patterns
        patterns = library.get_patterns("hip_hop", PatternType.DRUM)
        
        # Get high-intensity patterns for chorus
        chorus_patterns = library.get_patterns_for_section(
            genre="pop",
            section="chorus",
            intensity=PatternIntensity.HIGH
        )
    """
    
    def __init__(self):
        self.patterns: Dict[str, Dict[PatternType, List[Pattern]]] = {}
        self._load_all_patterns()
    
    def _load_all_patterns(self):
        """Load all built-in patterns."""
        self._load_hip_hop_patterns()
        self._load_pop_patterns()
        self._load_jazz_patterns()
        self._load_rock_patterns()
        self._load_edm_patterns()
        self._load_rnb_patterns()
        self._load_funk_patterns()
        self._load_latin_patterns()
        self._load_reggae_patterns()
        self._load_afrobeat_patterns()
    
    def get_patterns(
        self,
        genre: str,
        pattern_type: PatternType,
        intensity: Optional[PatternIntensity] = None,
        tags: Optional[Set[str]] = None
    ) -> List[Pattern]:
        """Get patterns matching criteria."""
        if genre not in self.patterns:
            return []
        
        if pattern_type not in self.patterns[genre]:
            return []
        
        results = self.patterns[genre][pattern_type]
        
        # Filter by intensity
        if intensity is not None:
            results = [p for p in results if p.intensity == intensity]
        
        # Filter by tags
        if tags is not None:
            results = [p for p in results if tags.issubset(p.tags)]
        
        return results
    
    def get_patterns_for_section(
        self,
        genre: str,
        section: str,
        intensity: Optional[PatternIntensity] = None
    ) -> Dict[PatternType, List[Pattern]]:
        """Get all pattern types suitable for a section."""
        result = {}
        
        if genre not in self.patterns:
            return result
        
        for pattern_type, patterns in self.patterns[genre].items():
            matching = [
                p for p in patterns
                if section in p.section_types
            ]
            
            if intensity is not None:
                matching = [p for p in matching if p.intensity == intensity]
            
            if matching:
                result[pattern_type] = matching
        
        return result
    
    def get_pattern_by_name(self, name: str) -> Optional[Pattern]:
        """Get a specific pattern by name."""
        for genre_patterns in self.patterns.values():
            for patterns in genre_patterns.values():
                for pattern in patterns:
                    if pattern.name == name:
                        return pattern
        return None
    
    def get_random_pattern(
        self,
        genre: str,
        pattern_type: PatternType,
        seed: Optional[int] = None
    ) -> Optional[Pattern]:
        """Get a random pattern matching criteria."""
        patterns = self.get_patterns(genre, pattern_type)
        if not patterns:
            return None
        
        if seed is not None:
            rng = random.Random(seed)
            return rng.choice(patterns)
        
        return random.choice(patterns)
    
    def get_compatible_patterns(
        self,
        base_pattern: Pattern,
        pattern_type: PatternType
    ) -> List[Pattern]:
        """Get patterns that work well with a base pattern."""
        # Get patterns from same genre
        candidates = self.get_patterns(base_pattern.genre, pattern_type)
        
        # Filter by intensity (similar intensity levels work well together)
        intensity_map = {
            PatternIntensity.MINIMAL: {PatternIntensity.MINIMAL, PatternIntensity.LOW},
            PatternIntensity.LOW: {PatternIntensity.MINIMAL, PatternIntensity.LOW, PatternIntensity.MEDIUM},
            PatternIntensity.MEDIUM: {PatternIntensity.LOW, PatternIntensity.MEDIUM, PatternIntensity.HIGH},
            PatternIntensity.HIGH: {PatternIntensity.MEDIUM, PatternIntensity.HIGH, PatternIntensity.INTENSE},
            PatternIntensity.INTENSE: {PatternIntensity.HIGH, PatternIntensity.INTENSE},
        }
        
        compatible_intensities = intensity_map.get(base_pattern.intensity, set())
        compatible = [
            p for p in candidates
            if p.intensity in compatible_intensities
        ]
        
        return compatible
    
    def add_pattern(self, pattern: Pattern):
        """Add a custom pattern to the library."""
        if pattern.genre not in self.patterns:
            self.patterns[pattern.genre] = {}
        
        if pattern.pattern_type not in self.patterns[pattern.genre]:
            self.patterns[pattern.genre][pattern.pattern_type] = []
        
        self.patterns[pattern.genre][pattern.pattern_type].append(pattern)
    
    def list_genres(self) -> List[str]:
        """List all available genres."""
        return list(self.patterns.keys())
    
    def list_patterns(self, genre: str) -> Dict[PatternType, List[str]]:
        """List all pattern names for a genre."""
        result = {}
        
        if genre not in self.patterns:
            return result
        
        for pattern_type, patterns in self.patterns[genre].items():
            result[pattern_type] = [p.name for p in patterns]
        
        return result
    
    # Genre-specific loaders
    def _load_hip_hop_patterns(self):
        """Load hip-hop patterns (boom bap, trap, lo-fi, g-funk)."""
        genre = "hip_hop"
        self.patterns[genre] = {
            PatternType.DRUM: [],
            PatternType.BASS: [],
            PatternType.CHORD: [],
            PatternType.MELODY: [],
            PatternType.ARPEGGIO: [],
            PatternType.FILL: [],
            PatternType.TRANSITION: []
        }
        
        # Boom Bap Drums
        self.patterns[genre][PatternType.DRUM].append(DrumPattern(
            name="boom_bap_basic",
            pattern_type=PatternType.DRUM,
            genre=genre,
            notes=[
                # Kick on 1, 2.5, 3
                (0, 120, 36, 100),
                (240, 120, 36, 95),
                (480, 120, 36, 100),
                # Snare on 2, 4
                (480, 100, 38, 105),
                (1440, 100, 38, 105),
                # Hi-hats on 8ths
                (0, 60, 42, 75),
                (240, 60, 42, 65),
                (480, 60, 42, 75),
                (720, 60, 42, 65),
                (960, 60, 42, 75),
                (1200, 60, 42, 65),
                (1440, 60, 42, 75),
                (1680, 60, 42, 65),
            ],
            instrument_map={36: "kick", 38: "snare", 42: "hihat_closed"},
            length_beats=4,
            intensity=PatternIntensity.MEDIUM,
            tags={"boom_bap", "classic"},
            swing_amount=0.15,
            description="Classic boom bap pattern with swing",
            section_types={"verse", "chorus"}
        ))
        
        # Trap Drums
        self.patterns[genre][PatternType.DRUM].append(DrumPattern(
            name="trap_808_hihat",
            pattern_type=PatternType.DRUM,
            genre=genre,
            notes=[
                # Kick on 1, 3
                (0, 150, 36, 110),
                (960, 150, 36, 110),
                # Snare on 3 (half-time)
                (960, 120, 38, 108),
                # Dense 16th note hi-hats
                (0, 40, 42, 80),
                (120, 40, 42, 60),
                (240, 40, 42, 80),
                (360, 40, 42, 60),
                (480, 40, 42, 75),
                (600, 40, 42, 58),
                (720, 40, 42, 75),
                (840, 40, 42, 58),
                (960, 40, 42, 85),
                (1080, 40, 42, 62),
                (1200, 40, 42, 80),
                (1320, 40, 42, 60),
                (1440, 40, 42, 75),
                (1560, 40, 42, 55),
                (1680, 40, 42, 75),
                (1800, 40, 42, 55),
            ],
            instrument_map={36: "kick", 38: "snare", 42: "hihat_closed"},
            length_beats=4,
            intensity=PatternIntensity.HIGH,
            tags={"trap", "modern", "dense"},
            description="Modern trap with dense hi-hats",
            section_types={"verse", "chorus", "drop"}
        ))
        
        # Lo-Fi Drums
        self.patterns[genre][PatternType.DRUM].append(DrumPattern(
            name="lofi_lazy_groove",
            pattern_type=PatternType.DRUM,
            genre=genre,
            notes=[
                # Kick - laid back
                (0, 140, 36, 85),
                (990, 140, 36, 82),
                # Snare - soft
                (495, 90, 38, 75),
                (1485, 90, 38, 72),
                # Hi-hats - sparse
                (0, 70, 42, 60),
                (510, 70, 42, 55),
                (1000, 70, 42, 58),
                (1510, 70, 42, 52),
            ],
            instrument_map={36: "kick", 38: "snare", 42: "hihat_closed"},
            length_beats=4,
            intensity=PatternIntensity.LOW,
            tags={"lofi", "chill", "laid_back"},
            swing_amount=0.25,
            description="Lazy lo-fi groove with swing",
            section_types={"verse", "chorus"}
        ))
        
        # Hip-Hop Bass Patterns
        self.patterns[genre][PatternType.BASS].append(BassPattern(
            name="hip_hop_bass_basic",
            pattern_type=PatternType.BASS,
            genre=genre,
            notes=[
                (0, 450, 0, 95),  # Root note (relative)
                (960, 450, 0, 90),
            ],
            root_relative=True,
            octave=2,
            follows_kick=True,
            length_beats=4,
            intensity=PatternIntensity.MEDIUM,
            tags={"basic", "locked"},
            description="Basic bass locked to kick"
        ))
        
        self.patterns[genre][PatternType.BASS].append(BassPattern(
            name="hip_hop_bass_syncopated",
            pattern_type=PatternType.BASS,
            genre=genre,
            notes=[
                (0, 200, 0, 100),
                (240, 200, 0, 85),
                (720, 200, 3, 90),  # Minor 3rd
                (960, 400, 0, 95),
            ],
            root_relative=True,
            octave=2,
            length_beats=4,
            intensity=PatternIntensity.MEDIUM,
            tags={"syncopated", "melodic"},
            syncopation_level=0.7,
            description="Syncopated bass line"
        ))
        
        # Hip-Hop Chord Patterns
        self.patterns[genre][PatternType.CHORD].append(ChordPattern(
            name="hip_hop_rhodes_voicing",
            pattern_type=PatternType.CHORD,
            genre=genre,
            notes=[
                # Simple 7th chord voicing (relative to root)
                (0, 1920, 0, 75),   # Root
                (0, 1920, 4, 70),   # Major 3rd
                (0, 1920, 7, 72),   # Perfect 5th
                (0, 1920, 11, 68),  # Major 7th
            ],
            voicing_type="basic",
            length_beats=4,
            intensity=PatternIntensity.LOW,
            tags={"rhodes", "warm"},
            description="Warm Rhodes-style chord voicing"
        ))
        
        # Hip-Hop Melody Patterns
        self.patterns[genre][PatternType.MELODY].append(MelodyPattern(
            name="hip_hop_melody_simple",
            pattern_type=PatternType.MELODY,
            genre=genre,
            notes=[
                (0, 240, 0, 85),    # Root
                (240, 240, 2, 80),  # Major 2nd
                (480, 240, 4, 85),  # Major 3rd
                (720, 240, 7, 82),  # Perfect 5th
                (960, 480, 4, 80),  # Major 3rd
                (1440, 480, 0, 75), # Root
            ],
            scale_degrees=[1, 2, 3, 5, 3, 1],
            contour="arch",
            length_beats=4,
            intensity=PatternIntensity.MEDIUM,
            tags={"simple", "pentatonic"},
            description="Simple pentatonic melody"
        ))
    
    def _load_pop_patterns(self):
        """Load pop patterns (modern pop, 80s, ballad)."""
        genre = "pop"
        self.patterns[genre] = {
            PatternType.DRUM: [],
            PatternType.BASS: [],
            PatternType.CHORD: [],
            PatternType.MELODY: [],
            PatternType.ARPEGGIO: [],
            PatternType.FILL: [],
            PatternType.TRANSITION: []
        }
        
        # Pop Drums
        self.patterns[genre][PatternType.DRUM].append(DrumPattern(
            name="pop_four_on_floor",
            pattern_type=PatternType.DRUM,
            genre=genre,
            notes=[
                # Kick on all beats
                (0, 120, 36, 105),
                (480, 120, 36, 105),
                (960, 120, 36, 105),
                (1440, 120, 36, 105),
                # Snare/clap on 2 and 4
                (480, 100, 39, 100),
                (1440, 100, 39, 100),
                # Hi-hats on 8ths
                (0, 60, 42, 80),
                (240, 60, 42, 70),
                (480, 60, 42, 80),
                (720, 60, 42, 70),
                (960, 60, 42, 80),
                (1200, 60, 42, 70),
                (1440, 60, 42, 80),
                (1680, 60, 42, 70),
            ],
            instrument_map={36: "kick", 39: "clap", 42: "hihat_closed"},
            length_beats=4,
            intensity=PatternIntensity.MEDIUM,
            tags={"four_on_floor", "modern"},
            description="Modern pop 4-on-the-floor",
            section_types={"chorus", "drop"}
        ))
        
        self.patterns[genre][PatternType.DRUM].append(DrumPattern(
            name="pop_80s_gated",
            pattern_type=PatternType.DRUM,
            genre=genre,
            notes=[
                # Kick
                (0, 150, 36, 110),
                (960, 150, 36, 110),
                # Gated snare on 2 and 4
                (480, 200, 38, 115),
                (1440, 200, 38, 115),
                # Hi-hats
                (0, 80, 42, 85),
                (480, 80, 42, 85),
                (960, 80, 42, 85),
                (1440, 80, 42, 85),
            ],
            instrument_map={36: "kick", 38: "snare", 42: "hihat_closed"},
            length_beats=4,
            intensity=PatternIntensity.HIGH,
            tags={"80s", "gated", "reverb"},
            description="80s gated reverb snare",
            section_types={"chorus"}
        ))
        
        # Pop Bass
        self.patterns[genre][PatternType.BASS].append(BassPattern(
            name="pop_bass_synth",
            pattern_type=PatternType.BASS,
            genre=genre,
            notes=[
                (0, 450, 0, 90),
                (480, 450, 0, 88),
                (960, 450, 0, 90),
                (1440, 450, 0, 88),
            ],
            root_relative=True,
            octave=2,
            length_beats=4,
            intensity=PatternIntensity.MEDIUM,
            tags={"synth", "modern"},
            description="Modern synth bass pattern"
        ))
        
        # Pop Chords
        self.patterns[genre][PatternType.CHORD].append(ChordPattern(
            name="pop_triad_spread",
            pattern_type=PatternType.CHORD,
            genre=genre,
            notes=[
                # Spread triad voicing
                (0, 1920, 0, 80),   # Root
                (0, 1920, 7, 75),   # 5th
                (0, 1920, 12, 78),  # Root octave
                (0, 1920, 16, 73),  # 3rd above
            ],
            voicing_type="spread",
            length_beats=4,
            intensity=PatternIntensity.MEDIUM,
            tags={"bright", "open"},
            description="Open spread triad voicing"
        ))
        
        # Pop Melody
        self.patterns[genre][PatternType.MELODY].append(MelodyPattern(
            name="pop_hook_catchy",
            pattern_type=PatternType.MELODY,
            genre=genre,
            notes=[
                (0, 240, 7, 90),
                (240, 240, 5, 85),
                (480, 480, 4, 90),
                (960, 240, 4, 85),
                (1200, 240, 2, 85),
                (1440, 480, 0, 90),
            ],
            scale_degrees=[5, 4, 3, 3, 2, 1],
            contour="descending",
            length_beats=4,
            intensity=PatternIntensity.HIGH,
            tags={"hook", "catchy", "chorus"},
            description="Catchy descending hook",
            section_types={"chorus"}
        ))
    
    def _load_jazz_patterns(self):
        """Load jazz patterns (swing, bebop, modal, fusion)."""
        genre = "jazz"
        self.patterns[genre] = {
            PatternType.DRUM: [],
            PatternType.BASS: [],
            PatternType.CHORD: [],
            PatternType.MELODY: [],
            PatternType.ARPEGGIO: [],
            PatternType.FILL: [],
            PatternType.TRANSITION: []
        }
        
        # Jazz Drums
        self.patterns[genre][PatternType.DRUM].append(DrumPattern(
            name="jazz_swing_ride",
            pattern_type=PatternType.DRUM,
            genre=genre,
            notes=[
                # Ride cymbal swing pattern
                (0, 140, 51, 75),
                (320, 100, 51, 60),  # Swing eighth
                (480, 140, 51, 75),
                (800, 100, 51, 60),
                (960, 140, 51, 75),
                (1280, 100, 51, 60),
                (1440, 140, 51, 75),
                (1760, 100, 51, 60),
                # Hi-hat on 2 and 4
                (480, 60, 44, 65),
                (1440, 60, 44, 65),
            ],
            instrument_map={51: "ride", 44: "hihat_pedal"},
            length_beats=4,
            intensity=PatternIntensity.LOW,
            tags={"swing", "ride"},
            swing_amount=0.33,
            description="Classic jazz swing ride pattern",
            section_types={"verse", "solo"}
        ))
        
        # Jazz Bass - Walking
        self.patterns[genre][PatternType.BASS].append(BassPattern(
            name="jazz_walking_bass",
            pattern_type=PatternType.BASS,
            genre=genre,
            notes=[
                (0, 450, 0, 85),    # Root
                (480, 450, 2, 82),  # 2nd
                (960, 450, 4, 85),  # 3rd
                (1440, 450, 5, 82), # 4th
            ],
            root_relative=True,
            octave=2,
            length_beats=4,
            intensity=PatternIntensity.MEDIUM,
            tags={"walking", "swing"},
            description="Walking bass line"
        ))
        
        # Jazz Chords - Drop 2 voicing
        self.patterns[genre][PatternType.CHORD].append(ChordPattern(
            name="jazz_drop2_maj7",
            pattern_type=PatternType.CHORD,
            genre=genre,
            notes=[
                # Drop-2 voicing (drop 2nd from top)
                (0, 1920, 0, 70),   # Root
                (0, 1920, 7, 68),   # 5th
                (0, 1920, 11, 72),  # 7th
                (0, 1920, 16, 65),  # 3rd (octave up)
            ],
            voicing_type="drop2",
            length_beats=4,
            intensity=PatternIntensity.MEDIUM,
            tags={"drop2", "maj7"},
            description="Drop-2 major 7th voicing"
        ))
        
        # Jazz Melody - Bebop
        self.patterns[genre][PatternType.MELODY].append(MelodyPattern(
            name="jazz_bebop_line",
            pattern_type=PatternType.MELODY,
            genre=genre,
            notes=[
                (0, 240, 0, 85),
                (240, 240, 2, 80),
                (480, 240, 4, 85),
                (720, 240, 5, 80),
                (960, 240, 7, 85),
                (1200, 240, 9, 80),
                (1440, 240, 11, 85),
                (1680, 240, 12, 90),
            ],
            scale_degrees=[1, 2, 3, 4, 5, 6, 7, 8],
            contour="ascending",
            length_beats=4,
            intensity=PatternIntensity.HIGH,
            tags={"bebop", "fast", "chromatic"},
            description="Fast bebop ascending line"
        ))
    
    def _load_rock_patterns(self):
        """Load rock patterns (classic, hard, indie, punk)."""
        genre = "rock"
        self.patterns[genre] = {
            PatternType.DRUM: [],
            PatternType.BASS: [],
            PatternType.CHORD: [],
            PatternType.MELODY: [],
            PatternType.ARPEGGIO: [],
            PatternType.FILL: [],
            PatternType.TRANSITION: []
        }
        
        # Rock Drums
        self.patterns[genre][PatternType.DRUM].append(DrumPattern(
            name="rock_basic_beat",
            pattern_type=PatternType.DRUM,
            genre=genre,
            notes=[
                # Kick on 1 and 3
                (0, 140, 36, 110),
                (960, 140, 36, 110),
                # Snare on 2 and 4
                (480, 120, 38, 115),
                (1440, 120, 38, 115),
                # Hi-hats on 8ths
                (0, 70, 42, 85),
                (240, 70, 42, 75),
                (480, 70, 42, 85),
                (720, 70, 42, 75),
                (960, 70, 42, 85),
                (1200, 70, 42, 75),
                (1440, 70, 42, 85),
                (1680, 70, 42, 75),
            ],
            instrument_map={36: "kick", 38: "snare", 42: "hihat_closed"},
            length_beats=4,
            intensity=PatternIntensity.MEDIUM,
            tags={"classic", "backbeat"},
            description="Classic rock backbeat"
        ))
        
        self.patterns[genre][PatternType.DRUM].append(DrumPattern(
            name="rock_hard_double_kick",
            pattern_type=PatternType.DRUM,
            genre=genre,
            notes=[
                # Fast double kick
                (0, 100, 36, 115),
                (120, 100, 36, 108),
                (480, 100, 36, 115),
                (600, 100, 36, 108),
                (960, 100, 36, 115),
                (1080, 100, 36, 108),
                (1440, 100, 36, 115),
                (1560, 100, 36, 108),
                # Snare on 2 and 4
                (480, 120, 38, 120),
                (1440, 120, 38, 120),
                # Ride
                (0, 80, 51, 90),
                (240, 80, 51, 85),
                (480, 80, 51, 90),
                (720, 80, 51, 85),
                (960, 80, 51, 90),
                (1200, 80, 51, 85),
                (1440, 80, 51, 90),
                (1680, 80, 51, 85),
            ],
            instrument_map={36: "kick", 38: "snare", 51: "ride"},
            length_beats=4,
            intensity=PatternIntensity.INTENSE,
            tags={"hard", "metal", "double_kick"},
            description="Hard rock double kick pattern"
        ))
        
        # Rock Bass
        self.patterns[genre][PatternType.BASS].append(BassPattern(
            name="rock_eighth_note_bass",
            pattern_type=PatternType.BASS,
            genre=genre,
            notes=[
                (0, 220, 0, 100),
                (240, 220, 0, 95),
                (480, 220, 0, 100),
                (720, 220, 0, 95),
                (960, 220, 0, 100),
                (1200, 220, 0, 95),
                (1440, 220, 0, 100),
                (1680, 220, 0, 95),
            ],
            root_relative=True,
            octave=1,
            follows_kick=True,
            length_beats=4,
            intensity=PatternIntensity.MEDIUM,
            tags={"driving", "eighth_notes"},
            description="Driving eighth note bass"
        ))
        
        # Rock Chords - Power chords
        self.patterns[genre][PatternType.CHORD].append(ChordPattern(
            name="rock_power_chord",
            pattern_type=PatternType.CHORD,
            genre=genre,
            notes=[
                # Power chord (root + 5th)
                (0, 1920, 0, 100),
                (0, 1920, 7, 100),
                (0, 1920, 12, 95),  # Octave for thickness
            ],
            voicing_type="power",
            length_beats=4,
            intensity=PatternIntensity.HIGH,
            tags={"power", "distortion"},
            description="Power chord voicing"
        ))
        
        # Rock Melody
        self.patterns[genre][PatternType.MELODY].append(MelodyPattern(
            name="rock_riff_pentatonic",
            pattern_type=PatternType.MELODY,
            genre=genre,
            notes=[
                (0, 240, 0, 95),
                (240, 240, 3, 90),
                (480, 240, 5, 95),
                (720, 240, 7, 90),
                (960, 480, 10, 100),
                (1440, 480, 7, 90),
            ],
            scale_degrees=[1, 3, 4, 5, 7, 5],
            contour="arch",
            length_beats=4,
            intensity=PatternIntensity.MEDIUM,
            tags={"pentatonic", "riff"},
            description="Pentatonic rock riff"
        ))
    
    def _load_edm_patterns(self):
        """Load EDM patterns (house, techno, dubstep, trance)."""
        genre = "edm"
        self.patterns[genre] = {
            PatternType.DRUM: [],
            PatternType.BASS: [],
            PatternType.CHORD: [],
            PatternType.MELODY: [],
            PatternType.ARPEGGIO: [],
            PatternType.FILL: [],
            PatternType.TRANSITION: []
        }
        
        # House Drums
        self.patterns[genre][PatternType.DRUM].append(DrumPattern(
            name="house_four_on_floor",
            pattern_type=PatternType.DRUM,
            genre=genre,
            notes=[
                # Kick on every beat
                (0, 130, 36, 115),
                (480, 130, 36, 115),
                (960, 130, 36, 115),
                (1440, 130, 36, 115),
                # Clap on 2 and 4
                (480, 90, 39, 105),
                (1440, 90, 39, 105),
                # Hi-hats on offbeats
                (240, 50, 42, 80),
                (720, 50, 42, 80),
                (1200, 50, 42, 80),
                (1680, 50, 42, 80),
            ],
            instrument_map={36: "kick", 39: "clap", 42: "hihat_closed"},
            length_beats=4,
            intensity=PatternIntensity.MEDIUM,
            tags={"house", "four_on_floor"},
            description="Classic house 4-on-the-floor"
        ))
        
        self.patterns[genre][PatternType.DRUM].append(DrumPattern(
            name="techno_driving",
            pattern_type=PatternType.DRUM,
            genre=genre,
            notes=[
                # Kick on all beats
                (0, 140, 36, 120),
                (480, 140, 36, 120),
                (960, 140, 36, 120),
                (1440, 140, 36, 120),
                # Hi-hats 16ths
                (0, 40, 42, 75),
                (120, 40, 42, 60),
                (240, 40, 42, 75),
                (360, 40, 42, 60),
                (480, 40, 42, 75),
                (600, 40, 42, 60),
                (720, 40, 42, 75),
                (840, 40, 42, 60),
                (960, 40, 42, 75),
                (1080, 40, 42, 60),
                (1200, 40, 42, 75),
                (1320, 40, 42, 60),
                (1440, 40, 42, 75),
                (1560, 40, 42, 60),
                (1680, 40, 42, 75),
                (1800, 40, 42, 60),
            ],
            instrument_map={36: "kick", 42: "hihat_closed"},
            length_beats=4,
            intensity=PatternIntensity.HIGH,
            tags={"techno", "driving", "industrial"},
            description="Driving techno pattern"
        ))
        
        # EDM Bass
        self.patterns[genre][PatternType.BASS].append(BassPattern(
            name="edm_sub_bass",
            pattern_type=PatternType.BASS,
            genre=genre,
            notes=[
                (0, 1920, 0, 100),  # Long sustained sub
            ],
            root_relative=True,
            octave=1,
            length_beats=4,
            intensity=PatternIntensity.MEDIUM,
            tags={"sub", "sustained"},
            description="Sustained sub bass"
        ))
        
        # EDM Chords
        self.patterns[genre][PatternType.CHORD].append(ChordPattern(
            name="edm_supersaw_chord",
            pattern_type=PatternType.CHORD,
            genre=genre,
            notes=[
                # Wide spread chord
                (0, 1920, 0, 85),
                (0, 1920, 4, 82),
                (0, 1920, 7, 85),
                (0, 1920, 12, 80),
                (0, 1920, 16, 78),
            ],
            voicing_type="spread",
            length_beats=4,
            intensity=PatternIntensity.HIGH,
            tags={"supersaw", "wide", "bright"},
            description="Wide supersaw chord"
        ))
        
        # EDM Melody - Arpeggio
        self.patterns[genre][PatternType.MELODY].append(MelodyPattern(
            name="edm_arpeggio_up",
            pattern_type=PatternType.MELODY,
            genre=genre,
            notes=[
                (0, 220, 0, 90),
                (240, 220, 4, 85),
                (480, 220, 7, 90),
                (720, 220, 12, 95),
                (960, 220, 7, 85),
                (1200, 220, 4, 80),
                (1440, 220, 0, 75),
                (1680, 220, 7, 80),
            ],
            scale_degrees=[1, 3, 5, 8, 5, 3, 1, 5],
            contour="arch",
            length_beats=4,
            intensity=PatternIntensity.MEDIUM,
            tags={"arpeggio", "triad"},
            description="Arpeggiated triad pattern"
        ))
    
    def _load_rnb_patterns(self):
        """Load R&B patterns (classic, neo-soul, modern)."""
        genre = "rnb"
        self.patterns[genre] = {
            PatternType.DRUM: [],
            PatternType.BASS: [],
            PatternType.CHORD: [],
            PatternType.MELODY: [],
            PatternType.ARPEGGIO: [],
            PatternType.FILL: [],
            PatternType.TRANSITION: []
        }
        
        # R&B Drums
        self.patterns[genre][PatternType.DRUM].append(DrumPattern(
            name="rnb_smooth_groove",
            pattern_type=PatternType.DRUM,
            genre=genre,
            notes=[
                # Kick
                (0, 130, 36, 95),
                (1200, 130, 36, 90),
                # Snare
                (480, 100, 38, 90),
                (1440, 100, 38, 90),
                # Hi-hats smooth 8ths
                (0, 70, 42, 70),
                (270, 70, 42, 60),  # Slight swing
                (480, 70, 42, 70),
                (750, 70, 42, 60),
                (960, 70, 42, 70),
                (1230, 70, 42, 60),
                (1440, 70, 42, 70),
                (1710, 70, 42, 60),
            ],
            instrument_map={36: "kick", 38: "snare", 42: "hihat_closed"},
            length_beats=4,
            intensity=PatternIntensity.LOW,
            tags={"smooth", "neo_soul"},
            swing_amount=0.08,
            description="Smooth R&B groove with subtle swing"
        ))
        
        # R&B Bass
        self.patterns[genre][PatternType.BASS].append(BassPattern(
            name="rnb_bass_melodic",
            pattern_type=PatternType.BASS,
            genre=genre,
            notes=[
                (0, 400, 0, 85),
                (480, 200, 2, 80),
                (720, 200, 0, 82),
                (960, 400, 5, 88),
                (1440, 480, 0, 85),
            ],
            root_relative=True,
            octave=2,
            length_beats=4,
            intensity=PatternIntensity.MEDIUM,
            tags={"melodic", "smooth"},
            description="Melodic R&B bass line"
        ))
        
        # R&B Chords
        self.patterns[genre][PatternType.CHORD].append(ChordPattern(
            name="rnb_9th_voicing",
            pattern_type=PatternType.CHORD,
            genre=genre,
            notes=[
                # 9th chord voicing
                (0, 1920, 0, 75),
                (0, 1920, 4, 70),
                (0, 1920, 7, 72),
                (0, 1920, 10, 68),  # Minor 7th
                (0, 1920, 14, 65),  # 9th
            ],
            voicing_type="extended",
            length_beats=4,
            intensity=PatternIntensity.MEDIUM,
            tags={"9th", "lush"},
            description="Lush 9th chord voicing"
        ))
        
        # R&B Melody
        self.patterns[genre][PatternType.MELODY].append(MelodyPattern(
            name="rnb_vocal_run",
            pattern_type=PatternType.MELODY,
            genre=genre,
            notes=[
                (0, 360, 7, 85),
                (360, 120, 9, 80),
                (480, 240, 7, 85),
                (720, 240, 5, 80),
                (960, 360, 4, 88),
                (1320, 120, 5, 82),
                (1440, 480, 7, 90),
            ],
            scale_degrees=[5, 6, 5, 4, 3, 4, 5],
            contour="wave",
            length_beats=4,
            intensity=PatternIntensity.MEDIUM,
            tags={"vocal", "melismatic"},
            description="Vocal-style melismatic run"
        ))
    
    def _load_funk_patterns(self):
        """Load funk patterns (classic, p-funk, modern)."""
        genre = "funk"
        self.patterns[genre] = {
            PatternType.DRUM: [],
            PatternType.BASS: [],
            PatternType.CHORD: [],
            PatternType.MELODY: [],
            PatternType.ARPEGGIO: [],
            PatternType.FILL: [],
            PatternType.TRANSITION: []
        }
        
        # Funk Drums
        self.patterns[genre][PatternType.DRUM].append(DrumPattern(
            name="funk_syncopated_groove",
            pattern_type=PatternType.DRUM,
            genre=genre,
            notes=[
                # Syncopated kick
                (0, 100, 36, 105),
                (360, 100, 36, 95),
                (720, 100, 36, 100),
                (1200, 100, 36, 98),
                # Snare on 2 and 4 with ghost notes
                (180, 60, 38, 55),  # Ghost
                (480, 100, 38, 110),
                (900, 60, 38, 60),  # Ghost
                (1440, 100, 38, 110),
                # Hi-hats 16ths
                (0, 40, 42, 80),
                (120, 40, 42, 65),
                (240, 40, 42, 80),
                (360, 40, 42, 65),
                (480, 40, 42, 80),
                (600, 40, 42, 65),
                (720, 40, 42, 80),
                (840, 40, 42, 65),
                (960, 40, 42, 80),
                (1080, 40, 42, 65),
                (1200, 40, 42, 80),
                (1320, 40, 42, 65),
                (1440, 40, 42, 80),
                (1560, 40, 42, 65),
                (1680, 40, 42, 80),
                (1800, 40, 42, 65),
            ],
            instrument_map={36: "kick", 38: "snare", 42: "hihat_closed"},
            has_ghost_notes=True,
            length_beats=4,
            intensity=PatternIntensity.HIGH,
            tags={"syncopated", "ghost_notes"},
            syncopation_level=0.8,
            description="Syncopated funk groove with ghost notes"
        ))
        
        # Funk Bass - slap style
        self.patterns[genre][PatternType.BASS].append(BassPattern(
            name="funk_slap_bass",
            pattern_type=PatternType.BASS,
            genre=genre,
            notes=[
                (0, 150, 0, 110),   # Slap
                (180, 80, 7, 85),   # Pop
                (360, 150, 0, 105),
                (600, 80, 5, 80),
                (720, 150, 0, 110),
                (960, 150, 3, 100),
                (1200, 80, 5, 85),
                (1320, 150, 0, 108),
                (1560, 80, 7, 82),
            ],
            root_relative=True,
            octave=2,
            length_beats=4,
            intensity=PatternIntensity.HIGH,
            tags={"slap", "percussive", "syncopated"},
            syncopation_level=0.9,
            description="Slap bass funk pattern"
        ))
        
        # Funk Chords - staccato
        self.patterns[genre][PatternType.CHORD].append(ChordPattern(
            name="funk_stab_chord",
            pattern_type=PatternType.CHORD,
            genre=genre,
            notes=[
                # Short stab chords
                (480, 100, 0, 95),
                (480, 100, 4, 92),
                (480, 100, 7, 95),
                (1440, 100, 0, 95),
                (1440, 100, 4, 92),
                (1440, 100, 7, 95),
            ],
            voicing_type="stab",
            length_beats=4,
            intensity=PatternIntensity.HIGH,
            tags={"stab", "rhythmic"},
            description="Stab chord on 2 and 4"
        ))
        
        # Funk Melody
        self.patterns[genre][PatternType.MELODY].append(MelodyPattern(
            name="funk_horn_riff",
            pattern_type=PatternType.MELODY,
            genre=genre,
            notes=[
                (0, 120, 7, 100),
                (180, 120, 9, 95),
                (360, 120, 7, 100),
                (480, 240, 5, 105),
                (960, 120, 7, 100),
                (1080, 120, 9, 95),
                (1200, 120, 7, 100),
                (1320, 120, 5, 95),
                (1440, 480, 4, 105),
            ],
            scale_degrees=[5, 6, 5, 4, 5, 6, 5, 4, 3],
            contour="wave",
            length_beats=4,
            intensity=PatternIntensity.HIGH,
            tags={"horn", "riff", "punchy"},
            description="Punchy horn section riff"
        ))
    
    def _load_latin_patterns(self):
        """Load Latin patterns (salsa, bossa, reggaeton)."""
        genre = "latin"
        self.patterns[genre] = {
            PatternType.DRUM: [],
            PatternType.BASS: [],
            PatternType.CHORD: [],
            PatternType.MELODY: [],
            PatternType.ARPEGGIO: [],
            PatternType.FILL: [],
            PatternType.TRANSITION: []
        }
        
        # Latin Drums - Bossa Nova
        self.patterns[genre][PatternType.DRUM].append(DrumPattern(
            name="bossa_nova_pattern",
            pattern_type=PatternType.DRUM,
            genre=genre,
            notes=[
                # Kick - bossa pattern
                (0, 120, 36, 90),
                (960, 120, 36, 90),
                # Rim/side stick cross-stick
                (480, 80, 37, 75),
                (720, 80, 37, 70),
                (1440, 80, 37, 75),
                (1680, 80, 37, 70),
                # Hi-hat
                (0, 60, 42, 65),
                (480, 60, 42, 65),
                (960, 60, 42, 65),
                (1440, 60, 42, 65),
            ],
            instrument_map={36: "kick", 37: "rimshot", 42: "hihat_closed"},
            length_beats=4,
            intensity=PatternIntensity.LOW,
            tags={"bossa", "brazilian", "cross_stick"},
            description="Bossa nova rhythm pattern"
        ))
        
        # Reggaeton Drums (dembow rhythm)
        self.patterns[genre][PatternType.DRUM].append(DrumPattern(
            name="reggaeton_dembow",
            pattern_type=PatternType.DRUM,
            genre=genre,
            notes=[
                # Kick - dembow pattern
                (0, 140, 36, 110),
                (480, 140, 36, 105),
                (720, 140, 36, 110),
                # Snare
                (960, 120, 38, 105),
                (1680, 120, 38, 100),
                # Hi-hats
                (0, 50, 42, 80),
                (240, 50, 42, 70),
                (480, 50, 42, 80),
                (720, 50, 42, 75),
                (960, 50, 42, 80),
                (1200, 50, 42, 70),
                (1440, 50, 42, 80),
                (1680, 50, 42, 75),
            ],
            instrument_map={36: "kick", 38: "snare", 42: "hihat_closed"},
            length_beats=4,
            intensity=PatternIntensity.MEDIUM,
            tags={"reggaeton", "dembow", "urban"},
            description="Reggaeton dembow rhythm"
        ))
        
        # Latin Bass
        self.patterns[genre][PatternType.BASS].append(BassPattern(
            name="latin_bass_tumbao",
            pattern_type=PatternType.BASS,
            genre=genre,
            notes=[
                (0, 200, 0, 95),
                (240, 150, 7, 85),
                (480, 200, 0, 95),
                (960, 200, 5, 90),
                (1200, 150, 7, 85),
                (1440, 200, 0, 95),
            ],
            root_relative=True,
            octave=2,
            length_beats=4,
            intensity=PatternIntensity.MEDIUM,
            tags={"tumbao", "salsa"},
            description="Tumbao bass pattern"
        ))
        
        # Latin Chords
        self.patterns[genre][PatternType.CHORD].append(ChordPattern(
            name="latin_montuno_voicing",
            pattern_type=PatternType.CHORD,
            genre=genre,
            notes=[
                # Montuno rhythm
                (0, 200, 0, 80),
                (0, 200, 4, 75),
                (0, 200, 7, 78),
                (480, 200, 0, 80),
                (480, 200, 4, 75),
                (480, 200, 7, 78),
                (960, 200, 0, 80),
                (960, 200, 4, 75),
                (960, 200, 7, 78),
                (1440, 200, 0, 80),
                (1440, 200, 4, 75),
                (1440, 200, 7, 78),
            ],
            voicing_type="montuno",
            length_beats=4,
            intensity=PatternIntensity.MEDIUM,
            tags={"montuno", "rhythmic"},
            description="Montuno piano voicing"
        ))
        
        # Latin Melody
        self.patterns[genre][PatternType.MELODY].append(MelodyPattern(
            name="latin_melody_call",
            pattern_type=PatternType.MELODY,
            genre=genre,
            notes=[
                (0, 240, 5, 90),
                (240, 240, 7, 85),
                (480, 360, 9, 92),
                (840, 120, 7, 82),
                (960, 480, 5, 90),
                (1440, 480, 4, 85),
            ],
            scale_degrees=[4, 5, 6, 5, 4, 3],
            contour="arch",
            length_beats=4,
            intensity=PatternIntensity.MEDIUM,
            tags={"call_response", "melodic"},
            description="Call-and-response melody"
        ))
    
    def _load_reggae_patterns(self):
        """Load reggae/dub patterns."""
        genre = "reggae"
        self.patterns[genre] = {
            PatternType.DRUM: [],
            PatternType.BASS: [],
            PatternType.CHORD: [],
            PatternType.MELODY: [],
            PatternType.ARPEGGIO: [],
            PatternType.FILL: [],
            PatternType.TRANSITION: []
        }
        
        # Reggae Drums - One Drop
        self.patterns[genre][PatternType.DRUM].append(DrumPattern(
            name="reggae_one_drop",
            pattern_type=PatternType.DRUM,
            genre=genre,
            notes=[
                # Kick on 3
                (960, 150, 36, 100),
                # Snare on 3
                (960, 120, 38, 95),
                # Hi-hats on offbeats
                (240, 80, 42, 70),
                (720, 80, 42, 70),
                (1200, 80, 42, 70),
                (1680, 80, 42, 70),
                # Rim clicks
                (480, 60, 37, 65),
                (1440, 60, 37, 65),
            ],
            instrument_map={36: "kick", 38: "snare", 42: "hihat_closed", 37: "rimshot"},
            length_beats=4,
            intensity=PatternIntensity.LOW,
            tags={"one_drop", "classic"},
            description="Classic one-drop reggae pattern"
        ))
        
        # Reggae Bass
        self.patterns[genre][PatternType.BASS].append(BassPattern(
            name="reggae_bass_dub",
            pattern_type=PatternType.BASS,
            genre=genre,
            notes=[
                (960, 450, 0, 105),    # On the 3
                (1680, 200, 7, 90),    # Pickup
            ],
            root_relative=True,
            octave=1,
            length_beats=4,
            intensity=PatternIntensity.HIGH,
            tags={"dub", "heavy", "sub"},
            description="Heavy dub bass on the 3"
        ))
        
        # Reggae Chords - Skank
        self.patterns[genre][PatternType.CHORD].append(ChordPattern(
            name="reggae_skank",
            pattern_type=PatternType.CHORD,
            genre=genre,
            notes=[
                # Offbeat skank chords (short staccato)
                (240, 120, 0, 85),
                (240, 120, 4, 82),
                (240, 120, 7, 85),
                (720, 120, 0, 85),
                (720, 120, 4, 82),
                (720, 120, 7, 85),
                (1200, 120, 0, 85),
                (1200, 120, 4, 82),
                (1200, 120, 7, 85),
                (1680, 120, 0, 85),
                (1680, 120, 4, 82),
                (1680, 120, 7, 85),
            ],
            voicing_type="skank",
            length_beats=4,
            intensity=PatternIntensity.MEDIUM,
            tags={"skank", "offbeat", "staccato"},
            description="Reggae skank offbeat chords"
        ))
        
        # Reggae Melody
        self.patterns[genre][PatternType.MELODY].append(MelodyPattern(
            name="reggae_melody_laid_back",
            pattern_type=PatternType.MELODY,
            genre=genre,
            notes=[
                (240, 400, 5, 80),
                (720, 400, 7, 82),
                (1200, 400, 5, 80),
                (1680, 320, 3, 78),
            ],
            scale_degrees=[4, 5, 4, 2],
            contour="wave",
            length_beats=4,
            intensity=PatternIntensity.LOW,
            tags={"laid_back", "offbeat"},
            description="Laid-back reggae melody"
        ))
    
    def _load_afrobeat_patterns(self):
        """Load Afrobeat patterns."""
        genre = "afrobeat"
        self.patterns[genre] = {
            PatternType.DRUM: [],
            PatternType.BASS: [],
            PatternType.CHORD: [],
            PatternType.MELODY: [],
            PatternType.ARPEGGIO: [],
            PatternType.FILL: [],
            PatternType.TRANSITION: []
        }
        
        # Afrobeat Drums
        self.patterns[genre][PatternType.DRUM].append(DrumPattern(
            name="afrobeat_complex_polyrhythm",
            pattern_type=PatternType.DRUM,
            genre=genre,
            notes=[
                # Kick pattern
                (0, 120, 36, 105),
                (360, 120, 36, 95),
                (720, 120, 36, 100),
                (1200, 120, 36, 100),
                (1560, 120, 36, 98),
                # Snare syncopated
                (480, 100, 38, 100),
                (960, 100, 38, 105),
                (1440, 100, 38, 100),
                # Hi-hats complex
                (0, 50, 42, 75),
                (180, 50, 42, 60),
                (360, 50, 42, 75),
                (540, 50, 42, 60),
                (720, 50, 42, 75),
                (900, 50, 42, 60),
                (1080, 50, 42, 75),
                (1260, 50, 42, 60),
                (1440, 50, 42, 75),
                (1620, 50, 42, 60),
                (1800, 50, 42, 75),
            ],
            instrument_map={36: "kick", 38: "snare", 42: "hihat_closed"},
            length_beats=4,
            intensity=PatternIntensity.HIGH,
            tags={"polyrhythm", "complex", "traditional"},
            syncopation_level=0.85,
            description="Complex Afrobeat polyrhythm"
        ))
        
        # Afrobeat Bass
        self.patterns[genre][PatternType.BASS].append(BassPattern(
            name="afrobeat_bass_groove",
            pattern_type=PatternType.BASS,
            genre=genre,
            notes=[
                (0, 180, 0, 100),
                (240, 180, 0, 95),
                (480, 180, 5, 98),
                (720, 180, 7, 92),
                (960, 180, 0, 100),
                (1200, 180, 3, 95),
                (1440, 180, 5, 98),
                (1680, 180, 0, 95),
            ],
            root_relative=True,
            octave=2,
            length_beats=4,
            intensity=PatternIntensity.HIGH,
            tags={"driving", "syncopated"},
            syncopation_level=0.7,
            description="Driving Afrobeat bass groove"
        ))
        
        # Afrobeat Chords
        self.patterns[genre][PatternType.CHORD].append(ChordPattern(
            name="afrobeat_guitar_comp",
            pattern_type=PatternType.CHORD,
            genre=genre,
            notes=[
                # Rhythmic comping pattern
                (0, 150, 0, 85),
                (0, 150, 4, 82),
                (0, 150, 7, 85),
                (360, 150, 0, 82),
                (360, 150, 4, 78),
                (360, 150, 7, 82),
                (720, 150, 0, 85),
                (720, 150, 4, 82),
                (720, 150, 7, 85),
                (1200, 150, 0, 82),
                (1200, 150, 4, 78),
                (1200, 150, 7, 82),
                (1560, 150, 0, 85),
                (1560, 150, 4, 82),
                (1560, 150, 7, 85),
            ],
            voicing_type="comp",
            length_beats=4,
            intensity=PatternIntensity.MEDIUM,
            tags={"guitar", "rhythmic", "comp"},
            description="Rhythmic guitar comping"
        ))
        
        # Afrobeat Melody
        self.patterns[genre][PatternType.MELODY].append(MelodyPattern(
            name="afrobeat_horn_line",
            pattern_type=PatternType.MELODY,
            genre=genre,
            notes=[
                (0, 240, 7, 95),
                (240, 120, 9, 90),
                (360, 240, 7, 95),
                (600, 120, 5, 85),
                (720, 240, 7, 95),
                (960, 240, 5, 92),
                (1200, 240, 4, 88),
                (1440, 480, 3, 95),
            ],
            scale_degrees=[5, 6, 5, 4, 5, 4, 3, 2],
            contour="descending",
            length_beats=4,
            intensity=PatternIntensity.HIGH,
            tags={"horn", "call_response"},
            description="Call-and-response horn line"
        ))


# Convenience functions
def get_drum_pattern(genre: str, style: str = "basic") -> Optional[DrumPattern]:
    """Quick access to drum patterns."""
    library = PatternLibrary()
    patterns = library.get_patterns(genre, PatternType.DRUM)
    
    # Try to find pattern with style in name
    for pattern in patterns:
        if style.lower() in pattern.name.lower():
            return pattern
    
    # Return first if no match
    return patterns[0] if patterns else None


def get_bass_pattern(genre: str, style: str = "basic") -> Optional[BassPattern]:
    """Quick access to bass patterns."""
    library = PatternLibrary()
    patterns = library.get_patterns(genre, PatternType.BASS)
    
    for pattern in patterns:
        if style.lower() in pattern.name.lower():
            return pattern
    
    return patterns[0] if patterns else None


def get_chord_voicings(genre: str, chord_type: str = "major7") -> List[ChordPattern]:
    """Get chord voicing patterns for a genre."""
    library = PatternLibrary()
    patterns = library.get_patterns(genre, PatternType.CHORD)
    
    # Filter by chord type if specified
    if chord_type.lower() in ["major7", "maj7"]:
        return [p for p in patterns if "maj7" in p.name.lower() or "major" in p.name.lower()]
    elif chord_type.lower() in ["minor7", "m7"]:
        return [p for p in patterns if "m7" in p.name.lower() or "minor" in p.name.lower()]
    
    return patterns


def build_pattern_set(
    genre: str,
    section: str,
    intensity: PatternIntensity = PatternIntensity.MEDIUM
) -> Dict[PatternType, Pattern]:
    """Build a complete compatible pattern set for a section."""
    library = PatternLibrary()
    patterns_dict = library.get_patterns_for_section(genre, section, intensity)
    
    # Select one pattern of each type
    result = {}
    for pattern_type, patterns in patterns_dict.items():
        if patterns:
            result[pattern_type] = patterns[0]
    
    return result


# Add additional pattern variations for each genre to reach 100+ total
def _add_extended_patterns(library):
    """Add extended patterns (fills, intros, outros, transitions, arpeggios) to reach 100+ patterns."""
    
    # Hip-Hop Extended Patterns
    genre = "hip_hop"
    
    library.patterns[genre][PatternType.FILL].append(DrumPattern(
        name="hip_hop_fill_snare_roll",
        pattern_type=PatternType.FILL,
        genre=genre,
        notes=[
            (1440, 60, 38, 95),
            (1500, 60, 38, 98),
            (1560, 60, 38, 100),
            (1620, 60, 38, 102),
            (1680, 60, 38, 105),
            (1740, 60, 38, 108),
            (1800, 60, 38, 110),
            (1860, 60, 38, 112),
        ],
        instrument_map={38: "snare"},
        length_beats=1,
        intensity=PatternIntensity.HIGH,
        tags={"fill", "snare_roll"},
        description="Snare roll fill",
        section_types={"transition", "outro"}
    ))
    
    library.patterns[genre][PatternType.DRUM].append(DrumPattern(
        name="hip_hop_intro_minimal",
        pattern_type=PatternType.DRUM,
        genre=genre,
        notes=[
            (0, 120, 42, 70),
            (480, 120, 42, 70),
            (960, 120, 42, 70),
            (1440, 120, 42, 70),
        ],
        instrument_map={42: "hihat_closed"},
        length_beats=4,
        intensity=PatternIntensity.MINIMAL,
        tags={"intro", "minimal"},
        description="Minimal hi-hat intro",
        section_types={"intro"}
    ))
    
    library.patterns[genre][PatternType.ARPEGGIO].append(MelodyPattern(
        name="hip_hop_synth_arp",
        pattern_type=PatternType.ARPEGGIO,
        genre=genre,
        notes=[
            (0, 200, 0, 80),
            (240, 200, 4, 75),
            (480, 200, 7, 80),
            (720, 200, 12, 85),
            (960, 200, 7, 75),
            (1200, 200, 4, 75),
            (1440, 200, 0, 75),
            (1680, 200, 7, 80),
        ],
        scale_degrees=[1, 3, 5, 8, 5, 3, 1, 5],
        contour="arch",
        length_beats=4,
        intensity=PatternIntensity.MEDIUM,
        tags={"arpeggio", "synth"},
        description="Synth arpeggio pattern"
    ))
    
    # Pop Extended Patterns
    genre = "pop"
    
    library.patterns[genre][PatternType.FILL].append(DrumPattern(
        name="pop_fill_tom_roll",
        pattern_type=PatternType.FILL,
        genre=genre,
        notes=[
            (1440, 120, 50, 100),
            (1560, 120, 47, 95),
            (1680, 120, 45, 90),
            (1800, 120, 36, 105),
        ],
        instrument_map={50: "tom_high", 47: "tom_mid", 45: "tom_low", 36: "kick"},
        length_beats=1,
        intensity=PatternIntensity.HIGH,
        tags={"fill", "toms"},
        description="Tom roll down fill",
        section_types={"transition"}
    ))
    
    library.patterns[genre][PatternType.ARPEGGIO].append(MelodyPattern(
        name="pop_piano_arp",
        pattern_type=PatternType.ARPEGGIO,
        genre=genre,
        notes=[
            (0, 200, 0, 85),
            (240, 200, 4, 82),
            (480, 200, 7, 85),
            (720, 200, 12, 88),
            (960, 200, 16, 90),
            (1200, 200, 12, 85),
            (1440, 200, 7, 82),
            (1680, 200, 4, 80),
        ],
        scale_degrees=[1, 3, 5, 8, 10, 8, 5, 3],
        contour="arch",
        length_beats=4,
        intensity=PatternIntensity.MEDIUM,
        tags={"arpeggio", "piano"},
        description="Piano arpeggio pattern"
    ))
    
    # Jazz Extended Patterns
    genre = "jazz"
    
    library.patterns[genre][PatternType.FILL].append(DrumPattern(
        name="jazz_fill_brush_sweep",
        pattern_type=PatternType.FILL,
        genre=genre,
        notes=[
            (1440, 200, 38, 70),
            (1680, 200, 45, 65),
        ],
        instrument_map={38: "snare", 45: "tom_low"},
        length_beats=1,
        intensity=PatternIntensity.LOW,
        tags={"fill", "brush"},
        description="Brush sweep fill",
        section_types={"transition"}
    ))
    
    library.patterns[genre][PatternType.ARPEGGIO].append(MelodyPattern(
        name="jazz_piano_comp",
        pattern_type=PatternType.ARPEGGIO,
        genre=genre,
        notes=[
            (240, 180, 4, 75),
            (480, 180, 7, 72),
            (720, 180, 11, 75),
            (1200, 180, 9, 72),
            (1440, 180, 7, 75),
            (1680, 180, 4, 72),
        ],
        scale_degrees=[3, 5, 7, 6, 5, 3],
        contour="wave",
        length_beats=4,
        intensity=PatternIntensity.LOW,
        tags={"arpeggio", "comping"},
        description="Jazz piano comping pattern"
    ))
    
    # Rock Extended Patterns
    genre = "rock"
    
    library.patterns[genre][PatternType.FILL].append(DrumPattern(
        name="rock_fill_crash_cymbal",
        pattern_type=PatternType.FILL,
        genre=genre,
        notes=[
            (1440, 120, 50, 110),
            (1560, 120, 47, 108),
            (1680, 120, 45, 105),
            (1800, 120, 36, 115),
            (1920, 200, 49, 120),
        ],
        instrument_map={50: "tom_high", 47: "tom_mid", 45: "tom_low", 36: "kick", 49: "crash"},
        length_beats=1,
        intensity=PatternIntensity.INTENSE,
        tags={"fill", "crash"},
        description="Crash cymbal fill",
        section_types={"transition", "chorus"}
    ))
    
    library.patterns[genre][PatternType.TRANSITION].append(DrumPattern(
        name="rock_transition_buildup",
        pattern_type=PatternType.TRANSITION,
        genre=genre,
        notes=[
            (0, 80, 42, 80),
            (120, 80, 42, 82),
            (240, 80, 42, 84),
            (360, 80, 42, 86),
            (480, 80, 42, 88),
            (600, 80, 42, 90),
            (720, 80, 42, 92),
            (840, 80, 42, 94),
            (960, 80, 42, 96),
            (1080, 80, 42, 98),
            (1200, 80, 42, 100),
            (1320, 80, 42, 102),
            (1440, 80, 42, 105),
            (1560, 80, 42, 108),
            (1680, 80, 42, 110),
            (1800, 80, 42, 115),
        ],
        instrument_map={42: "hihat_closed"},
        length_beats=4,
        intensity=PatternIntensity.HIGH,
        tags={"transition", "buildup"},
        description="Hi-hat buildup transition",
        section_types={"transition"}
    ))
    
    # EDM Extended Patterns
    genre = "edm"
    
    library.patterns[genre][PatternType.FILL].append(DrumPattern(
        name="edm_fill_snare_riser",
        pattern_type=PatternType.FILL,
        genre=genre,
        notes=[
            (0, 40, 38, 70),
            (240, 40, 38, 75),
            (480, 40, 38, 80),
            (720, 40, 38, 85),
            (960, 40, 38, 90),
            (1200, 40, 38, 95),
            (1440, 40, 38, 100),
            (1680, 40, 38, 105),
            (1800, 40, 38, 110),
            (1860, 40, 38, 115),
            (1900, 40, 38, 120),
        ],
        instrument_map={38: "snare"},
        length_beats=4,
        intensity=PatternIntensity.INTENSE,
        tags={"fill", "riser", "buildup"},
        description="Snare riser buildup",
        section_types={"transition", "drop"}
    ))
    
    library.patterns[genre][PatternType.TRANSITION].append(DrumPattern(
        name="edm_transition_breakdown",
        pattern_type=PatternType.TRANSITION,
        genre=genre,
        notes=[
            (0, 120, 36, 100),
            (480, 100, 39, 90),
            (960, 120, 36, 100),
            (1440, 100, 39, 90),
        ],
        instrument_map={36: "kick", 39: "clap"},
        length_beats=4,
        intensity=PatternIntensity.LOW,
        tags={"transition", "breakdown"},
        description="Breakdown transition",
        section_types={"breakdown"}
    ))
    
    library.patterns[genre][PatternType.ARPEGGIO].append(MelodyPattern(
        name="edm_pluck_arp",
        pattern_type=PatternType.ARPEGGIO,
        genre=genre,
        notes=[
            (0, 180, 0, 90),
            (180, 180, 4, 88),
            (360, 180, 7, 90),
            (540, 180, 12, 92),
            (720, 180, 16, 94),
            (900, 180, 19, 96),
            (1080, 180, 16, 94),
            (1260, 180, 12, 92),
            (1440, 180, 7, 90),
            (1620, 180, 4, 88),
            (1800, 180, 0, 86),
        ],
        scale_degrees=[1, 3, 5, 8, 10, 12, 10, 8, 5, 3, 1],
        contour="arch",
        length_beats=4,
        intensity=PatternIntensity.HIGH,
        tags={"arpeggio", "pluck", "fast"},
        description="Fast pluck synth arpeggio"
    ))
    
    # R&B Extended Patterns
    genre = "rnb"
    
    library.patterns[genre][PatternType.FILL].append(DrumPattern(
        name="rnb_fill_hihat_roll",
        pattern_type=PatternType.FILL,
        genre=genre,
        notes=[
            (1440, 50, 42, 75),
            (1490, 50, 42, 78),
            (1540, 50, 42, 80),
            (1590, 50, 42, 82),
            (1640, 50, 42, 85),
            (1690, 50, 42, 88),
            (1740, 50, 42, 90),
            (1790, 50, 42, 92),
            (1840, 50, 42, 95),
        ],
        instrument_map={42: "hihat_closed"},
        length_beats=1,
        intensity=PatternIntensity.MEDIUM,
        tags={"fill", "hihat"},
        description="Hi-hat roll fill",
        section_types={"transition"}
    ))
    
    library.patterns[genre][PatternType.ARPEGGIO].append(MelodyPattern(
        name="rnb_rhodes_arp",
        pattern_type=PatternType.ARPEGGIO,
        genre=genre,
        notes=[
            (0, 300, 0, 75),
            (360, 300, 4, 72),
            (720, 300, 7, 75),
            (1080, 300, 10, 72),
            (1440, 480, 14, 78),
        ],
        scale_degrees=[1, 3, 5, 7, 9],
        contour="ascending",
        length_beats=4,
        intensity=PatternIntensity.LOW,
        tags={"arpeggio", "rhodes", "lush"},
        description="Warm Rhodes arpeggio"
    ))
    
    # Funk Extended Patterns
    genre = "funk"
    
    library.patterns[genre][PatternType.FILL].append(DrumPattern(
        name="funk_fill_funky_break",
        pattern_type=PatternType.FILL,
        genre=genre,
        notes=[
            (1440, 80, 36, 105),
            (1560, 80, 38, 110),
            (1680, 80, 45, 95),
            (1800, 80, 36, 108),
            (1920, 100, 49, 115),
        ],
        instrument_map={36: "kick", 38: "snare", 45: "tom_low", 49: "crash"},
        length_beats=1,
        intensity=PatternIntensity.HIGH,
        tags={"fill", "funky"},
        description="Funky drum break fill",
        section_types={"transition"}
    ))
    
    library.patterns[genre][PatternType.TRANSITION].append(BassPattern(
        name="funk_bass_slide_up",
        pattern_type=PatternType.TRANSITION,
        genre=genre,
        notes=[
            (0, 100, 0, 100),
            (120, 100, 1, 102),
            (240, 100, 2, 104),
            (360, 100, 3, 106),
            (480, 100, 4, 108),
            (600, 100, 5, 110),
            (720, 100, 6, 112),
            (840, 100, 7, 115),
        ],
        root_relative=True,
        octave=2,
        length_beats=2,
        intensity=PatternIntensity.HIGH,
        tags={"transition", "slide"},
        description="Bass slide up transition"
    ))
    
    # Latin Extended Patterns
    genre = "latin"
    
    library.patterns[genre][PatternType.FILL].append(DrumPattern(
        name="latin_fill_conga_roll",
        pattern_type=PatternType.FILL,
        genre=genre,
        notes=[
            (1440, 100, 45, 90),
            (1560, 100, 47, 95),
            (1680, 100, 50, 100),
            (1800, 100, 47, 95),
        ],
        instrument_map={45: "tom_low", 47: "tom_mid", 50: "tom_high"},
        length_beats=1,
        intensity=PatternIntensity.MEDIUM,
        tags={"fill", "conga", "percussion"},
        description="Conga roll fill",
        section_types={"transition"}
    ))
    
    library.patterns[genre][PatternType.TRANSITION].append(MelodyPattern(
        name="latin_brass_stab",
        pattern_type=PatternType.TRANSITION,
        genre=genre,
        notes=[
            (0, 200, 7, 105),
            (0, 200, 12, 105),
            (0, 200, 16, 105),
        ],
        scale_degrees=[5, 8, 10],
        contour="ascending",
        length_beats=1,
        intensity=PatternIntensity.INTENSE,
        tags={"transition", "brass", "stab"},
        description="Brass stab transition"
    ))
    
    # Reggae Extended Patterns
    genre = "reggae"
    
    library.patterns[genre][PatternType.FILL].append(DrumPattern(
        name="reggae_fill_rim_pattern",
        pattern_type=PatternType.FILL,
        genre=genre,
        notes=[
            (1440, 80, 37, 75),
            (1560, 80, 37, 78),
            (1680, 80, 37, 80),
            (1800, 80, 37, 82),
        ],
        instrument_map={37: "rimshot"},
        length_beats=1,
        intensity=PatternIntensity.LOW,
        tags={"fill", "rim"},
        description="Rim click fill",
        section_types={"transition"}
    ))
    
    library.patterns[genre][PatternType.TRANSITION].append(DrumPattern(
        name="reggae_transition_drop",
        pattern_type=PatternType.TRANSITION,
        genre=genre,
        notes=[
            (960, 150, 36, 115),
            (960, 120, 38, 110),
        ],
        instrument_map={36: "kick", 38: "snare"},
        length_beats=2,
        intensity=PatternIntensity.HIGH,
        tags={"transition", "drop", "crash"},
        description="One-drop transition crash",
        section_types={"drop"}
    ))
    
    # Afrobeat Extended Patterns
    genre = "afrobeat"
    
    library.patterns[genre][PatternType.FILL].append(DrumPattern(
        name="afrobeat_fill_clave_break",
        pattern_type=PatternType.FILL,
        genre=genre,
        notes=[
            (0, 80, 37, 90),
            (240, 80, 37, 88),
            (360, 80, 37, 90),
            (600, 80, 37, 88),
            (720, 80, 37, 90),
        ],
        instrument_map={37: "rimshot"},
        length_beats=2,
        intensity=PatternIntensity.MEDIUM,
        tags={"fill", "clave", "polyrhythm"},
        description="Clave break fill",
        section_types={"transition"}
    ))
    
    library.patterns[genre][PatternType.TRANSITION].append(MelodyPattern(
        name="afrobeat_horn_call",
        pattern_type=PatternType.TRANSITION,
        genre=genre,
        notes=[
            (0, 240, 7, 105),
            (240, 240, 9, 105),
            (480, 480, 12, 110),
        ],
        scale_degrees=[5, 6, 8],
        contour="ascending",
        length_beats=2,
        intensity=PatternIntensity.HIGH,
        tags={"transition", "horn", "call"},
        description="Horn call transition"
    ))
    
    # Add more drum variations for each genre
    for genre in ["hip_hop", "pop", "jazz", "rock", "edm", "rnb", "funk", "latin", "reggae", "afrobeat"]:
        # Add outro pattern
        library.patterns[genre][PatternType.DRUM].append(DrumPattern(
            name=f"{genre}_outro_fade",
            pattern_type=PatternType.DRUM,
            genre=genre,
            notes=[
                (0, 120, 36, 85),
                (480, 100, 38, 80),
                (960, 120, 36, 75),
                (1440, 100, 38, 70),
            ],
            instrument_map={36: "kick", 38: "snare"},
            length_beats=4,
            intensity=PatternIntensity.LOW,
            tags={"outro", "fade"},
            description=f"{genre.replace('_', ' ').title()} outro fade pattern",
            section_types={"outro"}
        ))
        
        # Add bass variation
        library.patterns[genre][PatternType.BASS].append(BassPattern(
            name=f"{genre}_bass_minimal",
            pattern_type=PatternType.BASS,
            genre=genre,
            notes=[
                (0, 900, 0, 80),
                (960, 900, 0, 78),
            ],
            root_relative=True,
            octave=1,
            length_beats=4,
            intensity=PatternIntensity.LOW,
            tags={"minimal", "sustained"},
            description=f"{genre.replace('_', ' ').title()} minimal bass",
            section_types={"intro", "verse"}
        ))
        
        # Add chord variation
        library.patterns[genre][PatternType.CHORD].append(ChordPattern(
            name=f"{genre}_chord_pad",
            pattern_type=PatternType.CHORD,
            genre=genre,
            notes=[
                (0, 1920, 0, 65),
                (0, 1920, 4, 62),
                (0, 1920, 7, 65),
                (0, 1920, 12, 60),
            ],
            voicing_type="pad",
            length_beats=4,
            intensity=PatternIntensity.LOW,
            tags={"pad", "sustained", "ambient"},
            description=f"{genre.replace('_', ' ').title()} chord pad",
            section_types={"intro", "verse", "bridge"}
        ))
        
        # Add melody variation
        library.patterns[genre][PatternType.MELODY].append(MelodyPattern(
            name=f"{genre}_melody_counter",
            pattern_type=PatternType.MELODY,
            genre=genre,
            notes=[
                (480, 240, 4, 75),
                (720, 240, 5, 72),
                (960, 240, 4, 75),
                (1440, 480, 2, 72),
            ],
            scale_degrees=[3, 4, 3, 2],
            contour="wave",
            length_beats=4,
            intensity=PatternIntensity.LOW,
            tags={"counter_melody", "subtle"},
            description=f"{genre.replace('_', ' ').title()} counter melody",
            section_types={"verse", "chorus"}
        ))


# Initialize extended patterns when library is created
PatternLibrary._add_extended_patterns = _add_extended_patterns

# Modify __init__ to call _add_extended_patterns
_original_init = PatternLibrary.__init__

def _new_init(self):
    self.patterns: Dict[str, Dict[PatternType, List[Pattern]]] = {}
    # Initialize pattern type lists for extended types
    self._load_all_patterns()
    # Add extended patterns (fills, transitions, arpeggios, etc.)
    _add_extended_patterns(self)

PatternLibrary.__init__ = _new_init
