"""
Multimodal AI Music Generator

A text-to-MIDI-to-audio generation system with professional humanization
and MPC Software export support.
"""

__version__ = "0.2.0"
__author__ = "AI Music Generator Team"

from .prompt_parser import PromptParser, ParsedPrompt
from .midi_generator import (
    MidiGenerator,
    overdub_midi_track,
    create_midi_version,
    load_and_merge_midi_tracks,
)
from .audio_renderer import AudioRenderer
from .mpc_exporter import MpcExporter
from .arranger import Arranger, SongSection
from .assets_gen import (
    AssetsGenerator,
    WaveformType,
    ADSRParameters,
    SynthesisParameters,
    generate_waveform,
    generate_tone_with_adsr,
    generate_hybrid_sound,
)
from .sample_loader import SampleLibrary, quick_load_samples
from .bwf_writer import (
    BWFWriter,
    save_wav_with_ai_provenance,
    read_bwf_metadata,
)
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
    load_multiple_libraries,
    get_best_instruments_for_genre,
    analyze_sample,
)
from .instrument_intelligence import (
    InstrumentIntelligence,
    InstrumentMetadata,
    SampleFilenameParser,
    GENRE_PROFILES,
    create_instrument_intelligence,
    select_instruments_for_prompt,
)
from .expansion_manager import (
    ExpansionManager,
    ExpansionPack,
    ExpansionInstrument,
    ResolvedInstrument,
    MatchType,
    InstrumentRole,
    SonicFingerprint,
    create_expansion_manager,
    resolve_genre_instruments,
)
from .instrument_resolution import (
    InstrumentResolutionService,
    ResolvedInstrument as ServiceResolvedInstrument,
    MatchType as ServiceMatchType,
    DEFAULT_GENRE_INSTRUMENTS,
    DEFAULT_INSTRUMENT_TO_PROGRAM,
    DEFAULT_PROGRAM_TO_INSTRUMENT,
    create_instrument_service,
)
from .utils import (
    TICKS_PER_BEAT,
    generate_uuid,
    bpm_to_microseconds_per_beat,
    bars_to_ticks,
    note_name_to_midi,
    get_scale_notes,
)

from .midi_recording import (
    list_midi_inputs,
    list_midi_devices_detailed,
    record_midi_to_file,
    replace_channel_in_midi,
    RecordConfig,
    MidiRecordingError,
    MidiDeviceInfo,
)

from .session_graph import (
    SessionGraphBuilder,
    SessionGraph,
    create_session_graph,
    load_session,
    save_session,
)
from .genre_rules import (
    validate_generation,
    repair_violations,
    get_genre_rules,
)
from .take_generator import (
    TakeGenerator,
    TakeConfig,
    TakeLane,
    take_to_midi_track,
)
from .score_plan_adapter import (
    validate_score_plan,
    score_plan_to_parsed_prompt,
    score_plan_to_performance_score,
    extract_seed,
    ScorePlanError,
)

__all__ = [
    "PromptParser",
    "ParsedPrompt",
    "MidiGenerator",
    "overdub_midi_track",
    "create_midi_version",
    "load_and_merge_midi_tracks",
    "AudioRenderer",
    "MpcExporter",
    "Arranger",
    "SongSection",
    "AssetsGenerator",
    "WaveformType",
    "ADSRParameters",
    "SynthesisParameters",
    "generate_waveform",
    "generate_tone_with_adsr",
    "generate_hybrid_sound",
    "SampleLibrary",
    "quick_load_samples",
    "BWFWriter",
    "save_wav_with_ai_provenance",
    "read_bwf_metadata",
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
    "load_multiple_libraries",
    "get_best_instruments_for_genre",
    "analyze_sample",
    # Instrument Intelligence (semantic filtering)
    "InstrumentIntelligence",
    "InstrumentMetadata",
    "SampleFilenameParser",
    "GENRE_PROFILES",
    "create_instrument_intelligence",
    "select_instruments_for_prompt",
    # Expansion Manager (AI-powered instrument resolution)
    "ExpansionManager",
    "ExpansionPack",
    "ExpansionInstrument",
    "ResolvedInstrument",
    "MatchType",
    "InstrumentRole",
    "SonicFingerprint",
    "create_expansion_manager",
    "resolve_genre_instruments",
    # Instrument Resolution Service (bridges expansions to generation pipeline)
    "InstrumentResolutionService",
    "ServiceResolvedInstrument",
    "ServiceMatchType",
    "DEFAULT_GENRE_INSTRUMENTS",
    "DEFAULT_INSTRUMENT_TO_PROGRAM",
    "DEFAULT_PROGRAM_TO_INSTRUMENT",
    "create_instrument_service",
    # Utils
    "TICKS_PER_BEAT",
    "generate_uuid",
    "bpm_to_microseconds_per_beat",
    "bars_to_ticks",
    "note_name_to_midi",
    "get_scale_notes",
    # MIDI recording
    "list_midi_inputs",
    "list_midi_devices_detailed",
    "record_midi_to_file",
    "replace_channel_in_midi",
    "RecordConfig",
    "MidiRecordingError",
    "MidiDeviceInfo",
    # New modules
    "SessionGraphBuilder",
    "SessionGraph",
    "create_session_graph",
    "load_session",
    "save_session",
    "validate_generation",
    "repair_violations",
    "get_genre_rules",
    "TakeGenerator",
    "TakeConfig",
    "TakeLane",
    "take_to_midi_track",
    # Score plan adapter
    "validate_score_plan",
    "score_plan_to_parsed_prompt",
    "score_plan_to_performance_score",
    "extract_seed",
    "ScorePlanError",
]
