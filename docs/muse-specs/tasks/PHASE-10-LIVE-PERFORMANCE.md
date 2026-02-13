# Phase 10 — Live Performance

## Phase Overview

**Goal**: Enable real-time, interactive musical collaboration during live performance. The AI listens to incoming MIDI, detects key/mode/tempo, generates complementary parts on the fly, harmonizes live input, and adapts to performer energy. This is the capstone phase — the ultimate expression of MUSE as a musical co-performer, not just a generator.

**Dependencies**: Phase 5 (MIDI input/output, clock sync, scheduled playback — especially Task 5.8 MIDI input listener), Phase 1 (key detection, harmonic analysis), Phase 3 (rhythm/melody generation), Phase 7 (controller mapping for live use), Phase 8 (creativity dials), Phase 9 (personalization for style adaptation)

**Exports consumed by**: None (terminal phase)

---

## SDK Integration Points

| SDK Feature | Phase 10 Usage |
|---|---|
| `defineTool()` | `start_live_session`, `stop_live_session`, `set_live_mode`, `live_harmonize`, `live_generate_complement` |
| `customAgents` | All existing agents available during live mode; Composer agent orchestrates |
| `hooks.onPostToolUse` | Update live performance state after each generation |
| `infiniteSessions` | Essential — long-running live sessions with context compaction every N bars |
| `stream: true` | Streaming responses for real-time note delivery |

---

## Task Breakdown

### Task 10.1 — Real-Time MIDI Input Analyzer

**Description**: Process incoming MIDI note data in real-time to extract musical features: current key, mode/scale, tempo (if no external clock), rhythmic density, and playing energy.

**Input**: MIDI input stream from Phase 5.8 listener

**Output**: `LiveAnalysis` (continuously updated)
```typescript
interface LiveAnalysis {
  // Updated every bar (or more frequently)
  detectedKey: string | null;       // "C", "F#"
  detectedMode: string | null;      // "major", "dorian", "pentatonic-minor"
  keyConfidence: number;            // 0.0-1.0 (increases with more notes)
  detectedTempo: number | null;     // BPM if no external clock
  tempoConfidence: number;
  
  // Real-time metrics
  noteDensity: number;              // notes per beat (current window)
  velocityAverage: number;          // 0-127
  velocityRange: [number, number];  // [min, max] in window
  pitchRange: [number, number];     // [low, high] MIDI note
  pitchCenter: number;              // weighted average pitch
  
  // Pattern detection
  isChordal: boolean;               // multiple simultaneous notes → chordal
  isMelodic: boolean;               // sequential single notes → melodic
  isPercussive: boolean;            // channel 10 or low velocity variation
  
  // Energy
  energyLevel: number;             // 0.0-1.0, derived from density + velocity
  energyTrend: "rising" | "falling" | "stable";
  
  // History
  noteBuffer: MidiNote[];          // last N notes (ring buffer)
  chordBuffer: DetectedChord[];    // last N detected chords
  windowSize: number;              // analysis window in beats
}
```

**Implementation Hints**:
- Key detection algorithm:
  - Maintain pitch class histogram (12 bins) — count occurrences of each pitch class
  - Correlate with Krumhansl-Kessler key profiles (24 profiles for 12 major + 12 minor)
  - Return key with highest correlation + confidence
  - Need minimum ~7-10 notes for reliable detection
  - Update with each new note (sliding window, decay old notes)
- Tempo detection:
  - If external MIDI clock → use Phase 5.3 sync (authoritative)
  - If no clock: inter-onset interval (IOI) analysis
    - Collect onset times, compute IOI histogram
    - Peak IOI → estimate beat period → BPM
    - Requires ~8-16 onsets for reliable detection
- Energy computation:
  - `energy = 0.5 × normalize(density) + 0.3 × normalize(velocity) + 0.2 × normalize(pitchRange)`
  - Trend: compare current energy to 4-bar moving average
- Analysis window: 4 beats default, configurable 1-8 beats
- Must run in under 10ms per incoming note to maintain real-time feel

**Testing**: Send C major scale → verify key detection = C major. Send syncopated rhythm → verify tempo detection within ±5 BPM. Send crescendo → verify energyTrend = "rising".

**Complexity**: XL

---

### Task 10.2 — Live Harmonizer

**Description**: Given a live melodic input and detected key, generate harmony notes in real-time: parallel thirds, sixths, countermelody, or chord pad accompaniment.

**Input**: `LiveAnalysis` + incoming MIDI notes + harmonization mode

**Output**: MIDI notes sent to virtual output in real-time

**Implementation Hints**:
- Harmonization modes:
  - **Parallel thirds**: Add note 3rd above (diatonic) — always safe
  - **Parallel sixths**: Add note 6th above — warmer, more open
  - **Counter-melody**: Generate a complementary line moving in contrary motion
  - **Chord pad**: Detect implied chord from melody, sustain full chord voicing
  - **Octave doubling**: Simple but effective — double melody 1 or 2 octaves below
- Real-time constraints:
  - Must output harmony note within 5ms of input note arrival
  - Parallel intervals: trivial — lookup scale degree, add interval
  - Counter-melody: harder — needs look-ahead or responds lazily (acceptable for music)
  - Chord pad: detect chord change only on strong beats, sustain between changes
- Scale-aware intervals:
  - Must use diatonic intervals (not chromatic) for parallel harmonization
  - If key = C major and input = E, third above = G (not G#)
  - Requires real-time key detection from Task 10.1
- Voice leading between harmony notes:
  - Avoid leaps > octave in harmony voice
  - Prefer stepwise motion when possible
  - Handle scale tones vs. chromatic passing tones
- Edge cases:
  - Key not yet detected (< 7 notes): output octave doubling only (always safe)
  - Key change mid-performance: detect and adapt within 2 beats
  - Dissonant input note against detected key: pass through without harmony (avoid compounding dissonance)

**Testing**: Play C major melody → verify harmony notes are diatonic thirds above. Play in D minor → verify correct diatonic intervals. Verify latency < 5ms per note.

**Complexity**: L

---

### Task 10.3 — Complementary Part Generator

**Description**: During live performance, generate complementary musical parts that respond to the performer's input — e.g., auto-bass,  auto-drums, or auto-comping.

**Input**: `LiveAnalysis` + SongState + desired complementary part type

**Output**: Continuous MIDI output on separate channels/ports

**Implementation Hints**:
- Complementary part types:
  - **Auto-bass**: Generate bass line following detected chords
    - Root notes on beat 1 and 3
    - Walking bass pattern between roots
    - Adapt to energy: low energy → whole notes, high energy → eighth notes
  - **Auto-drums**: Generate drum pattern matching detected tempo + energy
    - Start with simple kick-snare
    - Add hi-hats as energy increases
    - Add fills at phrase boundaries (every 4 or 8 bars)
  - **Auto-comping**: Chord pad accompaniment following detected harmony
    - Sustained chords with rhythm matching performer's energy
    - Voice leading between chords
  - **Auto-counter**: Melodic counterpoint responding to performer
    - Contrary motion preference
    - Rhythmic complementarity (play in gaps)
- Generation timing:
  - Quantize output to the nearest beat subdivision (16th note grid)
  - Use Phase 5.4 scheduled event player for timing accuracy
  - Buffer: pre-generate 1-2 bars ahead, adjust on the fly
- Adaptation:
  - Energy tracking drives density/complexity
  - Key changes → re-calculate bass notes, chord voicings
  - Tempo changes → regenerate drum pattern
- Channel separation:
  - Live input: channel 1
  - Auto-bass: channel 2
  - Auto-drums: channel 10
  - Auto-comping: channel 3
  - Auto-counter: channel 4

**Testing**: Play melody in C major → verify auto-bass follows with C root. Increase playing density → verify drums add complexity. Change key to G major → verify bass adapts.

**Complexity**: XL

---

### Task 10.4 — Live Session Manager

**Description**: Orchestrate the start, configuration, and stop of live performance sessions.

**Input**: User commands ("start live session", "stop", "add auto-drums")

**Output**: Session lifecycle management

**Implementation Hints**:
- Session lifecycle:
  ```
  1. START: "Let's jam"
     - Detect available MIDI input port
     - Open MIDI output port (virtual)
     - Initialize LiveAnalysis with empty buffers
     - Set default mode (harmonize in thirds)
     - Confirm: "Live session started. Playing through [port name]. I'm listening and ready to harmonize."
  
  2. CONFIGURE: "Add auto-bass", "Switch to sixths", "Stop drums"
     - Toggle complementary parts on/off
     - Switch harmonization mode
     - Adjust energy sensitivity
  
  3. PERFORM: (continuous)
     - MIDI input → LiveAnalysis → Harmony/Complement → MIDI output
     - Periodic status: "Key: C major (95% confident) | Tempo: 92 BPM | Energy: 0.7 ↑"
  
  4. STOP: "Stop", "End session"
     - Stop all output
     - Close ports
     - Summary: "Session lasted 12 minutes. You played in C major at ~92 BPM. I generated 4 bars of auto-bass and 12 bars of harmonized thirds."
     - Option: "Want me to save this session as a starting point for a composition?"
  ```
- State machine:
  - IDLE → STARTING → LISTENING → PERFORMING → STOPPING → IDLE
  - Error states: DISCONNECTED (port lost), RECONFIGURING
- Integration with `infiniteSessions`:
  - Live sessions can be very long — compact context every 32 bars
  - Preserve key/tempo/energy history but drop individual note events

**Testing**: Start session → verify ports opened. Send MIDI notes → verify analysis begins. Stop session → verify ports closed and summary generated.

**Complexity**: L

---

### Task 10.5 — Performance Energy Mapper

**Description**: Map performer energy (detected from playing dynamics) to system behavior, creating a responsive musical experience.

**Input**: `LiveAnalysis.energyLevel` + `LiveAnalysis.energyTrend`

**Output**: Dynamic parameter adjustments for all active generators

**Implementation Hints**:
- Energy → parameter mapping:
  | Energy Level | Drums | Bass | Harmony | Effects |
  |---|---|---|---|---|
  | 0.0-0.2 | Kick only, quarter notes | Whole notes on root | Pads, sustained | Heavy reverb |
  | 0.2-0.4 | Add hi-hat | Half notes, 5ths | Block chords | Moderate reverb |
  | 0.4-0.6 | Full kit, eighth notes | Quarter notes, walking | Comping rhythm | Balanced |
  | 0.6-0.8 | Add ghost notes, fills | Eighth notes, chromatic runs | Syncopated comping | Chorus, delay |
  | 0.8-1.0 | Double-time, complex fills | Sixteenth notes, slap | Dense voicings, moving | Overdrive, distortion |
- Transition smoothing:
  - Don't jump between energy levels — interpolate over 2-4 beats
  - Respect musical phrase boundaries when possible (change at bar line)
- "Push-pull" dynamics:
  - If performer drops energy → system drops too (supportive)
  - Option: "contrarian mode" — system does the opposite (drives tension)
- Hysteresis: require energy to cross threshold by > 0.1 before changing level (avoid flicking between states on borderline values)

**Testing**: Low velocity playing → verify sparse drum pattern. Build to high velocity → verify progressive complexity increase. Sudden drop → verify system follows within 2 beats.

**Complexity**: M

---

### Task 10.6 — Phrase Boundary Detection

**Description**: Detect musical phrase boundaries in real-time input to align generated responses with natural musical structure.

**Input**: `LiveAnalysis` note buffer + timing data

**Output**: Phrase boundary events

**Implementation Hints**:
- Boundary indicators:
  - **Rest**: Silence > 1 beat → likely phrase boundary
  - **Register shift**: Large interval leap (> octave) → new phrase
  - **Rhythmic cadence**: Long note after series of short notes → phrase ending
  - **Harmonic cadence**: Detected chord returns to I or V
  - **Repetition**: Pattern repeats → phrase boundary between repetitions
- Uses:
  - Align drum fills with phrase boundaries
  - Trigger chord changes at phrase starts
  - Place complementary part variations at phrase changes
  - Context compact: remember phrase-level summary, not note-level detail
- Quantize detected boundaries to nearest strong beat (beat 1 or beat 3)
- Confidence-weighted: high-confidence boundaries trigger immediate response, low-confidence get 1-beat verification delay

**Testing**: Play 4-bar melody with clear rest at end → verify boundary detected. Play continuous stream → verify boundary detected at register shifts. Verify boundary events align to strong beats.

**Complexity**: M

---

### Task 10.7 — Live Performance Controller Integration

**Description**: Optimize controller mappings for live performance mode, enabling foot-pedal triggers, one-hand knob tweaks, and performance shortcuts.

**Input**: Controller profiles from Phase 7 + live session state

**Output**: Performance-optimized controller mapping

**Implementation Hints**:
- Performance mappings:
  - **Pads (if available)**:
    - Pad 1-4: Toggle complementary parts (drums, bass, comping, counter)
    - Pad 5-8: Switch harmonization mode (thirds, sixths, counter, octave)
    - Pad 9-12: Energy override (force low/mid/high/auto)
    - Pad 13-16: Trigger events (fill, break, key change, stop)
  - **Knobs (if available)**:
    - Knob 1: Harmony mix (dry/wet — how much harmony note)
    - Knob 2: Complement mix (volume of complementary parts)
    - Knob 3: Creativity/risk dial (real-time)
    - Knob 4: Reverb/space
  - **Foot pedal / sustain**: Toggle harmony on/off (hands-free)
- Generate custom .xmm for "MPC AI Live Performance" controller map
- Handle MIDI input routing:
  - Performance notes → live analysis
  - Controller CCs → parameter changes (NOT sent to analysis)
  - Distinguish using MIDI channel: notes on ch1, controls on ch2

**Testing**: Assign toggle pads → verify pad press toggles auto-drums state. Assign harmony wet/dry knob → verify knob sweep changes harmony volume. Verify controller events don't contaminate live analysis.

**Complexity**: M

---

### Task 10.8 — Session Recording & Playback

**Description**: Record the entire live session (input + generated output) for later review, editing, and conversion to a composition.

**Input**: All MIDI I/O during live session

**Output**: Multi-track MIDI recording + session metadata

**Implementation Hints**:
- Record channels:
  - Track 1: Live input (as played)
  - Track 2: Harmony output
  - Track 3: Auto-bass
  - Track 4: Auto-drums
  - Track 5: Other complementary parts
- Recording format:
  - Standard MIDI File Format 1 (multi-track)
  - 480 PPQ (consistent with Phase 3 output)
  - Tempo map embedded if tempo varied
  - Save as `.mid` in session output directory
- Metadata (separate JSON):
  ```json
  {
    "sessionDate": "2025-01-15T20:30:00Z",
    "duration": 720,
    "detectedKeys": ["C major", "A minor"],
    "averageTempo": 92,
    "energyCurve": [0.3, 0.4, 0.6, 0.8, 0.7, 0.5],
    "complementaryParts": ["auto-bass", "auto-drums"],
    "harmonizationModes": ["thirds", "sixths"],
    "tracks": 5
  }
  ```
- Conversion to composition:
  - "Save this jam as a starting point" → create SongState from session data
  - Populate progression from detected chords
  - Import drum, bass, melody tracks
  - → Enter standard composition workflow (Phase 6)

**Testing**: Record 16-bar live session → verify output .mid has correct number of tracks. Verify playback reproduces session accurately. Verify conversion to SongState preserves key/tempo.

**Complexity**: L

---

## Modular Boundaries

| Can develop independently | Notes |
|---|---|
| Task 10.1 (input analyzer) | Depends on Phase 5.8 listener; algorithm is standalone |
| Task 10.2 (harmonizer) | Needs 10.1 for key detection |
| Task 10.3 (complement gen) | Needs 10.1 + Phase 3 generators |
| Task 10.4 (session manager) | Orchestration — needs all other tasks |
| Task 10.5 (energy mapper) | Needs 10.1 energy output |
| Task 10.6 (phrase detection) | Depends only on 10.1 note buffer |
| Task 10.7 (controller integration) | Depends on Phase 7 profiles |
| Task 10.8 (recording) | Independent MIDI recording — needs only I/O streams |

**Critical path**: 10.1 → 10.2 + 10.3 + 10.5 + 10.6 (parallel) → 10.4 → 10.7

---

## Cross-Phase Exports

| Export | Consumer |
|---|---|
| None | Terminal phase — all exports are user-facing outputs |
| Session recordings | Phase 6 (conversion to composition starting point) |
| LiveAnalysis data | Could feed back to Phase 9 (preference signals from performance style) |

---

## Risk Flags

| Risk | Severity | Description |
|---|---|---|
| Latency budget | Critical | Real-time music demands < 10ms response. Node.js garbage collection pauses can exceed this. Mitigate: pre-allocate buffers, avoid allocation in hot path, consider native addon for timing-critical path. |
| MIDI clock jitter | High | Windows MIDI timing is not sample-accurate. Mitigate: use high-resolution timers (`performance.now()`), Phase 5.4 scheduled player with drift compensation. |
| Key detection accuracy | High | Wrong key = all harmony notes are dissonant. Mitigate: require confidence > 0.8 before harmonizing, fall back to octave doubling when uncertain. |
| CPU load during live performance | High | Multiple generators running simultaneously (drums + bass + harmony + analysis) could cause audio dropouts. Mitigate: profile and optimize, consider web workers or worker threads for parallel generation. |
| Note-off tracking | Medium | Must correctly track note-offs for harmony notes. If input note lifts but harmony note-off is missed → stuck note. Mitigate: implement note-off watchdog timer, periodic all-notes-off safety valve (MIDI CC 123). |
| Variable tempo | Medium | Live performance tempo drifts. Analyzers expecting steady tempo may produce artifacts. Mitigate: continuously update tempo estimate, use beat-relative timing not absolute ms. |
