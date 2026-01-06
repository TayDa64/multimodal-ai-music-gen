"""
Microtiming Engine - Humanized timing variations for MIDI notes.

Applies subtle, genre-appropriate timing shifts to create natural-feeling grooves.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from enum import Enum
import random


class GrooveStyle(Enum):
    """Predefined groove timing styles."""
    STRAIGHT = "straight"      # Minimal swing, on-grid
    SWING = "swing"            # Jazz swing feel (triplet-based)
    LAID_BACK = "laid_back"    # Behind the beat (R&B, neo-soul)
    PUSHED = "pushed"          # Ahead of the beat (punk, energetic)
    SHUFFLE = "shuffle"        # Blues shuffle
    HUMAN = "human"            # Random subtle variations


@dataclass
class MicrotimingConfig:
    """Configuration for microtiming behavior."""
    swing_amount: float = 0.0      # 0.0 = straight, 1.0 = full triplet swing
    push_pull: float = 0.0         # -1.0 = behind beat, +1.0 = ahead
    randomness: float = 0.0        # Amount of random variation (0.0-1.0)
    groove_style: GrooveStyle = GrooveStyle.STRAIGHT
    ticks_per_beat: int = 480


class MicrotimingEngine:
    """
    Applies humanized timing to MIDI notes.
    
    Usage:
        engine = MicrotimingEngine()
        humanized_notes = engine.apply(notes, config)
    """
    
    def __init__(self, ticks_per_beat: int = 480):
        self.ticks_per_beat = ticks_per_beat
    
    def apply(
        self,
        notes: List[Tuple[int, int, int, int]],  # (tick, duration, pitch, velocity)
        config: MicrotimingConfig
    ) -> List[Tuple[int, int, int, int]]:
        """
        Apply microtiming to a list of notes.
        
        Args:
            notes: List of (tick, duration, pitch, velocity) tuples
            config: Microtiming configuration
            
        Returns:
            New list with adjusted timing
        """
        if not notes:
            return []
        
        # Start with a copy of the notes
        result = list(notes)
        
        # Apply swing if needed
        if config.swing_amount > 0:
            result = self.apply_swing(result, config.swing_amount)
        
        # Apply push/pull if needed
        if config.push_pull != 0:
            result = self.apply_push_pull(result, config.push_pull)
        
        # Apply humanize if needed
        if config.randomness > 0:
            result = self.apply_humanize(result, config.randomness)
        
        # Ensure no negative ticks
        result = [(max(0, tick), dur, pitch, vel) for tick, dur, pitch, vel in result]
        
        return result
    
    def apply_swing(
        self,
        notes: List[Tuple[int, int, int, int]],
        swing_amount: float
    ) -> List[Tuple[int, int, int, int]]:
        """
        Apply swing timing (delay off-beat notes).
        
        swing_amount: 0.0 = straight eighths, 1.0 = full triplet swing
        
        The classic swing formula:
        - On-beat notes: unchanged
        - Off-beat notes: delayed by swing_amount * (ticks_per_beat / 3)
        """
        if swing_amount <= 0:
            return notes
        
        # Calculate swing offset (max = 1/3 of a beat for full triplet swing)
        max_swing_ticks = self.ticks_per_beat // 3
        swing_offset = int(max_swing_ticks * swing_amount)
        
        result = []
        for tick, duration, pitch, velocity in notes:
            # Check if this note is on an off-beat
            if self._is_offbeat(tick):
                # Delay off-beat notes
                new_tick = tick + swing_offset
            else:
                # Keep on-beat notes unchanged
                new_tick = tick
            
            result.append((new_tick, duration, pitch, velocity))
        
        return result
    
    def apply_push_pull(
        self,
        notes: List[Tuple[int, int, int, int]],
        amount: float
    ) -> List[Tuple[int, int, int, int]]:
        """
        Shift all notes slightly ahead or behind the beat.
        
        amount: -1.0 = behind (laid back), +1.0 = ahead (pushed)
        """
        if amount == 0:
            return notes
        
        # Max push/pull = 1/16th note = ticks_per_beat / 4
        max_shift = self.ticks_per_beat // 4
        # Negative amount = positive shift (later = behind)
        shift = int(-amount * max_shift)
        
        result = []
        for tick, duration, pitch, velocity in notes:
            new_tick = tick + shift
            result.append((new_tick, duration, pitch, velocity))
        
        return result
    
    def apply_humanize(
        self,
        notes: List[Tuple[int, int, int, int]],
        randomness: float
    ) -> List[Tuple[int, int, int, int]]:
        """
        Add random timing variations to simulate human performance.
        
        randomness: 0.0 = none, 1.0 = max variation (still musically reasonable)
        """
        if randomness <= 0:
            return notes
        
        # Random variation up to 1/32nd note at max randomness
        max_variation = self.ticks_per_beat // 8
        
        result = []
        for tick, duration, pitch, velocity in notes:
            # Use Gaussian distribution for more natural variation
            # Standard deviation = max_variation / 3 so 99.7% of values within max_variation
            variation = int(random.gauss(0, randomness * max_variation / 3))
            new_tick = tick + variation
            result.append((new_tick, duration, pitch, velocity))
        
        return result
    
    def _is_offbeat(self, tick: int) -> bool:
        """
        Check if tick falls on an off-beat (the 'and').
        
        For 8th note subdivision:
        - On-beats: 0, 480, 960, 1440, ... (multiples of ticks_per_beat)
        - Off-beats: 240, 720, 1200, ... (half-beat positions)
        """
        position_in_beat = tick % self.ticks_per_beat
        half_beat = self.ticks_per_beat // 2
        tolerance = self.ticks_per_beat // 8  # Allow some slop (1/16th note)
        
        return abs(position_in_beat - half_beat) < tolerance
    
    def get_preset(self, genre: str) -> MicrotimingConfig:
        """
        Get genre-appropriate microtiming preset.
        
        Args:
            genre: Genre name (jazz, hip-hop, funk, r&b, rock, etc.)
            
        Returns:
            MicrotimingConfig with appropriate settings
        """
        return GENRE_PRESETS.get(genre.lower(), MicrotimingConfig())


# Genre presets
GENRE_PRESETS: Dict[str, MicrotimingConfig] = {
    "jazz": MicrotimingConfig(
        swing_amount=0.6,
        push_pull=0.0,
        randomness=0.15,
        groove_style=GrooveStyle.SWING,
        ticks_per_beat=480
    ),
    "hip-hop": MicrotimingConfig(
        swing_amount=0.3,
        push_pull=-0.1,  # Slightly laid back
        randomness=0.1,
        groove_style=GrooveStyle.LAID_BACK,
        ticks_per_beat=480
    ),
    "funk": MicrotimingConfig(
        swing_amount=0.2,
        push_pull=0.05,  # Slightly pushed
        randomness=0.08,
        groove_style=GrooveStyle.PUSHED,
        ticks_per_beat=480
    ),
    "r&b": MicrotimingConfig(
        swing_amount=0.25,
        push_pull=-0.15,  # Behind the beat
        randomness=0.12,
        groove_style=GrooveStyle.LAID_BACK,
        ticks_per_beat=480
    ),
    "rock": MicrotimingConfig(
        swing_amount=0.0,
        push_pull=0.0,
        randomness=0.05,
        groove_style=GrooveStyle.STRAIGHT,
        ticks_per_beat=480
    ),
    "blues": MicrotimingConfig(
        swing_amount=0.5,
        push_pull=0.0,
        randomness=0.1,
        groove_style=GrooveStyle.SHUFFLE,
        ticks_per_beat=480
    ),
}


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def apply_microtiming(
    notes: List[Tuple[int, int, int, int]],
    genre: Optional[str] = None,
    config: Optional[MicrotimingConfig] = None
) -> List[Tuple[int, int, int, int]]:
    """
    Convenience function to apply microtiming to notes.
    
    Args:
        notes: List of (tick, duration, pitch, velocity) tuples
        genre: Genre name for preset (if config not provided)
        config: Custom MicrotimingConfig (overrides genre)
        
    Returns:
        New list with adjusted timing
    """
    engine = MicrotimingEngine()
    
    if config is None:
        if genre:
            config = engine.get_preset(genre)
        else:
            config = MicrotimingConfig()
    
    return engine.apply(notes, config)


# =============================================================================
# MODULE TEST
# =============================================================================

if __name__ == '__main__':
    print("=== Microtiming Engine Test ===\n")
    
    # Create test notes (4 eighth notes)
    test_notes = [
        (0, 240, 60, 100),      # Beat 1
        (240, 240, 62, 90),     # Off-beat (and of 1)
        (480, 240, 64, 100),    # Beat 2
        (720, 240, 65, 90),     # Off-beat (and of 2)
    ]
    
    print("Original notes:")
    for tick, dur, pitch, vel in test_notes:
        print(f"  Tick {tick:4d}: pitch {pitch:3d}, dur {dur:3d}, vel {vel:3d}")
    
    # Test swing
    print("\nApplying jazz swing (60%):")
    engine = MicrotimingEngine()
    jazz_config = GENRE_PRESETS['jazz']
    swung_notes = engine.apply_swing(test_notes, jazz_config.swing_amount)
    for tick, dur, pitch, vel in swung_notes:
        print(f"  Tick {tick:4d}: pitch {pitch:3d}, dur {dur:3d}, vel {vel:3d}")
    
    # Test push/pull
    print("\nApplying laid-back feel (R&B -15%):")
    rnb_config = GENRE_PRESETS['r&b']
    pushed_notes = engine.apply_push_pull(test_notes, rnb_config.push_pull)
    for tick, dur, pitch, vel in pushed_notes:
        print(f"  Tick {tick:4d}: pitch {pitch:3d}, dur {dur:3d}, vel {vel:3d}")
    
    # Test humanize with seed for determinism
    print("\nApplying humanize (15% randomness, seeded):")
    random.seed(42)
    humanized_notes = engine.apply_humanize(test_notes, 0.15)
    for tick, dur, pitch, vel in humanized_notes:
        print(f"  Tick {tick:4d}: pitch {pitch:3d}, dur {dur:3d}, vel {vel:3d}")
    
    # Test full jazz preset
    print("\nApplying full jazz preset (swing + humanize):")
    random.seed(42)
    jazz_notes = engine.apply(test_notes, jazz_config)
    for tick, dur, pitch, vel in jazz_notes:
        print(f"  Tick {tick:4d}: pitch {pitch:3d}, dur {dur:3d}, vel {vel:3d}")
    
    # Show all genre presets
    print("\nAvailable genre presets:")
    for genre_name, preset in GENRE_PRESETS.items():
        print(f"  {genre_name:12s}: swing={preset.swing_amount:.2f}, "
              f"push_pull={preset.push_pull:+.2f}, randomness={preset.randomness:.2f}, "
              f"style={preset.groove_style.value}")
    
    print("\n✅ Microtiming engine test complete!")
