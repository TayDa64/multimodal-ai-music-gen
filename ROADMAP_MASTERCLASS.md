# Masterclass Musicality Roadmap

## Executive Summary

Transform the AI Music Generator from a capable beat-making tool into an **industry-standard music production system** that produces emotionally compelling, professionally mixed, narratively coherent compositions—all while maintaining **offline/CPU-only operation** and **MPC compatibility**.

---

## Phase 1: Musical Rule Expansion & Motif System (Weeks 0-4)

### Task 1.1: Create Motif Generation Module
**Priority:** Critical (Foundation for all melodic improvements)
**File:** `multimodal_gen/motifs.py` (new)

**Description:**
Create a new module for generating and transforming musical motifs—short melodic/rhythmic ideas that can be developed throughout a composition.

**Requirements:**
- Generate base motifs constrained to scale/key with configurable:
  - Note density (notes per bar)
  - Rhythmic complexity (simple quarters vs. syncopated 16ths)
  - Melodic contour (ascending, descending, arch, wave)
  - Range (octave span)
- Support existing Ethiopian scales (tizita, ambassel, anchihoye, bati)
- Seed-based reproducibility

**Acceptance Criteria:**
- [ ] `generate_base_motif(key, scale, bars, complexity)` returns list of note events
- [ ] Motifs are musically coherent (stepwise motion dominant, leaps resolved)
- [ ] Unit tests verify scale constraint and reproducibility
- [ ] Integration with existing `midi_generator.py`

---

### Task 1.2: Implement Motif Transformations
**Priority:** Critical
**File:** `multimodal_gen/motifs.py`

**Description:**
Implement classical compositional transformation techniques for motif development.

**Transformations to implement:**
```python
- inversion: Mirror pitches around axis note
- retrograde: Reverse note order
- retrograde_inversion: Both combined
- augmentation: Double durations
- diminution: Halve durations
- sequence: Transpose by interval (e.g., up a 3rd)
- fragmentation: Extract subset of motif
- ornamentation: Add passing tones, neighbor notes, turns
- rhythmic_displacement: Shift start by subdivision
```

**Acceptance Criteria:**
- [ ] Each transformation produces valid MIDI-compatible output
- [ ] Transformations are chainable: `transform(transform(motif, "inversion"), "augmentation")`
- [ ] `get_related_motifs(base, count=4)` returns varied but thematically connected motifs
- [ ] Visual test: Generated motifs sound related when played sequentially

---

### Task 1.3: Expand Genre Pattern Libraries
**Priority:** High
**File:** `multimodal_gen/genre_patterns/` (new directory)

**Description:**
Create structured JSON/Python pattern libraries for multiple genres with annotated musical metadata.

**Genres to expand:**
- Trap (hi-hat rolls, 808 patterns, melodic trap piano voicings)
- Lo-Fi Hip Hop (jazzy chords, vinyl texture triggers, lazy drums)
- G-Funk (whine synth patterns, P-funk chord progressions)
- Boom Bap (classic break patterns, sample chop rhythms)
- House (4-on-floor variations, offbeat hi-hats, chord stabs)
- Ethiopian (eskista rhythms, masenqo bowing patterns, washint ornaments)
- Drill (UK vs Chicago patterns, sliding 808s)
- R&B (neo-soul progressions, gospel chord borrowings)

**Pattern metadata:**
```python
{
    "name": "trap_hihat_roll_triplet",
    "genre": "trap",
    "instrument": "hihat",
    "time_signature": "4/4",
    "duration_bars": 1,
    "notes": [...],
    "tags": ["build", "tension", "fill"],
    "energy_level": 0.8,
    "complexity": 0.7
}
```

**Acceptance Criteria:**
- [ ] Minimum 20 patterns per genre
- [ ] Patterns tagged with energy level, complexity, use context (intro/verse/drop/fill)
- [ ] `PatternLibrary.get_patterns(genre, instrument, energy_range, tags)` query interface
- [ ] Patterns validated against existing genre rules

---

### Task 1.4: Motif-Aware Arranger Integration
**Priority:** High
**File:** `multimodal_gen/arranger.py` (modify)

**Description:**
Modify the arranger to use motif system for thematic coherence across sections.

**Requirements:**
- Generate 1-3 core motifs at arrangement start
- Assign motif variants to sections:
  - Intro: Fragment of main motif
  - Verse: Main motif, simple form
  - Pre-chorus: Motif sequence (transposed)
  - Chorus: Motif inversion or augmentation (contrast)
  - Bridge: Diminution or retrograde (development)
  - Outro: Return to original or fragmented fade
- Track motif usage to ensure development arc

**Acceptance Criteria:**
- [ ] `Arrangement.motifs` property holds generated motifs
- [ ] Each section references which motif variant it uses
- [ ] Listening test: Full arrangement has recognizable thematic thread
- [ ] Backward compatible: Can still generate without motif system

---

## Phase 2: Expressive Performance & Groove (Weeks 4-8)

### Task 2.1: Phrase-Level Dynamics System
**Priority:** Critical
**File:** `multimodal_gen/expression.py` (new)

**Description:**
Implement phrase-aware dynamics that make melodies "breathe" with natural crescendos/decrescendos.

**Features:**
- Phrase boundary detection (based on rests, long notes, bar lines)
- Automatic velocity arcs within phrases:
  - Default: Crescendo to phrase midpoint, decrescendo to end
  - Climax: Build throughout phrase
  - Intimate: Soft throughout with subtle swells
- MIDI CC injection:
  - CC11 (Expression): Overall phrase volume envelope
  - CC1 (Modulation): Vibrato on sustained notes
  - CC74 (Brightness): Timbral variation

**Acceptance Criteria:**
- [ ] `apply_phrase_dynamics(track, style="natural")` modifies velocities and adds CCs
- [ ] Configurable phrase length (2, 4, 8 bars)
- [ ] Genre presets: trap (punchy, minimal dynamics), lofi (soft, expressive), orchestral (dramatic arcs)
- [ ] Before/after A/B test shows clear emotional improvement

---

### Task 2.2: Advanced Microtiming Engine
**Priority:** Critical
**File:** `multimodal_gen/groove_engine.py` (new or extend `groove_templates.py`)

**Description:**
Replace simple swing with genre-specific microtiming distributions based on analyzed professional recordings.

**Microtiming profiles:**
```python
GROOVE_PROFILES = {
    "trap": {
        "8th_notes": {"offset_ms": -8, "variance": 3},    # Push 8ths
        "16th_notes": {"offset_ms": 12, "variance": 8},   # Lazy 16ths
        "hi_hat_rolls": {"humanize_ms": 5, "accent_pattern": [1, 0.6, 0.8, 0.5]}
    },
    "lofi": {
        "all": {"variance": 25},  # Heavy random timing
        "snare": {"offset_ms": 15, "variance": 10},  # Lazy backbeat
        "velocity_variance": 20
    },
    "boom_bap": {
        "kick": {"offset_ms": -5},  # Slightly ahead
        "snare": {"offset_ms": 8, "variance": 5},  # Behind the beat
        "swing_amount": 0.62  # MPC-style swing
    },
    "house": {
        "kick": {"offset_ms": 0, "variance": 1},  # Tight on grid
        "hi_hat": {"offset_ms": -3},  # Push the groove forward
        "swing_amount": 0.52
    },
    "ethiopian_eskista": {
        "all": {"variance": 18},  # Expressive timing
        "accent_pattern": [1, 0.5, 0.7, 0.5, 0.9, 0.5, 0.7, 0.5]  # 12/8 feel
    }
}
```

**Acceptance Criteria:**
- [ ] `apply_groove(events, genre, intensity=1.0)` applies timing/velocity deviations
- [ ] Intensity parameter (0-1) controls how much groove is applied
- [ ] Per-instrument groove (kick tight, hi-hat loose)
- [ ] Reproducible with seed
- [ ] Groove profiles loadable from JSON for user customization

---

### Task 2.3: Ghost Note & Fill Generator
**Priority:** Medium
**File:** `multimodal_gen/drum_humanizer.py` (new or extend existing)

**Description:**
Add intelligent ghost notes and fills that respond to arrangement context.

**Features:**
- Ghost note placement on drums (soft hits between main hits)
- Context-aware fills:
  - Pre-drop builds (snare rolls, tom fills)
  - Section transitions (crash + fill)
  - Energy-appropriate complexity
- Genre-specific fill libraries:
  - Trap: Hi-hat roll builds, 808 glides
  - Boom Bap: Classic break fills
  - House: Percussion fills, clap builds

**Acceptance Criteria:**
- [ ] `add_ghost_notes(drum_track, density=0.3)` adds subtle ghost hits
- [ ] `generate_fill(genre, duration_beats, energy)` returns fill pattern
- [ ] Fills placed automatically at section boundaries
- [ ] Ghost note velocity correctly reduced (30-50% of main hits)

---

## Phase 3: DAW-Realistic Rendering (Weeks 8-14)

### Task 3.1: Per-Track Audio Processing Chain
**Priority:** High
**File:** `multimodal_gen/mix_processor.py` (new)

**Description:**
Implement CPU-efficient audio processing that makes rendered stems sound "produced."

**Processing modules (numpy/scipy based):**
```python
class TrackProcessor:
    - soft_saturate(drive, character)  # Warmth, harmonics
    - eq_shelf(low_gain, high_gain, mid_freq, mid_q)  # Tonal balance
    - compressor(threshold, ratio, attack, release, makeup)  # Dynamics
    - transient_shaper(attack_amount, sustain_amount)  # Punch
    - stereo_width(width, frequency_dependent=True)  # Spatial
    - send_to_bus(bus_name, amount)  # Reverb/delay sends
```

**Genre-specific presets:**
```python
TRACK_PRESETS = {
    "trap_808": {"saturate": 2.5, "compress": {"threshold": -12, "ratio": 4}, "eq": {"low": +3}},
    "lofi_keys": {"saturate": 1.2, "eq": {"high": -4}, "compress": {"threshold": -18, "ratio": 2}},
    "boom_bap_drums": {"transient": {"attack": +30}, "compress": {"ratio": 6}},
}
```

**Acceptance Criteria:**
- [ ] Each processor is real-time capable on CPU
- [ ] `process_track(audio, preset_name)` applies full chain
- [ ] A/B comparison shows professional improvement
- [ ] No clipping, proper gain staging throughout chain

---

### Task 3.2: Bus Processing & Glue
**Priority:** High
**File:** `multimodal_gen/mix_processor.py`

**Description:**
Implement mix bus processing for cohesion ("glue").

**Bus types:**
- Drum bus: Parallel compression, slight saturation
- Melodic bus: Shared reverb space, gentle compression
- Master bus: Soft limiting, stereo enhancement, final EQ

**Features:**
- Send/return architecture (tracks send to buses)
- Sidechain compression (kick ducking bass/pads)
- Stereo bus reverb (shared acoustic space)

**Acceptance Criteria:**
- [ ] `MixBus` class with insert and send slots
- [ ] Sidechain compression working (audible ducking effect)
- [ ] Reverb send creates cohesive space
- [ ] Master bus limiting prevents overs

---

### Task 3.3: Convolution Reverb with Genre IRs
**Priority:** Medium
**File:** `multimodal_gen/reverb.py` (new)

**Description:**
Implement efficient convolution reverb with genre-appropriate impulse responses.

**IRs to include (or generate procedurally):**
- Small room (tight, intimate)
- Plate (classic, smooth)
- Hall (spacious, orchestral)
- Lo-fi room (degraded, character)
- Spring (vintage, twangy)

**Acceptance Criteria:**
- [ ] `convolve(audio, ir_name, wet_dry)` applies reverb
- [ ] FFT-based convolution for efficiency
- [ ] Procedural IR generation for variety
- [ ] Pre/post EQ on reverb signal

---

## Phase 4: Advanced Reference Analysis (Weeks 14-18)

### Task 4.1: Chord Progression Extraction
**Priority:** High
**File:** `multimodal_gen/reference_analyzer.py` (extend)

**Description:**
Extract chord progressions from reference audio for style emulation.

**Approach:**
- Use librosa chromagram + template matching
- Beat-aligned chord detection
- Output chord symbols with timing

**Acceptance Criteria:**
- [ ] `extract_chords(audio_path)` returns list of `{"chord": "Cm7", "start_beat": 0, "duration_beats": 4}`
- [ ] Accuracy > 70% on clear recordings
- [ ] Handles common progressions (I-V-vi-IV, ii-V-I, etc.)
- [ ] Integration with prompt parser: "use chords from reference"

---

### Task 4.2: Melodic Contour Extraction
**Priority:** Medium
**File:** `multimodal_gen/reference_analyzer.py` (extend)

**Description:**
Extract melodic contour (pitch direction over time) from reference for melody generation guidance.

**Features:**
- F0 (fundamental frequency) extraction using librosa.pyin
- Contour simplification (remove ornaments, keep shape)
- Contour representation: sequence of (direction, interval_size, duration)

**Acceptance Criteria:**
- [ ] `extract_melody_contour(audio_path)` returns contour representation
- [ ] Contour can guide motif generation direction
- [ ] Works on vocals, lead synths, and melodic instruments

---

### Task 4.3: Drum Pattern Transcription
**Priority:** Medium
**File:** `multimodal_gen/reference_analyzer.py` (extend)

**Description:**
Transcribe drum patterns from reference audio to MIDI-like representation.

**Approach:**
- Onset detection with instrument classification (kick/snare/hihat)
- Quantize to grid with timing deviations preserved
- Output pattern usable by drum generator

**Acceptance Criteria:**
- [ ] `extract_drum_pattern(audio_path)` returns pattern dict
- [ ] Distinguishes kick, snare, hi-hat minimum
- [ ] Captures timing feel (swing amount, push/pull)
- [ ] Can be used as template for new generation

---

## Phase 5: Long-Range Structure & Narrative (Weeks 18-22)

### Task 5.1: Tension/Release Arc System
**Priority:** High
**File:** `multimodal_gen/narrative.py` (new)

**Description:**
Implement arrangement-level tension/release that creates emotional journey.

**Tension parameters:**
- Harmonic tension (dissonance, chord complexity)
- Rhythmic tension (syncopation, density)
- Timbral tension (brightness, distortion)
- Dynamic tension (volume, compression)

**Arc templates:**
```python
NARRATIVE_ARCS = {
    "classic_build": [0.2, 0.3, 0.5, 0.7, 1.0, 0.8, 0.3],  # Gradual build to climax
    "verse_chorus": [0.4, 0.4, 0.8, 0.4, 0.4, 0.9, 0.3],   # Repeated verse/chorus energy
    "trap_drop": [0.3, 0.3, 0.2, 0.1, 1.0, 1.0, 0.5],      # Quiet breakdown → hard drop
    "ethiopian_call_response": [0.5, 0.7, 0.5, 0.7, 0.6, 0.8, 0.6, 0.9]  # Building dialogue
}
```

**Acceptance Criteria:**
- [ ] `apply_tension_arc(arrangement, arc_name)` modifies section parameters
- [ ] Tension values influence all musical dimensions
- [ ] Custom arcs definable
- [ ] Listening test confirms emotional journey

---

### Task 5.2: Section Variation Engine
**Priority:** High
**File:** `multimodal_gen/variation.py` (new)

**Description:**
Ensure repeated sections (verse 1 vs verse 2) have meaningful variations.

**Variation techniques:**
- Add/remove instruments (verse 2 adds strings)
- Melodic ornamentation on repeats
- Drum fill variations
- Harmonic substitutions (V → V7 → V9)
- Octave displacement
- Countermelody introduction

**Acceptance Criteria:**
- [ ] `vary_section(section, variation_level)` returns modified section
- [ ] Variation level 0-1 controls how different repeat is
- [ ] Core identity preserved (same motif, key, groove)
- [ ] Automated: "verse_2" automatically varies from "verse_1"

---

### Task 5.3: Transition Generator
**Priority:** Medium
**File:** `multimodal_gen/transitions.py` (new)

**Description:**
Generate smooth transitions between sections.

**Transition types:**
- Fill-based (drum fill leads into new section)
- Breakdown (strip to minimal elements)
- Build/riser (filtered sweep, snare roll)
- Cut (hard stop → new section)
- Crossfade (overlap sections briefly)

**Acceptance Criteria:**
- [ ] `generate_transition(from_section, to_section, style)` returns transition events
- [ ] Energy-appropriate (calm→energetic needs build)
- [ ] Genre-appropriate (trap uses risers, boom bap uses cuts)
- [ ] Integrates with arrangement automatically

---

## Phase 6: Polish & Validation (Weeks 22-24)

### Task 6.1: Preset System for Quick Starts
**Priority:** Medium
**File:** `multimodal_gen/presets.py` (new)

**Description:**
Create curated presets combining all new features for instant professional results.

**Preset structure:**
```python
{
    "name": "Zaytoven Church Keys",
    "genre": "trap_soul",
    "motif_style": "gospel_piano",
    "groove_profile": "trap",
    "dynamics_style": "dramatic",
    "mix_preset": "atlanta_trap",
    "narrative_arc": "trap_drop",
    "reference_suggestions": ["Gucci Mane - Lemonade", "Future - March Madness"]
}
```

**Acceptance Criteria:**
- [ ] 20+ curated presets across genres
- [ ] `load_preset(name)` configures all systems
- [ ] User presets savable
- [ ] Preset browser in prompts

---

### Task 6.2: Quality Validation Suite
**Priority:** High
**File:** `tests/test_musicality.py` (new)

**Description:**
Automated tests for musical quality (beyond unit tests).

**Tests:**
- Motif coherence: Transformed motifs correlate with original
- Groove accuracy: Timing distributions match genre profiles
- Dynamic range: Phrases have velocity variance
- Mix headroom: No clipping, proper LUFS
- Structure: Sections have expected variation

**Acceptance Criteria:**
- [ ] `pytest tests/test_musicality.py` runs full suite
- [ ] CI/CD integration
- [ ] Quality score output (0-100)
- [ ] Regression detection

---

### Task 6.3: Example Generations & Documentation
**Priority:** Medium
**Files:** `examples/`, `docs/MASTERCLASS_GUIDE.md`

**Description:**
Create showcase examples demonstrating all new features.

**Examples:**
- "Before/After" comparisons (same prompt, old vs new system)
- Genre showcases (trap, lofi, Ethiopian, house)
- Feature spotlights (motif development, groove comparison, mix processing)

**Acceptance Criteria:**
- [ ] 10+ example MIDI + audio pairs
- [ ] Documentation explaining each feature
- [ ] Tutorial: "Creating a masterclass beat"
- [ ] YouTube-ready demo materials

---

## Task Dependency Graph

```
Phase 1 (Foundation)
├── 1.1 Motif Generation ──────┐
├── 1.2 Motif Transformations ─┼──→ 1.4 Arranger Integration
└── 1.3 Pattern Libraries ─────┘

Phase 2 (Expression) [Can parallel with late Phase 1]
├── 2.1 Phrase Dynamics
├── 2.2 Microtiming Engine
└── 2.3 Ghost Notes & Fills

Phase 3 (Rendering) [Can parallel with Phase 2]
├── 3.1 Track Processing
├── 3.2 Bus Processing ──→ depends on 3.1
└── 3.3 Convolution Reverb

Phase 4 (Analysis) [Can parallel with Phase 3]
├── 4.1 Chord Extraction
├── 4.2 Melodic Contour
└── 4.3 Drum Transcription

Phase 5 (Structure) [Depends on Phase 1, 2]
├── 5.1 Tension/Release ──→ depends on 1.4, 2.1
├── 5.2 Section Variation ──→ depends on 1.2
└── 5.3 Transitions

Phase 6 (Polish) [Depends on all]
├── 6.1 Presets
├── 6.2 Validation
└── 6.3 Documentation
```

---

## Coding Agent Task Format

For each task delegation, use this format:

```markdown
## Task [X.Y]: [Title]

### Context
[Brief description of the system and why this task matters]

### Files to Create/Modify
- `path/to/file.py` - [what to do]

### Requirements
1. [Specific requirement]
2. [Specific requirement]

### Interface
```python
# Expected function signatures
def function_name(param: Type) -> ReturnType:
    """Docstring with usage example"""
```

### Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

### Testing
```python
# Example test case
def test_feature():
    result = function_name(input)
    assert expected_condition
```

### Dependencies
- Requires: [Task X.Y]
- Blocks: [Task X.Y]
```

---

## Priority Order for Immediate Implementation

### Sprint 1 (Highest Impact, Foundation)
1. **Task 1.1**: Motif Generation Module
2. **Task 1.2**: Motif Transformations  
3. **Task 2.2**: Advanced Microtiming Engine

### Sprint 2 (Expression & Feel)
4. **Task 2.1**: Phrase-Level Dynamics
5. **Task 2.3**: Ghost Notes & Fills
6. **Task 1.4**: Motif-Aware Arranger

### Sprint 3 (Professional Sound)
7. **Task 3.1**: Track Processing Chain
8. **Task 3.2**: Bus Processing & Glue
9. **Task 3.3**: Convolution Reverb

### Sprint 4 (Intelligence)
10. **Task 4.1**: Chord Extraction
11. **Task 5.1**: Tension/Release Arc
12. **Task 5.2**: Section Variation

---

*This roadmap transforms the AI Music Generator into a masterclass-level production tool while preserving its core strengths: offline operation, CPU efficiency, MPC compatibility, and producer-centric workflow.*
