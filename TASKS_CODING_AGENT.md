# Coding Agent Tasks - Masterclass Musicality

## Overview
Atomic, PR-ready tasks for implementing masterclass-level music generation. Each task is self-contained with clear acceptance criteria.

---

## 🔴 CRITICAL PRIORITY (Sprint 1)

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
- [ ] Generates musically coherent motifs (stepwise motion, resolved leaps)
- [ ] Supports all scales including Ethiopian (tizita, ambassel, anchihoye, bati)
- [ ] Seed-based reproducibility
- [ ] Unit tests in `tests/test_motifs.py`
- [ ] Integration example with `midi_generator.py`

---

### TASK-002: Implement Motif Transformations
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
- [ ] All 8 transformations implemented correctly
- [ ] Transformations chainable
- [ ] Output always valid MIDI range (0-127)
- [ ] Unit tests for each transformation
- [ ] Audio test: Transformed motifs sound related to original

---

### TASK-003: Advanced Microtiming Engine
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
- [ ] 6 genre profiles implemented (trap, lofi, boom_bap, house, g_funk, ethiopian)
- [ ] Per-instrument timing (kick tight, hi-hat loose)
- [ ] Intensity parameter works (0-1)
- [ ] Seed-based reproducibility
- [ ] Custom profiles loadable from JSON
- [ ] Integration with existing `humanize_midi()` function

---

## 🟡 HIGH PRIORITY (Sprint 2)

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
- [ ] Phrase boundary detection working
- [ ] 4 dynamics styles implemented
- [ ] CC11 (expression) curves generated
- [ ] CC1 (modulation/vibrato) on long notes
- [ ] Genre presets (trap=punchy, lofi=subtle, orchestral=dramatic)
- [ ] Before/after velocity comparison shows clear variation

---

### TASK-005: Ghost Notes & Intelligent Fills
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
- [ ] Ghost notes at appropriate velocities (30-50% of main)
- [ ] Genre-specific fill libraries (trap, boom_bap, house)
- [ ] Fills respect energy level (calm sections get subtle fills)
- [ ] Integration with arranger section boundaries
- [ ] No ghost notes on kick (typically)

---

### TASK-006: Motif-Aware Arranger Integration
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
- [ ] 1-3 motifs generated per arrangement
- [ ] Each section references motif variant
- [ ] Backward compatible (works without motif flag)
- [ ] Listening test: Arrangement has recognizable theme
- [ ] Motif metadata exported in MIDI file comments

---

## 🟢 MEDIUM PRIORITY (Sprint 3)

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
- [ ] All processors real-time capable on CPU
- [ ] No clipping (proper gain staging)
- [ ] 8+ track presets (different instrument types)
- [ ] A/B comparison shows improvement
- [ ] Unit tests for each processor

---

### TASK-008: Bus Processing & Mix Glue
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
- [ ] Bus routing working (tracks → bus → master)
- [ ] Sidechain compression audible
- [ ] Reverb send creates cohesive space
- [ ] Master limiter prevents overs
- [ ] -14 LUFS target for streaming

---

### TASK-009: Convolution Reverb
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
- [ ] FFT convolution efficient (< 100ms for 10s audio)
- [ ] 5 IR presets
- [ ] Pre/post EQ on reverb signal
- [ ] Wet/dry control
- [ ] Stereo width control

---

## 🔵 LOWER PRIORITY (Sprint 4+)

### TASK-010: Chord Progression Extraction
**File:** `multimodal_gen/reference_analyzer.py` (extend)
**Estimated Effort:** 5-6 hours

Extract chord progressions from reference audio using chromagram analysis.

---

### TASK-011: Tension/Release Arc System  
**File:** `multimodal_gen/narrative.py` (new)
**Estimated Effort:** 4-5 hours
**Depends on:** TASK-006

Implement arrangement-level tension curves affecting dynamics, density, harmonic complexity.

---

### TASK-012: Section Variation Engine
**File:** `multimodal_gen/variation.py` (new)  
**Estimated Effort:** 4-5 hours
**Depends on:** TASK-002

Ensure repeated sections (verse 1 vs verse 2) have meaningful variations.

---

### TASK-013: Pattern Library Expansion
**File:** `multimodal_gen/genre_patterns/` (new directory)
**Estimated Effort:** 6-8 hours

Create structured pattern libraries for 8+ genres with 20+ patterns each.

---

### TASK-014: Preset System
**File:** `multimodal_gen/presets.py` (new)
**Estimated Effort:** 3-4 hours

Curated presets combining all features for instant professional results.

---

### TASK-015: Quality Validation Suite
**File:** `tests/test_musicality.py` (new)
**Estimated Effort:** 4-5 hours

Automated tests for musical quality metrics.

---

## Task Summary

| ID | Task | Priority | Effort | Dependencies |
|----|------|----------|--------|--------------|
| 001 | Motif Generation | 🔴 Critical | 4-6h | None |
| 002 | Motif Transformations | 🔴 Critical | 3-4h | 001 |
| 003 | Microtiming Engine | 🔴 Critical | 5-6h | None |
| 004 | Phrase Dynamics | 🟡 High | 4-5h | None |
| 005 | Ghost Notes & Fills | 🟡 High | 4-5h | None |
| 006 | Arranger Integration | 🟡 High | 4-5h | 001, 002 |
| 007 | Track Processing | 🟢 Medium | 6-8h | None |
| 008 | Bus Processing | 🟢 Medium | 4-5h | 007 |
| 009 | Convolution Reverb | 🟢 Medium | 3-4h | None |
| 010 | Chord Extraction | 🔵 Lower | 5-6h | None |
| 011 | Tension/Release | 🔵 Lower | 4-5h | 006 |
| 012 | Section Variation | 🔵 Lower | 4-5h | 002 |
| 013 | Pattern Library | 🔵 Lower | 6-8h | None |
| 014 | Presets | 🔵 Lower | 3-4h | All |
| 015 | Validation Suite | 🔵 Lower | 4-5h | All |

**Total Estimated Effort:** 65-80 hours

---

## Parallelization Strategy

```
Week 1-2: [TASK-001] + [TASK-003] (parallel)
Week 2-3: [TASK-002] + [TASK-004] + [TASK-005] (parallel)
Week 3-4: [TASK-006] + [TASK-007] (parallel)
Week 4-5: [TASK-008] + [TASK-009] (parallel)
Week 5-6: [TASK-010] + [TASK-011] + [TASK-012] (parallel)
Week 6-7: [TASK-013] + [TASK-014] + [TASK-015] (parallel)
```

---

*Each task is designed to be completable in a single focused session and results in a mergeable PR.*
