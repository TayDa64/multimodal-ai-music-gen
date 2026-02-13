# Phase 8 — Creative Frontier

## Phase Overview

**Goal**: Inject controlled unpredictability and creative risk into the system. Two independent creativity dials (harmonic + rhythmic) let the user tune how adventurous the AI is. A multi-critic system with 4 axes provides quality gates that prevent creativity from producing garbage. "Happy accident" mechanisms introduce musically valid surprises.

**Dependencies**: Phase 1 (harmonic analysis, substitution, tension), Phase 3 (rhythm generation, humanization), Phase 4 (sound design), Phase 6 (pipeline orchestrator)

**Exports consumed by**: Phase 9 (personalization calibrates creativity levels), Phase 10 (live creativity injection)

---

## SDK Integration Points

| SDK Feature | Phase 8 Usage |
|---|---|
| `defineTool()` | `set_creativity`, `judge_output`, `generate_variation`, `explain_surprise` |
| `hooks.onPreToolUse` | Quality gate — critic evaluates tool output before delivery |
| `hooks.onPostToolUse` | Log creativity-relevant metrics for tuning |
| `customAgents` | Not a separate agent — creativity is a cross-cutting concern woven into existing agents |
| `ask_user` | "This progression has a Lydian b7 chord — it's unusual. Want to keep it or try something safer?" |

---

## Task Breakdown

### Task 8.1 — Creativity Dial System

**Description**: Implement two independent dials (0.0–1.0) that control harmonic and rhythmic adventurousness.

**Input**: User preference (explicit set or inferred)

**Output**: `CreativitySettings` consumed by all generators
```typescript
interface CreativitySettings {
  harmonic: number;    // 0.0 = strictly diatonic, 1.0 = chromatic adventures
  rhythmic: number;    // 0.0 = straight quantized, 1.0 = polyrhythmic chaos
  coupled: boolean;    // if true, both dials move together
  overrides: {
    allowModalInterchange: boolean;
    allowTritoneSubstitution: boolean;
    allowPolyrhythm: boolean;
    allowOddTimeSignatures: boolean;
    allowMicrotonalHints: boolean;
  };
}
```

**Implementation Hints**:
- Presets:
  - `{ harmonic: 0.2, rhythmic: 0.1 }` — "Pop safe"
  - `{ harmonic: 0.5, rhythmic: 0.4 }` — "Genre-standard"
  - `{ harmonic: 0.7, rhythmic: 0.6 }` — "Neo-soul adventurous"
  - `{ harmonic: 0.9, rhythmic: 0.8 }` — "Jazz fusion experimental"
  - `{ harmonic: 1.0, rhythmic: 1.0 }` — "Free jazz / avant-garde"
- Effect on generators:
  - **Harmonic 0.0-0.3**: Only diatonic chords, no extensions beyond 7ths
  - **Harmonic 0.3-0.6**: Add 9ths, 11ths, modal interchange, secondary dominants
  - **Harmonic 0.6-0.8**: Tritone subs, chromatic mediants, borrowed chords
  - **Harmonic 0.8-1.0**: Symmetrical scales, polytonality, tone clusters
  - **Rhythmic 0.0-0.3**: Straight 4/4, on-the-grid quantization
  - **Rhythmic 0.3-0.6**: Swing, ghost notes, syncopation, dotted rhythms
  - **Rhythmic 0.6-0.8**: Cross-rhythms, metric modulation, tuplets
  - **Rhythmic 0.8-1.0**: Polymetric superposition, odd time signatures, isorhythms
- Store as part of SongState so it persists

**Testing**: Set harmonic=0.1 → verify progression generator only outputs diatonic chords. Set rhythmic=0.9 → verify drum generator includes odd groupings. Verify overrides correctly unlock/lock specific techniques.

**Complexity**: M

---

### Task 8.2 — Multi-Critic Evaluation System

**Description**: Implement a 4-axis quality evaluation system that scores generated content and enforces minimum quality floors.

**Input**: Any generated musical content (progression, rhythm, melody, mix suggestion)

**Output**: `CriticReport` (Contract C8)
```typescript
interface CriticReport {
  scores: {
    harmony: number;      // 0.0 - 1.0
    rhythm: number;       // 0.0 - 1.0
    arrangement: number;  // 0.0 - 1.0
    vibe: number;         // 0.0 - 1.0
  };
  overall: number;        // weighted average
  pass: boolean;          // overall >= 0.7 AND all axes >= 0.5
  flags: CriticFlag[];
  suggestions: string[];  // actionable improvement hints
}

interface CriticFlag {
  axis: "harmony" | "rhythm" | "arrangement" | "vibe";
  severity: "warning" | "fail";
  code: string;           // "PARALLEL_FIFTHS", "STATIC_RHYTHM", etc.
  description: string;
}
```

**Implementation Hints**:
- **Harmony critic (rule-based)**:
  - Voice leading violations → score penalty (parallel fifths -0.15, octaves -0.10)
  - Tension curve check: does T(t) follow a reasonable arc? (Schenkerian analysis lite)
  - Resolution check: dominant → tonic resolution present?
  - Scoring: start at 1.0, subtract penalties, clamp to 0.0
- **Rhythm critic (pattern analysis)**:
  - Variety score: entropy of note durations (all 16ths → low score)
  - Groove alignment: how well does the pattern align with genre's typical pocket
  - Density distribution: not too sparse, not too dense for the genre
  - Humanization quality: velocity spread, timing variation exist but not excessive
- **Arrangement critic (structure analysis)**:
  - Instrument role check: bass below 300Hz okay? Lead in audible range?
  - Frequency collision estimate (from Phase 4): overlapping frequency ranges → penalty
  - Dynamic arc: does the arrangement have contrast between sections?
  - Track count appropriateness for genre (country: 4-6, EDM: 8-12, orchestral: 15+)
- **Vibe critic (cohesion check)**:
  - Genre DNA consistency: all elements within acceptable distance of target genre vector
  - Tempo/key/scale cohesion: does everything align?
  - Energy function curve: does it tell a story? (flat energy curve → vibe penalty)
  - "It feels right" heuristic: Combination of above metrics into gestalt score
- Quality gates:
  - Floor: no axis below 0.5
  - Pass: overall ≥ 0.7
  - If fail, system regenerates (max 3 attempts) before presenting with warning

**Testing**: Feed deliberately bad progression (parallel 5ths, no resolution) → harmony score < 0.5. Feed good progression → all axes ≥ 0.7. Verify floor/pass logic.

**Complexity**: XL

---

### Task 8.3 — Quality Gate Hook

**Description**: Wire the multi-critic into pipeline execution via SDK hooks so every generated artifact passes quality checks.

**Input**: `onPreToolUse` / `onPostToolUse` hook data

**Output**: Approval/rejection of tool output

**Implementation Hints**:
- Use `onPostToolUse` hook:
  ```
  When tool in [generate_progression, generate_drums, generate_bassline, generate_melody]:
    1. Parse tool output
    2. Run through critic (Task 8.2)
    3. If pass → continue normally
    4. If fail AND attempts < 3 → modify parameters and re-invoke tool
    5. If fail AND attempts ≥ 3 → present output with warning: "This scored 0.58 — below target. Issues: [list]. Keep it anyway?"
  ```
- Track attempt count per generation session (not globally)
- Re-generation strategy:
  - Attempt 2: back off creativity by 0.15 on the failing axis
  - Attempt 3: back off by 0.30
  - Still fails: present to user with full critic report
- Performance: critic evaluation should complete in <100ms (all rule-based, no LLM calls)

**Testing**: Generate with creativity=1.0 → verify critic catches low-scoring output → verify re-generation attempt with lower creativity. Verify max 3 attempts before fallback.

**Complexity**: L

---

### Task 8.4 — Happy Accident Generator

**Description**: Introduce controlled surprises that produce musically interesting results the system wouldn't normally generate.

**Input**: `CreativitySettings`, current musical context

**Output**: Surprising but valid musical ideas

**Implementation Hints**:
- **5 Happy Accident Types** (from blueprint):
  1. **Chromatic passing chord**: Insert a chromatic approach chord (1 semitone above or below the target) between two chords. Probability: harmonic_creativity × 0.15
  2. **Ghost note burst**: Insert 3-5 ghost notes (velocity 15-30) before a strong beat in the drum pattern. Probability: rhythmic_creativity × 0.20
  3. **Tritone substitution**: Replace a V chord with bII7. Probability: harmonic_creativity × 0.10 (only when creativity > 0.5)
  4. **Metric displacement**: Shift an entire melody phrase by an eighth note earlier or later. Probability: rhythmic_creativity × 0.12
  5. **Unexpected instrument swap**: Suggest a non-standard instrument for a standard role (e.g., marimba for bass, reversed pad for lead). Probability: (harmonic + rhythmic) / 2 × 0.08
- Each accident type has:
  - Trigger probability (scaled by creativity)
  - Validation rule (must still pass critic with floor 0.5)
  - Explanation generator (so user understands WHY it happened)
- All accidents are tagged in output so user can undo specifically:
  ```
  { type: "happy_accident", accidentType: "tritone_substitution", 
    original: "G7", replacement: "Db7", reason: "Creates chromatic voice leading to Cmaj7" }
  ```

**Testing**: Set creativity=0.0 → verify zero accidents occur. Set creativity=1.0 → verify some accidents triggered across 10 generations. Verify each accident passes floor score.

**Complexity**: L

---

### Task 8.5 — Genre Bending Engine

**Description**: Deliberately blend elements from different genres to create fusion outputs — not by accident, but by understanding genre DNA distance and complementary characteristics.

**Input**: Two or more genre DNA vectors (Contract C5) + blend ratio

**Output**: Fusion genre DNA + adapted parameters

**Implementation Hints**:
- Genre distance matrix:
  - Close genres (jazz ↔ bossa nova, hip-hop ↔ trap): subtle blending
  - Medium genres (rock ↔ electronic, R&B ↔ jazz): interesting territory
  - Far genres (country ↔ dubstep, classical ↔ trap): extreme bending
- Blend algorithm:
  - Interpolate genre DNA vectors: `fusionDNA = lerp(genreA, genreB, ratio)`
  - But NOT naive interpolation — some parameters snap rather than blend:
    - Tempo: weighted average (valid)
    - Key/scale: pick one (you can't "average" two keys)
    - Time signature: pick one or design a polymetric scheme
    - Instruments: union of both sets
    - Rhythmic patterns: cross-pollinate (take kick from genre A, hi-hat pattern from genre B)
- Named fusions for common requests:
  - "Lo-fi jazz hop" → { jazz: 0.6, hip-hop: 0.4 }
  - "Electronic soul" → { R&B: 0.5, electronic: 0.5 }
  - "Trap classical" → { classical: 0.4, trap: 0.6 }
- Creativity dial naturally governs fusion distance tolerance:
  - Low creativity → only blend close genres
  - High creativity → any combination allowed

**Testing**: Blend jazz + hip-hop → verify fusion has swing feel + boom-bap rhythm. Blend country + dubstep at low creativity → verify rejection or warning. Verify fusion DNA is valid (all dimensions in range).

**Complexity**: L

---

### Task 8.6 — Surprise Mode ("Go Wild")

**Description**: A special mode where the system deliberately maximizes creative output — both creativity dials set to maximum, happy accidents enabled at full probability, and genre blending encouraged.

**Input**: User trigger ("Go wild", "Surprise me", "Make something crazy")

**Output**: Maximally creative output with full provenance tracking

**Implementation Hints**:
- Activation:
  - Explicit: User says "surprise me" or "go wild"
  - Implicit: User has been generating conservative outputs for 5+ turns (suggest break-out)
- Settings override:
  - Creativity dials → 1.0 / 1.0
  - Happy accident probability multiplier → 2.0
  - Genre: randomly select a genre blend with distance > 0.5
  - Critic floor: relaxed to 0.4 (allow stranger results)
  - Attempt limit: 5 (more retries to find something interesting)
- Provenance:
  - Every decision tagged: "I used a Lydian dominant scale because it creates an otherworldly feeling"
  - User can cherry-pick individual elements: "I like the chord progression but swap the drums back to standard"
- Safety: always present output with full explanation, never commit to SongState without user approval

**Testing**: Trigger "go wild" → verify creativity settings maxed. Verify output has at least 1 happy accident. Verify critic floor is relaxed. Verify rollback possible.

**Complexity**: M

---

### Task 8.7 — Explanation & Education System

**Description**: When the system makes creative choices, explain them in music-theory terms so the user learns. This turns creative risks into teaching moments.

**Input**: Any creative decision (chord substitution, rhythmic variation, etc.)

**Output**: Human-readable explanation with theory context

**Implementation Hints**:
- Explanation templates:
  - Chord substitution: "I replaced G7 with Db7 (tritone substitution). This works because both chords share the same tritone interval (B↔F), creating smooth voice leading to the C major target."
  - Rhythmic displacement: "The melody starts on the 'and' of beat 2 instead of beat 1 — this creates anticipation and forward momentum. Common in R&B and neo-soul."
  - Modal interchange: "I borrowed the Ebmaj7 from C minor (the parallel minor key). This adds a bittersweet color — it's a classic Beatles technique."
- Explanation depth levels:
  - **Brief**: "Tritone sub of G7 → smooth voice leading"
  - **Standard**: "Replaced G7 with Db7 (tritone substitution). Both share the B-F tritone, so the resolution to C is equally smooth."
  - **Deep**: Full theory breakdown with note names, interval analysis, historical context, famous songs using this technique
- Depth controlled by user preference (default: standard)
- Include "Famous example" where possible:
  - Tritone sub: "Hear it in 'Girl from Ipanema' at 'but she doesn't see...'"
  - Chromatic mediant: "Like the Star Wars key shifts"
  - Ghost notes: "Listen to any Questlove groove"

**Testing**: Generate tritone sub explanation → verify it mentions shared tritone interval. Generate at all three depth levels → verify increasing detail. Verify famous example is musically accurate.

**Complexity**: M

---

### Task 8.8 — Variation Generator

**Description**: Given an existing musical idea, generate N variations with controlled similarity distance.

**Input**: Source idea (progression, rhythm, melody) + number of variations + similarity target (0.0 = completely different, 1.0 = nearly identical)

**Output**: Array of variations with similarity scores

**Implementation Hints**:
- Variation techniques by content type:
  - **Progressions**: chord substitution, inversion changes, voicing modifications, add/remove extensions, reharmonization
  - **Rhythms**: displacement, subdivision change, accent shift, fill injection, density adjustment
  - **Melodies**: transposition, retrograde, inversion, augmentation/diminution, ornamental variations
- Similarity measurement:
  - Progression: count of shared chord roots + quality matches
  - Rhythm: grid correlation (compare quantized patterns as binary vectors)
  - Melody: contour correlation (compare direction sequences)
- Algorithm:
  1. Start with source material
  2. Apply random selection of applicable techniques
  3. Measure similarity to source
  4. If similarity outside target range, adjust technique intensity
  5. Run through critic (must pass floor)
  6. Repeat for N variations
- Used by Phase 6 (A/B generation) and Phase 8 (surprise mode)

**Testing**: Generate 3 variations of a known progression at similarity=0.8 → verify shared root structure. Generate at similarity=0.2 → verify significant differences. Verify all variations pass critic floor.

**Complexity**: L

---

### Task 8.9 — Creativity Metrics Dashboard

**Description**: Track creativity-related metrics across a session so the user can see how adventurous the system has been.

**Input**: Session-level tool call history + critic reports + accident log

**Output**: Summary statistics
```typescript
interface CreativityMetrics {
  session: {
    totalGenerations: number;
    happyAccidents: number;
    criticPasses: number;
    criticFails: number;
    averageScores: CriticScores;
    creativitySettings: CreativitySettings;
  };
  adventurousnessIndex: number;  // 0.0-1.0, how "out there" the session has been
  genreFidelity: number;         // how close to target genre (1.0 = dead on)
  surpriseRatio: number;         // accidents / total generations
}
```

**Implementation Hints**:
- Collect via `onPostToolUse` hook — log every generation event
- Calculate adventurousness from:
  - Average creativity settings used
  - Genre distance of outputs from target
  - Number of happy accidents that were kept
- Present on request: "How creative have we been?"
- Use to inform Phase 9 personalization (nudge toward more or less creativity based on user history)

**Testing**: Run 10 generations → verify metrics reflect actual creativity settings. Verify adventurousnessIndex correlates with creativity dial positions.

**Complexity**: S

---

## Modular Boundaries

| Can develop independently | Notes |
|---|---|
| Task 8.1 (creativity dials) | Foundation — needs to exist before other tasks |
| Task 8.2 (multi-critic) | Independent from creativity dials, purely evaluation |
| Task 8.4 (happy accidents) | Needs 8.1 for probability scaling |
| Task 8.5 (genre bending) | Needs Phase 1 genre DNA, otherwise independent |
| Task 8.7 (explanation system) | Content-independent, needs only the creative decisions to explain |
| Task 8.8 (variation generator) | Needs Phase 1/3 generators, otherwise independent |

**Critical path**: 8.1 + 8.2 (parallel) → 8.3 (hook wiring) → 8.4 → 8.6

---

## Cross-Phase Exports

| Export | Consumer |
|---|---|
| `CreativitySettings` | Phase 9 (personalization calibrates defaults) |
| `CriticReport` / multi-critic | Phase 6 (pipeline quality gates), Phase 9 (learning from scores) |
| Variation generator | Phase 6 (A/B generation) |
| Explanation system | All agents (any can trigger explanations) |
| Creativity metrics | Phase 9 (preference modeling) |

---

## Risk Flags

| Risk | Severity | Description |
|---|---|---|
| Critic subjectivity | High | Music quality is subjective — rule-based critics may reject things a user loves. Mitigate: critic floor is a minimum, user can always override via "keep it anyway." |
| Creativity spiral | Medium | High creativity + happy accidents can compound into incoherent output. Mitigate: critic quality gate ensures minimum coherence even at creativity=1.0. |
| Explanation accuracy | Medium | Music theory explanations must be factually correct or they damage trust. Mitigate: use structured templates, not free-form LLM generation, for theory facts. |
| Performance at max creativity | Low | More retries needed at high creativity = slower generation. Mitigate: set reasonable attempt limits (3 standard, 5 wild mode). |
