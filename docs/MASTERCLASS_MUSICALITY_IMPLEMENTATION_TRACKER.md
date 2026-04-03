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

**Status**: IN PROGRESS (slices 1-2 complete)  
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
- [x] Tension arc tests pass
- [x] Arrangement output shows section-aware tension-driven differences
- [x] Existing runtime remains fail-open if no arc exists

### Slice 1 completed
- Added explicit-arc-aware section gating for auxiliary orchestration layers in `multimodal_gen/midi_generator.py`
- Secondary orchestral chord layers (`Brass` / `Choir`) now enter more strongly in moderate/high-tension sections and thin or skip low-tension sections when a real tension arc is present
- `Texture` sections now favor low/mid-tension space, reduce to a sparser layer in mid tension, and suppress at high tension when a real tension arc is present
- Preserved existing fail-open behavior by leaving baseline auxiliary generation unchanged when `arrangement.tension_arc` is missing or unusable
- Added focused regressions proving higher tension increases auxiliary Brass/Choir activity, higher tension reduces Texture activity, and missing arcs fail open

### Remaining work inside Milestone 2
- Extend tension authority beyond auxiliary layer presence into safer section-level density / register / orchestration shaping on additional existing surfaces
- Slice 3 should now target the next bounded tension-authority surface beyond auxiliary gating and primary chord register center, without broadening into arranger construction-order refactors

### Slice 2 prepared
- Recommended title: **Milestone 2 Slice 2 — Explicit-Arc-Aware Primary Chord Register Shaping**
- Chosen because `_create_chord_track()` already centralizes section tension, complexity, motif accent reuse, and main harmonic-bed rendering, giving strong audible ROI with a single concentrated code surface
- Safer than transition rewiring because transition authority is currently drum-boundary-focused and would require broader API changes
- Safer than arranger-side section-config authority because arranger config currently precedes tension-arc creation and would require a wider construction-order refactor
- Planned implementation boundary:
  - modify `multimodal_gen/midi_generator.py`
  - add focused regressions in `tests/test_tension_arc_integration.py`
  - preserve fail-open behavior when no usable explicit tension arc exists
  - keep changes limited to a deterministic primary chord register-center lift in higher-tension sections
  - do **not** rewrite progression choice, harmony quality, note density, rhythm, timing, durations, bass, melody, motifs, transitions, or arranger templates
- Planned verification set:
  - `pytest tests/test_tension_arc.py -q`
  - `pytest tests/test_tension_arc_integration.py -q`
  - `pytest tests/test_motif_melody_integration.py -q`
  - `pytest tests/test_sprint6_wiring.py -q`
  - `pytest tests/test_sprint8_batch_c.py -q`
  - combined subset run across the same files

### Slice 2 completed
- Added explicit-arc-aware primary chord register shaping in `multimodal_gen/midi_generator.py`
- The primary `Chords` track now lifts by a deterministic section-wide octave in high-tension sections when a usable explicit tension arc exists
- The lift applies to both chord paths inside `_create_chord_track()`:
  - strategy-returned chord notes
  - fallback inline chord generation
- Missing or unusable explicit arcs fail open and do not trigger the new register lift
- The lift is conservative: if a section-wide shift would not fit the chord instrument range cleanly, that section remains at the baseline register instead of being per-note clamped or distorted
- Added focused regressions proving direct primary chord register lift, fail-open behavior for missing/unusable arcs, and strategy-path coverage

## Execution Log — Milestone 2 Slice 1 (tension-controlled auxiliary layer orchestration)
- Date: 2026-04-03
- Supervisor: recursive-supervisor decomposition + orchestration by supervisor
- Builder: recursive-builder
- Verifier: recursive-verifier
- Scope: use existing section tension values to add explicit-arc-aware gating for auxiliary orchestration layers only; keep changes bounded to secondary chord tracks (`Brass`/`Choir`) and the `Texture` track; preserve fail-open behavior and existing velocity scaling
- Files changed:
  - `multimodal_gen/midi_generator.py`
  - `tests/test_tension_arc_integration.py`
- Tests run:
  - `pytest tests/test_tension_arc_integration.py -q`
  - `pytest tests/test_motif_melody_integration.py -q`
  - `pytest tests/test_sprint6_wiring.py -q`
  - `pytest tests/test_tension_arc_integration.py tests/test_motif_melody_integration.py tests/test_sprint6_wiring.py -q`
- Result: PASS — 20 focused tests passed combined; verifier confirmed the slice stayed bounded to auxiliary-layer orchestration, tied new gating only to explicit usable tension arcs, and preserved fail-open baseline behavior when no arc exists
- Follow-up risks:
  - Explicit malformed-but-present arc objects rely on the helper’s usability checks rather than dedicated regression fixtures
  - This slice intentionally avoids primary chord, bass, melody, and arrangement-template authority changes, so further Milestone 2 slices are still needed for stronger top-level orchestration control

## Preparation Log — Milestone 2 Slice 2 (primary chord register authority)
- Date: 2026-04-03
- Supervisor: recursive-supervisor decomposition + aggregation by supervisor
- Scope chosen: explicit-arc-aware register-center shaping on the primary `Chords` track only
- Files planned:
  - `multimodal_gen/midi_generator.py`
  - `tests/test_tension_arc_integration.py`
- Why this slice:
  - uses an existing single high-leverage surface (`_create_chord_track`)
  - increases audible arrangement authority beyond velocity-only shaping
  - avoids broader arranger construction-order changes and transition API expansion
- Guardrails:
  - explicit usable arc required for any new behavior
  - fail open to the current baseline when no usable arc exists
  - no progression, density, duration, rhythm, motif, bass, melody, or arranger rewrites
- Planned proof focus:
  - high tension with explicit arc raises primary chord register center versus low tension
  - missing arc preserves current primary chord baseline behavior
  - adjacent chord-track and wiring regressions remain green

## Execution Log — Milestone 2 Slice 2 (primary chord register authority)
- Date: 2026-04-03
- Supervisor: recursive-supervisor decomposition + orchestration by supervisor
- Builder: recursive-builder
- Verifier: recursive-verifier
- Scope: primary `Chords` track only; add explicit-arc-aware section-wide register-center lifting in higher-tension sections; preserve fail-open behavior for missing/unusable arcs; avoid harmony, rhythm, duration, density, motif, arranger, transition, bass, melody, and auxiliary-layer rewrites
- Files changed:
  - `multimodal_gen/midi_generator.py`
  - `tests/test_tension_arc_integration.py`
- Tests run:
  - `pytest tests/test_tension_arc.py -q`
  - `pytest tests/test_tension_arc_integration.py -q`
  - `pytest tests/test_motif_melody_integration.py -q`
  - `pytest tests/test_sprint6_wiring.py -q`
  - `pytest tests/test_sprint8_batch_c.py -q`
  - `pytest tests/test_tension_arc.py tests/test_tension_arc_integration.py tests/test_motif_melody_integration.py tests/test_sprint6_wiring.py tests/test_sprint8_batch_c.py -q`
- Result: PASS — 92 focused tests passed in the combined subset run; verifier confirmed Slice 2 stayed behaviorally bounded to primary chord register authority, applied only on explicit usable tension arcs, covered both chord paths, and preserved fail-open behavior for missing/unusable arcs
- Follow-up risks:
  - The current working tree still contains accepted Slice 1 auxiliary-layer hunks alongside Slice 2, so a future commit should checkpoint both accepted Milestone 2 slices together or be carefully staged
  - Slice 2 intentionally changes register center only; it does not yet extend tension authority into broader primary-chord density, transition behavior, or arranger-side section authority

---

## Milestone 3 — Analyzer-to-Repair Closed Loop

**Status**: IN PROGRESS (slices 1-4 complete)  
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
- [x] Output analyzer tests pass
- [x] Producer/output-analysis behavior remains regression-safe
- [x] At least one repair pathway is covered by focused tests

## Preparation Log — Milestone 3 Slice 1 (producer-side correction translation)
- Date: 2026-04-03
- Supervisor: recursive-supervisor decomposition + aggregation by supervisor
- Scope chosen: translate structured `outputAnalysis.corrections` into concrete producer score-plan mutations, then prove those mutations survive the MUSE score-plan adaptation bridge
- Files planned:
  - `copilot-Liku-cli/src/main/agents/producer.js`
  - `copilot-Liku-cli/scripts/test-output-analysis-repair.js`
  - `multimodal_gen/score_plan_adapter.py` (only if downstream proof required it)
  - `tests/test_score_plan_adapter.py` (only if downstream proof required it)
- Why this slice:
  - `multimodal_gen/output_analyzer.py` already contained a real correction engine
  - the missing link was producer consumption of `outputAnalysis.corrections`
  - the safest initial slice was to reuse existing correction semantics before attempting broader regeneration/take-selection rewiring
- Guardrails:
  - preserve existing acceptance-gating semantics
  - keep the slice bounded to repair translation and downstream adapter proof
  - prefer proven downstream levers over cosmetic plan hints
  - keep `adjust_eq` conservative unless the correction direction is explicit
- Planned proof focus:
  - producer repair translations mutate score plans concretely for `mute_drums`, `swap_instrument`, and `adjust_dynamics`
  - `_passesAudioValidation(...)` behavior remains unchanged
  - adapter-side exclusions actually remove avoided drums/instruments after track adaptation

## Execution Log — Milestone 3 Slice 1 (producer correction translation + downstream exclusion bridge)
- Date: 2026-04-03
- Supervisor: recursive-supervisor decomposition + orchestration by supervisor
- Builder: recursive-builder
- Verifier: recursive-verifier
- Scope: producer-side translation of structured output-analysis corrections into concrete score-plan mutations for `mute_drums`, `swap_instrument -> piano`, and `adjust_dynamics`; preserve conservative `adjust_eq` guidance-only behavior; then re-apply adapter exclusions after track-derived instrument/drum overrides so those repair levers become effective downstream
- Files changed:
  - `copilot-Liku-cli/src/main/agents/producer.js`
  - `copilot-Liku-cli/scripts/test-output-analysis-repair.js`
  - `multimodal_gen/score_plan_adapter.py`
  - `tests/test_score_plan_adapter.py`
- Tests run:
  - `node scripts/test-output-analysis-repair.js`
  - `python -m pytest tests/test_output_analyzer.py tests/test_score_plan_adapter.py -q`
- Result: PASS — producer repair proofs passed (5/5) and analyzer/adapter regressions passed (49/49). Post-verifier confirmed the slice stayed bounded, made the translated repair levers effective downstream through `score_plan_to_parsed_prompt(...)`, and preserved the existing critic/audio acceptance-gating semantics.
- Follow-up risks:
  - `adjust_eq` is still conservative guidance-only by design, so deterministic EQ repair remains a later slice
  - the slice improved repair specificity and downstream leverage but did not yet add targeted retry routing

## Preparation Log — Milestone 3 Slice 2 (deterministic structured-repair retry routing)
- Date: 2026-04-03
- Supervisor: recursive-supervisor decomposition + aggregation by supervisor
- Scope chosen: route the next retry deterministically through the already-accepted structured repair delta when output-analysis corrections are actionable and critics are otherwise green
- Files planned:
  - `copilot-Liku-cli/src/main/agents/producer.js`
  - `copilot-Liku-cli/scripts/test-output-analysis-repair.js`
- Why this slice:
  - `builder.regenerateSection(...)` exists, but the current JSON-RPC request builder does not actually carry section/original-task semantics through the Copilot path yet
  - take generation is real, but take-selection is not yet safe enough on the JSON-RPC/render path for the first Slice 2
  - producer-side deterministic retry routing uses already-proven correction semantics without inventing broader protocol layers
- Guardrails:
  - preserve `_passesAudioValidation(...)` and critic-gate bypass behavior exactly
  - keep the slice producer-only
  - use the deterministic retry fast path only when structured corrections are actionable and critic metrics do not also require broader refinement
  - preserve the broader `_refineScorePlan(...)` path in all other cases
- Planned proof focus:
  - actionable structured correction + critics passed uses deterministic retry routing
  - no actionable corrections preserves the broader refinement path
  - failed critic metrics preserve the broader refinement path even when structured corrections exist

## Execution Log — Milestone 3 Slice 2 (deterministic structured-repair retry routing)
- Date: 2026-04-03
- Supervisor: recursive-supervisor decomposition + orchestration by supervisor
- Builder: recursive-builder
- Verifier: recursive-verifier
- Scope: replace the retry-loop's unconditional broader refinement call with a bounded chooser that directly reuses the concretely mutated heuristic plan when output-analysis corrections are actionable (`mute_drums`, `swap_instrument -> piano`, `adjust_dynamics`) and no critic metrics failed; otherwise preserve the existing broader `_refineScorePlan(...)` path
- Files changed:
  - `copilot-Liku-cli/src/main/agents/producer.js`
  - `copilot-Liku-cli/scripts/test-output-analysis-repair.js`
- Tests run:
  - `node scripts/test-output-analysis-repair.js`
- Result: PASS — focused producer repair/routing proofs passed (8/8). Post-verifier confirmed the slice stayed bounded to the producer/test surfaces, made retry routing more specific in a real way, preserved the broader refine path when critics or missing corrections require it, and left acceptance/audio gating semantics unchanged.
- Follow-up risks:
  - true section-specific regeneration is still only an apparent surface on the Copilot JSON-RPC path and should not be treated as wired yet
  - take generation exists, but take-selection remains unsafe as a first producer slice until the JSON-RPC/render path can prove per-take selection semantics
  - `adjust_eq` remains guidance-only until correction detail can be translated into a safe directional plan mutation

## Preparation Log — Milestone 3 Slice 3 (directional EQ repair)
- Date: 2026-04-03
- Supervisor: recursive-verifier pre-check + aggregation by supervisor
- Recommended title: **Directional EQ repair: analyzer-emitted brightness direction + bounded producer mastering mutation**
- Scope chosen: enrich `adjust_eq` corrections so they explicitly say whether the render is too bright or too dark, then let producer apply a small clamped mastering mutation to `brightness_target` (and only a conservative paired warmth move if the direction is explicit)
- Files planned:
  - `multimodal_gen/output_analyzer.py`
  - `tests/test_output_analyzer.py`
  - `copilot-Liku-cli/src/main/agents/producer.js`
  - `copilot-Liku-cli/scripts/test-output-analysis-repair.js`
- Why this slice:
  - downstream plumbing already exists: mastering `brightness_target` / `warmth_target` survive the score-plan path and are consumed at runtime
  - the current blocker is upstream correction detail, not transport/runtime wiring
  - current `adjust_eq` corrections are intentionally non-directional (`"Apply corrective EQ"`), so producer-only deterministic EQ mutation would still be guessing
- Why alternatives were rejected:
  - producer-only EQ mutation would duplicate Python target-threshold logic in JS or infer direction from generic failure state, both of which would drift and violate the bounded-slice rule
  - using current correction detail strings without enriching them is unsafe because they do not distinguish too bright vs too dark
  - section regeneration / take-selection remain riskier and not yet truthfully wired on the Copilot JSON-RPC path
- Guardrails:
  - no protocol, adapter, regeneration, or take-selection changes
  - keep the slice centered on centroid-driven brightness direction only; do not broaden into generic multi-band EQ synthesis
  - `adjust_eq` must remain guidance-only when direction is not explicit
  - clamp any mastering mutation within the existing schema-safe `[0,1]` range
- Planned proof focus:
  - analyzer emits explicit directional `adjust_eq` detail for high-centroid and low-centroid issues
  - producer lowers `brightness_target` for "too bright" and raises it for "too dark" using small bounded deltas
  - non-directional `adjust_eq` remains guidance-only
  - deterministic retry routing may include directional `adjust_eq` only when critics are otherwise green

## Execution Log — Milestone 3 Slice 3 (directional EQ repair)
- Date: 2026-04-03
- Supervisor: recursive-supervisor orchestration + recursive-verifier post-check aggregation by supervisor
- Builder: recursive-builder
- Verifier: recursive-verifier
- Scope: enrich centroid-driven `adjust_eq` corrections so they explicitly distinguish too-bright versus too-dark renders, then let producer consume only that explicit direction as a small clamped mastering-intent mutation (`brightness_target` plus a conservative paired `warmth_target` counter-move) while preserving non-directional `adjust_eq` as guidance-only and keeping deterministic retry routing gated on clean critic metrics
- Files changed:
  - `multimodal_gen/output_analyzer.py`
  - `tests/test_output_analyzer.py`
  - `copilot-Liku-cli/src/main/agents/producer.js`
  - `copilot-Liku-cli/scripts/test-output-analysis-repair.js`
- Tests run:
  - `python -m pytest tests/test_output_analyzer.py -q`
  - `node scripts/test-output-analysis-repair.js`
- Result: PASS — focused analyzer regressions passed (45/45) and focused producer repair/routing proofs passed (11/11). Post-verifier confirmed the slice remained bounded to centroid-direction EQ repair only, kept non-directional `adjust_eq` guidance-only, made deterministic retry routing include directional EQ only when critic metrics are otherwise green, and preserved the existing acceptance/audio gating semantics.
- Follow-up risks:
  - directional EQ repair is intentionally limited to centroid-derived bright/dark inference only; it does not yet attempt broader multi-band spectral repair
  - generic or unparseable `adjust_eq` detail still remains guidance-only by design
  - the next Milestone 3 slice should prefer another explicit, bounded rendered-audio repair lever rather than reopening protocol/regeneration surfaces prematurely

## Preparation Log — Milestone 3 Slice 4 (high onset-density drum-light escalation)
- Date: 2026-04-03
- Supervisor: recursive-supervisor read-only decomposition + aggregation by supervisor
- Recommended title: **High onset-density drum-light escalation via existing `mute_drums` repair**
- Scope chosen: reuse the already-accepted deterministic `mute_drums` repair path by teaching `output_analyzer.py` to emit `mute_drums` when onset density is explicitly too high in contexts where the genre target is drum-light / low-density, while avoiding any generic arrangement-density or protocol expansion
- Files planned:
  - `multimodal_gen/output_analyzer.py`
  - `tests/test_output_analyzer.py`
- Why this slice:
  - `output_analyzer.py` already emits structured onset-density issues, but the correction engine does not yet translate them into any concrete repair
  - producer-side `mute_drums` handling, deterministic retry routing, and adapter-side `avoid_drums` preservation are already implemented and proven end-to-end
  - this lets the next slice deepen analyzer-to-repair closure without inventing new correction actions or depending on unsupported track-density transport
- Why nearby alternatives were rejected:
  - generic onset-density reduction is riskier because track `density` / `activation` are not yet a proven deterministic downstream repair sink
  - broader timbre swaps beyond piano lack equally explicit analyzer semantics and proven producer mappings
  - tension-shape rebalance remains under-specified in analyzer outputs and would be less bounded than this reuse slice
- Guardrails:
  - no producer, adapter, regeneration, take-selection, or protocol changes unless proof shows they are strictly required
  - emit `mute_drums` only for explicit too-high onset density in drum-light contexts; do not treat all onset-density mismatches as drum muting
  - preserve deduplication behavior when other analyzer branches already suggest `mute_drums`
- Planned proof focus:
  - high onset-density issue in a drum-light context emits `mute_drums`
  - low or in-range onset density does not emit `mute_drums`
  - duplicate drum-muting cues do not create duplicate `mute_drums` corrections

## Execution Log — Milestone 3 Slice 4 (high onset-density drum-light escalation)
- Date: 2026-04-03
- Supervisor: recursive-supervisor decomposition + recursive-verifier post-check aggregation by supervisor
- Builder: recursive-builder
- Verifier: recursive-verifier
- Scope: extend the analyzer correction engine so explicit too-high onset-density issues escalate into the already-proven `mute_drums` repair path only when the parsed expected high bound indicates a drum-light context (`<= 2.0`), while preserving deduplication and avoiding any producer, adapter, or protocol changes
- Files changed:
  - `multimodal_gen/output_analyzer.py`
  - `tests/test_output_analyzer.py`
- Tests run:
  - `python -m pytest tests/test_output_analyzer.py -q`
- Result: PASS — focused analyzer regressions passed (49/49). Post-verifier confirmed the slice remained behaviorally bounded to onset-density issue translation only, reused the existing deterministic `mute_drums` downstream path truthfully, preserved deduplication, and kept the threshold conservative against current analyzer targets.
- Follow-up risks:
  - the `<= 2.0` drum-light cutoff is intentionally conservative for current targets but is still a literal boundary rather than metadata-derived intent
  - broader over-busy arrangement repair still lacks a proven deterministic downstream density sink and should not be conflated with this narrow drum-light escalation slice

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
