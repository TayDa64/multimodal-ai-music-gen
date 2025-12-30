"""
Performance Models - Role-Specific Player Profiles

This module implements Milestone E of likuTasks.md:
"Replace global ±timing/velocity noise with role-specific performance
models that mimic real players."

Key Concepts:
    - PlayerProfile: Defines how a specific "player" performs
    - Role-specific timing/velocity behavior
    - Beat-relative timing curves (push/pull feel)
    - Hand dominance and limb models for drums
    - Ghost note probabilities based on groove density
    - Constraints for physically impossible hits

Player Profiles:
    - TIGHT_DRUMMER: Machine-like precision, minimal variance
    - LOOSE_DRUMMER: Human feel, natural variance
    - FUNK_DRUMMER: Pocket feel, behind the beat
    - LAZY_BASSIST: Slightly late, relaxed feel
    - TIGHT_BASSIST: Punchy, on-the-beat precision
    - JAZZ_PIANIST: Loose timing, dynamic expression
    - MACHINE_TIGHT: DAW-style quantized feel
    - LIVE_FEEL: Concert performance energy

Usage:
    from multimodal_gen.performance_models import (
        PlayerProfile,
        get_profile_for_genre,
        apply_performance_model,
    )
    
    profile = get_profile_for_genre("trap_soul", "drums")
    humanized_notes = apply_performance_model(notes, profile)

Integration with MidiGenerator:
    - Each track gets a PlayerProfile based on role and genre
    - Humanization is applied per-role, not globally
    - Profiles are recorded in session_manifest for reproducibility
"""

import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from enum import Enum
from copy import deepcopy
import math

# Import local utilities
try:
    from .utils import (
        TICKS_PER_BEAT,
        TICKS_PER_16TH,
        TICKS_PER_8TH,
        TICKS_PER_BAR_4_4,
    )
except ImportError:
    TICKS_PER_BEAT = 480
    TICKS_PER_16TH = TICKS_PER_BEAT // 4
    TICKS_PER_8TH = TICKS_PER_BEAT // 2
    TICKS_PER_BAR_4_4 = TICKS_PER_BEAT * 4


# =============================================================================
# ENUMERATIONS
# =============================================================================

class ProfileType(Enum):
    """Categories of player profiles."""
    TIGHT = "tight"          # Minimal variance, precise
    NATURAL = "natural"      # Human-like feel
    LOOSE = "loose"          # Relaxed, behind the beat
    FUNK = "funk"            # Pocket/groove feel
    LIVE = "live"            # Concert energy, dynamic
    MACHINE = "machine"      # DAW-quantized


class TimingFeel(Enum):
    """How timing relates to the beat."""
    ON_TOP = "on_top"        # Slightly ahead
    IN_POCKET = "in_pocket"  # Right on the beat
    LAID_BACK = "laid_back"  # Slightly behind
    RUSHING = "rushing"      # Progressively ahead
    DRAGGING = "dragging"    # Progressively behind


class VelocityPattern(Enum):
    """Velocity distribution patterns."""
    EVEN = "even"            # Consistent dynamics
    ACCENTED = "accented"    # Strong downbeats
    CRESCENDO = "crescendo"  # Building intensity
    DECRESCENDO = "decrescendo"  # Fading intensity
    DYNAMIC = "dynamic"      # Wide range


class HandDominance(Enum):
    """For drum limb modeling."""
    RIGHT = "right"
    LEFT = "left"
    AMBIDEXTROUS = "ambidextrous"


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class TimingModel:
    """Defines timing behavior per subdivision.
    
    Models how a player's timing varies across different beat positions.
    Real players have consistent biases - they're not randomly early/late.
    """
    # Base timing offset (in ticks, positive = late, negative = early)
    base_offset: int = 0
    
    # Per-subdivision offsets (relative to 16th note grid)
    # Index 0-15 represents 16th note positions in a bar
    subdivision_offsets: List[int] = field(default_factory=lambda: [0] * 16)
    
    # Random timing variance (in ticks)
    variance: int = 5
    
    # Timing feel overall
    feel: str = TimingFeel.IN_POCKET.value
    
    # Swing amount (0.0 to 0.5, applied to offbeats)
    swing: float = 0.0
    
    # Whether timing drifts over time
    drift_enabled: bool = False
    drift_direction: int = 0  # Positive = rushing, negative = dragging
    drift_rate: float = 0.001  # Ticks per beat
    
    def get_offset_for_position(self, tick: int, total_ticks: int = 0) -> int:
        """Get timing offset for a specific tick position.
        
        Args:
            tick: Current tick position
            total_ticks: Total song length (for drift calculation)
        
        Returns:
            Timing offset in ticks
        """
        # Base offset
        offset = self.base_offset
        
        # Subdivision offset (position within bar)
        bar_position = tick % TICKS_PER_BAR_4_4
        subdivision = (bar_position * 16) // TICKS_PER_BAR_4_4
        offset += self.subdivision_offsets[subdivision % 16]
        
        # Apply swing to offbeats
        is_offbeat = (bar_position % TICKS_PER_8TH) >= TICKS_PER_16TH
        if self.swing > 0 and is_offbeat:
            offset += int(TICKS_PER_16TH * self.swing)
        
        # Random variance
        if self.variance > 0:
            offset += random.randint(-self.variance, self.variance)
        
        # Drift over time
        if self.drift_enabled and total_ticks > 0:
            progress = tick / total_ticks
            drift_amount = int(self.drift_rate * progress * total_ticks)
            offset += self.drift_direction * drift_amount
        
        return offset
    
    def to_dict(self) -> Dict:
        return {
            "base_offset": self.base_offset,
            "subdivision_offsets": self.subdivision_offsets,
            "variance": self.variance,
            "feel": self.feel,
            "swing": self.swing,
            "drift_enabled": self.drift_enabled,
            "drift_direction": self.drift_direction,
            "drift_rate": self.drift_rate,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "TimingModel":
        return cls(**data)


@dataclass
class VelocityModel:
    """Defines velocity behavior.
    
    Models how a player's dynamics vary with beat position,
    musical context, and physical constraints.
    """
    # Base velocity (0-127)
    base_velocity: int = 100
    
    # Velocity range (min, max)
    velocity_range: Tuple[int, int] = (60, 120)
    
    # Per-subdivision velocity multipliers (1.0 = base)
    # Index 0-15 represents 16th note positions in a bar
    subdivision_multipliers: List[float] = field(default_factory=lambda: [1.0] * 16)
    
    # Random variance (percentage, e.g., 0.1 = ±10%)
    variance: float = 0.1
    
    # Velocity pattern type
    pattern: str = VelocityPattern.ACCENTED.value
    
    # Downbeat accent (multiplier for beat 1)
    downbeat_accent: float = 1.15
    
    # Backbeat accent (multiplier for beats 2 and 4)
    backbeat_accent: float = 1.1
    
    # Ghost note velocity reduction (percentage)
    ghost_reduction: float = 0.5
    
    def get_velocity(self, base_vel: int, tick: int, 
                    is_downbeat: bool = False,
                    is_backbeat: bool = False,
                    is_ghost: bool = False) -> int:
        """Calculate velocity for a specific note.
        
        Args:
            base_vel: Input velocity
            tick: Tick position
            is_downbeat: True if on beat 1
            is_backbeat: True if on beats 2/4
            is_ghost: True if ghost note
        
        Returns:
            Adjusted velocity (0-127)
        """
        vel = float(base_vel)
        
        # Apply subdivision multiplier
        bar_position = tick % TICKS_PER_BAR_4_4
        subdivision = (bar_position * 16) // TICKS_PER_BAR_4_4
        vel *= self.subdivision_multipliers[subdivision % 16]
        
        # Apply accents
        if is_downbeat:
            vel *= self.downbeat_accent
        elif is_backbeat:
            vel *= self.backbeat_accent
        
        # Ghost note reduction
        if is_ghost:
            vel *= self.ghost_reduction
        
        # Random variance
        if self.variance > 0:
            vel *= (1.0 + (random.random() - 0.5) * 2 * self.variance)
        
        # Clamp to range
        min_vel, max_vel = self.velocity_range
        return max(min_vel, min(max_vel, int(vel)))
    
    def to_dict(self) -> Dict:
        return {
            "base_velocity": self.base_velocity,
            "velocity_range": list(self.velocity_range),
            "subdivision_multipliers": self.subdivision_multipliers,
            "variance": self.variance,
            "pattern": self.pattern,
            "downbeat_accent": self.downbeat_accent,
            "backbeat_accent": self.backbeat_accent,
            "ghost_reduction": self.ghost_reduction,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "VelocityModel":
        if "velocity_range" in data:
            data["velocity_range"] = tuple(data["velocity_range"])
        return cls(**data)


@dataclass
class DrumLimbModel:
    """Models physical drumming constraints.
    
    Real drummers have physical limitations:
    - Two hands, two feet
    - Dominant hand stronger
    - Minimum time between hits on same limb
    - Impossible simultaneous hits
    """
    # Hand dominance
    dominance: str = HandDominance.RIGHT.value
    
    # Velocity reduction for weak hand (percentage)
    weak_hand_reduction: float = 0.15
    
    # Minimum ticks between hits on same limb
    min_hit_interval: int = 60  # ~8ms at 120 BPM
    
    # Flam timing (ticks between grace and main note)
    flam_offset: int = 20
    
    # Roll minimum velocity retention
    roll_velocity_floor: float = 0.6
    
    # Physical impossibilities (pairs of drums that can't be hit simultaneously)
    impossible_pairs: List[Tuple[int, int]] = field(default_factory=list)
    
    # Limb assignments for drum pitches (pitch -> "R", "L", "RF", "LF")
    limb_assignments: Dict[int, str] = field(default_factory=dict)
    
    def is_physically_possible(
        self,
        pitch1: int,
        pitch2: int,
        time_diff: int
    ) -> bool:
        """Check if two hits are physically possible.
        
        Args:
            pitch1: First drum pitch
            pitch2: Second drum pitch
            time_diff: Time between hits in ticks
        
        Returns:
            True if physically possible
        """
        # Check impossible pairs
        if (pitch1, pitch2) in self.impossible_pairs or (pitch2, pitch1) in self.impossible_pairs:
            if time_diff < self.min_hit_interval:
                return False
        
        # Check same limb constraint
        limb1 = self.limb_assignments.get(pitch1)
        limb2 = self.limb_assignments.get(pitch2)
        if limb1 and limb2 and limb1 == limb2:
            if time_diff < self.min_hit_interval:
                return False
        
        return True
    
    def get_velocity_for_limb(self, base_vel: int, limb: str) -> int:
        """Adjust velocity based on limb.
        
        Args:
            base_vel: Input velocity
            limb: Limb identifier ("R", "L", "RF", "LF")
        
        Returns:
            Adjusted velocity
        """
        is_weak = (
            (self.dominance == HandDominance.RIGHT.value and limb in ["L", "LF"]) or
            (self.dominance == HandDominance.LEFT.value and limb in ["R", "RF"])
        )
        
        if is_weak:
            return int(base_vel * (1.0 - self.weak_hand_reduction))
        return base_vel
    
    def to_dict(self) -> Dict:
        return {
            "dominance": self.dominance,
            "weak_hand_reduction": self.weak_hand_reduction,
            "min_hit_interval": self.min_hit_interval,
            "flam_offset": self.flam_offset,
            "roll_velocity_floor": self.roll_velocity_floor,
            "impossible_pairs": [list(p) for p in self.impossible_pairs],
            "limb_assignments": self.limb_assignments,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "DrumLimbModel":
        if "impossible_pairs" in data:
            data["impossible_pairs"] = [tuple(p) for p in data["impossible_pairs"]]
        return cls(**data)


@dataclass
class GhostNoteModel:
    """Controls ghost note generation.
    
    Ghost notes add groove and fill:
    - Probability based on density/section
    - Placement relative to main hits
    - Velocity ranges for subtlety
    """
    # Base probability of ghost notes
    probability: float = 0.15
    
    # Density-based scaling (higher density = more ghosts)
    density_scaling: float = 0.3
    
    # Preferred positions (relative to main beat)
    # Values in 16ths: -2 = two 16ths before, 1 = one 16th after
    preferred_positions: List[int] = field(default_factory=lambda: [-1, 1])
    
    # Velocity range for ghosts (percentage of main hit)
    velocity_range: Tuple[float, float] = (0.3, 0.5)
    
    # Section type probability multipliers
    section_multipliers: Dict[str, float] = field(default_factory=lambda: {
        "intro": 0.5,
        "verse": 0.8,
        "chorus": 1.2,
        "drop": 0.3,
        "bridge": 1.0,
        "outro": 0.6,
    })
    
    def should_add_ghost(
        self,
        density: float = 0.5,
        section_type: str = "verse"
    ) -> bool:
        """Determine if a ghost note should be added.
        
        Args:
            density: Current drum density (0-1)
            section_type: Current section type
        
        Returns:
            True if ghost should be added
        """
        prob = self.probability
        
        # Scale by density
        prob += density * self.density_scaling
        
        # Scale by section
        section_mult = self.section_multipliers.get(section_type, 1.0)
        prob *= section_mult
        
        return random.random() < prob
    
    def get_ghost_velocity(self, main_velocity: int) -> int:
        """Calculate velocity for a ghost note.
        
        Args:
            main_velocity: Velocity of the main hit
        
        Returns:
            Ghost note velocity
        """
        min_mult, max_mult = self.velocity_range
        mult = random.uniform(min_mult, max_mult)
        return max(20, int(main_velocity * mult))
    
    def to_dict(self) -> Dict:
        return {
            "probability": self.probability,
            "density_scaling": self.density_scaling,
            "preferred_positions": self.preferred_positions,
            "velocity_range": list(self.velocity_range),
            "section_multipliers": self.section_multipliers,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "GhostNoteModel":
        if "velocity_range" in data:
            data["velocity_range"] = tuple(data["velocity_range"])
        return cls(**data)


@dataclass
class PlayerProfile:
    """Complete performance model for a player role.
    
    This is the main class that combines all aspects of humanization:
    - Timing behavior (push/pull, swing, variance)
    - Velocity behavior (dynamics, accents, range)
    - Physical constraints (for drums)
    - Ghost note behavior
    
    Each role/genre combination gets a unique profile that captures
    the "feel" of that style.
    """
    name: str
    role: str  # "drums", "bass", "lead", "chords", "pad"
    profile_type: str  # ProfileType value
    
    # Component models
    timing: TimingModel = field(default_factory=TimingModel)
    velocity: VelocityModel = field(default_factory=VelocityModel)
    limb_model: Optional[DrumLimbModel] = None  # Only for drums
    ghost_model: Optional[GhostNoteModel] = None  # Mainly for drums
    
    # Description for UI/logging
    description: str = ""
    
    # Genre associations (for lookup)
    genres: List[str] = field(default_factory=list)
    
    def apply_to_note(
        self,
        pitch: int,
        start_tick: int,
        duration_ticks: int,
        velocity: int,
        total_ticks: int = 0,
        section_type: str = "verse",
        **kwargs
    ) -> Tuple[int, int, int]:
        """Apply humanization to a single note.
        
        Args:
            pitch: MIDI pitch
            start_tick: Original start tick
            duration_ticks: Note duration
            velocity: Original velocity
            total_ticks: Song length (for drift)
            section_type: Current section
            **kwargs: Additional context (is_downbeat, is_ghost, etc.)
        
        Returns:
            Tuple of (new_start_tick, new_duration, new_velocity)
        """
        # Get timing offset
        timing_offset = self.timing.get_offset_for_position(
            start_tick, total_ticks
        )
        new_start = max(0, start_tick + timing_offset)
        
        # Adjust duration proportionally
        new_duration = max(10, duration_ticks + timing_offset // 2)
        
        # Get velocity
        is_downbeat = kwargs.get("is_downbeat", 
            (start_tick % TICKS_PER_BAR_4_4) < TICKS_PER_16TH)
        is_backbeat = kwargs.get("is_backbeat",
            (start_tick % (TICKS_PER_BAR_4_4 // 2)) < TICKS_PER_16TH and not is_downbeat)
        is_ghost = kwargs.get("is_ghost", False)
        
        new_velocity = self.velocity.get_velocity(
            velocity, start_tick,
            is_downbeat=is_downbeat,
            is_backbeat=is_backbeat,
            is_ghost=is_ghost
        )
        
        # Apply limb model for drums
        if self.limb_model and self.role == "drums":
            limb = self.limb_model.limb_assignments.get(pitch, "R")
            new_velocity = self.limb_model.get_velocity_for_limb(new_velocity, limb)
        
        return new_start, new_duration, new_velocity
    
    def should_add_ghost(
        self,
        density: float = 0.5,
        section_type: str = "verse"
    ) -> bool:
        """Check if a ghost note should be added."""
        if self.ghost_model:
            return self.ghost_model.should_add_ghost(density, section_type)
        return False
    
    def get_ghost_velocity(self, main_velocity: int) -> int:
        """Get velocity for a ghost note."""
        if self.ghost_model:
            return self.ghost_model.get_ghost_velocity(main_velocity)
        return max(20, int(main_velocity * 0.4))
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "role": self.role,
            "profile_type": self.profile_type,
            "timing": self.timing.to_dict(),
            "velocity": self.velocity.to_dict(),
            "limb_model": self.limb_model.to_dict() if self.limb_model else None,
            "ghost_model": self.ghost_model.to_dict() if self.ghost_model else None,
            "description": self.description,
            "genres": self.genres,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "PlayerProfile":
        timing_data = data.pop("timing", {})
        velocity_data = data.pop("velocity", {})
        limb_data = data.pop("limb_model", None)
        ghost_data = data.pop("ghost_model", None)
        
        profile = cls(**{k: v for k, v in data.items()
                        if k not in ("timing", "velocity", "limb_model", "ghost_model")})
        
        profile.timing = TimingModel.from_dict(timing_data)
        profile.velocity = VelocityModel.from_dict(velocity_data)
        if limb_data:
            profile.limb_model = DrumLimbModel.from_dict(limb_data)
        if ghost_data:
            profile.ghost_model = GhostNoteModel.from_dict(ghost_data)
        
        return profile


# =============================================================================
# PRESET PROFILES
# =============================================================================

def create_tight_drummer() -> PlayerProfile:
    """Machine-like precision drummer."""
    return PlayerProfile(
        name="Tight Drummer",
        role="drums",
        profile_type=ProfileType.TIGHT.value,
        description="Precise timing, consistent dynamics, minimal variance",
        genres=["trap", "drill", "house"],
        timing=TimingModel(
            base_offset=0,
            variance=3,
            feel=TimingFeel.IN_POCKET.value,
            swing=0.0,
        ),
        velocity=VelocityModel(
            base_velocity=100,
            velocity_range=(80, 115),
            variance=0.05,
            pattern=VelocityPattern.ACCENTED.value,
            downbeat_accent=1.1,
            backbeat_accent=1.05,
        ),
        limb_model=DrumLimbModel(
            dominance=HandDominance.RIGHT.value,
            weak_hand_reduction=0.08,
            min_hit_interval=50,
        ),
        ghost_model=GhostNoteModel(
            probability=0.08,
            velocity_range=(0.3, 0.4),
        ),
    )


def create_loose_drummer() -> PlayerProfile:
    """Human-feel drummer with natural variance."""
    return PlayerProfile(
        name="Loose Drummer",
        role="drums",
        profile_type=ProfileType.NATURAL.value,
        description="Natural human feel, moderate variance, groove-focused",
        genres=["lofi", "boom_bap", "jazz"],
        timing=TimingModel(
            base_offset=5,  # Slightly behind
            variance=12,
            feel=TimingFeel.LAID_BACK.value,
            swing=0.1,
        ),
        velocity=VelocityModel(
            base_velocity=95,
            velocity_range=(55, 120),
            variance=0.15,
            pattern=VelocityPattern.DYNAMIC.value,
            downbeat_accent=1.2,
            backbeat_accent=1.15,
        ),
        limb_model=DrumLimbModel(
            dominance=HandDominance.RIGHT.value,
            weak_hand_reduction=0.18,
            min_hit_interval=45,
        ),
        ghost_model=GhostNoteModel(
            probability=0.25,
            density_scaling=0.4,
            velocity_range=(0.25, 0.5),
        ),
    )


def create_funk_drummer() -> PlayerProfile:
    """Pocket/groove funk drummer."""
    return PlayerProfile(
        name="Funk Drummer",
        role="drums",
        profile_type=ProfileType.FUNK.value,
        description="Deep pocket, strong ghost notes, groove-focused",
        genres=["g_funk", "funk", "rnb"],
        timing=TimingModel(
            base_offset=8,  # Behind the beat
            variance=8,
            feel=TimingFeel.LAID_BACK.value,
            swing=0.15,
            # Accent certain 16ths for funk feel
            subdivision_offsets=[0, -3, 0, 5, 0, -2, 0, 3, 0, -3, 0, 5, 0, -2, 0, 3],
        ),
        velocity=VelocityModel(
            base_velocity=90,
            velocity_range=(50, 115),
            variance=0.12,
            pattern=VelocityPattern.DYNAMIC.value,
            downbeat_accent=1.25,
            backbeat_accent=1.3,  # Strong backbeat
            ghost_reduction=0.45,
        ),
        limb_model=DrumLimbModel(
            dominance=HandDominance.RIGHT.value,
            weak_hand_reduction=0.15,
            min_hit_interval=40,
            flam_offset=25,
        ),
        ghost_model=GhostNoteModel(
            probability=0.35,
            density_scaling=0.2,
            preferred_positions=[-1, -2, 1],
            velocity_range=(0.3, 0.55),
        ),
    )


def create_trap_soul_drummer() -> PlayerProfile:
    """Trap soul drummer - hybrid of tight and groove."""
    return PlayerProfile(
        name="Trap Soul Drummer",
        role="drums",
        profile_type=ProfileType.NATURAL.value,
        description="Clean modern trap with soul groove elements",
        genres=["trap_soul"],
        timing=TimingModel(
            base_offset=3,
            variance=6,
            feel=TimingFeel.IN_POCKET.value,
            swing=0.05,
        ),
        velocity=VelocityModel(
            base_velocity=95,
            velocity_range=(65, 115),
            variance=0.08,
            pattern=VelocityPattern.ACCENTED.value,
            downbeat_accent=1.12,
            backbeat_accent=1.1,
        ),
        limb_model=DrumLimbModel(
            dominance=HandDominance.RIGHT.value,
            weak_hand_reduction=0.1,
            min_hit_interval=55,
        ),
        ghost_model=GhostNoteModel(
            probability=0.12,
            velocity_range=(0.3, 0.45),
        ),
    )


def create_lazy_bassist() -> PlayerProfile:
    """Relaxed, behind-the-beat bassist."""
    return PlayerProfile(
        name="Lazy Bassist",
        role="bass",
        profile_type=ProfileType.LOOSE.value,
        description="Slightly late, relaxed groovy feel",
        genres=["lofi", "boom_bap", "jazz", "rnb"],
        timing=TimingModel(
            base_offset=12,  # Notably behind
            variance=10,
            feel=TimingFeel.LAID_BACK.value,
            swing=0.08,
        ),
        velocity=VelocityModel(
            base_velocity=90,
            velocity_range=(70, 110),
            variance=0.12,
            pattern=VelocityPattern.DYNAMIC.value,
            downbeat_accent=1.15,
        ),
    )


def create_tight_bassist() -> PlayerProfile:
    """Punchy, on-the-beat bassist."""
    return PlayerProfile(
        name="Tight Bassist",
        role="bass",
        profile_type=ProfileType.TIGHT.value,
        description="On-beat precision, punchy attack",
        genres=["trap", "house", "drill", "edm"],
        timing=TimingModel(
            base_offset=-2,  # Slightly ahead for punch
            variance=4,
            feel=TimingFeel.ON_TOP.value,
            swing=0.0,
        ),
        velocity=VelocityModel(
            base_velocity=105,
            velocity_range=(85, 120),
            variance=0.06,
            pattern=VelocityPattern.EVEN.value,
            downbeat_accent=1.1,
        ),
    )


def create_funk_bassist() -> PlayerProfile:
    """Groove pocket bassist."""
    return PlayerProfile(
        name="Funk Bassist",
        role="bass",
        profile_type=ProfileType.FUNK.value,
        description="Deep pocket, syncopated groove",
        genres=["g_funk", "funk", "rnb"],
        timing=TimingModel(
            base_offset=6,
            variance=7,
            feel=TimingFeel.LAID_BACK.value,
            swing=0.12,
            subdivision_offsets=[0, 3, -2, 5, 0, 3, -2, 5, 0, 3, -2, 5, 0, 3, -2, 5],
        ),
        velocity=VelocityModel(
            base_velocity=95,
            velocity_range=(65, 115),
            variance=0.1,
            pattern=VelocityPattern.DYNAMIC.value,
            downbeat_accent=1.2,
        ),
    )


def create_jazz_pianist() -> PlayerProfile:
    """Loose, expressive jazz pianist."""
    return PlayerProfile(
        name="Jazz Pianist",
        role="chords",
        profile_type=ProfileType.LOOSE.value,
        description="Expressive dynamics, loose timing, jazz feel",
        genres=["jazz", "lofi", "rnb"],
        timing=TimingModel(
            base_offset=5,
            variance=15,
            feel=TimingFeel.LAID_BACK.value,
            swing=0.15,
        ),
        velocity=VelocityModel(
            base_velocity=85,
            velocity_range=(50, 115),
            variance=0.2,
            pattern=VelocityPattern.DYNAMIC.value,
            downbeat_accent=1.3,
        ),
    )


def create_tight_keys() -> PlayerProfile:
    """Precise keyboard player."""
    return PlayerProfile(
        name="Tight Keys",
        role="chords",
        profile_type=ProfileType.TIGHT.value,
        description="Precise timing, consistent dynamics",
        genres=["trap", "trap_soul", "house", "edm"],
        timing=TimingModel(
            base_offset=0,
            variance=5,
            feel=TimingFeel.IN_POCKET.value,
            swing=0.03,
        ),
        velocity=VelocityModel(
            base_velocity=90,
            velocity_range=(75, 105),
            variance=0.08,
            pattern=VelocityPattern.ACCENTED.value,
            downbeat_accent=1.1,
        ),
    )


def create_lead_player() -> PlayerProfile:
    """Expressive melodic lead player."""
    return PlayerProfile(
        name="Lead Player",
        role="lead",
        profile_type=ProfileType.NATURAL.value,
        description="Expressive, dynamic lead playing",
        genres=["trap_soul", "rnb", "lofi", "g_funk"],
        timing=TimingModel(
            base_offset=3,
            variance=10,
            feel=TimingFeel.IN_POCKET.value,
            swing=0.05,
        ),
        velocity=VelocityModel(
            base_velocity=95,
            velocity_range=(60, 120),
            variance=0.15,
            pattern=VelocityPattern.DYNAMIC.value,
            downbeat_accent=1.15,
        ),
    )


def create_pad_player() -> PlayerProfile:
    """Ambient pad player."""
    return PlayerProfile(
        name="Pad Player",
        role="pad",
        profile_type=ProfileType.NATURAL.value,
        description="Smooth, atmospheric pad playing",
        genres=["lofi", "ambient", "trap_soul", "rnb"],
        timing=TimingModel(
            base_offset=10,  # Pads can be a bit late
            variance=20,  # Wide variance is fine for pads
            feel=TimingFeel.LAID_BACK.value,
            swing=0.0,
        ),
        velocity=VelocityModel(
            base_velocity=80,
            velocity_range=(55, 95),
            variance=0.1,
            pattern=VelocityPattern.EVEN.value,
            downbeat_accent=1.05,
        ),
    )


def create_machine_profile(role: str) -> PlayerProfile:
    """DAW-quantized, machine-tight profile."""
    return PlayerProfile(
        name=f"Machine {role.title()}",
        role=role,
        profile_type=ProfileType.MACHINE.value,
        description="Perfectly quantized, minimal humanization",
        genres=["edm", "techno", "house"],
        timing=TimingModel(
            base_offset=0,
            variance=1,
            feel=TimingFeel.IN_POCKET.value,
            swing=0.0,
        ),
        velocity=VelocityModel(
            base_velocity=100,
            velocity_range=(95, 105),
            variance=0.02,
            pattern=VelocityPattern.EVEN.value,
            downbeat_accent=1.0,
        ),
    )


# =============================================================================
# PROFILE REGISTRY
# =============================================================================

# Pre-built profiles
BUILTIN_PROFILES: Dict[str, PlayerProfile] = {
    "tight_drummer": create_tight_drummer(),
    "loose_drummer": create_loose_drummer(),
    "funk_drummer": create_funk_drummer(),
    "trap_soul_drummer": create_trap_soul_drummer(),
    "lazy_bassist": create_lazy_bassist(),
    "tight_bassist": create_tight_bassist(),
    "funk_bassist": create_funk_bassist(),
    "jazz_pianist": create_jazz_pianist(),
    "tight_keys": create_tight_keys(),
    "lead_player": create_lead_player(),
    "pad_player": create_pad_player(),
    "machine_drums": create_machine_profile("drums"),
    "machine_bass": create_machine_profile("bass"),
    "machine_keys": create_machine_profile("chords"),
}

# Genre to profile mapping (role -> profile name)
GENRE_PROFILE_MAP: Dict[str, Dict[str, str]] = {
    "trap": {
        "drums": "tight_drummer",
        "bass": "tight_bassist",
        "chords": "tight_keys",
        "lead": "lead_player",
        "pad": "pad_player",
    },
    "trap_soul": {
        "drums": "trap_soul_drummer",
        "bass": "lazy_bassist",
        "chords": "tight_keys",
        "lead": "lead_player",
        "pad": "pad_player",
    },
    "boom_bap": {
        "drums": "loose_drummer",
        "bass": "lazy_bassist",
        "chords": "jazz_pianist",
        "lead": "lead_player",
        "pad": "pad_player",
    },
    "g_funk": {
        "drums": "funk_drummer",
        "bass": "funk_bassist",
        "chords": "jazz_pianist",
        "lead": "lead_player",
        "pad": "pad_player",
    },
    "lofi": {
        "drums": "loose_drummer",
        "bass": "lazy_bassist",
        "chords": "jazz_pianist",
        "lead": "lead_player",
        "pad": "pad_player",
    },
    "house": {
        "drums": "tight_drummer",
        "bass": "tight_bassist",
        "chords": "tight_keys",
        "lead": "lead_player",
        "pad": "pad_player",
    },
    "drill": {
        "drums": "tight_drummer",
        "bass": "tight_bassist",
        "chords": "tight_keys",
        "lead": "lead_player",
        "pad": "pad_player",
    },
    "rnb": {
        "drums": "funk_drummer",
        "bass": "funk_bassist",
        "chords": "jazz_pianist",
        "lead": "lead_player",
        "pad": "pad_player",
    },
    "ethiopian_traditional": {
        "drums": "loose_drummer",
        "bass": "lazy_bassist",
        "chords": "jazz_pianist",
        "lead": "lead_player",
        "pad": "pad_player",
    },
    "eskista": {
        "drums": "funk_drummer",
        "bass": "funk_bassist",
        "chords": "tight_keys",
        "lead": "lead_player",
        "pad": "pad_player",
    },
}


# =============================================================================
# API FUNCTIONS
# =============================================================================

def get_profile(name: str) -> Optional[PlayerProfile]:
    """Get a player profile by name.
    
    Args:
        name: Profile name (e.g., "tight_drummer", "lazy_bassist")
    
    Returns:
        PlayerProfile or None if not found
    """
    return BUILTIN_PROFILES.get(name)


def get_profile_for_genre(genre: str, role: str) -> PlayerProfile:
    """Get the appropriate profile for a genre and role.
    
    Args:
        genre: Music genre (e.g., "trap_soul", "boom_bap")
        role: Instrument role (e.g., "drums", "bass")
    
    Returns:
        PlayerProfile (defaults to natural feel if not found)
    """
    # Look up genre mapping
    genre_profiles = GENRE_PROFILE_MAP.get(genre, {})
    profile_name = genre_profiles.get(role)
    
    if profile_name:
        profile = BUILTIN_PROFILES.get(profile_name)
        if profile:
            return profile
    
    # Default profiles by role
    default_profiles = {
        "drums": "loose_drummer",
        "bass": "lazy_bassist",
        "chords": "tight_keys",
        "lead": "lead_player",
        "pad": "pad_player",
    }
    
    profile_name = default_profiles.get(role, "tight_keys")
    return BUILTIN_PROFILES.get(profile_name, create_machine_profile(role))


def apply_performance_model(
    notes: List[Dict],
    profile: PlayerProfile,
    total_ticks: int = 0,
    section_type: str = "verse",
) -> List[Dict]:
    """Apply performance model humanization to a list of notes.
    
    Args:
        notes: List of note dicts with pitch, start_tick, duration_ticks, velocity
        profile: PlayerProfile to apply
        total_ticks: Total song length (for drift calculation)
        section_type: Current section type
    
    Returns:
        List of humanized note dicts
    """
    result = []
    
    for note in notes:
        new_start, new_duration, new_velocity = profile.apply_to_note(
            pitch=note.get("pitch", 60),
            start_tick=note.get("start_tick", 0),
            duration_ticks=note.get("duration_ticks", 480),
            velocity=note.get("velocity", 100),
            total_ticks=total_ticks,
            section_type=section_type,
        )
        
        result.append({
            **note,
            "start_tick": new_start,
            "duration_ticks": new_duration,
            "velocity": new_velocity,
        })
    
    # Sort by start time
    result.sort(key=lambda n: (n["start_tick"], n["pitch"]))
    
    return result


def list_profiles() -> List[str]:
    """List all available profile names."""
    return list(BUILTIN_PROFILES.keys())


def get_profiles_for_genre(genre: str) -> Dict[str, PlayerProfile]:
    """Get all profiles appropriate for a genre.
    
    Args:
        genre: Music genre
    
    Returns:
        Dict mapping role -> PlayerProfile
    """
    result = {}
    genre_profiles = GENRE_PROFILE_MAP.get(genre, {})
    
    for role in ["drums", "bass", "chords", "lead", "pad"]:
        profile_name = genre_profiles.get(role)
        if profile_name and profile_name in BUILTIN_PROFILES:
            result[role] = BUILTIN_PROFILES[profile_name]
        else:
            result[role] = get_profile_for_genre(genre, role)
    
    return result


# =============================================================================
# MODULE TEST
# =============================================================================

if __name__ == "__main__":
    print("Testing Performance Models module...")
    
    # Test profile lookup
    profile = get_profile("funk_drummer")
    print(f"\nFunk Drummer profile:")
    print(f"  Name: {profile.name}")
    print(f"  Type: {profile.profile_type}")
    print(f"  Timing offset: {profile.timing.base_offset}")
    print(f"  Timing variance: {profile.timing.variance}")
    print(f"  Swing: {profile.timing.swing}")
    print(f"  Ghost probability: {profile.ghost_model.probability if profile.ghost_model else 0}")
    
    # Test genre lookup
    print("\nProfiles for trap_soul:")
    for role, prof in get_profiles_for_genre("trap_soul").items():
        print(f"  {role}: {prof.name}")
    
    # Test humanization
    print("\nTesting humanization:")
    test_notes = [
        {"pitch": 36, "start_tick": 0, "duration_ticks": 120, "velocity": 100},
        {"pitch": 38, "start_tick": 480, "duration_ticks": 120, "velocity": 95},
        {"pitch": 36, "start_tick": 960, "duration_ticks": 120, "velocity": 100},
        {"pitch": 38, "start_tick": 1440, "duration_ticks": 120, "velocity": 95},
    ]
    
    # Compare tight vs loose drummer
    tight = get_profile("tight_drummer")
    loose = get_profile("loose_drummer")
    
    tight_result = apply_performance_model(test_notes, tight, total_ticks=1920)
    loose_result = apply_performance_model(test_notes, loose, total_ticks=1920)
    
    print("\nOriginal vs Tight vs Loose:")
    for orig, t, l in zip(test_notes, tight_result, loose_result):
        print(f"  Original: tick={orig['start_tick']}, vel={orig['velocity']}")
        print(f"  Tight:    tick={t['start_tick']}, vel={t['velocity']}")
        print(f"  Loose:    tick={l['start_tick']}, vel={l['velocity']}")
        print()
    
    # Test serialization
    print("Testing serialization...")
    profile_dict = profile.to_dict()
    restored = PlayerProfile.from_dict(profile_dict)
    assert restored.name == profile.name
    assert restored.timing.swing == profile.timing.swing
    print("✅ Serialization round-trip successful!")
    
    # Test determinism
    print("\nTesting determinism...")
    random.seed(42)
    result1 = apply_performance_model(test_notes, loose)
    random.seed(42)
    result2 = apply_performance_model(test_notes, loose)
    
    for n1, n2 in zip(result1, result2):
        assert n1["start_tick"] == n2["start_tick"]
        assert n1["velocity"] == n2["velocity"]
    print("✅ Determinism verified!")
    
    print("\n✅ Performance Models module test complete!")
