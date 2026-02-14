# TODO2.md — Advanced Roadmap (Post-Phases 0–7)

This file is an upgraded roadmap grounded in the current repo state (Python generator + OSC server + JUCE UI/audio/visualization are already implemented) and explicitly targets the **next missing product-grade layers**: analysis, project workflow, mixer/stems, robustness, testing, and distribution.

## Current Reality (Verified)

**Implemented and working (core):**
- Python generation pipeline + CLI + refinement workflow + metadata/BWF + stems/MPC export capabilities.
- Python OSC server with `/generate`, `/cancel`, `/instruments`, `/ping`, `/shutdown` plus background workers.
- JUCE app foundation: audio engine, MIDI synth playback, transport, timeline, prompt panel, progress overlay, recent files, piano-roll, waveform + spectrum visualizers, OSC client bridge, Python process manager.

**Known gaps present in code:**
- Python OSC `/analyze` endpoint is stubbed (“not yet implemented”).
- JUCE “Mixer / Instrument Browser” area is still placeholder.
- Transport duration uses a TODO heuristic instead of reading actual audio duration.
- Robustness items are deferred: queueing, reconnect/backoff, timeouts, request correlation.
- Automated tests exist for many Python primitives, but **not** for Python OSC server routes/worker cancellation semantics, and not for JUCE OSC bridge parsing/state.

## Design Principles (for professional-grade UX + realtime audio safety)

These principles are explicitly aligned with JUCE’s threading model:
- **Audio thread is sacred:** never block; never allocate; always fill output buffers (silence must be zeros); tolerate variable buffer sizes.
- **UI is asynchronous:** repaint is coalesced and happens later on the message thread; don’t do heavy work in `paint()` or `resized()`.
- **Cross-thread UI updates:** use message-thread scheduling (`MessageManager::callAsync`) rather than locks that risk deadlocks.
- **Timers are UI-thread tools:** timers run on the message thread; they are not precise, and heavy UI work will delay them.

## Roadmap Structure

- Milestones are ordered by dependency and user-visible value.
- Each milestone has acceptance criteria and a recommended “definition of done”.

---

# Milestone 1 — Protocol Hardening + Request Lifecycle

## Goals
Turn OSC from “best effort messages” into a predictable request/response protocol that supports UI retries, cancel, and robust error reporting.

## Work
1. **Add `request_id` to every request/response**
   - `/generate`, `/cancel`, `/instruments`, `/ping`, `/shutdown`, `/progress`, `/complete`, `/error`, `/status`.
   - Add `schema_version` field to all JSON payloads.

2. **Add formal message schemas (single source of truth)**
   - Python: define dataclasses/typed dicts for inbound/outbound payloads.
   - JUCE: define structs/classes mirroring the same schema.
   - Include: prompt, bpm/key/scale, duration bars, render flags (audio/stems/mpc), output paths, and error codes.

3. **Timeout + retry strategy (JUCE-side)**
   - If no `/pong` within N seconds, set status to disconnected.
   - If request sent while disconnected, queue *bounded* requests (e.g., max 1 generate + 1 instruments request).
   - Reconnect backoff (e.g., 250ms → 500ms → 1s → 2s → 5s max).

4. **Graceful shutdown strategy**
   - Prefer sending `/shutdown` (with `request_id`) before killing the Python process.
   - Add explicit “server shutting down” status from Python.

## Acceptance Criteria
- UI can show: “connected / disconnected / generating / canceling / error” reliably.
- Every completion/error/progress event maps to a known request.
- Cancels are deterministic: cancel stops work within a bounded latency.

---

# Milestone 2 — Implement `/analyze` (Reference + Local File Analysis)

## Goals
Make analysis a first-class flow for “import → analyze → generate/refine”, matching what the planning docs describe.

## Work
1. **Define analysis targets**
   - Input: audio file (`.wav/.mp3`) and/or MIDI file (`.mid`).
   - Output: estimated BPM, key, time signature (optional), section markers (optional), instrumentation hints (optional), loudness/peak (optional), and a generated “prompt suggestion”.

2. **Python implementation**
   - Add `analyze_file(path, options)` with:
     - Fast path: metadata + basic DSP (RMS/peak, spectral centroid, onset strength).
     - Optional heavier analysis behind feature flags (only if dependency present).
   - Add caching: key by file path + mtime + config.

3. **OSC route**
   - Implement `/analyze` with `request_id` and stream progress updates.

4. **JUCE UI**
   - Add “Import & Analyze” UX (file picker → progress overlay → populate BPM/key/genre prompt hints).

## Acceptance Criteria
- A user can drop a file, see analysis results, and generate a compatible track.
- Analysis never blocks audio thread; file IO is backgrounded.

---

# Milestone 3 — Real Mixer + Stem Playback (Phase 8++ done for real)

## Goals
Implement the missing “Track Mixer” with real multi-stem audio playback and export.

## Work
1. **Python: ensure stem export is stable and discoverable**
   - Standardize stem naming: `drums.wav`, `bass.wav`, `melody.wav`, `pads.wav`, `fx.wav` (plus a `stems.json` manifest).
   - Add an option to always produce a manifest describing stems and levels.

2. **JUCE: introduce a multitrack audio playback graph**
   - Load stems as audio sources and route them through:
     - Per-track fader, pan, mute/solo
     - Peak/RMS meter
     - Optional per-track FX slots (later milestone)
   - Keep DSP realtime-safe.

3. **Mixer UI**
   - Replace placeholder panel with:
     - Track list + channel strips
     - Mute/Solo buttons
     - Level meters (decimated updates; do not redraw excessively)
     - Track naming mapped from manifest

4. **Export**
   - Export mixeddown WAV from JUCE OR reuse Python export, but ensure it matches mixer gains.
   - Optional: export per-track stems with adjusted mixer settings.

## Acceptance Criteria
- A generated project loads with stems and the mixer can rebalance them.
- Playback is stable (no glitches) under typical buffer sizes.

---

# Milestone 4 — Project System v2 (Save/Load/History/Assets)

## Goals
Turn the app into a “real DAW-lite project” workflow.

## Work
1. **Define a project bundle format**
   - Option A: folder-based project with a single JSON manifest.
   - Option B: `.mmg` (zip) containing:
     - `project.json` (prompt history, params, render outputs, stems manifest)
     - `midi/`, `audio/`, `stems/`, `exports/`

2. **Prompt & render history**
   - Store every generation/refine iteration as an immutable record.
   - UI: “History” list with A/B compare (audio or MIDI).

3. **Recent files and auto-restore**
   - On crash/restart: restore last opened project if user opts in.

## Acceptance Criteria
- Save/Load is reliable across machines (relative paths inside project).
- Projects are portable and self-contained.

---

# Milestone 5 — UI/UX Professionalization (Polish + Accessibility)

## Goals
Make the JUCE app feel “finished”: predictable, discoverable, fast.

## Work
1. **LookAndFeel theming + typography**
   - Centralize colors and fonts; apply via JUCE LookAndFeel + per-component colour IDs.
   - Ensure high contrast text and consistent spacing.

2. **Keyboard shortcuts + command routing**
   - Space: play/pause
   - Ctrl/Cmd+O: open
   - Ctrl/Cmd+S: save
   - Esc: cancel generation

3. **Error UX**
   - Replace DBG-only failures with user-visible dialogs/toasts.
   - Provide “copy diagnostic bundle” (logs + settings + last request).

4. **Performance improvements**
   - Use buffered rendering for static UI where appropriate.
   - Decimate visualization repaint rate and avoid full-window repaints.

## Acceptance Criteria
- App feels responsive while generating.
- Clear error messages for disconnected server, missing dependencies, invalid prompts.

---

# Milestone 6 — Test & CI Hardening

## Goals
Protect the integration surface (OSC + worker cancellation + file formats).

## Work
1. **Python tests**
   - Unit tests for OSC handlers: `/generate`, `/cancel`, `/instruments`, `/ping`, `/shutdown`, `/analyze`.
   - Worker tests: cancellation latency and progress event ordering.

2. **JUCE tests**
   - Add lightweight tests for OSC message parsing and state transitions.
   - Add regression checks for serialization of project state.

3. **CI**
   - Python: run `test_suite.py` plus new server tests.
   - JUCE: at least build check (Windows) + basic unit tests.

## Acceptance Criteria
- “Change breaks OSC protocol” is caught automatically.

---

# Milestone 7 — Distribution (Windows-first, then cross-platform)

## Goals
Make it installable and runnable by non-developers.

## Work
1. **Python distribution strategy**
   - Option A: embed a Python runtime + wheels; run in-process.
   - Option B: bundle a venv in installer.

2. **Content distribution**
   - Optional instrument packs download manager, with integrity checks.

3. **Installer + updates**
   - Windows installer, desktop shortcut, file associations for `.mmg`.

## Acceptance Criteria
- A fresh machine can install and generate audio without manual setup.

---

# Stretch Milestones (If you want “pro DAW” features)

- **Plugin targets:** VST3/AU wrapper that hosts the generation engine and exposes parameters.
- **Realtime MIDI input:** record into project, quantize/humanize, resynthesize stems.
- **FX chains:** per-track + master bus, preset system.
- **Collaboration:** share project bundles; deterministic seed-based regeneration.
