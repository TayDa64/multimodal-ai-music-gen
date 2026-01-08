"""
Preset System - Curated configurations combining all musicality features.

DESIGN PRINCIPLE: Presets are starting points, not traps.
- All preset values are overridable
- Partial preset application supported
- Clear tracking of preset vs custom values
- Easy reset to defaults
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, Set, List
from enum import Enum
import json


class PresetCategory(Enum):
    """Categories of presets."""
    GENRE = "genre"           # Genre-specific full presets
    STYLE = "style"           # Style variations (chill, energetic, etc.)
    PRODUCTION = "production" # Production quality presets
    EXPERIMENTAL = "experimental"  # Creative/unusual combinations


@dataclass
class PresetValue:
    """
    A single preset value with provenance tracking.
    
    Tracks whether value is from preset or user-customized.
    """
    value: Any
    source: str = "default"  # "default", "preset:<name>", "user"
    locked: bool = False     # User explicitly set this, don't override
    
    def override(self, new_value: Any, source: str = "user") -> 'PresetValue':
        """Create new PresetValue with override."""
        return PresetValue(value=new_value, source=source, locked=(source == "user"))


@dataclass
class PresetConfig:
    """
    Complete preset configuration.
    
    Each field is Optional - None means "use default, don't override".
    This prevents trap defaults from persisting.
    """
    name: str
    category: PresetCategory
    description: str
    
    # Motif settings (None = don't override default)
    motif_density: Optional[float] = None
    motif_complexity: Optional[float] = None
    motif_variation_rate: Optional[float] = None
    
    # Timing/groove settings
    swing_amount: Optional[float] = None
    microtiming_intensity: Optional[float] = None
    groove_tightness: Optional[float] = None
    
    # Dynamics settings
    velocity_range: Optional[tuple] = None  # (min, max)
    dynamics_curve: Optional[str] = None
    accent_strength: Optional[float] = None
    
    # Humanization settings
    humanize_amount: Optional[float] = None
    ghost_note_probability: Optional[float] = None
    timing_variance: Optional[float] = None
    
    # Tension arc settings
    tension_arc_shape: Optional[str] = None
    tension_intensity: Optional[float] = None
    
    # Section variation settings
    variation_intensity: Optional[float] = None
    preserve_melody: Optional[bool] = None
    
    # Pattern preferences
    preferred_patterns: Optional[List[str]] = None
    pattern_intensity: Optional[str] = None
    
    # Tags for searchability
    tags: Set[str] = field(default_factory=set)
    
    def get_non_none_fields(self) -> Dict[str, Any]:
        """Get only the fields that are explicitly set (not None)."""
        result = {}
        for key, value in asdict(self).items():
            if key in ('name', 'category', 'description', 'tags'):
                continue  # Skip metadata fields
            if value is not None:
                result[key] = value
        return result
    
    def merge_with(self, other: 'PresetConfig') -> 'PresetConfig':
        """Merge with another preset, other takes precedence for non-None values."""
        merged_dict = asdict(self)
        
        # Update with non-None values from other
        for key, value in asdict(other).items():
            if key in ('name', 'category', 'description'):
                continue  # Keep original metadata
            if value is not None:
                merged_dict[key] = value
        
        # Merge tags
        merged_dict['tags'] = self.tags.union(other.tags)
        
        # Convert category back to enum if it became a string
        if isinstance(merged_dict['category'], str):
            merged_dict['category'] = PresetCategory(merged_dict['category'])
        
        return PresetConfig(**merged_dict)


class PresetManager:
    """
    Manages preset loading, application, and customization.
    
    Key principle: Transparency over magic.
    Users always know what values come from where.
    """
    
    def __init__(self):
        self.presets: Dict[str, PresetConfig] = {}
        self.current_values: Dict[str, PresetValue] = {}
        self.active_preset: Optional[str] = None
        self._load_builtin_presets()
    
    def _load_builtin_presets(self):
        """Load all built-in presets."""
        self._load_genre_presets()
        self._load_style_presets()
        self._load_production_presets()
    
    def _load_genre_presets(self):
        """Load genre-specific presets."""
        for name, preset in GENRE_PRESETS.items():
            self.presets[name] = preset
    
    def _load_style_presets(self):
        """Load style presets."""
        for name, preset in STYLE_PRESETS.items():
            self.presets[name] = preset
    
    def _load_production_presets(self):
        """Load production presets."""
        for name, preset in PRODUCTION_PRESETS.items():
            self.presets[name] = preset
    
    def apply_preset(
        self,
        preset_name: str,
        partial: bool = False,
        only_fields: Optional[Set[str]] = None,
        exclude_fields: Optional[Set[str]] = None
    ) -> Dict[str, PresetValue]:
        """
        Apply a preset.
        
        Args:
            preset_name: Name of preset to apply
            partial: If True, only apply non-None preset values
            only_fields: If provided, only apply these specific fields
            exclude_fields: If provided, skip these fields
            
        Returns:
            Dict of applied values with provenance
        """
        if preset_name not in self.presets:
            raise ValueError(f"Preset '{preset_name}' not found")
        
        preset = self.presets[preset_name]
        self.active_preset = preset_name
        
        # Get non-None fields from preset
        preset_fields = preset.get_non_none_fields()
        
        # Apply field filters
        if only_fields:
            preset_fields = {k: v for k, v in preset_fields.items() if k in only_fields}
        if exclude_fields:
            preset_fields = {k: v for k, v in preset_fields.items() if k not in exclude_fields}
        
        # Apply preset values (respecting locked user values)
        for field, value in preset_fields.items():
            # Don't override locked user values
            if field in self.current_values and self.current_values[field].locked:
                continue
            
            self.current_values[field] = PresetValue(
                value=value,
                source=f"preset:{preset_name}",
                locked=False
            )
        
        return self.current_values.copy()
    
    def override_value(self, field: str, value: Any) -> PresetValue:
        """
        Override a specific value (marks as user-set, won't be overwritten by preset).
        """
        preset_value = PresetValue(value=value, source="user", locked=True)
        self.current_values[field] = preset_value
        return preset_value
    
    def get_value(self, field: str, default: Any = None) -> Any:
        """Get current value for a field."""
        if field in self.current_values:
            return self.current_values[field].value
        return default
    
    def get_provenance(self, field: str) -> str:
        """Get where a value came from (default/preset/user)."""
        if field in self.current_values:
            return self.current_values[field].source
        return "default"
    
    def get_all_values(self) -> Dict[str, PresetValue]:
        """Get all current values with provenance."""
        return self.current_values.copy()
    
    def get_user_overrides(self) -> Dict[str, Any]:
        """Get only the values that user has explicitly set."""
        return {
            field: pv.value
            for field, pv in self.current_values.items()
            if pv.source == "user"
        }
    
    def get_preset_values(self) -> Dict[str, Any]:
        """Get only the values that came from preset (not user-overridden)."""
        return {
            field: pv.value
            for field, pv in self.current_values.items()
            if pv.source.startswith("preset:") and not pv.locked
        }
    
    def reset_to_defaults(self, fields: Optional[Set[str]] = None):
        """Reset specified fields (or all) to defaults, clearing preset and user values."""
        if fields is None:
            # Reset all
            self.current_values.clear()
            self.active_preset = None
        else:
            # Reset specific fields
            for field in fields:
                if field in self.current_values:
                    del self.current_values[field]
    
    def reset_to_preset(self, fields: Optional[Set[str]] = None):
        """Reset user overrides back to preset values."""
        if self.active_preset is None:
            return
        
        preset = self.presets[self.active_preset]
        preset_fields = preset.get_non_none_fields()
        
        if fields is None:
            # Reset all user overrides
            fields_to_reset = [
                field for field, pv in self.current_values.items()
                if pv.source == "user"
            ]
        else:
            fields_to_reset = fields
        
        for field in fields_to_reset:
            if field in self.current_values and self.current_values[field].source == "user":
                # Restore preset value if available
                if field in preset_fields:
                    self.current_values[field] = PresetValue(
                        value=preset_fields[field],
                        source=f"preset:{self.active_preset}",
                        locked=False
                    )
                else:
                    # Remove if preset doesn't have this field
                    del self.current_values[field]
    
    def clear_preset(self):
        """Remove preset influence, keep user overrides."""
        # Remove all preset values, keep only user overrides
        user_values = {
            field: pv for field, pv in self.current_values.items()
            if pv.source == "user"
        }
        self.current_values = user_values
        self.active_preset = None
    
    def list_presets(
        self,
        category: Optional[PresetCategory] = None,
        tags: Optional[Set[str]] = None
    ) -> List[PresetConfig]:
        """List available presets, optionally filtered."""
        result = []
        for preset in self.presets.values():
            # Filter by category
            if category and preset.category != category:
                continue
            # Filter by tags
            if tags and not tags.intersection(preset.tags):
                continue
            result.append(preset)
        return result
    
    def get_preset(self, name: str) -> Optional[PresetConfig]:
        """Get a specific preset by name."""
        return self.presets.get(name)
    
    def create_preset_from_current(self, name: str, description: str, 
                                   category: PresetCategory = PresetCategory.EXPERIMENTAL,
                                   tags: Optional[Set[str]] = None) -> PresetConfig:
        """Create a new preset from current values."""
        preset_dict = {
            'name': name,
            'category': category,
            'description': description,
            'tags': tags or set()
        }
        
        # Add current values
        for field, pv in self.current_values.items():
            preset_dict[field] = pv.value
        
        preset = PresetConfig(**preset_dict)
        self.presets[name] = preset
        return preset
    
    def export_preset(self, name: str) -> str:
        """Export preset as JSON."""
        if name not in self.presets:
            raise ValueError(f"Preset '{name}' not found")
        
        preset = self.presets[name]
        preset_dict = asdict(preset)
        
        # Convert enums and sets to serializable formats
        preset_dict['category'] = preset_dict['category'].value
        preset_dict['tags'] = list(preset_dict['tags'])
        
        return json.dumps(preset_dict, indent=2)
    
    def import_preset(self, json_data: str) -> PresetConfig:
        """Import preset from JSON."""
        preset_dict = json.loads(json_data)
        
        # Convert category string back to enum
        preset_dict['category'] = PresetCategory(preset_dict['category'])
        # Convert tags list back to set
        preset_dict['tags'] = set(preset_dict['tags'])
        
        preset = PresetConfig(**preset_dict)
        self.presets[preset.name] = preset
        return preset
    
    def save_user_presets(self, filepath: str):
        """Save user-created presets to file."""
        user_presets = {
            name: preset for name, preset in self.presets.items()
            if preset.category == PresetCategory.EXPERIMENTAL or (name not in GENRE_PRESETS and name not in STYLE_PRESETS and name not in PRODUCTION_PRESETS)
        }
        
        presets_list = []
        for preset in user_presets.values():
            preset_dict = asdict(preset)
            preset_dict['category'] = preset_dict['category'].value
            preset_dict['tags'] = list(preset_dict['tags'])
            presets_list.append(preset_dict)
        
        with open(filepath, 'w') as f:
            json.dump(presets_list, f, indent=2)
    
    def load_user_presets(self, filepath: str):
        """Load user-created presets from file."""
        with open(filepath, 'r') as f:
            presets_list = json.load(f)
        
        for preset_dict in presets_list:
            preset_dict['category'] = PresetCategory(preset_dict['category'])
            preset_dict['tags'] = set(preset_dict['tags'])
            preset = PresetConfig(**preset_dict)
            self.presets[preset.name] = preset


# Built-in presets organized by category

GENRE_PRESETS: Dict[str, PresetConfig] = {
    "hip_hop_boom_bap": PresetConfig(
        name="hip_hop_boom_bap",
        category=PresetCategory.GENRE,
        description="Classic 90s boom bap hip-hop with punchy drums and soulful samples",
        swing_amount=0.15,
        microtiming_intensity=0.3,
        humanize_amount=0.4,
        ghost_note_probability=0.2,
        velocity_range=(70, 110),
        tension_arc_shape="gradual_build",
        variation_intensity=0.3,
        pattern_intensity="medium",
        tags={"hip_hop", "boom_bap", "90s", "classic"},
    ),
    
    "hip_hop_trap": PresetConfig(
        name="hip_hop_trap",
        category=PresetCategory.GENRE,
        description="Modern trap with rolling hi-hats and 808s",
        swing_amount=0.0,  # Trap is more straight
        microtiming_intensity=0.1,
        humanize_amount=0.2,
        ghost_note_probability=0.1,
        velocity_range=(80, 127),
        tension_arc_shape="plateau",
        variation_intensity=0.2,
        pattern_intensity="high",
        tags={"hip_hop", "trap", "modern", "808"},
    ),
    
    "hip_hop_lofi": PresetConfig(
        name="hip_hop_lofi",
        category=PresetCategory.GENRE,
        description="Lo-fi hip-hop with relaxed beats and jazzy elements",
        swing_amount=0.25,
        microtiming_intensity=0.5,
        humanize_amount=0.6,
        ghost_note_probability=0.3,
        velocity_range=(50, 95),
        tension_arc_shape="flat",
        variation_intensity=0.4,
        pattern_intensity="low",
        accent_strength=0.3,
        tags={"hip_hop", "lofi", "chill", "jazzy"},
    ),
    
    "pop_modern": PresetConfig(
        name="pop_modern",
        category=PresetCategory.GENRE,
        description="Modern pop with polished production and strong hooks",
        swing_amount=0.05,
        microtiming_intensity=0.15,
        humanize_amount=0.25,
        ghost_note_probability=0.1,
        velocity_range=(75, 120),
        tension_arc_shape="peak_end",
        variation_intensity=0.4,
        pattern_intensity="high",
        accent_strength=0.5,
        tags={"pop", "modern", "polished", "hooks"},
    ),
    
    "pop_80s": PresetConfig(
        name="pop_80s",
        category=PresetCategory.GENRE,
        description="80s pop with synth-driven grooves and quantized feel",
        swing_amount=0.0,
        microtiming_intensity=0.1,
        humanize_amount=0.2,
        ghost_note_probability=0.05,
        velocity_range=(80, 115),
        tension_arc_shape="peak_middle",
        variation_intensity=0.3,
        pattern_intensity="medium",
        accent_strength=0.6,
        tags={"pop", "80s", "synth", "retro"},
    ),
    
    "jazz_swing": PresetConfig(
        name="jazz_swing",
        category=PresetCategory.GENRE,
        description="Jazz swing with triplet feel and dynamic expression",
        swing_amount=0.6,
        microtiming_intensity=0.4,
        humanize_amount=0.5,
        ghost_note_probability=0.4,
        velocity_range=(40, 110),
        tension_arc_shape="wave",
        variation_intensity=0.6,
        pattern_intensity="medium",
        accent_strength=0.4,
        timing_variance=0.3,
        tags={"jazz", "swing", "triplet", "dynamic"},
    ),
    
    "jazz_modal": PresetConfig(
        name="jazz_modal",
        category=PresetCategory.GENRE,
        description="Modal jazz with loose timing and exploratory feel",
        swing_amount=0.3,
        microtiming_intensity=0.5,
        humanize_amount=0.7,
        ghost_note_probability=0.35,
        velocity_range=(35, 105),
        tension_arc_shape="gradual_build",
        variation_intensity=0.7,
        pattern_intensity="low",
        accent_strength=0.3,
        timing_variance=0.4,
        tags={"jazz", "modal", "experimental", "loose"},
    ),
    
    "rock_classic": PresetConfig(
        name="rock_classic",
        category=PresetCategory.GENRE,
        description="Classic rock with driving drums and solid groove",
        swing_amount=0.1,
        microtiming_intensity=0.3,
        humanize_amount=0.4,
        ghost_note_probability=0.2,
        velocity_range=(80, 127),
        tension_arc_shape="peak_end",
        variation_intensity=0.35,
        pattern_intensity="high",
        accent_strength=0.6,
        tags={"rock", "classic", "driving", "groove"},
    ),
    
    "rock_indie": PresetConfig(
        name="rock_indie",
        category=PresetCategory.GENRE,
        description="Indie rock with loose, human feel and dynamic variety",
        swing_amount=0.15,
        microtiming_intensity=0.4,
        humanize_amount=0.5,
        ghost_note_probability=0.25,
        velocity_range=(60, 115),
        tension_arc_shape="double_peak",
        variation_intensity=0.5,
        pattern_intensity="medium",
        accent_strength=0.4,
        tags={"rock", "indie", "alternative", "dynamic"},
    ),
    
    "edm_house": PresetConfig(
        name="edm_house",
        category=PresetCategory.GENRE,
        description="House music with four-on-the-floor kick and tight timing",
        swing_amount=0.0,
        microtiming_intensity=0.05,
        humanize_amount=0.15,
        ghost_note_probability=0.05,
        velocity_range=(90, 127),
        tension_arc_shape="step_up",
        variation_intensity=0.25,
        pattern_intensity="high",
        accent_strength=0.5,
        tags={"edm", "house", "dance", "four-on-floor"},
    ),
    
    "edm_techno": PresetConfig(
        name="edm_techno",
        category=PresetCategory.GENRE,
        description="Techno with relentless energy and mechanical precision",
        swing_amount=0.0,
        microtiming_intensity=0.02,
        humanize_amount=0.1,
        ghost_note_probability=0.02,
        velocity_range=(95, 127),
        tension_arc_shape="plateau",
        variation_intensity=0.2,
        pattern_intensity="intense",
        accent_strength=0.4,
        tags={"edm", "techno", "industrial", "mechanical"},
    ),
    
    "rnb_neosoul": PresetConfig(
        name="rnb_neosoul",
        category=PresetCategory.GENRE,
        description="Neo-soul R&B with laid-back groove and rich dynamics",
        swing_amount=0.3,
        microtiming_intensity=0.6,
        humanize_amount=0.6,
        ghost_note_probability=0.35,
        velocity_range=(45, 105),
        tension_arc_shape="swell",
        variation_intensity=0.5,
        pattern_intensity="low",
        accent_strength=0.3,
        timing_variance=0.35,
        tags={"rnb", "neosoul", "groove", "laid_back"},
    ),
    
    "funk_classic": PresetConfig(
        name="funk_classic",
        category=PresetCategory.GENRE,
        description="Classic funk with tight pocket groove and syncopation",
        swing_amount=0.2,
        microtiming_intensity=0.25,
        humanize_amount=0.35,
        ghost_note_probability=0.3,
        velocity_range=(70, 115),
        tension_arc_shape="wave",
        variation_intensity=0.4,
        pattern_intensity="high",
        accent_strength=0.7,
        tags={"funk", "groove", "syncopated", "pocket"},
    ),
}

STYLE_PRESETS: Dict[str, PresetConfig] = {
    "chill": PresetConfig(
        name="chill",
        category=PresetCategory.STYLE,
        description="Relaxed, laid-back feel",
        humanize_amount=0.5,
        velocity_range=(50, 90),
        tension_intensity=0.3,
        variation_intensity=0.2,
        accent_strength=0.2,
        timing_variance=0.3,
        tags={"chill", "relaxed", "lofi"},
    ),
    
    "energetic": PresetConfig(
        name="energetic",
        category=PresetCategory.STYLE,
        description="High energy, driving feel",
        humanize_amount=0.2,
        velocity_range=(90, 127),
        tension_intensity=0.8,
        accent_strength=0.7,
        variation_intensity=0.4,
        pattern_intensity="high",
        tags={"energetic", "driving", "intense"},
    ),
    
    "aggressive": PresetConfig(
        name="aggressive",
        category=PresetCategory.STYLE,
        description="Hard-hitting, intense energy",
        humanize_amount=0.25,
        velocity_range=(95, 127),
        tension_intensity=0.9,
        accent_strength=0.8,
        variation_intensity=0.35,
        pattern_intensity="intense",
        microtiming_intensity=0.1,
        tags={"aggressive", "hard", "intense", "powerful"},
    ),
    
    "dreamy": PresetConfig(
        name="dreamy",
        category=PresetCategory.STYLE,
        description="Ethereal, floating atmosphere",
        humanize_amount=0.6,
        velocity_range=(40, 85),
        tension_intensity=0.4,
        accent_strength=0.2,
        variation_intensity=0.5,
        pattern_intensity="low",
        timing_variance=0.4,
        swing_amount=0.15,
        tags={"dreamy", "ethereal", "ambient", "floating"},
    ),
    
    "groovy": PresetConfig(
        name="groovy",
        category=PresetCategory.STYLE,
        description="Danceable, syncopated groove",
        humanize_amount=0.4,
        velocity_range=(70, 110),
        tension_intensity=0.6,
        accent_strength=0.6,
        variation_intensity=0.45,
        pattern_intensity="medium",
        swing_amount=0.25,
        ghost_note_probability=0.3,
        tags={"groovy", "danceable", "syncopated", "funky"},
    ),
}

PRODUCTION_PRESETS: Dict[str, PresetConfig] = {
    "demo_rough": PresetConfig(
        name="demo_rough",
        category=PresetCategory.PRODUCTION,
        description="Quick demo, less polish",
        humanize_amount=0.6,
        variation_intensity=0.5,
        timing_variance=0.35,
        ghost_note_probability=0.25,
        tags={"demo", "quick", "rough"},
    ),
    
    "polished": PresetConfig(
        name="polished",
        category=PresetCategory.PRODUCTION,
        description="Clean, professional production",
        humanize_amount=0.25,
        timing_variance=0.1,
        velocity_range=(60, 115),
        microtiming_intensity=0.15,
        variation_intensity=0.3,
        tags={"polished", "professional", "clean"},
    ),
    
    "experimental": PresetConfig(
        name="experimental",
        category=PresetCategory.PRODUCTION,
        description="Unconventional, creative approach",
        humanize_amount=0.7,
        variation_intensity=0.8,
        timing_variance=0.5,
        tension_intensity=0.7,
        ghost_note_probability=0.4,
        tags={"experimental", "creative", "unconventional", "avant_garde"},
    ),
}


# Convenience functions
def apply_genre_preset(genre: str, manager: Optional[PresetManager] = None) -> Dict[str, Any]:
    """Quick apply a genre preset, returns applied values."""
    if manager is None:
        manager = PresetManager()
    
    preset_values = manager.apply_preset(genre)
    return {field: pv.value for field, pv in preset_values.items()}


def get_preset_for_prompt(prompt: str, manager: Optional[PresetManager] = None) -> Optional[PresetConfig]:
    """Suggest a preset based on natural language prompt."""
    if manager is None:
        manager = PresetManager()
    
    prompt_lower = prompt.lower()
    
    # Search for genre keywords
    for preset_name, preset in manager.presets.items():
        # Check if preset name appears in prompt
        if preset_name.replace('_', ' ') in prompt_lower:
            return preset
        
        # Check if any tags appear in prompt
        for tag in preset.tags:
            if tag in prompt_lower:
                return preset
    
    return None


def combine_presets(
    genre_preset: str,
    style_preset: Optional[str] = None,
    production_preset: Optional[str] = None,
    manager: Optional[PresetManager] = None
) -> Dict[str, PresetValue]:
    """
    Combine multiple presets with clear precedence.
    
    Order: production > style > genre (later overrides earlier)
    """
    if manager is None:
        manager = PresetManager()
    
    # Apply in order: genre first, then style, then production
    manager.apply_preset(genre_preset)
    
    if style_preset:
        manager.apply_preset(style_preset)
    
    if production_preset:
        manager.apply_preset(production_preset)
    
    return manager.get_all_values()
