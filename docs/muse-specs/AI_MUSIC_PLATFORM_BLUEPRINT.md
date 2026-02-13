# The Omniscient Copilot: AI Music Platform Blueprint

## MPC Beats × Copilot SDK — Comprehensive Design Document

> **Date**: February 8, 2026  
> **Reviewers**: Gemini 3 Pro Preview (General-purpose), GPT-5.2 Codex (General-purpose)  
> **Methodology**: 3 rounds of parallel brainstorming with cross-pollination  
> **Subject**: Transforming MPC Beats (Akai Professional v2.9.0.21) into an omnipotent, omniscient AI music production platform using the GitHub Copilot SDK  

---

## Table of Contents

1. [Project Inventory & Analysis](#1-project-inventory--analysis)
2. [Architecture Vision](#2-architecture-vision)
3. [The Musical Omniscience Engine](#3-the-musical-omniscience-engine)
4. [Song Generation Pipeline](#4-song-generation-pipeline)
5. [MIDI Intelligence Layer](#5-midi-intelligence-layer)
6. [Sound Design & Effects Intelligence](#6-sound-design--effects-intelligence)
7. [Mixing & Mastering Brain](#7-mixing--mastering-brain)
8. [Hardware Integration](#8-hardware-integration)
9. [Genre DNA System](#9-genre-dna-system)
10. [Creative Risk & Happy Accidents](#10-creative-risk--happy-accidents)
11. [Quality Assurance & Self-Evaluation](#11-quality-assurance--self-evaluation)
12. [DAW Integration Strategy](#12-daw-integration-strategy)
13. [State Management & Iteration UX](#13-state-management--iteration-ux)
14. [Personalization & Learning](#14-personalization--learning)
15. [Competitive Analysis & Moat](#15-competitive-analysis--moat)
16. [Legal & IP Analysis](#16-legal--ip-analysis)
17. [Risks & Challenges](#17-risks--challenges)
18. [Implementation Roadmap](#18-implementation-roadmap)
19. [Naming & Identity](#19-naming--identity)
20. [Reviewer Comments & Cross-Pollination Log](#20-reviewer-comments--cross-pollination-log)

---

## 1. Project Inventory & Analysis

### What We're Building On

MPC Beats is Akai Professional's free Windows DAW (v2.9.0.21) containing:

| Asset Category | Count | Format | Description |
|---|---|---|---|
| **Arp Patterns** | 80 | `.mid` (MIDI) | Categorized: Chord (38), Melodic (18), Bass (24) spanning Chill Out, Dance, Pop, RnB, Hip Hop, Dubstep, Techno, Soul Ballad, SynBass, Slap Bass |
| **Chord Progressions** | 47 | `.progression` (JSON) | Structured chord data: name, rootNote, scale, recordingOctave, chords with MIDI note arrays. Genres: Gospel, Neo Soul, Jazz, House, Trap, RnB, Pop, Soul, Tech House |
| **MIDI Controller Maps** | 67 | `.xmm` (XML) | Hardware mappings for Akai, Alesis, Arturia, Korg, M-Audio, NI, Novation controllers. Maps pads, knobs, sliders to MPC internal targets |
| **Synth Plugins** | 100+ | Plugin directories | AIR synths (Bassline, TubeSynth, Electric, DrumSynth×10), AIR effects (30+), Akai effects (40+), VST instruments (DB-33, Hybrid, Loom, Mini Grand, Velvet, Xpand!2, etc.) |
| **UI Resources** | Extensive | JSON layouts, PNG/SVG assets | ACVS graphics engine (30 subsystems), Page layouts, Generic controls |

### The Gold Mine: Progression Data

The `.progression` files encode **professional producer knowledge**, not abstract theory. Example from `Godly.progression`:

```json
{
  "progression": {
    "name": "Gospel-Godly",
    "rootNote": "E",
    "scale": "Pentatonic Minor",
    "recordingOctave": 2,
    "chords": [
      { "name": "Em",    "role": "Root",   "notes": [52, 59, 64, 67] },
      { "name": "Em7/D", "role": "Normal", "notes": [50, 59, 62, 67] },
      { "name": "B/F#",  "role": "Normal", "notes": [54, 59, 63, 66] },
      { "name": "B7/D#", "role": "Normal", "notes": [51, 59, 63, 66, 69] }
    ]
  }
}
```

> **Gemini**: "Your 47 progression files encode real producer knowledge — not abstract music theory, but how actual hit records are voiced. The Neo Soul 1 file shows root moving 45→44→43→42 — a chromatic descent. This is the voicing intelligence that separates amateurs from professionals."

---

## 2. Architecture Vision

### Core Architecture: Copilot Chat Extension

The platform registers a **`@mpc` chat participant** with specialized slash commands and tools.

#### Slash Commands

| Command | Agent | Domain |
|---|---|---|
| `/compose` | Composer Agent | Song structure, arrangement, full pipeline |
| `/harmony` | Theory Agent | Chord progressions, music theory analysis |
| `/arp` | Arp Agent | Arpeggiator pattern generation/selection |
| `/sound` | Sound Design Agent | Synth preset selection, parameter reasoning |
| `/mix` | Mix Engineer Agent | Effect chains, frequency balance, stereo |
| `/controller` | Performance Agent | Hardware mapping, real-time MIDI |
| `/theory` | Theory Agent | Music theory explanations, analysis |
| `/feel` | Humanization Agent | Swing, velocity, micro-timing |
| `/surprise` | Creative Agent | Controlled creative risk mode |

#### Tools (LLM-Callable)

| Tool | Input | Output |
|---|---|---|
| `readProgression` | File path | Enriched harmonic analysis |
| `readArpPattern` | File path | Rhythm/pitch extraction from MIDI |
| `readSynthPresets` | Synth name | Preset catalog with timbral descriptions |
| `readControllerMap` | Controller name | Human-readable MIDI mapping |
| `generateProgression` | Genre, mood, key, complexity | New `.progression` JSON file |
| `generateMIDI` | Rhythmic/melodic specification | New `.mid` file |
| `generateEffectChain` | Instrument role, genre, aesthetic | Ordered effects + parameter values |
| `generateControllerMap` | Controller model, workflow | New `.xmm` file |
| `analyzeFrequencyBalance` | Multi-track specification | Masking report + suggestions |
| `suggestArrangement` | Song concept + constraints | Section-by-section structure |

#### Copilot Variables (Context Injection)

| Variable | Resolution | Enrichment |
|---|---|---|
| `#progression:Name` | Parse `.progression` JSON | Roman numeral analysis, voice leading, harmonic function, genre associations |
| `#arp:Number` | Parse `.mid` file | Note sequence, rhythm grid, velocity curve, density |
| `#synth:Name` | Scan preset directory | Category catalog, timbral descriptors |
| `#controller:Name` | Parse `.xmm` XML | Physical control layout, available mappings |
| `#palette` | Composite of current selections | Full creative state summary |

> **Gemini**: "Variables shouldn't just dump raw JSON — they should ENRICH the data with computed music-theory annotations so the LLM can reason about it musically."

> **GPT**: "Enrichments should be tiered. Level 1: chord symbols + roman numerals (~50 tokens). Level 2: add voice leading + tension analysis (~150 tokens). Level 3: full genre association + substitution suggestions (~300 tokens). The variable resolution should match the query complexity."

### Agent Orchestration: The Producer Graph

Every complex request decomposes into a DAG (Directed Acyclic Graph) of sub-agents:

```
User Intent → Intent Parser
  ├→ Genre Analyst (stylistic constraints)
  ├→ Key/Scale Agent
  ├→ Tempo/Feel Agent  
  ├→ Structure Agent (section layout)
  │
  ├→ Chord Progression Agent (depends on: key, tempo, genre, structure)
  │   ├→ Bass Agent (depends on: chords, feel, tempo)
  │   ├→ Melody/Arp Agent (depends on: chords, scale, groove)  
  │   └→ Preset Selection Agent (depends on: genre, all above)
  │
  ├→ Effect Chain Agent (depends on: presets, genre)
  ├→ Mix Agent (depends on: all tracks)
  └→ Assembly Agent (combines everything)
```

#### Agent Communication Protocol

Agents communicate through **typed intermediate results** with confidence scores:

- Each result carries: `status`, `confidence` (0-1), `data`, `reasoning`, `alternatives[]`, `constraints[]`
- A shared `PipelineContext` accumulates as agents complete
- Each result is **independently overridable** — user approval freezes it
- Sensitive annotations declare what changes trigger re-execution (`BassMelodyAgent.sensitiveTo = ['key', 'progression', 'tempo']`)

> **GPT**: "Each agent should return a candidates[] array ranked by confidence, not a single result. When the user says 'try something different for the bass,' we surface candidates[1]. Only if they exhaust candidates do we re-run with a temperature bump. This is dramatically faster for iteration."

> **Gemini**: "The DAG should be soft. Each agent should declare sensitivity annotations. A key change might invalidate the drum pattern (if it had pitched percussion), or might not. The orchestrator uses these to compute minimal re-execution sets."

---

## 3. The Musical Omniscience Engine

### Three-Tier Knowledge Architecture

#### Tier 1 — Embedded Corpus (Structured Data from MPC Beats)

**Harmonic DNA** (from 47 progressions):
- Parse all `.progression` files into normalized representations
- Derive roman numeral analysis from the `role: "Root"` field
- Compute interval vectors, voice leading distances, common-tone retention
- Extract statistical genre signatures:
  - **Neo Soul DNA**: Extended chords (maj9, m7, add9), chromatic bass motion, wide voicings spanning 3+ octaves
  - **Gospel DNA**: Pentatonic Minor foundation, secondary dominants (D7/F#, A7/C#), chromatic approach chords
  - **Jazz DNA**: ii-V-I patterns, 9th/11th extensions, walkdown bass
  - **Trap DNA**: Sparse minor progressions, dark intervals

**Rhythmic DNA** (from 80 arp patterns):
- Parse MIDI files for: note density, rhythmic grid quantization, pitch range, interval distribution, velocity curves
- Categorize by drive, space, complexity
- Map each arp to compatible chord types and genres

**Timbral DNA** (from 100+ synth plugins):
- TubeSynth alone: 297 presets organized as Synth (44), Lead (50), Pluck (40), Pad (68), Bass (65), Organ (7), FX (23)
- Build inverted index: "warm" → specific presets, "aggressive" → specific presets
- Generate rich text descriptions from preset naming conventions

#### Tier 2 — Implicit Music Theory Graph

A knowledge graph connecting:
- Scales → Modes → Chord sets → Voicing strategies → Genre associations
- Tempo ranges → Genre expectations → Energy levels → Rhythmic subdivision norms
- Frequency ranges → Instrument roles → Mixing conventions → Masking relationships
- Emotional descriptors → Harmonic devices → Timbral choices → Production techniques

Grounded in the actual workspace data — when the AI says "Neo Soul typically uses major 9th chords with chromatic bass motion," it can point to the actual Neo Soul 1 progression as evidence.

#### Tier 3 — Emergent Understanding (Tension/Resolution/Arc)

> **GPT**: "The system should model music as energy over time."

**Tension Function** per chord:

$$T_{chord} = w_r \cdot R + w_s \cdot (1 - S) + w_d \cdot D + w_c \cdot C$$

Where $R$ = roughness (contextual dissonance, not raw interval math), $S$ = stability (Krumhansl key profile distance), $D$ = density tension, $C$ = contextual surprise. Weights are genre-dependent.

**Computed example** from the Godly progression:

| Chord | Roughness | 1−Stability | Density | Contextual | **Total** |
|---|---|---|---|---|---|
| Em (52,59,64,67) | 0.12 | 0.05 | 0.15 | 0.00 | **0.073** |
| Em7/D (50,59,62,67) | 0.18 | 0.18 | 0.12 | 0.15 | **0.153** |
| B/F# (54,59,63,66) | 0.38 | 0.45 | 0.22 | 0.35 | **0.367** |

The delta Em→Em7/D (+0.080) is a gentle lean; Em7/D→B/F# (+0.214) is a dramatic pull. This is why the progression *feels* like a slow build — the system quantifies what a producer feels intuitively.

**Composite Energy Function:**

$$E(t) = \alpha \cdot H(t) + \beta \cdot R(t) + \gamma \cdot \Phi(t) + \delta \cdot H(t) \cdot R(t) + \epsilon \cdot \Phi(t) \cdot H(t)$$

Where $H(t)$ = harmonic tension, $R(t)$ = rhythmic energy, $\Phi(t)$ = timbral energy. The interaction terms capture that high harmonic tension + high rhythmic density = exponentially more intense than either alone.

> **Gemini**: "The interaction term H(t)*R(t) is the best idea here. I'd add a timbral dimension to the interaction: a sawtooth pad + rhythmic density + harmonic tension hits differently than a sine pad + the same."

> **GPT**: "A filter sweep is a rising timbral energy curve. The 'drop' in EDM is a sudden jump in rhythmic energy. The AI should reason about these as continuous functions."

### Vector Embedding Index

**Model**: `all-MiniLM-L6-v2` running locally via ONNX Runtime for Node.js (~80MB).

**Rationale**: ~650-1200 assets to embed. At 384 dimensions × 4 bytes × 1200 = ~1.8MB. Brute-force cosine similarity takes <1ms. No vector DB needed.

**Pipeline**: Musical asset → enriched text description → embedding vector

```
INPUT: Godly.progression

ENRICHMENT → "Gospel minor key progression in E pentatonic minor. 
Chromatic descending bass line. Heavy use of secondary dominants 
creating yearning pull. Soulful, devotional, emotionally intense. 
16 chords suggesting verse-chorus structure with modulation."

→ embed → [0.234, -0.112, 0.445, ...]
```

**Cross-modal queries**: "warm Sunday morning feeling" → retrieves Slow Praise (0.87 similarity), RhodesBallad (0.84), Electric "Ballad EP" preset (0.89), TubeSynth "Warm Pad" (0.86).

> **Gemini**: "No need for a vector database at this scale. A simple Float32Array with a cosineSimilarity() function is all you need. Store in context.globalStorageUri for persistence."

> **GPT**: "Local is correct over cloud — queries happen on every chat turn. The bottleneck is description quality, not dimensionality. Ship a pre-computed description catalog as part of the extension."

---

## 4. Song Generation Pipeline

### End-to-End Walkthrough: "Frank Ocean meets Burial"

> **GPT's complete pipeline** (summarized across all rounds):

**Phase 1 — Intent Decomposition:**
- Frank Ocean: Neo-soul harmony (maj9s, chromatic mediants), 60-75 BPM perceived, lush reverbs
- Burial: UK garage skeleton (2-step, skippy hi-hats), lo-fi vinyl, 130-140 BPM clock
- **Derived insight**: Half-time 130 = perceived 65 BPM → tempo intersection discovered
- Decision: 130 BPM clock, half-time feel, Eb minor

**Phase 2 — Harmonic Architecture:**
- Cross-reference Neo Soul + Gospel progressions from corpus
- Generate: Ebm9 → Dbmaj7/F → Gbmaj9 → Abm7(add11)
- Voice leading: smooth, maximum common tones, inner voices move by step
- Bass: descending chromatic pedal (Burial influence) under jazz voicings (Ocean influence)

**Phase 3 — Arrangement:**
```
Intro (8 bars):     Pad only, slow filter sweep, vinyl crackle
Verse A (16 bars):  Add drums (half-time), sub bass, sparse lead
Build (4 bars):     Hi-hat pattern intensifies, pad swells
Chorus (8 bars):    Full arrangement, melody doubles octave up
Break (8 bars):     Strip to pad + vocal chop + lone kick
Verse B (16 bars):  Like A but add 2-step percussion layer
Chorus 2 (8 bars):  Add Delay Multi-Tap on lead
Outro (8 bars):     Elements subtract one by one
```

**Phase 4 — Sound Selection:**
- Pad: TubeSynth "Warm Pad" → Lo-Fi → Chorus 4-voice → Reverb Large 2 (4.5s, hi-cut 6kHz)
- Sub bass: TubeSynth "Sub Bass 1" → Compressor Opto → LP Filter (120Hz)
- Hi-hats: DrumSynthHiHat → SP1200 → Delay Ping Pong (dotted 8th, 15%) → Reverb Small
- Lead: TubeSynth "Chillout Lead" → Phaser 1 → Delay Ping Pong → Reverb Large 2

**Phase 5 — Output:**
- `.progression` file for the chord progression
- Multiple `.mid` files (drums, bass, lead, pad, percussion)
- Text specification: presets, effect chains, arrangement map, producer's notes
- MIDI "play-in" capability via virtual port

> **GPT**: "The half-time insight is the kind of meta-knowledge that separates good from great. It's derived from constraint intersection of artist tempo profiles."

> **Gemini**: "Encode the principle ('artists often use double-tempo with half-time feel to occupy a perceptual tempo space at half the BPM') as a system-level heuristic. Let the LLM apply it. Pure emergence is unreliable for production use."

---

## 5. MIDI Intelligence Layer

### Humanization Framework

**Velocity Architecture:**
- Never flat velocity — every note determined by: metric position, phrase contour, genre convention, stochastic human variance (±5-12, Gaussian, sigma genre-dependent: EDM σ=3, jazz σ=10)

**Micro-timing:**
- Per-instrument offsets: hi-hats swing at 58%, kick dead on grid, bass 5-15ms behind kick
- Frank Ocean feel = everything slightly behind the beat
- Burial hi-hats = deliberately wonky, 10-40ms variable offset
- Flam and drag: layered hits offset 5-20ms for organic quality

**Ghost Notes:**
- Fill every 32nd note position with 20% probability, velocity 20-35
- Snare ghost hits between backbeats at velocity 25-40

**Polyrhythm Intelligence:**
- 3-over-4, 5-over-4, 7-over-8 metric superimposition
- Afrobeat influence → 12/8 feel over 4/4 framework
- J Dilla feel → snare offset late by 32nd, kick wanders

### Voicing Engine

Given `Ebm9`, the AI narrows voicings through constraints:
1. **Register Range**: C3-C5 for chord proper (both artists' registers)
2. **Voice Leading**: Minimize total semitone movement from previous chord
3. **Open Position**: Adjacent notes ≥5 semitones apart for "dreamy" quality
4. **Production Awareness**: Open low voicing + dense top (heavy reverb needs open lows)

> **GPT**: "The AI knows this voicing will be played by a synth pad with heavy reverb. Dense low voicings + heavy reverb = mud. Therefore: keep voicing open in the low register, denser on top."

---

## 6. Sound Design & Effects Intelligence

### Timbral Ontology

**Genre-to-Synth Mapping:**

| Genre | Keys/Chords | Bass | Lead | Drums | Character FX |
|---|---|---|---|---|---|
| Neo Soul | Velvet, Electric | TubeSynth Round/Smooth | TubeSynth Chillout | DrumSynth (soft) | Chorus, Reverb Large |
| Trap | THE WUB | Bassline (808) | TubeSynth Hard Sync | DrumSynth (808 kicks) | Distortion, Lo-Fi |
| House | TubeSynth Supersaw | Bassline (303 acid) | Bassline | DrumSynth (4-on-floor) | Delay Sync, Filter Gate |
| Gospel | DB-33 (Hammond), Mini Grand | TubeSynth Organ Bass | Mini Grand | DrumSynth | Reverb Large 2, Enhancer |
| Jazz | Mini Grand, DB-33 | Walk bass (Electric) | TubeSynth Soft Analog | Acoustic kits | Spring Reverb, subtle EQ |

### Effect Chain Intelligence

Signal flow order matters. The AI understands physics:

1. **Source shaping**: EQ, Filter, Distortion (shape raw timbre)
2. **Dynamics**: Compressor (Opto=smooth, VCA=punchy, Vintage=color), Transient Shaper
3. **Time-based**: Delay (Analog=warmth, Ping Pong=width, Tape=vintage), Reverb
4. **Modulation**: Chorus, Flanger, Phaser, Ensemble
5. **Character**: MPC3000 (grit), MPC60 (warmth), SP1200 (12-bit crunch), Lo-Fi
6. **Master**: Maximizer, Limiter, Stereo Width, Channel Strip

### Vintage Emulation Intelligence

> **Gemini**: "Your SP1200, MPC60, and MPC3000 emulations are legendary. The AI should know: SP1200 for boom-bap grit, MPC60 for J Dilla-style swing, MPC3000 for modern lo-fi."

---

## 7. Mixing & Mastering Brain

### Frequency Balance Model

The AI treats the spectrum as **real estate**:

| Zone | Hz | Typical Residents | Danger |
|---|---|---|---|
| Sub | 20-60 | 808/sub bass, kick fundamental | Mud, phase issues |
| Bass | 60-250 | Bass body, kick punch | Buildup, boom |
| Low-Mid | 250-800 | Chord body, snare body | Mud, boxiness |
| Mid | 800-2k | Vocal presence, lead synth | Harshness, masking |
| Upper-Mid | 2-5k | Clarity, hi-hat body | Piercing, fatigue |
| Air | 5-20k | Shimmer, sparkle, reverb air | Sibilance |

### Genre-Specific Mixing Templates

- **Trap**: 808 = loudest, Bus Compressor on drums, Maximizer targeting -7 to -9 LUFS
- **Neo Soul**: Warm, rounded, -12 to -14 LUFS (dynamic, breathing)
- **UK Garage**: Sub mono, everything reverb-drenched, -10 to -12 LUFS

### Frequency Masking Detection (Without Audio)

> **GPT**: "For each pair of elements, estimate spectral overlap from MIDI note fundamentals, preset harmonic content, and filter settings. Apply perceptual weighting: masking at 200-500Hz weighted 2x, below 100Hz weighted 3x, above 8kHz weighted 0.5x."

The AI generates actionable **mix review reports**:

> ⚠ **Frequency clash**: Pad and Lead both occupy 1-4kHz with similar spectral density. Suggest: cut Pad at 2.5kHz (-3dB), boost Lead at 3kHz (+2dB).  
> ✓ **Bass foundation**: Sub bass is mono, occupying 40-120Hz exclusively.  
> ⚠ **Mono compatibility risk**: Pad's 150% width + chorus effect. Estimated 2-3dB loss in 1-3kHz when summed to mono.

---

## 8. Hardware Integration

### The Controller Intelligence Layer

67 `.xmm` files = mappings for controllers from 7 manufacturers. The XML reveals:
- Pads: note-on messages (type=1) on channel 10, data1 = note number (36-51)
- Knobs: CC messages (type=2) on channel 1, data1 = CC number
- Transport: mapped controls for Play, Stop, Record
- Target_control indices 0-115+ map to MPC internal functions

**AI-Powered Workflows:**

1. **Smart Mapping**: "You're working on a bass line — I've mapped knobs 1-4 to TubeSynth filter cutoff, resonance, envelope amount, and drive"
2. **Context-Sensitive Remapping**: During mixing → knobs map to track volumes; during performance → knobs map to synth parameters
3. **Cross-Controller Translation**: "Switching from MPK Mini 3 (8 pads) to Launchkey 49 (16 pads)" — AI translates the workflow mapping
4. **Real-Time Co-Performance**: Auto-harmonize played notes, smart arp routing, contextual fill generation

> **GPT**: "This is the hidden iceberg: the Target_control enumeration is opaque. The existing .xmm files only map to a subset. Reverse-engineering all 116+ targets is a significant Phase 1 research task."

---

## 9. Genre DNA System

### Genre as Computable Vectors

Each genre encoded as a multi-dimensional fingerprint:

| Genre | Complexity | Chromatic | Voicing Spread | Swing | Vintage | Tempo Range |
|---|---|---|---|---|---|---|
| Neo Soul | 0.85 | 0.8 | 0.9 | 0.6 | 0.4 | 72-88 |
| Gospel | 0.9 | 0.7 | 0.7 | 0.5 | 0.3 | 65-90 |
| Jazz | 0.95 | 0.9 | 0.8 | 0.7 | 0.5 | 80-180 |
| House | 0.3 | 0.2 | 0.4 | 0.1 | 0.2 | 120-130 |
| Trap | 0.3 | 0.4 | 0.3 | 0.2 | 0.1 | 130-145 |
| RnB | 0.7 | 0.5 | 0.6 | 0.5 | 0.3 | 70-100 |

### Genre Fusion Algorithm

To blend "neo-soul with gospel influences," interpolate the DNA vectors:
- Primary weight 0.7 (Neo Soul) + 0.3 (Gospel)
- Resulting: complexity 0.87, chromatic 0.77, voicing spread 0.84
- Guides macro decisions: "use secondary dominants moderately," "add vintage character via MPC60 processing"

### Genre Innovation

"What if house had jazz complexity?" pushes House's chord_complexity from 0.3 to 0.8 while maintaining its rhythmic density and repetition. The AI generates something genuinely novel.

---

## 10. Creative Risk & Happy Accidents

### The Creativity Architecture

> **GPT proposed a single creativity dial. Gemini argued for splitting it:**

**Consensus: Two Dials**

| Dial | 25% | 50% | 75% | 90% |
|---|---|---|---|---|
| **Harmonic** | Borrowed chords from parallel modes | Modal interchange, chromatic mediants | Polytonality, tritone subs | Any chord from any mode |
| **Rhythmic** | Slight syncopation variations | Displacement by 2 subdivisions, cross-genre rhythms | Independent rhythmic cycles, metric modulation | Complete polyrhythmic freedom |

> **Gemini**: "Cap meaningful variation at ~80%. 80-100% should be 'AI's best judgment for maximum surprise that still resolves.' True randomness isn't creative, it's noise."

### Concrete Happy Accident Examples (Using Real MPC Beats Assets)

1. **"Gospel Contamination"**: Layer `035-Chord-Soul Ballad 01.mid` (transposed -5) over a trap bass pattern. The gospel voicings against 808s = Kanye "Jesus Walks" tension.

2. **"Register Swap"**: Pitch the bass arp up 2 octaves → route to `Hype Saw Lead`. Pitch chord progression down 1 octave → route to `Deep Sub Bass`. Inverts the textural hierarchy (à la Arca, Sophie).

3. **"Arp as Percussion"**: Load `050-Melodic-Techno 01.mid` but assign to a clicky percussion (Rimshot/Clave). The arp becomes a pitched percussion sequence — like Afrobeats steel drum processed through techno.

4. **"Tempo Domain Collision"**: Import `044-Melodic-Lead Hip Hop 01.mid` without time-stretching over a 140 BPM dance track. The tempo mismatch creates polyrhythmic IDM effects (Aphex Twin territory).

5. **"Reverse Function"**: Use `069-Bass-Synth Dance 01.mid` as a chord pattern — route to `Warm Pad`, pitch up an octave. The syncopated bass rhythm as pad chords creates unexpected breathing quality.

### Guardrails: "Creative Wrong" vs. "Just Wrong"

> **GPT**: "The algorithmic test: How many constraints does the suggestion violate, and which types? Violates 0 foundational + 1-3 expectation constraints = happy accident territory. Violates 1+ foundational constraints = just wrong."

Foundational constraints (never violate): voice-leading continuity, frequency masking limits, metric coherence floor.
Expectation constraints (intentionally violable): genre conventions, standard instrument roles, typical register assignments.

---

## 11. Quality Assurance & Self-Evaluation

### Multi-Critic Architecture

> **Initial consensus was 4 separate critics. Gemini refined the approach:**

**Final architecture: Single-pass multi-dimensional scoring with 4 axes:**

1. **Harmony Critic**: Voice leading, key coherence, progression sophistication
2. **Rhythm Critic**: Groove consistency, swing feel, density appropriateness
3. **Arrangement/Mix Critic**: Frequency allocation, stereo field, dynamic range
4. **Vibe Critic** (meta): Overall emotional coherence — do the parts work as a whole?

**Consensus thresholds:**
- No axis below 0.5 (hard floor)
- Average across all axes ≥ 0.7
- Vibe Critic ≥ 0.5 (hard gate — if the vibe is wrong, nothing else matters)

> **Gemini**: "Don't use 4 separate LLM passes — that's 4x latency. Use a single pass with structured output schema that scores all dimensions simultaneously."

> **GPT**: "The Vibe Critic should have hard veto, not soft. A technically perfect arrangement that doesn't vibe is worse than a sloppy one that does."

### Rejection → Targeted Regeneration

When a critic axis scores below threshold:
- Produce specific diagnosis ("harmonic content too simple for Frank Ocean profile")
- Regenerate **only the failing substep** with modified constraints
- Maximum 3 regeneration cycles
- If still unsatisfied: present best version with explicit caveats

### A/B Generation

Generate 2-3 alternatives for each element, evaluate head-to-head, select highest-scoring while explaining tradeoffs.

---

## 12. DAW Integration Strategy

### The Hybrid Architecture (Consensus)

> **Both reviewers converged on a hybrid MIDI + file-based approach:**

```
┌─────────────────────────────────────────────────────┐
│                 VS Code Extension                    │
│                                                      │
│  ┌────────────┐  ┌────────────┐  ┌───────────────┐  │
│  │ Copilot    │  │ File Gen   │  │ MIDI Engine   │  │
│  │ Chat @mpc  │  │ Service    │  │ (node-midi)   │  │
│  └─────┬──────┘  └─────┬──────┘  └──────┬────────┘  │
│        │               │                │            │
│  ┌─────┴───────────────┴────────────────┴─────────┐  │
│  │           Orchestrator / Command Router         │  │
│  └─────┬───────────────┬────────────────┬─────────┘  │
│        │               │                │            │
│   Intelligence     Asset Files      Real-time        │
│   (LLM+embeddings) (.progression,   MIDI Control     │
│                     .mid, .xpl)    (CC, Notes,       │
│                                    Transport)        │
└────────┼───────────────┼────────────────┼────────────┘
         │               │                │
         ▼               ▼                ▼
   Recommendations  MPC Beats Folders  Virtual MIDI Port
                    (hot-load)        "MPC AI Controller"
                                           │
                                           ▼
                                      MPC Beats.exe
```

### Channel Division

| Channel | Purpose | Examples |
|---|---|---|
| **File-based** | Static artifacts | .progression files, complete .mid compositions, .xmm controller maps |
| **Virtual MIDI** | Dynamic/real-time | Transport control, parameter tweaking, "play-in" recordings, preset switches |
| **Chat** | Recommendations | Analysis, music theory teaching, workflow guidance |

### Virtual MIDI Port Setup

- **Windows**: loopMIDI (user-installed) or virtualMIDI SDK (bundled)
- **Node.js bridge**: `easymidi` or `node-midi` (RtMidi binding)
- **Latency**: 2-5ms total (negligible — typical hardware USB MIDI is 1-3ms)
- **Custom .xmm**: Creates a "MPC AI Controller" mapping file

### The "Play It In" Feature

> **Gemini**: "Instead of file import, the AI literally performs the composition into MPC Beats via virtual MIDI. User arms recording, AI sends MIDI Start, then streams note events with precise timing. MPC Beats records it as a live performance."

> **GPT**: "This is genuinely brilliant — but timing synchronization needs pre-scheduled note events against an internal clock, not reactive firing. MIDI clock sync is essential for multi-note sequences."

---

## 13. State Management & Iteration UX

### Song State Object

```
SongState {
  metadata: { title, key, tempo, time_sig, influences[], mood_tags[] }
  tracks: [
    { id, name, role, midi_source, preset, effects_chain[], pan, volume }
  ]
  arrangement: {
    sections: [{ name, start_bar, end_bar, active_tracks[] }],
    energy_arc: [(bar, energy_value)],
    transitions: [{ from, to, type }]
  }
  progression: {
    chords: [{ symbol, midi_notes[], duration_beats }],
    key_centers: [{ chord_index, key }]
  }
  history: [
    { turn, user_request, changes_made[], previous_values[] }
  ]
}
```

### Hierarchical Compression (4 Levels)

| Level | Content | Tokens | Use |
|---|---|---|---|
| L0 Summary | "8 tracks, Eb minor, 130 BPM, neo-soul/ambient" | ~100 | Quick context |
| L1 Structural | All names/roles/presets, section boundaries, chord symbols | ~500 | Most decisions |
| L2 Detailed | Full MIDI notes, exact parameters, full effect chains | ~3000 | Note-level work |
| L3 History | Every change with before/after values | Variable | Undo, learning |

> **Gemini**: "Serialize from turn 1 — the JSON file IS the project file. Git tracks it for free. Use spatial pruning (by section) rather than temporal pruning (by turn count)."

### 10-Turn Iteration Example

> **GPT provided a complete dialogue:**
> Turn 1: "Late-night R&B, Frank Ocean vibes, ~130 BPM" → Initial SongState
> Turn 2: "3rd chord too bright, make darker" → Gbmaj9 → Gbm9
> Turn 3: "Too dark, find middle ground" → History lookup → Gb6/9
> Turn 4: "Add bass layer" → Generate bassline from SynBass arp
> Turn 5: "Bass too busy, simplify" → Reduce density 40%
> Turn 6: "Add Burial-style vocal chops" → Simulate with short-decay synth + pitch-bend
> Turn 7: "Build the arrangement" → Create verse/chorus structure
> Turn 8: "Verse feels empty, add something subtle" → Delay throws + quiet ride cymbal
> Turn 9: "Make it warmer overall" → Global parameter adjustments
> Turn 10: "Keep vocal chops bright though" → Selective undo from history

### Contradiction Handling

Three strategies:
1. **Temporal Override**: Latest instruction wins for the specific element
2. **Scope Detection**: Ask for clarification only when ambiguous
3. **Synthesis**: "Warm + bright" = analog warmth in low-mids + sparkle on top (different frequency ranges)

### Context Window Mitigation

- Carry L1 + L2 only for active elements; load L2 on demand
- Prune history after consolidation (merge sequential edits)
- Serialize to external JSON file for songs exceeding ~25 turns
- **Speculative generation**: Pre-generate 2-3 likely follow-up variants in parallel to hide latency

> **Gemini**: "Latency compounding in iterative workflows is the biggest unaddressed risk. Pre-generate likely follow-ups to hide it."

---

## 14. Personalization & Learning

### Implicit Preference Modeling

| Signal | Method |
|---|---|
| Acceptance velocity | Immediate "yes" = high match. 5 iterations = first suggestion off |
| Modification delta | Always bumps tempo +10 → learn tempo bias. Always picks brighter pad → learn brightness preference |
| Genre frequency | Which genres requested most → build prior |
| Rejection vocabulary | "Too dark" → adjust brightness preference vector |
| Embedding centroids | Track accepted preset/progression embeddings → predict future preferences |

### Preference Vector

```
brightness:      -1 (dark) → +1 (bright)
complexity:      -1 (simple) → +1 (complex)
energy:          -1 (chill) → +1 (hype)
density:         -1 (sparse) → +1 (dense)
experimentalism: -1 (conventional) → +1 (avant-garde)
tempoAffinity:   Average BPM delta from genre default
voicingSpread:   -1 (tight) → +1 (open)
```

Converges after ~10-15 interactions. Stored locally in `context.globalStorageUri`.

### Avoiding the Echo Chamber

- **20% exploration budget**: Epsilon-greedy strategy — always suggest some outside-preference-zone options
- **Genre-bridging**: Find overlaps between user's genre preferences
- **Temporal novelty decay**: After 10 sessions with the same preset, surface alternatives
- **Explicit "/surprise" mode**: Intentionally inverts parts of the preference vector

### Production Personas

> **Gemini proposed auto-detection. GPT pushed back:**

> **GPT**: "Time-of-day heuristics are fragile and presumptuous. It feels like surveillance."

**Consensus: Explicit, user-driven modes.**
- The system *suggests* creating modes after detecting patterns: "You've started 5 sessions with Neo Soul and warm pads. Want to save this as a preset mode?"
- The user names and controls the modes
- `@mpc switch to gospel mode` loads the associated preference vector

---

## 15. Competitive Analysis & Moat

### This Platform vs. Suno/Udio/Boomy

| Dimension | Suno/Udio | This Platform |
|---|---|---|
| **Output** | Rendered audio (opaque) | MIDI + synth config + effect chains (editable) |
| **Editability** | None — regenerate entirely | Full note-level, parameter-level control |
| **Hardware** | Zero integration | 67+ controllers with intelligent mapping |
| **Sound Engine** | Black box neural audio | Named, tweakable synths (TubeSynth, Velvet, etc.) |
| **Learning** | User learns nothing | User sees *why* each decision was made |
| **Approach** | Replace the producer | Augment the producer |
| **Vintage Character** | Generic "vintage" filter | Authentic MPC3000/MPC60/SP1200 emulation |
| **Real-Time** | Offline generation only | Live co-performance with hardware |
| **Copyright** | Opaque training data (lawsuits) | Traceable to theory + user's asset library |

### The 5x Moat

> **Gemini**: "The moat is: depth of musical reasoning × native tool integration × symbolic editability × hardware-in-the-loop × compounding knowledge from the production corpus. No competitor attacks all five simultaneously."

### Killer Differentiating Features

1. **"X-Ray Mode"**: Ask "why?" for any AI decision and get music-theory explanation grounded in the actual corpus
2. **"Genre Reactor"**: Drag genre sliders and hear music transform
3. **"Deconstruct This"**: Drop any MIDI file → reverse-engineer the recipe using MPC Beats assets
4. **"Controller Consciousness"**: "Try turning knob 3 to sweep the filter — I've mapped it to TubeSynth cutoff"
5. **Live MIDI Harmonization**: Play a melody → AI generates complementary parts in real-time

> **Gemini**: "Suno and Udio are jukebox machines. This is a creative amplifier. The tagline: 'Not AI-generated music. AI-elevated music.'"

> **GPT**: "'Deconstruct This' is the feature that would make producers say 'I need this.' Every producer has reference tracks they want to understand. Turning 'how did they make this sound?' into a one-click answer is genuinely differentiated."

---

## 16. Legal & IP Analysis

### Risk Assessment

| Action | Risk Level | Reasoning |
|---|---|---|
| Reading .progression files for analysis | **Very Low** | Interoperability, local only |
| Generating new .progression files | **Very Low** | Chord progressions aren't copyrightable |
| Reading preset names for indexing | **Very Low** | Functional identifiers, not redistributed |
| Sending MIDI to MPC Beats via virtual port | **None** | MIDI is an open standard |
| Creating .xmm controller mappings | **Low** | Functional format, interoperability |
| Bundling Akai presets/progressions WITH extension | **High** | Redistribution — never do this |
| Using "MPC" in extension name | **Medium-High** | Registered trademark — avoid |

### Legal Framing

> **Gemini**: "This is fundamentally a Photoshop plugin, not a Photoshop fork. Frame as 'compatible with MPC Beats' with explicit disclaimer: 'This extension is not made by, endorsed by, or affiliated with Akai Professional or inMusic.'"

> **GPT**: "Avoid 'MPC' in the extension name entirely. Use it only in descriptions for nominative fair use. Also: preset descriptions should describe sonic character ('warm analog pad'), never parameter values ('OSC1: Saw, Detune: 7, Filter Cutoff: 4200Hz'). The distinction matters for derivative work analysis."

---

## 17. Risks & Challenges

### Technical Risks

| Risk | Severity | Mitigation |
|---|---|---|
| MPC Beats is a closed binary — no API | **Critical** | Virtual MIDI + file-based hybrid approach |
| Target_control indices are undocumented | **High** | Systematic reverse-engineering in Phase 1 |
| Preset parameter files (.xpl) are binary/encoded | **Medium** | Limit to preset *selection*, not preset *design* |
| Real-time latency for co-performance | **Medium** | Pre-computed response tables, local inference |
| Audio output gap (can't generate/evaluate audio) | **Medium** | Operate on structural/theoretical metrics |
| MPC Beats version fragility | **High** | Version detection + compatibility matrix |
| Context window limits for complex songs | **Medium** | Hierarchical state compression, external serialization |
| Latency compounding in iterative workflows | **High** | Speculative generation of likely follow-ups |

### Strategic Risks

| Risk | Severity | Mitigation |
|---|---|---|
| IP/trademark exposure | **Medium** | Clean naming, disclaimers, no asset redistribution |
| Genre evolution (static DNA stales) | **Low** | Mechanism to ingest new reference material |
| User skill spectrum (beginner vs. advanced) | **Medium** | Adaptive interaction depth |
| "Uncanny valley" of AI music (90% good = sounds wrong) | **High** | Multi-critic quality gates, transparency about limitations |

> **GPT**: "MPC Beats version fragility is the biggest unaddressed risk. Akai can ship an update that silently breaks our entire integration. We need version detection and compatibility matrix from day one."

> **Gemini**: "The hardest problem isn't technical — it's taste calibration. The system that wins learns what this specific user thinks sounds good after 10 sessions, and silently adjusts every threshold, weight, and default to match."

---

## 18. Implementation Roadmap

| Phase | Focus | Deliverable |
|---|---|---|
| **0 — Foundation** | Extension scaffold, tool registration, .progression/.xmm parsers, Song State schema | `@mpc` participant responds, reads all data |
| **1 — Harmonic Brain** | Progression generation, chord analysis, theory explanations, Target_control mapping research | `/harmony` and `/theory` functional |
| **2 — Embeddings & Search** | Build description catalog, local embedding index, semantic asset search | "Warm Sunday morning" → progressions + presets |
| **3 — Rhythm Engine** | MIDI generation, humanization, arp pattern manipulation | `/compose` generates drum + bass MIDI |
| **4 — Sound Oracle** | Preset recommendation, effect chain generation, parameter specification | `/sound` and `/mix` functional |
| **5 — Virtual MIDI** | loopMIDI integration, custom .xmm, transport control, "play-in" | Real-time DAW control |
| **6 — Full Pipeline** | End-to-end song generation from prompt to multi-track output | `/compose` produces complete sessions |
| **7 — Controller Intelligence** | Hardware auto-configuration, performance adaptation | `/controller` functional |
| **8 — Creative Frontier** | Surprise mode, genre-bending, self-evaluation, multi-critic quality gates | `/surprise`, quality scoring |
| **9 — Personalization** | Preference learning, producer modes, speculative generation | Adaptive suggestions |
| **10 — Live Performance** | Real-time MIDI input → AI harmonization and arrangement | Jam session co-pilot |

### Phase 1 Priority (Consensus)

> **Gemini**: "The single most important decision is the Song State schema and serialization format. Everything flows downstream. Decide now whether state is chord-symbol-level (abstract) or note-event-level (concrete). The answer: both, in separate layers — designed upfront."

> **GPT**: "The .xmm Target_control mapping table. Everything downstream depends on knowing which index corresponds to which MPC Beats function."

**Synthesized Phase 1 priorities:**
1. Song State schema design (the contract between all components)
2. `.progression` parser + enrichment pipeline
3. Target_control reverse-engineering and documentation
4. Asset description catalog authoring
5. Basic `@mpc /theory` agent (no DAW integration needed)

---

## 19. Naming & Identity

### Proposals

| Name | Source | Rationale | Trademark Risk |
|---|---|---|---|
| **MUSE** | Gemini | Music Understanding and Synthesis Engine. Mythological resonance | Low (common word) |
| **Harmonia** | Gemini | Emphasizes harmonic intelligence. Born from union of opposites | Low |
| **BeatCode** | GPT | Fuses "Beats" + "Code". Works as VS Code extension ID | Low-Medium |
| **GridForge** | GPT | References MPC pad grid without trademark. Implies crafting | Low |

> **GPT**: "Avoid anything with 'AI' in the name (market saturation) or 'MPC' (trademark risk)."

**Recommendation**: **MUSE** as primary brand, with extension ID `muse.muse-copilot`.

### Tagline

> "Not AI-generated music. AI-elevated music." — Gemini

---

## 20. Reviewer Comments & Cross-Pollination Log

### Round 1: Initial Analysis

**Gemini's strongest contributions:**
- The multi-agent architecture with 6 specialized agents and tool surface
- The 5-layer knowledge graph (Harmonic Atoms → Genre Fingerprints → Arp Pattern DNA → Sound Palette Ontology → Effect Chain Templates)
- Detailed genre DNA vector system with numerical fingerprints
- The phase 1 execution priority emphasizing theory-first approach
- The "Not AI-generated music. AI-elevated music." tagline

**GPT's strongest contributions:**
- The Tier 3 "Emergent Understanding" concept (tension/resolution/arc as continuous energy functions)
- The complete Frank Ocean + Burial walkthrough with algorithmic reasoning at every step
- The micro-timing and humanization framework (per-instrument swing, flam/drag, ghost notes)
- The multi-critic architecture with the "Vibe Critic" concept
- The composability and iteration UX (10-turn dialogue example)

### Round 2: Deep Dives

**Gemini's unique deep-dive insights:**
- Virtual MIDI port architecture with node-midi + custom .xmm as "virtual controller" — the most viable DAW integration path
- Copilot Variables with tiered enrichment (L1: symbols, L2: voice leading, L3: genre associations)
- Local embedding model (all-MiniLM-L6-v2 via ONNX) — 1.8MB index, <1ms search, no vector DB needed
- Orchestrator DAG with typed AgentResult<T>, confidence scores, freeze/unfreeze semantics
- Producer personas with automatic detection (later refined to explicit user-driven modes)
- Legal analysis: "compatible with" framing, interoperability rights, safe boundaries

**GPT's unique deep-dive insights:**
- Concrete tension formula: $T = w_r R + w_s(1-S) + w_d D + w_c C$ with computed values for actual Godly chords
- Energy function interaction terms: $\delta \cdot H(t) \cdot R(t)$ — harmonic tension × rhythmic density amplifies exponentially
- Happy Accident guardrail system: foundational vs. expectation constraints, precedent checking
- Multi-critic with specific consensus mechanism (no axis < 0.3, average ≥ 0.6, vibe ≥ 0.5)
- Song State with 4-level hierarchical compression and context window mitigation strategies
- User-drawn emotional arc → constraint decomposition → AI composition

### Round 3: Cross-Pollination Consensus

**Where both reviewers agreed:**
- Hybrid MIDI + file-based architecture is the right path
- Local embedding model over cloud API
- Typed agent communication with confidence scores
- Explicit user-driven producer modes (not auto-detection)
- Legal safety of the plugin/interoperability model
- The Vibe Critic needs strong authority in quality evaluation
- Single-pass multi-dimensional scoring, not separate LLM calls per critic

**Where they productively disagreed:**

| Topic | Gemini Position | GPT Position | Synthesis |
|---|---|---|---|
| Creativity dial | Single dial, cap at 80% | Parameterized by constraint type | **Two dials: harmonic + rhythmic** |
| Critic thresholds | Floor 0.5, average 0.7 | Floor 0.3, average 0.6 | **Gemini's stricter thresholds adopted** |
| Half-time as derived vs. encoded | Encode the principle, let LLM apply | Feasible as emergent reasoning | **Gemini's hybrid approach adopted** |
| Auto-detection of personas | Brilliant concept, auto-detect from patterns | Concept good, auto-detection "feels like surveillance" | **User-driven with suggestions** |
| Phase 1 priority | Song State schema | Target_control mapping | **Both — schema is the contract, targets are the capability** |
| History pruning | Spatial (by section) over temporal (by turn count) | Temporal (after 10 turns) | **Gemini's spatial approach adopted** |
| Emotional arc UX | Segmented sliders (default) + freehand curve (advanced) | Freehand curve with spline interpolation | **Gemini's tiered UX adopted** |
| Project name | MUSE (Music Understanding and Synthesis Engine) | BeatCode (Beats + Code) | **MUSE recommended** |

**Gemini's final killer feature proposal:**
> "Live MIDI Input → Real-Time AI Harmonization. User plays a melody on a controller, the system identifies key/mode and immediately generates complementary parts — bass, chords, counter-melody — that play back through virtual instruments WHILE the user is still performing. This turns the AI from an assistant into a band member you jam with."

**GPT's final killer feature proposal:**
> "'Deconstruct This' — drop any MIDI file and the system reverse-engineers the recipe using MPC Beats assets. 'This sounds like Neo Soul 1.progression with arp pattern 025-Chord-Old School RnB 01 on TubeSynth Analog Tube Richness.' Turning 'how did they make this sound?' into a one-click answer."

**Gemini's final philosophical statement:**
> "The hardest problem isn't technical — it's taste calibration. 'Good' is subjective, genre-dependent, era-dependent, and deeply personal. The implicit personalization layer — never discussed, never shown in UI, but always adapting — is what makes the difference between a tool and a collaborator."

**GPT's final philosophical statement:**
> "This is not an AI that makes music. This is an AI that understands music at the level of a conservatory-trained, studio-veteran, genre-omnivorous producer — and it speaks directly through the tools a professional already uses."

---

## Appendix: Asset Summary Statistics

| Category | Count | Genres Covered |
|---|---|---|
| Chord Arp Patterns | 38 | Chill Out, Dance, Fast Pop, Old School RnB, Rhythm, Soul Ballad |
| Melodic Arp Patterns | 18 | Lead Dubstep, Lead Hip Hop, Techno, Plucked Muted, Rhythmic Echo |
| Bass Arp Patterns | 24 | Rhythm, Slap, SynBass, Synth Dance, Synth Eighties, Synth Hip Hop |
| Progressions | 47 | Gospel, Neo Soul, Jazz, House, Trap, RnB, Pop, Soul, Tech House, Classic House, Deep House |
| Controller Maps | 67 | 7 manufacturers (Akai, Alesis, Arturia, Korg, M-Audio, NI, Novation) |
| Synth Engines | 15+ | TubeSynth, Bassline, Electric, DrumSynth×10, + 8 VSTs |
| Effects | 60+ | Compressors, EQs, Delays, Reverbs, Distortions, Filters, Modulation, Character (SP1200, MPC60, MPC3000) |
| TubeSynth Presets | 297 | Synth(44), Lead(50), Pluck(40), Pad(68), Bass(65), Organ(7), FX(23) |

---

*This document represents the synthesis of 3 rounds of parallel brainstorming across two premium AI models, cross-pollinated for maximum insight coverage. It serves as the architectural blueprint for implementation.*

*Next step: Begin Phase 0 — Foundation (Extension scaffold, tool registration, Song State schema, .progression parser).*
