# MUSE AI Music Platform — Task Decomposition: Phases 0–2

## Complete Engineering Specification

> **Generated**: February 8, 2026
> **Scope**: Phase 0 (Foundation), Phase 1 (Harmonic Brain), Phase 2 (Embeddings & Search)
> **SDK**: `@github/copilot-sdk` — CLI-based JSON-RPC
> **Architecture**: Single session, 6 `customAgents`, quality gates in tool handlers, `SongState` externally serialized, three-tier knowledge

---

## Cross-Phase Contract Definitions

All contracts are defined first. Every task references these by `C{N}` identifier. Contracts are **immutable once Phase 0 ships** — changes require a migration strategy.

---

### Contract C1: SongState

The master state object threaded through every phase. Externally serialized to JSON.

```typescript
// ━━━ C1: SongState ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * Top-level song state — the single source of truth for an in-progress production.
 * Persisted to `output/<session-id>/song-state.json`.
 * All agents read from and write to this via SongStateManager.
 *
 * Compression levels:
 *   L0 (~100 tokens): metadata summary string — "8 tracks, Eb minor, 130 BPM, neo-soul/ambient"
 *   L1 (~500 tokens): structural skeleton — names, roles, presets, section boundaries, chord symbols
 *   L2 (~3000 tokens): full detail — MIDI notes, exact parameters, effect chains
 *   L3 (variable): full history with before/after deltas
 */
export interface SongState {
  /** Schema version for forward migration. SemVer string. */
  readonly version: string;

  /** Song-level metadata: key, tempo, genre, influences. */
  metadata: SongMetadata;

  /** Ordered array of tracks. Index is NOT stable — use `id` for references. */
  tracks: Track[];

  /** Arrangement: sections, energy arc, transitions. */
  arrangement: Arrangement;

  /** Active chord progression with key center analysis. */
  progression: ProgressionState;

  /** Master bus mix state. */
  mixState: MixState;

  /** Append-only change history for undo/redo and preference learning. */
  history: HistoryEntry[];

  /** Session-scoped preferences (populated from Phase 9 UserPreferences if available). */
  preferences: SessionPreferences;
}

/** Immutable metadata describing the musical identity of the song. */
export interface SongMetadata {
  /** User-assigned or auto-generated title. */
  title: string;

  /** Musical key — pitch class name. e.g. "Eb", "F#". */
  key: string;

  /** BPM. Integer or float (e.g. 128.5 for half-time 64.25 feel). */
  tempo: number;

  /** Time signature as [numerator, denominator]. e.g. [4, 4], [6, 8], [7, 8]. */
  timeSignature: [numerator: number, denominator: number];

  /** Artist / style influences. Free-text. e.g. ["Frank Ocean", "Burial"]. */
  influences: string[];

  /** Mood descriptors. e.g. ["melancholic", "dreamy", "nocturnal"]. */
  moodTags: string[];

  /** Computed genre DNA — the mathematical fingerprint of this song's genre blend. */
  genreDNA: GenreDNAVector;

  /** ISO 8601 creation timestamp. */
  createdAt: string;

  /** ISO 8601 last-modified timestamp. */
  updatedAt: string;
}

/**
 * A single track in the arrangement.
 * Maps 1:1 to an MPC Beats track slot.
 */
export interface Track {
  /** UUID v4. Stable across edits. */
  readonly id: string;

  /** Human-readable track name. e.g. "Main Pad", "Sub Bass". */
  name: string;

  /** Functional role in the mix — drives preset selection, EQ slot, panning defaults. */
  role: TrackRole;

  /** Path to source .mid file (relative to output dir). Undefined if not yet generated. */
  midiSource?: string;

  /** Synth preset assigned to this track. */
  preset?: PresetReference;

  /** Ordered insert effect chain. Signal flows left-to-right. */
  effectsChain: EffectInstance[];

  /** Stereo pan. -1.0 = hard left, 0.0 = center, +1.0 = hard right. */
  pan: number;

  /** Track volume. 0.0 = silence, 1.0 = unity gain. */
  volume: number;

  /** Mute state. */
  mute: boolean;

  /** Solo state. */
  solo: boolean;
}

/**
 * Semantic role of a track. Drives mixing heuristics,
 * frequency allocation, and preset recommendation scope.
 */
export type TrackRole =
  | 'drums'
  | 'bass'
  | 'sub_bass'
  | 'chords'
  | 'pad'
  | 'lead'
  | 'melody'
  | 'percussion'
  | 'fx'
  | 'vocal_chop'
  | 'arp';

/**
 * Reference to a synth preset by engine + index + name.
 * Does NOT contain the preset data (binary .xpl) — only identification.
 */
export interface PresetReference {
  /** Synth engine name as installed. e.g. "TubeSynth", "Bassline", "Electric". */
  engine: string;

  /** Zero-based preset index within the engine's preset bank. */
  presetIndex: number;

  /** Human-readable preset name. e.g. "Warm Pad", "Sub Bass 1". */
  presetName: string;

  /** Category extracted from preset filename. e.g. "Pad", "Lead", "Bass", "Synth", "FX". */
  category: string;

  /** Full preset identifier as it appears in directory. e.g. "169-Pad-Warm Pad". */
  fullName: string;
}

/**
 * An effect plugin instance with its parameter state.
 * Maps to a single insert slot on an MPC Beats track.
 */
export interface EffectInstance {
  /** Plugin identifier as named in the Synths directory.
   *  e.g. "AIR Reverb", "MPC3000", "Compressor Opto". */
  pluginId: string;

  /** Manufacturer. e.g. "AIR Music Technology", "Akai Professional". */
  manufacturer: string;

  /** Named parameter → value map.
   *  Values are normalized 0.0–1.0 or raw plugin units depending on the parameter.
   *  Keys are human-readable parameter names (not internal IDs). */
  parameters: Record<string, number>;

  /** Whether this effect slot is bypassed. */
  bypass: boolean;
}

/** Song arrangement — the macro structure of sections over time. */
export interface Arrangement {
  /** Ordered sections. Must cover all bars without gaps or overlaps. */
  sections: Section[];

  /** Sampled energy curve. Used for arrangement visualization and energy-arc guidance. */
  energyArc: EnergyPoint[];

  /** Transitions between consecutive sections. */
  transitions: Transition[];
}

/** A named section of the arrangement (e.g. Intro, Verse A, Chorus). */
export interface Section {
  /** Section label. Must be unique within arrangement. */
  name: string;

  /** 1-based start bar (inclusive). */
  startBar: number;

  /** 1-based end bar (inclusive). */
  endBar: number;

  /** Track IDs active in this section. Subset of SongState.tracks[].id. */
  activeTracks: string[];

  /** Target energy level for this section. 0.0 = minimal, 1.0 = peak. */
  energyLevel: number;
}

/** A single sample point on the energy arc curve. */
export interface EnergyPoint {
  /** 1-based bar number. */
  bar: number;

  /** Composite energy value E(t). 0.0–1.0. */
  energy: number;
}

/** Describes how one section transitions into the next. */
export interface Transition {
  /** Name of the source section. */
  fromSection: string;

  /** Name of the destination section. */
  toSection: string;

  /** Transition technique. */
  type: TransitionType;
}

export type TransitionType =
  | 'cut'
  | 'fade'
  | 'build'
  | 'breakdown'
  | 'drop'
  | 'filter_sweep'
  | 'riser'
  | 'reverse_cymbal';

/** The chord progression state within the song. */
export interface ProgressionState {
  /** Ordered chord instances. Each chord has a duration in beats. */
  chords: ChordInstance[];

  /** Key center annotations — marks where modulations occur. */
  keyCenters: KeyCenterAnnotation[];
}

/** A chord as it appears in the song timeline. */
export interface ChordInstance {
  /** Chord symbol string. e.g. "Ebm9", "F#7/D#". */
  symbol: string;

  /** Voicing: ordered MIDI note numbers (low to high). */
  midiNotes: number[];

  /** Duration in beats. e.g. 4.0 = one bar in 4/4. */
  durationBeats: number;

  /** Computed tension value (from Phase 1 tension function). */
  tension: number;
}

/** Marks the key center at a specific chord index. */
export interface KeyCenterAnnotation {
  /** Zero-based index into ProgressionState.chords[]. */
  chordIndex: number;

  /** Key string. e.g. "Eb minor", "B major". */
  key: string;
}

/** Master bus mix state. */
export interface MixState {
  /** Master fader. 0.0–1.0. */
  masterVolume: number;

  /** Master bus insert effects. */
  masterEffects: EffectInstance[];

  /** Latest frequency balance analysis (generated by Mix agent). */
  frequencyReport?: FrequencyReport;
}

/** Frequency balance analysis across all tracks. */
export interface FrequencyReport {
  /** Per-zone analysis. */
  zones: FrequencyZoneReport[];

  /** Detected masking conflicts. */
  clashes: FrequencyClash[];

  /** ISO 8601 timestamp when this report was generated. */
  generatedAt: string;
}

export interface FrequencyZoneReport {
  zone: FrequencyZone;
  lowHz: number;
  highHz: number;
  dominantTracks: string[];   // track IDs
  level: 'empty' | 'sparse' | 'balanced' | 'dense' | 'congested';
}

export type FrequencyZone = 'sub' | 'bass' | 'low_mid' | 'mid' | 'upper_mid' | 'air';

export interface FrequencyClash {
  trackA: string;             // track ID
  trackB: string;
  zone: FrequencyZone;
  severity: 'low' | 'medium' | 'high';
  suggestion: string;
}

/** A single change record in the undo history. */
export interface HistoryEntry {
  /** Monotonically increasing turn number within the session. */
  turn: number;

  /** ISO 8601 timestamp. */
  timestamp: string;

  /** Original user request text. */
  userRequest: string;

  /** Which agent handled this turn. */
  agentUsed: string;

  /** Atomic changes applied. Enables undo by reverting each. */
  changesMade: Change[];
}

/** A single atomic state mutation, expressed as a JSON-path delta. */
export interface Change {
  /** JSON-path to the changed field. e.g. "tracks[0].preset.presetName". */
  path: string;

  /** The value before this change. `undefined` for insertions. */
  previousValue: unknown;

  /** The value after this change. `undefined` for deletions. */
  newValue: unknown;
}

/** Session-scoped preferences. Lightweight subset of full UserPreferences (C9). */
export interface SessionPreferences {
  /** Active producer mode name, if any. */
  activeMode?: string;

  /** Genre bias for this session. e.g. { "neo_soul": 0.7, "house": 0.3 }. */
  genreBias: Record<string, number>;

  /** Creativity dial: harmonic risk tolerance. 0.0 = safe, 1.0 = experimental. */
  harmonicRisk: number;

  /** Creativity dial: rhythmic risk tolerance. */
  rhythmicRisk: number;
}

// ━━━ Compression Functions ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * L0 Summary: ~100 tokens. Injected into system message on every turn.
 * Format: "{trackCount} tracks, {key} {mode}, {tempo} BPM, {genre}. Sections: {sectionNames}."
 */
export type CompressL0 = (state: SongState) => string;

/**
 * L1 Structural: ~500 tokens. Used for most agent decisions.
 * Returns: track names/roles/presets, section boundaries, chord symbols.
 */
export type CompressL1 = (state: SongState) => SongStateL1;

export interface SongStateL1 {
  title: string;
  key: string;
  tempo: number;
  genre: string;
  tracks: { name: string; role: TrackRole; preset?: string }[];
  sections: { name: string; bars: string; energy: number }[];
  chordSymbols: string[];
}

/**
 * L2 Detailed: ~3000 tokens. Used for note-level editing.
 * Returns: full MIDI notes, exact parameters, full effect chains.
 */
export type CompressL2 = (state: SongState) => SongState; // identity — full state

/**
 * L3 History: variable tokens. Used for undo analysis and preference mining.
 * Returns: full history array.
 */
export type CompressL3 = (state: SongState) => HistoryEntry[];
```

---

### Contract C2: EnrichedProgression

Extends the raw `.progression` parse with full harmonic analysis.

```typescript
// ━━━ C2: EnrichedProgression ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * Raw parsed `.progression` file.
 * Direct 1:1 mapping from the JSON format used by MPC Beats.
 * Validated at parse time via Zod schema.
 *
 * @example Godly.progression
 * ```json
 * { "progression": { "name": "Gospel-Godly", "rootNote": "E",
 *   "scale": "Pentatonic Minor", "recordingOctave": 2,
 *   "chords": [{ "name": "Em", "role": "Root", "notes": [52,59,64,67] }] }}
 * ```
 */
export interface RawProgression {
  progression: {
    /** Display name. Format: "{Genre}-{Name}" or just "{Name}". */
    name: string;

    /** Root note pitch class. e.g. "E", "Bb", "F#". */
    rootNote: string;

    /** Scale name as displayed in MPC Beats. e.g. "Pentatonic Minor", "Major", "Natural Minor". */
    scale: string;

    /** Recording octave setting (MPC Beats internal — affects MIDI octave offset). */
    recordingOctave: number;

    /** Ordered chord array. Typically 4, 8, or 16 chords. */
    chords: RawChord[];
  };
}

/**
 * A single chord entry from a .progression file.
 * The `role` field distinguishes the tonic/root chord from passing chords.
 */
export interface RawChord {
  /** Chord symbol. e.g. "Em7/D", "Amaj9", "B/F#".
   *  Uses standard jazz/pop chord notation with slash for inversions. */
  name: string;

  /** "Root" = the tonic chord. "Normal" = all other chords. Only one chord per progression has role="Root". */
  role: 'Root' | 'Normal';

  /** MIDI note numbers of the voicing (unordered, but typically low-to-high).
   *  Range observed in corpus: 38–88. Length observed: 4–9 notes. */
  notes: number[];
}

/**
 * Fully analyzed progression — the core output of the Harmonic Brain.
 * Extends RawProgression with computed theory annotations.
 * Consumed by Phase 2 (embedding descriptions), Phase 3 (rhythmic context),
 * Phase 6 (pipeline generation), Phase 8 (creativity constraints).
 */
export interface EnrichedProgression {
  /** The original raw parse. Immutable copy. */
  raw: RawProgression;

  /** Source file path (absolute). */
  filePath: string;

  /** Content hash for cache invalidation. SHA-256 of file bytes. */
  contentHash: string;

  /** Parsed genre from the progression name field. e.g. "Gospel", "Neo Soul", "House". */
  genre: string;

  /** Parsed progression name (without genre prefix). e.g. "Godly", "Neo Soul 1". */
  displayName: string;

  /** Complete harmonic analysis. */
  analysis: HarmonicAnalysis;
}

/** Deep harmonic analysis computed from the raw chord data. */
export interface HarmonicAnalysis {
  /** Roman numeral for each chord relative to the detected key center.
   *  e.g. ["i", "i7/♭VII", "V/♯ii", "V7/♯vii"].
   *  Length MUST equal raw.progression.chords.length. */
  romanNumerals: string[];

  /** Detected key center with confidence. May differ from raw.rootNote+raw.scale
   *  if the stated scale is inaccurate (observed in some progression files). */
  keyCenter: KeyCenter;

  /** Voice leading distance (total semitone movement) between each consecutive chord pair.
   *  Length = chords.length - 1. */
  voiceLeadingDistances: number[];

  /** Common tone count between each consecutive chord pair.
   *  Length = chords.length - 1. */
  commonToneRetention: number[];

  /** Tension T(chord) value for each chord. Range: 0.0–1.0.
   *  Computed via: T = w_r·R + w_s·(1−S) + w_d·D + w_c·C.
   *  Length MUST equal chords.length. */
  tensionValues: number[];

  /** Tension arc descriptor: overall shape of tension curve. */
  tensionArc: 'ascending' | 'descending' | 'arch' | 'valley' | 'flat' | 'oscillating';

  /** Genre associations derived from harmonic features.
   *  Top-3 matching genres by feature similarity to GenreDNA vectors. */
  genreAssociations: GenreAssociation[];

  /** Harmonic complexity score. 0.0 = simple triads. 1.0 = max extensions + chromaticism. */
  complexity: number;

  /** Chromaticism score. Ratio of non-diatonic pitch classes used. 0.0–1.0. */
  chromaticism: number;

  /** Average voicing spread in semitones (distance from lowest to highest note per chord). */
  averageVoicingSpread: number;

  /** Detected harmonic patterns. */
  patterns: HarmonicPattern[];

  /** Full voice leading analysis between all consecutive chord pairs. */
  voiceLeading: VoiceLeadingAnalysis;

  /** Unique pitch classes used across all chords (0–11). */
  pitchClassProfile: number[];

  /** Suggestions for chord substitutions (top 3 most impactful). */
  topSubstitutions: SubstitutionSuggestion[];
}

/** Detected key center with a confidence score. */
export interface KeyCenter {
  /** Root pitch class name. e.g. "E", "Bb". */
  root: string;

  /** Mode name. e.g. "minor", "major", "dorian", "mixolydian". */
  mode: string;

  /** Confidence in this key assignment. 0.0–1.0.
   *  Computed via Krumhansl-Kessler key profile correlation. */
  confidence: number;

  /** Alternative key interpretations if confidence < 0.8. */
  alternatives?: KeyCenter[];
}

/** Genre association with similarity score and reasoning. */
export interface GenreAssociation {
  genre: string;
  similarity: number;         // cosine similarity to GenreDNA vector
  reasoning: string;          // e.g. "High chromaticism + extended chords match Neo Soul profile"
}

/** Named harmonic pattern detected in the progression. */
export interface HarmonicPattern {
  /** Pattern type identifier. */
  type: HarmonicPatternType;

  /** Human-readable description. */
  description: string;

  /** Zero-based chord indices where this pattern occurs. */
  chordIndices: number[];
}

export type HarmonicPatternType =
  | 'chromatic_bass_descent'
  | 'chromatic_bass_ascent'
  | 'circle_of_fifths'
  | 'pedal_point'
  | 'secondary_dominant_chain'
  | 'modal_interchange'
  | 'deceptive_cadence'
  | 'plagal_cadence'
  | 'authentic_cadence'
  | 'tritone_substitution'
  | 'sequence'               // repeated pattern transposed
  | 'turnaround';

/** Analysis of voice leading across an entire progression. */
export interface VoiceLeadingAnalysis {
  /** Per-transition analysis. Length = chords.length - 1. */
  transitions: VoiceLeadingTransition[];

  /** Average semitone movement per transition across all voices. */
  averageMovement: number;

  /** Overall smoothness score. 0.0 = jagged, 1.0 = maximally smooth. */
  smoothness: number;

  /** Count of parallel perfect interval violations (fifths/octaves). */
  parallelMotionCount: number;
}

/** Voice leading analysis between two consecutive chords. */
export interface VoiceLeadingTransition {
  /** Source chord symbol. */
  fromChord: string;

  /** Destination chord symbol. */
  toChord: string;

  /** Total semitone movement across all matched voices. */
  totalSemitoneMovement: number;

  /** Count of notes shared between both chords. */
  commonToneCount: number;

  /** Count of voice crossings (a higher voice moves below a lower voice or vice versa). */
  voiceCrossings: number;

  /** True if parallel 5ths detected between any voice pair. */
  parallelFifths: boolean;

  /** True if parallel octaves detected between any voice pair. */
  parallelOctaves: boolean;

  /** Motion type for each matched voice pair. */
  motionTypes: Array<'oblique' | 'similar' | 'contrary' | 'parallel'>;
}

/** A suggested chord substitution. */
export interface SubstitutionSuggestion {
  /** Zero-based index of the chord to substitute. */
  chordIndex: number;

  /** Original chord symbol. */
  original: string;

  /** Proposed replacement chord symbol. */
  substitution: string;

  /** Substitution technique used. */
  type: SubstitutionType;

  /** Change in tension. Positive = more tension. Negative = less. */
  tensionDelta: number;

  /** Explanation of the substitution and its musical effect. */
  reasoning: string;

  /** MIDI note voicing for the substitution (in context of surrounding chords). */
  voicing: number[];
}

export type SubstitutionType =
  | 'tritone_sub'
  | 'relative_major_minor'
  | 'modal_interchange'
  | 'secondary_dominant'
  | 'sus_resolution'
  | 'chromatic_mediant'
  | 'upper_structure'
  | 'simplification'
  | 'reharmonization';
```

---

### Contract C3: MidiPattern

Parsed arp pattern / generated MIDI data.

```typescript
// ━━━ C3: MidiPattern ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * A MIDI note event with absolute tick position and duration.
 * Tick resolution depends on the source file's ticksPerBeat (typically 480 or 960).
 */
export interface MidiNoteEvent {
  /** Absolute tick position from start of file. */
  tick: number;

  /** MIDI channel (0–15). */
  channel: number;

  /** MIDI note number (0–127). Middle C = 60. */
  note: number;

  /** Note-on velocity (1–127). 0 is treated as note-off. */
  velocity: number;

  /** Duration in ticks. */
  durationTicks: number;
}

/**
 * Parsed arp pattern from a .mid file in the Arp Patterns directory.
 * Includes raw MIDI data + computed rhythmic/melodic analysis.
 */
export interface ParsedArpPattern {
  /** Source filename without extension. e.g. "044-Melodic-Lead Hip Hop 01". */
  fileName: string;

  /** Absolute file path. */
  filePath: string;

  /** Category derived from filename prefix. */
  category: ArpCategory;

  /** Sub-category from filename. e.g. "Lead Hip Hop", "SynBass", "Dance", "Soul Ballad". */
  subCategory: string;

  /** Genre inferred from sub-category. e.g. "hip_hop", "electronic", "soul". */
  genre: string;

  /** Zero-based index from filename prefix. e.g. 44 for "044-...". */
  index: number;

  /** Variant number (the trailing digit). e.g. 1 for "...01.mid". */
  variant: number;

  /** MIDI file header metadata. */
  header: MidiFileHeader;

  /** All note events extracted from the MIDI file. Sorted by tick ascending. */
  notes: MidiNoteEvent[];

  /** Computed rhythmic and melodic analysis. */
  analysis: ArpAnalysis;
}

export type ArpCategory = 'Chord' | 'Melodic' | 'Bass';

/** MIDI file header (Standard MIDI File format). */
export interface MidiFileHeader {
  /** Format: 0 (single track), 1 (multi-track synchronous), 2 (multi-track async). */
  format: 0 | 1 | 2;

  /** Number of tracks in the file. */
  numTracks: number;

  /** Ticks per quarter note. Typically 480 or 960. */
  ticksPerBeat: number;
}

/** Rhythmic and melodic analysis of an arp pattern. */
export interface ArpAnalysis {
  /** Total duration of the pattern in ticks. */
  durationTicks: number;

  /** Total duration in beats (durationTicks / ticksPerBeat). */
  durationBeats: number;

  /** Total number of note events. */
  noteCount: number;

  /** Pitch range of all notes. */
  pitchRange: {
    /** Lowest MIDI note number in the pattern. */
    low: number;
    /** Highest MIDI note number in the pattern. */
    high: number;
    /** Span in semitones (high - low). */
    span: number;
  };

  /** Note density: notes per beat. Higher = busier pattern. */
  density: number;

  /** Velocity statistics. */
  velocityStats: {
    min: number;
    max: number;
    mean: number;
    stddev: number;
  };

  /**
   * Smallest rhythmic subdivision used, expressed as a fraction of a beat.
   * e.g. 4 = quarter notes only, 8 = 8th notes, 16 = 16th notes, 32 = 32nd notes.
   * Computed as GCD of all note-on tick positions relative to beat boundaries.
   */
  rhythmicGrid: number;

  /**
   * Estimated swing amount (0.0–1.0).
   * 0.0 = straight (50/50 division of each beat pair).
   * 1.0 = maximum swing (75/25 triplet feel).
   * Computed by comparing even vs odd subdivision placements.
   */
  swingAmount: number;

  /**
   * Interval distribution: maps interval (in semitones) → count of occurrences.
   * Computed between consecutive notes (by pitch, not time).
   * Negative values = descending intervals.
   */
  intervalDistribution: Record<number, number>;

  /**
   * Whether the pattern is predominantly monophonic (one note at a time)
   * or polyphonic (simultaneous notes).
   */
  polyphony: 'monophonic' | 'polyphonic' | 'mixed';

  /**
   * Maximum simultaneous note count at any point.
   */
  maxPolyphony: number;
}
```

---

### Contract C7: EmbeddingIndex

Local vector search index over all MPC Beats assets.

```typescript
// ━━━ C7: EmbeddingIndex ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * A single asset embedded as a 384-dimensional vector.
 * The vector is the all-MiniLM-L6-v2 sentence embedding of the
 * asset's human-authored description text.
 */
export interface AssetEmbedding {
  /** Unique asset identifier. Format: "{type}:{name}". e.g. "progression:Godly". */
  id: string;

  /** Asset type discriminator. */
  type: AssetType;

  /** Human-readable display name. */
  name: string;

  /** The enriched text description that was embedded.
   *  50–100 words capturing sonic character, genre, mood, and use cases. */
  description: string;

  /** 384-dimensional L2-normalized embedding vector.
   *  cosine_similarity(a,b) = dot_product(a,b) when both are L2-normalized. */
  vector: Float32Array;

  /** Type-specific metadata for filtering and display. */
  metadata: AssetMetadata;
}

export type AssetType = 'progression' | 'arp' | 'preset' | 'effect' | 'controller';

/**
 * Type-specific metadata carried alongside each embedding entry.
 * Enables type-safe filtering without deserializing the vector.
 */
export type AssetMetadata =
  | ProgressionMetadata
  | ArpMetadata
  | PresetMetadata
  | EffectMetadata
  | ControllerMetadata;

export interface ProgressionMetadata {
  type: 'progression';
  filePath: string;
  genre: string;
  key: string;
  scale: string;
  chordCount: number;
  complexity: number;
}

export interface ArpMetadata {
  type: 'arp';
  filePath: string;
  category: ArpCategory;
  subCategory: string;
  genre: string;
  density: number;
  rhythmicGrid: number;
}

export interface PresetMetadata {
  type: 'preset';
  engine: string;
  presetIndex: number;
  category: string;
  fullName: string;
}

export interface EffectMetadata {
  type: 'effect';
  manufacturer: string;
  effectFamily: EffectFamily;
  pluginId: string;
}

export type EffectFamily =
  | 'compressor' | 'eq' | 'delay' | 'reverb'
  | 'distortion' | 'filter' | 'modulation'
  | 'character' | 'dynamics' | 'utility';

export interface ControllerMetadata {
  type: 'controller';
  manufacturer: string;
  model: string;
  padCount: number;
  knobCount: number;
  filePath: string;
}

/**
 * The complete embedding index. Held in memory at runtime (~1MB).
 * Persisted to `data/embedding-index.json` as serialized JSON.
 */
export interface EmbeddingIndex {
  /** Model identifier. Always "all-MiniLM-L6-v2" for MUSE v1. */
  readonly model: string;

  /** Vector dimensionality. Always 384 for all-MiniLM-L6-v2. */
  readonly dimensions: number;

  /** ISO 8601 timestamp of last full index rebuild. */
  builtAt: string;

  /** All embedded asset entries. */
  entries: AssetEmbedding[];

  /**
   * Search the index with a natural-language query.
   *
   * @param query - The search text. Embedded at query time.
   * @param topK - Maximum results to return (default 10).
   * @param typeFilter - Restrict to specific asset types.
   * @returns Ranked results with similarity scores.
   */
  search(query: string, topK?: number, typeFilter?: AssetType[]): Promise<SearchResult[]>;
}

/** A single search result with similarity score. */
export interface SearchResult {
  /** The matching asset embedding entry. */
  asset: AssetEmbedding;

  /** Cosine similarity between query vector and asset vector. Range: -1.0 to 1.0.
   *  In practice, 0.3+ indicates meaningful similarity for this model. */
  similarity: number;
}

/**
 * Serialized index format for JSON persistence.
 * Float32Array entries are serialized as number[] for JSON compatibility.
 */
export interface SerializedEmbeddingIndex {
  model: string;
  dimensions: number;
  builtAt: string;
  entries: Array<{
    id: string;
    type: AssetType;
    name: string;
    description: string;
    vector: number[];         // Float32Array → number[] for JSON
    metadata: AssetMetadata;
  }>;
}
```

---

### Contract C8: GenreDNA

Genre as a computable vector. Used for fusion, matching, and constraint generation.

```typescript
// ━━━ C8: GenreDNA ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * 10-dimensional fingerprint encoding a genre's musical characteristics.
 * All dimensions are normalized to specific ranges for meaningful interpolation.
 *
 * Used for: genre fusion, progression/pattern selection, preset filtering,
 * creativity constraint generation, preference vector comparison.
 */
export interface GenreDNAVector {
  /**
   * Harmonic complexity: how many extensions, alterations, and non-diatonic
   * chords are typical. 0.0 = triads only (pop/punk). 1.0 = max extensions +
   * constant chromaticism (bebop jazz).
   */
  chordComplexity: number;

  /**
   * Degree of chromatic (non-diatonic) pitch usage. 0.0 = strictly diatonic
   * (simple folk). 1.0 = fully chromatic (12-tone).
   */
  chromaticism: number;

  /**
   * Typical voicing spread: average distance in semitones between lowest and
   * highest chord tones, normalized. 0.0 = tight close voicing (power chords).
   * 1.0 = wide open voicing spanning 3+ octaves (neo-soul, orchestral).
   */
  voicingSpread: number;

  /**
   * Swing factor. 0.0 = dead straight quantized (EDM, metal).
   * 1.0 = heavy shuffle/swing (New Orleans jazz, J Dilla).
   */
  swing: number;

  /**
   * Vintage/lo-fi character. 0.0 = pristine digital production (modern pop).
   * 1.0 = heavy vintage processing (boom-bap, lo-fi hip hop).
   */
  vintage: number;

  /**
   * Tempo range in BPM. A tuple [min, max].
   * e.g. [120, 130] for house, [130, 145] for trap, [65, 90] for neo-soul.
   */
  tempoRange: [min: number, max: number];

  /**
   * Rhythmic density: how many note events per beat are typical for the
   * primary rhythmic instrument. 0.0 = whole notes. 1.0 = 32nd note density.
   */
  rhythmicDensity: number;

  /**
   * Harmonic rhythm: chord changes per bar. 0.25 = one chord every 4 bars.
   * 4.0 = chord changes on every beat (jazz, gospel).
   */
  harmonicRhythm: number;

  /**
   * Brightness axis. -1.0 = dark, heavy, sub-dominant (doom metal, dark ambient).
   * +1.0 = bright, airy, sparkling (bubblegum pop, vaporwave).
   */
  darkBright: number;

  /**
   * Organic vs electronic production character.
   * -1.0 = fully organic/acoustic (folk, classical).
   * +1.0 = fully electronic/synthetic (IDM, EDM).
   */
  organicElectronic: number;
}

/**
 * Genre identifier type. Must match keys in the GENRE_DNA registry.
 */
export type GenreId =
  | 'neo_soul' | 'gospel' | 'jazz' | 'house' | 'deep_house' | 'tech_house'
  | 'trap' | 'rnb' | 'pop' | 'soul' | 'hip_hop' | 'boom_bap'
  | 'dubstep' | 'edm' | 'dance' | 'chill_out' | 'ambient'
  | 'classic_rock' | 'funk' | 'blues' | 'afrobeat' | 'reggae'
  | 'classical' | 'lo_fi' | 'synthwave' | 'uk_garage';

/** The pre-defined genre registry loaded from `data/genre-dna.json`. */
export type GenreDNARegistry = Record<GenreId, GenreDNAVector>;

/** Result of blending two or more genres. */
export interface GenreFusionResult {
  /** The interpolated DNA vector. */
  vector: GenreDNAVector;

  /** Source genres and their blend weights. Sum must equal 1.0. */
  sources: Array<{ genre: GenreId; weight: number }>;

  /** Human-readable description of what this blend sounds like. */
  description: string;

  /** Suggested tempo derived from weighted tempo range intersection/union. */
  suggestedTempo: number;
}
```

---

## PHASE 0 — FOUNDATION

**Goal**: Project scaffold, SDK integration, all file parsers, SongState schema, tool registration infrastructure. After Phase 0, MUSE reads every MPC Beats asset type, maintains a conversation with SongState, responds to basic queries.

**Task Count**: 8
**Estimated Effort**: 3–4 dev-weeks

---

### P0-T1: Project Scaffold & SDK Bootstrap

| Field | Value |
|---|---|
| **Complexity** | S |
| **Description** | Initialize Node.js/TypeScript monorepo, install `@github/copilot-sdk`, configure build tooling, create the entry point that spawns a `CopilotClient` and creates a `CopilotSession`. Establish directory skeleton: `src/`, `skills/`, `data/`, `output/`, and path aliases. |
| **Dependencies** | None (root task) |
| **SDK Integration** | `CopilotClient` instantiation, `CopilotSession.create()` with initial `systemMessage`, `infiniteSessions: { backgroundCompactionThreshold: 0.80, bufferExhaustionThreshold: 0.95 }`, empty `customAgents: []`, empty `skillDirectories: ['./skills']`, placeholder `hooks` object. CLI arg parsing: `--mpc-path`, `--model`, `--provider`, `--api-key`, `--session`, `--output-dir`, `--verbose`. |
| **Input Interface** | `interface CLIArgs { mpcPath?: string; model?: string; provider?: 'copilot' \| 'openai' \| 'azure' \| 'anthropic' \| 'ollama'; apiKey?: string; session?: string; outputDir?: string; verbose?: boolean; }` |
| **Output Interface** | `interface BootstrapResult { client: CopilotClient; session: CopilotSession; config: ResolvedConfig; }` — where `interface ResolvedConfig { mpcBeatsPath: string; model: string; provider: string; outputDir: string; sessionId: string; verbose: boolean; }` |
| **Testing** | Unit: verify `CopilotSession` creates with system message set. Integration: start session → send "hello" → receive response → exit cleanly. E2E: `--mpc-path` auto-detection finds `C:\dev\MPC Beats`. Assert `tsconfig.json` strict mode passes. Vitest green on empty suite. |
| **Risk** | SDK API may change between versions — pin exact version in `package.json`. Windows-only path detection requires `path.win32` normalization. |

---

### P0-T2: System Message Template Engine

| Field | Value |
|---|---|
| **Complexity** | M |
| **Description** | Design the MUSE system prompt composed from 5 sections: (1) Identity (~100 tokens), (2) Capabilities (~200 tokens), (3) Workspace Context (~150 tokens injected from `AssetManifest`), (4) Active State (~100 tokens from SongState L0), (5) Behavioral Rules (~150 tokens). Implement as a template engine function that dynamic-composes the prompt string. |
| **Dependencies** | P0-T1 (project exists) |
| **SDK Integration** | `systemMessage: { mode: 'append', content: buildSystemMessage(manifest, songState?) }`. Mode `'append'` preserves the SDK's base system prompt, adding MUSE's persona after it. |
| **Input Interface** | `function buildSystemMessage(manifest: AssetManifest \| null, songState?: SongState): string` |
| **Output Interface** | Returns `string` (the full system message). Must stay ≤ 700 tokens (measured via `tiktoken` `cl100k_base` encoding or the 4-chars-per-token heuristic). |
| **Testing** | Snapshot: golden-file comparison for known inputs. Token budget: assert `estimateTokens(buildSystemMessage(fullManifest, fullState)) ≤ 700`. Null manifest: produces valid prompt without workspace section. Null SongState: omits active state section. Empty manifest: graceful "No MPC Beats assets found" phrasing. |
| **Risk** | Token budget is tight. If the asset manifest grows (user adds many presets), the workspace section may need truncation logic. Add a `maxWorkspaceTokens` parameter with default 150. |

---

### P0-T3: Workspace Asset Scanner & Manifest Builder

| Field | Value |
|---|---|
| **Complexity** | M |
| **Description** | Scan the MPC Beats installation directory tree, discover all asset files (.progression, .mid, .xmm, synth presets, effect plugins), and produce a structured `AssetManifest`. Cache the manifest to `data/asset-manifest.json` with a timestamp; re-scan on demand or if cache is >24h stale. |
| **Dependencies** | P0-T1 |
| **SDK Integration** | Called from `hooks.onSessionStart` to populate workspace context. Can optionally be wired to an MCP filesystem-watcher server for live asset detection. |
| **Input Interface** | `function scanWorkspace(basePath: string): Promise<AssetManifest>` |
| **Output Interface** | `interface AssetManifest { basePath: string; scannedAt: string; progressions: Array<{ path: string; name: string }>; arpPatterns: Array<{ path: string; name: string; category: ArpCategory; subCategory: string; index: number }>; controllerMaps: Array<{ path: string; manufacturer: string; model: string }>; synthEngines: SynthEngineManifest[]; effects: EffectPluginManifest[]; }` — where `interface SynthEngineManifest { name: string; manufacturer: string; path: string; type: 'synth' \| 'drum' \| 'vst'; presetCount: number; }` and `interface EffectPluginManifest { name: string; manufacturer: string; displayName: string; family: EffectFamily; directory: string; presetCount: number; }` |
| **Testing** | Run against live `C:\dev\MPC Beats`. Assert: 47 progressions, 80 arp patterns (verify all listed in Arp Patterns/), 67 controller maps (count .xmm files excluding VERSION.xml), 298 TubeSynth presets. Verify arp category parsing: indices 0–37 → Chord, 38–55 → Melodic, 56+ → Bass. Verify effect family classification: "Compressor Opto" → compressor, "AIR Reverb" → reverb. Cache round-trip: scan → serialize → deserialize → compare counts. |
| **Risk** | Windows path length limits (>260 chars) for deeply nested synth directories. Use `fs.promises` with `{ recursive: true }`. Some effects share names across manufacturers — disambiguate by full directory path. |

---

### P0-T4: `.progression` JSON Parser

| Field | Value |
|---|---|
| **Complexity** | S |
| **Description** | Parse `.progression` JSON files (MPC Beats chord progression format) into `RawProgression` (C2 contract). Runtime-validate with Zod schema. Extract genre and display name from the `name` field (format: `"Genre-Name"` or just `"Name"`). |
| **Dependencies** | P0-T1 |
| **SDK Integration** | Consumed by `read_progression` tool (P0-T7), Phase 1 enrichment pipeline. |
| **Input Interface** | `function parseProgression(filePath: string): Promise<ParsedProgressionResult>` |
| **Output Interface** | `interface ParsedProgressionResult { raw: RawProgression; genre: string; displayName: string; filePath: string; warnings: string[]; }` — Zod schemas: `const RawChordSchema = z.object({ name: z.string().min(1), role: z.enum(['Root', 'Normal']), notes: z.array(z.number().int().min(0).max(127)).min(1).max(16) })` and `const RawProgressionSchema = z.object({ progression: z.object({ name: z.string(), rootNote: z.string(), scale: z.string(), recordingOctave: z.number().int(), chords: z.array(RawChordSchema).min(1).max(64) }) })`. |
| **Testing** | Parse all 47 .progression files — zero failures. Spot-checks: Godly has 16 chords, first chord role="Root" with notes=[52,59,64,67]. Neo Soul 1 has 16 chords, notes array lengths range from 5 to 9. Classic House has 16 chords with notes lengths 5–9. Genre extraction: "Gospel-Godly" → genre="Gospel", displayName="Godly". "ClassicMajor" → genre="", displayName="ClassicMajor". Malformed JSON: returns descriptive ZodError. MIDI note range across corpus: verify min≥38, max≤88 (from Neo Soul 1 chord data: 38 lowest observed, 88 highest observed). |
| **Risk** | Low. Files are well-formed JSON. Edge case: progression names without genre prefix (e.g. "SoSimple", "TheCanon") — parser must not crash, just set genre="" . |

---

### P0-T5: `.xmm` XML Controller Map Parser

| Field | Value |
|---|---|
| **Complexity** | M |
| **Description** | Parse `.xmm` XML files (MPC Beats MIDI controller mapping format) into `ParsedControllerMap`. Extract device info (manufacturer, port names), MIDI preamble, and all Target_control ↔ MIDI mappings. Classify each pairing as pad/key (Mapping_control=4) or knob/slider (Mapping_control=7). |
| **Dependencies** | P0-T1 |
| **SDK Integration** | Consumed by `read_controller_map` tool (P0-T7), Phase 7 controller intelligence. |
| **Input Interface** | `function parseControllerMap(filePath: string): Promise<ParsedControllerMap>` |
| **Output Interface** | `interface ParsedControllerMap { filePath: string; manufacturer: string; version: string; device: { inputPort: string; outputPort: string; }; hasMidiPreamble: boolean; pairings: ControlPairing[]; stats: ControllerStats; }` — `interface ControlPairing { targetControl: number; targetName?: string; mapping: { type: MappingType; channel: number; data1: number; control: ControlType; reverse: boolean; }; }` — `enum MappingType { UNMAPPED = 0, NOTE = 1, CC = 2 }` — `enum ControlType { PAD_KEY = 4, KNOB_SLIDER = 7 }` — `interface ControllerStats { totalTargets: number; mappedPads: number; mappedKnobs: number; unmapped: number; maxTargetControl: number; }` |
| **Testing** | Parse all 67 .xmm files (exclude VERSION.xml) — zero failures. MPK mini 3: 16 pads (targets 0–15, type=1, channel=10, notes 36–51), 8 knobs (targets 24–31, type=2, channel=1, CCs 70–77), rest unmapped. Max Target_control observed = 116 across all files. Manufacturer extraction: "Akai" from MPK mini 3, verify all manufacturers: Akai, Alesis, Arturia, Korg, M-Audio, NI, Novation (+ Ableton from Push files). Stats validation: `stats.mappedPads + stats.mappedKnobs + stats.unmapped === stats.totalTargets`. |
| **Risk** | XML attributes use underscore suffixes (`MidiLearnMap_`, `Target_`, `Mapping_`) — ensure `fast-xml-parser` attribute extraction handles these. Some controllers may have different XML structure versions — test against oldest (Korg nanoPAD) and newest files. |

---

### P0-T6: SongState Schema, Manager & Compression

| Field | Value |
|---|---|
| **Complexity** | L |
| **Description** | Implement the full `SongState` schema (C1 contract) as Zod schemas + TypeScript types. Build `SongStateManager` with CRUD operations, immutable update pattern, undo/redo via history replay, and the L0–L3 compression functions. Implement JSON persistence to `output/<session-id>/song-state.json`. |
| **Dependencies** | P0-T1 |
| **SDK Integration** | `SongStateManager` is the central state container. `hooks.onPostToolUse` calls `manager.applyChange()`. `hooks.onSessionEnd` calls `manager.persist()`. `hooks.onSessionStart` calls `manager.loadOrCreate()`. L0 compression feeds into `systemMessage` via P0-T2. |
| **Input Interface** | `class SongStateManager { constructor(outputDir: string, sessionId: string); loadOrCreate(): Promise<SongState>; get current(): Readonly<SongState>; applyChange(agentName: string, userRequest: string, changes: Change[]): SongState; undo(count?: number): SongState; redo(count?: number): SongState; persist(): Promise<void>; compressL0(): string; compressL1(): SongStateL1; compressL2(): SongState; compressL3(): HistoryEntry[]; }` |
| **Output Interface** | All types from C1 contract. Zod schemas for runtime validation: `SongStateSchema`, `TrackSchema`, `ArrangementSchema`, `ProgressionStateSchema`, `MixStateSchema`, `HistoryEntrySchema`. Static factory: `function createEmptySongState(sessionId: string): SongState`. |
| **Testing** | Round-trip: `createEmpty → applyChange × 3 → persist → load → compare`. L0 compression: "0 tracks, C major, 120 BPM, pop" from empty state — assert ≤100 tokens. L1 compression: verify track/section/chord arrays populated correctly. Undo: apply 5 changes, undo 3, verify state matches state-after-change-2. Redo after undo: restore change 3. Change path validation: invalid JSON path in Change.path throws. Session ID collision: verify UUIDs are unique across 10000 generations. Persist permissions: verify output directory created recursively. |
| **Risk** | Immutable update performance — deep cloning large states. Use `structuredClone()` (available in Node 17+). History can grow unbounded — add a `maxHistory` config (default 100 entries). JSON serialization of `Float32Array` in `genreDNA.tempoRange` — ensure tuple survives round-trip. |

---

### P0-T7: Tool Registration Factory & Initial Read Tools

| Field | Value |
|---|---|
| **Complexity** | M |
| **Description** | Create the `defineMuseTool()` wrapper around the SDK's `defineTool()` that enforces MUSE conventions: Zod parameter validation, structured error responses, SongState mutation tracking, execution logging, and tool categorization. Then register the initial 5 read-only tools: `read_progression`, `read_arp_pattern`, `read_controller_map`, `list_presets`, `list_assets`. |
| **Dependencies** | P0-T1, P0-T3 (scanner), P0-T4 (.progression parser), P0-T5 (.xmm parser) |
| **SDK Integration** | Each tool registered via `defineTool(name, { description, parameters, handler })`. `MuseToolContext` injected into every handler provides `currentState: SongState`, `manifest: AssetManifest`, `logger`, `sessionId`. Tools returned as array for `CopilotSession.create({ tools: [...registeredTools] })`. |
| **Input Interface** | Factory: `function defineMuseTool<T extends z.ZodType>(name: string, config: { description: string; parameters: T; category: 'read' \| 'generate' \| 'analyze' \| 'control'; modifiesSongState: boolean; handler: (params: z.infer<T>, context: MuseToolContext) => Promise<ToolResult>; }): Tool` — Context: `interface MuseToolContext { state: Readonly<SongState>; manifest: AssetManifest; logger: Logger; sessionId: string; mpcBasePath: string; }` — Result: `interface ToolResult { success: boolean; data: unknown; displayText: string; songStateChanges?: Change[]; }` |
| **Output Interface** | Tool definitions: `read_progression: { params: { filePath: z.string() }, returns: ParsedProgressionResult }`, `read_arp_pattern: { params: { filePath: z.string() }, returns: ParsedArpPattern }`, `read_controller_map: { params: { filePath: z.string() }, returns: ParsedControllerMap }`, `list_presets: { params: { engine: z.string().optional() }, returns: PresetCatalog }`, `list_assets: { params: { type: z.enum(['progression','arp','controller','preset','effect']).optional() }, returns: AssetManifest (filtered) }`. Registry: `class ToolRegistry { tools: Map<string, Tool>; register(tool: Tool): void; getByCategory(cat: string): Tool[]; toArray(): Tool[]; generateDocString(): string; }` |
| **Testing** | Unit: register mock tool, invoke with valid params → success. Register mock tool, invoke with invalid params → ZodError caught, structured error returned. Verify `modifiesSongState: true` tools produce `songStateChanges`. Integration: create session with 5 tools registered, send "What progressions are available?" → LLM calls `list_assets` → response includes file names. Verify `read_progression` for Godly returns 16 chords with correct names. Verify `list_presets` with `engine="TubeSynth"` returns 298 entries. Verify `read_controller_map` for MPK mini 3 returns 16 pads and 8 knobs. |
| **Risk** | Tool description quality affects LLM tool selection. Descriptions must be precise and unambiguous. `list_assets` vs `read_progression` — LLM must understand when to use discovery (list) vs detail (read). Test with multiple LLM providers to verify tool-calling reliability. |

---

### P0-T8: Session Lifecycle Hooks & Configuration

| Field | Value |
|---|---|
| **Complexity** | L |
| **Description** | Implement all session lifecycle hooks (`onSessionStart`, `onSessionEnd`, `onPreToolUse`, `onPostToolUse`, `onErrorOccurred`), the CLI interface with arg parsing and config resolution, and the session resume flow. Wire everything together into a bootable system. |
| **Dependencies** | P0-T1, P0-T2, P0-T3, P0-T6, P0-T7 (all prior tasks) |
| **SDK Integration** | `hooks: { onSessionStart: async () => { scan workspace, build/load manifest, create/resume SongState, return { additionalContext: compressL0(state) + manifestSummary } }, onSessionEnd: async () => { persist SongState, log session summary }, onPreToolUse: async (toolName, params) => { log invocation, check permissions for write tools, return { permissionDecision: 'allow' } }, onPostToolUse: async (toolName, result) => { if result.songStateChanges → applyChange(), check if context compression should escalate }, onErrorOccurred: async (error) => { map to user-friendly message, suggest recovery } }`. Permission handler for file writes to MPC Beats directories (require user confirmation). |
| **Input Interface** | CLI: `muse [--mpc-path <path>] [--model <model>] [--provider <provider>] [--session <id>] [--output-dir <dir>] [--verbose]`. Config file: `muse.config.json` at workspace root (optional). `interface MuseConfig { mpcBeatsPath?: string; model?: string; provider?: string; outputDir?: string; defaultGenre?: string; maxHistoryEntries?: number; }` |
| **Output Interface** | Running MUSE CLI session that: (1) accepts user input, (2) routes to LLM with tools available, (3) streams responses, (4) persists state between turns, (5) supports session resume via `--session <id>`. Session metadata file: `output/<session-id>/session-meta.json` with `{ sessionId, startedAt, lastTurnAt, turnCount, mpcBeatsVersion?, config }`. |
| **Testing** | `onSessionStart`: start session → verify `AssetManifest` populated with correct counts → verify `SongState` created with empty state → verify L0 context injected. `onSessionEnd`: end session → verify `song-state.json` exists on disk → verify `session-meta.json` written. `onPostToolUse`: call `read_progression` → verify NO state change (read-only tool). Call a hypothetical state-modifying tool → verify `HistoryEntry` appended. `onErrorOccurred`: simulate file-not-found → verify user-friendly message "Progression file not found. Try `list_assets` to see available files." Session resume: start session → apply 3 changes → exit → restart with `--session same-id` → verify state restored with 3 history entries. MPC path auto-detection: mock `C:\Program Files\Akai\MPC Beats\` and `C:\dev\MPC Beats\` → verify detection. Config precedence: CLI args > config file > defaults. |
| **Risk** | `infiniteSessions` interaction with SongState — when the SDK compacts context, our SongState L0/L1 must be re-injected. Verify `additionalContext` survives compaction. Session resume with incompatible schema version — implement version check + migration stub. Graceful degradation when MPC Beats path not found — operate in "demo mode" with no workspace context. |

---

## PHASE 1 — HARMONIC BRAIN

**Goal**: Full harmonic intelligence. Roman numeral analysis, tension scoring, voice leading, chord-to-MIDI voicing, progression generation, and the Harmony agent.

**Task Count**: 8
**Estimated Effort**: 4–5 dev-weeks

---

### P1-T1: Music Theory Foundation Types & Scale Library

| Field | Value |
|---|---|
| **Complexity** | M |
| **Description** | Define the foundational music theory type system: `NoteName`, `PitchClass`, `Interval`, `ScaleType`, `ChordQuality`. Build the scale library: 21 scale types × 12 root notes = 252 scale instances. Each scale provides: pitch class set, interval pattern, characteristic chords at each degree, and mode relationships. Implement pitch-class arithmetic utilities. |
| **Dependencies** | P0-T1 |
| **SDK Integration** | Pure library — no direct SDK integration. Consumed by all Phase 1 tools and the Harmony skill directory. |
| **Input Interface** | Constants/types — no runtime input. |
| **Output Interface** | `type NoteName = 'C' \| 'C#' \| 'Db' \| 'D' \| 'D#' \| 'Eb' \| 'E' \| 'F' \| 'F#' \| 'Gb' \| 'G' \| 'G#' \| 'Ab' \| 'A' \| 'A#' \| 'Bb' \| 'B'`. `type PitchClass = 0 \| 1 \| 2 \| 3 \| 4 \| 5 \| 6 \| 7 \| 8 \| 9 \| 10 \| 11`. `interface ScaleDefinition { name: string; aliases: string[]; intervals: number[]; pitchClasses: (root: PitchClass) => PitchClass[]; degreeQualities: ChordQuality[]; modes: string[]; }` — Scale types: Major, Natural Minor, Harmonic Minor, Melodic Minor, Dorian, Phrygian, Lydian, Mixolydian, Locrian, Pentatonic Major, Pentatonic Minor, Blues, Whole Tone, Diminished (HW), Diminished (WH), Chromatic, Hungarian Minor, Phrygian Dominant, Lydian Dominant, Altered, Bebop Dominant. Utilities: `noteNameToPitchClass(name: NoteName): PitchClass`, `pitchClassToNoteName(pc: PitchClass, preferSharps?: boolean): NoteName`, `midiToNoteName(midi: number): { name: NoteName; octave: number }`, `midiToPitchClass(midi: number): PitchClass`, `intervalSemitones(interval: Interval): number`, `transposeNote(note: NoteName, semitones: number): NoteName`. |
| **Testing** | All 252 root+scale combinations produce valid pitch class sets (no duplicates, correct cardinality). Enharmonic: `noteNameToPitchClass('C#') === noteNameToPitchClass('Db')`. MIDI conversion: `midiToNoteName(60) → { name: 'C', octave: 4 }`. Scale degree qualities: C major → [major, minor, minor, major, major, minor, diminished]. Pentatonic Minor intervals: [3, 2, 2, 3, 2]. All 21 scales have valid mode relationships. Cross-reference scales named in corpus: "Pentatonic Minor" (Godly), "Major" (Neo Soul 1), "Natural Minor" (Classic House) — all must exist in library. |
| **Risk** | Enharmonic spelling ambiguity is the primary risk. "F#" vs "Gb" depends on key context. The `preferSharps` parameter handles this, but downstream consumers must pass context correctly. MPC Beats uses inconsistent sharp/flat spelling across files. |

---

### P1-T2: Chord Symbol Parser

| Field | Value |
|---|---|
| **Complexity** | M |
| **Description** | Parse arbitrary chord symbol strings into structured representations. Must handle every chord name found in the 47 progression files plus standard jazz/pop notation. This is a critical dependency — used by the Roman numeral analyzer, voicing engine, transposition, and substitution tools. |
| **Dependencies** | P1-T1 (pitch class utilities) |
| **SDK Integration** | Pure library. No direct SDK call. |
| **Input Interface** | `function parseChordSymbol(symbol: string): ParsedChordSymbol` |
| **Output Interface** | `interface ParsedChordSymbol { root: NoteName; quality: ChordQuality; intervals: number[]; extensions: ChordExtension[]; alterations: ChordAlteration[]; bassNote?: NoteName; isSuspended: boolean; isSlashChord: boolean; pitchClasses: PitchClass[]; displaySymbol: string; }` — `type ChordQuality = 'major' \| 'minor' \| 'diminished' \| 'augmented' \| 'dominant' \| 'half_diminished' \| 'sus2' \| 'sus4' \| 'power' \| 'major7' \| 'minor7' \| 'dominant7'` — `type ChordExtension = '7' \| 'maj7' \| '9' \| 'maj9' \| '11' \| '13' \| '6' \| 'add9' \| 'add11'` — `type ChordAlteration = '#5' \| 'b5' \| '#9' \| 'b9' \| '#11' \| 'b13'`. Parser must handle regex alternation for quality indicators: `m`, `min`, `-` for minor; `M`, `maj`, `Δ` for major 7th; `°`, `dim` for diminished; `ø`, `m7b5` for half-diminished; `aug`, `+` for augmented; `sus2`, `sus4` for suspended. |
| **Testing** | Exhaustive: harvest every unique chord name from all 47 progression files (run extraction script). Parse 100% of them — zero failures. Corpus chord names verified: "Em", "Em7/D", "B/F#", "B7/D#", "Amaj9", "Emaj7/G#", "Em6/G" (Neo Soul 1 chords of 6), "Badd9/F#", "Bm7/D", "F#m9", "Bmaj7", "Bmaj9", "Emaj9/G#", "Bmaj9/F#", "Dmaj9", "F#m7", "Am7", "D7", "D7/F#", "A7", "A7/C#", "F#7/F", "F#/E", "F#/Eb", "Em7/A", "Fmaj7/A", "Bm7/A", "Am9", "Dm7/A", "Gmaj9", "Fmaj9", "Cmaj9", "A#maj9", "A7" — all parsed correctly. Pitch class verification: `parseChordSymbol("Cmaj7").pitchClasses → [0,4,7,11]`. `parseChordSymbol("Em").pitchClasses → [4,7,11]`. Slash chord: `parseChordSymbol("B/F#").bassNote → "F#"`. Edge case: "F#7/F" — bassNote should be "F" (likely E# enharmonically, but parse literally). |
| **Risk** | High ambiguity. "Badd9/F#" — is root B-major with add9 and F# bass? Yes. "A#maj9" — A-sharp major 9, not A-sharp-maj-9. Parser must be greedy for root extraction (try two-char roots first: A#, Bb, C#, Db, etc.). |

---

### P1-T3: Roman Numeral Analyzer

| Field | Value |
|---|---|
| **Complexity** | L |
| **Description** | Given a `RawProgression`, compute Roman numeral analysis for each chord relative to the detected key center. Handle diatonic chords (direct scale degree mapping), borrowed chords (modal interchange), secondary dominants (V/x), and Neapolitan/augmented-6th chords. Must handle discrepancies between the stated `rootNote`+`scale` and the actual chords present. |
| **Dependencies** | P1-T1 (scale library), P1-T2 (chord symbol parser) |
| **SDK Integration** | Core of the `analyze_harmony` tool. Output populates `EnrichedProgression.analysis.romanNumerals`. |
| **Input Interface** | `function analyzeRomanNumerals(progression: RawProgression, keyOverride?: KeyCenter): RomanNumeralAnalysis` |
| **Output Interface** | `interface RomanNumeralAnalysis { romanNumerals: string[]; keyCenter: KeyCenter; borrowedChords: Array<{ index: number; borrowedFrom: string }>; secondaryDominants: Array<{ index: number; target: string }>; modulationPoints: Array<{ index: number; fromKey: string; toKey: string }>; diatonicPercentage: number; }`. Roman numeral format: uppercase = major quality, lowercase = minor, ° = diminished, + = augmented, superscript extensions (represented as inline text: "V7", "ii9", "♭VII"). Slash chords rendered as "V/♭VII" for secondary function or "i7/♭VII" for inversion with bass degree. |
| **Testing** | Godly (E Pentatonic Minor): first 4 chords → i, i7/♭VII (or i7 with ♭7 bass), V/♯ii?, V7/♯vii? — verify exact Roman numerals. Cross-reference all 47 progressions with human-audited subset. Classic House (A Natural Minor): Em7/A → v7 (with pedal), Fmaj7/A → ♭VI^maj7, Am7 → i7, etc. Key center detection: Godly's stated key "E Pentatonic Minor" should resolve to E minor with high confidence. Neo Soul 1 stated key "B Major" — verify diatonic percentage and flag borrowed chords (Em6 is borrowed from B minor). Secondary dominant detection: Godly's D7/F# should be flagged as V/V (secondary dominant of V). |
| **Risk** | Key detection confidence for ambiguous progressions (e.g. classic major/relative minor ambiguity). Some progressions may have modulations — need to detect key center changes within the progression. The Krumhansl-Kessler profile correlation approach handles this but needs segmented analysis for long progressions. |

---

### P1-T4: Voice Leading Engine

| Field | Value |
|---|---|
| **Complexity** | M |
| **Description** | Analyze voice leading between consecutive chords in a progression. Compute total semitone movement, common tone retention, parallel motion detection, voice crossing, and per-voice motion types (oblique, similar, contrary, parallel). Use minimum-cost matching (Hungarian algorithm) for optimal voice assignment when chord sizes differ. |
| **Dependencies** | P1-T1 |
| **SDK Integration** | Populates `EnrichedProgression.analysis.voiceLeading` and `voiceLeadingDistances`/`commonToneRetention` arrays. |
| **Input Interface** | `function analyzeVoiceLeading(chords: RawChord[]): VoiceLeadingAnalysis` (types from C2 contract). Also: `function computeOptimalVoiceAssignment(from: number[], to: number[]): VoiceAssignment` — `interface VoiceAssignment { pairings: Array<{ fromNote: number; toNote: number; movement: number }>; enteringVoices: number[]; leavingVoices: number[]; totalMovement: number; }` |
| **Output Interface** | `VoiceLeadingAnalysis` (from C2 contract). |
| **Testing** | Godly: Em [52,59,64,67] → Em7/D [50,59,62,67]: total movement should be ~7 semitones (52→50=2, 59→59=0, 64→62=2, 67→67=0... but 64→62 is 2). Neo Soul 1 chromatic bass: first 4 chords bass notes 45→44→43→42 — analyzer should detect single-voice chromatic descent. Parallel fifths/octaves: verify zero false positives across all 47 professionally-authored progressions. Variable-length chords: Neo Soul 1 chord 9 has 9 notes while chord 8 has 5 — verify entering voices correctly identified. Smoothness score: Godly should score higher than a randomly shuffled chord order. Hungarian algorithm correctness: verify against brute-force for small (≤5 voice) cases. |
| **Risk** | Hungarian algorithm implementation complexity — consider using an npm package like `munkres-js`. Performance: O(n³) per chord pair — with max 9 voices, this is ≤729 operations, trivially fast. Voice matching heuristic may not match human expectation in all cases — the "nearest note" approach sometimes disagrees with functional voice assignment. |

---

### P1-T5: Tension Function Implementation

| Field | Value |
|---|---|
| **Complexity** | L |
| **Description** | Implement the tension formula: $T_{chord} = w_r \cdot R + w_s \cdot (1-S) + w_d \cdot D + w_c \cdot C$ where R=roughness (interval dissonance), S=stability (Krumhansl key profile), D=density (note count), C=contextual surprise (distance from previous chord). Genre-dependent weights. |
| **Dependencies** | P1-T1 (pitch class utilities), P1-T3 (key center for stability calculation) |
| **SDK Integration** | Populates `EnrichedProgression.analysis.tensionValues[]` and `ChordInstance.tension` in SongState. Exported for Phase 3 (harmonic-rhythmic interaction), Phase 8 (creativity dials). |
| **Input Interface** | `function computeTension(chord: number[], key: KeyCenter, previousChord?: number[], genre?: GenreId): TensionResult` — `interface TensionWeights { roughness: number; stability: number; density: number; contextual: number; }` |
| **Output Interface** | `interface TensionResult { total: number; components: { roughness: number; stability: number; density: number; contextual: number; }; weights: TensionWeights; }`. Roughness lookup table: `const INTERVAL_ROUGHNESS: Record<number, number> = { 0: 0.0, 1: 1.0, 2: 0.5, 3: 0.2, 4: 0.15, 5: 0.05, 6: 0.8, 7: 0.05, 8: 0.15, 9: 0.2, 10: 0.5, 11: 1.0 }` (indexed by interval in semitones mod 12). Krumhansl-Kessler major profile: `[6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]`. Minor profile: `[6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]`. Default weight sets: `classical: { r:0.3, s:0.3, d:0.1, c:0.3 }`, `pop: { r:0.2, s:0.4, d:0.1, c:0.3 }`, `neo_soul: { r:0.25, s:0.25, d:0.2, c:0.3 }`. |
| **Testing** | Reproduce blueprint Godly analysis: Em (notes [52,59,64,67]) → T≈0.073, Em7/D ([50,59,62,67]) → T≈0.153, B/F# ([54,59,63,66]) → T≈0.367 (within ±0.05 tolerance). Verify monotonic tension increase for Godly's first 3 chords. I→IV→V→I in C major should produce: low→medium→medium-high→very-low pattern. Pure unison [60,60,60] → roughness = 0.0. Dense 9-note chord → density near 1.0. First chord (no previous) → contextual = 0.0. Genre weight verification: same chord produces different tension in "jazz" vs "pop" weight set — jazz emphasizes roughness more. |
| **Risk** | Calibration: the blueprint's example values were estimates. Need empirical tuning against "felt tension" across the real 47 progressions. The tension function is a scoring heuristic, not ground truth — communicate this via JSDoc. Stability (S) computed via Pearson correlation with key profile — ensure negative correlations map to low stability, not high. |

---

### P1-T6: Chord-to-MIDI Voicing Engine

| Field | Value |
|---|---|
| **Complexity** | XL |
| **Description** | Given a chord symbol and voice-leading context (previous voicing, target register, genre), generate an optimal MIDI note array (voicing). This is the generative heart of the progression engine — it turns abstract chord symbols into playable notes. Handles open/close voicing, register constraints, minimum voice spacing, and anti-parallel-fifths. |
| **Dependencies** | P1-T1, P1-T2 (chord parser provides pitch class set), P1-T4 (voice leading scoring) |
| **SDK Integration** | Called by `generate_progression` tool (produces voicings for LLM-generated chord sequences), `transpose_progression` tool (re-voices after transposition). |
| **Input Interface** | `function voiceChord(request: VoicingRequest): VoicingResult` — `interface VoicingRequest { chordSymbol: string; previousVoicing?: number[]; registerRange?: { low: number; high: number }; voicingStyle?: 'close' \| 'open' \| 'drop2' \| 'drop3' \| 'spread'; genre?: GenreId; minVoiceSpacing?: number; maxVoiceSpacing?: number; }` |
| **Output Interface** | `interface VoicingResult { midiNotes: number[]; score: number; voicingStyle: string; voiceLeadingMovement: number; alternativeVoicings: Array<{ midiNotes: number[]; score: number }>; }`. Scoring function: `score = α·voiceLeadingSmoothness + β·registerComfort + γ·spacingBalance − δ·parallelFifthPenalty`. Default register range: `{ low: 48 (C3), high: 84 (C6) }`. Default min voice spacing: 2 semitones (close), 5 semitones (open). |
| **Testing** | "Cmaj7" close voicing in C4 range → [60,64,67,71]. "Cmaj7" open voicing → [48,64,67,71] or similar with wide spacing. Voice leading test: voice "Dm7" → "G7" → "Cmaj7" and verify total movement ≤ 10 semitones across the cadence. Genre test: "neo_soul" + "Ebm9" → open voicing with spread > 15 semitones. "pop" + "C" → tight close voicing. Drop-2 voicing: "Cmaj7" → second-from-top voice dropped an octave → [55,60,64,71]. Anti-parallel: voice two chords → verify no parallel 5ths in output. Register enforcement: voicing output notes all within `registerRange`. Performance: voice 100 chord symbols in < 100ms. Alternative count: always return ≥2 alternatives. Round-trip: voice all chords from Godly → compare with original notes → voice leading distance should be small. |
| **Risk** | High. Combinatorial explosion for large chords (9 notes = huge search space). Must prune candidate space aggressively. The scoring function weights need empirical tuning. Drop voicings with many extensions (e.g., 13th chords) have non-obvious voicing rules that vary by genre. Edge case: power chords (only root + fifth) need special handling — no quality indicator. |

---

### P1-T7: Enriched Progression Generator (Assembly)

| Field | Value |
|---|---|
| **Complexity** | M |
| **Description** | Orchestrate P1-T1 through P1-T5 into the full `EnrichedProgression` pipeline: parse → chord symbols → key detection → Roman numerals → voice leading → tension → genre association → pattern detection. Replace the Phase 0 `read_progression` tool with this enriched version. Implement the `analyze_harmony` tool. |
| **Dependencies** | P1-T1, P1-T2, P1-T3, P1-T4, P1-T5 |
| **SDK Integration** | Registers `analyze_harmony` tool via `defineMuseTool()`. Upgrades `read_progression` tool to return enrichment at L1/L2 detail on request. Populates `skills/harmony/` skill directory. |
| **Input Interface** | `function enrichProgression(parsed: ParsedProgressionResult): Promise<EnrichedProgression>` — also: `analyze_harmony` tool params: `z.object({ filePath: z.string().optional(), chords: z.array(z.string()).optional(), key: z.string().optional(), depth: z.enum(['L1','L2']).default('L1') })` |
| **Output Interface** | Full `EnrichedProgression` (C2 contract). `analyze_harmony` tool returns formatted text: Roman numerals, tension values, voice leading summary, genre associations, detected patterns, top 3 substitution suggestions. L1 format (~150 tokens): chord symbols + Roman numerals + key + genre. L2 format (~500 tokens): adds tension values, voice leading distances, pattern descriptions. |
| **Testing** | Enrich all 47 progressions — zero crashes. Verify Godly: genre="Gospel", keyCenter.root="E", keyCenter.mode="minor", romanNumerals.length=16, tensionValues.length=16, genreAssociations includes "Gospel". Classic House: keyCenter.root="A", mode="minor", complexity < Godly.complexity. Neo Soul 1: chromaticism > 0.5, complexity > 0.7, genreAssociations includes "Neo Soul". Pattern detection: Godly should detect "chromatic_bass_descent" in chords 12-15 (F#→F→E→Eb in bass). Neo Soul 1 should detect "chromatic_bass_descent" in chords 0–3 (bass 45→44→43→42). Cache test: enrich same file twice → second call returns cached result (content hash match). |
| **Risk** | Enrichment performance: all analyses combined must complete in < 2 seconds per progression (most is O(n²) where n ≤ 16 chords — trivially fast). Pattern detection may produce false positives if thresholds are too loose — tune conservatively. |

---

### P1-T8: Harmony Agent Configuration & Skill Directory

| Field | Value |
|---|---|
| **Complexity** | S |
| **Description** | Create the `skills/harmony/` directory with SKILL.md, theory-reference.md, voicing-rules.md, and genre-dna.json. Define the Harmony `customAgent` configuration object for the SDK, including the agent-specific system prompt grounded in the actual corpus. Implement the `GenreDNAVector` system (C8 contract) with 25+ genre definitions and the interpolation/fusion algorithm. |
| **Dependencies** | P1-T1 through P1-T7 (all content available) |
| **SDK Integration** | `customAgents: [{ name: 'harmony', displayName: 'Harmony Agent', description: '...', prompt: buildHarmonyAgentPrompt(), tools: ['read_progression', 'analyze_harmony', 'generate_progression', 'transpose_progression', 'suggest_substitution', 'get_genre_dna', 'blend_genres'], infer: true }]`. `skillDirectories: ['./skills']` — SDK auto-discovers `skills/harmony/SKILL.md`. |
| **Input Interface** | Static configuration + `function buildHarmonyAgentPrompt(): string` — concatenates (1) theory expertise persona, (2) condensed theory reference (~2000 tokens), (3) corpus grounding ("You have access to 47 real progressions. The Godly progression demonstrates gospel chromatic bass descent..."), (4) behavioral rules (always explain reasoning, always call tools for data, never hallucinate preset names). Genre DNA: `function getGenreDNA(genre: GenreId): GenreDNAVector`, `function blendGenres(sources: Array<{ genre: GenreId; weight: number }>): GenreFusionResult`. |
| **Output Interface** | Files: `skills/harmony/SKILL.md`, `skills/harmony/theory-reference.md`, `skills/harmony/voicing-rules.md`, `data/genre-dna.json`. GenreDNA registry: all 25+ genres populated with empirically-derived vectors. Fusion result includes suggested tempo (weighted midpoint of tempo ranges), description string, and the interpolated vector. |
| **Testing** | Verify SKILL.md parses as valid markdown. Theory reference ≤ 2000 tokens. Genre DNA: all 25+ entries have all 10 dimensions populated. Vector validation: all values in [0,1] for normalized dims, valid BPM ranges for tempoRange. Fusion: `blend([{neo_soul, 0.7}, {house, 0.3}])` → chordComplexity ≈ 0.685 (0.85*0.7 + 0.3*0.3). Corpus-derived verification: compute actual complexity/chromaticism for all Gospel progressions → verify Geneva DNA chordComplexity matches within ±0.1. Integration: start session → ask "What key is Godly in?" → verify routes to Harmony agent → calls `read_progression` + `analyze_harmony` → response mentions E minor and gospel characteristics. |
| **Risk** | Low. This is assembly/configuration work. Risk: Harmony agent prompt too long and consuming excessive context window — budget carefully, keep under 3000 tokens total. |

---

## PHASE 2 — EMBEDDINGS & SEMANTIC SEARCH

**Goal**: Local vector embedding index over all MPC Beats assets. Natural-language semantic search. All inference local via ONNX Runtime.

**Task Count**: 7
**Estimated Effort**: 3–4 dev-weeks

---

### P2-T1: Asset Description Catalog — Progressions & Arp Patterns

| Field | Value |
|---|---|
| **Complexity** | M |
| **Description** | Author rich natural-language descriptions for all 47 progression files and all 80 arp pattern MIDI files. Progressions use Phase 1 enrichment (genre, key, complexity, tension arc, harmonic patterns) as input. Arp patterns use Phase 0 analysis (density, pitch range, velocity, rhythmic grid). Output as structured JSON catalogs for embedding. |
| **Dependencies** | P0-T4 (progression parser), P0-T3 (arp pattern scanner), P1-T7 (enriched progression) |
| **SDK Integration** | Catalogs stored in `data/descriptions/progressions.json` and `data/descriptions/arp-patterns.json`. Referenced by embedding pipeline (P2-T5). Also usable as skill knowledge in `skills/sound/`. |
| **Input Interface** | `function generateProgressionDescription(enriched: EnrichedProgression): AssetDescription` and `function generateArpDescription(pattern: ParsedArpPattern): AssetDescription` — `interface AssetDescription { id: string; name: string; description: string; tags: string[]; metadata: Record<string, unknown>; }` |
| **Output Interface** | Progression description template: `"{genre} progression in {key} {mode}. {chordCount} chords with {complexity_adj} harmonic complexity. Features {patterns}. Tension arc: {tensionArc}. Voice leading: {smoothness_adj}. Evokes {emotional_quality}. Suitable for {use_cases}. Similar styles: {genreAssociations}."` (~50–100 words). Arp description template: `"{category} arp pattern in {genre} style. {density_adj} note density ({density:.1f} notes/beat) at {rhythmicGrid}th note resolution. Pitch range: {pitchRange.span} semitones. Velocity: {velocity_adj}. Character: {character_adjectives}. Suitable for {use_cases}."` (~30–60 words). Adjective derivation: density > 4 → "busy, driving"; density < 2 → "sparse, breathing"; pitchRange > 12 → "expansive"; velocityStddev > 15 → "dynamic, expressive"; velocityStddev < 5 → "mechanical, steady". |
| **Testing** | All 47 progressions have descriptions ≥ 40 words and ≤ 150 words. All 80 arp patterns have descriptions ≥ 30 words. No empty tags arrays. Godly description includes: "Gospel", "E", "minor", "chromatic", "devotional" or synonyms. Neo Soul 1 description includes: "Neo Soul", "B", "major", "chromatic bass descent". Arp 044 (Melodic-Lead Hip Hop 01): description includes "Hip Hop", "melodic". Tags are lowercase and hyphenated (standard search format). |
| **Risk** | Description quality is the #1 determinant of embedding search quality. Algorithmic descriptions may be too formulaic — consider LLM-assisted description generation for the 47 progressions (more unique/creative language). Arp descriptions are more safely algorithmic since the sonic character is abstract without audio. |

---

### P2-T2: Asset Description Catalog — Presets & Effects

| Field | Value |
|---|---|
| **Complexity** | L |
| **Description** | Author descriptions for all synth presets (~298 TubeSynth + Bassline + Electric + DrumSynth variants + VST instruments) and all ~60+ effect plugins. Presets are described from filename/category only (binary .xpl not parsed). Effects are described from directory names + music production knowledge. |
| **Dependencies** | P0-T3 (asset scanner for inventory) |
| **SDK Integration** | Catalogs stored in `data/descriptions/presets.json` and `data/descriptions/effects.json`. Loaded into `skills/sound/preset-catalog.json`. |
| **Input Interface** | Preset: `function generatePresetDescription(entry: PresetEntry, engine: string): AssetDescription` — Effect: `function generateEffectDescription(effect: EffectPluginManifest): AssetDescription` |
| **Output Interface** | Preset description template (20–40 words): `"{engine} {category}: {name}. {timbral_character}. Suitable for {use_cases}. Genre affinity: {genres}."` — Timbral character derived from naming conventions and category: category="Pad" → "Sustained, atmospheric, background texture"; "Lead" → "Monophonic, cutting, designed for melody"; "Bass" → "Low-frequency, foundational"; "Pluck" → "Short attack, percussive decay"; "FX" → "Sound design, risers, transitions"; "Synth" → "Polyphonic, versatile"; "Organ" → "Hammond-style, warm, rotary". Name-to-adjective mapping: "Warm" → warm, "Bright" → bright, "Analog" → warm+vintage, "Digital" → clean+modern, "Super" → thick+wide, "Sub" → deep+sub-frequency, "Acid" → squelchy+resonant, "Dirty" → distorted+gritty. Effect descriptions (30–60 words each): include what it does sonically, when to use it, genre associations. Character effects: SP1200 → "12-bit sampler emulation, lo-fi grit, aliasing warmth, boom-bap classic", MPC60 → "Vintage warmth, J Dilla swing character, sample-based production", MPC3000 → "90s grit, punchy sample processing, golden-era hip-hop". |
| **Testing** | All presets have descriptions with ≥ 15 words. TubeSynth: 298 entries. All effects have descriptions with ≥ 25 words. Category alignment: all "Pad-*" presets tagged "pad". All "Bass-*" tagged "bass". No description contains parameter values (legal risk — describe character not implementation). Effect families: Compressor Opto → family "compressor", AIR Reverb → "reverb", SP1200 → "character". VST instruments described at engine level: "DB-33: Hammond B3 organ emulation, warm drawbar tones, rotary speaker simulation." |
| **Risk** | Largest catalog task. 400+ descriptions to author. Risk of low-quality or repetitive descriptions degrading search quality. Mitigation: use templated generation with name-derived adjectives, then review a random 10% sample. The inability to parse .xpl means descriptions are educated guesses about sonic character — acceptable for search but not for precise parameter documentation. |

---

### P2-T3: ONNX Runtime Integration & Tokenizer

| Field | Value |
|---|---|
| **Complexity** | L |
| **Description** | Set up `onnxruntime-node` to run `all-MiniLM-L6-v2` sentence transformer locally. Implement the full inference pipeline: text → tokenization (WordPiece) → ONNX model inference → mean pooling → L2 normalization → 384-dim Float32Array. Bundle or lazy-download the ~80MB ONNX model file. Implement the WordPiece tokenizer using the model's bundled vocabulary. |
| **Dependencies** | P0-T1 (project setup) |
| **SDK Integration** | No direct SDK integration — pure embedding infrastructure. Called by search tool (P2-T6) and index builder (P2-T5). Loaded eagerly in `hooks.onSessionStart` to hide cold-start latency. |
| **Input Interface** | `class EmbeddingService { constructor(modelPath: string); initialize(): Promise<void>; embed(text: string): Promise<Float32Array>; embedBatch(texts: string[]): Promise<Float32Array[]>; get isReady(): boolean; dispose(): void; }` |
| **Output Interface** | `Float32Array` of length 384, L2-normalized (norm ≈ 1.0 ± 1e-6). Tokenizer: `class WordPieceTokenizer { constructor(vocabPath: string); tokenize(text: string, maxLength?: number): TokenizerOutput; }` — `interface TokenizerOutput { inputIds: BigInt64Array; attentionMask: BigInt64Array; tokenTypeIds: BigInt64Array; }`. ONNX session input tensors: `input_ids: [1, seqLen]`, `attention_mask: [1, seqLen]`, `token_type_ids: [1, seqLen]`. Output: `last_hidden_state: [1, seqLen, 384]` → mean pool along seqLen axis (masked by attention_mask) → L2 normalize. Model location: `data/models/all-MiniLM-L6-v2/model.onnx` + `vocab.txt`. |
| **Testing** | Determinism: `embed("hello world")` called twice → identical vectors (cosine sim = 1.0). Normalization: `||embed(x)||₂ ≈ 1.0` for any input. Semantic: `cosineSim(embed("warm pad sound"), embed("cold harsh lead")) < 0.5`. `cosineSim(embed("gospel choir"), embed("church worship music")) > 0.7`. Dimension: `embed(x).length === 384` for all inputs. Tokenizer: "[CLS] hello world [SEP]" → correct token IDs matching HuggingFace reference implementation. Max length: text > 256 tokens → truncated without error. Batch: `embedBatch(100 texts)` completes in < 5 seconds. Empty string: handled gracefully (returns zero vector or throws descriptive error). `dispose()` releases ONNX session memory. |
| **Risk** | `onnxruntime-node` native binary compatibility — test on Windows x64 specifically. Node.js version compatibility: onnxruntime-node requires Node 16+. Model file size (~80MB) — consider download-on-first-use with progress bar rather than bundling in the package. Tokenizer: must use the EXACT vocab file that matches the ONNX model — mismatched tokenizers produce garbage embeddings silently. |

---

### P2-T4: Float32Array Vector Index

| Field | Value |
|---|---|
| **Complexity** | M |
| **Description** | Implement the in-memory vector index that stores all asset embeddings and performs brute-force cosine similarity search. Includes JSON serialization/deserialization for persistence. At ~600 entries × 384 dims × 4 bytes ≈ 900KB this is trivially small for brute-force. |
| **Dependencies** | P2-T3 (embedding service for query embedding at search time) |
| **SDK Integration** | Loaded into memory on `hooks.onSessionStart`. Exposes the `search()` method consumed by the `search_assets` tool (P2-T6). |
| **Input Interface** | `class VectorIndex { constructor(model: string, dimensions: number); addEntry(entry: AssetEmbedding): void; addEntries(entries: AssetEmbedding[]): void; search(queryVector: Float32Array, topK?: number, typeFilter?: AssetType[]): SearchResult[]; getEntry(id: string): AssetEmbedding \| undefined; removeEntry(id: string): boolean; get size(): number; serialize(): SerializedEmbeddingIndex; static deserialize(data: SerializedEmbeddingIndex): VectorIndex; }` |
| **Output Interface** | `SearchResult[]` (from C7 contract) sorted by `similarity` descending. Cosine similarity computed as dot product (vectors are pre-normalized): `function dotProduct(a: Float32Array, b: Float32Array): number`. Serialization: `SerializedEmbeddingIndex` (C7 contract) — Float32Array → number[] for JSON compatibility. Deserialization reconstructs Float32Array from number[]. |
| **Testing** | Empty index: `search()` returns []. Single entry: `search(identicalVector)` → similarity ≈ 1.0. Orthogonal vectors: similarity ≈ 0.0. `topK=3` returns exactly 3 results when index has > 3 entries. Type filter: with type="progression", only progression entries returned. Performance: 600-entry index search < 1ms (benchmark). Serialization round-trip: `serialize → deserialize → search` produces identical results. `Float32Array precision: `serialize → deserialize` preserves vectors to 6 decimal places. `removeEntry`: reduces size by 1, removed entry no longer appears in search. |
| **Risk** | Low. This is straightforward linear algebra. Only risk: Float32Array → number[] serialization loses precision beyond ~7 significant digits — acceptable for cosine similarity. Consider using Base64-encoded binary buffers for more compact serialization if file size is a concern (would reduce from ~2MB to ~1.2MB). |

---

### P2-T5: Embedding Pipeline & Index Builder

| Field | Value |
|---|---|
| **Complexity** | M |
| **Description** | Process all description catalogs (P2-T1, P2-T2) through the embedding service (P2-T3) to build the complete `EmbeddingIndex`. Support incremental rebuilds (skip entries whose description hash hasn't changed). Persist the index to `data/embedding-index.json`. |
| **Dependencies** | P2-T1, P2-T2, P2-T3, P2-T4 |
| **SDK Integration** | Run as a build step (CLI command: `muse build-index`) and lazily on first `search_assets` call if index is missing/stale. |
| **Input Interface** | `async function buildEmbeddingIndex(catalogs: { progressions: AssetDescription[]; arps: AssetDescription[]; presets: AssetDescription[]; effects: AssetDescription[]; }, embeddingService: EmbeddingService, existingIndex?: VectorIndex): Promise<VectorIndex>` |
| **Output Interface** | Persisted `data/embedding-index.json` (~1–2MB). Build statistics: `interface IndexBuildResult { totalEntries: number; newEntries: number; cachedEntries: number; skippedEntries: number; buildTimeMs: number; indexSizeBytes: number; }`. Expected counts: ~47 progressions + ~80 arps + ~400 presets + ~60 effects + ~67 controllers = ~654 entries (controllers may be added later). Each entry has: id, type, name, description, vector[384], metadata. |
| **Testing** | Full build: all catalogs → index with correct entry count (sum of all catalog entries). Incremental: build full index → modify 1 description → rebuild → verify only 1 entry re-embedded (`newEntries=1`). Cache hit: rebuild with no changes → `newEntries=0`, build time < 1 second (no ONNX calls). Index persistence: write → read → search → results match in-memory search. Build performance: full cold build (embedding ~654 entries) < 60 seconds. Verify no duplicate IDs in output index. Verify all entries have non-zero vectors (no failed embeddings). |
| **Risk** | Cold build time (~60s for ~654 embeddings at ~10ms each) — acceptable but should show progress. If ONNX model fails to load, the entire embedding pipeline is down — implement graceful degradation (keyword-based fallback search). Description hash stability: if description templates change, all entries re-embed — expected but could be surprising for users. |

---

### P2-T6: Cross-Modal Semantic Search Engine

| Field | Value |
|---|---|
| **Complexity** | M |
| **Description** | Implement the runtime search function: embed a natural-language query, search the vector index, optionally re-rank by metadata relevance (genre match, active SongState context), and return formatted results. Supports cross-modal search (a mood query matches both progressions and presets). |
| **Dependencies** | P2-T3, P2-T4, P2-T5 |
| **SDK Integration** | Core function behind the `search_assets` tool. Can be called programmatically by other tools (e.g., Sound Oracle uses it for preset search in Phase 4). |
| **Input Interface** | `async function searchAssets(query: string, options?: SearchOptions): Promise<SearchResult[]>` — `interface SearchOptions { topK?: number; typeFilter?: AssetType[]; genre?: string; minSimilarity?: number; contextBoost?: { songState?: SongState; genreBias?: Record<string, number> }; }` |
| **Output Interface** | `SearchResult[]` (C7 contract). With `contextBoost`: raw cosine similarity is combined with a metadata relevance score: `finalScore = α·cosineSim + β·genreMatch + γ·categoryRelevance`. Default α=0.8, β=0.1, γ=0.1. Genre match: 1.0 if result genre == SongState genre, 0.5 if related, 0.0 if unrelated. Category relevance: based on query intent detection (mentions "bass" → boost bass presets). Formatted display: `"Found {n} results for \"{query}\":\n1. [{similarity:.2f}] {name} ({type}) — {description_truncated_50_words}...\n2. ..."` |
| **Testing** | Semantic search quality (golden test cases): "warm Sunday morning feeling" → Slow Praise, RhodesBallad in top 5. "aggressive trap bass" → Bass presets + Trap progressions in top 5. "80s gated reverb" → Reverb In Gate in top 3. "gospel worship chords" → Godly, Slow Praise in top 3. "jazzy walking bass line" → Bass arp patterns + Jazz progressions in top 5. "lo-fi dusty vinyl" → SP1200, MPC60, Lo-Fi effects in top 5. "bright energetic dance lead" → TubeSynth Lead presets in top 5. Type filter: `typeFilter=['progression']` → only progression results. MinSimilarity: `minSimilarity=0.5` → no results with score < 0.5. Empty query: returns empty or throws descriptive error. Context boost: with SongState.genre="neo_soul", Neo Soul progression results boosted above same-similarity non-Neo-Soul results. |
| **Risk** | all-MiniLM-L6-v2 is a general-purpose text model — it doesn't inherently understand music. The query "ii-V-I" won't match "jazz" unless descriptions bridge that gap with text. Mitigation: descriptions explicitly mention theory terms alongside natural-language descriptions. Cross-modal accuracy may be lower than single-modal — "warm" applied to a progression means harmonic warmth, but applied to a preset means timbral warmth. The descriptions must use shared vocabulary for this to work. |

---

### P2-T7: Embedding Persistence & Search Tool Registration

| Field | Value |
|---|---|
| **Complexity** | S |
| **Description** | Register the `search_assets` tool via `defineMuseTool()`, integrate the embedding index into session lifecycle (load on start, rebuild command), and handle edge cases (missing index, stale index, search failures). |
| **Dependencies** | P2-T5, P2-T6, P0-T7 (tool registration factory) |
| **SDK Integration** | Tool registration: `defineMuseTool('search_assets', { description: 'Search all MPC Beats assets using natural language...', parameters: z.object({ query: z.string().describe('Natural language search query'), type: z.enum(['progression','arp','preset','effect','all']).default('all'), topK: z.number().int().min(1).max(25).default(10), genre: z.string().optional() }), category: 'read', modifiesSongState: false, handler: async (params, ctx) => { ... } })`. Session lifecycle: `hooks.onSessionStart` → load `data/embedding-index.json` into memory (~1MB). If missing: log warning, search tool returns "Index not built yet. Run `muse build-index`." If stale (>7 days): trigger background rebuild. |
| **Input Interface** | Tool parameters (see above). |
| **Output Interface** | Tool returns formatted text for LLM consumption: `"Found {n} results for \"{query}\":\n\n1. **[{sim:.0%}]** {name} ({type})\n   {description_truncated}\n   Path: {filePath}\n\n2. ..."`. Each result includes the file path so the LLM can follow up with `read_progression` or `read_arp_pattern` for details. |
| **Testing** | E2E: create session → load index → send "Find me something that sounds like a rainy day" → verify LLM calls `search_assets` → verify results returned → verify results are musically plausible (expect ambient/melancholic progressions and pads). Missing index: tool returns helpful error, no crash. Stale index detection: mock index with old `builtAt` → verify rebuild triggered. Tool description: verify LLM tool selection — send "What presets are warm?" → should call `search_assets` with type="preset", not `list_presets`. Response format: verify results include clickable file paths. TopK enforcement: verify exactly K results returned when index has > K entries. Performance: full tool invocation (embed query + search + format) < 200ms. |
| **Risk** | Low. This is wrapper/integration work. Main risk: LLM confusion between `search_assets` (semantic/fuzzy) and `list_presets`/`list_assets` (exact/inventory) — tool descriptions must clearly differentiate: search is for "when you want to find something by mood/character/feeling", list is for "when you want to see what's available by name/category". |

---

## Phase Dependency Graph (Phases 0–2)

```
P0-T1 ─────────────────────────────────────────────────┐
  │                                                      │
  ├─→ P0-T2 (system msg)                                │
  ├─→ P0-T3 (scanner) ──────────────────────────────┐   │
  ├─→ P0-T4 (.progression parser) ──────────────┐   │   │
  ├─→ P0-T5 (.xmm parser) ─────────────────┐   │   │   │
  ├─→ P0-T6 (SongState) ──────────────┐    │   │   │   │
  │                                     │    │   │   │   │
  └─→ P0-T7 (tools) ◄─────────────────┼────┼───┼───┘   │
       │                                │    │   │       │
       └─→ P0-T8 (hooks/CLI) ◄────────┘────┘   │       │
                                                 │       │
  ┌──────────────────────────────────────────────┘       │
  │                                                      │
  ├─→ P1-T1 (theory types) ─────┐                       │
  │    │                          │                       │
  │    ├─→ P1-T2 (chord parser)──┼──┐                    │
  │    │                          │  │                    │
  │    ├─→ P1-T3 (roman) ◄──────┘──┘                    │
  │    │                                                  │
  │    ├─→ P1-T4 (voice leading)                         │
  │    │                                                  │
  │    ├─→ P1-T5 (tension)                               │
  │    │                                                  │
  │    ├─→ P1-T6 (voicing engine)                        │
  │    │                                                  │
  │    └─→ P1-T7 (enrichment assembly) ◄ P1-T3,T4,T5    │
  │         │                                             │
  │         └─→ P1-T8 (agent config + genre DNA)         │
  │                                                      │
  ├─→ P2-T1 (descriptions: progression+arp) ◄ P1-T7     │
  ├─→ P2-T2 (descriptions: preset+effect)               │
  ├─→ P2-T3 (ONNX runtime) ◄───────────────────────────┘
  │    │
  │    └─→ P2-T4 (vector index)
  │         │
  │         └─→ P2-T5 (index builder) ◄ P2-T1, P2-T2
  │              │
  │              └─→ P2-T6 (search engine)
  │                   │
  │                   └─→ P2-T7 (tool registration)
```

### Parallelization Opportunities

| Parallel Group | Tasks | Rationale |
|---|---|---|
| Phase 0 parsers | P0-T3, P0-T4, P0-T5, P0-T6 | Independent data domains. All depend only on P0-T1. |
| Phase 1 analyzers | P1-T2, P1-T4, P1-T5 | Independent algorithms. All depend on P1-T1. |
| Phase 2 catalogs + ONNX | P2-T1, P2-T2, P2-T3 | Description authoring is independent of embedding infrastructure. |
| Phase 1 + Phase 2 ONNX | P1-* + P2-T3 | ONNX setup has zero dependency on Phase 1. Can start immediately after P0-T1. |

### Critical Path

```
P0-T1 → P0-T4 → P0-T7 → P0-T8 → P1-T1 → P1-T2 → P1-T3 → P1-T7 → P2-T1 → P2-T5 → P2-T6 → P2-T7
```

Estimated critical path duration: ~8–10 dev-weeks (single developer).
With parallelization across 2 developers: ~5–7 dev-weeks.

---

## Summary Matrix

| Task ID | Name | Complexity | Dependencies | SDK Features Used |
|---|---|---|---|---|
| **P0-T1** | Project Scaffold & SDK Bootstrap | S | — | `CopilotClient`, `CopilotSession`, `infiniteSessions` |
| **P0-T2** | System Message Template Engine | M | P0-T1 | `systemMessage: { mode: 'append' }` |
| **P0-T3** | Workspace Asset Scanner | M | P0-T1 | `hooks.onSessionStart`, MCP filesystem (optional) |
| **P0-T4** | `.progression` JSON Parser | S | P0-T1 | — (library) |
| **P0-T5** | `.xmm` XML Controller Map Parser | M | P0-T1 | — (library) |
| **P0-T6** | SongState Schema & Persistence | L | P0-T1 | `hooks.onSessionEnd`, `hooks.onPostToolUse` |
| **P0-T7** | Tool Registration Factory & Read Tools | M | P0-T1,T3,T4,T5 | `defineTool()`, `MuseToolContext` |
| **P0-T8** | Session Lifecycle Hooks & CLI | L | P0-T1,T2,T3,T6,T7 | All `hooks.*`, permission handler, CLI |
| **P1-T1** | Music Theory Types & Scale Library | M | P0-T1 | — (library) |
| **P1-T2** | Chord Symbol Parser | M | P1-T1 | — (library) |
| **P1-T3** | Roman Numeral Analyzer | L | P1-T1, P1-T2 | `analyze_harmony` tool |
| **P1-T4** | Voice Leading Engine | M | P1-T1 | — (library) |
| **P1-T5** | Tension Function | L | P1-T1, P1-T3 | — (library, exported) |
| **P1-T6** | Chord-to-MIDI Voicing Engine | XL | P1-T1, P1-T2, P1-T4 | `generate_progression` tool |
| **P1-T7** | Enriched Progression Assembly | M | P1-T1–T5 | `analyze_harmony` tool, upgrades `read_progression` |
| **P1-T8** | Harmony Agent Config & Genre DNA | S | P1-T1–T7 | `customAgents`, `skillDirectories` |
| **P2-T1** | Description Catalog: Progressions & Arps | M | P0-T3,T4, P1-T7 | — (data authoring) |
| **P2-T2** | Description Catalog: Presets & Effects | L | P0-T3 | — (data authoring) |
| **P2-T3** | ONNX Runtime & Tokenizer | L | P0-T1 | — (ML infrastructure) |
| **P2-T4** | Float32Array Vector Index | M | P2-T3 | — (library) |
| **P2-T5** | Embedding Pipeline & Index Builder | M | P2-T1–T4 | CLI command `muse build-index` |
| **P2-T6** | Cross-Modal Semantic Search | M | P2-T3, P2-T4, P2-T5 | — (library) |
| **P2-T7** | Search Tool Registration & Integration | S | P2-T5, P2-T6, P0-T7 | `defineTool()`, `hooks.onSessionStart` |

### Complexity Distribution

| Complexity | Phase 0 | Phase 1 | Phase 2 | Total |
|---|---|---|---|---|
| S | 2 | 1 | 1 | **4** |
| M | 4 | 4 | 4 | **12** |
| L | 2 | 2 | 2 | **6** |
| XL | 0 | 1 | 0 | **1** |
| **Total** | **8** | **8** | **7** | **23** |
