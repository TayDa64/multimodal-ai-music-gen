"""
Phrase-Level Dynamics System - Musical expression through velocity shaping.

Applies crescendos, decrescendos, accents, and phrase-level velocity curves
to create more expressive and musical output.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple, Callable
from enum import Enum
import math


class DynamicShape(Enum):
    """Predefined dynamic envelope shapes."""
    FLAT = "flat"                  # No change
    CRESCENDO = "crescendo"        # Gradual increase
    DECRESCENDO = "decrescendo"    # Gradual decrease
    SWELL = "swell"                # Crescendo then decrescendo (peak in middle)
    FADE_IN = "fade_in"            # Quick crescendo at start
    FADE_OUT = "fade_out"          # Quick decrescendo at end
    ACCENT_FIRST = "accent_first"  # Strong first beat, decay
    ACCENT_LAST = "accent_last"    # Build to final note


class DynamicLevel(Enum):
    """Standard musical dynamic levels."""
    PPP = 16    # Pianississimo
    PP = 32     # Pianissimo
    P = 48      # Piano
    MP = 64     # Mezzo-piano
    MF = 80     # Mezzo-forte
    F = 96      # Forte
    FF = 112    # Fortissimo
    FFF = 127   # Fortississimo


@dataclass
class DynamicsConfig:
    """Configuration for dynamics processing."""
    base_velocity: int = 80              # Base velocity level
    velocity_range: Tuple[int, int] = (40, 120)  # Min/max velocity
    phrase_shape: DynamicShape = DynamicShape.SWELL
    accent_strength: float = 0.2         # How much accents stand out (0.0-1.0)
    downbeat_accent: float = 0.1         # Extra velocity on downbeats
    phrase_length_beats: int = 4         # Length of phrase for shaping


class DynamicsEngine:
    """
    Applies phrase-level dynamics to MIDI notes.
    
    Usage:
        engine = DynamicsEngine()
        expressive_notes = engine.apply(notes, config)
    """
    
    def __init__(self, ticks_per_beat: int = 480):
        self.ticks_per_beat = ticks_per_beat
    
    def apply(
        self,
        notes: List[Tuple[int, int, int, int]],  # (tick, duration, pitch, velocity)
        config: DynamicsConfig
    ) -> List[Tuple[int, int, int, int]]:
        """
        Apply dynamics shaping to notes.
        
        Args:
            notes: List of (tick, duration, pitch, velocity) tuples
            config: Dynamics configuration
            
        Returns:
            New list with shaped velocities
        """
        if not notes:
            return []
        
        # Start with a copy, setting base velocity
        result = [(tick, dur, pitch, config.base_velocity) for tick, dur, pitch, vel in notes]
        
        # Apply phrase-level shaping
        phrase_length_ticks = config.phrase_length_beats * self.ticks_per_beat
        result = self.apply_phrase_shape(result, config.phrase_shape, phrase_length_ticks)
        
        # Apply downbeat accents if configured
        if config.downbeat_accent > 0:
            result = self.apply_downbeat_accents(result, config.downbeat_accent)
        
        # Clamp velocities to valid range
        min_vel, max_vel = config.velocity_range
        result = [(tick, dur, pitch, self._clamp_velocity(vel, min_vel, max_vel)) 
                  for tick, dur, pitch, vel in result]
        
        return result
    
    def apply_phrase_shape(
        self,
        notes: List[Tuple[int, int, int, int]],
        shape: DynamicShape,
        phrase_length_ticks: int
    ) -> List[Tuple[int, int, int, int]]:
        """
        Apply a dynamic shape curve over phrases.
        
        Divides notes into phrases and applies the shape to each.
        """
        if not notes or shape == DynamicShape.FLAT:
            return notes
        
        result = []
        for tick, dur, pitch, vel in notes:
            # Calculate position within phrase (0.0 to 1.0)
            position = self._get_phrase_position(tick, phrase_length_ticks)
            
            # Get velocity multiplier from shape curve
            multiplier = self._get_shape_multiplier(shape, position)
            
            # Apply multiplier to velocity
            new_vel = int(vel * multiplier)
            result.append((tick, dur, pitch, new_vel))
        
        return result
    
    def apply_downbeat_accents(
        self,
        notes: List[Tuple[int, int, int, int]],
        accent_amount: float
    ) -> List[Tuple[int, int, int, int]]:
        """
        Add accent to notes falling on downbeats.
        
        accent_amount: 0.0 = no accent, 1.0 = max accent (+20 velocity)
        """
        if accent_amount <= 0:
            return notes
        
        # Max accent boost = 20 velocity units
        max_accent = 20
        accent_boost = int(max_accent * accent_amount)
        
        result = []
        for tick, dur, pitch, vel in notes:
            if self._is_downbeat(tick):
                new_vel = vel + accent_boost
            else:
                new_vel = vel
            result.append((tick, dur, pitch, new_vel))
        
        return result
    
    def apply_crescendo(
        self,
        notes: List[Tuple[int, int, int, int]],
        start_velocity: int,
        end_velocity: int
    ) -> List[Tuple[int, int, int, int]]:
        """Apply linear crescendo across all notes."""
        if not notes or len(notes) == 1:
            return notes
        
        result = []
        for i, (tick, dur, pitch, vel) in enumerate(notes):
            # Linear interpolation from start to end
            progress = i / (len(notes) - 1)
            new_vel = int(start_velocity + (end_velocity - start_velocity) * progress)
            result.append((tick, dur, pitch, new_vel))
        
        return result
    
    def apply_decrescendo(
        self,
        notes: List[Tuple[int, int, int, int]],
        start_velocity: int,
        end_velocity: int
    ) -> List[Tuple[int, int, int, int]]:
        """Apply linear decrescendo across all notes."""
        # Decrescendo is just a crescendo with reversed velocities
        return self.apply_crescendo(notes, start_velocity, end_velocity)
    
    def get_shape_curve(self, shape: DynamicShape, num_points: int) -> List[float]:
        """
        Get velocity multiplier curve for a shape.
        
        Returns list of multipliers (0.0-1.0) for each point.
        """
        if num_points <= 0:
            return []
        
        curve = []
        for i in range(num_points):
            position = i / (num_points - 1) if num_points > 1 else 0.0
            multiplier = self._get_shape_multiplier(shape, position)
            curve.append(multiplier)
        
        return curve
    
    def get_preset(self, genre: str) -> DynamicsConfig:
        """Get genre-appropriate dynamics preset."""
        return GENRE_DYNAMICS.get(genre.lower(), GENRE_DYNAMICS["jazz"])
    
    def _get_phrase_position(self, tick: int, phrase_length_ticks: int) -> float:
        """
        Get position within phrase as 0.0-1.0.
        
        tick=0 in phrase → 0.0
        tick at end of phrase → 1.0
        """
        if phrase_length_ticks <= 0:
            return 0.0
        
        position_in_phrase = tick % phrase_length_ticks
        return position_in_phrase / phrase_length_ticks
    
    def _get_shape_multiplier(self, shape: DynamicShape, position: float) -> float:
        """Get velocity multiplier for a shape at given position."""
        if shape == DynamicShape.FLAT:
            return 1.0
        elif shape == DynamicShape.CRESCENDO:
            return curve_crescendo(position)
        elif shape == DynamicShape.DECRESCENDO:
            return curve_decrescendo(position)
        elif shape == DynamicShape.SWELL:
            return curve_swell(position)
        elif shape == DynamicShape.FADE_IN:
            return curve_fade_in(position)
        elif shape == DynamicShape.FADE_OUT:
            return curve_fade_out(position)
        elif shape == DynamicShape.ACCENT_FIRST:
            return curve_accent_first(position)
        elif shape == DynamicShape.ACCENT_LAST:
            return curve_accent_last(position)
        else:
            return 1.0
    
    def _is_downbeat(self, tick: int, beats_per_bar: int = 4) -> bool:
        """Check if tick falls on beat 1 of a bar."""
        ticks_per_bar = self.ticks_per_beat * beats_per_bar
        # Allow some tolerance for slightly off-grid notes (1/16th note)
        tolerance = self.ticks_per_beat // 8
        return (tick % ticks_per_bar) < tolerance
    
    def _clamp_velocity(self, velocity: int, min_vel: int = 1, max_vel: int = 127) -> int:
        """Ensure velocity stays in valid MIDI range."""
        return max(min_vel, min(max_vel, velocity))


# Shape curve generators
def curve_crescendo(position: float) -> float:
    """Linear crescendo: 0.5 at start, 1.0 at end."""
    return 0.5 + (position * 0.5)


def curve_decrescendo(position: float) -> float:
    """Linear decrescendo: 1.0 at start, 0.5 at end."""
    return 1.0 - (position * 0.5)


def curve_swell(position: float) -> float:
    """Swell: crescendo to middle, decrescendo to end."""
    # Sine curve peaking at 0.5
    return 0.6 + 0.4 * math.sin(position * math.pi)


def curve_accent_first(position: float) -> float:
    """Strong first beat, gradual decay."""
    return 1.0 - (position * 0.3)


def curve_accent_last(position: float) -> float:
    """Build to strong final note."""
    return 0.7 + (position * 0.3)


def curve_fade_in(position: float) -> float:
    """Quick crescendo at start using exponential curve."""
    # Exponential fade in: starts very soft, quickly builds
    return 0.3 + 0.7 * (position ** 0.5)


def curve_fade_out(position: float) -> float:
    """Quick decrescendo at end using exponential curve."""
    # Exponential fade out: starts strong, quickly decreases
    return 1.0 - 0.7 * (position ** 2)


# Genre presets
GENRE_DYNAMICS: Dict[str, DynamicsConfig] = {
    "jazz": DynamicsConfig(
        base_velocity=75,
        velocity_range=(45, 115),
        phrase_shape=DynamicShape.SWELL,
        accent_strength=0.15,
        downbeat_accent=0.1,
        phrase_length_beats=4
    ),
    "hip-hop": DynamicsConfig(
        base_velocity=90,
        velocity_range=(60, 120),
        phrase_shape=DynamicShape.ACCENT_FIRST,
        accent_strength=0.25,
        downbeat_accent=0.2,
        phrase_length_beats=4
    ),
    "classical": DynamicsConfig(
        base_velocity=70,
        velocity_range=(30, 110),
        phrase_shape=DynamicShape.SWELL,
        accent_strength=0.1,
        downbeat_accent=0.05,
        phrase_length_beats=8
    ),
    "rock": DynamicsConfig(
        base_velocity=100,
        velocity_range=(80, 127),
        phrase_shape=DynamicShape.FLAT,
        accent_strength=0.3,
        downbeat_accent=0.25,
        phrase_length_beats=4
    ),
    "r&b": DynamicsConfig(
        base_velocity=75,
        velocity_range=(50, 105),
        phrase_shape=DynamicShape.SWELL,
        accent_strength=0.12,
        downbeat_accent=0.08,
        phrase_length_beats=4
    ),
    "funk": DynamicsConfig(
        base_velocity=95,
        velocity_range=(70, 120),
        phrase_shape=DynamicShape.ACCENT_FIRST,
        accent_strength=0.35,
        downbeat_accent=0.3,
        phrase_length_beats=2
    ),
}


# Convenience function
def apply_dynamics(
    notes: List[Tuple[int, int, int, int]],
    genre: str = "jazz",
    config: Optional[DynamicsConfig] = None
) -> List[Tuple[int, int, int, int]]:
    """
    Convenience function to apply dynamics.
    
    Args:
        notes: MIDI notes as (tick, duration, pitch, velocity)
        genre: Genre name for preset selection
        config: Optional custom config (overrides genre)
        
    Returns:
        Notes with dynamics applied
    """
    engine = DynamicsEngine()
    if config is None:
        config = GENRE_DYNAMICS.get(genre, GENRE_DYNAMICS["jazz"])
    return engine.apply(notes, config)


# =============================================================================
# MODULE TEST
# =============================================================================

if __name__ == '__main__':
    print("=== Dynamics Engine Test ===\n")
    
    # Create test notes (8 quarter notes at C4)
    test_notes = [
        (i * 480, 240, 60, 80) for i in range(8)
    ]
    
    print("Original notes:")
    for tick, dur, pitch, vel in test_notes:
        print(f"  Tick {tick:4d}: pitch {pitch:3d}, vel {vel:3d}")
    
    # Test jazz preset
    print("\nApplying jazz dynamics (swell shape):")
    engine = DynamicsEngine()
    jazz_config = GENRE_DYNAMICS['jazz']
    shaped_notes = engine.apply(test_notes, jazz_config)
    for tick, dur, pitch, vel in shaped_notes:
        print(f"  Tick {tick:4d}: pitch {pitch:3d}, vel {vel:3d}")
    
    # Test crescendo
    print("\nApplying crescendo (p to f):")
    cresc_notes = engine.apply_crescendo(test_notes, 48, 96)
    for tick, dur, pitch, vel in cresc_notes:
        print(f"  Tick {tick:4d}: pitch {pitch:3d}, vel {vel:3d}")
    
    # Test accent_first shape
    print("\nApplying accent_first shape:")
    config = DynamicsConfig(
        base_velocity=80,
        phrase_shape=DynamicShape.ACCENT_FIRST,
        phrase_length_beats=4
    )
    accent_notes = engine.apply(test_notes, config)
    for tick, dur, pitch, vel in accent_notes:
        print(f"  Tick {tick:4d}: pitch {pitch:3d}, vel {vel:3d}")
    
    # Show all genre presets
    print("\nAvailable genre presets:")
    for genre_name, preset in GENRE_DYNAMICS.items():
        print(f"  {genre_name:12s}: base_vel={preset.base_velocity:3d}, "
              f"range={preset.velocity_range}, shape={preset.phrase_shape.value}, "
              f"accent={preset.accent_strength:.2f}")
    
    print("\n✅ Dynamics engine test complete!")
