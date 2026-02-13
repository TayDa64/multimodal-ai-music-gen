# MUSE × multimodal-ai-music-gen: Integration Synthesis Report

> **Generated**: February 10, 2026  
> **Purpose**: Comprehensive analysis of integrating MUSE AI intelligence specs into the multimodal-ai-music-gen application  
> **Reviewers**: 4 subagent reviews across 2 rounds (architecture + algorithm deep-dives)  
> **Status**: CONSENSUS REACHED — integrate into multimodal-ai-music-gen  
> **Action**: Move this file to `multimodal-ai-music-gen/docs/muse-specs/` once repo is cloned locally

---

## Executive Summary

**Unanimous verdict: Integrate MUSE intelligence into multimodal-ai-music-gen. Kill the standalone MUSE project.**

MUSE has 91 tasks across 11 phases, 15 contracts, and 14 architecture decisions — but 0% implementation and no audio output capability. multimodal-ai-music-gen has a working pipeline (PromptParser → Arranger → MIDIGenerator → AudioRenderer → MPCExporter), 8 performer agents, a JUCE real-time audio frontend, and MPC export — but its algorithm "is not fully functional" and produces beginner-sounding output.

The projects solve the same problem at different layers. MUSE has the **brain** (harmonic theory, genre DNA, quality critics, personalization). multimodal-ai-music-gen has the **body** (MIDI generation, audio synthesis, GUI, performer agents). Merging them produces a complete system. Building MUSE standalone would take 30-38 weeks to reach MVP with no audio output and dependence on a closed-source DAW.

---

## Table of Contents

1. [Reviewer Consensus & Divergences](#1-reviewer-consensus--divergences)
2. [Architecture Decision: 3-Layer Model](#2-architecture-decision-3-layer-model)
3. [Agent Reconciliation: X-Axis × Y-Axis](#3-agent-reconciliation-x-axis--y-axis)
4. [Copilot SDK Placement](#4-copilot-sdk-placement)
5. [Data Model Unification](#5-data-model-unification)
6. [Why the Algorithm Sounds "Beginner"](#6-why-the-algorithm-sounds-beginner)
7. [The 10 Cardinal Sins of AI Music](#7-the-10-cardinal-sins-of-ai-music)
8. [Voice Leading: The #1 Fix](#8-voice-leading-the-1-fix)
9. [Genre DNA: The 10 Dimensions](#9-genre-dna-the-10-dimensions)
10. [Quality Gate Design](#10-quality-gate-design)
11. [MPC Beats Data Extraction Plan](#11-mpc-beats-data-extraction-plan)
12. [The JUCE Question](#12-the-juce-question)
13. [4-Week Sprint Plan](#13-4-week-sprint-plan)
14. [The Masterclass Test](#14-the-masterclass-test)
15. [Risk Assessment](#15-risk-assessment)
16. [Gap Analysis](#16-gap-analysis)
17. [What Gets Removed, Kept, Enhanced](#17-what-gets-removed-kept-enhanced)
18. [Final Recommendation & Next Steps](#18-final-recommendation--next-steps)

---

## 1. Reviewer Consensus & Divergences

### Full Consensus (All 4 Reviews Agree)

| Decision | Position |
|----------|----------|
| **Merge?** | Yes — MUSE brain + multimodal body |
| **Kill standalone MUSE?** | Yes — it will never ship as a standalone project |
| **Priority #1** | Voice leading engine — highest single-change ROI for music quality |
| **Agent model** | 3-layer: Intent → Domain Intelligence → Performance |
| **Data model** | Extend SessionGraph (don't replace with SongState) |
| **MPC data** | Extract musical knowledge from 47 progressions + 80 arp patterns |
| **Offline-first** | All musical intelligence must work without cloud LLM |
| **Electron standalone?** | No — would require 6-9 months to reach feature parity |
| **MUSE Controller Intelligence (P7)** | Deprioritize — MPC-specific, not critical path |

### Divergences (Resolved)

| Question | Reviewer 1 | Reviewer 2 | Resolution |
|----------|-----------|-----------|------------|
| **JUCE** | Keep as primary GUI + audio engine | Consider dropping entirely | **Keep frozen as passive viewport.** Zero new features for 8 weeks. All creation logic in CLI + Python. (See Section 12) |
| **Copilot SDK role** | Optional NL interface alongside Python | "Brain" with Python as "hands" via defineTool() | **TypeScript CLI as router/session manager, Python persistent process as intelligence engine.** (See Section 4) |
| **Where intelligence lives** | Port MUSE concepts to Python modules | Copilot SDK makes musical decisions | **Python owns all musical intelligence (HarmonicBrain, GenreDNA, Critics). Copilot SDK adds NL understanding and conversational iteration. Music theory is deterministic code, not LLM inference.** |

---

## 2. Architecture Decision: 3-Layer Model

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Layer 1: INTENT (Copilot SDK CLI — TypeScript)                          │
│                                                                          │
│  - JSON-RPC over stdin/stdout                                            │
│  - customAgents with infer:true for routing                              │
│  - defineTool() wrappers calling Layer 2                                 │
│  - Context window management (L0-L3 compression)                         │
│  - Session state, hooks, streaming                                       │
│  - NL interpretation: "dark neo-soul with gospel" → constraints          │
│                                                                          │
│  Decomposes user intent into musical specifications                      │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ JSON-RPC over stdio (or local socket)
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Layer 2: DOMAIN INTELLIGENCE (Python — persistent process)              │
│                                                                          │
│  ┌──────────────┐ ┌──────────┐ ┌───────────┐ ┌──────────┐              │
│  │ HarmonicBrain│ │ GenreDNA │ │ Embeddings│ │ Critics  │              │
│  │              │ │          │ │ (ONNX)    │ │          │              │
│  │ Voice leading│ │ 10-dim   │ │ Preset    │ │ 5-axis   │              │
│  │ Tension func │ │ vectors  │ │ search    │ │ scoring  │              │
│  │ Chord subst  │ │ Genre    │ │ Similarity│ │ Quality  │              │
│  │ Voicing      │ │ fusion   │ │           │ │ gate     │              │
│  └──────┬───────┘ └────┬─────┘ └─────┬─────┘ └────┬─────┘              │
│         │              │             │             │                     │
│         └──────────────┴─────────────┴─────────────┘                     │
│                        │                                                 │
│         OUTPUT: PerformanceScore (not MIDI — a specification)            │
│         { chords, voicings, groove_template, timbral_palette, mix }      │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ PerformanceContext (enriched)
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Layer 3: PERFORMANCE (Python — existing agents)                         │
│                                                                          │
│  ┌──────────┐ ┌──────────┐ ┌────────────┐ ┌──────────┐ ┌──────────┐   │
│  │ Drummer  │ │ Bassist  │ │ Keyboardist│ │ Krar     │ │ Kebero   │   │
│  │ Agent    │ │ Agent    │ │ Agent      │ │ Agent    │ │ Agent    │   │
│  └──────────┘ └──────────┘ └────────────┘ └──────────┘ └──────────┘   │
│                                                                          │
│  These agents receive enriched PerformanceContext from Layer 2           │
│  and execute it with personality, humanization, and variation.            │
│                                                                          │
│  OUTPUT: Dict[track_name, List[NoteEvent]] → MIDI + Audio + MPC export  │
└─────────────────────────────────────────────────────────────────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
        ┌──────────┐     ┌────────────┐     ┌────────────┐
        │ MPC Beats│     │ JUCE App   │     │ WAV/MIDI   │
        │ (virtual │     │ (passive   │     │ files      │
        │  MIDI)   │     │  viewport) │     │            │
        └──────────┘     └────────────┘     └────────────┘
```

### Why 3 Layers, Not 2

The naive approach — Copilot SDK talks directly to performers — conflates LLM reasoning with musical intelligence. The HarmonicBrain and GenreDNA should be **deterministic Python code**, not LLM chain-of-thought. An LLM shouldn't guess which chord voicing has the best voice leading when a 10-line algorithm computes it exactly.

Layer 2 is where MUSE's real value lives: music theory encoded as code, not as prompts.

---

## 3. Agent Reconciliation: X-Axis × Y-Axis

> *"This is the hardest design problem in the integration."* — Reviewer 2

MUSE's agents and multimodal's agents are **orthogonal**, not competing:

**MUSE agents (X-axis — cross-cutting concerns):**
- HarmonyAgent: "What chords should play?" → affects ALL melodic/harmonic instruments
- RhythmAgent: "What groove pattern?" → affects ALL rhythmic instruments  
- SoundAgent: "What timbre/preset?" → affects ALL sound sources
- MixAgent: "What frequency allocation?" → affects ALL tracks simultaneously

**multimodal agents (Y-axis — instrument instances):**
- DrummerAgent: "What do I play?" → handles ALL concerns for drums
- BassistAgent: "What do I play?" → handles ALL concerns for bass
- KeyboardistAgent: "What do I play?" → handles ALL concerns for keys

### The Bridge: PerformanceContext

The `PerformanceContext` already exists and carries `bpm`, `key`, `tension`, `chords`, `kick_ticks`, etc. Extend it with MUSE intelligence:

| New Field | Source | Consumers |
|-----------|--------|-----------|
| `voicing_constraints` | HarmonyAgent (voice leading rules, register ranges) | KeyboardistAgent, BassistAgent |
| `groove_template` | RhythmAgent (swing amount, ghost density, micro-timing) | DrummerAgent, BassistAgent |
| `genre_dna` | GenreDNA system (10-dimensional vector) | All agents |
| `tension_curve` | HarmonicBrain (composite energy function) | Conductor orchestration |
| `orchestration_map` | Conductor (which agents play per tension level) | All agents |

### The Critical Rule

> HarmonyAgent decides chord voicings. KeyboardistAgent executes them with performance character (timing, velocity, arpeggiation). **The KeyboardistAgent never overrides the harmonic content.** The OfflineConductor becomes a pure scheduler — it stops making musical decisions and only handles execution logistics.

---

## 4. Copilot SDK Placement

### The Design

```
Copilot SDK (TypeScript CLI)
├── customAgents with infer:true route to domains
├── defineTool("generate_section") → calls Python intelligence server
├── defineTool("analyze_harmony") → calls Python HarmonicBrain
├── defineTool("evaluate_quality") → calls Python CriticSystem
├── defineTool("search_presets") → calls Python embedding index
├── defineTool("play_into_mpc") → calls Python virtual MIDI
└── hooks: onSessionStart → load SongState at L1 compression
```

**Python Intelligence Server**: A persistent process (spawned once via `child_process.spawn()` or as a tiny FastAPI HTTP server on localhost), NOT a subprocess-per-call. Communicates via JSON-RPC over stdio or local HTTP. Exposes all existing modules as callable endpoints.

**The user interacts via**: VS Code terminal (or any terminal). Natural language in, streaming progress out. The JUCE app (if running) receives OSC notifications and passively displays piano roll.

### Offline Mode

Critical. All musical intelligence (HarmonicBrain, GenreDNA, Critics, performers) runs locally in Python — zero cloud dependency. The only cloud dependency is the LLM for NL understanding via Copilot SDK, and that's swappable (Ollama, LM Studio for local models). The system must produce masterclass output with `--offline` flag using pure algorithmic generation.

### Context Window Management (L0-L3)

Implemented as methods on SessionGraph:

| Level | Tokens | Content | Use Case |
|-------|--------|---------|----------|
| L0 | ~100 | "8 tracks, Eb minor, 130 BPM, neo-soul/ambient" | Every turn's system message |
| L1 | ~500 | Chord symbols, track names, section boundaries | Most musical decisions |
| L2 | ~3000 | Full MIDI, exact parameters, effect chains | Note-level editing |
| L3 | Variable | All history with before/after deltas | Undo/redo, preference learning |

---

## 5. Data Model Unification

### SessionGraph Wins Over SongState

| Reason | Detail |
|--------|--------|
| **Implemented & tested** | 1350+ lines with full serialization, round-trip validation, builder pattern |
| **Has features MUSE lacks** | Constraint system, take lanes, render directives, per-section instrument enables, groove templates |
| **Pipeline-integrated** | `SessionGraphBuilder.build_from_prompt()` and `build_from_arrangement()` already connected |

### What to Add to SessionGraph

```python
# New fields for MUSE compatibility:
genre_dna: GenreDNAVector          # Replace string genre with 10-dim vector
progression: ProgressionState      # Explicit chord progression with tension values
preferences: UserPreferences       # MUSE's C14 personalization
mix_state: MixState                # Richer effects chain model
# Enhanced history: add previousValues[] for undo/redo
# Compression methods: to_summary(), to_structural(), to_detailed(), to_history()
```

### Detailed Comparison

| Aspect | MUSE SongState | SessionGraph | Winner |
|--------|---------------|--------------|--------|
| Tonality | `key`, `tempo`, `timeSignature` | `bpm`, `key`, `scale`, `time_signature` | Tie |
| Genre | `genreDNA` (10-dim vector) | `genre` (string) | **MUSE** — extend SessionGraph |
| Tracks | `Track { role, preset, effectsChain[] }` | `Track { role, instrument, mix, clips[] }` | **SessionGraph** — richer |
| Sections | `Section { name, startBar, endBar, energyLevel }` | `SectionMarker { name, ticks, energy, tension, complexity, enable_kick/snare... }` | **SessionGraph** — more granular |
| Harmony | `progression.chords[]` (symbol + MIDI + tension) | No explicit field (in MIDI only) | **MUSE** — add to SessionGraph |
| Constraints | Not modeled | `ConstraintSet` with severity levels | **SessionGraph** |
| Takes | Not modeled | Full `TakeLane` system | **SessionGraph** |
| Compression | L0-L3 hierarchical | Not modeled | **MUSE** — add as methods |
| History | Undo/redo capable | Explainability only | **MUSE** — enhance SessionGraph |

---

## 6. Why the Algorithm Sounds "Beginner"

### Reviewer Diagnosis: 3 Root Causes

**6.1 — Chord progressions are lookup tables, not theory-driven.**

`MidiGenerator._create_chord_track()` calls `get_chord_progression()` from utils, which returns hardcoded progressions per genre. No voice leading logic. Voicings are fixed MIDI note arrays. The `KeyboardistAgent` wraps this same generation. Result: technically correct but *rigid* harmony — like a student playing from a textbook.

**6.2 — Bass and melody don't respond to harmonic context.**

`_create_bass_track()` generates from genre templates with only root transposition. The BassistAgent "attempts groove-locking to kick" but doesn't derive notes from chord tones, approach tones, or passing tones. Bass pattern ≠ bass line.

**6.3 — Tension arc doesn't translate to orchestration.**

The `TensionArcGenerator` produces beautiful 0.0-1.0 per-section values. But the MidiGenerator uses these only for velocity scaling (`_tension_multiplier()`). A tension of 0.8 should mean: denser drums, wider voicing spread, higher lead register, busier bass, more modulation. Instead, notes just get louder.

### What Makes Music Sound "Beginner" (Music Producer's Perspective)

> *Reviewer 4 (Algorithm Expert): "A trained ear can't articulate WHY something sounds student-level, but they feel it instantly."*

Five things that immediately reveal generated music:

1. **No voice leading** — Chords jump between voicings without smooth inner-voice motion. This is THE #1 tell.
2. **Grid-locked timing** — Zero swing, zero push/pull. Every note at exact quantized positions.
3. **Velocity flatline** — Uniform dynamics. No accent hierarchy, no ghost notes, no phrase shaping.
4. **Static density** — Same number of notes per bar regardless of section. No breathing.
5. **No inter-agent conversation** — Bass doesn't respond to drums, keys don't respond to bass. Parts stacked, not interlocked.

---

## 7. The 10 Cardinal Sins of AI Music

> *From Reviewer 4's deep-dive analysis*

| # | Sin | What a Pro Does Differently | How It Manifests In This System |
|---|-----|---------------------------|-------------------------------|
| 1 | **Parallel fifths/octaves** | Contrary motion, common tone retention | KeyboardistAgent generates each chord without reference to previous voicing |
| 2 | **Velocity flatline** | Hierarchical accents: beat 1 > 3 > 2&4 > offbeats | Personality adds random offsets, not hierarchical patterns |
| 3 | **Grid-locked timing** | Consistent instrument-specific offsets per genre | MidiGenerator generates at exact tick positions |
| 4 | **Root-position bass** | Chromatic approaches, passing tones, anticipation | BassistAgent uses templates transposed to root, no harmonic awareness |
| 5 | **Density monotony** | Add/subtract layers with purpose per section | Conductor processes all agents for every section — no sit-out logic |
| 6 | **Chord rhythm amnesia** | Genre-specific chord attack patterns (soul = "&" of 2&4; house = pumping 8ths) | KeyboardistAgent decides *what notes* but not *when* rhythmically |
| 7 | **Fills that don't set up phrases** | Fills crescendo into the downbeat, kick drops out before fill | Fills are pattern substitutions, not momentum-builders |
| 8 | **No harmonic substitution** | Tritone subs, chromatic mediants, reharmonization per repetition | System receives chord symbols and generates literal interpretations |
| 9 | **Sterile repetition** | 90% same pattern + 10% micro-variations per bar | Agent generates 1-2 bar pattern, system repeats without mutation |
| 10 | **No inter-agent conversation** | Bass responds to kick, keys respond to bass, lead responds to keys | Sequential pipeline with minimal context passing — bass sees kick positions only |

---

## 8. Voice Leading: The #1 Fix

### Why It's the Highest-Impact Single Change

Voice leading failure is uniquely detectable. It collapses four-dimensional motion (four voices over time) into one dimension (a chord shape moving monolithically). When all voices jump in the same direction by the same interval, the ear hears one blob, not a living ensemble.

### Minimum Viable Rule Set (5 Rules)

| Rule | Description | Impact |
|------|-------------|--------|
| **Common tone retention** | If two adjacent chords share a pitch, at least one voice stays on it | Eliminates unnecessary jumps |
| **Stepwise motion** | Non-common voices move by step (≤ whole step), not by leap | Smooth lines |
| **Contrary motion to bass** | When bass moves up, at least one upper voice moves down | Creates independence |
| **Resolve tendency tones** | 7th of chord resolves down by step; leading tone resolves up | Musical expectation met |
| **Spacing constraints** | ≤ octave between adjacent upper voices; no voice crossing | Clean voicings |

### Worked Example: ii-V-I in Bb Major (Cm7 → F7 → BbMaj7)

**Bad (AI default — root position blocks):**
```
S: Bb3 → Eb4 → D4      Every voice leaps
A: G3  → C4  → Bb3     No common tones retained
T: Eb3 → A3  → F3      Eb present in both Cm7 and F7 — wasted
B: C3  → F3  → Bb2     Fine for bass
Sound: chunk → chunk → chunk. Three disconnected blocks.
```

**Good (voice-led):**
```
S: Bb4 → A4  → A4      Bb→A is a half-step (7th resolves to 3rd). A stays (common tone)
A: G4  → F4  → F4      G→F is a step. F stays (common tone)
T: Eb4 → Eb4 → D4      Common tone retained. Then Eb→D (7th of F7 resolves to 3rd of BbMaj7)
B: C3  → F2  → Bb2     Standard bass motion by fourths/fifths
Sound: Only 3 notes change across 3 chords. Two voices stay completely still from F7→BbMaj7.
```

### Genre Interaction

| Genre | Voice Leading Character |
|-------|----------------------|
| **Jazz** | Looser but more sophisticated. Rootless voicings. Top voice moves by step. |
| **Neo-soul** | Smooth, minimal motion. Wide open voicings. Common tones emphasized. |
| **Pop** | Top note of chord traces a counter-melody. Inner voices less important. |
| **Electronic** | "Voice leading" via filter sweeps and pitch automation, not pitch motion. |
| **Trap** | Minimal harmony — mostly power chords or single bass notes. Voice leading less relevant. |

---

## 9. Genre DNA: The 10 Dimensions

> *Proposed by Reviewer 4, validated across all reviews*

| # | Dimension | 0.0 | 1.0 | Generation Impact |
|---|-----------|-----|-----|-------------------|
| 1 | **Rhythmic Density** | Sparse (ambient) | Dense (DnB) | Note count per bar, subdivision level |
| 2 | **Swing Amount** | Straight (EDM) | Deep shuffle (neo-soul) | Timing grid transformation |
| 3 | **Harmonic Complexity** | Triads only (punk) | Extended/altered (jazz) | Voicing choices, chord extensions |
| 4 | **Syncopation Level** | On-beat (march) | Off-beat (reggae, funk) | Rhythmic pattern probability weights |
| 5 | **Bass-Drum Coupling** | Independent (jazz) | Locked (hip-hop) | Bass pattern vs kick pattern correlation |
| 6 | **Repetition/Variation** | High variation (jazz) | High repetition (techno) | Pattern length, mutation rate |
| 7 | **Register Spread** | Narrow (lo-fi) | Wide (orchestral, EDM drops) | Octave placement of parts |
| 8 | **Timbral Brightness** | Dark/warm (dub) | Bright/harsh (trance) | Filter cutoff, sample selection |
| 9 | **Dynamic Range** | Compressed (modern pop) | Wide (classical, jazz) | Velocity range, automation |
| 10 | **Tension Resolution** | Always resolved (pop) | Sustained/unresolved (ambient) | Cadence probability at phrase endings |

### Computing from MIDI/Audio

Each dimension is computable algorithmically from the MPC Beats corpus:
- **Rhythmic Density**: Note onsets per bar, normalized
- **Swing**: Average timing offset of upbeat 16th notes vs straight grid
- **Harmonic Complexity**: Avg unique pitch classes sounding simultaneously  
- **Syncopation**: Ratio of weak-beat to strong-beat onsets
- **Bass-Drum Coupling**: Cross-correlation between kick and bass onsets
- **Repetition**: Self-similarity matrix of 2-bar segments
- **Register Spread**: Std dev of pitch values across voices
- **Timbral Brightness**: Spectral centroid or velocity-weighted pitch average
- **Dynamic Range**: Std dev of velocity values
- **Tension Resolution**: Cadential motion probability at phrase boundaries

### Does Interpolation Work?

**Yes for most combinations:**
- 70% neo-soul + 30% trap = The Weeknd's early work. Natural.
- 50% jazz + 50% hip-hop = Robert Glasper. Natural.
- 60% house + 40% disco = Nu-disco. Natural.

**Resists interpolation when >5 dimensions oppose:**
- Death metal + bossa nova: rhythmic DNA conflicts fundamentally
- Ambient + drum & bass: opposite extremes on density, tempo, dynamics
- Classical + trap: developmental form vs loop-based — structural incompatibility

**Solution for resistant pairs**: Don't average vectors. Use one as primary, borrow specific elements from the other (fusion strategy vs interpolation).

---

## 10. Quality Gate Design

### 5 Algorithmic Metrics (No LLM Required)

| Metric | What It Measures | Threshold (Pass) | Threshold (Reject) | Compute Cost |
|--------|-----------------|-------------------|---------------------|-------------|
| **Voice Leading Cost (VLC)** | Total semitone movement per chord change | < 3.0 avg | > 5.0 avg | O(n × v²) — trivial |
| **Rhythmic Consistency (RCS)** | Autocorrelation of 1-bar pattern | 0.70 ≤ x ≤ 0.95 | < 0.5 or > 0.98 | O(n × m) — cheap |
| **Bass-Kick Alignment (BKAS)** | % of kick hits with corresponding bass note | > 70% (when coupling > 0.7) | < 40% | O(k + b) — trivial |
| **Velocity Distribution (VDQ)** | Stddev + hierarchical structure + no flatlines | stddev > 15, max_identical_streak < 8 | stddev < 8 or streak > 16 | O(n) — trivial |
| **Arrangement Density Curve (ADC)** | Correlation between tension arc and note density | > 0.6 with ≥1 density dip | < 0.3 or no dip | O(n) — trivial |

**All 5 metrics run in < 10ms for a 64-bar arrangement.**

### Preventing Over-Conservative Critics

1. **Genre-conditional thresholds** — parallel fifths are intentional in rock power chords
2. **"Swing budget"** — excellent VLC earns tolerance for a parallel fifth moment
3. **Soft thresholds** — 3 regeneration attempts; if all fail same metric, loosen by 20% and take the best
4. **Never reject on single metric** — require failure on ≥ 2 axes for hard rejection
5. **Creative override flag** — consistent intentional rule-breaking passes (e.g., all parallel motion by design)

---

## 11. MPC Beats Data Extraction Plan

### Source Material

| Source | Count | Format | Musical Knowledge |
|--------|-------|--------|------------------|
| `.progression` files | 47 | JSON: `{ name, rootNote, scale, chords: [{ name, role, notes[] }] }` | Professional chord voicings, genre-specific harmony |
| `.mid` arp patterns | 80+ | Standard MIDI | Rhythmic patterns, melodic contours, swing profiles |

### Key Discovery: Dual-Register Structure

> *Reviewer 3: "Each progression has 16 chords in two halves. Chords 1-8 are close-voiced (comping), chords 9-16 are open-voiced (Big Chord moments). This directly maps to arrangement: verses use compact voicings, choruses use spread voicings. The corpus literally encodes arrangement intelligence."*

### Extraction Pipeline

**Step 1: Parse & Analyze Progressions**

| Analysis | Output |
|----------|--------|
| Chord vocabulary per genre | e.g., Gospel uses dim chords 3× more than House |
| Voice leading distances | Neo Soul ≈ 2.3 semitones avg; House ≈ 4.1 |
| Bass motion patterns | Chromatic descents in Neo Soul; fourths in House |
| Extension frequency | Neo Soul: 87% extended; Trap: 45%; House: 30% |
| Register spread | Neo Soul: avg 24 semitones; Trap: avg 30+ |
| Common-tone retention rates | Smooth (high) vs dramatic (low) per genre |
| Tension arc shapes | Cluster: "slow build," "wave," "plateau + drop" |

**Step 2: Parse & Analyze Arp Patterns**

| Analysis | Output |
|----------|--------|
| Note density per genre | Quantified "busy-ness" |
| Rhythmic grid | 16ths, triplets, 32nds — subdivision per genre |
| Swing ratio | Light (58%), medium (62%), deep (66%) |
| Velocity contour | Crescendo, accent-on-1, constant, humanized |
| Pitch interval distribution | Stepwise vs leaps — melodic character |

**Step 3: Encode into Data Structures**

```
ProgressionCorpus {
  progressions: EnrichedProgression[]           // 47 entries
  genreProfiles: Map<genre, GenreHarmonicProfile>  // statistical fingerprints
  voicingTemplates: Map<chordQuality, VoicingTemplate[]>  // ~750 real voicings
  bassMotionPatterns: Map<genre, IntervalSequence[]>
  tensionArcTemplates: Map<arcShape, TensionCurve[]>
}

ArpCorpus {
  patterns: ParsedArpPattern[]                  // 80 entries
  genreRhythmProfiles: Map<genre, RhythmProfile>
  densityBuckets: Map<"sparse"|"medium"|"dense", ParsedArpPattern[]>
}
```

**Step 4: Usage in Generation Pipeline**

1. **Genre → Constraints**: "Neo Soul" → lookup `GenreHarmonicProfile` → extended chords (87%), tight voice leading (2.3 semitones), chromatic bass
2. **Progression generation**: Template mutation (pick closest corpus match, transpose, substitute 1-3 chords) OR constrained generation from profile statistics
3. **Voicing**: Lookup `VoicingTemplate[]` — 750 real voicings from the corpus. Don't invent voicings — use producer-tested ones
4. **Arrangement**: Dual-register structure → verses = chords 1-8 (compact), choruses = chords 9-16 (spread)
5. **Critic calibration**: "This Neo Soul progression has VLC 5.8 — corpus average is 2.3. Flag as too jumpy."

> *Reviewer 3: "These 47 progressions aren't just example data. They're THE TASTE MODEL. They encode what professional sound designers at Akai decided sounds correct for each genre. The generation algorithm should treat these as ground truth."*

---

## 12. The JUCE Question

### Verdict: Keep Frozen as Passive Viewport

> *Reviewer 3: "Keep JUCE. Don't drop it. But stop investing in it for the next 8 weeks."*

**Why not drop it:**
- Months of real work: piano roll, waveform, spectrum, 16-voice synth, transport, OSC bridge — all functional
- Useful as a visual debugger/preview for the generation pipeline
- The synth provides preview playback independent of MPC Beats

**Why freeze it:**
- Every hour spent on C++ = hour not spent making the algorithm work
- C++ iteration speed is 5-10× slower than Python
- The user already owns MPC Beats (TubeSynth, Bassline, 60+ effects) — building a competing audio engine is redundant
- If Copilot SDK chat becomes the primary interface, JUCE GUI duplicates what the terminal provides

**The specific plan:**
1. Zero new JUCE features for 8 weeks
2. Keep OSC listener alive — passive piano roll display
3. All creation logic in Copilot SDK CLI + Python intelligence layer
4. After Week 4 demo: revisit JUCE as "preview panel" and decide if it earns further investment
5. Never compete with MPC Beats' audio engine — JUCE synth is preview-only

---

## 13. 4-Week Sprint Plan

### Goal: "Algorithm not functional" → "Generates coherent, genre-appropriate multi-track songs"

### Week 1: Harmonic Foundation + Data Ingestion

| Task | Detail | Output |
|------|--------|--------|
| Parse 47 `.progression` files | JSON with known schema | `EnrichedProgression` objects with roman numeral analysis, tension, genre tags |
| Parse 80 `.mid` arp patterns | Extract density, pitch range, velocity curves, swing | `ParsedArpPattern` objects |
| Build GenreDNA vector table | Derive from corpus analysis, not hand-authored | 10-dim vectors per genre |
| Build chord progression generator | Given (key, scale, genre, length) → select from corpus + mutate | Deterministic Python, no LLM |

**Measurable**: "Neo Soul in Eb minor, 8 chords" → progression that sounds corpus-quality. Test on 10 prompts.

### Week 2: MIDI Generation + Voicing Engine

| Task | Detail | Output |
|------|--------|--------|
| Voice leading engine | Given chord symbol + previous voicing + register constraints → voice-led voicing | Inject into KeyboardistAgent |
| Bass line generator | Root notes + passing tones + chromatic approaches, genre-specific | Inject into BassistAgent |
| Drum pattern generator | Genre-appropriate with correct subdivisions (triplet hi-hats for trap, etc.) | Enhance DrummerAgent |
| Humanization pass | Velocity hierarchy, micro-timing offsets, genre-specific groove tables | Post-generation layer |

**Measurable**: 3 MIDI files (chords, bass, drums) that sound coherent when loaded into MPC Beats. Test on 5 genres.

### Week 3: Multi-Track Assembly + Critics

| Task | Detail | Output |
|------|--------|--------|
| Arrangement engine | Genre + tempo → section map (intro/verse/chorus/outro) with instrument activation per section | Conductor orchestration |
| Multi-track assembly | Combine all parts into coherent arrangement | Multi-track MIDI file |
| 3-axis critic system | VLC + RCS + ADC algorithmic checks | Quality gate with regeneration |
| Targeted regeneration | If critic fails → re-generate only failing component, max 3 attempts | Consistency guarantee |

**Measurable**: "Lo-fi hip hop chill beat, 2 minutes" → multi-track arrangement passing all critics. Test on 8 genres.

### Week 4: Integration + Virtual MIDI + Demo

| Task | Detail | Output |
|------|--------|--------|
| Copilot SDK CLI wrapper | TypeScript shell: text prompt → Python intelligence → file output | End-to-end interface |
| Virtual MIDI playback | loopMIDI + rtmidi: play generated arrangement into MPC Beats | Live performance |
| Preset recommendation | Track role + genre → specific MPC Beats preset name (text-based) | Timbral guidance |
| End-to-end pipeline | NL prompt → analysis → generation → critics → output + playback | Complete flow |

**The Demo Moment**: Screen recording. User types a prompt. Terminal streams progress. MPC Beats receives MIDI in real-time. Piano roll lights up. User assigns AI-recommended presets. Presses play. Music plays. **It sounds intentional. It responds to the prompt. It's a coherent musical idea a producer would use as a starting point.**

---

## 14. The Masterclass Test

### Example 1: "Neo-soul ballad in Eb major, 75 BPM, melancholy"

**Masterclass output:**
- Chords: EbMaj9 → Cm11 → AbMaj7#11 → Bb13sus4 → Bb13 (2+2+2+1+1 bar phrasing — asymmetric)
- Keyboard voicing of EbMaj9: [Bb2, Eb3, G3, D4, F4] — spread voicing. Voice-led to Cm11: only one note moves (D→C)
- Bass: Roots with chromatic approaches. 25ms behind grid. Round, sub-heavy tone.
- Drums: Kick on 1 and "& of 3" (neo-soul signature). Snare on 3 only (half-time). Hi-hat 16ths with "&" notes 15-20ms late (systematic groove, not random).
- Arrangement: Intro = keys alone (4 bars) → V1 = kick + side-stick enter → V2 = full drums, melodic bass → Chorus = add Rhodes pad, rhythmic chord comping → Bridge = strip to bass + keys, modulate to Gb major → Final chorus = everything + counter-melody

**Beginner AI output (same prompt):**
- Chords: Eb → Cm → Ab → Bb. Basic triads, root position, no extensions. Every chord = 2 bars (symmetric, predictable).
- All voices jump together. No common tones retained.
- Bass: Root whole notes on the grid.
- Drums: Kick on 1&3, snare on 2&4 (not half-time — wrong genre). Straight 8th hi-hats, uniform velocity 80.
- Arrangement: All instruments enter at bar 1, play at same level until the end.

### Example 2: "Trap banger in C minor, 140 BPM, aggressive"

**Masterclass output:**
- 808: C2 sustained with glide down to Bb1 (pitch bend). Syncopated: beat 1, "& of 2," "a of 3." Long decay. The 808 IS the bass AND kick.
- Snare: Beat 3 ONLY (half-time defining trait). Layered snare+clap. Snare rolls: 16th→32nd→64th accelerating into beat 1 every 4th bar.
- Hi-hats: TRIPLET 16ths (not straight — this is the trap signature). Rolls on beat 4 at 32nd-note triplets. Open hat on "& of 1" and "& of 3." Velocity accelerates through rolls 50→110.
- Arrangement: Intro = 808 alone → Add hi-hats → Add melody → The drop: everything cuts (silence), then EVERYTHING hits on beat 1 with crash. Post-drop 808 drops to G1 (heavier).

**Beginner AI:**
- 808: Quarter notes on 1-2-3-4. No glide. No syncopation.
- Snare: On 2 and 4 (wrong — should be half-time on 3 only).
- Hi-hats: Straight 16ths, uniform velocity. No triplets, no rolls.

### Example 3: "Ethiopian jazz fusion, Tizita scale, 100 BPM, soulful"

**Masterclass output:**
- Krar: Drone strings (C3, G3) in tremolo (32nd notes) while upper strings play Tizita melody. NOT Western arpeggios — drone-plus-melody technique.
- Kebero: Eskista rhythm — asymmetric pattern in 12/8 feel. Deep head on beat 1 and "& of 3." High head plays "da-ga-da DA-ga-da" grouping. INTERLOCKS with krar (call-and-response).
- Jazz element: Walking bass using Tizita scale notes only (D-G-A, not Dm7 with F). Jazz voice leading constrained to pentatonic — gives fusion flavor.
- Bridge: Modulate to minor Tizita (Db-Eb instead of D-E) — dramatic darkening.

**Beginner AI:**
- Krar: C major arpeggios in 16th notes. No drone. Sounds like a MIDI music box.
- Kebero: Standard rock beat — kick-snare-kick-snare. No eskista.
- Melody uses chromatic tones (E-F, B-C) that don't exist in Tizita. Sounds "Western with vaguely pentatonic melody."

---

## 15. Risk Assessment

### Top 5 Risks

| # | Risk | Severity | Mitigation |
|---|------|----------|------------|
| 1 | **Scope explosion** — 91 MUSE tasks + multimodal's M1-M7 milestones | CRITICAL | Strict timebox: only HarmonicBrain, GenreDNA, Critics in first sprint. Everything else is Phase 2+ |
| 2 | **Two-language maintenance** — MUSE specs are TypeScript, multimodal is Python | HIGH | Treat MUSE specs as design docs, not code to transpile. Implement in Pythonic idioms |
| 3 | **LLM dependency for core function** — if Copilot API is unavailable, does generation break? | HIGH | OfflineConductor as always-works fallback. LLM is enhancement layer, never requirement. Feature flag: `--use-api-agents` |
| 4 | **Integration delays algorithm fix** — weeks on architecture before fixing generation quality | MEDIUM-HIGH | Fix algorithm FIRST (Weeks 1-3). Integration architecture in Week 4. |
| 5 | **MUSE specs are untested theory** — tension formula, genre DNA, voicing engine never validated | MEDIUM | Prototype each concept as isolated Python module, test against real MIDI, iterate before integrating |

---

## 16. Gap Analysis

### What MUSE Brings That multimodal Lacks

| Capability | MUSE Detail | Impact |
|-----------|-------------|--------|
| **Deep harmonic intelligence** | Tension function, roman numeral analysis, voice leading, chord substitution | Transforms chord quality |
| **Genre DNA vectors** | 10-dim continuous fingerprints, interpolation-based fusion | Enables genre blending |
| **Multi-critic quality evaluation** | Harmony/Rhythm/Arrangement/Vibe critics with thresholds | Catches bad output |
| **Embedding-based search** | "warm Sunday morning" → matching presets/progressions | Semantic asset discovery |
| **Personalization** | Preference vectors, epsilon-greedy exploration, producer modes | Adapts to user over time |
| **Energy modeling** | Composite function with interaction terms (harmonic × rhythmic energy) | Professional energy curves |
| **MPC progression corpus** | 47 progressions as taste model and calibration ground truth | Professional harmonic knowledge |

### What multimodal Has That MUSE Lacks

| Capability | Detail | Impact |
|-----------|--------|--------|
| **Working audio synthesis** | Procedural drums, FluidSynth, Ethiopian physical modeling | Produces sound |
| **Real-time GUI** | JUCE piano roll, waveform, spectrum, transport | Visual feedback |
| **End-to-end pipeline** | Prompt → MIDI → Audio → MPC export | Actually ships output |
| **Ethiopian music system** | Qenet theory, 5 instruments, physical modeling | Unique cultural value |
| **Humanization physics** | DrumHumanizer, MicrotimingEngine, arm-weight modeling | Sophisticated feel |
| **Reference analysis** | YouTube/audio BPM/key/groove extraction | Learning from examples |
| **Take system** | TakeGenerator with variation seeds, comp tracks | Multiple outputs |

---

## 17. What Gets Removed, Kept, Enhanced

| Component | Action | Rationale |
|-----------|--------|-----------|
| PromptParser (regex) | **Keep + Enhance** | Works; augment with LLM for NL depth |
| OfflineConductor | **Keep** | Working orchestration; becomes offline fallback |
| All 8 Performer Agents | **Keep** | Core engine; enhance with richer PerformanceContext |
| SessionGraph | **Keep + Extend** | Superior data model; add genre_dna, progression, compression |
| MPC Exporter | **Keep** | Working, tested, unique |
| Ethiopian instruments | **Keep** | Irreplaceable cultural/sonic value |
| AudioRenderer | **Keep** | Produces audio; improve timbre quality over time |
| MUSE SongState | **Adapt as view** | L0-L3 compression becomes SessionGraph serializer |
| MUSE HarmonicBrain | **Port to Python** | Core intelligence upgrade — top priority |
| MUSE GenreDNA | **Port to Python** | Enables fusion, continuous decisions |
| MUSE Multi-Critic | **Port to Python** | Quality assurance layer |
| MUSE Embeddings (ONNX) | **Port to Python** | Python has better ONNX support than Node.js |
| MUSE .progression parser | **Port to Python** | Adds 47 professional progressions as training data |
| MidiGenerator (legacy direct) | **Phase out** | Replaced by Agent pipeline once voice leading works |
| `get_chord_progression()` | **Replace** | Replaced by HarmonicBrain-generated progressions |
| MUSE Controller Intelligence | **Defer** | MPC-specific, not critical path |
| MUSE .xmm parser | **Defer** | MPC-specific, low priority |

---

## 18. Final Recommendation & Next Steps

### The Path Forward

1. **Clone multimodal-ai-music-gen locally** alongside the MPC Beats workspace
2. **Copy MUSE docs** → `multimodal-ai-music-gen/docs/muse-specs/` (preserve institutional knowledge)
3. **Execute the 4-week sprint** (Section 13) — algorithm quality first, integration architecture second
4. **Week 1 milestone**: Corpus parsed, GenreDNA computed, chord generator producing corpus-quality progressions
5. **Week 2 milestone**: Voice-led voicings, harmonic bass lines, genre-appropriate drums
6. **Week 3 milestone**: Multi-track arrangements passing critic system
7. **Week 4 milestone**: Copilot SDK CLI + virtual MIDI to MPC Beats — the demo moment

### What Does NOT Happen

- ❌ No standalone MUSE Electron app
- ❌ No new JUCE features for 8 weeks
- ❌ No porting all 91 MUSE tasks — only intelligence layers
- ❌ No TypeScript rewrite of the Python backend
- ❌ No LLM dependency for basic generation (offline-first)

### The Demo Moment (Week 4)

> User types: "dark neo-soul with gospel influences at 75 BPM"  
> Terminal streams: "Analyzing genre... Generating progression... Voice-leading chords... Building bass line... Assembling arrangement... Running critics (4/5 pass, regenerating bass)... Done."  
> MPC Beats: Receives 4 tracks via virtual MIDI. Piano roll lights up with voice-led chords, melodic bass, half-time neo-soul drums, subtle pad.  
> User assigns AI-recommended presets: TubeSynth 'Round Bass', Electric 'Soul Keys', DrumSynth '808 Kit'.  
> Presses play.  
> **It sounds like music.**

---

*This document synthesizes findings from 4 independent expert reviews conducted on February 10, 2026. All reviewers reached consensus on the integration path. The MUSE specs are preserved as the design bible for the intelligence layer. The multimodal-ai-music-gen application provides the body. Together: a production-ready AI music system.*
