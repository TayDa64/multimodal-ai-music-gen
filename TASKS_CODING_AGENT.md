# Coding Agent Tasks - Masterclass Musicality

## Overview
Atomic, PR-ready tasks for implementing masterclass-level music generation. Each task is self-contained with clear acceptance criteria.

> **Status**: All 15 tasks COMPLETE as of 2026-02-14 (Sprints 5-11 + Waves 1-3).  
> **Test Baseline**: 1223 passed, 6 skipped.  
> **Verification**: Every module imports cleanly, has dedicated test coverage, and is wired into the generation pipeline.

---

## ✅ CRITICAL PRIORITY (Sprint 1) — ALL COMPLETE

### TASK-001: Create Motif Generation Module
**Estimated Effort:** 4-6 hours
**File:** `multimodal_gen/motifs.py` (new)

**Context:**
Motifs are short melodic/rhythmic ideas that provide thematic coherence. This is the foundation for all melodic improvements.

**Implementation:**
```python
# Required functions
def generate_base_motif(
    key: str,              # e.g., "C", "F#"
    scale_type: str,       # "minor", "major", "tizita_minor", etc.
    bars: int = 2,
    notes_per_bar: int = 4,
    contour: str = "arch", # "ascending", "descending", "arch", "wave"
    seed: int = None
) -> List[MotifNote]:
    """Generate a base motif constrained to scale."""

@dataclass
class MotifNote:
    pitch: int        # MIDI note number
    duration: float   # In beats
    velocity: int     # 0-127
    offset: float     # Start time in beats

# Support existing Ethiopian scales from genre_rules.py
# Ensure stepwise motion dominant (70%), leaps (30%) and leaps resolved
```

**Acceptance Criteria:**
- [x] Generates musically coherent motifs (stepwise motion, resolved leaps)
- [x] Supports all scales including Ethiopian (tizita, ambassel, anchihoye, bati)
- [x] Seed-based reproducibility
- [x] Unit tests: `tests/test_motif_engine.py` (52 tests), `tests/test_arranger_motifs.py` (31 tests)
- [x] Integration: wired into `midi_generator.py` via `motif_engine.py` (Sprint 6)

**Implementation**: `multimodal_gen/motif_engine.py` — Motif dataclass, `generate_base_motif()`, contour control, scale-constrained generation, 15 exports.

---

### TASK-002: Implement Motif Transformations ✅
**Estimated Effort:** 3-4 hours
**File:** `multimodal_gen/motifs.py` (extend)
**Depends on:** TASK-001

**Implementation:**
```python
def transform_motif(
    motif: List[MotifNote],
    technique: str,
    params: dict = None
) -> List[MotifNote]:
    """
    Apply compositional transformation to motif.
    
    Techniques:
    - "inversion": Mirror pitches around axis (default: first note)
    - "retrograde": Reverse note order
    - "retrograde_inversion": Both combined
    - "augmentation": Double durations
    - "diminution": Halve durations
    - "sequence": Transpose by interval (params: {"interval": 3})
    - "fragmentation": Extract subset (params: {"start": 0, "length": 4})
    - "ornamentation": Add passing/neighbor tones (params: {"density": 0.3})
    """

def get_related_motifs(
    base: List[MotifNote],
    count: int = 4,
    variation_range: float = 0.5  # 0=identical, 1=very different
) -> List[List[MotifNote]]:
    """Generate family of related motifs for arrangement."""
```

**Acceptance Criteria:**
- [x] All 8+ transformations implemented (inversion, retrograde, retrograde_inversion, augmentation, diminution, sequence, fragmentation, ornamentation, displace)
- [x] Transformations chainable via `Motif.transform()` method
- [x] Output always valid MIDI range (0-127) — velocity clamped, pitch bounded
- [x] Unit tests: `tests/test_motif_transforms.py` (17 tests)
- [x] `get_related_motifs()` generates family of variations

**Implementation**: Extended in `multimodal_gen/motif_engine.py` (Sprint 6). Edge cases guarded: `fragment(length=0)`, `displace` negative offset clamped.

---

### TASK-003: Advanced Microtiming Engine ✅
**Estimated Effort:** 5-6 hours
**File:** `multimodal_gen/groove_engine.py` (new)

**Context:**
Replace simple swing with genre-specific microtiming. Professional tracks have characteristic timing "feel" that's more nuanced than simple swing percentages.

**Implementation:**
```python
@dataclass
class GrooveProfile:
    name: str
    genre: str
    timing_offsets: Dict[str, TimingConfig]  # Per subdivision
    velocity_patterns: Dict[str, List[float]]  # Per instrument
    swing_amount: float  # 0.5 = straight, 0.67 = triplet swing

@dataclass  
class TimingConfig:
    offset_ms: float = 0       # Fixed offset
    variance_ms: float = 0     # Random variance (gaussian)
    probability: float = 1.0   # Chance to apply

# Built-in profiles
GROOVE_PROFILES = {
    "trap": GrooveProfile(
        name="trap",
        genre="trap",
        timing_offsets={
            "8th": TimingConfig(offset_ms=-8, variance_ms=3),
            "16th": TimingConfig(offset_ms=12, variance_ms=8),
        },
        velocity_patterns={
            "hihat": [1.0, 0.6, 0.8, 0.5, 0.9, 0.6, 0.8, 0.5],
        },
        swing_amount=0.5
    ),
    "lofi": GrooveProfile(...),
    "boom_bap": GrooveProfile(...),
    "house": GrooveProfile(...),
    "g_funk": GrooveProfile(...),
    "ethiopian_eskista": GrooveProfile(...),
}

def apply_groove(
    events: List[MidiEvent],
    profile: Union[str, GrooveProfile],
    intensity: float = 1.0,  # 0=none, 1=full
    seed: int = None
) -> List[MidiEvent]:
    """Apply groove profile to MIDI events."""

def load_groove_profile(path: str) -> GrooveProfile:
    """Load custom groove from JSON."""
```

**Acceptance Criteria:**
- [x] 6+ genre profiles implemented (trap, lofi, boom_bap, house, g_funk, ethiopian, drill, etc.)
- [x] Per-instrument timing (kick tight, hi-hat loose) via `groove_templates.py` GENRE_TIMING_OFFSETS
- [x] Intensity parameter works (0-1)
- [x] Seed-based reproducibility
- [x] Custom profiles loadable from JSON
- [x] Integration: wired into `midi_generator.py` via `_apply_performance_humanization()` (Sprint 7.5)

**Implementation**: `multimodal_gen/microtiming.py` (17 exports) + `multimodal_gen/groove_templates.py` (35 exports). Tests: `tests/test_microtiming.py` (30 tests).

---

## ✅ HIGH PRIORITY (Sprint 2) — ALL COMPLETE

### TASK-004: Phrase-Level Dynamics System
**Estimated Effort:** 4-5 hours
**File:** `multimodal_gen/expression.py` (new)

**Implementation:**
```python
def detect_phrase_boundaries(
    track: List[MidiEvent],
    method: str = "auto"  # "auto", "bars", "rests"
) -> List[Tuple[float, float]]:
    """Return list of (start_beat, end_beat) for each phrase."""

def apply_phrase_dynamics(
    track: List[MidiEvent],
    style: str = "natural",  # "natural", "dramatic", "subtle", "punchy"
    phrase_length_bars: int = 4
) -> List[MidiEvent]:
    """
    Apply velocity arcs within phrases.
    
    Styles:
    - natural: Crescendo to midpoint, decrescendo to end
    - dramatic: Build throughout, sudden drop at end
    - subtle: Gentle 10-15% variation
    - punchy: Strong accents on downbeats, soft between
    """

def add_expression_ccs(
    track: List[MidiEvent],
    cc_types: List[int] = [11, 1]  # Expression, Modulation
) -> List[MidiEvent]:
    """Add MIDI CC curves for expressive playback."""
```

**Acceptance Criteria:**
- [x] Phrase boundary detection working
- [x] 4+ dynamics styles implemented (DynamicShape enum: CRESCENDO, DIMINUENDO, SWELL, ACCENT, ARC, TERRACED)
- [x] CC11 (expression) curves generated via `generate_phrase_cc_events()` + CC_INTENSITY_PRESETS (21 genres)
- [x] CC1 (modulation/vibrato) on long notes
- [x] Genre presets: 17 entries in GENRE_DYNAMICS (trap=punchy, lofi=subtle, orchestral=dramatic, etc.)
- [x] Wired into `_create_chord_track` and `_create_melody_track` (Sprint 6)

**Implementation**: `multimodal_gen/dynamics.py` (24 exports). Tests: `tests/test_dynamics.py` (36 tests).

---

### TASK-005: Ghost Notes & Intelligent Fills ✅
**Estimated Effort:** 4-5 hours
**File:** `multimodal_gen/drum_humanizer.py` (new)

**Implementation:**
```python
def add_ghost_notes(
    drum_track: List[MidiEvent],
    instrument: str,  # "snare", "hihat", "kick"
    density: float = 0.3,  # 0-1
    velocity_ratio: float = 0.35  # Ghost velocity relative to main hits
) -> List[MidiEvent]:
    """Add subtle ghost hits between main drum hits."""

def generate_fill(
    genre: str,
    duration_beats: float,
    energy: float = 0.7,  # 0-1
    instruments: List[str] = ["snare", "tom", "hihat"]
) -> List[MidiEvent]:
    """Generate context-appropriate drum fill."""

def place_fills_at_boundaries(
    drum_track: List[MidiEvent],
    section_boundaries: List[float],  # Beat positions
    genre: str,
    fill_probability: float = 0.8
) -> List[MidiEvent]:
    """Automatically add fills at section transitions."""
```

**Acceptance Criteria:**
- [x] Ghost notes at appropriate velocities (30-50% of main) — DrumHumanizer with configurable velocity_ratio
- [x] Genre-specific fill libraries (trap, boom_bap, house) — FillComplexity enum, `generate_fill()`
- [x] Fills respect energy level (calm sections get subtle fills)
- [x] Integration: `place_fills_at_boundaries()` wired into `_create_drum_track` (Sprint 7)
- [x] Ghost note instrument control via DRUM_MIDI_MAP

**Implementation**: `multimodal_gen/drum_humanizer.py` (19 exports). Tests: `tests/test_drum_humanizer.py` (37 tests).

---

### TASK-006: Motif-Aware Arranger Integration ✅
**Estimated Effort:** 4-5 hours
**File:** `multimodal_gen/arranger.py` (modify)
**Depends on:** TASK-001, TASK-002

**Implementation:**
```python
# Extend Arrangement class
class Arrangement:
    # ... existing code ...
    
    motifs: List[List[MotifNote]] = field(default_factory=list)
    motif_assignments: Dict[str, MotifAssignment] = field(default_factory=dict)

@dataclass
class MotifAssignment:
    motif_index: int
    transformation: str  # "original", "inversion", "sequence", etc.
    transform_params: dict = None

def generate_arrangement_with_motifs(
    parsed: ParsedPrompt,
    num_motifs: int = 2
) -> Arrangement:
    """
    Generate arrangement with thematic coherence.
    
    Default motif mapping:
    - intro: motif[0] fragment
    - verse: motif[0] original
    - pre_chorus: motif[0] sequence(+3)
    - chorus: motif[1] original (contrast)
    - bridge: motif[0] inversion + motif[1] diminution
    - outro: motif[0] fragment
    """
```

**Acceptance Criteria:**
- [x] 1-3 motifs generated per arrangement via MotifAssignment
- [x] Each section references motif variant (original, inversion, sequence, fragment, etc.)
- [x] Backward compatible (USE_CONFIG_DRIVEN feature flag, 100% fallback)
- [x] Arrangement has recognizable theme — verified in `test_arranger_motifs.py`
- [x] YAML-driven templates: 11 genre templates in `configs/arrangements/templates/`

**Implementation**: `multimodal_gen/arranger.py` (40 exports) + `multimodal_gen/config_loader.py`. Tests: `tests/test_arranger_motifs.py` (31 tests).

---

## ✅ MEDIUM PRIORITY (Sprint 3) — ALL COMPLETE

### TASK-007: Track Processing Chain
**Estimated Effort:** 6-8 hours
**File:** `multimodal_gen/mix_processor.py` (new)

**Implementation:**
```python
class TrackProcessor:
    """CPU-efficient audio processing chain."""
    
    def soft_saturate(self, audio: np.ndarray, drive: float = 2.0) -> np.ndarray:
        """Warm saturation using tanh waveshaping."""
    
    def parametric_eq(self, audio: np.ndarray, 
                      low_shelf_db: float = 0, low_freq: float = 100,
                      mid_db: float = 0, mid_freq: float = 1000, mid_q: float = 1,
                      high_shelf_db: float = 0, high_freq: float = 8000) -> np.ndarray:
        """3-band parametric EQ using biquad filters."""
    
    def compress(self, audio: np.ndarray,
                 threshold_db: float = -12, ratio: float = 4,
                 attack_ms: float = 10, release_ms: float = 100,
                 makeup_db: float = 0) -> np.ndarray:
        """Dynamic range compression with envelope follower."""
    
    def transient_shape(self, audio: np.ndarray,
                        attack: float = 0, sustain: float = 0) -> np.ndarray:
        """Transient shaper for punch control (-100 to +100)."""

# Genre presets
TRACK_PRESETS = {
    "trap_808": {"saturate": 3.0, "eq": {"low_shelf_db": 3}, "compress": {"threshold": -12, "ratio": 4}},
    "trap_hihat": {"eq": {"high_shelf_db": 2}, "compress": {"threshold": -18, "ratio": 2}},
    "lofi_keys": {"saturate": 1.5, "eq": {"high_shelf_db": -4}, "compress": {"ratio": 2}},
    "boom_bap_drums": {"transient": {"attack": 30}, "compress": {"ratio": 6}},
}

def process_track(audio: np.ndarray, preset: str, sample_rate: int = 44100) -> np.ndarray:
    """Apply full processing chain for track type."""
```

**Acceptance Criteria:**
- [x] All processors real-time capable on CPU — CompressorConfig, EQBand, saturation
- [x] No clipping (proper gain staging) — CLIPPING_THRESHOLD guard
- [x] 8+ track presets: punchy_kick, boom_bap_drums, trap_808, boom_bap_bass, clean_bass, warm_pad, bright_synth, lofi_keys
- [x] Genre-gated to target genres only (classical/jazz/ambient skip processing)
- [x] Wired per-stem in `audio_renderer._render_procedural` (Sprint 8)

**Implementation**: `multimodal_gen/track_processor.py` (16 exports). Tests: `tests/test_mix_engine.py` (54 tests, shared).

---

### TASK-008: Bus Processing & Mix Glue ✅
**Estimated Effort:** 4-5 hours
**File:** `multimodal_gen/mix_processor.py` (extend)
**Depends on:** TASK-007

**Implementation:**
```python
class MixBus:
    """Audio bus with insert processing and send/return."""
    
    def __init__(self, name: str):
        self.inserts: List[Processor] = []
        self.sends: Dict[str, float] = {}  # bus_name -> send_level
    
    def process(self, audio: np.ndarray) -> np.ndarray:
        """Process through insert chain."""

class MixEngine:
    """Full mixing engine with buses."""
    
    buses = {
        "drums": MixBus("drums"),
        "melodic": MixBus("melodic"),
        "master": MixBus("master"),
        "reverb": MixBus("reverb"),  # Return bus
    }
    
    def apply_sidechain(self, 
                        source: np.ndarray, 
                        trigger: np.ndarray,
                        threshold: float = -20,
                        ratio: float = 4,
                        attack_ms: float = 5,
                        release_ms: float = 100) -> np.ndarray:
        """Sidechain compression (kick ducking bass/pads)."""
    
    def mix_stems(self, stems: Dict[str, np.ndarray]) -> np.ndarray:
        """Full mix with bus routing and processing."""
```

**Acceptance Criteria:**
- [x] Bus routing working (tracks → bus → master) — BusConfig with drum/melodic/master buses
- [x] Sidechain compression: `apply_sidechain_ducking()` wired for trap/drill/house/edm/hip_hop/phonk (Sprint 8)
- [x] Reverb send creates cohesive space — genre-specific reverb presets (GENRE_REVERB_CONFIGS)
- [x] Master limiter prevents overs — true_peak_limiter.py (-1 dBTP, ITU-R BS.1770-4)
- [x] -14 LUFS target via auto_gain_staging.py K-weighting filter

**Implementation**: `multimodal_gen/mix_engine.py` (18 exports) — GENRE_SIDECHAINS, MIX_PRESETS. Tests: `tests/test_mix_engine.py` (54 tests).

---

### TASK-009: Convolution Reverb ✅
**Estimated Effort:** 3-4 hours
**File:** `multimodal_gen/reverb.py` (new)

**Implementation:**
```python
def generate_ir(
    type: str,  # "room", "plate", "hall", "spring", "lofi"
    decay_seconds: float = 1.5,
    damping: float = 0.5,  # High frequency absorption
    sample_rate: int = 44100
) -> np.ndarray:
    """Generate procedural impulse response."""

def convolve_reverb(
    audio: np.ndarray,
    ir: np.ndarray,
    wet_dry: float = 0.3,
    pre_delay_ms: float = 20
) -> np.ndarray:
    """FFT-based convolution reverb."""

# Pre-generated IRs for common spaces
REVERB_PRESETS = {
    "tight_room": generate_ir("room", decay=0.3),
    "plate": generate_ir("plate", decay=1.5),
    "hall": generate_ir("hall", decay=2.5),
    "lofi_room": generate_ir("lofi", decay=0.8),
}
```

**Acceptance Criteria:**
- [x] FFT convolution efficient — ConvolutionReverb with scipy.signal.fftconvolve
- [x] 5+ IR presets in IR_PRESETS (tight_room, plate, hall, lofi_room, spring, etc.)
- [x] Pre/post EQ on reverb signal — IRConfig with damping/brightness control
- [x] Wet/dry control — `wet_dry` parameter in convolve method
- [x] Genre-specific reverb configs: GENRE_REVERB_CONFIGS with decay/preset mapping
- [x] Wired into `audio_renderer._render_procedural` as send effect (Sprint 7)

**Implementation**: `multimodal_gen/reverb.py` (14 exports). Tests: `tests/test_reverb.py` (37 tests).

---

## ✅ LOWER PRIORITY (Sprint 4+) — ALL COMPLETE

### TASK-010: Chord Progression Extraction ✅
**File:** `multimodal_gen/chord_extractor.py`
**Estimated Effort:** 5-6 hours

Extract chord progressions from reference audio using chromagram analysis.

- [x] CHORD_TEMPLATES (major, minor, dim, aug, 7th, etc.), COMMON_PROGRESSIONS
- [x] ChordExtractor, ChordEvent, ChordProgression dataclasses
- [x] Wired into `reference_analyzer.py` `analyze_url`/`analyze_file` (Sprint 7)
- [x] Tests: `tests/test_chord_extractor.py` (40 tests)

---

### TASK-011: Tension/Release Arc System ✅
**File:** `multimodal_gen/tension_arc.py`
**Estimated Effort:** 4-5 hours
**Depends on:** TASK-006

Arrangement-level tension curves affecting dynamics, density, harmonic complexity.

- [x] GENRE_TENSION_PROFILES, ArcShape enum, 19 exports
- [x] `Arrangement.get_tension_curve()` added (Sprint 6)
- [x] Edge cases guarded: negative tension values clamped
- [x] Tests: `tests/test_critics_module.py` (12 tests), `tests/test_harmonic_brain.py` (8 tests)

---

### TASK-012: Section Variation Engine ✅
**File:** `multimodal_gen/section_variation.py`
**Estimated Effort:** 4-5 hours
**Depends on:** TASK-002

Repeated sections (verse 1 vs verse 2) have meaningful variations.

- [x] GENRE_VARIATION_PROFILES, SectionVariationEngine, 18 exports
- [x] Occurrence tracking per section type with progressive variation
- [x] Wired into arranger with disable-compare verification (Sprint 6)
- [x] Tests: `tests/test_section_variation.py` (50 tests)

---

### TASK-013: Pattern Library Expansion ✅
**File:** `multimodal_gen/pattern_library.py`
**Estimated Effort:** 6-8 hours

Structured pattern libraries for 8+ genres with 20+ patterns each.

- [x] DrumPattern, BassPattern, ChordPattern dataclasses, DRUM_MAP
- [x] PatternLibrary wired into `_create_drum_track` with per-section tick offset (Sprint 7)
- [x] Notes offset by `section.start_tick` — not piled at tick 0
- [x] Tests: `tests/test_pattern_library.py` (37 tests)

---

### TASK-014: Preset System ✅
**File:** `multimodal_gen/preset_system.py`
**Estimated Effort:** 3-4 hours

Curated presets combining all features for instant professional results.

- [x] GENRE_PRESETS, PresetSystem, 20 exports
- [x] `set_preset_values()` wired into AudioRenderer (Sprint 8)
- [x] `_get_preset_target_rms()`, `_get_preset_reverb_send()` extracted as testable helpers
- [x] Tests: `tests/test_preset_system.py` (46 tests)

---

### TASK-015: Quality Validation Suite ✅
**File:** `multimodal_gen/quality_validator.py`
**Estimated Effort:** 4-5 hours

Automated tests for musical quality metrics.

- [x] CriticReport, CriticResult, GENRE_QUALITY_PROFILES, 28 exports
- [x] VLC/BKAS/ADC critics post-generation gate in `main.py` (Sprint 5)
- [x] Proper note_on/note_off pairing with 480-tick fallback for unclosed notes
- [x] Tests: `tests/test_quality_validator.py` (61 tests)

---

## Task Summary

| ID | Task | Priority | Status | Module | Tests |
|----|------|----------|--------|--------|-------|
| 001 | Motif Generation | 🔴 Critical | ✅ COMPLETE | `motif_engine.py` | 52 |
| 002 | Motif Transformations | 🔴 Critical | ✅ COMPLETE | `motif_engine.py` | 17 |
| 003 | Microtiming Engine | 🔴 Critical | ✅ COMPLETE | `microtiming.py` + `groove_templates.py` | 30 |
| 004 | Phrase Dynamics | 🟡 High | ✅ COMPLETE | `dynamics.py` | 36 |
| 005 | Ghost Notes & Fills | 🟡 High | ✅ COMPLETE | `drum_humanizer.py` | 37 |
| 006 | Arranger Integration | 🟡 High | ✅ COMPLETE | `arranger.py` + `config_loader.py` | 31 |
| 007 | Track Processing | 🟢 Medium | ✅ COMPLETE | `track_processor.py` | 54* |
| 008 | Bus Processing | 🟢 Medium | ✅ COMPLETE | `mix_engine.py` | 54* |
| 009 | Convolution Reverb | 🟢 Medium | ✅ COMPLETE | `reverb.py` | 37 |
| 010 | Chord Extraction | 🔵 Lower | ✅ COMPLETE | `chord_extractor.py` | 40 |
| 011 | Tension/Release | 🔵 Lower | ✅ COMPLETE | `tension_arc.py` | 20 |
| 012 | Section Variation | 🔵 Lower | ✅ COMPLETE | `section_variation.py` | 50 |
| 013 | Pattern Library | 🔵 Lower | ✅ COMPLETE | `pattern_library.py` | 37 |
| 014 | Presets | 🔵 Lower | ✅ COMPLETE | `preset_system.py` | 46 |
| 015 | Validation Suite | 🔵 Lower | ✅ COMPLETE | `quality_validator.py` | 61 |

\* Shared test file `test_mix_engine.py`

**Total Tests Covering These Tasks:** ~562 dedicated tests  
**Total Estimated Effort:** 65-80 hours → **DELIVERED across Sprints 5-11 + Waves 1-3**

---

## Implementation History

```
Sprint 5:  TASK-001 (motifs) + TASK-011 (tension) + TASK-015 (quality gate)
Sprint 6:  TASK-002 (transforms) + TASK-004 (dynamics) + TASK-012 (variation)
Sprint 7:  TASK-005 (ghost notes) + TASK-009 (reverb) + TASK-010 (chords) + TASK-013 (patterns)
Sprint 7.5: TASK-003 (microtiming) pipeline wiring
Sprint 8:  TASK-007 (track processor) + TASK-008 (bus processing) + TASK-014 (presets)
Wave 1-3:  Final integration, reconciliation, ROADMAP gap closure
```

---

*Each task was completed as a targeted sprint batch and verified via multi-model cross-validation (Gemini auditor + GPT stress-tester + diagnostician).*
