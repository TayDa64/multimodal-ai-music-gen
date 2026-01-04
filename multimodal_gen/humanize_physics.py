"""
Physics-Aware Humanization Module

Provides realistic humanization for MIDI performances based on physical
constraints of human drummers, keyboardists, and other instrumentalists.

This module goes beyond simple random velocity/timing variation by modeling:
- Fatigue: Performance degradation at high BPM or dense subdivisions
- Limb Conflicts: Physical impossibilities (e.g., simultaneous hat/snare hits)
- Ghost Notes: Characteristic "feel" notes added by policy
- Hand Alternation: Realistic sticking patterns
- Emphasis Patterns: Genre-specific accent placement

Industry Reference:
- Logic Pro Humanize (basic)
- Superior Drummer Avatar (advanced limb modeling)
- EZdrummer Groove Agent (pattern-based)

Usage:
    from multimodal_gen.humanize_physics import PhysicsHumanizer, HumanizeConfig
    
    humanizer = PhysicsHumanizer(
        role="drums",
        bpm=145,
        genre="trap"
    )
    
    # Apply to a list of notes
    humanized_notes = humanizer.apply(notes)
    
    # Get decision log for debugging/UI
    decisions = humanizer.get_decision_log()
"""

from __future__ import annotations
import random
import math
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)

# Import local utilities
try:
    from .utils import (
        TICKS_PER_BEAT,
        TICKS_PER_16TH,
        TICKS_PER_8TH,
        TICKS_PER_BAR_4_4,
        humanize_velocity,
        humanize_timing,
        apply_drummer_physics,
    )
except ImportError:
    TICKS_PER_BEAT = 480
    TICKS_PER_16TH = 120
    TICKS_PER_8TH = 240
    TICKS_PER_BAR_4_4 = 1920
    
    def humanize_velocity(v, variation=0.1):
        return max(1, min(127, int(v * (1 + (random.random() - 0.5) * 2 * variation))))
    
    def humanize_timing(t, swing=0, timing_variation=0.02, is_offbeat=False):
        jitter = int(TICKS_PER_16TH * timing_variation * (random.random() * 2 - 1))
        return max(0, t + jitter)
    
    def apply_drummer_physics(v, is_strong_hand=True, accent=False):
        if not is_strong_hand:
            v = int(v * random.uniform(0.80, 0.90))
        if accent:
            v = int(v * random.uniform(1.10, 1.20))
        return max(30, min(127, v))


# =============================================================================
# ENUMERATIONS
# =============================================================================

class InstrumentRole(Enum):
    """Musical roles with different physics constraints."""
    DRUMS = "drums"
    BASS = "bass"
    KEYS = "keys"
    LEAD = "lead"
    PADS = "pads"
    STRINGS = "strings"


class LimbType(Enum):
    """Limbs used in drum performance."""
    RIGHT_HAND = "right_hand"
    LEFT_HAND = "left_hand"
    RIGHT_FOOT = "right_foot"
    LEFT_FOOT = "left_foot"


class DrumElement(Enum):
    """Standard drum kit elements with their typical limb assignments."""
    KICK = "kick"
    SNARE = "snare"
    HIHAT = "hihat"
    HIHAT_OPEN = "hihat_open"
    HIHAT_PEDAL = "hihat_pedal"
    RIDE = "ride"
    CRASH = "crash"
    TOM_HIGH = "tom_high"
    TOM_MID = "tom_mid"
    TOM_LOW = "tom_low"
    CLAP = "clap"
    PERC = "perc"


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class HumanizeConfig:
    """Configuration for physics-aware humanization."""
    
    # Enable/disable features
    apply_fatigue: bool = True
    apply_limb_conflicts: bool = True
    apply_ghost_notes: bool = True
    apply_hand_alternation: bool = True
    apply_emphasis: bool = True
    
    # Fatigue parameters
    fatigue_bpm_threshold: float = 140.0  # BPM above which fatigue kicks in
    fatigue_strength: float = 0.3  # Max velocity reduction from fatigue
    fatigue_density_threshold: int = 8  # Notes per beat triggering fatigue
    
    # Ghost note parameters
    ghost_note_probability: float = 0.4  # Chance of adding ghost notes
    ghost_note_velocity_min: int = 25
    ghost_note_velocity_max: int = 50
    ghost_note_elements: List[str] = field(default_factory=lambda: ["snare", "hihat"])
    
    # Timing parameters
    timing_variation: float = 0.025  # Max timing jitter (fraction of 16th)
    swing_amount: float = 0.0  # Applied to offbeats (0.0 - 0.5)
    
    # Limb physics
    weak_hand_factor: float = 0.85  # Weak hand velocity multiplier
    simultaneous_tolerance_ticks: int = 10  # Ticks within which notes are "simultaneous"
    
    # Emphasis patterns (beat positions that get accent, 1-indexed within bar)
    emphasis_beats: List[float] = field(default_factory=lambda: [1.0, 3.0])  # Downbeats


@dataclass
class Note:
    """Simple note representation for humanization."""
    pitch: int
    start_tick: int
    duration_ticks: int
    velocity: int
    channel: int = 0
    
    # Metadata for humanization tracking
    element: str = ""  # e.g., "kick", "snare", "hihat"
    limb: Optional[str] = None  # Assigned limb
    is_ghost: bool = False
    humanize_decision: str = ""  # Log of what was applied


@dataclass
class HumanizeDecision:
    """Record of a humanization decision for debugging/UI."""
    note_index: int
    original_velocity: int
    original_timing: int
    new_velocity: int
    new_timing: int
    reason: str
    limb_assigned: Optional[str] = None


# =============================================================================
# LIMB ASSIGNMENT
# =============================================================================

# Default limb assignments for drum elements
DEFAULT_LIMB_ASSIGNMENTS: Dict[str, LimbType] = {
    "kick": LimbType.RIGHT_FOOT,
    "kick2": LimbType.LEFT_FOOT,
    "snare": LimbType.LEFT_HAND,  # Most drummers lead with right, snare on left
    "snare_rim": LimbType.LEFT_HAND,
    "hihat": LimbType.RIGHT_HAND,  # Typical crossed setup
    "hihat_closed": LimbType.RIGHT_HAND,
    "hihat_open": LimbType.RIGHT_HAND,
    "hihat_pedal": LimbType.LEFT_FOOT,
    "ride": LimbType.RIGHT_HAND,
    "crash": LimbType.RIGHT_HAND,
    "crash2": LimbType.LEFT_HAND,
    "tom_high": LimbType.RIGHT_HAND,
    "tom_mid": LimbType.LEFT_HAND,
    "tom_low": LimbType.RIGHT_HAND,
    "clap": LimbType.LEFT_HAND,
    "perc": LimbType.RIGHT_HAND,
}


# =============================================================================
# GENRE-SPECIFIC GHOST NOTE POLICIES
# =============================================================================

GHOST_NOTE_POLICIES: Dict[str, Dict[str, Any]] = {
    "trap": {
        "elements": ["hihat"],
        "probability": 0.15,
        "velocity_range": (30, 50),
        "positions": ["16th_offbeat"],  # Ghost hats on 16th offbeats
    },
    "boom_bap": {
        "elements": ["snare"],
        "probability": 0.45,
        "velocity_range": (25, 45),
        "positions": ["before_2_4", "after_2_4"],  # Ghosts around backbeats
    },
    "g_funk": {
        "elements": ["snare", "hihat"],
        "probability": 0.35,
        "velocity_range": (30, 55),
        "positions": ["16th_offbeat", "before_2_4"],
    },
    "lofi": {
        "elements": ["snare"],
        "probability": 0.5,
        "velocity_range": (20, 40),
        "positions": ["before_2_4", "random"],
    },
    "house": {
        "elements": ["hihat"],
        "probability": 0.25,
        "velocity_range": (40, 60),
        "positions": ["offbeat_8th"],
    },
    "default": {
        "elements": ["snare"],
        "probability": 0.3,
        "velocity_range": (30, 50),
        "positions": ["before_2_4"],
    },
}


# =============================================================================
# PHYSICS HUMANIZER
# =============================================================================

class PhysicsHumanizer:
    """
    Physics-aware humanizer for MIDI performances.
    
    Models physical constraints of human performers to create
    more realistic MIDI output.
    """
    
    def __init__(
        self,
        role: str = "drums",
        bpm: float = 90.0,
        genre: str = "default",
        config: Optional[HumanizeConfig] = None
    ):
        """
        Initialize the physics humanizer.
        
        Args:
            role: Instrument role (drums, bass, keys, lead, pads)
            bpm: Tempo in beats per minute
            genre: Genre for policy selection
            config: Optional custom configuration
        """
        self.role = InstrumentRole(role) if isinstance(role, str) else role
        self.bpm = bpm
        self.genre = genre.lower().replace(" ", "_").replace("-", "_")
        self.config = config or HumanizeConfig()
        
        self.decisions: List[HumanizeDecision] = []
        self._limb_last_hit: Dict[LimbType, int] = {}  # Track limb activity
        
        # Load genre-specific ghost note policy
        self._ghost_policy = GHOST_NOTE_POLICIES.get(
            self.genre, 
            GHOST_NOTE_POLICIES["default"]
        )
        
        logger.debug(f"PhysicsHumanizer initialized: role={role}, bpm={bpm}, genre={genre}")
    
    def apply(self, notes: List[Note]) -> List[Note]:
        """
        Apply physics-aware humanization to a list of notes.
        
        Args:
            notes: List of Note objects to humanize
            
        Returns:
            List of humanized notes (new list, original unmodified)
        """
        if not notes:
            return []
        
        self.decisions.clear()
        self._limb_last_hit.clear()
        
        # Sort by start time for proper processing
        sorted_notes = sorted(notes, key=lambda n: n.start_tick)
        result = []
        
        for i, note in enumerate(sorted_notes):
            humanized = self._humanize_note(note, i, sorted_notes)
            result.append(humanized)
        
        # Add ghost notes if enabled (for drums)
        if self.role == InstrumentRole.DRUMS and self.config.apply_ghost_notes:
            ghost_notes = self._generate_ghost_notes(result)
            result.extend(ghost_notes)
            result.sort(key=lambda n: n.start_tick)
        
        logger.debug(f"Humanized {len(notes)} notes, added {len(result) - len(notes)} ghost notes")
        return result
    
    def _humanize_note(
        self, 
        note: Note, 
        index: int, 
        all_notes: List[Note]
    ) -> Note:
        """Humanize a single note with physics constraints."""
        
        # Create a copy to avoid modifying original
        humanized = Note(
            pitch=note.pitch,
            start_tick=note.start_tick,
            duration_ticks=note.duration_ticks,
            velocity=note.velocity,
            channel=note.channel,
            element=note.element,
            limb=note.limb,
            is_ghost=note.is_ghost,
            humanize_decision=""
        )
        
        original_velocity = humanized.velocity
        original_timing = humanized.start_tick
        reasons = []
        
        # 1. Assign limb (for drums)
        if self.role == InstrumentRole.DRUMS:
            humanized.limb = self._assign_limb(humanized.element)
        
        # 2. Apply fatigue
        if self.config.apply_fatigue:
            fatigue_factor = self._calculate_fatigue(index, all_notes)
            if fatigue_factor < 1.0:
                humanized.velocity = int(humanized.velocity * fatigue_factor)
                reasons.append(f"fatigue({fatigue_factor:.2f})")
        
        # 3. Apply limb conflict resolution
        if self.role == InstrumentRole.DRUMS and self.config.apply_limb_conflicts:
            conflict_adj = self._resolve_limb_conflict(humanized, all_notes, index)
            if conflict_adj != 0:
                humanized.start_tick += conflict_adj
                reasons.append(f"limb_conflict({conflict_adj:+d})")
        
        # 4. Apply hand alternation physics
        if self.config.apply_hand_alternation and humanized.limb:
            limb_type = LimbType(humanized.limb) if isinstance(humanized.limb, str) else humanized.limb
            is_strong = limb_type in [LimbType.RIGHT_HAND, LimbType.RIGHT_FOOT]
            humanized.velocity = apply_drummer_physics(
                humanized.velocity,
                is_strong_hand=is_strong,
                accent=self._is_emphasis_beat(humanized.start_tick)
            )
            if not is_strong:
                reasons.append("weak_hand")
        
        # 5. Apply emphasis
        if self.config.apply_emphasis and self._is_emphasis_beat(humanized.start_tick):
            accent_boost = int(humanized.velocity * 0.1)
            humanized.velocity = min(127, humanized.velocity + accent_boost)
            reasons.append("emphasis")
        
        # 6. Apply base humanization (timing jitter, velocity variation)
        humanized.velocity = humanize_velocity(humanized.velocity, variation=0.08)
        
        is_offbeat = self._is_offbeat(humanized.start_tick)
        humanized.start_tick = humanize_timing(
            humanized.start_tick,
            swing=self.config.swing_amount,
            timing_variation=self.config.timing_variation,
            is_offbeat=is_offbeat
        )
        
        # Clamp velocity
        humanized.velocity = max(1, min(127, humanized.velocity))
        
        # Record decision
        humanized.humanize_decision = ", ".join(reasons) if reasons else "base"
        self.decisions.append(HumanizeDecision(
            note_index=index,
            original_velocity=original_velocity,
            original_timing=original_timing,
            new_velocity=humanized.velocity,
            new_timing=humanized.start_tick,
            reason=humanized.humanize_decision,
            limb_assigned=humanized.limb
        ))
        
        # Update limb tracking
        if humanized.limb:
            limb = LimbType(humanized.limb) if isinstance(humanized.limb, str) else humanized.limb
            self._limb_last_hit[limb] = humanized.start_tick
        
        return humanized
    
    def _assign_limb(self, element: str) -> Optional[str]:
        """Assign a limb to a drum element."""
        if not element:
            return None
        
        element_lower = element.lower()
        
        # Check direct mapping
        if element_lower in DEFAULT_LIMB_ASSIGNMENTS:
            return DEFAULT_LIMB_ASSIGNMENTS[element_lower].value
        
        # Fuzzy matching for common variations
        if "kick" in element_lower or "bass" in element_lower:
            return LimbType.RIGHT_FOOT.value
        if "snare" in element_lower:
            return LimbType.LEFT_HAND.value
        if "hat" in element_lower:
            return LimbType.RIGHT_HAND.value
        if "tom" in element_lower:
            return LimbType.RIGHT_HAND.value  # Default, should alternate
        if "ride" in element_lower or "crash" in element_lower:
            return LimbType.RIGHT_HAND.value
        
        return None
    
    def _calculate_fatigue(self, note_index: int, all_notes: List[Note]) -> float:
        """
        Calculate fatigue factor based on BPM and note density.
        
        Returns a multiplier (1.0 = no fatigue, 0.7 = high fatigue).
        """
        if self.bpm < self.config.fatigue_bpm_threshold:
            return 1.0
        
        # Calculate local density (notes in the surrounding beat)
        if note_index >= len(all_notes):
            return 1.0
        
        current_tick = all_notes[note_index].start_tick
        window_start = current_tick - TICKS_PER_BEAT
        window_end = current_tick + TICKS_PER_BEAT
        
        notes_in_window = sum(
            1 for n in all_notes 
            if window_start <= n.start_tick <= window_end
        )
        
        # Calculate fatigue based on BPM excess and density
        bpm_excess = (self.bpm - self.config.fatigue_bpm_threshold) / 60.0
        density_factor = max(0, notes_in_window - self.config.fatigue_density_threshold) / 8.0
        
        fatigue = min(self.config.fatigue_strength, bpm_excess * 0.1 + density_factor * 0.15)
        
        return 1.0 - fatigue
    
    def _resolve_limb_conflict(
        self, 
        note: Note, 
        all_notes: List[Note], 
        index: int
    ) -> int:
        """
        Check for limb conflicts and return timing adjustment.
        
        A conflict occurs when the same limb would need to hit two
        different drums at nearly the same time.
        """
        if not note.limb:
            return 0
        
        limb = LimbType(note.limb) if isinstance(note.limb, str) else note.limb
        tolerance = self.config.simultaneous_tolerance_ticks
        
        # Check nearby notes
        for i, other in enumerate(all_notes):
            if i == index:
                continue
            
            if abs(other.start_tick - note.start_tick) > tolerance:
                continue
            
            other_limb = self._assign_limb(other.element)
            if other_limb and LimbType(other_limb) == limb:
                # Same limb, different time - flam or roll
                # Push the later note slightly later
                if other.start_tick <= note.start_tick:
                    return int(TICKS_PER_16TH * 0.2)  # Small offset
        
        return 0
    
    def _is_emphasis_beat(self, tick: int) -> bool:
        """Check if tick falls on an emphasis beat."""
        position_in_bar = (tick % TICKS_PER_BAR_4_4) / TICKS_PER_BEAT
        
        for beat in self.config.emphasis_beats:
            # Allow small tolerance for floating point
            if abs(position_in_bar - (beat - 1)) < 0.1:
                return True
        
        return False
    
    def _is_offbeat(self, tick: int) -> bool:
        """Check if tick is on an offbeat (for swing application)."""
        position_in_beat = tick % TICKS_PER_BEAT
        
        # 8th note offbeats
        if abs(position_in_beat - TICKS_PER_8TH) < TICKS_PER_16TH:
            return True
        
        # 16th note offbeats
        if abs(position_in_beat - TICKS_PER_16TH) < TICKS_PER_16TH // 2:
            return True
        if abs(position_in_beat - (TICKS_PER_16TH * 3)) < TICKS_PER_16TH // 2:
            return True
        
        return False
    
    def _generate_ghost_notes(self, notes: List[Note]) -> List[Note]:
        """
        Generate ghost notes based on genre policy.
        
        Ghost notes are soft hits that add "feel" to drum patterns,
        especially common on snare in hip-hop and funk.
        """
        ghost_notes = []
        policy = self._ghost_policy
        
        if random.random() > policy["probability"]:
            return ghost_notes
        
        # Find existing backbeat snares (beats 2 and 4)
        snare_hits = [n for n in notes if "snare" in n.element.lower()]
        
        for snare in snare_hits:
            if random.random() > policy["probability"]:
                continue
            
            for pos_type in policy["positions"]:
                ghost = self._create_ghost_note(snare, pos_type, policy)
                if ghost:
                    ghost_notes.append(ghost)
        
        # Cap ghost notes to avoid over-saturation
        max_ghosts = max(2, len(notes) // 4)
        return ghost_notes[:max_ghosts]
    
    def _create_ghost_note(
        self, 
        reference_note: Note, 
        position_type: str,
        policy: Dict
    ) -> Optional[Note]:
        """Create a single ghost note relative to a reference note."""
        
        vel_min, vel_max = policy["velocity_range"]
        velocity = random.randint(vel_min, vel_max)
        
        # Calculate position based on type
        if position_type == "before_2_4":
            # Ghost 16th before the backbeat
            offset = -TICKS_PER_16TH + random.randint(-10, 10)
        elif position_type == "after_2_4":
            # Ghost 16th after the backbeat
            offset = TICKS_PER_16TH + random.randint(-10, 10)
        elif position_type == "16th_offbeat":
            # 16th note offbeat
            offset = random.choice([-TICKS_PER_16TH, TICKS_PER_16TH])
        elif position_type == "offbeat_8th":
            # 8th note offbeat
            offset = TICKS_PER_8TH
        elif position_type == "random":
            # Random position within a beat
            offset = random.randint(-TICKS_PER_8TH, TICKS_PER_8TH)
        else:
            return None
        
        new_tick = reference_note.start_tick + offset
        if new_tick < 0:
            return None
        
        return Note(
            pitch=reference_note.pitch,
            start_tick=new_tick,
            duration_ticks=reference_note.duration_ticks // 2,  # Shorter
            velocity=velocity,
            channel=reference_note.channel,
            element=reference_note.element + "_ghost",
            limb=reference_note.limb,
            is_ghost=True,
            humanize_decision="ghost_note"
        )
    
    def get_decision_log(self) -> List[Dict[str, Any]]:
        """
        Get a log of all humanization decisions made.
        
        Returns:
            List of decision dictionaries for debugging/UI display
        """
        return [
            {
                "note_index": d.note_index,
                "original_velocity": d.original_velocity,
                "original_timing": d.original_timing,
                "new_velocity": d.new_velocity,
                "new_timing": d.new_timing,
                "velocity_change": d.new_velocity - d.original_velocity,
                "timing_change": d.new_timing - d.original_timing,
                "reason": d.reason,
                "limb": d.limb_assigned
            }
            for d in self.decisions
        ]
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of humanization applied."""
        if not self.decisions:
            return {"notes_processed": 0}
        
        velocity_changes = [d.new_velocity - d.original_velocity for d in self.decisions]
        timing_changes = [d.new_timing - d.original_timing for d in self.decisions]
        
        return {
            "notes_processed": len(self.decisions),
            "avg_velocity_change": sum(velocity_changes) / len(velocity_changes),
            "avg_timing_change_ticks": sum(timing_changes) / len(timing_changes),
            "fatigue_applied": any("fatigue" in d.reason for d in self.decisions),
            "limb_conflicts_resolved": sum(1 for d in self.decisions if "limb_conflict" in d.reason),
            "ghost_notes_added": sum(1 for d in self.decisions if d.reason == "ghost_note"),
            "genre": self.genre,
            "bpm": self.bpm,
            "role": self.role.value
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def humanize_drums(
    notes: List[Note],
    bpm: float = 90.0,
    genre: str = "default",
    config: Optional[HumanizeConfig] = None
) -> List[Note]:
    """
    Convenience function to humanize drum notes.
    
    Args:
        notes: List of drum notes
        bpm: Tempo
        genre: Genre for policy selection
        config: Optional custom configuration
        
    Returns:
        Humanized notes
    """
    humanizer = PhysicsHumanizer(role="drums", bpm=bpm, genre=genre, config=config)
    return humanizer.apply(notes)


def humanize_bass(
    notes: List[Note],
    bpm: float = 90.0,
    genre: str = "default",
    config: Optional[HumanizeConfig] = None
) -> List[Note]:
    """
    Convenience function to humanize bass notes.
    
    Bass humanization focuses on timing feel and velocity dynamics
    rather than limb physics.
    """
    if config is None:
        config = HumanizeConfig(
            apply_limb_conflicts=False,
            apply_ghost_notes=False,
            apply_hand_alternation=False,
            timing_variation=0.03,  # Bassists tend to be more locked
        )
    
    humanizer = PhysicsHumanizer(role="bass", bpm=bpm, genre=genre, config=config)
    return humanizer.apply(notes)


def humanize_keys(
    notes: List[Note],
    bpm: float = 90.0,
    genre: str = "default",
    config: Optional[HumanizeConfig] = None
) -> List[Note]:
    """
    Convenience function to humanize keyboard notes.
    
    Keys humanization applies chord voicing dynamics and subtle
    timing variations.
    """
    if config is None:
        config = HumanizeConfig(
            apply_limb_conflicts=False,
            apply_ghost_notes=False,
            apply_hand_alternation=False,
            timing_variation=0.02,
            apply_emphasis=True,
        )
    
    humanizer = PhysicsHumanizer(role="keys", bpm=bpm, genre=genre, config=config)
    return humanizer.apply(notes)


# =============================================================================
# CLI TESTING
# =============================================================================

if __name__ == "__main__":
    import sys
    
    print("🥁 Physics Humanizer Test")
    print("=" * 60)
    
    # Create test notes (simple drum pattern)
    test_notes = [
        Note(pitch=36, start_tick=0, duration_ticks=120, velocity=100, element="kick"),
        Note(pitch=38, start_tick=TICKS_PER_BEAT, duration_ticks=120, velocity=95, element="snare"),
        Note(pitch=36, start_tick=TICKS_PER_BEAT * 2, duration_ticks=120, velocity=100, element="kick"),
        Note(pitch=38, start_tick=TICKS_PER_BEAT * 3, duration_ticks=120, velocity=95, element="snare"),
    ]
    
    # Add hi-hats
    for i in range(8):
        test_notes.append(Note(
            pitch=42,
            start_tick=i * TICKS_PER_8TH,
            duration_ticks=60,
            velocity=80,
            element="hihat"
        ))
    
    # Test different genres
    for genre in ["trap", "boom_bap", "g_funk", "lofi"]:
        print(f"\n📀 Genre: {genre}")
        print("-" * 40)
        
        humanizer = PhysicsHumanizer(role="drums", bpm=95, genre=genre)
        humanized = humanizer.apply(test_notes)
        
        summary = humanizer.get_summary()
        print(f"   Notes processed: {summary['notes_processed']}")
        print(f"   Avg velocity change: {summary['avg_velocity_change']:.1f}")
        print(f"   Ghost notes added: {summary['ghost_notes_added']}")
        print(f"   Limb conflicts: {summary['limb_conflicts_resolved']}")
    
    print("\n✅ Test complete")
