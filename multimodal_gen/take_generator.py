"""
Take Generator - Stochastic Multi-Take Generation System

This module implements Milestone D of likuTasks.md:
"Generate multiple believable takes per role (bass/lead/harmony/drums)
and represent them as parallel take lanes so JUCE can expose comping."

Key Concepts:
    - TakeLane: Parallel variation of a clip with its own seed
    - Variation Axes: Rhythm, pitch, timing, ornament, fill
    - Deterministic: Same seed always produces same take
    - Per-Role: Different variation strategies for drums vs lead vs bass

Variation Types:
    - rhythm: Change note placements, syncopation
    - pitch: Alternate voicings, octave shifts, note substitutions
    - timing: Push/pull feel, groove variations
    - ornament: Add/remove grace notes, fills, ghost notes
    - intensity: Velocity/dynamics variations
    - fill: Generate different fills at section boundaries

Usage:
    from multimodal_gen.take_generator import TakeGenerator, TakeConfig
    
    generator = TakeGenerator()
    takes = generator.generate_takes(
        clip_notes=original_notes,
        role="lead",
        config=TakeConfig(num_takes=3, variation_axis="rhythm")
    )

Integration with SessionGraph:
    - Each Clip gets TakeLane objects appended
    - TakeMetadata stores seed, variation_type, parameters
    - Active take index tracks which take is "comped"
"""

import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any, Callable
from enum import Enum
from copy import deepcopy
import hashlib

# Import local utilities
try:
    from .utils import (
        TICKS_PER_BEAT,
        TICKS_PER_16TH,
        TICKS_PER_8TH,
        TICKS_PER_BAR_4_4,
        humanize_velocity,
        humanize_timing,
    )
except ImportError:
    # Fallback for direct execution
    TICKS_PER_BEAT = 480
    TICKS_PER_16TH = TICKS_PER_BEAT // 4
    TICKS_PER_8TH = TICKS_PER_BEAT // 2
    TICKS_PER_BAR_4_4 = TICKS_PER_BEAT * 4
    
    def humanize_velocity(v, variation=0.1):
        return max(1, min(127, int(v * (1 + (random.random() - 0.5) * 2 * variation))))
    
    def humanize_timing(t, variation=0.03):
        return int(t + (random.random() - 0.5) * 2 * variation * TICKS_PER_16TH)


# =============================================================================
# ENUMERATIONS
# =============================================================================

class VariationAxis(Enum):
    """Axes along which takes can vary."""
    RHYTHM = "rhythm"          # Note placements, syncopation
    PITCH = "pitch"            # Voicings, octaves, substitutions
    TIMING = "timing"          # Push/pull, micro-timing
    ORNAMENT = "ornament"      # Grace notes, fills, ghosts
    INTENSITY = "intensity"    # Velocity, dynamics
    FILL = "fill"              # Fills at section boundaries
    COMBINED = "combined"      # All axes


class RoleVariationStrategy(Enum):
    """How each role should vary between takes."""
    DRUMS_FEEL = "drums_feel"       # Mainly timing + ghost notes
    BASS_GROOVE = "bass_groove"     # Timing + note length + octaves
    LEAD_PHRASE = "lead_phrase"     # Pitch + ornaments + rhythm
    CHORDS_VOICING = "chords_voicing"  # Voicing + rhythm
    PAD_TEXTURE = "pad_texture"     # Timing + intensity only


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class NoteVariation:
    """A single note with variation parameters."""
    pitch: int
    start_tick: int
    duration_ticks: int
    velocity: int
    channel: int = 0
    
    # Variation tracking
    original_pitch: Optional[int] = None
    original_start: Optional[int] = None
    was_added: bool = False
    was_removed: bool = False
    variation_reason: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "pitch": self.pitch,
            "start_tick": self.start_tick,
            "duration_ticks": self.duration_ticks,
            "velocity": self.velocity,
            "channel": self.channel,
            "original_pitch": self.original_pitch,
            "original_start": self.original_start,
            "was_added": self.was_added,
            "was_removed": self.was_removed,
            "variation_reason": self.variation_reason,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "NoteVariation":
        return cls(**data)


@dataclass
class TakeLane:
    """A parallel take lane containing a variation of a clip.
    
    This is the core data structure for the takes system:
    - Each TakeLane represents one "performance" of a clip
    - Contains modified notes from the original
    - Tracks what variations were applied
    
    JUCE will use this to:
    - Display stacked take lanes visually
    - Allow clicking to "comp" sections from different takes
    - Audition takes in place during playback
    """
    take_id: int
    seed: int
    variation_type: str  # VariationAxis value
    notes: List[NoteVariation] = field(default_factory=list)
    
    # Generation parameters (for reproducibility)
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Variation summary
    notes_added: int = 0
    notes_removed: int = 0
    notes_modified: int = 0
    avg_timing_shift: float = 0.0
    avg_velocity_change: float = 0.0
    
    # MIDI output reference
    midi_track_name: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "take_id": self.take_id,
            "seed": self.seed,
            "variation_type": self.variation_type,
            "notes": [n.to_dict() for n in self.notes],
            "parameters": self.parameters,
            "notes_added": self.notes_added,
            "notes_removed": self.notes_removed,
            "notes_modified": self.notes_modified,
            "avg_timing_shift": self.avg_timing_shift,
            "avg_velocity_change": self.avg_velocity_change,
            "midi_track_name": self.midi_track_name,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "TakeLane":
        notes_data = data.pop("notes", [])
        lane = cls(**{k: v for k, v in data.items() if k != "notes"})
        lane.notes = [NoteVariation.from_dict(n) for n in notes_data]
        return lane


@dataclass
class TakeConfig:
    """Configuration for take generation."""
    num_takes: int = 3
    variation_axis: str = "combined"  # VariationAxis value
    
    # Variation intensity (0.0 = identical, 1.0 = maximum variation)
    variation_intensity: float = 0.5
    
    # Per-axis weights (when using combined)
    rhythm_weight: float = 0.3
    pitch_weight: float = 0.2
    timing_weight: float = 0.4
    ornament_weight: float = 0.3
    intensity_weight: float = 0.2
    
    # Role-specific
    role: str = "lead"
    genre: str = "trap_soul"
    
    # Reproducibility
    base_seed: Optional[int] = None
    
    # Section context
    section_type: str = "verse"
    is_fill_opportunity: bool = False
    
    def get_take_seed(self, take_index: int) -> int:
        """Generate deterministic seed for a specific take."""
        if self.base_seed is None:
            self.base_seed = random.randint(0, 2**31)
        
        # Combine base seed with take index deterministically
        content = f"{self.base_seed}_{take_index}_{self.variation_axis}"
        return int(hashlib.md5(content.encode()).hexdigest()[:8], 16)


@dataclass
class TakeSet:
    """A complete set of takes for a clip."""
    clip_id: str
    role: str
    original_note_count: int
    takes: List[TakeLane] = field(default_factory=list)
    config: Optional[TakeConfig] = None
    
    # Active take tracking
    active_take_index: int = 0
    
    def get_active_take(self) -> Optional[TakeLane]:
        """Get the currently active/comped take."""
        if 0 <= self.active_take_index < len(self.takes):
            return self.takes[self.active_take_index]
        return None
    
    def to_dict(self) -> Dict:
        return {
            "clip_id": self.clip_id,
            "role": self.role,
            "original_note_count": self.original_note_count,
            "takes": [t.to_dict() for t in self.takes],
            "config": self.config.__dict__ if self.config else None,
            "active_take_index": self.active_take_index,
        }


# =============================================================================
# VARIATION FUNCTIONS
# =============================================================================

def _vary_rhythm(notes: List[NoteVariation], rng: random.Random, 
                 intensity: float, role: str) -> List[NoteVariation]:
    """Apply rhythm variations (note placements, syncopation).
    
    Strategies:
    - Drums: Shift beats slightly, add/remove ghost notes
    - Bass: Change rhythmic patterns, anticipate/delay
    - Lead: Syncopation, phrase boundary shifts
    - Chords: Strum timing, rhythmic hits
    """
    result = []
    
    # Role-specific parameters
    if role in ["drums", "percussion"]:
        # Drums: subtle shifts, ghost note probability
        shift_range = int(TICKS_PER_16TH * 0.5 * intensity)
        add_ghost_prob = 0.15 * intensity
        remove_prob = 0.05 * intensity
    elif role == "bass":
        # Bass: anticipation/push
        shift_range = int(TICKS_PER_16TH * intensity)
        add_ghost_prob = 0.0
        remove_prob = 0.08 * intensity
    elif role == "lead":
        # Lead: more freedom
        shift_range = int(TICKS_PER_8TH * 0.5 * intensity)
        add_ghost_prob = 0.1 * intensity
        remove_prob = 0.1 * intensity
    else:
        # Chords/pads: minimal rhythm change
        shift_range = int(TICKS_PER_16TH * 0.3 * intensity)
        add_ghost_prob = 0.0
        remove_prob = 0.05 * intensity
    
    for note in notes:
        # Remove note with probability
        if rng.random() < remove_prob:
            removed = deepcopy(note)
            removed.was_removed = True
            removed.variation_reason = "rhythm_variation_removal"
            # Still include in tracking but mark as removed
            continue
        
        # Shift timing
        varied = deepcopy(note)
        if shift_range > 0:
            shift = rng.randint(-shift_range, shift_range)
            varied.original_start = varied.start_tick
            varied.start_tick = max(0, varied.start_tick + shift)
            varied.variation_reason = "rhythm_shift"
        
        result.append(varied)
        
        # Add ghost note after
        if rng.random() < add_ghost_prob and role in ["drums", "lead"]:
            ghost = NoteVariation(
                pitch=note.pitch,
                start_tick=note.start_tick + TICKS_PER_16TH,
                duration_ticks=min(note.duration_ticks, TICKS_PER_16TH),
                velocity=max(30, int(note.velocity * 0.5)),
                channel=note.channel,
                was_added=True,
                variation_reason="ghost_note_added"
            )
            result.append(ghost)
    
    return result


def _vary_pitch(notes: List[NoteVariation], rng: random.Random,
                intensity: float, role: str, 
                scale_notes: List[int] = None) -> List[NoteVariation]:
    """Apply pitch variations (voicings, octaves, substitutions).
    
    Strategies:
    - Lead: Neighbor tones, octave jumps, passing tones
    - Chords: Voice leading, inversion changes
    - Bass: Octave variations, approach notes
    - Drums: Don't vary pitch (except cymbal choices)
    """
    result = []
    
    if role in ["drums", "percussion"]:
        # Drums: only cymbal variations
        return [deepcopy(n) for n in notes]
    
    # Default scale if not provided (chromatic within octave)
    if scale_notes is None:
        scale_notes = list(range(0, 128))
    
    # Role-specific parameters
    if role == "bass":
        octave_shift_prob = 0.15 * intensity
        neighbor_prob = 0.1 * intensity
        max_shift = 12  # One octave
    elif role == "lead":
        octave_shift_prob = 0.1 * intensity
        neighbor_prob = 0.2 * intensity
        max_shift = 2  # Steps
    else:  # chords, pad
        octave_shift_prob = 0.05 * intensity
        neighbor_prob = 0.1 * intensity
        max_shift = 2
    
    for note in notes:
        varied = deepcopy(note)
        
        # Octave shift
        if rng.random() < octave_shift_prob:
            direction = rng.choice([-12, 12])
            new_pitch = note.pitch + direction
            if 0 <= new_pitch <= 127:
                varied.original_pitch = varied.pitch
                varied.pitch = new_pitch
                varied.variation_reason = "octave_shift"
        
        # Neighbor tone substitution
        elif rng.random() < neighbor_prob:
            direction = rng.choice([-1, 1]) * rng.randint(1, max_shift)
            new_pitch = note.pitch + direction
            if 0 <= new_pitch <= 127:
                varied.original_pitch = varied.pitch
                varied.pitch = new_pitch
                varied.variation_reason = "neighbor_tone"
        
        result.append(varied)
    
    return result


def _vary_timing(notes: List[NoteVariation], rng: random.Random,
                 intensity: float, role: str) -> List[NoteVariation]:
    """Apply micro-timing variations (push/pull feel).
    
    This creates the "groove" differences between takes:
    - Laid-back feel (everything slightly late)
    - Pushing feel (slightly ahead)
    - Loose feel (random variance)
    - Tight feel (minimal variance, close to grid)
    """
    result = []
    
    # Determine feel type for this take
    feel_types = ["laid_back", "pushing", "loose", "tight"]
    feel = rng.choice(feel_types)
    
    # Role-specific timing variance
    if role in ["drums", "percussion"]:
        max_variance = int(TICKS_PER_16TH * 0.15 * intensity)
    elif role == "bass":
        max_variance = int(TICKS_PER_16TH * 0.2 * intensity)
    else:
        max_variance = int(TICKS_PER_16TH * 0.25 * intensity)
    
    for note in notes:
        varied = deepcopy(note)
        
        if feel == "laid_back":
            # Everything slightly late
            shift = rng.randint(0, max_variance)
        elif feel == "pushing":
            # Everything slightly early
            shift = -rng.randint(0, max_variance)
        elif feel == "loose":
            # Random variance
            shift = rng.randint(-max_variance, max_variance)
        else:  # tight
            # Minimal variance
            shift = rng.randint(-max_variance // 3, max_variance // 3)
        
        varied.original_start = varied.start_tick
        varied.start_tick = max(0, varied.start_tick + shift)
        varied.variation_reason = f"timing_{feel}"
        
        result.append(varied)
    
    return result


def _vary_ornament(notes: List[NoteVariation], rng: random.Random,
                   intensity: float, role: str,
                   section_type: str = "verse") -> List[NoteVariation]:
    """Apply ornament variations (grace notes, fills, trills).
    
    Strategies:
    - Lead: Grace notes before accents, mordents, turns
    - Drums: Flams, rolls, drags
    - Bass: Slides, hammer-ons (represented as quick grace notes)
    - Chords: Arpeggiated vs block
    """
    result = []
    
    # Role-specific ornament probability
    if role == "lead":
        grace_prob = 0.15 * intensity
        trill_prob = 0.05 * intensity
    elif role in ["drums", "percussion"]:
        grace_prob = 0.1 * intensity  # Flams
        trill_prob = 0.03 * intensity  # Rolls
    elif role == "bass":
        grace_prob = 0.08 * intensity
        trill_prob = 0.0
    else:
        grace_prob = 0.0
        trill_prob = 0.0
    
    # Increase ornamentation at section boundaries
    if section_type in ["drop", "chorus", "outro"]:
        grace_prob *= 1.5
        trill_prob *= 1.5
    
    for i, note in enumerate(notes):
        # Add grace note before
        if rng.random() < grace_prob:
            grace_pitch = note.pitch + rng.choice([-2, -1, 1, 2])
            if 0 <= grace_pitch <= 127:
                grace = NoteVariation(
                    pitch=grace_pitch,
                    start_tick=note.start_tick - TICKS_PER_16TH // 2,
                    duration_ticks=TICKS_PER_16TH // 2,
                    velocity=max(30, int(note.velocity * 0.7)),
                    channel=note.channel,
                    was_added=True,
                    variation_reason="grace_note"
                )
                if grace.start_tick >= 0:
                    result.append(grace)
        
        # Main note
        result.append(deepcopy(note))
        
        # Add trill after
        if rng.random() < trill_prob:
            trill_pitch = note.pitch + rng.choice([1, 2])
            for j in range(2):  # Two trill notes
                trill = NoteVariation(
                    pitch=note.pitch if j % 2 == 0 else trill_pitch,
                    start_tick=note.start_tick + note.duration_ticks + j * TICKS_PER_16TH // 2,
                    duration_ticks=TICKS_PER_16TH // 2,
                    velocity=max(40, int(note.velocity * 0.6)),
                    channel=note.channel,
                    was_added=True,
                    variation_reason="trill"
                )
                if 0 <= trill.pitch <= 127:
                    result.append(trill)
    
    return result


def _vary_intensity(notes: List[NoteVariation], rng: random.Random,
                    intensity: float, role: str) -> List[NoteVariation]:
    """Apply velocity/dynamics variations.
    
    Creates different dynamic profiles:
    - Even dynamics (minimal variation)
    - Accented downbeats
    - Building intensity
    - Fading intensity
    """
    result = []
    
    # Determine intensity profile for this take
    profiles = ["even", "accented", "building", "fading"]
    profile = rng.choice(profiles)
    
    # Role-specific velocity range
    if role in ["drums", "percussion"]:
        vel_range = int(25 * intensity)
    elif role == "bass":
        vel_range = int(20 * intensity)
    else:
        vel_range = int(30 * intensity)
    
    note_count = len(notes)
    
    for i, note in enumerate(notes):
        varied = deepcopy(note)
        
        if profile == "even":
            # Minimal change
            change = rng.randint(-vel_range // 3, vel_range // 3)
        elif profile == "accented":
            # Accent notes on downbeats (assuming 4/4)
            is_downbeat = (note.start_tick % TICKS_PER_BEAT) < TICKS_PER_16TH
            if is_downbeat:
                change = rng.randint(0, vel_range)
            else:
                change = rng.randint(-vel_range // 2, 0)
        elif profile == "building":
            # Crescendo over the clip
            progress = i / max(1, note_count - 1)
            change = int(-vel_range + vel_range * 2 * progress)
        else:  # fading
            # Decrescendo
            progress = i / max(1, note_count - 1)
            change = int(vel_range - vel_range * 2 * progress)
        
        varied.velocity = max(1, min(127, varied.velocity + change))
        varied.variation_reason = f"intensity_{profile}"
        result.append(varied)
    
    return result


def _vary_fill(notes: List[NoteVariation], rng: random.Random,
               intensity: float, role: str,
               bar_start: int, bar_end: int) -> List[NoteVariation]:
    """Generate fill variations at section boundaries.
    
    Fills are typically in the last 1-2 beats of a phrase.
    """
    result = []
    
    # Calculate fill region (last beat of the bar)
    fill_start = bar_end - TICKS_PER_BEAT
    
    for note in notes:
        varied = deepcopy(note)
        
        # Check if note is in fill region
        in_fill_region = fill_start <= note.start_tick < bar_end
        
        if in_fill_region and role in ["drums", "percussion"]:
            # Drums: add fill notes
            if rng.random() < 0.4 * intensity:
                # Add extra hits
                for j in range(rng.randint(1, 3)):
                    fill_note = NoteVariation(
                        pitch=note.pitch,
                        start_tick=note.start_tick + j * TICKS_PER_16TH,
                        duration_ticks=TICKS_PER_16TH,
                        velocity=max(50, int(note.velocity * (0.7 + j * 0.1))),
                        channel=note.channel,
                        was_added=True,
                        variation_reason="fill_note"
                    )
                    if fill_note.start_tick < bar_end:
                        result.append(fill_note)
        
        result.append(varied)
    
    return result


# =============================================================================
# TAKE GENERATOR CLASS
# =============================================================================

class TakeGenerator:
    """Main class for generating multiple takes of a clip.
    
    Usage:
        generator = TakeGenerator()
        take_set = generator.generate_takes(
            notes=original_notes,
            config=TakeConfig(num_takes=3, role="lead")
        )
    """
    
    # Map role to default variation strategy
    ROLE_STRATEGIES = {
        "drums": RoleVariationStrategy.DRUMS_FEEL,
        "percussion": RoleVariationStrategy.DRUMS_FEEL,
        "bass": RoleVariationStrategy.BASS_GROOVE,
        "lead": RoleVariationStrategy.LEAD_PHRASE,
        "chords": RoleVariationStrategy.CHORDS_VOICING,
        "pad": RoleVariationStrategy.PAD_TEXTURE,
        "texture": RoleVariationStrategy.PAD_TEXTURE,
    }
    
    # Variation functions for each axis
    VARIATION_FUNCS = {
        VariationAxis.RHYTHM.value: _vary_rhythm,
        VariationAxis.PITCH.value: _vary_pitch,
        VariationAxis.TIMING.value: _vary_timing,
        VariationAxis.ORNAMENT.value: _vary_ornament,
        VariationAxis.INTENSITY.value: _vary_intensity,
        VariationAxis.FILL.value: _vary_fill,
    }
    
    def __init__(self):
        """Initialize the TakeGenerator."""
        pass
    
    def generate_takes(
        self,
        notes: List[Any],  # Accept NoteEvent or dict format
        config: TakeConfig,
        clip_id: str = "default_clip",
        scale_notes: List[int] = None,
    ) -> TakeSet:
        """Generate a set of takes from original notes.
        
        Args:
            notes: Original note events (NoteEvent or dict format)
            config: TakeConfig with generation parameters
            clip_id: Identifier for the clip
            scale_notes: Optional scale notes for pitch variations
        
        Returns:
            TakeSet containing all generated takes
        """
        # Convert input notes to NoteVariation format
        original_notes = self._convert_notes(notes)
        
        # Create take set
        take_set = TakeSet(
            clip_id=clip_id,
            role=config.role,
            original_note_count=len(original_notes),
            config=config,
        )
        
        # Generate each take
        for i in range(config.num_takes):
            take = self._generate_single_take(
                original_notes=original_notes,
                take_index=i,
                config=config,
                scale_notes=scale_notes,
            )
            take_set.takes.append(take)
        
        return take_set
    
    def _convert_notes(self, notes: List[Any]) -> List[NoteVariation]:
        """Convert input notes to NoteVariation format."""
        result = []
        
        for note in notes:
            if isinstance(note, NoteVariation):
                result.append(deepcopy(note))
            elif isinstance(note, dict):
                result.append(NoteVariation(
                    pitch=note.get("pitch", 60),
                    start_tick=note.get("start_tick", 0),
                    duration_ticks=note.get("duration_ticks", 480),
                    velocity=note.get("velocity", 100),
                    channel=note.get("channel", 0),
                ))
            else:
                # Assume it's a NoteEvent-like object
                result.append(NoteVariation(
                    pitch=getattr(note, "pitch", 60),
                    start_tick=getattr(note, "start_tick", 0),
                    duration_ticks=getattr(note, "duration_ticks", 480),
                    velocity=getattr(note, "velocity", 100),
                    channel=getattr(note, "channel", 0),
                ))
        
        return result
    
    def _generate_single_take(
        self,
        original_notes: List[NoteVariation],
        take_index: int,
        config: TakeConfig,
        scale_notes: List[int] = None,
    ) -> TakeLane:
        """Generate a single take variation.
        
        Args:
            original_notes: Original notes to vary
            take_index: Index of this take (0-based)
            config: Generation configuration
            scale_notes: Optional scale notes for pitch variations
        
        Returns:
            TakeLane with varied notes
        """
        # Get deterministic seed for this take
        seed = config.get_take_seed(take_index)
        rng = random.Random(seed)
        
        # Start with copy of original notes
        varied_notes = [deepcopy(n) for n in original_notes]
        
        # Determine which variation axes to apply
        if config.variation_axis == VariationAxis.COMBINED.value:
            # Apply all axes with weights
            axes_to_apply = [
                (VariationAxis.RHYTHM.value, config.rhythm_weight),
                (VariationAxis.TIMING.value, config.timing_weight),
                (VariationAxis.INTENSITY.value, config.intensity_weight),
            ]
            # Add role-specific axes
            if config.role in ["lead", "chords"]:
                axes_to_apply.append((VariationAxis.PITCH.value, config.pitch_weight))
                axes_to_apply.append((VariationAxis.ORNAMENT.value, config.ornament_weight))
            elif config.role in ["drums", "percussion"]:
                axes_to_apply.append((VariationAxis.ORNAMENT.value, config.ornament_weight * 0.5))
        else:
            # Single axis
            axes_to_apply = [(config.variation_axis, 1.0)]
        
        # Apply each variation axis
        for axis, weight in axes_to_apply:
            if weight <= 0:
                continue
            
            effective_intensity = config.variation_intensity * weight
            
            if axis in self.VARIATION_FUNCS:
                func = self.VARIATION_FUNCS[axis]
                
                # Special handling for pitch (needs scale notes)
                if axis == VariationAxis.PITCH.value:
                    varied_notes = func(varied_notes, rng, effective_intensity, 
                                       config.role, scale_notes)
                # Special handling for ornament (needs section type)
                elif axis == VariationAxis.ORNAMENT.value:
                    varied_notes = func(varied_notes, rng, effective_intensity,
                                       config.role, config.section_type)
                # Special handling for fill (needs bar boundaries)
                elif axis == VariationAxis.FILL.value and config.is_fill_opportunity:
                    # Estimate bar boundaries from notes
                    if varied_notes:
                        bar_start = min(n.start_tick for n in varied_notes)
                        bar_end = max(n.start_tick + n.duration_ticks for n in varied_notes)
                        varied_notes = func(varied_notes, rng, effective_intensity,
                                           config.role, bar_start, bar_end)
                else:
                    varied_notes = func(varied_notes, rng, effective_intensity, config.role)
        
        # Sort notes by start time
        varied_notes.sort(key=lambda n: (n.start_tick, n.pitch))
        
        # Calculate variation statistics
        notes_added = sum(1 for n in varied_notes if n.was_added)
        notes_modified = sum(1 for n in varied_notes 
                            if n.original_pitch or n.original_start)
        
        timing_shifts = [abs(n.start_tick - n.original_start) 
                        for n in varied_notes if n.original_start]
        avg_timing_shift = sum(timing_shifts) / len(timing_shifts) if timing_shifts else 0.0
        
        # Create take lane
        take = TakeLane(
            take_id=take_index,
            seed=seed,
            variation_type=config.variation_axis,
            notes=varied_notes,
            parameters={
                "intensity": config.variation_intensity,
                "role": config.role,
                "genre": config.genre,
                "section_type": config.section_type,
            },
            notes_added=notes_added,
            notes_modified=notes_modified,
            avg_timing_shift=avg_timing_shift,
            midi_track_name=f"{config.role}_take_{take_index:02d}",
        )
        
        return take
    
    def generate_takes_for_role(
        self,
        notes: List[Any],
        role: str,
        num_takes: int = 3,
        genre: str = "trap_soul",
        section_type: str = "verse",
        base_seed: int = None,
    ) -> TakeSet:
        """Convenience method to generate takes with role-appropriate settings.
        
        Args:
            notes: Original note events
            role: Track role (drums, bass, lead, etc.)
            num_takes: Number of takes to generate
            genre: Genre for context-aware variation
            section_type: Section type for fill handling
            base_seed: Optional seed for reproducibility
        
        Returns:
            TakeSet with role-optimized takes
        """
        # Get role-appropriate strategy
        strategy = self.ROLE_STRATEGIES.get(role, RoleVariationStrategy.LEAD_PHRASE)
        
        # Configure based on strategy
        if strategy == RoleVariationStrategy.DRUMS_FEEL:
            config = TakeConfig(
                num_takes=num_takes,
                variation_axis=VariationAxis.COMBINED.value,
                variation_intensity=0.4,
                rhythm_weight=0.2,
                pitch_weight=0.0,  # Drums don't vary pitch
                timing_weight=0.5,
                ornament_weight=0.3,
                intensity_weight=0.3,
                role=role,
                genre=genre,
                section_type=section_type,
                base_seed=base_seed,
            )
        elif strategy == RoleVariationStrategy.BASS_GROOVE:
            config = TakeConfig(
                num_takes=num_takes,
                variation_axis=VariationAxis.COMBINED.value,
                variation_intensity=0.35,
                rhythm_weight=0.25,
                pitch_weight=0.15,  # Occasional octave shifts
                timing_weight=0.5,
                ornament_weight=0.1,
                intensity_weight=0.2,
                role=role,
                genre=genre,
                section_type=section_type,
                base_seed=base_seed,
            )
        elif strategy == RoleVariationStrategy.LEAD_PHRASE:
            config = TakeConfig(
                num_takes=num_takes,
                variation_axis=VariationAxis.COMBINED.value,
                variation_intensity=0.5,
                rhythm_weight=0.3,
                pitch_weight=0.25,
                timing_weight=0.35,
                ornament_weight=0.35,
                intensity_weight=0.25,
                role=role,
                genre=genre,
                section_type=section_type,
                base_seed=base_seed,
            )
        elif strategy == RoleVariationStrategy.CHORDS_VOICING:
            config = TakeConfig(
                num_takes=num_takes,
                variation_axis=VariationAxis.COMBINED.value,
                variation_intensity=0.3,
                rhythm_weight=0.2,
                pitch_weight=0.3,  # Voicing changes
                timing_weight=0.3,
                ornament_weight=0.05,
                intensity_weight=0.2,
                role=role,
                genre=genre,
                section_type=section_type,
                base_seed=base_seed,
            )
        else:  # PAD_TEXTURE
            config = TakeConfig(
                num_takes=num_takes,
                variation_axis=VariationAxis.COMBINED.value,
                variation_intensity=0.2,
                rhythm_weight=0.1,
                pitch_weight=0.1,
                timing_weight=0.3,
                ornament_weight=0.0,
                intensity_weight=0.3,
                role=role,
                genre=genre,
                section_type=section_type,
                base_seed=base_seed,
            )
        
        # Set fill opportunity for boundary sections
        config.is_fill_opportunity = section_type in ["drop", "chorus", "outro", "buildup"]
        
        return self.generate_takes(notes, config)


# =============================================================================
# MIDI OUTPUT HELPERS
# =============================================================================

def take_to_midi_track(
    take: TakeLane,
    bpm: float = 120.0,
    channel: int = 0,
) -> "MidiTrack":
    """Convert a TakeLane to a mido MidiTrack.
    
    Args:
        take: TakeLane with notes
        bpm: Tempo for the track
        channel: MIDI channel
    
    Returns:
        mido.MidiTrack ready to append to MidiFile
    """
    try:
        from mido import MidiTrack, Message, MetaMessage
    except ImportError:
        raise ImportError("mido is required for MIDI export")
    
    track = MidiTrack()
    track.append(MetaMessage('track_name', name=take.midi_track_name, time=0))
    
    # Convert notes to MIDI messages
    events = []
    for note in take.notes:
        if note.was_removed:
            continue
        events.append(("on", note.start_tick, note.pitch, note.velocity, channel))
        events.append(("off", note.start_tick + note.duration_ticks, note.pitch, 0, channel))
    
    # Sort by time
    events.sort(key=lambda e: (e[1], e[0] == "off"))
    
    # Convert to delta time and add to track
    current_tick = 0
    for event_type, tick, pitch, vel, ch in events:
        delta = tick - current_tick
        if event_type == "on":
            track.append(Message('note_on', note=pitch, velocity=vel, 
                                channel=ch, time=delta))
        else:
            track.append(Message('note_off', note=pitch, velocity=0,
                                channel=ch, time=delta))
        current_tick = tick
    
    # End of track
    track.append(MetaMessage('end_of_track', time=0))
    
    return track


# =============================================================================
# MODULE TEST
# =============================================================================

if __name__ == "__main__":
    print("Testing TakeGenerator module...")
    
    # Create test notes (simple 4-bar lead phrase)
    test_notes = []
    for bar in range(4):
        bar_offset = bar * TICKS_PER_BAR_4_4
        # Simple melody: C-E-G-E pattern
        pitches = [60, 64, 67, 64]
        for i, pitch in enumerate(pitches):
            test_notes.append({
                "pitch": pitch,
                "start_tick": bar_offset + i * TICKS_PER_BEAT,
                "duration_ticks": TICKS_PER_BEAT - 20,
                "velocity": 100,
                "channel": 0,
            })
    
    print(f"Original notes: {len(test_notes)}")
    
    # Generate takes
    generator = TakeGenerator()
    
    # Test lead takes
    lead_takes = generator.generate_takes_for_role(
        notes=test_notes,
        role="lead",
        num_takes=3,
        genre="trap_soul",
        section_type="verse",
        base_seed=42,
    )
    
    print(f"\nGenerated {len(lead_takes.takes)} lead takes:")
    for take in lead_takes.takes:
        print(f"  Take {take.take_id}: {len(take.notes)} notes, "
              f"+{take.notes_added} added, {take.notes_modified} modified, "
              f"avg timing shift: {take.avg_timing_shift:.1f} ticks")
    
    # Test drum takes
    drum_notes = [
        {"pitch": 36, "start_tick": 0, "duration_ticks": 120, "velocity": 110},  # Kick
        {"pitch": 38, "start_tick": TICKS_PER_BEAT, "duration_ticks": 120, "velocity": 100},  # Snare
        {"pitch": 42, "start_tick": TICKS_PER_16TH, "duration_ticks": 60, "velocity": 80},  # HH
    ]
    
    drum_takes = generator.generate_takes_for_role(
        notes=drum_notes,
        role="drums",
        num_takes=3,
        base_seed=42,
    )
    
    print(f"\nGenerated {len(drum_takes.takes)} drum takes:")
    for take in drum_takes.takes:
        print(f"  Take {take.take_id}: {len(take.notes)} notes, "
              f"+{take.notes_added} added, avg timing: {take.avg_timing_shift:.1f}")
    
    # Test serialization
    take_dict = lead_takes.takes[0].to_dict()
    restored = TakeLane.from_dict(take_dict)
    assert restored.take_id == lead_takes.takes[0].take_id
    assert len(restored.notes) == len(lead_takes.takes[0].notes)
    print("\n✅ Serialization round-trip successful!")
    
    # Test determinism (same seed = same output)
    take_set_1 = generator.generate_takes_for_role(test_notes, "lead", 2, base_seed=123)
    take_set_2 = generator.generate_takes_for_role(test_notes, "lead", 2, base_seed=123)
    
    # Compare notes
    assert len(take_set_1.takes[0].notes) == len(take_set_2.takes[0].notes)
    for n1, n2 in zip(take_set_1.takes[0].notes, take_set_2.takes[0].notes):
        assert n1.pitch == n2.pitch
        assert n1.start_tick == n2.start_tick
    print("✅ Determinism verified (same seed = same output)!")
    
    print("\n✅ TakeGenerator module test complete!")
