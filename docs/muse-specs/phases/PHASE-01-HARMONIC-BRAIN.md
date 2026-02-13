# Phase 1 — Harmonic Brain

> **Effort**: 7–9 dev-weeks solo | 4–5 weeks with 2 devs  
> **Risk Level**: Medium-High (music theory edge cases)  
> **Prerequisites**: P0-T1 (scaffold), P0-T3 (.progression parser), P0-T5 (SongState), P0-T7 (tool factory)  
> **Outputs Consumed By**: Phase 2 (embeddings need enriched descriptions), Phase 6 (pipeline), Phase 8 (creative frontier)  
> **Reviewers**: GPT-5.2 Codex, Gemini 3 Pro Preview

---

## Phase Overview

Phase 1 builds the complete music theory engine — the "brain" that understands harmony at a conservatory level. It covers pitch/scale/chord type systems, a pre-computed scale/mode library, Roman numeral analysis, voice leading algorithms, chord-to-MIDI conversion with multiple voicing strategies, a hybrid progression generator (rules-based + LLM-guided), a harmonic enrichment pipeline, and the Harmony custom agent.

> **Gemini**: "Your 47 progression files encode real producer knowledge — not abstract music theory, but how actual hit records are voiced."

> **GPT**: "The tension function T = w_r·R + w_s·(1−S) + w_d·D + w_c·C quantifies what a producer feels intuitively."

---

## Architecture Decisions (Phase 1)

| Decision | Choice | Rationale |
|---|---|---|
| Theory representation | Pitch class integers (0–11) | Eliminates enharmonic ambiguity at computation level |
| Scale library | Pre-computed lookup (252 entries) | 21 modes × 12 keys; O(1) lookup, no runtime computation |
| Voice leading | Minimal weighted distance | Balances smoothness, common tones, and rule avoidance |
| Progression gen | Hybrid: rules + LLM re-ranking | Rules provide musical validity; LLM provides creativity and context |
| Tension model | 4-component weighted sum | GPT's formula with genre-dependent weights |

---

## Tasks

### P1-T1: Music Theory Type System
**Complexity**: M  
**Description**: Define the foundational music theory types: Note, PitchClass, Interval, Key, Scale, Mode, Chord, ChordQuality. Handle enharmonic equivalence (C# = Db) at the display layer while using pitch class integers (0–11) internally. This is the type foundation for all harmonic operations.  
**Depends On**: P0-T1  
**SDK Integration**: Types used across all tools; serialized in SongState

**Output Interface**:
```typescript
/** Pitch class: 0=C, 1=C#/Db, ..., 11=B */
type PitchClass = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11;

/** Note with octave */
interface Note {
  /** Pitch class (0-11) */
  pitchClass: PitchClass;
  /** MIDI octave (0-10, middle C = octave 4) */
  octave: number;
  /** MIDI note number (0-127) */
  midiNote: number;
  /** Preferred spelling for display */
  spelling: string;
}

/** Musical interval */
interface Interval {
  /** Semitones (0-12+) */
  semitones: number;
  /** Interval name: "P1", "m2", "M2", "m3", "M3", "P4", "A4/d5", "P5", "m6", "M6", "m7", "M7", "P8" */
  name: string;
  /** Interval quality */
  quality: 'perfect' | 'major' | 'minor' | 'augmented' | 'diminished';
  /** Generic interval number (1-8+) */
  number: number;
}

/** Key center */
interface Key {
  /** Tonic pitch class */
  tonic: PitchClass;
  /** Mode: major or minor (includes modes) */
  mode: Mode;
  /** Display name: "Eb minor", "C major" */
  displayName: string;
  /** Number of sharps (+) or flats (-) in key signature */
  accidentals: number;
}

/** Scale/mode types */
type Mode =
  | 'ionian' | 'dorian' | 'phrygian' | 'lydian'
  | 'mixolydian' | 'aeolian' | 'locrian'
  | 'melodic_minor' | 'dorian_b2' | 'lydian_augmented'
  | 'lydian_dominant' | 'mixolydian_b6' | 'aeolian_b5' | 'altered'
  | 'harmonic_minor' | 'locrian_natural6' | 'ionian_augmented'
  | 'dorian_sharp4' | 'phrygian_dominant' | 'lydian_sharp2' | 'altered_dominant_bb7';

/** Scale: collection of pitch classes */
interface Scale {
  /** Interval pattern in semitones from root */
  intervals: number[];
  /** Pitch classes in the scale (in a given key) */
  pitchClasses: PitchClass[];
  /** Mode identifier */
  mode: Mode;
  /** Parent scale family */
  family: 'major' | 'melodic_minor' | 'harmonic_minor';
  /** Degree number within the parent (1-7) */
  degree: number;
}

/** Chord quality enumeration */
type ChordQuality =
  | 'major' | 'minor' | 'diminished' | 'augmented'
  | 'dominant7' | 'major7' | 'minor7' | 'half_diminished'
  | 'diminished7' | 'augmented7' | 'minor_major7'
  | 'dominant9' | 'major9' | 'minor9'
  | 'dominant11' | 'major11' | 'minor11'
  | 'dominant13' | 'major13' | 'minor13'
  | 'sus2' | 'sus4' | 'add9' | 'add11'
  | '6' | 'minor6' | '6_9';

/** Chord structure */
interface Chord {
  /** Root pitch class */
  root: PitchClass;
  /** Chord quality */
  quality: ChordQuality;
  /** All pitch classes in the chord */
  pitchClasses: PitchClass[];
  /** Bass note (for inversions/slash chords) */
  bass?: PitchClass;
  /** Standard symbol: "Ebm9", "C/G" */
  symbol: string;
  /** Interval vector [ic1, ic2, ic3, ic4, ic5, ic6] */
  intervalVector: [number, number, number, number, number, number];
}
```

**Testing Strategy**:
- Unit: Note C4 → midiNote 60, pitchClass 0
- Unit: Interval from C to G = P5 (7 semitones)
- Unit: All 12 major keys produce correct key signatures
- Unit: Chord "Ebm9" → root=3, quality=minor9, pitchClasses=[3,6,10,1,5]
- Unit: Enharmonic display: key of Gb shows Gb, key of F# shows F#

**Risk**: Low. Well-defined domain. Edge case: double sharps/flats in obscure modes.

---

### P1-T2: Scale & Mode Library
**Complexity**: S  
**Description**: Pre-compute all 252 scale instances (21 modes × 12 keys). Each entry contains the pitch class set, interval pattern, parent scale family, and degree. Stored as a static lookup table for O(1) access.  
**Depends On**: P1-T1  
**SDK Integration**: Accessed by theory tools, loaded into skill files as reference data

**Output Interface**:
```typescript
interface ScaleLibrary {
  /** Get scale by key and mode */
  get(tonic: PitchClass, mode: Mode): Scale;
  /** Get all modes of a key */
  getModes(tonic: PitchClass): Scale[];
  /** Find scales containing a set of pitch classes */
  findContaining(pitchClasses: PitchClass[]): Array<{ scale: Scale; key: Key; coverage: number }>;
  /** Get relative modes (same pitch class set) */
  getRelatives(tonic: PitchClass, mode: Mode): Array<{ key: Key; mode: Mode }>;
  /** Total entries */
  readonly size: 252;
}
```

**Testing Strategy**:
- Unit: Library.size === 252
- Unit: C ionian === [0,2,4,5,7,9,11], A aeolian === [9,11,0,2,4,5,7]
- Unit: C ionian and A aeolian are relatives (same pitch class set)
- Unit: findContaining([0,4,7]) returns C major, F lydian, G mixolydian, etc.
- Exhaustive: Every scale has exactly 7 pitch classes

**Risk**: Low. Static data, fully deterministic.

---

### P1-T3: Roman Numeral Analyzer
**Complexity**: L  
**Description**: Parse Roman numeral notation ("IVmaj7", "viio7/V", "bVI") and map to concrete chords in any key. Also reverse-map: given a chord and key, produce the Roman numeral. Handle secondary dominants (V/V, V/vi), borrowed chords (bVI from parallel minor), Neapolitan (bII), augmented sixths.  
**Depends On**: P1-T1, P1-T2  
**SDK Integration**: Core of `readProgression` enrichment and `generateProgression` tool

**Output Interface**:
```typescript
interface RomanNumeralAnalyzer {
  /** Parse Roman numeral string → chord in context of key */
  parse(romanNumeral: string, key: Key): Chord;
  /** Analyze chord in context of key → Roman numeral */
  analyze(chord: Chord, key: Key): RomanNumeralResult;
  /** Analyze a full sequence with context-aware inference */
  analyzeSequence(chords: Chord[], key: Key): RomanNumeralSequence;
}

interface RomanNumeralResult {
  /** Primary analysis (most likely interpretation) */
  primary: string;
  /** All possible interpretations ranked by likelihood */
  alternatives: Array<{ numeral: string; likelihood: number; explanation: string }>;
  /** Is this diatonic to the key? */
  isDiatonic: boolean;
  /** If non-diatonic, what is it? */
  harmonicFunction?: 'secondary_dominant' | 'borrowed' | 'neapolitan' | 'augmented_sixth' | 'chromatic';
  /** Secondary function target (e.g., for V/vi, target = vi) */
  secondaryTarget?: string;
}

interface RomanNumeralSequence {
  /** Analyzed numerals in order */
  numerals: RomanNumeralResult[];
  /** Detected functional progressions */
  functionalPatterns: Array<{
    name: string;         // "ii-V-I", "circle of fifths descent"
    chordIndices: number[];
    strength: number;     // 0-1
  }>;
  /** Key change suggestions */
  modulationPoints: Array<{
    atIndex: number;
    suggestedNewKey: Key;
    evidence: string;
  }>;
}
```

**Testing Strategy**:
- Unit: parse("IV", C major) → F major
- Unit: parse("viio7/V", C major) → F# diminished 7 (secondary leading tone of G)
- Unit: parse("bVI", C major) → Ab major (borrowed from C minor)
- Unit: analyze(F major, C major) → "IV"
- Unit: Analyze Godly progression in E minor → correct Roman numerals
- Unit: analyzeSequence detects ii-V-I in jazz progressions
- Edge: Handle uppercase/lowercase correctly (I=major, i=minor)

**Risk**: Medium-High. Roman numeral analysis is inherently ambiguous (same chord can be analyzed multiple ways depending on context). Mitigation: return ranked alternatives, use sequence context for disambiguation.

---

### P1-T4: Voice Leading Engine
**Complexity**: L  
**Description**: Compute optimal voice leading between chords. Minimize total voice movement while preserving common tones, avoiding parallel fifths/octaves, and maintaining smooth bass motion. Used by both the progression generator (evaluating smoothness) and the voicing engine (choosing inversions).  
**Depends On**: P1-T1  
**SDK Integration**: Internal engine consumed by enrichment pipeline and voicing tools

**Output Interface**:
```typescript
interface VoiceLeadingEngine {
  /** Compute optimal voice leading from chord A to chord B */
  computeLeading(from: number[], to: Chord, options?: VoiceLeadingOptions): VoiceLeadingResult;
  /** Score the quality of a voice leading */
  score(from: number[], to: number[]): VoiceLeadingScore;
  /** Find the smoothest path through a chord sequence */
  optimizePath(chords: Chord[], startVoicing: number[]): number[][];
}

interface VoiceLeadingOptions {
  /** Voice count (3, 4, 5, or 6) */
  voiceCount: number;
  /** Preserve common tones when possible */
  preserveCommonTones: boolean;
  /** Avoid parallel fifths and octaves */
  avoidParallels: boolean;
  /** Keep bass motion smooth (steps preferred over leaps) */
  smoothBass: boolean;
  /** Maximum semitone leap for any voice */
  maxLeap: number;
  /** Register constraints */
  registerBounds: { low: number; high: number };
}

interface VoiceLeadingResult {
  /** The resulting voicing as MIDI note numbers */
  voicing: number[];
  /** Total semitone distance across all voices */
  totalDistance: number;
  /** Per-voice movements */
  movements: Array<{ from: number; to: number; distance: number; direction: 'up' | 'down' | 'hold' }>;
  /** Common tones retained */
  commonTones: number[];
  /** Voice leading violations (parallel 5ths, etc.) */
  violations: string[];
  /** Overall quality score (0-1) */
  qualityScore: number;
}

interface VoiceLeadingScore {
  /** Total semitone movement (lower = smoother) */
  totalMovement: number;
  /** Common tone count */
  commonTones: number;
  /** Parallel motion violations */
  parallelViolations: number;
  /** Voice crossing count */
  voiceCrossings: number;
  /** Composite quality score (0-1) */
  overall: number;
}
```

**Testing Strategy**:
- Unit: C major → G major with 4 voices: expect common tone G retained, total movement ≤ 5 semitones
- Unit: Parallel fifths detected: C-G → D-A flags violation
- Unit: Voice crossing detected: soprano drops below alto
- Unit: optimizePath for "Godly" Em→Em7/D→B/F#→B7/D#: verify total distance matches expected
- Unit: Verify chromatic bass descent in Neo Soul 1 (45→44→43→42) is optimal by this engine

**Risk**: Medium. Optimal voice leading is NP-hard for arbitrary voice counts. Mitigation: use greedy/beam search with 4-voice constraint (tractable).

---

### P1-T5: Tension Function Calculator
**Complexity**: M  
**Description**: Implement GPT's tension formula: T = w_r·R + w_s·(1−S) + w_d·D + w_c·C. Compute roughness (contextual dissonance), stability (Krumhansl key profile distance), density tension, and contextual surprise. Weights are genre-dependent. Produces the tension arc used for energy function computation.  
**Depends On**: P1-T1, P1-T2 (for key profiles)  
**SDK Integration**: Tension values stored in enriched progressions, exposed via theory tools

**Output Interface**:
```typescript
interface TensionCalculator {
  /** Compute tension for a single chord in context */
  computeTension(chord: Chord, context: TensionContext): TensionResult;
  /** Compute tension arc for a full progression */
  computeArc(chords: Chord[], key: Key, genre?: string): TensionArc;
}

interface TensionContext {
  /** Current key center */
  key: Key;
  /** Previous chord (for contextual surprise) */
  previousChord?: Chord;
  /** Genre for weight selection */
  genre?: string;
}

interface TensionResult {
  /** Overall tension (0-1) */
  total: number;
  /** Component breakdown */
  components: {
    /** Roughness: contextual dissonance, not raw interval (0-1) */
    roughness: number;
    /** Instability: 1 - Krumhansl key profile distance (0-1) */
    instability: number;
    /** Density: note count / register span (0-1) */
    density: number;
    /** Contextual surprise: how unexpected this chord is (0-1) */
    contextualSurprise: number;
  };
  /** Genre-specific weights used */
  weights: { w_r: number; w_s: number; w_d: number; w_c: number };
}

interface TensionArc {
  /** Per-chord tension values */
  values: number[];
  /** Per-transition deltas (values[i+1] - values[i]) */
  deltas: number[];
  /** Average tension */
  average: number;
  /** Maximum tension and its index */
  peak: { value: number; index: number };
  /** Tension trajectory: 'ascending' | 'descending' | 'arc' | 'flat' | 'oscillating' */
  trajectory: string;
}

/** Genre-specific tension weights */
const GENRE_TENSION_WEIGHTS: Record<string, { w_r: number; w_s: number; w_d: number; w_c: number }> = {
  'neo_soul':  { w_r: 0.15, w_s: 0.25, w_d: 0.20, w_c: 0.40 },
  'gospel':    { w_r: 0.20, w_s: 0.30, w_d: 0.15, w_c: 0.35 },
  'jazz':      { w_r: 0.10, w_s: 0.20, w_d: 0.25, w_c: 0.45 },
  'house':     { w_r: 0.30, w_s: 0.35, w_d: 0.25, w_c: 0.10 },
  'trap':      { w_r: 0.25, w_s: 0.40, w_d: 0.20, w_c: 0.15 },
  'default':   { w_r: 0.20, w_s: 0.30, w_d: 0.20, w_c: 0.30 },
};
```

**Testing Strategy**:
- Unit: Godly Em tension ≈ 0.073 (per blueprint calculation)
- Unit: Godly Em7/D tension ≈ 0.153
- Unit: Godly B/F# tension ≈ 0.367
- Unit: Delta Em→Em7/D ≈ +0.080 (gentle lean)
- Unit: Delta Em7/D→B/F# ≈ +0.214 (dramatic pull)
- Unit: Genre weight switch: jazz weights produce different tensions than trap weights for same chord
- Unit: Arc trajectory detection: ascending, descending, oscillating

**Risk**: Medium. Krumhansl key profiles are from cognitive musicology research — need accurate implementation. Mitigation: use published coefficient tables.

---

### P1-T6: Chord-to-MIDI Voicing Engine
**Complexity**: L  
**Description**: Convert abstract chords to concrete MIDI voicings using multiple strategies: close position, open position, drop-2, drop-3, rootless (jazz). Apply register constraints, production awareness (reverb needs open low voicings), and velocity layering.  
**Depends On**: P1-T1, P1-T4 (voice leading)  
**SDK Integration**: Core of `generateMIDI` tool for harmonic content

**Output Interface**:
```typescript
interface VoicingEngine {
  /** Generate a voicing for a chord using specified strategy */
  voice(chord: Chord, strategy: VoicingStrategy, constraints: VoicingConstraints): VoicedChord;
  /** Generate all reasonable voicings and rank by fitness */
  generateCandidates(chord: Chord, constraints: VoicingConstraints): VoicedChord[];
  /** Select best voicing considering context */
  selectBest(chord: Chord, context: VoicingContext): VoicedChord;
}

type VoicingStrategy = 'close' | 'open' | 'drop2' | 'drop3' | 'rootless_a' | 'rootless_b' | 'spread' | 'cluster';

interface VoicingConstraints {
  /** Register bounds */
  register: { low: number; high: number };
  /** Minimum semitones between adjacent voices (for clarity with reverb) */
  minSpacing?: number;
  /** Maximum total span in semitones */
  maxSpan?: number;
  /** Voice count override */
  voiceCount?: number;
  /** Production context: heavy reverb needs open low voicings */
  productionContext?: {
    reverbLevel: 'dry' | 'moderate' | 'heavy';
    bassPresence: boolean;
  };
}

interface VoicingContext {
  /** Previous voicing (for voice leading) */
  previousVoicing?: number[];
  /** Genre (affects default strategy) */
  genre?: string;
  /** Musical role: pad prefers open/spread, lead prefers close */
  role?: TrackRole;
  /** Strategy preference */
  preferredStrategy?: VoicingStrategy;
}

interface VoicedChord {
  /** Chord being voiced */
  chord: Chord;
  /** Strategy used */
  strategy: VoicingStrategy;
  /** MIDI note numbers (sorted low to high) */
  midiNotes: number[];
  /** Per-note velocity (0-127) */
  velocities: number[];
  /** Voice leading score relative to previous chord */
  voiceLeadingScore?: number;
  /** Fitness score considering all constraints (0-1) */
  fitness: number;
}
```

**Testing Strategy**:
- Unit: Cmaj7 close position → [48, 52, 55, 59] (C3-E3-G3-B3)
- Unit: Cmaj7 drop-2 → [48, 55, 59, 64] (C3-G3-B3-E4)
- Unit: Cmaj7 rootless_a → [52, 55, 59, 62] (E3-G3-B3-D4)
- Unit: Heavy reverb constraint → minSpacing ≥ 5 semitones in low register
- Unit: Pad role defaults to open/spread strategy
- Unit: Voice leading from Cmaj7 to Fmaj7 → common tone C retained
- Integration: Reproduce Godly voicings [52,59,64,67] from Em chord with correct strategy

**Risk**: Medium. "Best" voicing is subjective and genre-dependent. Mitigation: always return ranked candidates, let downstream consumer choose.

---

### P1-T7: Progression Generator (Hybrid Rules + LLM)
**Complexity**: XL  
**Description**: Generate chord progressions using a hybrid approach: (1) rules engine enforces functional harmony, tension patterns, and genre templates; (2) LLM provides creative direction, style blending, and natural language interpretation via tool call. The rules engine builds candidate progressions; the LLM re-ranks and selects based on the user's artistic intent.  
**Depends On**: P1-T1, P1-T2, P1-T3, P1-T4, P1-T5, P1-T6  
**SDK Integration**: `defineTool("generateProgression", ...)` — this is one of the most important tools in the platform

**Input Interface**:
```typescript
interface ProgressionGenerationRequest {
  /** Genre or genre blend (e.g., "neo-soul with gospel influences") */
  genre: string;
  /** Mood descriptors */
  mood: string[];
  /** Key center (optional — auto-detect from genre if omitted) */
  key?: Key;
  /** Number of chords */
  chordCount?: number;
  /** Complexity level (0-1) */
  complexity?: number;
  /** Tension arc shape */
  tensionShape?: 'ascending' | 'descending' | 'arc' | 'wave' | 'flat';
  /** Reference progressions to use as inspiration */
  references?: string[];
  /** Constraints: chords to include or exclude */
  constraints?: {
    mustInclude?: string[];     // Roman numerals
    mustExclude?: string[];     // Roman numerals
    startWith?: string;         // Starting chord
    endWith?: string;           // Ending chord/cadence type
  };
  /** Number of candidates to generate */
  candidateCount?: number;
}
```

**Output Interface**:
```typescript
interface ProgressionGenerationResult {
  /** Ranked progression candidates */
  candidates: ProgressionCandidate[];
  /** Selected best candidate */
  selected: ProgressionCandidate;
  /** Generation reasoning */
  reasoning: string;
  /** Genre DNA vector used */
  genreDNA: GenreDNAVector;
}

interface ProgressionCandidate {
  /** Chord sequence */
  chords: VoicedChord[];
  /** Roman numeral analysis */
  romanNumerals: string[];
  /** Tension arc */
  tensionArc: TensionArc;
  /** Voice leading quality score */
  voiceLeadingScore: number;
  /** Genre match score */
  genreMatchScore: number;
  /** Overall fitness (weighted composite) */
  overallScore: number;
  /** Human-readable explanation of why this works */
  explanation: string;
  /** Exportable as .progression JSON */
  asProgressionFile: RawProgressionFile;
}
```

**Testing Strategy**:
- Unit: Generate "jazz" 4-chord progression → contains ii-V-I pattern with >0.7 probability
- Unit: Generate "trap" progression → sparse minor chords, complexity < 0.4
- Unit: All candidates pass quality gate: no axis below 0.5
- Unit: Genre match score for "neo-soul" request → neo_soul association > 0.7
- Unit: Constraints: "must include IV, must end with I" → verified in output
- Integration: Full tool invocation via mock session, natural language → progression → valid .progression JSON
- Regression: 10 fixed seeds produce deterministic outputs for snapshot testing

**Risk**: High. Balancing rules rigidity with LLM creativity is the core challenge. Mitigation: rules provide *candidates*, LLM *selects* — never let LLM override musical validity constraints.

---

### P1-T8: Harmonic Enrichment Pipeline
**Complexity**: M  
**Description**: Takes raw parsed .progression files (from P0-T3) and runs them through the full Phase 1 analysis stack: Roman numeral analysis, tension calculation, voice leading scoring, genre association, and text description generation. Produces the canonical `EnrichedProgression` (Contract C2) consumed by embeddings and all downstream phases.  
**Depends On**: P1-T3, P1-T4, P1-T5, P0-T3  
**SDK Integration**: Produces data for `readProgression` tool and embedding pipeline

**Output Interface**:
```typescript
interface HarmonicEnrichmentPipeline {
  /** Enrich a single parsed progression */
  enrich(raw: RawProgressionFile): EnrichedProgression;
  /** Batch-enrich all 47 progressions */
  enrichAll(progressions: RawProgressionFile[]): EnrichedProgression[];
  /** Generate embedding-ready text description */
  generateDescription(enriched: EnrichedProgression): string;
}
```

**Example Description Output**:
```
Gospel minor key progression in E pentatonic minor. 4 chords with chromatic 
descending bass line (E→D→F#→D#). Heavy use of inversions (Em7/D, B/F#, 
B7/D#). Tension arc: gentle build from 0.07 to 0.37. Voice leading: very 
smooth (avg 2 semitones per transition). Soulful, devotional, emotionally 
intense. Suitable for: Gospel, Neo Soul, R&B ballad.
```

**Testing Strategy**:
- Unit: Enrich all 47 progressions without errors
- Unit: Verify Godly enrichment matches expected Roman numerals and tension values
- Unit: Verify description contains key, scale, tension trajectory, genre associations
- Unit: Description token count < 200 per progression (estimator check)
- Snapshot: Golden-file all 47 enriched outputs and descriptions

**Risk**: Low. Composition of previously tested components.

---

### P1-T9: Harmony Custom Agent Configuration
**Complexity**: S  
**Description**: Configure the `@harmony` custom agent for the Copilot SDK. Define its specialized system prompt (music theory expert persona), tool bindings (readProgression, generateProgression, analyzeProgression, explainTheory), and the `infer` function that routes harmony-related queries to this agent.  
**Depends On**: P0-T9 (session config), P1-T7 (progression generator)  
**SDK Integration**: `customAgents` array entry in CopilotClient config

**Output Interface**:
```typescript
const harmonyAgent: CustomAgentConfig = {
  name: 'harmony',
  displayName: 'Harmony Agent',
  description: 'Music theory expert — chord progressions, key analysis, voice leading, harmonic enrichment',
  prompt: `You are the Harmony Agent of MUSE. You are a conservatory-trained music 
theorist with deep knowledge of:
- Functional harmony (Roman numeral analysis, cadences, modulations)
- Voice leading (Bach chorale rules adapted for modern production)
- Genre-specific harmonic conventions (Neo Soul, Gospel, Jazz, Trap, House)
- Tension/resolution mechanics and energy arcs
- Chord voicing strategies for different production contexts

When analyzing progressions, always provide:
1. Roman numeral analysis with key context
2. Tension arc assessment
3. Voice leading quality evaluation
4. Genre associations with confidence
5. Suggested substitutions or improvements

Use the tools available to you: readProgression, generateProgression, 
analyzeProgression, explainTheory.`,
  tools: ['read-progression', 'generate-progression', 'analyze-progression', 'explain-theory'],
  infer: undefined, // Defined as function at runtime
};

/** Infer function: does this message belong to the harmony agent? */
function harmonyInfer(message: string): boolean {
  const harmonyKeywords = [
    'chord', 'progression', 'key', 'scale', 'harmony', 'harmonic',
    'voice leading', 'tension', 'resolution', 'cadence', 'modulation',
    'roman numeral', 'theory', 'interval', 'voicing', 'transpose',
    'minor', 'major', 'dominant', 'diminished', 'augmented',
    'ii-V-I', 'circle of fifths',
  ];
  const lower = message.toLowerCase();
  return harmonyKeywords.some(kw => lower.includes(kw));
}
```

**Testing Strategy**:
- Unit: `harmonyInfer("What key is this progression in?")` → true
- Unit: `harmonyInfer("Add more reverb to the drums")` → false
- Unit: `harmonyInfer("Analyze the voice leading")` → true
- Unit: Verify all 4 tool names match registered tool names
- Integration: Send "analyze this chord progression" to session → routed to harmony agent

**Risk**: Low. Routing conflicts possible with other agents (e.g., "make the bass chord darker" — is it bass or harmony?). Mitigation: infer functions are priority-ordered, Composer agent as catch-all.

---

### P1-T10: Theory Explanation Tool
**Complexity**: S  
**Description**: A `defineTool("explain-theory", ...)` that explains music theory concepts in context. When a user asks "why does this chord work here?", the tool provides the musical reasoning grounded in the actual progression data. Educational surface of the platform.  
**Depends On**: P1-T3, P1-T5, P0-T7 (tool factory)  
**SDK Integration**: `defineTool` via `createMuseTool()` factory

**Input Interface**:
```typescript
interface TheoryExplanationInput {
  /** The concept or chord to explain */
  query: string;
  /** Context: which progression file or generated progression */
  progressionContext?: string;
  /** Specific chord index to focus on */
  chordIndex?: number;
  /** Depth of explanation */
  depth: 'beginner' | 'intermediate' | 'advanced';
}
```

**Output Interface**:
```typescript
interface TheoryExplanationOutput {
  /** Main explanation text */
  explanation: string;
  /** Related concepts for further learning */
  relatedConcepts: string[];
  /** Examples from the corpus */
  corpusExamples: Array<{
    progressionName: string;
    relevance: string;
  }>;
  /** Visual aids (Roman numerals, tension values) */
  analysis?: {
    romanNumerals: string[];
    tensionValues: number[];
  };
}
```

**Testing Strategy**:
- Unit: explain-theory("why does B/F# work after Em7/D?") → includes "secondary dominant", "tritone resolution"
- Unit: Beginner depth → avoids jargon, uses analogies
- Unit: Advanced depth → includes interval vectors, Krumhansl profiles
- Unit: Corpus examples reference actual .progression files

**Risk**: Low. Relies on previously built components.

---

## Phase 1 Summary

| Task | Complexity | Effort | Critical Path |
|---|---|---|---|
| P1-T1: Theory Type System | M | 3 days | Yes |
| P1-T2: Scale/Mode Library | S | 1 day | No |
| P1-T3: Roman Numeral Analyzer | L | 4 days | Yes |
| P1-T4: Voice Leading Engine | L | 4 days | Yes |
| P1-T5: Tension Calculator | M | 3 days | No (parallel with T4) |
| P1-T6: Voicing Engine | L | 4 days | No (parallel with T3) |
| P1-T7: Progression Generator | XL | 6 days | Yes |
| P1-T8: Enrichment Pipeline | M | 2 days | Yes |
| P1-T9: Harmony Agent Config | S | 1 day | No |
| P1-T10: Theory Explanation Tool | S | 1 day | No |

**Critical Path**: T1 → T3 → T4 → T7 → T8 (types → analysis → voice leading → generator → enrichment)  
**Parallel Track A**: T2 (scale library, independent after T1)  
**Parallel Track B**: T5 (tension, needs T1+T2 only)  
**Parallel Track C**: T6 (voicing, needs T1+T4)  
**Parallel Track D**: T9 + T10 (agent config + explanation tool, after T7/T8)

---

*Phase 1 delivers the harmonic intelligence that makes MUSE musically literate. Upon completion, the system can analyze any chord progression, generate new ones in any genre, explain the theory behind every decision, and produce publication-quality enriched descriptions for the embedding pipeline.*
