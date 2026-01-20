"""
MPC Exporter - Export generated music to Akai MPC .xpj format

This module generates MPC Software 2.x compatible project files including:
- .xpj project file (XML-based)
- .xpm drum program files
- .xal audio layer references
- Proper [ProjectData] folder structure with relative paths

Targets MPC Software 2.13.1.27+ compatibility with MPC One/Live/X hardware.

Technical Notes:
- MPC uses 480 PPQ (Pulses Per Quarter note) - matches our MIDI standard
- Pad banks A-H with 16 pads each (0-127 MIDI notes mapped)
- Sequences organized in tracks with clip automation
- Audio references use relative paths from [ProjectData] folder
"""

import os
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
from datetime import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom
import uuid

if TYPE_CHECKING:
    import mido

from .utils import (
    TICKS_PER_BEAT,
    GM_DRUM_NOTES,
    midi_note_to_name,
)

# Optional validation (graceful degradation if pydantic not installed)
try:
    from .schemas import validate_project, validate_drum_program
    HAS_VALIDATION = True
except ImportError:
    HAS_VALIDATION = False
    validate_project = None
    validate_drum_program = None


# MPC-specific constants
MPC_PPQ = 480  # MPC uses 480 ticks per quarter note
MPC_PAD_BANKS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
MPC_PADS_PER_BANK = 16
MPC_SOFTWARE_VERSION = "2.13.1"


@dataclass
class PadMapping:
    """Maps a pad to a sample file."""
    bank: str  # A-H
    pad: int  # 0-15
    sample_path: str  # Relative path from [ProjectData]
    note: int  # MIDI note number
    name: str  # Display name
    volume: float = 1.0  # 0.0-1.0
    pan: float = 0.5  # 0.0=L, 0.5=C, 1.0=R
    tune: float = 0.0  # Semitones (-24 to +24)
    attack: float = 0.0  # Envelope attack (0-1)
    decay: float = 1.0  # Envelope decay (0-1)
    mute_group: int = 0  # 0=off, 1-32 for mute groups


@dataclass
class DrumProgram:
    """Represents an MPC drum program (.xpm file)."""
    name: str
    pads: List[PadMapping] = field(default_factory=list)
    master_volume: float = 0.8
    
    def get_pad(self, bank: str, pad: int) -> Optional[PadMapping]:
        """Get pad mapping by bank and pad number."""
        for p in self.pads:
            if p.bank == bank and p.pad == pad:
                return p
        return None


@dataclass
class MidiEvent:
    """MIDI event for MPC sequence."""
    tick: int
    note: int
    velocity: int
    duration: int  # In ticks
    
    
@dataclass
class Track:
    """MPC track containing MIDI events."""
    name: str
    program_name: str  # Reference to drum program
    events: List[MidiEvent] = field(default_factory=list)
    volume: float = 0.8
    pan: float = 0.5
    mute: bool = False
    solo: bool = False


@dataclass
class Sequence:
    """MPC sequence (like a pattern in a DAW)."""
    name: str
    bars: int = 4
    bpm: float = 120.0
    time_sig_num: int = 4
    time_sig_denom: int = 4
    tracks: List[Track] = field(default_factory=list)


@dataclass
class MpcProject:
    """Complete MPC project structure."""
    name: str
    bpm: float = 120.0
    sequences: List[Sequence] = field(default_factory=list)
    programs: List[DrumProgram] = field(default_factory=list)
    audio_files: List[str] = field(default_factory=list)  # Paths to copy
    created_date: str = field(default_factory=lambda: datetime.now().isoformat())


def generate_uuid() -> str:
    """Generate MPC-compatible UUID string."""
    return str(uuid.uuid4()).upper()


def format_xml(element: ET.Element, indent: str = "  ") -> str:
    """Pretty-print XML with proper indentation."""
    rough_string = ET.tostring(element, encoding='unicode')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent=indent)


def _create_xpj_root(project: MpcProject) -> ET.Element:
    """Create the root element for .xpj project file."""
    root = ET.Element("MPCVObject")
    root.set("Version", "2.0")
    root.set("Application", "MPC")
    root.set("ApplicationVersion", MPC_SOFTWARE_VERSION)
    
    # Project metadata
    meta = ET.SubElement(root, "Metadata")
    ET.SubElement(meta, "Name").text = project.name
    ET.SubElement(meta, "CreatedDate").text = project.created_date
    ET.SubElement(meta, "ModifiedDate").text = datetime.now().isoformat()
    ET.SubElement(meta, "UUID").text = generate_uuid()
    
    return root


def _add_master_settings(root: ET.Element, project: MpcProject) -> None:
    """Add master tempo and time signature settings."""
    master = ET.SubElement(root, "MasterSettings")
    ET.SubElement(master, "Tempo").text = str(project.bpm)
    ET.SubElement(master, "TimeSignatureNumerator").text = "4"
    ET.SubElement(master, "TimeSignatureDenominator").text = "4"
    ET.SubElement(master, "MasterVolume").text = "0.8"
    ET.SubElement(master, "PPQ").text = str(MPC_PPQ)
    
    # Metronome settings
    metro = ET.SubElement(master, "Metronome")
    ET.SubElement(metro, "Enabled").text = "false"
    ET.SubElement(metro, "Volume").text = "0.5"
    ET.SubElement(metro, "CountIn").text = "1"


def _add_programs(root: ET.Element, project: MpcProject) -> None:
    """Add drum program references to project."""
    programs_elem = ET.SubElement(root, "Programs")
    
    for idx, program in enumerate(project.programs):
        prog_elem = ET.SubElement(programs_elem, "Program")
        prog_elem.set("Index", str(idx))
        
        ET.SubElement(prog_elem, "Name").text = program.name
        ET.SubElement(prog_elem, "Type").text = "Drum"
        ET.SubElement(prog_elem, "FilePath").text = f"[ProjectData]/{program.name}.xpm"
        ET.SubElement(prog_elem, "UUID").text = generate_uuid()
        ET.SubElement(prog_elem, "MasterVolume").text = str(program.master_volume)


def _add_sequences(root: ET.Element, project: MpcProject) -> None:
    """Add sequences to project."""
    sequences_elem = ET.SubElement(root, "Sequences")
    
    for idx, seq in enumerate(project.sequences):
        seq_elem = ET.SubElement(sequences_elem, "Sequence")
        seq_elem.set("Index", str(idx))
        
        # Sequence metadata
        ET.SubElement(seq_elem, "Name").text = seq.name
        ET.SubElement(seq_elem, "UUID").text = generate_uuid()
        ET.SubElement(seq_elem, "Bars").text = str(seq.bars)
        ET.SubElement(seq_elem, "Tempo").text = str(seq.bpm)
        ET.SubElement(seq_elem, "TimeSignatureNumerator").text = str(seq.time_sig_num)
        ET.SubElement(seq_elem, "TimeSignatureDenominator").text = str(seq.time_sig_denom)
        
        # Sequence length in ticks
        ticks_per_bar = MPC_PPQ * seq.time_sig_num * (4 // seq.time_sig_denom)
        total_ticks = seq.bars * ticks_per_bar
        ET.SubElement(seq_elem, "LengthTicks").text = str(total_ticks)
        
        # Add tracks
        tracks_elem = ET.SubElement(seq_elem, "Tracks")
        for track_idx, track in enumerate(seq.tracks):
            _add_track(tracks_elem, track, track_idx)


def _add_track(tracks_elem: ET.Element, track: Track, index: int) -> None:
    """Add a track to sequence."""
    track_elem = ET.SubElement(tracks_elem, "Track")
    track_elem.set("Index", str(index))
    
    ET.SubElement(track_elem, "Name").text = track.name
    ET.SubElement(track_elem, "UUID").text = generate_uuid()
    ET.SubElement(track_elem, "ProgramName").text = track.program_name
    ET.SubElement(track_elem, "Volume").text = str(track.volume)
    ET.SubElement(track_elem, "Pan").text = str(track.pan)
    ET.SubElement(track_elem, "Mute").text = str(track.mute).lower()
    ET.SubElement(track_elem, "Solo").text = str(track.solo).lower()
    ET.SubElement(track_elem, "MidiChannel").text = "10"  # Drum channel
    
    # Add MIDI events
    events_elem = ET.SubElement(track_elem, "Events")
    for event in track.events:
        event_elem = ET.SubElement(events_elem, "NoteEvent")
        ET.SubElement(event_elem, "Tick").text = str(event.tick)
        ET.SubElement(event_elem, "Note").text = str(event.note)
        ET.SubElement(event_elem, "Velocity").text = str(event.velocity)
        ET.SubElement(event_elem, "Duration").text = str(event.duration)


def _add_audio_pool(root: ET.Element, project: MpcProject) -> None:
    """Add audio file references to project."""
    pool_elem = ET.SubElement(root, "AudioPool")
    
    for idx, audio_path in enumerate(project.audio_files):
        file_elem = ET.SubElement(pool_elem, "AudioFile")
        file_elem.set("Index", str(idx))
        
        filename = Path(audio_path).name
        ET.SubElement(file_elem, "Name").text = Path(audio_path).stem
        ET.SubElement(file_elem, "FilePath").text = f"[ProjectData]/Samples/{filename}"
        ET.SubElement(file_elem, "UUID").text = generate_uuid()


def generate_xpj(project: MpcProject) -> str:
    """Generate .xpj project file XML content."""
    root = _create_xpj_root(project)
    _add_master_settings(root, project)
    _add_programs(root, project)
    _add_sequences(root, project)
    _add_audio_pool(root, project)
    
    return format_xml(root)


def _create_xpm_root(program: DrumProgram) -> ET.Element:
    """Create the root element for .xpm drum program file."""
    root = ET.Element("MPCVObject")
    root.set("Version", "2.0")
    root.set("Application", "MPC")
    root.set("ApplicationVersion", MPC_SOFTWARE_VERSION)
    root.set("Type", "DrumProgram")
    
    # Program metadata
    meta = ET.SubElement(root, "Metadata")
    ET.SubElement(meta, "Name").text = program.name
    ET.SubElement(meta, "UUID").text = generate_uuid()
    ET.SubElement(meta, "MasterVolume").text = str(program.master_volume)
    
    return root


def _add_pad_banks(root: ET.Element, program: DrumProgram) -> None:
    """Add pad bank configuration to drum program."""
    banks_elem = ET.SubElement(root, "PadBanks")
    
    for bank_letter in MPC_PAD_BANKS:
        bank_elem = ET.SubElement(banks_elem, "Bank")
        bank_elem.set("Name", bank_letter)
        
        # Add 16 pads per bank
        for pad_num in range(MPC_PADS_PER_BANK):
            pad_elem = ET.SubElement(bank_elem, "Pad")
            pad_elem.set("Number", str(pad_num))
            
            # Calculate MIDI note for this pad position
            bank_index = MPC_PAD_BANKS.index(bank_letter)
            midi_note = 36 + (bank_index * 16) + pad_num
            
            # Check if we have a mapping for this pad
            mapping = program.get_pad(bank_letter, pad_num)
            
            if mapping:
                ET.SubElement(pad_elem, "Name").text = mapping.name
                ET.SubElement(pad_elem, "MidiNote").text = str(mapping.note)
                ET.SubElement(pad_elem, "Volume").text = str(mapping.volume)
                ET.SubElement(pad_elem, "Pan").text = str(mapping.pan)
                ET.SubElement(pad_elem, "Tune").text = str(mapping.tune)
                ET.SubElement(pad_elem, "Attack").text = str(mapping.attack)
                ET.SubElement(pad_elem, "Decay").text = str(mapping.decay)
                ET.SubElement(pad_elem, "MuteGroup").text = str(mapping.mute_group)
                
                # Layer reference (sample file)
                layers_elem = ET.SubElement(pad_elem, "Layers")
                layer_elem = ET.SubElement(layers_elem, "Layer")
                layer_elem.set("Index", "0")
                ET.SubElement(layer_elem, "FilePath").text = mapping.sample_path
                ET.SubElement(layer_elem, "VelocityLow").text = "0"
                ET.SubElement(layer_elem, "VelocityHigh").text = "127"
            else:
                # Empty pad
                ET.SubElement(pad_elem, "Name").text = f"Pad {bank_letter}{pad_num + 1}"
                ET.SubElement(pad_elem, "MidiNote").text = str(midi_note)
                ET.SubElement(pad_elem, "Volume").text = "1.0"
                ET.SubElement(pad_elem, "Pan").text = "0.5"


def generate_xpm(program: DrumProgram) -> str:
    """Generate .xpm drum program file XML content."""
    root = _create_xpm_root(program)
    _add_pad_banks(root, program)
    
    return format_xml(root)


def create_default_drum_program(samples_dir: str = "[ProjectData]/Samples") -> DrumProgram:
    """Create a default trap/hip-hop drum program mapping.
    
    Standard GM drum mapping on Bank A (pads 0-15):
    - Pad 0 (A01): Kick (C1/36)
    - Pad 1 (A02): Snare (D1/38)
    - Pad 2 (A03): Closed HH (F#1/42)
    - Pad 3 (A04): Open HH (A#1/46)
    - Pad 4 (A05): Clap (D#1/39)
    - Pad 5 (A06): Rim (C#1/37)
    - Pad 6 (A07): Tom Low (G1/43)
    - Pad 7 (A08): Tom Mid (B1/47)
    - etc.
    """
    program = DrumProgram(name="Drums")
    
    # Map GM drum notes to MPC pads
    gm_to_pad = {
        36: ("A", 0, "Kick"),      # C1 - Bass Drum
        37: ("A", 5, "Rim"),       # C#1 - Side Stick
        38: ("A", 1, "Snare"),     # D1 - Snare
        39: ("A", 4, "Clap"),      # D#1 - Clap
        40: ("A", 6, "Snare2"),    # E1 - Electric Snare
        42: ("A", 2, "HH Closed"), # F#1 - Closed HH
        44: ("A", 7, "HH Pedal"),  # G#1 - Pedal HH
        46: ("A", 3, "HH Open"),   # A#1 - Open HH
        47: ("A", 9, "Tom Mid"),   # B1 - Mid Tom
        43: ("A", 8, "Tom Low"),   # G1 - Low Tom
        49: ("A", 10, "Crash"),    # C#2 - Crash Cymbal
        51: ("A", 11, "Ride"),     # D#2 - Ride Cymbal
    }
    
    for note, (bank, pad, name) in gm_to_pad.items():
        sample_name = name.lower().replace(" ", "_")
        mapping = PadMapping(
            bank=bank,
            pad=pad,
            sample_path=f"{samples_dir}/{sample_name}.wav",
            note=note,
            name=name,
            volume=1.0,
            pan=0.5,
            mute_group=1 if "HH" in name else 0,  # Hi-hats in mute group
        )
        program.pads.append(mapping)
    
    return program


class MpcExporter:
    """Export music generator output to MPC project format."""
    
    def __init__(self, output_dir: str):
        """Initialize exporter with output directory.
        
        Args:
            output_dir: Base directory for MPC project output
        """
        self.output_dir = Path(output_dir)
        self.project_data_dir = self.output_dir / "[ProjectData]"
        self.samples_dir = self.project_data_dir / "Samples"
        
    def _ensure_directories(self) -> None:
        """Create required MPC directory structure."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.project_data_dir.mkdir(exist_ok=True)
        self.samples_dir.mkdir(exist_ok=True)
        
    def _copy_samples(self, sample_paths: List[str]) -> List[str]:
        """Copy sample files to [ProjectData]/Samples.
        
        Args:
            sample_paths: List of source sample file paths
            
        Returns:
            List of relative paths for MPC references
        """
        copied_paths = []
        
        for src_path in sample_paths:
            src = Path(src_path)
            if src.exists():
                dst = self.samples_dir / src.name
                shutil.copy2(src, dst)
                copied_paths.append(f"[ProjectData]/Samples/{src.name}")
            else:
                print(f"Warning: Sample not found: {src_path}")
                
        return copied_paths
    
    def export_midi_to_mpc(
        self,
        midi_file: "mido.MidiFile",
        project_name: str,
        sample_paths: Optional[List[str]] = None,
        bpm: float = 120.0,
    ) -> str:
        """Export a MIDI file to MPC project format.
        
        Args:
            midi_file: mido.MidiFile object to export
            project_name: Name for the MPC project
            sample_paths: Optional list of sample file paths to include
            bpm: Tempo in BPM
            
        Returns:
            Path to the exported .xpj file
        """
        self._ensure_directories()
        
        # Copy samples if provided
        if sample_paths:
            self._copy_samples(sample_paths)
        
        # Create project structure
        project = MpcProject(
            name=project_name,
            bpm=bpm,
        )
        
        # Create default drum program
        drum_program = create_default_drum_program()
        project.programs.append(drum_program)
        
        # Convert MIDI to MPC sequences
        sequence = self._midi_to_sequence(midi_file, project_name, bpm)
        project.sequences.append(sequence)
        
        # Track audio files
        if sample_paths:
            project.audio_files = sample_paths
        
        # Generate and write .xpj file
        xpj_content = generate_xpj(project)
        xpj_path = self.output_dir / f"{project_name}.xpj"
        with open(xpj_path, 'w', encoding='utf-8') as f:
            f.write(xpj_content)
        
        # Generate and write .xpm drum program
        xpm_content = generate_xpm(drum_program)
        xpm_path = self.project_data_dir / f"{drum_program.name}.xpm"
        with open(xpm_path, 'w', encoding='utf-8') as f:
            f.write(xpm_content)
        
        print(f"Exported MPC project: {xpj_path}")
        return str(xpj_path)
    
    def _midi_to_sequence(
        self,
        midi_file: "mido.MidiFile",
        name: str,
        bpm: float,
    ) -> Sequence:
        """Convert MIDI file to MPC sequence.
        
        Args:
            midi_file: mido.MidiFile to convert
            name: Sequence name
            bpm: Tempo in BPM
            
        Returns:
            MPC Sequence object
        """
        # Calculate length in bars
        total_ticks = 0
        for track in midi_file.tracks:
            track_ticks = sum(msg.time for msg in track)
            total_ticks = max(total_ticks, track_ticks)
        
        ticks_per_bar = MPC_PPQ * 4  # Assuming 4/4 time
        bars = max(4, (total_ticks + ticks_per_bar - 1) // ticks_per_bar)
        
        sequence = Sequence(
            name=name,
            bars=bars,
            bpm=bpm,
        )
        
        # Convert each MIDI track
        for track_idx, midi_track in enumerate(midi_file.tracks):
            if not any(msg.type == 'note_on' for msg in midi_track):
                continue  # Skip tracks with no notes
                
            track = self._midi_track_to_mpc_track(
                midi_track,
                f"Track {track_idx + 1}",
                "Drums",
            )
            sequence.tracks.append(track)
        
        return sequence
    
    def _midi_track_to_mpc_track(
        self,
        midi_track: "mido.MidiTrack",
        name: str,
        program_name: str,
    ) -> Track:
        """Convert MIDI track to MPC track.
        
        Args:
            midi_track: mido.MidiTrack to convert
            name: Track name
            program_name: Reference to drum program
            
        Returns:
            MPC Track object
        """
        track = Track(name=name, program_name=program_name)
        
        # Track note on/off for duration calculation
        note_starts: Dict[int, Tuple[int, int]] = {}  # note -> (tick, velocity)
        current_tick = 0
        
        for msg in midi_track:
            current_tick += msg.time
            
            if msg.type == 'note_on' and msg.velocity > 0:
                note_starts[msg.note] = (current_tick, msg.velocity)
                
            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                if msg.note in note_starts:
                    start_tick, velocity = note_starts.pop(msg.note)
                    duration = current_tick - start_tick
                    
                    event = MidiEvent(
                        tick=start_tick,
                        note=msg.note,
                        velocity=velocity,
                        duration=max(duration, MPC_PPQ // 8),  # Min 32nd note
                    )
                    track.events.append(event)
        
        # Handle any notes without note_off
        for note, (start_tick, velocity) in note_starts.items():
            event = MidiEvent(
                tick=start_tick,
                note=note,
                velocity=velocity,
                duration=MPC_PPQ,  # Default to quarter note
            )
            track.events.append(event)
        
        # Sort events by tick
        track.events.sort(key=lambda e: e.tick)
        
        return track
    
    def export_project(
        self,
        project_name: str,
        sequences: List[Sequence],
        programs: List[DrumProgram],
        sample_paths: Optional[List[str]] = None,
        bpm: float = 120.0,
        validate: bool = True,
    ) -> str:
        """Export a complete MPC project.
        
        Args:
            project_name: Name for the MPC project
            sequences: List of MPC sequences
            programs: List of drum programs
            sample_paths: Optional list of sample file paths
            bpm: Tempo in BPM
            validate: If True, validate data before export (requires pydantic)
            
        Returns:
            Path to the exported .xpj file
            
        Raises:
            pydantic.ValidationError: If validate=True and validation fails
        """
        self._ensure_directories()
        
        # Copy samples
        if sample_paths:
            self._copy_samples(sample_paths)
        
        # Create project
        project = MpcProject(
            name=project_name,
            bpm=bpm,
            sequences=sequences,
            programs=programs,
            audio_files=sample_paths or [],
        )
        
        # Validate if enabled and pydantic is available
        if validate and HAS_VALIDATION and validate_project is not None:
            try:
                validate_project(project)
            except Exception as e:
                print(f"Warning: MPC project validation failed: {e}")
                # Re-raise to let caller handle validation errors
                raise
        
        # Generate and write .xpj file
        xpj_content = generate_xpj(project)
        xpj_path = self.output_dir / f"{project_name}.xpj"
        with open(xpj_path, 'w', encoding='utf-8') as f:
            f.write(xpj_content)
        
        # Generate and write .xpm files for each program
        for program in programs:
            xpm_content = generate_xpm(program)
            xpm_path = self.project_data_dir / f"{program.name}.xpm"
            with open(xpm_path, 'w', encoding='utf-8') as f:
                f.write(xpm_content)
        
        print(f"Exported MPC project: {xpj_path}")
        return str(xpj_path)


def create_trap_drum_program(samples_dir: str = "[ProjectData]/Samples") -> DrumProgram:
    """Create a trap-style drum program with typical mappings.
    
    Trap layout:
    - Pad A01: 808 Kick
    - Pad A02: Snare
    - Pad A03: Closed Hi-hat
    - Pad A04: Open Hi-hat  
    - Pad A05: Clap
    - Pad A06: Perc 1
    - Pad A07: Perc 2
    - Pad A08: Crash
    """
    program = DrumProgram(name="Trap Kit")
    
    trap_pads = [
        ("A", 0, "808 Kick", 36, 1.0, 0.5),
        ("A", 1, "Snare", 38, 0.9, 0.5),
        ("A", 2, "HH Closed", 42, 0.7, 0.6),   # Slightly right
        ("A", 3, "HH Open", 46, 0.7, 0.4),     # Slightly left
        ("A", 4, "Clap", 39, 0.85, 0.5),
        ("A", 5, "Rim Shot", 37, 0.8, 0.5),
        ("A", 6, "Perc 1", 47, 0.75, 0.3),
        ("A", 7, "Perc 2", 48, 0.75, 0.7),
        ("A", 8, "Crash", 49, 0.6, 0.5),
        ("A", 9, "808 Kick Low", 35, 1.0, 0.5),
        ("A", 10, "Snare 2", 40, 0.85, 0.5),
        ("A", 11, "Snap", 31, 0.8, 0.5),
    ]
    
    for bank, pad, name, note, vol, pan in trap_pads:
        sample_name = name.lower().replace(" ", "_")
        mapping = PadMapping(
            bank=bank,
            pad=pad,
            sample_path=f"{samples_dir}/{sample_name}.wav",
            note=note,
            name=name,
            volume=vol,
            pan=pan,
            mute_group=1 if "HH" in name else 0,
        )
        program.pads.append(mapping)
    
    return program


def create_lofi_drum_program(samples_dir: str = "[ProjectData]/Samples") -> DrumProgram:
    """Create a lo-fi hip-hop drum program."""
    program = DrumProgram(name="Lofi Kit")
    
    lofi_pads = [
        ("A", 0, "Dusty Kick", 36, 0.9, 0.5),
        ("A", 1, "Snare", 38, 0.85, 0.48),
        ("A", 2, "HH Closed", 42, 0.6, 0.55),
        ("A", 3, "HH Open", 46, 0.55, 0.45),
        ("A", 4, "Clap", 39, 0.75, 0.52),
        ("A", 5, "Shaker", 70, 0.5, 0.6),
        ("A", 6, "Vinyl Crackle", 31, 0.3, 0.5),
    ]
    
    for bank, pad, name, note, vol, pan in lofi_pads:
        sample_name = name.lower().replace(" ", "_")
        mapping = PadMapping(
            bank=bank,
            pad=pad,
            sample_path=f"{samples_dir}/{sample_name}.wav",
            note=note,
            name=name,
            volume=vol,
            pan=pan,
            mute_group=1 if "HH" in name else 0,
        )
        program.pads.append(mapping)
    
    return program


# Convenience function for quick export
def quick_export_midi(
    midi_file: "mido.MidiFile",
    output_dir: str,
    project_name: str,
    sample_paths: Optional[List[str]] = None,
    bpm: float = 120.0,
    genre: str = "trap",
) -> str:
    """Quick export MIDI to MPC format.
    
    Args:
        midi_file: mido.MidiFile to export
        output_dir: Output directory path
        project_name: Project name
        sample_paths: Optional sample file paths
        bpm: Tempo in BPM
        genre: Genre for drum program selection ("trap", "lofi", "default")
        
    Returns:
        Path to exported .xpj file
    """
    exporter = MpcExporter(output_dir)
    
    # Create genre-appropriate drum program
    if genre == "trap":
        program = create_trap_drum_program()
    elif genre == "lofi":
        program = create_lofi_drum_program()
    else:
        program = create_default_drum_program()
    
    # Create project
    project = MpcProject(
        name=project_name,
        bpm=bpm,
        programs=[program],
        audio_files=sample_paths or [],
    )
    
    return exporter.export_midi_to_mpc(
        midi_file,
        project_name,
        sample_paths,
        bpm,
    )
