# zzTODO.md — Grounded Roadmap (Docs↔Code Audit)

This file is a **high-level, implementation-oriented roadmap** generated from a static (read-only) audit of the project markdown docs and corresponding code. It is intended to stay “industry-aligned” (modern AI-assisted music production workflows) while remaining **grounded** in what is already implemented vs. what is still missing.

## Audit Method (No Execution)

- No tests were executed as part of producing this roadmap.
- Verification is by **docs↔code cross-reference** (grep + file inspection) only.
- Practical note: you can run tests without touching `test_suite.py` via `pytest -q tests` (avoids collecting the standalone runner script).

## Note: `test_suite.py` (Why It Broke Under Pytest)

During an earlier attempt to “verify comprehensively”, `pytest` was run and it tried to collect `test_suite.py` as a test module. This failed because:

- `test_suite.py` is a **standalone runner** (it says “Run with: `python test_suite.py`”).
- It defines a decorator `def test(name): ...` at `multimodal-ai-music-gen/test_suite.py:26`.
- Under pytest, a top-level `test(...)` looks like a test function requiring a fixture named `name`, producing the error: *fixture 'name' not found*.

What I *temporarily* changed (and then reverted per request):
- Rename `test(...)` → `register_test(...)` and update decorators `@test(...)` → `@register_test(...)`.

Why that rename is a reasonable fix (if you ever want it):
- It prevents pytest from treating `test(name)` as a test function/fixture entry-point while preserving the standalone runner behavior.

Why it was reverted:
- This roadmap is now “no execution; docs↔code audit only”, and you asked to avoid changes that might ripple into established workflows.

## Sources Synthesized (Markdown)

Primary “state of the repo” docs:
- `multimodal-ai-music-gen/remainingTasks.md` — explicitly calls itself the source of truth for what remains; includes code pointers for what’s verified complete.
- `multimodal-ai-music-gen/IMPLEMENTATION_STATUS.md` + `multimodal-ai-music-gen/IMPLEMENTATION_SUMMARY.md` — session summaries (useful, but should be treated as claims to verify).
- `multimodal-ai-music-gen/PROTOCOL.md` — canonical OSC contract reference (also points to the authoritative code files).
- `multimodal-ai-music-gen/README.md` + `multimodal-ai-music-gen/NEW_FEATURES.md` — user-facing capabilities and usage claims.

Strategic / older planning docs (some content is already implemented and should not be re-done):
- `multimodal-ai-music-gen/MASTER_PLAN.md`, `multimodal-ai-music-gen/TODO*.md`, `multimodal-ai-music-gen/TODOtasks.md`
- `multimodal-ai-music-gen/juce/UI_IMPROVEMENTS_PHASE2.md` (targeted UX follow-ups)
- `multimodal-ai-music-gen/knowing.md` (project knowledge base / continuation guide)
- `multimodal-ai-music-gen/TODO_PHASE5.md` (editing phase summary)
- `multimodal-ai-music-gen/docs/ETHIOPIAN_INSTRUMENTS.md` and `multimodal-ai-music-gen/instruments/README.md` (domain-specific subsystem docs)

## Current Reality (Grounded in Code Pointers)

### Python backend (generation + server) is “feature-rich”
Grounded by presence of:
- Protocol hardening fields (`schema_version`, `request_id`) in `multimodal-ai-music-gen/multimodal_gen/server/osc_server.py` and dataclasses in `multimodal-ai-music-gen/multimodal_gen/server/worker.py`.
- BWF writer and metadata reader in `multimodal-ai-music-gen/multimodal_gen/bwf_writer.py`.
- Refinement workflow flags and metadata in `multimodal-ai-music-gen/main.py` (e.g., `--refine`, `project_metadata.json` creation).
- Expansion system in `multimodal-ai-music-gen/multimodal_gen/expansion_manager.py` plus OSC handlers in `multimodal-ai-music-gen/multimodal_gen/server/osc_server.py`.

### JUCE app is already beyond “prototype UI”
Grounded by presence of:
- Project state + undo: `multimodal-ai-music-gen/juce/Source/Project/ProjectState.cpp` and widespread ValueTree listening in UI components.
- Mixer graph core: `multimodal-ai-music-gen/juce/Source/Audio/MixerGraph.*`.
- FX chain UI and persistence hooks: `multimodal-ai-music-gen/juce/Source/UI/FXChainPanel.*`.
- Arrangement-style multi-track UI: `multimodal-ai-music-gen/juce/Source/UI/TrackList/ArrangementView.*`.

### Key doc inconsistencies (important for planning)
- Several “plan” docs list items as remaining that are already implemented (explicitly called out by `multimodal-ai-music-gen/remainingTasks.md`).
- Treat `multimodal-ai-music-gen/remainingTasks.md` as the “planning truth”, and treat other TODO docs as idea backlogs unless re-validated.

## Producer-GPT Checklist (External) — Reconciled With Repo Reality

You provided an external “Producer-GPT” checklist. The direction is strong, but a few assumptions in that checklist don’t match this repo (which already contains a JUCE app and a mature OSC contract). This section maps “what to build” into the repo’s actual architecture.

### Already true here (don’t re-build)
- This repo is not “just a script”: JUCE UI + audio engine + OSC bridge already exist.
  - Grounding: `multimodal-ai-music-gen/juce/Source/MainComponent.cpp`, `multimodal-ai-music-gen/juce/Source/Communication/OSCBridge.cpp`, `multimodal-ai-music-gen/juce/Source/Audio/AudioEngine.h`, `multimodal-ai-music-gen/juce/Source/Audio/MixerGraph.cpp`.
- “Takes” are already defined in the protocol and server, and there is take-lane UI code, but the UI isn’t wired into the main app flow yet.
  - Grounding: `multimodal-ai-music-gen/multimodal_gen/server/osc_server.py` (handlers for `/take/select`, `/take/comp`, `/take/render`), `multimodal-ai-music-gen/juce/Source/UI/TakeLaneComponent.cpp`.
- Groove templates and mix “glue” scaffolding exist in Python; the remaining work is making them policy-driven and user-visible.
  - Grounding: `multimodal-ai-music-gen/multimodal_gen/groove_templates.py`, `multimodal-ai-music-gen/multimodal_gen/mix_chain.py`.

### Still valuable + not clearly complete end-to-end (net-new work)
- A formal **StylePolicy / StyleEnforcer** layer that explains and controls “producer decisions” (micro-timing, voicing, arrangement rules, instrumentation constraints).
- A “crate digger” **asset manifest + intent-based retrieval** system (beyond string matching).
  - Grounding starting point: instrument analysis/indexing exists (`multimodal-ai-music-gen/multimodal_gen/instrument_manager.py`, `multimodal-ai-music-gen/multimodal_gen/instrument_index.py`), but “prompt → feature search” is not established as a first-class workflow.
- A **physics-aware humanizer** (fatigue/limb-conflicts/ghost-note heuristics) layered on top of groove templates.
- A **plugin hosting strategy**: choose where VSTs live (JUCE realtime vs Python offline render) and keep FX chain semantics consistent.
- **Professional delivery/export**: MPC-hardware-safe packaging and explicit stem/master bit-depth policy.
- **Engineer polish for “studio feel”**: make tails/looping and bus processing explicit and deterministic.
  - Grounding starting point: soft clipping + limiter and tail rendering already exist (`multimodal-ai-music-gen/multimodal_gen/audio_renderer.py` includes `soft_clip_audio(...)` and `tail_seconds`).

## What’s Not Implemented Yet (High-Confidence Gaps)

These are repeatedly identified as remaining in docs and/or are missing integration touchpoints in code.

### 1) Take Lanes: UI exists, but not wired into the app flow
Grounding:
- Take lane UI exists: `multimodal-ai-music-gen/juce/Source/UI/TakeLaneComponent.*`.
- There’s no reference to `TakeLanePanel` in `multimodal-ai-music-gen/juce/Source/MainComponent.*` (no integration into tabs/bottom panel, no listener wiring).

### 2) “Timeline → Arrangement Editor” (clip/region editing)
Grounding:
- `remainingTasks.md` calls this out as still remaining (“upgrade timeline from display + seek to arrangement (region clips, editing)”).
- Current `ArrangementView` draws a ruler and shows lanes, but there’s no explicit clip-region object model exposed in the docs as completed.

### 3) Distribution packaging (non-dev install)
Grounding:
- Still listed as pending in `multimodal-ai-music-gen/remainingTasks.md` and `multimodal-ai-music-gen/IMPLEMENTATION_STATUS.md`.
- No installer scripts/configs are present as committed artifacts in the project root (the plans mention them, but codebase doesn’t show implementation).

### 4) Plugin hosting (VST3/AU)
Grounding:
- Planning docs emphasize it; code search shows no `PluginDirectoryScanner` / `KnownPluginList` usage in `multimodal-ai-music-gen/juce/Source/`.

### 5) UI Improvements Phase 2 items (partially implemented)
Grounding:
- Instruments still open in a floating `juce::DocumentWindow`: `multimodal-ai-music-gen/juce/Source/MainComponent.cpp:196` (case 1).
- Expansions window is also a raw `juce::DocumentWindow` without custom close handling: `multimodal-ai-music-gen/juce/Source/MainComponent.cpp:241` (case 3).
- Timeline ruler zoom-sync appears implemented now (uses `hZoom` + viewport position): `multimodal-ai-music-gen/juce/Source/UI/TrackList/ArrangementView.cpp:498`.

## Roadmap (Industry-Standard AI Music Production Direction)

This roadmap is structured as “product workflows first”, then “pro-grade infrastructure”.

### 🛑 Strategic Architecture Risks (Must Validate Early)

Before committing to Phase E (VST3) or Phase C (Pro Mixer), we must validate the **"Python Sidecar" architecture**:
- **Risk:** Shipping a VST3 that depends on a local Python background process is fragile (firewalls, zombie processes, installation size).
- **Validation Task:** Create a "Hello World" VST3 that spawns a Python process, sends a prompt, and plays returning audio. If latency > 20ms or startup fails > 5% of the time, **abort VST3** and focus on "Standalone App + Drag-and-Drop".

### Phase A — “Non-Destructive Iteration” (Modern AI co-pilot workflow)
Goal: make the core workflow match what users expect from current AI music tools: iterate, compare, and keep versions.

- **A0. Establish a StylePolicy / StyleEnforcer layer (“producer brain”)**
  - Implement `multimodal_gen/style_policies.py` (or similar) that produces a structured “policy context” from `(parsed prompt, genre, target vibe)`:
    - micro-timing rules (e.g., snare-late ranges per genre)
    - voicing constraints (e.g., lofi chord extensions)
    - arrangement constraints (fills, dropouts, transitions)
    - instrumentation/mix constraints (low-end management and role mutex)
  - Integration: consumed by `MidiGenerator`, `TakeGenerator`, and default mix/render choices (rather than scattering rules across modules).
  - Acceptance: emit a JSON-able “decision record” that the UI can show (“why did it do this?”).

- **A1. Wire Take Lanes into JUCE**
  - Surface takes per track, allow audition, select, render, and comp.
  - Touchpoints: `juce/Source/MainComponent.*`, `juce/Source/UI/TakeLaneComponent.*`, `juce/Source/Communication/OSCBridge.*`, server handlers in `multimodal_gen/server/osc_server.py`.
  - Acceptance: user can generate variations, audition per-track takes, and render a selected comp to audio without losing previous takes.

- **A1.1 Ensure take generation is real (not just protocol/UI)**
  - Ensure generation requests with `num_takes > 1` actually produce take lane metadata (stable IDs, seeds, variation axis, bar ranges) that the JUCE UI can render.
  - Grounding: take generation infrastructure exists (`multimodal-ai-music-gen/multimodal_gen/take_generator.py`) and the worker protocol includes `num_takes` and `take_variation` (`multimodal-ai-music-gen/multimodal_gen/server/worker.py`), but it’s not obvious from docs/UI that the full loop is complete.

- **A2. Region-based regeneration (“inpainting”) in ArrangementView**
  - Select bar range + target tracks → `/regenerate` on server.
  - Touchpoints: `juce/Source/UI/TrackList/ArrangementView.*`, protocol in `multimodal-ai-music-gen/PROTOCOL.md`, handlers in `multimodal_gen/server/osc_server.py`.
  - Acceptance: user can fix a drum fill or melody segment without re-generating the whole song.

- **A3. Prompt history + A/B comparison**
  - Store prompt + seed + outputs; provide fast A/B switching and blind rating (optional).
  - Touchpoints: `juce/Source/Project/ProjectState.*`, `main.py` metadata, `output/project_metadata.json`.
  - Acceptance: the app behaves like “version control for music ideas”.

### Phase A+ — “Crate Digger” Instrument Discovery (producer-grade sound selection)
Goal: selection by sound and intent (“underwater pad”), not filename (“pad_underwater.wav”).

- **A4. Standardize an asset manifest**
  - Define a single manifest schema (JSON) for samples/expansions (and later plugin presets): spectral features, envelope estimates, pitch estimate (when relevant), tags, file path, provenance.
  - Grounding starting point: indexing/analysis infrastructure exists in `multimodal-ai-music-gen/multimodal_gen/instrument_manager.py` and `multimodal-ai-music-gen/multimodal_gen/instrument_index.py`.

- **A5. Visual Instrument Browser (UI)**
  - Implement the frontend for the "Crate Digger".
  - **Category Tree:** Hierarchical view (Drums > Kicks > Analog).
  - **Preview Panel:** Waveform thumbnail + Play/Stop for samples before loading.
  - **Drag-and-Drop:** Dragging a sample from the browser directly onto a track or piano roll.
  - Touchpoints: `juce/Source/UI/InstrumentBrowser/*` (New components).

- **A6. Add intent-based retrieval**
  - Start simple: cosine similarity over normalized numeric features + rule-based filters (attack/brightness/category).
  - Later optional: ANN index behind a feature flag if you need scale.
  - Acceptance: prompts like “dark, slow-attack pad” reliably retrieve assets even when filenames are unhelpful.

### Phase B — “DAW-Grade Project Workflow”
Goal: stop being “a generator + UI” and become a reliable production project.

- **B1. Make save/load truly portable and complete**
  - Validate that ProjectState persistence includes: tracks, instruments, FX chains, loop regions, analysis results, takes.
  - Touchpoints: `juce/Source/Project/ProjectState.*`, `juce/Source/UI/FXChainPanel.*`, take lane persistence additions.
  - Acceptance: round-trip save→close→open restores the session identically.

- **B2. Export interoperability**
  - At minimum: consistent stems manifest + MIDI export + BWF metadata.
  - Optional: DAW-friendly folder export structure (Ableton/Logic templates are “nice to have” but can be a later layer).
  - Touchpoints: `multimodal_gen/audio_renderer.py`, `multimodal_gen/bwf_writer.py`, `main.py`.

### Phase B+ — “Professional Delivery” (what studios expect)
- **B3. Stem/master bit-depth policy**
  - Add explicit export targets:
    - stems: 44.1kHz / 24-bit WAV
    - master: 44.1kHz / 16-bit WAV (document limiter + dither behavior)
  - Grounding: current writes call `sf.write(...)` without explicit subtype in places like `multimodal-ai-music-gen/multimodal_gen/audio_renderer.py:1218`, while other parts explicitly use `subtype='PCM_16'` (`multimodal-ai-music-gen/multimodal_gen/assets_gen.py:2440`).

- **B4. MPC hardware-safe “package export”**
  - Research/validate MPC 3.x expectations vs MPC Software 2.x, then implement a single “package” output structure (samples/programs/sequences) that avoids broken paths on transfer.
  - Grounding: an MPC exporter exists (`multimodal-ai-music-gen/multimodal_gen/mpc_exporter.py`), but MPC 3.x packaging specifics are not verified by this repo’s code/doc set.

### Phase C — “Pro Audio Mixing & Sound”
Goal: match baseline expectations: good stem mixing, routing, and extensibility.

- **C1. Clarify “real-time mixer” vs “offline render parity”**
  - The repo already has a real-time `MixerGraph` and a Python-side `/fx_chain` for render parity; ensure they converge on the same chain semantics and naming.
  - Touchpoints: `juce/Source/Audio/MixerGraph.*`, `juce/Source/UI/FXChainPanel.*`, `multimodal_gen/server/osc_server.py`.

- **C2. Mixer UI & Metering (Preview vs Pro)**
  - **Decision:** If targeting "Pro Producer", implement full Channel Strips (Phase 8 in `TODO.md`). If targeting "Loop Hunter", implement simple Volume/Pan knobs.
  - **Implementation (Pro):**
    - VU Metering (300ms ballistics).
    - Channel Strips (Fader, Pan, Mute, Solo).
    - Real-time level monitoring.
  - Touchpoints: `juce/Source/UI/Mixer/*` (New components).

- **C3. Stem playback as first-class**
  - Ensure stems are generated with stable naming and a manifest; JUCE loads stems into the mixer for playback/editing (not just synthesized MIDI).
  - Acceptance: user can rebalance stems without re-rendering in Python.

- **C4. Physics-aware humanization (“drummer physics”, not random jitter)**
  - Add a dedicated layer (e.g., `multimodal_gen/humanize_physics.py`) applied by role and tempo:
    - fatigue constraints (velocity caps at high BPM / dense subdivisions)
    - limb-conflict constraints (simultaneous hat/snare behavior)
    - policy-driven ghost notes/fills
  - Relationship to existing work: complements groove templates in `multimodal-ai-music-gen/multimodal_gen/groove_templates.py`.

### Phase E — “DAW Integration” (Conditional on Architecture Validation)
Goal: The "Holy Grail" of AI tools — running directly inside the DAW.

- **E1. VST3/AU Plugin Wrapper**
  - **Prerequisite:** Successful validation of "Python Sidecar" architecture (see Strategic Risks).
  - Implement `PluginProcessor` wrapping `AudioEngine` and `OSCBridge`.
  - Implement Host Transport Sync (BPM, Play/Stop, Position).
  - Implement State persistence (saving generator state in DAW project).
  - Touchpoints: `juce/Source/Plugin/*` (New directory).

- **E2. Drag-and-Drop Export (Fallback Strategy)**
  - If VST3 is too fragile, implement robust Drag-and-Drop from the Standalone App to the DAW.
  - Drag MIDI clips or Audio Stems directly from the UI.

### Phase D — “Shipping & Trust” (Distribution)
Goal: install/run on fresh machines reliably.

- **D1. Bundle Python backend**
  - Decide: embedded backend vs external server UX; define stable resource paths (models, templates, expansions, soundfonts).
  - Acceptance: end-user doesn’t install Python manually.

- **D2. Installer**
  - Windows-first (Inno Setup or WiX), then macOS bundle + notarization.
  - Acceptance: one-click install, creates shortcuts, handles updates cleanly.

## Questions (Answering These Changes the Roadmap)

1) **Product form factor:** should this ship primarily as a standalone app, a plugin (VST3), or both?
2) **Offline vs cloud:** is “offline-first” still non-negotiable for *all* features (including reference analysis), or can some workflows be optional-online?
3) **Target users:** beatmakers wanting fast loops, or producers expecting DAW-like editing depth? (This affects how far “ArrangementView clip editing” needs to go.)
4) **Model strategy:** are you committing to local models (and which licenses), or is procedural + MIDI-first still the baseline with optional ML enhancements?
5) **Interchange priority:** is MPC `.xpj` still the flagship export, or should Ableton/Logic workflows be prioritized next?
6) **Plugin strategy:** should VST hosting be JUCE-only (realtime), Python-only (offline render via `pedalboard`), or “JUCE realtime + Python render parity” (highest complexity)?
7) **Asset intelligence depth:** is “intent-based retrieval” OK as numeric-feature similarity first, or do you want text embeddings/vector DB in v1?
8) **Delivery defaults:** should stems default to 24-bit (studio) and master to 16-bit (consumer), or keep everything 16-bit for simplicity?

---

If you answer the questions above, I can rewrite this roadmap into a sharper “next 30/60/90 days” plan with acceptance criteria per milestone, while keeping it grounded in the current repo reality.
