"""
Session Graph - Structured Session Representation

This module implements Milestone A of likuTasks.md:
"Represent generation as a structured session: sections, tracks, roles,
constraints, clip/take lanes, and render directives."

The SessionGraph becomes the central contract between Python and JUCE,
enabling:
- Section-based arrangement editing
- Multi-take generation with comping
- Role-based instrument assignment
- Constraint enforcement via genre rules
- Complete session reconstruction from manifest

Key Classes:
    - SessionGraph: Root container for the entire session
    - Section: Song section with timing, energy, and constraints
    - Track: Instrument/role track with clips and settings
    - Role: Semantic function (DRUMS, BASS, LEAD, etc.)
    - Clip: Audio/MIDI region on a track
    - TakeLane: Parallel variation lane for a clip
    - ConstraintSet: Genre rules applied to generation
    - RenderDirective: Export/mix settings per track

Usage:
    from multimodal_gen.session_graph import SessionGraphBuilder, SessionGraph
    
    builder = SessionGraphBuilder()
    graph = builder.build_from_prompt(parsed_prompt, reference_analysis)
    graph.save_manifest("output/project/session_manifest.json")

Serialization:
    All classes implement to_dict() and from_dict() for JSON serialization.
    Schema version is tracked for backward compatibility.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any, Set
from enum import Enum
import json
import random
import hashlib
from datetime import datetime
from pathlib import Path

# Schema version for manifest compatibility
SCHEMA_VERSION = "1.0.0"


# =============================================================================
# ENUMERATIONS
# =============================================================================

class Role(Enum):
    """Semantic roles for tracks in the session.
    
    Roles define what function a track serves, enabling:
    - Intelligent instrument selection
    - Role-specific humanization
    - Mix presets per role
    - Genre rule enforcement
    """
    # Rhythm Section
    DRUMS = "drums"
    PERCUSSION = "percussion"
    BASS = "bass"
    
    # Harmonic
    CHORDS = "chords"
    PAD = "pad"
    
    # Melodic
    LEAD = "lead"
    COUNTER_MELODY = "counter_melody"
    HOOK = "hook"
    
    # Texture
    TEXTURE = "texture"
    FX = "fx"
    
    # Ethnic/Specialized
    ETHIOPIAN_STRING = "ethiopian_string"
    ETHIOPIAN_WIND = "ethiopian_wind"
    ETHIOPIAN_DRUM = "ethiopian_drum"


class ClipType(Enum):
    """Type of content in a clip."""
    MIDI = "midi"
    AUDIO = "audio"
    REFERENCE = "reference"  # Points to external file


class MatchType(Enum):
    """How an instrument was resolved."""
    EXACT = "exact"
    MAPPED = "mapped"
    SEMANTIC = "semantic"
    SPECTRAL = "spectral"
    DEFAULT = "default"


class ConstraintSeverity(Enum):
    """How strictly a constraint should be enforced."""
    MANDATORY = "mandatory"   # Must be present
    FORBIDDEN = "forbidden"   # Must not be present
    RECOMMENDED = "recommended"  # Suggested but optional
    DISCOURAGED = "discouraged"  # Avoid if possible


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class InstrumentSelection:
    """Records an instrument selection decision with rationale.
    
    Provides transparency into AI instrument choices:
    - What was selected
    - Why it was selected
    - What alternatives were considered
    """
    name: str
    path: str
    match_type: str  # MatchType value
    confidence: float  # 0.0 - 1.0
    candidates: List[Dict[str, Any]] = field(default_factory=list)
    selection_reason: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "path": self.path,
            "match_type": self.match_type,
            "confidence": self.confidence,
            "candidates": self.candidates,
            "selection_reason": self.selection_reason,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "InstrumentSelection":
        return cls(**data)


@dataclass
class TakeMetadata:
    """Metadata for a single take.
    
    Captures the generation context so takes can be:
    - Reproduced deterministically
    - Compared meaningfully
    - Understood in context
    """
    take_id: int
    seed: int
    variation_type: str  # "rhythm", "pitch", "timing", "ornament"
    parameters: Dict[str, Any] = field(default_factory=dict)
    generated_at: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "take_id": self.take_id,
            "seed": self.seed,
            "variation_type": self.variation_type,
            "parameters": self.parameters,
            "generated_at": self.generated_at or datetime.now().isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "TakeMetadata":
        return cls(**data)


@dataclass
class TakeLaneRef:
    """Reference to a TakeLane in the manifest.
    
    Stores metadata about a generated take without the full note data.
    Full note data is in separate MIDI files or the TakeLane objects.
    
    This allows the manifest to stay lightweight while tracking:
    - Which takes exist for each clip
    - Generation parameters for reproducibility
    - MIDI file references for each take
    """
    take_id: int
    seed: int
    variation_type: str
    midi_track_name: str = ""
    midi_file: Optional[str] = None  # Path to MIDI file for this take
    notes_count: int = 0
    notes_added: int = 0
    notes_modified: int = 0
    avg_timing_shift: float = 0.0
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "take_id": self.take_id,
            "seed": self.seed,
            "variation_type": self.variation_type,
            "midi_track_name": self.midi_track_name,
            "midi_file": self.midi_file,
            "notes_count": self.notes_count,
            "notes_added": self.notes_added,
            "notes_modified": self.notes_modified,
            "avg_timing_shift": self.avg_timing_shift,
            "parameters": self.parameters,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "TakeLaneRef":
        return cls(**data)


@dataclass
class Clip:
    """A region of content on a track.
    
    Clips are the atomic units of arrangement:
    - MIDI clips contain note events
    - Audio clips reference rendered audio
    - Can have multiple takes for comping
    
    Takes System (Milestone D):
    - Each clip can have multiple TakeLane variations
    - active_take_index points to the "comped" take
    - take_lanes stores references to generated takes
    - JUCE can display stacked lanes and allow switching
    """
    clip_id: str
    start_tick: int
    end_tick: int
    clip_type: str  # ClipType value
    
    # Content reference
    midi_file: Optional[str] = None
    audio_file: Optional[str] = None
    
    # Take management (legacy - kept for compatibility)
    active_take: int = 0
    takes: List[TakeMetadata] = field(default_factory=list)
    
    # Take lanes (Milestone D - full take system)
    take_lanes: List[TakeLaneRef] = field(default_factory=list)
    active_take_index: int = 0
    num_takes_generated: int = 0
    take_generation_seed: Optional[int] = None
    
    # Clip properties
    velocity_scale: float = 1.0
    time_offset_ticks: int = 0
    is_muted: bool = False
    is_looped: bool = False
    loop_length_ticks: int = 0
    
    @property
    def duration_ticks(self) -> int:
        return self.end_tick - self.start_tick
    
    @property
    def has_takes(self) -> bool:
        """Check if this clip has multiple takes."""
        return len(self.take_lanes) > 1
    
    def add_take(self, seed: int, variation_type: str = "default",
                 parameters: Dict[str, Any] = None) -> TakeMetadata:
        """Add a new take to this clip (legacy method)."""
        take = TakeMetadata(
            take_id=len(self.takes),
            seed=seed,
            variation_type=variation_type,
            parameters=parameters or {},
        )
        self.takes.append(take)
        return take
    
    def add_take_lane(
        self,
        take_id: int,
        seed: int,
        variation_type: str,
        midi_track_name: str = "",
        notes_count: int = 0,
        notes_added: int = 0,
        notes_modified: int = 0,
        avg_timing_shift: float = 0.0,
        parameters: Dict[str, Any] = None,
    ) -> TakeLaneRef:
        """Add a TakeLane reference to this clip.
        
        Called after TakeGenerator produces takes to register them
        in the session manifest.
        """
        ref = TakeLaneRef(
            take_id=take_id,
            seed=seed,
            variation_type=variation_type,
            midi_track_name=midi_track_name,
            notes_count=notes_count,
            notes_added=notes_added,
            notes_modified=notes_modified,
            avg_timing_shift=avg_timing_shift,
            parameters=parameters or {},
        )
        self.take_lanes.append(ref)
        self.num_takes_generated = len(self.take_lanes)
        return ref
    
    def get_active_take_lane(self) -> Optional[TakeLaneRef]:
        """Get the currently active/comped take lane."""
        if 0 <= self.active_take_index < len(self.take_lanes):
            return self.take_lanes[self.active_take_index]
        return None
    
    def set_active_take(self, take_index: int) -> bool:
        """Set the active take by index. Returns True if successful."""
        if 0 <= take_index < len(self.take_lanes):
            self.active_take_index = take_index
            self.active_take = take_index  # Keep legacy field in sync
            return True
        return False
    
    def to_dict(self) -> Dict:
        return {
            "clip_id": self.clip_id,
            "start_tick": self.start_tick,
            "end_tick": self.end_tick,
            "clip_type": self.clip_type,
            "midi_file": self.midi_file,
            "audio_file": self.audio_file,
            "active_take": self.active_take,
            "takes": [t.to_dict() for t in self.takes],
            "take_lanes": [tl.to_dict() for tl in self.take_lanes],
            "active_take_index": self.active_take_index,
            "num_takes_generated": self.num_takes_generated,
            "take_generation_seed": self.take_generation_seed,
            "velocity_scale": self.velocity_scale,
            "time_offset_ticks": self.time_offset_ticks,
            "is_muted": self.is_muted,
            "is_looped": self.is_looped,
            "loop_length_ticks": self.loop_length_ticks,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Clip":
        takes_data = data.pop("takes", [])
        take_lanes_data = data.pop("take_lanes", [])
        clip = cls(**{k: v for k, v in data.items() 
                      if k not in ("takes", "take_lanes")})
        clip.takes = [TakeMetadata.from_dict(t) for t in takes_data]
        clip.take_lanes = [TakeLaneRef.from_dict(tl) for tl in take_lanes_data]
        return clip


@dataclass
class Constraint:
    """A single rule constraint from genre or user preferences.
    
    Constraints drive validation and auto-repair:
    - Mandatory elements are added if missing
    - Forbidden elements are removed or substituted
    - Recommendations influence selection scores
    """
    element: str
    severity: str  # ConstraintSeverity value
    scope: str = "global"  # "global", "section", "track"
    applies_to: Optional[str] = None  # Track/section name if scoped
    substitution: Optional[str] = None  # What to use instead (for forbidden)
    reason: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "element": self.element,
            "severity": self.severity,
            "scope": self.scope,
            "applies_to": self.applies_to,
            "substitution": self.substitution,
            "reason": self.reason,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Constraint":
        return cls(**data)


@dataclass
class ConstraintSet:
    """Collection of constraints applied to generation.
    
    Sources:
    - Genre rules (from genres.json/genre_rules)
    - User preferences (from prompt)
    - Reference analysis (stylistic constraints)
    """
    constraints: List[Constraint] = field(default_factory=list)
    source: str = "default"  # "genre", "user", "reference"
    
    def get_mandatory(self) -> List[Constraint]:
        """Get all mandatory constraints."""
        return [c for c in self.constraints 
                if c.severity == ConstraintSeverity.MANDATORY.value]
    
    def get_forbidden(self) -> List[Constraint]:
        """Get all forbidden constraints."""
        return [c for c in self.constraints 
                if c.severity == ConstraintSeverity.FORBIDDEN.value]
    
    def is_allowed(self, element: str) -> bool:
        """Check if an element is allowed by constraints."""
        for c in self.constraints:
            if c.element == element and c.severity == ConstraintSeverity.FORBIDDEN.value:
                return False
        return True
    
    def to_dict(self) -> Dict:
        return {
            "constraints": [c.to_dict() for c in self.constraints],
            "source": self.source,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ConstraintSet":
        constraints_data = data.pop("constraints", [])
        cs = cls(**data)
        cs.constraints = [Constraint.from_dict(c) for c in constraints_data]
        return cs


@dataclass
class TrackMixSettings:
    """Mix settings for a track (for render directives)."""
    volume_db: float = 0.0
    pan: float = 0.0  # -1.0 to 1.0
    mute: bool = False
    solo: bool = False
    
    # FX sends
    reverb_send: float = 0.0
    delay_send: float = 0.0
    
    # Processing chain intent
    fx_chain: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "TrackMixSettings":
        return cls(**data)


@dataclass
class Track:
    """A track in the session containing clips.
    
    Tracks are organized by role and contain:
    - One or more clips (arrangement regions)
    - Instrument selection with rationale
    - Mix settings (volume, pan, FX)
    - Role-specific constraints
    """
    track_id: str
    name: str
    role: str  # Role value
    channel: int
    
    # Clips on this track
    clips: List[Clip] = field(default_factory=list)
    
    # Instrument assignment
    instrument: Optional[InstrumentSelection] = None
    
    # Mix settings
    mix: TrackMixSettings = field(default_factory=TrackMixSettings)
    
    # Track constraints (role-specific rules)
    constraints: Optional[ConstraintSet] = None
    
    # Player profile for humanization
    player_profile: str = "natural"  # "tight", "natural", "loose", "live"
    
    # Metadata
    is_enabled: bool = True
    color: str = "#808080"
    
    def add_clip(self, start_tick: int, end_tick: int, clip_type: str = "midi",
                 seed: int = None) -> Clip:
        """Add a new clip to this track."""
        clip_id = f"{self.track_id}_clip_{len(self.clips)}"
        clip = Clip(
            clip_id=clip_id,
            start_tick=start_tick,
            end_tick=end_tick,
            clip_type=clip_type,
        )
        if seed is not None:
            clip.add_take(seed)
        self.clips.append(clip)
        return clip
    
    def to_dict(self) -> Dict:
        return {
            "track_id": self.track_id,
            "name": self.name,
            "role": self.role,
            "channel": self.channel,
            "clips": [c.to_dict() for c in self.clips],
            "instrument": self.instrument.to_dict() if self.instrument else None,
            "mix": self.mix.to_dict(),
            "constraints": self.constraints.to_dict() if self.constraints else None,
            "player_profile": self.player_profile,
            "is_enabled": self.is_enabled,
            "color": self.color,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Track":
        clips_data = data.pop("clips", [])
        instrument_data = data.pop("instrument", None)
        mix_data = data.pop("mix", {})
        constraints_data = data.pop("constraints", None)
        
        track = cls(**{k: v for k, v in data.items() 
                       if k not in ("clips", "instrument", "mix", "constraints")})
        track.clips = [Clip.from_dict(c) for c in clips_data]
        track.instrument = InstrumentSelection.from_dict(instrument_data) if instrument_data else None
        track.mix = TrackMixSettings.from_dict(mix_data)
        track.constraints = ConstraintSet.from_dict(constraints_data) if constraints_data else None
        return track


@dataclass
class SectionMarker:
    """A section marker in the arrangement.
    
    Sections define arrangement structure:
    - Energy level for dynamics
    - Enabled elements per section
    - Filter/FX automation targets
    """
    name: str
    start_tick: int
    end_tick: int
    section_type: str  # From arranger.SectionType
    
    # Energy/dynamics
    energy_level: float = 0.5  # 0.0 - 1.0
    drum_density: float = 0.5
    instrument_density: float = 0.5
    
    # Enabled elements
    enable_kick: bool = True
    enable_snare: bool = True
    enable_hihat: bool = True
    enable_bass: bool = True
    enable_chords: bool = True
    enable_melody: bool = False
    enable_textures: bool = False
    
    # Mix automation
    filter_cutoff: float = 1.0  # 0.0 - 1.0
    master_volume: float = 1.0
    
    # Variation control
    variation_seed: int = 0
    pattern_variation: int = 0
    
    @property
    def duration_ticks(self) -> int:
        return self.end_tick - self.start_tick
    
    @property
    def bars(self) -> int:
        """Approximate bars (assumes 4/4 at 480 PPQ)."""
        return self.duration_ticks // 1920
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "SectionMarker":
        return cls(**data)


@dataclass
class RenderDirective:
    """Instructions for rendering/exporting the session.
    
    Controls how the final mix is rendered:
    - Sample rate, bit depth
    - Stem export settings
    - Headroom/mastering targets
    """
    # Audio format
    sample_rate: int = 44100
    bit_depth: int = 24
    channels: int = 2  # Stereo
    
    # Output settings
    normalize: bool = False
    target_lufs: float = -14.0  # Streaming standard
    headroom_db: float = -1.0   # Peak headroom
    
    # Tail handling
    tail_seconds: float = 2.0
    fade_out_seconds: float = 0.5
    
    # Stem export
    export_stems: bool = True
    stem_groups: List[str] = field(default_factory=lambda: [
        "drums", "bass", "melodic", "fx"
    ])
    
    # MPC export
    export_mpc: bool = False
    mpc_version: str = "3.0"
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "RenderDirective":
        return cls(**data)


@dataclass
class GrooveTemplate:
    """Groove/timing template extracted or defined.
    
    Captures the rhythmic "feel" that can be:
    - Extracted from reference
    - Applied to generated patterns
    - Saved as reusable asset
    """
    name: str
    bars: int = 1
    subdivisions: int = 16  # Resolution
    
    # Per-subdivision offsets (in ticks)
    timing_offsets: List[int] = field(default_factory=list)
    velocity_offsets: List[int] = field(default_factory=list)
    
    # Swing/shuffle
    swing_amount: float = 0.0
    swing_ratio: float = 0.5  # 0.5 = straight, 0.67 = triplet feel
    
    # Source info
    extracted_from: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "GrooveTemplate":
        return cls(**data)


@dataclass
class GenerationHistory:
    """Record of generation decisions for explainability."""
    timestamp: str
    decision_type: str  # "instrument", "pattern", "rule_repair", etc.
    description: str
    before: Optional[str] = None
    after: Optional[str] = None
    reason: str = ""
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "GenerationHistory":
        return cls(**data)


# =============================================================================
# SESSION GRAPH (MAIN CLASS)
# =============================================================================

@dataclass
class SessionGraph:
    """Root container for the complete session.
    
    The SessionGraph is the central "contract" between Python and JUCE:
    - Python generates/modifies the graph
    - JUCE reads/displays/plays the graph
    - Saved as session_manifest.json for persistence
    
    All generation decisions, instrument choices, and structure are
    recorded here for full transparency and reproducibility.
    """
    # Schema versioning
    schema_version: str = SCHEMA_VERSION
    
    # Session identity
    session_id: str = ""
    created_at: str = ""
    modified_at: str = ""
    
    # Original prompt and parsed data
    raw_prompt: str = ""
    negative_prompt: str = ""
    parsed_parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Timing
    bpm: float = 120.0
    time_signature: Tuple[int, int] = (4, 4)
    key: str = "C"
    scale: str = "minor"
    total_ticks: int = 0
    total_bars: int = 0
    
    # Genre and constraints
    genre: str = "trap_soul"
    global_constraints: Optional[ConstraintSet] = None
    
    # Arrangement
    sections: List[SectionMarker] = field(default_factory=list)
    
    # Tracks
    tracks: List[Track] = field(default_factory=list)
    
    # Groove
    groove_template: Optional[GrooveTemplate] = None
    
    # Output files
    midi_path: Optional[str] = None
    audio_path: Optional[str] = None
    stems_path: Optional[str] = None
    
    # Render settings
    render_directive: RenderDirective = field(default_factory=RenderDirective)
    
    # Generation history (for explainability)
    history: List[GenerationHistory] = field(default_factory=list)
    
    def __post_init__(self):
        """Initialize session ID and timestamps if not set."""
        if not self.session_id:
            self.session_id = self._generate_session_id()
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        self.modified_at = datetime.now().isoformat()
    
    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        content = f"{self.raw_prompt}{datetime.now().isoformat()}{random.random()}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def duration_seconds(self) -> float:
        """Calculate total duration in seconds."""
        if self.bpm <= 0:
            return 0.0
        ticks_per_beat = 480  # Standard
        beats = self.total_ticks / ticks_per_beat
        return beats * 60.0 / self.bpm
    
    def add_track(self, name: str, role: str, channel: int = 0) -> Track:
        """Add a new track to the session."""
        track_id = f"track_{len(self.tracks)}_{role}"
        track = Track(
            track_id=track_id,
            name=name,
            role=role,
            channel=channel,
        )
        self.tracks.append(track)
        self.modified_at = datetime.now().isoformat()
        return track
    
    def add_section(self, name: str, section_type: str, 
                    start_tick: int, end_tick: int, **kwargs) -> SectionMarker:
        """Add a section marker."""
        section = SectionMarker(
            name=name,
            section_type=section_type,
            start_tick=start_tick,
            end_tick=end_tick,
            **kwargs
        )
        self.sections.append(section)
        self.modified_at = datetime.now().isoformat()
        return section
    
    def get_track_by_role(self, role: str) -> Optional[Track]:
        """Find track by role."""
        for track in self.tracks:
            if track.role == role:
                return track
        return None
    
    def get_section_at_tick(self, tick: int) -> Optional[SectionMarker]:
        """Get section containing a tick position."""
        for section in self.sections:
            if section.start_tick <= tick < section.end_tick:
                return section
        return None
    
    def log_decision(self, decision_type: str, description: str,
                     before: str = None, after: str = None, reason: str = "") -> None:
        """Log a generation decision for explainability."""
        entry = GenerationHistory(
            timestamp=datetime.now().isoformat(),
            decision_type=decision_type,
            description=description,
            before=before,
            after=after,
            reason=reason,
        )
        self.history.append(entry)
        self.modified_at = datetime.now().isoformat()
    
    def validate(self) -> List[str]:
        """Validate session graph for completeness and consistency.
        
        Returns list of validation warnings/errors.
        """
        issues = []
        
        # Check timing
        if self.bpm <= 0:
            issues.append("BPM must be positive")
        if self.total_ticks <= 0:
            issues.append("Session has no duration")
        
        # Check sections
        if not self.sections:
            issues.append("No sections defined")
        else:
            # Check for gaps/overlaps
            sorted_sections = sorted(self.sections, key=lambda s: s.start_tick)
            for i in range(len(sorted_sections) - 1):
                if sorted_sections[i].end_tick != sorted_sections[i + 1].start_tick:
                    issues.append(f"Gap or overlap between sections {i} and {i + 1}")
        
        # Check tracks
        if not self.tracks:
            issues.append("No tracks defined")
        else:
            # Check for essential roles
            roles = {t.role for t in self.tracks}
            if Role.DRUMS.value not in roles and Role.PERCUSSION.value not in roles:
                issues.append("No drum/percussion track")
        
        return issues
    
    def to_dict(self) -> Dict:
        """Serialize to dictionary for JSON export."""
        return {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "raw_prompt": self.raw_prompt,
            "negative_prompt": self.negative_prompt,
            "parsed_parameters": self.parsed_parameters,
            "bpm": self.bpm,
            "time_signature": list(self.time_signature),
            "key": self.key,
            "scale": self.scale,
            "total_ticks": self.total_ticks,
            "total_bars": self.total_bars,
            "genre": self.genre,
            "global_constraints": self.global_constraints.to_dict() if self.global_constraints else None,
            "sections": [s.to_dict() for s in self.sections],
            "tracks": [t.to_dict() for t in self.tracks],
            "groove_template": self.groove_template.to_dict() if self.groove_template else None,
            "midi_path": self.midi_path,
            "audio_path": self.audio_path,
            "stems_path": self.stems_path,
            "render_directive": self.render_directive.to_dict(),
            "history": [h.to_dict() for h in self.history],
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "SessionGraph":
        """Deserialize from dictionary."""
        # Extract nested structures
        global_constraints_data = data.pop("global_constraints", None)
        sections_data = data.pop("sections", [])
        tracks_data = data.pop("tracks", [])
        groove_data = data.pop("groove_template", None)
        render_data = data.pop("render_directive", {})
        history_data = data.pop("history", [])
        time_sig = data.pop("time_signature", [4, 4])
        
        # Create base object
        graph = cls(**{k: v for k, v in data.items() 
                       if k not in ("global_constraints", "sections", "tracks", 
                                    "groove_template", "render_directive", 
                                    "history", "time_signature")})
        
        # Restore nested structures
        graph.time_signature = tuple(time_sig)
        graph.global_constraints = ConstraintSet.from_dict(global_constraints_data) if global_constraints_data else None
        graph.sections = [SectionMarker.from_dict(s) for s in sections_data]
        graph.tracks = [Track.from_dict(t) for t in tracks_data]
        graph.groove_template = GrooveTemplate.from_dict(groove_data) if groove_data else None
        graph.render_directive = RenderDirective.from_dict(render_data)
        graph.history = [GenerationHistory.from_dict(h) for h in history_data]
        
        return graph
    
    def save_manifest(self, path: str) -> None:
        """Save session manifest to JSON file."""
        self.modified_at = datetime.now().isoformat()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load_manifest(cls, path: str) -> "SessionGraph":
        """Load session manifest from JSON file."""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)


# =============================================================================
# SESSION GRAPH BUILDER
# =============================================================================

class SessionGraphBuilder:
    """Builds a SessionGraph from parsed prompts and analysis.
    
    This is the main entry point for creating sessions:
    1. Takes ParsedPrompt, optional ReferenceAnalysis
    2. Builds arrangement structure
    3. Creates tracks with role assignments
    4. Applies genre constraints
    5. Returns complete SessionGraph
    """
    
    def __init__(self):
        self.default_track_colors = {
            Role.DRUMS.value: "#FF6B6B",      # Red
            Role.PERCUSSION.value: "#FFA94D", # Orange
            Role.BASS.value: "#4DABF7",       # Blue
            Role.CHORDS.value: "#69DB7C",     # Green
            Role.PAD.value: "#9775FA",        # Purple
            Role.LEAD.value: "#F783AC",       # Pink
            Role.TEXTURE.value: "#20C997",    # Teal
            Role.FX.value: "#FCC419",         # Yellow
        }
    
    def build_from_prompt(self, parsed, reference_analysis=None) -> SessionGraph:
        """Build a SessionGraph from a ParsedPrompt.
        
        Args:
            parsed: ParsedPrompt from prompt_parser
            reference_analysis: Optional ReferenceAnalysis from reference_analyzer
        
        Returns:
            Fully constructed SessionGraph
        """
        # Create base graph
        graph = SessionGraph(
            raw_prompt=parsed.raw_prompt,
            negative_prompt=getattr(parsed, 'negative_prompt', ''),
            bpm=parsed.bpm,
            time_signature=parsed.time_signature,
            key=parsed.key,
            scale=parsed.scale_type.value if hasattr(parsed.scale_type, 'value') else str(parsed.scale_type),
            genre=parsed.genre,
        )
        
        # Store parsed parameters
        graph.parsed_parameters = {
            "mood": getattr(parsed, 'mood', 'neutral'),
            "energy": getattr(parsed, 'energy', 'medium'),
            "use_sidechain": getattr(parsed, 'use_sidechain', False),
            "use_swing": getattr(parsed, 'use_swing', False),
            "swing_amount": getattr(parsed, 'swing_amount', 0.0),
            "textures": getattr(parsed, 'textures', []),
        }
        
        # Apply reference analysis if provided
        if reference_analysis:
            graph = self._apply_reference(graph, reference_analysis)
        
        # Build constraints from genre
        graph.global_constraints = self._build_constraints(parsed)
        
        # Create default tracks based on instruments
        graph = self._create_tracks(graph, parsed)
        
        # Log initial setup
        graph.log_decision(
            decision_type="initialization",
            description=f"Created session for {parsed.genre} at {parsed.bpm} BPM in {parsed.key}"
        )
        
        return graph
    
    def _apply_reference(self, graph: SessionGraph, ref) -> SessionGraph:
        """Apply reference analysis to the graph."""
        # Override BPM/key if higher confidence
        if hasattr(ref, 'bpm_confidence') and ref.bpm_confidence > 0.7:
            graph.log_decision(
                decision_type="reference_override",
                description="Applied reference BPM",
                before=str(graph.bpm),
                after=str(ref.bpm),
                reason=f"Reference confidence: {ref.bpm_confidence:.2f}"
            )
            graph.bpm = ref.bpm
        
        if hasattr(ref, 'key_confidence') and ref.key_confidence > 0.7:
            graph.log_decision(
                decision_type="reference_override",
                description="Applied reference key",
                before=graph.key,
                after=ref.key,
                reason=f"Reference confidence: {ref.key_confidence:.2f}"
            )
            graph.key = ref.key
        
        # Extract groove template if available
        if hasattr(ref, 'groove') and ref.groove:
            graph.groove_template = GrooveTemplate(
                name="reference_groove",
                swing_amount=ref.groove.swing_amount,
                extracted_from=getattr(ref, 'source_url', 'reference'),
            )
        
        return graph
    
    def _build_constraints(self, parsed) -> ConstraintSet:
        """Build constraint set from genre and prompt."""
        constraints = []
        
        # Add forbidden elements from negative prompt
        excluded_drums = getattr(parsed, 'excluded_drums', [])
        excluded_instruments = getattr(parsed, 'excluded_instruments', [])
        
        for elem in excluded_drums:
            constraints.append(Constraint(
                element=elem,
                severity=ConstraintSeverity.FORBIDDEN.value,
                scope="track",
                applies_to=Role.DRUMS.value,
                reason="User excluded via negative prompt"
            ))
        
        for elem in excluded_instruments:
            constraints.append(Constraint(
                element=elem,
                severity=ConstraintSeverity.FORBIDDEN.value,
                scope="global",
                reason="User excluded via negative prompt"
            ))
        
        # Add genre-specific constraints
        # (This would integrate with genre_rules.py when implemented)
        genre_constraints = self._get_genre_constraints(parsed.genre)
        constraints.extend(genre_constraints)
        
        return ConstraintSet(constraints=constraints, source="combined")
    
    def _get_genre_constraints(self, genre: str) -> List[Constraint]:
        """Get constraints specific to a genre.
        
        This is a placeholder that will integrate with genre_rules.py
        when Milestone B is implemented.
        """
        # Basic genre-specific constraints
        genre_rules = {
            "boom_bap": [
                Constraint("hihat_roll", ConstraintSeverity.FORBIDDEN.value,
                          substitution="hihat", reason="Boom bap uses clean hi-hats"),
            ],
            "g_funk": [
                Constraint("hihat_roll", ConstraintSeverity.DISCOURAGED.value,
                          reason="G-Funk prefers groovy, clean hi-hats"),
            ],
            "trap_soul": [
                Constraint("brass_stab", ConstraintSeverity.RECOMMENDED.value,
                          reason="Brass stabs add trap soul flavor"),
            ],
        }
        return genre_rules.get(genre, [])
    
    def _create_tracks(self, graph: SessionGraph, parsed) -> SessionGraph:
        """Create tracks based on parsed instruments and genre."""
        channel = 0
        
        # Always create drums track (channel 9 for GM compatibility)
        drums_track = graph.add_track("Drums", Role.DRUMS.value, channel=9)
        drums_track.color = self.default_track_colors.get(Role.DRUMS.value, "#808080")
        drums_track.player_profile = getattr(parsed, 'humanization_profile', 'natural')
        channel += 1
        
        # Create bass track
        bass_track = graph.add_track("Bass", Role.BASS.value, channel=channel)
        bass_track.color = self.default_track_colors.get(Role.BASS.value, "#808080")
        channel += 1
        
        # Create tracks for other instruments
        instrument_roles = {
            "piano": Role.CHORDS.value,
            "rhodes": Role.CHORDS.value,
            "organ": Role.CHORDS.value,
            "keys": Role.CHORDS.value,
            "pad": Role.PAD.value,
            "strings": Role.PAD.value,
            "synth": Role.LEAD.value,
            "lead": Role.LEAD.value,
            "brass": Role.LEAD.value,
            "guitar": Role.CHORDS.value,
            # Ethiopian instruments
            "krar": Role.ETHIOPIAN_STRING.value,
            "masenqo": Role.ETHIOPIAN_STRING.value,
            "begena": Role.ETHIOPIAN_STRING.value,
            "washint": Role.ETHIOPIAN_WIND.value,
            "kebero": Role.ETHIOPIAN_DRUM.value,
        }
        
        instruments = getattr(parsed, 'instruments', [])
        created_roles = set()
        
        for inst in instruments:
            inst_lower = inst.lower()
            role = instrument_roles.get(inst_lower, Role.LEAD.value)
            
            # Avoid duplicate role tracks (combine similar instruments)
            if role in created_roles:
                continue
            
            track = graph.add_track(inst.title(), role, channel=channel)
            track.color = self.default_track_colors.get(role, "#808080")
            created_roles.add(role)
            channel += 1
        
        return graph
    
    def build_from_arrangement(self, graph: SessionGraph, arrangement) -> SessionGraph:
        """Add sections and clips from an Arrangement object.
        
        Args:
            graph: SessionGraph to populate
            arrangement: Arrangement from arranger.py
        
        Returns:
            SessionGraph with sections and clips populated
        """
        graph.total_ticks = arrangement.total_ticks
        graph.total_bars = arrangement.total_bars
        
        # Add section markers
        for arr_section in arrangement.sections:
            section = graph.add_section(
                name=arr_section.section_type.value,
                section_type=arr_section.section_type.value,
                start_tick=arr_section.start_tick,
                end_tick=arr_section.end_tick,
                energy_level=arr_section.config.energy_level,
                drum_density=arr_section.config.drum_density,
                instrument_density=arr_section.config.instrument_density,
                enable_kick=arr_section.config.enable_kick,
                enable_snare=arr_section.config.enable_snare,
                enable_hihat=arr_section.config.enable_hihat,
                enable_bass=arr_section.config.enable_bass,
                enable_chords=arr_section.config.enable_chords,
                enable_melody=arr_section.config.enable_melody,
                enable_textures=arr_section.config.enable_textures,
                filter_cutoff=arr_section.config.filter_cutoff,
                variation_seed=arr_section.variation_seed,
                pattern_variation=arr_section.pattern_variation,
            )
        
        # Add clips to tracks based on sections
        for track in graph.tracks:
            for section in graph.sections:
                # Create a clip for each section on each track
                clip = track.add_clip(
                    start_tick=section.start_tick,
                    end_tick=section.end_tick,
                    clip_type=ClipType.MIDI.value,
                    seed=section.variation_seed + hash(track.track_id) % 10000,
                )
                clip.add_take(
                    seed=section.variation_seed,
                    variation_type="default",
                    parameters={
                        "section_type": section.section_type,
                        "energy": section.energy_level,
                    }
                )
        
        graph.log_decision(
            decision_type="arrangement",
            description=f"Built arrangement with {len(graph.sections)} sections, {graph.total_bars} bars"
        )
        
        return graph


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_session_graph(parsed_prompt, arrangement=None, 
                        reference_analysis=None) -> SessionGraph:
    """Convenience function to create a SessionGraph.
    
    Args:
        parsed_prompt: ParsedPrompt from prompt_parser
        arrangement: Optional Arrangement from arranger
        reference_analysis: Optional ReferenceAnalysis
    
    Returns:
        Complete SessionGraph ready for MIDI generation
    """
    builder = SessionGraphBuilder()
    graph = builder.build_from_prompt(parsed_prompt, reference_analysis)
    
    if arrangement:
        graph = builder.build_from_arrangement(graph, arrangement)
    
    return graph


def load_session(path: str) -> SessionGraph:
    """Load a session from manifest file."""
    return SessionGraph.load_manifest(path)


def save_session(graph: SessionGraph, path: str) -> None:
    """Save a session to manifest file."""
    graph.save_manifest(path)


# =============================================================================
# MODULE TEST
# =============================================================================

if __name__ == "__main__":
    # Quick test
    print("Testing SessionGraph module...")
    
    # Create mock ParsedPrompt
    from dataclasses import dataclass as dc
    
    @dc
    class MockParsed:
        raw_prompt: str = "trap soul beat at 87 BPM in C minor"
        negative_prompt: str = ""
        bpm: float = 87.0
        time_signature: tuple = (4, 4)
        key: str = "C"
        scale_type: str = "minor"
        genre: str = "trap_soul"
        instruments: list = None
        mood: str = "dark"
        energy: str = "medium"
        use_sidechain: bool = True
        use_swing: bool = False
        swing_amount: float = 0.0
        textures: list = None
        excluded_drums: list = None
        excluded_instruments: list = None
        humanization_profile: str = "natural"
        
        def __post_init__(self):
            self.instruments = self.instruments or ["808", "piano", "strings"]
            self.textures = self.textures or []
            self.excluded_drums = self.excluded_drums or []
            self.excluded_instruments = self.excluded_instruments or []
    
    parsed = MockParsed()
    
    # Build session graph
    builder = SessionGraphBuilder()
    graph = builder.build_from_prompt(parsed)
    
    # Add test section manually
    graph.add_section("intro", "intro", 0, 1920 * 4, energy_level=0.4)
    graph.add_section("verse", "verse", 1920 * 4, 1920 * 12, energy_level=0.6)
    graph.total_ticks = 1920 * 12
    graph.total_bars = 12
    
    # Validate
    issues = graph.validate()
    print(f"Validation issues: {issues}")
    
    # Serialize
    data = graph.to_dict()
    print(f"\nSession Graph created:")
    print(f"  - ID: {graph.session_id}")
    print(f"  - Genre: {graph.genre}")
    print(f"  - BPM: {graph.bpm}")
    print(f"  - Tracks: {len(graph.tracks)}")
    print(f"  - Sections: {len(graph.sections)}")
    print(f"  - Duration: {graph.duration_seconds():.1f}s")
    
    # Test round-trip serialization
    restored = SessionGraph.from_dict(data)
    assert restored.session_id == graph.session_id
    assert len(restored.tracks) == len(graph.tracks)
    print("\n✅ Round-trip serialization successful!")
    
    # Save manifest
    test_path = "./output/test_session_manifest.json"
    graph.save_manifest(test_path)
    print(f"\n✅ Manifest saved to {test_path}")
