# Masterclass Features Orchestration Plan

> **Generated:** January 17, 2026  
> **Status:** Research Complete → Ready for Implementation  
> **Pattern:** RLM (arxiv:2512.24601) - Probe→Decompose→Aggregate

---

## Executive Summary

This document aggregates research from 8 parallel subagents and provides a comprehensive implementation plan for professional masterclass features. Each feature has been researched for industry-standard algorithms, dataclass schemas, and integration points with the existing codebase.

---

## Codebase Architecture Overview (Critical for Builders)

### Core DSP Modules

| Module | Purpose | Key Classes/Functions |
|--------|---------|----------------------|
| `mix_chain.py` | Effect chain processing | `EffectType`, `MixChain`, `DSP`, `*Params` dataclasses |
| `mix_engine.py` | Bus routing, master processing | `MixBus`, `MixEngine`, `MasterConfig` |
| `audio_renderer.py` | MIDI→Audio rendering | `AudioRenderer`, `ProceduralRenderer` |
| `stereo_utils.py` | M/S processing (NEW) | `ms_encode`, `ms_decode`, `apply_stereo_width` |
| `reverb.py` | Convolution reverb | `ReverbProcessor`, `ReverbConfig` |
| `reference_analyzer.py` | Track analysis | `ReferenceAnalyzer`, `SpectralProfile`, `DrumAnalysis` |
| `track_processor.py` | Per-track DSP | `TrackProcessor`, `ProcessorChain` |

### JUCE Components (C++)

| Component | Purpose | Location |
|-----------|---------|----------|
| `MSProcessor` | Real-time M/S | `juce/Source/Audio/Processors/` |
| `MixerGraph` | Audio routing | `juce/Source/Audio/` |
| `ChannelStrip` | Mixer UI | `juce/Source/UI/Mixer/` |
| `ProjectState` | State persistence | `juce/Source/Project/` |

### Integration Patterns

1. **New Effect Type:**
   - Add to `EffectType` enum in `mix_chain.py`
   - Create `*Params` dataclass
   - Add to `DSP` class as static method
   - Add to `MixChain.process()` switch statement
   - Create preset function if needed

2. **New Processor (JUCE):**
   - Create `*Processor.h/cpp` in `juce/Source/Audio/Processors/`
   - Inherit from `ProcessorBase` or `juce::AudioProcessor`
   - Add to `MixerGraph.createProcessor()` factory
   - Add to `ProjectState` for persistence

---

## Feature Implementation Matrix

| # | Feature | Priority | Complexity | Dependencies | New Files | Modified Files |
|---|---------|----------|------------|--------------|-----------|----------------|
| 1 | Multiband Dynamics | HIGH | High | scipy | `multiband_dynamics.py` | `mix_chain.py`, `mix_engine.py` |
| 2 | Transient Shaping | HIGH | Medium | numpy | `transient_shaper.py` | `mix_chain.py`, `track_processor.py` |
| 3 | True Peak Limiter (ISP) | HIGH | Medium | scipy | `true_peak_limiter.py` | `mix_engine.py`, `audio_renderer.py` |
| 4 | Auto-Gain Staging | MEDIUM | Medium | pyloudnorm | `auto_gain.py` | `mix_engine.py` |
| 5 | Spectral Processing | MEDIUM | High | scipy.fft | `spectral_processor.py` | `mix_chain.py` |
| 6 | Spatial Audio | LOW | Very High | scipy, optional HRTF | `spatial_audio.py` | New subsystem |
| 7 | Reference Matching | MEDIUM | Medium | - | `reference_matcher.py` | `reference_analyzer.py` |
| 8 | Stem Separation | LOW | Low (integration) | demucs | `stem_separator.py` | `reference_analyzer.py` |

---

## Feature 1: Multiband Dynamics Processing

### Research Summary
- **Algorithm:** Linkwitz-Riley LR4 crossovers for phase-coherent band splitting
- **Bands:** 5-band (sub/bass/low-mid/high-mid/air) with crossovers at [80, 250, 2000, 8000] Hz
- **Per-band:** Independent compression with genre-specific presets

### Files to Create
```
multimodal_gen/multiband_dynamics.py
```

### Files to Modify
```
multimodal_gen/mix_chain.py:
  - Add EffectType.MULTIBAND_DYNAMICS
  - Add MultibandDynamicsParams dataclass
  - Add DSP.multiband_dynamics() method
  - Add to MixChain.process()

multimodal_gen/mix_engine.py:
  - Add multiband to master chain option
```

### Key Dataclass
```python
@dataclass
class MultibandDynamicsParams(EffectParams):
    crossover_freqs: List[float] = field(default_factory=lambda: [80, 250, 2000, 8000])
    crossover_type: str = "lr4"  # lr2, lr4, lr8
    bands: List[BandParams] = field(default_factory=list)
    output_limiter_ceiling_db: float = -0.3
```

### Integration Notes
- Use `scipy.signal.butter` with SOS output for numerical stability
- Process bands in parallel with NumPy vectorization
- Apply DC blocking after saturation

---

## Feature 2: Transient Shaping

### Research Summary
- **Algorithm:** Differential envelope (fast - slow = transient)
- **Parameters:** attack_amount (-100 to +100), sustain_amount (-100 to +100)
- **Lookahead:** 1-10ms for catching initial attack

### Files to Create
```
multimodal_gen/transient_shaper.py
```

### Files to Modify
```
multimodal_gen/mix_chain.py:
  - Add EffectType.TRANSIENT_SHAPER
  - Add TransientShaperParams dataclass
  - Add DSP.transient_shape() method

multimodal_gen/track_processor.py:
  - Add transient shaping to drum processing chain
```

### Key Dataclass
```python
@dataclass
class TransientShaperParams(EffectParams):
    attack_amount: float = 0.0      # -100 to +100 (% boost/cut)
    sustain_amount: float = 0.0     # -100 to +100
    fast_attack_ms: float = 0.5     # 0.1-5.0
    slow_attack_ms: float = 20.0    # 5.0-100.0
    lookahead_ms: float = 5.0       # 0-20
```

### Integration Notes
- Apply gain smoothing (1-5ms) to prevent clicks
- Use existing envelope follower pattern from `mix_chain.py` compressor

---

## Feature 3: True Peak Limiter (ISP Detection)

### Research Summary
- **Standard:** ITU-R BS.1770-4, EBU R128
- **Method:** 4x oversampling with polyphase filtering
- **Ceiling:** -1 dBTP for streaming compliance

### Files to Create
```
multimodal_gen/true_peak_limiter.py
```

### Files to Modify
```
multimodal_gen/mix_engine.py:
  - Replace basic limiter with True Peak limiter
  - Add compliance validation

multimodal_gen/audio_renderer.py:
  - Use True Peak limiter for final output
```

### Key Dataclass
```python
@dataclass
class TruePeakLimiterParams:
    ceiling_dbtp: float = -1.0      # True Peak ceiling
    oversampling: int = 4           # 4x recommended
    lookahead_ms: float = 1.5       # 1-5ms
    release_ms: float = 100.0       # 50-300ms
    filter_taps: int = 48           # FIR filter length
```

### Integration Notes
- Use `scipy.signal.resample_poly` for efficient oversampling
- Kaiser window (β=4.5) for FIR filter design
- Add `TruePeakMeasurement` for compliance reporting

---

## Feature 4: Intelligent Auto-Gain Staging

### Research Summary
- **Algorithm:** LUFS measurement per ITU-R BS.1770-4
- **Targets:** Genre-specific relative levels by track role
- **Output:** Gain adjustments with headroom preservation

### Files to Create
```
multimodal_gen/auto_gain.py
```

### Files to Modify
```
multimodal_gen/mix_engine.py:
  - Add auto_stage_tracks() method
  - Add GenreMixTemplate integration
```

### Key Dataclass
```python
@dataclass
class GenreMixTemplate:
    name: str
    target_lufs: float = -14.0
    headroom_db: float = -6.0
    track_targets: Dict[str, float] = field(default_factory=dict)
    # Example: {"kick": -6.0, "snare": -8.0, "808": -4.0, "melody": -10.0}
```

### Integration Notes
- Integrate with existing `MIX_PRESETS` in `mix_engine.py`
- Use K-weighting filter from research for accurate LUFS
- Preserve crest factor (never compress below 6dB)

---

## Feature 5: Spectral Processing Suite

### Research Summary
- **Dynamic EQ:** Threshold-triggered per-band gain
- **Resonance Suppression:** FFT peak detection + auto-notch
- **Exciter:** Waveshaping for harmonic enhancement

### Files to Create
```
multimodal_gen/spectral_processor.py
```

### Files to Modify
```
multimodal_gen/mix_chain.py:
  - Add EffectType.DYNAMIC_EQ
  - Add EffectType.RESONANCE_SUPPRESSOR
  - Add EffectType.EXCITER
  - Add corresponding Params dataclasses
```

### Key Dataclasses
```python
@dataclass
class DynamicEQParams(EffectParams):
    bands: List[DynamicEQBandParams] = field(default_factory=list)

@dataclass
class DynamicEQBandParams:
    frequency: float
    gain_db: float
    q: float = 1.0
    threshold_db: float = -20.0
    attack_ms: float = 10.0
    release_ms: float = 100.0

@dataclass
class ExciterParams(EffectParams):
    drive: float = 1.0
    frequency_hz: float = 3000.0  # Above this, add harmonics
    harmonics: str = "even"       # even, odd, both
```

### Integration Notes
- Use `scipy.signal.find_peaks` for resonance detection
- Apply saturation only above specified frequency for exciter
- Chebyshev polynomials for isolated harmonic generation

---

## Feature 6: Spatial Audio / Dolby Atmos Prep

### Research Summary
- **Binaural:** HRTF convolution with MIT KEMAR dataset
- **VBAP:** Vector Base Amplitude Panning for 3D
- **Atmos:** Object metadata preparation (ADM format)

### Files to Create
```
multimodal_gen/spatial_audio.py
multimodal_gen/binaural_renderer.py (optional)
```

### Files to Modify
```
multimodal_gen/mix_engine.py:
  - Add spatial panning option
  - Add binaural export mode
```

### Key Dataclass
```python
@dataclass
class SpatialPosition:
    x: float = 0.0  # Left-Right (-1 to 1)
    y: float = 0.0  # Front-Back (-1 to 1)
    z: float = 0.0  # Bottom-Top (-1 to 1)
    
    def to_spherical(self) -> Tuple[float, float, float]:
        """Convert to azimuth, elevation, distance."""
        ...
```

### Integration Notes
- This is the most complex feature - consider phased implementation
- Start with simple binaural panning, add full Atmos later
- HRTF data requires ~2MB database

---

## Feature 7: Reference Track Matching

### Research Summary
- **LTAS:** Long-Term Average Spectrum for tonal matching
- **EQ Matching:** Difference curve → parametric EQ bands
- **Loudness Matching:** LUFS normalization

### Files to Create
```
multimodal_gen/reference_matcher.py
```

### Files to Modify
```
multimodal_gen/reference_analyzer.py:
  - Add calculate_ltas() method
  - Add analyze_dynamics() method
  - Extend SpectralProfile dataclass
```

### Key Dataclass
```python
@dataclass
class MatchConfig:
    eq_match_amount: float = 0.7      # 0-1
    max_eq_boost_db: float = 8.0
    max_eq_cut_db: float = 10.0
    match_lufs: bool = True
    target_lufs: float = -14.0
```

### Integration Notes
- Fit difference curve to 6-8 parametric EQ bands
- Apply frequency-dependent gain limits
- Default to 50-70% match to preserve source character

---

## Feature 8: Stem Separation Integration

### Research Summary
- **Demucs v4:** 9.0 dB SDR, PyTorch, 4-6 stems
- **Spleeter:** Faster but lower quality, TensorFlow
- **Use Case:** Reference analysis, style transfer

### Files to Create
```
multimodal_gen/stem_separator.py
```

### Files to Modify
```
multimodal_gen/reference_analyzer.py:
  - Add stem-based analysis workflow
```

### Key Dataclass
```python
@dataclass
class SeparationConfig:
    backend: str = "demucs"
    demucs_model: str = "htdemucs"
    device: str = "cpu"
    output_format: str = "wav"
```

### Integration Notes
- Use subprocess for isolation (avoids PyTorch/TensorFlow conflicts)
- Cache separated stems with MD5-based file hash
- Create `StyleTemplate` for reusable style matching

---

## Implementation Order Recommendation

### Phase 1: Core Dynamics (Week 1-2)
1. **True Peak Limiter** - Foundation for all mastering
2. **Transient Shaping** - Quick wins for drum punch

### Phase 2: Advanced Dynamics (Week 3-4)
3. **Multiband Dynamics** - Most impactful for loudness
4. **Auto-Gain Staging** - Workflow improvement

### Phase 3: Spectral & Matching (Week 5-6)
5. **Spectral Processing** - Dynamic EQ, Exciter
6. **Reference Matching** - User workflow enhancement

### Phase 4: Advanced (Week 7+)
7. **Stem Separation** - Research workflow
8. **Spatial Audio** - Future-proofing for immersive

---

## Builder Instructions Template

For each feature, the Builder subagent should receive:

```markdown
## Task: Implement [Feature Name]

### Pre-Check Results
[Verifier output confirming no existing implementation]

### Files to Create
- `multimodal_gen/[feature].py` - Main module

### Files to Modify
1. `multimodal_gen/mix_chain.py`
   - Add `EffectType.[FEATURE]` to enum
   - Add `[Feature]Params` dataclass after existing params
   - Add `DSP.[feature]()` static method
   - Add to `MixChain.process()` elif chain

### Dataclass Schema
[Exact dataclass from research]

### Algorithm Pseudocode
[From research report]

### Integration Points
- Import from existing: `from .utils import SAMPLE_RATE`
- Follow pattern of existing effects (e.g., `CompressorParams`)
- Use NumPy vectorization where possible

### Acceptance Criteria
- [ ] Module created with documented functions
- [ ] Params dataclass with type hints
- [ ] Integrated into MixChain
- [ ] No syntax errors (Pylance clean)
- [ ] Existing tests still pass
```

---

## State File Updates

After completing this research phase, update:

### `.github/state/orchestration.json`
```json
{
  "current_phase": "decompose",
  "task_queue": [
    {"id": "mc-001", "description": "Implement True Peak Limiter", "status": "pending"},
    {"id": "mc-002", "description": "Implement Transient Shaper", "status": "pending"},
    // ... etc
  ]
}
```

### `.github/state/memory.json`
```json
{
  "learnings": {
    "masterclass_features": {
      "multiband": "Use LR4 crossovers, process bands in parallel, DC block after saturation",
      "transient": "Differential envelope (fast-slow), 5ms lookahead, gain smoothing",
      "true_peak": "4x oversampling, -1 dBTP ceiling, 1.5ms lookahead",
      "auto_gain": "K-weighting for LUFS, genre-specific templates, preserve crest factor"
    }
  }
}
```

---

## Next Steps

1. **Update state files** with research findings
2. **Spawn Verifier** for pre-implementation check on True Peak Limiter
3. **Spawn Builder** with detailed instructions from this document
4. **Iterate** through features in priority order

---

*Document generated by Supervisor agent following RLM orchestration pattern.*
