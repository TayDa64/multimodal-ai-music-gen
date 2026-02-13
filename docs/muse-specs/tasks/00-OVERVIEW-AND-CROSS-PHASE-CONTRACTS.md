# MUSE — Round 2: Implementation Decomposition Overview

## Master Architecture: Copilot SDK Mapping

### SDK Feature → MUSE Component Mapping

| Copilot SDK Feature | MUSE Usage | Phase |
|---|---|---|
| `CopilotClient` + `CopilotSession` | Main entry point. CLI server wraps all agent interactions | 0 |
| `defineTool(name, { description, parameters, handler })` | Every MPC Beats operation: parsers, generators, analyzers, MIDI senders | 0-10 |
| `systemMessage: { mode, content }` | MUSE persona prompt with music-theory grounding + active SongState L0/L1 context | 0 |
| `skillDirectories: string[]` | Modular domain skills: `./skills/harmony`, `./skills/rhythm`, `./skills/sound`, `./skills/mix`, `./skills/controller` | 1-7 |
| `customAgents: CustomAgentConfig[]` | Multi-agent orchestration: Harmony, Rhythm, Sound, Mix, Arrangement, Creative agents | 6+ |
| `mcpServers: Record<string, MCPServerConfig>` | Optional: filesystem MCP for watching asset directories, virtual MIDI MCP server | 0, 5 |
| `hooks.onPreToolUse` | Quality gates (critic scoring before committing changes), permission for destructive ops | 8 |
| `hooks.onPostToolUse` | SongState update after every tool execution, preference signal capture | 0, 9 |
| `hooks.onSessionStart` | Load user preferences, scan workspace for assets, inject L0/L1 context | 0, 9 |
| `hooks.onSessionEnd` | Persist SongState to disk, update preference vectors, save session metadata | 0, 9 |
| `hooks.onUserPromptSubmitted` | Intent classification, SongState compression level selection | 6 |
| `hooks.onErrorOccurred` | Graceful degradation: fall back to text-only recommendations if MIDI/file ops fail | 0 |
| `infiniteSessions` | Long production sessions (50+ turns), context compaction keeps SongState coherent | 0, 13 |
| Streaming (`assistant.message_delta`) | Real-time progress for generation tasks ("Generating bass line... bar 4/16") | 3, 6 |
| BYOK (custom providers) | Let users bring their own model keys for quality/cost tradeoff | 0 |
| Permission handler | Approve file writes, MIDI port access, controller remapping | 0, 5, 7 |
| `ask_user` tool | Disambiguation for intent, genre selection, A/B preference choices | 6, 8 |

### Why Not `@mpc` Chat Participant?

The original blueprint assumed VS Code Chat Extension API. The Copilot SDK is **CLI-based JSON-RPC**, which means:

1. **No VS Code dependency** — MUSE runs as a standalone CLI agent or can be integrated into any editor
2. **`customAgents` replace slash commands** — instead of `/harmony`, `/rhythm`, we define named agents with `infer: true` that the router dispatches to automatically
3. **`defineTool` replaces VS Code tool registrations** — same semantic, different API surface
4. **`skillDirectories` replace manual skill loading** — directory-based modularity is native
5. **Session management is built-in** — no need for custom state persistence layer (but we still need SongState serialization)
6. **MCP servers enable filesystem watching** — can detect when user adds new .progression or .mid files

### The Multi-Agent Architecture via `customAgents`

```
customAgents: [
  {
    name: "harmony",
    displayName: "Harmony Agent",
    description: "Chord progression specialist — generates, analyzes, and transforms harmonic content",
    prompt: "<harmony-system-prompt>",
    tools: ["read_progression", "generate_progression", "analyze_harmony", "transpose_progression"],
    infer: true  // SDK auto-routes harmony questions here
  },
  {
    name: "rhythm",
    displayName: "Rhythm Agent",
    description: "Beat, groove, and arp pattern specialist",
    prompt: "<rhythm-system-prompt>",
    tools: ["read_arp_pattern", "generate_midi", "humanize_midi", "analyze_rhythm"],
    infer: true
  },
  {
    name: "sound",
    displayName: "Sound Oracle",
    description: "Preset recommendation and effect chain design",
    prompt: "<sound-system-prompt>",
    tools: ["search_presets", "generate_effect_chain", "analyze_frequency_balance"],
    infer: true
  },
  {
    name: "mix",
    displayName: "Mix Engineer",
    description: "Mixing, mastering, and frequency balance",
    prompt: "<mix-system-prompt>",
    tools: ["analyze_frequency_balance", "generate_effect_chain", "suggest_mix_settings"],
    infer: true
  },
  {
    name: "controller",
    displayName: "Controller Agent",
    description: "Hardware mapping, MIDI controller configuration",
    prompt: "<controller-system-prompt>",
    tools: ["read_controller_map", "generate_controller_map", "auto_map_controller"],
    infer: true
  },
  {
    name: "composer",
    displayName: "Composer (Orchestrator)",
    description: "End-to-end song generation, arrangement, multi-agent coordination",
    prompt: "<composer-system-prompt>",
    tools: ["*"],  // Access to all tools
    infer: true
  }
]
```

When `infer: true`, the SDK's router examines the user query and dispatches to the best-matching agent. The Composer agent has access to all tools and acts as the orchestrator for complex multi-step requests.

### Skill Directories Structure

```
skills/
├── harmony/
│   ├── SKILL.md              # Skill description for SDK discovery
│   ├── theory-reference.md   # Music theory grounding document
│   ├── genre-dna.json        # Genre DNA vectors
│   └── voicing-rules.md      # Voicing constraint reference
├── rhythm/
│   ├── SKILL.md
│   ├── humanization-rules.md
│   ├── groove-templates.json
│   └── time-signature-ref.md
├── sound/
│   ├── SKILL.md
│   ├── preset-catalog.json   # Pre-authored descriptions of all presets
│   ├── effect-chains.md      # Signal flow rules
│   └── genre-sound-map.json  # Genre → preset associations
├── mix/
│   ├── SKILL.md
│   ├── frequency-zones.md
│   ├── genre-mix-templates.json
│   └── masking-rules.md
└── controller/
    ├── SKILL.md
    ├── target-control-map.json  # Reverse-engineered Target_control index
    └── controller-profiles.json # Manufacturer-specific quirks
```

---

## Cross-Phase Contract Definitions

These are the **interfaces and data shapes** that cross phase boundaries. They MUST be defined before any phase begins implementation.

### Contract C1: ProgressionData (Phase 0 → 1, 2, 3, 6)

```typescript
/** Raw parsed .progression file */
interface RawProgression {
  progression: {
    name: string;           // e.g. "Gospel-Godly"
    rootNote: string;       // e.g. "E"
    scale: string;          // e.g. "Pentatonic Minor"
    recordingOctave: number;// e.g. 2
    chords: RawChord[];
  };
}

interface RawChord {
  name: string;             // e.g. "Em7/D"
  role: "Root" | "Normal";
  notes: number[];          // MIDI note numbers
}

/** Enriched progression with theory annotations */
interface EnrichedProgression extends RawProgression {
  analysis: {
    romanNumerals: string[];        // ["i", "i7/♭VII", "V/♯II", "V7/♯VII"]
    keyCenter: KeyCenter;
    voiceLeadingDistances: number[];// semitone movement between successive chords
    commonToneRetention: number[];  // count of shared notes between successive chords
    tensionValues: number[];        // T(chord) per the tension formula
    genreAssociations: string[];    // derived from name + theory features
    complexity: number;             // 0-1 scalar
    chromaticism: number;           // 0-1 scalar
  };
}

interface KeyCenter {
  root: string;        // "E"
  mode: string;        // "minor", "dorian", "mixolydian"
  confidence: number;  // 0-1
}
```

### Contract C2: ArpPatternData (Phase 0 → 3, 6)

```typescript
interface ParsedArpPattern {
  fileName: string;           // "044-Melodic-Lead Hip Hop 01"
  category: "Chord" | "Melodic" | "Bass";
  subCategory: string;        // "Lead Hip Hop", "SynBass", "Dance"
  genre: string;              // inferred from subCategory
  index: number;              // 044

  notes: MidiNoteEvent[];
  analysis: {
    durationTicks: number;
    durationBeats: number;
    noteCount: number;
    pitchRange: { low: number; high: number };
    density: number;          // notes per beat
    velocityRange: { min: number; max: number; mean: number };
    rhythmicGrid: number;     // smallest subdivision used (e.g. 16 for 16th notes)
    swingAmount: number;      // 0-1 estimated swing
    intervalDistribution: Record<number, number>; // interval → frequency
  };
}

interface MidiNoteEvent {
  tick: number;
  channel: number;
  note: number;          // MIDI note number
  velocity: number;
  durationTicks: number;
}
```

### Contract C3: ControllerMapData (Phase 0 → 7, 5)

```typescript
interface ParsedControllerMap {
  manufacturer: string;       // "Akai"
  version: string;            // "0.3"
  device: {
    inputPort: string;        // "MPK mini 3"
    outputPort: string;
  };
  pairings: ControlPairing[];
}

interface ControlPairing {
  targetControl: number;      // 0-115+ (MPC internal function index)
  targetName?: string;        // reverse-engineered human name (Phase 7 research)
  mapping: {
    type: MappingType;        // 0=unmapped, 1=note, 2=CC
    channel: number;          // MIDI channel (0-15 internal, display 1-16)
    data1: number;            // Note number or CC number
    control: number;          // 4=pad/key, 7=knob/slider
    reverse: boolean;
  };
}

enum MappingType {
  UNMAPPED = 0,
  NOTE = 1,
  CC = 2
}
```

### Contract C4: SongState (Phase 0 → ALL)

```typescript
interface SongState {
  version: string;            // schema version for migration
  metadata: SongMetadata;
  tracks: Track[];
  arrangement: Arrangement;
  progression: ProgressionState;
  mixState: MixState;
  history: HistoryEntry[];
  preferences: SessionPreferences; // Phase 9
}

interface SongMetadata {
  title: string;
  key: string;
  tempo: number;
  timeSignature: [number, number]; // [4, 4]
  influences: string[];
  moodTags: string[];
  genreDNA: GenreDNAVector;
  createdAt: string;
  updatedAt: string;
}

interface Track {
  id: string;
  name: string;
  role: TrackRole;
  midiSource?: string;        // path to .mid file
  preset?: PresetReference;
  effectsChain: EffectInstance[];
  pan: number;                // -1 to +1
  volume: number;             // 0 to 1
  mute: boolean;
  solo: boolean;
}

type TrackRole = "drums" | "bass" | "chords" | "pad" | "lead" | "melody" |
                 "percussion" | "fx" | "vocal_chop" | "sub_bass";

interface PresetReference {
  engine: string;             // "TubeSynth", "Bassline", "Electric"
  presetIndex: number;
  presetName: string;         // "169-Pad-Warm Pad"
  category: string;           // "Pad"
}

interface EffectInstance {
  pluginId: string;           // "AIR Reverb", "MPC3000"
  parameters: Record<string, number>;
  bypass: boolean;
}

interface Arrangement {
  sections: Section[];
  energyArc: EnergyPoint[];
  transitions: Transition[];
}

interface Section {
  name: string;               // "Intro", "Verse A", "Chorus"
  startBar: number;
  endBar: number;
  activeTracks: string[];     // track IDs
  energyLevel: number;        // 0-1
}

interface EnergyPoint {
  bar: number;
  energy: number;             // composite E(t) value
}

interface Transition {
  fromSection: string;
  toSection: string;
  type: "cut" | "fade" | "build" | "breakdown" | "drop" | "filter_sweep";
}

interface ProgressionState {
  chords: ChordInstance[];
  keyCenters: { chordIndex: number; key: string }[];
}

interface ChordInstance {
  symbol: string;
  midiNotes: number[];
  durationBeats: number;
  tension: number;
}

interface MixState {
  masterVolume: number;
  masterEffects: EffectInstance[];
  frequencyReport?: FrequencyReport;
}

interface HistoryEntry {
  turn: number;
  timestamp: string;
  userRequest: string;
  agentUsed: string;
  changesMade: Change[];
}

interface Change {
  path: string;               // JSON path: "tracks[0].preset"
  previousValue: unknown;
  newValue: unknown;
}
```

### Contract C5: GenreDNA (Phase 0 → 1, 3, 4, 6, 8, 9)

```typescript
interface GenreDNAVector {
  chordComplexity: number;    // 0-1
  chromaticism: number;       // 0-1
  voicingSpread: number;      // 0-1
  swing: number;              // 0-1
  vintage: number;            // 0-1
  tempoRange: [number, number]; // BPM
  rhythmicDensity: number;    // 0-1
  harmonicRhythm: number;     // chord changes per bar (0.25-4)
  darkBright: number;         // -1 to +1
  organicElectronic: number;  // -1 to +1
}

/** Pre-defined genre fingerprints */
const GENRE_DNA: Record<string, GenreDNAVector> = {
  "neo_soul": { chordComplexity: 0.85, chromaticism: 0.8, /* ... */ },
  "gospel":   { chordComplexity: 0.9, chromaticism: 0.7, /* ... */ },
  "trap":     { chordComplexity: 0.3, chromaticism: 0.4, /* ... */ },
  // ... all genres
};
```

### Contract C6: EmbeddingIndex (Phase 2 → 4, 6, 8, 9)

```typescript
interface AssetEmbedding {
  id: string;                 // unique asset ID
  type: "progression" | "arp" | "preset" | "effect" | "controller";
  name: string;
  description: string;        // human-authored enriched description
  vector: Float32Array;       // 384-dimensional
  metadata: Record<string, unknown>; // type-specific metadata
}

interface EmbeddingIndex {
  model: string;              // "all-MiniLM-L6-v2"
  dimensions: number;         // 384
  entries: AssetEmbedding[];
  search(query: string, topK?: number, typeFilter?: string[]): SearchResult[];
}

interface SearchResult {
  asset: AssetEmbedding;
  similarity: number;         // cosine similarity 0-1
}
```

### Contract C7: MidiPort (Phase 5 → 6, 7, 10)

```typescript
interface VirtualMidiPort {
  name: string;               // "MPC AI Controller"
  isOpen: boolean;

  sendNote(channel: number, note: number, velocity: number, durationMs: number): void;
  sendCC(channel: number, cc: number, value: number): void;
  sendProgramChange(channel: number, program: number): void;
  sendStart(): void;
  sendStop(): void;
  sendClock(): void;

  // Scheduled playback
  scheduleNote(channel: number, note: number, velocity: number,
               startMs: number, durationMs: number): void;
  scheduleSequence(events: ScheduledMidiEvent[]): void;
  cancelScheduled(): void;

  // Input listening (Phase 10)
  onNoteOn(callback: (channel: number, note: number, velocity: number) => void): void;
  onCC(callback: (channel: number, cc: number, value: number) => void): void;

  close(): void;
}

interface ScheduledMidiEvent {
  type: "note" | "cc" | "program_change" | "start" | "stop" | "clock";
  channel: number;
  data1: number;
  data2?: number;
  timestampMs: number;
  durationMs?: number;        // for notes
}
```

### Contract C8: CriticScores (Phase 8 → 6, 9)

```typescript
interface CriticReport {
  harmony: CriticAxis;
  rhythm: CriticAxis;
  arrangement: CriticAxis;
  vibe: CriticAxis;
  overall: number;            // weighted average
  passed: boolean;            // all axes ≥ 0.5, avg ≥ 0.7, vibe ≥ 0.5
  regenerationTarget?: string;// which axis to fix if failed
}

interface CriticAxis {
  score: number;              // 0-1
  reasoning: string;          // "Voice leading too parallel in bars 5-8"
  suggestions: string[];      // actionable fixes
}
```

### Contract C9: UserPreferences (Phase 9 → ALL)

```typescript
interface UserPreferences {
  preferenceVector: PreferenceVector;
  genreFrequency: Record<string, number>;  // genre → session count
  acceptedEmbeddingCentroid: Float32Array;  // rolling average of accepted asset embeddings
  rejectedPatterns: string[];               // "too dark", "too busy" vocabulary
  tempoAffinity: number;                   // average BPM delta from genre default
  sessionCount: number;
  producerModes: ProducerMode[];
  activeMode?: string;
}

interface PreferenceVector {
  brightness: number;        // -1 to +1
  complexity: number;
  energy: number;
  density: number;
  experimentalism: number;
  voicingSpread: number;
}

interface ProducerMode {
  name: string;
  description: string;
  overrides: Partial<PreferenceVector>;
  genreBias: Record<string, number>;
  createdAt: string;
}
```

---

## Phase Dependency Graph

```
Phase 0 ──────────────────────────────────────────────────┐
   │                                                       │
   ├──→ Phase 1 (Harmonic Brain)                          │
   │       │                                               │
   │       ├──→ Phase 2 (Embeddings) ──→ Phase 4 (Sound) │
   │       │                               │              │
   │       └──→ Phase 3 (Rhythm) ─────────┘              │
   │                │                      │              │
   │                └──────────→ Phase 5 (Virtual MIDI)   │
   │                                │                     │
   │                                ▼                     │
   │                          Phase 6 (Full Pipeline) ◄───┘
   │                                │
   │                   ┌────────────┼────────────┐
   │                   ▼            ▼            ▼
   │            Phase 7       Phase 8       Phase 9
   │          (Controller)  (Creative)    (Personal.)
   │                   │            │            │
   │                   └────────────┼────────────┘
   │                                ▼
   │                          Phase 10
   │                     (Live Performance)
   │
   └──→ [All phases import C4: SongState from Phase 0]
```

### Parallelization Opportunities

| Can run in parallel | Reason |
|---|---|
| Phase 1 + Phase 2 + Phase 3 | Independent tool domains; share only Phase 0 contracts |
| Phase 4 + Phase 5 | Sound Oracle needs embeddings (Phase 2), MIDI needs rhythm (Phase 3), but they don't need each other |
| Phase 7 + Phase 8 + Phase 9 | All depend on Phase 6 but are independent of each other |

---

## File Naming Conventions

| File Type | Convention | Example |
|---|---|---|
| Task files | `docs/tasks/PHASE-NN-NAME.md` | `PHASE-00-FOUNDATION.md` |
| Source code | `src/<domain>/<module>.ts` | `src/harmony/progression-parser.ts` |
| Skills | `skills/<domain>/SKILL.md` | `skills/harmony/SKILL.md` |
| Tests | `src/<domain>/__tests__/<module>.test.ts` | `src/harmony/__tests__/progression-parser.test.ts` |
| Schemas | `src/schemas/<name>.ts` | `src/schemas/song-state.ts` |
| Generated assets | `output/<session>/<type>/` | `output/session-001/midi/bass.mid` |
| Data catalogs | `data/<catalog>.json` | `data/preset-descriptions.json` |

---

## Estimated Total Effort

| Phase | Tasks | Complexity Profile | Estimated Dev-Weeks (1 dev) |
|---|---|---|---|
| 0 — Foundation | 12 | 6S + 4M + 2L | 3-4 |
| 1 — Harmonic Brain | 10 | 3S + 4M + 2L + 1XL | 4-5 |
| 2 — Embeddings & Search | 8 | 3S + 3M + 2L | 3-4 |
| 3 — Rhythm Engine | 11 | 4S + 4M + 2L + 1XL | 4-5 |
| 4 — Sound Oracle | 9 | 3S + 4M + 2L | 3-4 |
| 5 — Virtual MIDI | 10 | 2S + 3M + 3L + 2XL | 5-7 |
| 6 — Full Pipeline | 8 | 1S + 2M + 3L + 2XL | 5-7 |
| 7 — Controller Intelligence | 7 | 2S + 3M + 1L + 1XL | 3-4 |
| 8 — Creative Frontier | 9 | 1S + 3M + 4L + 1XL | 5-6 |
| 9 — Personalization | 8 | 0S + 5M + 3L | 4-5 |
| 10 — Live Performance | 8 | 0S + 3M + 3L + 2XL | 6-8 |
| **Total** | **100** | | **45-59 weeks** |

With parallelization (3 devs), critical path ≈ 22-30 weeks.
