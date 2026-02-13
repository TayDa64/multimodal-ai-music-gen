# MUSE AI Masterclass Production Guide

## Overview

MUSE AI is a multimodal AI music generation system that produces professional-quality beats, arrangements, and mixes from natural-language prompts. It combines motif-based composition, genre-aware strategies, reference analysis, and a full audio processing pipeline into one cohesive workflow.

The system lives in `multimodal_gen/` and is driven by `main.py`. A prompt like *"dark trap beat in C minor at 140 BPM"* flows through parsing, motif generation, MIDI arrangement, audio rendering, and quality validation — outputting a production-ready WAV and MIDI file.

---

## Quick Start

```python
from main import generate

# Simplest invocation — genre and mood inferred from prompt
result = generate("chill lofi beat with jazzy chords")

# With explicit parameters
result = generate(
    "aggressive trap beat in D minor at 145 BPM",
    output_dir="output/my_beat",
)

# The result dict contains paths to MIDI and WAV files
print(result["midi_path"])
print(result["wav_path"])
```

---

## Feature Guide

### 1. Motif System

**Module:** `multimodal_gen/motif_engine.py`

The motif engine generates interval-based musical phrases that can be transposed to any key.

#### Key Classes

- **`Motif`** — Interval + rhythm pattern with accent weights and genre tags.
- **`MotifLibrary`** — Collection of motifs filterable by genre and chord context.
- **`MotifGenerator`** — Generates motifs via `generate_motif(key, scale, genre, num_notes, ...)`.

#### Transformations

Each `Motif` instance supports:

| Method | Description |
|--------|-------------|
| `transpose(semitones)` | Shift all intervals |
| `invert()` | Mirror intervals around root |
| `retrograde()` | Reverse note order |
| `retrograde_inversion()` | Reverse + mirror |
| `fragment(start, length)` | Extract a sub-phrase |
| `ornament(density)` | Add passing tones / neighbor notes |
| `displace(offset_beats)` | Shift rhythmic position |
| `get_related_motifs()` | Return a set of derived motifs |

#### How Motifs Flow Through Arrangements

1. `MotifGenerator.generate_motif()` creates a seed motif for the track's genre/key.
2. The arranger maps motifs to sections via `configs/arrangements/motif_mappings.yaml`.
3. `SectionVariationEngine` applies transformations (inversion, density change, etc.) on repeated sections.

---

### 2. Groove & Expression

#### Microtiming Profiles

**Module:** `multimodal_gen/microtiming.py`

6 built-in genre presets in `GENRE_PRESETS`:

| Preset | Swing | Push/Pull | Style |
|--------|-------|-----------|-------|
| jazz | 0.60 | 0.00 | Swing |
| hip-hop | 0.30 | −0.10 | Laid back |
| funk | 0.20 | +0.05 | Pushed |
| r&b | 0.25 | −0.15 | Laid back |
| rock | 0.00 | 0.00 | Straight |
| blues | 0.50 | 0.00 | Shuffle |

Usage:
```python
from multimodal_gen.microtiming import apply_microtiming
grooved = apply_microtiming(notes, genre="jazz")
```

#### Ghost Notes & Fills

**Module:** `multimodal_gen/drum_humanizer.py`

`DrumHumanizer` adds ghost notes (low-velocity hits) and fill patterns to drum tracks, wired into `MidiGenerator._create_drum_track()`.

#### Phrase-Level Dynamics

**Module:** `multimodal_gen/dynamics.py`

`DynamicsEngine` shapes velocity across phrases using 8 curve types:

| Shape | Description |
|-------|-------------|
| `FLAT` | No change |
| `CRESCENDO` | Gradual increase |
| `DECRESCENDO` | Gradual decrease |
| `SWELL` | Rise to middle, fall |
| `FADE_IN` | Quick ramp at start |
| `FADE_OUT` | Quick decay at end |
| `ACCENT_FIRST` | Strong first beat |
| `ACCENT_LAST` | Build to final note |

17 genre presets available in `GENRE_DYNAMICS` (jazz, hip-hop, classical, rock, r&b, funk, trap, lofi, ethiopian, ethio_jazz, house, trap_soul, boom_bap, drill, ambient, lo-fi, lo_fi).

**MIDI CC Generation** (Wave 3): `generate_phrase_cc_events(notes, boundaries, genre)` produces CC11 (Expression), CC1 (Modulation/Vibrato), and CC74 (Brightness) events aligned to phrase boundaries. Genre-specific intensity in `CC_INTENSITY_PRESETS`.

#### Per-Instrument Groove Offsets

Groove templates in `multimodal_gen/groove_templates.py` provide per-instrument timing and velocity offsets:

```python
from multimodal_gen.groove_templates import get_preset_groove, GrooveApplicator
template = get_preset_groove("boom_bap")
applicator = GrooveApplicator()
grooved = applicator.apply(notes, template)
```

---

### 3. Genre Strategies

**Module:** `multimodal_gen/strategies/`

The system uses a Strategy Pattern: each genre has a dedicated `GenreStrategy` subclass registered in `StrategyRegistry`.

#### Available Strategies (12)

| Strategy | File |
|----------|------|
| `TrapStrategy` | `trap_strategy.py` |
| `LofiStrategy` | `lofi_strategy.py` |
| `HouseStrategy` | `house_strategy.py` |
| `RnBStrategy` | `rnb_strategy.py` |
| `EthiopianStrategy` | `ethiopian_strategy.py` |
| `EthioJazzStrategy` | `ethiopian_strategy.py` |
| `DrillStrategy` | `drill_strategy.py` |
| `BoomBapStrategy` | `boom_bap_strategy.py` |
| `TrapSoulStrategy` | `trap_soul_strategy.py` |
| `GFunkStrategy` | `gfunk_strategy.py` |
| `DefaultStrategy` | `default_strategy.py` |

Each strategy implements `generate_drums()`, `generate_bass()`, and `generate_chords()` with genre-specific patterns, voicings, and rhythmic conventions.

#### Pattern Libraries

**Module:** `multimodal_gen/pattern_library.py`

Pre-built drum patterns for each genre, wired into `MidiGenerator._create_drum_track()` with per-section offset handling.

---

### 4. Reference Analysis

**Module:** `multimodal_gen/reference_analyzer.py`

`ReferenceAnalyzer` extracts musical features from audio files or YouTube URLs.

#### Chord Extraction

**Module:** `multimodal_gen/chord_extractor.py`

`ChordExtractor.analyze(audio)` returns a `ChordProgression` with chord names, timing, and confidence. Integrated into `ReferenceAnalyzer.analyze_url()` and `analyze_file()`.

#### Melodic Contour Extraction

`ReferenceAnalyzer._extract_melody_contour()` uses pYIN F0 estimation to produce a list of `{direction, interval_semitones, duration_beats}` dicts describing the melodic shape.

#### Drum Pattern Transcription

`extract_drum_pattern(audio_path, quantize_grid=16)` — standalone convenience function that loads audio, runs onset detection across frequency bands, quantizes to a grid, and returns a reusable template dict with `kick`, `snare`, `hihat`, `swing`, `density`, `tempo`, and `time_signature`.

#### Reference Track Matching

**Module:** `multimodal_gen/reference_matching.py`

`ReferenceMatcher` compares a generated mix's spectral profile against a reference track and suggests EQ/dynamics adjustments.

---

### 5. Audio Processing

**Module:** `multimodal_gen/audio_renderer.py`, `multimodal_gen/mix_engine.py`

#### Per-Track Processing Chains

**Module:** `multimodal_gen/track_processor.py`, `multimodal_gen/mix_chain.py`

`TrackProcessor` applies genre-gated channel-strip processing per stem (EQ, compression, saturation). Active for 11 production genres; bypassed for classical/jazz/ambient.

#### Bus Processing & Sidechain

**Module:** `multimodal_gen/mix_engine.py`

- Sidechain ducking for bass tracks in trap/drill/house/EDM/hip-hop/phonk genres.
- Drum bus, bass bus, and master bus processing chains.

#### Convolution Reverb

**Module:** `multimodal_gen/reverb.py`

`ConvolutionReverb` with 5 IR types:

| IR Type | Character |
|---------|-----------|
| `room` | Small room ambience |
| `hall` | Concert hall |
| `plate` | Classic plate reverb |
| `spring` | Guitar-amp spring |
| `lofi` | Degraded, vintage |

Wired as a send effect in `audio_renderer._render_procedural()`.

#### True Peak Limiting

**Module:** `multimodal_gen/true_peak_limiter.py`

ISP (inter-sample peak) detection with oversampling, lookahead, and release. Integrated into the master bus.

#### Multiband Dynamics

**Module:** `multimodal_gen/multiband_dynamics.py`

3-band (low/mid/high) compressor with genre-specific presets, wired after reverb in the rendering pipeline.

#### Additional DSP

- **Parametric EQ / Dynamic EQ** — `multimodal_gen/parametric_eq.py` (RBJ biquad cookbook, per-band envelope follower)
- **Transient Shaper** — `multimodal_gen/transient_shaper.py` (attack/sustain control)
- **Auto-Gain Staging** — `multimodal_gen/auto_gain_staging.py` (intelligent level normalization)
- **Harmonic Exciter** — Chebyshev polynomial saturation in `parametric_eq.py`
- **Stereo Utils / M-S Processing** — `multimodal_gen/stereo_utils.py`

---

### 6. Arrangement Intelligence

#### Tension/Release Arcs

**Module:** `multimodal_gen/tension_arc.py`

`TensionArc` with 10 shapes in `ArcShape`:

| Shape | Description |
|-------|-------------|
| `FLAT` | No tension variation |
| `LINEAR_BUILD` | Steady increase |
| `LINEAR_DECAY` | Steady decrease |
| `PEAK_MIDDLE` | Build to middle, release |
| `PEAK_END` | Build throughout to climax |
| `DOUBLE_PEAK` | Two climaxes |
| `WAVE` | Oscillating tension |
| `STEP_UP` | Stepwise increases |
| `STEP_DOWN` | Stepwise decreases |
| `DRAMATIC` | Low–high–low with sharp transitions |

Tension curves modulate dynamics, density, harmonic complexity, register, and articulation via `TensionConfig` influence weights.

#### Section Variation Engine

**Module:** `multimodal_gen/section_variation.py`

`SectionVariationEngine` applies 11 variation types on repeated sections:

`NONE`, `OCTAVE_SHIFT`, `DENSITY_CHANGE`, `RHYTHM_VARIATION`, `FILL_ADDITION`, `INSTRUMENT_SWAP`, `HARMONY_ENRICHMENT`, `DYNAMICS_SHIFT`, `REGISTER_SHIFT`, `ARTICULATION_CHANGE`, `MOTIF_TRANSFORM`

Wired with occurrence tracking — first occurrence is unvaried; subsequent occurrences accumulate variations.

#### Transition Generator

**Module:** `multimodal_gen/transitions.py`

`TransitionGenerator` with 6 transition types:

| Type | Description |
|------|-------------|
| `FILL` | Drum fill at section end |
| `BREAKDOWN` | Strip to sparse elements |
| `BUILD` | Energy ramp (snare roll, increasing density) |
| `CUT` | Hard stop / silence |
| `CRASH` | Crash cymbal + brief silence |
| `CROSSFADE` | Overlapping volume crossfade |

Genre-specific transition style maps in `GENRE_TRANSITION_STYLES`.

#### Config-Driven Arrangement Templates

**Module:** `multimodal_gen/config_loader.py`, `multimodal_gen/arranger.py`

YAML templates in `configs/arrangements/templates/` define section order, lengths, instrument assignments, and motif mappings per genre. `ConfigLoader` supports caching and hot-reload. Enabled via `USE_CONFIG_DRIVEN` feature flag with 100% backward-compatible fallback.

Available templates: `trap.yaml`, `lofi.yaml`, `boom_bap.yaml`, `house.yaml`, `ambient.yaml`, `trap_soul.yaml`, `rnb.yaml`, `ethiopian.yaml`, `ethio_jazz.yaml`, `ethiopian_traditional.yaml`, `eskista.yaml`.

---

### 7. Preset System

**Module:** `multimodal_gen/preset_loader.py`, `multimodal_gen/preset_system.py`

#### Curated Presets (10 YAML files)

Located in `configs/presets/`:

| Preset | Genre |
|--------|-------|
| `trap_atlanta.yaml` | Trap |
| `lofi_chill.yaml` | Lo-fi |
| `boom_bap_classic.yaml` | Boom Bap |
| `house_deep.yaml` | House |
| `jazz_swing.yaml` | Jazz |
| `drill_uk.yaml` | Drill |
| `ethio_jazz.yaml` | Ethio-Jazz |
| `trap_soul.yaml` | Trap Soul |
| `rnb_neosoul.yaml` | R&B / Neo Soul |
| `ambient_ethereal.yaml` | Ambient |

#### YAML Preset Format

```yaml
name: "My Preset"
genre: trap
bpm: 140
key: C
scale: minor
mix:
  brightness_target: 0.6
  warmth_target: 0.4
  sub_bass_target: 0.7
  saturation_type: tape
  saturation_amount: 0.3
```

#### Creating Custom Presets

1. Copy an existing preset from `configs/presets/`.
2. Adjust fields (BPM, key, mix parameters).
3. Save as `configs/presets/my_preset.yaml`.
4. Reference in generation: `generate("beat", preset="my_preset")`.

---

### 8. Quality Validation

**Module:** `multimodal_gen/quality_validator.py`

`QualityValidator.validate(notes, genre, key, scale, tempo, ...)` runs automated quality checks:

- **Voice Leading Critic (VLC)** — Checks parallel motion, voice crossing, large leaps.
- **Beat/Key Adherence Score (BKAS)** — Validates scale adherence and rhythmic grid alignment.
- **Arrangement Density Critic (ADC)** — Evaluates density variation, tension arc presence.

Returns a `QualityLevel` enum (`EXCELLENT`, `GOOD`, `ACCEPTABLE`, `POOR`) with per-metric scores. Wired as a post-generation gate in `main.py`.

---

## Architecture

### Module Dependency Graph (simplified)

```
main.py
├── prompt_parser.py          (NLP → ParsedPrompt)
├── midi_generator.py         (MIDI track creation)
│   ├── strategies/           (genre-specific generation)
│   ├── motif_engine.py       (motif generation + transforms)
│   ├── dynamics.py           (velocity shaping + CC events)
│   ├── microtiming.py        (swing, push/pull)
│   ├── groove_templates.py   (groove extraction + application)
│   ├── pattern_library.py    (pre-built drum patterns)
│   ├── drum_humanizer.py     (ghost notes, fills)
│   ├── transitions.py        (section transitions)
│   └── section_variation.py  (variation on repeats)
├── arranger.py               (arrangement structure)
│   ├── tension_arc.py        (emotional arc)
│   └── config_loader.py      (YAML template loading)
├── audio_renderer.py         (WAV rendering)
│   ├── mix_engine.py         (bus processing)
│   ├── mix_chain.py          (effect chains)
│   ├── track_processor.py    (per-stem processing)
│   ├── reverb.py             (convolution reverb)
│   ├── multiband_dynamics.py (3-band compressor)
│   ├── parametric_eq.py      (EQ + exciter)
│   ├── true_peak_limiter.py  (ISP limiter)
│   ├── transient_shaper.py   (attack/sustain)
│   └── auto_gain_staging.py  (level normalization)
├── quality_validator.py      (post-gen gate)
├── reference_analyzer.py     (audio feature extraction)
│   ├── chord_extractor.py    (chord detection)
│   └── reference_matching.py (spectral matching)
└── preset_loader.py          (YAML presets)
```

### Guard Import Pattern

All optional dependencies use a lazy-load guard:

```python
_HAS_LIBROSA = False
try:
    import librosa
    _HAS_LIBROSA = True
except ImportError:
    pass
```

This ensures the system runs in environments where heavy dependencies (librosa, numpy, scipy) may not be installed, gracefully degrading features.

### Strategy Pattern for Genres

Each genre registers a `GenreStrategy` subclass via `StrategyRegistry`:

```python
from multimodal_gen.strategies.registry import StrategyRegistry

registry = StrategyRegistry()
strategy = registry.get_strategy("trap")
drums = strategy.generate_drums(config)
```

---

## API Reference

### Core Generation

```python
# main.py
generate(prompt: str, output_dir: str = "output", preset: str = None) -> dict
```

### Motif Engine

```python
# multimodal_gen/motif_engine.py
MotifGenerator.generate_motif(key: str, scale: str, genre: str, num_notes: int, ...) -> Motif
Motif.transpose(semitones: int) -> Motif
Motif.invert() -> Motif
Motif.retrograde() -> Motif
Motif.retrograde_inversion() -> Motif
Motif.fragment(start: int, length: int) -> Motif
Motif.ornament(density: float) -> Motif
```

### Dynamics

```python
# multimodal_gen/dynamics.py
DynamicsEngine.apply(notes, config, auto_detect_phrases=False) -> list
apply_dynamics(notes, genre="jazz", config=None) -> list
detect_phrase_boundaries(notes, ticks_per_beat=480) -> list
generate_phrase_cc_events(notes, boundaries, genre="default", ticks_per_beat=480) -> list
```

### Reference Analysis

```python
# multimodal_gen/reference_analyzer.py
ReferenceAnalyzer.analyze_file(file_path: str) -> ReferenceAnalysis
ReferenceAnalyzer.analyze_url(url: str) -> ReferenceAnalysis
analyze_reference(url: str, verbose=False) -> ReferenceAnalysis
extract_drum_pattern(audio_path: str, quantize_grid: int = 16) -> dict
```

### Quality Validation

```python
# multimodal_gen/quality_validator.py
QualityValidator.validate(notes, genre, key, scale, tempo, ...) -> QualityResult
```

### Arrangement

```python
# multimodal_gen/tension_arc.py
TensionArc.get_tension_at(position: float) -> float

# multimodal_gen/section_variation.py
SectionVariationEngine.apply_variation(notes, variation_type, ...) -> list

# multimodal_gen/transitions.py
TransitionGenerator.generate(from_section, to_section, ...) -> list
```

### Audio Processing

```python
# multimodal_gen/reverb.py
ConvolutionReverb.process(audio, config) -> ndarray

# multimodal_gen/true_peak_limiter.py
TruePeakLimiter.process(audio, ...) -> ndarray

# multimodal_gen/multiband_dynamics.py
multiband_compress(audio, preset, sr) -> ndarray
```
