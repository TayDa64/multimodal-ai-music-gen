"""
Tension/Release Arc System - Emotional narrative through musical parameters.

Creates tension curves that modulate dynamics, note density, harmonic complexity,
and other parameters to build emotional arcs across arrangements.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Callable
from enum import Enum
import numpy as np


class ArcShape(Enum):
    """Predefined tension arc shapes."""
    FLAT = "flat"                    # No tension variation
    LINEAR_BUILD = "linear_build"    # Steady increase
    LINEAR_DECAY = "linear_decay"    # Steady decrease
    PEAK_MIDDLE = "peak_middle"      # Build to middle, release
    PEAK_END = "peak_end"            # Build throughout to climax
    DOUBLE_PEAK = "double_peak"      # Two climaxes
    WAVE = "wave"                    # Oscillating tension
    STEP_UP = "step_up"              # Stepwise increases
    STEP_DOWN = "step_down"          # Stepwise decreases
    DRAMATIC = "dramatic"            # Low-high-low with sharp transitions


@dataclass
class TensionPoint:
    """A tension value at a specific position."""
    position: float      # 0.0 to 1.0 (normalized position in arrangement)
    tension: float       # 0.0 (minimal) to 1.0 (maximum tension)
    label: str = ""      # Optional label (e.g., "climax", "breakdown")


@dataclass
class TensionConfig:
    """Configuration for tension arc processing."""
    base_tension: float = 0.5           # Starting tension level
    tension_range: Tuple[float, float] = (0.2, 1.0)  # Min/max tension
    
    # How tension affects different parameters (0 = no effect, 1 = full effect)
    dynamics_influence: float = 0.7      # Affect velocity/loudness
    density_influence: float = 0.6       # Affect note density
    complexity_influence: float = 0.5    # Affect harmonic complexity
    register_influence: float = 0.4      # Affect pitch range
    articulation_influence: float = 0.3  # Affect note lengths


@dataclass
class TensionArc:
    """A complete tension arc for an arrangement."""
    points: List[TensionPoint] = field(default_factory=list)
    shape: ArcShape = ArcShape.PEAK_MIDDLE
    config: TensionConfig = field(default_factory=TensionConfig)
    
    def get_tension_at(self, position: float) -> float:
        """Get interpolated tension value at normalized position (0-1)."""
        if not self.points:
            return self.config.base_tension
        
        # Clamp position to valid range
        position = max(0.0, min(1.0, position))
        
        # Find surrounding points for interpolation
        if position <= self.points[0].position:
            return self.points[0].tension
        
        if position >= self.points[-1].position:
            return self.points[-1].tension
        
        # Linear interpolation between points
        for i in range(len(self.points) - 1):
            p1, p2 = self.points[i], self.points[i + 1]
            if p1.position <= position <= p2.position:
                # Interpolate
                t = (position - p1.position) / (p2.position - p1.position)
                return p1.tension + t * (p2.tension - p1.tension)
        
        return self.config.base_tension
    
    def to_curve(self, num_points: int = 100) -> np.ndarray:
        """Convert to dense curve array for visualization/processing."""
        positions = np.linspace(0.0, 1.0, num_points)
        return np.array([self.get_tension_at(pos) for pos in positions])


class TensionArcGenerator:
    """
    Generate and apply tension arcs to arrangements.
    
    Usage:
        generator = TensionArcGenerator()
        arc = generator.create_arc(ArcShape.PEAK_END, num_sections=8)
        
        # Apply to arrangement parameters
        dynamics_curve = generator.get_dynamics_curve(arc)
        density_curve = generator.get_density_curve(arc)
    """
    
    def __init__(self):
        self._shape_functions: Dict[ArcShape, Callable] = self._build_shape_functions()
    
    def _build_shape_functions(self) -> Dict[ArcShape, Callable]:
        """Build mapping of arc shapes to generator functions."""
        return {
            ArcShape.FLAT: self._generate_flat,
            ArcShape.LINEAR_BUILD: self._generate_linear_build,
            ArcShape.LINEAR_DECAY: self._generate_linear_decay,
            ArcShape.PEAK_MIDDLE: self._generate_peak_middle,
            ArcShape.PEAK_END: self._generate_peak_end,
            ArcShape.DOUBLE_PEAK: self._generate_double_peak,
            ArcShape.WAVE: self._generate_wave,
            ArcShape.STEP_UP: self._generate_step_up,
            ArcShape.STEP_DOWN: self._generate_step_down,
            ArcShape.DRAMATIC: self._generate_dramatic,
        }
    
    def _generate_flat(self, num_sections: int, config: TensionConfig) -> List[TensionPoint]:
        """Generate flat tension arc."""
        return [
            TensionPoint(i / max(1, num_sections - 1), config.base_tension)
            for i in range(num_sections)
        ]
    
    def _generate_linear_build(self, num_sections: int, config: TensionConfig) -> List[TensionPoint]:
        """Generate linear build tension arc."""
        min_tension, max_tension = config.tension_range
        return [
            TensionPoint(
                i / max(1, num_sections - 1),
                min_tension + (max_tension - min_tension) * (i / max(1, num_sections - 1))
            )
            for i in range(num_sections)
        ]
    
    def _generate_linear_decay(self, num_sections: int, config: TensionConfig) -> List[TensionPoint]:
        """Generate linear decay tension arc."""
        min_tension, max_tension = config.tension_range
        return [
            TensionPoint(
                i / max(1, num_sections - 1),
                max_tension - (max_tension - min_tension) * (i / max(1, num_sections - 1))
            )
            for i in range(num_sections)
        ]
    
    def _generate_peak_middle(self, num_sections: int, config: TensionConfig) -> List[TensionPoint]:
        """Generate peak in middle tension arc."""
        min_tension, max_tension = config.tension_range
        points = []
        for i in range(num_sections):
            pos = i / max(1, num_sections - 1)
            # Use sine curve for smooth build and release
            tension = min_tension + (max_tension - min_tension) * np.sin(pos * np.pi)
            points.append(TensionPoint(pos, tension))
        return points
    
    def _generate_peak_end(self, num_sections: int, config: TensionConfig) -> List[TensionPoint]:
        """Generate peak at end tension arc."""
        min_tension, max_tension = config.tension_range
        points = []
        for i in range(num_sections):
            pos = i / max(1, num_sections - 1)
            # Use power curve for gradual then steep build
            tension = min_tension + (max_tension - min_tension) * (pos ** 1.5)
            points.append(TensionPoint(pos, tension))
        return points
    
    def _generate_double_peak(self, num_sections: int, config: TensionConfig) -> List[TensionPoint]:
        """Generate double peak tension arc."""
        min_tension, max_tension = config.tension_range
        mid_tension = (min_tension + max_tension) / 2
        amplitude = (max_tension - min_tension) / 2
        points = []
        for i in range(num_sections):
            pos = i / max(1, num_sections - 1)
            # Two sine waves (abs to keep positive, creating two peaks)
            tension = mid_tension + amplitude * abs(np.sin(pos * 2 * np.pi))
            points.append(TensionPoint(pos, tension))
        return points
    
    def _generate_wave(self, num_sections: int, config: TensionConfig) -> List[TensionPoint]:
        """Generate wave tension arc."""
        min_tension, max_tension = config.tension_range
        mid_tension = (min_tension + max_tension) / 2
        amplitude = (max_tension - min_tension) / 2
        points = []
        for i in range(num_sections):
            pos = i / max(1, num_sections - 1)
            # Continuous wave
            tension = mid_tension + amplitude * np.sin(pos * 3 * np.pi)
            points.append(TensionPoint(pos, tension))
        return points
    
    def _generate_step_up(self, num_sections: int, config: TensionConfig) -> List[TensionPoint]:
        """Generate stepwise increase tension arc."""
        min_tension, max_tension = config.tension_range
        step_size = (max_tension - min_tension) / max(1, num_sections - 1)
        return [
            TensionPoint(i / max(1, num_sections - 1), min_tension + i * step_size)
            for i in range(num_sections)
        ]
    
    def _generate_step_down(self, num_sections: int, config: TensionConfig) -> List[TensionPoint]:
        """Generate stepwise decrease tension arc."""
        min_tension, max_tension = config.tension_range
        step_size = (max_tension - min_tension) / max(1, num_sections - 1)
        return [
            TensionPoint(i / max(1, num_sections - 1), max_tension - i * step_size)
            for i in range(num_sections)
        ]
    
    def _generate_dramatic(self, num_sections: int, config: TensionConfig) -> List[TensionPoint]:
        """Generate dramatic low-high-low tension arc."""
        min_tension, max_tension = config.tension_range
        points = []
        for i in range(num_sections):
            pos = i / max(1, num_sections - 1)
            if pos < 0.25:
                # Low tension
                tension = min_tension
            elif pos < 0.5:
                # Sharp rise to high
                t = (pos - 0.25) / 0.25
                tension = min_tension + (max_tension - min_tension) * t
            elif pos < 0.75:
                # High tension
                tension = max_tension
            else:
                # Sharp drop to low
                t = (pos - 0.75) / 0.25
                tension = max_tension - (max_tension - min_tension) * t
            points.append(TensionPoint(pos, tension))
        return points
    
    def create_arc(
        self,
        shape: ArcShape,
        num_sections: int = 8,
        config: Optional[TensionConfig] = None
    ) -> TensionArc:
        """
        Create a tension arc with the specified shape.
        
        Args:
            shape: Arc shape type
            num_sections: Number of sections in arrangement
            config: Optional configuration override
            
        Returns:
            TensionArc with generated points
        """
        if config is None:
            config = TensionConfig()
        
        generator_func = self._shape_functions.get(shape)
        if generator_func is None:
            raise ValueError(f"Unknown arc shape: {shape}")
        
        points = generator_func(num_sections, config)
        return TensionArc(points=points, shape=shape, config=config)
    
    def create_custom_arc(
        self,
        tension_values: List[float],
        config: Optional[TensionConfig] = None
    ) -> TensionArc:
        """
        Create arc from explicit tension values per section.
        
        Args:
            tension_values: List of tension values (0-1) for each section
            config: Optional configuration
            
        Returns:
            Custom TensionArc
        """
        if config is None:
            config = TensionConfig()
        
        num_sections = len(tension_values)
        points = [
            TensionPoint(i / max(1, num_sections - 1), tension_values[i])
            for i in range(num_sections)
        ]
        
        return TensionArc(points=points, shape=ArcShape.FLAT, config=config)
    
    def create_arc_for_sections(
        self,
        section_types: List[str],
        genre: str = "pop"
    ) -> TensionArc:
        """
        Create tension arc based on section types.
        
        Maps section types to typical tension levels:
        - intro: 0.3
        - verse: 0.5
        - pre_chorus: 0.7
        - chorus: 0.9
        - bridge: 0.6
        - breakdown: 0.2
        - drop: 1.0
        - outro: 0.3
        
        Args:
            section_types: List of section type names
            genre: Genre for style-specific adjustments
            
        Returns:
            TensionArc matched to section structure
        """
        # Get genre-specific profile if available
        genre_profile = GENRE_TENSION_PROFILES.get(genre.lower(), {})
        
        points = []
        for i, section_type in enumerate(section_types):
            pos = i / max(1, len(section_types) - 1)
            
            # Normalize section type
            section_key = section_type.lower().replace(" ", "_")
            
            # Try genre-specific first, then fall back to default
            if section_key in genre_profile:
                tension = genre_profile[section_key]
            elif section_key in SECTION_TENSION_MAP:
                tension = SECTION_TENSION_MAP[section_key]
            else:
                tension = 0.5  # Default medium tension
            
            points.append(TensionPoint(pos, tension, section_type))
        
        return TensionArc(points=points, shape=ArcShape.FLAT, config=TensionConfig())
    
    def get_tension_at_position(
        self,
        arc: TensionArc,
        position: float
    ) -> float:
        """Get interpolated tension at normalized position."""
        return arc.get_tension_at(position)
    
    def get_dynamics_curve(
        self,
        arc: TensionArc,
        num_points: int = 100
    ) -> np.ndarray:
        """
        Get dynamics (velocity) curve from tension arc.
        
        Maps tension to velocity range based on config.dynamics_influence.
        """
        curve = arc.to_curve(num_points)
        
        # Base velocity range (40-120)
        base_min, base_max = 40, 120
        base_range = base_max - base_min
        
        # Apply influence factor
        influenced_curve = base_min + curve * base_range * arc.config.dynamics_influence
        
        # Add back some of the non-influenced range
        non_influenced = base_min + (base_max - base_min) * 0.5
        influenced_curve += non_influenced * (1 - arc.config.dynamics_influence)
        
        return np.clip(influenced_curve, base_min, base_max)
    
    def get_density_curve(
        self,
        arc: TensionArc,
        num_points: int = 100
    ) -> np.ndarray:
        """
        Get note density curve from tension arc.
        
        Higher tension = more notes per bar.
        """
        curve = arc.to_curve(num_points)
        
        # Base density range (0.2 to 1.0, where 1.0 is maximum density)
        base_min, base_max = 0.2, 1.0
        base_range = base_max - base_min
        
        # Apply influence factor
        influenced_curve = base_min + curve * base_range * arc.config.density_influence
        
        # Add back baseline
        non_influenced = base_min + (base_max - base_min) * 0.5
        influenced_curve += non_influenced * (1 - arc.config.density_influence)
        
        return np.clip(influenced_curve, base_min, base_max)
    
    def get_complexity_curve(
        self,
        arc: TensionArc,
        num_points: int = 100
    ) -> np.ndarray:
        """
        Get harmonic complexity curve.
        
        Higher tension = more complex chords, extensions, alterations.
        """
        curve = arc.to_curve(num_points)
        
        # Complexity range (0.0 to 1.0)
        base_min, base_max = 0.0, 1.0
        base_range = base_max - base_min
        
        # Apply influence factor
        influenced_curve = base_min + curve * base_range * arc.config.complexity_influence
        
        # Add baseline
        non_influenced = base_min + (base_max - base_min) * 0.3
        influenced_curve += non_influenced * (1 - arc.config.complexity_influence)
        
        return np.clip(influenced_curve, base_min, base_max)
    
    def get_register_curve(
        self,
        arc: TensionArc,
        num_points: int = 100
    ) -> np.ndarray:
        """
        Get pitch register curve.
        
        Higher tension = wider pitch range, higher average pitch.
        """
        curve = arc.to_curve(num_points)
        
        # Register range (0.0 to 1.0, where 1.0 is highest/widest)
        base_min, base_max = 0.0, 1.0
        base_range = base_max - base_min
        
        # Apply influence factor
        influenced_curve = base_min + curve * base_range * arc.config.register_influence
        
        # Add baseline
        non_influenced = base_min + (base_max - base_min) * 0.5
        influenced_curve += non_influenced * (1 - arc.config.register_influence)
        
        return np.clip(influenced_curve, base_min, base_max)
    
    def apply_to_velocities(
        self,
        notes: List[Tuple[int, int, int, int]],
        arc: TensionArc,
        total_ticks: int
    ) -> List[Tuple[int, int, int, int]]:
        """
        Apply tension arc to note velocities.
        
        Args:
            notes: List of (tick, duration, pitch, velocity)
            arc: Tension arc to apply
            total_ticks: Total length in ticks
            
        Returns:
            Notes with adjusted velocities
        """
        if not notes or total_ticks <= 0:
            return notes
        
        result = []
        for tick, duration, pitch, velocity in notes:
            # Calculate normalized position
            position = tick / total_ticks
            position = max(0.0, min(1.0, position))
            
            # Get tension at this position
            tension = arc.get_tension_at(position)
            
            # Map tension to velocity multiplier
            # Low tension: 0.6x, high tension: 1.2x
            min_mult, max_mult = 0.6, 1.2
            influence = arc.config.dynamics_influence
            multiplier = 1.0 + (tension - 0.5) * (max_mult - 1.0) * influence * 2
            
            # Apply multiplier
            new_velocity = int(velocity * multiplier)
            new_velocity = max(1, min(127, new_velocity))
            
            result.append((tick, duration, pitch, new_velocity))
        
        return result
    
    def suggest_section_instruments(
        self,
        arc: TensionArc,
        section_index: int,
        available_instruments: List[str]
    ) -> List[str]:
        """
        Suggest instruments for a section based on tension level.
        
        Low tension: fewer instruments, softer sounds
        High tension: full ensemble, powerful sounds
        """
        if not available_instruments or section_index < 0 or section_index >= len(arc.points):
            return available_instruments
        
        tension = arc.points[section_index].tension
        
        # Determine how many instruments to use based on tension
        num_instruments = max(1, int(len(available_instruments) * tension))
        
        # Prioritize certain instruments based on tension
        # Low tension: prefer pads, ambient sounds
        # High tension: prefer drums, bass, leads
        
        # For now, just return proportional subset
        return available_instruments[:num_instruments]


# Section type to base tension mapping
SECTION_TENSION_MAP: Dict[str, float] = {
    "intro": 0.3,
    "verse": 0.5,
    "verse_1": 0.45,
    "verse_2": 0.55,
    "pre_chorus": 0.7,
    "chorus": 0.9,
    "chorus_1": 0.85,
    "chorus_2": 0.95,
    "hook": 0.85,
    "bridge": 0.6,
    "breakdown": 0.2,
    "build": 0.75,
    "drop": 1.0,
    "outro": 0.3,
    "solo": 0.7,
    "interlude": 0.4,
}


# Genre-specific tension profiles
GENRE_TENSION_PROFILES: Dict[str, Dict[str, float]] = {
    "edm": {
        "breakdown": 0.15,
        "build": 0.85,
        "drop": 1.0,
    },
    "classical": {
        "exposition": 0.5,
        "development": 0.8,
        "recapitulation": 0.7,
        "coda": 0.4,
    },
    "jazz": {
        "head": 0.6,
        "solo": 0.75,
        "trading": 0.7,
        "out_head": 0.65,
    },
    "pop": {
        "verse": 0.5,
        "pre_chorus": 0.75,
        "chorus": 0.9,
    },
    "hip_hop": {
        "verse": 0.6,
        "hook": 0.85,
        "bridge": 0.5,
    },
}


# Convenience functions
def create_tension_arc(
    shape: str = "peak_middle",
    num_sections: int = 8
) -> TensionArc:
    """Quick tension arc creation."""
    generator = TensionArcGenerator()
    arc_shape = ArcShape(shape)
    return generator.create_arc(arc_shape, num_sections)


def apply_tension_to_arrangement(
    notes: List[Tuple[int, int, int, int]],
    section_types: List[str],
    section_boundaries: List[int],
    genre: str = "pop"
) -> List[Tuple[int, int, int, int]]:
    """
    Apply tension-based dynamics to an arrangement.
    
    Args:
        notes: All notes in arrangement
        section_types: Type of each section
        section_boundaries: Tick position of each section start
        genre: Genre for tension profile
        
    Returns:
        Notes with tension-adjusted velocities
    """
    if not notes or not section_types:
        return notes
    
    # Create arc from section types
    generator = TensionArcGenerator()
    arc = generator.create_arc_for_sections(section_types, genre)
    
    # Determine total ticks
    if section_boundaries:
        total_ticks = max(note[0] for note in notes) if notes else section_boundaries[-1]
    else:
        total_ticks = max(note[0] for note in notes) if notes else 1
    
    # Apply to velocities
    return generator.apply_to_velocities(notes, arc, total_ticks)


def get_tension_for_section(
    section_type: str,
    genre: str = "pop"
) -> float:
    """Get appropriate tension level for a section type and genre."""
    # Get genre-specific profile if available
    genre_profile = GENRE_TENSION_PROFILES.get(genre.lower(), {})
    
    # Normalize section type
    section_key = section_type.lower().replace(" ", "_")
    
    # Try genre-specific first, then fall back to default
    if section_key in genre_profile:
        return genre_profile[section_key]
    elif section_key in SECTION_TENSION_MAP:
        return SECTION_TENSION_MAP[section_key]
    else:
        return 0.5  # Default medium tension
