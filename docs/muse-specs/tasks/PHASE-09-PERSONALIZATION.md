# Phase 9 — Personalization

## Phase Overview

**Goal**: Build a learning system that adapts to the user's musical preferences over time. Track implicit signals (what they keep, reject, modify), maintain a preference profile with 7 dimensions, implement epsilon-greedy exploration (20% budget for trying new things), and support explicit "producer mode" profiles. The system should feel like a collaborator who knows your taste.

**Dependencies**: Phase 8 (creativity metrics, critic reports), Phase 1 (genre DNA), Phase 6 (pipeline — iteration/refinement provides accept/reject signals), Phase 0 (session hooks for persistence)

**Exports consumed by**: Phase 10 (personalization informs live performance adaptation)

---

## SDK Integration Points

| SDK Feature | Phase 9 Usage |
|---|---|
| `defineTool()` | `get_preferences`, `set_preference`, `reset_preferences`, `show_producer_mode` |
| `hooks.onSessionEnd` | Persist updated preference profile to disk |
| `hooks.onSessionStart` | Load preference profile, inject into system context |
| `hooks.onPostToolUse` | Capture implicit preference signals from user reactions |
| `infiniteSessions` | Long-running sessions with context compaction preserving preference-relevant history |
| `ask_user` | "You've been accepting jazzy chord extensions lately. Want me to use more of them by default?" |
| Contract C9 | `UserPreferences` — loaded, updated, persisted |

---

## Task Breakdown

### Task 9.1 — Implicit Preference Tracker

**Description**: Monitor user interactions and extract preference signals without explicit input.

**Input**: Tool call results + user responses + editing commands

**Output**: Stream of `PreferenceSignal` events
```typescript
interface PreferenceSignal {
  timestamp: number;
  type: "accept" | "reject" | "modify" | "request" | "ignore" | "repeat";
  domain: "harmony" | "rhythm" | "sound" | "arrangement" | "mix" | "genre" | "creativity";
  context: {
    toolName: string;
    input: Record<string, unknown>;
    output: unknown;
  };
  inferredPreference: {
    dimension: string;     // "chord_complexity", "tempo_range", "bass_style", etc.
    direction: "increase" | "decrease" | "neutral";
    confidence: number;    // 0.0 - 1.0
  };
}
```

**Implementation Hints**:
- **6 Implicit Signals** (from blueprint):
  1. **Acceptance**: User proceeds with generated output → positive signal for those characteristics
  2. **Rejection**: User says "no", "try again", "different" → negative signal
  3. **Modification**: User adjusts part of output ("keep the chords but change the rhythm") → mixed signal (positive for chords, negative for rhythm)
  4. **Repetition**: User requests the same type of thing multiple times → strong positive signal
  5. **Request pattern**: Frequent requests for specific genres/sounds → implicit genre preference
  6. **Ignoring**: User doesn't engage with a suggestion → weak negative signal (lower confidence)
- Signal extraction via `onPostToolUse`:
  - After `generate_progression`: track if user accepts or requests modification
  - After `suggest_preset`: track if user asks for alternatives
  - After `set_creativity`: track explicit creativity preference
- Debounce: don't log signals faster than 1 per tool call
- Buffer signals in memory, flush to preference model periodically

**Testing**: User accepts 5 jazz progressions → verify "harmony.complexity" signals trend "increase". User rejects 3 EDM drum patterns → verify "rhythm.genre_alignment" signals for EDM trend "decrease".

**Complexity**: L

---

### Task 9.2 — Preference Profile Model

**Description**: Maintain a persistent user preference model with 7 dimensions, updated from implicit signals.

**Input**: `PreferenceSignal` stream

**Output**: `UserPreferences` (Contract C9)
```typescript
interface UserPreferences {
  version: number;
  lastUpdated: number;
  
  // 7 Core Dimensions (each 0.0 - 1.0)
  dimensions: {
    harmonicComplexity: number;      // simple triads ↔ extended jazz voicings
    rhythmicDensity: number;         // sparse ↔ dense/complex
    timbralBrightness: number;       // dark/warm ↔ bright/present
    arrangementDensity: number;      // minimal ↔ layered/full
    experimentalTendency: number;    // safe/conventional ↔ avant-garde
    energyLevel: number;             // chill/ambient ↔ high-energy/intense
    productionCleanness: number;     // lo-fi/raw ↔ polished/clean
  };
  
  // Derived preferences
  genreAffinities: Record<string, number>;  // "jazz": 0.78, "hip-hop": 0.65
  tempoRange: [number, number];             // preferred BPM range
  keyPreferences: string[];                 // frequently used keys
  
  // Confidence tracking
  signalCount: number;      // total signals received
  confidence: number;       // overall profile confidence (increases with more signals)
  
  // Exploration
  explorationBudget: number;   // current epsilon (starts at 0.30, settles to 0.20)
  
  // History (ring buffer, last 50 sessions)
  sessionHistory: SessionSummary[];
}

interface SessionSummary {
  date: number;
  duration: number;
  genresUsed: string[];
  averageCriticScore: number;
  creativitySettings: { harmonic: number; rhythmic: number };
  acceptRate: number;        // what % of suggestions were accepted
}
```

**Implementation Hints**:
- Update algorithm:
  - Exponential moving average (EMA) with α = 0.1:
    `dim_new = dim_old × (1 - α) + signal_value × α`
  - Higher α for explicit signals (user directly sets a preference)
  - Lower α for implicit signals (acceptance/rejection inference)
- Confidence increases logarithmically with signal count:
  `confidence = min(1.0, 0.3 + 0.15 × log2(signalCount + 1))`
- Cold start: default to middle-of-road values (0.5 for all dimensions)
- Genre affinities derived from:
  - Genre DNA distance of accepted outputs
  - Explicit genre requests
  - Genre of rejected outputs (decrease affinity)
- Persistence: JSON file at `~/.muse/user-preferences.json`
- Migration: version field enables schema evolution

**Testing**: Start with default profile → send 20 "jazz acceptance" signals → verify harmonicComplexity > 0.6 and genreAffinities.jazz > 0.5. Verify confidence increases from 0.3 toward 1.0.

**Complexity**: L

---

### Task 9.3 — Epsilon-Greedy Exploration

**Description**: Reserve a portion of generation attempts (default 20%) for exploring outside the user's established preferences, to prevent filter bubbles and enable taste evolution.

**Input**: `UserPreferences.explorationBudget` + current request

**Output**: Decision: exploit preferences OR explore new territory

**Implementation Hints**:
- Algorithm:
  ```
  roll = random()
  if roll < explorationBudget:
    // EXPLORE: deviate from preferences
    deviationAxis = randomChoice(7 dimensions)
    deviationDirection = randomChoice(["increase", "decrease"])
    deviationMagnitude = random() * 0.3  // max 30% deviation
    adjustedPreferences = clone(preferences)
    adjustedPreferences[deviationAxis] += deviationDirection * deviationMagnitude
  else:
    // EXPLOIT: use preferences as-is
    adjustedPreferences = preferences
  ```
- Track exploration outcomes:
  - If explored output accepted → shrink exploration budget (user's comfort zone is expanding)
  - If explored output rejected → small increase to exploration budget (try again later)
  - Budget bounds: [0.10, 0.30] — never stop exploring, never explore too much
- Label explored outputs: "Trying something a bit different — I've added some modal interchange chords that are outside your usual style."
- If user loves an exploration: "Great! I'll incorporate more of this into your profile."

**Testing**: With budget=0.20, run 100 generation decisions → verify ~20 are exploration. Verify budget adjusts: 5 accepted explorations → budget decreases toward 0.15.

**Complexity**: M

---

### Task 9.4 — Producer Mode Profiles

**Description**: Named presets that set all preferences explicitly, allowing users to switch "hats" — e.g., "I'm making a lo-fi beat" vs. "I'm scoring a film."

**Input**: Mode name or custom profile

**Output**: Complete preference override

**Implementation Hints**:
- Built-in modes:
  - **"Beat Maker"**: rhythmicDensity 0.7, harmonicComplexity 0.4, energyLevel 0.6, genreAffinities: { "hip-hop": 0.8, "trap": 0.7 }
  - **"Jazz Cat"**: harmonicComplexity 0.9, rhythmicDensity 0.5, timbralBrightness 0.4, genreAffinities: { "jazz": 0.9, "bossa-nova": 0.6 }
  - **"EDM Producer"**: energyLevel 0.9, productionCleanness 0.8, arrangementDensity 0.8, genreAffinities: { "house": 0.7, "techno": 0.7 }
  - **"Lo-fi Chill"**: productionCleanness 0.2, energyLevel 0.2, experimentalTendency 0.3, genreAffinities: { "lo-fi": 0.9, "jazz": 0.5 }
  - **"Film Scorer"**: arrangementDensity 0.8, harmonicComplexity 0.7, experimentalTendency 0.5
  - **"Songwriter"**: harmonicComplexity 0.3, rhythmicDensity 0.3, productionCleanness 0.6
- Custom modes:
  - User can save current profile as a named mode
  - User can describe a mode: "I want to make dark, aggressive dubstep" → system derives dimensions
  - Stored in `~/.muse/producer-modes.json`
- Mode switching:
  - "Switch to beat maker mode" → apply Beat Maker preset
  - Implicit learning continues within mode (mode is base, learning adjusts)
  - On mode switch, preference model resets to mode defaults but keeps session history

**Testing**: Switch to "Jazz Cat" → verify harmonicComplexity = 0.9. Create custom mode → verify it persists. Switch modes → verify preferences reset to mode defaults.

**Complexity**: M

---

### Task 9.5 — Preference-Driven Defaults

**Description**: Use the preference model to set intelligent defaults for all generation tools, so the user gets good results without specifying every parameter.

**Input**: `UserPreferences` + tool call without explicit parameters

**Output**: Filled-in default parameters

**Implementation Hints**:
- Default mappings:
  - `generate_progression()` without genre → use top genreAffinity
  - `generate_progression()` without creativity → use experimentalTendency
  - `generate_drums()` without style → infer from top genre affinity + rhythmicDensity
  - `suggest_preset()` without brightness preference → use timbralBrightness
  - Pipeline tempo → use median of tempoRange
  - Pipeline key → use most frequent from keyPreferences (if any)
- Implementation via tool wrapper:
  ```
  Before tool execution:
  1. Check which parameters are unspecified
  2. For each missing parameter, look up preference model
  3. Fill in defaults
  4. Log: "Using your preferred tempo range (85-95 BPM) — say 'at 120 BPM' to override"
  ```
- Never override explicitly provided parameters
- Transparency: always mention when a default is preference-derived

**Testing**: User with jazz affinity calls `generate_progression()` → verify jazz-style defaults applied. User explicitly says "in D minor at 140 BPM" → verify preferences NOT overridden.

**Complexity**: M

---

### Task 9.6 — Preference Introspection Tools

**Description**: Let the user inspect and modify their preference profile explicitly.

**Input**: User queries ("What are my preferences?", "I don't like minor keys")

**Output**: Formatted preference display + modification confirmation

**Implementation Hints**:
- Tools:
  - `get_preferences` → display current profile with natural language:
    ```
    Your Music Profile:
    ─────────────────────
    Harmonic Complexity:   ████████░░  0.78 (you enjoy rich chord extensions)
    Rhythmic Density:      █████░░░░░  0.52 (moderate groove complexity)
    Timbral Brightness:    ███░░░░░░░  0.35 (you prefer warm, dark tones)
    ...
    
    Top Genres: Jazz (0.82), Neo-Soul (0.71), Hip-Hop (0.58)
    Preferred Tempo: 80-110 BPM
    Confidence: 0.68 (based on 47 interactions)
    ```
  - `set_preference` → explicit override: "Make me prefer brighter sounds" → timbralBrightness += 0.2
  - `reset_preferences` → back to defaults (with confirmation)
- Bar chart visualization using Unicode block characters
- Historical comparison: "Your harmonic complexity has increased from 0.45 to 0.78 over 12 sessions"

**Testing**: After 20 sessions → verify `get_preferences` shows meaningful profile. `set_preference("brighter sounds")` → verify timbralBrightness increases. `reset_preferences` → verify all dimensions back to 0.5.

**Complexity**: M

---

### Task 9.7 — Session Persistence via Hooks

**Description**: Wire preference persistence to SDK session hooks.

**Input**: `onSessionStart` / `onSessionEnd` events

**Output**: Automatic load/save

**Implementation Hints**:
- `onSessionStart`:
  1. Load `~/.muse/user-preferences.json` (create with defaults if missing)
  2. Inject preference summary into agent context: "User prefers jazz-influenced harmony with moderate complexity..."
  3. Set creativity dials from preference model defaults
  4. Load active producer mode if any
- `onSessionEnd`:
  1. Flush pending preference signals
  2. Update preference model with session signals
  3. Calculate session summary
  4. Append to session history (ring buffer, last 50)
  5. Write to `~/.muse/user-preferences.json`
- Error handling:
  - Corrupted preference file → backup and reset to defaults
  - Read-only filesystem → warn user, operate without persistence
- File locking: simple write-after-read pattern (single user, not concurrent)

**Testing**: Start session → verify preferences loaded. End session → verify preferences updated and persisted. Corrupt file → verify graceful recovery.

**Complexity**: M

---

### Task 9.8 — Speculative Pre-Generation

**Description**: Based on preference patterns, predict what the user will ask for next and pre-compute likely outputs.

**Input**: Session history + preference model + current SongState

**Output**: Cached speculative outputs ready for instant delivery

**Implementation Hints**:
- Prediction heuristics:
  - After user generates a progression → they'll likely want drums next (85% probability)
  - After drums → they'll want bass (78% probability)
  - After all tracks → they'll want mix suggestions (81% probability)
  - If user is iterating on progression → pre-generate 2 variations
- Pre-computation:
  - Run prediction after each tool call
  - If confidence > 0.70, start generating the predicted output
  - Store in cache with 5-minute TTL
  - When user actually asks → serve from cache (near-instant response)
- Resource management:
  - Max 3 speculative generations in cache
  - Don't speculate during high-creativity mode (output too unpredictable)
  - Don't speculate if last 3 predictions were wrong (back off)
- Transparency: "I anticipated you'd want drums next — here's what I prepared! Want to adjust?"

**Testing**: After progression generation → verify drum pattern pre-generated. Verify cached output served when user requests drums. Verify cache cleared after 5 minutes.

**Complexity**: L

---

## Modular Boundaries

| Can develop independently | Notes |
|---|---|
| Task 9.1 (implicit tracker) | Needs hook infrastructure from Phase 0; otherwise independent |
| Task 9.2 (preference model) | Needs 9.1 for input; mathematical model is standalone |
| Task 9.3 (exploration) | Needs 9.2 for preference values |
| Task 9.4 (producer modes) | Needs 9.2 for storage; presets are standalone |
| Task 9.5 (defaults) | Needs 9.2 for values + all generation tools from Phases 1/3/4 |
| Task 9.6 (introspection) | Needs 9.2 for data; UI formatting is standalone |
| Task 9.7 (persistence) | Needs 9.2 for data + Phase 0 hooks |
| Task 9.8 (speculative gen) | Needs 9.2 + Phase 3/4 generators; most complex dependency chain |

**Critical path**: 9.1 → 9.2 → 9.3 + 9.5 (parallel) → 9.7 → 9.8

---

## Cross-Phase Exports

| Export | Consumer |
|---|---|
| `UserPreferences` (C9) | Phase 8 (creativity defaults), Phase 10 (live performance adaptation) |
| Preference-driven defaults | All generation tools (Phases 1, 3, 4) |
| Producer modes | Phase 6 (pipeline uses active mode for defaults) |
| Session summaries | Phase 8 (creativity metrics include preference trends) |
| Speculative generation cache | Phase 10 (pre-generate live variations) |

---

## Risk Flags

| Risk | Severity | Description |
|---|---|---|
| Filter bubble | High | Preference model converges too tightly, user never hears new ideas. Mitigate: epsilon-greedy exploration with hard minimum 10%. |
| Privacy sensitivity | Medium | Preference data could reveal personal information. Mitigate: all data is local only (`~/.muse/`), never transmitted. |
| Cold start quality | Medium | First few sessions have no preference data → defaults must be good. Mitigate: middle-of-road defaults, optional quick "taste quiz" on first run. |
| Model drift | Medium | Preferences from 6 months ago may not reflect current taste. Mitigate: time-weighted EMA (recent signals weighted more), periodic decay of old signals. |
| Speculative waste | Low | Pre-generating wrong predictions wastes compute. Mitigate: confidence threshold 0.70, back-off after misses, max 3 cached items. |
