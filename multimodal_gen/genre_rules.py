"""
Genre Rules DSL v2 - Enforced Pattern Constraints & Validation

This module extends the existing genres.json with:
- mandatory_patterns: Named pattern constraints that MUST appear
- forbidden_signatures: Element combinations that MUST NOT appear  
- mix_rules: Spectral/frequency guardrails
- validation_hooks: Auto-repair for violations

The system upgrades genre handling from "recommendations" into
**enforced constraints** so the arranger/generator doesn't produce
genre-breaking artifacts.

Per likuTasks.md Milestone B:
- For at least 5 genres (trap, trap_soul, boom_bap, g_funk, lofi),
  rules prevent clearly wrong outputs.
- The system logs rule decisions into session_manifest.json.
- If rules are missing for a genre, generation behaves as today.

Usage:
    from multimodal_gen.genre_rules import (
        GenreRulesEngine,
        get_genre_rules,
        validate_generation,
        repair_violations
    )
    
    engine = get_genre_rules()
    
    # Check if a pattern is valid
    result = engine.validate_elements("trap", ["808", "kick"], ["hihat_roll"])
    
    # Get required patterns
    required = engine.get_mandatory_patterns("boom_bap")
    
    # Auto-repair forbidden elements
    repaired = engine.repair_violations("g_funk", ["808_glide", "synth"])
"""

from __future__ import annotations
import json
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# RULE SEVERITY & TYPES
# =============================================================================

class RuleSeverity(Enum):
    """Severity level for rule violations."""
    ERROR = "error"       # Must not happen, blocks generation
    WARNING = "warning"   # Strongly discouraged, auto-repair available
    INFO = "info"         # Suggestion only, logged but allowed


class PatternType(Enum):
    """Types of musical pattern constraints."""
    DRUM = "drum"
    BASS = "bass"
    MELODIC = "melodic"
    RHYTHMIC = "rhythmic"
    HARMONIC = "harmonic"
    TEXTURE = "texture"


class MixRuleType(Enum):
    """Types of mix/mastering rules."""
    DYNAMICS = "dynamics"
    SPECTRAL = "spectral"
    STEREO = "stereo"
    LOUDNESS = "loudness"


# =============================================================================
# PATTERN SPECIFICATION DATA STRUCTURES
# =============================================================================

@dataclass
class PatternSpec:
    """
    Specification for a mandatory or recommended pattern.
    
    Examples:
    - "g_funk_swing_hat": hi-hat with specific swing percentage
    - "boom_bap_kick_placements": kick on beats 1, 2.5, 3
    - "trap_half_time_snare": snare on beat 3 only
    """
    name: str
    type: PatternType
    description: str
    
    # Pattern requirements
    beats: List[float] = field(default_factory=list)  # Beat positions (1-indexed)
    velocity_range: Tuple[int, int] = (60, 127)
    swing_percent: float = 0.0  # 0.0 = straight, 0.5 = max swing
    density: str = "8th"  # "quarter", "8th", "16th", "random"
    
    # Conditional application
    section_types: List[str] = field(default_factory=list)  # Empty = all sections
    min_bars: int = 1
    
    @classmethod
    def from_dict(cls, name: str, data: Dict) -> 'PatternSpec':
        return cls(
            name=name,
            type=PatternType(data.get('type', 'drum')),
            description=data.get('description', ''),
            beats=data.get('beats', []),
            velocity_range=tuple(data.get('velocity_range', [60, 127])),
            swing_percent=data.get('swing_percent', 0.0),
            density=data.get('density', '8th'),
            section_types=data.get('section_types', []),
            min_bars=data.get('min_bars', 1)
        )
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'type': self.type.value,
            'description': self.description,
            'beats': self.beats,
            'velocity_range': list(self.velocity_range),
            'swing_percent': self.swing_percent,
            'density': self.density,
            'section_types': self.section_types,
            'min_bars': self.min_bars
        }


@dataclass
class ForbiddenSignature:
    """
    A combination or pattern that must NOT appear in a genre.
    
    Examples:
    - "boom_bap + 808_glide": No gliding 808s in boom bap
    - "g_funk + trap_hihat_roll": No dense trap rolls in G-Funk
    - "lofi + brickwall_limiter": No harsh limiting in lo-fi
    """
    id: str
    description: str
    severity: RuleSeverity
    
    # Triggering conditions (any match triggers the rule)
    elements: List[str] = field(default_factory=list)       # Instrument/drum names
    patterns: List[str] = field(default_factory=list)       # Pattern types
    combinations: List[List[str]] = field(default_factory=list)  # Element combos
    
    # Auto-repair suggestion
    replacement: Optional[str] = None  # Suggested replacement element
    repair_action: str = "remove"  # "remove", "replace", "modify"
    
    @classmethod
    def from_dict(cls, sig_id: str, data: Dict) -> 'ForbiddenSignature':
        severity_str = data.get('severity', 'warning')
        try:
            severity = RuleSeverity(severity_str)
        except ValueError:
            severity = RuleSeverity.WARNING
            
        return cls(
            id=sig_id,
            description=data.get('description', ''),
            severity=severity,
            elements=data.get('elements', []),
            patterns=data.get('patterns', []),
            combinations=data.get('combinations', []),
            replacement=data.get('replacement'),
            repair_action=data.get('repair_action', 'remove')
        )
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'description': self.description,
            'severity': self.severity.value,
            'elements': self.elements,
            'patterns': self.patterns,
            'combinations': self.combinations,
            'replacement': self.replacement,
            'repair_action': self.repair_action
        }


@dataclass
class MixRule:
    """
    Mix/mastering guardrail for a genre.
    
    Examples:
    - "lofi_no_brickwall": Prevent harsh limiting in lo-fi
    - "trap_allow_softclip": Allow soft clipping on master
    - "house_sidechain": Require sidechain compression
    """
    id: str
    type: MixRuleType
    description: str
    
    # Rule parameters
    allowed_fx: List[str] = field(default_factory=list)
    forbidden_fx: List[str] = field(default_factory=list)
    
    # Spectral constraints
    max_brightness: float = 1.0  # 0.0 - 1.0
    min_warmth: float = 0.0      # 0.0 - 1.0
    max_sub_bass: float = 1.0    # 0.0 - 1.0
    
    # Dynamics constraints
    min_dynamic_range_db: float = 0.0
    max_peak_db: float = 0.0
    allow_hard_clip: bool = False
    
    @classmethod
    def from_dict(cls, rule_id: str, data: Dict) -> 'MixRule':
        mix_type_str = data.get('type', 'dynamics')
        try:
            mix_type = MixRuleType(mix_type_str)
        except ValueError:
            mix_type = MixRuleType.DYNAMICS
            
        return cls(
            id=rule_id,
            type=mix_type,
            description=data.get('description', ''),
            allowed_fx=data.get('allowed_fx', []),
            forbidden_fx=data.get('forbidden_fx', []),
            max_brightness=data.get('max_brightness', 1.0),
            min_warmth=data.get('min_warmth', 0.0),
            max_sub_bass=data.get('max_sub_bass', 1.0),
            min_dynamic_range_db=data.get('min_dynamic_range_db', 0.0),
            max_peak_db=data.get('max_peak_db', 0.0),
            allow_hard_clip=data.get('allow_hard_clip', False)
        )
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'type': self.type.value,
            'description': self.description,
            'allowed_fx': self.allowed_fx,
            'forbidden_fx': self.forbidden_fx,
            'max_brightness': self.max_brightness,
            'min_warmth': self.min_warmth,
            'max_sub_bass': self.max_sub_bass,
            'min_dynamic_range_db': self.min_dynamic_range_db,
            'max_peak_db': self.max_peak_db,
            'allow_hard_clip': self.allow_hard_clip
        }


@dataclass
class GenreRuleset:
    """Complete ruleset for a single genre."""
    genre: str
    version: str = "1.0.0"
    
    mandatory_patterns: Dict[str, PatternSpec] = field(default_factory=dict)
    forbidden_signatures: Dict[str, ForbiddenSignature] = field(default_factory=dict)
    mix_rules: Dict[str, MixRule] = field(default_factory=dict)
    
    # Quick lookup sets for validation
    _forbidden_elements: Set[str] = field(default_factory=set)
    
    def __post_init__(self):
        # Build forbidden element index for fast lookup
        for sig in self.forbidden_signatures.values():
            self._forbidden_elements.update(sig.elements)
    
    @classmethod
    def from_dict(cls, genre: str, data: Dict) -> 'GenreRuleset':
        ruleset = cls(
            genre=genre,
            version=data.get('version', '1.0.0')
        )
        
        # Parse mandatory patterns
        for name, pattern_data in data.get('mandatory_patterns', {}).items():
            ruleset.mandatory_patterns[name] = PatternSpec.from_dict(name, pattern_data)
        
        # Parse forbidden signatures
        for sig_id, sig_data in data.get('forbidden_signatures', {}).items():
            ruleset.forbidden_signatures[sig_id] = ForbiddenSignature.from_dict(sig_id, sig_data)
        
        # Parse mix rules
        for rule_id, rule_data in data.get('mix_rules', {}).items():
            ruleset.mix_rules[rule_id] = MixRule.from_dict(rule_id, rule_data)
        
        # Build index
        ruleset.__post_init__()
        
        return ruleset
    
    def to_dict(self) -> Dict:
        return {
            'genre': self.genre,
            'version': self.version,
            'mandatory_patterns': {k: v.to_dict() for k, v in self.mandatory_patterns.items()},
            'forbidden_signatures': {k: v.to_dict() for k, v in self.forbidden_signatures.items()},
            'mix_rules': {k: v.to_dict() for k, v in self.mix_rules.items()}
        }


# =============================================================================
# VALIDATION RESULT DATA STRUCTURES
# =============================================================================

@dataclass
class RuleViolation:
    """A single rule violation found during validation."""
    rule_id: str
    rule_type: str  # "forbidden_signature", "missing_mandatory", "mix_rule"
    severity: RuleSeverity
    message: str
    elements_involved: List[str]
    repair_suggestion: Optional[str] = None
    auto_repaired: bool = False


@dataclass
class ValidationResult:
    """Complete validation result for a generation request."""
    genre: str
    valid: bool
    
    violations: List[RuleViolation] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    repairs_applied: List[Dict[str, Any]] = field(default_factory=list)
    
    # Breakdown
    forbidden_used: List[str] = field(default_factory=list)
    mandatory_missing: List[str] = field(default_factory=list)
    mix_violations: List[str] = field(default_factory=list)
    
    # For manifest logging
    rule_decisions: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            'genre': self.genre,
            'valid': self.valid,
            'violations': [
                {
                    'rule_id': v.rule_id,
                    'rule_type': v.rule_type,
                    'severity': v.severity.value,
                    'message': v.message,
                    'elements': v.elements_involved,
                    'repair': v.repair_suggestion,
                    'auto_repaired': v.auto_repaired
                }
                for v in self.violations
            ],
            'warnings': self.warnings,
            'repairs_applied': self.repairs_applied,
            'forbidden_used': self.forbidden_used,
            'mandatory_missing': self.mandatory_missing,
            'mix_violations': self.mix_violations,
            'rule_decisions': self.rule_decisions
        }


# =============================================================================
# DEFAULT GENRE RULES (Built-in)
# =============================================================================

DEFAULT_GENRE_RULES: Dict[str, Dict] = {
    "trap": {
        "version": "1.0.0",
        "mandatory_patterns": {
            "trap_half_time_snare": {
                "type": "drum",
                "description": "Snare on beat 3 (half-time feel)",
                "beats": [3.0],
                "velocity_range": [90, 127],
                "section_types": ["verse", "chorus", "drop"]
            },
            "trap_808_presence": {
                "type": "bass",
                "description": "808 bass must be present",
                "density": "sustain"
            },
            "trap_hihat_16th": {
                "type": "drum",
                "description": "Dense 16th note hi-hats",
                "density": "16th",
                "section_types": ["verse", "chorus", "drop"]
            }
        },
        "forbidden_signatures": {
            "no_boom_bap_swing": {
                "description": "Boom bap swing pattern doesn't fit trap",
                "severity": "warning",
                "patterns": ["boom_bap_swing"],
                "replacement": "straight_16th",
                "repair_action": "replace"
            }
        },
        "mix_rules": {
            "trap_808_presence": {
                "type": "spectral",
                "description": "Strong sub-bass presence required",
                "max_sub_bass": 1.0,
                "min_warmth": 0.3
            },
            "trap_allow_softclip": {
                "type": "dynamics",
                "description": "Soft clipping allowed on master",
                "allowed_fx": ["soft_clip", "saturation"],
                "allow_hard_clip": False
            }
        }
    },
    
    "trap_soul": {
        "version": "1.0.0",
        "mandatory_patterns": {
            "trapsoul_smooth_hihat": {
                "type": "drum",
                "description": "Clean 8th note hi-hats, not dense 16ths",
                "density": "8th",
                "swing_percent": 0.08
            },
            "trapsoul_rhodes_chords": {
                "type": "melodic",
                "description": "Rhodes or piano chords for warmth"
            }
        },
        "forbidden_signatures": {
            "no_trap_hihat_rolls": {
                "description": "Trap-style hi-hat rolls break the smooth vibe",
                "severity": "error",
                "elements": ["hihat_roll", "hihat_triplet_roll"],
                "patterns": ["trap_hihat_16th"],
                "replacement": "standard_8th_hihat",
                "repair_action": "replace"
            },
            "no_aggressive_808": {
                "description": "Distorted 808s too harsh for trap soul",
                "severity": "warning",
                "elements": ["808_distorted", "808_aggressive"],
                "replacement": "808_clean",
                "repair_action": "replace"
            }
        },
        "mix_rules": {
            "trapsoul_warmth": {
                "type": "spectral",
                "description": "Warm, smooth character required",
                "min_warmth": 0.6,
                "max_brightness": 0.6
            }
        }
    },
    
    "boom_bap": {
        "version": "1.0.0",
        "mandatory_patterns": {
            "boom_bap_kick_placement": {
                "type": "drum",
                "description": "Classic boom bap kick pattern",
                "beats": [1.0, 2.5, 3.0],
                "swing_percent": 0.10
            },
            "boom_bap_snare_backbeat": {
                "type": "drum", 
                "description": "Snare on 2 and 4 (backbeat)",
                "beats": [2.0, 4.0],
                "velocity_range": [85, 110]
            },
            "boom_bap_mpc_swing": {
                "type": "rhythmic",
                "description": "MPC-style swing feel",
                "swing_percent": 0.10
            }
        },
        "forbidden_signatures": {
            "no_808_glide": {
                "description": "808 glides/slides are not authentic boom bap",
                "severity": "error",
                "elements": ["808_glide", "808_slide", "808_portamento"],
                "replacement": "bass_staccato",
                "repair_action": "replace"
            },
            "no_trap_hihat_rolls": {
                "description": "Dense trap rolls break the classic feel",
                "severity": "error",
                "elements": ["hihat_roll", "hihat_triplet_roll"],
                "patterns": ["trap_hihat_16th"],
                "repair_action": "remove"
            },
            "no_half_time_snare": {
                "description": "Boom bap uses full backbeat, not half-time",
                "severity": "warning",
                "patterns": ["half_time_snare"],
                "replacement": "backbeat_snare",
                "repair_action": "replace"
            }
        },
        "mix_rules": {
            "boom_bap_warmth": {
                "type": "spectral",
                "description": "Warm, vinyl character",
                "min_warmth": 0.65,
                "max_brightness": 0.55
            },
            "boom_bap_dynamics": {
                "type": "dynamics",
                "description": "SP-1200 style compression, not modern brickwall",
                "forbidden_fx": ["brickwall_limiter", "multiband_limit"],
                "allowed_fx": ["tape_saturation", "sp1200_crunch", "light_compression"],
                "min_dynamic_range_db": 6.0
            }
        }
    },
    
    "g_funk": {
        "version": "1.0.0",
        "mandatory_patterns": {
            "gfunk_swing_hihat": {
                "type": "drum",
                "description": "Swung 8th note hi-hats",
                "density": "8th",
                "swing_percent": 0.15
            },
            "gfunk_synth_lead": {
                "type": "melodic",
                "description": "Portamento synth lead characteristic of G-Funk"
            },
            "gfunk_funk_bass": {
                "type": "bass",
                "description": "Funk-style bass (not 808)"
            }
        },
        "forbidden_signatures": {
            "no_trap_hihat_rolls": {
                "description": "Trap hi-hat patterns break the funk groove",
                "severity": "error",
                "elements": ["hihat_roll", "hihat_triplet_roll"],
                "patterns": ["trap_hihat_16th"],
                "repair_action": "remove"
            },
            "no_distorted_808": {
                "description": "Distorted 808s not authentic G-Funk",
                "severity": "error",
                "elements": ["808_distorted", "808_aggressive", "808_trap"],
                "replacement": "clean_sine_bass",
                "repair_action": "replace"
            },
            "no_trap_snare": {
                "description": "Trap snares don't fit G-Funk aesthetic",
                "severity": "warning",
                "elements": ["trap_snare", "snap_snare"],
                "replacement": "funk_snare",
                "repair_action": "replace"
            }
        },
        "mix_rules": {
            "gfunk_warmth": {
                "type": "spectral",
                "description": "Warm, vintage character",
                "min_warmth": 0.7,
                "max_brightness": 0.65
            },
            "gfunk_stereo": {
                "type": "stereo",
                "description": "Wide stereo image for synths",
                "allowed_fx": ["stereo_width", "phaser", "chorus"]
            }
        }
    },
    
    "lofi": {
        "version": "1.0.0",
        "mandatory_patterns": {
            "lofi_swing": {
                "type": "rhythmic",
                "description": "Lazy swing feel",
                "swing_percent": 0.12
            },
            "lofi_dusty_texture": {
                "type": "texture",
                "description": "Vinyl crackle or tape noise required"
            }
        },
        "forbidden_signatures": {
            "no_trap_elements": {
                "description": "Dense trap patterns break the chill vibe",
                "severity": "error",
                "elements": ["hihat_roll", "hihat_triplet_roll", "trap_snare"],
                "patterns": ["trap_hihat_16th"],
                "repair_action": "remove"
            },
            "no_bright_synths": {
                "description": "Bright/harsh synths don't fit lo-fi aesthetic",
                "severity": "warning",
                "elements": ["synth_lead_bright", "supersaw"],
                "replacement": "rhodes",
                "repair_action": "replace"
            }
        },
        "mix_rules": {
            "lofi_no_brickwall": {
                "type": "dynamics",
                "description": "No harsh limiting - preserve dynamics",
                "forbidden_fx": ["brickwall_limiter", "multiband_limit"],
                "allowed_fx": ["tape_saturation", "light_compression", "vinyl_crackle"],
                "min_dynamic_range_db": 8.0
            },
            "lofi_character": {
                "type": "spectral",
                "description": "Warm, dark, filtered character",
                "min_warmth": 0.8,
                "max_brightness": 0.4
            }
        }
    },
    
    "house": {
        "version": "1.0.0",
        "mandatory_patterns": {
            "house_four_on_floor": {
                "type": "drum",
                "description": "4-on-the-floor kick pattern",
                "beats": [1.0, 2.0, 3.0, 4.0],
                "velocity_range": [100, 120]
            },
            "house_offbeat_hihat": {
                "type": "drum",
                "description": "Hi-hats on offbeats",
                "beats": [1.5, 2.5, 3.5, 4.5],
                "density": "8th_offbeat"
            },
            "house_clap_backbeat": {
                "type": "drum",
                "description": "Clap on 2 and 4",
                "beats": [2.0, 4.0]
            }
        },
        "forbidden_signatures": {
            "no_trap_elements": {
                "description": "Trap elements break the 4/4 groove",
                "severity": "error",
                "elements": ["808_trap", "trap_snare", "hihat_roll"],
                "repair_action": "remove"
            },
            "no_half_time": {
                "description": "Half-time feel breaks house energy",
                "severity": "error",
                "patterns": ["half_time_snare", "trap_half_time"],
                "repair_action": "remove"
            }
        },
        "mix_rules": {
            "house_sidechain": {
                "type": "dynamics",
                "description": "Sidechain compression for pumping effect",
                "allowed_fx": ["sidechain_duck", "sidechain_compression"]
            },
            "house_brightness": {
                "type": "spectral",
                "description": "Bright, energetic character",
                "max_brightness": 0.8
            }
        }
    },
    
    "drill": {
        "version": "1.0.0",
        "mandatory_patterns": {
            "drill_808_slides": {
                "type": "bass",
                "description": "808 slides are characteristic of drill"
            },
            "drill_half_time_snare": {
                "type": "drum",
                "description": "Half-time snare pattern",
                "beats": [3.0]
            }
        },
        "forbidden_signatures": {},
        "mix_rules": {
            "drill_sub_bass": {
                "type": "spectral",
                "description": "Heavy sub-bass presence",
                "max_sub_bass": 1.0
            },
            "drill_dark": {
                "type": "spectral",
                "description": "Dark, aggressive character",
                "max_brightness": 0.5
            }
        }
    },
    
    "rnb": {
        "version": "1.0.0",
        "mandatory_patterns": {
            "rnb_smooth_groove": {
                "type": "rhythmic",
                "description": "Smooth, laid-back groove",
                "swing_percent": 0.08
            }
        },
        "forbidden_signatures": {
            "no_dense_hihats": {
                "description": "Dense hi-hat patterns break the smooth vibe",
                "severity": "warning",
                "patterns": ["trap_hihat_16th"],
                "repair_action": "remove"
            },
            "no_distorted_808": {
                "description": "Distorted bass too harsh for R&B",
                "severity": "warning",
                "elements": ["808_distorted"],
                "replacement": "clean_bass",
                "repair_action": "replace"
            }
        },
        "mix_rules": {
            "rnb_warmth": {
                "type": "spectral",
                "description": "Warm, smooth character",
                "min_warmth": 0.75
            }
        }
    },
    
    "ethiopian_traditional": {
        "version": "1.0.0",
        "mandatory_patterns": {
            "ethiopian_kebero": {
                "type": "drum",
                "description": "Kebero drum patterns required"
            },
            "ethiopian_pentatonic": {
                "type": "harmonic",
                "description": "Ethiopian pentatonic modes (tizita, bati, etc.)"
            }
        },
        "forbidden_signatures": {
            "no_808": {
                "description": "808 bass not authentic for traditional Ethiopian",
                "severity": "error",
                "elements": ["808", "808_distorted", "808_clean"],
                "repair_action": "remove"
            },
            "no_synth_leads": {
                "description": "Modern synth leads break traditional feel",
                "severity": "warning",
                "elements": ["synth_lead", "synth_lead_bright"],
                "repair_action": "remove"
            }
        },
        "mix_rules": {
            "ethiopian_natural": {
                "type": "spectral",
                "description": "Natural, acoustic character",
                "min_warmth": 0.7
            }
        }
    },
    
    "eskista": {
        "version": "1.0.0",
        "mandatory_patterns": {
            "eskista_pulse": {
                "type": "rhythmic",
                "description": "Characteristic eskista dance rhythm"
            }
        },
        "forbidden_signatures": {
            "no_808": {
                "description": "808 not authentic for eskista",
                "severity": "error",
                "elements": ["808", "808_distorted"],
                "repair_action": "remove"
            }
        },
        "mix_rules": {}
    }
}


# =============================================================================
# GENRE RULES ENGINE
# =============================================================================

class GenreRulesEngine:
    """
    Engine for validating and enforcing genre-specific rules.
    
    This extends the existing genres.json with enforced constraints
    that prevent genre-breaking artifacts during generation.
    
    Usage:
        engine = GenreRulesEngine()
        
        # Validate elements before generation
        result = engine.validate_elements("trap", ["808", "kick"], ["hihat"])
        
        # Get mandatory patterns for a genre
        patterns = engine.get_mandatory_patterns("boom_bap")
        
        # Auto-repair violations
        repaired = engine.repair_violations("g_funk", ["808_distorted", "synth"])
    """
    
    def __init__(self, rules_path: Optional[Path] = None):
        """
        Initialize Genre Rules Engine.
        
        Args:
            rules_path: Optional path to custom rules JSON file.
                       Falls back to built-in defaults if not provided.
        """
        self._rules_path = rules_path
        self._rulesets: Dict[str, GenreRuleset] = {}
        self._load_rules()
    
    def _load_rules(self) -> None:
        """Load rules from file or use built-in defaults."""
        rules_data = DEFAULT_GENRE_RULES.copy()
        
        # Try to load custom rules file if provided
        if self._rules_path and self._rules_path.exists():
            try:
                with open(self._rules_path, 'r', encoding='utf-8') as f:
                    custom_rules = json.load(f)
                    
                # Merge custom rules (custom takes precedence)
                for genre, data in custom_rules.get("genres", {}).items():
                    rules_data[genre] = data
                    
                logger.info(f"Loaded custom genre rules from {self._rules_path}")
            except Exception as e:
                logger.warning(f"Failed to load custom rules: {e}")
        
        # Parse all rulesets
        for genre, data in rules_data.items():
            self._rulesets[genre] = GenreRuleset.from_dict(genre, data)
    
    # =========================================================================
    # PUBLIC API - Validation
    # =========================================================================
    
    def validate_elements(
        self,
        genre: str,
        instruments: List[str],
        drum_elements: List[str],
        patterns_used: Optional[List[str]] = None
    ) -> ValidationResult:
        """
        Validate instrument and drum choices against genre rules.
        
        Args:
            genre: Genre identifier
            instruments: List of instrument names
            drum_elements: List of drum element names
            patterns_used: Optional list of pattern types used
            
        Returns:
            ValidationResult with violations, warnings, and repair suggestions
        """
        result = ValidationResult(genre=genre, valid=True)
        
        ruleset = self._rulesets.get(genre)
        if not ruleset:
            # No rules for this genre - allow everything (fallback behavior)
            result.rule_decisions.append({
                "type": "no_rules",
                "message": f"No rules defined for genre '{genre}', using defaults"
            })
            return result
        
        all_elements = set(instruments + drum_elements)
        patterns = set(patterns_used or [])
        
        # Check forbidden signatures
        for sig_id, signature in ruleset.forbidden_signatures.items():
            violation = self._check_forbidden_signature(signature, all_elements, patterns)
            if violation:
                result.violations.append(violation)
                result.forbidden_used.extend(violation.elements_involved)
                
                if violation.severity == RuleSeverity.ERROR:
                    result.valid = False
                    
                result.rule_decisions.append({
                    "type": "forbidden_violation",
                    "rule_id": sig_id,
                    "elements": violation.elements_involved,
                    "repair": violation.repair_suggestion
                })
        
        # Check mandatory patterns
        for pattern_name, pattern in ruleset.mandatory_patterns.items():
            if not self._is_pattern_satisfied(pattern, all_elements, patterns):
                violation = RuleViolation(
                    rule_id=pattern_name,
                    rule_type="missing_mandatory",
                    severity=RuleSeverity.WARNING,
                    message=f"Missing mandatory pattern: {pattern.description}",
                    elements_involved=[pattern_name],
                    repair_suggestion=f"Add {pattern.type.value} pattern: {pattern_name}"
                )
                result.violations.append(violation)
                result.mandatory_missing.append(pattern_name)
                
                result.rule_decisions.append({
                    "type": "mandatory_missing",
                    "pattern": pattern_name,
                    "description": pattern.description
                })
        
        return result
    
    def validate_mix_settings(
        self,
        genre: str,
        fx_chain: List[str],
        spectral_profile: Optional[Dict[str, float]] = None
    ) -> ValidationResult:
        """
        Validate mix/FX settings against genre mix rules.
        
        Args:
            genre: Genre identifier
            fx_chain: List of FX in the chain
            spectral_profile: Optional spectral characteristics
            
        Returns:
            ValidationResult for mix-specific rules
        """
        result = ValidationResult(genre=genre, valid=True)
        
        ruleset = self._rulesets.get(genre)
        if not ruleset:
            return result
        
        fx_set = set(fx_chain)
        
        for rule_id, rule in ruleset.mix_rules.items():
            # Check forbidden FX
            forbidden_used = fx_set.intersection(rule.forbidden_fx)
            if forbidden_used:
                violation = RuleViolation(
                    rule_id=rule_id,
                    rule_type="mix_rule",
                    severity=RuleSeverity.WARNING,
                    message=f"FX '{', '.join(forbidden_used)}' not recommended for {genre}",
                    elements_involved=list(forbidden_used),
                    repair_suggestion=f"Consider using: {', '.join(rule.allowed_fx)}"
                )
                result.violations.append(violation)
                result.mix_violations.append(rule_id)
            
            # Check spectral constraints
            if spectral_profile and rule.type == MixRuleType.SPECTRAL:
                brightness = spectral_profile.get('brightness', 0.5)
                warmth = spectral_profile.get('warmth', 0.5)
                
                if brightness > rule.max_brightness:
                    result.warnings.append(
                        f"Brightness ({brightness:.2f}) exceeds recommended max ({rule.max_brightness:.2f}) for {genre}"
                    )
                
                if warmth < rule.min_warmth:
                    result.warnings.append(
                        f"Warmth ({warmth:.2f}) below recommended min ({rule.min_warmth:.2f}) for {genre}"
                    )
        
        return result
    
    # =========================================================================
    # PUBLIC API - Pattern Queries
    # =========================================================================
    
    def get_mandatory_patterns(self, genre: str) -> List[PatternSpec]:
        """Get all mandatory patterns for a genre."""
        ruleset = self._rulesets.get(genre)
        if not ruleset:
            return []
        return list(ruleset.mandatory_patterns.values())
    
    def get_forbidden_elements(self, genre: str) -> Set[str]:
        """Get all forbidden elements for a genre."""
        ruleset = self._rulesets.get(genre)
        if not ruleset:
            return set()
        return ruleset._forbidden_elements.copy()
    
    def get_forbidden_signatures(self, genre: str) -> List[ForbiddenSignature]:
        """Get all forbidden signature rules for a genre."""
        ruleset = self._rulesets.get(genre)
        if not ruleset:
            return []
        return list(ruleset.forbidden_signatures.values())
    
    def get_mix_rules(self, genre: str) -> List[MixRule]:
        """Get all mix rules for a genre."""
        ruleset = self._rulesets.get(genre)
        if not ruleset:
            return []
        return list(ruleset.mix_rules.values())
    
    def is_element_forbidden(self, genre: str, element: str) -> Tuple[bool, Optional[str]]:
        """
        Check if a specific element is forbidden.
        
        Returns:
            Tuple of (is_forbidden, replacement_suggestion)
        """
        ruleset = self._rulesets.get(genre)
        if not ruleset:
            return (False, None)
        
        for signature in ruleset.forbidden_signatures.values():
            if element in signature.elements:
                return (True, signature.replacement)
        
        return (False, None)
    
    # =========================================================================
    # PUBLIC API - Auto-Repair
    # =========================================================================
    
    def repair_violations(
        self,
        genre: str,
        elements: List[str],
        auto_repair: bool = True
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Auto-repair elements that violate genre rules.
        
        Args:
            genre: Genre identifier
            elements: List of elements to check/repair
            auto_repair: If True, apply repairs; if False, only report
            
        Returns:
            Tuple of (repaired_elements, repair_log)
        """
        repair_log = []
        result_elements = elements.copy()
        
        ruleset = self._rulesets.get(genre)
        if not ruleset:
            return (result_elements, repair_log)
        
        for signature in ruleset.forbidden_signatures.values():
            for i, element in enumerate(result_elements):
                if element in signature.elements:
                    repair_entry = {
                        "original": element,
                        "rule_id": signature.id,
                        "reason": signature.description,
                        "action": signature.repair_action
                    }
                    
                    if auto_repair:
                        if signature.repair_action == "remove":
                            result_elements[i] = None  # Mark for removal
                            repair_entry["result"] = "removed"
                        elif signature.repair_action == "replace" and signature.replacement:
                            result_elements[i] = signature.replacement
                            repair_entry["result"] = signature.replacement
                        else:
                            repair_entry["result"] = "no_repair_available"
                    else:
                        repair_entry["suggestion"] = signature.replacement or "remove"
                    
                    repair_log.append(repair_entry)
        
        # Remove None entries
        result_elements = [e for e in result_elements if e is not None]
        
        return (result_elements, repair_log)
    
    def suggest_additions(self, genre: str, current_elements: List[str]) -> List[str]:
        """
        Suggest elements to add based on mandatory patterns.
        
        Args:
            genre: Genre identifier
            current_elements: Current element list
            
        Returns:
            List of suggested additions
        """
        suggestions = []
        ruleset = self._rulesets.get(genre)
        
        if not ruleset:
            return suggestions
        
        current_set = set(current_elements)
        
        for pattern in ruleset.mandatory_patterns.values():
            # If pattern has associated element requirements
            if pattern.type == PatternType.DRUM:
                if pattern.density == "16th" and "hihat" not in current_set:
                    suggestions.append("hihat")
            elif pattern.type == PatternType.BASS:
                if "808" not in current_set and "bass" not in current_set:
                    suggestions.append("808" if "808" not in ruleset._forbidden_elements else "bass")
        
        return list(set(suggestions))
    
    # =========================================================================
    # PUBLIC API - Export
    # =========================================================================
    
    def get_all_genres(self) -> List[str]:
        """Get list of all genres with rules defined."""
        return list(self._rulesets.keys())
    
    def get_ruleset(self, genre: str) -> Optional[GenreRuleset]:
        """Get complete ruleset for a genre."""
        return self._rulesets.get(genre)
    
    def to_dict(self) -> Dict:
        """Export all rules as dictionary."""
        return {
            genre: ruleset.to_dict()
            for genre, ruleset in self._rulesets.items()
        }
    
    def to_json(self, pretty: bool = False) -> str:
        """Export all rules as JSON string."""
        if pretty:
            return json.dumps(self.to_dict(), indent=2)
        return json.dumps(self.to_dict(), separators=(',', ':'))
    
    # =========================================================================
    # PRIVATE METHODS
    # =========================================================================
    
    def _check_forbidden_signature(
        self,
        signature: ForbiddenSignature,
        elements: Set[str],
        patterns: Set[str]
    ) -> Optional[RuleViolation]:
        """Check if a forbidden signature is triggered."""
        triggered_by = []
        
        # Check individual elements
        for elem in signature.elements:
            if elem in elements:
                triggered_by.append(elem)
        
        # Check patterns
        for pattern in signature.patterns:
            if pattern in patterns:
                triggered_by.append(pattern)
        
        # Check combinations (all elements in combo must be present)
        for combo in signature.combinations:
            if all(c in elements for c in combo):
                triggered_by.extend(combo)
        
        if triggered_by:
            return RuleViolation(
                rule_id=signature.id,
                rule_type="forbidden_signature",
                severity=signature.severity,
                message=signature.description,
                elements_involved=list(set(triggered_by)),
                repair_suggestion=signature.replacement
            )
        
        return None
    
    def _is_pattern_satisfied(
        self,
        pattern: PatternSpec,
        elements: Set[str],
        patterns: Set[str]
    ) -> bool:
        """
        Check if a mandatory pattern is satisfied.
        
        This is a heuristic check - actual pattern validation
        happens in the MIDI generator.
        """
        # For now, we do basic element presence checks
        # More sophisticated pattern matching can be added later
        
        if pattern.type == PatternType.DRUM:
            if pattern.density == "16th":
                return "hihat" in elements
            elif pattern.density == "8th":
                return "hihat" in elements
            return True
            
        elif pattern.type == PatternType.BASS:
            return any(b in elements for b in ["808", "bass", "synth_bass"])
            
        elif pattern.type == PatternType.MELODIC:
            melodic_instruments = ["piano", "rhodes", "synth", "synth_lead", "keys", "guitar", "strings"]
            return any(m in elements for m in melodic_instruments)
            
        elif pattern.type == PatternType.TEXTURE:
            texture_elements = ["vinyl_crackle", "tape_hiss", "rain", "ambient"]
            return any(t in elements for t in texture_elements)
        
        # Default: consider satisfied
        return True


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_genre_rules_engine: Optional[GenreRulesEngine] = None


def get_genre_rules() -> GenreRulesEngine:
    """Get or create the global GenreRulesEngine instance."""
    global _genre_rules_engine
    if _genre_rules_engine is None:
        _genre_rules_engine = GenreRulesEngine()
    return _genre_rules_engine


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def validate_generation(
    genre: str,
    instruments: List[str],
    drums: List[str],
    patterns: Optional[List[str]] = None
) -> ValidationResult:
    """Validate generation elements (convenience function)."""
    return get_genre_rules().validate_elements(genre, instruments, drums, patterns)


def repair_violations(
    genre: str,
    elements: List[str]
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Auto-repair element violations (convenience function)."""
    return get_genre_rules().repair_violations(genre, elements)


def is_forbidden(genre: str, element: str) -> bool:
    """Check if element is forbidden (convenience function)."""
    forbidden, _ = get_genre_rules().is_element_forbidden(genre, element)
    return forbidden


def get_mandatory_patterns(genre: str) -> List[PatternSpec]:
    """Get mandatory patterns (convenience function)."""
    return get_genre_rules().get_mandatory_patterns(genre)


# =============================================================================
# CLI TESTING
# =============================================================================

if __name__ == "__main__":
    import sys
    
    engine = GenreRulesEngine()
    
    print("🎵 Genre Rules DSL v2 Engine")
    print("=" * 60)
    print(f"Loaded rules for {len(engine.get_all_genres())} genres:")
    
    for genre in engine.get_all_genres():
        ruleset = engine.get_ruleset(genre)
        print(f"\n  [{genre}]")
        print(f"    Mandatory patterns: {len(ruleset.mandatory_patterns)}")
        print(f"    Forbidden signatures: {len(ruleset.forbidden_signatures)}")
        print(f"    Mix rules: {len(ruleset.mix_rules)}")
        
        if ruleset.forbidden_signatures:
            forbidden = engine.get_forbidden_elements(genre)
            print(f"    Forbidden elements: {', '.join(forbidden) if forbidden else 'none'}")
    
    print("\n" + "=" * 60)
    print("\n🔍 Validation Examples:\n")
    
    # Test 1: G-Funk with trap elements (should fail)
    print("Test 1: G-Funk with hi-hat rolls")
    result = engine.validate_elements("g_funk", ["synth", "bass"], ["hihat_roll", "kick"])
    print(f"  Valid: {result.valid}")
    for v in result.violations:
        print(f"  ⚠️  {v.message}")
        if v.repair_suggestion:
            print(f"     → Repair: {v.repair_suggestion}")
    
    # Test 2: Boom bap with 808 glide (should fail)
    print("\nTest 2: Boom bap with 808 glide")
    result = engine.validate_elements("boom_bap", ["808_glide", "piano"], ["kick", "snare"])
    print(f"  Valid: {result.valid}")
    for v in result.violations:
        print(f"  ⚠️  {v.message}")
    
    # Test 3: Auto-repair
    print("\nTest 3: Auto-repair g_funk elements")
    elements = ["808_distorted", "synth", "trap_snare", "piano"]
    repaired, log = engine.repair_violations("g_funk", elements)
    print(f"  Original: {elements}")
    print(f"  Repaired: {repaired}")
    for entry in log:
        print(f"  📝 {entry['original']} → {entry.get('result', 'N/A')} ({entry['reason']})")
    
    # Test 4: Lo-fi mix validation
    print("\nTest 4: Lo-fi mix rule validation")
    result = engine.validate_mix_settings(
        "lofi",
        ["brickwall_limiter", "vinyl_crackle"],
        {"brightness": 0.6, "warmth": 0.5}
    )
    print(f"  Valid: {result.valid}")
    for v in result.violations:
        print(f"  ⚠️  {v.message}")
    for w in result.warnings:
        print(f"  💡 {w}")
    
    print("\n✅ Genre Rules DSL v2 loaded successfully!")
