# GPTtasks.md — Masterclass Musicality Uplift (Grounded Integration Plan)

> Goal: raise musical quality (“masterclass instruments played like legends”) **without breaking existing functionality**.
>
> This plan is grounded in the current repo reality:
> - Generation orchestration happens in `main.py::run_generation()`.
> - Arrangement already has per-section configs and **motif fields** in `multimodal_gen/arranger.py`.
> - A full **tension arc system exists** in `multimodal_gen/tension_arc.py` but is not currently wired into `Arranger`/`MidiGenerator`.
> - Take/comp pipeline already exists and is already invoked from `main.py` (do not rebuild).
> - Audio rendering supports FluidSynth + procedural fallback + instrument libraries in `multimodal_gen/audio_renderer.py`.
>
---

## 0) Leading Questions (to avoid guessing)

- [x] **Q0.1 (Timbre priority)**: **A** — strongly prefer real timbres, keep procedural fallback but warn loudly and document setup.

- [x] **Q0.2 (Target genres)**: Tune first: `ethiopian` + `g_funk`.

- [x] **Q0.3 (Regression baseline)**: Start with **A** (MIDI + metrics + render-path report). Add **B** later as opt-in once render is pinned.

- [x] **Q0.4 (SoundFont policy)**: **A + B**, plus **C** as optional strict mode.

---

## Phase 0 — Observability + “Why does it sound beginner?” proof

### Objective
Make output quality **diagnosable**. Right now, a big quality swing comes from whether rendering uses FluidSynth+SF2 vs procedural fallback.

### Tasks
- [x] **P0.1 Write a render diagnostics report per generation**
  - Where: `multimodal_gen/audio_renderer.py` + `main.py::run_generation()`
  - Deliverable: `output/<project>/*_render_report.json` (written alongside the WAV)
  - Must include:
    - renderer path taken: `fluidsynth` vs `procedural`
    - `fluidsynth_available` boolean
    - `soundfont_path` actually used (or `null`)
    - whether instrument library loaded + counts per category (if used)
    - whether expansion instruments were loaded
    - any warnings encountered (missing SF2, missing librosa, etc.)

- [x] **P0.2 Create repo-local SoundFont folder + instructions (no copyrighted binaries)**
  - Create: `assets/soundfonts/README.md`
  - Align with existing search behavior in `audio_renderer.find_soundfont()` which already checks `./assets/soundfonts/`.
  - Document expected naming (already checked by code): `FluidR3_GM.sf2`, `GeneralUser_GS.sf2`, `default.sf2`, etc.

- [x] **P0.3 Add a CLI “audio doctor” command**
  - Where: `diagnose_audio.py` or add a new `--diagnose-audio` mode in `main.py`
  - Output:
    - FluidSynth detection (`check_fluidsynth_available()`)
    - `find_soundfont()` result
    - whether default `instruments/` folder has any samples

### Acceptance
- [x] Every generation produces a clear statement of what renderer was used.
- [x] A missing SF2 explains itself (no silent quality cliff).

---

## Phase 1 — Wire tension arc end-to-end (existing module, currently unused)

### Objective
Make sections feel like they *evolve* (build → peak → release) using `multimodal_gen/tension_arc.py`.

### Tasks
- [x] **P1.1 Add a tension arc to `Arrangement`**
  - Where: `multimodal_gen/arranger.py` (`@dataclass class Arrangement`)
  - Add field(s) such as `tension_arc: Optional[TensionArc]` or `tension_points: List[...]`.
  - Generate arc during `Arranger.create_arrangement(parsed)`:
    - Prefer matching to section structure using `TensionArcGenerator.match_to_sections()`.
    - If preset system sets `tension_arc_shape`, map to `ArcShape`.

- [x] **P1.2 Apply tension arc to MIDI generation**
  - Where: `multimodal_gen/midi_generator.py::MidiGenerator.generate()` and track builders.
  - Approach (minimal change, maximum leverage):
    - For each section, compute normalized position and get tension via `TensionArc.get_tension_at()`.
    - Modulate existing section-driven parameters (already used widely):
      - dynamics: scale base velocities
      - density: adjust hit probability / note addition
      - complexity: bias chord extensions (where supported)
  - Keep it safe: tension arc should be *multipliers* on existing section config, not a rewrite.

- [x] **P1.3 Persist tension arc into the session manifest**
  - Where: `multimodal_gen/session_graph.py` manifest save logic + `main.py` manifest writing.
  - Add tension curve/points so JUCE UI can visualize it later.

- [x] **P1.4 Add genre-aware complexity shaping + qenet embellishment**
  - Where: `multimodal_gen/midi_generator.py`, `multimodal_gen/session_graph.py`, `multimodal_gen/ethio_melody.py`
  - Deliverables:
    - Harmony/voicing/melody ornamentation driven by tension-derived `complexity`
    - Mode-aware qenet/ethio-jazz melodic embellisher that keeps notes in-scale

### Acceptance
- [ ] Tracks become clearly denser/louder near choruses/drops and sparser in breakdown/outro.
- [ ] No genre regressions: existing section configs remain the base behavior.

---

## Phase 2 — Use the existing motif system for real thematic coherence

### Objective
The arranger already generates motifs + per-section motif assignments, but MIDI generation mostly ignores them.

### Tasks
- [x] **P2.1 Verify motif generation happens for target genres**
  - Where: `multimodal_gen/arranger.py` (motif generation + `GENRE_MOTIF_MAPPINGS`)
  - Add/verify unit coverage that `Arrangement.motifs` and `motif_assignments` are populated for a known prompt.

- [x] **P2.2 Drive melody generation from arrangement motifs**
  - Where: `multimodal_gen/midi_generator.py` in `_create_melody_track()`
  - Use:
    - section identity → motif assignment → transformed motif → note events
    - transformation options already represented in `MotifAssignment` (invert/retrograde/augment/diminish/sequence)
  - Preserve constraints:
    - keep within key/scale
    - keep density gated by `section.config.enable_melody` and section energy

- [x] **P2.3 Quality validator: promote “motif repetition” from suggestion to actionable**
  - Where: `multimodal_gen/quality_validator.py`
  - If “no motifs detected”, suggest enabling motif-driven melody (or raising motif_density via preset).

### Acceptance
- [ ] Lead lines are recognizably related across sections (theme/variation).
- [ ] No new module creation; only wiring existing pieces.

---

## Phase 3 — “Pro timbre by default” (without breaking offline fallback)

### Objective
Eliminate the “toy synth” perception when possible, and make it explicit when we cannot.

### Tasks
- [x] **P3.1 Promote consistent renderer selection**
  - Where: `multimodal_gen/audio_renderer.py::AudioRenderer.render_midi_file()`
  - Ensure the decision tree is visible and stable:
    - If custom drum cache / instrument library is loaded, confirm whether FluidSynth should still be allowed for melodic tracks.
    - If not, document why in `render_report.json`.

- [x] **P3.2 Default SoundFont UX**
  - Where: `main.py` CLI help + `README.md`
  - Add one canonical path recommendation:
    - Put SF2 in `assets/soundfonts/` OR pass `--soundfont`.

- [x] **P3.3 Stem naming + manifest alignment**
  - Where: `multimodal_gen/audio_renderer.py::render_stems()` + session manifest
  - Verify the existing `stems_manifest.json` generation (noted as implemented in `MASTER_PLAN.md`) and extend it only if needed:
    - ensure stem naming is stable and matches session manifest track/role names
    - include suggested mix gains only if not already present

### Acceptance
- [ ] On machines with FluidSynth+SF2, default output is noticeably better.
- [ ] On procedural fallback, users understand what they’re hearing and how to upgrade it.

---

## Phase 4 — Regression and quality gates (don’t break what works)

### Objective
Protect existing capabilities while raising musicality.

### Tasks
- [x] **P4.1 Add MIDI-level “musicality metrics” tests**
  - Where: `tests/` (create `tests/test_musicality_metrics.py`)
  - Examples (deterministic-ish):
    - velocity distribution not collapsed (avoid all ~same velocity)
    - note density changes across sections (drop > breakdown)
    - no impossible drum overlaps if physics humanizer is enabled

- [x] **P4.2 Add a “render path” regression test**
  - Where: `tests/`
  - Assert the `render_report.json` fields are present and consistent.

- [x] **P4.3 Golden prompt set**
  - Where: `tests/fixtures/` (or a simple JSON file in `tests/`)
  - Store ~10–15 prompts (genre coverage + common variants) used in CI/local checks.

### Acceptance
- [x] Running `pytest` catches obvious musical regressions quickly.

### Next (optional but valuable)
- [x] **P4.5 Golden prompt runner (lightweight harness)**
  - Where: `tests/` (e.g., `tests/test_golden_prompts_smoke.py`)
  - Load `tests/fixtures/golden_prompts.json` and assert:
    - `PromptParser` normalizes `expected_genre`
    - generation returns a MIDI with non-empty drums (fast, no audio render)

### New Guard (prevent genre fallbacks)
- [x] **P4.4 Genre normalization regression test**
  - Where: `multimodal_gen/utils.py` + `tests/`
  - Purpose: ensure variants like `gfunk`, `g-funk`, `g funk` normalize to `g_funk` and never silently fall back to a default genre.

---

## Phase 5 — Nice-to-have (only after Phase 0–4)

- [x] **P5.1 Integrate preset system into generation**
  - Where: `multimodal_gen/preset_system.py` + `PromptParser`/`main.py`
  - Goal: “production presets” that set `tension_arc_shape`, motif density, swing/microtiming, etc.

- [x] **P5.2 Expose tension/motif/preset/duration controls over OSC**
  - Where: `PROTOCOL.md` + `multimodal_gen/server/osc_server.py` + `multimodal_gen/server/worker.py` + `main.py`
  - Backward-compatible: schema v1, optional fields, and accept legacy `bars` as alias for `duration_bars`.
  - Added persisted global overrides via `/controls/set` and `/controls/clear` (per-request overrides win).

---

## Phase 6 — JUCE UI: ControlsWindow + MultiView (regen-first)

### Objective
Expose Phase 5.2 controls in the JUCE app with a **user-friendly**, MPC-like workflow:
- **Global defaults** persisted via OSC `/controls/*` (default)
- **Per-request overrides** (per-tab/channel later) that can override globals
- Regen-first iteration: timeline loop/region → regenerate that region quickly

### Tasks (JUCE)
- [x] **P6.1 Add OSC address constants for `/controls/set` and `/controls/clear`**
  - Where: `juce/Source/Communication/Messages.h` (`namespace OSCAddresses`)

- [x] **P6.2 Implement OSCBridge helpers for global controls**
  - Where: `juce/Source/Communication/OSCBridge.h/.cpp`
  - Add: `sendControlsSet(overridesJson)` and `sendControlsClear(keys)`
  - Payload must include: `request_id` + `schema_version` (+ `overrides` / `keys`)

- [x] **P6.3 Add a floating ControlsWindow (graceful exit)**
  - Where: `juce/Source/UI/ControlsWindow.*` + `juce/Source/UI/ControlsPanel.*`
  - Controls (Phase 5.2):
    - tension: `tension_arc_shape`, `tension_intensity`
    - motifs: `motif_mode` (auto/on/off), `num_motifs` (1–3)
    - presets: `preset`, `style_preset`, `production_preset`
    - generation: `seed`, `duration_bars` (still show “Bars”)
  - Actions:
    - “Apply Global” → `/controls/set`
    - “Clear Global” → `/controls/clear`
  - Graceful exit: close button hides window (does not crash/kill app)

- [x] **P6.4 Wire ControlsWindow into Tools menu + MainComponent**
  - Where: `juce/Source/UI/TransportComponent.*` + `juce/Source/MainComponent.*`
  - Add Tools menu item: “Controls”
  - MainComponent forwards apply/clear actions to `OSCBridge`

- [ ] **P6.4b Add per-request overrides (apply-once) from ControlsWindow**
  - Where: `juce/Source/Communication/Messages.h` + `juce/Source/MainComponent.*` + `juce/Source/UI/ControlsPanel.*`
  - Behavior:
    - “Apply Next” arms overrides for the next `/generate` and `/regenerate` request only (then clears)
    - Overrides are sent via `options` (do not persist)
    - Existing fields remain compatible (JUCE still sends `bars`; Python accepts `duration_bars` and legacy `bars`)

### Tasks (next: MultiView tabs)
- [ ] **P6.5 MultiView channel tabs (design + implement)**
  - Concept: Overview tab + N “channels” (tabs) that act like per-track/per-scene workspaces
  - Default behavior: global controls apply everywhere; per-tab overrides optional
  - Regen-first: each channel can store a loop region + last request_id + prompt snapshot

### Acceptance
- [ ] Changing controls in JUCE affects Python generation without breaking existing `/generate`/`/regenerate`.
- [ ] ControlsWindow can be opened/closed repeatedly without leaks/crashes.
- [ ] Protocol remains schema v1 compatible.

---

## Notes (ground truth reminders)

- `main.py::run_generation()` already:
  - builds arrangement via `Arranger.create_arrangement()`
  - builds session graph (`SessionGraphBuilder`)
  - compiles and applies `StylePolicy` if available
  - generates takes and comps (do not duplicate)
  - renders audio via `AudioRenderer.render_midi_file()` and optionally stems

- `multimodal_gen/arranger.py` already contains motif structures and genre motif mappings.
- `multimodal_gen/tension_arc.py` already contains tension curve generation and mapping helpers.

---

## Quick “Start Here” checklist

- [x] Answer Q0.1–Q0.4
- [x] Implement Phase 0 first (diagnose the real bottleneck)
- [x] Then Phase 1 (tension arc) + Phase 2 (motif wiring)
- [x] Add Phase 4 tests before large refactors
