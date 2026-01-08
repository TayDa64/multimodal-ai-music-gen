"""
Section Variation Engine - Create meaningful variations for repeated sections.

Ensures verse 2 differs from verse 1, chorus 2 builds on chorus 1, etc.
while maintaining thematic coherence and recognizability.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set
from enum import Enum
import random


class VariationType(Enum):
    """Types of variations that can be applied."""
    NONE = "none"                      # No variation
    OCTAVE_SHIFT = "octave_shift"      # Shift some parts up/down octave
    DENSITY_CHANGE = "density_change"  # Add or remove notes
    RHYTHM_VARIATION = "rhythm_variation"  # Modify rhythmic patterns
    FILL_ADDITION = "fill_addition"    # Add fills/embellishments
    INSTRUMENT_SWAP = "instrument_swap"  # Change instrumentation
    HARMONY_ENRICHMENT = "harmony_enrichment"  # Add harmony notes
    DYNAMICS_SHIFT = "dynamics_shift"  # Change velocity profile
    REGISTER_SHIFT = "register_shift"  # Move to different octave range
    ARTICULATION_CHANGE = "articulation_change"  # Change note lengths
    MOTIF_TRANSFORM = "motif_transform"  # Apply motif transformation


@dataclass
class VariationConfig:
    """Configuration for section variation."""
    intensity: float = 0.5           # How different (0=identical, 1=very different)
    preserve_melody: bool = True     # Keep main melody recognizable
    preserve_harmony: bool = True    # Keep chord progression
    preserve_rhythm: bool = False    # Keep rhythmic pattern (looser default)
    
    # Which variation types to use
    allowed_types: Set[VariationType] = field(default_factory=lambda: {
        VariationType.DENSITY_CHANGE,
        VariationType.FILL_ADDITION,
        VariationType.DYNAMICS_SHIFT,
        VariationType.RHYTHM_VARIATION,
    })
    
    # Probability weights for each variation type
    type_weights: Dict[VariationType, float] = field(default_factory=dict)


@dataclass
class SectionVariation:
    """A specific variation applied to a section."""
    variation_type: VariationType
    parameters: Dict = field(default_factory=dict)
    description: str = ""


class SectionVariationEngine:
    """
    Generate variations for repeated sections.
    
    Usage:
        engine = SectionVariationEngine()
        
        # Get variation for second verse
        varied_notes = engine.create_variation(
            original_notes,
            section_type="verse",
            occurrence=2,  # This is the 2nd verse
            config=config
        )
    """
    
    def __init__(self, ticks_per_beat: int = 480, seed: Optional[int] = None):
        self.ticks_per_beat = ticks_per_beat
        self.rng = random.Random(seed)
    
    def create_variation(
        self,
        notes: List[Tuple[int, int, int, int]],
        section_type: str,
        occurrence: int,
        config: Optional[VariationConfig] = None
    ) -> Tuple[List[Tuple[int, int, int, int]], List[SectionVariation]]:
        """
        Create a variation of a section.
        
        Args:
            notes: Original notes (tick, duration, pitch, velocity)
            section_type: Type of section (verse, chorus, etc.)
            occurrence: Which occurrence (1, 2, 3...)
            config: Variation configuration
            
        Returns:
            (varied_notes, list of variations applied)
        """
        if config is None:
            config = VariationConfig()
        
        # First occurrence gets no variation
        if occurrence <= 1:
            return notes.copy(), []
        
        # Get variation plan
        variation_types = self.get_variation_plan(section_type, occurrence, config)
        
        # Apply variations
        varied_notes = notes.copy()
        applied_variations = []
        
        for var_type in variation_types:
            if var_type == VariationType.NONE:
                continue
            elif var_type == VariationType.OCTAVE_SHIFT:
                shift = 12 if self.rng.random() > 0.5 else -12
                probability = config.intensity * 0.3
                varied_notes = self.apply_octave_shift(varied_notes, shift, probability)
                applied_variations.append(SectionVariation(
                    var_type,
                    {"shift": shift, "probability": probability},
                    f"Octave shift {'+' if shift > 0 else ''}{shift//12}"
                ))
            elif var_type == VariationType.DENSITY_CHANGE:
                # Scale change with intensity
                change = (config.intensity - 0.5) * 0.4  # -0.2 to +0.2
                varied_notes = self.apply_density_change(varied_notes, change)
                applied_variations.append(SectionVariation(
                    var_type,
                    {"change": change},
                    f"Density change {'+' if change > 0 else ''}{change:.1%}"
                ))
            elif var_type == VariationType.RHYTHM_VARIATION:
                intensity = config.intensity * 0.5
                varied_notes = self.apply_rhythm_variation(varied_notes, intensity)
                applied_variations.append(SectionVariation(
                    var_type,
                    {"intensity": intensity},
                    f"Rhythm variation (intensity {intensity:.2f})"
                ))
            elif var_type == VariationType.FILL_ADDITION:
                # Calculate section end tick
                section_end_tick = max(n[0] + n[1] for n in varied_notes) if varied_notes else 0
                fill_density = config.intensity * 0.3
                varied_notes = self.apply_fill_addition(varied_notes, fill_density, section_end_tick)
                applied_variations.append(SectionVariation(
                    var_type,
                    {"fill_density": fill_density},
                    f"Fill addition (density {fill_density:.2f})"
                ))
            elif var_type == VariationType.HARMONY_ENRICHMENT:
                probability = config.intensity * 0.4
                varied_notes = self.apply_harmony_enrichment(varied_notes, probability)
                applied_variations.append(SectionVariation(
                    var_type,
                    {"harmony_probability": probability},
                    f"Harmony enrichment (prob {probability:.2f})"
                ))
            elif var_type == VariationType.DYNAMICS_SHIFT:
                velocity_delta = int(config.intensity * 15)
                direction = "up" if occurrence % 2 == 0 else "crescendo"
                varied_notes = self.apply_dynamics_shift(varied_notes, velocity_delta, direction)
                applied_variations.append(SectionVariation(
                    var_type,
                    {"velocity_delta": velocity_delta, "direction": direction},
                    f"Dynamics {direction} (±{velocity_delta})"
                ))
            elif var_type == VariationType.REGISTER_SHIFT:
                octaves = 1 if occurrence % 2 == 0 else -1
                direction = "up" if octaves > 0 else "down"
                varied_notes = self.apply_register_shift(varied_notes, octaves, direction)
                applied_variations.append(SectionVariation(
                    var_type,
                    {"octaves": octaves, "direction": direction},
                    f"Register shift {direction} {abs(octaves)} octave(s)"
                ))
            elif var_type == VariationType.ARTICULATION_CHANGE:
                # Alternate between staccato and legato
                length_factor = 0.7 if occurrence % 2 == 0 else 1.2
                varied_notes = self.apply_articulation_change(varied_notes, length_factor)
                applied_variations.append(SectionVariation(
                    var_type,
                    {"length_factor": length_factor},
                    f"Articulation {'staccato' if length_factor < 1 else 'legato'}"
                ))
        
        return varied_notes, applied_variations
    
    def get_variation_plan(
        self,
        section_type: str,
        occurrence: int,
        config: VariationConfig
    ) -> List[VariationType]:
        """
        Plan which variations to apply based on section type and occurrence.
        
        Later occurrences get more variation.
        Choruses vary less than verses (need to stay recognizable).
        """
        if occurrence <= 1:
            return [VariationType.NONE]
        
        # Get section-specific strategy
        section_key = section_type.lower()
        strategy = SECTION_VARIATION_STRATEGIES.get(section_key, {})
        preferred_types = strategy.get("preferred_types", [
            VariationType.DENSITY_CHANGE,
            VariationType.DYNAMICS_SHIFT,
        ])
        max_intensity = strategy.get("max_intensity", 0.5)
        
        # Calculate effective intensity (increases with occurrence)
        occurrence_multiplier = min(1.0, 0.5 + (occurrence - 2) * 0.25)
        effective_intensity = min(config.intensity * occurrence_multiplier, max_intensity)
        
        # Filter preferred types by allowed types
        available_types = [t for t in preferred_types if t in config.allowed_types]
        
        if not available_types:
            available_types = list(config.allowed_types)
        
        # Determine how many variations to apply based on intensity
        num_variations = 1 + int(effective_intensity * 2)  # 1-3 variations
        num_variations = min(num_variations, len(available_types))
        
        # Select variations with weighted randomness
        selected = []
        for _ in range(num_variations):
            # Weight by config weights if available
            weights = []
            for vtype in available_types:
                if vtype in selected:
                    weights.append(0)  # Don't select twice
                else:
                    weights.append(config.type_weights.get(vtype, 1.0))
            
            if sum(weights) == 0:
                break
            
            # Weighted choice
            total_weight = sum(weights)
            r = self.rng.random() * total_weight
            cumulative = 0
            for i, weight in enumerate(weights):
                cumulative += weight
                if r <= cumulative:
                    selected.append(available_types[i])
                    break
        
        return selected if selected else [VariationType.NONE]
    
    def apply_octave_shift(
        self,
        notes: List[Tuple[int, int, int, int]],
        shift: int = 12,
        probability: float = 0.3
    ) -> List[Tuple[int, int, int, int]]:
        """Shift some notes up or down by octave."""
        result = []
        for tick, duration, pitch, velocity in notes:
            if self.rng.random() < probability:
                new_pitch = pitch + shift
                # Clamp to MIDI range
                new_pitch = max(0, min(127, new_pitch))
                result.append((tick, duration, new_pitch, velocity))
            else:
                result.append((tick, duration, pitch, velocity))
        return result
    
    def apply_density_change(
        self,
        notes: List[Tuple[int, int, int, int]],
        change: float = 0.2  # Positive=add, negative=remove
    ) -> List[Tuple[int, int, int, int]]:
        """Add or remove notes to change density."""
        if not notes:
            return notes
        
        if change < 0:
            # Remove notes randomly
            removal_prob = abs(change)
            result = [
                note for note in notes
                if self.rng.random() > removal_prob
            ]
            # Ensure at least one note remains
            return result if result else [notes[0]]
        else:
            # Add notes by duplicating with slight variation
            result = notes.copy()
            num_to_add = int(len(notes) * change)
            
            for _ in range(num_to_add):
                if not result:
                    break
                # Pick a random note to duplicate
                original = self.rng.choice(result)
                tick, duration, pitch, velocity = original
                
                # Add slight timing variation
                tick_offset = self.rng.randint(-self.ticks_per_beat // 8, self.ticks_per_beat // 8)
                new_tick = max(0, tick + tick_offset)
                
                # Add slight pitch variation (neighbor tone)
                pitch_offset = self.rng.choice([-2, -1, 0, 1, 2])
                new_pitch = max(0, min(127, pitch + pitch_offset))
                
                result.append((new_tick, duration, new_pitch, velocity))
            
            # Sort by tick
            result.sort(key=lambda x: x[0])
            return result
    
    def apply_rhythm_variation(
        self,
        notes: List[Tuple[int, int, int, int]],
        intensity: float = 0.3
    ) -> List[Tuple[int, int, int, int]]:
        """Apply subtle rhythmic variations (anticipations, delays)."""
        if not notes:
            return notes
        
        result = []
        max_shift = int(self.ticks_per_beat * 0.25 * intensity)  # Max shift in ticks
        
        for tick, duration, pitch, velocity in notes:
            if self.rng.random() < intensity:
                # Apply anticipation or delay
                shift = self.rng.randint(-max_shift, max_shift)
                new_tick = max(0, tick + shift)
                result.append((new_tick, duration, pitch, velocity))
            else:
                result.append((tick, duration, pitch, velocity))
        
        # Sort by tick
        result.sort(key=lambda x: x[0])
        return result
    
    def apply_fill_addition(
        self,
        notes: List[Tuple[int, int, int, int]],
        fill_density: float = 0.2,
        section_end_tick: int = None
    ) -> List[Tuple[int, int, int, int]]:
        """Add fills and embellishments, especially at phrase ends."""
        if not notes:
            return notes
        
        result = notes.copy()
        
        # Determine section length
        if section_end_tick is None:
            section_end_tick = max(n[0] + n[1] for n in notes)
        
        # Add fills in last 25% of section
        fill_start_tick = int(section_end_tick * 0.75)
        
        # Find notes in fill zone
        notes_in_zone = [n for n in notes if n[0] >= fill_start_tick]
        
        if not notes_in_zone:
            return result
        
        # Calculate number of fill notes to add
        num_fills = max(1, int(len(notes_in_zone) * fill_density * 2))
        
        for _ in range(num_fills):
            # Pick a reference note
            ref_note = self.rng.choice(notes_in_zone)
            tick, duration, pitch, velocity = ref_note
            
            # Create fill note - shorter duration, nearby pitch
            fill_duration = duration // 2
            fill_pitch = pitch + self.rng.choice([-2, -1, 1, 2])
            fill_pitch = max(0, min(127, fill_pitch))
            fill_velocity = max(1, velocity - 10)  # Slightly quieter
            
            # Place between existing notes
            fill_tick = tick + (duration // 2)
            
            result.append((fill_tick, fill_duration, fill_pitch, fill_velocity))
        
        # Sort by tick
        result.sort(key=lambda x: x[0])
        return result
    
    def apply_harmony_enrichment(
        self,
        notes: List[Tuple[int, int, int, int]],
        harmony_probability: float = 0.3,
        intervals: List[int] = None  # Default: [3, 4, 7] (thirds, fourths, fifths)
    ) -> List[Tuple[int, int, int, int]]:
        """Add harmony notes (parallel thirds, sixths, etc.)."""
        if not notes:
            return notes
        
        if intervals is None:
            intervals = [3, 4, 7]  # thirds, fourths, fifths
        
        result = notes.copy()
        
        for tick, duration, pitch, velocity in notes:
            if self.rng.random() < harmony_probability:
                # Add a harmony note
                interval = self.rng.choice(intervals)
                # Randomly choose above or below
                harmony_pitch = pitch + (interval if self.rng.random() > 0.5 else -interval)
                harmony_pitch = max(0, min(127, harmony_pitch))
                
                # Harmony note slightly quieter
                harmony_velocity = max(1, velocity - 10)
                
                result.append((tick, duration, harmony_pitch, harmony_velocity))
        
        # Sort by tick
        result.sort(key=lambda x: x[0])
        return result
    
    def apply_dynamics_shift(
        self,
        notes: List[Tuple[int, int, int, int]],
        velocity_delta: int = 10,
        direction: str = "up"  # "up", "down", "crescendo", "decrescendo"
    ) -> List[Tuple[int, int, int, int]]:
        """Shift overall dynamics."""
        if not notes:
            return notes
        
        result = []
        
        for i, (tick, duration, pitch, velocity) in enumerate(notes):
            if direction == "up":
                new_velocity = velocity + velocity_delta
            elif direction == "down":
                new_velocity = velocity - velocity_delta
            elif direction == "crescendo":
                # Gradual increase
                progress = i / (len(notes) - 1) if len(notes) > 1 else 0
                new_velocity = velocity + int(velocity_delta * progress)
            elif direction == "decrescendo":
                # Gradual decrease
                progress = i / (len(notes) - 1) if len(notes) > 1 else 0
                new_velocity = velocity - int(velocity_delta * progress)
            else:
                new_velocity = velocity
            
            # Clamp to MIDI range
            new_velocity = max(1, min(127, new_velocity))
            result.append((tick, duration, pitch, new_velocity))
        
        return result
    
    def apply_register_shift(
        self,
        notes: List[Tuple[int, int, int, int]],
        octaves: int = 1,
        direction: str = "up"
    ) -> List[Tuple[int, int, int, int]]:
        """Shift entire section to different register."""
        if not notes:
            return notes
        
        shift = octaves * 12 * (1 if direction == "up" else -1)
        
        result = []
        for tick, duration, pitch, velocity in notes:
            new_pitch = pitch + shift
            # Clamp to MIDI range
            new_pitch = max(0, min(127, new_pitch))
            result.append((tick, duration, new_pitch, velocity))
        
        return result
    
    def apply_articulation_change(
        self,
        notes: List[Tuple[int, int, int, int]],
        length_factor: float = 0.8  # <1 = more staccato, >1 = more legato
    ) -> List[Tuple[int, int, int, int]]:
        """Change note durations (staccato/legato)."""
        if not notes:
            return notes
        
        result = []
        for tick, duration, pitch, velocity in notes:
            new_duration = int(duration * length_factor)
            # Ensure minimum duration
            new_duration = max(1, new_duration)
            result.append((tick, new_duration, pitch, velocity))
        
        return result
    
    def suggest_variations_for_structure(
        self,
        section_types: List[str]
    ) -> Dict[int, List[VariationType]]:
        """
        Suggest variations for an entire arrangement structure.
        
        Returns dict mapping section index to suggested variations.
        First occurrence of each type gets no variation.
        """
        # Track occurrences of each section type
        occurrences = {}
        suggestions = {}
        
        for i, section_type in enumerate(section_types):
            section_key = section_type.lower()
            
            if section_key not in occurrences:
                occurrences[section_key] = 0
            occurrences[section_key] += 1
            
            occurrence = occurrences[section_key]
            
            # Get variation plan
            config = VariationConfig()
            variations = self.get_variation_plan(section_key, occurrence, config)
            suggestions[i] = variations
        
        return suggestions
    
    def get_section_variation_preset(
        self,
        section_type: str,
        genre: str
    ) -> VariationConfig:
        """Get genre-appropriate variation config for section type."""
        # Get section strategy
        section_key = section_type.lower()
        strategy = SECTION_VARIATION_STRATEGIES.get(section_key, {})
        
        # Get genre profile
        genre_key = genre.lower()
        genre_profile = GENRE_VARIATION_PROFILES.get(genre_key, {})
        
        # Base intensity from section
        max_intensity = strategy.get("max_intensity", 0.5)
        
        # Apply genre multiplier
        intensity_mult = genre_profile.get("intensity_multiplier", 1.0)
        intensity = max_intensity * intensity_mult
        
        # Build config
        config = VariationConfig(
            intensity=intensity,
            preserve_melody=strategy.get("preserve_melody", True),
            preserve_harmony=strategy.get("preserve_harmony", True),
            preserve_rhythm=strategy.get("preserve_rhythm", False),
            allowed_types=set(strategy.get("preferred_types", [
                VariationType.DENSITY_CHANGE,
                VariationType.DYNAMICS_SHIFT,
            ]))
        )
        
        # Apply genre-specific weights
        weights = {}
        for var_type in config.allowed_types:
            weight_key = f"{var_type.value}_weight"
            weights[var_type] = genre_profile.get(weight_key, 1.0)
        config.type_weights = weights
        
        return config


# Section-specific variation strategies
SECTION_VARIATION_STRATEGIES: Dict[str, Dict[str, any]] = {
    "verse": {
        "max_intensity": 0.4,  # Verses can vary moderately
        "preferred_types": [
            VariationType.DENSITY_CHANGE,
            VariationType.DYNAMICS_SHIFT,
            VariationType.FILL_ADDITION,
        ],
        "preserve_melody": True,
    },
    "chorus": {
        "max_intensity": 0.2,  # Choruses should stay recognizable
        "preferred_types": [
            VariationType.DYNAMICS_SHIFT,
            VariationType.HARMONY_ENRICHMENT,
        ],
        "preserve_melody": True,
        "preserve_rhythm": True,
    },
    "bridge": {
        "max_intensity": 0.5,  # Bridges can be more varied
        "preferred_types": [
            VariationType.REGISTER_SHIFT,
            VariationType.DENSITY_CHANGE,
            VariationType.ARTICULATION_CHANGE,
        ],
    },
    "hook": {
        "max_intensity": 0.15,  # Hooks must be very consistent
        "preferred_types": [
            VariationType.DYNAMICS_SHIFT,
        ],
        "preserve_melody": True,
        "preserve_rhythm": True,
    },
}


# Genre-specific variation preferences
GENRE_VARIATION_PROFILES: Dict[str, Dict[str, float]] = {
    "pop": {
        "intensity_multiplier": 0.8,  # Pop is more consistent
        "harmony_enrichment_weight": 1.5,
    },
    "jazz": {
        "intensity_multiplier": 1.3,  # Jazz varies more
        "rhythm_variation_weight": 1.5,
        "fill_addition_weight": 1.3,
    },
    "classical": {
        "intensity_multiplier": 1.0,
        "motif_transform_weight": 1.5,
        "register_shift_weight": 1.2,
    },
    "hip_hop": {
        "intensity_multiplier": 0.7,
        "density_change_weight": 1.3,
    },
    "edm": {
        "intensity_multiplier": 0.6,  # EDM is very consistent in loops
        "fill_addition_weight": 1.5,  # But adds builds/fills
    },
}


# Convenience functions
def create_section_variation(
    notes: List[Tuple[int, int, int, int]],
    section_type: str,
    occurrence: int,
    genre: str = "pop",
    seed: Optional[int] = None
) -> List[Tuple[int, int, int, int]]:
    """
    Quick variation creation with genre preset.
    
    Args:
        notes: Original section notes
        section_type: Type of section
        occurrence: Which occurrence (2nd, 3rd, etc.)
        genre: Genre for variation style
        seed: Random seed
        
    Returns:
        Varied notes
    """
    engine = SectionVariationEngine(seed=seed)
    config = engine.get_section_variation_preset(section_type, genre)
    varied_notes, _ = engine.create_variation(notes, section_type, occurrence, config)
    return varied_notes


def vary_arrangement_sections(
    arrangement_notes: Dict[str, List[Tuple[int, int, int, int]]],
    section_order: List[str],
    genre: str = "pop"
) -> Dict[str, List[Tuple[int, int, int, int]]]:
    """
    Apply variations to all repeated sections in an arrangement.
    
    Args:
        arrangement_notes: Dict mapping section name to notes
        section_order: Order of sections (e.g., ["verse_1", "chorus_1", "verse_2", "chorus_2"])
        genre: Genre for variation style
        
    Returns:
        Dict with varied notes for repeated sections
    """
    engine = SectionVariationEngine()
    result = {}
    
    # Track section type occurrences
    occurrences = {}
    
    for section_name in section_order:
        # Extract section type (e.g., "verse" from "verse_1")
        section_type = section_name.rsplit('_', 1)[0] if '_' in section_name else section_name
        
        # Track occurrence
        if section_type not in occurrences:
            occurrences[section_type] = 0
        occurrences[section_type] += 1
        
        occurrence = occurrences[section_type]
        
        # Get original notes
        if section_name not in arrangement_notes:
            continue
        
        original_notes = arrangement_notes[section_name]
        
        # Get variation config
        config = engine.get_section_variation_preset(section_type, genre)
        
        # Create variation
        varied_notes, _ = engine.create_variation(original_notes, section_type, occurrence, config)
        
        result[section_name] = varied_notes
    
    return result
