# InstrumentPatch Proposal (Track-Scoped v1)

## Problem statement

The repo already has useful instrument-shaping pieces, but they are split across multiple runtime-specific abstractions:

- Python procedural synthesis exposes envelopes and waveform settings.
- Python sample discovery/matching exposes sonic descriptors and library lookup.
- JUCE live preview exposes a separate default synth state and voice.

What does **not** exist today is a single shared cross-runtime contract that says, "this track should sound like _this_ patch, with these envelopes, layers, fallback bindings, and descriptor targets."

That gap matters because it blocks two practical goals:

1. **Planning/runtime alignment** — backend render, sample fallback, and app preview cannot point to the same portable patch description.
2. **Truthful parity messaging** — the backend mastered render/export can be the reference output, while JUCE live MIDI preview is still a dry/unmastered subset path. A shared patch contract should improve instrument intent alignment without falsely implying live mastered parity.

This proposal is intentionally **planning-ready, not implementation-complete**. It recommends a **track-scoped v1 `InstrumentPatch` contract** before any deeper live MIDI `program_change` rewrite.

## Current source of truth / evidence

| Area | Current evidence | What it already provides | Gap relevant to this proposal |
| --- | --- | --- | --- |
| Procedural envelope/waveform data | `multimodal_gen/assets_gen.py` defines `ADSRParameters` and `SynthesisParameters` | Backend can describe note-shaping basics such as attack/decay/sustain/release and waveform choice | The data is local to procedural generation, not a shared patch contract |
| Sample/descriptor data | `multimodal_gen/instrument_manager.py` defines `SonicProfile` and `InstrumentLibrary` | The backend can describe/analyze sonic qualities and match samples intelligently | `SonicProfile` is a measured sample descriptor, not a portable patch definition |
| Concrete instrument behavior | Functions such as `generate_krar_tone()` in `assets_gen.py` encode real instrument recipes | The backend already contains meaningful timbral knowledge, including physical-model-like plucked string behavior, filtered transients, and body resonance | The recipes are per-function and ad hoc rather than represented as shared patch objects |
| JUCE live preview state | `juce/Source/Audio/AudioEngine.h` defines `AudioEngine::Track::DefaultSynthState` | JUCE already has per-track preview state for waveform, attack, release, cutoff, LFO rate, and LFO depth | The state is a narrow preview subset and is not shared with Python |
| JUCE live preview voice | `juce/Source/Audio/AudioEngine.cpp` defines `DefaultSynthVoice` | JUCE can preview one oscillator through amplitude ADSR, simple low-pass filtering, and amplitude LFO | Decay/sustain are currently fixed in code, there is no shared patch schema, and there is no multi-layer/sample-aware patch realization |
| Existing planning evidence | `docs/UPGRADE_PLAN_2026-05-14_1990S_ROCK_QUALITY_UI.md` already notes there is no unified patch object and distinguishes backend mastered render from live preview | The repo already acknowledges the architectural gap and the truthfulness constraint | The next step needs to be made explicit and scoped so it can be implemented safely |

### Truthfulness constraint to preserve

This proposal does **not** change the repo's current honesty rule:

- **Backend mastered render/export parity** is the reference audio path.
- **JUCE live MIDI preview parity** is still partial/dry/unmastered until separate playback/FX/mastering work lands.

`InstrumentPatch` should unify instrument intent first. It should not be used to overclaim real-time mastered parity.

## Proposed core model

### `InstrumentPatch`

Top-level, track-scoped contract for one resolved instrument identity. It should hold:

- stable `patch_id`
- display name / family / track-role intent
- one optional `SynthesisVoice`
- zero or more `SampleLayerSpec` entries
- one `FallbackBinding`
- one `PatchProfile`
- notes about preview subset realization vs full backend realization

### `SynthesisVoice`

Portable synthesis description for procedural or hybrid patches. Holds oscillators, envelopes, filter, LFOs, velocity response, transient/noise layers, and saturation.

### `EnvelopeSpec`

Shared envelope description for amp/filter/pitch-style modulation. Should be reusable rather than inventing separate ad hoc envelope structs per runtime.

### `VelocityMap`

Declarative velocity response. V1 should at least cover amplitude and should reserve fields for cutoff/transient/noise response.

### `OscillatorSpec`

Describes one oscillator or algorithm slot. V1 should allow both classic waveforms and a small set of algorithm labels such as `karplus_strong` or `fm`, so existing backend recipes can be represented without pretending every voice is just a saw or sine.

### `FilterSpec`

Portable filter intent: mode, cutoff, resonance, drive, and whether the filter is static or modulated.

### `LfoSpec`

Portable modulation source for amplitude, pitch, cutoff, or pan targets.

### `NoiseLayerSpec`

Describes shaped noise components such as breath, bow noise, vinyl-like texture, or filtered pluck noise.

### `TransientLayerSpec`

Describes short onset components such as pick, hammer, click, or breath attacks.

### `SaturationSpec`

Per-patch harmonic coloration intent. This is not the same thing as final mastering.

### `SampleLayerSpec`

Describes sample-backed layers when an SF2/SFZ/custom sample path exists. This is how the shared contract can point to sample-backed realizations without forcing every runtime to realize them identically on day one.

### `FallbackBinding`

Portable fallback rules for cases where the preferred sample layer or synth engine is unavailable. This is where GM program hints, category preferences, and instrument-id hints belong.

### `PatchProfile`

Descriptor layer used for reporting, matching, and planning. This should carry portable intent fields such as family, genre tags, brightness/warmth/punch/richness/noise, and notes. It is adjacent to `SonicProfile`, but not identical to it:

- `SonicProfile` = measured or analyzed sample characteristics.
- `PatchProfile` = portable patch intent/identity plus descriptor defaults.

## Python-style schema sketch

```python
from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass
class EnvelopeSpec:
    attack_ms: float = 10.0
    decay_ms: float = 80.0
    sustain_level: float = 0.7
    release_ms: float = 200.0
    curve: Literal["linear", "exp"] = "exp"
    amount: float = 1.0  # used when the envelope targets filter/pitch


@dataclass
class VelocityMap:
    amp: float = 1.0
    cutoff_delta_hz: float = 0.0
    transient_level: float = 0.0
    noise_level: float = 0.0


@dataclass
class OscillatorSpec:
    algorithm: Literal[
        "sine", "triangle", "saw", "square", "pulse", "noise", "fm", "karplus_strong"
    ] = "sine"
    level: float = 1.0
    detune_cents: float = 0.0
    phase_offset: float = 0.0
    duty_cycle: float = 0.5


@dataclass
class FilterSpec:
    mode: Literal["lowpass", "highpass", "bandpass"] = "lowpass"
    cutoff_hz: float = 18000.0
    resonance: float = 0.0
    drive: float = 0.0


@dataclass
class LfoSpec:
    target: Literal["amp", "cutoff", "pitch", "pan"] = "amp"
    shape: Literal["sine", "triangle", "square", "sample_hold"] = "sine"
    rate_hz: float = 0.0
    depth: float = 0.0
    phase_offset: float = 0.0


@dataclass
class NoiseLayerSpec:
    color: Literal["white", "pink", "filtered"] = "filtered"
    level: float = 0.0
    attack_ms: float = 0.0
    decay_ms: float = 20.0
    band_low_hz: float = 200.0
    band_high_hz: float = 6000.0


@dataclass
class TransientLayerSpec:
    source: Literal["pick", "hammer", "click", "breath"] = "pick"
    level: float = 0.0
    duration_ms: float = 10.0
    band_low_hz: float = 400.0
    band_high_hz: float = 5000.0


@dataclass
class SaturationSpec:
    model: Literal["none", "tanh", "soft_clip", "tape"] = "none"
    drive: float = 0.0
    mix: float = 0.0


@dataclass
class SampleLayerSpec:
    source_id: str
    path_hint: str = ""
    root_midi_note: Optional[int] = None
    low_velocity: int = 1
    high_velocity: int = 127
    gain_db: float = 0.0
    start_offset_ms: float = 0.0
    one_shot: bool = False
    category_hint: str = ""


@dataclass
class FallbackBinding:
    gm_program: Optional[int] = None
    category_preferences: list[str] = field(default_factory=list)
    instrument_id_hints: list[str] = field(default_factory=list)
    sample_search_tags: list[str] = field(default_factory=list)
    allow_builtin_synth: bool = True


@dataclass
class PatchProfile:
    family: str
    genre_tags: list[str] = field(default_factory=list)
    brightness: float = 0.5
    warmth: float = 0.5
    punch: float = 0.5
    richness: float = 0.5
    noise_level: float = 0.0
    notes: list[str] = field(default_factory=list)


@dataclass
class SynthesisVoice:
    oscillators: list[OscillatorSpec] = field(default_factory=list)
    amp_envelope: EnvelopeSpec = field(default_factory=EnvelopeSpec)
    filter: Optional[FilterSpec] = None
    filter_envelope: Optional[EnvelopeSpec] = None
    lfos: list[LfoSpec] = field(default_factory=list)
    velocity_map: VelocityMap = field(default_factory=VelocityMap)
    noise_layer: Optional[NoiseLayerSpec] = None
    transient_layer: Optional[TransientLayerSpec] = None
    saturation: Optional[SaturationSpec] = None


@dataclass
class InstrumentPatch:
    patch_id: str
    display_name: str
    track_role: str
    scope: Literal["track"] = "track"
    patch_profile: PatchProfile = field(default_factory=lambda: PatchProfile(family="unknown"))
    synthesis_voice: Optional[SynthesisVoice] = None
    sample_layers: list[SampleLayerSpec] = field(default_factory=list)
    fallback: FallbackBinding = field(default_factory=FallbackBinding)
    preview_subset_notes: list[str] = field(default_factory=list)
    render_notes: list[str] = field(default_factory=list)
```

## Mapping from current repo concepts to the proposed model

| Current repo concept | Current role | Proposed model mapping | Notes |
| --- | --- | --- | --- |
| `ADSRParameters` | Backend procedural amp envelope | `EnvelopeSpec` | Direct conceptual mapping for shared envelope data |
| `SynthesisParameters` | Backend waveform/frequency/duration bundle | `SynthesisVoice` + `OscillatorSpec` + `EnvelopeSpec` | Frequency/duration remain note/event data, while patch-level waveform/envelope intent becomes shared |
| `SonicProfile` | Sample analysis / matching descriptor | `PatchProfile` seed values | `SonicProfile` remains measured analysis; `PatchProfile` becomes portable intent/reporting data |
| `InstrumentLibrary` / matcher | Sample discovery and best-fit selection | `SampleLayerSpec` candidates + `FallbackBinding` | Lets the contract express preferred samples without hard-coding one runtime path |
| Procedural functions such as `generate_krar_tone()` / `generate_guitar_tone()` | Ad hoc per-instrument recipes | Library-backed `InstrumentPatch` presets with `SynthesisVoice` data | Moves recipe identity into portable data while keeping implementation adapters bounded |
| `AudioEngine::Track::DefaultSynthState` | JUCE per-track preview controls | JUCE v1 realization subset of `InstrumentPatch` | Important: it is a subset, not the whole model |
| `DefaultSynthVoice` | JUCE preview executor | JUCE v1 `SynthesisVoice` adapter | Today it covers single oscillator + attack/release + cutoff + amp LFO |
| SF2/SFZ/custom sample instruments | Existing sample-backed playback choices | `SampleLayerSpec` + `FallbackBinding` | The shared contract can point at these without forcing identical live realization immediately |
| Backend mix/master chain | Render-stage loudness and finishing | **Not part of `InstrumentPatch`** | Patch identity should stay separate from mastering truthfulness and backend render parity |

## Explicit v1 decision: track-scoped patches first

**Decision:** v1 should resolve **one patch per track** for a generation/preview session. It should **not** start with dynamic runtime MIDI `program_change` patch switching.

### Why this is the safer next step

- The repo is already track-centric in both backend arrangement/session data and JUCE track state.
- A track-scoped contract is enough to unify instrument intent across backend render, sample fallback, and JUCE preview subset.
- It avoids prematurely rewriting transport/runtime state around mid-song patch mutation.
- It keeps verification/reporting simpler: each track can report `patch_id`, preferred realization, and actual realization.
- It preserves truthfulness: a track can still say "backend full render uses richer patch realization; JUCE preview uses subset/fallback realization" without pretending dynamic parity exists.

### Deferred by this decision

- MIDI `program_change` driven live patch swaps mid-track
- per-note patch mutation in the real-time engine
- generalized live patch graph/state migration across running playback

## JUCE v1 realization subset vs deferred fields

### JUCE v1 subset that maps cleanly today

| Shared field | JUCE v1 status | Current grounding |
| --- | --- | --- |
| Primary oscillator waveform (`sine`/`triangle`/`saw`/`square`) | Supported | `DefaultSynthState.waveform` + `DefaultSynthVoice` oscillator switch |
| Amp attack | Supported | `DefaultSynthState.attackSeconds` |
| Amp release | Supported | `DefaultSynthState.releaseSeconds` |
| Static low-pass cutoff | Supported | `DefaultSynthState.cutoffHz` |
| Velocity-to-cutoff (default-synth subset only) | Supported in the bounded JUCE subset | Existing `velocity_map.cutoff_delta_hz` now flows through the per-track default-synth seam and modulates the live preview low-pass cutoff by note velocity for remaining default-synth tracks only |
| Amp LFO rate/depth | Supported | `DefaultSynthState.lfoRateHz` / `lfoDepth` |
| Velocity to amplitude | Supported | `DefaultSynthVoice::startNote()` already maps velocity to level |

### Unsupported or deferred in JUCE v1

| Shared field | Status | Why deferred |
| --- | --- | --- |
| Configurable amp decay/sustain | Supported in the bounded default-synth subset | The existing per-track default-synth seam now persists additive decay/sustain values with legacy-safe defaults |
| Filter envelope | Deferred | No separate filter-envelope modulation path exists in JUCE live preview today |
| Multi-oscillator stacks / detune / unison | Deferred | Current voice is single-oscillator |
| Noise/transient layers | Deferred | No shared layer engine exists in the live preview synth |
| Per-patch saturation | Deferred | Current live preview path does not expose patch-local saturation stages |
| Shared `SampleLayerSpec` playback through the patch contract | Deferred/partial | JUCE has samplers, but not yet through a shared `InstrumentPatch` resolver |
| Backend master chain parity | Out of scope for this contract | Mastering truthfulness remains a separate playback/render concern |
| Dynamic runtime `program_change` switching | Explicitly deferred | Higher-risk architecture rewrite than the track-scoped contract |

### Truthfulness note

Even after `InstrumentPatch` exists, JUCE v1 should still report preview honestly:

- **backend render/export** = full/mastered reference path
- **JUCE live preview** = subset or fallback patch realization, still dry/unmastered unless separate parity work lands

## Concrete example patch: krar (Ethio-jazz flavored)

The goal here is not to freeze one final sound. The goal is to show how current repo evidence can be expressed as a portable patch.

```python
KRAR_ETHIO_JAZZ_V1 = InstrumentPatch(
    patch_id="ethiopian.krar.ethio_jazz.v1",
    display_name="Krar - Warm Ethio-jazz Pluck",
    track_role="melody",
    patch_profile=PatchProfile(
        family="ethiopian_string",
        genre_tags=["ethio_jazz", "ethiopian_traditional"],
        brightness=0.75,
        warmth=0.60,
        punch=0.50,
        richness=0.70,
        noise_level=0.08,
        notes=[
            "Grounded in current SonicProfile defaults for krar.",
            "Backend recipe already uses Karplus-Strong-style plucked string behavior, warm body resonance, strong high-frequency damping, and a soft finger-like attack.",
            "Backend mastered render remains the reference path; JUCE preview is subset/fallback only in v1.",
        ],
    ),
    synthesis_voice=SynthesisVoice(
        oscillators=[
            OscillatorSpec(algorithm="karplus_strong", level=1.0),
            OscillatorSpec(algorithm="sine", level=0.12, detune_cents=1200.0),
        ],
        amp_envelope=EnvelopeSpec(
            attack_ms=15.0,
            decay_ms=140.0,
            sustain_level=0.32,
            release_ms=160.0,
        ),
        filter=FilterSpec(mode="lowpass", cutoff_hz=2000.0, resonance=0.15),
        filter_envelope=EnvelopeSpec(
            attack_ms=0.0,
            decay_ms=120.0,
            sustain_level=0.55,
            release_ms=120.0,
            amount=350.0,
        ),
        velocity_map=VelocityMap(
            amp=1.0,
            cutoff_delta_hz=250.0,
            transient_level=0.10,
            noise_level=0.05,
        ),
        noise_layer=NoiseLayerSpec(
            color="filtered",
            level=0.08,
            attack_ms=0.0,
            decay_ms=15.0,
            band_low_hz=300.0,
            band_high_hz=2200.0,
        ),
        transient_layer=TransientLayerSpec(
            source="pick",
            level=0.10,
            duration_ms=15.0,
            band_low_hz=400.0,
            band_high_hz=2400.0,
        ),
        saturation=SaturationSpec(model="soft_clip", drive=0.08, mix=0.15),
    ),
    fallback=FallbackBinding(
        gm_program=110,
        category_preferences=["krar", "ethiopian_string", "strings", "guitar"],
        instrument_id_hints=["krar"],
        sample_search_tags=["ethio", "krar", "lyre", "warm_pluck"],
        allow_builtin_synth=True,
    ),
    preview_subset_notes=[
        "JUCE v1 can realize only a subset: one primary waveform fallback, attack/release, cutoff, amp LFO, and velocity->amp.",
        "Karplus-Strong-specific behavior and sample layers remain backend/full-render or later-preview work.",
    ],
)
```

## Minimal phased migration plan

| Phase | Scope | Deliverable |
| --- | --- | --- |
| 0. Proposal/data shape | Freeze the field set and vocabulary | This document, plus later JSON/YAML/dataclass schema work |
| 1. Backend patch registry | Define a small patch registry and map a few existing procedural instruments into it | `patch_id` appears in render diagnostics/reporting; no live preview promises changed |
| 2. JUCE subset adapter | Map the shared contract into `DefaultSynthState` subset fields on a per-track basis | Honest preview metadata: subset/fallback/full-sample status per track |
| 3. Sample fallback binding | Thread `InstrumentLibrary`, SF2/SFZ/custom samples, and category hints through `FallbackBinding` / `SampleLayerSpec` | Shared patch can prefer a sample-backed realization when available |
| 4. Deeper parity follow-up | Only after phases 1-3 are stable, decide whether more live preview fidelity is worth the complexity | Possible later work: extra envelopes, sample-layer preview, or dynamic switching research |

## Acceptance criteria

This proposal is complete enough for the next architecture slice if all of the following are true:

- The shared model names are explicit: `InstrumentPatch`, `SynthesisVoice`, `EnvelopeSpec`, `VelocityMap`, `OscillatorSpec`, `FilterSpec`, `LfoSpec`, `NoiseLayerSpec`, `TransientLayerSpec`, `SaturationSpec`, `SampleLayerSpec`, `FallbackBinding`, and `PatchProfile`.
- The document is grounded in current repo evidence rather than hypothetical greenfield systems.
- The v1 decision is explicit: **track-scoped patches first**.
- The document distinguishes **backend mastered render parity** from **live MIDI preview parity**.
- JUCE v1 supported subset vs deferred fields are written down clearly.
- At least one concrete patch example shows how current backend knowledge can map into the shared contract.
- The migration plan is small enough to implement in bounded follow-up slices.

## Non-goals

- Implementing the runtime patch engine in this docs-only slice
- Promising full audible parity between backend mastered render and live JUCE preview
- Replacing `InstrumentLibrary`, `SonicProfile`, or existing procedural instrument functions in one rewrite
- Introducing dynamic MIDI `program_change` patch switching as the first step
- Folding mix/mastering policy into the patch contract

The safe next architecture step is therefore: **introduce a track-scoped shared `InstrumentPatch` / `SynthesisVoice` contract, then map each runtime to it honestly and incrementally.**