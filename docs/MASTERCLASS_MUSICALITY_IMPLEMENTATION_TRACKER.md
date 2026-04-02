# Masterclass Musicality Implementation Tracker

> **Created**: 2026-04-02  
> **Purpose**: durable implementation tracker for the next MUSE musicality milestone wave  
> **Grounded against**: current codebase source of truth, focused module inspection, and passing focused test verification  
> **Verification baseline**: 206/206 focused tests passed for motif, arranger, tension arc, melody integration, and output analysis

---

## Why this tracker exists

MUSE already contains significant musicality infrastructure that earlier roadmap notes and external brainstorming can understate:

- `multimodal_gen/motif_engine.py` exists and is tested
- `multimodal_gen/tension_arc.py` exists and is wired into arrangement/generation
- `multimodal_gen/dynamics.py` and `multimodal_gen/microtiming.py` exist
- `multimodal_gen/output_analyzer.py` exists and is part of the producer acceptance loop
- `multimodal_gen/reference_analyzer.py` already extracts chords, groove, drum traits, and melodic contour

Therefore, the next implementation phase should **extend and converge existing systems** instead of replacing them or creating parallel abstractions.

---

## Source-of-truth synthesis

### Already implemented enough to preserve

#### Musicality infrastructure already present
- Motif engine with transformations, related motifs, and arrangement integration
- Tension arc generation and section-aware tension lookup
- Phrase/dynamics infrastructure and CC expression injection
- Microtiming and performance-humanization layers
- Reference analysis for BPM/key/groove/chords/melodic contour
- Output analyzer with genre-aware rendered-audio scoring

#### Production infrastructure already present
- Iterative refinement and seed persistence
- BWF / provenance metadata
- JUCE controls for motif count and tension arc shape
- JSON-RPC / OSC transport and regeneration pathways
- Takes, comps, sectional regeneration, and output-analysis-aware producer gating

### Real gaps to close next

1. **Motif depth, not motif existence**
   - Motif logic is present, but non-jazz depth and cross-track usage are still limited.
   - Motif usage is stronger in selected melody sections than across the full composition arc.

2. **Narrative authority of tension arc**
   - Tension exists, but it still acts more like a modifier than a top-level arrangement authority.
   - It should more strongly affect orchestration, transitions, texture, and section identity.

3. **Analyzer-to-repair translation**
   - Output analysis already scores and detects issues.
   - Missing link: convert failures into structured regeneration/refinement changes.

4. **Reference-to-composition reuse**
   - Chords and melodic contour are extracted.
   - They are not yet strongly fed into motif generation and long-range development.

5. **Phrase realism deployment quality**
   - Expression and microtiming systems exist.
   - Runtime usage can become more phrase-aware and role-aware.

---

## Execution policy

### Primary rule
Implement **one milestone at a time**, end-to-end, with proof before starting the next.

### Orchestration preference
Because autopilot is enabled, the recommended execution model is:

1. **`recursive-supervisor`** for decomposition and milestone scoping
2. **`recursive-builder`** for minimal, focused code changes
3. **`recursive-verifier`** for post-change proof

### Why this is the preferred mode
- It matches the repo’s orchestration patterns
- It reduces context drift in large files like `midi_generator.py` and `arranger.py`
- It protects already-working production features
- It enforces milestone-level verification instead of uncontrolled multi-feature churn

### Important note about “premium subagents”
Use the strongest available subagents in-session, but keep in mind model routing for `runSubagent` is not always strictly controllable from frontmatter alone. The safe strategy is still:

- milestone decomposition
- narrow builder scope
- explicit verifier proof

---

## Milestone roadmap

---

## Milestone 1 — Motif Depth and Full-Section Thematic Development

**Status**: COMPLETE (slices 1-3 complete)  
**Priority**: Highest  
**Risk**: Medium  
**Reason**: Highest leverage musicality gain with best reuse of existing code

### Goal
Turn motifs from a partially used melody feature into a **composition-wide thematic engine**.

### Target areas
- `multimodal_gen/motif_engine.py`
- `multimodal_gen/arranger.py`
- `multimodal_gen/midi_generator.py`
- tests around motif generation/integration

### Scope
#### 1. Deepen motif generation by genre
- Improve non-jazz motif generation instead of relying on generic fallback behavior
- Add stronger support for:
  - cinematic
  - classical
  - neo_soul / rnb
  - Ethiopian / ethio-jazz / eskista

#### 2. Expand motif usage across section types
- Extend motif-driven logic beyond primarily chorus/drop/variation paths
- Introduce more consistent motif behavior for:
  - intro
  - verse
  - pre-chorus
  - bridge
  - outro

#### 3. Expand motif influence beyond lead melody
- Reuse motif identity for:
  - countermelody fragments
  - bass response gestures where musically appropriate
  - voicing/rhythm hints for chordal tracks

#### 4. Preserve backward compatibility
- Motif system must remain optional/fail-open
- Existing generation should still work when motif path is disabled or absent

### Acceptance criteria
- Motif-driven melody appears in more than just climax sections
- Genre-specific motif generation reduces generic fallback usage
- Existing motif integration tests still pass
- New tests prove section-spanning thematic continuity behavior

### Verification checklist
- [x] Focused motif tests pass
- [x] Melody integration tests pass
- [x] No regression in arranger backward compatibility
- [x] Manual code inspection confirms no replacement of existing motif stack

### Slice 1 completed
- Added dedicated motif fallbacks for `cinematic`, `classical`, `rnb`, and `neo_soul` in `multimodal_gen/motif_engine.py`
- Fixed classical motif mappings so they match the real arrangement template section names
- Added `fragment` transform support in `get_section_motif()`
- Expanded motif-aware melody participation to non-chorus sections in `generate_arrangement_with_motifs()` without changing plain `create_arrangement()` defaults
- Updated melody-track section naming/counter handling so repeated sections like `verse_2` resolve the correct motif assignment
- Added focused regressions for genre-specific motif fallbacks, fragment retrieval, classical mapping alignment, isolated mapping copies, motif-aware non-chorus melody enablement, and `verse_2` motif playback

### Milestone 1 closeout
- Slice 3 completed the planned low-risk cross-track thematic reuse pass by extending motif influence into the primary chord track as onset-group velocity contouring only.
- Milestone 1 is now considered complete because the motif system has been deepened across genre fallbacks, section coverage, melody usage, bass-side expressive reuse, and conservative chord-track reuse without destabilizing plain arrangement defaults.
- Any future motif work should now be treated as follow-on polish or as part of later milestones, not as unfinished Milestone 1 scope.

## Execution Log — Milestone 1 Slice 1 (motif depth + section coverage)
- Date: 2026-04-02
- Supervisor: recursive-supervisor decomposition + orchestration by supervisor
- Builder: recursive-builder
- Verifier: recursive-verifier
- Scope: genre-specific motif fallbacks for cinematic/classical/rnb/neo_soul; classical mapping repair; fragment transform; motif-aware intro/verse/pre-chorus/bridge/outro melody participation; repeated-section counter alignment
- Files changed:
  - `multimodal_gen/motif_engine.py`
  - `multimodal_gen/arranger.py`
  - `multimodal_gen/midi_generator.py`
  - `tests/test_motif_engine.py`
  - `tests/test_arranger_motifs.py`
  - `tests/test_motif_melody_integration.py`
- Tests run:
  - `pytest tests/test_motif_engine.py -q`
  - `pytest tests/test_arranger_motifs.py -q`
  - `pytest tests/test_motif_melody_integration.py -q`
  - `pytest tests/test_motif_engine.py tests/test_arranger_motifs.py tests/test_motif_melody_integration.py -q`
- Result: PASS — 95 focused tests passed; verifier confirmed the bounded slice landed without changing plain arrangement defaults
- Follow-up risks:
  - `get_section_motif()` now fails open on bad transform params, which preserves runtime safety but can hide malformed assignments
  - `pre_chorus` was already melody-enabled by default, so the clearest new behavior in this slice is intro/verse/bridge/outro participation

## Execution Log — Milestone 1 Slice 2 (Ethiopian-family motif depth + conservative bass reuse)
- Date: 2026-04-02
- Supervisor: recursive-supervisor decomposition + orchestration by supervisor
- Builder: recursive-builder
- Verifier: recursive-verifier
- Scope: Ethiopian / ethio_jazz / eskista / ethiopian_traditional motif fallbacks; Ethiopian-family section-correct motif mappings; Ethiopian-family-only motif-aware melody participation for mapped sections; conservative bass velocity contour reuse from motif accent patterns; additional cinematic and Ethiopian integration proofs
- Files changed:
  - `multimodal_gen/motif_engine.py`
  - `multimodal_gen/arranger.py`
  - `multimodal_gen/midi_generator.py`
  - `tests/test_motif_engine.py`
  - `tests/test_arranger_motifs.py`
  - `tests/test_motif_melody_integration.py`
- Tests run:
  - `pytest tests/test_motif_engine.py -q`
  - `pytest tests/test_arranger_motifs.py -q`
  - `pytest tests/test_motif_melody_integration.py -q`
  - `pytest tests/test_motif_engine.py tests/test_arranger_motifs.py tests/test_motif_melody_integration.py -q`
- Result: PASS — 107 focused tests passed; verifier confirmed Ethiopian-family fallback generation, section-correct motif deployment, scoped melody broadening, and velocity-only bass reuse without pitch/timing rewrites or plain-arrangement default changes
- Follow-up risks:
  - Bass cross-track reuse is intentionally narrow and currently contours velocity by note order rather than pulse-aware rhythmic alignment
  - Fail-open motif lookup protects runtime stability but can hide malformed accent data or bad motif assignments
  - Ethiopian-family bass contouring has the strongest direct proof on the inline fallback path; strategy-generated bass paths would benefit from an additional targeted regression if we deepen this area later

## Execution Log — Milestone 1 Slice 3 (primary chord-track motif accent reuse)
- Date: 2026-04-02
- Supervisor: recursive-supervisor decomposition + orchestration by supervisor
- Builder: recursive-builder
- Verifier: recursive-verifier
- Scope: primary `Chords` track only; reuse motif `accent_pattern` as a subtle onset-group velocity contour in both strategy and fallback chord paths; add deterministic chord contour and fail-open integration tests; avoid arranger, motif-engine, harmony, timing, pitch, and secondary-track changes
- Files changed:
  - `multimodal_gen/midi_generator.py`
  - `tests/test_motif_melody_integration.py`
- Tests run:
  - `pytest tests/test_motif_melody_integration.py -q`
  - `pytest tests/test_arranger_motifs.py -q`
  - `pytest tests/test_sprint7_wiring.py -q`
  - `pytest tests/test_motif_melody_integration.py tests/test_arranger_motifs.py tests/test_sprint7_wiring.py -q`
- Result: PASS — 59 focused tests passed combined; baseline-aware verifier confirmed Slice 3 stayed behaviorally bounded on top of the accepted Slice 1/2 baseline and remained onset-group velocity-only plus fail-open
- Follow-up risks:
  - The chord hook intentionally equalizes note velocities within each shared chord onset, which is still within the intended velocity-only scope but does reduce intra-voicing velocity variation
  - The current proof targets the primary `Chords` track only; secondary orchestral chord-like layers remain intentionally untouched for Milestone 1

---

## Milestone 2 — Tension Arc as Arrangement Authority

**Status**: QUEUED  
**Priority**: Very high  
**Risk**: Medium

### Goal
Promote tension arc from a note-level modifier to a **top-level arrangement and orchestration controller**.

### Target areas
- `multimodal_gen/tension_arc.py`
- `multimodal_gen/arranger.py`
- `multimodal_gen/midi_generator.py`
- transition/section-variation integration points

### Scope
- Map tension more directly to:
  - instrument density
  - register spread
  - harmonic complexity
  - texture intensity
  - transition behavior
  - section-specific timbral openness
- Preserve existing CC11 / CC1 / CC74 behavior while making higher-level section config more tension-aware

### Acceptance criteria
- Section-level orchestration changes become visibly tension-dependent
- Tension affects more than velocity/density multipliers
- Existing tension tests remain green

### Verification checklist
- [ ] Tension arc tests pass
- [ ] Arrangement output shows section-aware tension-driven differences
- [ ] Existing runtime remains fail-open if no arc exists

---

## Milestone 3 — Analyzer-to-Repair Closed Loop

**Status**: QUEUED  
**Priority**: Very high  
**Risk**: Medium-high

### Goal
Convert rendered-audio analysis into **actionable regeneration/refinement instructions**.

### Target areas
- `multimodal_gen/output_analyzer.py`
- producer/refinement orchestration
- regeneration/take-selection call paths

### Scope
- Build a structured translation layer from output issues to plan changes
- Examples:
  - reduce onset density
  - reduce brightness
  - swap instrument role/timbre
  - simplify over-busy motif deployment
  - rebalance tension shape
- Use targeted regeneration instead of generic retry where possible

### Acceptance criteria
- Output analysis failure produces concrete musical repair guidance
- Producer retries are more specific than generic “refine and retry”
- Existing acceptance gating remains preserved

### Verification checklist
- [ ] Output analyzer tests pass
- [ ] Producer/output-analysis behavior remains regression-safe
- [ ] At least one repair pathway is covered by focused tests

---

## Milestone 4 — Reference-to-Motif / Narrative Reuse

**Status**: QUEUED  
**Priority**: High  
**Risk**: Medium

### Goal
Use existing reference analysis outputs to seed better composition decisions.

### Target areas
- `multimodal_gen/reference_analyzer.py` consumers
- motif and arrangement planning paths

### Scope
- Feed extracted chords into motif/harmonic decisions
- Feed melodic contour into motif direction and development hints
- Feed groove traits into section-level timing character

### Acceptance criteria
- Reference-derived fields affect actual generation decisions, not only metadata
- Behavior remains optional and no-reference flow stays unchanged

---

## Milestone 5 — Phrase Realism Upgrade

**Status**: QUEUED  
**Priority**: High  
**Risk**: Low-medium

### Goal
Improve how existing expression systems are deployed at runtime.

### Scope
- Prefer phrase-aware shaping where appropriate
- Make CC event generation more phrase- and role-aware
- Deepen microtiming by role/instrument behavior

### Acceptance criteria
- More natural expressive phrasing in melody/pad/lead tracks
- No regression in current MIDI rendering pipeline

---

## Implementation order recommendation

1. **Milestone 1 — Motif Depth and Full-Section Thematic Development**
2. **Milestone 2 — Tension Arc as Arrangement Authority**
3. **Milestone 3 — Analyzer-to-Repair Closed Loop**
4. **Milestone 4 — Reference-to-Motif / Narrative Reuse**
5. **Milestone 5 — Phrase Realism Upgrade**

This order maximizes reuse and minimizes regression risk.

---

## Milestone tracking template

Use this block when executing each milestone:

```md
## Execution Log — <Milestone Name>
- Date:
- Supervisor:
- Builder:
- Verifier:
- Scope:
- Files changed:
- Tests run:
- Result:
- Follow-up risks:
```

---

## Recommended next action

Begin with **Milestone 1** using:

- `recursive-supervisor` to decompose the motif-depth milestone into safe change slices
- `recursive-builder` to implement the first slice
- `recursive-verifier` to validate with focused motif/arranger/melody tests

Do **not** combine Milestones 1 and 2 in the same implementation pass.
