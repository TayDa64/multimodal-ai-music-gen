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


class TakeMode(Enum):
    """
    Take export modes - how takes relate to original tracks.
    
    Industry-standard overdubbing behavior:
    - REPLACE: Takes replace original (DAW comping workflow)
    - LAYER: Takes add to original (double-tracking effect)
    - COMP: AI selects best sections from all takes
    """
    REPLACE = "replace"      # Takes replace original (default, correct overdub)
    LAYER = "layer"          # Takes layer on top (intentional doubling)
    COMP = "comp"            # AI creates comp track from best sections


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
    
    Industry-Standard Overdubbing:
    - Takes are REPLACEMENT alternatives, not layers
    - Only one take plays at a time (user selects which)
    - Comping allows mixing sections from different takes
    """
    take_id: int
    seed: int
    variation_type: str  # VariationAxis value
    notes: List[NoteVariation] = field(default_factory=list)
    
    # Generation parameters (for reproducibility)
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Variation summary (complete accounting)
    notes_added: int = 0
    notes_removed: int = 0       # Notes intentionally omitted from original
    notes_modified: int = 0
    notes_kept: int = 0          # Notes unchanged from original
    avg_timing_shift: float = 0.0
    avg_velocity_change: float = 0.0
    
    # MIDI output reference
    midi_track_name: str = ""
    
    # Take relationship metadata
    original_track_name: str = ""   # Name of the track this is a take of
    is_active_take: bool = False     # Whether this is the currently selected take
    
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
            "notes_kept": self.notes_kept,
            "avg_timing_shift": self.avg_timing_shift,
            "avg_velocity_change": self.avg_velocity_change,
            "midi_track_name": self.midi_track_name,
            "original_track_name": self.original_track_name,
            "is_active_take": self.is_active_take,
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
    # Class variable for request uniqueness across instances
    _request_counter: int = 0
    
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
        """Generate deterministic seed for a specific take.
        
        Uses timestamp-based seed when base_seed is None to ensure
        different requests produce different takes.
        """
        if self.base_seed is None:
            # Use timestamp-based seed for true uniqueness between requests
            import time
            TakeConfig._request_counter += 1
            self.base_seed = int(time.time() * 1000000 + TakeConfig._request_counter) % (2**31)
        
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
    
    UPDATED: Higher variation values for AUDIBLY PERCEPTIBLE differences.
    Human timing perception: ~20-50ms minimum for noticeable change.
    At 120 BPM, 480 ticks/beat = 1 tick ≈ 1ms, so we need shifts of 20-60 ticks.
    """
    result = []
    
    # Role-specific parameters - INCREASED for audible variation
    if role in ["drums", "percussion"]:
        # Drums: shifts and ghost notes for groove variation
        shift_range = int(TICKS_PER_16TH * 0.4 * intensity)  # Up to 48 ticks at full intensity
        add_ghost_prob = 0.25 * intensity  # Up to 25% ghost note probability
        remove_prob = 0.12 * intensity     # Up to 12% note removal
    elif role == "bass":
        # Bass: anticipation/push feel
        shift_range = int(TICKS_PER_16TH * 0.5 * intensity)  # Up to 60 ticks
        add_ghost_prob = 0.08 * intensity  # Occasional approach notes
        remove_prob = 0.15 * intensity     # More note variation
    elif role == "lead":
        # Lead: more freedom for phrasing
        shift_range = int(TICKS_PER_8TH * 0.4 * intensity)   # Up to 96 ticks
        add_ghost_prob = 0.20 * intensity  # Grace notes, pickup notes
        remove_prob = 0.18 * intensity     # Phrase simplification
    else:
        # Chords/pads: moderate rhythm change
        shift_range = int(TICKS_PER_16TH * 0.35 * intensity)  # Up to 42 ticks
        add_ghost_prob = 0.05 * intensity
        remove_prob = 0.10 * intensity
    
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
            # Only mark as modified if there's actual change
            if shift != 0:
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
    
    UPDATED: Increased probabilities for AUDIBLY DIFFERENT variations.
    """
    result = []
    
    if role in ["drums", "percussion"]:
        # Drums: only cymbal variations
        return [deepcopy(n) for n in notes]
    
    # Default scale if not provided (chromatic within octave)
    if scale_notes is None:
        scale_notes = list(range(0, 128))
    
    # Role-specific parameters - INCREASED for noticeable pitch variation
    if role == "bass":
        octave_shift_prob = 0.25 * intensity   # Up to 25% octave shift
        neighbor_prob = 0.18 * intensity       # Up to 18% neighbor tone
        max_shift = 12  # One octave
    elif role == "lead":
        octave_shift_prob = 0.15 * intensity   # Up to 15% octave jump
        neighbor_prob = 0.30 * intensity       # Up to 30% neighbor tone
        max_shift = 3  # Up to 3 semitones
    else:  # chords, pad
        octave_shift_prob = 0.12 * intensity   # Up to 12% octave shift
        neighbor_prob = 0.20 * intensity       # Up to 20% voicing change
        max_shift = 4  # Up to 4 semitones for voicing
    
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
    
    UPDATED: Increased variance for AUDIBLY PERCEPTIBLE timing differences.
    Human timing perception threshold: ~20-50ms minimum.
    At 120 BPM: 1 tick ≈ 1ms, so we need variance of 20-60 ticks.
    """
    result = []
    
    # Determine feel type for this take
    feel_types = ["laid_back", "pushing", "loose", "tight"]
    feel = rng.choice(feel_types)
    
    # Role-specific timing variance - INCREASED for audible differences
    if role in ["drums", "percussion"]:
        max_variance = int(TICKS_PER_16TH * 0.35 * intensity)  # Up to 42 ticks (42ms)
    elif role == "bass":
        max_variance = int(TICKS_PER_16TH * 0.45 * intensity)  # Up to 54 ticks (54ms)
    else:
        max_variance = int(TICKS_PER_16TH * 0.50 * intensity)  # Up to 60 ticks (60ms)
    
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
        
        # Only mark as modified if there's an actual timing change
        if shift != 0:
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
    
    UPDATED: Higher ornament probabilities for AUDIBLY DIFFERENT takes.
    """
    result = []
    
    # Role-specific ornament probability - INCREASED for noticeable variation
    if role == "lead":
        grace_prob = 0.28 * intensity   # Up to 28% grace notes
        trill_prob = 0.10 * intensity   # Up to 10% trills
    elif role in ["drums", "percussion"]:
        grace_prob = 0.22 * intensity   # Up to 22% flams
        trill_prob = 0.08 * intensity   # Up to 8% rolls
    elif role == "bass":
        grace_prob = 0.15 * intensity   # Up to 15% slides/hammer-ons
        trill_prob = 0.0
    else:
        grace_prob = 0.08 * intensity   # Low for chords/pads
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
    
    UPDATED: Higher velocity ranges for AUDIBLY DIFFERENT dynamics.
    Typical velocity changes need to be 15-40 for noticeable difference.
    """
    result = []
    
    # Determine intensity profile for this take
    profiles = ["even", "accented", "building", "fading"]
    profile = rng.choice(profiles)
    
    # Role-specific velocity range - INCREASED for audible dynamics
    if role in ["drums", "percussion"]:
        vel_range = int(45 * intensity)  # Up to 45 velocity units
    elif role == "bass":
        vel_range = int(35 * intensity)  # Up to 35 velocity units
    else:
        vel_range = int(50 * intensity)  # Up to 50 velocity units
    
    note_count = len(notes)
    
    for i, note in enumerate(notes):
        varied = deepcopy(note)
        
        if profile == "even":
            # Some variation even in "even" mode
            change = rng.randint(-vel_range // 2, vel_range // 2)
        elif profile == "accented":
            # Accent notes on downbeats (assuming 4/4)
            is_downbeat = (note.start_tick % TICKS_PER_BEAT) < TICKS_PER_16TH
            if is_downbeat:
                change = rng.randint(vel_range // 4, vel_range)
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
        
        # Sort notes by start time (exclude removed notes from final output)
        active_notes = [n for n in varied_notes if not n.was_removed]
        active_notes.sort(key=lambda n: (n.start_tick, n.pitch))
        
        # Calculate comprehensive variation statistics
        # Notes added: new notes not in original
        notes_added = sum(1 for n in active_notes if n.was_added)
        
        # Notes removed: original notes intentionally omitted (was_removed=True in varied_notes)
        notes_removed = sum(1 for n in varied_notes if n.was_removed)
        
        # Notes modified: notes with changed timing or pitch (excluding added notes)
        # Count as modified if pitch changed OR timing shifted by more than minimal amount
        MIN_TIMING_SHIFT_FOR_MODIFIED = 10  # ticks - ignore very tiny shifts
        notes_modified = 0
        timing_shifts = []
        
        for n in active_notes:
            if n.was_added:
                continue
            
            is_modified = False
            
            # Check pitch modification
            if n.original_pitch is not None and n.original_pitch != n.pitch:
                is_modified = True
            
            # Check timing modification (only if significant)
            if n.original_start is not None:
                shift = abs(n.start_tick - n.original_start)
                timing_shifts.append(shift)
                if shift > MIN_TIMING_SHIFT_FOR_MODIFIED:
                    is_modified = True
            
            if is_modified:
                notes_modified += 1
        
        # Notes kept: original notes with minimal/no changes
        notes_kept = len(active_notes) - notes_added - notes_modified
        
        # Average timing shift (for notes that were shifted)
        avg_timing_shift = sum(timing_shifts) / len(timing_shifts) if timing_shifts else 0.0
        
        # Create take lane with complete accounting
        take = TakeLane(
            take_id=take_index,
            seed=seed,
            variation_type=config.variation_axis,
            notes=active_notes,  # Only include non-removed notes
            parameters={
                "intensity": config.variation_intensity,
                "role": config.role,
                "genre": config.genre,
                "section_type": config.section_type,
                "original_note_count": len(original_notes),
            },
            notes_added=notes_added,
            notes_removed=notes_removed,
            notes_modified=notes_modified,
            notes_kept=notes_kept,
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
        # CRITICAL: Variation must be AUDIBLY PERCEPTIBLE
        # Human timing perception threshold: ~20-50ms = ~20-50 ticks at 120 BPM
        # Previous values were WAY too low (3-4 ticks = 3-4ms = imperceptible)
        # 
        # New approach: Higher base intensity, higher weights, to produce:
        # - Timing shifts of 30-60 ticks (30-60ms) = clearly audible
        # - 5-15% note addition/removal probability = noticeable structural changes
        # - Velocity changes of 15-30 = audible dynamics
        if strategy == RoleVariationStrategy.DRUMS_FEEL:
            config = TakeConfig(
                num_takes=num_takes,
                variation_axis=VariationAxis.COMBINED.value,
                variation_intensity=0.85,  # HIGH: drums need groove feel variation
                rhythm_weight=0.6,         # HIGH: add/remove ghost notes, shuffle hits
                pitch_weight=0.0,          # Drums don't vary pitch
                timing_weight=0.8,         # HIGH: timing feel is key differentiator
                ornament_weight=0.5,       # MEDIUM: flams, drags, rolls
                intensity_weight=0.7,      # HIGH: velocity grooves matter
                role=role,
                genre=genre,
                section_type=section_type,
                base_seed=base_seed,
            )
        elif strategy == RoleVariationStrategy.BASS_GROOVE:
            config = TakeConfig(
                num_takes=num_takes,
                variation_axis=VariationAxis.COMBINED.value,
                variation_intensity=0.75,  # HIGH: bass groove drives the feel
                rhythm_weight=0.5,         # MEDIUM: syncopation changes
                pitch_weight=0.4,          # MEDIUM: octave jumps, approach notes
                timing_weight=0.7,         # HIGH: push/pull feel
                ornament_weight=0.3,       # LOW: slides, hammer-ons
                intensity_weight=0.5,      # MEDIUM: dynamics
                role=role,
                genre=genre,
                section_type=section_type,
                base_seed=base_seed,
            )
        elif strategy == RoleVariationStrategy.LEAD_PHRASE:
            config = TakeConfig(
                num_takes=num_takes,
                variation_axis=VariationAxis.COMBINED.value,
                variation_intensity=0.80,  # HIGH: lead should have clear variations
                rhythm_weight=0.6,         # HIGH: phrasing changes
                pitch_weight=0.5,          # MEDIUM: melodic variations
                timing_weight=0.6,         # HIGH: expressive timing
                ornament_weight=0.7,       # HIGH: grace notes, turns, fills
                intensity_weight=0.5,      # MEDIUM: dynamics
                role=role,
                genre=genre,
                section_type=section_type,
                base_seed=base_seed,
            )
        elif strategy == RoleVariationStrategy.CHORDS_VOICING:
            config = TakeConfig(
                num_takes=num_takes,
                variation_axis=VariationAxis.COMBINED.value,
                variation_intensity=0.65,  # MEDIUM: chords less extreme
                rhythm_weight=0.4,         # MEDIUM: strum patterns
                pitch_weight=0.6,          # HIGH: voicing changes are key
                timing_weight=0.5,         # MEDIUM: strum timing
                ornament_weight=0.2,       # LOW: arpeggiation
                intensity_weight=0.4,      # MEDIUM: dynamics
                role=role,
                genre=genre,
                section_type=section_type,
                base_seed=base_seed,
            )
        else:  # PAD_TEXTURE
            config = TakeConfig(
                num_takes=num_takes,
                variation_axis=VariationAxis.COMBINED.value,
                variation_intensity=0.50,  # MEDIUM: pads are subtle
                rhythm_weight=0.2,         # LOW: minimal rhythm change
                pitch_weight=0.3,          # MEDIUM: voicing changes
                timing_weight=0.4,         # MEDIUM: swells, timing
                ornament_weight=0.1,       # LOW: arpeggiation rare
                intensity_weight=0.6,      # HIGH: dynamics are key for pads
                role=role,
                genre=genre,
                section_type=section_type,
                base_seed=base_seed,
            )
        
        # Set fill opportunity for boundary sections
        config.is_fill_opportunity = section_type in ["drop", "chorus", "outro", "buildup"]
        
        return self.generate_takes(notes, config)


# =============================================================================
# TAKE VALIDATOR - Correctness Verification for Generated Takes
# =============================================================================

@dataclass
class TakeValidationResult:
    """Results from validating a take against musical correctness criteria."""
    is_valid: bool
    score: float  # 0.0 to 1.0 overall quality
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # Detailed metrics
    note_density_ok: bool = True
    rhythm_consistency_ok: bool = True
    timing_reasonable_ok: bool = True
    pitch_in_range_ok: bool = True
    velocity_distribution_ok: bool = True


class TakeValidator:
    """
    Validates generated takes for musical correctness.
    
    Industry-standard overdubbing quality checks:
    - Note density shouldn't deviate too far from original
    - Rhythm patterns should maintain genre consistency
    - Timing variations should be within musical bounds
    - Pitch changes should stay in key/scale
    - Velocity distribution should be musically appropriate
    
    Usage:
        validator = TakeValidator()
        result = validator.validate_take(take, original_notes, genre="trap")
        if not result.is_valid:
            print(f"Issues: {result.issues}")
    """
    
    # Maximum acceptable deviation ratios
    MAX_NOTE_DENSITY_CHANGE = 0.4  # 40% more or fewer notes than original
    MAX_TIMING_DEVIATION_16TH = 0.75  # Max 75% of a 16th note timing shift
    MIN_NOTES_RETAINED = 0.3  # At least 30% of original notes should remain
    
    def __init__(self):
        pass
    
    def validate_take(
        self,
        take: TakeLane,
        original_notes: List[NoteVariation],
        genre: str = "default",
        scale_root: int = 0,
        scale_type: str = "minor",
    ) -> TakeValidationResult:
        """
        Validate a take against musical correctness criteria.
        
        Args:
            take: The generated TakeLane to validate
            original_notes: Original notes the take was derived from
            genre: Genre for context-specific rules
            scale_root: Root note of the key (0=C, 1=C#, etc.)
            scale_type: major, minor, pentatonic, etc.
        
        Returns:
            TakeValidationResult with pass/fail and detailed feedback
        """
        result = TakeValidationResult(is_valid=True, score=1.0)
        
        original_count = len(original_notes)
        take_count = len(take.notes)
        
        # 1. Note Density Check
        if original_count > 0:
            density_ratio = take_count / original_count
            if density_ratio < (1 - self.MAX_NOTE_DENSITY_CHANGE):
                result.issues.append(
                    f"Note density too low: {take_count} notes vs {original_count} original "
                    f"(ratio {density_ratio:.2f}, min {1 - self.MAX_NOTE_DENSITY_CHANGE:.2f})"
                )
                result.note_density_ok = False
                result.score -= 0.2
            elif density_ratio > (1 + self.MAX_NOTE_DENSITY_CHANGE):
                result.issues.append(
                    f"Note density too high: {take_count} notes vs {original_count} original "
                    f"(ratio {density_ratio:.2f}, max {1 + self.MAX_NOTE_DENSITY_CHANGE:.2f})"
                )
                result.note_density_ok = False
                result.score -= 0.2
        
        # 2. Notes Retained Check
        if original_count > 0:
            retained_ratio = take.notes_kept / original_count if original_count > 0 else 0
            if retained_ratio < self.MIN_NOTES_RETAINED:
                result.warnings.append(
                    f"Low note retention: {take.notes_kept}/{original_count} kept "
                    f"({retained_ratio:.1%}, recommended >{self.MIN_NOTES_RETAINED:.0%})"
                )
                result.score -= 0.1
        
        # 3. Timing Deviation Check
        max_timing_ticks = int(TICKS_PER_16TH * self.MAX_TIMING_DEVIATION_16TH)
        if take.avg_timing_shift > max_timing_ticks:
            result.warnings.append(
                f"Large timing shifts: avg {take.avg_timing_shift:.1f} ticks "
                f"(max recommended {max_timing_ticks})"
            )
            result.timing_reasonable_ok = False
            result.score -= 0.1
        
        # 4. Pitch Range Check
        if take.notes:
            pitches = [n.pitch for n in take.notes]
            min_pitch, max_pitch = min(pitches), max(pitches)
            
            # Check for unreasonable range (more than 4 octaves)
            if max_pitch - min_pitch > 48:
                result.warnings.append(
                    f"Wide pitch range: {max_pitch - min_pitch} semitones "
                    f"(MIDI {min_pitch} to {max_pitch})"
                )
                result.pitch_in_range_ok = False
                result.score -= 0.1
            
            # Check for out-of-range notes
            out_of_range = [p for p in pitches if p < 21 or p > 108]
            if out_of_range:
                result.issues.append(
                    f"{len(out_of_range)} notes outside piano range (21-108)"
                )
                result.pitch_in_range_ok = False
                result.score -= 0.15
        
        # 5. Velocity Distribution Check
        if take.notes:
            velocities = [n.velocity for n in take.notes]
            avg_vel = sum(velocities) / len(velocities)
            
            # Check for too quiet or too loud
            if avg_vel < 40:
                result.warnings.append(f"Very quiet take: avg velocity {avg_vel:.0f}")
                result.velocity_distribution_ok = False
            elif avg_vel > 115:
                result.warnings.append(f"Very loud take: avg velocity {avg_vel:.0f}")
                result.velocity_distribution_ok = False
            
            # Check for no dynamics
            vel_range = max(velocities) - min(velocities)
            if vel_range < 10 and len(velocities) > 4:
                result.warnings.append(
                    f"No dynamics: velocity range only {vel_range} "
                    f"({min(velocities)}-{max(velocities)})"
                )
                result.score -= 0.05
        
        # 6. Genre-Specific Checks
        genre_issues = self._validate_genre_rules(take, genre)
        result.warnings.extend(genre_issues)
        
        # Finalize
        result.score = max(0.0, min(1.0, result.score))
        result.is_valid = len(result.issues) == 0 and result.score >= 0.5
        
        return result
    
    def _validate_genre_rules(self, take: TakeLane, genre: str) -> List[str]:
        """Check genre-specific musical rules."""
        warnings = []
        
        role = take.parameters.get("role", "lead")
        
        if "trap" in genre:
            # Trap: hi-hats should have lots of notes, kicks should be sparse
            if role == "drums":
                if take.notes_added > take.notes_removed * 2:
                    warnings.append("Trap drums: consider more note removal for space")
        
        elif "lofi" in genre or "chill" in genre:
            # Lo-fi: should have swing and ghost notes
            if take.notes_added == 0 and role in ["drums", "bass"]:
                warnings.append("Lo-fi style: consider adding ghost notes for groove")
        
        elif "boom_bap" in genre:
            # Boom bap: needs swing, ghost notes on drums
            if role == "drums" and take.avg_timing_shift < 5:
                warnings.append("Boom bap drums: may need more swing/timing variation")
        
        return warnings
    
    def validate_take_set(
        self,
        take_set: TakeSet,
        original_notes: List[NoteVariation],
        genre: str = "default",
    ) -> Dict[int, TakeValidationResult]:
        """Validate all takes in a TakeSet."""
        results = {}
        for take in take_set.takes:
            results[take.take_id] = self.validate_take(take, original_notes, genre)
        return results
    
    def get_best_take(
        self,
        take_set: TakeSet,
        original_notes: List[NoteVariation],
        genre: str = "default",
    ) -> Optional[TakeLane]:
        """Return the highest-scoring valid take."""
        validation_results = self.validate_take_set(take_set, original_notes, genre)
        
        best_take = None
        best_score = -1.0
        
        for take in take_set.takes:
            result = validation_results.get(take.take_id)
            if result and result.is_valid and result.score > best_score:
                best_score = result.score
                best_take = take
        
        return best_take


# =============================================================================
# MIDI OUTPUT HELPERS
# =============================================================================

# =============================================================================
# COMP GENERATOR - Industry-Standard Comping Workflow
# =============================================================================

@dataclass
class CompSection:
    """A section of a comp track with source take information."""
    start_tick: int
    end_tick: int
    source_take_id: int
    source_score: float
    notes: List[NoteVariation] = field(default_factory=list)
    
    # Why this section was chosen
    selection_reason: str = ""
    
    def duration_ticks(self) -> int:
        return self.end_tick - self.start_tick


@dataclass 
class CompResult:
    """Result of comp generation with full metadata."""
    comp_notes: List[NoteVariation]
    sections: List[CompSection]
    source_takes: List[TakeLane]
    
    # Overall metrics
    total_score: float = 0.0
    num_sections: int = 0
    takes_used: Dict[int, int] = field(default_factory=dict)  # take_id -> section count
    
    # MIDI output
    midi_track_name: str = ""
    original_track_name: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "comp_notes_count": len(self.comp_notes),
            "sections": [
                {
                    "start_tick": s.start_tick,
                    "end_tick": s.end_tick,
                    "source_take_id": s.source_take_id,
                    "source_score": s.source_score,
                    "notes_count": len(s.notes),
                    "selection_reason": s.selection_reason,
                }
                for s in self.sections
            ],
            "total_score": self.total_score,
            "num_sections": self.num_sections,
            "takes_used": self.takes_used,
            "midi_track_name": self.midi_track_name,
            "original_track_name": self.original_track_name,
        }


class CompGenerator:
    """
    Generate composite tracks from multiple takes.
    
    Industry-standard comping workflow:
    1. Divide track into sections (typically 1-4 bars)
    2. Score each section in each take independently  
    3. Select best section from any take for each position
    4. Combine selected sections with smooth transitions
    5. Validate final comp for coherence
    
    This creates the optimal "performance" by combining the best
    moments from multiple takes - exactly like a professional
    recording session.
    
    Usage:
        comp_gen = CompGenerator()
        result = comp_gen.generate_comp(
            take_set=take_set,
            original_notes=original_notes,
            bars_per_section=2
        )
    """
    
    def __init__(self, validator: Optional[TakeValidator] = None):
        """Initialize CompGenerator with optional validator."""
        self.validator = validator or TakeValidator()
    
    def generate_comp(
        self,
        take_set: TakeSet,
        original_notes: List[NoteVariation],
        bars_per_section: int = 2,
        genre: str = "default",
        crossfade_ticks: int = 0,
    ) -> CompResult:
        """
        Generate optimal comp track from multiple takes.
        
        Args:
            take_set: TakeSet containing all takes to comp from
            original_notes: Original notes for reference
            bars_per_section: How many bars per comping section
            genre: Genre for context-aware scoring
            crossfade_ticks: Ticks of overlap for smooth transitions
        
        Returns:
            CompResult with comp notes and metadata
        """
        if not take_set.takes:
            return CompResult(
                comp_notes=[],
                sections=[],
                source_takes=[],
                total_score=0.0,
                num_sections=0,
            )
        
        # Calculate section boundaries
        all_notes = []
        for take in take_set.takes:
            all_notes.extend(take.notes)
        
        if not all_notes:
            return CompResult(
                comp_notes=[],
                sections=[],
                source_takes=take_set.takes,
                total_score=0.0,
                num_sections=0,
            )
        
        # Find total duration
        min_tick = min(n.start_tick for n in all_notes)
        max_tick = max(n.start_tick + n.duration_ticks for n in all_notes)
        
        # Calculate section length in ticks
        section_ticks = bars_per_section * TICKS_PER_BAR_4_4
        
        # Generate section boundaries
        sections = []
        current_start = min_tick
        
        while current_start < max_tick:
            section_end = min(current_start + section_ticks, max_tick)
            
            # Score each take for this section
            best_take_id = 0
            best_score = -1.0
            best_notes = []
            best_reason = "default"
            
            for take in take_set.takes:
                # Get notes in this section
                section_notes = [
                    n for n in take.notes
                    if n.start_tick >= current_start and n.start_tick < section_end
                ]
                
                # Score this section
                score = self._score_section(
                    section_notes, 
                    original_notes, 
                    current_start, 
                    section_end,
                    take.parameters.get("role", "lead"),
                    genre
                )
                
                if score > best_score:
                    best_score = score
                    best_take_id = take.take_id
                    best_notes = section_notes
                    best_reason = f"highest_score_{score:.2f}"
            
            # Create comp section
            comp_section = CompSection(
                start_tick=current_start,
                end_tick=section_end,
                source_take_id=best_take_id,
                source_score=best_score,
                notes=best_notes,
                selection_reason=best_reason,
            )
            sections.append(comp_section)
            
            current_start = section_end
        
        # Combine all selected sections
        comp_notes = []
        takes_used = {}
        
        for section in sections:
            # Track which takes contributed
            takes_used[section.source_take_id] = takes_used.get(section.source_take_id, 0) + 1
            
            # Add notes from this section (deep copy to avoid mutation)
            for note in section.notes:
                comp_note = deepcopy(note)
                comp_note.variation_reason = f"comp_from_take_{section.source_take_id}"
                comp_notes.append(comp_note)
        
        # Apply crossfade if specified (smooth velocity transitions at boundaries)
        if crossfade_ticks > 0:
            comp_notes = self._apply_crossfades(comp_notes, sections, crossfade_ticks)
        
        # Calculate total score (weighted average)
        if sections:
            total_score = sum(s.source_score for s in sections) / len(sections)
        else:
            total_score = 0.0
        
        # Sort notes by time
        comp_notes.sort(key=lambda n: (n.start_tick, n.pitch))
        
        return CompResult(
            comp_notes=comp_notes,
            sections=sections,
            source_takes=take_set.takes,
            total_score=total_score,
            num_sections=len(sections),
            takes_used=takes_used,
            midi_track_name=f"{take_set.role}_comp",
            original_track_name=take_set.role,
        )
    
    def _score_section(
        self,
        section_notes: List[NoteVariation],
        original_notes: List[NoteVariation],
        section_start: int,
        section_end: int,
        role: str,
        genre: str,
    ) -> float:
        """
        Score a section for musical quality.
        
        Scoring criteria:
        - Note density relative to original (not too sparse/dense)
        - Velocity consistency (avoid harsh jumps)
        - Timing coherence (smooth rhythm)
        - Role-appropriate characteristics
        """
        score = 1.0
        
        if not section_notes:
            return 0.2  # Empty section gets low score but not zero
        
        # Get original notes in this section
        orig_section = [
            n for n in original_notes
            if n.start_tick >= section_start and n.start_tick < section_end
        ]
        
        # 1. Note density comparison
        if orig_section:
            density_ratio = len(section_notes) / len(orig_section)
            # Ideal: 0.8 to 1.2 of original
            if density_ratio < 0.5:
                score -= 0.2
            elif density_ratio > 2.0:
                score -= 0.15
            elif 0.8 <= density_ratio <= 1.2:
                score += 0.1  # Bonus for similar density
        
        # 2. Velocity consistency
        velocities = [n.velocity for n in section_notes]
        if len(velocities) > 1:
            vel_changes = [abs(velocities[i] - velocities[i-1]) for i in range(1, len(velocities))]
            avg_vel_change = sum(vel_changes) / len(vel_changes)
            # Large velocity jumps are usually bad
            if avg_vel_change > 50:
                score -= 0.15
            elif avg_vel_change < 20:
                score += 0.05  # Smooth dynamics bonus
        
        # 3. Timing spread (avoid clumping)
        if len(section_notes) > 1:
            times = sorted(n.start_tick for n in section_notes)
            gaps = [times[i] - times[i-1] for i in range(1, len(times))]
            if gaps:
                min_gap = min(gaps)
                max_gap = max(gaps)
                # Very uneven spacing
                if max_gap > min_gap * 10 and min_gap < TICKS_PER_16TH:
                    score -= 0.1
        
        # 4. Role-specific bonuses
        if role == "drums":
            # Drums: reward ghost notes
            ghost_count = sum(1 for n in section_notes if n.velocity < 70)
            if ghost_count > 0:
                score += 0.05
        
        elif role == "bass":
            # Bass: reward octave relationships
            pitches = set(n.pitch for n in section_notes)
            octave_pairs = sum(1 for p in pitches if (p + 12) in pitches or (p - 12) in pitches)
            if octave_pairs > 0:
                score += 0.05
        
        elif role == "lead":
            # Lead: reward melodic movement
            if len(section_notes) > 2:
                pitches = [n.pitch for n in sorted(section_notes, key=lambda x: x.start_tick)]
                intervals = [abs(pitches[i] - pitches[i-1]) for i in range(1, len(pitches))]
                avg_interval = sum(intervals) / len(intervals)
                # Good melodic motion: 2-7 semitones average
                if 2 <= avg_interval <= 7:
                    score += 0.1
        
        # 5. Genre-specific adjustments
        if "trap" in genre:
            # Trap: reward hi-hat density
            if role == "drums":
                hi_hat_pitches = {42, 44, 46}  # Common hi-hat MIDI notes
                hh_count = sum(1 for n in section_notes if n.pitch in hi_hat_pitches)
                if hh_count > len(section_notes) * 0.3:
                    score += 0.05
        
        elif "lofi" in genre or "boom_bap" in genre:
            # Lo-fi/boom bap: reward timing variation (swing)
            added_notes = sum(1 for n in section_notes if n.was_added)
            if added_notes > 0:
                score += 0.05  # Ghost notes add character
        
        return max(0.0, min(1.0, score))
    
    def _apply_crossfades(
        self,
        comp_notes: List[NoteVariation],
        sections: List[CompSection],
        crossfade_ticks: int,
    ) -> List[NoteVariation]:
        """Apply smooth velocity crossfades at section boundaries."""
        if len(sections) < 2:
            return comp_notes
        
        # Create set of boundary tick positions
        boundaries = set()
        for section in sections:
            boundaries.add(section.start_tick)
            boundaries.add(section.end_tick)
        
        # Adjust velocities near boundaries
        for note in comp_notes:
            for boundary in boundaries:
                distance = abs(note.start_tick - boundary)
                if distance < crossfade_ticks:
                    # Fade factor: 1.0 at full distance, lower near boundary
                    fade = distance / crossfade_ticks
                    # Subtle velocity reduction at boundaries
                    note.velocity = max(40, int(note.velocity * (0.85 + 0.15 * fade)))
        
        return comp_notes
    
    def generate_comp_from_takes(
        self,
        takes: List[TakeLane],
        role: str,
        bars_per_section: int = 2,
        genre: str = "default",
    ) -> CompResult:
        """
        Convenience method to generate comp directly from list of takes.
        
        Args:
            takes: List of TakeLane objects
            role: Track role for scoring context
            bars_per_section: Section size
            genre: Genre context
        
        Returns:
            CompResult with optimal comp
        """
        # Get original notes from first take's parameters
        original_notes = []
        if takes and takes[0].parameters.get("original_note_count", 0) > 0:
            # Use first take's notes as reference (they're derived from original)
            original_notes = takes[0].notes
        
        # Create TakeSet
        take_set = TakeSet(
            clip_id="comp_source",
            role=role,
            original_note_count=len(original_notes),
            takes=takes,
        )
        
        return self.generate_comp(
            take_set=take_set,
            original_notes=original_notes,
            bars_per_section=bars_per_section,
            genre=genre,
        )


def comp_to_midi_track(
    comp_result: CompResult,
    bpm: float = 120.0,
    channel: int = None,
) -> "MidiTrack":
    """Convert a CompResult to a mido MidiTrack.
    
    Args:
        comp_result: CompResult with comp notes
        bpm: Tempo for the track
        channel: MIDI channel override. If None, uses note.channel from each note
                 (preserves drum channel 9 correctly)
    
    Returns:
        mido.MidiTrack ready to append to MidiFile
    """
    try:
        from mido import MidiTrack, Message, MetaMessage
    except ImportError:
        raise ImportError("mido is required for MIDI export")
    
    track = MidiTrack()
    track_name = comp_result.midi_track_name or "Comp"
    track.append(MetaMessage('track_name', name=track_name, time=0))
    
    # Convert notes to MIDI messages
    # CRITICAL: Use note.channel to preserve drum channel (9) vs melodic channels
    events = []
    for note in comp_result.comp_notes:
        if note.was_removed:
            continue
        # Use per-note channel if no override, preserves drum track on channel 9
        note_channel = channel if channel is not None else note.channel
        events.append(("on", note.start_tick, note.pitch, note.velocity, note_channel))
        events.append(("off", note.start_tick + note.duration_ticks, note.pitch, 0, note_channel))
    
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
# MIDI OUTPUT HELPERS
# =============================================================================

def take_to_midi_track(
    take: TakeLane,
    bpm: float = 120.0,
    channel: int = None,
) -> "MidiTrack":
    """Convert a TakeLane to a mido MidiTrack.
    
    Args:
        take: TakeLane with notes
        bpm: Tempo for the track
        channel: MIDI channel override. If None, uses note.channel from each note
                 (preserves drum channel 9 correctly)
    
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
    # CRITICAL: Use note.channel to preserve drum channel (9) vs melodic channels
    events = []
    for note in take.notes:
        if note.was_removed:
            continue
        # Use per-note channel if no override, preserves drum track on channel 9
        note_channel = channel if channel is not None else note.channel
        events.append(("on", note.start_tick, note.pitch, note.velocity, note_channel))
        events.append(("off", note.start_tick + note.duration_ticks, note.pitch, 0, note_channel))
    
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
