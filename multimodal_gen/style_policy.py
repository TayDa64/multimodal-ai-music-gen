"""
Style Policy Module - "Producer Brain" Decision Layer

This module provides a unified policy layer that makes coherent musical decisions
based on genre rules, groove templates, prompt parsing, and production standards.

The StylePolicy acts as a "producer brain" that:
1. Consolidates rules from GenreRulesEngine, GrooveTemplates, and prompt parsing
2. Resolves conflicts between competing rules with clear precedence
3. Produces a JSON-able "decision record" explaining why choices were made
4. Provides the canonical policy context consumed by generators

Industry Reference:
- Logic Pro's "Drummer" track: genre-aware beat generation with explainable controls
- Splice's "Sounds" AI: intent-based instrument selection with coherent styling
- iZotope's Assistant: context-aware mixing decisions with transparency

Architecture:
    ParsedPrompt -> StylePolicy.compile() -> PolicyContext
                       |
                       v
            [GenreRulesEngine, GrooveTemplates, HumanizeConfig]
                       |
                       v
                DecisionRecord (JSON-able, UI-displayable)

Usage:
    from multimodal_gen.style_policy import StylePolicy, compile_policy
    
    # Quick compile from prompt
    policy_context = compile_policy(parsed_prompt)
    
    # Or with more control
    policy = StylePolicy()
    policy_context = policy.compile(parsed_prompt)
    
    # Access decisions for UI
    decisions_json = policy_context.to_decision_record()
    
    # Use in generators
    midi_generator.generate(arrangement, parsed, policy_context=policy_context)
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Tuple, Set
from enum import Enum
import logging

logger = logging.getLogger(__name__)

# Import dependencies
from .utils import ScaleType, TICKS_PER_BEAT, TICKS_PER_16TH
from .prompt_parser import ParsedPrompt
from .genre_rules import GenreRulesEngine, get_genre_rules, RuleSeverity
from .groove_templates import GrooveTemplate, get_groove_for_genre

try:
    from .humanize_physics import HumanizeConfig, PhysicsHumanizer
    HAS_PHYSICS = True
except ImportError:
    HAS_PHYSICS = False
    HumanizeConfig = None

# Optional genre DNA for continuous genre dimension overlay (Sprint 5)
try:
    from multimodal_gen.intelligence.genre_dna import get_genre_dna, GenreDNAVector
    _HAS_GENRE_DNA = True
except ImportError:
    _HAS_GENRE_DNA = False


# =============================================================================
# ENUMERATIONS
# =============================================================================

class DecisionSource(Enum):
    """Source of a policy decision for transparency."""
    PROMPT = "prompt"                    # User explicitly requested
    GENRE_RULE = "genre_rule"           # GenreRulesEngine mandatory/forbidden
    GROOVE_TEMPLATE = "groove_template"  # Groove template default
    DEFAULT = "default"                  # Fallback/system default
    CONFLICT_RESOLUTION = "conflict"     # Resolved from competing sources
    PHYSICS_MODEL = "physics_model"      # From humanize_physics
    

class TimingFeel(Enum):
    """Micro-timing feel categories."""
    STRAIGHT = "straight"      # Quantized, no swing
    LIGHT_SWING = "light"      # 5-10% swing
    MEDIUM_SWING = "medium"    # 15-25% swing
    HEAVY_SWING = "heavy"      # 30-50% swing (triplet feel)
    DRUNK = "drunk"            # Randomized timing (lo-fi, J Dilla)
    PUSH = "push"              # Slightly ahead of beat (energetic)
    LAY_BACK = "lay_back"      # Slightly behind beat (relaxed)


class VoicingStyle(Enum):
    """Chord voicing styles."""
    TIGHT = "tight"            # Close voicings, minimal spread
    OPEN = "open"              # Wide voicings, spread across octaves
    DROP_2 = "drop_2"          # Jazz drop-2 voicings
    SHELL = "shell"            # Root + 3rd + 7th only
    POWER = "power"            # Root + 5th only
    EXTENDED = "extended"      # 9ths, 11ths, 13ths


class ArrangementDensity(Enum):
    """Arrangement density for fills/transitions."""
    MINIMAL = "minimal"        # Very few fills, sparse
    LIGHT = "light"            # Subtle fills at section boundaries
    MODERATE = "moderate"      # Standard pop/hip-hop density
    BUSY = "busy"              # Frequent fills and variations
    MAXIMAL = "maximal"        # Dense, constant variation


# =============================================================================
# POLICY DECISIONS (Individual Decision Records)
# =============================================================================

@dataclass
class PolicyDecision:
    """A single policy decision with provenance."""
    category: str              # e.g., "timing", "voicing", "dynamics"
    name: str                  # e.g., "swing_amount", "snare_position"
    value: Any                 # The actual value
    source: DecisionSource     # Where this came from
    confidence: float = 1.0    # 0-1, how confident in this decision
    reason: str = ""           # Human-readable explanation
    alternatives: List[Any] = field(default_factory=list)  # Other considered values
    
    def to_dict(self) -> Dict:
        return {
            "category": self.category,
            "name": self.name,
            "value": self.value if not isinstance(self.value, Enum) else self.value.value,
            "source": self.source.value,
            "confidence": self.confidence,
            "reason": self.reason,
            "alternatives": self.alternatives
        }


# =============================================================================
# POLICY CONTEXT (Complete Policy Output)
# =============================================================================

@dataclass
class TimingPolicy:
    """Timing/rhythm policy decisions."""
    feel: TimingFeel = TimingFeel.STRAIGHT
    swing_amount: float = 0.0
    
    # Per-element timing offsets (ticks, positive = late)
    snare_offset: int = 0      # Snare relative to grid
    kick_offset: int = 0       # Kick relative to grid
    hihat_offset: int = 0      # Hi-hat relative to grid
    bass_offset: int = 0       # Bass relative to grid
    
    # Genre-specific timing ranges
    snare_late_range: Tuple[int, int] = (0, 0)  # (min, max) ticks late
    push_pull_strength: float = 0.0  # -1 (push) to +1 (lay back)
    
    # Jitter/humanization
    timing_jitter: float = 0.02  # Fraction of 16th note
    velocity_variation: float = 0.12  # Fraction of velocity
    
    def to_dict(self) -> Dict:
        return {
            "feel": self.feel.value,
            "swing_amount": self.swing_amount,
            "snare_offset": self.snare_offset,
            "kick_offset": self.kick_offset,
            "hihat_offset": self.hihat_offset,
            "bass_offset": self.bass_offset,
            "snare_late_range": self.snare_late_range,
            "push_pull_strength": self.push_pull_strength,
            "timing_jitter": self.timing_jitter,
            "velocity_variation": self.velocity_variation
        }


@dataclass
class VoicingPolicy:
    """Chord voicing and harmonic policy."""
    style: VoicingStyle = VoicingStyle.OPEN
    
    # Chord complexity
    max_extensions: int = 9    # Highest extension (7, 9, 11, 13)
    use_alterations: bool = False  # b9, #9, #11, etc.
    use_suspensions: bool = True   # sus2, sus4
    
    # Voicing rules
    bass_octave: int = 2       # MIDI octave for bass notes
    chord_octave: int = 4      # MIDI octave for chord roots
    spread_octaves: int = 1    # How many octaves to spread voicings
    
    # Genre-specific
    parallel_motion: bool = True   # Allow parallel 5ths/octaves
    voice_leading: bool = True     # Smooth voice leading
    
    def to_dict(self) -> Dict:
        return {
            "style": self.style.value,
            "max_extensions": self.max_extensions,
            "use_alterations": self.use_alterations,
            "use_suspensions": self.use_suspensions,
            "bass_octave": self.bass_octave,
            "chord_octave": self.chord_octave,
            "spread_octaves": self.spread_octaves,
            "parallel_motion": self.parallel_motion,
            "voice_leading": self.voice_leading
        }


@dataclass
class DynamicsPolicy:
    """Dynamics and velocity policy."""
    # Velocity ranges by element
    kick_velocity_range: Tuple[int, int] = (90, 120)
    snare_velocity_range: Tuple[int, int] = (85, 115)
    hihat_velocity_range: Tuple[int, int] = (60, 100)
    bass_velocity_range: Tuple[int, int] = (80, 110)
    chord_velocity_range: Tuple[int, int] = (60, 90)
    
    # Accent patterns (beat positions 1-indexed)
    accent_beats: List[float] = field(default_factory=lambda: [1.0, 3.0])
    accent_strength: float = 0.15  # Velocity boost for accents
    
    # Compression behavior hints
    use_sidechain: bool = False
    sidechain_amount: float = 0.3  # 0-1 ducking depth
    sidechain_trigger: str = "kick"  # What triggers sidechain
    
    # Ghost notes
    ghost_note_probability: float = 0.3
    ghost_note_velocity_factor: float = 0.35  # Relative to main hits
    
    def to_dict(self) -> Dict:
        return {
            "kick_velocity_range": self.kick_velocity_range,
            "snare_velocity_range": self.snare_velocity_range,
            "hihat_velocity_range": self.hihat_velocity_range,
            "bass_velocity_range": self.bass_velocity_range,
            "chord_velocity_range": self.chord_velocity_range,
            "accent_beats": self.accent_beats,
            "accent_strength": self.accent_strength,
            "use_sidechain": self.use_sidechain,
            "sidechain_amount": self.sidechain_amount,
            "sidechain_trigger": self.sidechain_trigger,
            "ghost_note_probability": self.ghost_note_probability,
            "ghost_note_velocity_factor": self.ghost_note_velocity_factor
        }


@dataclass
class ArrangementPolicy:
    """Arrangement structure policy."""
    density: ArrangementDensity = ArrangementDensity.MODERATE
    
    # Fill placement
    fill_frequency_bars: int = 8  # Add fill every N bars
    fill_intensity: float = 0.5   # 0-1, how dramatic fills are
    
    # Transitions
    transition_type: str = "standard"  # "standard", "breakdown", "buildup", "drop"
    use_dropouts: bool = True         # Momentary silence for impact
    dropout_probability: float = 0.1
    
    # Section behavior
    double_up_bars: int = 4   # Vary pattern every N bars
    variation_intensity: float = 0.3  # How different variations are
    
    # Instrumentation mutations
    allow_instrument_drops: bool = True  # Can drop instruments at sections
    allow_texture_layers: bool = True    # Can add ambient layers
    
    def to_dict(self) -> Dict:
        return {
            "density": self.density.value,
            "fill_frequency_bars": self.fill_frequency_bars,
            "fill_intensity": self.fill_intensity,
            "transition_type": self.transition_type,
            "use_dropouts": self.use_dropouts,
            "dropout_probability": self.dropout_probability,
            "double_up_bars": self.double_up_bars,
            "variation_intensity": self.variation_intensity,
            "allow_instrument_drops": self.allow_instrument_drops,
            "allow_texture_layers": self.allow_texture_layers
        }


@dataclass
class MixPolicy:
    """Mix and mastering policy."""
    # Spectral balance targets
    sub_bass_target: float = 0.5   # 0-1, sub-bass presence
    brightness_target: float = 0.5  # 0-1, high frequency presence
    warmth_target: float = 0.5      # 0-1, low-mid warmth
    
    # Stereo field
    kick_pan: float = 0.0      # -1 to 1
    snare_pan: float = 0.0
    hihat_pan: float = 0.0
    bass_pan: float = 0.0
    
    # Headroom
    stem_headroom_db: float = -6.0
    master_ceiling_db: float = -1.0
    
    # FX chain recommendations (ordered)
    master_fx_chain: List[str] = field(default_factory=lambda: ["eq", "compressor", "limiter"])
    drum_bus_fx: List[str] = field(default_factory=lambda: ["eq", "compressor", "saturation"])
    bass_fx: List[str] = field(default_factory=lambda: ["eq", "compressor"])
    
    # Saturation character
    saturation_type: str = "tape"  # "tape", "tube", "transistor", "digital"
    saturation_amount: float = 0.2
    
    def to_dict(self) -> Dict:
        return {
            "sub_bass_target": self.sub_bass_target,
            "brightness_target": self.brightness_target,
            "warmth_target": self.warmth_target,
            "kick_pan": self.kick_pan,
            "snare_pan": self.snare_pan,
            "hihat_pan": self.hihat_pan,
            "bass_pan": self.bass_pan,
            "stem_headroom_db": self.stem_headroom_db,
            "master_ceiling_db": self.master_ceiling_db,
            "master_fx_chain": self.master_fx_chain,
            "drum_bus_fx": self.drum_bus_fx,
            "bass_fx": self.bass_fx,
            "saturation_type": self.saturation_type,
            "saturation_amount": self.saturation_amount
        }


@dataclass
class InstrumentPolicy:
    """Instrumentation constraint policy."""
    # Required instruments (from genre rules)
    required_instruments: List[str] = field(default_factory=list)
    
    # Forbidden instruments (from genre rules)
    forbidden_instruments: List[str] = field(default_factory=list)
    
    # Role assignments (instrument -> role)
    role_assignments: Dict[str, str] = field(default_factory=dict)
    # e.g., {"808": "bass", "piano": "chords", "synth": "lead"}
    
    # Frequency mutex (instruments that can't coexist in same range)
    low_end_mutex: List[str] = field(default_factory=lambda: ["808", "bass", "sub"])
    
    # Instrument selection hints for asset resolver
    preferred_tags: List[str] = field(default_factory=list)  # ["vintage", "warm", "dusty"]
    
    def to_dict(self) -> Dict:
        return {
            "required_instruments": self.required_instruments,
            "forbidden_instruments": self.forbidden_instruments,
            "role_assignments": self.role_assignments,
            "low_end_mutex": self.low_end_mutex,
            "preferred_tags": self.preferred_tags
        }


@dataclass
class PolicyContext:
    """
    Complete policy context for a generation.
    
    This is the main output of StylePolicy.compile() and should be
    consumed by all downstream generators.
    """
    # Source info
    genre: str
    bpm: float
    key: str
    scale_type: ScaleType
    mood: str
    energy: str
    
    # Sub-policies
    timing: TimingPolicy = field(default_factory=TimingPolicy)
    voicing: VoicingPolicy = field(default_factory=VoicingPolicy)
    dynamics: DynamicsPolicy = field(default_factory=DynamicsPolicy)
    arrangement: ArrangementPolicy = field(default_factory=ArrangementPolicy)
    mix: MixPolicy = field(default_factory=MixPolicy)
    instruments: InstrumentPolicy = field(default_factory=InstrumentPolicy)
    
    # Physics humanization config (if available)
    humanize_config: Optional[Any] = None  # HumanizeConfig
    
    # Decision log for transparency
    decisions: List[PolicyDecision] = field(default_factory=list)
    
    # Validation status
    genre_rules_applied: bool = False
    violations_auto_repaired: int = 0
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "genre": self.genre,
            "bpm": self.bpm,
            "key": self.key,
            "scale_type": self.scale_type.value if hasattr(self.scale_type, 'value') else str(self.scale_type),
            "mood": self.mood,
            "energy": self.energy,
            "timing": self.timing.to_dict(),
            "voicing": self.voicing.to_dict(),
            "dynamics": self.dynamics.to_dict(),
            "arrangement": self.arrangement.to_dict(),
            "mix": self.mix.to_dict(),
            "instruments": self.instruments.to_dict(),
            "genre_rules_applied": self.genre_rules_applied,
            "violations_auto_repaired": self.violations_auto_repaired,
            "warnings": self.warnings
        }
    
    def to_decision_record(self) -> Dict:
        """
        Get a human-readable decision record for UI display.
        
        This explains WHY each major decision was made, which is
        crucial for user trust and adjustability.
        """
        return {
            "summary": {
                "genre": self.genre,
                "total_decisions": len(self.decisions),
                "rules_applied": self.genre_rules_applied,
                "auto_repairs": self.violations_auto_repaired
            },
            "decisions": [d.to_dict() for d in self.decisions],
            "warnings": self.warnings
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


# =============================================================================
# GENRE POLICY PRESETS
# =============================================================================

GENRE_TIMING_PRESETS: Dict[str, Dict] = {
    "trap": {
        "feel": TimingFeel.STRAIGHT,
        "swing_amount": 0.0,
        "snare_late_range": (0, 10),  # Slightly late snare allowed
        "timing_jitter": 0.01,  # Very tight
    },
    "trap_soul": {
        "feel": TimingFeel.LIGHT_SWING,
        "swing_amount": 0.08,
        "snare_late_range": (5, 20),
        "timing_jitter": 0.02,
    },
    "boom_bap": {
        "feel": TimingFeel.MEDIUM_SWING,
        "swing_amount": 0.18,
        "snare_late_range": (10, 30),  # Classic "late snare"
        "timing_jitter": 0.03,
    },
    "g_funk": {
        "feel": TimingFeel.LIGHT_SWING,
        "swing_amount": 0.12,
        "snare_late_range": (5, 15),
        "timing_jitter": 0.025,
    },
    "lofi": {
        "feel": TimingFeel.DRUNK,
        "swing_amount": 0.15,
        "snare_late_range": (15, 40),  # Very loose
        "timing_jitter": 0.05,  # High jitter for lo-fi feel
    },
    "house": {
        "feel": TimingFeel.STRAIGHT,
        "swing_amount": 0.0,
        "snare_late_range": (0, 5),
        "timing_jitter": 0.01,
    },
    "rnb": {
        "feel": TimingFeel.LAY_BACK,
        "swing_amount": 0.10,
        "snare_late_range": (10, 25),
        "push_pull_strength": 0.2,  # Slightly laid back
        "timing_jitter": 0.03,
    },
    "eskista": {
        "feel": TimingFeel.PUSH,
        "swing_amount": 0.05,
        "snare_late_range": (0, 10),
        "push_pull_strength": -0.15,  # Pushed forward for energy
        "timing_jitter": 0.02,
    },
    "default": {
        "feel": TimingFeel.STRAIGHT,
        "swing_amount": 0.0,
        "snare_late_range": (0, 15),
        "timing_jitter": 0.02,
    }
}

GENRE_VOICING_PRESETS: Dict[str, Dict] = {
    "trap": {
        "style": VoicingStyle.POWER,
        "max_extensions": 7,
        "use_suspensions": False,
    },
    "trap_soul": {
        "style": VoicingStyle.EXTENDED,
        "max_extensions": 11,
        "use_alterations": True,
        "use_suspensions": True,
    },
    "boom_bap": {
        "style": VoicingStyle.OPEN,
        "max_extensions": 9,
        "use_suspensions": True,
    },
    "g_funk": {
        "style": VoicingStyle.EXTENDED,
        "max_extensions": 11,
        "use_suspensions": True,
    },
    "lofi": {
        "style": VoicingStyle.EXTENDED,
        "max_extensions": 13,
        "use_alterations": True,
    },
    "house": {
        "style": VoicingStyle.TIGHT,
        "max_extensions": 7,
    },
    "rnb": {
        "style": VoicingStyle.EXTENDED,
        "max_extensions": 13,
        "use_alterations": True,
        "use_suspensions": True,
    },
    "default": {
        "style": VoicingStyle.OPEN,
        "max_extensions": 9,
    }
}

GENRE_DYNAMICS_PRESETS: Dict[str, Dict] = {
    "trap": {
        "kick_velocity_range": (100, 127),
        "snare_velocity_range": (90, 120),
        "ghost_note_probability": 0.15,
        "use_sidechain": True,
        "sidechain_amount": 0.4,
    },
    "boom_bap": {
        "kick_velocity_range": (90, 115),
        "snare_velocity_range": (85, 110),
        "ghost_note_probability": 0.45,
        "use_sidechain": False,
    },
    "g_funk": {
        "kick_velocity_range": (85, 110),
        "snare_velocity_range": (80, 105),
        "ghost_note_probability": 0.35,
        "use_sidechain": True,
        "sidechain_amount": 0.25,
    },
    "lofi": {
        "kick_velocity_range": (70, 95),
        "snare_velocity_range": (65, 90),
        "ghost_note_probability": 0.5,
        "use_sidechain": False,
    },
    "default": {
        "ghost_note_probability": 0.3,
    }
}

GENRE_MIX_PRESETS: Dict[str, Dict] = {
    "trap": {
        "sub_bass_target": 0.8,
        "brightness_target": 0.6,
        "saturation_type": "digital",
        "saturation_amount": 0.1,
        "drum_bus_fx": ["eq", "compressor", "saturation", "limiter"],
    },
    "boom_bap": {
        "sub_bass_target": 0.5,
        "brightness_target": 0.4,
        "warmth_target": 0.7,
        "saturation_type": "tape",
        "saturation_amount": 0.3,
    },
    "g_funk": {
        "sub_bass_target": 0.7,
        "brightness_target": 0.5,
        "warmth_target": 0.6,
        "saturation_type": "tube",
        "saturation_amount": 0.25,
    },
    "lofi": {
        "sub_bass_target": 0.4,
        "brightness_target": 0.3,
        "warmth_target": 0.8,
        "saturation_type": "tape",
        "saturation_amount": 0.4,
        "drum_bus_fx": ["eq", "compressor", "saturation", "lofi_filter"],
    },
    "default": {
        "saturation_type": "tape",
        "saturation_amount": 0.2,
    }
}


# =============================================================================
# STYLE POLICY ENGINE
# =============================================================================

class StylePolicy:
    """
    Producer brain - makes coherent musical decisions.
    
    Compiles ParsedPrompt + GenreRules + GrooveTemplates into
    a unified PolicyContext with full transparency.
    """
    
    def __init__(self):
        self._genre_engine: Optional[GenreRulesEngine] = None
    
    @property
    def genre_engine(self) -> GenreRulesEngine:
        """Lazy-load genre rules engine."""
        if self._genre_engine is None:
            self._genre_engine = get_genre_rules()
        return self._genre_engine
    
    def compile(self, parsed: ParsedPrompt) -> PolicyContext:
        """
        Compile a complete PolicyContext from a parsed prompt.
        
        This is the main entry point for the style policy system.
        
        Args:
            parsed: ParsedPrompt from prompt_parser
            
        Returns:
            PolicyContext with all decisions and explanations
        """
        genre = (parsed.genre or '').lower().replace("-", "_").replace(" ", "_")
        
        # Initialize context
        ctx = PolicyContext(
            genre=genre,
            bpm=parsed.bpm,
            key=parsed.key,
            scale_type=parsed.scale_type,
            mood=parsed.mood,
            energy=parsed.energy
        )
        
        # Compile each sub-policy
        ctx.timing = self._compile_timing_policy(parsed, ctx.decisions)
        ctx.voicing = self._compile_voicing_policy(parsed, ctx.decisions)
        ctx.dynamics = self._compile_dynamics_policy(parsed, ctx.decisions)
        ctx.arrangement = self._compile_arrangement_policy(parsed, ctx.decisions)
        ctx.mix = self._compile_mix_policy(parsed, ctx.decisions)
        ctx.instruments = self._compile_instrument_policy(parsed, ctx.decisions)
        
        # Overlay genre DNA intelligence (Sprint 5)
        if _HAS_GENRE_DNA:
            self._apply_genre_dna_overlay(genre, ctx)
        
        # Apply genre rules validation
        self._apply_genre_rules(parsed, ctx)
        
        # Build humanize config if available
        if HAS_PHYSICS:
            ctx.humanize_config = self._build_humanize_config(ctx)
        
        logger.info(f"StylePolicy compiled: {len(ctx.decisions)} decisions for {genre}")
        
        return ctx
    
    def _compile_timing_policy(
        self, 
        parsed: ParsedPrompt, 
        decisions: List[PolicyDecision]
    ) -> TimingPolicy:
        """Compile timing/rhythm policy."""
        genre = (parsed.genre or '').lower().replace("-", "_").replace(" ", "_")
        preset = GENRE_TIMING_PRESETS.get(genre, GENRE_TIMING_PRESETS["default"])
        
        policy = TimingPolicy()
        
        # Feel
        if parsed.use_swing and parsed.swing_amount > 0:
            policy.feel = TimingFeel.MEDIUM_SWING
            policy.swing_amount = parsed.swing_amount
            decisions.append(PolicyDecision(
                category="timing",
                name="feel",
                value=policy.feel,
                source=DecisionSource.PROMPT,
                reason=f"User requested swing ({parsed.swing_amount:.0%})"
            ))
        else:
            policy.feel = preset.get("feel", TimingFeel.STRAIGHT)
            policy.swing_amount = preset.get("swing_amount", 0.0)
            decisions.append(PolicyDecision(
                category="timing",
                name="feel",
                value=policy.feel,
                source=DecisionSource.GENRE_RULE,
                reason=f"Genre default for {genre}"
            ))
        
        # Snare offset range
        policy.snare_late_range = preset.get("snare_late_range", (0, 15))
        decisions.append(PolicyDecision(
            category="timing",
            name="snare_late_range",
            value=policy.snare_late_range,
            source=DecisionSource.GENRE_RULE,
            reason=f"{genre} snare timing tradition"
        ))
        
        # Jitter
        policy.timing_jitter = preset.get("timing_jitter", 0.02)
        policy.velocity_variation = parsed.velocity_variation
        
        # Push/pull
        policy.push_pull_strength = preset.get("push_pull_strength", 0.0)
        
        return policy
    
    def _compile_voicing_policy(
        self,
        parsed: ParsedPrompt,
        decisions: List[PolicyDecision]
    ) -> VoicingPolicy:
        """Compile chord voicing policy."""
        genre = (parsed.genre or '').lower().replace("-", "_").replace(" ", "_")
        preset = GENRE_VOICING_PRESETS.get(genre, GENRE_VOICING_PRESETS["default"])
        
        policy = VoicingPolicy()
        policy.style = preset.get("style", VoicingStyle.OPEN)
        policy.max_extensions = preset.get("max_extensions", 9)
        policy.use_alterations = preset.get("use_alterations", False)
        policy.use_suspensions = preset.get("use_suspensions", True)
        
        decisions.append(PolicyDecision(
            category="voicing",
            name="style",
            value=policy.style,
            source=DecisionSource.GENRE_RULE,
            reason=f"{genre} voicing tradition"
        ))
        
        return policy
    
    def _compile_dynamics_policy(
        self,
        parsed: ParsedPrompt,
        decisions: List[PolicyDecision]
    ) -> DynamicsPolicy:
        """Compile dynamics and velocity policy."""
        genre = (parsed.genre or '').lower().replace("-", "_").replace(" ", "_")
        preset = GENRE_DYNAMICS_PRESETS.get(genre, GENRE_DYNAMICS_PRESETS["default"])
        
        policy = DynamicsPolicy()
        
        # Velocity ranges
        if "kick_velocity_range" in preset:
            policy.kick_velocity_range = tuple(preset["kick_velocity_range"])
        if "snare_velocity_range" in preset:
            policy.snare_velocity_range = tuple(preset["snare_velocity_range"])
        
        # Ghost notes
        policy.ghost_note_probability = preset.get("ghost_note_probability", 0.3)
        decisions.append(PolicyDecision(
            category="dynamics",
            name="ghost_note_probability",
            value=policy.ghost_note_probability,
            source=DecisionSource.GENRE_RULE,
            reason=f"{genre} ghost note tradition"
        ))
        
        # Sidechain
        if parsed.use_sidechain:
            policy.use_sidechain = True
            policy.sidechain_amount = 0.35
            decisions.append(PolicyDecision(
                category="dynamics",
                name="sidechain",
                value=True,
                source=DecisionSource.PROMPT,
                reason="User requested sidechain compression"
            ))
        elif preset.get("use_sidechain", False):
            policy.use_sidechain = True
            policy.sidechain_amount = preset.get("sidechain_amount", 0.3)
            decisions.append(PolicyDecision(
                category="dynamics",
                name="sidechain",
                value=True,
                source=DecisionSource.GENRE_RULE,
                reason=f"{genre} typically uses sidechain"
            ))
        
        return policy
    
    def _compile_arrangement_policy(
        self,
        parsed: ParsedPrompt,
        decisions: List[PolicyDecision]
    ) -> ArrangementPolicy:
        """Compile arrangement structure policy."""
        policy = ArrangementPolicy()
        
        # Density based on energy
        if parsed.energy == "high":
            policy.density = ArrangementDensity.BUSY
            policy.fill_frequency_bars = 4
        elif parsed.energy == "low":
            policy.density = ArrangementDensity.LIGHT
            policy.fill_frequency_bars = 16
        else:
            policy.density = ArrangementDensity.MODERATE
            policy.fill_frequency_bars = 8
        
        decisions.append(PolicyDecision(
            category="arrangement",
            name="density",
            value=policy.density,
            source=DecisionSource.PROMPT,
            reason=f"Energy level: {parsed.energy}"
        ))
        
        # Genre-specific arrangement
        genre = (parsed.genre or '').lower()
        if genre in ["trap", "trap_soul"]:
            policy.use_dropouts = True
            policy.dropout_probability = 0.15
        elif genre == "lofi":
            policy.variation_intensity = 0.15  # Subtle variations
            policy.use_dropouts = False
        
        return policy
    
    def _compile_mix_policy(
        self,
        parsed: ParsedPrompt,
        decisions: List[PolicyDecision]
    ) -> MixPolicy:
        """Compile mix and mastering policy."""
        genre = (parsed.genre or '').lower().replace("-", "_").replace(" ", "_")
        preset = GENRE_MIX_PRESETS.get(genre, GENRE_MIX_PRESETS["default"])
        
        policy = MixPolicy()
        
        # Spectral targets from parsed prompt or preset
        policy.sub_bass_target = parsed.sub_bass_presence if parsed.sub_bass_presence else preset.get("sub_bass_target", 0.5)
        policy.brightness_target = parsed.brightness if parsed.brightness else preset.get("brightness_target", 0.5)
        policy.warmth_target = parsed.warmth if parsed.warmth else preset.get("warmth_target", 0.5)
        
        # Saturation
        policy.saturation_type = preset.get("saturation_type", "tape")
        policy.saturation_amount = preset.get("saturation_amount", 0.2)
        
        decisions.append(PolicyDecision(
            category="mix",
            name="saturation",
            value=f"{policy.saturation_type} @ {policy.saturation_amount:.0%}",
            source=DecisionSource.GENRE_RULE,
            reason=f"{genre} mix character"
        ))
        
        # Sprint 11.1: Bias brightness/warmth from sonic adjectives
        try:
            _adj = getattr(parsed, 'sonic_adjectives', []) or []
            if 'bright' in _adj or 'crisp' in _adj:
                policy.brightness_target = min(1.0, policy.brightness_target + 0.15)
            if 'dark' in _adj or 'heavy' in _adj:
                policy.brightness_target = max(0.0, policy.brightness_target - 0.15)
            if 'warm' in _adj or 'vintage' in _adj:
                policy.warmth_target = min(1.0, policy.warmth_target + 0.15)
            if 'crisp' in _adj or 'clean' in _adj:
                policy.warmth_target = max(0.0, policy.warmth_target - 0.1)
        except Exception:
            pass
        
        # FX chains
        if parsed.fx_chain_master:
            policy.master_fx_chain = parsed.fx_chain_master
        if parsed.fx_chain_drums:
            policy.drum_bus_fx = parsed.fx_chain_drums
        elif "drum_bus_fx" in preset:
            policy.drum_bus_fx = preset["drum_bus_fx"]
        
        return policy
    
    def _compile_instrument_policy(
        self,
        parsed: ParsedPrompt,
        decisions: List[PolicyDecision]
    ) -> InstrumentPolicy:
        """Compile instrumentation policy."""
        policy = InstrumentPolicy()
        
        # From prompt
        policy.required_instruments = list(parsed.instruments)
        policy.forbidden_instruments = list(parsed.excluded_instruments)
        
        # Preferred tags from mood
        if parsed.mood == "dark":
            policy.preferred_tags = ["dark", "heavy", "saturated"]
        elif parsed.mood == "chill":
            policy.preferred_tags = ["warm", "soft", "mellow"]
        elif parsed.mood == "hype":
            policy.preferred_tags = ["bright", "punchy", "aggressive"]
        
        # Low-end mutex (can't have multiple bass sources)
        if "808" in parsed.instruments and "bass" in parsed.instruments:
            policy.low_end_mutex = ["808", "bass"]
            decisions.append(PolicyDecision(
                category="instruments",
                name="low_end_conflict",
                value="808 + bass conflict",
                source=DecisionSource.CONFLICT_RESOLUTION,
                reason="808 and bass compete for low frequencies; prefer 808 in this genre"
            ))
        
        return policy
    
    def _apply_genre_rules(self, parsed: ParsedPrompt, ctx: PolicyContext):
        """Apply genre rules validation and auto-repair."""
        genre = (parsed.genre or '').lower().replace("-", "_").replace(" ", "_")
        
        # Get validation result
        result = self.genre_engine.validate_elements(
            genre,
            parsed.instruments,
            parsed.drum_elements
        )
        
        ctx.genre_rules_applied = True
        
        if not result.valid:
            # Count auto-repairs
            ctx.violations_auto_repaired = len([
                v for v in result.violations 
                if v.auto_repaired
            ])
            
            # Add warnings for non-auto-repaired issues
            for violation in result.violations:
                if not violation.auto_repaired:
                    ctx.warnings.append(f"{violation.message}")
                    ctx.decisions.append(PolicyDecision(
                        category="validation",
                        name=violation.rule_id,
                        value=violation.elements_involved,
                        source=DecisionSource.GENRE_RULE,
                        confidence=0.8,
                        reason=violation.message
                    ))
    
    def _build_humanize_config(self, ctx: PolicyContext) -> Optional[Any]:
        """Build HumanizeConfig from PolicyContext."""
        if not HAS_PHYSICS:
            return None
        
        return HumanizeConfig(
            apply_fatigue=True,
            apply_limb_conflicts=True,
            apply_ghost_notes=True,
            apply_hand_alternation=True,
            apply_emphasis=True,
            fatigue_bpm_threshold=140.0,
            ghost_note_probability=ctx.dynamics.ghost_note_probability,
            ghost_note_velocity_min=int(60 * ctx.dynamics.ghost_note_velocity_factor),
            ghost_note_velocity_max=int(90 * ctx.dynamics.ghost_note_velocity_factor),
            timing_variation=ctx.timing.timing_jitter,
            swing_amount=ctx.timing.swing_amount,
            weak_hand_factor=0.85,
        )

    def _apply_genre_dna_overlay(self, genre: str, ctx: 'PolicyContext'):
        """Enrich PolicyContext with continuous genre DNA values.

        Genre DNA provides 10 continuous dimensions (0.0-1.0) that refine
        the discrete genre presets. Especially valuable for fusion genres
        where no exact preset match exists.
        """
        try:
            dna = get_genre_dna(genre)
        except (KeyError, ValueError):
            return  # Unknown genre, skip overlay

        if dna is None:
            return

        # Timing enrichment
        if hasattr(dna, 'swing') and dna.swing > ctx.timing.swing_amount:
            ctx.timing.swing_amount = dna.swing * 0.8  # DNA-informed swing
            ctx.decisions.append(PolicyDecision(
                category="timing",
                name="swing_amount",
                value=ctx.timing.swing_amount,
                source=DecisionSource.GENRE_RULE,
                reason=f"Genre DNA swing={dna.swing:.2f} applied"
            ))

        # Voicing enrichment
        if hasattr(dna, 'harmonic_complexity'):
            target_extensions = int(1 + dna.harmonic_complexity * 3)  # 1-4
            if target_extensions > ctx.voicing.max_extensions:
                ctx.voicing.max_extensions = target_extensions
                ctx.decisions.append(PolicyDecision(
                    category="voicing",
                    name="max_extensions",
                    value=target_extensions,
                    source=DecisionSource.GENRE_RULE,
                    reason=f"Genre DNA harmonic_complexity={dna.harmonic_complexity:.2f}"
                ))

        # Dynamics enrichment
        if hasattr(dna, 'dynamic_range'):
            ghost_prob = 0.05 + dna.dynamic_range * 0.20  # 0.05-0.25
            if ghost_prob > ctx.dynamics.ghost_note_probability:
                ctx.dynamics.ghost_note_probability = ghost_prob
                ctx.decisions.append(PolicyDecision(
                    category="dynamics",
                    name="ghost_note_probability",
                    value=ghost_prob,
                    source=DecisionSource.GENRE_RULE,
                    reason=f"Genre DNA dynamic_range={dna.dynamic_range:.2f}"
                ))


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def compile_policy(parsed: ParsedPrompt) -> PolicyContext:
    """
    Convenience function to compile policy from parsed prompt.
    
    Args:
        parsed: ParsedPrompt from prompt_parser
        
    Returns:
        PolicyContext ready for generators
    """
    policy = StylePolicy()
    return policy.compile(parsed)


def get_policy_summary(ctx: PolicyContext) -> str:
    """
    Get a human-readable summary of policy decisions.
    
    Args:
        ctx: PolicyContext
        
    Returns:
        Summary string
    """
    lines = [
        f"Style Policy for {ctx.genre} @ {ctx.bpm} BPM",
        f"  Timing: {ctx.timing.feel.value}, swing={ctx.timing.swing_amount:.0%}",
        f"  Voicing: {ctx.voicing.style.value}, max ext={ctx.voicing.max_extensions}",
        f"  Dynamics: ghost={ctx.dynamics.ghost_note_probability:.0%}, sidechain={ctx.dynamics.use_sidechain}",
        f"  Mix: sub={ctx.mix.sub_bass_target:.0%}, sat={ctx.mix.saturation_type}",
        f"  Decisions: {len(ctx.decisions)} made, {ctx.violations_auto_repaired} auto-repaired"
    ]
    if ctx.warnings:
        lines.append(f"  Warnings: {len(ctx.warnings)}")
    return "\n".join(lines)


# =============================================================================
# CLI TESTING
# =============================================================================

if __name__ == "__main__":
    print("🎛️  Style Policy Test")
    print("=" * 60)
    
    # Create test prompt
    from .prompt_parser import parse_prompt
    
    test_prompts = [
        "dark trap beat 145 bpm A minor with 808 and hi-hat rolls",
        "chill lofi hip hop 85 bpm G major with piano and vinyl crackle",
        "g funk west coast 95 bpm C minor with synth lead and funk bass",
        "boom bap 92 bpm F minor with dusty drums and jazz piano",
    ]
    
    for prompt in test_prompts:
        print(f"\n📝 Prompt: {prompt}")
        print("-" * 50)
        
        parsed = parse_prompt(prompt)
        policy_ctx = compile_policy(parsed)
        
        print(get_policy_summary(policy_ctx))
        print(f"\n📋 Decision Record ({len(policy_ctx.decisions)} decisions):")
        for d in policy_ctx.decisions[:5]:  # Show first 5
            print(f"   [{d.source.value}] {d.category}.{d.name} = {d.value}")
            if d.reason:
                print(f"      → {d.reason}")
    
    print("\n✅ Style Policy test complete")
