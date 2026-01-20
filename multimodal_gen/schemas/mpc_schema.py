"""
Pydantic schemas for MPC project validation.

These models validate data before MPC export to prevent
malformed .xpj/.xpm files that could crash MPC Software.

Validation includes:
- MIDI note ranges (0-127)
- Velocity values (1-127, 0 is note-off)
- Pan/volume ranges (0.0-1.0)
- Sample path format validation
- Time signature validation (denominator must be power of 2)
- Event bounds checking (events must be within sequence length)
- Program reference validation (tracks must reference existing programs)
"""
from typing import List, Optional, Any
from pydantic import BaseModel, Field, field_validator, model_validator


# MPC-specific constants
MPC_PPQ = 480  # MPC uses 480 ticks per quarter note


class PadMappingSchema(BaseModel):
    """Validated pad mapping for MPC drum program.
    
    Represents a single pad assignment in an MPC drum program,
    including sample reference, MIDI note mapping, and sound parameters.
    """
    
    bank: str = Field(..., pattern=r'^[A-H]$', description="Pad bank A-H")
    pad: int = Field(..., ge=0, le=15, description="Pad number 0-15")
    sample_path: str = Field(..., min_length=1, description="Sample file path")
    note: int = Field(..., ge=0, le=127, description="MIDI note 0-127")
    name: str = Field(..., min_length=1, max_length=64, description="Display name")
    
    volume: float = Field(default=1.0, ge=0.0, le=1.0, description="Volume 0-1")
    pan: float = Field(default=0.5, ge=0.0, le=1.0, description="Pan 0=L, 0.5=C, 1=R")
    tune: float = Field(default=0.0, ge=-24.0, le=24.0, description="Tuning semitones")
    attack: float = Field(default=0.0, ge=0.0, le=1.0, description="Attack time")
    decay: float = Field(default=1.0, ge=0.0, le=1.0, description="Decay time")
    mute_group: int = Field(default=0, ge=0, le=32, description="Mute group 0-32")
    
    @field_validator('sample_path')
    @classmethod
    def validate_sample_path(cls, v: str) -> str:
        """Validate and normalize sample path format.
        
        MPC projects use [ProjectData] prefix for relative paths.
        Auto-fixes simple filenames to proper MPC format.
        """
        # Should use [ProjectData] prefix for MPC compatibility
        if not v.startswith('[ProjectData]') and not v.startswith('./'):
            # Auto-fix relative paths
            return f"[ProjectData]/Samples/{v}" if '/' not in v else v
        return v


class DrumProgramSchema(BaseModel):
    """Validated MPC drum program.
    
    Represents a complete drum program (.xpm file) with pad assignments.
    Validates that no duplicate bank+pad combinations exist.
    """
    
    name: str = Field(..., min_length=1, max_length=64, description="Program name")
    pads: List[PadMappingSchema] = Field(default_factory=list)
    master_volume: float = Field(default=0.8, ge=0.0, le=1.0)
    
    @field_validator('pads')
    @classmethod
    def validate_unique_pads(cls, v: List[PadMappingSchema]) -> List[PadMappingSchema]:
        """Ensure no duplicate bank+pad combinations.
        
        Each pad position (e.g., A1, B3) can only have one sample assigned.
        """
        seen = set()
        for pad in v:
            key = (pad.bank, pad.pad)
            if key in seen:
                raise ValueError(f"Duplicate pad mapping: {pad.bank}{pad.pad}")
            seen.add(key)
        return v


class MidiEventSchema(BaseModel):
    """Validated MIDI event for MPC sequence.
    
    Represents a note event with position, pitch, velocity, and duration.
    """
    
    tick: int = Field(..., ge=0, description="Tick position")
    note: int = Field(..., ge=0, le=127, description="MIDI note 0-127")
    velocity: int = Field(..., ge=0, le=127, description="Velocity 0-127")
    duration: int = Field(..., ge=1, description="Duration in ticks")
    
    @field_validator('velocity')
    @classmethod
    def validate_velocity(cls, v: int) -> int:
        """Ensure velocity is valid for note-on events.
        
        Velocity 0 is technically a note-off in MIDI spec.
        For note-on events, we require positive velocity.
        """
        if v == 0:
            raise ValueError("Velocity 0 is a note-off, use positive velocity for note events")
        return v


class TrackSchema(BaseModel):
    """Validated MPC track.
    
    Represents a track within a sequence, containing MIDI events
    and referencing a drum program.
    """
    
    name: str = Field(..., min_length=1, max_length=64, description="Track name")
    program_name: str = Field(..., min_length=1, description="Referenced program")
    events: List[MidiEventSchema] = Field(default_factory=list)
    
    volume: float = Field(default=0.8, ge=0.0, le=1.0)
    pan: float = Field(default=0.5, ge=0.0, le=1.0)
    mute: bool = Field(default=False)
    solo: bool = Field(default=False)
    
    @field_validator('events')
    @classmethod
    def sort_events(cls, v: List[MidiEventSchema]) -> List[MidiEventSchema]:
        """Sort events by tick position.
        
        MPC expects events in chronological order.
        """
        return sorted(v, key=lambda e: e.tick)


class SequenceSchema(BaseModel):
    """Validated MPC sequence.
    
    Represents a sequence (pattern) with tempo, time signature,
    and multiple tracks.
    """
    
    name: str = Field(..., min_length=1, max_length=64, description="Sequence name")
    bars: int = Field(default=4, ge=1, le=999, description="Length in bars")
    bpm: float = Field(default=120.0, ge=20.0, le=300.0, description="Tempo BPM")
    time_sig_num: int = Field(default=4, ge=1, le=32, description="Time signature numerator")
    time_sig_denom: int = Field(default=4, ge=1, le=32, description="Time signature denominator")
    tracks: List[TrackSchema] = Field(default_factory=list)
    
    @field_validator('time_sig_denom')
    @classmethod
    def validate_time_sig_denom(cls, v: int) -> int:
        """Time signature denominator must be power of 2.
        
        Valid values: 1, 2, 4, 8, 16, 32 (standard music notation).
        """
        valid_denoms = {1, 2, 4, 8, 16, 32}
        if v not in valid_denoms:
            raise ValueError(f"Time signature denominator must be power of 2, got {v}")
        return v
    
    @model_validator(mode='after')
    def validate_events_within_bounds(self) -> 'SequenceSchema':
        """Ensure all events are within sequence length.
        
        Events that exceed the sequence length would be truncated
        or cause issues in MPC Software.
        """
        ticks_per_bar = MPC_PPQ * self.time_sig_num * (4 // self.time_sig_denom)
        max_tick = self.bars * ticks_per_bar
        
        for track in self.tracks:
            for event in track.events:
                if event.tick >= max_tick:
                    raise ValueError(
                        f"Event at tick {event.tick} exceeds sequence length "
                        f"({max_tick} ticks = {self.bars} bars)"
                    )
        return self


class MpcProjectSchema(BaseModel):
    """Validated complete MPC project.
    
    Represents a full MPC project (.xpj file) with sequences,
    programs, and audio file references.
    """
    
    name: str = Field(..., min_length=1, max_length=128, description="Project name")
    bpm: float = Field(default=120.0, ge=20.0, le=300.0, description="Master tempo")
    sequences: List[SequenceSchema] = Field(default_factory=list)
    programs: List[DrumProgramSchema] = Field(default_factory=list)
    audio_files: List[str] = Field(default_factory=list)
    created_date: Optional[str] = Field(default=None)
    
    @model_validator(mode='after')
    def validate_program_references(self) -> 'MpcProjectSchema':
        """Ensure all tracks reference existing programs.
        
        Tracks that reference non-existent programs would cause
        MPC Software to fail loading the project.
        """
        program_names = {p.name for p in self.programs}
        
        for seq in self.sequences:
            for track in seq.tracks:
                if track.program_name not in program_names:
                    raise ValueError(
                        f"Track '{track.name}' references unknown program '{track.program_name}'. "
                        f"Available: {program_names}"
                    )
        return self
    
    @field_validator('audio_files')
    @classmethod
    def validate_audio_paths(cls, v: List[str]) -> List[str]:
        """Validate audio file paths have supported extensions.
        
        MPC supports WAV, AIF/AIFF, and MP3 audio formats.
        """
        validated = []
        valid_extensions = {'.wav', '.aif', '.aiff', '.mp3'}
        for path in v:
            # Ensure proper extension
            path_lower = path.lower()
            if not any(path_lower.endswith(ext) for ext in valid_extensions):
                raise ValueError(
                    f"Invalid audio file extension: {path}. "
                    f"Supported: {', '.join(valid_extensions)}"
                )
            validated.append(path)
        return validated


# Conversion utilities

def from_dataclass(obj: Any, schema_class: type) -> BaseModel:
    """Convert a dataclass instance to a Pydantic schema.
    
    Args:
        obj: Dataclass instance to convert
        schema_class: Target Pydantic model class
        
    Returns:
        Validated Pydantic model instance
        
    Raises:
        pydantic.ValidationError: If validation fails
    """
    from dataclasses import asdict
    return schema_class(**asdict(obj))


def validate_project(project: Any) -> MpcProjectSchema:
    """Validate an MpcProject dataclass.
    
    Converts an MpcProject dataclass instance to a validated
    Pydantic schema, checking all fields and relationships.
    
    Args:
        project: MpcProject dataclass instance
        
    Returns:
        Validated MpcProjectSchema
        
    Raises:
        pydantic.ValidationError: If validation fails with detailed errors
        
    Example:
        >>> from multimodal_gen.mpc_exporter import MpcProject
        >>> project = MpcProject(name="My Project", bpm=120.0)
        >>> validated = validate_project(project)
    """
    from dataclasses import asdict
    data = asdict(project)
    return MpcProjectSchema(**data)


def validate_drum_program(program: Any) -> DrumProgramSchema:
    """Validate a DrumProgram dataclass.
    
    Converts a DrumProgram dataclass instance to a validated
    Pydantic schema.
    
    Args:
        program: DrumProgram dataclass instance
        
    Returns:
        Validated DrumProgramSchema
        
    Raises:
        pydantic.ValidationError: If validation fails
    """
    from dataclasses import asdict
    data = asdict(program)
    return DrumProgramSchema(**data)
