"""
Genre Intelligence Module

Provides deep genre understanding for AI music generation by loading
structured genre templates with mandatory/forbidden elements, spectral
profiles, and FX chains.

This module bridges the gap between simple keyword parsing and 
industry-standard genre-aware production decisions.

Usage:
    from multimodal_gen.genre_intelligence import GenreIntelligence
    
    gi = GenreIntelligence()
    template = gi.get_genre_template("trap")
    
    # Check if element is allowed
    if gi.is_element_allowed("trap", "hihat_roll"):
        # Generate hi-hat roll pattern
        
    # Get FX chain for a genre
    fx_chain = gi.get_fx_chain("lofi", "melodic")
"""

from __future__ import annotations
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class SpectralCharacter(Enum):
    """808 bass character types."""
    NONE = "none"
    CLEAN = "clean"
    CLEAN_SINE = "clean_sine"
    DISTORTED = "distorted"
    AGGRESSIVE = "aggressive"


@dataclass
class TempoConfig:
    """Tempo configuration for a genre."""
    bpm_range: Tuple[int, int]
    default_bpm: int
    swing_amount: float
    groove_template: str
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TempoConfig':
        return cls(
            bpm_range=tuple(data.get('bpm_range', [120, 130])),
            default_bpm=data.get('default_bpm', 120),
            swing_amount=data.get('swing_amount', 0.0),
            groove_template=data.get('groove_template', 'straight')
        )


@dataclass
class KeyConfig:
    """Key/scale configuration for a genre."""
    preferred_keys: List[str]
    scale_type: str
    allow_modal: bool
    ethiopian_modes: List[str] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'KeyConfig':
        return cls(
            preferred_keys=data.get('preferred_keys', ['Aminor']),
            scale_type=data.get('scale_type', 'minor'),
            allow_modal=data.get('allow_modal', True),
            ethiopian_modes=data.get('ethiopian_modes', [])
        )


@dataclass
class InstrumentConfig:
    """Instrument configuration for a genre."""
    mandatory: List[str]
    recommended: List[str]
    forbidden: List[str]
    default_set: List[str]
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'InstrumentConfig':
        return cls(
            mandatory=data.get('mandatory', []),
            recommended=data.get('recommended', []),
            forbidden=data.get('forbidden', []),
            default_set=data.get('default_set', [])
        )


@dataclass
class DrumConfig:
    """Drum pattern configuration for a genre."""
    pattern_type: str
    hihat_density: str
    hihat_rolls: bool
    half_time_snare: bool
    velocity_variation: float
    timing_humanization: float
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'DrumConfig':
        return cls(
            pattern_type=data.get('pattern_type', 'standard'),
            hihat_density=data.get('hihat_density', '8th'),
            hihat_rolls=data.get('hihat_rolls', False),
            half_time_snare=data.get('half_time_snare', False),
            velocity_variation=data.get('velocity_variation', 0.12),
            timing_humanization=data.get('timing_humanization', 0.02)
        )


@dataclass
class SpectralProfile:
    """Spectral characteristics for a genre."""
    sub_bass_presence: float  # 0.0 - 1.0
    brightness: float         # 0.0 - 1.0
    warmth: float            # 0.0 - 1.0
    character_808: SpectralCharacter
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SpectralProfile':
        char = data.get('808_character', 'none')
        try:
            spectral_char = SpectralCharacter(char)
        except ValueError:
            spectral_char = SpectralCharacter.NONE
            
        return cls(
            sub_bass_presence=data.get('sub_bass_presence', 0.5),
            brightness=data.get('brightness', 0.5),
            warmth=data.get('warmth', 0.5),
            character_808=spectral_char
        )


@dataclass
class FXChain:
    """FX chain configuration for a genre."""
    master: List[str]
    drums: List[str]
    bass: List[str]
    melodic: List[str]
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'FXChain':
        return cls(
            master=data.get('master', []),
            drums=data.get('drums', []),
            bass=data.get('bass', []),
            melodic=data.get('melodic', [])
        )


@dataclass
class ArrangementConfig:
    """Arrangement preferences for a genre."""
    typical_length_bars: int
    intro_bars: int
    verse_bars: int
    chorus_bars: int
    breakdown_style: str
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ArrangementConfig':
        return cls(
            typical_length_bars=data.get('typical_length_bars', 64),
            intro_bars=data.get('intro_bars', 8),
            verse_bars=data.get('verse_bars', 16),
            chorus_bars=data.get('chorus_bars', 8),
            breakdown_style=data.get('breakdown_style', 'minimal')
        )


@dataclass
class GenreTemplate:
    """Complete genre template with all configurations."""
    name: str
    display_name: str
    color_theme: str
    icon: str
    
    tempo: TempoConfig
    key: KeyConfig
    instruments: InstrumentConfig
    drums: DrumConfig
    fx_chain: FXChain
    spectral_profile: SpectralProfile
    arrangement: ArrangementConfig
    
    textures: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, name: str, data: Dict) -> 'GenreTemplate':
        return cls(
            name=name,
            display_name=data.get('display_name', name.title()),
            color_theme=data.get('color_theme', '#808080'),
            icon=data.get('icon', 'default_icon'),
            tempo=TempoConfig.from_dict(data.get('tempo', {})),
            key=KeyConfig.from_dict(data.get('key', {})),
            instruments=InstrumentConfig.from_dict(data.get('instruments', {})),
            drums=DrumConfig.from_dict(data.get('drums', {})),
            fx_chain=FXChain.from_dict(data.get('fx_chain', {})),
            spectral_profile=SpectralProfile.from_dict(data.get('spectral_profile', {})),
            arrangement=ArrangementConfig.from_dict(data.get('arrangement', {})),
            textures=data.get('textures', {})
        )


@dataclass
class InstrumentCategory:
    """Category definition for instrument browser."""
    name: str
    display_name: str
    icon: str
    subcategories: List[str]


@dataclass
class FXDefinition:
    """Definition of an audio effect."""
    name: str
    type: str
    description: str
    parameters: Dict[str, Any]


@dataclass
class HumanizationProfile:
    """Humanization settings for natural feel."""
    name: str
    velocity_variation: float
    timing_variation: float
    description: str


# =============================================================================
# GENRE INTELLIGENCE CLASS
# =============================================================================

class GenreIntelligence:
    """
    Genre Intelligence System for AI Music Generation.
    
    Provides deep understanding of genre-specific:
    - Mandatory and forbidden elements
    - Spectral profiles (brightness, warmth, 808 character)
    - FX chains and processing
    - Arrangement conventions
    - Humanization profiles
    
    Example:
        gi = GenreIntelligence()
        
        # Get full template
        template = gi.get_genre_template("trap")
        print(f"BPM range: {template.tempo.bpm_range}")
        
        # Check element validity
        if not gi.is_element_allowed("g_funk", "hihat_roll"):
            print("Hi-hat rolls are forbidden in G-Funk!")
        
        # Get FX chain
        fx = gi.get_fx_chain("lofi", "drums")
        # Returns: ['bitcrush_light', 'room_reverb']
    """
    
    def __init__(self, genres_path: Optional[Path] = None):
        """
        Initialize Genre Intelligence system.
        
        Args:
            genres_path: Path to genres.json. If None, uses default location.
        """
        if genres_path is None:
            genres_path = Path(__file__).parent / "genres.json"
        
        self._genres_path = genres_path
        self._templates: Dict[str, GenreTemplate] = {}
        self._categories: Dict[str, InstrumentCategory] = {}
        self._fx_definitions: Dict[str, FXDefinition] = {}
        self._humanization: Dict[str, HumanizationProfile] = {}
        self._raw_data: Dict = {}
        
        self._load_genres()
    
    def _load_genres(self) -> None:
        """Load genre templates from JSON file."""
        try:
            with open(self._genres_path, 'r', encoding='utf-8') as f:
                self._raw_data = json.load(f)
        except FileNotFoundError:
            print(f"Warning: genres.json not found at {self._genres_path}")
            self._raw_data = {"genres": {}}
            return
        except json.JSONDecodeError as e:
            print(f"Warning: Invalid JSON in genres.json: {e}")
            self._raw_data = {"genres": {}}
            return
        
        # Parse genre templates
        for name, data in self._raw_data.get("genres", {}).items():
            self._templates[name] = GenreTemplate.from_dict(name, data)
        
        # Parse instrument categories
        for name, data in self._raw_data.get("instrument_categories", {}).items():
            self._categories[name] = InstrumentCategory(
                name=name,
                display_name=data.get("display_name", name.title()),
                icon=data.get("icon", "📁"),
                subcategories=data.get("subcategories", [])
            )
        
        # Parse FX definitions
        for name, data in self._raw_data.get("fx_definitions", {}).items():
            self._fx_definitions[name] = FXDefinition(
                name=name,
                type=data.get("type", "unknown"),
                description=data.get("description", ""),
                parameters=data.get("parameters", {})
            )
        
        # Parse humanization profiles
        for name, data in self._raw_data.get("humanization_profiles", {}).items():
            self._humanization[name] = HumanizationProfile(
                name=name,
                velocity_variation=data.get("velocity_variation", 0.12),
                timing_variation=data.get("timing_variation", 0.02),
                description=data.get("description", "")
            )
    
    # =========================================================================
    # PUBLIC API
    # =========================================================================
    
    def get_genre_template(self, genre: str) -> Optional[GenreTemplate]:
        """
        Get complete template for a genre.
        
        Args:
            genre: Genre identifier (e.g., "trap", "g_funk", "lofi")
            
        Returns:
            GenreTemplate or None if not found
        """
        return self._templates.get(genre)
    
    def get_all_genres(self) -> List[str]:
        """Get list of all available genre identifiers."""
        return list(self._templates.keys())
    
    def get_genre_display_names(self) -> Dict[str, str]:
        """Get mapping of genre ID to display name."""
        return {name: t.display_name for name, t in self._templates.items()}
    
    def is_element_allowed(self, genre: str, element: str) -> bool:
        """
        Check if an element (instrument/drum) is allowed in a genre.
        
        Args:
            genre: Genre identifier
            element: Element to check (e.g., "hihat_roll", "808")
            
        Returns:
            True if allowed, False if forbidden
        """
        template = self._templates.get(genre)
        if not template:
            return True  # Default to allowed if genre unknown
        
        return element not in template.instruments.forbidden
    
    def get_mandatory_elements(self, genre: str) -> List[str]:
        """Get mandatory elements for a genre."""
        template = self._templates.get(genre)
        if not template:
            return []
        return template.instruments.mandatory
    
    def get_forbidden_elements(self, genre: str) -> List[str]:
        """Get forbidden elements for a genre."""
        template = self._templates.get(genre)
        if not template:
            return []
        return template.instruments.forbidden
    
    def get_recommended_elements(self, genre: str) -> List[str]:
        """Get recommended elements for a genre."""
        template = self._templates.get(genre)
        if not template:
            return []
        return template.instruments.recommended
    
    def get_default_instruments(self, genre: str) -> List[str]:
        """Get default instrument set for a genre."""
        template = self._templates.get(genre)
        if not template:
            return []
        return template.instruments.default_set
    
    def get_fx_chain(self, genre: str, bus: str = "master") -> List[str]:
        """
        Get FX chain for a genre and bus type.
        
        Args:
            genre: Genre identifier
            bus: "master", "drums", "bass", or "melodic"
            
        Returns:
            List of FX names to apply
        """
        template = self._templates.get(genre)
        if not template:
            return []
        
        return getattr(template.fx_chain, bus, [])
    
    def get_spectral_profile(self, genre: str) -> Optional[SpectralProfile]:
        """Get spectral profile for a genre."""
        template = self._templates.get(genre)
        if not template:
            return None
        return template.spectral_profile
    
    def get_bpm_range(self, genre: str) -> Tuple[int, int]:
        """Get BPM range for a genre."""
        template = self._templates.get(genre)
        if not template:
            return (120, 130)
        return template.tempo.bpm_range
    
    def get_default_bpm(self, genre: str) -> int:
        """Get default BPM for a genre."""
        template = self._templates.get(genre)
        if not template:
            return 120
        return template.tempo.default_bpm
    
    def get_swing_amount(self, genre: str) -> float:
        """Get swing amount for a genre (0.0 - 1.0)."""
        template = self._templates.get(genre)
        if not template:
            return 0.0
        return template.tempo.swing_amount
    
    def get_preferred_keys(self, genre: str) -> List[str]:
        """Get preferred keys for a genre."""
        template = self._templates.get(genre)
        if not template:
            return ["Aminor"]
        return template.key.preferred_keys
    
    def get_drum_config(self, genre: str) -> Optional[DrumConfig]:
        """Get drum configuration for a genre."""
        template = self._templates.get(genre)
        if not template:
            return None
        return template.drums
    
    def get_arrangement_config(self, genre: str) -> Optional[ArrangementConfig]:
        """Get arrangement configuration for a genre."""
        template = self._templates.get(genre)
        if not template:
            return None
        return template.arrangement
    
    def should_use_hihat_rolls(self, genre: str) -> bool:
        """Check if hi-hat rolls are appropriate for a genre."""
        template = self._templates.get(genre)
        if not template:
            return False
        return template.drums.hihat_rolls
    
    def should_use_half_time_snare(self, genre: str) -> bool:
        """Check if half-time snare is standard for a genre."""
        template = self._templates.get(genre)
        if not template:
            return False
        return template.drums.half_time_snare
    
    def get_color_theme(self, genre: str) -> str:
        """Get UI color theme for a genre."""
        template = self._templates.get(genre)
        if not template:
            return "#808080"
        return template.color_theme
    
    # =========================================================================
    # INSTRUMENT CATEGORIES
    # =========================================================================
    
    def get_instrument_categories(self) -> List[InstrumentCategory]:
        """Get all instrument categories for browser UI."""
        return list(self._categories.values())
    
    def get_category(self, name: str) -> Optional[InstrumentCategory]:
        """Get a specific instrument category."""
        return self._categories.get(name)
    
    # =========================================================================
    # FX DEFINITIONS
    # =========================================================================
    
    def get_fx_definition(self, fx_name: str) -> Optional[FXDefinition]:
        """Get definition for a specific FX."""
        return self._fx_definitions.get(fx_name)
    
    def get_all_fx(self) -> List[str]:
        """Get list of all defined FX names."""
        return list(self._fx_definitions.keys())
    
    # =========================================================================
    # HUMANIZATION
    # =========================================================================
    
    def get_humanization_profile(self, profile: str) -> Optional[HumanizationProfile]:
        """Get humanization profile by name."""
        return self._humanization.get(profile)
    
    def get_humanization_for_genre(self, genre: str) -> HumanizationProfile:
        """
        Get appropriate humanization profile for a genre.
        
        Automatically maps genre to humanization profile:
        - trap, drill → tight
        - house → tight
        - lofi → loose
        - boom_bap, g_funk → live
        - others → natural
        """
        template = self._templates.get(genre)
        if not template:
            return self._humanization.get("natural", HumanizationProfile(
                name="natural",
                velocity_variation=0.12,
                timing_variation=0.025,
                description="Default humanization"
            ))
        
        # Map genres to humanization profiles
        tight_genres = ["trap", "drill", "house"]
        loose_genres = ["lofi"]
        live_genres = ["boom_bap", "g_funk", "rnb"]
        
        if genre in tight_genres:
            profile_name = "tight"
        elif genre in loose_genres:
            profile_name = "loose"
        elif genre in live_genres:
            profile_name = "live"
        else:
            profile_name = "natural"
        
        return self._humanization.get(profile_name, self._humanization.get("natural"))
    
    # =========================================================================
    # VALIDATION
    # =========================================================================
    
    def validate_prompt_against_genre(
        self,
        genre: str,
        instruments: List[str],
        drum_elements: List[str]
    ) -> Dict[str, Any]:
        """
        Validate user's instrument/drum choices against genre rules.
        
        Returns dict with:
            - valid: bool
            - forbidden_used: List of forbidden elements found
            - mandatory_missing: List of mandatory elements missing
            - warnings: List of recommendation warnings
        """
        template = self._templates.get(genre)
        if not template:
            return {"valid": True, "forbidden_used": [], "mandatory_missing": [], "warnings": []}
        
        all_elements = set(instruments + drum_elements)
        
        # Check forbidden
        forbidden_used = [e for e in all_elements if e in template.instruments.forbidden]
        
        # Check mandatory
        mandatory_missing = [e for e in template.instruments.mandatory if e not in all_elements]
        
        # Generate warnings for missing recommended
        warnings = []
        recommended_missing = [e for e in template.instruments.recommended if e not in all_elements]
        if recommended_missing:
            warnings.append(f"Consider adding: {', '.join(recommended_missing)}")
        
        return {
            "valid": len(forbidden_used) == 0,
            "forbidden_used": forbidden_used,
            "mandatory_missing": mandatory_missing,
            "warnings": warnings
        }
    
    # =========================================================================
    # JSON EXPORT (for JUCE)
    # =========================================================================
    
    def to_json_manifest(self) -> str:
        """
        Export genres as JSON manifest for JUCE UI.
        
        Returns compact JSON suitable for OSC transmission.
        """
        manifest = {
            "genres": {},
            "categories": {},
            "version": self._raw_data.get("version", "1.0.0")
        }
        
        for name, template in self._templates.items():
            manifest["genres"][name] = {
                "display_name": template.display_name,
                "color": template.color_theme,
                "bpm_range": list(template.tempo.bpm_range),
                "default_bpm": template.tempo.default_bpm,
                "swing": template.tempo.swing_amount,
                "instruments": template.instruments.default_set,
                "hihat_rolls": template.drums.hihat_rolls,
                "forbidden": template.instruments.forbidden
            }
        
        for name, category in self._categories.items():
            manifest["categories"][name] = {
                "display_name": category.display_name,
                "icon": category.icon,
                "subcategories": category.subcategories
            }
        
        return json.dumps(manifest, separators=(',', ':'))


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_genre_intelligence: Optional[GenreIntelligence] = None


def get_genre_intelligence() -> GenreIntelligence:
    """Get or create the global GenreIntelligence instance."""
    global _genre_intelligence
    if _genre_intelligence is None:
        _genre_intelligence = GenreIntelligence()
    return _genre_intelligence


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_genre_template(genre: str) -> Optional[GenreTemplate]:
    """Get genre template (convenience function)."""
    return get_genre_intelligence().get_genre_template(genre)


def is_element_allowed(genre: str, element: str) -> bool:
    """Check if element is allowed in genre (convenience function)."""
    return get_genre_intelligence().is_element_allowed(genre, element)


def get_fx_chain(genre: str, bus: str = "master") -> List[str]:
    """Get FX chain for genre (convenience function)."""
    return get_genre_intelligence().get_fx_chain(genre, bus)


def validate_prompt(genre: str, instruments: List[str], drums: List[str]) -> Dict[str, Any]:
    """Validate prompt against genre rules (convenience function)."""
    return get_genre_intelligence().validate_prompt_against_genre(genre, instruments, drums)


# =============================================================================
# CLI TESTING
# =============================================================================

if __name__ == "__main__":
    import sys
    
    gi = GenreIntelligence()
    
    print("🎵 Genre Intelligence System")
    print("=" * 50)
    print(f"Loaded {len(gi.get_all_genres())} genres:")
    
    for genre in gi.get_all_genres():
        template = gi.get_genre_template(genre)
        print(f"\n  [{genre}] {template.display_name}")
        print(f"    BPM: {template.tempo.bpm_range[0]}-{template.tempo.bpm_range[1]} (default: {template.tempo.default_bpm})")
        print(f"    Swing: {template.tempo.swing_amount * 100:.0f}%")
        print(f"    Hi-hat rolls: {'✓' if template.drums.hihat_rolls else '✗'}")
        print(f"    Mandatory: {', '.join(template.instruments.mandatory)}")
        if template.instruments.forbidden:
            print(f"    Forbidden: {', '.join(template.instruments.forbidden)}")
    
    print("\n" + "=" * 50)
    print("Validation example (trap with hi-hat rolls):")
    result = gi.validate_prompt_against_genre("g_funk", ["synth", "bass"], ["hihat_roll"])
    print(f"  Valid: {result['valid']}")
    print(f"  Forbidden used: {result['forbidden_used']}")
    print(f"  Mandatory missing: {result['mandatory_missing']}")
