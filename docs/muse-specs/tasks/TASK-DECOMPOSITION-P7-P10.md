````markdown
# MUSE AI Music Platform — Task Decomposition: Phases 7–10

## Complete Engineering Specification

> **Generated**: February 9, 2026
> **Scope**: Phases 7–10 (Controller Intelligence, Creative Frontier, Personalization, Live Performance)
> **SDK**: `@github/copilot-sdk` — CLI-based JSON-RPC
> **Architecture**: Continues from P0–P6 contracts (C1–C13). Adds contracts C14, C15.
> **Prerequisite**: TASK-DECOMPOSITION-P0-P2.md (C1–C8), TASK-DECOMPOSITION-P3-P5.md (C9–C12), TASK-DECOMPOSITION-P6.md (C13)
> **Dependencies**: All prior phases form the substrate — P7–P10 consume every contract C1–C13
> **Total Tasks**: 32 tasks across 4 phases (7 + 9 + 8 + 8)
> **Estimated Effort**: 48–70 dev-weeks solo | 16–24 weeks with 3 devs

---

## Table of Contents

1. [Decisions D-012, D-013, D-014 Resolution](#decisions-resolved)
2. [Contracts C14 & C15](#contracts-c14-c15)
3. [Master Task Summary](#master-task-summary)
4. [Phase 7 — Controller Intelligence (7 tasks)](#phase-7--controller-intelligence)
5. [Phase 8 — Creative Frontier (9 tasks)](#phase-8--creative-frontier)
6. [Phase 9 — Personalization (8 tasks)](#phase-9--personalization)
7. [Phase 10 — Live Performance (8 tasks)](#phase-10--live-performance)
8. [Cross-Phase Export Registry](#cross-phase-export-registry)
9. [Cross-Phase Dependency DAG](#cross-phase-dependency-dag)
10. [Risk Matrix](#risk-matrix)
11. [Effort Estimates & Critical Paths](#effort-estimates--critical-paths)
12. [Appendices](#appendices)

---

## Decisions Resolved

### Decision D-012: target_control Reverse Engineering Scope

**Question**: Should Phase 7 reverse-engineer all ~116+ `target_control` indices or work with a verified subset?

**Options Analyzed**:

| Option | Coverage | Effort | Risk | Maintenance |
|--------|----------|--------|------|-------------|
| **(a) All 116+** | 100% | 4–6 weeks | Low (complete map) | Must re-verify on MPC Beats updates |
| **(b) Known subset ~50** | ~43% | 1–2 weeks | Medium (gaps cause auto-mapping failures) | Partial re-verify |
| **(c) Community-sourced** | Variable | 1 week integration | High (unverified, inconsistent) | Depends on community |

**Empirical Evidence from .xmm Corpus (67 files)**:

| Index Range | Observed Types | Consistency | Likely Function |
|-------------|---------------|-------------|-----------------|
| **0–15** | `type=1` (Note), `control=4` | **All** pad controllers | Pad Bank A |
| **16–23** | `type=1` or `type=2`, `control=3/5` | Dual-use | Pad Bank B / Q-Link Knobs |
| **24–31** | `type=2` (CC), `control=5/7` | Knob/fader controllers | Q-Link Knobs (primary) |
| **32–41** | `type=0` (unmapped) | Most controllers | Faders / reserved |
| **42–43** | `type=2` (CC), `control=3/5` | Push 2, nanoKONTROL2 | Transport: Play/Stop or Jog |
| **44–45** | `type=2`, `control=5` | nanoKONTROL2 | Transport: Record/Overdub |
| **48** | `type=2`, `control=1` (button) | Push 2, nanoKONTROL2 | Transport: Play |
| **52–53** | `type=2`, `control=5` | Push 2 | Browser/navigate |
| **66** | `type=2`, `control=1` | Push 2, nanoKONTROL2 | Transport: Stop |
| **67–116** | `type=0` universally | Never mapped in stock files | Unknown / app-specific |
| **117–244** | Present only in nanoKONTROL2 | Extended address space | Mixer faders, solos, mutes, rec-arm |
| **≥4,086,032** | Anomalous high values | MPD218, nanoKONTROL2 | Internal state hooks (non-MIDI) |

**Key Finding**: Of 0–116, only indices **0–31, 42–43, 44–45, 48, 52–53, 66** show active mappings. ~40 indices with observed usage, ~76 never mapped. nanoKONTROL2's extended range (117–244) maps per-track mixer controls.

**Resolution**: **Option (a) — All indices, phased approach.**

| Sub-phase | Scope | Method | Gate |
|-----------|-------|--------|------|
| **7.1a** (Wk 1–2) | Known ~40 targets (0–31, 42–48, 52–53, 66) | Cross-reference .xmm corpus + UI observation | Unblocks P7-T3/T4 |
| **7.1b** (Wk 3–4) | Unknown ~67 targets (32–41, 49–51, 54–65, 67–116) | Experimental probing via virtual MIDI (P5 dep) | Unblocks P7-T5 mixer features |
| **7.1c** (Wk 5–6) | Extended 117–244 + anomalous high-value targets | Probing + binary analysis | Complete registry |

**Decision ID**: D-012 | **Resolved By**: Corpus analysis + architectural precedent | **Date**: 2026-02-09

---

### Decision D-013: Preference Persistence Model

**Question**: Should user preferences be per-user global or per-workspace local?

**Resolution**: **Global `~/.muse/user-preferences.json`** — single user preference profile with producer-mode switching for project-specific overrides. Session history ring buffer (last 50). Custom producer modes stored in `~/.muse/producer-modes.json`.

**Rationale**: Musical taste is portable across projects; genre/complexity preferences don't change per-workspace. Producer modes provide project-level specialization without fragmenting the core profile. Global storage also supports a taste quiz on first run.

**Decision ID**: D-013 | **Resolved By**: Architectural analysis | **Date**: 2026-02-09

---

### Decision D-014: Live Performance Latency Budget

**Question**: What latency is acceptable for real-time MIDI response?

**Resolution**: **Tiered latency budget**:

| Operation | Budget | Rationale |
|-----------|--------|-----------|
| Harmonization (parallel intervals) | <5ms | Lookup-based diatonic interval calculation — trivial compute |
| MIDI input analysis (per-note) | <10ms | Histogram update + correlation — arithmetic only |
| Complementary part generation | <50ms | Pre-generate 1–2 bars ahead; serve from buffer |
| Energy mapping parameter update | <100ms | Interpolated transitions over 2–4 beats |
| Session state persistence | <500ms | Background write, non-blocking |

**Mitigations**: Pre-allocate all buffers in hot path (no GC pressure). Use `performance.now()` for high-resolution timing. Consider native addon (`node-ffi` or Rust via NAPI) for timing-critical harmonization path. Worker threads for complement generation to avoid blocking the main MIDI I/O loop.

**Decision ID**: D-014 | **Resolved By**: Performance analysis + music perception research (>10ms audible as lag) | **Date**: 2026-02-09

---

## Contracts C14 & C15

### Contract C14: UserPreferences

```typescript
/**
 * Contract C14: User Preference Profile
 * Persistent model of user's musical taste, updated from implicit signals.
 * Produced by: Phase 9
 * Consumed by: All phases (via system context injection at session start)
 * Persistence: ~/.muse/user-preferences.json
 */
interface UserPreferences {
  /** Schema version for migration support */
  readonly version: number;
  /** ISO timestamp of last update */
  readonly lastUpdated: string;

  /**
   * 7 Core Dimensions — each normalized to 0.0–1.0.
   * Default: 0.5 (middle-of-road) for cold start.
   * Updated via EMA: dim_new = dim_old × (1 - α) + signal × α
   */
  readonly dimensions: {
    /** Simple triads (0.0) ↔ Extended jazz voicings (1.0) */
    readonly harmonicComplexity: number;
    /** Sparse, minimal (0.0) ↔ Dense, complex patterns (1.0) */
    readonly rhythmicDensity: number;
    /** Dark, warm tones (0.0) ↔ Bright, present tones (1.0) */
    readonly timbralBrightness: number;
    /** Minimal tracks (0.0) ↔ Full, layered arrangement (1.0) */
    readonly arrangementDensity: number;
    /** Safe, conventional (0.0) ↔ Avant-garde, experimental (1.0) */
    readonly experimentalTendency: number;
    /** Chill, ambient (0.0) ↔ High-energy, intense (1.0) */
    readonly energyLevel: number;
    /** Lo-fi, raw (0.0) ↔ Polished, clean production (1.0) */
    readonly productionCleanness: number;
  };

  /** Genre affinity scores derived from accepted/rejected outputs */
  readonly genreAffinities: Readonly<Record<string, number>>;
  /** Preferred BPM range [low, high] */
  readonly tempoRange: readonly [number, number];
  /** Frequently used keys */
  readonly keyPreferences: ReadonlyArray<string>;

  /** Total implicit signals received (for confidence calculation) */
  readonly signalCount: number;
  /**
   * Profile confidence: min(1.0, 0.3 + 0.15 × log2(signalCount + 1))
   * 0.3 at cold start, ~0.75 after 50 signals, ~0.9 after 200 signals.
   */
  readonly confidence: number;

  /**
   * Exploration budget (epsilon for epsilon-greedy).
   * Starts at 0.30, settles to 0.20. Bounds: [0.10, 0.30].
   */
  readonly explorationBudget: number;

  /** Session history ring buffer (last 50 sessions) */
  readonly sessionHistory: ReadonlyArray<SessionSummary>;
}

interface SessionSummary {
  readonly date: string;
  readonly durationMinutes: number;
  readonly genresUsed: ReadonlyArray<string>;
  readonly averageCriticScore: number;
  readonly creativitySettings: { readonly harmonic: number; readonly rhythmic: number };
  readonly acceptRate: number;
}

/**
 * Preference signal emitted by the implicit tracker (P9-T1).
 * Consumed by the preference model (P9-T2) for EMA updates.
 */
interface PreferenceSignal {
  readonly timestamp: string;
  readonly type: "accept" | "reject" | "modify" | "request" | "ignore" | "repeat";
  readonly domain: "harmony" | "rhythm" | "sound" | "arrangement" | "mix" | "genre" | "creativity";
  readonly context: {
    readonly toolName: string;
    readonly input: Readonly<Record<string, unknown>>;
    readonly output: unknown;
  };
  readonly inferredPreference: {
    readonly dimension: keyof UserPreferences["dimensions"];
    readonly direction: "increase" | "decrease" | "neutral";
    readonly confidence: number;
  };
}
```

### Contract C15: LivePerformanceState

```typescript
/**
 * Contract C15: Live Performance State
 * Real-time musical analysis updated per-note during live performance.
 * Produced by: Phase 10 (P10-T1)
 * Consumed by: Phase 10 only (P10-T2 through P10-T8)
 * Lifecycle: Created on session start, destroyed on session end. Not persisted.
 */
interface LivePerformanceState {
  /** Session lifecycle state */
  readonly sessionState: "idle" | "starting" | "listening" | "performing" | "stopping";

  /** Real-time musical analysis (updated per-note, <10ms) */
  readonly analysis: LiveAnalysis;

  /** Active complementary parts */
  readonly activeParts: ReadonlyArray<ComplementaryPartType>;

  /** Active harmonization mode */
  readonly harmonizationMode: HarmonizationMode;

  /** Session recording state */
  readonly recording: {
    readonly isRecording: boolean;
    readonly barCount: number;
    readonly trackCount: number;
  };

  /** MIDI port configuration */
  readonly ports: {
    readonly inputPort: string | null;
    readonly outputPort: string | null;
    readonly clockSource: "internal" | "external";
  };
}

/**
 * Continuously updated musical analysis from live MIDI input.
 * Core of the live performance system — every other P10 task reads this.
 */
interface LiveAnalysis {
  /** Detected key (null if <7 notes analyzed) */
  readonly detectedKey: string | null;
  /** Detected mode/scale */
  readonly detectedMode: string | null;
  /** Key detection confidence (0.0–1.0, increases with more notes) */
  readonly keyConfidence: number;
  /** Detected tempo in BPM (null if using external clock or <8 onsets) */
  readonly detectedTempo: number | null;
  /** Tempo detection confidence */
  readonly tempoConfidence: number;

  /** Notes per beat in current analysis window */
  readonly noteDensity: number;
  /** Average MIDI velocity (0–127) in current window */
  readonly velocityAverage: number;
  /** [min, max] velocity in current window */
  readonly velocityRange: readonly [number, number];
  /** [lowest, highest] MIDI note number in current window */
  readonly pitchRange: readonly [number, number];
  /** Weighted average pitch */
  readonly pitchCenter: number;

  /** Multiple simultaneous notes detected → chordal playing */
  readonly isChordal: boolean;
  /** Sequential single notes → melodic playing */
  readonly isMelodic: boolean;
  /** Channel 10 or low velocity variation → percussive playing */
  readonly isPercussive: boolean;

  /** Derived energy level (0.0–1.0) from density + velocity + range */
  readonly energyLevel: number;
  /** Energy trajectory over recent window */
  readonly energyTrend: "rising" | "falling" | "stable";

  /** Ring buffer of last N MIDI notes */
  readonly noteBuffer: ReadonlyArray<MidiNoteEvent>;
  /** Ring buffer of last N detected chords */
  readonly chordBuffer: ReadonlyArray<DetectedChord>;
  /** Analysis window size in beats */
  readonly windowSize: number;
}

interface MidiNoteEvent {
  readonly note: number;
  readonly velocity: number;
  readonly channel: number;
  readonly timestampMs: number;
  readonly durationMs: number | null;
}

interface DetectedChord {
  readonly symbol: string;
  readonly midiNotes: ReadonlyArray<number>;
  readonly timestampMs: number;
  readonly confidence: number;
}

type ComplementaryPartType = "auto-bass" | "auto-drums" | "auto-comping" | "auto-counter";
type HarmonizationMode = "thirds" | "sixths" | "counter-melody" | "chord-pad" | "octave" | "off";
```

---

## Master Task Summary

| Task ID | Name | Complexity | Phase | Dependencies |
|---------|------|-----------|-------|--------------|
| **P7-T1** | target_control Reverse Engineering | XL | 7 | P0-T5, P5-T1 |
| **P7-T2** | Controller Profile Database | M | 7 | P0-T5 |
| **P7-T3** | Context-Sensitive Auto-Mapping | L | 7 | P7-T1a, P7-T2, P0-T5(writer), C1 |
| **P7-T4** | Cross-Controller Translation | M | 7 | P7-T2, P0-T5 |
| **P7-T5** | Dynamic Remap Suggestions | M | 7 | P7-T3, C13 |
| **P7-T6** | Controller Agent & Skill Directory | S | 7 | P7-T2 |
| **P7-T7** | Controller Visualization | S | 7 | P7-T2 |
| **P8-T1** | Creativity Dial System | M | 8 | P0-T6 (SongState) |
| **P8-T2** | Multi-Critic Evaluation System | XL | 8 | P1-T5 (tension), P3-T4 (humanization) |
| **P8-T3** | Quality Gate Hook | L | 8 | P8-T2, P0-T7 |
| **P8-T4** | Happy Accident Generator | L | 8 | P8-T1 |
| **P8-T5** | Genre Bending Engine | L | 8 | P1-T8 (genre DNA) |
| **P8-T6** | Surprise Mode ("Go Wild") | M | 8 | P8-T1, P8-T4 |
| **P8-T7** | Explanation & Education System | M | 8 | P1-T3 (Roman numeral) |
| **P8-T8** | Variation Generator | L | 8 | P1, P3 generators |
| **P8-T9** | Creativity Metrics Dashboard | S | 8 | P8-T2 |
| **P9-T1** | Implicit Preference Tracker | L | 9 | P0 hooks |
| **P9-T2** | Preference Profile Model | L | 9 | P9-T1 |
| **P9-T3** | Epsilon-Greedy Exploration | M | 9 | P9-T2 |
| **P9-T4** | Producer Mode Profiles | M | 9 | P9-T2 |
| **P9-T5** | Preference-Driven Defaults | M | 9 | P9-T2, all gen tools |
| **P9-T6** | Preference Introspection Tools | M | 9 | P9-T2 |
| **P9-T7** | Session Persistence via Hooks | M | 9 | P9-T2, P0 hooks |
| **P9-T8** | Speculative Pre-Generation | L | 9 | P9-T2, P3/P4 gens |
| **P10-T1** | Real-Time MIDI Input Analyzer | XL | 10 | P5-T8 |
| **P10-T2** | Live Harmonizer | L | 10 | P10-T1, P1-T2 |
| **P10-T3** | Complementary Part Generator | XL | 10 | P10-T1, P3 |
| **P10-T4** | Live Session Manager | L | 10 | P10-T1–T3, P5 |
| **P10-T5** | Performance Energy Mapper | M | 10 | P10-T1 |
| **P10-T6** | Phrase Boundary Detection | M | 10 | P10-T1 |
| **P10-T7** | Live Performance Controller Integration | M | 10 | P7-T2, P10-T4 |
| **P10-T8** | Session Recording & Playback | L | 10 | P10-T4, P3-T2 |

**Summary**: 4 XL, 8 L, 14 M, 6 S = 32 tasks

---

## Phase 7 — Controller Intelligence

### Phase Overview

**Goal**: Transform MPC Beats hardware controllers from static MIDI mappers into intelligent, context-aware instruments that auto-configure based on workflow, translate between controller models, dynamically remap based on task, and visualize current state.

**Dependencies**: P0 (`.xmm` parser — C3), P5 (Virtual MIDI — C11), P4 (Sound Oracle — C10)

**Exports to**: P10 (live performance controller integration)

**Controller corpus**: 67 `.xmm` files spanning Akai, Alesis, Arturia, Korg, M-Audio, Novation, NI, Ableton — the complete set bundled with MPC Beats 2.9.0.21.

### XMM Format Reference

```xml
<MidiLearnMap_ Manufacturer="{string}" Version="{string}?">
  <device>
    <Input UnixPortName="{string}" WindowsPortName="{string}"/>
    <Output UnixPortName="{string}" WindowsPortName="{string}"/>
  </device>
  <midiPreamble>? <message base64:payload="{base64}"/> </midiPreamble>
  <shouldSyncMidi/>?
  <pairing>  <!-- Repeated 117–245+ times -->
    <Target_ Target_control="{int}"/>
    <Mapping_ Mapping_type="{0|1|2}" Mapping_channel="{int}"
              Mapping_data1="{int}" Mapping_control="{int}"
              Mapping_reverse="{0|1}" />
  </pairing>
</MidiLearnMap_>
```

**Mapping_type**: 0=unmapped, 1=Note, 2=CC

**Mapping_control enum** (reverse-engineered):

| Value | Physical Control Type | Observed Context |
|-------|----------------------|------------------|
| `1` | Button (momentary/toggle) | Transport buttons, scene launch |
| `3` | Pad (velocity-sensitive) | Drum pads on pad controllers |
| `4` | Key/Pad (generic note input) | Piano keys, standard pads |
| `5` | Knob/Fader (continuous CC) | Rotary encoders, linear faders |
| `7` | Knob/Slider (CC variant) | MPK mini 3 knobs |

**Corpus statistics**: 67 files, 47 with `<device>` block (70%), 12 with `<midiPreamble>` (18%), 12 with `<shouldSyncMidi/>` (18%), min range 0–116, max range 0–244 (nanoKONTROL2).

---

### P7-T1: target_control Reverse Engineering

| Attribute | Value |
|-----------|-------|
| **Task ID** | P7-T1 |
| **Complexity** | XL (4–6 weeks, research-heavy) |
| **Dependencies** | P0-T5 (`.xmm` parser), P5-T1 (Virtual MIDI port for probing) |
| **SDK** | `defineTool("probe_target_control")` — dev-time probing tool; `skillDirectories` — output loaded as skill context |

**Description**: Systematically decode the mapping between every `Target_control` integer index and the MPC Beats function it controls. The mapping is proprietary and undocumented. Approach combines statistical cross-referencing of 67 `.xmm` files, experimental probing via virtual MIDI, MPC Beats UI observation, and `MpcMmcSetup.pdf` analysis. Output is a versioned JSON registry serving as ground-truth for all P7 tasks.

**Input Interface**:
```typescript
interface XmmCrossReferenceInput {
  readonly sourceFile: string;
  readonly manufacturer: string;
  readonly knownLayout: KnownControllerLayout;
  readonly activePairings: ReadonlyArray<{
    readonly targetControl: number;
    readonly mappingType: 1 | 2;
    readonly channel: number;
    readonly data1: number;
    readonly controlType: number;
  }>;
}

interface KnownControllerLayout {
  readonly model: string;
  readonly padCount: number;
  readonly knobCount: number;
  readonly faderCount: number;
  readonly keyCount: number;
  readonly transportButtons: ReadonlyArray<string>;
}

interface ProbeRequest {
  readonly targetIndex: number;
  readonly probeType: "cc" | "note";
  readonly channel: number;
  readonly data1: number;
  readonly data2: number;
}
```

**Output Interface**:
```typescript
interface TargetControlEntry {
  readonly index: number;
  readonly name: string;
  readonly category: "pad" | "knob" | "fader" | "transport" | "mixer" | "browser" | "performance" | "program" | "internal" | "unknown";
  readonly description: string;
  readonly mpcFunction: string;
  readonly inputType: "note" | "cc" | "either" | "unknown";
  readonly valueRange?: { readonly min: number; readonly max: number };
  readonly observedInFiles: ReadonlyArray<string>;
  readonly confidence: "confirmed" | "inferred" | "experimental" | "unknown";
  readonly verificationMethod: ReadonlyArray<"cross-reference" | "experimental-probe" | "documentation" | "behavioral-observation">;
  readonly verifiedVersions: ReadonlyArray<string>;
}

interface TargetControlRegistry {
  readonly schemaVersion: string;
  readonly mpcBeatsVersion: string;
  readonly lastVerified: string;
  readonly totalEntries: number;
  readonly confidenceSummary: {
    readonly confirmed: number;
    readonly inferred: number;
    readonly experimental: number;
    readonly unknown: number;
  };
  readonly entries: ReadonlyArray<TargetControlEntry>;
}
```

**Implementation Hints**:
1. Cross-reference all 67 files — build matrix of `target → [files, types, controls]`. Consistent mappings = high-confidence inferences
2. Targets 0–15 = Pad Bank A (all controllers with pads, `type=1, control=4`)
3. Targets 16–23: dual behavior — Push 2 maps as knobs, CTRL49 maps as pads. Mode-dependent function
4. Identify transport by `Mapping_control=1` (button) — targets 48 and 66 = Play and Stop
5. Probe unmapped targets (32–41, 49–51, 54–65, 67–116) via P5 virtual MIDI port
6. nanoKONTROL2 extended range (117–244): per-track mixer controls (vol×8, pan×8, mute×8, solo×8, rec-arm×8)
7. Exclude anomalous values (>10M) — document as internal pointers
8. Version-gate: `verifiedVersions` per entry; baseline 2.9.0.21

**Testing**:

| # | Test Case | Expected Result |
|---|-----------|-----------------|
| 1 | Cross-reference targets 0–15 across all 67 files | 100% yield `type=1` on pad-equipped controllers; category="pad" |
| 2 | Cross-reference targets 24–31 | Majority yield `type=2` with `control=5/7`; category="knob" |
| 3 | Probe target 48 with CC via virtual MIDI | MPC Beats Play transport activates; confidence="confirmed" |
| 4 | Probe target 66 with CC via virtual MIDI | MPC Beats Stop transport activates; confidence="confirmed" |
| 5 | Generate registry JSON | Passes schema validation; all indices unique; totalEntries matches array length |
| 6 | Anomalous targets (>10M) | category="internal" or "unknown" |
| 7 | Registry O(1) lookup | Load registry, lookup by index returns correct entry |

**Risk**: **Critical** — if most targets remain unidentified, auto-mapping is severely limited. Mitigation: phased approach (D-012), mark unknowns as `"unknown"` category, graceful degradation.

---

### P7-T2: Controller Profile Database

| Attribute | Value |
|-----------|-------|
| **Task ID** | P7-T2 |
| **Complexity** | M (1–2 weeks) |
| **Dependencies** | P0-T5 (`.xmm` parser) |
| **SDK** | `skillDirectories` → `skills/controller/controller-profiles.json`; `defineTool("list_controllers")`, `defineTool("get_controller_profile")` |

**Description**: Build a structured JSON database of all 67 controllers' physical capabilities and MIDI specs. Pad count, knob count, fader count, key count, transport buttons, MIDI channels, note ranges, CC assignments. Derived from `.xmm` parsing + manufacturer spec cross-reference.

**Input Interface**:
```typescript
interface ProfileGenerationInput {
  readonly parsedMap: ParsedControllerMap; // Contract C3
  readonly specOverride?: ManufacturerSpec;
}

interface ManufacturerSpec {
  readonly model: string;
  readonly padCount: number;
  readonly knobCount: number;
  readonly faderCount: number;
  readonly keyCount: number;
  readonly hasAftertouch: boolean;
  readonly hasPitchBend: boolean;
  readonly transportButtons: ReadonlyArray<string>;
  readonly sourceUrl?: string;
}
```

**Output Interface**:
```typescript
interface ControllerProfile {
  readonly id: string;
  readonly manufacturer: string;
  readonly model: string;
  readonly xmmFile: string;
  readonly physicalControls: {
    readonly pads: number;
    readonly knobs: number;
    readonly faders: number;
    readonly keys: number;
    readonly transportButtons: ReadonlyArray<string>;
    readonly otherButtons: ReadonlyArray<string>;
    readonly velocitySensitivePads: boolean;
  };
  readonly midiSpec: {
    readonly padChannel: number;
    readonly padNoteRange: readonly [number, number];
    readonly knobCCs: ReadonlyArray<number>;
    readonly faderCCs: ReadonlyArray<number>;
    readonly ccChannel: number;
    readonly portCount: number;
  };
  readonly capabilities: ReadonlyArray<ControllerCapability>;
  readonly connection: {
    readonly windowsPorts: ReadonlyArray<string>;
    readonly unixPorts: ReadonlyArray<string>;
  };
  readonly requiresSysExInit: boolean;
  readonly supportsClockSync: boolean;
}

type ControllerCapability =
  | "velocity-sensitive-pads" | "aftertouch" | "pitch-bend" | "mod-wheel"
  | "transport-controls" | "clock-sync" | "sysex-init" | "multi-port"
  | "extended-pads" | "mixer-mode" | "encoders-relative";

interface ControllerProfileDatabase {
  readonly schemaVersion: string;
  readonly generatedFrom: string;
  readonly totalProfiles: number;
  readonly manufacturers: ReadonlyArray<string>;
  readonly profiles: ReadonlyArray<ControllerProfile>;
}
```

**Implementation Hints**:
1. Derive pad count from targets 0–15 active `type=1` mappings
2. Derive knob count from targets 24–31 active `type=2` mappings
3. Push 2 uses 16–23 for knobs (not 24–31) — flag as `layoutVariant`
4. Detect transport via targets 42, 43, 48, 66 with `type=2, control=1`
5. Key count from model name parsing or static lookup (can't derive from .xmm)
6. Multi-port: M-Audio Oxygen Pro 25 and CTRL49 declare 4 I/O port pairs
7. `<shouldSyncMidi/>` → `"clock-sync"` capability; `<midiPreamble>` → `"sysex-init"`

**Testing**:

| # | Test Case | Expected |
|---|-----------|----------|
| 1 | MPK mini 3 → profile | pads=16, knobs=8, faders=0, keys=25, padChannel=10 |
| 2 | nanoKONTROL2 → profile | pads=0, knobs=8, faders=8, transport=["play","stop","record"] |
| 3 | Ableton Push 2 → profile | pads=16, knobs=8 (targets 16–23), transport present |
| 4 | All 67 files → valid profiles | totalProfiles=67, all pass schema validation |
| 5 | Capability detection | Clock-sync controllers have `"clock-sync"`; SysEx controllers have `"sysex-init"` |

**Risk**: Medium — key count not derivable from .xmm. Mitigation: static lookup table from model name.

---

### P7-T3: Context-Sensitive Auto-Mapping

| Attribute | Value |
|-----------|-------|
| **Task ID** | P7-T3 |
| **Complexity** | L (2–3 weeks) |
| **Dependencies** | P7-T1a (registry, known targets), P7-T2 (profiles), P0-T5 (.xmm writer), C1 (SongState), C10 (EffectChain) |
| **SDK** | `defineTool("auto_map_controller")`, `defineTool("generate_controller_map")`, `hooks.onPostToolUse` |

**Description**: Given a controller profile and workflow context (composing, mixing, performing, sound design), automatically generate an optimal mapping. Introspects SongState for tracks, instruments, and effects. Uses target registry to produce a valid `.xmm` file.

**Input Interface**:
```typescript
interface AutoMapRequest {
  readonly controllerId: string;
  readonly context?: "composing-harmony" | "composing-rhythm" | "composing-melody" | "mixing" | "sound-design" | "performing" | "arranging";
  readonly songState: SongState; // Contract C1
  readonly focusTrackId?: string;
  readonly preferences?: {
    readonly padMode: "drums" | "chords" | "clips" | "auto";
    readonly knobMode: "synth" | "mixer" | "effects" | "auto";
    readonly preserveExisting: boolean;
  };
}
```

**Output Interface**:
```typescript
interface AutoMapResult {
  readonly success: boolean;
  readonly controller: ControllerProfile;
  readonly context: string;
  readonly summary: {
    readonly headline: string;
    readonly groups: ReadonlyArray<{
      readonly groupName: string;
      readonly assignments: ReadonlyArray<{ readonly label: string; readonly parameter: string }>;
    }>;
    readonly unmappedParameters: ReadonlyArray<string>;
  };
  readonly assignments: ReadonlyArray<ControlAssignment>;
  readonly xmmFilePath?: string;
  readonly warnings: ReadonlyArray<string>;
}

interface ControlAssignment {
  readonly targetIndex: number;
  readonly targetName: string;
  readonly physicalControl: "pad" | "knob" | "fader" | "button";
  readonly physicalLabel: string;
  readonly mappedParameter: string;
  readonly rationale: string;
  readonly priority: number;
  readonly midi: { readonly type: 1 | 2; readonly channel: number; readonly data1: number; readonly controlType: number };
}
```

**Implementation Hints**:
1. Context detection heuristic from tool-call history: 3 mixing tools → `"mixing"`
2. Knob assignment by context: mixing → track volumes/pans; sound-design → filter cutoff, resonance, envelope
3. Composing-harmony + ProgressionState → map pads to chord MIDI clusters
4. Effect chain awareness: map knobs to highest-impact effect parameters
5. Fallback to generic mapping if context detection fails
6. Write .xmm atomically (temp → validate XML → rename)
7. `preserveExisting=true` → only overwrite `type=0` (unmapped) targets

**Testing**:

| # | Test Case | Expected |
|---|-----------|----------|
| 1 | MPK mini 3 + mixing + 4 tracks | Knobs 1–4 → Track{1-4} Vol, Knobs 5–8 → Track{1-4} Pan |
| 2 | MPK mini 3 + composing-rhythm | Pads → GM drum notes, Knobs → note repeat / velocity |
| 3 | MPK mini 3 + harmony + [Am7, Dm9, G13, Cmaj7] | Pads 1–4 → chord clusters |
| 4 | nanoKONTROL2 + mixing | Faders 1–8 → Track vol, Knobs 1–8 → Track pan |
| 5 | Context auto-detection | 3 mixing tools → `context="mixing"` |
| 6 | Launchpad Mk2 (0 knobs) + mixing | Warning about no continuous controls |
| 7 | Generated .xmm validates | Well-formed XML, valid target indices, valid Mapping_type values |

**Risk**: High — synth parameter mapping requires knowledge of synth engine internals. Mitigation: start with generic names; enhance as P4 matures.

---

### P7-T4: Cross-Controller Translation

| Attribute | Value |
|-----------|-------|
| **Task ID** | P7-T4 |
| **Complexity** | M (1–2 weeks) |
| **Dependencies** | P7-T2 (profiles), P0-T5 (.xmm parser + writer) |
| **SDK** | `defineTool("translate_controller_map")` |

**Description**: Translate a mapping from one controller to another, handling mismatches in control count, type, and capabilities. Produces a translated `.xmm` and a human-readable migration report.

**Input Interface**:
```typescript
interface TranslationRequest {
  readonly sourceProfile: ControllerProfile;
  readonly sourceMapping: ReadonlyArray<ControlAssignment>;
  readonly targetProfile: ControllerProfile;
  readonly strategy: "preserve-all" | "prioritize-pads" | "prioritize-knobs" | "balanced";
  readonly priorityOverrides?: ReadonlyArray<{ readonly targetIndex: number; readonly priority: number }>;
}
```

**Output Interface**:
```typescript
interface TranslationResult {
  readonly success: boolean;
  readonly translatedAssignments: ReadonlyArray<ControlAssignment>;
  readonly report: {
    readonly from: string;
    readonly to: string;
    readonly sourceMappingCount: number;
    readonly preservedCount: number;
    readonly adaptedCount: number;
    readonly droppedCount: number;
    readonly preserved: ReadonlyArray<{ readonly targetIndex: number; readonly parameterName: string; readonly sourceControl: string; readonly targetControl: string }>;
    readonly adapted: ReadonlyArray<{ readonly targetIndex: number; readonly parameterName: string; readonly sourceControl: string; readonly targetControl: string; readonly adaptationNote: string }>;
    readonly dropped: ReadonlyArray<{ readonly targetIndex: number; readonly parameterName: string; readonly sourceControl: string; readonly reason: string }>;
    readonly suggestions: ReadonlyArray<string>;
  };
  readonly xmmFilePath?: string;
}
```

**Implementation Hints**:
1. Build capacity table: `{ pads: {source: 16, target: 8, deficit: 8}, ... }`
2. 1:1 where capacities match; downscale by priority; upscale leaves extras unmapped
3. Type adaptation: fader → knob (physical reassignment only, same CC range)
4. Transport: if target lacks buttons, generate warning, don't map to pads
5. Bidirectional algorithm (handles both up and down scaling)

**Testing**:

| # | Test Case | Expected |
|---|-----------|----------|
| 1 | MPK mini 3 → Launchkey 49 | 8 pads preserved, 8 knobs preserved, report suggests 8 more pads |
| 2 | Maschine MK3 (16 pads) → MPK mini 3 (8 pads) | 8 preserved, 8 dropped with report |
| 3 | Launchpad Mk2 (64 pads) → MPK mini 3 | 8 of 64 preserved, 56 dropped |
| 4 | nanoKONTROL2 (faders+knobs) → LPD8 (pads only) | Warning about continuous→momentary degradation |
| 5 | Same controller → same controller | All preserved, 0 adapted, 0 dropped |

**Risk**: Medium — continuous→momentary adaptation unusable. Mitigation: explicit warning, recommend different target.

---

### P7-T5: Dynamic Remap Suggestions

| Attribute | Value |
|-----------|-------|
| **Task ID** | P7-T5 |
| **Complexity** | M (1–2 weeks) |
| **Dependencies** | P7-T3 (auto-mapping), C13 (ComposerPipeline context), C1 (SongState), SDK hooks |
| **SDK** | `hooks.onPostToolUse`, `hooks.onUserPromptSubmitted`, `defineTool("suggest_remap")` |

**Description**: Monitor workflow in real-time via tool usage patterns and SongState mutations. Proactively suggest controller remapping at context transition boundaries with rate limiting and dismissal learning.

**Input Interface**:
```typescript
interface RemapEngineState {
  readonly activeController: ControllerProfile | null;
  readonly currentContext: string;
  readonly currentMapping: ReadonlyArray<ControlAssignment>;
  readonly recentTools: ReadonlyArray<{ readonly toolName: string; readonly timestamp: string; readonly agentUsed: string }>;
  readonly dismissedCount: number;
  readonly lastSuggestionTime: string | null;
  readonly suppressedContexts: ReadonlyArray<string>;
}
```

**Output Interface**:
```typescript
interface RemapSuggestion {
  readonly shouldSuggest: boolean;
  readonly detectedContext: string;
  readonly previousContext: string;
  readonly reason: string;
  readonly proposedMapping: AutoMapResult;
  readonly changeSummary: { readonly reassignedControls: number; readonly newlyMappedControls: number; readonly unaffectedControls: number };
  readonly confidence: number;
}
```

**Implementation Hints**:
1. Tool-call classification: `generate_progression` → harmony; `analyze_frequency_balance` → mixing
2. Sliding window consensus: 3 consecutive tools in same context before trigger
3. Rate limiting: 5-minute cooldown, max 3/session, suppress after 2 dismissals
4. Explicit keyword detection via `onUserPromptSubmitted`: "let's mix", "time to perform"
5. Confidence: `(matchingTools / totalRecent) × contextSwitchFreshness`
6. Non-blocking: chat message, not modal. Store `RemapResponse` in history for P9.

**Testing**:

| # | Test Case | Expected |
|---|-----------|----------|
| 1 | 3 harmony tools in sequence | detectedContext="composing-harmony", suggestion if context differs |
| 2 | 3 mixing tools | detectedContext="mixing", confidence ≥ 0.8 |
| 3 | "let's mix this" (no tool call) | Immediate suggestion via keyword detection |
| 4 | 2 mixing dismissals | Third mixing transition: shouldSuggest=false (suppressed) |
| 5 | 1 mixing, 1 composing, 1 mixing | No suggestion (no 3-consecutive consensus) |
| 6 | Same context for 15 min | No re-suggestion |

**Risk**: Medium — false positives annoy user. Mitigation: 3-tool consensus + rate limiting + suppression.

---

### P7-T6: Controller Agent & Skill Directory

| Attribute | Value |
|-----------|-------|
| **Task ID** | P7-T6 |
| **Complexity** | S (0.5–1 week) |
| **Dependencies** | P7-T2 (profiles) |
| **SDK** | `customAgents` → `controller` agent with `infer: true`; `skillDirectories` → `skills/controller/` |

**Description**: Create `skills/controller/` directory and configure the `controller` customAgent. Handles "Map my knobs to filter controls", "I switched from MPK mini to Launchkey", "What is knob 3 doing?"

**Output Files**:
- `skills/controller/SKILL.md` — agent capability description
- `skills/controller/target-control-registry.json` — from P7-T1
- `skills/controller/controller-profiles.json` — from P7-T2
- `skills/controller/mapping-conventions.md` — workflow→mapping reference

**Agent Config**:
```typescript
const controllerAgent: CustomAgentConfig = {
  name: "controller",
  displayName: "Controller Agent",
  description: "Hardware controller mapping, auto-configuration, cross-controller translation, MIDI controller intelligence",
  prompt: "You are the Controller Agent of MUSE...",
  tools: ["read_controller_map", "generate_controller_map", "auto_map_controller", "translate_controller_map", "list_controllers"],
  infer: true,
};
```

**Testing**:

| # | Test Case | Expected |
|---|-----------|----------|
| 1 | "Map my knobs to filter controls" | Routes to controller agent |
| 2 | "I switched from MPK mini to Launchkey" | Routes to controller, calls translate |
| 3 | "What is knob 3 doing?" | Routes to controller, calls read_controller_map |
| 4 | SKILL.md loads in SDK | Skill directory recognized |
| 5 | All 5 tools registered | All callable |

**Risk**: Low — routing conflicts possible. Mitigation: explicit keywords in description.

---

### P7-T7: Controller Visualization

| Attribute | Value |
|-----------|-------|
| **Task ID** | P7-T7 |
| **Complexity** | S (0.5–1 week) |
| **Dependencies** | P7-T2 (profiles), P7-T1 (target names) |
| **SDK** | `defineTool("visualize_controller")` |

**Description**: Generate text-based visualizations of controller mapping state (ASCII art, compact, or Mermaid). Shows what each physical control maps to, utilization stats, and unmapped controls.

**Input/Output**:
```typescript
interface VisualizationRequest {
  readonly profile: ControllerProfile;
  readonly assignments: ReadonlyArray<ControlAssignment>;
  readonly context: string;
  readonly format: "ascii" | "mermaid" | "compact";
  readonly showUnmapped: boolean;
  readonly showMidiDetails: boolean;
}

interface VisualizationResult {
  readonly visualization: string;
  readonly mermaidMarkup?: string;
  readonly stats: { readonly mappedControls: number; readonly unmappedControls: number; readonly totalControls: number; readonly utilizationPercent: number };
}
```

**Example Output**:
```
┌─────────────────────────────────────────────────────────┐
│  MPK mini 3 — Mixing Mode                              │
├─────────────────────────────────────────────────────────┤
│  Knobs:                                                 │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                  │
│  │Vol 1 │ │Vol 2 │ │Vol 3 │ │Vol 4 │                  │
│  └──────┘ └──────┘ └──────┘ └──────┘                  │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                  │
│  │Pan 1 │ │Pan 2 │ │Pan 3 │ │Pan 4 │                  │
│  └──────┘ └──────┘ └──────┘ └──────┘                  │
├─────────────────────────────────────────────────────────┤
│  8/8 knobs mapped │ 8/8 pads mapped │ 100% utilization │
└─────────────────────────────────────────────────────────┘
```

**Testing**:

| # | Test Case | Expected |
|---|-----------|----------|
| 1 | MPK mini 3, mixing, ASCII | 8 knobs + 8 pads in grid with labels |
| 2 | nanoKONTROL2, mixing, ASCII | 8 faders + 8 knobs + transport shown |
| 3 | All unmapped controller | All show `[empty]`, utilization=0% |
| 4 | Compact format | One line per group |
| 5 | Mermaid format | Valid Mermaid graph markup |

**Risk**: Low — ASCII may break in narrow terminals. Mitigation: compact format fallback.

---

## Phase 8 — Creative Frontier

### Phase Overview

**Goal**: Inject controlled unpredictability into generation. Two independent creativity dials (harmonic + rhythmic), a 4-axis multi-critic quality gate, happy accident mechanisms, genre bending, and an explanation system that turns creative risks into learning moments.

**Dependencies**: P1 (harmony, tension), P3 (rhythm, humanization), P4 (sound design), P6 (pipeline orchestrator)

**Exports to**: P9 (creativity calibration), P10 (live creativity injection)

---

### P8-T1: Creativity Dial System

| Attribute | Value |
|-----------|-------|
| **Task ID** | P8-T1 |
| **Complexity** | M (1 week) |
| **Dependencies** | P0-T6 (SongState, extends C1 with creativity settings) |
| **SDK** | `defineTool("set_creativity")` |

**Description**: Two independent dials (0.0–1.0) controlling harmonic and rhythmic adventurousness. Consumed by all generators to scale output unpredictability. Stored in SongState for persistence.

**Output Interface**:
```typescript
interface CreativitySettings {
  readonly harmonic: number;    // 0.0 = strictly diatonic → 1.0 = chromatic/polytonal
  readonly rhythmic: number;    // 0.0 = straight quantized → 1.0 = polyrhythmic chaos
  readonly coupled: boolean;    // If true, both dials move together
  readonly overrides: {
    readonly allowModalInterchange: boolean;
    readonly allowTritoneSubstitution: boolean;
    readonly allowPolyrhythm: boolean;
    readonly allowOddTimeSignatures: boolean;
    readonly allowMicrotonalHints: boolean;
  };
}
```

**Named Presets**:
| Name | Harmonic | Rhythmic | Style |
|------|----------|----------|-------|
| Pop Safe | 0.2 | 0.1 | Diatonic, on-grid |
| Genre Standard | 0.5 | 0.4 | Extensions, swing |
| Neo-Soul | 0.7 | 0.6 | Modal interchange, cross-rhythms |
| Jazz Fusion | 0.9 | 0.8 | Chromatic mediants, metric modulation |
| Free Jazz | 1.0 | 1.0 | Tone clusters, polymetric superposition |

**Effect on generators**:
- **Harmonic 0.0–0.3**: Diatonic only, no extensions beyond 7ths
- **Harmonic 0.3–0.6**: Add 9ths, 11ths, modal interchange, secondary dominants
- **Harmonic 0.6–0.8**: Tritone subs, chromatic mediants, borrowed chords
- **Harmonic 0.8–1.0**: Symmetrical scales, polytonality
- **Rhythmic 0.0–0.3**: Straight 4/4, quantized
- **Rhythmic 0.3–0.6**: Swing, ghost notes, syncopation
- **Rhythmic 0.6–0.8**: Cross-rhythms, metric modulation, tuplets
- **Rhythmic 0.8–1.0**: Polymetric superposition, odd time signatures

**Testing**:

| # | Test Case | Expected |
|---|-----------|----------|
| 1 | harmonic=0.1 → generate progression | Only diatonic chords |
| 2 | rhythmic=0.9 → generate drums | Odd groupings present |
| 3 | Overrides: tritone sub disabled at harmonic=0.8 | No tritone subs despite high creativity |
| 4 | coupled=true, set harmonic=0.5 | rhythmic also changes to 0.5 |
| 5 | Persist in SongState → reload | Settings preserved |

**Risk**: Low — well-defined domain.

---

### P8-T2: Multi-Critic Evaluation System

| Attribute | Value |
|-----------|-------|
| **Task ID** | P8-T2 |
| **Complexity** | XL (2–3 weeks) |
| **Dependencies** | P1-T5 (tension), P3-T4 (humanization), C8 (GenreDNA) |
| **SDK** | Internal engine consumed by P8-T3 (quality gate hook) |

**Description**: 4-axis quality evaluation: harmony, rhythm, arrangement, vibe. Each axis 0.0–1.0. Quality floor: no axis below 0.5, overall ≥ 0.7. Produces `CriticReport` (Contract C12).

**Output Interface**:
```typescript
/** Extends Contract C12: QualityScore */
interface CriticReport {
  readonly scores: {
    readonly harmony: number;
    readonly rhythm: number;
    readonly arrangement: number;
    readonly vibe: number;
  };
  readonly overall: number;
  readonly pass: boolean;
  readonly flags: ReadonlyArray<{
    readonly axis: "harmony" | "rhythm" | "arrangement" | "vibe";
    readonly severity: "warning" | "fail";
    readonly code: string;
    readonly description: string;
  }>;
  readonly suggestions: ReadonlyArray<string>;
}
```

**Critic Implementations**:
- **Harmony** (rule-based): Parallel fifths penalty (–0.15), parallel octaves (–0.10), tension arc check (Schenkerian), resolution check (V→I)
- **Rhythm** (pattern analysis): Duration entropy, groove alignment, density distribution, humanization quality
- **Arrangement** (structure): Instrument role check (bass <300Hz), frequency collision estimate (C10), dynamic contrast, track count vs. genre
- **Vibe** (cohesion): Genre DNA distance (C8), tempo/key/scale alignment, energy function curve

**Testing**:

| # | Test Case | Expected |
|---|-----------|----------|
| 1 | Progression with parallel fifths, no resolution | harmony < 0.5 |
| 2 | Well-crafted jazz progression | All axes ≥ 0.7 |
| 3 | Monotonous rhythm (all 16ths, same velocity) | rhythm < 0.5 |
| 4 | Genre-inconsistent elements | vibe penalty |
| 5 | pass=true requires overall ≥ 0.7 AND all axes ≥ 0.5 | Verify threshold logic |

**Risk**: High — music quality is subjective. Mitigation: critic floor is minimum, user can override via "keep it anyway."

---

### P8-T3: Quality Gate Hook

| Attribute | Value |
|-----------|-------|
| **Task ID** | P8-T3 |
| **Complexity** | L (1 week) |
| **Dependencies** | P8-T2 (multi-critic), P0-T7 (tool factory) |
| **SDK** | `hooks.onPostToolUse` — evaluate output after generation tools |

**Description**: Wire multi-critic into pipeline via SDK hooks. Every generated artifact passes quality checks. Failed outputs trigger re-generation with reduced creativity (up to 3 attempts), then present with warning.

**Implementation**: After tools in `[generate_progression, generate_drums, generate_bassline, generate_melody]`: parse output → run critic → if pass, continue → if fail AND attempts<3, reduce creativity by 0.15 per axis and re-invoke → if still fails, present with full report + "Keep it anyway?"

**Testing**:

| # | Test Case | Expected |
|---|-----------|----------|
| 1 | creativity=1.0 → low-scoring output | Critic catches, re-generation attempted |
| 2 | Verify max 3 attempts | After 3 fails, user gets output with warning |
| 3 | Creativity backed off on retry | Attempt 2: –0.15; Attempt 3: –0.30 |
| 4 | Good output at creativity=0.5 | Passes first attempt, no retry |
| 5 | Performance: critic < 100ms | Rule-based evaluation, no LLM calls |

**Risk**: Medium — latency from retries. Mitigation: <100ms per gate, max 3 attempts.

---

### P8-T4: Happy Accident Generator

| Attribute | Value |
|-----------|-------|
| **Task ID** | P8-T4 |
| **Complexity** | L (1–2 weeks) |
| **Dependencies** | P8-T1 (creativity dials for probability scaling) |
| **SDK** | Internal module consumed by generators |

**Description**: Introduce controlled surprises — 5 types of musically valid "accidents" with probability scaled by creativity dials.

**5 Accident Types**:
1. **Chromatic passing chord**: Insert between two chords. Probability: `harmonic × 0.15`
2. **Ghost note burst**: 3–5 ghost notes (vel 15–30) before strong beat. Probability: `rhythmic × 0.20`
3. **Tritone substitution**: Replace V with bII7. Probability: `harmonic × 0.10` (only when >0.5)
4. **Metric displacement**: Shift phrase by eighth note. Probability: `rhythmic × 0.12`
5. **Unexpected instrument swap**: Non-standard instrument for role. Probability: `(h+r)/2 × 0.08`

All accidents tagged for selective undo and must pass critic floor 0.5.

**Testing**:

| # | Test Case | Expected |
|---|-----------|----------|
| 1 | creativity=0.0 → 10 generations | Zero accidents |
| 2 | creativity=1.0 → 10 generations | Some accidents triggered |
| 3 | Each accident passes floor | All pass critic ≥ 0.5 |
| 4 | Accident has undo tag | `{ type: "happy_accident", accidentType, original, replacement, reason }` |
| 5 | Tritone sub blocked when harmonic < 0.5 | Not triggered |

**Risk**: Low.

---

### P8-T5: Genre Bending Engine

| Attribute | Value |
|-----------|-------|
| **Task ID** | P8-T5 |
| **Complexity** | L (1–2 weeks) |
| **Dependencies** | P1-T8 (genre DNA — Contract C8) |
| **SDK** | `defineTool("blend_genres")` |

**Description**: Deliberately blend elements from different genres using genre DNA distance matrix. Handles close genres (subtle), medium (interesting), and far (extreme) combinations.

**Blend Algorithm**: Interpolate DNA vectors with snap rules — tempo: weighted average; key/scale: pick one; time signature: pick or polymetric; instruments: union; rhythmic patterns: cross-pollinate.

**Named Fusions**: "Lo-fi jazz hop" (jazz:0.6, hip-hop:0.4), "Electronic soul" (R&B:0.5, electronic:0.5), "Trap classical" (classical:0.4, trap:0.6).

**Testing**:

| # | Test Case | Expected |
|---|-----------|----------|
| 1 | jazz + hip-hop → fusion | Swing feel + boom-bap rhythm |
| 2 | country + dubstep at low creativity | Rejection or warning |
| 3 | Fusion DNA validity | All dimensions in valid range |
| 4 | Close-genre blend | Subtle differences from either parent |
| 5 | Far-genre blend at high creativity | Accepted, more dramatic differences |

**Risk**: Medium — subjective quality of blends. Mitigation: critic validation on output.

---

### P8-T6: Surprise Mode ("Go Wild")

| Attribute | Value |
|-----------|-------|
| **Task ID** | P8-T6 |
| **Complexity** | M (1 week) |
| **Dependencies** | P8-T1, P8-T4 |
| **SDK** | `defineTool("surprise_me")`, keyword detection via `hooks.onUserPromptSubmitted` |

**Description**: Maximizes creative output — creativity 1.0/1.0, happy accident probability ×2, random genre blend (distance>0.5), critic floor relaxed to 0.4, attempt limit 5. Full provenance tracking for cherry-picking elements.

**Testing**:

| # | Test Case | Expected |
|---|-----------|----------|
| 1 | "go wild" | Creativity maxed, at least 1 accident |
| 2 | Critic floor relaxed | 0.4 instead of 0.5 |
| 3 | Provenance | Every decision tagged with reasoning |
| 4 | Cherry-pick | "Keep chords, swap drums" works |
| 5 | Implicit trigger | After 5+ conservative turns, suggest break-out |

**Risk**: Low — bounded by critic even at relaxed floor.

---

### P8-T7: Explanation & Education System

| Attribute | Value |
|-----------|-------|
| **Task ID** | P8-T7 |
| **Complexity** | M (1 week) |
| **Dependencies** | P1-T3 (Roman numeral analyzer) |
| **SDK** | Internal module called by all agents when creative choices are made |

**Description**: Explain creative decisions in music-theory terms at 3 depth levels: brief, standard, deep. Include famous examples where applicable.

**Depth Levels**:
- **Brief**: "Tritone sub of G7 → smooth voice leading"
- **Standard**: "Replaced G7 with Db7 (tritone substitution). Both share the B-F tritone..."
- **Deep**: Full interval analysis, historical context, famous songs

**Output Interface**:
```typescript
interface TheoryExplanation {
  readonly explanation: string;
  readonly depth: "brief" | "standard" | "deep";
  readonly relatedConcepts: ReadonlyArray<string>;
  readonly famousExamples: ReadonlyArray<{ readonly song: string; readonly context: string }>;
  readonly analysis?: { readonly romanNumerals: ReadonlyArray<string>; readonly tensionValues: ReadonlyArray<number> };
}
```

**Testing**:

| # | Test Case | Expected |
|---|-----------|----------|
| 1 | Tritone sub explanation | Mentions shared tritone interval |
| 2 | All 3 depth levels | Increasing detail |
| 3 | Famous example accuracy | Musically correct reference |
| 4 | Modal interchange explanation | Mentions parallel minor |
| 5 | Ghost note explanation | References feel/groove context |

**Risk**: Medium — theory explanations must be factually correct. Mitigation: structured templates, not free-form LLM.

---

### P8-T8: Variation Generator

| Attribute | Value |
|-----------|-------|
| **Task ID** | P8-T8 |
| **Complexity** | L (1–2 weeks) |
| **Dependencies** | P1 (harmony generators), P3 (rhythm generators) |
| **SDK** | `defineTool("generate_variations")` |

**Description**: Given source material (progression/rhythm/melody), generate N variations with controlled similarity distance (0.0=completely different, 1.0=nearly identical). All variations pass critic floor.

**Variation techniques**: Progressions → substitution, inversion, reharmonization. Rhythms → displacement, subdivision, accent shift. Melodies → transposition, retrograde, inversion, augmentation.

**Similarity measurement**: Progressions → shared root count. Rhythms → grid correlation (binary vector). Melodies → contour correlation (direction sequences).

**Testing**:

| # | Test Case | Expected |
|---|-----------|----------|
| 1 | 3 variations at similarity=0.8 | High structural similarity |
| 2 | 3 variations at similarity=0.2 | Significant differences |
| 3 | All variations pass critic | Each ≥ 0.5 all axes |
| 4 | Similarity score matches | Computed similarity within ±0.15 of target |
| 5 | Deterministic with seed | Fixed seed → same variations |

**Risk**: Low — composition of existing generators.

---

### P8-T9: Creativity Metrics Dashboard

| Attribute | Value |
|-----------|-------|
| **Task ID** | P8-T9 |
| **Complexity** | S (0.5 week) |
| **Dependencies** | P8-T2 (critic reports) |
| **SDK** | `defineTool("creativity_metrics")`, `hooks.onPostToolUse` for collection |

**Description**: Track creativity metrics across session: total generations, happy accidents, critic pass/fail rates, average scores, adventurousness index.

**Output Interface**:
```typescript
interface CreativityMetrics {
  readonly session: {
    readonly totalGenerations: number;
    readonly happyAccidents: number;
    readonly criticPasses: number;
    readonly criticFails: number;
    readonly averageScores: { readonly harmony: number; readonly rhythm: number; readonly arrangement: number; readonly vibe: number };
    readonly creativitySettings: CreativitySettings;
  };
  readonly adventurousnessIndex: number;
  readonly genreFidelity: number;
  readonly surpriseRatio: number;
}
```

**Testing**:

| # | Test Case | Expected |
|---|-----------|----------|
| 1 | 10 generations → metrics | Accurate counts |
| 2 | Adventurousness correlates with dials | High creativity → high index |
| 3 | "How creative have we been?" | Returns formatted metrics |

**Risk**: Low.

---

## Phase 9 — Personalization

### Phase Overview

**Goal**: Build a learning system that adapts to user's musical preferences over time. Implicit signal tracking, 7-dimension preference model, epsilon-greedy exploration, producer mode profiles, preference-driven defaults, and speculative pre-generation.

**Dependencies**: P8 (creativity metrics), P1 (genre DNA), P6 (pipeline — accept/reject signals), P0 (session hooks)

**Exports to**: P10 (personalization informs live adaptation)

---

### P9-T1: Implicit Preference Tracker

| Attribute | Value |
|-----------|-------|
| **Task ID** | P9-T1 |
| **Complexity** | L (1–2 weeks) |
| **Dependencies** | P0 hooks (`onPostToolUse`) |
| **SDK** | `hooks.onPostToolUse` — extract preference signals from user reactions |

**Description**: Monitor user interactions and extract preference signals without explicit input. 6 implicit signal types: acceptance, rejection, modification, repetition, request pattern, ignoring.

**Output**: Stream of `PreferenceSignal` events (Contract C14).

**Implementation Hints**:
1. After `generate_progression`: track if user accepts or requests modification
2. After `suggest_preset`: track if user asks for alternatives
3. After `set_creativity`: track explicit creativity preference
4. Debounce: max 1 signal per tool call
5. Buffer in memory, flush to preference model periodically

**Testing**:

| # | Test Case | Expected |
|---|-----------|----------|
| 1 | Accept 5 jazz progressions | harmonicComplexity signals trend "increase" |
| 2 | Reject 3 EDM drums | rhythmicDensity signals for EDM trend "decrease" |
| 3 | User says "more reverb" | timbralBrightness might stay neutral; productionCleanness decreases |
| 4 | User ignores suggestion | Weak negative signal (low confidence) |
| 5 | Debounce | Max 1 signal per tool call |

**Risk**: Medium — signal inference may be inaccurate. Mitigation: low α for implicit signals in EMA.

---

### P9-T2: Preference Profile Model

| Attribute | Value |
|-----------|-------|
| **Task ID** | P9-T2 |
| **Complexity** | L (1–2 weeks) |
| **Dependencies** | P9-T1 (signal input) |
| **SDK** | Stores to `~/.muse/user-preferences.json` |

**Description**: Maintain persistent user preference model (Contract C14) with 7 dimensions, updated via exponential moving average from implicit signals.

**Update Algorithm**: `dim_new = dim_old × (1 - α) + signal × α` with α=0.1 for implicit signals, higher for explicit. Confidence: `min(1.0, 0.3 + 0.15 × log2(signalCount + 1))`. Cold start: all dimensions at 0.5.

**Genre affinities**: Derived from genre DNA distance of accepted outputs. Explicit genre requests increase, rejected genre outputs decrease.

**Testing**:

| # | Test Case | Expected |
|---|-----------|----------|
| 1 | Default profile | All dimensions = 0.5, confidence = 0.3 |
| 2 | 20 "jazz acceptance" signals | harmonicComplexity > 0.6, genreAffinities.jazz > 0.5 |
| 3 | Confidence growth | Increases toward 1.0 logarithmically |
| 4 | Persistence roundtrip | Save → load → deep equality |
| 5 | EMA convergence | After 100 signals of value 0.8, dimension approaches 0.8 |

**Risk**: Medium — model drift over time. Mitigation: time-weighted EMA, periodic decay.

---

### P9-T3: Epsilon-Greedy Exploration

| Attribute | Value |
|-----------|-------|
| **Task ID** | P9-T3 |
| **Complexity** | M (1 week) |
| **Dependencies** | P9-T2 (preference values) |
| **SDK** | Internal module consumed by all generators |

**Description**: Reserve 20% of generations for exploring outside established preferences. Prevents filter bubbles. Budget adjusts: accepted explorations reduce budget (comfort zone expanding), rejected increase it.

**Algorithm**: `roll < explorationBudget` → explore (random axis, random direction, max 30% deviation). Label explored outputs: "Trying something different..."

**Budget bounds**: [0.10, 0.30]. Never stop exploring, never explore too much.

**Testing**:

| # | Test Case | Expected |
|---|-----------|----------|
| 1 | budget=0.20, 100 generations | ~20 are explorations |
| 2 | 5 accepted explorations | Budget decreases toward 0.15 |
| 3 | 5 rejected explorations | Budget increases toward 0.25 |
| 4 | Budget never < 0.10 | Hard minimum enforced |
| 5 | Exploration labeled | Output flagged as exploration |

**Risk**: Low.

---

### P9-T4: Producer Mode Profiles

| Attribute | Value |
|-----------|-------|
| **Task ID** | P9-T4 |
| **Complexity** | M (1 week) |
| **Dependencies** | P9-T2 (preference storage) |
| **SDK** | `defineTool("set_producer_mode")`, `defineTool("list_producer_modes")` |

**Description**: Named presets setting all preferences explicitly. Built-in: Beat Maker, Jazz Cat, EDM Producer, Lo-fi Chill, Film Scorer, Songwriter. Custom modes saveable.

**Built-in Modes**:
| Mode | harmonicComplexity | rhythmicDensity | timbralBrightness | energyLevel | Top Genres |
|------|-------------------|-----------------|-------------------|-------------|------------|
| Beat Maker | 0.4 | 0.7 | 0.5 | 0.6 | hip-hop, trap |
| Jazz Cat | 0.9 | 0.5 | 0.4 | 0.4 | jazz, bossa-nova |
| EDM Producer | 0.3 | 0.6 | 0.8 | 0.9 | house, techno |
| Lo-fi Chill | 0.5 | 0.3 | 0.3 | 0.2 | lo-fi, jazz |
| Film Scorer | 0.7 | 0.4 | 0.5 | 0.5 | orchestral |
| Songwriter | 0.3 | 0.3 | 0.5 | 0.4 | pop, folk |

**Testing**:

| # | Test Case | Expected |
|---|-----------|----------|
| 1 | Switch to Jazz Cat | harmonicComplexity=0.9 |
| 2 | Save custom mode | Persists in ~/.muse/producer-modes.json |
| 3 | Switch modes | Preferences reset to mode defaults |
| 4 | Describe mode: "dark aggressive dubstep" | System derives dimensions |
| 5 | List modes | Returns built-in + custom |

**Risk**: Low.

---

### P9-T5: Preference-Driven Defaults

| Attribute | Value |
|-----------|-------|
| **Task ID** | P9-T5 |
| **Complexity** | M (1 week) |
| **Dependencies** | P9-T2 (preference values), all generation tools (P1, P3, P4) |
| **SDK** | Tool wrapper: fill missing parameters from preferences before execution |

**Description**: Use preference model to set intelligent defaults for all generation tools. User gets good results without specifying every parameter. Transparency: always mention when defaults are preference-derived.

**Default Mappings**:
- `generate_progression()` without genre → top genreAffinity
- `generate_drums()` without style → top genre + rhythmicDensity
- Pipeline tempo → median of tempoRange
- Pipeline key → most frequent from keyPreferences

**Testing**:

| # | Test Case | Expected |
|---|-----------|----------|
| 1 | Jazz user + `generate_progression()` no args | Jazz defaults applied |
| 2 | User says "in D minor at 140 BPM" | Explicit params NOT overridden |
| 3 | Log message | "Using your preferred tempo range (85-95 BPM)" |
| 4 | Cold start (no preferences) | Generic middle-of-road defaults |
| 5 | After mode switch | Defaults reflect new mode |

**Risk**: Low — never overrides explicit params.

---

### P9-T6: Preference Introspection Tools

| Attribute | Value |
|-----------|-------|
| **Task ID** | P9-T6 |
| **Complexity** | M (1 week) |
| **Dependencies** | P9-T2 |
| **SDK** | `defineTool("get_preferences")`, `defineTool("set_preference")`, `defineTool("reset_preferences")` |

**Description**: Let user inspect and modify their preference profile. ASCII bar chart visualization. Historical comparison. Explicit overrides.

**Display Format**:
```
Your Music Profile:
─────────────────────
Harmonic Complexity:   ████████░░  0.78 (rich chord extensions)
Rhythmic Density:      █████░░░░░  0.52 (moderate groove complexity)
Timbral Brightness:    ███░░░░░░░  0.35 (warm, dark tones)
...
Top Genres: Jazz (0.82), Neo-Soul (0.71), Hip-Hop (0.58)
Preferred Tempo: 80-110 BPM
Confidence: 0.68 (47 interactions)
```

**Testing**:

| # | Test Case | Expected |
|---|-----------|----------|
| 1 | 20 sessions → get_preferences | Meaningful profile displayed |
| 2 | set_preference("brighter") | timbralBrightness increases |
| 3 | reset_preferences | All dimensions back to 0.5 |
| 4 | Historical comparison | "Complexity increased from 0.45 to 0.78 over 12 sessions" |
| 5 | Bar chart rendering | Unicode blocks proportional to values |

**Risk**: Low.

---

### P9-T7: Session Persistence via Hooks

| Attribute | Value |
|-----------|-------|
| **Task ID** | P9-T7 |
| **Complexity** | M (1 week) |
| **Dependencies** | P9-T2 (preference model), P0 hooks |
| **SDK** | `hooks.onSessionStart` — load preferences; `hooks.onSessionEnd` — persist updates |

**Description**: Wire preference persistence to SDK session lifecycle. OnStart: load `~/.muse/user-preferences.json`, inject into agent context, set creativity defaults. OnEnd: flush signals, update model, write session summary, persist.

**Error handling**: Corrupted file → backup + reset to defaults. Read-only filesystem → warn, operate without persistence.

**Testing**:

| # | Test Case | Expected |
|---|-----------|----------|
| 1 | Start session | Preferences loaded |
| 2 | End session | Preferences updated + persisted |
| 3 | Corrupt file | Graceful recovery to defaults |
| 4 | First run (no file) | Created with defaults |
| 5 | Session summary appended | Ring buffer, last 50 |

**Risk**: Low.

---

### P9-T8: Speculative Pre-Generation

| Attribute | Value |
|-----------|-------|
| **Task ID** | P9-T8 |
| **Complexity** | L (1–2 weeks) |
| **Dependencies** | P9-T2 (preference model), P3/P4 (generators), C1 (SongState) |
| **SDK** | Internal module; `hooks.onPostToolUse` triggers prediction |

**Description**: Predict next user request based on session patterns and pre-compute outputs. Cache with 5-minute TTL. Serve from cache for near-instant response.

**Prediction heuristics**: After progression → drums (85%); after drums → bass (78%); after all tracks → mix suggestions (81%). If iterating on progression → pre-generate 2 variations.

**Constraints**: Max 3 cached items, confidence threshold 0.70, back off after 3 wrong predictions, skip in high-creativity mode.

**Testing**:

| # | Test Case | Expected |
|---|-----------|----------|
| 1 | After progression → user asks for drums | Served from cache (near-instant) |
| 2 | Cached output expires after 5 min | New generation on next request |
| 3 | 3 wrong predictions | Speculative gen paused |
| 4 | High creativity mode active | No speculation |
| 5 | Max 3 cached items | Oldest evicted on overflow |

**Risk**: Low — speculative waste bounded by max items + TTL + back-off.

---

## Phase 10 — Live Performance

### Phase Overview

**Goal**: Real-time interactive musical collaboration. AI listens to live MIDI, detects key/mode/tempo, generates complementary parts on the fly, harmonizes live input, and adapts to performer energy. Capstone phase — MUSE as co-performer.

**Dependencies**: P5 (MIDI I/O, clock sync — especially P5-T8 listener), P1 (key detection, harmony), P3 (rhythm/melody generation), P7 (controller mapping), P8 (creativity dials), P9 (personalization)

**Exports**: None (terminal phase). Session recordings feed back to P6 for composition conversion.

---

### P10-T1: Real-Time MIDI Input Analyzer

| Attribute | Value |
|-----------|-------|
| **Task ID** | P10-T1 |
| **Complexity** | XL (2–3 weeks) |
| **Dependencies** | P5-T8 (MIDI input listener), P1-T1 (theory types), P1-T2 (scales for key profiles) |
| **SDK** | Internal engine — all other P10 tasks consume `LiveAnalysis` (Contract C15) |

**Description**: Process incoming MIDI note data in real-time to extract: key, mode/scale, tempo (if no external clock), rhythmic density, playing energy, and playing style (chordal/melodic/percussive). Must process each incoming note in <10ms.

**Key detection**: Pitch class histogram (12 bins) correlated with Krumhansl-Kessler profiles (24 profiles for 12 major + 12 minor). Minimum ~7–10 notes for reliable detection. Sliding window with decay.

**Tempo detection**: If external MIDI clock → use P5-T3 sync. Otherwise: inter-onset interval (IOI) histogram, peak → beat period → BPM. Requires ~8–16 onsets.

**Energy computation**: `0.5 × norm(density) + 0.3 × norm(velocity) + 0.2 × norm(pitchRange)`. Trend: compare to 4-bar moving average.

**Analysis window**: 4 beats default, configurable 1–8.

**Testing**:

| # | Test Case | Expected |
|---|-----------|----------|
| 1 | Send C major scale | key=C, mode=major |
| 2 | Syncopated rhythm | Tempo within ±5 BPM |
| 3 | Crescendo | energyTrend="rising" |
| 4 | Simultaneous notes | isChordal=true |
| 5 | <10ms per note | Performance benchmark passes |
| 6 | <7 notes | detectedKey=null (insufficient data) |
| 7 | Key change mid-stream | New key detected within 2 beats |

**Risk**: **Critical** — wrong key = all harmony is dissonant. Mitigation: require confidence > 0.8 before harmonizing, fall back to octave doubling.

---

### P10-T2: Live Harmonizer

| Attribute | Value |
|-----------|-------|
| **Task ID** | P10-T2 |
| **Complexity** | L (1–2 weeks) |
| **Dependencies** | P10-T1 (key detection), P1-T2 (scale library), P5-T2 (MIDI output) |
| **SDK** | `defineTool("live_harmonize")`, `defineTool("set_harmonization_mode")` |

**Description**: Given live melodic input and detected key, generate harmony notes in real-time: parallel thirds, sixths, counter-melody, chord pad, octave doubling. Must output within 5ms of input.

**Modes**: `"thirds"` (diatonic 3rd above — always safe), `"sixths"` (6th above — warmer), `"counter-melody"` (contrary motion — responds lazily), `"chord-pad"` (detect chord, sustain voicing), `"octave"` (simple but effective).

**Scale-aware intervals**: Diatonic, not chromatic. If key=C and input=E, third above=G (not G#).

**Edge cases**: Key not detected (<7 notes) → octave only. Key change → adapt within 2 beats. Dissonant input → pass through without harmony.

**Testing**:

| # | Test Case | Expected |
|---|-----------|----------|
| 1 | C major melody, thirds mode | Diatonic thirds above |
| 2 | D minor melody, sixths mode | Correct diatonic intervals |
| 3 | Latency < 5ms | Performance benchmark |
| 4 | Key not yet detected | Only octave doubling |
| 5 | Dissonant note vs key | No harmony added |
| 6 | Note-off tracking | No stuck notes |

**Risk**: High — stuck notes if note-off missed. Mitigation: note-off watchdog timer + periodic all-notes-off (CC 123).

---

### P10-T3: Complementary Part Generator

| Attribute | Value |
|-----------|-------|
| **Task ID** | P10-T3 |
| **Complexity** | XL (2–3 weeks) |
| **Dependencies** | P10-T1 (analysis), P3 (MIDI generation), P5-T4 (scheduled player) |
| **SDK** | `defineTool("live_generate_complement")` |

**Description**: Generate complementary musical parts that respond to performer's input: auto-bass, auto-drums, auto-comping, auto-counter.

**Part Types**:
- **Auto-bass**: Root on beats 1+3, walking bass between roots, density adapts to energy
- **Auto-drums**: Kick-snare base, add hi-hats/fills as energy increases
- **Auto-comping**: Chord pad, voice-led, rhythm matching performer energy
- **Auto-counter**: Contrary motion, rhythmic complementarity (play in gaps)

**Timing**: Quantize to 16th note grid, use P5-T4 scheduler, pre-generate 1–2 bars ahead.

**Channel separation**: Input ch1, bass ch2, drums ch10, comping ch3, counter ch4.

**Testing**:

| # | Test Case | Expected |
|---|-----------|----------|
| 1 | C major melody → auto-bass | Bass follows with C root |
| 2 | Increase playing density | Drums add complexity |
| 3 | Key change to G major | Bass adapts |
| 4 | Toggle parts on/off | Clean start/stop |
| 5 | Energy 0.2 → drums | Kick only, quarter notes |
| 6 | Energy 0.8 → drums | Full kit, ghost notes, fills |

**Risk**: High — CPU load from multiple simultaneous generators. Mitigation: worker threads for parallel generation.

---

### P10-T4: Live Session Manager

| Attribute | Value |
|-----------|-------|
| **Task ID** | P10-T4 |
| **Complexity** | L (1 week) |
| **Dependencies** | P10-T1, T2, T3, P5 (MIDI ports) |
| **SDK** | `defineTool("start_live_session")`, `defineTool("stop_live_session")`, `defineTool("set_live_mode")` |

**Description**: Orchestrate live performance session lifecycle: start (detect ports, initialize analysis), configure (toggle parts, switch modes), perform (continuous MIDI processing), stop (close ports, generate summary).

**State machine**: IDLE → STARTING → LISTENING → PERFORMING → STOPPING → IDLE. Error states: DISCONNECTED, RECONFIGURING.

**Context compaction**: Every 32 bars, compact via `infiniteSessions`. Preserve key/tempo/energy history but drop individual notes.

**Testing**:

| # | Test Case | Expected |
|---|-----------|----------|
| 1 | Start session | Ports opened, confirmed |
| 2 | Send MIDI notes | Analysis begins |
| 3 | Stop session | Ports closed, summary generated |
| 4 | Port disconnect | DISCONNECTED state, recovery attempt |
| 5 | 32-bar compaction | History preserved, notes dropped |

**Risk**: Medium — port management complexity. Mitigation: graceful error states.

---

### P10-T5: Performance Energy Mapper

| Attribute | Value |
|-----------|-------|
| **Task ID** | P10-T5 |
| **Complexity** | M (1 week) |
| **Dependencies** | P10-T1 (energy level) |
| **SDK** | Internal module consumed by P10-T3 |

**Description**: Map performer energy to system behavior: density of drums, complexity of bass, comping style, effect parameters.

**Energy → Parameter Mapping**:

| Energy | Drums | Bass | Harmony | Effects |
|--------|-------|------|---------|---------|
| 0.0–0.2 | Kick only, quarters | Whole notes | Sustained pads | Heavy reverb |
| 0.2–0.4 | Add hi-hat | Half notes | Block chords | Moderate reverb |
| 0.4–0.6 | Full kit, eighths | Quarters, walking | Comping rhythm | Balanced |
| 0.6–0.8 | Ghost notes, fills | Eighths, chromatic | Syncopated | Chorus, delay |
| 0.8–1.0 | Double-time | Sixteenths, slap | Dense voicings | Overdrive |

**Transition smoothing**: Interpolate over 2–4 beats. Hysteresis: threshold ± 0.1 to avoid flicker.

**Optional**: "Contrarian mode" — system does opposite (drives tension).

**Testing**:

| # | Test Case | Expected |
|---|-----------|----------|
| 1 | Low velocity → drums | Sparse pattern |
| 2 | Build to high velocity | Progressive complexity |
| 3 | Sudden drop | System follows within 2 beats |
| 4 | Borderline energy (0.39–0.41) | No flicker (hysteresis) |
| 5 | Contrarian mode | System intensifies when player softens |

**Risk**: Low.

---

### P10-T6: Phrase Boundary Detection

| Attribute | Value |
|-----------|-------|
| **Task ID** | P10-T6 |
| **Complexity** | M (1 week) |
| **Dependencies** | P10-T1 (note buffer) |
| **SDK** | Internal module — events consumed by P10-T3, T5 |

**Description**: Detect musical phrase boundaries in real-time: rest (>1 beat), register shift (>octave), rhythmic cadence (long after short), harmonic cadence (return to I), repetition.

**Uses**: Align drum fills, trigger chord changes, place variation between phrases, context compaction.

**Quantize** boundaries to nearest strong beat (beat 1 or 3). Confidence-weighted: high → immediate, low → 1-beat delay.

**Testing**:

| # | Test Case | Expected |
|---|-----------|----------|
| 1 | 4-bar melody + rest at end | Boundary detected |
| 2 | Register shift (>octave leap) | Boundary detected |
| 3 | Continuous stream, no clear boundary | No false boundary |
| 4 | Boundary aligns to strong beat | Beat 1 or 3 |
| 5 | Repeated pattern | Boundary between repetitions |

**Risk**: Low — false positives are tolerable (just mis-time a fill).

---

### P10-T7: Live Performance Controller Integration

| Attribute | Value |
|-----------|-------|
| **Task ID** | P10-T7 |
| **Complexity** | M (1 week) |
| **Dependencies** | P7-T2 (controller profiles), P10-T4 (session manager) |
| **SDK** | `defineTool("set_live_controller_mapping")` — generates performance .xmm |

**Description**: Optimize controller mappings for live performance: pads toggle parts/modes, knobs control mix/creativity, foot pedal toggles harmony. Distinguish performance notes (ch1) from controller CCs (ch2) in MIDI routing.

**Performance Pad Layout**:
- Pads 1–4: Toggle parts (drums, bass, comping, counter)
- Pads 5–8: Switch harmonization mode
- Pads 9–12: Energy override (force low/mid/high/auto)
- Pads 13–16: Trigger events (fill, break, key change, stop)

**Performance Knob Layout**:
- Knob 1: Harmony mix (dry/wet)
- Knob 2: Complement volume
- Knob 3: Creativity dial (real-time)
- Knob 4: Reverb/space

**Testing**:

| # | Test Case | Expected |
|---|-----------|----------|
| 1 | Pad press toggles drums | State changes, no analysis contamination |
| 2 | Knob sweep → harmony wet/dry | Volume changes |
| 3 | CC events on ch2 not sent to analysis | MIDI routing correct |
| 4 | Foot pedal (CC 64) toggles harmony | On/off toggle |
| 5 | Custom .xmm generated | Valid "MPC AI Live Performance" mapping |

**Risk**: Medium — MIDI routing between performance notes and controller CCs must be bulletproof.

---

### P10-T8: Session Recording & Playback

| Attribute | Value |
|-----------|-------|
| **Task ID** | P10-T8 |
| **Complexity** | L (1 week) |
| **Dependencies** | P10-T4 (session manager), P3-T2 (MIDI writer) |
| **SDK** | `defineTool("save_live_session")` |

**Description**: Record entire live session (input + all generated output) as multi-track Standard MIDI File + session metadata JSON. Support conversion to composition (SongState from session data).

**Tracks**: 1=Live input, 2=Harmony, 3=Auto-bass, 4=Auto-drums, 5=Other parts. SMF Format 1, 480 PPQ.

**Session Metadata**:
```typescript
interface SessionMetadata {
  readonly sessionDate: string;
  readonly durationSeconds: number;
  readonly detectedKeys: ReadonlyArray<string>;
  readonly averageTempo: number;
  readonly energyCurve: ReadonlyArray<number>;
  readonly complementaryParts: ReadonlyArray<string>;
  readonly harmonizationModes: ReadonlyArray<string>;
  readonly tracks: number;
}
```

**Conversion to composition**: Create SongState from session — populate progression from detected chords, import tracks, enter standard P6 pipeline.

**Testing**:

| # | Test Case | Expected |
|---|-----------|----------|
| 1 | Record 16-bar session | .mid with correct track count |
| 2 | Playback reproduces session | Accurate reproduction |
| 3 | Metadata file valid | JSON schema validation passes |
| 4 | Convert to SongState | Preserves key, tempo, tracks |
| 5 | Variable tempo session | Tempo map embedded in .mid |

**Risk**: Low — standard MIDI file I/O.

---

## Cross-Phase Export Registry

| Export Artifact | Type | Producer | Consumer(s) | Contract |
|-----------------|------|----------|-------------|----------|
| target-control-registry.json | Data file | P7-T1 | P10 (live input → MPC routing) | `TargetControlRegistry` |
| controller-profiles.json | Data file | P7-T2 | P10 (physical setup understanding) | `ControllerProfileDatabase` |
| `auto_map_controller` tool | SDK tool | P7-T3 | P6 (pipeline controller setup), P10 (perf mapping) | `AutoMapRequest → AutoMapResult` |
| `translate_controller_map` tool | SDK tool | P7-T4 | P10 (hot-swap controllers) | `TranslationRequest → TranslationResult` |
| `suggest_remap` tool | SDK tool | P7-T5 | P10 (real-time context shifts) | `RemapSuggestion` |
| `visualize_controller` tool | SDK tool | P7-T7 | P10 (live overlay) | `VisualizationResult` |
| Controller agent config | SDK config | P7-T6 | P0 (main registration) | `ControllerAgentConfig` |
| `CreativitySettings` | State | P8-T1 | P9 (calibrates defaults), P10 (live creativity) | `CreativitySettings` |
| `CriticReport` / multi-critic | Engine | P8-T2 | P6 (pipeline gates), P9 (learning from scores) | Contract C12 |
| Variation generator | Engine | P8-T8 | P6 (A/B generation) | `VariationRequest → VariationResult` |
| Explanation system | Engine | P8-T7 | All agents | `TheoryExplanation` |
| Creativity metrics | Data | P8-T9 | P9 (preference modeling) | `CreativityMetrics` |
| `UserPreferences` (C14) | State | P9-T2 | ALL (via system context), P8 (creativity defaults) | Contract C14 |
| Producer modes | Data | P9-T4 | P6 (pipeline defaults) | `ProducerMode` |
| Speculative cache | Engine | P9-T8 | P10 (pre-generate live variations) | Internal |
| Session recordings | Data | P10-T8 | P6 (conversion to composition) | `SessionMetadata` + SMF |
| LiveAnalysis (C15) | State | P10-T1 | P9 (preference signals from perf style) | Contract C15 |

---

## Cross-Phase Dependency DAG

```
Phase 7 Internal:
  P0-T5 ─┬→ P7-T1 ──→ P7-T3 ──→ P7-T5
          └→ P7-T2 ─┬→ P7-T3
                     ├→ P7-T4
                     ├→ P7-T6
                     └→ P7-T7
  Critical path: P0-T5 → P7-T1 → P7-T3 → P7-T5

Phase 8 Internal:
  P8-T1 ──→ P8-T4 ──→ P8-T6
  P8-T2 ──→ P8-T3
  P8-T2 ──→ P8-T9
  P8-T1 + P8-T2 (parallel) → P8-T3 → P8-T4 → P8-T6
  Critical path: P8-T2 (XL) → P8-T3 → P8-T4 → P8-T6

Phase 9 Internal:
  P9-T1 → P9-T2 → P9-T3
                  → P9-T4
                  → P9-T5
                  → P9-T6
                  → P9-T7
         P9-T2 → P9-T8
  Critical path: P9-T1 → P9-T2 → P9-T7 → P9-T8

Phase 10 Internal:
  P10-T1 ─┬→ P10-T2 ──→ P10-T4 → P10-T7
           ├→ P10-T3 ──→ P10-T4 → P10-T8
           ├→ P10-T5
           └→ P10-T6
  Critical path: P10-T1 → P10-T3 (parallel with T2) → P10-T4 → P10-T8

Cross-Phase:
  P6 → P7 (controller setup for generated sessions)
  P6 → P8 (quality gates applied to pipeline)
  P6 → P9 (preference learning from pipeline interactions)
  P7 → P10 (controller mapping for live use)
  P8 → P10 (creativity dials during live performance)
  P9 → P10 (personalization informs live adaptation)
```

---

## Risk Matrix

| ID | Risk | Severity | Probability | Tasks | Mitigation |
|----|------|----------|-------------|-------|------------|
| R7-01 | target_control indices undiscoverable | **Critical** | Medium | P7-T1,T3,T4 | Phased approach (D-012); `"unknown"` category; graceful degradation |
| R7-02 | MPC Beats version changes indices | **High** | Medium | P7-T1+ | Version-gate registry; detect from VERSION.xml |
| R7-03 | .xmm write requires admin | **High** | High | P7-T3,T4 | Write to Documents; provide copy instructions |
| R8-01 | Critic subjectivity | **High** | Medium | P8-T2,T3 | Floor is minimum, user override available |
| R8-02 | Creativity spiral → incoherent output | **Medium** | Medium | P8-T4,T6 | Critic gate ensures minimum coherence |
| R8-03 | Theory explanation errors | **Medium** | Low | P8-T7 | Structured templates, not free-form LLM |
| R9-01 | Filter bubble | **High** | Medium | P9-T2,T3 | Epsilon-greedy with hard minimum 10% |
| R9-02 | Cold start quality | **Medium** | High | P9-T2 | Middle-of-road defaults + optional taste quiz |
| R9-03 | Model drift | **Medium** | Medium | P9-T2 | Time-weighted EMA, periodic decay |
| R10-01 | Latency >10ms → audible lag | **Critical** | Medium | P10-T1,T2 | Pre-allocated buffers, native addon, `performance.now()` |
| R10-02 | Wrong key → dissonant harmony | **Critical** | Medium | P10-T1,T2 | Confidence > 0.8 required; fallback to octave doubling |
| R10-03 | CPU overload → audio dropouts | **High** | Medium | P10-T3 | Worker threads for parallel generation; profile + optimize |
| R10-04 | Stuck MIDI notes | **High** | Medium | P10-T2 | Note-off watchdog + periodic CC 123 (all-notes-off) |
| R10-05 | Variable tempo artifacts | **Medium** | Medium | P10-T1 | Continuous tempo update; beat-relative timing |

---

## Effort Estimates & Critical Paths

### Phase 7 — Controller Intelligence

| Task | Complexity | Dev-Days | Parallelizable With |
|------|-----------|----------|---------------------|
| P7-T1 (Registry) | XL | 15–20 | P7-T2 (after P0 complete) |
| P7-T2 (Profiles) | M | 5–7 | P7-T1 (after P0 complete) |
| P7-T3 (Auto-Map) | L | 8–12 | P7-T4 (after T1a + T2) |
| P7-T4 (Translation) | M | 5–7 | P7-T3 (after T2) |
| P7-T5 (Dynamic Remap) | M | 5–7 | P7-T6, T7 (after T3) |
| P7-T6 (Agent Config) | S | 2–3 | P7-T5, T7 (after T2) |
| P7-T7 (Visualization) | S | 2–3 | P7-T5, T6 (after T2) |
| **P7 Total** | | **42–59 days** | **Critical path: ~30 days** |

### Phase 8 — Creative Frontier

| Task | Complexity | Dev-Days | Parallelizable With |
|------|-----------|----------|---------------------|
| P8-T1 (Creativity Dials) | M | 5–7 | P8-T2 |
| P8-T2 (Multi-Critic) | XL | 15–20 | P8-T1 |
| P8-T3 (Quality Gate) | L | 5–7 | — (needs T2) |
| P8-T4 (Happy Accidents) | L | 7–10 | P8-T5 (after T1) |
| P8-T5 (Genre Bending) | L | 7–10 | P8-T4 (after P1) |
| P8-T6 (Surprise Mode) | M | 3–5 | — (needs T1, T4) |
| P8-T7 (Explanations) | M | 5–7 | P8-T8 |
| P8-T8 (Variations) | L | 7–10 | P8-T7 |
| P8-T9 (Metrics) | S | 2–3 | — (needs T2) |
| **P8 Total** | | **56–79 days** | **Critical path: ~40 days** |

### Phase 9 — Personalization

| Task | Complexity | Dev-Days | Parallelizable With |
|------|-----------|----------|---------------------|
| P9-T1 (Implicit Tracker) | L | 7–10 | — (root) |
| P9-T2 (Preference Model) | L | 7–10 | — (needs T1) |
| P9-T3 (Exploration) | M | 5–7 | P9-T4, T5, T6 (after T2) |
| P9-T4 (Producer Modes) | M | 5–7 | P9-T3, T5, T6 |
| P9-T5 (Defaults) | M | 5–7 | P9-T3, T4, T6 |
| P9-T6 (Introspection) | M | 5–7 | P9-T3, T4, T5 |
| P9-T7 (Persistence) | M | 5–7 | — (needs T2) |
| P9-T8 (Speculative Gen) | L | 7–10 | — (needs T2 + generators) |
| **P9 Total** | | **46–65 days** | **Critical path: ~35 days** |

### Phase 10 — Live Performance

| Task | Complexity | Dev-Days | Parallelizable With |
|------|-----------|----------|---------------------|
| P10-T1 (MIDI Analyzer) | XL | 15–20 | — (root) |
| P10-T2 (Harmonizer) | L | 7–10 | P10-T3, T5, T6 (after T1) |
| P10-T3 (Complement Gen) | XL | 15–20 | P10-T2, T5, T6 (after T1) |
| P10-T4 (Session Manager) | L | 5–7 | — (needs T1–T3) |
| P10-T5 (Energy Mapper) | M | 5–7 | P10-T2, T3, T6 |
| P10-T6 (Phrase Detection) | M | 5–7 | P10-T2, T3, T5 |
| P10-T7 (Controller Integ.) | M | 5–7 | — (needs P7-T2, T4) |
| P10-T8 (Session Recording) | L | 5–7 | — (needs T4, P3-T2) |
| **P10 Total** | | **62–85 days** | **Critical path: ~45 days** |

### Combined P7–P10

| Metric | Value |
|--------|-------|
| Total Tasks | 32 |
| Total Dev-Days (solo) | 206–288 days (41–58 weeks) |
| Total Dev-Days (3 devs, parallelized) | ~80–110 days (16–22 weeks) |
| Critical Path | P7-T1 → P7-T3 → P7-T5 runs parallel with P8 critical path → P10-T1 → P10-T3 → P10-T4 |

### Parallelization Strategy (3 Devs)

```
Dev A (Controller + Live):  P7-T1 → P7-T3 → P7-T5 → P10-T1 → P10-T2 → P10-T4
Dev B (Creative + Personal): P8-T2 → P8-T3 → P8-T4 → P8-T6 → P9-T1 → P9-T2 → P9-T7
Dev C (Support + Polish):    P7-T2 → P7-T4 → P7-T6/T7 → P8-T1 → P8-T5 → P8-T7/T8 →
                             P9-T3/T4/T5/T6 → P10-T3 → P10-T5/T6/T7/T8
```

---

## Appendices

### Appendix A: Anomalous target_control Values

These values appear in multiple `.xmm` files, always `type=0` (unmapped). NOT part of standard 0–244 parameter space.

| Value | Hex | Observed In | Hypothesis |
|-------|-----|-------------|------------|
| 4,086,032 | 0x3E5510 | MPD218, nanoKONTROL2 | Internal feature flag |
| 96,753,616 | 0x5C3D7D0 | MPD218, nanoKONTROL2 | MPC preference address |
| 132,638,976 | 0x7E7E500 | MPD218, nanoKONTROL2 | GUI state identifier |
| 292,467,232 | 0x116F2E20 | MPD218, nanoKONTROL2 | Plugin host reference |
| 1,143,453,048 | 0x4424AF78 | MPD218, nanoKONTROL2 | Unknown internal |
| 1,203,982,464 | 0x47C30C80 | MPD218, nanoKONTROL2 | Unknown internal |
| 1,672,134,317 | 0x63A8F2AD | MPD218, nanoKONTROL2 | Unknown internal |

**Recommendation**: Document but exclude from standard registry. Include in `internal-targets.json` for future analysis.

### Appendix B: Contract Reference Summary (C1–C15)

| # | Name | Location | Key Types |
|---|------|----------|-----------|
| C1 | SongState | TASK-DECOMP-P0-P2 | `SongState`, `SongStateL0/L1/L2` |
| C2 | EnrichedProgression | TASK-DECOMP-P0-P2 | `EnrichedProgression`, `EnrichedChord` |
| C3 | ParsedControllerMap | TASK-DECOMP-P0-P2 | `ControllerMap`, `PadMapping`, `KnobMapping` |
| C7 | EmbeddingIndex | TASK-DECOMP-P0-P2 | `VectorIndex`, `SearchResult` |
| C8 | GenreDNA | TASK-DECOMP-P0-P2 | `GenreDNAVector` |
| C9 | SynthPresetCatalog | TASK-DECOMP-P3-P5 | `PresetEntry`, `PresetCatalog` |
| C10 | EffectChain | TASK-DECOMP-P3-P5 | `EffectInstance`, `EffectChain` |
| C11 | ControllerMapping | TASK-DECOMP-P3-P5 | `ControlAssignment`, `AutomationRoute` |
| C12 | QualityScore | TASK-DECOMP-P3-P5 | `CriticReport`, `CriticFlag` |
| C13 | ComposerPipeline | TASK-DECOMP-P6 | `PipelineState`, `StageResult` |
| C14 | UserPreferences | **This document** | `UserPreferences`, `PreferenceSignal` |
| C15 | LivePerformanceState | **This document** | `LivePerformanceState`, `LiveAnalysis` |

---

*End of Phase 7–10 Engineering Specification.*
*Total: 32 tasks | 4 phases | 3 decisions resolved | 2 contracts defined | ~206–288 dev-days solo.*
*Project is now FULLY SPECIFIED across all 11 phases (P0–P10).*
````
