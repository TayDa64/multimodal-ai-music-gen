# Phase 1 — Harmonic Brain

## Phase Overview

**Goal**: Transform the raw progression parser from Phase 0 into a full harmonic intelligence layer. The system can analyze any chord progression with Roman numeral analysis, tension scoring, voice leading evaluation, and genre association. It can generate new progressions given genre/mood/key constraints, explain music theory concepts, and map its knowledge to the MPC Beats `.progression` file format.

**Dependencies**: Phase 0 (parsers, SongState, tool infrastructure)

**Exports consumed by**: Phase 2 (descriptions for embedding), Phase 3 (harmonic context for rhythm generation), Phase 6 (progression generation in pipeline), Phase 8 (harmonic creativity dial)

---

## SDK Integration Points

| SDK Feature | Phase 1 Usage |
|---|---|
| `defineTool()` | Register `analyze_harmony`, `generate_progression`, `transpose_progression`, `suggest_substitution`, `explain_theory` |
| `customAgents` | Define `harmony` agent with specialized prompt + tool subset |
| `skillDirectories` | `skills/harmony/` with `SKILL.md`, theory reference, genre-dna.json, voicing-rules.md |
| `systemMessage` (agent-level) | Harmony agent prompt: grounding in the 47 real progressions, theory expertise |
| `hooks.onPostToolUse` | Update SongState.progression when generate/modify tools are called |

---

## Task Breakdown

### Task 1.1 — Roman Numeral Analyzer

**Description**: Given a `RawProgression` (C1 contract), compute Roman numeral analysis for each chord relative to the stated key center. This is the foundation of all harmonic reasoning.

**Input**: `RawProgression` (from Phase 0 parser)

**Output**: `string[]` — Roman numerals for each chord (e.g., `["i", "i7/♭VII", "V/♯II", "V7/♯VII"]`)

**Implementation Hints**:
- Map chord names to pitch classes using standard chord symbol parsing
- Root note detection: extract root from chord name (e.g., "Em7/D" → root E, bass D)
- Scale degree calculation: interval from key root to chord root, adjusted for mode
- Chord quality mapping:
  - Major triad → uppercase Roman: I, IV, V
  - Minor triad → lowercase: i, iv, v
  - Dominant 7th → V7, secondary dominants → V7/vi
  - Extensions: maj7, m7, add9, 9, 11, 13
  - Inversions: /bass-note → /scale-degree
- Handle borrowed chords (e.g., ♭VII in a major key → borrowed from parallel minor)
- Handle modal mixture: flag chords that don't belong to the stated scale
- Edge cases from real data:
  - "B/F#" in key of E → V/♯II (this is an enharmonic pun, may also be just V with ♯II bass)
  - "F#7/F" — enharmonic spelling, the "F" is likely E♯
  - Neo Soul 1 has mixture of major and minor chords in B major → modal interchange

**Testing**: Validate against all 47 progressions. Cross-reference with manually verified Roman numerals for Godly, Neo Soul 1, Classic House, Trap 1. Verify secondary dominant detection: Godly's D7/F# and A7/C# should be flagged as V/V and V/vi or similar.

**Complexity**: L

---

### Task 1.2 — Voice Leading Analyzer

**Description**: Compute voice leading metrics between consecutive chords: total semitone movement, common tone retention, parallel motion, and voice crossing detection.

**Input**: `RawChord[]` (sequential chords from a progression)

**Output**:
```typescript
interface VoiceLeadingAnalysis {
  transitions: VoiceLeadingTransition[];
  averageMovement: number;      // avg semitone distance per transition
  smoothness: number;           // 0-1 (inverse of avg movement, normalized)
  parallelMotionCount: number;  // instances of parallel fifths/octaves
}

interface VoiceLeadingTransition {
  fromChord: string;
  toChord: string;
  totalSemitoneMovement: number;
  commonToneCount: number;
  voiceCrossings: number;
  parallelFifths: boolean;
  parallelOctaves: boolean;
  motionTypes: ("oblique" | "similar" | "contrary" | "parallel")[];
}
```

**Implementation Hints**:
- MIDI note arrays have variable length (4-9 notes observed in real data)
- Voice matching heuristic: match voices by proximity (nearest-note assignment), not by array index
- Algorithm: For each pair of consecutive chords:
  1. Sort both note arrays
  2. If lengths differ, the extra voice(s) are "entering" or "leaving" — handle separately
  3. Use minimum-cost matching (Hungarian algorithm) for optimal voice assignment
  4. Compute per-voice semitone movement
  5. Check for parallel perfect intervals between any voice pair
- Common tone: notes present in both chords (MIDI note equality)
- Neo Soul 1 analysis: bass descends chromatically 45→44→43→42 (4 semitones over 4 chords) — the analyzer should flag this pattern as "chromatic bass descent"

**Testing**: Verify against Godly: Em→Em7/D should show 2 semitone movement (E4→D4 in bass). Neo Soul 1 first 4 chords should show chromatic descent in bass voice. Verify no false positive parallel fifths in professionally authored progressions.

**Complexity**: M

---

### Task 1.3 — Tension Function Implementation

**Description**: Implement the tension formula from the blueprint:
$$T_{chord} = w_r \cdot R + w_s \cdot (1-S) + w_d \cdot D + w_c \cdot C$$

**Input**: A chord (MIDI notes), key context, previous chord (for contextual surprise)

**Output**: `number` (0-1 tension value) + component breakdown

**Implementation Hints**:
- **Roughness (R)**: Compute from interval vector. Intervals ranked by roughness:
  - Minor 2nd / major 7th: 1.0
  - Tritone: 0.8
  - Major 2nd / minor 7th: 0.5
  - Minor 3rd / major 6th: 0.2
  - Major 3rd / minor 6th: 0.15
  - Perfect 4th/5th: 0.05
  - Unison/octave: 0.0
  - Normalize: sum of interval roughness / max possible for that cardinality
- **Stability (S)**: Use Krumhansl-Kessler key profiles. Compute correlation between chord pitch classes and profile for the stated key. Higher correlation = higher stability.
  - Major profile: [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
  - Minor profile: [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
- **Density (D)**: `(chord.length - 3) / 6` — normalized, where triads=0, 9-note voicing=1
- **Contextual surprise (C)**: Cosine distance between this chord's pitch class vector and the previous chord's. First chord → C=0.
- **Weights** (genre-dependent defaults):
  - Classical/Jazz: w_r=0.3, w_s=0.3, w_d=0.1, w_c=0.3
  - Pop/House: w_r=0.2, w_s=0.4, w_d=0.1, w_c=0.3
  - Neo Soul: w_r=0.25, w_s=0.25, w_d=0.2, w_c=0.3

**Testing**: Reproduce the blueprint's Godly analysis table. Em should have T≈0.073, Em7/D≈0.153, B/F#≈0.367. Verify tension increases across the progression's "pull" section. Test with simple progressions (I-IV-V-I should have known tension profile).

**Complexity**: L

---

### Task 1.4 — Enriched Progression Generator

**Description**: Combine Tasks 1.1-1.3 into the full `EnrichedProgression` (C1 contract extension). This replaces the basic `read_progression` tool from Phase 0 with a deeply analyzed version.

**Input**: `RawProgression`

**Output**: `EnrichedProgression` (Contract C1, full analysis fields populated)

**Implementation Hints**:
- Orchestrate: parse → Roman numerals → voice leading → tension → genre association
- Genre association algorithm:
  1. Extract features: chord complexity (avg extensions), chromaticism (non-diatonic chords / total), voicing spread (avg note range), harmonic rhythm (implicit from chord count)
  2. Compare feature vector against Genre DNA vectors (C5 contract)
  3. Top-3 genres by cosine similarity
- Complexity score: weighted combination of extension depth, non-diatonic degree count, modulation count
- Chromaticism score: ratio of chromatic (non-diatonic) pitch classes used
- Cache enriched results keyed by file path + content hash

**Testing**: Enrich all 47 progressions. Verify genre associations make sense: Godly → "Gospel", Neo Soul 1 → "Neo Soul", Classic House → "House". Verify no crashes on edge cases.

**Complexity**: M

---

### Task 1.5 — Progression Generation Engine

**Description**: Generate new `.progression` files given constraints: genre, mood, key, complexity, chord count. This is the core creative tool of the Harmonic Brain.

**Input**:
```typescript
interface ProgressionGenerationRequest {
  genre: string;                    // "neo_soul", "trap", "house"
  key?: string;                     // "Eb minor" — generated if omitted
  chordCount?: number;              // default: 8
  complexity?: number;              // 0-1 dial
  mood?: string;                    // "dark", "uplifting", "bittersweet"
  constraints?: {
    mustInclude?: string[];         // chord symbols that must appear
    mustAvoid?: string[];           // chords to avoid
    bassMotion?: "chromatic_descent" | "fifths" | "stepwise" | "pedal" | "free";
    maxTension?: number;            // cap on tension values
    minResolution?: boolean;        // must end on tonic?
  };
}
```

**Output**: `RawProgression` (ready to write as `.progression` file) + `EnrichedProgression` (analysis of what was generated)

**Implementation Hints**:
- **This is NOT a generative AI model.** The LLM generates the progression with its own knowledge, but the tool:
  1. Validates the LLM's output against music theory rules
  2. Computes and returns the enrichment analysis
  3. Enforces constraints (tension limits, required chords, bass motion)
  4. Generates proper MIDI note voicings from chord symbols
- Voicing engine:
  - Input: chord symbol (e.g., "Ebm9") + voice leading context (previous chord)
  - Output: MIDI note array
  - Constraints: register range, minimum voice spacing, maximum movement from previous chord
  - Algorithm: enumerate candidate voicings → score by voice leading smoothness → select best
- The tool provides the LLM with genre DNA constraints and corpus examples, then validates and voices the result
- Output format must match `.progression` JSON schema exactly (validated by Zod)

**Testing**: Generate progressions for each genre. Validate: output parses as valid .progression. Enrichment analysis matches expected genre DNA. Voice leading smoothness ≥ 0.6. No parallel fifths. Test constraint enforcement: "must include Dm7" → verify presence.

**Complexity**: XL

---

### Task 1.6 — Chord Symbol Parser

**Description**: Parse arbitrary chord symbols (e.g., "Ebm9", "F#7/D#", "Cmaj7♯11") into structured representations with root, quality, extensions, and bass note.

**Input**: `string` (chord symbol)

**Output**:
```typescript
interface ParsedChordSymbol {
  root: string;           // "Eb"
  quality: ChordQuality;  // "minor"
  extensions: number[];   // [9] for "m9"
  alterations: string[];  // ["♯11"] for "maj7♯11"
  bassNote?: string;      // "D#" for slash chords
  pitchClasses: number[]; // [3, 6, 10, 1] for Ebm9 (pitch classes 0-11)
}

type ChordQuality = "major" | "minor" | "diminished" | "augmented" |
                    "dominant" | "half_diminished" | "sus2" | "sus4" | "power";
```

**Implementation Hints**:
- This is a parsing-heavy task. Chord symbol notation is notoriously inconsistent:
  - "m" vs "min" vs "-" for minor
  - "Δ" vs "maj" vs "M" for major 7th
  - "°" vs "dim" for diminished
  - "ø" vs "m7♭5" for half-diminished
  - "add9" vs "9" (add9 = no 7th; 9 = includes 7th)
- Use a recursive descent parser or regex-based state machine
- Test against all chord names in the 47 progression files (harvest unique chord names first)
- Edge cases from real data: "B/F#" (simple slash chord), "A7/C#" (dominant with 3rd in bass), "Bmaj9/F#" (complex slash)
- This parser is a critical dependency for Tasks 1.1, 1.5, and Phase 3

**Testing**: Parse every unique chord name across all 47 progressions (extract programmatically). Zero failures. Verify pitch class output for known chords: "Cmaj7" → [0,4,7,11], "Em" → [4,7,11... wait, 0,4,7 in E base → [4,7,11] for E,G,B]. Extensive unit test suite.

**Complexity**: M

---

### Task 1.7 — Transposition Tool

**Description**: Transpose an entire progression to a new key, maintaining voicing character and voice leading quality.

**Input**: `EnrichedProgression` + `targetKey: string` (e.g., "Ab minor")

**Output**: New `RawProgression` in the target key + `EnrichedProgression` of result

**Implementation Hints**:
- Simple case: uniform transposition (all notes += N semitones)
- Complex case: modal transposition (e.g., Dorian to Mixolydian in same key center — changes quality of some chords)
- The tool must update: chord names, MIDI notes, rootNote, scale
- Re-voice if transposition moves voicing out of optimal register (C3-C5):
  - If lowest note < C2 after transposition, octave-shift entire voicing up
  - If highest note > C6, shift down
- Preserve relative voicing structure as much as possible

**Testing**: Transpose Godly from E minor to A minor (+5 semitones). Verify all notes shifted by +5. Verify chord names correctly respelled (Em→Am, B/F#→E/B). Round-trip test: transpose up 7, then down 7, verify identity.

**Complexity**: M

---

### Task 1.8 — Chord Substitution Suggester

**Description**: Given a chord in context, suggest substitutions that maintain harmonic function but alter color/tension.

**Input**: A chord index within an `EnrichedProgression` + substitution type preference

**Output**:
```typescript
interface SubstitutionSuggestion {
  original: string;           // "Dm7"
  substitution: string;       // "D♭maj7"
  type: SubstitutionType;
  tensionDelta: number;       // how much tension changes
  reasoning: string;          // "Tritone substitution of G7→D♭maj7 preserves guide tones E and B♭"
  voicing: number[];          // MIDI notes for the substitution in context
}

type SubstitutionType =
  | "tritone_sub"             // ♭II7 for V7
  | "relative_major_minor"   // vi for I, iii for V
  | "modal_interchange"      // ♭VII from parallel minor
  | "secondary_dominant"      // V/V, V/vi, etc.
  | "sus_resolution"          // Vsus4 → V
  | "chromatic_mediant"       // ♭III, ♯III, etc.
  | "upper_structure"         // add extensions (7→9→11→13)
  | "simplification"          // reduce extensions
  | "reharmonization";       // complete function change
```

**Implementation Hints**:
- Substitution rules are well-defined in jazz theory
- For each rule type, generate candidate then score by:
  1. Voice leading smoothness to surrounding chords
  2. Tension delta (user may want more or less tension)
  3. Genre appropriateness (tritone subs work in jazz/neo-soul, less so in pop)
- Limit to 3-5 suggestions, ranked by relevance
- The LLM can elaborate on the reasoning; the tool provides the structured candidates

**Testing**: For a ii-V-I in C (Dm7-G7-Cmaj7), verify tritone sub suggests D♭7 for G7. Verify modal interchange suggests B♭maj7 as ♭VII. Check that suggestions maintain voice leading smoothness ≥ 0.5.

**Complexity**: L

---

### Task 1.9 — Genre DNA Vector System

**Description**: Implement the genre DNA vectors (C5 contract) and the fusion interpolation algorithm. Provide tools for genre lookup, comparison, and blending.

**Input**: Genre name(s) + optional blend weights

**Output**: `GenreDNAVector` (single or interpolated)

**Implementation Hints**:
- Initial genre set (from blueprint + real corpus analysis):
  ```
  neo_soul, gospel, jazz, house, deep_house, tech_house,
  trap, rnb, pop, soul, hip_hop, boom_bap,
  dubstep, edm, dance, chill_out, ambient,
  classic_rock, funk, blues, afrobeat, reggae,
  classical, lo_fi, synthwave, uk_garage
  ```
- Each genre has a `GenreDNAVector` (10 dimensions)
- Derive initial values from analyzing real corpus:
  - Gospel progressions → compute actual complexity, chromaticism, voicing spread
  - House progressions → same
  - Use as ground truth, extrapolate remaining genres from music theory knowledge
- Fusion: `blend(genres: {name: string, weight: number}[]): GenreDNAVector`
  - Weighted average of each dimension
  - Special handling for `tempoRange`: intersection of ranges if overlapping, union if not
- Store in `data/genre-dna.json` as a reference file and in `skills/harmony/genre-dna.json` as skill knowledge

**Testing**: Verify corpus-derived values: Gospel progressions have complexity > 0.8. House progressions have swing < 0.2. Blend "neo_soul (0.7) + house (0.3)" should yield complexity ~0.68, swing ~0.45. Verify all 25+ genres have valid vectors.

**Complexity**: M

---

### Task 1.10 — Harmony Skill Directory & Agent Definition

**Description**: Create the `skills/harmony/` directory with SKILL.md and reference documents. Define the Harmony `customAgent` configuration.

**Input**: All outputs from Tasks 1.1-1.9

**Output**:
- `skills/harmony/SKILL.md` — skill description for SDK auto-discovery
- `skills/harmony/theory-reference.md` — condensed music theory reference (scales, modes, chord construction, cadences)
- `skills/harmony/voicing-rules.md` — voicing constraint rules by genre
- `skills/harmony/genre-dna.json` — genre DNA vectors
- Harmony agent config object (for `customAgents` array)

**Implementation Hints**:
- `SKILL.md` format (following SDK conventions):
  ```markdown
  # Harmony Skill
  ## Description
  Provides deep music theory analysis, chord progression generation,
  and harmonic reasoning capabilities for MUSE.
  ## Capabilities
  - Roman numeral analysis of any chord progression
  - Tension/resolution scoring using Krumhansl profiles
  - Voice leading quality assessment
  - ...
  ```
- Theory reference should be concise (~2000 tokens) — the LLM already knows theory, this grounds it in MUSE's specific vocabulary and computing conventions
- Harmony agent configuration:
  ```typescript
  {
    name: "harmony",
    displayName: "Harmony Agent",
    description: "Chord progression specialist: analyzes, generates, transforms, and explains harmonic content. Routes here for questions about chords, keys, scales, progressions, music theory.",
    prompt: buildHarmonyAgentPrompt(),  // includes theory reference + corpus examples
    tools: ["read_progression", "analyze_harmony", "generate_progression",
            "transpose_progression", "suggest_substitution", "explain_theory",
            "get_genre_dna", "blend_genres"],
    infer: true
  }
  ```

**Testing**: Verify SKILL.md is valid markdown. Verify agent config has all required fields. Integration test: send "What key is the Godly progression in?" → verify routes to harmony agent → calls read_progression → returns analysis.

**Complexity**: S

---

## Modular Boundaries

| Can develop independently | Notes |
|---|---|
| Task 1.1 (Roman numerals) + 1.6 (chord symbol parser) | Fundamental, no deps on each other but 1.1 uses 1.6 |
| Task 1.2 (Voice leading) | Independent algorithm |
| Task 1.3 (Tension function) | Independent, needs pitch class math only |
| Task 1.9 (Genre DNA) | Data-centric, independent of analysis code |
| Task 1.7 (Transposition) | Needs 1.6 for chord name regeneration |
| Task 1.8 (Substitution) | Needs 1.3 + 1.6 + 1.2 |

**Critical path**: 1.6 → 1.1 → 1.4 → 1.5 (chord parser → Roman numerals → enrichment → generation)

**Parallelizable**: 1.2, 1.3, 1.6, 1.9 can all start simultaneously

---

## Cross-Phase Exports

| Export | Consumer |
|---|---|
| `EnrichedProgression` (full analysis) | Phase 2 (embedding descriptions), Phase 6 (pipeline) |
| `tensionFunction(chord, key, prev)` | Phase 3 (harmonic-rhythmic interaction), Phase 8 (creative dial) |
| `voiceLeadingAnalyzer` | Phase 3 (melody constraint), Phase 8 |
| `GenreDNAVector` and `GENRE_DNA` | Phase 3, 4, 6, 8, 9 |
| `chordSymbolParser` | Phase 3 (melody note selection), Phase 5 (MIDI voicing) |
| `generateProgression` tool | Phase 6 (pipeline), Phase 8 (creative mode) |
| `transposeProgression` tool | Phase 6 |
| Harmony agent config | Phase 6 (multi-agent orchestration) |

---

## Risk Flags

| Risk | Severity | Description |
|---|---|---|
| Chord symbol ambiguity | High | Real-world chord naming is inconsistent. "Badd9/F#" — is the root B major or minor? Context needed. The parser must handle ALL 47 progressions' chord names without failure. |
| Enharmonic spelling | Medium | "F#7/F" — the "F" is likely E♯ enharmonically. The parser must normalize enharmonics. |
| Key detection confidence | Medium | Some progressions are ambiguous (Classic House could be C major or A minor). Need confidence score. |
| Tension formula calibration | Medium | The weight values from the blueprint are estimates. Need empirical tuning against human judgment of "tension" in the real progressions. |
| Voicing engine combinatorial explosion | High | For 9-note chords (Neo Soul 1), the voicing search space is astronomical. Must prune aggressively by register constraints. |
