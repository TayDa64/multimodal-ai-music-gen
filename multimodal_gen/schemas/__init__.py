"""
MPC Schema Validation Package

Provides Pydantic models for validating MPC project data
before export to .xpj/.xpm files.

Usage:
    from multimodal_gen.schemas import (
        MpcProjectSchema,
        DrumProgramSchema,
        validate_project,
    )
    
    # Validate before export
    try:
        validated = validate_project(my_project)
    except ValidationError as e:
        print(f"Validation failed: {e}")
"""

from .mpc_schema import (
    PadMappingSchema,
    DrumProgramSchema,
    MidiEventSchema,
    TrackSchema,
    SequenceSchema,
    MpcProjectSchema,
    validate_project,
    validate_drum_program,
    from_dataclass,
)

__all__ = [
    'PadMappingSchema',
    'DrumProgramSchema',
    'MidiEventSchema',
    'TrackSchema',
    'SequenceSchema',
    'MpcProjectSchema',
    'validate_project',
    'validate_drum_program',
    'from_dataclass',
]
