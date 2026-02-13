````markdown
# MUSE AI Music Platform — Task Decomposition: Phase 6

## Complete Engineering Specification

> **Generated**: February 9, 2026
> **Scope**: Phase 6 (Full Pipeline — End-to-End Song Generation)
> **SDK**: `@github/copilot-sdk` — CLI-based JSON-RPC
> **Architecture**: Continues from P0–P5 contracts (C1–C12). Adds contract C13.
> **Prerequisite**: TASK-DECOMPOSITION-P0-P2.md (C1–C8), TASK-DECOMPOSITION-P3-P5.md (C9–C12)
> **Dependencies**: Phase 0 (foundation), Phase 1 (harmony), Phase 2 (search), Phase 3 (rhythm), Phase 4 (sound), Phase 5 (MIDI bridge)

---

## Table of Contents

1. [Decision D-011 Resolution](#decision-d-011-resolution)
2. [Contract C13: ComposerPipeline](#contract-c13-composerpipeline)
3. [Task Specifications (P6-T1 through P6-T8)](#phase-6--full-pipeline)
4. [Cross-Phase Export Registry](#cross-phase-export-registry)
5. [Risk Matrix](#risk-matrix)

---

## Decision D-011 Resolution

### P6 Orchestrator Pattern: DAG vs. Sequential vs. LLM-Orchestrated

**Decision**: **(a) Custom DAG with `Promise.all` parallelism** — augmented with LLM decision points at stage boundaries.

#### Analysis

| Option | Pros | Cons |
|--------|------|------|
| **(a) Custom DAG** | Deterministic stage ordering; explicit parallelism for MIDI generation (4a–4d); predictable latency; testable without LLM; clear retry boundaries; dependency graph enforces correctness | Rigid — adding stages requires code changes; no dynamic re-routing based on intermediate results |
| **(b) LangGraph-style graph** | Formal state machine; built-in persistence/checkpointing; supports cycles (retry loops) | External dependency; node.js LangGraph is immature; over-engineering for 8 linear stages; SDK already provides session state |
| **(c) Pure LLM orchestration** | Maximum flexibility — LLM decides stage order per-prompt; handles novel prompts gracefully; elegant for creative re-routing | Non-deterministic execution order; unpredictable latency (30–120s); untestable pipeline guarantees; expensive (6–10 LLM calls per pipeline run); no parallelism without explicit tool-level support |

#### Resolution Rationale

The pipeline has **8 well-defined stages** with clear input/output contracts (C1–C12). The dependency structure is a fixed DAG — there is no conditional branching in the happy path. LLM flexibility is needed only at two points:

1. **Intent decomposition** (Stage 1) — interpreting natural language into `PipelineIntent`
2. **Quality-gate recovery** (Stage 7) — deciding which stage to retry when validation fails

Both are achieved by inserting LLM calls at specific DAG nodes rather than making the entire orchestration LLM-driven.

The DAG engine provides:
- **Explicit parallelism**: Stage 4 sub-tasks (drums, bass, chords, lead) run via `Promise.all`
- **Checkpoint persistence**: `SongState` written to disk after each stage for crash recovery
- **Deterministic testing**: pipeline can be tested end-to-end with mock tool handlers
- **Observable progress**: each stage emits progress events for streaming to the user
- **Retry isolation**: failed stages retry independently without re-running upstream stages

**Hybrid approach**: The Composer agent (P6-T8) wraps the DAG engine. For standard `/compose` requests, the agent delegates to the DAG. For ambiguous or creative requests ("make it more interesting"), the LLM exercises judgment within the iteration loop (P6-T6).

```
┌──────────────────────────────────────────────────────┐
│                   Composer Agent (LLM)                │
│  Handles: intent parsing, disambiguation, iteration  │
│                                                       │
│  ┌────────────────────────────────────────────────┐   │
│  │            Pipeline DAG Engine                  │   │
│  │  Handles: deterministic stage execution,        │   │
│  │  parallelism, checkpointing, progress           │   │
│  │                                                  │   │
│  │  S1 → S2 → S3 → S4[a,b,c,d] → S5 → S6 → S7 → S8 │
│  └────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────┘
```

**Decision ID**: D-011
**Resolved By**: Architectural analysis (DAG determinism + LLM flexibility at boundaries)
**Date**: 2026-02-09
**Phase Impact**: P6, P8 (quality gates inject into DAG), P10 (live pipeline variant)

---

## Contract C13: ComposerPipeline

The pipeline orchestration state threaded through all 8 stages. Tracks execution progress, stage results, timing, and recovery state.

```typescript
// ━━━ C13: ComposerPipeline ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * End-to-end song generation pipeline state.
 * Created by the Pipeline Orchestrator (P6-T2), consumed by all 8 stages.
 * Persisted to `output/<session-id>/state/pipeline-state.json` after each stage.
 *
 * The pipeline is a fixed DAG with 8 stages:
 *   S1: Intent Decomposition     → PipelineIntent
 *   S2: Harmonic Generation      → EnrichedProgression
 *   S3: Arrangement Design       → Arrangement
 *   S4: MIDI Generation (parallel) → MidiPattern[] per track
 *   S5: Sound Selection          → PresetReference[] + EffectChain[]
 *   S6: Assembly                 → Multi-track file
 *   S7: Validation               → QualityScore (if Phase 8 available)
 *   S8: Output & Playback        → SessionManifest + optional MIDI playback
 *
 * Stage 4 has internal parallelism: drums, bass, chords, lead run concurrently.
 */
export interface ComposerPipeline {
  /** Pipeline instance ID (UUID v4). Unique per pipeline run. */
  readonly pipelineId: string;

  /** Session ID that owns this pipeline. Links to output/<session-id>/. */
  readonly sessionId: string;

  /** Pipeline schema version. SemVer. */
  readonly version: string;

  /** The original user prompt that triggered this pipeline. */
  rawPrompt: string;

  /** Decomposed intent from Stage 1. Undefined until S1 completes. */
  intent?: PipelineIntent;

  /** Current pipeline execution status. */
  status: PipelineStatus;

  /** Current stage being executed. 0 = not started, 1-8 = in progress, 9 = complete. */
  currentStage: number;

  /** Per-stage execution records. Keyed by stage number (1-8). */
  stages: Record<number, StageRecord>;

  /** Accumulated SongState. Updated after each stage. */
  songState: SongState;

  /** A/B alternatives generated during this pipeline (P6-T7). */
  alternatives: AlternativeSet[];

  /** Pipeline-level configuration. */
  config: PipelineConfig;

  /** Error recovery state. */
  recovery: RecoveryState;

  /** ISO 8601 timestamps. */
  createdAt: string;
  updatedAt: string;
  completedAt?: string;

  /** Total pipeline wall-clock duration in milliseconds. */
  totalDurationMs?: number;
}

// ━━━ Pipeline Status ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

export type PipelineStatus =
  | 'pending'          // created but not started
  | 'running'          // actively executing stages
  | 'paused'           // waiting for user input (ask_user)
  | 'recovering'       // retrying a failed stage
  | 'completed'        // all stages finished successfully
  | 'completed_partial'// completed with some stages skipped or degraded
  | 'failed'           // unrecoverable failure
  | 'cancelled';       // user cancelled

// ━━━ Stage Record ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * Execution record for a single pipeline stage.
 * Tracks timing, status, output, and any errors encountered.
 */
export interface StageRecord {
  /** Stage number (1-8). */
  stage: number;

  /** Human-readable stage name. */
  name: string;

  /** Execution status. */
  status: StageStatus;

  /** ISO 8601 start time. */
  startedAt?: string;

  /** ISO 8601 completion time. */
  completedAt?: string;

  /** Execution duration in milliseconds. */
  durationMs?: number;

  /** Number of retry attempts (0 = first attempt succeeded). */
  retryCount: number;

  /** Maximum retries allowed for this stage. */
  maxRetries: number;

  /**
   * Stage-specific output data.
   * Typed per-stage — the orchestrator knows the expected shape
   * based on the stage number.
   */
  output?: StageOutput;

  /** Error details if stage failed. */
  error?: StageError;

  /**
   * Tools invoked during this stage.
   * Used for timing analysis and debugging.
   */
  toolCalls: ToolCallRecord[];

  /**
   * Quality score from Phase 8 critics (if available).
   * Populated during Stage 7 (Validation) for each prior stage's output.
   */
  qualityScore?: QualityScore;
}

export type StageStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'retrying'
  | 'skipped';

/**
 * Discriminated union of per-stage output types.
 * Each stage produces a known contract-typed result.
 */
export type StageOutput =
  | { stage: 1; intent: PipelineIntent }
  | { stage: 2; progression: EnrichedProgression; progressionFilePath: string }
  | { stage: 3; arrangement: Arrangement }
  | { stage: 4; tracks: TrackGenerationResult[] }
  | { stage: 5; presets: PresetAssignment[]; effectChains: EffectChain[] }
  | { stage: 6; assembledFilePath: string; trackFilePaths: string[] }
  | { stage: 7; qualityReport: QualityScore; passed: boolean }
  | { stage: 8; manifest: SessionManifest; playbackInitiated: boolean };

/** Result of generating a single MIDI track in Stage 4. */
export interface TrackGenerationResult {
  /** Track ID (matches SongState track). */
  trackId: string;

  /** Track role. */
  role: TrackRole;

  /** Path to generated .mid file. */
  midiFilePath: string;

  /** The MidiPattern metadata (C3 contract). */
  pattern: MidiPattern;

  /** Humanization config applied. */
  humanizationApplied?: HumanizationConfig;

  /** Groove template applied. */
  grooveTemplateApplied?: string;
}

/** Preset assignment linking a track to its recommended preset and effect chain. */
export interface PresetAssignment {
  /** Track ID. */
  trackId: string;

  /** Recommended preset. */
  preset: PresetReference;

  /** Confidence in this recommendation. 0-1. */
  confidence: number;

  /** Why this preset was chosen. */
  reasoning: string;

  /** Alternative presets, ranked. */
  alternatives: PresetReference[];
}

/** Error details for a failed stage. */
export interface StageError {
  /** Error code for programmatic handling. */
  code: StageErrorCode;

  /** Human-readable error message. */
  message: string;

  /** The tool call that failed, if applicable. */
  failedToolCall?: string;

  /** Stack trace (development only). */
  stack?: string;

  /** Whether this error is recoverable via retry. */
  recoverable: boolean;

  /** Suggested recovery action. */
  recoveryHint?: string;
}

export type StageErrorCode =
  | 'TOOL_EXECUTION_FAILED'
  | 'QUALITY_GATE_FAILED'
  | 'TIMEOUT'
  | 'INVALID_INPUT'
  | 'DEPENDENCY_MISSING'
  | 'USER_CANCELLED'
  | 'MIDI_PORT_UNAVAILABLE'
  | 'FILE_WRITE_FAILED'
  | 'LLM_PARSE_FAILED'
  | 'UNKNOWN';

/** A record of a single tool invocation during a pipeline stage. */
export interface ToolCallRecord {
  /** Tool name. */
  toolName: string;

  /** ISO 8601 invocation time. */
  invokedAt: string;

  /** Duration in milliseconds. */
  durationMs: number;

  /** Whether the call succeeded. */
  success: boolean;

  /** Error message if failed. */
  error?: string;
}

// ━━━ Pipeline Configuration ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * Configuration for a pipeline run.
 * Defaults are suitable for standard song generation.
 * Can be overridden by user preferences (Phase 9) or per-request.
 */
export interface PipelineConfig {
  /** Maximum retries per stage before failing. Default: 3 (from blueprint). */
  maxRetriesPerStage: number;

  /** Total pipeline timeout in milliseconds. Default: 300000 (5 minutes). */
  pipelineTimeoutMs: number;

  /** Per-stage timeout in milliseconds. Default: 60000 (1 minute). */
  stageTimeoutMs: number;

  /** Whether to run Stage 4 sub-tasks in parallel. Default: true. */
  parallelMidiGeneration: boolean;

  /** Whether to run the quality gate (Stage 7). Requires Phase 8. Default: false until P8 ships. */
  enableQualityGate: boolean;

  /** Whether to initiate MIDI playback after assembly (Stage 8). Default: false. */
  enablePlayback: boolean;

  /** Quality gate configuration override (if enableQualityGate). */
  qualityGateConfig?: QualityGateConfig;

  /** Which stages to skip. e.g. [8] to skip playback. */
  skipStages: number[];

  /** Whether to generate A/B alternatives. Default: false (explicit request via P6-T7). */
  generateAlternatives: boolean;

  /** Number of alternatives to generate per element. Default: 3. */
  alternativeCount: number;

  /** Whether to write checkpoint files after each stage. Default: true. */
  enableCheckpoints: boolean;

  /**
   * Stages at which to pause and ask the user for approval before proceeding.
   * e.g. [2, 4] = pause after harmony generation and after MIDI generation.
   * Empty array = no approval gates (fully autonomous).
   * Default: [2] — pause after chord progression for user review.
   */
  approvalGates: number[];
}

/** Default pipeline configuration. */
export const DEFAULT_PIPELINE_CONFIG: PipelineConfig = {
  maxRetriesPerStage: 3,
  pipelineTimeoutMs: 300_000,
  stageTimeoutMs: 60_000,
  parallelMidiGeneration: true,
  enableQualityGate: false,
  enablePlayback: false,
  skipStages: [],
  generateAlternatives: false,
  alternativeCount: 3,
  enableCheckpoints: true,
  approvalGates: [2],
};

// ━━━ Recovery State ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * Recovery metadata for crash recovery and retry logic.
 * Enables resuming a pipeline from the last successful checkpoint.
 */
export interface RecoveryState {
  /** The last stage that completed successfully. 0 = none. */
  lastSuccessfulStage: number;

  /** Path to the checkpoint SongState file. */
  checkpointPath?: string;

  /** Total retry count across all stages. */
  totalRetries: number;

  /** Whether this pipeline run was resumed from a checkpoint. */
  isResumed: boolean;

  /** Previous pipeline ID if this is a resumed run. */
  previousPipelineId?: string;
}

// ━━━ Intent ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * Structured creative intent decomposed from a natural-language prompt.
 * Output of Stage 1 (P6-T1). Drives all downstream generation.
 *
 * The LLM extracts entities from the prompt; enrichment tools validate
 * and augment with genre DNA, tempo inference, and half-time detection.
 */
export interface PipelineIntent {
  /** Primary genre(s). e.g. ["neo_soul", "uk_garage"]. */
  genre: string[];

  /** Sub-genre refinements. e.g. ["deep_neo_soul", "2_step"]. */
  subGenre?: string[];

  /** Inferred or explicit tempo. */
  tempo?: number;

  /** Musical key. e.g. "Eb". Undefined = let the pipeline choose. */
  key?: string;

  /** Mode. e.g. "minor", "dorian". Undefined = natural minor default. */
  mode?: string;

  /** Mood descriptors. e.g. ["melancholic", "dreamy", "nocturnal"]. */
  mood: string[];

  /** Artist / style influences. e.g. ["Frank Ocean", "Burial"]. */
  influences: string[];

  /** Specific instrument requests. e.g. ["808 bass", "lo-fi piano", "2-step drums"]. */
  instrumentRequests: string[];

  /** Structure hints. e.g. ["no chorus", "long intro", "drop at bar 32"]. */
  structureHints: string[];

  /** Duration preference in bars. */
  duration?: { min: number; max: number };

  /** Explicit constraints. e.g. ["no vocals", "keep it simple", "no reverb"]. */
  constraints: string[];

  /** The original user prompt text, preserved verbatim. */
  rawPrompt: string;

  // ━━━ Enriched fields (computed by enrichment tool, not LLM) ━━━

  /** Artist influence analysis with genre mappings and trait extraction. */
  influenceAnalysis?: ArtistInfluence[];

  /** Interpolated GenreDNA vector from genre blend. */
  genreDNA?: GenreDNAVector;

  /** Inferred tempo with half-time detection. */
  tempoAnalysis?: TempoAnalysis;

  /** Key inference reasoning. */
  keyAnalysis?: KeyAnalysis;

  /** Creativity dial settings (from mood + constraints). */
  creativityDials?: CreativityDials;

  /** What outputs to generate (inferred from prompt or defaulted). */
  requestedOutputs: PipelineOutputType[];

  /** Ambiguities requiring user clarification via ask_user. */
  ambiguities: Ambiguity[];
}

/** Artist influence with musical trait extraction. */
export interface ArtistInfluence {
  /** Artist name as stated. */
  name: string;

  /** Extracted musical traits. */
  traits: string[];

  /** Mapped genre ID. */
  genreMapping: string;

  /** Blend weight (0-1, all influences sum to 1.0). */
  weight: number;

  /** Tempo range associated with this artist's typical work. */
  tempoRange?: [number, number];
}

/** Tempo analysis with half-time detection (blueprint Section 4). */
export interface TempoAnalysis {
  /** Resolved BPM. */
  bpm: number;

  /** How the BPM was determined. */
  source: 'explicit' | 'genre_default' | 'influence_intersection' | 'mood_inferred';

  /** Whether half-time feel was detected. */
  halfTime: boolean;

  /** Perceived BPM (= bpm if not half-time, = bpm/2 if half-time). */
  perceivedBpm: number;

  /** Confidence in this tempo choice. */
  confidence: number;

  /** Reasoning chain (for X-ray mode debugging). */
  reasoning: string;
}

/** Key inference analysis. */
export interface KeyAnalysis {
  /** Resolved key root. */
  root: string;

  /** Resolved mode. */
  mode: string;

  /** How the key was determined. */
  source: 'explicit' | 'genre_convention' | 'mood_mapping' | 'random';

  /** Confidence. */
  confidence: number;

  /** Reasoning. */
  reasoning: string;
}

/** Creativity dial settings from blueprint Section 10 (two dials, D-006). */
export interface CreativityDials {
  /** Harmonic risk: 0=safe diatonic, 0.25=borrowed chords, 0.5=modal interchange,
   *  0.75=polytonality, 0.9=free chromatic. */
  harmonic: number;

  /** Rhythmic risk: 0=straight grid, 0.25=light syncopation,
   *  0.5=cross-genre rhythms, 0.75=metric modulation, 0.9=polyrhythmic freedom. */
  rhythmic: number;
}

export type PipelineOutputType =
  | 'progression'
  | 'midi'
  | 'presets'
  | 'effects'
  | 'arrangement'
  | 'playback'
  | 'producer_notes';

/** An ambiguity detected during intent parsing that may need user clarification. */
export interface Ambiguity {
  /** What's ambiguous. */
  field: string;

  /** Why it's ambiguous. */
  reason: string;

  /** Suggested options for the user. */
  options?: string[];

  /** Default value if user doesn't clarify. */
  defaultValue?: string;

  /** Severity: 'blocking' = must ask user, 'optional' = proceed with default. */
  severity: 'blocking' | 'optional';
}

// ━━━ Alternatives (P6-T7) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * A set of alternative versions for a specific pipeline element.
 * Generated by P6-T7 (A/B Alternative Generation).
 */
export interface AlternativeSet {
  /** Unique ID. */
  readonly id: string;

  /** Which element was varied. */
  element: AlternativeElement;

  /** The alternatives, ranked by score (best first). */
  variants: Alternative[];

  /** Which variant is currently selected (index into variants[]). */
  selectedIndex: number;

  /** ISO 8601 generation time. */
  generatedAt: string;
}

export type AlternativeElement =
  | { type: 'progression'; stageOutput: StageOutput & { stage: 2 } }
  | { type: 'track'; trackId: string; role: TrackRole }
  | { type: 'preset'; trackId: string }
  | { type: 'effect_chain'; trackId: string }
  | { type: 'arrangement' };

/** A single alternative variant with its score and rationale. */
export interface Alternative {
  /** Variant label. e.g. "A (default)", "B (more chromatic)", "C (walking bass)". */
  label: string;

  /** Description of what makes this variant different. */
  description: string;

  /** Data payload — type depends on AlternativeElement.type. */
  data: unknown;

  /** File path if a file was generated for this variant. */
  filePath?: string;

  /** Quality score (if Phase 8 available). */
  qualityScore?: QualityScore;

  /** Composite score for ranking. 0-1. Computed from quality or heuristic. */
  score: number;

  /** Generation parameters that differ from the default. */
  parameterDelta: Record<string, unknown>;
}

// ━━━ Iteration (P6-T6) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * Sensitivity annotations for each SongState component.
 * When a component changes, all components sensitive to it
 * must be re-evaluated and potentially regenerated.
 *
 * From blueprint Section 13: "Each agent should declare sensitivity annotations."
 */
export interface SensitivityMap {
  /** Component name → list of components it depends on. */
  [component: string]: SensitivityEntry;
}

export interface SensitivityEntry {
  /** What this component is sensitive to. */
  sensitiveTo: SensitivityTrigger[];

  /** Estimated regeneration cost. */
  regenerationCost: 'cheap' | 'moderate' | 'expensive';

  /** Which pipeline stage regenerates this component. */
  regenerationStage: number;
}

export type SensitivityTrigger =
  | 'key'
  | 'tempo'
  | 'genre'
  | 'progression'
  | 'scale'
  | 'energy'
  | 'arrangement'
  | 'preset'
  | 'role'
  | 'mixPosition';

/**
 * Default sensitivity map from blueprint consensus.
 * Drives the blast-radius calculation in P6-T6 (Iteration & Refinement).
 */
export const DEFAULT_SENSITIVITY_MAP: SensitivityMap = {
  drums:        { sensitiveTo: ['tempo', 'genre', 'energy', 'arrangement'],
                  regenerationCost: 'moderate', regenerationStage: 4 },
  bass:         { sensitiveTo: ['key', 'progression', 'tempo', 'genre'],
                  regenerationCost: 'moderate', regenerationStage: 4 },
  chords:       { sensitiveTo: ['key', 'progression', 'scale'],
                  regenerationCost: 'moderate', regenerationStage: 4 },
  lead:         { sensitiveTo: ['key', 'progression', 'scale', 'arrangement'],
                  regenerationCost: 'moderate', regenerationStage: 4 },
  preset:       { sensitiveTo: ['genre', 'role'],
                  regenerationCost: 'cheap', regenerationStage: 5 },
  effectChain:  { sensitiveTo: ['genre', 'preset', 'mixPosition', 'tempo'],
                  regenerationCost: 'cheap', regenerationStage: 5 },
  arrangement:  { sensitiveTo: ['genre', 'energy'],
                  regenerationCost: 'moderate', regenerationStage: 3 },
  progression:  { sensitiveTo: ['key', 'scale', 'genre'],
                  regenerationCost: 'expensive', regenerationStage: 2 },
};

/**
 * A modification request parsed from user feedback during iteration.
 * Produced by P6-T6, consumed by the pipeline orchestrator for targeted re-generation.
 */
export interface ModificationRequest {
  /** Unique ID. */
  readonly id: string;

  /** Original user text. e.g. "3rd chord too bright, make darker". */
  userText: string;

  /** Parsed modification target(s). */
  targets: ModificationTarget[];

  /** Components that must be regenerated (blast radius). */
  blastRadius: string[];

  /** Estimated cost of this modification. */
  estimatedCost: 'cheap' | 'moderate' | 'expensive';

  /** Whether user confirmation is recommended (for expensive modifications). */
  confirmationRequired: boolean;
}

/** A single targeted modification within a ModificationRequest. */
export interface ModificationTarget {
  /** What component to modify. */
  component: string;

  /** JSON path within SongState. e.g. "progression.chords[2]". */
  path: string;

  /** What kind of modification. */
  operation: 'replace' | 'adjust' | 'remove' | 'add';

  /** Modification parameters (type depends on component). */
  parameters: Record<string, unknown>;
}

// ━━━ Session Manifest ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * Session manifest file — the human+machine-readable summary
 * of a complete pipeline run.
 * Written to `output/<session-id>/manifest.json`.
 */
export interface SessionManifest {
  /** Session ID. Matches directory name. */
  sessionId: string;

  /** Pipeline ID that produced this session. */
  pipelineId: string;

  /** ISO 8601 creation time. */
  createdAt: string;

  /** Original user prompt. */
  prompt: string;

  /** Resolved genre. */
  genre: string;

  /** Resolved key. */
  key: string;

  /** Resolved tempo. */
  tempo: number;

  /** Time signature. */
  timeSignature: [number, number];

  /** Total bars. */
  totalBars: number;

  /** Track count. */
  trackCount: number;

  /** All generated files with relative paths and descriptions. */
  files: ManifestFile[];

  /** Per-stage timing for performance analysis. */
  stageTimings: StageTimingEntry[];

  /** Quality score summary (if Phase 8). */
  qualityScoreSummary?: {
    composite: number;
    passed: boolean;
    harmony: number;
    rhythm: number;
    arrangement: number;
    vibe: number;
  };

  /** MUSE version that generated this session. */
  museVersion: string;
}

export interface ManifestFile {
  /** Relative path from session root. e.g. "midi/drums.mid". */
  path: string;

  /** File type. */
  type: 'progression' | 'midi' | 'state' | 'notes' | 'manifest';

  /** Human-readable description. */
  description: string;

  /** File size in bytes. */
  sizeBytes: number;
}

export interface StageTimingEntry {
  /** Stage number. */
  stage: number;

  /** Stage name. */
  name: string;

  /** Duration in milliseconds. */
  durationMs: number;

  /** Number of tool calls. */
  toolCallCount: number;

  /** Number of retries. */
  retryCount: number;
}
```

---

## PHASE 6 — FULL PIPELINE

**Goal**: Integrate all prior phases into a cohesive end-to-end pipeline. A single natural-language prompt produces: chord progressions, multi-track MIDI, preset recommendations, effect chain specifications, arrangement structures, and optionally live MIDI playback — all orchestrated through the Copilot SDK's multi-agent system.

**Task Count**: 8
**Estimated Effort**: 5–7 dev-weeks
**Critical Path Position**: P0 → P1 → P3 → P5 → **P6** → P8 → P10

---

### P6-T1: Intent Decomposition Engine

| Field | Value |
|---|---|
| **ID** | P6-T1 |
| **Name** | Intent Decomposition Engine |
| **Complexity** | L |

**Description**: Parse a natural-language song request into a structured `PipelineIntent` object that drives all downstream generation stages. This is a hybrid LLM + deterministic enrichment task. The LLM extracts entities (artists, genres, moods, tempo, key, instruments, structure) from the prompt. The enrichment tool validates extractions, resolves genre DNA vectors via interpolation, infers missing parameters from genre conventions, detects half-time tempo intersections between influences, and flags ambiguities for user clarification via `ask_user`.

**Dependencies**: P0-T7 (tool registration factory), P1-T8 (GenreDNA lookup), P2-T6 (semantic search for influence-to-genre mapping)

**SDK Integration**:
- `defineMuseTool('decompose_intent', ...)` — main decomposition tool
- `ask_user` tool — for resolving blocking ambiguities
- `hooks.onUserPromptSubmitted` — trigger intent classification to decide if full pipeline or simple query
- `systemMessage` injection — artist-to-genre mapping tables via skill file

**Input Interface**:

```typescript
/**
 * Input to the intent decomposition tool.
 * The LLM provides `llmExtraction` from its analysis of the raw prompt;
 * the tool enriches it with computed fields.
 *
 * @tool decompose_intent
 * @param rawPrompt — The user's verbatim prompt text.
 * @param llmExtraction — LLM's structured extraction (partial PipelineIntent).
 * @returns Fully enriched PipelineIntent.
 */
export interface IntentDecompositionInput {
  /** The original user prompt. */
  rawPrompt: string;

  /**
   * LLM's extraction — may have missing fields.
   * The tool fills in gaps using genre conventions and influence analysis.
   */
  llmExtraction: Partial<PipelineIntent>;
}
```

**Output Interface**:

```typescript
/**
 * Result of intent decomposition.
 * Contains the fully enriched PipelineIntent and any ambiguities.
 */
export interface IntentDecompositionResult {
  /** The enriched intent. */
  intent: PipelineIntent;

  /** Whether the intent is complete enough to proceed. */
  readyToExecute: boolean;

  /** Summary for user confirmation. */
  summary: string;

  /** Fields that were inferred (not explicit in prompt). */
  inferredFields: string[];
}
```

**Implementation Hints**:
- The LLM parses natural language; the tool validates and enriches. Never rely on LLM alone for genre DNA computation or tempo math.
- Artist → genre mapping table: embed a lookup of ~100 common artists in the skill file (`skills/harmony/artist-genre-map.json`). Entries: `{ "Frank Ocean": { genre: "neo_soul", tempo: [60, 75], traits: ["maj9 chords", "lush reverbs", "dreamy"] } }`.
- Half-time detection algorithm: when two influences have non-overlapping tempo ranges (e.g., Frank Ocean 60-75 vs. Burial 130-140), check if halving the faster range creates an intersection. If `[130/2, 140/2] = [65, 70]` overlaps `[60, 75]` → set `halfTime: true`, `bpm = mean(130, 140)`, `perceivedBpm = bpm/2`.
- Key inference from genre conventions: trap → minor keys (Am, Bm, Cm preferred), house → major keys (C, F, G preferred), jazz → any key with sharp/flat emphasis. Store in genre DNA.
- Creativity dials: extract from mood words. "dark" → harmonic risk +0.1, "experimental" → both dials +0.3, "chill" → both dials -0.1. Base from genre DNA defaults.
- If `ambiguities` has any `severity: 'blocking'` entries, set `readyToExecute: false` and the Composer agent should call `ask_user` before proceeding.
- Token budget: the enrichment skill file should be ≤ 1500 tokens.

**Testing**:

| # | Test Case | Input | Expected Outcome |
|---|-----------|-------|-----------------|
| 1 | Explicit prompt | "Trap beat, dark, 140 BPM, key of Am" | `genre: ["trap"]`, `tempo: 140`, `key: "A"`, `mode: "minor"`, `mood: ["dark"]`, no ambiguities, `readyToExecute: true` |
| 2 | Influence-based prompt | "Frank Ocean meets Burial, late-night vibes" | Half-time detected: `tempoAnalysis.halfTime: true`, `bpm: 135`, `perceivedBpm: 67.5`. Genre blend: neo_soul + uk_garage. Mood: ["late-night"]. `readyToExecute: true` |
| 3 | Ambiguous prompt | "Something warm" | Genre ambiguous → `ambiguities[0].severity: 'blocking'`, `readyToExecute: false`. Options: ["neo_soul", "lo_fi", "ambient", "gospel"] |
| 4 | All defaults | "Make me a beat" | Genre defaults to user preference or hip_hop. Tempo from genre. Key from genre. All fields marked as `inferredFields`. `readyToExecute: true` |
| 5 | Conflicting constraints | "Happy trap at 70 BPM" | Trap at 70 BPM conflicts with genre norm (130-145). `ambiguities[0].reason: "tempo 70 BPM is outside typical trap range"`, `severity: 'optional'` (proceed with requested values if user insists). |
| 6 | Multi-genre explicit | "Jazz house, complex chords, 4-on-floor, 122 BPM" | `genre: ["jazz", "house"]`, `tempo: 122`, harmonic creativity dial elevated (complexity request), `structureHints` includes "4-on-floor" influence on drum pattern. |
| 7 | Instrument-specific | "Lo-fi piano with 808s, no drums except kick" | `instrumentRequests: ["lo-fi piano", "808 bass"]`, `constraints: ["no drums except kick"]`. Proper track role inference: piano→chords, 808→sub_bass, kick→drums (solo). |

**Risk**: The LLM extraction quality depends heavily on the system prompt and few-shot examples in the skill file. Poor extraction (e.g., misidentifying "Burial" as burial-themed music rather than the artist) degrades the entire pipeline. **Mitigation**: Include the artist lookup table in the tool handler — if the LLM returns an influence name, the tool checks the lookup and corrects genre mapping deterministically. For unknown artists, fall back to the LLM's genre inference with lower confidence. Test with 50+ diverse prompts and track extraction accuracy. Target: ≥ 90% first-attempt accuracy on genre/mood/tempo.

---

### P6-T2: Pipeline Orchestrator

| Field | Value |
|---|---|
| **ID** | P6-T2 |
| **Name** | Pipeline Orchestrator (DAG Engine) |
| **Complexity** | XL |

**Description**: Implement the 8-stage pipeline DAG engine that coordinates all sub-agents to produce a complete song from a `PipelineIntent`. This is the deterministic backbone of Phase 6 — the Composer agent (P6-T8) wraps it with LLM judgment for intent parsing and iteration. The orchestrator manages stage execution, parallelism (Stage 4 sub-tasks), checkpoint persistence, progress streaming, retry logic, timeout enforcement, and crash recovery from checkpoints. It is the single owner of the `ComposerPipeline` state (C13 contract).

**Dependencies**: P6-T1 (Stage 1: intent), P1-T7 (Stage 2: progression enrichment), P6-T3 (Stage 3: arrangement), P3-T2/P3-T4/P3-T7 (Stage 4: MIDI generation+humanization), P4-T1/P4-T4 (Stage 5: presets+effects), P6-T5 (Stage 6: assembly), P6-T4 (Stage 8: file output), P5-T8 (Stage 8: playback)

**SDK Integration**:
- `defineMuseTool('run_pipeline', ...)` — main pipeline execution tool
- `defineMuseTool('resume_pipeline', ...)` — resume from checkpoint
- `defineMuseTool('get_pipeline_status', ...)` — query active pipeline
- `hooks.onPostToolUse` — update SongState after each internal tool call
- Streaming (`message_delta`) — real-time progress: "Stage 2/8: Generating harmony..."
- `ask_user` — approval gates between stages (configurable)

**Input Interface**:

```typescript
/**
 * Input to the pipeline orchestrator.
 *
 * @tool run_pipeline
 * @param intent — Fully decomposed PipelineIntent from P6-T1.
 * @param config — Optional pipeline configuration overrides.
 * @returns ComposerPipeline with all stages completed.
 */
export interface PipelineRunInput {
  /** Decomposed intent. Must have readyToExecute = true. */
  intent: PipelineIntent;

  /** Configuration overrides. Merged with DEFAULT_PIPELINE_CONFIG. */
  config?: Partial<PipelineConfig>;

  /** Session ID override. Auto-generated if not provided. */
  sessionId?: string;
}

/**
 * Input to resume a pipeline from a checkpoint.
 *
 * @tool resume_pipeline
 * @param checkpointPath — Path to checkpoint pipeline-state.json.
 * @param config — Optional config overrides for the resumed run.
 */
export interface PipelineResumeInput {
  /** Absolute path to the checkpoint file. */
  checkpointPath: string;

  /** Optional config overrides. */
  config?: Partial<PipelineConfig>;
}
```

**Output Interface**:

```typescript
/**
 * Pipeline execution result.
 * Contains the final ComposerPipeline state with all stage records.
 */
export interface PipelineRunResult {
  /** The completed pipeline state. */
  pipeline: ComposerPipeline;

  /** The final SongState (also persisted to disk). */
  songState: SongState;

  /** The session manifest (also persisted to disk). */
  manifest: SessionManifest;

  /** Output directory path. */
  outputPath: string;

  /** Human-readable completion summary. */
  summary: string;
}
```

**Implementation Hints**:
- Stage execution loop (pseudo-code):
  ```
  for stage = currentStage to 8:
    if stage in config.skipStages: mark skipped, continue
    record = initStageRecord(stage)
    for attempt = 0 to config.maxRetriesPerStage:
      try:
        result = await executeStage(stage, pipeline)
        record.output = result
        record.status = 'completed'
        updateSongState(pipeline, stage, result)
        if config.enableCheckpoints: persistCheckpoint(pipeline)
        if stage in config.approvalGates: await askUserApproval(stage, result)
        break
      catch (error):
        record.retryCount++
        if attempt == maxRetries: record.status = 'failed'; handle failure
    emit progress: "✓ Stage {stage}/8: {summary}"
  ```
- **Stage 4 parallelism**: Use `Promise.all` for up to 4 MIDI generation sub-tasks. Each sub-task calls the appropriate rhythm/melody tool independently. Note: the Copilot SDK executes tools sequentially per turn, but the DAG engine invokes tool handlers directly (not through the LLM), enabling true parallelism.
- **Checkpoint format**: Write `pipeline-state.json` to `output/<session-id>/state/`. Include full `ComposerPipeline` with all completed stage outputs. On resume, deserialize, validate schema version, and continue from `lastSuccessfulStage + 1`.
- **Progress streaming**: After each stage, emit a structured progress message via the session's response stream. Format: `"✓ Stage 2/8: Generated 8-chord progression in Eb minor (Ebm9 → Dbmaj7/F → Gbmaj9 → Abm7add11)"`.
- **Timeout enforcement**: Use `Promise.race` with a timeout promise per stage. On timeout, record `StageErrorCode.TIMEOUT` and attempt retry with simplified parameters.
- **SongState threading**: The pipeline owns a single `SongState` instance. Each stage reads from it and writes results back. After Stage 2: progression populated. After Stage 3: arrangement populated. After Stage 4: tracks array populated with MIDI sources. After Stage 5: presets and effects assigned to tracks. Stage 6: assembly reference. Stage 8: file paths finalized.
- The orchestrator does NOT use LLM calls internally — it invokes tool handler functions directly. The LLM is only involved in Stage 1 (via the Composer agent) and in the iteration loop (P6-T6).
- Error propagation: if a critical stage (1, 2, 4) fails after max retries, the entire pipeline fails with `status: 'failed'`. If a non-critical stage (7, 8) fails, the pipeline completes with `status: 'completed_partial'`.

**Testing**:

| # | Test Case | Input | Expected Outcome |
|---|-----------|-------|-----------------|
| 1 | Happy path — full pipeline | PipelineIntent: neo_soul, Eb minor, 90 BPM, 32 bars, 4 tracks | Pipeline completes. SongState has 4 tracks, arrangement with ≥3 sections, progression with ≥4 chords. All 8 stage records present with status 'completed'. Output directory contains: manifest.json, song-state.json, main.progression, 4+ .mid files. |
| 2 | Stage 4 parallelism | Config: parallelMidiGeneration=true, 4 tracks requested | Measure Stage 4 wallclock time. Should be < 2× single-track time (evidence of parallelism), not 4×. All 4 track .mid files generated correctly. |
| 3 | Stage failure + retry | Inject mock failure in Stage 2 (harmony) on first attempt | Stage 2 retryCount = 1. Stage 2 eventually completes. Pipeline completes. Recovery state records the retry. |
| 4 | Max retries exhausted | Inject persistent failure in Stage 2 (all 3 attempts fail) | Pipeline status = 'failed'. `recovery.lastSuccessfulStage = 1`. Error message includes root cause from all 3 attempts. |
| 5 | Checkpoint + resume | Run pipeline, kill after Stage 3 checkpoint. Resume from checkpoint. | Resumed pipeline starts at Stage 4. Stages 1-3 not re-executed. Final output identical to a non-interrupted run (same chord progression, same arrangement). |
| 6 | Approval gate | Config: approvalGates=[2]. Pipeline runs. | After Stage 2, pipeline pauses. User approval unblocks. Pipeline continues to Stage 3+. |
| 7 | Skip stages | Config: skipStages=[7, 8] | Stages 7 and 8 record status='skipped'. Pipeline completes at Stage 6. No quality scoring, no playback. |
| 8 | Timeout | Config: stageTimeoutMs=100 (absurdly low) | Stage times out. Retry with same params. After max retries, pipeline fails with TIMEOUT error. |
| 9 | Pipeline timing | Full pipeline run | `manifest.stageTimings` has 8 entries. Sum of stage durations ≤ totalDurationMs. No stage takes > stageTimeoutMs. |
| 10 | Partial completion | Stage 8 (playback) fails — no MIDI port | Pipeline status='completed_partial'. Stages 1-7 completed. Stage 8 has error with recovery hint: "Install loopMIDI for MIDI playback." |

**Risk**: **Critical — highest-risk task in Phase 6.** Integration of 5 prior phases means any breaking change in P1-P5 tool interfaces directly breaks the pipeline. **Mitigation**: (1) Define explicit adapter interfaces between the orchestrator and each phase's tools — decoupling the pipeline from internal tool signatures. (2) Integration test suite that exercises every tool used by the pipeline with representative inputs. (3) Mock tool handlers for CI that return structurally valid but simplified outputs — enabling pipeline shape testing without full P1-P5 stack. **Secondary risk**: Pipeline latency — 8 stages × 3-5s per stage = 24-40s best case. With parallelism at Stage 4, target < 30s total. Without LLM in the loop (DAG engine calls tool handlers directly), stages 2-8 should be sub-second each (pure computation), with the LLM only involved in Stage 1. Total: 5-10s achievable.

---

### P6-T3: Arrangement Generator

| Field | Value |
|---|---|
| **ID** | P6-T3 |
| **Name** | Arrangement Structure Generator |
| **Complexity** | M |

**Description**: Generate a song's macro structure (sections, energy arc, transitions, per-section track activation) from the `PipelineIntent` and a chord progression. Implements genre-normative song forms from the blueprint (Section 4): Pop/RnB verse-chorus, House/EDM intro-build-drop, Trap verse-hook, Jazz head-solo-head. Maps the chord progression across sections (loop, vary, or subset per section). Computes the energy arc as a continuous function sampled per bar. Assigns track activation per section to create dynamic arrangement.

**Dependencies**: P6-T1 (intent for genre and structure hints), P1-T7 (enriched progression for chord progression data), C1 SongState (Arrangement type)

**SDK Integration**:
- `defineMuseTool('generate_arrangement', ...)` — main arrangement tool
- Skill file: `skills/harmony/arrangement-templates.json` (~1000 tokens)

**Input Interface**:

```typescript
/**
 * Input to arrangement generation.
 *
 * @tool generate_arrangement
 * @param intent — PipelineIntent with genre, duration, energy preferences.
 * @param progression — The chord progression to arrange across sections.
 * @param trackRoles — Track roles that will be generated (for activation planning).
 * @returns Arrangement structure conforming to C1 contract.
 */
export interface ArrangementGeneratorInput {
  /** Pipeline intent (genre, duration, energy, structure hints). */
  intent: PipelineIntent;

  /** The chord progression (enriched). */
  progression: EnrichedProgression;

  /** Track roles to plan activation for. */
  trackRoles: TrackRole[];

  /** Total desired bars. If unspecified, derived from genre conventions. */
  totalBars?: number;
}
```

**Output Interface**:

```typescript
/**
 * Generated arrangement structure.
 * Directly populates SongState.arrangement.
 */
export interface ArrangementGeneratorResult {
  /** The arrangement (C1 contract). */
  arrangement: Arrangement;

  /** Chord-to-section mapping. Maps each section to the chord indices it uses. */
  chordSectionMap: Record<string, number[]>;

  /** Per-section track activation plan. */
  trackActivation: Record<string, TrackRole[]>;

  /** Template used (for X-ray mode). */
  templateUsed: string;

  /** Summary for user display. */
  summary: string;
}
```

**Implementation Hints**:
- Genre form templates (stored in skill file JSON):
  ```
  pop_rnb:    Intro(4) → Verse(8) → PreChorus(4) → Chorus(8) → Verse(8) → Chorus(8) → Bridge(8) → Chorus(8) → Outro(4) = 60 bars
  house_edm:  Intro(16) → Build(8) → Drop(16) → Break(8) → Build(8) → Drop(16) → Outro(8) = 80 bars
  trap:       Intro(4) → Verse(16) → Hook(8) → Verse(16) → Hook(8) → Outro(4) = 56 bars
  jazz:       Head(16) → SoloA(16) → SoloB(16) → Head(16) = 64 bars
  lo_fi:      Intro(4) → LoopA(16) → LoopB(16) → LoopA(16) → Outro(4) = 56 bars
  ```
- Energy arc calculation: assign each section type a base energy: Intro=0.2, Verse=0.5, PreChorus=0.65, Chorus/Drop=0.9, Bridge=0.5, Break=0.3, Outro=0.2. Interpolate between section boundaries for smooth arc. Sample at every bar.
- Track activation progressive building:
  - Intro: pad only (or pad + sparse drums)
  - Verse: +bass, +drums (half pattern)
  - Chorus/Drop: all tracks active
  - Break: strip to 1-2 elements
  - Outro: subtractive (elements drop out one by one)
- Chord-to-section mapping: if progression has 4 chords and verse has 8 bars, loop the progression 2×. If chorus, use same progression or a contrasting subset. `structureHints` from intent can override defaults.
- Transition types from genre: House uses "build"→"drop", Pop uses "cut" or "fade", Trap uses "cut".
- If `intent.duration` is specified, scale the template proportionally. Minimum section length: 4 bars.

**Testing**:

| # | Test Case | Input | Expected Outcome |
|---|-----------|-------|-----------------|
| 1 | Pop arrangement | genre=pop, 64 bars, 4 tracks | ≥4 sections (Intro, Verse, Chorus, Outro minimum). Choruses have highest energy. All tracks active in at least one section. Total bars = 64 (±4 bar rounding). |
| 2 | House arrangement | genre=house, default duration | Contains Build and Drop sections. Drop energy > Build energy. Intro ≥ 8 bars. |
| 3 | Energy arc continuity | Any genre | Energy arc sampled at every bar. No adjacent bars differ by > 0.3 (smooth). Peak energy at Chorus/Drop. Valley at Break/Intro. |
| 4 | Chord-section mapping | 4-chord progression, 16-bar verse | Verse maps to chord indices [0,1,2,3,0,1,2,3] (loop). All section chord arrays are valid indices. |
| 5 | Track activation | 4 tracks: drums, bass, chords, lead | Intro: ≤2 tracks. Chorus: all 4 tracks. At least one section has fewer tracks than chorus (dynamic contrast). |
| 6 | Custom duration | duration: min=24, max=32 | Total bars between 24 and 32 (inclusive). Sections scaled proportionally. |
| 7 | Structure hints | structureHints: ["no chorus", "loop-based"] | No section named "Chorus". Structure resembles lo-fi/ambient template. |

**Risk**: Genre template coverage — initial templates cover ~5 forms. Uncommon genres (Afrobeat, Latin, Ambient, Experimental) may not have well-defined forms. **Mitigation**: Fallback to a generic "ABAB" template with genre-appropriate energy levels. Mark template as `"generic_fallback"` in the result for X-ray transparency. Expand templates incrementally as genre coverage grows.

---

### P6-T4: Output File Manager

| Field | Value |
|---|---|
| **ID** | P6-T4 |
| **Name** | Output File Manager |
| **Complexity** | M |

**Description**: Manage the output directory structure for generated sessions. Creates the session directory tree, writes all generated files atomically (write-to-temp then rename), produces the session manifest, and generates human-readable producer notes describing how to load the session into MPC Beats. Handles file naming, deduplication, and cleanup of incomplete sessions.

**Dependencies**: P0-T1 (project scaffold for output root path), P3-T2 (MIDI writer for .mid validation)

**SDK Integration**:
- `defineMuseTool('write_session_output', ...)` — main file-writing tool
- `defineMuseTool('list_sessions', ...)` — enumerate past sessions
- `defineMuseTool('clean_sessions', ...)` — remove incomplete/old sessions
- Permission handler: first file write per session requires user confirmation

**Input Interface**:

```typescript
/**
 * Input to the session output writer.
 *
 * @tool write_session_output
 * @param sessionId — Unique session identifier.
 * @param songState — The completed SongState to persist.
 * @param pipeline — The ComposerPipeline state for stage timings.
 * @param files — Generated file payloads to write.
 * @returns SessionManifest + file paths.
 */
export interface OutputWriterInput {
  /** Session ID. Format: "session-{YYYYMMDD}-{random6}". */
  sessionId: string;

  /** Final SongState. */
  songState: SongState;

  /** Pipeline state for timing data. */
  pipeline: ComposerPipeline;

  /** File payloads to write. */
  files: OutputFilePayload[];
}

/** A file payload to be written to the output directory. */
export interface OutputFilePayload {
  /** Relative path within session directory. e.g. "midi/drums.mid". */
  relativePath: string;

  /** File content. Buffer for binary (MIDI), string for text (JSON, markdown). */
  content: Buffer | string;

  /** File type for manifest. */
  type: ManifestFile['type'];

  /** Description for manifest. */
  description: string;
}
```

**Output Interface**:

```typescript
/**
 * Result of writing session output.
 */
export interface OutputWriterResult {
  /** Absolute path to the session directory. */
  sessionPath: string;

  /** Written manifest. */
  manifest: SessionManifest;

  /** Per-file write results. */
  fileResults: { path: string; success: boolean; error?: string }[];

  /** Path to generated producer notes. */
  producerNotesPath: string;
}
```

**Implementation Hints**:
- Directory structure:
  ```
  output/
  └── session-20260209-a1b2c3/
      ├── manifest.json
      ├── state/
      │   ├── song-state.json
      │   └── pipeline-state.json
      ├── progression/
      │   └── main.progression
      ├── midi/
      │   ├── drums.mid
      │   ├── bass.mid
      │   ├── chords.mid
      │   ├── lead.mid
      │   └── full-arrangement.mid
      └── notes/
          ├── preset-assignments.md
          ├── effect-chains.md
          ├── arrangement-map.md
          └── producer-notes.md
  ```
- Atomic writes: write to `<target>.tmp`, then `fs.rename` to final path. If the process crashes mid-write, only `.tmp` files remain (cleaned up by `clean_sessions`).
- Session ID format: `session-{YYYYMMDD}-{crypto.randomBytes(3).toString('hex')}`. e.g. `session-20260209-a1b2c3`.
- `producer-notes.md` generation — template:
  ```markdown
  # 🎵 Session: {prompt summary}
  **Genre**: {genre} | **Key**: {key} {mode} | **Tempo**: {bpm} BPM | **Bars**: {totalBars}

  ## Quick Start — MPC Beats Setup
  1. Open MPC Beats
  2. Set tempo to {bpm} BPM
  3. Create {trackCount} tracks:
     {for each track:}
     - **Track {n} ({role})**: Load {engine} → Preset "{presetName}". Import `midi/{trackFile}`
  4. Apply effect chains (see effect-chains.md)
  5. Set arrangement markers (see arrangement-map.md)

  ## Files
  {table of all files with descriptions}
  ```
- `list_sessions`: scan `output/` directory for `session-*` subdirectories. Return session ID, creation date, and manifest summary if `manifest.json` exists.
- `clean_sessions`: remove sessions older than N days, or sessions missing `manifest.json` (incomplete). Confirm via `ask_user`.

**Testing**:

| # | Test Case | Input | Expected Outcome |
|---|-----------|-------|-----------------|
| 1 | Full session write | SongState + 5 file payloads | Session directory created. All 5 files written. `manifest.json` parseable. `song-state.json` round-trips through SongState schema. |
| 2 | Atomic write safety | Kill process mid-write (simulate) | Only `.tmp` files remain. No partial final files. `clean_sessions` removes the orphaned `.tmp` files. |
| 3 | Producer notes | 4-track neo-soul session | `producer-notes.md` contains correct BPM, key, track names, preset names. Markdown renders correctly. |
| 4 | Manifest completeness | Full pipeline output | `manifest.files` contains entries for: manifest.json, song-state.json, pipeline-state.json, main.progression, ≥1 .mid files, producer-notes.md. All `sizeBytes > 0`. |
| 5 | List sessions | 3 sessions exist in output/ | Returns 3 entries sorted by creation date (newest first). Each has sessionId, date, and genre from manifest. |
| 6 | Clean incomplete | One session lacks manifest.json | `clean_sessions` identifies it as incomplete. After user confirmation, removes it. Valid sessions untouched. |
| 7 | Idempotent write | Write same session twice | Second write overwrites cleanly. No duplicate files. Manifest updated timestamp changes. |

**Risk**: File permissions — MUSE needs write access to the workspace `output/` directory. On some systems, VS Code's process may not have write access to arbitrary directories. **Mitigation**: default to workspace root `output/` (VS Code workspace always writable), but allow user override via config. Detect permission errors and provide clear guidance.

---

### P6-T5: Multi-Track Assembly Tool

| Field | Value |
|---|---|
| **ID** | P6-T5 |
| **Name** | Multi-Track MIDI Assembly |
| **Complexity** | M |

**Description**: Combine individual per-track MIDI files into a single multi-track MIDI file (SMF Format 1) with arrangement structure applied. Each track becomes a separate MIDI track with proper channel assignment, track name meta-events, and tempo map. Applies the arrangement by muting/unmuting tracks per section (via note filtering) and inserting section markers as MIDI text events. The assembled file can be imported into MPC Beats as a complete session reference.

**Dependencies**: P3-T1 (MIDI parser for reading individual tracks), P3-T2 (MIDI writer for Format 1 output), P6-T3 (arrangement structure for section mapping)

**SDK Integration**:
- `defineMuseTool('assemble_tracks', ...)` — main assembly tool

**Input Interface**:

```typescript
/**
 * Input to multi-track assembly.
 *
 * @tool assemble_tracks
 * @param tracks — Individual track MIDI files with role assignments.
 * @param arrangement — Arrangement structure (sections, track activation).
 * @param tempo — BPM for the tempo track.
 * @param timeSignature — Time signature.
 * @param outputPath — Where to write the assembled file.
 * @returns Path to assembled multi-track .mid file.
 */
export interface TrackAssemblyInput {
  /** Per-track MIDI file paths and metadata. */
  tracks: TrackAssemblyEntry[];

  /** Arrangement structure from P6-T3. */
  arrangement: Arrangement;

  /** Track activation map: section name → active track IDs. */
  trackActivation: Record<string, string[]>;

  /** BPM. */
  tempo: number;

  /** Time signature. Default: [4, 4]. */
  timeSignature?: [number, number];

  /** Output file path. */
  outputPath: string;
}

/** A single track entry for assembly. */
export interface TrackAssemblyEntry {
  /** Track ID (matches SongState track ID). */
  trackId: string;

  /** Path to the individual .mid file. */
  midiFilePath: string;

  /** Track name for MIDI meta-event. */
  trackName: string;

  /** MIDI channel assignment (0-15). */
  channel: number;

  /** Track role (for arrangement filtering). */
  role: TrackRole;
}
```

**Output Interface**:

```typescript
/**
 * Result of track assembly.
 */
export interface TrackAssemblyResult {
  /** Path to the assembled multi-track .mid file. */
  outputPath: string;

  /** MIDI file stats. */
  stats: {
    trackCount: number;
    totalEvents: number;
    totalBars: number;
    durationSeconds: number;
    fileSizeBytes: number;
  };

  /** Section markers inserted. */
  sectionMarkers: { bar: number; name: string }[];
}
```

**Implementation Hints**:
- **Track 0 (conductor track)**: contains Set Tempo meta-event, Time Signature meta-event, and section marker Text Events (`FF 01 len "Verse A"` at appropriate ticks). No note data.
- **Tracks 1-N**: one per instrument. Each has Track Name meta-event (`FF 03 len "Drums"`). Note events from the source file, filtered by arrangement activation.
- **Arrangement application**: for each section, check `trackActivation[sectionName]`. If a track is NOT active in a section, remove all note events in that section's bar range. This creates genuine silence in the MIDI file rather than relying on DAW muting.
- **Channel assignment**: drums → channel 9 (GM standard, 0-indexed), bass → channel 1, chords → channel 2, lead → channel 3, pad → channel 4. Configurable via `TrackAssemblyEntry.channel`.
- **Bar-to-tick conversion**: `ticksPerBar = ticksPerBeat × timeSignature[0]`. Section boundaries: `startTick = (section.startBar - 1) × ticksPerBar`, `endTick = section.endBar × ticksPerBar`.
- **Transition handling**: at section boundaries with `type: "fade"`, insert CC7 (volume) ramp from 127→0 over the last 2 bars. For `type: "build"`, insert CC1 (mod wheel) ramp from 0→127 over the last 4 bars. For `type: "filter_sweep"`, insert CC74 (cutoff) ramp.
- **PPQ**: use 480 ticks per quarter note (standard). Match source file PPQ; re-scale ticks if source files use different PPQ.
- The assembled file should be importable into MPC Beats, Ableton, Logic, or any SMF-compliant DAW.

**Testing**:

| # | Test Case | Input | Expected Outcome |
|---|-----------|-------|-----------------|
| 1 | 4-track assembly | drums, bass, chords, lead + 3-section arrangement | Output is valid SMF Format 1 with 5 tracks (conductor + 4). Parse back with P3-T1 → 4 note tracks + tempo track. |
| 2 | Arrangement filtering | Bass inactive in Intro section (bars 1-4) | No bass notes in ticks 0 to (4×480×4). Bass notes present in subsequent sections. |
| 3 | Section markers | 3 sections: Intro, Verse, Chorus | Track 0 contains 3 text meta-events at correct tick positions. |
| 4 | Channel assignment | drums=ch9, bass=ch1, chords=ch2, lead=ch3 | All note events on each track use the assigned channel. No channel conflicts. |
| 5 | Transition — fade | Transition type "fade" between Verse→Chorus | CC7 ramp (127→0) in last 2 bars of Verse on fading track. |
| 6 | Round-trip | Assemble → parse back → verify note counts | Total notes in assembled file = sum of notes in active sections across all tracks. |
| 7 | PPQ normalization | Source files at 480 PPQ and 960 PPQ mixed | Output uses single PPQ (480). Ticks correctly scaled for the 960-source file. |

**Risk**: Large MIDI files (100+ bars, 4+ tracks) can have thousands of events. Performance should remain acceptable — target < 500ms for assembly of 100-bar, 4-track files. **Mitigation**: use pre-allocated arrays and avoid repeated array resizing. Most complex part is tick re-calculation for PPQ normalization — test with edge cases (prime-number PPQ values). Secondary risk: some DAWs are strict about SMF Format 1 compliance (track chunk sizes, end-of-track events). Validate output with an external MIDI validator.

---

### P6-T6: Iteration & Refinement Loop

| Field | Value |
|---|---|
| **ID** | P6-T6 |
| **Name** | Iteration & Refinement Loop |
| **Complexity** | XL |

**Description**: Enable surgical re-generation of individual song elements in response to user feedback, without re-running the entire pipeline. Parses a modification request, computes the blast radius (which downstream components are affected), regenerates only the affected components, and updates the SongState and output files. Implements the sensitivity annotation system from the blueprint (Section 13) and the contradiction handling strategies (temporal override, scope detection, synthesis). This is what makes MUSE iterative rather than one-shot.

**Dependencies**: P6-T2 (pipeline orchestrator for partial re-execution), P6-T4 (file manager for updating output files), C1 SongState (history), C13 ComposerPipeline (stage records)

**SDK Integration**:
- `defineMuseTool('modify_song', ...)` — main modification tool
- `defineMuseTool('undo_change', ...)` — revert last change using history
- `hooks.onPostToolUse` — record change to SongState.history after each modification
- `ask_user` — confirm expensive modifications (key change = full re-gen)
- `infiniteSessions` — iteration can extend sessions beyond 50 turns

**Input Interface**:

```typescript
/**
 * Input to the modification tool.
 *
 * @tool modify_song
 * @param userText — The user's modification request in natural language.
 * @param songState — Current SongState (injected from session context).
 * @param parsedModification — LLM-parsed modification (optional; tool can re-parse).
 * @returns Updated SongState + list of regenerated components.
 */
export interface ModifySongInput {
  /** User's modification request text. */
  userText: string;

  /** Current SongState. */
  songState: SongState;

  /** Pipeline state (for re-executing specific stages). */
  pipeline: ComposerPipeline;

  /**
   * LLM-parsed modification targets (optional).
   * If provided, the tool validates and computes blast radius.
   * If not provided, the tool uses heuristics to parse.
   */
  parsedTargets?: ModificationTarget[];
}

/**
 * Input to the undo tool.
 *
 * @tool undo_change
 * @param songState — Current SongState with history.
 * @param steps — Number of changes to undo. Default: 1.
 * @returns Reverted SongState.
 */
export interface UndoInput {
  songState: SongState;
  steps?: number;
}
```

**Output Interface**:

```typescript
/**
 * Result of a song modification.
 */
export interface ModifySongResult {
  /** Updated SongState. */
  songState: SongState;

  /** What was regenerated. */
  regeneratedComponents: string[];

  /** What was preserved (unchanged). */
  preservedComponents: string[];

  /** Files updated on disk. */
  updatedFiles: string[];

  /** Modification cost classification. */
  cost: 'cheap' | 'moderate' | 'expensive';

  /** Human-readable summary of changes. */
  summary: string;

  /** History entry recorded. */
  historyEntry: HistoryEntry;
}
```

**Implementation Hints**:
- **Blast radius algorithm**:
  1. Parse modification → identify changed component(s) and changed field(s)
  2. Consult `DEFAULT_SENSITIVITY_MAP` → find all components sensitive to changed field(s)
  3. For each affected component, check: is it generated yet? If yes, mark for regeneration.
  4. Transitively: if regenerated component X is itself a sensitivity trigger for component Y, mark Y too.
  5. Sort regeneration order by stage number (ascending) to maintain correct data flow.
  6. Example: change `key` → triggers: progression, chords, bass, lead (all sensitive to `key`). Drums sensitive to `tempo` and `genre` but NOT `key` → preserved.
- **Modification classification**:
  - `cheap`: change preset, adjust effect parameter, change pan/volume → single file update, no MIDI regeneration
  - `moderate`: change one chord, simplify bassline, add ghost notes → 1-2 MIDI files regenerated
  - `expensive`: change key, change genre, change tempo → most components regenerate
- **Confirmation for expensive modifications**: if `cost === 'expensive'`, use `ask_user`: "Changing the key will regenerate the progression, bass, chords, and lead tracks. Drums will be preserved. Proceed?"
- **Contradiction handling** (from blueprint):
  - Temporal override: "make it warmer" then "make it brighter" → latest wins (brightness applied after warmth, potentially overriding).
  - Scope detection: "make the bass warmer" vs. "make it warmer" — detect scope from user text. If ambiguous, ask: "Do you mean the bass specifically, or the overall mix?"
  - Synthesis: "warm + bright" → EQ: boost low-mids (warm) and air (bright). Different frequency ranges, not contradictory.
- **History recording**: every modification appends to `SongState.history[]`. Each `HistoryEntry` records the user request, agent used, and atomic `Change[]` with JSON paths and before/after values. This enables undo and preference learning (Phase 9).
- **Undo**: pop the last `HistoryEntry`, apply `Change[].previousValue` to each path. Regenerate affected files. Multi-step undo: apply N entries in reverse order.
- **Partial pipeline re-execution**: when regenerating (e.g., bass track), create a minimal pipeline context with the current SongState and invoke only Stage 4 (sub-task: bass) → Stage 5 (preset re-check) → Stage 6 (re-assemble). The orchestrator supports targeted stage execution via a `stages` parameter.

**Testing**:

| # | Test Case | Input | Expected Outcome |
|---|-----------|-------|-----------------|
| 1 | Single chord change | "3rd chord too bright, make darker" | Only `progression.chords[2]` modified. Chord MIDI track regenerated. Bass regenerated (sensitive to progression). Drums unchanged. `historyEntry` recorded with path `progression.chords[2].midiNotes`. |
| 2 | Density reduction | "Bass too busy, simplify" | Bass MIDI file regenerated with lower density. Progression unchanged. Drums unchanged. Cost: moderate. |
| 3 | Preset change | "Use a warmer pad preset" | Only `tracks[n].preset` updated. No MIDI regeneration. Effect chain re-evaluated (sensitive to preset). Cost: cheap. |
| 4 | Key change (expensive) | "Change to F# minor" | Confirmation prompt fired. After confirmation: progression, chords, bass, lead all regenerated. Drums preserved (not sensitive to key). Cost: expensive. |
| 5 | Tempo change | "Slow it down to 85 BPM" | All time-based parameters recalculated (delay times, reverb pre-delay). Drums regenerated (sensitive to tempo). Effect chains updated. |
| 6 | Undo single step | After change from test 1, "undo that" | SongState reverted to pre-test-1 state. Chord restored to original. Affected files regenerated back. |
| 7 | Undo 3 steps | 3 modifications applied, then undo_change(steps=3) | SongState reverted to 3 changes ago. All intermediate changes unwound. History entries preserved (not deleted — marked as undone). |
| 8 | Contradiction — scope | "Make it warmer" after "make the bass brighter" | "Warmer" detected as global scope → applies warmth to all effect chains. Bass brightness preserved (different frequency range — synthesis strategy). |
| 9 | No-op modification | "The bass sounds great" (praise, not a change) | No changes made. Response acknowledges feedback. No history entry. |
| 10 | Cascading regeneration | Change genre from neo_soul to trap | Blast radius: progression (genre-sensitive), drums (genre-sensitive), bass (genre-sensitive), presets (genre-sensitive), effects (genre-sensitive). Nearly full re-gen. Only arrangement structure shape preserved if still compatible. |

**Risk**: **Blast radius over-computation** — conservative sensitivity analysis may regenerate too many components for minor changes, destroying user-approved content. **Mitigation**: (1) Track which components the user has explicitly approved (via `approvalGates` or verbal approval). Approved components get a `frozen: true` flag that prevents regeneration unless their dependency is directly changed. (2) Present the blast radius to the user before executing expensive modifications. (3) Limit transitive sensitivity depth to 2 levels — prevent runaway cascades. **Secondary risk**: Undo with 10+ changes creates complex state rollback. Keep the history as an append-only log and re-derive state from scratch if needed (replay forward from initial state minus undone changes).

---

### P6-T7: A/B Alternative Generation

| Field | Value |
|---|---|
| **ID** | P6-T7 |
| **Name** | A/B Alternative Generation |
| **Complexity** | L |

**Description**: Generate 2-3 alternative versions of any pipeline element (progression, track, preset, effect chain, arrangement) for user comparison and selection. Each alternative is generated with systematically varied parameters: variant A = default/best-match, variant B = elevated creativity dial, variant C = different structural approach. Alternatives are scored (heuristically in Phase 6; via Phase 8 critics when available), ranked, and presented with natural-language descriptions of their differences. Unused alternatives are cached in the `AlternativeSet` for retrieval if the user says "try something different."

**Dependencies**: P6-T2 (pipeline orchestrator for re-running stages with varied params), P6-T6 (iteration loop for applying selected alternative), P1-P4 tools (for generating individual elements)

**SDK Integration**:
- `defineMuseTool('generate_alternatives', ...)` — create alternatives for an element
- `defineMuseTool('select_alternative', ...)` — apply a chosen alternative to SongState
- `defineMuseTool('next_alternative', ...)` — cycle to next alternative for current element
- `ask_user` — present alternatives with descriptions for user selection

**Input Interface**:

```typescript
/**
 * Input to generate alternatives for a pipeline element.
 *
 * @tool generate_alternatives
 * @param element — What to generate alternatives for.
 * @param songState — Current SongState for context.
 * @param count — Number of alternatives to generate. Default: 3.
 * @returns AlternativeSet with ranked variants.
 */
export interface GenerateAlternativesInput {
  /** Which element to vary. */
  element: AlternativeElement;

  /** Current SongState for context. */
  songState: SongState;

  /** Pipeline intent (for constraint context). */
  intent: PipelineIntent;

  /** Number of alternatives. Default: 3, max: 5. */
  count?: number;
}

/**
 * Apply a selected alternative to the SongState.
 *
 * @tool select_alternative
 * @param alternativeSetId — Which alternative set.
 * @param variantIndex — Which variant to select (0-based).
 * @param songState — Current SongState.
 * @returns Updated SongState with selected alternative applied.
 */
export interface SelectAlternativeInput {
  /** AlternativeSet ID. */
  alternativeSetId: string;

  /** Variant index (0-based). */
  variantIndex: number;

  /** Current SongState. */
  songState: SongState;
}
```

**Output Interface**:

```typescript
/**
 * Result of alternative generation.
 */
export interface GenerateAlternativesResult {
  /** The generated alternative set. */
  alternativeSet: AlternativeSet;

  /** Formatted comparison for user display. */
  comparisonText: string;

  /**
   * Example comparison format:
   *
   * **Option A** (score 0.82) — Default:
   *   Traditional II-V-I progression with smooth voice leading.
   *
   * **Option B** (score 0.78) — More chromatic:
   *   Adds chromatic mediant in bar 3, creating unexpected color.
   *
   * **Option C** (score 0.71) — Walking bass approach:
   *   Replaces chord tones with chromatic walkdowns, Burial influence.
   */
}

/**
 * Result of selecting an alternative.
 */
export interface SelectAlternativeResult {
  /** Updated SongState. */
  songState: SongState;

  /** What was changed (for history). */
  changesSummary: string;

  /** Updated files. */
  updatedFiles: string[];
}
```

**Implementation Hints**:
- **Variant generation strategy**:
  - Variant A: default parameters (the generation that would normally happen)
  - Variant B: bump `creativityDials.harmonic` by +0.15 and/or `creativityDials.rhythmic` by +0.15
  - Variant C: structural variation — for progressions: different root motion (ascending vs. descending); for bass: different style (walking vs. syncopated); for drums: different pattern family (boom-bap vs. trap vs. 4-on-floor)
  - Variant D/E (if count > 3): combine B's creativity with C's structural change; or use a different genre influence
- **Scoring heuristic** (pre-Phase 8): simple multi-criteria score:
  - Harmonic: count of non-diatonic chords / total chords → penalize > 50%
  - Rhythmic: density variance from genre norm → penalize large deviations
  - Consonance: average tension value → compare to genre norm range
  - Composite = weighted average, 0-1
- **"Try something different" flow**: when user says "try something different" for an element:
  1. Find the active `AlternativeSet` for that element
  2. Advance `selectedIndex` to the next variant
  3. Apply via `select_alternative`
  4. If all candidates exhausted, regenerate new batch with `creativityDials` + 0.2 and `temperature` bump
- **Caching**: store `AlternativeSet` objects in `ComposerPipeline.alternatives[]`. Persist to disk with checkpoints. Unused alternatives remain available for the entire session.
- **Presentation**: format comparison as structured text with labels, scores, and 1-sentence descriptions. Use `ask_user` to present choices: "Which do you prefer? A, B, or C?"

**Testing**:

| # | Test Case | Input | Expected Outcome |
|---|-----------|-------|-----------------|
| 1 | 3 progression alternatives | element: progression, count=3 | 3 variants returned. All are valid EnrichedProgressions in the same key. At least 2 are meaningfully different (different chord symbols or voicings). All scored 0-1. |
| 2 | Alternatives are different | Generate 3 bass alternatives | Variant A ≠ Variant B ≠ Variant C (compare note arrays). Hash-based deduplication: no two variants have identical note sequences. |
| 3 | Select alternative B | Select variant index 1 | SongState updated with variant B's data. Affected downstream components flagged for regeneration. History entry recorded. |
| 4 | Cycle through alternatives | "Try something different" 3 times | Selection cycles: A→B→C→regenerate new batch. New batch has higher creativity parameters. |
| 5 | Score ranking | All variants scored | Variants sorted by score descending. Variant A (default) typically scores highest. |
| 6 | Cache persistence | Generate alternatives, checkpoint, resume | AlternativeSet survives checkpoint/resume. No regeneration needed for cached alternatives. |
| 7 | Max alternatives | count=5 | 5 variants generated. Each meaningfully different. No crashes or timeouts. |

**Risk**: Alternative generation multiplies pipeline computation — 3 alternatives × 1 stage = 3× the cost. For expensive elements (full progression), this adds 3-10s. **Mitigation**: generate alternatives lazily (only when user requests them, not proactively). For `config.generateAlternatives = true` (proactive mode), run alternative generation in parallel with Stage 7 (validation) to hide latency. **Secondary risk**: alternatives may not be "meaningfully different" if the parameter space is too constrained. Implement a diversity check: minimum edit distance between variants. If variants are too similar, increase the creativity dial delta.

---

### P6-T8: Composer Agent Definition

| Field | Value |
|---|---|
| **ID** | P6-T8 |
| **Name** | Composer Agent Definition |
| **Complexity** | M |

**Description**: Define the master Composer agent that orchestrates the full pipeline via the Copilot SDK's `customAgents` system. The Composer agent is the "god agent" — it has access to all tools, handles complex multi-step requests, and delegates domain-specific queries to specialist agents. Its system prompt encodes the pipeline stage descriptions, sensitivity annotation table, iteration philosophy, and the Frank Ocean meets Burial walkthrough as a reference example. This task also defines the intent classification logic that routes user queries to the Composer vs. domain agents.

**Dependencies**: P6-T1 through P6-T7 (all pipeline tools), P0-T7 (tool registration factory), P0-T2 (system message template engine), all prior phase agent configs (P1-T8, P3-T8, P4-T8)

**SDK Integration**:
- `customAgents` configuration — the Composer agent definition
- `hooks.onUserPromptSubmitted` — intent classification for pipeline vs. domain routing
- `systemMessage` — dynamic L0/L1 SongState injection
- `infiniteSessions` — pipeline + iteration sessions are long-lived
- Streaming — progress reporting during pipeline execution

**Input Interface**:

```typescript
/**
 * Composer agent configuration for the Copilot SDK customAgents array.
 * This is the agent definition, not a tool input.
 */
export interface ComposerAgentConfig {
  /** Agent identifier. */
  name: 'composer';

  /** Display name in UI. */
  displayName: 'Composer';

  /** Description for SDK router's infer logic. */
  description: string;

  /** System prompt builder function. */
  prompt: string;

  /** Tool access — all tools ("*"). */
  tools: ['*'];

  /** Enable automatic routing. */
  infer: true;
}

/**
 * Intent classification result.
 * Determines whether a user query should route to the Composer
 * or a domain-specific agent.
 *
 * Implemented in hooks.onUserPromptSubmitted.
 */
export interface IntentClassification {
  /** Target agent. */
  agent: 'composer' | 'harmony' | 'rhythm' | 'sound' | 'mix' | 'controller';

  /** Why this routing was chosen. */
  reasoning: string;

  /** Whether this is a pipeline trigger (full generation request). */
  isPipelineTrigger: boolean;

  /** Confidence in routing decision. */
  confidence: number;
}
```

**Output Interface**:

```typescript
/**
 * The built Composer agent configuration object,
 * ready for inclusion in the customAgents array.
 */
export interface ComposerAgentBuildResult {
  /** The agent config. */
  agentConfig: ComposerAgentConfig;

  /** The skill directory path. */
  skillPath: string;

  /** Token count of the prompt. */
  promptTokenCount: number;

  /** List of all tools accessible. */
  toolList: string[];
}
```

**Implementation Hints**:
- **Agent description** (critical for `infer: true` routing accuracy):
  ```
  "End-to-end song generation and arrangement orchestrator. Handles requests
  that involve creating complete songs, beats, or multi-track compositions
  from natural language descriptions. Coordinates harmony, rhythm, sound design,
  and mix engineering. Use for: 'compose a song', 'create a beat', 'make me a
  track', 'generate a full arrangement', or any request involving multiple
  musical domains simultaneously. Also handles iterative refinement of
  generated songs."
  ```
- **Composer system prompt** (stored in `skills/composer/SKILL.md`, ≤ 3000 tokens):
  1. Pipeline overview (8 stages, 1 paragraph)
  2. Stage descriptions (8 × 1 sentence = ~100 tokens)
  3. Sensitivity annotation table (from `DEFAULT_SENSITIVITY_MAP`, ~150 tokens)
  4. Iteration philosophy: "Change only what's necessary. Use blast-radius analysis to determine the minimum re-generation set. Prefer surgical edits over full re-runs."
  5. Quality philosophy: "No axis below 0.5. Average ≥ 0.7. Vibe has veto power."
  6. Reference walkthrough: condensed Frank Ocean × Burial example (~200 tokens)
  7. Behavioral rules: "For simple domain queries (e.g., 'what key is this in?'), delegate to the appropriate domain agent. Only invoke the full pipeline for generation requests."
  8. L0 SongState injection placeholder: `[SONG_STATE_L0]` (replaced dynamically)
- **Intent classification rules** (in `onUserPromptSubmitted`):
  - Pipeline triggers (→ Composer): keywords `compose`, `create`, `generate`, `make me`, `build`, `produce` + musical scope words `song`, `beat`, `track`, `arrangement`
  - Iteration triggers (→ Composer): keywords `change`, `modify`, `adjust`, `make it`, `try`, `undo`, references to existing tracks/elements
  - Domain queries (→ specialist): `what key`, `what chord`, `analyze`, `theory` → Harmony; `add swing`, `humanize`, `drums` → Rhythm; `what preset`, `recommend`, `sound like` → Sound; `frequency`, `EQ`, `masking`, `levels` → Mix; `controller`, `map`, `knob`, `pad` → Controller
  - Ambiguous (→ Composer with fallback): queries that span multiple domains. Composer can delegate internally.
- **Dynamic system message**: on every turn, inject the L0 SongState summary into the system message. If no SongState exists yet, inject: "No active session. Ready to create a new composition."
- **Skill directory**: `skills/composer/SKILL.md`, `skills/composer/pipeline-reference.md` (condensed pipeline spec), `skills/composer/sensitivity-map.json`.
- The Composer agent should be listed LAST in the `customAgents` array so domain-specific agents get routing priority for clear domain queries, with the Composer as catch-all.

**Testing**:

| # | Test Case | Input | Expected Outcome |
|---|-----------|-------|-----------------|
| 1 | Pipeline routing | "Create a neo-soul beat at 90 BPM" | Routes to Composer. `isPipelineTrigger: true`. Pipeline initiated. |
| 2 | Domain routing — harmony | "What key is the Godly progression in?" | Routes to Harmony agent (not Composer). |
| 3 | Domain routing — rhythm | "Add some swing to the hi-hats" | Routes to Rhythm agent. |
| 4 | Iteration routing | "Make the bass warmer" | Routes to Composer (modification of existing session). `isPipelineTrigger: false`. |
| 5 | Ambiguous → Composer | "Make this more interesting" | Routes to Composer (multi-domain, subjective). |
| 6 | Prompt token budget | Build Composer prompt | `promptTokenCount ≤ 3000`. |
| 7 | L0 injection | Active SongState with 4 tracks | System message contains: "4 tracks, Eb minor, 90 BPM, neo_soul". |
| 8 | Full E2E — pipeline trigger | "Late-night R&B, Frank Ocean vibes, ~130 BPM" | Composer routes to pipeline. Pipeline runs 8 stages. Complete output generated. |
| 9 | Full E2E — iteration | (after E2E) "3rd chord too bright, darken it" | Composer invokes modify_song. Only affected components regenerated. |
| 10 | Skill file validation | Read skills/composer/SKILL.md | Valid markdown. Contains pipeline overview, sensitivity table, quality thresholds. ≤ 3000 tokens. |

**Risk**: Agent routing accuracy — `infer: true` depends on the quality of agent descriptions. The Composer's broad description may "steal" domain-specific queries from specialist agents. **Mitigation**: (1) Make domain agent descriptions very specific and concrete (listing exact keywords they handle). (2) Place Composer last in the `customAgents` array. (3) Test routing with ≥ 30 sample queries across all domains and measure routing accuracy. Target: ≥ 90% correct routing on first attempt. (4) If routing is wrong, the Composer can detect the mismatch (query too simple for full orchestration) and internally delegate by calling domain tools directly.

---

## Cross-Phase Export Registry

Phase 6 produces the following exports consumed by downstream phases:

| Export | Type | Defined In | Consuming Phases | Notes |
|--------|------|-----------|-----------------|-------|
| `PipelineIntent` | Interface | C13 | P8 (creative dials), P9 (preference extraction) | Genre, mood, and influence data feeds preference learning |
| `ComposerPipeline` | Interface | C13 | P8 (quality gates inject into stages), P10 (live pipeline variant) | Pipeline state enables Phase 8 to run critics per-stage |
| `SessionManifest` | Interface | C13 | P9 (session history), P10 (session loading for live performance) | Session metadata for cross-session learning |
| `PipelineConfig` | Interface | C13 | P8 (quality gate config), P9 (preference-adjusted config) | Phase 9 adjusts approvalGates based on user trust level |
| `SensitivityMap` | Interface/Const | C13 | P8 (critic-targeted regeneration), P9 (preference change sensitivity) | Shared blast-radius logic |
| `ModificationRequest` | Interface | C13 | P9 (modification patterns → preference signals) | "Always darkens chords" → brightness:-0.3 preference |
| `AlternativeSet` | Interface | C13 | P8 (multi-critic scoring of alternatives), P9 (selection patterns) | Which alternatives user chooses reveals preferences |
| Pipeline DAG Engine | Runtime | P6-T2 | P10 (live pipeline with reduced stages) | P10 may run a 3-stage mini-pipeline for live generation |
| Composer Agent Config | Config | P6-T8 | Root agent setup, P8 (critic integration into agent prompt) | Phase 8 adds quality gate instructions to Composer prompt |
| Output File Manager | Runtime | P6-T4 | P7 (auto-mapping generated sessions), P9 (session history scanning) | Phase 7 auto-creates controller maps for new sessions |
| Intent Classification | Runtime | P6-T8 | P9 (classify-then-learn: different learning for domain vs. pipeline queries) | Routing decisions inform preference model |

---

## Risk Matrix

```
┌────────────────────────────────────────────────────────────────────┐
│                    PHASE 6 RISK HEAT MAP                           │
│                                                                    │
│  Business Impact ↑                                                 │
│       HIGH │     P6-T2           P6-T6                             │
│            │   Orchestrator    Iteration                           │
│            │    (critical)      (critical)                         │
│            │                                                       │
│       MED  │  P6-T1        P6-T8         P6-T7                    │
│            │ Intent       Composer       A/B Gen                   │
│            │ Decomp       Agent                                    │
│            │                                                       │
│       LOW  │           P6-T3    P6-T5    P6-T4                    │
│            │         Arrange  Assembly  File Mgr                   │
│            │                                                       │
│            └──────────────────────────────────────────────────────  │
│              LOW          MED           HIGH    Technical Risk →    │
└────────────────────────────────────────────────────────────────────┘
```

### Risk Register

| ID | Risk | Severity | Probability | Impact | Task(s) | Mitigation |
|----|------|----------|------------|--------|---------|------------|
| R6-01 | **Pipeline latency exceeds 60s** — 8 stages × multiple LLM calls | Critical | Medium | Users abandon long-running generation | P6-T2 | DAG engine calls tool handlers directly (no LLM per stage). Stage 4 parallelism. Target < 15s for non-LLM stages. Progress streaming hides perceived latency. |
| R6-02 | **Cross-phase interface breakage** — P1-P5 tool signature changes break pipeline | Critical | High | Pipeline fails entirely on upstream changes | P6-T2 | Adapter interfaces isolate pipeline from internal tool signatures. Integration test suite validates all tool contracts. Semantic versioning on tool interfaces. |
| R6-03 | **Blast radius over-computation** — conservative sensitivity analysis regenerates user-approved content | High | Medium | User frustration: "I liked the drums, why did you change them?" | P6-T6 | `frozen: true` flag on user-approved components. Present blast radius before executing. Limit transitive depth to 2. |
| R6-04 | **Agent routing misclassification** — `infer: true` sends pipeline requests to domain agents or vice versa | High | Medium | Poor user experience: unexpected responses | P6-T8 | Specific agent descriptions. Composer agent last in array. Test with 30+ query routing benchmark. Composer can internally re-delegate. |
| R6-05 | **Context window exhaustion** — pipeline + 10 iterations = 100+ tool calls | High | Medium | LLM loses track of SongState, makes contradictory changes | P6-T6, T8 | SongState always injected fresh (L0 in system message, L1 on demand). Never depend on conversation memory for state. `infiniteSessions` compaction preserves state injection. |
| R6-06 | **Intent decomposition accuracy < 80%** — LLM misidentifies genre/mood/tempo | Medium | Medium | Pipeline generates wrong-genre content | P6-T1 | Deterministic enrichment layer validates LLM output. Artist lookup table corrects common misidentifications. Ambiguity detection asks user to clarify. |
| R6-07 | **Checkpoint file corruption** — crash during checkpoint write | Medium | Low | Cannot resume interrupted pipeline | P6-T2, T4 | Atomic writes (write-to-temp, rename). Validate checkpoint schema before resuming. Keep N-1 checkpoint as backup. |
| R6-08 | **Alternative generation timeout** — 3× computation per element | Medium | Medium | User waits too long for A/B options | P6-T7 | Lazy generation (only on request). Parallel generation with Stage 7. Time-box each variant (10s max). |
| R6-09 | **Arrangement template gap** — uncommon genre has no form template | Low | Medium | Poor arrangement for niche genres | P6-T3 | Generic ABAB fallback template. Mark as `template: "generic_fallback"` for transparency. Expand templates incrementally. |
| R6-10 | **Multi-track MIDI format rejection by DAW** — strict SMF compliance failure | Low | Low | Generated file won't import into MPC Beats | P6-T5 | Validate output with external SMF parser. Test import in MPC Beats directly (manual integration test). Match exact formatting of stock .mid files. |

### Dependency Risk — Upstream Phase Changes

| Upstream Phase | Critical Tools Consumed | Breaking Change Risk | Mitigation |
|----------------|----------------------|---------------------|------------|
| P1 (Harmonic Brain) | `generate_progression`, `analyze_harmony` | Medium — chord format changes break Stage 2 | Pin `EnrichedProgression` (C2) schema. Adapter validates shape. |
| P2 (Embeddings) | `search_assets` | Low — search is used for enrichment, not critical path | Degrade gracefully: if search fails, use LLM knowledge only. |
| P3 (Rhythm Engine) | `generate_midi`, `humanize_midi`, `write_midi_file` | High — MIDI generation is core pipeline | Pin `MidiPattern` (C3) and `MidiNoteEvent` schemas. Integration tests for every tool. |
| P4 (Sound Oracle) | `recommend_preset`, `generate_effect_chain` | Medium — preset/effect changes affect Stage 5 | Pin `PresetReference` and `EffectChain` (C9, C10) schemas. Degrade: if preset recommendation fails, skip preset assignment (user assigns manually). |
| P5 (MIDI Bridge) | `play_sequence`, `midi_transport` | Low — playback is optional (Stage 8) | Stage 8 is skippable. Pipeline completes as `completed_partial` if MIDI bridge unavailable. |

---

## Implementation Sequence

The recommended build order within Phase 6, based on dependencies and testability:

```
                  P6-T4 (File Manager)       ← Independent, build first
                       ↓
P6-T1 (Intent) → P6-T3 (Arrangement) → P6-T5 (Assembly) → P6-T2 (Orchestrator)
                                                                    ↓
                                                    P6-T6 (Iteration) → P6-T7 (A/B)
                                                                    ↓
                                                              P6-T8 (Composer Agent)
```

**Critical path**: P6-T1 → P6-T3 → P6-T5 → P6-T2 → P6-T6

**Parallelizable**: P6-T4 can develop in parallel with P6-T1 through P6-T3. P6-T7 can develop in parallel with P6-T6 (both depend on P6-T2).

---

## Open Items & Unresolved Markers

| Item | Status | Notes |
|------|--------|-------|
| [UNRESOLVED: Artist lookup table coverage] | Needs authoring | The ~100 artist → genre mapping table referenced by P6-T1 must be authored. Initial set: top-50 artists from hip-hop, R&B, electronic, jazz, pop, rock. Expand based on user queries. |
| [UNRESOLVED: Quality gate scoring pre-Phase 8] | Deferred | P6-T7 uses a heuristic scoring function. The exact weights and criteria are placeholders until Phase 8 defines the full critic system (C12). For now, use simple consonance + density heuristics. |
| [UNRESOLVED: Approval gate UX format] | Needs design | When `approvalGates` pauses the pipeline, what exactly is presented to the user? Current plan: L1 summary + generated chord symbols + "Approve? [yes/modify/regenerate]". Needs UX iteration. |
| [UNRESOLVED: Checkpoint format versioning] | Needs migration strategy | If the C13 schema changes between MUSE versions, old checkpoints may not deserialize. Need a migration function or version-check with "cannot resume, start fresh" fallback. |

---

*This document defines the complete engineering specification for Phase 6 of the MUSE AI Music Platform. All TypeScript interfaces extend or reference contracts C1–C13. All tools use `defineMuseTool()` from P0-T7. Total estimated effort: 5–7 dev-weeks (critical path: 4 weeks with parallelization).*

*Next priority: Update ORCHESTRATION_STATE.md with D-011 resolution and C13 contract registration.*
````
