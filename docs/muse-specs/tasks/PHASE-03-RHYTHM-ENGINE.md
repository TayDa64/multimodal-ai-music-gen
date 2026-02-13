# Phase 3 — Rhythm Engine

## Phase Overview

**Goal**: Build the MIDI generation layer. The system can generate rhythmically correct, humanized MIDI files for drums, bass, melody, and chord parts. It can manipulate existing arp patterns, apply swing/humanization transforms, and output standard `.mid` files compatible with MPC Beats.

**Dependencies**: Phase 0 (MIDI parser, SongState), Phase 1 (harmonic context for pitch selection, tension for energy mapping)

**Exports consumed by**: Phase 5 (MIDI data for virtual port playback), Phase 6 (full pipeline MIDI generation), Phase 8 (rhythmic creativity dial), Phase 10 (real-time MIDI manipulation)

---

## SDK Integration Points

| SDK Feature | Phase 3 Usage |
|---|---|
| `defineTool()` | `generate_midi`, `humanize_midi`, `transform_arp`, `generate_drum_pattern`, `set_groove` |
| `customAgents` | Define `rhythm` agent with beat/groove specialization |
| `skillDirectories` | `skills/rhythm/` with groove templates, humanization rules, time signature reference |
| `systemMessage` (agent-level) | Rhythm agent prompt: groove expertise, per-genre swing conventions |
| Streaming (`message_delta`) | Progress updates during multi-bar generation ("Generating bass... bar 8/16") |
| `hooks.onPostToolUse` | Update SongState.tracks with generated MIDI file references |

---

## Task Breakdown

### Task 3.1 — MIDI File Writer

**Description**: Complement the Phase 0 MIDI reader with a MIDI writer that generates valid Standard MIDI Files from internal note event representations.

**Input**: `MidiNoteEvent[]` + metadata (tempo, time signature, track name)

**Output**: `.mid` file (binary, Standard MIDI File Format 1)

**Implementation Hints**:
- Use `midi-file` or `jsmidgen` npm package for SMF generation
- Format 1 (multi-track): tempo track (track 0) + note tracks (track 1+)
- Tempo track: set BPM via Set Tempo meta event, time signature via Time Signature meta event
- Note events: Note On (velocity > 0) + Note Off (velocity = 0) with correct delta-times
- Tick resolution: 480 PPQ (pulses per quarter note) — standard for most DAWs
- Must handle:
  - Multiple channels (different instruments on different channels)
  - Overlapping notes (polyphonic parts)
  - CC events (for expression, modulation)
  - Program Change events (for preset switching)
- File naming convention: `{role}_{genre}_{timestamp}.mid`

**Testing**: Write a known sequence (C major scale, quarter notes, 120 BPM), read it back with the Phase 0 parser, verify note-for-note accuracy. Open generated file in a MIDI viewer to verify visual correctness. Test polyphonic writing (chords).

**Complexity**: M

---

### Task 3.2 — Drum Pattern Generator

**Description**: Generate rhythmically correct drum patterns for any genre, time signature, and energy level. Outputs MIDI on channel 10 (GM drum map).

**Input**:
```typescript
interface DrumPatternRequest {
  genre: string;
  tempo: number;
  timeSignature: [number, number];
  bars: number;                    // 1-16
  energy: number;                  // 0-1
  swing: number;                   // 0-1
  elements: DrumElement[];         // which drum voices to include
  complexity: number;              // 0-1
  variation: "none" | "subtle" | "fill_every_4" | "fill_every_8";
}

type DrumElement = "kick" | "snare" | "closed_hh" | "open_hh" |
                   "ride" | "crash" | "tom_hi" | "tom_mid" | "tom_lo" |
                   "clap" | "rim" | "shaker" | "perc";
```

**Output**: `MidiNoteEvent[]` (channel 10) + generated `.mid` file

**Implementation Hints**:
- **GM Drum Map** (MIDI note assignments):
  - Kick: 36, Snare: 38, Rim: 37, Clap: 39
  - Closed HH: 42, Open HH: 46, Pedal HH: 44
  - Crash: 49, Ride: 51, Ride Bell: 53
  - Tom Hi: 50, Tom Mid: 47, Tom Lo: 45
- **Genre templates** (pattern skeletons):
  - **4-on-floor** (House/Techno): Kick on every beat, HH on every 8th/16th, snare on 2&4
  - **Boom-bap**: Kick on 1 and 3-and, snare on 2 and 4, HH on 8ths with swing
  - **Trap**: Sparse kick (1, occasional 3), snare on 3, rapid hi-hat rolls (32nd notes)
  - **Neo Soul/RnB**: Soft kick patterns, ghost snare hits, laid-back feel
  - **Breakbeat**: Syncopated kick, displaced snare, busy ride/hi-hat
- Energy scaling:
  - Low energy: fewer elements, lower velocity, wider spacing
  - High energy: more elements, higher velocity, fills, open hi-hats
- Complexity scaling:
  - Low: straight 8ths, predictable
  - High: 16th-note kicks, syncopation, ghost notes, metric displacement
- Fills: insert at end of 4-bar or 8-bar phrases. Fill types by genre.

**Testing**: Generate patterns for each genre template. Verify: kick on expected beats, snare on expected beats, HH density increases with energy. Verify fills appear at correct bar boundaries. Play through MIDI player to verify groove feel.

**Complexity**: L

---

### Task 3.3 — Bassline Generator

**Description**: Generate bass parts that lock with the drum pattern and follow the chord progression. Bass is the bridge between harmony and rhythm.

**Input**:
```typescript
interface BasslineRequest {
  progression: EnrichedProgression;
  genre: string;
  tempo: number;
  bars: number;
  style: BassStyle;
  density: number;           // 0-1
  octave: number;            // 1-3 (MIDI octave)
  drumPattern?: MidiNoteEvent[]; // for rhythmic alignment
}

type BassStyle = "root_notes" | "walking" | "syncopated" | "octave_jump" |
                 "pedal" | "arpeggiated" | "slap" | "sub_808";
```

**Output**: `MidiNoteEvent[]` + `.mid` file

**Implementation Hints**:
- Note selection algorithm:
  1. For each chord in progression, determine available bass notes: root, 3rd, 5th, 7th, approach tones
  2. Apply style constraints:
     - `root_notes`: play root on beat 1 of each chord
     - `walking`: chromatic/scalar approach to next chord's root
     - `syncopated`: anticipate chord changes by 8th note
     - `octave_jump`: root in two octaves alternating
     - `sub_808`: sustained root, 808-style long decay
  3. Rhythmic placement: align with kick drum pattern (if provided)
     - Bass note on or near every kick hit
     - Ghost notes between kick hits at lower velocity
  4. Velocity shape: accent on beat 1, ghost notes at 40-60% velocity
- Genre-specific behavior:
  - **Trap sub_808**: single sustained note per chord, very low octave (C1-C2)
  - **Jazz walking**: chromatic approaches, quarter note rhythm, swing
  - **House/Dance**: offbeat 8th notes, filter-heavy
  - **Neo Soul**: sparse roots with chromatic passing tones

**Testing**: Generate bassline over Godly progression. Verify: every bass note belongs to or approaches the current chord. Verify root notes appear on chord changes. Test with drum pattern alignment: bass note within 1 tick of every kick hit.

**Complexity**: L

---

### Task 3.4 — Melody/Lead Generator

**Description**: Generate melodic lead lines that work against the chord progression, respecting genre conventions for melodic density, range, and contour.

**Input**:
```typescript
interface MelodyRequest {
  progression: EnrichedProgression;
  genre: string;
  tempo: number;
  bars: number;
  range: { low: number; high: number }; // MIDI note range
  density: number;                       // notes per beat average
  contour: "ascending" | "descending" | "arch" | "wave" | "static" | "free";
  rhythmicStyle: "on_beat" | "syncopated" | "triplet" | "mixed";
}
```

**Output**: `MidiNoteEvent[]` + `.mid` file

**Implementation Hints**:
- Note selection hierarchy:
  1. **Chord tones** (strong beats): root, 3rd, 5th, 7th of current chord
  2. **Scale tones** (weak beats): other notes in the scale
  3. **Passing tones** (between beats): chromatic approaches, neighbor tones
  4. **Tension tones** (expressive): ♭9, ♯11, ♭13 — used sparingly, genre-dependent
- Contour algorithms:
  - `arch`: rise to middle, peak, descend — classic phrase shape
  - `ascending`: start low, tend upward with occasional dips
  - `wave`: sinusoidal pitch envelope
- Rhythmic placement:
  - `on_beat`: melody on beats 1 and 3; minimal syncopation
  - `syncopated`: anticipations, delayed attacks, off-beat emphasis
  - `triplet`: dotted rhythms, swing feel
- Voice-to-chord relationship: avoid doubled bass note in melody, prefer tensions (9ths, 11ths) over octave doubling
- Phrase structure: 4-bar phrases with breath (rest at phrase boundaries)

**Testing**: Generate 8-bar melody over Classic House progression. Verify: all notes on strong beats are chord tones. No notes outside the scale (unless density/genre warrants it). Verify phrase boundaries have rests.

**Complexity**: L

---

### Task 3.5 — Humanization Engine

**Description**: Apply human-feel transformations to mechanical MIDI data: velocity variation, micro-timing offsets, swing, ghost notes, and flams.

**Input**: `MidiNoteEvent[]` + humanization parameters

**Output**: Humanized `MidiNoteEvent[]`

**Parameters**:
```typescript
interface HumanizationConfig {
  // Velocity
  velocityVariance: number;       // 0-20 (standard deviation in MIDI velocity units)
  accentPattern?: number[];       // metric accent weights per beat subdivision
  
  // Timing
  swingAmount: number;            // 0-1 (0=straight, 1=full triplet swing)
  swingSubdivision: 8 | 16;      // apply swing to 8th or 16th notes
  timingVariance: number;         // 0-40ms random timing offset (Gaussian)
  globalOffset: number;           // -50 to +50ms (negative=ahead, positive=behind the beat)
  
  // Additions
  ghostNotes: boolean;
  ghostProbability: number;       // 0-1
  ghostVelocityRange: [number, number]; // [20, 40]
  flamProbability: number;        // 0-1
  flamOffsetMs: number;           // 5-20ms
  
  // Genre presets (shorthand)
  groove?: "straight" | "swing_8" | "swing_16" | "dilla" | "behind_beat" |
           "ahead_beat" | "uk_garage" | "bossa";
}
```

**Implementation Hints**:
- **Swing implementation**: For every pair of 8ths (or 16ths), delay the offbeat note by `swingAmount * (triplet_position - straight_position)` ticks
  - At swingAmount=0.67: standard jazz swing (1:2 ratio)
  - At swingAmount=0.5: light shuffle
  - At swingAmount=1.0: full dotted-8th feel
- **Dilla groove**: Non-uniform swing + timing variance of 15-40ms + velocity emphasis on offbeats. Mathematically: apply different swing ratios to different beat positions, making the feel "drunk" but intentional.
- **Behind-the-beat** (Frank Ocean, Erykah Badu): global offset +10-25ms, increasing toward phrase ends
- **UK Garage**: skippy 2-step — remove or move snare on certain beats, hi-hat pattern alternates between 8ths and 16ths irregularly
- **Velocity accent patterns** by time signature:
  - 4/4: [1.0, 0.5, 0.8, 0.5] for quarter notes; [1.0, 0.3, 0.5, 0.3, 0.8, 0.3, 0.5, 0.3] for 8ths
  - 3/4: [1.0, 0.5, 0.5] for quarters
- Ghost notes: insert at random empty 32nd-note positions with configured probability
- Flams: duplicate a note onset with -10ms offset and lower velocity

**Testing**: Humanize a mechanical 8th-note hi-hat pattern with swing=0.67. Verify offbeat notes are delayed by correct amount. Verify velocity variance: standard deviation of velocity values ≈ configured variance. Verify ghost note count is within statistical expectation.

**Complexity**: M

---

### Task 3.6 — Arp Pattern Transformer

**Description**: Take an existing arp pattern from the MPC Beats library and transform it: transpose, change timing, fit to a different chord progression, change density, reverse, mirror.

**Input**: `ParsedArpPattern` + transformation specification

**Output**: Transformed `MidiNoteEvent[]` + `.mid` file

**Transforms**:
```typescript
interface ArpTransform {
  transpose?: number;              // semitones
  fitToChords?: RawChord[];        // re-pitch notes to fit chord progression
  timeStretch?: number;            // 0.5 = half speed, 2.0 = double speed
  reverse?: boolean;               // play backward
  mirror?: boolean;                // invert pitch contour
  densityScale?: number;           // 0.5 = remove half the notes, 2.0 = double via interpolation
  velocityScale?: number;          // 0-2 multiplier
  channelRemap?: number;           // assign to different MIDI channel
}
```

**Implementation Hints**:
- **Fit to chords** (most complex transform):
  1. For each note in the arp pattern, determine its scale degree relative to the original implied root
  2. Map that scale degree to the corresponding note in the target chord
  3. If the target chord has fewer notes, wrap using modular arithmetic
  4. If more notes, distribute evenly
  5. Preserve rhythmic timing, only change pitch
- **Density scaling**:
  - Reduce: randomly remove notes, preserving the first note of each beat
  - Increase: interpolate between existing notes (add passing tones at midpoints)
- **Reverse**: reverse the array of note events, adjust delta times accordingly
- **Mirror**: reflect pitch around the median pitch of the pattern (if median is C4, C5→C3)
- Time stretch: multiply all tick values by stretch factor, adjust durations proportionally

**Testing**: Transform "025-Chord-Old School RnB 01" → transpose +5, fit to Trap 1 progression chords. Verify all notes are chord tones of the target progression. Time stretch ×2 → verify duration doubles. Reverse → verify last note is now first.

**Complexity**: M

---

### Task 3.7 — Arrangement Sequencer

**Description**: Given a set of generated MIDI parts (drums, bass, chords, melody) and a section structure, assemble them into a complete multi-track arrangement MIDI file.

**Input**: `SongState` with tracks + arrangement sections

**Output**: Multi-track `.mid` file (Format 1) with all parts sequenced per arrangement

**Implementation Hints**:
- Each section in `SongState.arrangement.sections` specifies:
  - Name, start bar, end bar, active tracks
- For each section:
  1. Time offset = startBar × ticksPerBar
  2. Copy active track MIDI events with time offset
  3. Handle track intro/outro: fade in velocity over 1 bar for sections where track enters
- Transitions between sections:
  - `build`: crescendo velocity over last 2 bars
  - `breakdown`: strip to 1-2 elements
  - `drop`: all elements enter simultaneously
  - `filter_sweep`: add CC (filter cutoff) ramp over transition period
- Multi-track assembly:
  - Track 0: Tempo map + time signature
  - Track 1: Drums (channel 10)
  - Track 2: Bass (channel 2)
  - Track 3: Chords (channel 3)
  - Track 4: Lead (channel 4)
  - Additional tracks as needed
- Total duration computation: last section's endBar × ticksPerBar

**Testing**: Build a simple arrangement: Intro (4 bars, chords only) → Verse (8 bars, all tracks) → Outro (4 bars, chords + bass). Verify correct event counts per section. Verify tracks not in a section's activeTracks list have zero events in that time range.

**Complexity**: L

---

### Task 3.8 — Chord Voicing MIDI Generator

**Description**: Take a chord progression and render it as sustained MIDI chords with proper voicing, timing, and articulation.

**Input**: `EnrichedProgression` + voicing style + rhythm pattern

**Output**: `MidiNoteEvent[]` (polyphonic chord MIDI)

**Voicing styles**:
```typescript
type ChordVoicingStyle = "block" | "arpeggiated" | "broken" | "rhythmic_stab" |
                         "sustained_pad" | "comping";
```

**Implementation Hints**:
- The progression already has MIDI notes (from the .progression file), but we may need to:
  1. Re-voice for a different register (pad vs piano vs guitar-like)
  2. Apply rhythmic pattern (block chords on 1&3 vs stabs on the and-of-2)
  3. Adjust voicing spread for the target instrument
- **Block chords**: all notes simultaneously, sustained for chord duration
- **Arpeggiated**: roll notes from bottom to top with 30-60ms offset
- **Broken**: play chord tones in a repeating pattern (1-3-5-3, 1-5-8-5)
- **Rhythmic stab**: short notes on offbeats with rests
- **Sustained pad**: very long notes, slow release, overlap between chords
- **Comping**: jazz-style rhythmic chords, syncopated, varying voicings
- Use the voicing from the .progression file as starting point, then transform

**Testing**: Render Godly progression as block chords. Verify MIDI output has correct notes matching the source. Render as arpeggiated — verify notes are staggered by 30-60ms. Render as rhythmic stabs — verify note durations are ≤ 1/8 note.

**Complexity**: M

---

### Task 3.9 — Groove Template System

**Description**: Define and manage reusable groove templates that encode genre-specific rhythmic feels as abstract timing/velocity modifiers.

**Input**: Genre name or custom groove specification

**Output**: `GrooveTemplate` object that can be applied to any MIDI part

```typescript
interface GrooveTemplate {
  name: string;
  description: string;
  swingAmount: number;
  swingSubdivision: 8 | 16;
  timingGrid: number[];           // per-subdivision timing offsets in ms
  velocityGrid: number[];         // per-subdivision velocity multipliers
  globalOffset: number;           // ms
}
```

**Implementation Hints**:
- Pre-defined templates (one per genre):
  - `straight_16`: no swing, even velocity — modern pop, EDM
  - `swing_8_light`: subtle 8th note swing (55%) — light jazz, bossa
  - `swing_8_heavy`: heavy swing (67%) — hard bop, blues
  - `swing_16_trap`: 16th note swing — modern trap hi-hats
  - `dilla`: asymmetric swing + timing drift — neo-soul, lo-fi
  - `uk_garage_2step`: remove every other snare, skippy hat — UK garage
  - `boom_bap`: medium swing, heavy kick emphasis, SP1200 timing
  - `afrobeat_12_8`: 12/8 compound meter feel over 4/4 grid
- Templates are stored in `skills/rhythm/groove-templates.json`
- Application: same as humanization engine (Task 3.5) but using template values instead of user-specified parameters

**Testing**: Apply `dilla` template to a straight 16th-note pattern. Verify timing offsets are non-uniform. Apply `swing_8_heavy` — verify offbeats are delayed by 67% of an 8th note value. Verify templates are round-trip serializable.

**Complexity**: S

---

### Task 3.10 — Energy-to-Rhythm Mapper

**Description**: Translate the composite energy function $E(t)$ from the blueprint into concrete rhythmic parameter changes across a song's timeline.

**Input**: `EnergyPoint[]` (from SongState.arrangement) + track roles

**Output**: Per-bar parameter modifiers for each track

```typescript
interface RhythmicEnergyMap {
  bars: {
    barNumber: number;
    energy: number;
    drumDensity: number;          // 0-1
    bassDensity: number;          // 0-1  
    hihatRate: 8 | 16 | 32;      // subdivision
    kickSyncopation: number;      // 0-1 syncopation amount
    ghostNoteFrequency: number;   // 0-1
    velocityCeiling: number;      // 0-127
  }[];
}
```

**Implementation Hints**:
- Map energy levels to rhythmic parameters via piecewise functions:
  - Energy 0-0.3 (low): hi-hat 8ths, kick on 1&3, no ghost notes, velocity ≤ 80
  - Energy 0.3-0.6 (medium): hi-hat 16ths, kick syncopation, some ghost notes, velocity ≤ 100
  - Energy 0.6-0.8 (high): hi-hat rolls, aggressive kick patterns, fills, velocity ≤ 120
  - Energy 0.8-1.0 (peak): everything maxed, open hi-hats, crash accents, velocity ≤ 127
- Transitions should be smooth (no sudden parameter jumps between bars unless "drop" transition)
- The harmonic-rhythmic interaction term $\delta \cdot H(t) \cdot R(t)$ means: when harmonic tension is high AND rhythmic energy is high, the combined intensity is more than additive
- This function is called by the arrangement sequencer (Task 3.7) to shape dynamics

**Testing**: Create an energy arc: [0.2, 0.2, 0.4, 0.5, 0.7, 0.8, 0.6, 0.3] over 8 bars. Verify drum density increases monotonically through bar 6 then decreases. Verify hi-hat subdivision increases from 8→16 at energy 0.4.

**Complexity**: M

---

### Task 3.11 — Rhythm Agent & Skill Directory

**Description**: Create the `skills/rhythm/` directory and define the Rhythm `customAgent`.

**Input**: Outputs from Tasks 3.1-3.10

**Output**:
- `skills/rhythm/SKILL.md`
- `skills/rhythm/humanization-rules.md`
- `skills/rhythm/groove-templates.json`
- `skills/rhythm/time-signature-ref.md`
- Rhythm agent config object

**Implementation Hints**:
- Rhythm agent prompt should include:
  - Per-genre drumming conventions (what hits where)
  - Humanization philosophy ("never flat velocity, always contextual swing")
  - Reference to available groove templates
  - Awareness of MPC Beats MIDI channel conventions
- Tools assigned to rhythm agent:
  ```
  ["generate_drum_pattern", "generate_bassline", "generate_melody",
   "humanize_midi", "transform_arp", "read_arp_pattern", "set_groove",
   "generate_chord_voicing_midi", "sequence_arrangement"]
  ```

**Testing**: Send "Create an 8-bar boom-bap drum pattern at 90 BPM" → verify routes to rhythm agent → calls generate_drum_pattern → returns MIDI file path.

**Complexity**: S

---

## Modular Boundaries

| Can develop independently | Notes |
|---|---|
| Task 3.1 (MIDI writer) | Depends only on note event types from Phase 0 |
| Task 3.2, 3.3, 3.4 (generators) | All parallel; 3.3 and 3.4 need Phase 1 harmonic context |
| Task 3.5 (humanization) | Independent algorithm |
| Task 3.6 (arp transforms) | Independent, needs Phase 0 parser output |
| Task 3.9 (groove templates) | Independent data task |
| Task 3.7 (arrangement sequencer) | Needs 3.1-3.6 as inputs |
| Task 3.10 (energy mapper) | Needs Phase 1 tension function |

**Critical path**: 3.1 → (3.2 + 3.3 + 3.4 parallel) → 3.7

---

## Cross-Phase Exports

| Export | Consumer |
|---|---|
| `writeMidiFile(events, options)` | Phase 5 (MIDI port playback), Phase 6 (pipeline output) |
| `generateDrumPattern`, `generateBassline`, `generateMelody` | Phase 6 (pipeline), Phase 10 (real-time) |
| `humanizeMidi` | Phase 6, Phase 10 |
| `transformArp` | Phase 6, Phase 8 (creative transformations) |
| `GrooveTemplate` type and templates | Phase 6, Phase 9 (per-user groove preferences) |
| `RhythmicEnergyMap` | Phase 6 (arrangement rendering) |
| `sequenceArrangement` | Phase 6 (final output) |
| Rhythm agent config | Phase 6 (multi-agent orchestration) |

---

## Risk Flags

| Risk | Severity | Description |
|---|---|---|
| MIDI timing precision | Medium | JavaScript `setTimeout` has ~4ms minimum resolution. For MIDI generation, this is a write-time issue (solved by computing ticks algebraically, not via real-time timers). Real-time playback timing is Phase 5's concern. |
| Melody generation quality | High | Melodic lines that "sound good" are extremely subjective. The generator provides raw material; the LLM should iterate on it. Quality gate in Phase 8 provides the safety net. |
| Drum pattern originality | Medium | Template-based generation can sound generic. Mitigation: stochastic variation + humanization + LLM can suggest novel patterns. |
| Bassline-to-kick alignment | Low | Algorithm is straightforward but edge cases (syncopated kick + walking bass) need careful testing. |
| Context window for long arrangements | Medium | A 64-bar arrangement with 4 tracks at full note-level detail is ~3000+ MIDI events. LLM shouldn't see all of this — use SongState L1 compression. |
