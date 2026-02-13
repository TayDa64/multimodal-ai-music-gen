# Phase 6 — Full Pipeline (End-to-End Song Generation)

## Phase Overview

**Goal**: Integrate all prior phases into a cohesive end-to-end pipeline. A single natural-language prompt ("Frank Ocean meets Burial, late-night vibes") produces: a chord progression (.progression), multi-track MIDI (.mid files), preset recommendations, effect chain specifications, arrangement structure, and optionally live MIDI playback — all orchestrated through the Copilot SDK's multi-agent system.

**Dependencies**: ALL prior phases (0-5)

**Exports consumed by**: Phase 7 (controller setup for generated sessions), Phase 8 (quality gates applied to pipeline output), Phase 9 (preference learning from pipeline interactions), Phase 10 (live performance from generated material)

---

## SDK Integration Points

| SDK Feature | Phase 6 Usage |
|---|---|
| `customAgents` | **Composer agent** (orchestrator) with access to all tools + sub-agent routing |
| `hooks.onUserPromptSubmitted` | Intent classification: simple query vs. full pipeline trigger |
| `hooks.onPreToolUse` | Pipeline progress tracking, stage gating |
| `hooks.onPostToolUse` | SongState accumulation after each pipeline stage |
| `infiniteSessions` | Critical: pipeline + iteration can exceed 50 turns |
| Streaming (`message_delta`) | Real-time progress: "Stage 2/6: Generating harmony..." |
| `ask_user` tool | Genre disambiguation, A/B choices, approval gates between stages |
| `systemMessage` (dynamic) | Inject L1 SongState after each pipeline stage for context |

---

## Task Breakdown

### Task 6.1 — Intent Decomposition Engine

**Description**: Parse a natural-language song request into structured creative constraints that drive the pipeline.

**Input**: User prompt string (e.g., "Frank Ocean meets Burial, late-night vibes, 130 BPM")

**Output**:
```typescript
interface PipelineIntent {
  // Extracted constraints
  influences: ArtistInfluence[];
  mood: string[];                   // ["late-night", "melancholy", "atmospheric"]
  genre: {
    primary: string;                // derived from influences
    secondary?: string;
    blendWeights: [number, number]; // [0.6, 0.4]
    dnaVector: GenreDNAVector;      // interpolated
  };
  tempo: {
    bpm: number;
    confidence: "explicit" | "inferred";
    halfTime: boolean;              // derived insight from tempo intersection
  };
  key: {
    root: string;
    mode: string;
    confidence: "explicit" | "inferred";
  };
  duration: {
    totalBars: number;
    sections: string[];             // ["intro", "verse", "chorus", "outro"]
  };
  energy: {
    overall: number;                // 0-1
    arc: "building" | "steady" | "declining" | "wave" | "custom";
  };
  creativityDials: {
    harmonic: number;               // 0-1
    rhythmic: number;               // 0-1
  };
  // What to generate
  requestedOutputs: ("progression" | "midi" | "presets" | "effects" | "arrangement" | "playback")[];

  // Ambiguities requiring clarification
  ambiguities: string[];
}

interface ArtistInfluence {
  name: string;
  traits: string[];                 // ["neo-soul harmony", "lush reverbs", "60-75 BPM"]
  genreMapping: string;
  weight: number;
}
```

**Implementation Hints**:
- This is primarily an LLM task, but the tool structures the output:
  1. The LLM analyzes the prompt and extracts entities (artists, genres, moods, tempo, key)
  2. The tool validates and enriches:
     - Artist → genre mapping (lookup table of ~100 common artists)
     - Tempo inference: from genre DNA if not specified
     - Key inference: common keys for genre (trap → minor keys, house → major)
     - Half-time detection: if two influences have different tempo ranges, check for half-time intersection
  3. Genre DNA blending: interpolate vectors based on influence weights
  4. If ambiguities remain, use `ask_user` to clarify
- The "Frank Ocean meets Burial" example from the blueprint:
  - Frank Ocean → neo-soul, 60-75 BPM, maj9 chords, lush reverbs
  - Burial → UK garage, 130-140 BPM, lo-fi vinyl, 2-step
  - Half-time insight: 130 BPM clock, half-time feel → perceived 65 BPM
  - Blend: (0.6 × neo-soul + 0.4 × uk-garage) DNA

**Testing**: "Trap beat, dark, 140 BPM" → verify: genre=trap, mood=dark, tempo=140, key=minor (inferred). "Frank Ocean meets Burial" → verify half-time detection, genre blending. "Something warm" → verify ambiguity flagged for genre.

**Complexity**: L

---

### Task 6.2 — Pipeline Orchestrator

**Description**: Implement the multi-stage pipeline that coordinates all sub-agents to produce a complete song. This is the Composer agent's core logic.

**Input**: `PipelineIntent` (from Task 6.1)

**Output**: Completed `SongState` + generated files

**Pipeline stages**:
```
Stage 1: Intent → Constraints (Task 6.1)
Stage 2: Constraints → Chord Progression (Harmony Agent)
Stage 3: Constraints + Chords → Arrangement Structure
Stage 4: Arrangement + Chords → MIDI Parts (Rhythm Agent, parallelized)
  └→ 4a: Drums
  └→ 4b: Bass
  └→ 4c: Chord voicing
  └→ 4d: Lead/melody (optional)
Stage 5: All Parts → Preset Selection (Sound Agent)
Stage 6: Presets + Genre → Effect Chains (Sound/Mix Agent)
Stage 7: Everything → Assembly + Validation (Composer)
Stage 8: (Optional) Play via virtual MIDI port
```

**Implementation Hints**:
- The Composer agent has `tools: ["*"]` — access to all tools
- Pipeline coordination is conversation-driven: the Composer agent sends messages to itself, calling tools at each stage
- Stage parallelization: 4a, 4b, 4c, 4d can run in parallel (independent MIDI generation tasks)
  - But the Copilot SDK executes tools sequentially per turn
  - Workaround: have the LLM call `generate_drum_pattern` → `generate_bassline` → `generate_chord_voicing_midi` → `generate_melody` in one multi-tool turn
- After each stage, update SongState via `onPostToolUse` hook
- Progress reporting: after each stage, emit a status message:
  ```
  ✓ Stage 2: Generated 8-chord progression in Eb minor (Ebm9 → Dbmaj7/F → ...)
  → Stage 3: Designing arrangement structure...
  ```
- Checkpoint: persist `SongState` to disk after each stage (crash recovery)
- If any stage fails (tool error, quality gate rejection in Phase 8), retry that stage with modified parameters, max 3 attempts

**Testing**: Run full pipeline with "Neo soul, Eb minor, 90 BPM, 4 tracks, 32 bars" → verify all files generated. Verify SongState has all tracks, arrangement, progression. Verify file count: 1 .progression + 4+ .mid files.

**Complexity**: XL

---

### Task 6.3 — Arrangement Structure Generator

**Description**: Given constraints and a chord progression, design the song's section structure (intro, verse, chorus, etc.) with energy arc and track assignments.

**Input**: `PipelineIntent` + `EnrichedProgression`

**Output**: `Arrangement` (for SongState)

**Implementation Hints**:
- Genre-typical structures:
  - **Pop/RnB**: Intro(4) → Verse(8) → Pre-Chorus(4) → Chorus(8) → Verse(8) → Chorus(8) → Bridge(8) → Chorus(8) → Outro(4)
  - **House/EDM**: Intro(16) → Build(8) → Drop(16) → Break(8) → Build(8) → Drop(16) → Outro(8)
  - **Trap**: Intro(4) → Verse(16) → Hook(8) → Verse(16) → Hook(8) → Outro(4)
  - **Jazz/Neo Soul**: Head(16) → Solo section(16-32) → Head reprise(16)
- Energy arcs:
  - Default: gradual build with climax at chorus/drop
  - Wave: energy rises and falls cyclically
  - Build: continuous upward energy
- Section transitions from SongState contract: "cut", "fade", "build", "breakdown", "drop", "filter_sweep"
- Track activation per section:
  - Intro: sparse (pad only, or pad + drums)
  - Verse: moderate (add bass, light drums)
  - Chorus/Drop: all tracks active
  - Break: strip to 1-2 elements
- Map the chord progression across sections: repeat it or use different subsets per section

**Testing**: Generate arrangement for "pop, 64 bars, 4 tracks" → verify at least 4 sections, energy peaks at chorus, all tracks active somewhere, total bars = 64.

**Complexity**: M

---

### Task 6.4 — Output File Manager

**Description**: Manage the output directory structure, write all generated files, and produce a session manifest.

**Input**: SongState + generated MIDI/progression data

**Output**: Files written to `output/<session-id>/`

**Directory structure**:
```
output/
└── session-20260208-a1b2/
    ├── song-state.json           # Full SongState
    ├── manifest.json             # File listing + metadata
    ├── progression/
    │   └── main.progression      # Generated chord progression
    ├── midi/
    │   ├── drums.mid
    │   ├── bass.mid
    │   ├── chords.mid
    │   ├── lead.mid
    │   └── full-arrangement.mid  # Multi-track arrangement
    └── notes/
        ├── preset-assignments.md  # Which preset for each track
        ├── effect-chains.md       # Effect chains with parameters
        ├── arrangement-map.md     # Section structure
        └── producer-notes.md      # Setup instructions for MPC Beats
```

**Implementation Hints**:
- Create session directory with timestamp + random suffix
- `manifest.json`:
  ```typescript
  interface SessionManifest {
    sessionId: string;
    createdAt: string;
    prompt: string;                // original user prompt
    genre: string;
    key: string;
    tempo: number;
    files: { path: string; type: string; description: string }[];
    stageTimings: { stage: string; durationMs: number }[];
  }
  ```
- `producer-notes.md` — human-readable setup guide:
  ```markdown
  # Session: Frank Ocean meets Burial
  
  ## Quick Start
  1. Open MPC Beats
  2. Set tempo to 130 BPM
  3. Create 4 tracks:
     - Track 1 (Drums): Load DrumSynth, import `midi/drums.mid`
     - Track 2 (Bass): Load TubeSynth → Preset 237 "Sub Bass 1", import `midi/bass.mid`
     ...
  4. Apply effect chains (see effect-chains.md)
  ```
- Write all files atomically (write to temp, then rename) to avoid partial output on crash

**Testing**: Run pipeline → verify all expected files exist. Verify manifest.json parses correctly. Verify .progression file loads in Phase 0 parser. Verify .mid files are valid.

**Complexity**: M

---

### Task 6.5 — Multi-Track Assembly Tool

**Description**: Combine individual MIDI track files into a single multi-track MIDI file and a combined SongState.

**Input**: Individual track MIDI files + arrangement structure

**Output**: `full-arrangement.mid` (Format 1, multi-track)

**Implementation Hints**:
- This extends Task 3.7 (arrangement sequencer) with file-based workflow:
  1. Read each individual track .mid file
  2. Apply arrangement structure (which tracks play in which sections)
  3. Apply transitions (volume automations, fills at section boundaries)
  4. Write combined Format 1 MIDI file
- Track assignment:
  - Track 0: Tempo map
  - Track 1-N: Individual instrument tracks with correct channel assignments
- Include track names (MIDI meta event: track name) for DAW display
- File can be imported directly into MPC Beats as a reference

**Testing**: Assembly 4 individual tracks into one multi-track file. Verify track count, total duration, event counts per track. Parse with Phase 0 MIDI parser to verify.

**Complexity**: M

---

### Task 6.6 — Iteration & Refinement Loop

**Description**: Enable iterative refinement of the generated song: modify a single element, re-generate a section, change a track, adjust mix settings — without re-running the entire pipeline.

**Input**: User modification request + current SongState

**Output**: Updated SongState + updated files

**Implementation Hints**:
- From the blueprint's 10-turn iteration example:
  - "3rd chord too bright, make darker" → modify single chord in progression, re-voice, re-generate chord track MIDI
  - "Bass too busy, simplify" → reduce bassline density, re-generate bass MIDI only
  - "Make it warmer overall" → adjust effect chains, preset recommendations
- Modification routing:
  1. Parse modification request → identify which SongState component to change
  2. Determine blast radius: what other components are affected?
     - Change key → everything re-generates
     - Change one chord → re-voice that chord, may affect surrounding voice leading
     - Change preset → only preset reference + possibly effect chain
     - Change tempo → re-calculate all time-based values (delay, reverb pre-delay)
  3. Re-generate only affected components (from Task 6.2, but partial)
  4. Update SongState history
- Sensitivity annotations (from blueprint):
  - `DrumPattern.sensitiveTo = ['tempo', 'genre', 'energy']`
  - `Bassline.sensitiveTo = ['key', 'progression', 'tempo', 'genre']`
  - `Melody.sensitiveTo = ['key', 'progression', 'scale']`
  - `Preset.sensitiveTo = ['genre', 'role']`
  - `EffectChain.sensitiveTo = ['genre', 'preset', 'mixPosition']`
- Contradiction handling from blueprint:
  - Temporal override: latest instruction wins for specific element
  - Scope detection: ask clarification if ambiguous
  - Synthesis: "warm + bright" = different frequency ranges affected differently

**Testing**: Generate full song → change one chord → verify only progression + chord MIDI regenerated, drums unchanged. Change tempo → verify all time-based parameters updated. Verify SongState history records each change.

**Complexity**: XL

---

### Task 6.7 — A/B Alternative Generation

**Description**: Generate 2-3 alternative versions of any pipeline element for user comparison and selection.

**Input**: Element to vary + SongState context

**Output**: Ranked alternatives with comparison descriptions

**Implementation Hints**:
- From blueprint: "Generate 2-3 alternatives for each element, evaluate head-to-head"
- Implementation:
  1. For the target element (progression, bassline, preset, etc.), generate 3 variants:
     - Variant A: default/best-match generation
     - Variant B: +10% creativity dial
     - Variant C: different structural approach (e.g., different bass style, different voicing)
  2. Score each variant (using Phase 8 critics when available, or simpler heuristics pre-Phase 8)
  3. Present to user with descriptions: "Option A is more traditional, Option B has unexpected chromatic movement, Option C uses a walking bass instead"
  4. User selects → apply to SongState
- When user says "try something different": surface the next ranked alternative from the candidates array
- Only regenerate if all candidates exhausted (with temperature bump)
- Store unused alternatives in SongState for potential retrieval later

**Testing**: Request 3 bassline alternatives. Verify all 3 are valid (parseable, correct key). Verify they are meaningfully different (not identical). Select alternative B → verify SongState updated with B.

**Complexity**: L

---

### Task 6.8 — Composer Agent Definition

**Description**: Define the master Composer agent that orchestrates the full pipeline, coordinating with all sub-agents.

**Input**: All agent definitions from prior phases + pipeline tools

**Output**: Composer agent config for `customAgents`

**Implementation Hints**:
- The Composer agent is the "god agent" — access to ALL tools:
  ```typescript
  {
    name: "composer",
    displayName: "Composer",
    description: "End-to-end song generation and arrangement orchestrator. Coordinates harmony, rhythm, sound, and mix agents. Handles complex multi-step requests that span multiple domains.",
    prompt: buildComposerPrompt(),
    tools: ["*"],   // all tools
    infer: true
  }
  ```
- Composer prompt includes:
  - Pipeline stage descriptions
  - Sensitivity annotation table
  - Iteration philosophy ("change only what's necessary")
  - SongState L1 context injection
  - Reference to the pipeline walkthrough (Frank Ocean meets Burial)
- The Composer should be the default agent for complex requests ("compose a song", "create a beat")
- Simple domain-specific queries ("what key is this in?") should route to domain agents
- When the Composer needs domain expertise, it should call domain tools (which are backed by domain agents' logic)
- Session-level system message should include: "For complex composition requests, the Composer agent orchestrates multiple specialized sub-agents."

**Testing**: "Create a neo-soul beat" → routes to Composer → triggers full pipeline. "What chord is this?" → routes to Harmony agent (not Composer). Verify Composer produces complete output with all expected files.

**Complexity**: M

---

## Modular Boundaries

| Can develop independently | Notes |
|---|---|
| Task 6.1 (intent decomposition) | Needs genre DNA from Phase 1 |
| Task 6.3 (arrangement generator) | Needs Phase 1 progression data |
| Task 6.4 (file manager) | Independent — pure I/O |
| Task 6.5 (multi-track assembly) | Needs Phase 3 sequencer |
| Task 6.2 (pipeline orchestrator) | Integrates everything — last to develop |
| Task 6.6 (iteration loop) | Requires 6.2 as foundation |
| Task 6.7 (A/B generation) | Requires individual generators from Phases 1, 3, 4 |

**Critical path**: 6.1 → 6.4 → 6.2 → 6.6

---

## Cross-Phase Exports

| Export | Consumer |
|---|---|
| `PipelineIntent` type | Phase 8 (creative dials setting), Phase 9 (preference extraction) |
| `PipelineOrchestrator` | Phase 8 (quality gates inject into pipeline), Phase 9 (preference-adjusted orchestration) |
| `SessionManifest` | Phase 9 (session history for learning) |
| Iteration loop mechanics | Phase 9 (captures modification signals for preference learning) |
| Composer agent config | Root-level agent setup, Phase 8 (critic integration) |
| A/B generation framework | Phase 8 (multi-critic scoring of alternatives) |

---

## Risk Flags

| Risk | Severity | Description |
|---|---|---|
| Pipeline latency | Critical | Full pipeline = 6+ LLM calls + 4+ tool calls. At 3-5s per LLM call, total could be 30-60s. Mitigation: parallel tool calls where possible, progress streaming, speculative generation. |
| Agent routing accuracy | High | `infer: true` may misroute complex queries. "Make the bass warmer" could go to Sound or Mix agent. Mitigation: Composer as catch-all, clear agent descriptions. |
| Context window in long sessions | High | Pipeline + 10 iterations = potentially 100+ tool calls. `infiniteSessions` compaction must preserve SongState coherence. Mitigation: L0/L1 compression, SongState always injected fresh. |
| Iteration blast radius | Medium | Changing key should re-generate everything, but that's expensive. Mitigation: sensitivity annotations + user confirmation for large re-generations. |
| Cross-agent state consistency | Medium | If Harmony agent modifies the progression and Rhythm agent hasn't been notified, generated bass may not fit new chords. Mitigation: SongState is the single source of truth, always re-read before generating. |
