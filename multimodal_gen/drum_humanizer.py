"""
Ghost Notes & Intelligent Fills - Professional drum humanization.

Adds ghost notes between main drum hits and generates context-appropriate
drum fills at section boundaries for more musical drum tracks.
"""

from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from enum import Enum
import random


class FillComplexity(Enum):
    """Drum fill complexity levels."""
    MINIMAL = "minimal"      # 2-4 hits
    SIMPLE = "simple"        # 4-8 hits
    MODERATE = "moderate"    # 8-12 hits
    COMPLEX = "complex"      # 12-16 hits
    ELABORATE = "elaborate"  # 16+ hits


@dataclass
class GhostNoteConfig:
    """Configuration for ghost note generation."""
    density: float = 0.3              # 0-1, how many ghost notes to add
    velocity_ratio: float = 0.35      # Ghost velocity relative to main hits
    min_velocity: int = 20            # Minimum ghost note velocity
    max_velocity: int = 50            # Maximum ghost note velocity
    instruments: Tuple[str, ...] = ("snare", "hihat")  # Which drums get ghosts
    avoid_instruments: Tuple[str, ...] = ("kick",)     # Never add ghosts


@dataclass
class FillConfig:
    """Configuration for drum fill generation."""
    complexity: FillComplexity = FillComplexity.MODERATE
    energy: float = 0.7               # 0-1, affects velocity and density
    instruments: Tuple[str, ...] = ("snare", "tom_high", "tom_mid", "tom_low", "hihat")
    include_kick: bool = False        # Include kick in fills
    velocity_range: Tuple[int, int] = (70, 120)
    use_crescendo: bool = True        # Build intensity through fill


class DrumHumanizer:
    """
    Adds ghost notes and generates intelligent fills.
    
    Usage:
        humanizer = DrumHumanizer()
        humanized = humanizer.add_ghost_notes(drum_track, config)
        with_fills = humanizer.place_fills_at_boundaries(track, boundaries, "trap")
    """
    
    def __init__(self, ticks_per_beat: int = 480):
        self.ticks_per_beat = ticks_per_beat
    
    def add_ghost_notes(
        self,
        drum_track: List[Tuple[int, int, int, int]],  # (tick, duration, pitch, velocity)
        config: GhostNoteConfig,
        seed: Optional[int] = None
    ) -> List[Tuple[int, int, int, int]]:
        """
        Add subtle ghost hits between main drum hits.
        
        Ghost notes are quiet hits that fill in the space between main hits,
        adding groove and human feel. Typically 30-50% velocity of main hits.
        
        Args:
            drum_track: List of (tick, duration, pitch, velocity) tuples
            config: Ghost note configuration
            seed: Random seed for reproducibility
            
        Returns:
            New list with original notes plus ghost notes added
        """
        if seed is not None:
            random.seed(seed)
        
        if not drum_track:
            return []
        
        # Start with a copy of the original track
        result = list(drum_track)
        ghost_notes = []
        
        # Get instrument pitches from config
        instrument_pitches = set()
        for inst_name in config.instruments:
            # Check if it's a group name
            if inst_name in INSTRUMENT_GROUPS:
                for drum in INSTRUMENT_GROUPS[inst_name]:
                    if drum in DRUM_MIDI_MAP:
                        instrument_pitches.add(DRUM_MIDI_MAP[drum])
            # Otherwise check if it's a direct drum name
            elif inst_name in DRUM_MIDI_MAP:
                instrument_pitches.add(DRUM_MIDI_MAP[inst_name])
        
        # Get avoid pitches
        avoid_pitches = set()
        for inst_name in config.avoid_instruments:
            if inst_name in INSTRUMENT_GROUPS:
                for drum in INSTRUMENT_GROUPS[inst_name]:
                    if drum in DRUM_MIDI_MAP:
                        avoid_pitches.add(DRUM_MIDI_MAP[drum])
            elif inst_name in DRUM_MIDI_MAP:
                avoid_pitches.add(DRUM_MIDI_MAP[inst_name])
        
        # Sort notes by time
        sorted_notes = sorted(drum_track, key=lambda x: x[0])
        
        # Add ghost notes between main hits
        for i in range(len(sorted_notes) - 1):
            tick1, dur1, pitch1, vel1 = sorted_notes[i]
            tick2, dur2, pitch2, vel2 = sorted_notes[i + 1]
            
            # Only add ghost notes for appropriate instruments
            if pitch1 not in instrument_pitches or pitch1 in avoid_pitches:
                continue
            
            # Calculate gap between notes
            gap = tick2 - tick1
            
            # Only add ghosts if there's enough space (at least 16th note)
            min_gap = self.ticks_per_beat // 4
            if gap < min_gap:
                continue
            
            # Decide if we should add a ghost note based on density
            if random.random() > config.density:
                continue
            
            # Calculate ghost note position (between the two main notes)
            # Add some randomness to avoid mechanical feel
            position_ratio = 0.5 + random.uniform(-0.2, 0.2)
            ghost_tick = int(tick1 + gap * position_ratio)
            
            # Calculate ghost note velocity
            # Base it on the main note's velocity
            base_vel = int(vel1 * config.velocity_ratio)
            # Add slight variation
            variation = random.randint(-5, 5)
            ghost_vel = base_vel + variation
            
            # Clamp to configured range
            ghost_vel = max(config.min_velocity, min(config.max_velocity, ghost_vel))
            
            # Use same pitch as main note, shorter duration
            ghost_dur = dur1 // 2
            
            ghost_notes.append((ghost_tick, ghost_dur, pitch1, ghost_vel))
        
        # Combine original and ghost notes
        result.extend(ghost_notes)
        
        # Sort by time
        result.sort(key=lambda x: x[0])
        
        return result
    
    def generate_fill(
        self,
        genre: str,
        duration_beats: float,
        config: FillConfig,
        seed: Optional[int] = None
    ) -> List[Tuple[int, int, int, int]]:
        """
        Generate a context-appropriate drum fill.
        
        Args:
            genre: Genre name for style-appropriate fill
            duration_beats: Length of fill in beats (typically 1, 2, or 4)
            config: Fill configuration
            seed: Random seed for reproducibility
            
        Returns:
            List of (tick, duration, pitch, velocity) for fill notes
        """
        if seed is not None:
            random.seed(seed)
        
        # Calculate duration in ticks
        duration_ticks = int(duration_beats * self.ticks_per_beat)
        
        # Determine number of notes based on complexity
        complexity_map = {
            FillComplexity.MINIMAL: (2, 4),
            FillComplexity.SIMPLE: (4, 8),
            FillComplexity.MODERATE: (8, 12),
            FillComplexity.COMPLEX: (12, 16),
            FillComplexity.ELABORATE: (16, 24),
        }
        
        min_notes, max_notes = complexity_map[config.complexity]
        # Scale by duration
        min_notes = int(min_notes * duration_beats / 2.0)
        max_notes = int(max_notes * duration_beats / 2.0)
        num_notes = random.randint(min_notes, max_notes)
        
        # Get available instruments
        available_pitches = []
        for inst_name in config.instruments:
            if inst_name in DRUM_MIDI_MAP:
                available_pitches.append(DRUM_MIDI_MAP[inst_name])
        
        # Add kick if configured
        if config.include_kick:
            available_pitches.append(DRUM_MIDI_MAP["kick"])
        
        if not available_pitches:
            return []
        
        # Pre-compute available toms for efficient selection
        available_pitches_set = set(available_pitches)
        available_toms = [DRUM_MIDI_MAP[tom] for tom in ["tom_high", "tom_mid", "tom_low", "tom_floor"]
                          if DRUM_MIDI_MAP[tom] in available_pitches_set]
        
        # Generate fill notes
        fill_notes = []
        min_vel, max_vel = config.velocity_range
        
        for i in range(num_notes):
            # Calculate position in fill (0.0 to 1.0)
            if num_notes > 1:
                position = i / (num_notes - 1)
            else:
                position = 0.5
            
            # Calculate tick position
            # Add some randomness for human feel
            base_tick = int(position * duration_ticks)
            variation = random.randint(-self.ticks_per_beat // 16, self.ticks_per_beat // 16)
            tick = max(0, min(duration_ticks - 1, base_tick + variation))
            
            # Select instrument (favor snare and toms for fills)
            if random.random() < 0.6 and DRUM_MIDI_MAP["snare"] in available_pitches_set:
                pitch = DRUM_MIDI_MAP["snare"]
            elif random.random() < 0.3 and available_toms:
                pitch = random.choice(available_toms)
            else:
                pitch = random.choice(available_pitches)
            
            # Calculate velocity with optional crescendo
            if config.use_crescendo:
                # Build intensity through the fill
                crescendo_factor = 0.6 + (position * 0.4)  # 0.6 to 1.0
                base_vel = int(min_vel + (max_vel - min_vel) * config.energy * crescendo_factor)
            else:
                base_vel = int(min_vel + (max_vel - min_vel) * config.energy)
            
            # Add slight variation
            variation = random.randint(-5, 5)
            velocity = max(1, min(127, base_vel + variation))
            
            # Duration (typically short for fills)
            duration = self.ticks_per_beat // 8  # 32nd note duration
            
            fill_notes.append((tick, duration, pitch, velocity))
        
        # Sort by time
        fill_notes.sort(key=lambda x: x[0])
        
        return fill_notes
    
    def place_fills_at_boundaries(
        self,
        drum_track: List[Tuple[int, int, int, int]],
        section_boundaries: List[float],  # Beat positions
        genre: str,
        fill_probability: float = 0.8,
        config: Optional[FillConfig] = None,
        seed: Optional[int] = None
    ) -> List[Tuple[int, int, int, int]]:
        """
        Automatically add fills at section transitions.
        
        Args:
            drum_track: Original drum track
            section_boundaries: Beat positions where sections change
            genre: Genre for fill style
            fill_probability: Chance to add fill at each boundary (0-1)
            config: Optional fill configuration
            seed: Random seed for reproducibility
            
        Returns:
            Track with fills inserted before section boundaries
        """
        if seed is not None:
            random.seed(seed)
        
        if not section_boundaries:
            return list(drum_track)
        
        if config is None:
            config = self.get_genre_fill_config(genre)
        
        result = list(drum_track)
        
        for boundary_beat in section_boundaries:
            # Decide if we should add a fill here
            if random.random() > fill_probability:
                continue
            
            # Determine fill duration (typically 1 or 2 beats before boundary)
            fill_durations = [1.0, 2.0]
            fill_duration = random.choice(fill_durations)
            
            # Calculate fill start position (before boundary)
            fill_start_beat = boundary_beat - fill_duration
            if fill_start_beat < 0:
                continue
            
            fill_start_tick = int(fill_start_beat * self.ticks_per_beat)
            
            # Generate the fill
            fill_notes = self.generate_fill(genre, fill_duration, config, seed=None)
            
            # Offset fill notes to start at the correct position
            offset_fill = [
                (tick + fill_start_tick, dur, pitch, vel)
                for tick, dur, pitch, vel in fill_notes
            ]
            
            # Remove any existing notes in the fill region to avoid conflicts
            boundary_tick = int(boundary_beat * self.ticks_per_beat)
            result = [
                note for note in result
                if note[0] < fill_start_tick or note[0] >= boundary_tick
            ]
            
            # Add fill notes
            result.extend(offset_fill)
        
        # Sort by time
        result.sort(key=lambda x: x[0])
        
        return result
    
    def get_genre_ghost_config(self, genre: str) -> GhostNoteConfig:
        """Get genre-appropriate ghost note configuration."""
        return GENRE_GHOST_CONFIGS.get(genre.lower(), GhostNoteConfig())
    
    def get_genre_fill_config(self, genre: str) -> FillConfig:
        """Get genre-appropriate fill configuration."""
        return GENRE_FILL_CONFIGS.get(genre.lower(), FillConfig())

    def generate_pattern_fill(
        self,
        genre: str,
        pattern_name: str,
        start_tick: int = 0,
        **kwargs,
    ) -> List[Tuple[int, int, int, int]]:
        """Return fill notes from ``GENRE_FILL_PATTERNS``.

        Each stored pattern is a list of ``(relative_tick, pitch, velocity)``
        tuples. This method converts them to full note tuples offset by
        *start_tick*.

        Args:
            genre: Genre key in ``GENRE_FILL_PATTERNS``.
            pattern_name: Pattern key within the genre dict.
            start_tick: Absolute tick to offset the pattern by.
            **kwargs: Reserved for future use.

        Returns:
            List of ``(tick, duration, pitch, velocity)`` tuples.
            Returns empty list if genre/pattern not found.
        """
        if not GENRE_FILL_PATTERNS:
            _init_genre_fill_patterns()

        patterns = GENRE_FILL_PATTERNS.get(genre, {})
        pattern = patterns.get(pattern_name)
        if pattern is None:
            return []

        duration = self.ticks_per_beat // 8  # 32nd-note default duration
        return [
            (start_tick + rel_tick, duration, pitch, vel)
            for rel_tick, pitch, vel in pattern
        ]


# Genre-specific ghost note presets
GENRE_GHOST_CONFIGS: Dict[str, GhostNoteConfig] = {
    "jazz": GhostNoteConfig(density=0.5, velocity_ratio=0.4, instruments=("snare", "hihat")),
    "hip_hop": GhostNoteConfig(density=0.3, velocity_ratio=0.35, instruments=("snare", "hihat")),
    "boom_bap": GhostNoteConfig(density=0.35, velocity_ratio=0.38, instruments=("snare",)),
    "trap": GhostNoteConfig(density=0.4, velocity_ratio=0.3, instruments=("hihat",)),  # Mostly hihat ghosts
    "funk": GhostNoteConfig(density=0.6, velocity_ratio=0.45, instruments=("snare", "hihat")),  # Heavy ghosts
    "r_and_b": GhostNoteConfig(density=0.35, velocity_ratio=0.35, instruments=("snare", "hihat")),
    "rock": GhostNoteConfig(density=0.25, velocity_ratio=0.3, instruments=("snare",)),
    "house": GhostNoteConfig(density=0.3, velocity_ratio=0.35, instruments=("hihat",)),
}


# Genre-specific fill presets
GENRE_FILL_CONFIGS: Dict[str, FillConfig] = {
    "jazz": FillConfig(complexity=FillComplexity.MODERATE, energy=0.6, use_crescendo=True),
    "hip_hop": FillConfig(complexity=FillComplexity.SIMPLE, energy=0.7, use_crescendo=False),
    "boom_bap": FillConfig(complexity=FillComplexity.MODERATE, energy=0.75, use_crescendo=True),
    "trap": FillConfig(complexity=FillComplexity.COMPLEX, energy=0.8, instruments=("snare", "hihat")),
    "funk": FillConfig(complexity=FillComplexity.ELABORATE, energy=0.85, use_crescendo=True),
    "r_and_b": FillConfig(complexity=FillComplexity.SIMPLE, energy=0.65, use_crescendo=True),
    "rock": FillConfig(complexity=FillComplexity.MODERATE, energy=0.9, include_kick=True),
    "house": FillConfig(complexity=FillComplexity.MINIMAL, energy=0.6, instruments=("hihat", "snare")),
}


# =============================================================================
# GENRE FILL PATTERNS (Wave 2 – C3)
# =============================================================================

# Pre-composed fill patterns per genre.
# Each pattern is a list of (relative_tick, pitch, velocity) tuples
# covering a 1-bar fill (1920 ticks at 480 PPQ).

GENRE_FILL_PATTERNS: Dict[str, Dict[str, List[Tuple[int, int, int]]]] = {}

def _init_genre_fill_patterns() -> None:
    """Populate ``GENRE_FILL_PATTERNS`` after DRUM_MIDI_MAP is defined."""
    global GENRE_FILL_PATTERNS

    _K = 36   # kick
    _S = 38   # snare
    _HH = 42  # hi-hat closed
    _TH = 50  # tom high
    _TM = 47  # tom mid
    _TL = 45  # tom low
    _CR = 49  # crash

    GENRE_FILL_PATTERNS.update({
        "trap": {
            "hi_hat_roll": [
                (i * 60, _HH, 60 + i * 4) for i in range(32)  # 32nd-note hi-hat build
            ],
            "snare_roll": [
                (i * 120, _S, 70 + i * 3) for i in range(16)  # 16th-note snare roll
            ],
        },
        "boom_bap": {
            "classic_break": [
                (0, _TH, 90), (240, _TH, 85),
                (480, _TM, 95), (720, _TM, 88),
                (960, _TL, 100), (1200, _TL, 92),
                (1440, _S, 110), (1680, _K, 100),
                (1800, _CR, 120),
            ],
            "snare_4": [
                (0, _S, 85), (480, _S, 90),
                (960, _S, 100), (1440, _S, 115),
            ],
        },
        "house": {
            "clap_build": [
                (0, _S, 60), (240, _S, 65), (480, _S, 70),
                (720, _S, 78), (960, _S, 85), (1200, _S, 95),
                (1440, _S, 110), (1680, _S, 120),
            ],
            "percussion_fill": [
                (0, _HH, 80), (120, _HH, 70), (240, _TH, 85),
                (480, _HH, 75), (600, _HH, 65), (720, _TM, 90),
                (960, _HH, 80), (1080, _HH, 70), (1200, _TL, 95),
                (1440, _CR, 110), (1680, _K, 100),
            ],
        },
    })


def energy_aware_fill_selection(genre: str, energy: float = 0.5) -> str:
    """Pick a fill pattern name based on energy level.

    High energy (>0.6) → complex fills (rolls, builds).
    Low energy (<=0.6) → simple fills (snare_4, ghost patterns).

    Args:
        genre: Genre key in ``GENRE_FILL_PATTERNS``.
        energy: Energy level 0.0–1.0.

    Returns:
        Pattern name string from the genre's fill dict.
        Falls back to the first available pattern if genre is unknown.
    """
    if not GENRE_FILL_PATTERNS:
        _init_genre_fill_patterns()

    patterns = GENRE_FILL_PATTERNS.get(genre, {})
    if not patterns:
        # Fallback: try first genre that exists
        for _g, _p in GENRE_FILL_PATTERNS.items():
            patterns = _p
            break
    if not patterns:
        return "default"

    names = list(patterns.keys())

    # Simple heuristic: high-energy picks last pattern (more complex),
    # low-energy picks first pattern (simpler).
    if energy > 0.6:
        return names[-1] if len(names) > 1 else names[0]
    return names[0]


# Standard MIDI drum mapping (General MIDI)
DRUM_MIDI_MAP = {
    "kick": 36,
    "snare": 38,
    "snare_rim": 37,
    "hihat_closed": 42,
    "hihat_open": 46,
    "hihat_pedal": 44,
    "tom_high": 50,
    "tom_mid": 47,
    "tom_low": 45,
    "tom_floor": 43,
    "crash": 49,
    "ride": 51,
    "ride_bell": 53,
}


# Instrument group mappings for convenience
INSTRUMENT_GROUPS = {
    "snare": ["snare", "snare_rim"],
    "hihat": ["hihat_closed", "hihat_open", "hihat_pedal"],
    "tom": ["tom_high", "tom_mid", "tom_low", "tom_floor"],
}


# Initialize genre fill patterns on module load
_init_genre_fill_patterns()


# Convenience function
def add_ghost_notes(
    drum_track: List[Tuple[int, int, int, int]],
    genre: str = "hip_hop",
    density: Optional[float] = None,
    seed: Optional[int] = None
) -> List[Tuple[int, int, int, int]]:
    """
    Convenience function to add ghost notes with genre preset.
    
    Args:
        drum_track: Drum notes as (tick, duration, pitch, velocity)
        genre: Genre for preset selection
        density: Optional override for ghost density
        seed: Random seed
        
    Returns:
        Track with ghost notes added
    """
    humanizer = DrumHumanizer()
    config = humanizer.get_genre_ghost_config(genre)
    
    if density is not None:
        # Create a copy to avoid modifying the shared preset
        from dataclasses import replace
        config = replace(config, density=density)
    
    return humanizer.add_ghost_notes(drum_track, config, seed)


def generate_fill(
    genre: str,
    duration_beats: float = 2.0,
    energy: float = 0.7,
    seed: Optional[int] = None
) -> List[Tuple[int, int, int, int]]:
    """
    Convenience function to generate a drum fill.
    
    Args:
        genre: Genre for fill style
        duration_beats: Length in beats
        energy: Energy level 0-1
        seed: Random seed
        
    Returns:
        Fill notes as (tick, duration, pitch, velocity)
    """
    humanizer = DrumHumanizer()
    config = humanizer.get_genre_fill_config(genre)
    
    # Create a copy to avoid modifying the shared preset
    from dataclasses import replace
    config = replace(config, energy=energy)
    
    return humanizer.generate_fill(genre, duration_beats, config, seed)


# =============================================================================
# MODULE TEST
# =============================================================================

if __name__ == '__main__':
    print("=== Drum Humanizer Test ===\n")
    
    # Create test drum track (simple kick and snare pattern)
    test_track = [
        (0, 240, 36, 100),       # Kick on beat 1
        (480, 240, 38, 90),      # Snare on beat 2
        (960, 240, 36, 100),     # Kick on beat 3
        (1440, 240, 38, 90),     # Snare on beat 4
        (1920, 240, 36, 100),    # Kick on beat 5
    ]
    
    print("Original track:")
    for tick, dur, pitch, vel in test_track:
        print(f"  Tick {tick:4d}: pitch {pitch:2d} (vel {vel:3d})")
    
    # Test ghost notes
    print("\nAdding hip-hop ghost notes (seeded):")
    humanizer = DrumHumanizer()
    ghosted = humanizer.add_ghost_notes(
        test_track,
        humanizer.get_genre_ghost_config("hip_hop"),
        seed=42
    )
    print(f"Original notes: {len(test_track)}, With ghosts: {len(ghosted)}")
    for tick, dur, pitch, vel in sorted(ghosted, key=lambda x: x[0]):
        note_type = "MAIN" if vel > 70 else "ghost"
        print(f"  Tick {tick:4d}: pitch {pitch:2d} (vel {vel:3d}) [{note_type}]")
    
    # Test fill generation
    print("\nGenerating trap fill (2 beats, seeded):")
    fill = humanizer.generate_fill(
        "trap",
        duration_beats=2.0,
        config=humanizer.get_genre_fill_config("trap"),
        seed=42
    )
    print(f"Fill notes: {len(fill)}")
    for tick, dur, pitch, vel in fill[:10]:  # Show first 10
        print(f"  Tick {tick:4d}: pitch {pitch:2d} (vel {vel:3d})")
    
    # Test section boundary fills
    print("\nPlacing fills at section boundaries:")
    boundaries = [8.0, 16.0]  # Beat 8 and 16
    with_fills = humanizer.place_fills_at_boundaries(
        test_track,
        boundaries,
        "hip_hop",
        fill_probability=1.0,  # Always add fills for testing
        seed=42
    )
    print(f"Original notes: {len(test_track)}, With fills: {len(with_fills)}")
    
    # Show genre presets
    print("\nAvailable ghost note presets:")
    for genre_name, config in GENRE_GHOST_CONFIGS.items():
        print(f"  {genre_name:12s}: density={config.density:.2f}, "
              f"velocity_ratio={config.velocity_ratio:.2f}, "
              f"instruments={config.instruments}")
    
    print("\nAvailable fill presets:")
    for genre_name, config in GENRE_FILL_CONFIGS.items():
        print(f"  {genre_name:12s}: complexity={config.complexity.value}, "
              f"energy={config.energy:.2f}, crescendo={config.use_crescendo}")
    
    print("\n✅ Drum humanizer test complete!")
