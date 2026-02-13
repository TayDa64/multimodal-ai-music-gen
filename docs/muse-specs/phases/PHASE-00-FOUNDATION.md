# Phase 0 — Foundation & Scaffold

> **Effort**: 6–8 dev-weeks solo | 3–4 weeks with 2 devs  
> **Risk Level**: Medium (SDK integration unknowns)  
> **Prerequisites**: None — this is the root phase  
> **Outputs Consumed By**: All subsequent phases  
> **Reviewers**: GPT-5.2 Codex, Gemini 3 Pro Preview

---

## Phase Overview

Phase 0 establishes the entire project foundation: directory structure, build tooling, CopilotClient initialization, all MPC Beats format parsers (.progression JSON, .xmm XML), the Song State schema with L0–L3 compression tiers, the tool registration factory, system message template engine, and the CLI entry point. Every subsequent phase depends on artifacts produced here.

> **Gemini**: "The single most important decision is the Song State schema and serialization format. Everything flows downstream."

> **GPT**: "Quality gates inside tool handlers, not hooks. Hooks are passive/annotation only."

---

## Architecture Decisions (Phase 0)

| Decision | Choice | Rationale |
|---|---|---|
| SDK transport | CLI-based JSON-RPC via `CopilotClient` | Copilot SDK is CLI-based, not VS Code Extension API |
| Session model | Single session, 6 `customAgents` | Shared context, reduced latency vs. multi-session |
| Tool pattern | `defineTool()` with wrapper factory | Uniform logging, timing, error handling, quality gates |
| Knowledge tiers | System message → skill files → tools | Maps to SDK's `systemMessage` + `skillDirectories` + `defineTool` |
| State persistence | External JSON + MessagePack | SongState NEVER depends on conversation memory |
| Context compaction | Dual: SDK `infiniteSessions` + MUSE L0–L3 | SDK handles conversation; MUSE handles musical state |

---

## Tasks

### P0-T1: Project Scaffold
**Complexity**: S  
**Description**: Initialize the monorepo with TypeScript, ESLint, Vitest, and directory conventions. Establishes the canonical folder structure that all phases contribute to.  
**Depends On**: None  
**SDK Integration**: None (build tooling only)

**Directory Structure**:
```
muse/
├── src/
│   ├── core/           # Song State, types, contracts
│   ├── agents/         # Custom agent configs
│   ├── tools/          # defineTool() implementations
│   ├── parsers/        # .progression, .xmm, .mid parsers
│   ├── embeddings/     # ONNX, vector index
│   ├── midi/           # Virtual MIDI, scheduling
│   ├── pipeline/       # Orchestrator, stages
│   ├── skills/         # Skill directory markdown files
│   └── index.ts        # CLI entry point
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/       # Sample .progression, .xmm, .mid files
├── skills/             # skillDirectories content
│   ├── harmony/
│   ├── rhythm/
│   ├── sound/
│   └── general/
├── package.json
├── tsconfig.json
├── vitest.config.ts
└── .eslintrc.json
```

**Output Interface**:
```typescript
// No runtime interface — this is a structural task
// Validation: all imports resolve, `npm run build` succeeds, `npm test` runs
```

**Testing Strategy**:
- `npm run build` completes without errors
- `npm test` runs with 0 tests (framework operational)
- ESLint passes on empty project
- TypeScript strict mode enabled and compiling

**Risk**: Low. Standard tooling.

---

### P0-T2: CopilotClient Initialization Wrapper
**Complexity**: M  
**Description**: Create a `MuseClient` class that wraps `CopilotClient` with connection management, health checks, auto-reconnect, and graceful shutdown. This is the single entry point for all SDK interactions.  
**Depends On**: P0-T1  
**SDK Integration**: `CopilotClient` (spawn/connect), TCP or stdio transport, health ping

**Input Interface**:
```typescript
/** Configuration for MUSE client initialization */
interface MuseClientConfig {
  /** Path to Copilot CLI binary (auto-detected if omitted) */
  copilotBinaryPath?: string;
  /** Transport mode: TCP (default) or stdio */
  transport: 'tcp' | 'stdio';
  /** TCP port (auto-assigned if omitted) */
  port?: number;
  /** Maximum reconnection attempts before fatal error */
  maxReconnectAttempts: number;
  /** Reconnection backoff base in ms */
  reconnectBackoffMs: number;
  /** Health check interval in ms */
  healthCheckIntervalMs: number;
  /** Enable infinite sessions for context compaction */
  infiniteSessions: {
    enabled: boolean;
    /** Token count that triggers background compaction */
    backgroundCompactionThreshold: number;
    /** Token count that triggers synchronous compaction */
    bufferExhaustionThreshold: number;
  };
  /** Custom model providers (BYOK) */
  modelProviders?: Record<string, ModelProviderConfig>;
}

interface ModelProviderConfig {
  /** Provider type: openai, azure, anthropic, ollama */
  type: 'openai' | 'azure' | 'anthropic' | 'ollama';
  /** API endpoint URL */
  endpoint: string;
  /** API key (resolved from env var) */
  apiKeyEnvVar: string;
  /** Model identifier */
  model: string;
}
```

**Output Interface**:
```typescript
interface MuseClient {
  /** Current connection state */
  readonly state: 'disconnected' | 'connecting' | 'connected' | 'error';
  /** Connect to Copilot CLI server */
  connect(): Promise<void>;
  /** Create a new MUSE session with all agents and tools registered */
  createSession(songState?: SongState): Promise<MuseSession>;
  /** Resume an existing session by ID */
  resumeSession(sessionId: string): Promise<MuseSession>;
  /** List all active sessions */
  listSessions(): Promise<SessionSummary[]>;
  /** Graceful shutdown */
  disconnect(): Promise<void>;
  /** Health check */
  ping(): Promise<{ latencyMs: number; status: 'ok' | 'degraded' }>;
}
```

**Testing Strategy**:
- Unit: Mock CopilotClient, verify connection lifecycle (connect → ping → disconnect)
- Unit: Verify auto-reconnect triggers after simulated disconnect (up to maxReconnectAttempts)
- Unit: Verify health check fires at configured interval
- Integration: Connect to actual Copilot CLI, create session, send trivial prompt, verify response stream
- Edge: Verify graceful behavior when CLI binary not found

**Risk**: Medium. SDK transport details may change. Mitigation: abstract behind `MuseClient` so internals are swappable.

---

### P0-T3: .progression JSON Parser & Enrichment
**Complexity**: M  
**Description**: Parse all 47 `.progression` JSON files from MPC Beats into a normalized internal representation. Enrich with computed properties: Roman numeral analysis, interval vectors, voice leading distances, genre associations. This is the foundation for the Harmonic Brain (Phase 1).  
**Depends On**: P0-T1  
**SDK Integration**: Data consumed by `defineTool("readProgression", ...)` and by `skillDirectories` content generation

**Input Interface**:
```typescript
/** Raw .progression file format (as shipped by MPC Beats) */
interface RawProgressionFile {
  progression: {
    /** Display name, e.g. "Gospel-Godly" */
    name: string;
    /** Root note as string, e.g. "E", "Bb" */
    rootNote: string;
    /** Scale name, e.g. "Pentatonic Minor", "Major" */
    scale: string;
    /** MIDI octave for recording, typically 2-4 */
    recordingOctave: number;
    /** Ordered chord sequence */
    chords: RawChord[];
  };
}

interface RawChord {
  /** Chord symbol, e.g. "Em7/D", "Bbmaj9" */
  name: string;
  /** Functional role: "Root" | "Normal" */
  role: string;
  /** MIDI note numbers (absolute, not relative) */
  notes: number[];
}
```

**Output Interface**:
```typescript
/** Enriched progression with computed analysis — Contract C2 */
interface EnrichedProgression {
  /** Original file path */
  sourcePath: string;
  /** Parsed display name */
  name: string;
  /** Detected key center */
  key: Key;
  /** Detected scale/mode */
  scale: Scale;
  /** Recording octave from source */
  recordingOctave: number;
  /** Enriched chord sequence */
  chords: EnrichedChord[];
  /** Computed harmonic analysis */
  analysis: HarmonicAnalysis;
  /** Genre associations with confidence scores */
  genreAssociations: Array<{ genre: string; confidence: number }>;
  /** Embedding-ready text description */
  textDescription: string;
}

interface EnrichedChord {
  /** Original chord symbol */
  symbol: string;
  /** Roman numeral in context of key */
  romanNumeral: string;
  /** MIDI note numbers */
  midiNotes: number[];
  /** Pitch class set (0-11) */
  pitchClasses: number[];
  /** Interval vector (6 values) */
  intervalVector: [number, number, number, number, number, number];
  /** Chord quality (major, minor, dominant7, etc.) */
  quality: ChordQuality;
  /** Bass note (lowest pitch class) */
  bassNote: number;
  /** Is this an inversion? */
  isInversion: boolean;
  /** Computed tension value (0-1) */
  tension: number;
  /** Voice leading distance to next chord (semitones) */
  voiceLeadingDistanceToNext: number | null;
  /** Common tones with next chord */
  commonTonesWithNext: number[];
}

interface HarmonicAnalysis {
  /** Full Roman numeral sequence, e.g. ["i", "i7/♭VII", "V/♯IV", "V7/♯IV"] */
  romanNumeralSequence: string[];
  /** Detected cadential patterns */
  cadences: Array<{ type: string; chordIndices: [number, number] }>;
  /** Key modulations detected */
  modulations: Array<{ fromKey: Key; toKey: Key; atChordIndex: number }>;
  /** Average tension across progression */
  averageTension: number;
  /** Tension arc: array of tension values */
  tensionArc: number[];
  /** Detected voice leading patterns */
  voiceLeadingPatterns: string[];
  /** Harmonic complexity score (0-1) */
  complexityScore: number;
}
```

**Testing Strategy**:
- Unit: Parse each of the 47 .progression files without errors
- Unit: Verify "Godly" enrichment: rootNote "E" → Key.E, Roman numerals ["i", "i7/♭VII", "V/♯IV", "V7/♯IV"]
- Unit: Verify "Neo Soul 1" chromatic bass descent detection (45→44→43→42)
- Unit: Verify voice leading distance calculation: Em→Em7/D = 2 semitones total
- Unit: Verify genre association: "Godly" → Gospel (>0.8 confidence)
- Snapshot: Golden-file test for all 47 enriched outputs

**Risk**: Medium. Chord symbol parsing is ambiguous (e.g., "B/F#" — slash chord vs. polychord). Mitigation: build exhaustive test cases from actual MPC Beats chord naming conventions.

---

### P0-T4: .xmm XML Parser
**Complexity**: M  
**Description**: Parse all 67 `.xmm` MIDI Learn maps from MPC Beats. Extract controller metadata, control mappings (pads, knobs, sliders, transport), and the opaque Target_control indices. Build a lookup table for future reverse-engineering of Target_control semantics.  
**Depends On**: P0-T1  
**SDK Integration**: Data consumed by `defineTool("readControllerMap", ...)` and Performance agent skill files

**Input Interface**:
```typescript
/** Raw .xmm XML structure (simplified) */
interface RawXmmFile {
  /** Controller manufacturer and model from filename */
  controllerName: string;
  /** All control mappings in the file */
  mappings: RawXmmMapping[];
}

interface RawXmmMapping {
  /** MIDI message type: 1=Note, 2=CC, others */
  type: number;
  /** MIDI channel (0-15) */
  channel: number;
  /** data1: note number or CC number */
  data1: number;
  /** data2: typically 127 or unused */
  data2: number;
  /** MPC Beats internal target index (0-115+) */
  targetControl: number;
  /** Human-readable target name if available */
  targetName?: string;
}
```

**Output Interface**:
```typescript
/** Parsed controller map — Contract C6 */
interface ControllerMap {
  /** Source file path */
  sourcePath: string;
  /** Controller manufacturer */
  manufacturer: string;
  /** Controller model name */
  model: string;
  /** Pads: Note-on mappings (typically channel 10) */
  pads: PadMapping[];
  /** Knobs/Sliders: CC mappings */
  knobs: KnobMapping[];
  /** Transport controls */
  transport: TransportMapping[];
  /** All Target_control indices found (for reverse-engineering) */
  targetControlRegistry: Map<number, string[]>;
  /** Total number of mapped controls */
  totalMappings: number;
}

interface PadMapping {
  /** MIDI note number */
  noteNumber: number;
  /** MIDI channel */
  channel: number;
  /** Target function in MPC Beats */
  targetControl: number;
  /** Resolved name (if known) */
  resolvedName?: string;
}

interface KnobMapping {
  /** CC number */
  ccNumber: number;
  /** MIDI channel */
  channel: number;
  /** Target function in MPC Beats */
  targetControl: number;
  /** Resolved name (if known) */
  resolvedName?: string;
}

interface TransportMapping {
  /** Transport function: play, stop, record, loop */
  function: 'play' | 'stop' | 'record' | 'loop' | 'unknown';
  /** MIDI message type */
  type: number;
  /** MIDI channel */
  channel: number;
  /** data1 value */
  data1: number;
  /** Target control index */
  targetControl: number;
}
```

**Testing Strategy**:
- Unit: Parse all 67 .xmm files without errors
- Unit: Verify MPK mini 3 mapping: 8 pads on channel 10, 8 knobs on channel 1
- Unit: Verify Target_control indices 0-115+ are cataloged
- Unit: Verify transport control detection (play/stop/record) from known controller maps
- Regression: Count total mappings across all 67 files, verify stable (should be ~1800+)

**Risk**: Medium. XML schema may vary between controller families. Mitigation: parse defensively, log unknown elements.

---

### P0-T5: Song State Schema (L0–L3 Compression)
**Complexity**: XL  
**Description**: Design and implement the central Song State schema — the contract between ALL components. Implements 4 compression levels: L0 (~100 tokens, quick context), L1 (~500 tokens, structural decisions), L2 (~3000 tokens, full detail), L3 (variable, complete history). This is the single most critical data structure in the entire platform.  
**Depends On**: P0-T1  
**SDK Integration**: L0 injected via `systemMessage`; L1/L2 passed as tool results; L3 persisted to filesystem

**Output Interface**:
```typescript
/** The central Song State — Contract C1 */
interface SongState {
  /** Schema version for migration support */
  schemaVersion: string;
  /** Unique song identifier */
  id: string;
  /** Song metadata */
  metadata: SongMetadata;
  /** All tracks in the song */
  tracks: Track[];
  /** Song arrangement (sections, energy arc) */
  arrangement: Arrangement;
  /** Active chord progression */
  progression: ProgressionState;
  /** Mix state (per-track and master) */
  mix: MixState;
  /** Edit history for undo/redo */
  history: HistoryEntry[];
  /** Song-level quality scores from last evaluation */
  qualityScores?: QualityScore;
  /** User preference overrides for this song */
  preferenceOverrides?: Partial<UserPreferenceVector>;
  /** Genre DNA vector for this song */
  genreDNA: GenreDNAVector;
  /** Creation and modification timestamps */
  timestamps: {
    created: string;
    lastModified: string;
    lastEvaluated?: string;
  };
}

interface SongMetadata {
  /** Song title */
  title: string;
  /** Key center */
  key: Key;
  /** Tempo in BPM */
  tempo: number;
  /** Time signature */
  timeSignature: { numerator: number; denominator: number };
  /** Genre/style influences */
  influences: string[];
  /** Mood descriptors */
  moodTags: string[];
  /** Total duration in bars */
  totalBars: number;
}

interface Track {
  /** Unique track ID */
  id: string;
  /** Display name */
  name: string;
  /** Musical role: lead, pad, bass, drums, fx, etc. */
  role: TrackRole;
  /** Source MIDI file or generated pattern */
  midiSource: string | GeneratedMidiRef;
  /** Assigned synth/instrument preset */
  preset: PresetAssignment;
  /** Effect chain (ordered) */
  effectsChain: EffectInstance[];
  /** Pan position (-1 to +1) */
  pan: number;
  /** Volume (0 to 1) */
  volume: number;
  /** Muted state */
  muted: boolean;
  /** Solo state */
  soloed: boolean;
}

type TrackRole = 'lead' | 'pad' | 'bass' | 'drums' | 'percussion' | 'fx' | 'vocal' | 'arp' | 'sub';

interface PresetAssignment {
  /** Synth/plugin name */
  pluginName: string;
  /** Preset name within the plugin */
  presetName: string;
  /** Category if known */
  category?: string;
}

interface Arrangement {
  /** Ordered sections */
  sections: Section[];
  /** Energy arc as (bar, energy) pairs */
  energyArc: Array<{ bar: number; energy: number }>;
  /** Section transitions */
  transitions: Transition[];
}

interface Section {
  /** Section name: intro, verse, chorus, bridge, outro, etc. */
  name: string;
  /** Start bar (1-indexed) */
  startBar: number;
  /** End bar (inclusive) */
  endBar: number;
  /** Which tracks are active in this section */
  activeTrackIds: string[];
  /** Section-specific intensity (0-1) */
  intensity: number;
}

interface Transition {
  /** Section transitioning from */
  fromSection: string;
  /** Section transitioning to */
  toSection: string;
  /** Transition type */
  type: 'cut' | 'crossfade' | 'build' | 'breakdown' | 'fill' | 'riser';
  /** Duration in beats */
  durationBeats: number;
}

interface ProgressionState {
  /** Active chord sequence */
  chords: Array<{
    symbol: string;
    midiNotes: number[];
    durationBeats: number;
    romanNumeral?: string;
  }>;
  /** Key centers (for modulating progressions) */
  keyCenters: Array<{ chordIndex: number; key: Key }>;
}

interface MixState {
  /** Master bus effects */
  masterEffects: EffectInstance[];
  /** Master volume */
  masterVolume: number;
  /** Target loudness in LUFS */
  targetLufs: number;
}

interface HistoryEntry {
  /** Conversation turn number */
  turn: number;
  /** Timestamp */
  timestamp: string;
  /** User's original request */
  userRequest: string;
  /** What changed */
  changesMade: ChangeRecord[];
}

interface ChangeRecord {
  /** What was changed */
  path: string;
  /** Previous value (for undo) */
  previousValue: unknown;
  /** New value */
  newValue: unknown;
}

/** L0 Compact Representation (~100 tokens) */
interface SongStateL0 {
  title: string;
  key: string;
  tempo: number;
  trackCount: number;
  genres: string[];
  mood: string[];
  sections: string[];
  bars: number;
}

/** L1 Structural Representation (~500 tokens) */
interface SongStateL1 extends SongStateL0 {
  tracks: Array<{ name: string; role: string; preset: string }>;
  progression: string[];  // chord symbols only
  sectionBoundaries: Array<{ name: string; bars: string }>;
  energySummary: string;  // "builds from 0.3 to 0.8 over 64 bars"
}

/** L2 Detailed Representation (~3000 tokens) */
interface SongStateL2 extends SongStateL1 {
  fullProgression: ProgressionState;
  effectChains: Record<string, string[]>;
  mixLevels: Record<string, { volume: number; pan: number }>;
  qualityScores?: QualityScore;
  recentHistory: HistoryEntry[];  // last 5 entries only
}
```

**Compression Functions**:
```typescript
interface SongStateCompressor {
  /** Compress full state to L0 (~100 tokens) */
  toL0(state: SongState): SongStateL0;
  /** Compress full state to L1 (~500 tokens) */
  toL1(state: SongState): SongStateL1;
  /** Compress full state to L2 (~3000 tokens) */
  toL2(state: SongState): SongStateL2;
  /** Estimate token count for a compression level */
  estimateTokens(level: 'L0' | 'L1' | 'L2' | 'L3'): number;
  /** Get appropriate level for available context budget */
  selectLevel(availableTokens: number): 'L0' | 'L1' | 'L2' | 'L3';
}
```

**Testing Strategy**:
- Unit: Create a full SongState for a "Frank Ocean meets Burial" song, verify all fields
- Unit: Compress to L0, verify < 150 tokens (via tiktoken)
- Unit: Compress to L1, verify < 600 tokens
- Unit: Compress to L2, verify < 3500 tokens
- Unit: Roundtrip: full → L0 → verify all L0 fields present
- Unit: History entry creation and undo via ChangeRecord
- Snapshot: Golden-file L0/L1/L2 outputs for reference song

**Risk**: High. Schema will evolve as phases add dimensions. Mitigation: version the schema (`schemaVersion`), write migration functions from v1→v2 etc.

---

### P0-T6: Song State Serializer & Persistence
**Complexity**: M  
**Description**: Serialize SongState to JSON (human-readable, git-friendly) and MessagePack (compact, fast I/O). Manage filesystem persistence with atomic writes, file locking, and auto-save.  
**Depends On**: P0-T5  
**SDK Integration**: Persistence path configured via CopilotClient config; loaded in `onSessionStart` hook

**Input/Output Interface**:
```typescript
interface SongStatePersistence {
  /** Save state to file (atomic write) */
  save(state: SongState, filePath: string, format: 'json' | 'msgpack'): Promise<void>;
  /** Load state from file */
  load(filePath: string): Promise<SongState>;
  /** Auto-save with debounce */
  enableAutoSave(state: SongState, filePath: string, debounceMs: number): void;
  /** Disable auto-save */
  disableAutoSave(): void;
  /** List all saved song states in a directory */
  listSongs(directory: string): Promise<SongFileSummary[]>;
  /** Detect format from file extension/magic bytes */
  detectFormat(filePath: string): 'json' | 'msgpack';
}

interface SongFileSummary {
  filePath: string;
  title: string;
  key: string;
  tempo: number;
  lastModified: string;
  sizeBytes: number;
}
```

**Testing Strategy**:
- Unit: Roundtrip JSON: save → load → deep equality check
- Unit: Roundtrip MessagePack: save → load → deep equality check
- Unit: Atomic write: verify no partial writes on simulated process crash (write to temp then rename)
- Unit: Auto-save fires after debounce period, not before
- Unit: `listSongs` returns correct metadata for directory with 5 test files

**Risk**: Low. Standard serialization patterns.

---

### P0-T7: Tool Registration Factory
**Complexity**: L  
**Description**: Create a `createMuseTool()` factory that wraps SDK's `defineTool()` with standardized logging, execution timing, error handling with retry policies, quality gate enforcement, and input/output validation via Zod schemas. Every tool in the platform uses this factory.  
**Depends On**: P0-T1, P0-T2  
**SDK Integration**: Wraps `defineTool(name, {description, parameters, handler})`. Quality gates execute inside handler, not in hooks.

**Input Interface**:
```typescript
interface MuseToolConfig<TInput, TOutput> {
  /** Tool name (kebab-case, unique) */
  name: string;
  /** Human-readable description for LLM */
  description: string;
  /** Zod schema for input validation */
  inputSchema: ZodSchema<TInput>;
  /** The tool handler */
  handler: (input: TInput, context: ToolContext) => Promise<TOutput>;
  /** Quality gate: validate output before returning to LLM */
  qualityGate?: (output: TOutput) => QualityGateResult;
  /** Retry policy on failure */
  retryPolicy?: RetryPolicy;
  /** Maximum execution time in ms */
  timeoutMs?: number;
  /** Tags for categorization */
  tags?: string[];
}

interface ToolContext {
  /** Current Song State (read-only snapshot) */
  songState: Readonly<SongState>;
  /** Update Song State (triggers persistence) */
  updateSongState: (updater: (state: SongState) => SongState) => void;
  /** Session ID for correlation */
  sessionId: string;
  /** Logger instance */
  logger: MuseLogger;
}

interface QualityGateResult {
  /** Did the output pass the quality gate? */
  passed: boolean;
  /** Score (0-1) if applicable */
  score?: number;
  /** Reason for failure */
  failureReason?: string;
  /** Suggested fix for the handler to try on retry */
  suggestedFix?: string;
}

interface RetryPolicy {
  /** Maximum retry attempts */
  maxRetries: number;
  /** Backoff strategy */
  backoff: 'fixed' | 'exponential';
  /** Base delay in ms */
  baseDelayMs: number;
  /** Only retry on specific error types */
  retryableErrors?: string[];
}
```

**Output Interface**:
```typescript
interface MuseToolRegistration {
  /** The defineTool-compatible registration object */
  toolDefinition: {
    name: string;
    description: string;
    parameters: ZodSchema;
    handler: (input: unknown) => Promise<unknown>;
  };
  /** Execution statistics */
  stats: {
    totalCalls: number;
    totalErrors: number;
    averageLatencyMs: number;
    qualityGatePassRate: number;
  };
}
```

**Testing Strategy**:
- Unit: Create tool with quality gate, verify gate runs on output
- Unit: Verify retry fires on transient error, respects maxRetries
- Unit: Verify timeout kills long-running handler
- Unit: Verify Zod validation rejects bad input with clear error message
- Unit: Verify logging captures tool name, latency, success/failure
- Integration: Register 3 tools via factory, verify all callable by mock CopilotSession

**Risk**: Medium. Quality gate logic must not add significant latency. Mitigation: gates should be synchronous, <5ms per invocation.

---

### P0-T8: System Message Template Engine
**Complexity**: M  
**Description**: Build a dynamic system message that injects L0 Song State, genre context, session personality, and active constraints. Uses SDK's `systemMessage: { mode: "append", content }` to augment the base Copilot system prompt.  
**Depends On**: P0-T5 (SongState), P0-T2 (MuseClient)  
**SDK Integration**: `systemMessage` config option, dynamically updated via `onSessionStart` hook and on SongState changes

**Input Interface**:
```typescript
interface SystemMessageConfig {
  /** Platform identity and capabilities */
  identity: string;
  /** Current L0 state injection */
  songStateL0: SongStateL0 | null;
  /** Active genre context */
  genreContext?: string;
  /** Session personality mode */
  personality: 'professional' | 'educational' | 'experimental';
  /** Active constraints from user */
  activeConstraints: string[];
  /** User preference summary */
  preferenceSummary?: string;
}
```

**Output Interface**:
```typescript
interface SystemMessageBuilder {
  /** Build the system message from current state */
  build(config: SystemMessageConfig): string;
  /** Estimate token count of generated message */
  estimateTokens(config: SystemMessageConfig): number;
  /** Get the SDK-compatible systemMessage object */
  toSdkConfig(config: SystemMessageConfig): {
    mode: 'append';
    content: string;
  };
}
```

**Example Output** (~400 tokens):
```
You are MUSE (Music Understanding and Synthesis Engine), an expert AI music 
production assistant integrated with MPC Beats. You have deep knowledge of 
music theory, sound design, mixing, and production workflows.

CURRENT SONG: "Late Night Vibes" | Eb minor | 130 BPM | 8 tracks
GENRE: Neo-soul × UK Garage | MOOD: dreamy, nostalgic
SECTIONS: Intro(8) → Verse(16) → Build(4) → Chorus(8) → Break(8)
ENERGY: builds from 0.3 to 0.8, drops to 0.2 at break

CONSTRAINTS: Keep vocals in 200-4kHz range. No distortion on pad.
PERSONALITY: Professional — concise, decisive recommendations.
```

**Testing Strategy**:
- Unit: Build message with full config, verify < 500 tokens
- Unit: Build with null songState, verify graceful fallback
- Unit: Verify constraints appear verbatim in output
- Unit: Verify L0 data is accurately represented
- Snapshot: Golden-file for reference configs

**Risk**: Low. String templating with token counting.

---

### P0-T9: Session Configuration Factory
**Complexity**: L  
**Description**: Builds the complete `CopilotClient` configuration object: registers all 6 custom agents, all tools, skill directories, MCP servers, hooks, and infinite session settings. This is the "wiring" layer that connects all MUSE components to the SDK.  
**Depends On**: P0-T2, P0-T7, P0-T8  
**SDK Integration**: Constructs the full config object passed to `CopilotClient` initialization. Uses `customAgents`, `skillDirectories`, `mcpServers`, all hook registrations.

**Output Interface**:
```typescript
interface SessionConfigFactory {
  /** Build complete session config from registered components */
  build(options: SessionBuildOptions): CopilotSessionConfig;
}

interface SessionBuildOptions {
  /** Which agents to enable (all by default) */
  enabledAgents?: AgentName[];
  /** Additional tools beyond agent-specific ones */
  globalTools?: MuseToolRegistration[];
  /** Override skill directories */
  skillDirectories?: string[];
  /** MCP server configurations */
  mcpServers?: Record<string, McpServerConfig>;
  /** Song state for system message injection */
  initialSongState?: SongState;
}

type AgentName = 'harmony' | 'rhythm' | 'sound' | 'mix' | 'performance' | 'creative';

interface CopilotSessionConfig {
  systemMessage: { mode: 'append'; content: string };
  customAgents: CustomAgentConfig[];
  tools: ToolDefinition[];
  skillDirectories: string[];
  mcpServers: Record<string, McpServerConfig>;
  infiniteSessions: {
    enabled: boolean;
    backgroundCompactionThreshold: number;
    bufferExhaustionThreshold: number;
  };
  hooks: {
    onSessionStart: (session: unknown) => Promise<void>;
    onPreToolUse: (toolName: string, args: unknown) => unknown;
    onPostToolUse: (toolName: string, result: unknown) => unknown;
    onErrorOccurred: (error: Error) => 'retry' | 'skip' | 'abort';
  };
}

interface CustomAgentConfig {
  /** Agent identifier (used as @harmony, @rhythm, etc.) */
  name: string;
  /** Display name in UI */
  displayName: string;
  /** Description for routing */
  description: string;
  /** Agent-specific system prompt */
  prompt: string;
  /** Tools available to this agent */
  tools: string[];
  /** Auto-routing inference function */
  infer?: (message: string) => boolean;
}
```

**Testing Strategy**:
- Unit: Build config with all agents enabled, verify 6 agents registered
- Unit: Build config with subset of agents, verify only those are present
- Unit: Verify all tools are unique by name (no duplicates)
- Unit: Verify skill directories resolve to valid filesystem paths
- Integration: Pass built config to MuseClient.createSession(), verify session starts

**Risk**: Medium. Agent routing conflicts if `infer` functions overlap. Mitigation: test routing with 50+ sample prompts to verify correct agent selection.

---

### P0-T10: Error Handling Foundation
**Complexity**: M  
**Description**: Define the error taxonomy, structured error types, retry policies, graceful degradation strategies, and the `onErrorOccurred` hook implementation. Covers SDK errors, tool errors, MIDI errors, and parse errors.  
**Depends On**: P0-T1  
**SDK Integration**: `onErrorOccurred` hook returns 'retry' | 'skip' | 'abort'

**Output Interface**:
```typescript
/** Base error class for all MUSE errors */
abstract class MuseError extends Error {
  /** Error category for routing */
  abstract readonly category: ErrorCategory;
  /** Is this error retryable? */
  abstract readonly retryable: boolean;
  /** Severity level */
  abstract readonly severity: 'warn' | 'error' | 'fatal';
  /** Structured context for logging */
  abstract readonly context: Record<string, unknown>;
}

type ErrorCategory =
  | 'sdk'           // CopilotClient/session errors
  | 'parse'         // .progression/.xmm/.mid parse failures
  | 'tool'          // Tool handler errors
  | 'midi'          // Virtual MIDI port errors
  | 'quality'       // Quality gate failures
  | 'embedding'     // ONNX/embedding errors
  | 'state'         // SongState validation errors
  | 'timeout'       // Operation timeouts
  | 'user';         // User input validation

/** Specific error types */
class SdkConnectionError extends MuseError { /* ... */ }
class ParseError extends MuseError { /* ... */ }
class ToolExecutionError extends MuseError { /* ... */ }
class QualityGateError extends MuseError { /* ... */ }
class MidiPortError extends MuseError { /* ... */ }

/** Error handler for the onErrorOccurred hook */
interface ErrorHandler {
  /** Determine action for an error */
  handle(error: MuseError): 'retry' | 'skip' | 'abort';
  /** Log error with structured context */
  log(error: MuseError): void;
  /** Get error statistics */
  stats(): ErrorStats;
}

interface ErrorStats {
  /** Errors by category */
  byCategory: Record<ErrorCategory, number>;
  /** Errors by severity */
  bySeverity: Record<string, number>;
  /** Retry success rate */
  retrySuccessRate: number;
  /** Total errors in session */
  totalErrors: number;
}
```

**Testing Strategy**:
- Unit: Verify each error category maps to correct retry/skip/abort policy
- Unit: Verify retryable errors get retried, non-retryable get skipped/aborted
- Unit: Verify error logging captures structured context
- Unit: Verify error stats accumulate correctly
- Integration: Simulate tool handler throwing each error type, verify hook behavior

**Risk**: Low. Error handling is well-understood domain. Main risk is incomplete categorization — mitigated by catch-all handler.

---

## Phase 0 Summary

| Task | Complexity | Effort | Critical Path |
|---|---|---|---|
| P0-T1: Project Scaffold | S | 1 day | Yes |
| P0-T2: CopilotClient Wrapper | M | 3 days | Yes |
| P0-T3: .progression Parser | M | 3 days | No (parallel with T4, T5) |
| P0-T4: .xmm Parser | M | 2 days | No (parallel with T3, T5) |
| P0-T5: Song State Schema | XL | 5 days | Yes |
| P0-T6: State Persistence | M | 2 days | No |
| P0-T7: Tool Factory | L | 3 days | Yes |
| P0-T8: System Message Engine | M | 2 days | No |
| P0-T9: Session Config Factory | L | 3 days | Yes |
| P0-T10: Error Foundation | M | 2 days | No |

**Critical Path**: T1 → T2 → T7 → T9 (scaffold → client → tools → session)  
**Parallel Track A**: T3 + T4 (parsers, independent)  
**Parallel Track B**: T5 → T6 → T8 (state schema → persistence → system message)  
**Parallel Track C**: T10 (error handling, independent)

---

*Phase 0 produces the platform skeleton that all subsequent phases flesh out. Upon completion, a developer can run `npm start`, connect to Copilot CLI, send a message, and receive a response with Song State context injected.*
