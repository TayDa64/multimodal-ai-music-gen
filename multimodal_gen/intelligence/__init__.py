"""
MUSE Intelligence Module

Higher-level music intelligence components including:
- HarmonicBrain: Voice leading and harmonic analysis engine
- mpc_corpus: MPC Beats data parser and harmonic analysis
- genre_dna: 10-dimensional genre DNA vectors
- critics: Quality gate metrics for generated music
- midi_bridge: Virtual MIDI bridge for loopMIDI → MPC Beats
"""

# HarmonicBrain may not be implemented yet
try:
    from .harmonic_brain import HarmonicBrain, VoicingConstraints, VoicedChord
    _HAS_HARMONIC_BRAIN = True
except ImportError:
    _HAS_HARMONIC_BRAIN = False

from .mpc_corpus import (
    RawChord,
    RawProgression,
    EnrichedProgression,
    HarmonicAnalysis,
    KeyCenter,
    ParsedArpPattern,
    ArpAnalysis,
    GenreHarmonicProfile,
    CorpusData,
    load_corpus,
    parse_progression,
    parse_all_progressions,
    enrich_progression,
    parse_arp_pattern,
    parse_all_arp_patterns,
    build_genre_profiles,
    extract_voicing_templates,
    get_mpc_beats_path,
)
from .genre_dna import (
    GenreDNAVector,
    GenreFusionResult,
    NAMED_FUSIONS,
    compute_genre_dna_from_corpus,
    get_genre_dna,
    blend_genres,
    genre_distance,
    get_named_fusion,
    nearest_genre,
    classify_blend_distance,
    list_genres,
)
from .critics import (
    CriticResult,
    CriticReport,
    compute_vlc,
    compute_bkas,
    compute_adc,
    run_all_critics,
)

# embeddings — optional (needs numpy, always available in this project)
try:
    from .embeddings import (
        EmbeddingService,
        AssetEmbedding,
        VectorIndex,
        SearchResult,
        search_assets,
        build_embedding_index,
        cosine_similarity,
        BUILTIN_DESCRIPTION_COUNT,
    )
    _HAS_EMBEDDINGS = True
except ImportError:
    _HAS_EMBEDDINGS = False

# midi_bridge has optional deps — import only the safe symbols
try:
    from .midi_bridge import (
        MidiBridge,
        MidiBridgeConfig,
        create_midi_bridge,
        get_midi_setup_instructions,
        RTMIDI_AVAILABLE,
    )
    _HAS_MIDI_BRIDGE = True
except ImportError:
    _HAS_MIDI_BRIDGE = False

__all__ = [
    # mpc_corpus
    "RawChord",
    "RawProgression",
    "EnrichedProgression",
    "HarmonicAnalysis",
    "KeyCenter",
    "ParsedArpPattern",
    "ArpAnalysis",
    "GenreHarmonicProfile",
    "CorpusData",
    "load_corpus",
    "parse_progression",
    "parse_all_progressions",
    "enrich_progression",
    "parse_arp_pattern",
    "parse_all_arp_patterns",
    "build_genre_profiles",
    "extract_voicing_templates",
    "get_mpc_beats_path",
    # genre_dna
    "GenreDNAVector",
    "GenreFusionResult",
    "NAMED_FUSIONS",
    "compute_genre_dna_from_corpus",
    "get_genre_dna",
    "blend_genres",
    "genre_distance",
    "get_named_fusion",
    "nearest_genre",
    "classify_blend_distance",
    "list_genres",
    # critics
    "CriticResult",
    "CriticReport",
    "compute_vlc",
    "compute_bkas",
    "compute_adc",
    "run_all_critics",
]

if _HAS_HARMONIC_BRAIN:
    __all__.extend(["HarmonicBrain", "VoicingConstraints", "VoicedChord"])

if _HAS_EMBEDDINGS:
    __all__.extend([
        "EmbeddingService",
        "AssetEmbedding",
        "VectorIndex",
        "SearchResult",
        "search_assets",
        "build_embedding_index",
        "cosine_similarity",
        "BUILTIN_DESCRIPTION_COUNT",
    ])

if _HAS_MIDI_BRIDGE:
    __all__.extend([
        "MidiBridge",
        "MidiBridgeConfig",
        "create_midi_bridge",
        "get_midi_setup_instructions",
        "RTMIDI_AVAILABLE",
    ])

# preferences — Contract C14
try:
    from .preferences import (
        PreferenceDimensions,
        PreferenceSignal,
        SessionSummary,
        UserPreferences,
        PreferenceTracker,
    )
    _HAS_PREFERENCES = True
except ImportError:
    _HAS_PREFERENCES = False

if _HAS_PREFERENCES:
    __all__.extend([
        "PreferenceDimensions",
        "PreferenceSignal",
        "SessionSummary",
        "UserPreferences",
        "PreferenceTracker",
    ])
