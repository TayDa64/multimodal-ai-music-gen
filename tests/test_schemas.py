"""Tests for MPC Schema Validation."""
import pytest


class TestSchemaImports:
    """Test suite for schema imports."""
    
    def test_import_all(self):
        """Test all schemas can be imported."""
        from multimodal_gen.schemas import (
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
        
        assert PadMappingSchema is not None
        assert DrumProgramSchema is not None
        assert MidiEventSchema is not None
        assert TrackSchema is not None
        assert SequenceSchema is not None
        assert MpcProjectSchema is not None


class TestPadMappingSchema:
    """Test suite for PadMappingSchema."""
    
    def test_valid_pad_mapping(self):
        """Test valid pad mapping."""
        from multimodal_gen.schemas import PadMappingSchema
        
        pad = PadMappingSchema(
            bank='A',
            pad=0,
            sample_path='[ProjectData]/Samples/kick.wav',
            note=36,
            name='Kick',
        )
        
        assert pad.bank == 'A'
        assert pad.pad == 0
        assert pad.note == 36
        assert pad.volume == 1.0  # Default
        assert pad.pan == 0.5  # Default
    
    def test_pad_mapping_auto_fix_path(self):
        """Test sample path auto-fix."""
        from multimodal_gen.schemas import PadMappingSchema
        
        pad = PadMappingSchema(
            bank='A',
            pad=0,
            sample_path='kick.wav',
            note=36,
            name='Kick',
        )
        
        # Should auto-fix to MPC format
        assert '[ProjectData]' in pad.sample_path or '/' in pad.sample_path
    
    def test_pad_mapping_invalid_bank(self):
        """Test invalid bank raises error."""
        from multimodal_gen.schemas import PadMappingSchema
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            PadMappingSchema(
                bank='Z',  # Invalid - must be A-H
                pad=0,
                sample_path='test.wav',
                note=36,
                name='Test',
            )
    
    def test_pad_mapping_invalid_pad_number(self):
        """Test invalid pad number raises error."""
        from multimodal_gen.schemas import PadMappingSchema
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            PadMappingSchema(
                bank='A',
                pad=20,  # Invalid - must be 0-15
                sample_path='test.wav',
                note=36,
                name='Test',
            )
    
    def test_pad_mapping_invalid_note(self):
        """Test MIDI note out of range raises error."""
        from multimodal_gen.schemas import PadMappingSchema
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            PadMappingSchema(
                bank='A',
                pad=0,
                sample_path='test.wav',
                note=200,  # Invalid - must be 0-127
                name='Test',
            )
    
    def test_pad_mapping_volume_range(self):
        """Test volume out of range raises error."""
        from multimodal_gen.schemas import PadMappingSchema
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            PadMappingSchema(
                bank='A',
                pad=0,
                sample_path='test.wav',
                note=36,
                name='Test',
                volume=1.5,  # Invalid - must be 0-1
            )


class TestDrumProgramSchema:
    """Test suite for DrumProgramSchema."""
    
    def test_valid_drum_program(self):
        """Test valid drum program."""
        from multimodal_gen.schemas import DrumProgramSchema, PadMappingSchema
        
        program = DrumProgramSchema(
            name='Test Kit',
            pads=[
                PadMappingSchema(
                    bank='A',
                    pad=0,
                    sample_path='kick.wav',
                    note=36,
                    name='Kick',
                ),
                PadMappingSchema(
                    bank='A',
                    pad=1,
                    sample_path='snare.wav',
                    note=38,
                    name='Snare',
                ),
            ],
        )
        
        assert program.name == 'Test Kit'
        assert len(program.pads) == 2
        assert program.master_volume == 0.8  # Default
    
    def test_drum_program_empty_pads(self):
        """Test drum program with no pads."""
        from multimodal_gen.schemas import DrumProgramSchema
        
        program = DrumProgramSchema(
            name='Empty Kit',
        )
        
        assert len(program.pads) == 0
    
    def test_drum_program_duplicate_pads(self):
        """Test duplicate pad positions raises error."""
        from multimodal_gen.schemas import DrumProgramSchema, PadMappingSchema
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            DrumProgramSchema(
                name='Test Kit',
                pads=[
                    PadMappingSchema(bank='A', pad=0, sample_path='a.wav', note=36, name='A'),
                    PadMappingSchema(bank='A', pad=0, sample_path='b.wav', note=37, name='B'),  # Duplicate!
                ],
            )


class TestMidiEventSchema:
    """Test suite for MidiEventSchema."""
    
    def test_valid_event(self):
        """Test valid MIDI event."""
        from multimodal_gen.schemas import MidiEventSchema
        
        event = MidiEventSchema(
            tick=0,
            note=60,
            velocity=100,
            duration=480,
        )
        
        assert event.tick == 0
        assert event.note == 60
        assert event.velocity == 100
        assert event.duration == 480
    
    def test_invalid_velocity_zero(self):
        """Test velocity 0 raises error (note-off)."""
        from multimodal_gen.schemas import MidiEventSchema
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            MidiEventSchema(
                tick=0,
                note=60,
                velocity=0,  # Invalid - 0 is note-off
                duration=480,
            )
    
    def test_invalid_note_range(self):
        """Test note out of range raises error."""
        from multimodal_gen.schemas import MidiEventSchema
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            MidiEventSchema(
                tick=0,
                note=130,  # Invalid - must be 0-127
                velocity=100,
                duration=480,
            )


class TestTrackSchema:
    """Test suite for TrackSchema."""
    
    def test_valid_track(self):
        """Test valid track."""
        from multimodal_gen.schemas import TrackSchema
        
        track = TrackSchema(
            name='Drums',
            program_name='Kit 1',
        )
        
        assert track.name == 'Drums'
        assert track.program_name == 'Kit 1'
        assert track.volume == 0.8  # Default
        assert track.mute == False  # Default
    
    def test_track_with_events(self):
        """Test track with MIDI events."""
        from multimodal_gen.schemas import TrackSchema, MidiEventSchema
        
        events = [
            MidiEventSchema(tick=0, note=36, velocity=100, duration=240),
            MidiEventSchema(tick=480, note=38, velocity=90, duration=240),
        ]
        
        track = TrackSchema(
            name='Drums',
            program_name='Kit 1',
            events=events,
        )
        
        assert len(track.events) == 2
    
    def test_track_events_sorted(self):
        """Test track events are sorted by tick."""
        from multimodal_gen.schemas import TrackSchema, MidiEventSchema
        
        # Add events out of order
        events = [
            MidiEventSchema(tick=960, note=36, velocity=100, duration=240),
            MidiEventSchema(tick=0, note=38, velocity=90, duration=240),
            MidiEventSchema(tick=480, note=40, velocity=80, duration=240),
        ]
        
        track = TrackSchema(
            name='Drums',
            program_name='Kit 1',
            events=events,
        )
        
        # Events should be sorted by tick
        assert track.events[0].tick == 0
        assert track.events[1].tick == 480
        assert track.events[2].tick == 960


class TestSequenceSchema:
    """Test suite for SequenceSchema."""
    
    def test_valid_sequence(self):
        """Test valid sequence."""
        from multimodal_gen.schemas import SequenceSchema
        
        seq = SequenceSchema(
            name='Test Sequence',
            bars=8,
            bpm=120.0,
        )
        
        assert seq.name == 'Test Sequence'
        assert seq.bars == 8
        assert seq.bpm == 120.0
        assert seq.time_sig_num == 4  # Default
        assert seq.time_sig_denom == 4  # Default
    
    def test_sequence_invalid_bpm_low(self):
        """Test BPM too low raises error."""
        from multimodal_gen.schemas import SequenceSchema
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            SequenceSchema(
                name='Test',
                bpm=10.0,  # Invalid - min 20
            )
    
    def test_sequence_invalid_bpm_high(self):
        """Test BPM too high raises error."""
        from multimodal_gen.schemas import SequenceSchema
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            SequenceSchema(
                name='Test',
                bpm=500.0,  # Invalid - max 300
            )
    
    def test_sequence_invalid_time_sig_denom(self):
        """Test invalid time signature denominator."""
        from multimodal_gen.schemas import SequenceSchema
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            SequenceSchema(
                name='Test',
                time_sig_denom=3,  # Invalid - must be power of 2
            )
    
    def test_sequence_valid_time_signatures(self):
        """Test valid time signature denominators."""
        from multimodal_gen.schemas import SequenceSchema
        
        for denom in [1, 2, 4, 8, 16, 32]:
            seq = SequenceSchema(
                name='Test',
                time_sig_num=4,
                time_sig_denom=denom,
            )
            assert seq.time_sig_denom == denom


class TestMpcProjectSchema:
    """Test suite for MpcProjectSchema."""
    
    def test_valid_project(self):
        """Test complete project schema."""
        from multimodal_gen.schemas import (
            MpcProjectSchema,
            SequenceSchema,
            DrumProgramSchema,
            TrackSchema,
        )
        
        project = MpcProjectSchema(
            name='Test Project',
            bpm=120.0,
            sequences=[
                SequenceSchema(
                    name='Seq 1',
                    bars=4,
                    tracks=[
                        TrackSchema(name='Drums', program_name='Kit 1'),
                    ],
                ),
            ],
            programs=[
                DrumProgramSchema(name='Kit 1'),
            ],
        )
        
        assert project.name == 'Test Project'
        assert project.bpm == 120.0
        assert len(project.sequences) == 1
        assert len(project.programs) == 1
    
    def test_project_empty(self):
        """Test empty project is valid."""
        from multimodal_gen.schemas import MpcProjectSchema
        
        project = MpcProjectSchema(
            name='Empty Project',
        )
        
        assert len(project.sequences) == 0
        assert len(project.programs) == 0
    
    def test_project_invalid_program_reference(self):
        """Test track referencing non-existent program raises error."""
        from multimodal_gen.schemas import (
            MpcProjectSchema,
            SequenceSchema,
            TrackSchema,
        )
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            MpcProjectSchema(
                name='Test',
                sequences=[
                    SequenceSchema(
                        name='Seq 1',
                        tracks=[
                            TrackSchema(name='Drums', program_name='NonExistent'),
                        ],
                    ),
                ],
                programs=[],  # No programs defined!
            )
    
    def test_project_audio_file_validation(self):
        """Test audio file extension validation."""
        from multimodal_gen.schemas import MpcProjectSchema
        from pydantic import ValidationError
        
        # Valid extensions
        project = MpcProjectSchema(
            name='Test',
            audio_files=['kick.wav', 'snare.aif', 'hihat.mp3'],
        )
        assert len(project.audio_files) == 3
        
        # Invalid extension
        with pytest.raises(ValidationError):
            MpcProjectSchema(
                name='Test',
                audio_files=['sound.xyz'],  # Invalid extension
            )


class TestValidationHelpers:
    """Test suite for validation helper functions."""
    
    def test_validate_project_function(self):
        """Test validate_project function."""
        from multimodal_gen.schemas import validate_project
        from dataclasses import dataclass
        from typing import List
        
        @dataclass
        class MockProject:
            name: str
            bpm: float
            sequences: List
            programs: List
            audio_files: List
            created_date: str = None
        
        project = MockProject(
            name='Test',
            bpm=120.0,
            sequences=[],
            programs=[],
            audio_files=[],
        )
        
        validated = validate_project(project)
        assert validated.name == 'Test'
    
    def test_validate_drum_program_function(self):
        """Test validate_drum_program function."""
        from multimodal_gen.schemas import validate_drum_program
        from dataclasses import dataclass
        from typing import List
        
        @dataclass
        class MockProgram:
            name: str
            pads: List
            master_volume: float = 0.8
        
        program = MockProgram(
            name='Test Kit',
            pads=[],
        )
        
        validated = validate_drum_program(program)
        assert validated.name == 'Test Kit'
    
    def test_from_dataclass_function(self):
        """Test from_dataclass conversion function."""
        from multimodal_gen.schemas import from_dataclass, DrumProgramSchema
        from dataclasses import dataclass
        from typing import List
        
        @dataclass
        class MockProgram:
            name: str
            pads: List
            master_volume: float = 0.8
        
        program = MockProgram(
            name='Converted Kit',
            pads=[],
        )
        
        validated = from_dataclass(program, DrumProgramSchema)
        assert validated.name == 'Converted Kit'
