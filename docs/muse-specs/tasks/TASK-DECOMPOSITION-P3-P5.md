````markdown
# MUSE AI Music Platform — Task Decomposition: Phases 3–5

## Complete Engineering Specification

> **Generated**: February 8, 2026
> **Scope**: Phase 3 (Rhythm Engine), Phase 4 (Sound Oracle), Phase 5 (MIDI Bridge)
> **SDK**: `@github/copilot-sdk` — CLI-based JSON-RPC
> **Architecture**: Continues from P0–P2 contracts (C1–C8). Adds contracts C9–C12.
> **Prerequisite**: TASK-DECOMPOSITION-P0-P2.md (all contracts C1–C8 are assumed stable).

---

## New Cross-Phase Contracts (C9–C12)

These contracts extend the C1–C8 definitions from P0–P2. All prior contracts remain immutable.

---

### Contract C9: SynthPresetCatalog

Complete typed catalog of all synth presets discoverable in MPC Beats.

```typescript
// ━━━ C9: SynthPresetCatalog ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * Complete inventory of synth presets across all engines installed in MPC Beats.
 * Built at scan-time (P0-T3), enriched with timbral descriptions (P2-T2),
 * and consumed by the Sound Oracle (Phase 4) for recommendation.
 *
 * Persisted to `data/preset-catalog.json`.
 */
export interface SynthPresetCatalog {
  /** ISO 8601 build timestamp. */
  builtAt: string;

  /** MPC Beats installation path from which this catalog was scanned. */
  mpcBeatsPath: string;

  /** Total preset count across all engines. Expected: ~450+ for stock install. */
  totalPresets: number;

  /** Per-engine preset collections. Keyed by engine display name. */
  engines: Record<string, EnginePresetCollection>;

  /**
   * Inverted timbral index: adjective → preset IDs.
   * Built from preset description analysis.
   * e.g. "warm" → ["tubesynth:168", "tubesynth:169", "velvet:3", ...]
   */
  timbralIndex: Record<string, string[]>;

  /**
   * Genre affinity index: genre → ranked preset IDs.
   * Derived from genre-sound map (Phase 4 timbral ontology).
   * e.g. "neo_soul" → ["velvet:0", "electric:2", "tubesynth:168", ...]
   */
  genreIndex: Record<string, string[]>;

  /**
   * Spectral profile estimates per preset category.
   * Used by frequency masking analysis (P4-T3).
   */
  spectralProfiles: Record<PresetSpectralCategory, SpectralProfile>;
}

/** All presets for a single synth engine. */
export interface EnginePresetCollection {
  /** Engine display name. e.g. "TubeSynth", "Bassline", "DB-33". */
  engineName: string;

  /** Manufacturer. e.g. "AIR Music Technology", "Akai Professional". */
  manufacturer: string;

  /** Engine type classifier. */
  engineType: 'synth' | 'drum' | 'vst' | 'effect';

  /** Installation directory path. */
  directoryPath: string;

  /** Total presets in this engine. */
  presetCount: number;

  /** Category breakdown. e.g. { Pad: 68, Lead: 50, Bass: 65, ... }. */
  categoryBreakdown: Record<string, number>;

  /** All presets in this engine. */
  presets: PresetEntry[];
}

/** A single preset entry with its metadata and timbral description. */
export interface PresetEntry {
  /** Unique preset ID. Format: "{engine}:{index}". e.g. "tubesynth:168". */
  id: string;

  /** Zero-based preset index within the engine bank. */
  index: number;

  /** Preset display name. e.g. "Warm Pad". */
  name: string;

  /** Category from filename prefix. e.g. "Pad", "Lead", "Bass", "Synth", "FX". */
  category: string;

  /** Full filename without extension. e.g. "169-Pad-Warm Pad". */
  fullName: string;

  /** Timbral description (authored in P2-T2). 20–60 words. */
  description: string;

  /** Timbral adjective tags. Lowercase. e.g. ["warm", "lush", "sustained"]. */
  timbralTags: string[];

  /** Genre affinity tags. e.g. ["neo_soul", "ambient", "gospel"]. */
  genreTags: string[];

  /** Estimated primary frequency range. */
  spectralCategory: PresetSpectralCategory;

  /** Engine reference for quick lookup. */
  engine: string;
}

/** Spectral category — coarse frequency range classification. */
export type PresetSpectralCategory =
  | 'sub'          // 20-80Hz: sub basses, 808s
  | 'bass'         // 60-300Hz: bass synths, bass guitars
  | 'low_mid'      // 200-800Hz: warm pads, organ bass register
  | 'mid'          // 500-4kHz: leads, plucks, pianos, organs
  | 'full_range'   // 100Hz-8kHz: pads, strings, supersaw
  | 'high'         // 2-16kHz: bells, sparkle FX
  | 'percussion'   // transient-based: clicks, hits, noise
  | 'fx';          // non-tonal: risers, sweeps, noise

/** Estimated spectral energy distribution for a preset category. */
export interface SpectralProfile {
  /** Fundamental frequency range [low, high] in Hz. */
  fundamentalRange: [number, number];

  /** Harmonic content descriptor. */
  harmonicContent: 'sine' | 'triangle' | 'saw' | 'square' | 'noise' | 'complex';

  /** Spectral rolloff rate in dB/octave. e.g. -6 for saw, -12 for filtered saw. */
  rolloffRate: number;

  /** Whether the preset has significant transient content. */
  hasTransient: boolean;

  /** Estimated reverb tail contribution (from built-in FX). 0 = dry, 1 = very wet. */
  reverbTail: number;
}
```

---

### Contract C10: EffectChain

Typed effect chain specification with signal-flow ordering and parameter constraints.

```typescript
// ━━━ C10: EffectChain ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * A complete effect chain with validated signal-flow ordering.
 * Extends the per-track EffectInstance[] from C1 with chain-level
 * metadata, ordering validation, and genre context.
 *
 * Generated by Phase 4's effect chain generator (P4-T2).
 * Consumed by SongState (C1 Track.effectsChain) and Phase 7 (knob mapping).
 */
export interface EffectChain {
  /** Unique chain ID (UUID v4). */
  readonly id: string;

  /** Human-readable name. e.g. "Neo Soul Pad Chain", "Trap 808 Chain". */
  name: string;

  /** Design intent description. e.g. "Warm, spacious pad with vintage character". */
  intent: string;

  /** Target track role this chain was designed for. */
  targetRole: TrackRole;

  /** Genre context. */
  genre: string;

  /** Ordered effect slots. Index 0 = first in signal path. */
  slots: EffectSlot[];

  /** Total estimated latency in samples (sum of per-effect latency). */
  estimatedLatencySamples: number;

  /** Signal-flow stage validation result. */
  signalFlowValid: boolean;

  /** Per-slot parameter values calculated from tempo/genre (e.g. synced delay). */
  tempoSyncedParams: TempoSyncedParam[];
}

/**
 * A single effect slot in the chain with its stage classification.
 * Wraps EffectInstance (C1) with signal-flow metadata.
 */
export interface EffectSlot {
  /** Position in chain (0-based). */
  index: number;

  /** The effect instance (plugin + parameters). From C1. */
  effect: EffectInstance;

  /** Signal-flow stage. Chain ordering MUST be non-decreasing by stage ordinal. */
  stage: SignalFlowStage;

  /** Whether this slot is optional (can be removed without breaking the chain). */
  optional: boolean;

  /** Purpose of this effect in the chain. */
  purpose: string;

  /** Automatable parameters (subset of effect.parameters suitable for CC mapping). */
  automatableParams: string[];
}

/**
 * Signal flow stages in correct physics ordering.
 * Ordinal values enforce ordering: a stage-2 effect must never precede a stage-1.
 *
 * Based on blueprint Section 6:
 * 1. Source shaping → 2. Dynamics → 3. Time-based →
 * 4. Modulation → 5. Character → 6. Master
 */
export enum SignalFlowStage {
  SOURCE_SHAPING = 1,     // EQ, Filter, Distortion
  DYNAMICS = 2,           // Compressor, Transient Shaper, Gate
  TIME_BASED = 3,         // Delay, Reverb
  MODULATION = 4,         // Chorus, Flanger, Phaser, Ensemble
  CHARACTER = 5,          // MPC3000, MPC60, SP1200, Lo-Fi
  MASTER = 6,             // Maximizer, Limiter, Stereo Width, Channel Strip
}

/** A parameter whose value is derived from BPM and musical subdivision. */
export interface TempoSyncedParam {
  /** Effect slot index in the chain. */
  slotIndex: number;

  /** Parameter name within the effect. */
  paramName: string;

  /** Musical subdivision used for calculation. */
  subdivision: MusicalSubdivision;

  /** Computed value in milliseconds (for delays) or Hz (for LFOs). */
  computedValue: number;

  /** Unit of the computed value. */
  unit: 'ms' | 'hz' | 'bpm';
}

export type MusicalSubdivision =
  | '1/1' | '1/2' | '1/2d' | '1/2t'
  | '1/4' | '1/4d' | '1/4t'
  | '1/8' | '1/8d' | '1/8t'
  | '1/16' | '1/16d' | '1/16t'
  | '1/32' | '1/32d' | '1/32t'
  | '1/64';

/**
 * Validates that an effect chain respects signal-flow physics.
 * Returns violations (if any).
 */
export function validateSignalFlow(chain: EffectSlot[]): SignalFlowViolation[];

export interface SignalFlowViolation {
  /** Index of the offending slot. */
  slotIndex: number;
  /** The slot's stage. */
  stage: SignalFlowStage;
  /** The previous slot's stage (which is higher — violation). */
  precedingStage: SignalFlowStage;
  /** Human-readable explanation. */
  message: string;
}
```

---

### Contract C11: ControllerMapping

Virtual MIDI controller mapping for the "MPC AI Controller" and hardware mapping translation.

```typescript
// ━━━ C11: ControllerMapping ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * Complete mapping specification for a virtual or physical MIDI controller
 * as it interfaces with MPC Beats.
 *
 * Generated by Phase 5 (.xmm generator) and Phase 7 (controller intelligence).
 * Consumed by the CC automation system and the controller agent.
 */
export interface ControllerMapping {
  /** Controller identifier. e.g. "MPC AI Controller", "MPK mini 3". */
  controllerName: string;

  /** Manufacturer. "MUSE" for the virtual controller. */
  manufacturer: string;

  /** Whether this is the AI virtual controller or a physical device. */
  isVirtual: boolean;

  /** Virtual MIDI port name. e.g. "MPC AI Controller". */
  portName: string;

  /** All control assignments. */
  assignments: ControlAssignment[];

  /** Parameter automation routes — maps CC numbers to synth/effect parameters. */
  automationRoutes: AutomationRoute[];

  /** .xmm file path (if generated/loaded from file). */
  xmmPath?: string;

  /** Last-modified timestamp. */
  updatedAt: string;
}

/**
 * A single control → MPC target assignment.
 * Maps a physical/virtual control (pad, knob, slider, button) to an
 * MPC Beats internal function via Target_control index.
 */
export interface ControlAssignment {
  /** Human-readable control name. e.g. "Pad 1", "Knob 3", "Play Button". */
  controlName: string;

  /** Physical control type. */
  controlType: 'pad' | 'knob' | 'slider' | 'button' | 'encoder';

  /** MIDI message type. */
  midiType: 'note' | 'cc' | 'program_change';

  /** MIDI channel (0-15). */
  midiChannel: number;

  /** MIDI data1 value: note number for pads, CC number for knobs. */
  midiData1: number;

  /** MPC internal Target_control index. */
  targetControl: number;

  /** Resolved target name (if known from reverse-engineering). */
  targetName?: string;

  /** Target category. */
  targetCategory: 'pad' | 'transport' | 'mixer' | 'plugin_param' | 'navigation' | 'unknown';

  /** Value range for continuous controls. */
  valueRange?: { min: number; max: number };

  /** Whether the mapping is bidirectional (MPC sends feedback). */
  bidirectional: boolean;
}

/**
 * An automation route connecting a MIDI CC to a specific synth or effect parameter.
 * This is the "smart mapping" layer — beyond raw MIDI.
 */
export interface AutomationRoute {
  /** Source CC number (0-127). */
  cc: number;

  /** Source MIDI channel (0-15). */
  channel: number;

  /** Target track ID in SongState. */
  trackId: string;

  /** Target: either a synth parameter or an effect parameter. */
  target: AutomationTarget;

  /** Curve type for value scaling. */
  curve: 'linear' | 'logarithmic' | 'exponential' | 's_curve';

  /** Value range mapping: CC 0-127 → parameter min-max. */
  inputRange: [number, number];
  outputRange: [number, number];

  /** Human-readable description. e.g. "Knob 1 → TubeSynth Filter Cutoff". */
  description: string;
}

/** Target of a CC automation route. */
export type AutomationTarget =
  | { type: 'synth_param'; paramName: string }
  | { type: 'effect_param'; effectSlotIndex: number; paramName: string }
  | { type: 'mixer'; param: 'volume' | 'pan' | 'send1' | 'send2' }
  | { type: 'transport'; action: 'play' | 'stop' | 'record' | 'tempo' };
```

---

### Contract C12: QualityScore

Multi-dimensional quality assessment used by the critic system (Phase 8) and inline validation.

```typescript
// ━━━ C12: QualityScore ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * Multi-dimensional quality score for any musical artifact.
 * Implements the "multi-critic architecture" from the blueprint (Section 11).
 *
 * Used by Phase 8 (Creative Frontier) for quality gates, and by Phases 3-6
 * for inline validation during generation.
 *
 * Scoring convention:
 *   0.0 = worst possible
 *   0.5 = acceptable minimum
 *   0.7 = target average
 *   1.0 = exemplary
 *
 * Hard constraints (from blueprint consensus):
 *   - No axis below 0.5 (hard floor)
 *   - Average across all axes ≥ 0.7
 *   - Vibe score ≥ 0.5 (hard gate — veto power)
 */
export interface QualityScore {
  /** Unique assessment ID (UUID v4). */
  readonly id: string;

  /** What was scored. */
  subject: QualitySubject;

  /** ISO 8601 timestamp of assessment. */
  assessedAt: string;

  /**
   * Harmony Critic: voice leading, key coherence, progression sophistication,
   * chord-to-genre appropriateness.
   */
  harmony: AxisScore;

  /**
   * Rhythm Critic: groove consistency, swing feel, density appropriateness,
   * humanization quality, drum-to-bass alignment.
   */
  rhythm: AxisScore;

  /**
   * Arrangement/Mix Critic: frequency allocation, stereo field, dynamic range,
   * section contrast, energy arc coherence.
   */
  arrangement: AxisScore;

  /**
   * Vibe Critic (meta): overall emotional coherence — do the parts work as a whole?
   * Has HARD VETO POWER: if vibe < 0.5, the entire artifact fails regardless of
   * other scores. "A technically perfect arrangement that doesn't vibe is worse
   * than a sloppy one that does." — GPT
   */
  vibe: AxisScore;

  /** Weighted composite score. */
  composite: number;

  /** Whether this artifact passes all quality gates. */
  passes: boolean;

  /** If failed, which gates were violated. */
  violations: QualityViolation[];

  /** Actionable recommendations to improve the score. */
  recommendations: QualityRecommendation[];

  /** Number of regeneration attempts so far (max 3 per blueprint). */
  regenerationCount: number;
}

/** A single quality axis with score, confidence, and diagnostics. */
export interface AxisScore {
  /** Numeric score. 0.0–1.0. */
  value: number;

  /** Confidence in this score. 0.0 = uncertain, 1.0 = definitive.
   *  Low confidence when insufficient data (e.g. rhythm score for a pad-only track). */
  confidence: number;

  /** Per-criterion breakdown within this axis. */
  criteria: CriterionScore[];

  /** Prose diagnosis from the critic. */
  diagnosis: string;
}

/** A single scored criterion within a quality axis. */
export interface CriterionScore {
  /** Criterion name. e.g. "voice_leading_smoothness", "kick_snare_alignment". */
  name: string;

  /** Numeric score. 0.0–1.0. */
  value: number;

  /** Weight of this criterion within its axis. Sum of weights per axis = 1.0. */
  weight: number;

  /** Brief explanation. */
  note: string;
}

/** What was scored — discriminated union. */
export type QualitySubject =
  | { type: 'progression'; chords: string[]; key: string }
  | { type: 'midi_track'; trackRole: TrackRole; barCount: number }
  | { type: 'effect_chain'; chainId: string; targetRole: TrackRole }
  | { type: 'arrangement'; sectionCount: number; totalBars: number }
  | { type: 'full_song'; songStateVersion: string };

/** A quality gate violation. */
export interface QualityViolation {
  /** Which gate was violated. */
  gate: 'axis_floor' | 'average_threshold' | 'vibe_veto';

  /** Which axis (if applicable). */
  axis?: 'harmony' | 'rhythm' | 'arrangement' | 'vibe';

  /** The score that violated the gate. */
  score: number;

  /** The threshold that was not met. */
  threshold: number;

  /** Explanation. */
  message: string;
}

/** Actionable recommendation to improve a quality score. */
export interface QualityRecommendation {
  /** Which axis this targets. */
  axis: 'harmony' | 'rhythm' | 'arrangement' | 'vibe';

  /** Priority: higher = more impactful on composite score. */
  priority: 'high' | 'medium' | 'low';

  /** Specific action to take. */
  action: string;

  /** Estimated score improvement if action is taken. */
  estimatedImprovement: number;

  /** Which Phase 3-5 tool would implement this. */
  suggestedTool?: string;
}

/**
 * Quality gate configuration. Per-genre thresholds may vary.
 * Defaults match blueprint consensus (Gemini's stricter thresholds).
 */
export interface QualityGateConfig {
  /** Minimum score for any individual axis. Default: 0.5. */
  axisFloor: number;

  /** Minimum average across all four axes. Default: 0.7. */
  averageThreshold: number;

  /** Minimum vibe score (hard veto). Default: 0.5. */
  vibeFloor: number;

  /** Maximum regeneration attempts before presenting best effort. Default: 3. */
  maxRegenerations: number;

  /** Axis weights for composite calculation. Must sum to 1.0. */
  axisWeights: {
    harmony: number;    // default: 0.25
    rhythm: number;     // default: 0.25
    arrangement: number; // default: 0.25
    vibe: number;       // default: 0.25
  };
}

/** Default quality gate configuration. */
export const DEFAULT_QUALITY_GATES: QualityGateConfig = {
  axisFloor: 0.5,
  averageThreshold: 0.7,
  vibeFloor: 0.5,
  maxRegenerations: 3,
  axisWeights: { harmony: 0.25, rhythm: 0.25, arrangement: 0.25, vibe: 0.25 },
};

/**
 * Compute the composite score and check all gates.
 */
export function evaluateQuality(
  scores: { harmony: AxisScore; rhythm: AxisScore; arrangement: AxisScore; vibe: AxisScore },
  config?: QualityGateConfig
): Pick<QualityScore, 'composite' | 'passes' | 'violations'>;
```

---

## PHASE 3 — RHYTHM ENGINE

**Goal**: MIDI generation, humanization, arp manipulation, groove templates. After Phase 3, MUSE generates rhythmically correct, humanized multi-track MIDI files.

**Task Count**: 8
**Estimated Effort**: 5–6 dev-weeks

---

### P3-T1: MIDI Binary Parser (SMF Reader)

| Field | Value |
|---|---|
| **ID** | P3-T1 |
| **Name** | MIDI Binary Parser (Standard MIDI File Reader) |
| **Complexity** | M |
| **Description** | Parse Standard MIDI File (SMF) binary format into the `MidiNoteEvent[]` and `MidiFileHeader` structures defined in C3. Must handle Format 0 (single-track) and Format 1 (multi-track). Extracts note-on/note-off pairs, CC events, tempo changes, time signature meta-events, and track names. Uses variable-length quantity (VLQ) decoding for delta-times. Converts delta-times to absolute ticks. Handles running status (a MIDI optimization where repeated status bytes are omitted). |
| **Dependencies** | P0-T1 (project scaffold) |
| **Interfaces** | **Input**: `function parseMidiFile(filePath: string): Promise<ParsedMidiFile>` — **Output**: `interface ParsedMidiFile { header: MidiFileHeader; tracks: MidiTrack[]; tempoMap: TempoEvent[]; timeSignatures: TimeSignatureEvent[]; }` — `interface MidiTrack { name?: string; channel?: number; events: MidiEvent[]; notes: MidiNoteEvent[]; }` — `type MidiEvent = NoteOnEvent \| NoteOffEvent \| CCEvent \| ProgramChangeEvent \| TempoEvent \| TimeSignatureEvent \| TrackNameEvent` — `interface TempoEvent { tick: number; microsecondsPerBeat: number; bpm: number; }` — `interface TimeSignatureEvent { tick: number; numerator: number; denominator: number; }` |
| **Testing** | Parse all 80 arp `.mid` files — zero failures. Verify `044-Melodic-Lead Hip Hop 01.mid`: correct note count, pitch range, tick positions. Round-trip: parse → write (P3-T2) → re-parse → diff notes arrays — zero deltas. VLQ edge cases: values at 0, 127, 128, 16383, 16384. Running status: synthesize a file with running status, parse correctly. Format 0 vs Format 1: handle both. Corrupted file: return descriptive error, no crash. |
| **Risk** | Running status handling is the primary source of parser bugs in MIDI implementations. Some MPC Beats files may use non-standard meta-events — log and skip gracefully. The `midi-file` npm package can serve as a reference implementation for validation, but building a custom parser gives full control over the C3 contract types. |

---

### P3-T2: MIDI Binary Writer (SMF Writer)

| Field | Value |
|---|---|
| **ID** | P3-T2 |
| **Name** | MIDI Binary Writer (Standard MIDI File Writer) |
| **Complexity** | M |
| **Description** | Generate valid Standard MIDI File Format 1 binary output from internal `MidiNoteEvent[]` representations. Produces tempo track (track 0) with Set Tempo and Time Signature meta-events, plus one or more note tracks. Encodes note-on/note-off pairs with correct VLQ delta-times. Supports multi-channel output, CC events, and Program Change events. |
| **Dependencies** | P3-T1 (shares types, enables round-trip testing) |
| **Interfaces** | **Input**: `function writeMidiFile(spec: MidiWriteSpec): Promise<string>` — `interface MidiWriteSpec { outputPath: string; ticksPerBeat?: number; tempo: number; timeSignature?: [number, number]; tracks: MidiWriteTrack[]; }` — `interface MidiWriteTrack { name: string; channel: number; notes: MidiNoteEvent[]; ccEvents?: MidiCCEvent[]; programChange?: number; }` — `interface MidiCCEvent { tick: number; channel: number; controller: number; value: number; }` — **Output**: Returns absolute path to written `.mid` file. |
| **Testing** | Write C major scale (quarter notes, 120 BPM, 480 PPQ) → read back with P3-T1 → verify 8 notes, correct pitches [60,62,64,65,67,69,71,72], correct tick spacing (480 ticks each). Write polyphonic chord (C, E, G simultaneously) → verify all 3 notes at same tick. Write multi-track file (drums ch10 + bass ch2) → verify tracks separated. Open in external MIDI viewer (e.g., MuseScore, MIDI Monitor). File size: 8-note file should be < 500 bytes. CC events: write CC74 ramp → read back → verify values. Empty track: handled gracefully. |
| **Risk** | VLQ encoding for large delta-times (>16383 ticks) must handle multi-byte encoding correctly. End-of-track meta-event (0xFF 0x2F 0x00) must terminate every track. Some DAWs are strict about SMF compliance — test imports into MPC Beats, Ableton, and a standards-compliant reference parser. |

---

### P3-T3: Velocity Curve Engine

| Field | Value |
|---|---|
| **ID** | P3-T3 |
| **Name** | Velocity Curve Engine |
| **Complexity** | M |
| **Description** | Generate musically-meaningful velocity profiles for any MIDI part. Implements metric accent patterns (strong/weak beats), phrase-level contour shaping (crescendo, diminuendo, arch), genre-specific velocity conventions, and stochastic human variance layered on top. Never produces flat velocity — every note's velocity is determined by its metric position, phrase position, genre, and a Gaussian random component. |
| **Dependencies** | P0-T1 |
| **Interfaces** | **Input**: `function generateVelocityCurve(request: VelocityCurveRequest): VelocityProfile` — `interface VelocityCurveRequest { noteCount: number; subdivision: number; timeSignature: [number, number]; genre: GenreId; phraseLength: number; contour: 'flat' \| 'crescendo' \| 'diminuendo' \| 'arch' \| 'valley' \| 'wave'; humanVariance: number; accentPattern?: number[]; }` — **Output**: `interface VelocityProfile { velocities: number[]; accentMap: number[]; phraseContour: number[]; humanOffsets: number[]; }` — Velocity clamped to [1, 127]. Accent patterns per time signature: 4/4 quarter = [1.0, 0.5, 0.8, 0.5]; 4/4 eighth = [1.0, 0.3, 0.5, 0.3, 0.8, 0.3, 0.5, 0.3]; 3/4 = [1.0, 0.5, 0.5]; 6/8 = [1.0, 0.3, 0.5, 0.8, 0.3, 0.5]. Genre variance (sigma): EDM σ=3, pop σ=5, jazz σ=10, gospel σ=8. |
| **Testing** | 4/4 eighth notes: beat 1 velocity > beat 2 velocity. Crescendo over 16 notes: last note velocity > first note velocity. Arch: peak at midpoint. Human variance: generate 1000 profiles with σ=10, verify stddev of velocity values ≈ 10 (±2). Genre difference: jazz profile has higher stddev than EDM. All velocities in [1, 127]. Zero-length: handled gracefully. |
| **Risk** | Metric accent patterns must align with actual note positions (not just sequential index). If notes are syncopated, the accent pattern must be applied relative to the beat grid (tick positions) rather than the note array index. This requires tick-position-aware velocity assignment. |

---

### P3-T4: Humanization Engine

| Field | Value |
|---|---|
| **ID** | P3-T4 |
| **Name** | Humanization Engine |
| **Complexity** | L |
| **Description** | Transform mechanical MIDI data into human-feeling performances. Applies four layers simultaneously: (1) velocity variation via P3-T3 velocity curves, (2) micro-timing offsets from the grid (Gaussian, σ genre-dependent), (3) swing transformation (delay offbeat subdivisions), (4) structural additions (ghost notes, flams, drags). All parameters are tunable per-track and per-genre. Implements the complete humanization framework from blueprint Section 5. |
| **Dependencies** | P3-T3 (velocity curves), P0-T1 |
| **Interfaces** | **Input**: `function humanize(events: MidiNoteEvent[], config: HumanizationConfig): MidiNoteEvent[]` — `interface HumanizationConfig { velocityVariance: number; accentPattern?: number[]; swingAmount: number; swingSubdivision: 8 \| 16; timingVariance: number; globalOffset: number; ghostNotes: boolean; ghostProbability: number; ghostVelocityRange: [number, number]; flamProbability: number; flamOffsetTicks: number; instrumentOffsets?: Record<number, number>; groove?: GroovePresetName; }` — `type GroovePresetName = 'straight' \| 'swing_8' \| 'swing_16' \| 'dilla' \| 'behind_beat' \| 'ahead_beat' \| 'uk_garage' \| 'bossa' \| 'boom_bap' \| 'afrobeat_12_8'` — **Output**: new `MidiNoteEvent[]` (original not mutated). Ghost notes appended with `ghostNote: true` tag via subtype. Flams create duplicate notes offset by `flamOffsetTicks` with velocity at 60% of original. |
| **Testing** | Straight 8th hi-hat with swing=0.67: verify offbeat notes delayed by `0.67 × (tripletTick - straightTick)` ticks. Timing variance σ=20ms at 480 PPQ 120 BPM: verify note tick offsets have stddev ≈ 16 ticks (20ms × 480/500). Ghost notes: humanize 16-bar pattern with ghostProbability=0.2, count ghost notes, verify within statistical range (expected ± 2σ). Dilla groove: non-uniform swing + velocity emphasis on offbeats — verify offbeat average velocity > onbeat average. Flam: verify duplicate note exists at -flamOffsetTicks with 60% velocity. Global offset: all notes shifted by globalOffset ticks. Original array unchanged (immutability). |
| **Risk** | Swing + timing variance compound — heavily swung notes with high timing variance can push notes past the next grid point, creating unintended rhythmic chaos. Clamp total offset so notes cannot cross beat boundaries (unless intentional "Dilla" mode). Ghost note insertion in polyphonic parts may create unplayable density — limit ghost probability to monophonic events. |

---

### P3-T5: Ghost Note Generator

| Field | Value |
|---|---|
| **ID** | P3-T5 |
| **Name** | Ghost Note Generator |
| **Complexity** | S |
| **Description** | Specialized ghost note insertion for drum parts. Fills empty 32nd-note positions with low-velocity hits contextually appropriate to the instrument and genre. Snare ghosts between backbeats, hi-hat ghosts for extra shuffle, kick ghosts for syncopation depth. Implements blueprint Section 5 ghost note spec: 20% probability, velocity 20–35 for general percussion; velocity 25–40 for snare ghosts between backbeats. |
| **Dependencies** | P3-T1 (note event types) |
| **Interfaces** | **Input**: `function insertGhostNotes(events: MidiNoteEvent[], config: GhostNoteConfig): MidiNoteEvent[]` — `interface GhostNoteConfig { instrument: 'snare' \| 'hihat' \| 'kick' \| 'general'; probability: number; velocityRange: [number, number]; gridResolution: 32; avoidPositions?: number[]; maxConsecutive?: number; }` — **Output**: new `MidiNoteEvent[]` with ghost notes inserted. |
| **Testing** | 8-bar pattern with snare on 2 and 4: ghost notes appear between backbeats, velocity 25–40. Hi-hat ghosts fill 32nd subdivisions at 20% density. No ghost note at positions already occupied. No more than `maxConsecutive` (default 2) ghost notes in a row. Statistical: over 100 runs, ghost density converges to configured probability ±5%. |
| **Risk** | Low. Self-contained algorithm. Only risk: at high tempos (>160 BPM), 32nd-note ghost notes become extremely fast (< 47ms apart). Consider disabling ghosts at 32nd resolution above 150 BPM and falling back to 16th. |

---

### P3-T6: Groove Template System

| Field | Value |
|---|---|
| **ID** | P3-T6 |
| **Name** | Groove Template System |
| **Complexity** | S |
| **Description** | Define, store, and apply reusable groove templates that encode genre-specific rhythmic feel as abstract timing and velocity modifier grids. Each template specifies per-subdivision timing offsets (ms) and velocity multipliers. Templates are JSON-serializable and stored in `skills/rhythm/groove-templates.json`. Application is equivalent to calling the humanization engine (P3-T4) with template-derived parameters. |
| **Dependencies** | P3-T4 (humanization engine for application) |
| **Interfaces** | **Input**: `function applyGrooveTemplate(events: MidiNoteEvent[], template: GrooveTemplate, ticksPerBeat: number): MidiNoteEvent[]` — `interface GrooveTemplate { name: string; description: string; genre: string; swingAmount: number; swingSubdivision: 8 \| 16; timingGrid: number[]; velocityGrid: number[]; globalOffset: number; }` — **Output**: groove-applied `MidiNoteEvent[]`. Pre-defined templates: `straight_16` (modern pop/EDM), `swing_8_light` (bossa, light jazz), `swing_8_heavy` (hard bop, blues), `swing_16_trap` (modern trap hi-hats), `dilla` (neo-soul, lo-fi), `uk_garage_2step` (UK garage), `boom_bap` (90s hip-hop), `afrobeat_12_8` (Afrobeats compound meter). |
| **Testing** | Apply `dilla` to straight 16th notes: timing offsets non-uniform, velocity emphasis on offbeats. Apply `swing_8_heavy` to 8th notes: offbeats delayed by ~67% of an 8th note. Apply `straight_16`: output ≈ input (minimal change). Round-trip serialize/deserialize all templates — zero data loss. All templates have non-empty `description` and `genre` fields. |
| **Risk** | Low. Data-driven task. Risk: groove templates authored without audio validation may feel wrong when actually heard. Mitigation: base timing values on published MPC60/SP1200 swing values and academic references on groove analysis. |

---

### P3-T7: Arp Pattern Analyzer & Transformer

| Field | Value |
|---|---|
| **ID** | P3-T7 |
| **Name** | Arp Pattern Analyzer & Transformer |
| **Complexity** | L |
| **Description** | Analyze the 80 arp patterns from the MPC Beats library to extract rhythmic DNA (density, swing, grid, velocity shape, interval distribution, polyphony). Then provide transformation functions: transpose, fit-to-chords, time-stretch, reverse, mirror, density-scale. The analyzer populates `ParsedArpPattern.analysis` (C3 contract). The transformer is the core of the `transform_arp` tool. Fit-to-chords is the most complex transform: re-pitch arp notes to fit a different chord progression while preserving rhythmic timing. |
| **Dependencies** | P3-T1 (MIDI parser for reading arps), P1-T2 (chord parser for fit-to-chords) |
| **Interfaces** | **Input — Analysis**: `function analyzeArpPattern(parsed: ParsedMidiFile, fileName: string): ParsedArpPattern` (C3 contract). **Input — Transform**: `function transformArp(pattern: ParsedArpPattern, transform: ArpTransform): MidiNoteEvent[]` — `interface ArpTransform { transpose?: number; fitToChords?: RawChord[]; timeStretch?: number; reverse?: boolean; mirror?: boolean; densityScale?: number; velocityScale?: number; channelRemap?: number; }` — **Output**: transformed `MidiNoteEvent[]` + optional `.mid` file via P3-T2. |
| **Testing** | **Analysis**: Analyze all 80 arps. Verify categorization matches filename: indices 0–37 → Chord, 38–55 → Melodic, 56–79 → Bass. Verify density > 3 for "Dance" patterns, < 2 for "Chill Out". Verify `rhythmicGrid` detection: most patterns should be 8 or 16. **Transform**: Transpose +5 then -5 → original notes restored. Fit-to-chords with Godly progression → all output notes are chord tones. Time-stretch ×2 → duration doubles. Reverse → first note tick = 0, last note was original tick 0. Mirror → pitch contour inverted around median. Density-scale 0.5 → ~50% note reduction (first beat of each beat preserved). |
| **Risk** | Fit-to-chords with polyphonic arp patterns is complex: multiple simultaneous notes must all map to valid chord tones. When target chord has fewer notes than arp polyphony, use modular wrapping (cycle through chord tones). When arp has bass notes in a different octave, preserve octave relationships. Edge case: chromatic passing tones in melodic arps — should these map to nearest chord tone or preserve intervallic relationship? Decision: map to nearest chord tone (simpler, more consonant result). |

---

### P3-T8: Rhythm Agent Configuration

| Field | Value |
|---|---|
| **ID** | P3-T8 |
| **Name** | Rhythm Agent Configuration & Skill Directory |
| **Complexity** | S |
| **Description** | Create the `skills/rhythm/` directory with SKILL.md, humanization-rules.md, and groove-templates.json. Define the Rhythm `customAgent` configuration for the SDK. The agent prompt encodes per-genre drumming conventions, humanization philosophy ("never flat velocity"), awareness of Channel 10 GM drum map, and reference to available groove templates. Register all Phase 3 tools with the agent. |
| **Dependencies** | P3-T1 through P3-T7 (all content available) |
| **Interfaces** | **Agent config**: `{ name: 'rhythm', displayName: 'Rhythm Agent', description: 'Beat, groove, and arp pattern specialist. Generates drums, bass, melody. Applies humanization and genre-specific groove.', prompt: buildRhythmAgentPrompt(), tools: ['generate_midi', 'humanize_midi', 'transform_arp', 'read_arp_pattern', 'set_groove', 'write_midi_file'], infer: true }`. **Files**: `skills/rhythm/SKILL.md`, `skills/rhythm/humanization-rules.md` (~1500 tokens: per-genre swing conventions, ghost note rules, micro-timing ranges), `skills/rhythm/groove-templates.json` (all GrooveTemplate definitions). **Tools registered**: `generate_midi` (params: `{ type: 'drums'\|'bass'\|'melody'\|'chords', genre, tempo, bars, config: object }`), `humanize_midi` (params: `{ filePath, groove?, config? }`), `transform_arp` (params: `{ arpIndex \| filePath, transforms: ArpTransform }`), `set_groove` (params: `{ trackId, template: GroovePresetName }`), `write_midi_file` (params: `MidiWriteSpec`). |
| **Testing** | End-to-end: send "Create an 8-bar boom-bap drum pattern at 90 BPM" → verify routes to Rhythm agent → calls `generate_midi` with type='drums' → verify .mid file created → parse and verify kick on beats 1 & 3-and, snare on 2 & 4. Send "Add swing to the hi-hats" → verify calls `humanize_midi` or `set_groove`. Skill directory: verify SKILL.md is valid markdown, groove-templates.json is valid JSON with ≥8 templates. Agent prompt: verify ≤ 3000 tokens. |
| **Risk** | Agent routing ambiguity between Rhythm and the future Composer agent for complex requests. Rhythm agent handles single-instrument generation; Composer orchestrates multi-track. The `description` field must clearly differentiate. |

---

## PHASE 4 — SOUND ORACLE

**Goal**: Preset recommendation, effect chain generation, timbral ontology, frequency masking analysis. After Phase 4, MUSE recommends specific presets, designs effect chains with parameter values, and detects mix issues — all structurally, without audio.

**Task Count**: 8
**Estimated Effort**: 4–5 dev-weeks

---

### P4-T1: Plugin Scanner & Preset Catalog Builder

| Field | Value |
|---|---|
| **ID** | P4-T1 |
| **Name** | Plugin Scanner & Preset Catalog Builder |
| **Complexity** | M |
| **Description** | Deep-scan the MPC Beats `Synths/` directory tree to build the complete `SynthPresetCatalog` (C9 contract). Enumerates every synth engine, counts presets per category, builds the inverted timbral index and genre affinity index. Extends P0-T3's scanner with per-preset granularity. Scans: AIR synths (TubeSynth, Bassline, Electric, DrumSynth×10), AIR VSTs (DB-33, Hybrid, Loom, Mini Grand, theRiser, VacuumPro, Velvet, Xpand!2), Akai VSTs (THE BANK, THE NOISE, THE WUB), and effect plugins from both AIR and Akai. |
| **Dependencies** | P0-T3 (workspace scanner for base inventory), P2-T2 (preset descriptions for timbral tags) |
| **Interfaces** | **Input**: `function buildPresetCatalog(synthsPath: string, descriptions: AssetDescription[]): Promise<SynthPresetCatalog>` — **Output**: `SynthPresetCatalog` (C9 contract). Persisted to `data/preset-catalog.json`. Expected counts: TubeSynth 297 (Synth 44, Lead 50, Pluck 40, Pad 68, Bass 65, Organ 7, FX 23), Bassline ~50, Electric ~30, DrumSynth variants ~20 each, VSTs variable. Total: ~450+. |
| **Testing** | Scan live Synths directory. Verify TubeSynth preset count = 297. Verify category breakdown matches known distribution. Timbral index: `catalog.timbralIndex['warm']` contains multiple entries across engines. Genre index: `catalog.genreIndex['neo_soul']` has Velvet and Electric entries. Spectral profiles: 'bass' category → `fundamentalRange[0] < 100`. Cache: serialize → deserialize → compare totalPresets — equal. No duplicate preset IDs across engines. |
| **Risk** | Preset enumeration relies on directory listing — if preset files are not directly discoverable (nested in binary databases), counts may be inaccurate. Verify by spot-checking against MPC Beats UI preset browser counts. Binary `.xpl` files are NOT parsed — only presence/naming is used. |

---

### P4-T2: Preset Description Generator

| Field | Value |
|---|---|
| **ID** | P4-T2 |
| **Name** | Timbral Description Generator |
| **Complexity** | M |
| **Description** | Generate rich natural-language descriptions for every preset and effect plugin. Presets are described from filename structure and category conventions (binary .xpl not parsed). Effects are described from directory names plus domain knowledge. Implements the name-to-adjective mapping system: "Warm" → warm, "Bright" → bright, "Analog" → warm+vintage, "Sub" → deep+sub-frequency, "Acid" → squelchy+resonant. Generates the timbral tag arrays for the inverted index. |
| **Dependencies** | P4-T1 (preset inventory), P2-T2 (may extend existing descriptions) |
| **Interfaces** | **Input**: `function describePreset(entry: PresetEntry): PresetDescription` — `interface PresetDescription { id: string; description: string; timbralTags: string[]; genreTags: string[]; spectralCategory: PresetSpectralCategory; useCases: string[]; }` — **Adjective extraction rules**: category prefix → base tags; name words → modifier tags; engine → context tags. Name word mapping: `const NAME_TIMBRAL_MAP: Record<string, string[]> = { 'Warm': ['warm', 'smooth'], 'Bright': ['bright', 'shimmery'], 'Dark': ['dark', 'deep'], 'Analog': ['warm', 'vintage', 'analog'], 'Digital': ['clean', 'modern', 'digital'], 'Super': ['thick', 'wide', 'big'], 'Sub': ['deep', 'sub-frequency', 'rumble'], 'Acid': ['squelchy', 'resonant', 'aggressive'], 'Hard': ['aggressive', 'cutting', 'harsh'], 'Soft': ['gentle', 'subtle', 'smooth'], 'Dirty': ['distorted', 'gritty', 'raw'], 'Vintage': ['vintage', 'retro', 'classic'] };` — **Output**: `PresetDescription`. |
| **Testing** | TubeSynth "Warm Pad": description includes "warm", "sustained", "pad"; tags include "warm", "pad"; spectralCategory = "full_range"; genreTags include "neo_soul", "ambient". "Hard Sync Lead": tags include "aggressive", "cutting", "lead". All 297 TubeSynth presets get descriptions ≥ 15 words. No description contains parameter values (legal constraint). All effect plugins get descriptions ≥ 25 words. SP1200: description mentions "12-bit", "lo-fi", "boom-bap". |
| **Risk** | Name-derived descriptions are educated guesses — "Hard Sync" preset might actually sound smooth with certain parameter settings. Accept this limitation and note it in the description: "Character inferred from preset name; actual sound may vary." Keep descriptions about sonic intent/character rather than asserting specific sonic qualities. |

---

### P4-T3: Timbral Ontology & Genre-Sound Map

| Field | Value |
|---|---|
| **ID** | P4-T3 |
| **Name** | Timbral Ontology & Genre-Preset Mapping |
| **Complexity** | L |
| **Description** | Build the structured genre-to-sound mapping from blueprint Section 6. For each genre, define the canonical instrument-to-preset pairings (keys/chords, bass, lead, drums, character FX). Implement the spectral profile estimation system: given a preset category and MIDI note range, estimate the frequency content using harmonic series approximation. Build the spectral overlap calculator for frequency masking analysis (P4-T5). |
| **Dependencies** | P4-T1 (preset catalog), P1-T8 (GenreDNA for genre identification) |
| **Interfaces** | **Input**: None (static knowledge base) + `function estimateSpectralContent(preset: PresetEntry, midiNotes: number[]): SpectralEstimate` — `interface SpectralEstimate { fundamentals: number[]; harmonicPeaks: number[][]; estimatedBandwidth: [number, number]; dominantFrequency: number; spectralCentroid: number; }` — **Genre sound map**: `interface GenreSoundMap { [genre: string]: { keys: string[]; bass: string[]; lead: string[]; drums: string[]; characterFX: string[]; typicalChain: EffectChainTemplate; } }` — `interface EffectChainTemplate { role: TrackRole; slots: Array<{ pluginId: string; stage: SignalFlowStage; purpose: string; }>; }` — **Output**: `data/genre-sound-map.json`, `data/spectral-profiles.json`. |
| **Testing** | Genre map covers all GenreId values (25+ genres). Neo Soul keys → includes Velvet, Electric, TubeSynth. Trap bass → includes Bassline (808). Gospel keys → includes DB-33, Mini Grand. Spectral estimate: C2 (MIDI 36) on saw synth → fundamentals include 65.4Hz, harmonics at 130.8, 196.2 etc. Spectral overlap between same-register saw pad and saw lead → high overlap score. Bass (C1) vs Lead (C5) → low overlap. |
| **Risk** | Spectral estimation without audio is inherently approximate. Saw/square/sine harmonic series are textbook, but real synth presets have filters, modulation, and complex waveforms that change the spectrum dramatically. Frame all spectral analysis as "estimated" with appropriate confidence scores. |

---

### P4-T4: Effect Chain Generator

| Field | Value |
|---|---|
| **ID** | P4-T4 |
| **Name** | Effect Chain Generator |
| **Complexity** | L |
| **Description** | Generate ordered effect chains with parameter value suggestions for a given instrument role, genre, and aesthetic goal. Enforces signal-flow physics ordering (C10 contract): Source Shaping → Dynamics → Time-Based → Modulation → Character → Master. Calculates tempo-synced parameters (delay times, LFO rates) from BPM. Implements genre-specific chain templates from blueprint Section 6. Every generated chain passes `validateSignalFlow()`. |
| **Dependencies** | P4-T3 (genre-sound map for template chains), P4-T1 (effect plugin inventory) |
| **Interfaces** | **Input**: `function generateEffectChain(request: EffectChainRequest): EffectChain` — `interface EffectChainRequest { trackRole: TrackRole; preset?: PresetReference; genre: string; aesthetic: string; mixPosition: 'front' \| 'middle' \| 'back'; stereoWidth: 'mono' \| 'narrow' \| 'wide' \| 'extreme'; vintage?: boolean; tempo: number; }` — **Output**: `EffectChain` (C10 contract). Tempo-synced calculations: `delayMs = 60000 / tempo * subdivisionMultiplier`. Reverb pre-delay from tempo: `1/64 to 1/16 note`. Parameter estimation rules: reverb time 0.5–1s (tight) to 4–6s (spacious); compressor ratio 2:1 (gentle) to 8:1 (aggressive); delay feedback 15–40% (genre-dependent). |
| **Testing** | "neo-soul pad, warm and spacious, back, wide" → chain contains Chorus + Reverb Large in correct signal flow order, no Distortion. "trap 808 bass, tight and punchy, front, mono" → Compressor + LP Filter, zero reverb. All generated chains pass `validateSignalFlow()`. Tempo sync: at 120 BPM, dotted-8th delay = 375ms. At 130 BPM, quarter-note delay = 461.5ms. Signal flow violation: manually construct chain with Reverb before Compressor → `validateSignalFlow()` returns violation. All effect `pluginId` values exist in the asset manifest. Chain length: 2–6 effects (never empty, never > 8). Character effects (SP1200, MPC60, MPC3000) only present when `vintage: true`. |
| **Risk** | We don't know actual parameter ranges of MPC Beats effects — parameter values are estimated using standard ranges (0.0–1.0 normalized, 0–127 MIDI, or physical units like ms/Hz). Output should note uncertainty: "Estimated values — adjust to taste in MPC Beats." Effect availability: user's MPC Beats installation may not have all effects (especially VSTs). Validate against manifest and degrade gracefully. |

---

### P4-T5: Frequency Masking Analyzer

| Field | Value |
|---|---|
| **ID** | P4-T5 |
| **Name** | Frequency Masking Analyzer |
| **Complexity** | L |
| **Description** | Analyze a multi-track arrangement for frequency masking issues WITHOUT audio. Uses MIDI note fundamentals, preset spectral profiles (P4-T3), and effect chain impacts to estimate spectral content per track. Detects masking conflicts, spectral gaps, and mono-compatibility risks. Generates the `FrequencyReport` defined in C1. Implements perceptual weighting from blueprint: masking at 200–500Hz weighted 2×, below 100Hz weighted 3×, above 8kHz weighted 0.5×. |
| **Dependencies** | P4-T3 (spectral estimation), P4-T4 (effect chain impact on spectrum), C1 SongState |
| **Interfaces** | **Input**: `function analyzeFrequencyBalance(state: SongState): FrequencyReport` — **Output**: `FrequencyReport` (from C1 contract) extended with: `interface ExtendedFrequencyReport extends FrequencyReport { gaps: FrequencyGap[]; monoCompatibility: MonoCompatibilityIssue[]; overallScore: number; perTrackSpectra: Record<string, SpectralEstimate>; }` — `interface FrequencyGap { zone: FrequencyZone; description: string; suggestion: string; }` — `interface MonoCompatibilityIssue { trackId: string; effect: string; estimatedLossDb: number; frequencyRange: [number, number]; suggestion: string; }` — Perceptual weights: `const PERCEPTUAL_WEIGHTS: Record<FrequencyZone, number> = { sub: 3.0, bass: 2.0, low_mid: 2.0, mid: 1.0, upper_mid: 0.8, air: 0.5 };` |
| **Testing** | SongState with pad (C3–C5) + lead (C4–C6) both on saw presets → masking detected in mid/upper-mid zone. Add sub bass (C1–C2) → no masking with pad. Stereo chorus on pad → mono compatibility warning with estimated loss. Empty SongState → score 1.0, no clashes. Single-track state → score 1.0 (no masking possible). Gap detection: state with bass + lead but no pad → gap in low-mid zone. Report `generatedAt` timestamp is valid ISO 8601. |
| **Risk** | High. All frequency analysis is theoretical and approximate. Two saw-wave presets might not actually mask if one has a radically different filter setting. Frame all outputs as "potential issues" with severity levels, not definitive problems. The overallScore is a rough heuristic — do not present as a mix quality measurement. |

---

### P4-T6: Genre Mix Template System

| Field | Value |
|---|---|
| **ID** | P4-T6 |
| **Name** | Genre Mix Template System |
| **Complexity** | S |
| **Description** | Define per-genre mixing conventions as structured templates: target LUFS, frequency balance profiles, stereo conventions, characteristic effects, dynamic range expectations. Stored in `skills/mix/genre-mix-templates.json`. Used by the mix suggestion tool and frequency analyzer as genre-appropriate baselines. Covers all 25+ GenreId values. |
| **Dependencies** | P1-T8 (GenreDNA for genre definitions) |
| **Interfaces** | **Input**: genre name → template lookup. `function getGenreMixTemplate(genre: GenreId): GenreMixTemplate` — `interface GenreMixTemplate { genre: string; targetLUFS: [number, number]; frequencyBalance: FrequencyBalance; stereoConventions: StereoConventions; characterEffects: string[]; dynamicRange: 'compressed' \| 'moderate' \| 'dynamic'; referenceArtists: string[]; notes: string; }` — `interface FrequencyBalance { sub: number; bass: number; lowMid: number; mid: number; upperMid: number; air: number; }` (relative levels, sum to ~1.0). `interface StereoConventions { bassPosition: 'mono' \| 'narrow'; drumsPosition: 'centered' \| 'natural_spread'; padsPosition: 'wide' \| 'moderate'; leadsPosition: 'center' \| 'slight_offset'; }` — **Output**: `GenreMixTemplate`. Values from blueprint Section 7: Trap [-7,-9] LUFS; Neo Soul [-12,-14]; UK Garage [-10,-12]; House [-8,-10]; Jazz [-14,-18]; Lo-fi [-12,-14]. |
| **Testing** | All 25+ genres have templates. LUFS ranges valid (all between [-18, -5]). Frequency balance values all positive and ≤ 1.0. Trap frequencyBalance.sub > Neo Soul frequencyBalance.sub. Jazz dynamicRange = 'dynamic'. EDM dynamicRange = 'compressed'. Serialization round-trip: all templates survive JSON persistence. |
| **Risk** | Low. Static data task. Mix templates represent general conventions — individual tracks may deviate significantly. Templates should be presented as starting points, not rules. |

---

### P4-T7: Effect Parameter Calculator

| Field | Value |
|---|---|
| **ID** | P4-T7 |
| **Name** | Tempo-Synced Effect Parameter Calculator |
| **Complexity** | S |
| **Description** | Pure math utility: calculate tempo-synced effect parameters (delay times, LFO rates, gate durations, reverb pre-delays) from BPM and musical subdivision. Returns a complete table of all common subdivisions for a given tempo. Used by the effect chain generator (P4-T4) and the MIDI CC automation system (Phase 5). |
| **Dependencies** | None (pure math) |
| **Interfaces** | **Input**: `function calculateTempoParams(bpm: number): TempoParamTable` — `interface TempoParamTable { bpm: number; subdivisions: Record<MusicalSubdivision, SubdivisionParams>; }` — `interface SubdivisionParams { delayMs: number; frequencyHz: number; ticks480: number; description: string; }` — Core formula: `delayMs = 60000 / bpm × multiplier`. Multipliers: `'1/1': 4.0, '1/2': 2.0, '1/2d': 3.0, '1/2t': 1.333, '1/4': 1.0, '1/4d': 1.5, '1/4t': 0.667, '1/8': 0.5, '1/8d': 0.75, '1/8t': 0.333, '1/16': 0.25, '1/16d': 0.375, '1/16t': 0.167, '1/32': 0.125, '1/32d': 0.1875, '1/32t': 0.0833, '1/64': 0.0625`. Also: `function delayMsForSubdivision(bpm: number, subdivision: MusicalSubdivision): number`. |
| **Testing** | 120 BPM: 1/4 = 500ms, 1/8 = 250ms, 1/8d = 375ms, 1/16 = 125ms. 130 BPM: 1/4 = 461.54ms. 90 BPM: 1/4 = 666.67ms. Frequency: 120 BPM 1/4 = 2.0 Hz. Ticks at 480 PPQ: 1/4 = 480, 1/8 = 240, 1/16 = 120. All subdivisions produce positive values for any BPM > 0. BPM = 0 → throw. Negative BPM → throw. |
| **Risk** | None. Pure deterministic math. |

---

### P4-T8: Sound Agent & Mix Agent Configuration

| Field | Value |
|---|---|
| **ID** | P4-T8 |
| **Name** | Sound Oracle & Mix Engineer Agent Configuration |
| **Complexity** | S |
| **Description** | Create two agent configurations and their skill directories. **Sound Oracle**: preset recommendation, timbral design, creative effect chains. **Mix Engineer**: frequency balance, corrective EQ/compression, mastering. Both share the `generate_effect_chain` tool but differ in intent (creative vs. corrective). Register all Phase 4 tools. |
| **Dependencies** | P4-T1 through P4-T7 (all tools available) |
| **Interfaces** | **Sound agent**: `{ name: 'sound', displayName: 'Sound Oracle', tools: ['recommend_preset', 'generate_effect_chain', 'search_assets', 'describe_preset'], infer: true }`. **Mix agent**: `{ name: 'mix', displayName: 'Mix Engineer', tools: ['analyze_frequency_balance', 'suggest_mix_settings', 'generate_effect_chain', 'calculate_effect_params'], infer: true }`. **Files**: `skills/sound/SKILL.md`, `skills/sound/preset-catalog-summary.md` (~2000 tokens: engine overview, top presets per category), `skills/sound/genre-sound-map.json`. `skills/mix/SKILL.md`, `skills/mix/genre-mix-templates.json`, `skills/mix/frequency-zones.md` (~500 tokens: zone definitions from blueprint), `skills/mix/masking-rules.md` (~800 tokens). **Tools registered**: `recommend_preset` (params: `PresetRecommendationRequest`), `generate_effect_chain` (params: `EffectChainRequest`), `analyze_frequency_balance` (params: `{ trackIds?: string[] }`), `suggest_mix_settings` (params: `{ genre?: string }`), `calculate_effect_params` (params: `{ bpm: number, subdivision?: MusicalSubdivision }`), `describe_preset` (params: `{ presetId: string }`). |
| **Testing** | Routing: "What preset for a warm neo-soul pad?" → Sound Oracle. "My bass and pad are clashing" → Mix Engineer. "How should I set up reverb for this track?" → either (context-dependent). Skill files: valid markdown, within token budgets. Agent prompts ≤ 3000 tokens each. All tool parameter schemas validate with Zod. All tool handler functions pass smoke tests with mock SongState. |
| **Risk** | Routing ambiguity between Sound and Mix agents for effect-related questions. The SDK's `infer: true` routing depends on description quality. Sound description emphasizes "creative, aesthetic, what instrument/preset to use." Mix description emphasizes "technical, corrective, frequency balance, levels, mastering." |

---

## PHASE 5 — MIDI BRIDGE

**Goal**: Virtual MIDI port integration with MPC Beats. Real-time note sending, CC automation, transport control, and the "play-in" recording workflow.

**Task Count**: 8
**Estimated Effort**: 5–6 dev-weeks

---

### P5-T1: Virtual MIDI Port Detection & Setup

| Field | Value |
|---|---|
| **ID** | P5-T1 |
| **Name** | Virtual MIDI Port Detection & loopMIDI Integration |
| **Complexity** | L |
| **Description** | Detect available MIDI ports on the Windows system, identify virtual MIDI ports (loopMIDI), and provide guided setup if none exist. Uses `node-midi` (RtMidi native binding) for port enumeration. Checks for loopMIDI installation via process detection and registry lookup. Creates a virtual port named "MPC AI Controller" if loopMIDI is available. Provides step-by-step setup instructions when manual installation is required. |
| **Dependencies** | P0-T1 (project scaffold) |
| **Interfaces** | **Input**: `async function detectMidiPorts(): Promise<MidiPortStatus>` — `interface MidiPortStatus { availableOutputs: MidiPortInfo[]; availableInputs: MidiPortInfo[]; virtualPortDetected: boolean; virtualPortName?: string; loopMIDIInstalled: boolean; setupRequired: boolean; setupInstructions?: string; }` — `interface MidiPortInfo { index: number; name: string; isVirtual: boolean; }` — **Setup**: `async function createVirtualPort(portName?: string): Promise<VirtualPortResult>` — `interface VirtualPortResult { success: boolean; portName: string; portIndex: number; error?: string; instructions?: string; }` — Detection heuristics: port names containing "loopMIDI", "MIDI Through", or "MPC AI Controller" flagged as virtual. loopMIDI process: check via `tasklist /fi "imagename eq loopMIDI.exe"`. |
| **Testing** | Mock system with loopMIDI: detect port, verify `virtualPortDetected = true`. Mock system without: verify `setupRequired = true`, `setupInstructions` non-empty and includes download URL. Port enumeration: verify all system MIDI ports listed. Port creation: create "MPC AI Controller" → verify appears in subsequent enumeration. Clean up: close port → verify removed from list. Error: attempt create on system without loopMIDI → verify friendly error message with instructions. CI: fully mocked (no native MIDI in CI). |
| **Risk** | `node-midi` requires native compilation via `node-gyp` — the #1 source of installation failures on Windows. Mitigation: use `@julusian/midi` (pre-built binaries) or bundle pre-compiled RtMidi for win32-x64. loopMIDI detection is fragile — the process may not be running even if installed. Also check `HKLM\SOFTWARE\Tobias Erichsen\loopMIDI` registry key. |

---

### P5-T2: node-midi Wrapper & Port Manager

| Field | Value |
|---|---|
| **ID** | P5-T2 |
| **Name** | node-midi Wrapper & MIDI Port Manager |
| **Complexity** | L |
| **Description** | Implement the `MidiPortManager` class that wraps `node-midi` (or `@julusian/midi`) with error handling, automatic reconnection, and the clean API surface needed by all Phase 5 consumers. Provides `MidiOutput` for sending notes/CCs/transport and `MidiInput` for receiving (Phase 10 foundation). Manages port lifecycle: open, close, reconnect, health monitoring. Implements the `VirtualMidiPort` interface. |
| **Dependencies** | P5-T1 (port detection) |
| **Interfaces** | **Input**: `class MidiPortManager { constructor(config: MidiPortConfig); open(portName: string): Promise<ManagedMidiPort>; close(portName: string): Promise<void>; closeAll(): Promise<void>; getPort(portName: string): ManagedMidiPort \| undefined; listOpen(): ManagedMidiPort[]; onPortDisconnected(callback: (portName: string) => void): void; }` — `interface MidiPortConfig { autoReconnect: boolean; reconnectIntervalMs: number; maxReconnectAttempts: number; defaultPort?: string; }` — `interface ManagedMidiPort { readonly name: string; readonly isOpen: boolean; readonly direction: 'input' \| 'output' \| 'bidirectional'; sendNoteOn(channel: number, note: number, velocity: number): void; sendNoteOff(channel: number, note: number): void; sendCC(channel: number, controller: number, value: number): void; sendProgramChange(channel: number, program: number): void; sendRawMessage(bytes: number[]): void; onMessage?(callback: (deltaTime: number, message: number[]) => void): void; close(): void; }` — **Output**: managed port instances. |
| **Testing** | Open → send note-on → send note-off → close: no errors, correct message bytes. CC: send CC74 value 64 on channel 1 → verify bytes [0xB0, 0x4A, 0x40]. Program change: channel 3 program 12 → verify bytes [0xC2, 0x0C]. Reconnect: simulate port disconnect → verify reconnection attempt within `reconnectIntervalMs`. Max reconnect: after `maxReconnectAttempts`, stop trying and emit event. Close all: verify all ports closed, no resource leaks. Send after close: throws descriptive error. Invalid values: channel > 15 → throw. Note > 127 → throw. Velocity > 127 → clamp to 127. |
| **Risk** | Native module crashes (segfaults) if port is used after being closed at the OS level. Wrap all sends in try-catch with graceful degradation. Auto-reconnect polling should not consume significant CPU — use exponential backoff. MIDI ports are a shared system resource — two MUSE instances opening the same port will conflict. Implement port locking via PID file. |

---

### P5-T3: Message Scheduler & Clock

| Field | Value |
|---|---|
| **ID** | P5-T3 |
| **Name** | MIDI Message Scheduler & Clock Sync |
| **Complexity** | XL |
| **Description** | Implement the high-precision MIDI event scheduler that can play back pre-computed note sequences with sub-millisecond timing accuracy. Also implements MIDI Clock (24 PPQ) and transport messages (Start, Stop, Continue). This is the core of the "play-in" feature. Uses `worker_threads` for a dedicated timing thread that is not affected by main-thread garbage collection pauses. The scheduler accepts a `ScheduledMidiEvent[]` sorted by timestamp, starts playback, and dispatches events at their scheduled times via hrtime comparison. |
| **Dependencies** | P5-T2 (port manager for actual message sending) |
| **Interfaces** | **Input**: `class MidiScheduler { constructor(port: ManagedMidiPort); schedule(events: ScheduledMidiEvent[]): PlaybackHandle; startClock(bpm: number): ClockHandle; stopClock(): void; sendTransport(action: 'start' \| 'stop' \| 'continue'): void; }` — `interface ScheduledMidiEvent { timestampMs: number; type: 'noteon' \| 'noteoff' \| 'cc' \| 'program_change'; channel: number; data1: number; data2?: number; }` — `interface PlaybackHandle { readonly isPlaying: boolean; readonly elapsedMs: number; readonly progress: number; cancel(): void; onProgress(callback: (bar: number, beat: number, progress: number) => void): void; onComplete(callback: () => void): void; }` — `interface ClockHandle { readonly bpm: number; readonly isRunning: boolean; setBpm(bpm: number): void; stop(): void; }` — **Worker thread**: `scheduler-worker.ts` runs a tight `setImmediate()` loop comparing `process.hrtime.bigint()` against next event timestamp. Communicates via `MessagePort` with the main thread. Events are pre-sorted and loaded into the worker via `SharedArrayBuffer` or structured clone. |
| **Testing** | Schedule 4-beat metronome (C5 at 0, 500, 1000, 1500ms at 120 BPM). Measure actual dispatch times via hrtime logging — verify within ±2ms of target. Schedule 100 events → verify all dispatched in correct order. Cancel mid-playback → verify remaining events NOT dispatched. Progress callback: verify bar/beat reporting. Clock: 120 BPM → measure 48 clock messages/second (±2). Clock BPM change: switch from 120 to 130 → verify interval adjusts within 1 beat. Transport: Start → Clock → Stop sequence. Stress test: 1000 events over 10 seconds → no dropped events, max jitter < 5ms. Memory: no leaks after 10 play/cancel cycles. Worker crash recovery: worker dies → main thread gets error, can restart. |
| **Risk** | **Critical.** JavaScript's event loop is not real-time. `setImmediate` in a worker thread achieves ~0.1ms resolution but consumes 100% of one CPU core during playback. Alternative: use `Atomics.wait` with timeout for lower CPU usage (but ~1ms resolution). Test both approaches. At 140 BPM with 32nd notes, events are ~107ms apart — 5ms jitter is noticeable but acceptable. For 16th notes at 120 BPM (~125ms apart), 2ms jitter is imperceptible. Memory pressure from `SharedArrayBuffer`: pre-allocate buffer size based on event count. |

---

### P5-T4: .xmm Controller Map Generator

| Field | Value |
|---|---|
| **ID** | P5-T4 |
| **Name** | .xmm Controller Map File Generator |
| **Complexity** | M |
| **Description** | Generate valid `.xmm` XML files that tell MPC Beats how to interpret MIDI from the virtual "MPC AI Controller" port. The generated file maps our defined CC numbers and note messages to MPC Beats internal `Target_control` indices. Outputs XML matching the exact schema observed in the 67 existing `.xmm` files. The generated file is placed in `Midi Learn/` directory for MPC Beats to discover. |
| **Dependencies** | P0-T5 (.xmm parser for format reference), P5-T1 (port name "MPC AI Controller") |
| **Interfaces** | **Input**: `function generateXmm(config: XmmGeneratorConfig): Promise<string>` — `interface XmmGeneratorConfig { controllerName: string; manufacturer: string; portName: string; pads: PadMapping[]; knobs: KnobMapping[]; transport?: TransportMapping[]; outputPath: string; }` — `interface PadMapping { padIndex: number; targetControl: number; midiNote: number; midiChannel: number; }` — `interface KnobMapping { knobIndex: number; targetControl: number; midiCC: number; midiChannel: number; }` — `interface TransportMapping { name: string; targetControl: number; midiType: 'note' \| 'cc'; midiData1: number; midiChannel: number; }` — **Output**: returns path to written `.xmm` file. Default layout: 16 pads (Target 0–15, notes 36–51 on ch10), 8 knobs (Target 24–31, CCs 74–81 on ch1). XML structure: `<?xml version="1.0" encoding="UTF-8"?><MidiLearnMap_ Manufacturer="MUSE" Version="1.0">...</MidiLearnMap_>`. |
| **Testing** | Generate default .xmm → parse with P0-T5 parser → verify: manufacturer="MUSE", 16 pads mapped, 8 knobs mapped, port name = "MPC AI Controller". Verify XML is well-formed (parse with `fast-xml-parser`). Verify `Target_control` values match config. Verify output path is within `Midi Learn/` directory. Round-trip: generate → parse → compare config values — zero mismatches. Custom config: 4 pads + 16 knobs → verify correct pairing count. |
| **Risk** | MPC Beats `.xmm` parsing may be strict about XML formatting (attribute ordering, whitespace, encoding). Generate XML that exactly matches the formatting observed in stock `.xmm` files. Test by loading the generated file in MPC Beats and verifying it appears in the controller selection menu (manual integration test). File permissions: MUSE needs write access to the `Midi Learn/` directory. |

---

### P5-T5: Transport Control Interface

| Field | Value |
|---|---|
| **ID** | P5-T5 |
| **Name** | Transport Control (Play/Stop/Record) Interface |
| **Complexity** | M |
| **Description** | Implement transport control for MPC Beats via MIDI System Real-Time messages and MMC (MIDI Machine Control). Provides play, stop, continue, record arm, and position commands. Transport control is essential for the "play-in" workflow (P5-T7) and future timeline synchronization. Also provides BPM-aware bar/beat position tracking. |
| **Dependencies** | P5-T2 (port manager), P5-T3 (clock for tempo sync) |
| **Interfaces** | **Input**: `class TransportController { constructor(port: ManagedMidiPort, scheduler: MidiScheduler); play(): void; stop(): void; continue_(): void; startWithClock(bpm: number): void; stopWithClock(): void; sendMMC(command: MMCCommand): void; getPosition(): TransportPosition; setTempo(bpm: number): void; }` — `type MMCCommand = 'stop' \| 'play' \| 'deferred_play' \| 'fast_forward' \| 'rewind' \| 'record_strobe' \| 'record_exit' \| 'record_pause' \| 'pause' \| 'reset' \| 'goto'` — `interface TransportPosition { bar: number; beat: number; tick: number; totalTicks: number; totalMs: number; }` — MMC message format: `[0xF0, 0x7F, 0x7F, 0x06, command, 0xF7]`. Commands: stop=0x01, play=0x02, deferred_play=0x03, ff=0x04, rw=0x05, record_strobe=0x06, record_exit=0x07, pause=0x09. |
| **Testing** | Play → verify 0xFA sent. Stop → verify 0xFC sent. Continue → verify 0xFB sent. `startWithClock(120)` → verify Start + Clock messages begin. `stopWithClock()` → verify Clock stops + Stop sent. MMC play → verify SysEx [F0 7F 7F 06 02 F7]. Position tracking: after startWithClock at 120 BPM, wait 1000ms → position should be bar 1, beat 3 (±1 beat tolerance due to timing). Tempo change during playback: verify clock interval adjusts. |
| **Risk** | MPC Beats' response to MIDI transport commands depends on its Sync settings. User must configure "MIDI Sync: External" or "MMC Slave" mode. Without this, transport commands are ignored silently. The setup guidance (via chat) must be very clear. Some DAWs respond to MIDI Real-Time messages but not MMC, or vice versa — test both paths with MPC Beats specifically. |

---

### P5-T6: CC Automation System

| Field | Value |
|---|---|
| **ID** | P5-T6 |
| **Name** | MIDI CC Automation System |
| **Complexity** | M |
| **Description** | Send MIDI CC messages to control MPC Beats parameters in real-time. Implements smooth CC ramps (filter sweeps, volume fades), stepped CC changes, and automation playback from recorded CC curves. Uses the `AutomationRoute` definitions from C11 to map high-level parameter changes to specific CC numbers. Supports value curves: linear, logarithmic, exponential, and S-curve for perceptually correct parameter transitions. |
| **Dependencies** | P5-T2 (port manager for sending), P5-T3 (scheduler for timed CC sequences) |
| **Interfaces** | **Input**: `class CCAutomation { constructor(port: ManagedMidiPort, scheduler: MidiScheduler); sendCC(channel: number, cc: number, value: number): void; rampCC(channel: number, cc: number, fromValue: number, toValue: number, durationMs: number, curve?: CurveType): PlaybackHandle; playAutomation(events: MidiCCEvent[]): PlaybackHandle; }` — `type CurveType = 'linear' \| 'logarithmic' \| 'exponential' \| 's_curve'` — CC ramp implementation: generate intermediate CC values at 10ms intervals (100 steps/second → smooth), schedule via P5-T3. Linear: `value = from + (to - from) * (t / duration)`. Logarithmic: `value = from + (to - from) * Math.log(1 + 9 * t/duration) / Math.log(10)`. Exponential: `value = from + (to - from) * (Math.pow(10, t/duration) - 1) / 9`. S-curve: `value = from + (to - from) * (1 / (1 + Math.exp(-12 * (t/duration - 0.5))))`. |
| **Testing** | Send CC74 = 64 → verify single message sent with correct bytes. Ramp CC74 from 0 to 127 over 1000ms → verify ~100 messages sent at ~10ms intervals, values increasing monotonically. Ramp with curve='logarithmic' → verify slow start, fast end. Cancel ramp mid-way → verify messages stop. Play automation sequence → verify events at expected times (within ±5ms). All CC values clamped to [0, 127]. CC number validation: > 127 → throw. Channel validation: > 15 → throw. Multiple simultaneous ramps on different CCs → verify non-interference. |
| **Risk** | MIDI CC message flooding: 100 msg/sec is fine for a single CC, but 8 CCs ramping simultaneously = 800 msg/sec. RtMidi can handle this but some virtual ports may buffer or drop. Test with loopMIDI at high throughput. CC resolution: MIDI CC is 7-bit (0–127), which gives only 128 steps. For filter sweeps, this can produce audible stepping. Consider NRPN (14-bit CC pairs) for higher resolution — but MPC Beats may not support NRPN on all parameters. |

---

### P5-T7: Health Check & Diagnostics

| Field | Value |
|---|---|
| **ID** | P5-T7 |
| **Name** | MIDI Connection Health Monitor & Diagnostics |
| **Complexity** | S |
| **Description** | Monitor the virtual MIDI connection health continuously and provide user-friendly status and diagnostics. Implements a `midi_status` tool that reports connection state, port availability, latency estimate, and troubleshooting guidance. Auto-detects port disconnection and attempts reconnection. On session start, checks MIDI readiness and either silently connects or guides setup. |
| **Dependencies** | P5-T1 (port detection), P5-T2 (port manager) |
| **Interfaces** | **Input**: `class MidiHealthMonitor { constructor(portManager: MidiPortManager); start(pollIntervalMs?: number): void; stop(): void; getStatus(): MidiHealthStatus; onStatusChange(callback: (status: MidiHealthStatus) => void): void; }` — `interface MidiHealthStatus { connectionState: 'connected' \| 'degraded' \| 'disconnected' \| 'not_configured'; portName?: string; uptimeMs?: number; lastMessageSentAt?: string; estimatedLatencyMs?: number; mpcBeatsDetected: boolean; diagnostics: MidiDiagnostic[]; }` — `interface MidiDiagnostic { level: 'info' \| 'warning' \| 'error'; message: string; action?: string; }` — Tool registered: `midi_status` (no params) → returns formatted health report. |
| **Testing** | Connected state: port open → status = 'connected', diagnostics empty. Simulate port disconnect → status transitions to 'disconnected', diagnostic with reconnection suggestion. Not configured: no loopMIDI → status = 'not_configured', diagnostic with setup instructions including loopMIDI download URL. `mpcBeatsDetected`: true if "MPC Beats" appears in process list (via `tasklist`). Polling: status updates within `pollIntervalMs` of state change. No resource leaks: start/stop 100 times → memory stable. |
| **Risk** | Low. Monitoring is non-critical — if it fails, MIDI still works, just without diagnostics. `tasklist` for MPC Beats detection is Windows-specific but this entire platform is Windows-targeted (MPC Beats is Windows-only). Detection may false-positive if a different process has "MPC" in its name. |

---

### P5-T8: MIDI Bridge Tool Registration & Agent Integration

| Field | Value |
|---|---|
| **ID** | P5-T8 |
| **Name** | MIDI Bridge Tool Registration & Unified Interface |
| **Complexity** | M |
| **Description** | Register all Phase 5 tools with the SDK, implement the convenience tools (`play_progression`, `play_sequence`), and integrate MIDI capabilities into the session lifecycle. On session start: detect/create MIDI port, load CC mapping, run health check. On session end: stop playback, close ports. Implements the "play-in" workflow as a high-level tool that orchestrates transport, clock, and sequence playback. Permission handler: first MIDI send requires user confirmation via `hooks.onPreToolUse`. |
| **Dependencies** | P5-T1 through P5-T7 (all Phase 5 components), P3-T2 (MIDI writer for persisting played content), P0-T7 (tool registration factory) |
| **Interfaces** | **Tools registered**: `create_virtual_port` (params: `{ portName?: string }` → `VirtualPortResult`), `send_midi_note` (params: `{ channel, note, velocity, durationMs }` → success), `send_midi_cc` (params: `{ channel, cc, value }` → success), `midi_transport` (params: `{ action: 'play'\|'stop'\|'continue' }` → success), `play_sequence` (params: `{ events: ScheduledMidiEvent[], sync?: boolean }` → `PlaybackHandle` summary), `play_progression` (params: `{ filePath: string, tempo: number, voicingStyle?: string }` → PlaybackHandle summary), `ramp_cc` (params: `{ channel, cc, from, to, durationMs, curve? }` → success), `midi_status` (params: none → `MidiHealthStatus`). **Lifecycle**: `hooks.onSessionStart` → `detectMidiPorts()`, if virtual port found → open silently, inject "MIDI: connected to {portName}" into system message. `hooks.onSessionEnd` → `scheduler.cancelAll()`, `portManager.closeAll()`. `hooks.onPreToolUse` for any `send_*` or `play_*` tool → first invocation per session triggers permission prompt: "MUSE wants to send MIDI to MPC Beats via {portName}. Allow?" |
| **Testing** | Full E2E: create port → play Godly at 100 BPM → verify notes sent → verify playback completes → verify port remains open. Convenience: `play_progression` with Godly → verify it reads .progression, generates note events, schedules playback. Permission: first `send_midi_note` → verify permission prompt fires. Subsequent sends → no prompt. Session end: verify all ports closed, scheduler stopped. Error: `play_progression` with invalid file → friendly error. MIDI not configured: `play_sequence` → error message with setup instructions (not crash). |
| **Risk** | Integration complexity: wiring 7 components into a cohesive tool surface requires careful error handling at every boundary. The "play-in" workflow depends on MPC Beats being configured correctly (MIDI input set to our port, recording armed) — MUSE cannot verify this programmatically. Rely on chat-based guidance and the health monitor for best-effort detection. |

---

## Phase Dependency Graph (Phases 3–5)

```
Phase 0-2 (complete)
    │
    ├─→ P3-T1 (MIDI parser) ─────────────────────────────┐
    │    │                                                 │
    │    ├─→ P3-T2 (MIDI writer)                          │
    │    │                                                 │
    │    ├─→ P3-T7 (arp analyzer) ◄─also needs P1-T2      │
    │                                                      │
    ├─→ P3-T3 (velocity curves) ─┐                        │
    │                              │                        │
    │                              └→ P3-T4 (humanization) │
    │                                  │                    │
    ├─→ P3-T5 (ghost notes)           │                    │
    │                                  │                    │
    ├─→ P3-T6 (groove templates) ◄────┘                    │
    │                                                      │
    └─→ P3-T8 (rhythm agent) ◄────── all P3-T*            │
                                                           │
    ┌──────────────────────────────────────────────────────┘
    │
    ├─→ P4-T1 (plugin scanner) ◄─ P0-T3, P2-T2
    │    │
    │    ├─→ P4-T2 (descriptions) ◄─ P4-T1
    │    │
    │    ├─→ P4-T3 (timbral ontology) ◄─ P4-T1, P1-T8
    │    │    │
    │    │    ├─→ P4-T4 (effect chain gen)
    │    │    │
    │    │    └─→ P4-T5 (freq masking)
    │    │
    │    ├─→ P4-T6 (genre mix templates)
    │    │
    │    ├─→ P4-T7 (param calculator) ◄─ none (independent)
    │    │
    │    └─→ P4-T8 (agents) ◄─ all P4-T*
    │
    ├─→ P5-T1 (port detection) ─────────────────────┐
    │    │                                            │
    │    └─→ P5-T2 (node-midi wrapper)               │
    │         │                                       │
    │         ├─→ P5-T3 (scheduler/clock) ⚠ XL       │
    │         │    │                                   │
    │         │    ├─→ P5-T5 (transport)              │
    │         │    │                                   │
    │         │    └─→ P5-T6 (CC automation)          │
    │         │                                       │
    │         └─→ P5-T7 (health monitor)              │
    │                                                 │
    ├─→ P5-T4 (xmm generator) ◄─ P0-T5              │
    │                                                 │
    └─→ P5-T8 (tool registration) ◄─ all P5-T* + P3-T2
```

### Parallelization Opportunities

| Parallel Group | Tasks | Rationale |
|---|---|---|
| Phase 3 core | P3-T1, P3-T3, P3-T5, P3-T6 | Independent algorithms. No shared dependencies beyond P0-T1. |
| Phase 4 independent | P4-T6, P4-T7 | Pure data/math tasks with zero cross-deps. |
| Phase 4 post-scan | P4-T2, P4-T3 | Both consume P4-T1 output, independent of each other. |
| Phase 5 independent | P5-T1, P5-T4 | Port detection and .xmm generation are orthogonal. |
| Cross-phase parallel | P3-* + P4-T7 + P5-T1 | All three thread-starts are independent of each other. |

### Critical Path

```
P3-T1 → P3-T2 → P3-T7 → P3-T8
                                 ↘
P4-T1 → P4-T3 → P4-T4 → P4-T5 → P4-T8
                                        ↘
P5-T1 → P5-T2 → P5-T3 → P5-T5 → P5-T8
```

Estimated critical path duration: ~12–14 dev-weeks (single developer).
With parallelization across 2 developers: ~8–10 dev-weeks.

---

## Summary Matrix

| Task ID | Name | Complexity | Dependencies | Key Interfaces |
|---|---|---|---|---|
| **P3-T1** | MIDI Binary Parser | M | P0-T1 | `parseMidiFile()` → `ParsedMidiFile` |
| **P3-T2** | MIDI Binary Writer | M | P3-T1 | `writeMidiFile()` → `.mid` file path |
| **P3-T3** | Velocity Curve Engine | M | P0-T1 | `generateVelocityCurve()` → `VelocityProfile` |
| **P3-T4** | Humanization Engine | L | P3-T3 | `humanize()` → `MidiNoteEvent[]` |
| **P3-T5** | Ghost Note Generator | S | P3-T1 | `insertGhostNotes()` → `MidiNoteEvent[]` |
| **P3-T6** | Groove Template System | S | P3-T4 | `applyGrooveTemplate()` → `MidiNoteEvent[]` |
| **P3-T7** | Arp Analyzer & Transformer | L | P3-T1, P1-T2 | `analyzeArpPattern()`, `transformArp()` |
| **P3-T8** | Rhythm Agent Config | S | all P3-T* | Agent config + `skills/rhythm/` |
| **P4-T1** | Plugin Scanner & Catalog | M | P0-T3, P2-T2 | `buildPresetCatalog()` → C9 `SynthPresetCatalog` |
| **P4-T2** | Timbral Descriptions | M | P4-T1 | `describePreset()` → `PresetDescription` |
| **P4-T3** | Timbral Ontology & Genre Map | L | P4-T1, P1-T8 | `estimateSpectralContent()`, `GenreSoundMap` |
| **P4-T4** | Effect Chain Generator | L | P4-T3 | `generateEffectChain()` → C10 `EffectChain` |
| **P4-T5** | Frequency Masking Analyzer | L | P4-T3, P4-T4 | `analyzeFrequencyBalance()` → `ExtendedFrequencyReport` |
| **P4-T6** | Genre Mix Templates | S | P1-T8 | `getGenreMixTemplate()` → `GenreMixTemplate` |
| **P4-T7** | Effect Param Calculator | S | None | `calculateTempoParams()` → `TempoParamTable` |
| **P4-T8** | Sound & Mix Agent Config | S | all P4-T* | Agent configs + `skills/sound/`, `skills/mix/` |
| **P5-T1** | Virtual MIDI Detection | L | P0-T1 | `detectMidiPorts()` → `MidiPortStatus` |
| **P5-T2** | node-midi Wrapper | L | P5-T1 | `MidiPortManager` → `ManagedMidiPort` |
| **P5-T3** | Message Scheduler & Clock | XL | P5-T2 | `MidiScheduler` → `PlaybackHandle`, `ClockHandle` |
| **P5-T4** | .xmm Generator | M | P0-T5, P5-T1 | `generateXmm()` → `.xmm` file path |
| **P5-T5** | Transport Control | M | P5-T2, P5-T3 | `TransportController` → play/stop/continue |
| **P5-T6** | CC Automation | M | P5-T2, P5-T3 | `CCAutomation` → ramps, curves, automation |
| **P5-T7** | Health Monitor | S | P5-T1, P5-T2 | `MidiHealthMonitor` → `MidiHealthStatus` |
| **P5-T8** | MIDI Bridge Tools & Integration | M | all P5-T*, P3-T2 | Tool registrations + lifecycle hooks |

### Complexity Distribution

| Complexity | Phase 3 | Phase 4 | Phase 5 | Total |
|---|---|---|---|---|
| S | 3 | 3 | 1 | **7** |
| M | 3 | 2 | 4 | **9** |
| L | 2 | 3 | 2 | **7** |
| XL | 0 | 0 | 1 | **1** |
| **Total** | **8** | **8** | **8** | **24** |

---

## Cross-Phase Export Registry (P3–P5)

| Export | Source | Consumers |
|---|---|---|
| `parseMidiFile()` | P3-T1 | P3-T7, P5-T8, P6, P10 |
| `writeMidiFile()` | P3-T2 | P3-T7, P5-T8, P6. P8 |
| `generateVelocityCurve()` | P3-T3 | P3-T4, P6 |
| `humanize()` | P3-T4 | P3-T8, P6, P10 |
| `GrooveTemplate` + templates | P3-T6 | P6, P9 |
| `analyzeArpPattern()`, `transformArp()` | P3-T7 | P6, P8 |
| Rhythm agent config | P3-T8 | P6 (orchestration) |
| `SynthPresetCatalog` (C9) | P4-T1 | P4-T2, P4-T3, P6, P9 |
| `EffectChain` (C10) | P4-T4 | C1 SongState, P5-T6, P6, P7 |
| `analyzeFrequencyBalance()` | P4-T5 | P6 (validation), P8 (critic) |
| `GenreMixTemplate` | P4-T6 | P6, P7, P9 |
| `calculateTempoParams()` | P4-T7 | P4-T4, P5-T6, P6 |
| Sound + Mix agent configs | P4-T8 | P6 (multi-agent orchestration) |
| `MidiPortManager` | P5-T2 | P5-T3 through P5-T8, P6, P7, P10 |
| `MidiScheduler` | P5-T3 | P5-T5, P5-T6, P5-T8, P6, P10 |
| `ControllerMapping` (C11) | P5-T4/P5-T8 | P7 (controller intelligence) |
| `TransportController` | P5-T5 | P5-T8, P6, P10 |
| `CCAutomation` | P5-T6 | P5-T8, P7, P10 |
| `MidiHealthMonitor` | P5-T7 | P5-T8, all subsequent phases |
| `QualityScore` (C12) | Contract | P6, P8, P9 |

---

## Consolidated Risk Matrix (P3–P5)

| Risk | Phase | Severity | Mitigation |
|---|---|---|---|
| MIDI timing precision in JavaScript | P3, P5 | **High** | Worker thread with `hrtime` polling. Write-time computation (P3) is algebraic — no real-time issue. Playback (P5) uses dedicated worker. |
| Melody/bassline generation quality | P3 | **High** | Generators produce raw material. LLM iterates. Quality gates (C12) in Phase 8 provide safety net. |
| Preset descriptions inferred from names only | P4 | **High** | Cannot parse binary `.xpl`. Conservative descriptions + "try it" philosophy. Frame as "inferred character." |
| Spectral estimation without audio | P4 | **High** | Theoretical approximation only. Frame outputs as "potential issues" not "definitive." Include confidence scores. |
| node-midi native compilation on Windows | P5 | **High** | Use `@julusian/midi` with pre-built binaries. Test on clean Windows 10/11 installs. Bundle `node-gyp` fallback. |
| loopMIDI dependency (user installation) | P5 | **High** | Cannot bundle or auto-install. Provide step-by-step guide with screenshots. Detect and guide in health check. Graceful file-only fallback. |
| MPC Beats MIDI configuration (manual) | P5 | **High** | User must manually set MIDI input in MPC Beats. Chat-based guidance with step-by-step instructions. Health monitor detects MPC Beats process. |
| MIDI feedback loops | P5 | **Medium** | Channel isolation + message tagging. Output on ch1-9, input monitor on different channels. Document bidirectional routing rules. |
| Groove template accuracy without audio | P3 | **Medium** | Base values on published MPC60/SP1200 swing research and academic groove analysis literature. |
| Effect parameter range uncertainty | P4 | **Medium** | Standard ranges assumed (0-127, 0-1.0 normalized). Note uncertainty in output. "Adjust to taste in MPC Beats." |
| Arp fit-to-chords with polyphonic patterns | P3 | **Medium** | Modular wrapping for chord-tone mapping. Preserve octave relationships. Map to nearest chord tone for passing tones. |
| Agent routing ambiguity (Sound vs Mix) | P4 | **Medium** | Differentiate via `description` field: Sound = creative/aesthetic, Mix = technical/corrective. Test routing with 20+ sample queries. |
| Worker thread crash recovery | P5 | **Medium** | Restart worker on unhandled rejection. Drain event queue before restart. Log crash for diagnostics. |
| Context window with large arrangements | P3 | **Low** | Use SongState L1 compression. LLM never sees full note-level data unless editing a specific bar. |

````
