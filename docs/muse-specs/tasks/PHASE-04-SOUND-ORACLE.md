# Phase 4 — Sound Oracle

## Phase Overview

**Goal**: Build the preset recommendation, effect chain generation, and mix analysis layer. The system can recommend specific synth presets for each track role, design appropriate effect chains with parameter values, and detect frequency masking issues — all without hearing audio, using structural/theoretical analysis.

**Dependencies**: Phase 0 (preset catalog), Phase 1 (harmonic context, genre DNA), Phase 2 (embedding index for semantic preset search)

**Exports consumed by**: Phase 6 (preset + effect assignment in pipeline), Phase 7 (parameter mapping to controller knobs), Phase 8 (novel sound combinations), Phase 9 (timbral preference learning)

---

## SDK Integration Points

| SDK Feature | Phase 4 Usage |
|---|---|
| `defineTool()` | `recommend_preset`, `generate_effect_chain`, `analyze_frequency_balance`, `suggest_mix_settings` |
| `customAgents` | Define `sound` agent (presets, timbral design) + `mix` agent (mixing, effects, frequency balance) |
| `skillDirectories` | `skills/sound/` with preset catalog, effect chain rules, genre sound maps |
| `search_assets` tool (from Phase 2) | Sound agent uses semantic search to find presets by description |

---

## Task Breakdown

### Task 4.1 — Preset Recommendation Engine

**Description**: Given a track role, genre, and mood context, recommend specific synth presets from the MPC Beats library with reasoning.

**Input**:
```typescript
interface PresetRecommendationRequest {
  trackRole: TrackRole;          // "pad", "bass", "lead", etc.
  genre: string;
  mood?: string;                 // "warm", "aggressive", "ethereal"
  context?: {
    otherPresets: PresetReference[];  // already-chosen presets (avoid spectral overlap)
    key: string;
    tempo: number;
  };
  count?: number;                // how many suggestions (default 3)
}
```

**Output**:
```typescript
interface PresetRecommendation {
  preset: PresetReference;
  similarity: number;           // embedding search score
  reasoning: string;            // "TubeSynth Warm Pad provides the lush, enveloping texture ideal for neo-soul chord pads"
  genreMatch: number;           // 0-1 how well it fits the genre
  roleMatch: number;            // 0-1 how well it fits the track role
  alternatives: PresetReference[];  // 2-3 backup options
}
```

**Implementation Hints**:
- Two-stage recommendation:
  1. **Filter**: By engine capability × track role (e.g., bass role → only TubeSynth Bass category, Bassline engine)
  2. **Rank**: Semantic search (Phase 2) on constructed query: "{mood} {genre} {role} sound"
- Role-to-engine mapping:
  - `drums` → DrumSynth variants (Kick, Snare, HiHat, etc.)
  - `bass` → TubeSynth Bass (65), Bassline
  - `pad` → TubeSynth Pad (68)
  - `lead` → TubeSynth Lead (50)
  - `chords` → TubeSynth Synth (44), Velvet, Mini Grand, Electric
  - `fx` → TubeSynth FX (23)
- Genre-to-preset associations (from blueprint Section 6):
  - Neo Soul → Velvet, Electric, TubeSynth smooth categories
  - Trap → Bassline (808), TubeSynth hard categories
  - House → TubeSynth Supersaw, Bassline (303 acid)
  - Gospel → DB-33, Mini Grand
  - Jazz → Mini Grand, DB-33
- Context-aware: if another pad is already using a "warm" preset, suggest a contrasting timbre to avoid masking
- Include spectral region estimate per preset category:
  - Bass: 40-300Hz primary
  - Pad: 200Hz-4kHz wide
  - Lead: 800Hz-6kHz focused

**Testing**: Request "neo-soul pad" → verify TubeSynth Warm Pad or Analog Tube Richness in top 3. Request "trap bass" → verify Bassline or TubeSynth Sub Bass variants. Request "gospel keys" → verify DB-33 or Mini Grand. Verify no cross-category errors (lead preset recommended for bass role).

**Complexity**: M

---

### Task 4.2 — Effect Chain Generator

**Description**: Generate ordered effect chains with parameter value suggestions for a given instrument role, genre, and aesthetic goal.

**Input**:
```typescript
interface EffectChainRequest {
  trackRole: TrackRole;
  preset: PresetReference;
  genre: string;
  aesthetic: string;            // "warm and spacious", "tight and punchy", "vintage crunch"
  mixPosition: "front" | "middle" | "back";  // perceived depth
  stereoWidth: "mono" | "narrow" | "wide" | "extreme";
  vintage?: boolean;            // apply character effects
}
```

**Output**: `EffectInstance[]` (ordered chain with parameters)

**Implementation Hints**:
- **Signal flow order is physics** (from blueprint Section 6):
  1. Source shaping: EQ, Filter, Distortion
  2. Dynamics: Compressor, Transient Shaper
  3. Time-based: Delay, Reverb
  4. Modulation: Chorus, Phaser, Flanger
  5. Character: MPC3000, MPC60, SP1200, Lo-Fi
  6. Master: Maximizer, Limiter, Stereo Width
- The chain generator NEVER violates this order
- Genre-specific chains (from blueprint's timbral ontology):
  - **Neo Soul Pad**: Chorus 4-voice → Reverb Large 2 (4.5s, hi-cut 6kHz)
  - **Trap 808**: Compressor Opto → LP Filter (120Hz) → Distortion Custom (light)
  - **Boom-bap drums**: SP1200 → Bus Compressor → Reverb Small
  - **House lead**: Filter Gate → Delay Sync → Reverb Medium
  - **Lo-fi anything**: MPC60 → Lo-Fi → Reverb Small → Chorus 2-voice
- Parameter value estimation (without hearing audio):
  - Reverb time: 0.5-1s (tight) to 4-6s (spacious), genre-dependent
  - Delay time: calculated from BPM (1/4 note = 60000/BPM ms, dotted 8th = 0.75 × that)
  - Compressor ratio: 2:1 (gentle) to 8:1 (aggressive), genre-dependent
  - Filter cutoff: based on spectral region of the instrument role
- Mix position mapping:
  - `front`: less reverb, more compression, upper-mid boost
  - `back`: more reverb, less compression, hi-cut filter
  - `middle`: balanced

**Testing**: Generate chain for "neo-soul pad, warm and spacious, back, wide" → verify contains Chorus + Reverb Large in correct order. Generate chain for "trap 808 bass, tight and punchy, front, mono" → verify Compressor + LP Filter, no reverb. Verify no chain ever has delay before dynamics.

**Complexity**: L

---

### Task 4.3 — Frequency Balance Analyzer

**Description**: Analyze a multi-track arrangement for potential frequency masking issues WITHOUT audio — using MIDI note data, preset spectral profiles, and effect chain impacts.

**Input**: `SongState` with tracks (MIDI notes + presets + effects)

**Output**:
```typescript
interface FrequencyReport {
  zones: FrequencyZone[];
  clashes: FrequencyClash[];
  gaps: FrequencyGap[];
  monoCompatibility: MonoCompatibilityIssue[];
  overallScore: number;         // 0-1 (1 = clean)
  suggestions: string[];
}

interface FrequencyClash {
  track1: string;
  track2: string;
  frequencyRange: [number, number]; // Hz
  severity: "info" | "warning" | "critical";
  suggestion: string;
}

interface FrequencyGap {
  frequencyRange: [number, number];
  description: string;
}
```

**Implementation Hints**:
- **Spectral profile estimation** (per track):
  1. MIDI note fundamentals → frequency (f = 440 × 2^((n-69)/12))
  2. Preset category → harmonic content estimate:
     - Sine/sub: fundamental only, decay above fundamental
     - Saw: odd+even harmonics, -6dB/octave rolloff
     - Square: odd harmonics only, -6dB/octave
     - Pad: wide spectral content, 200Hz-4kHz
     - Pluck: initial bright transient → dark sustain
  3. Effect chain impact: LP filter → cut above cutoff, Distortion → add harmonics above fundamental, Reverb → extend spectral energy at tail frequencies
- **Masking detection**: For each pair of tracks, estimate spectral overlap:
  - Compute overlap area between two spectral profiles
  - Weight by perceptual importance (200-500Hz × 2, sub 100Hz × 3, above 8kHz × 0.5)
  - Threshold: overlap > 0.4 → warning, > 0.7 → critical
- **Gap detection**: If no track has significant energy in a frequency zone, flag it
- **Mono compatibility**: Stereo effects (Chorus, Stereo Width, Ping Pong Delay) → estimate phase cancellation when summed to mono
- Blueprint's frequency zones:
  | Zone | Hz | Typical Role |
  |---|---|---|
  | Sub | 20-60 | 808/sub, kick fundamental |
  | Bass | 60-250 | Bass body, kick punch |
  | Low-Mid | 250-800 | Chord body, snare |
  | Mid | 800-2k | Lead, vocal |
  | Upper-Mid | 2-5k | Clarity, hi-hat |
  | Air | 5-20k | Shimmer, sparkle |

**Testing**: Create SongState with pad (C3-C5 range) + lead (C4-C6 range) → verify masking detected in 500Hz-2kHz zone. Add bass (C1-C2) → verify no masking with pad. Verify mono compatibility warning when wide stereo chorus is applied.

**Complexity**: L

---

### Task 4.4 — Genre Mix Template System

**Description**: Define per-genre mixing conventions: target LUFS, frequency balance profiles, typical effect usage, stereo field conventions.

**Input**: Genre name

**Output**:
```typescript
interface GenreMixTemplate {
  genre: string;
  targetLUFS: [number, number];           // range, e.g. [-14, -12] for neo-soul
  frequencyBalance: FrequencyBalance;     // relative level per zone
  stereoConventions: StereoConventions;
  characterEffects: string[];             // effects that define the genre's character
  dynamicRange: "compressed" | "moderate" | "dynamic";
  notes: string;
}

interface FrequencyBalance {
  sub: number;          // relative level (0-1)
  bass: number;
  lowMid: number;
  mid: number;
  upperMid: number;
  air: number;
}
```

**Implementation Hints**:
- From blueprint Section 7:
  - **Trap**: 808 loudest, Bus Compressor on drums, -7 to -9 LUFS
  - **Neo Soul**: warm, rounded, -12 to -14 LUFS, dynamic
  - **UK Garage**: sub mono, reverb-drenched, -10 to -12 LUFS
  - **House**: sub centered, bright top, -8 to -10 LUFS
  - **Gospel**: natural dynamics, warm, -10 to -12 LUFS
  - **Jazz**: very dynamic, -14 to -18 LUFS, minimal processing
  - **Lo-fi**: mid-focused, limited bandwidth, -12 to -14 LUFS
- Store in `skills/mix/genre-mix-templates.json`
- Used by mix agent to guide suggestions and validate effect chain outputs

**Testing**: Verify all supported genres have templates. Verify LUFS ranges are reasonable. Verify frequency balance values sum to reasonable total.

**Complexity**: S

---

### Task 4.5 — Mix Suggestion Tool

**Description**: Given a SongState with tracks, generate mix-level suggestions: track volumes, panning, master bus processing.

**Input**: `SongState`

**Output**:
```typescript
interface MixSuggestion {
  trackSettings: {
    trackId: string;
    suggestedVolume: number;     // 0-1
    suggestedPan: number;        // -1 to +1
    reasoning: string;
  }[];
  masterBusSuggestions: EffectInstance[];
  overallNotes: string;
}
```

**Implementation Hints**:
- Volume balancing heuristic:
  - Drums/bass: loudest (0.8-1.0) in most genres
  - Lead: prominent (0.7-0.9)
  - Chords/pads: supportive (0.5-0.7)
  - FX: subtle (0.2-0.5)
  - Adjust by genre (Trap: 808 dominates; Jazz: everything balanced)
- Panning conventions:
  - Kick, snare, bass: center (0.0)
  - Hi-hat: slight off-center (±0.2-0.4)
  - Chords: spread (LR)
  - Percussion: wide (±0.5-0.8)
  - Lead: center or slight offset
- Master bus: Bus Compressor (glue) → Para EQ (tonal shape) → Maximizer (loudness)
- Parameter values derived from genre mix template (Task 4.4)

**Testing**: Create SongState with drums+bass+pad+lead. Verify bass is centered, pad is spread, lead is centered. Verify master bus chain follows correct signal flow order.

**Complexity**: M

---

### Task 4.6 — Timbral Similarity Score

**Description**: Compute a similarity score between two presets based on their descriptions and category alignment. Used for finding alternatives and detecting potential masking.

**Input**: Two `PresetReference` objects

**Output**: `{ similarity: number, spectralOverlap: number, reasoning: string }`

**Implementation Hints**:
- Use embedding cosine similarity from Phase 2 descriptions
- Spectral overlap estimate: if both presets occupy the same frequency zone (e.g., both pads → high overlap), penalize
- Same engine + same category → very high similarity (>0.9)
- Same engine + different category → moderate (0.4-0.6)
- Different engine → depends on description similarity
- Useful for: "suggest an alternative that sounds different" (low similarity), "find something that pairs well" (moderate similarity, low spectral overlap)

**Testing**: TubeSynth "Warm Pad" vs "Large Warm Pad" → high similarity. TubeSynth "Warm Pad" vs "Hard Sync" → low similarity. TubeSynth "Sub Bass 1" vs Bassline preset → moderate (similar role, different engine character).

**Complexity**: S

---

### Task 4.7 — Effect Parameter Calculator

**Description**: Calculate tempo-synced effect parameters (delay times, LFO rates, gate durations) from BPM and musical subdivision.

**Input**: BPM + subdivision (quarter, 8th, dotted 8th, 16th, triplet, etc.)

**Output**: Parameter values in milliseconds or Hz

**Implementation Hints**:
- Core formula: `delayMs = 60000 / BPM * multiplier`
  - Quarter: multiplier = 1.0
  - 8th: 0.5
  - Dotted 8th: 0.75
  - 16th: 0.25
  - Triplet 8th: 0.333
  - Dotted quarter: 1.5
- For LFO rates (tremolo, chorus, phaser): convert ms period to Hz: `lfoHz = 1000 / delayMs`
- For reverb pre-delay: typically 1/64 to 1/16 note: 60000 / (BPM × 16) to 60000 / (BPM × 4)
- For gate/sidechain frequency: match kick pattern (usually quarter note in house)
- Return all common subdivisions in a table for the LLM to select from

**Testing**: At 120 BPM: quarter = 500ms, 8th = 250ms, dotted 8th = 375ms, 16th = 125ms. Verify all calculations. Test at 130 BPM (common house tempo) and 90 BPM (common hip-hop tempo).

**Complexity**: S

---

### Task 4.8 — Sound & Mix Agent Definitions

**Description**: Create the `skills/sound/` and `skills/mix/` directories and define both `customAgent` configurations.

**Input**: Outputs from Tasks 4.1-4.7

**Output**:
- `skills/sound/SKILL.md`, `skills/sound/preset-catalog.json`, `skills/sound/genre-sound-map.json`
- `skills/mix/SKILL.md`, `skills/mix/genre-mix-templates.json`, `skills/mix/frequency-zones.md`, `skills/mix/masking-rules.md`
- Sound agent and Mix agent config objects

**Implementation Hints**:
- Sound agent handles: "Which synth should I use for bass?", "Make this sound warmer"
- Mix agent handles: "Check my frequency balance", "How should I set up reverb?"
- Overlap resolution: when user asks about effects, the SDK router may ambiguate between sound (timbral effects) and mix (technical effects). Solution: both agents have access to `generate_effect_chain`, but Sound agent focuses on creative chain design while Mix agent focuses on corrective EQ/compression.
- Sound agent tools: `["recommend_preset", "generate_effect_chain", "search_assets", "analyze_frequency_balance"]`
- Mix agent tools: `["analyze_frequency_balance", "suggest_mix_settings", "generate_effect_chain", "calculate_effect_params"]`

**Testing**: "What preset should I use for a warm neo-soul pad?" → Sound agent. "My bass and pad are clashing" → Mix agent. Verify routing differentiation.

**Complexity**: S

---

### Task 4.9 — "X-Ray Mode" Explainer

**Description**: Implement the capability to explain any sound design or mixing decision with music theory and physics grounding. This is the "Why?" feature from the blueprint.

**Input**: Any previous recommendation or suggestion (preset, effect chain, mix setting)

**Output**: Multi-level explanation
```typescript
interface XRayExplanation {
  decision: string;             // what was recommended
  quickExplanation: string;     // 1-2 sentences
  deepExplanation: {
    musicalReasoning: string;   // why this works musically
    physicsReasoning: string;   // signal chain physics
    genreContext: string;       // how this fits the genre
    alternatives: string;       // what else could work and tradeoffs
    corpusEvidence: string;     // grounded in actual MPC Beats assets
  };
}
```

**Implementation Hints**:
- This is primarily a prompt engineering task — the tool formats context for the LLM to explain
- The tool retrieves the decision's context (from SongState history) and constructs a prompt:
  - "Explain why [preset X] was recommended for [role Y] in [genre Z] context"
  - Include: genre DNA vector values, spectral considerations, alternative candidates
- Ground in corpus: "I recommended TubeSynth 'Warm Pad' because your Neo Soul progressions (like the ones in your library) pair with wide, sustained textures..."
- The LLM provides the actual explanation; the tool provides structured context

**Testing**: Recommend a preset, then ask "Why?" → verify explanation references the genre, the role, and ideally the specific preset's sonic character. Verify corpus grounding is present.

**Complexity**: M

---

## Modular Boundaries

| Can develop independently | Notes |
|---|---|
| Task 4.1 (preset recommendation) | Needs Phase 2 search |
| Task 4.2 (effect chain generator) | Independent — rule-based |
| Task 4.3 (frequency analyzer) | Independent algorithm |
| Task 4.4 (genre mix templates) | Independent data task |
| Task 4.5 (mix suggestions) | Needs 4.3 + 4.4 |
| Task 4.6 (timbral similarity) | Needs Phase 2 embeddings |
| Task 4.7 (parameter calculator) | Fully independent — pure math |
| Task 4.9 (X-Ray mode) | Needs all above for context |

**Parallelizable**: 4.1, 4.2, 4.3, 4.4, 4.6, 4.7 all in parallel → 4.5 → 4.8, 4.9

---

## Cross-Phase Exports

| Export | Consumer |
|---|---|
| `recommendPreset` tool | Phase 6 (pipeline), Phase 9 (preference-adjusted recommendations) |
| `generateEffectChain` tool | Phase 6 (pipeline), Phase 7 (mapping effect params to knobs) |
| `analyzeFrequencyBalance` tool | Phase 6 (post-generation validation), Phase 8 (arrangement critic) |
| `GenreMixTemplate` type and data | Phase 6, Phase 7 |
| `calculateEffectParams` function | Phase 5 (setting MIDI CC for delay sync), Phase 6 |
| Sound + Mix agent configs | Phase 6 (multi-agent orchestration) |
| `XRayExplanation` type | Phase 6 (user asks "why?"), Phase 8 (quality gate explanations) |

---

## Risk Flags

| Risk | Severity | Description |
|---|---|---|
| Preset descriptions accuracy | High | We're describing presets from their names only. "Hard Sync" could sound very different from what the name implies. Mitigation: conservative descriptions + "try it" philosophy. |
| Effect parameter ranges | Medium | We don't know the actual parameter ranges of MPC Beats effects. We're estimating values. Mitigation: use standard ranges (0-127, 0-100%), note uncertainty in output. |
| Spectral estimation without audio | High | All frequency analysis is theoretical. Real audio could clash differently than predicted. Mitigation: frame outputs as "potential issues" not "definitive problems." |
| .xpl binary format | Medium | Phase 4 is designed to AVOID parsing .xpl. If future phases need actual preset parameters (e.g., filter cutoff value), this becomes a reverse-engineering task. |
