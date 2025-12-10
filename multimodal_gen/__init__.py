"""
Multimodal AI Music Generator

A text-to-MIDI-to-audio generation system with professional humanization
and MPC Software export support.
"""

__version__ = "0.1.0"
__author__ = "AI Music Generator Team"

from .prompt_parser import PromptParser, ParsedPrompt
from .midi_generator import MidiGenerator
from .audio_renderer import AudioRenderer
from .mpc_exporter import MpcExporter
from .arranger import Arranger, SongSection
from .assets_gen import AssetsGenerator
from .sample_loader import SampleLibrary, quick_load_samples
from .reference_analyzer import (
    ReferenceAnalyzer,
    ReferenceAnalysis,
    analyze_reference,
    reference_to_prompt,
)
from .instrument_manager import (
    InstrumentLibrary,
    InstrumentMatcher,
    InstrumentAnalyzer,
    SonicProfile,
    AnalyzedInstrument,
    InstrumentCategory,
    discover_instruments,
    get_best_instruments_for_genre,
    analyze_sample,
)
from .utils import (
    TICKS_PER_BEAT,
    generate_uuid,
    bpm_to_microseconds_per_beat,
    bars_to_ticks,
    note_name_to_midi,
    get_scale_notes,
)

__all__ = [
    "PromptParser",
    "ParsedPrompt",
    "MidiGenerator",
    "AudioRenderer",
    "MpcExporter",
    "Arranger",
    "SongSection",
    "AssetsGenerator",
    "SampleLibrary",
    "quick_load_samples",
    "ReferenceAnalyzer",
    "ReferenceAnalysis",
    "analyze_reference",
    "reference_to_prompt",
    # Instrument Manager (3 approaches)
    "InstrumentLibrary",
    "InstrumentMatcher",
    "InstrumentAnalyzer",
    "SonicProfile",
    "AnalyzedInstrument",
    "InstrumentCategory",
    "discover_instruments",
    "get_best_instruments_for_genre",
    "analyze_sample",
    # Utils
    "TICKS_PER_BEAT",
    "generate_uuid",
    "bpm_to_microseconds_per_beat",
    "bars_to_ticks",
    "note_name_to_midi",
    "get_scale_notes",
]
