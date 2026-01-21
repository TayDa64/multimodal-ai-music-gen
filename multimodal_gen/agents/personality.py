"""
Agent Personality System

This module defines the personality configurations that make each
agent instance unique. Think of this as the "musician's style" -
two drummers given the same chart will play differently based on
their personality.

Includes:
- AgentPersonality: Configuration dataclass
- Preset dictionaries for each role
- Genre-to-personality mapping

Design Philosophy:
    Personality affects timing, dynamics, pattern choices, and creative
    decisions. It's how we achieve variation between takes and match
    the "feel" of different genres/styles.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum

from .base import AgentRole


@dataclass
class AgentPersonality:
    """
    Configuration that makes each agent instance unique.
    
    Think of this as the "musician's style" - two drummers
    given the same chart will play differently based on personality.
    
    Attributes:
        Core Style:
            aggressiveness: 0=laid-back, 1=intense (affects velocity)
            complexity: 0=simple patterns, 1=intricate patterns
            consistency: 0=wild/loose, 1=metronomic/tight
            
        Timing Feel:
            push_pull: -1=plays behind the beat, 0=on the beat, 1=ahead
            swing_affinity: 0-1, how much they like swing feel
            
        Creative Tendencies:
            fill_frequency: 0-1, how often they add fills
            ghost_note_density: 0-1, subtlety of ghost notes
            variation_tendency: 0-1, how much they vary patterns
            
        Signature Elements:
            signature_patterns: Pattern names they favor
            avoided_patterns: Patterns they never use
    
    Example:
        ```python
        jazz_drummer = AgentPersonality(
            aggressiveness=0.3,
            complexity=0.8,
            consistency=0.5,
            push_pull=-0.1,  # Slightly behind the beat
            swing_affinity=0.8,
            fill_frequency=0.4,
            ghost_note_density=0.8
        )
        ```
    """
    # Core style (0-1)
    aggressiveness: float = 0.5      # 0=laid-back, 1=intense
    complexity: float = 0.5          # 0=simple, 1=intricate
    consistency: float = 0.7         # 0=wild, 1=metronomic
    
    # Timing feel
    push_pull: float = 0.0           # -1=behind, 0=on, 1=ahead
    swing_affinity: float = 0.0      # How much they like swing
    
    # Creative tendencies (0-1)
    fill_frequency: float = 0.3      # How often they add fills
    ghost_note_density: float = 0.5  # Subtlety of ghost notes
    variation_tendency: float = 0.4  # How much they vary patterns
    
    # Signature elements
    signature_patterns: List[str] = field(default_factory=list)
    avoided_patterns: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Ensure mutable defaults and validate ranges."""
        if self.signature_patterns is None:
            self.signature_patterns = []
        if self.avoided_patterns is None:
            self.avoided_patterns = []
        
        # Clamp values to valid ranges
        self.aggressiveness = max(0.0, min(1.0, self.aggressiveness))
        self.complexity = max(0.0, min(1.0, self.complexity))
        self.consistency = max(0.0, min(1.0, self.consistency))
        self.push_pull = max(-1.0, min(1.0, self.push_pull))
        self.swing_affinity = max(0.0, min(1.0, self.swing_affinity))
        self.fill_frequency = max(0.0, min(1.0, self.fill_frequency))
        self.ghost_note_density = max(0.0, min(1.0, self.ghost_note_density))
        self.variation_tendency = max(0.0, min(1.0, self.variation_tendency))
    
    def apply_tension_scaling(self, tension: float) -> 'AgentPersonality':
        """
        Return a new personality scaled by tension level.
        
        Higher tension typically means:
        - More aggressive
        - More complex
        - More fills
        - Higher energy
        
        Args:
            tension: Tension value from 0.0 to 1.0
            
        Returns:
            New AgentPersonality with scaled values
        """
        tension = max(0.0, min(1.0, tension))
        
        # Scale factors based on tension
        agg_scale = 0.8 + (0.4 * tension)  # 0.8-1.2
        complexity_scale = 0.9 + (0.2 * tension)  # 0.9-1.1
        fill_scale = 1.0 + (0.5 * tension)  # 1.0-1.5
        
        return AgentPersonality(
            aggressiveness=min(1.0, self.aggressiveness * agg_scale),
            complexity=min(1.0, self.complexity * complexity_scale),
            consistency=self.consistency,  # Consistency shouldn't change with tension
            push_pull=self.push_pull,
            swing_affinity=self.swing_affinity,
            fill_frequency=min(1.0, self.fill_frequency * fill_scale),
            ghost_note_density=self.ghost_note_density,
            variation_tendency=self.variation_tendency,
            signature_patterns=self.signature_patterns.copy(),
            avoided_patterns=self.avoided_patterns.copy()
        )
    
    def blend_with(self, other: 'AgentPersonality', weight: float = 0.5) -> 'AgentPersonality':
        """
        Blend this personality with another.
        
        Useful for transitioning between styles or creating hybrid
        personalities.
        
        Args:
            other: Another personality to blend with
            weight: 0.0 = all self, 1.0 = all other
            
        Returns:
            New blended AgentPersonality
        """
        weight = max(0.0, min(1.0, weight))
        w1 = 1.0 - weight
        w2 = weight
        
        return AgentPersonality(
            aggressiveness=w1 * self.aggressiveness + w2 * other.aggressiveness,
            complexity=w1 * self.complexity + w2 * other.complexity,
            consistency=w1 * self.consistency + w2 * other.consistency,
            push_pull=w1 * self.push_pull + w2 * other.push_pull,
            swing_affinity=w1 * self.swing_affinity + w2 * other.swing_affinity,
            fill_frequency=w1 * self.fill_frequency + w2 * other.fill_frequency,
            ghost_note_density=w1 * self.ghost_note_density + w2 * other.ghost_note_density,
            variation_tendency=w1 * self.variation_tendency + w2 * other.variation_tendency,
            # Merge signature/avoided patterns (union)
            signature_patterns=list(set(self.signature_patterns + other.signature_patterns)),
            avoided_patterns=list(set(self.avoided_patterns + other.avoided_patterns))
        )


# =============================================================================
# PERSONALITY PRESETS
# =============================================================================

DRUMMER_PRESETS: Dict[str, AgentPersonality] = {
    "session_pro": AgentPersonality(
        aggressiveness=0.4,
        complexity=0.5,
        consistency=0.9,
        push_pull=0.0,
        swing_affinity=0.2,
        fill_frequency=0.2,
        ghost_note_density=0.6,
        variation_tendency=0.3,
        signature_patterns=["four_on_floor", "standard_backbeat"]
    ),
    
    "jazz_master": AgentPersonality(
        aggressiveness=0.3,
        complexity=0.8,
        consistency=0.5,
        push_pull=-0.1,  # Slightly behind the beat
        swing_affinity=0.8,
        fill_frequency=0.4,
        ghost_note_density=0.8,
        variation_tendency=0.6,
        signature_patterns=["jazz_ride", "brushes", "feathered_kick"]
    ),
    
    "trap_producer": AgentPersonality(
        aggressiveness=0.7,
        complexity=0.6,
        consistency=0.8,
        push_pull=0.0,
        swing_affinity=0.0,
        fill_frequency=0.15,
        ghost_note_density=0.4,
        variation_tendency=0.4,
        signature_patterns=["trap_hihat_roll", "808_pattern", "half_time_snare"]
    ),
    
    "punk_energy": AgentPersonality(
        aggressiveness=0.9,
        complexity=0.3,
        consistency=0.6,
        push_pull=0.15,  # Slightly ahead of the beat
        swing_affinity=0.0,
        fill_frequency=0.5,
        ghost_note_density=0.2,
        variation_tendency=0.3,
        signature_patterns=["d_beat", "blast_beat"],
        avoided_patterns=["ghost_notes", "brush_pattern"]
    ),
    
    "lofi_chill": AgentPersonality(
        aggressiveness=0.25,
        complexity=0.4,
        consistency=0.6,
        push_pull=-0.05,
        swing_affinity=0.6,
        fill_frequency=0.15,
        ghost_note_density=0.5,
        variation_tendency=0.4,
        signature_patterns=["boom_bap", "lazy_swing"]
    ),
    
    "rnb_smooth": AgentPersonality(
        aggressiveness=0.35,
        complexity=0.5,
        consistency=0.85,
        push_pull=-0.03,
        swing_affinity=0.4,
        fill_frequency=0.25,
        ghost_note_density=0.7,
        variation_tendency=0.35,
        signature_patterns=["pocket_groove", "rim_accent"]
    ),
    
    "gfunk_groove": AgentPersonality(
        aggressiveness=0.4,
        complexity=0.5,
        consistency=0.8,
        push_pull=-0.05,
        swing_affinity=0.7,
        fill_frequency=0.2,
        ghost_note_density=0.6,
        variation_tendency=0.35,
        signature_patterns=["west_coast_bounce", "funk_kick"]
    ),
    
    "ethiopian_traditional": AgentPersonality(
        aggressiveness=0.5,
        complexity=0.6,
        consistency=0.7,
        push_pull=0.0,
        swing_affinity=0.3,  # Compound meter feel, not swing
        fill_frequency=0.3,
        ghost_note_density=0.4,
        variation_tendency=0.5,
        signature_patterns=["kebero_pattern", "eskista_accent"]
    ),
    
    "house_steady": AgentPersonality(
        aggressiveness=0.5,
        complexity=0.4,
        consistency=0.95,
        push_pull=0.0,
        swing_affinity=0.1,
        fill_frequency=0.1,
        ghost_note_density=0.3,
        variation_tendency=0.2,
        signature_patterns=["four_on_floor", "offbeat_hihat"]
    ),
}


BASSIST_PRESETS: Dict[str, AgentPersonality] = {
    "pocket_player": AgentPersonality(
        aggressiveness=0.3,
        complexity=0.4,
        consistency=0.95,
        push_pull=-0.05,  # Sits in the pocket
        swing_affinity=0.3,
        fill_frequency=0.1,
        ghost_note_density=0.3,
        variation_tendency=0.25,
        signature_patterns=["root_fifth", "lock_to_kick"]
    ),
    
    "melodic_explorer": AgentPersonality(
        aggressiveness=0.5,
        complexity=0.7,
        consistency=0.7,
        push_pull=0.0,
        swing_affinity=0.4,
        fill_frequency=0.3,
        ghost_note_density=0.5,
        variation_tendency=0.6,
        signature_patterns=["walking_bass", "fills", "chromatic_approach"]
    ),
    
    "808_specialist": AgentPersonality(
        aggressiveness=0.6,
        complexity=0.5,
        consistency=0.8,
        push_pull=0.0,
        swing_affinity=0.0,
        fill_frequency=0.15,
        ghost_note_density=0.2,
        variation_tendency=0.4,
        signature_patterns=["808_glide", "sub_octave", "long_sustain"]
    ),
    
    "funk_groover": AgentPersonality(
        aggressiveness=0.6,
        complexity=0.6,
        consistency=0.8,
        push_pull=-0.03,
        swing_affinity=0.5,
        fill_frequency=0.25,
        ghost_note_density=0.6,
        variation_tendency=0.45,
        signature_patterns=["slap_pop", "octave_jump", "sixteenth_fills"]
    ),
    
    "gfunk_roller": AgentPersonality(
        aggressiveness=0.5,
        complexity=0.55,
        consistency=0.85,
        push_pull=-0.05,
        swing_affinity=0.6,
        fill_frequency=0.2,
        ghost_note_density=0.4,
        variation_tendency=0.4,
        signature_patterns=["rolling_bass", "octave_slide", "moog_style"]
    ),
    
    "dub_reggae": AgentPersonality(
        aggressiveness=0.35,
        complexity=0.4,
        consistency=0.8,
        push_pull=-0.1,  # Very laid back
        swing_affinity=0.2,
        fill_frequency=0.15,
        ghost_note_density=0.3,
        variation_tendency=0.3,
        signature_patterns=["one_drop", "root_emphasis"]
    ),
}


KEYIST_PRESETS: Dict[str, AgentPersonality] = {
    "jazz_voicings": AgentPersonality(
        aggressiveness=0.35,
        complexity=0.8,
        consistency=0.6,
        push_pull=-0.05,
        swing_affinity=0.7,
        fill_frequency=0.3,
        ghost_note_density=0.5,
        variation_tendency=0.6,
        signature_patterns=["rootless_voicing", "shell_voicing", "walking_tenths"]
    ),
    
    "pad_specialist": AgentPersonality(
        aggressiveness=0.2,
        complexity=0.3,
        consistency=0.9,
        push_pull=0.0,
        swing_affinity=0.0,
        fill_frequency=0.05,
        ghost_note_density=0.1,
        variation_tendency=0.2,
        signature_patterns=["sustained_pad", "slow_attack"]
    ),
    
    "gospel_chops": AgentPersonality(
        aggressiveness=0.6,
        complexity=0.8,
        consistency=0.7,
        push_pull=0.05,
        swing_affinity=0.3,
        fill_frequency=0.4,
        ghost_note_density=0.4,
        variation_tendency=0.5,
        signature_patterns=["church_run", "staccato_chord", "call_response"]
    ),
    
    "rhodes_soul": AgentPersonality(
        aggressiveness=0.35,
        complexity=0.5,
        consistency=0.75,
        push_pull=-0.03,
        swing_affinity=0.4,
        fill_frequency=0.2,
        ghost_note_density=0.5,
        variation_tendency=0.4,
        signature_patterns=["tremolo_chord", "soft_comp"]
    ),
    
    "synth_lead": AgentPersonality(
        aggressiveness=0.5,
        complexity=0.5,
        consistency=0.8,
        push_pull=0.0,
        swing_affinity=0.0,
        fill_frequency=0.2,
        ghost_note_density=0.3,
        variation_tendency=0.45,
        signature_patterns=["portamento", "arp_pattern"]
    ),
    
    "ethiopian_krar": AgentPersonality(
        aggressiveness=0.4,
        complexity=0.5,
        consistency=0.7,
        push_pull=0.0,
        swing_affinity=0.2,
        fill_frequency=0.3,
        ghost_note_density=0.4,
        variation_tendency=0.5,
        signature_patterns=["pentatonic_run", "drone_string", "qenet_embellishment"]
    ),
}


# =============================================================================
# GENRE TO PERSONALITY MAPPING
# =============================================================================

GENRE_PERSONALITY_MAP: Dict[str, Dict[AgentRole, str]] = {
    # Electronic/Hip-Hop
    "trap": {
        AgentRole.DRUMS: "trap_producer",
        AgentRole.BASS: "808_specialist",
        AgentRole.KEYS: "pad_specialist",
    },
    "trap_soul": {
        AgentRole.DRUMS: "trap_producer",
        AgentRole.BASS: "808_specialist",
        AgentRole.KEYS: "rhodes_soul",
    },
    "drill": {
        AgentRole.DRUMS: "trap_producer",
        AgentRole.BASS: "808_specialist",
        AgentRole.KEYS: "pad_specialist",
    },
    "lofi": {
        AgentRole.DRUMS: "lofi_chill",
        AgentRole.BASS: "pocket_player",
        AgentRole.KEYS: "rhodes_soul",
    },
    "house": {
        AgentRole.DRUMS: "house_steady",
        AgentRole.BASS: "pocket_player",
        AgentRole.KEYS: "pad_specialist",
    },
    
    # Traditional/Soul
    "rnb": {
        AgentRole.DRUMS: "rnb_smooth",
        AgentRole.BASS: "pocket_player",
        AgentRole.KEYS: "rhodes_soul",
    },
    "g_funk": {
        AgentRole.DRUMS: "gfunk_groove",
        AgentRole.BASS: "gfunk_roller",
        AgentRole.KEYS: "synth_lead",
    },
    "jazz": {
        AgentRole.DRUMS: "jazz_master",
        AgentRole.BASS: "melodic_explorer",
        AgentRole.KEYS: "jazz_voicings",
    },
    "funk": {
        AgentRole.DRUMS: "session_pro",
        AgentRole.BASS: "funk_groover",
        AgentRole.KEYS: "rhodes_soul",
    },
    "gospel": {
        AgentRole.DRUMS: "session_pro",
        AgentRole.BASS: "pocket_player",
        AgentRole.KEYS: "gospel_chops",
    },
    
    # Ethiopian
    "ethiopian": {
        AgentRole.DRUMS: "ethiopian_traditional",
        AgentRole.BASS: "pocket_player",
        AgentRole.KEYS: "ethiopian_krar",
    },
    "ethiopian_traditional": {
        AgentRole.DRUMS: "ethiopian_traditional",
        AgentRole.BASS: "pocket_player",
        AgentRole.KEYS: "ethiopian_krar",
    },
    "eskista": {
        AgentRole.DRUMS: "ethiopian_traditional",
        AgentRole.BASS: "pocket_player",
        AgentRole.KEYS: "ethiopian_krar",
    },
    "ethio_jazz": {
        AgentRole.DRUMS: "jazz_master",
        AgentRole.BASS: "melodic_explorer",
        AgentRole.KEYS: "ethiopian_krar",
    },
    
    # Rock/Alternative
    "rock": {
        AgentRole.DRUMS: "session_pro",
        AgentRole.BASS: "pocket_player",
        AgentRole.KEYS: "pad_specialist",
    },
    "punk": {
        AgentRole.DRUMS: "punk_energy",
        AgentRole.BASS: "pocket_player",
        AgentRole.KEYS: "pad_specialist",
    },
    
    # Default fallback
    "default": {
        AgentRole.DRUMS: "session_pro",
        AgentRole.BASS: "pocket_player",
        AgentRole.KEYS: "rhodes_soul",
    },
}


def get_personality_for_role(genre: str, role: AgentRole) -> AgentPersonality:
    """
    Get the appropriate personality for a role in a given genre.
    
    Args:
        genre: Genre string (e.g., "trap", "jazz", "lofi")
        role: AgentRole enum value
        
    Returns:
        AgentPersonality instance from the appropriate preset
    """
    genre_lower = genre.lower().strip()
    
    # Get genre mapping, fall back to default
    genre_map = GENRE_PERSONALITY_MAP.get(genre_lower, GENRE_PERSONALITY_MAP["default"])
    
    # Get preset name for this role
    preset_name = genre_map.get(role, None)
    
    if preset_name is None:
        # No preset defined for this role in this genre, use default
        default_map = GENRE_PERSONALITY_MAP["default"]
        preset_name = default_map.get(role, "session_pro")
    
    # Look up the preset in the appropriate preset dictionary
    if role == AgentRole.DRUMS:
        return DRUMMER_PRESETS.get(preset_name, DRUMMER_PRESETS["session_pro"])
    elif role == AgentRole.BASS:
        return BASSIST_PRESETS.get(preset_name, BASSIST_PRESETS["pocket_player"])
    elif role in [AgentRole.KEYS, AgentRole.PAD, AgentRole.LEAD]:
        return KEYIST_PRESETS.get(preset_name, KEYIST_PRESETS["rhodes_soul"])
    else:
        # Generic fallback
        return AgentPersonality()
