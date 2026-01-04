# Remaining Implementation Tasks (Grounded)

> **Target audience**: Opus / Senior Developer  
> **Scope**: Tasks required to take the current codebase from “works on dev machine” to “reliable, shippable app”.  
> **Status**: Living document; updated against current code.

This repo includes several older task docs (e.g. `MASTER_PLAN.md`, `TODOtasks.md`, large `TODO.md`) that still list already-finished work. This file is the *source of truth* for what remains.

---

## 0) What’s Already Implemented (Verified in Code)
These were previously tracked as “remaining”, but are already present today:

- [x] `request_id` correlation end-to-end  
  - Python: `multimodal_gen/server/worker.py` (`GenerationRequest.request_id`, `GenerationResult.request_id`)  
  - Python: `multimodal_gen/server/osc_server.py` (`/generate` parsing; `generation_started` status echoes `request_id`)  
  - JUCE: `juce/Source/Communication/Messages.h` (`GenerationRequest.requestId`, JSON serialization)  
  - JUCE: `juce/Source/Communication/OSCBridge.cpp` (tracks `currentRequestId`; ignores mismatched `/progress`)

- [x] Connection state machine + ping/timeout/reconnect logic  
  - JUCE: `juce/Source/Communication/OSCBridge.h` (`ConnectionState`, timeout constants)  
  - JUCE: `juce/Source/Communication/OSCBridge.cpp` (`timerCallback()` heartbeat + reconnect backoff + activity timeouts)

- [x] Graceful shutdown messaging  
  - Python: `multimodal_gen/server/osc_server.py` (`/shutdown` handler + ack status)  
  - JUCE: `juce/Source/Communication/OSCBridge.cpp` (`sendShutdown()` sends `request_id`)

- [x] `/analyze` endpoint + JUCE client support (but "apply results" UX still pending)  
  - Python: `multimodal_gen/server/osc_server.py` (`/analyze` -> `/analyze_result`)  
  - JUCE: `juce/Source/Communication/Messages.h` (`AnalyzeRequest`, `AnalyzeResult`)  
  - JUCE: `juce/Source/Communication/OSCBridge.cpp` (send/receive analyze)

- [x] Project state / undo / MIDI editor foundation  
  - JUCE: `juce/Source/Project/ProjectState.cpp` (ValueTree + UndoManager + MIDI import/export)

- [x] Professional Multi-Track UI (DAW-style arrangement view)
  - JUCE: `juce/Source/UI/TrackList/TrackHeaderComponent.*` (track headers with MIDI/Audio type, mute/solo/arm)
  - JUCE: `juce/Source/UI/TrackList/ArrangementView.*` (split view: track list + lane content with per-track piano rolls)
  - JUCE: `juce/Source/UI/TrackList/TrackListComponent.*` (vertical track headers with "+" button for dynamic creation)
  - JUCE: `juce/Source/UI/VisualizationPanel.cpp` (added "Arrange" tab hosting ArrangementView)

- [x] Arrangement View Enhancements
  - JUCE: `PianoRollComponent::setEmbeddedMode()` - hides track selector dropdown when embedded in ArrangementView (redundant in multi-track context)
  - JUCE: `ArrangementView::setFocusedTrack()` - full-screen single track view within arrangement
  - JUCE: Right-click context menu in ArrangementView for "Focus Track", "Exit Focus View", "Expand Track", "Reset Zoom"
  - Focus mode indicator in timeline ruler showing "FOCUSED: Track N (Right-click to exit)"

- [x] Loop Region Sync (Timeline <-> AudioEngine <-> PianoRoll)
  - JUCE: `juce/Source/Audio/AudioEngine.*` (added `setLoopRegion()`, `getLoopRegionStart/End()`, `hasLoopRegion()`, atomic loop boundaries)
  - JUCE: `juce/Source/UI/TimelineComponent.cpp` (syncs loop region to AudioEngine on change)
  - JUCE: `juce/Source/UI/Visualization/PianoRollComponent.*` (loop region overlay visualization, note release tails with gradient)
  - JUCE: `juce/Source/MainComponent.*` (implements TimelineComponent::Listener for loop region propagation)

- [x] Instrument Integration in Generation
  - JUCE: `juce/Source/MainComponent.cpp` (`generateRequested()` collects instrumentPaths from ProjectState tracks)

- [x] Expansion Scanning (recursive directory traversal)
  - Python: `multimodal_gen/expansion_manager.py` (fixed recursive scanning for nested expansion packages like Funk o Rama)

- [x] Protocol Tests (Python)
  - Python: `tests/test_protocol.py` (request_id correlation, schema version, OSC addresses, error codes, take messages)

- [x] StylePolicy ("Producer Brain") Layer
  - Python: `multimodal_gen/style_policy.py` - unified policy layer for coherent musical decisions
  - PolicyContext with TimingPolicy, VoicingPolicy, DynamicsPolicy, ArrangementPolicy, MixPolicy, InstrumentPolicy
  - Genre-specific presets for timing/swing, voicing style, ghost note probability, mix parameters
  - Integration: compile_policy() called in main.py, passed to MidiGenerator.generate()
  - Physics humanization respects policy context for swing, ghost notes, timing jitter
  - JSON-able decision records for UI transparency

- [x] Physics-Aware Humanization
  - Python: `multimodal_gen/humanize_physics.py` - realistic MIDI humanization
  - Models: fatigue at high BPM, limb conflicts, ghost notes, hand alternation
  - Integration: MidiGenerator._apply_physics_humanization() uses PolicyContext

---

## 1) Priority 0: Protocol Correctness & Contract Alignment
**Goal**: Make the OSC contract internally consistent (schemas, correlation, and state transitions), so UI never applies stale/mismatched results and never gets “stuck”.

### 1.1 Correlation invariants (finish the last 10%)
- [x] ~~Ensure every server->client message includes `request_id` where applicable~~ (cancel status already includes request_id in `osc_server.py`)
- [x] ~~Harden JUCE handling of `/complete` so mismatched `request_id` is ignored~~ (implemented in `OSCBridge.cpp::handleComplete()`)
- [x] Define and document the "generation lifecycle" states and enforce them on both sides:
  - started/acknowledged/progress/complete/error/cancelled (documented in PROTOCOL.md)

### 1.2 Schema versioning behavior (not just logging)
- [x] Decide behavior for `schema_version != SCHEMA_VERSION`: **Newer client → Older server = REJECT (error 103); Older client → Newer server = WARN + ACCEPT** (documented in PROTOCOL.md)
- [x] ~~Surface schema mismatch in JUCE UI (toast/status)~~ (implemented in `MainComponent::onSchemaVersionWarning()` with AlertWindow)

### 1.3 Canonical protocol reference update (this doc)
- [x] Remove legacy references to `/analyze_complete`; clarified in PROTOCOL.md that it's a progress stage name, not an OSC address
- [x] Document supported addresses from code (`multimodal_gen/server/config.py`, `juce/Source/Communication/Messages.h`) - PROTOCOL.md is comprehensive

**Acceptance criteria**
- [x] Killing the Python server mid-generation always transitions UI out of "Generating…" within timeout (handled by ACTIVITY_TIMEOUT_MS in OSCBridge).
- [x] No "zombie" `/progress` or `/complete` can update the wrong run (request_id correlation enforced in handleComplete/handleProgress).
- [x] Cancel produces deterministic UI state (fire-and-forget cancel with timeout fallback to IDLE).

---

## 1.5 Priority 0: Responsive JUCE UI (All Display Sizes)
**Goal**: Ensure the JUCE app layout adapts cleanly from small windows/laptops to large/4K displays (no clipped controls, no overlapping panels, no “hardcoded” layouts that break on resize).

### 1.5.1 Layout audit + refactor targets (responsive by design)
- [x] Replace "manual pixel layouts" with `FlexBox`/`Grid` in high-impact UI surfaces (all already implemented):
  - `juce/Source/MainComponent.cpp` (overall page layout + split panes)
  - `juce/Source/UI/PromptPanel.cpp` (input areas + buttons)
  - `juce/Source/UI/InstrumentBrowserPanel.cpp` (search row, tabs, list, preview)
  - `juce/Source/UI/ExpansionBrowserPanel.cpp` (cards/grid/list responsiveness)
  - `juce/Source/UI/FXChainPanel.cpp` (strip layout + parameter panel)
  - `juce/Source/UI/TransportComponent.cpp` (transport controls; keep clear at narrow widths)
  - `juce/Source/UI/VisualizationPanel.cpp` (visualization modes + resizing behavior)

### 1.5.2 Minimum size + scalable metrics
- [x] Define a minimum window size and enforce it: `setResizeLimits(Layout::minWindowWidth, Layout::minWindowHeight, 4096, 4096)` in Main.cpp
- [x] Replace "magic numbers" with LayoutConstants.h:
  - scaled paddings/margins (paddingXS through paddingXXL)
  - typography scale (fontSizeXS through fontSizeHeader)
  - safe areas for touch targets (buttonHeightTouch = 44px)
  - adaptive helpers: `getAdaptivePadding()`, `getAdaptiveSidebarWidth()`, `getAdaptiveBottomPanelHeight()`

### 1.5.3 Acceptance criteria (responsive)
- [x] App remains usable at small widths (minWindowWidth = 1024) and scales cleanly to 4K via breakpoints.
- [x] No critical controls disappear - FlexBox with calculated widths, viewport-based scrolling for lists.
- [x] All scrollable lists (instruments/expansions/recent files) use viewport components for proper scrolling.

---

## 2) Priority 1: Analyze -> Apply Workflow (User-Facing) ✅ COMPLETE
**Goal**: Make analysis actionable: analyze a reference, then apply results to the current session (BPM/key/prompt hints) rather than only showing an alert.

### 2.1 Apply analysis results to UI + session state
- [x] In `MainComponent::onAnalyzeResultReceived` (`juce/Source/MainComponent.cpp`), "Apply" actions implemented:
  - [x] Apply BPM to `appState.setBPM()` when `bpmConfidence` exceeds 0.5
  - [x] Apply key/mode to `appState.setKey()` when keyConfidence exceeds 0.5
  - [x] Apply prompt hints via `promptPanel->appendToPrompt()`
- [x] Persist the last analysis result in `ProjectState` ValueTree (LastAnalysis node with all fields)

### 2.2 Promote “Analyze” entry points
- [x] Add explicit UI affordances (PromptPanel has analyzeButton + drag/drop):
  - local file analyze (`OSCBridge::sendAnalyzeFile`)
  - URL analyze (`OSCBridge::sendAnalyzeUrl`)
- [ ] Keep the recent-files context menu entry (already triggers analyze) but treat it as secondary UX.

### 2.3 Clarify which analysis engine backs `/analyze`
- [ ] Decide and document whether `/analyze` should use:
  - `multimodal_gen/reference_analyzer.py` (current server implementation; supports URL; optional deps)
  - `multimodal_gen/file_analysis.py` (offline-first; supports MIDI/audio; currently unused by `/analyze`)
- [ ] If both remain: define routing rules (URL -> reference analyzer, local path -> fast file analysis) and normalize output schema.

**Acceptance criteria**
- [x] A user can Analyze -> Apply -> Generate without copying values manually (AlertWindow offers Apply button).  
- [ ] Missing optional deps (`librosa`, `yt-dlp`) produce clear, non-blocking remediation messages.

---

## 2.5 NotebookLM Roadmap Integration (Grounded Against Repo)
This maps the NotebookLM phases into *what is already present in code* and *what remains to implement*.

### Phase 1 (NotebookLM): Intelligent Instrument & Browser System
**Already present (partial)**
- [x] Backend instrument scanning + structured JSON: `multimodal_gen/server/worker.py` (`InstrumentScanWorker`) and server route `/instruments` -> `/instruments_loaded` in `multimodal_gen/server/osc_server.py`
- [x] JUCE instrument browser + categories + preview: `juce/Source/UI/InstrumentBrowserPanel.*`
- [x] Expansion system (backend + OSC): `multimodal_gen/expansion_manager.py`, expansion OSC handlers in `multimodal_gen/server/osc_server.py`

**Remaining gaps**
- [ ] Treat “instrument manifest” as a stable contract (schema version + required fields), and persist/cache it client-side:
  - Python: formalize the `/instruments_loaded` schema and include version + per-item feature fields (BPM/key/tags are already included; extend as needed).
  - JUCE: persist the manifest and last scan summary in `ProjectState` (or app cache) so UI loads instantly.
- [ ] Waveform previews in the browser:
  - Current state: the browser has a `SamplePreviewPanel` and uses local file paths; there is no “stream waveform via OSC” pipeline.
  - Decide: compute waveform peaks in JUCE from the audio file (fast + local), or add an OSC endpoint returning precomputed peaks.
- [ ] Make “AI uses expansions intelligently” a real feature (not implied):
  - Add a resolver step in the generation pipeline that ranks instruments by prompt tags (“vintage”, “analog”, “dusty”) and expansion availability.
  - Grounding hooks:
    - Python: `multimodal_gen/instrument_index.py` has a TODO for spectral matching; expansion resolve already exists via manager.
    - Python: `multimodal_gen/prompt_parser.py` already extracts intent; extend it to emit style adjectives into a structured field.

### Phase 2 (NotebookLM): Arrangement, Takes, Comping, Section Regeneration
**Already present (partial)**
- [x] Timeline visualization: `juce/Source/UI/TimelineComponent.*` (sections + beat/bar markers + click-to-seek)
- [x] Piano roll editing + ValueTree persistence foundation: `juce/Source/Project/ProjectState.*`, `TODO_PHASE5.md`
- [x] Take generation system exists in backend: `multimodal_gen/take_generator.py`, take lanes in `multimodal_gen/session_graph.py`
- [x] Multi-track arrangement view with track headers: `juce/Source/UI/TrackList/ArrangementView.*`
- [x] Dynamic track spawning with per-track piano rolls: `juce/Source/UI/TrackList/TrackListComponent.*`
- [x] Loop region sync across Timeline, AudioEngine, PianoRoll: `juce/Source/Audio/AudioEngine.*`, `juce/Source/UI/TimelineComponent.cpp`
- [x] Note release tail visualization (decay): `juce/Source/UI/Visualization/PianoRollComponent.cpp`

**Remaining gaps**
- [x] Surface "takes" in the OSC protocol and UI:
  - ✅ Python: extended generation results with rich take metadata (take_id, variation_type, seed, etc.)
  - ✅ JUCE: GenerationResult.takesJson parsed in Messages.h, TakeLanePanel populated in onGenerationComplete
- [x] Sectional regeneration:
  - ✅ `/regenerate` OSC endpoint in `multimodal_gen/server/osc_server.py`
  - ✅ JUCE: ArrangementView context menu for "Regenerate Track" / "Regenerate All"
  - ✅ JUCE: MainComponent::regenerateRequested() sends RegenerationRequest via OSCBridge
- [ ] Upgrade timeline from “display + seek” to “arrangement”:
  - Add region clips (MIDI + audio) and editing (move/trim/duplicate), then reflect changes into `ProjectState`.

### Phase 3 (NotebookLM): Industry-Standard Signal Processing (“Analog Feel”)
**Already present (partial)**
- [x] Offline mix chain architecture: `multimodal_gen/mix_chain.py`
- [x] Soft clipping exists in render path (per docs) and JUCE has real-time graph infrastructure (`juce/Source/Audio/MixerGraph.*`)

**Remaining gaps**
- [ ] Define a canonical channel strip order and apply it consistently (pre-filter -> EQ -> dynamics -> saturation -> post gain):
  - Implement in Python render chain (stems + master) and/or JUCE real-time chain (MixerGraph).
- [ ] Add “aural exciter” style harmonic enhancement as an explicit processor (per-track and/or master).
- [ ] Automated sidechain routing (kick keys bass compressor):
  - Python: add a sidechain-capable compressor model in `mix_chain.py` (and wire routing at render time).
  - JUCE: add sidechain bus routing in `MixerGraph` if real-time parity is desired.
- [ ] Warping / time-stretch for loops at variable BPM:
  - Start with offline time-stretch for imported loops (optional deps), then consider real-time stretch if needed.

### Phase 4 (NotebookLM): Bidirectional Control & Plugin Hosting
**Already present (partial)**
- [x] FX UI exists: `juce/Source/UI/FXChainPanel.*` (but integration is incomplete)

**Remaining gaps**
- [ ] Standardize OSC parameter streaming endpoints:
  - `/param/bpm`, `/param/key`, `/param/transpose`, `/param/loop_region`, etc.
  - JUCE: send updates on slider changes.
  - Python/JUCE: define what can be updated live (MIDI transpose is easy; audio warping is harder and may be offline-first).
- [ ] Plugin scanning/hosting:
  - JUCE-side scanning for VST3 (and optionally AU on macOS) and a safe UX for enabling plugins.
  - If AI is to “choose plugins”, define a strict allowlist/metadata model (avoid arbitrary plugin execution without user consent).
- [ ] Tempo follower:
  - Define first iteration scope: tap-tempo + external MIDI clock vs “audio tempo follower”.

---

## 3) Priority 1: FX Chain Integration (UI <-> Engine <-> Render) ✅ CORE COMPLETE
**Goal**: FX chain controls affect sound in a deterministic way (real-time monitoring and/or offline render).

### 3.1 Decide routing: real-time only vs “render matches monitoring”
- [x] ~~Real-time only path~~ FXChainPanel drives JUCE `MixerGraph` processors:
  - Created EQProcessor, CompressorProcessor, ReverbProcessor, DelayProcessor, SaturationProcessor, LimiterProcessor in `juce/Source/Audio/Processors/`
  - Added `setFXChainForBus()`, `clearFXForBus()`, `setFXParameter()`, `setFXEnabled()` to MixerGraph
  - `MainComponent::fxChainChanged()` now applies FX chain to MixerGraph in real-time
- [x] ~~Render parity path~~ FX chain sent to Python via `/fx_chain` OSC endpoint (already implemented)

### 3.2 FXChainPanel usability gaps
- [x] Implement drag reordering of FX units - Uses JUCE DragAndDropContainer/Target pattern
  - FXUnitComponent supports drag image creation and drop targeting
  - FXChainStrip inherits from DragAndDropContainer and DragAndDropTarget
  - Drag between positions within same strip or move across strips
  - Visual feedback with cyan indicator showing drop position
- [ ] Add "Reset/Copy/Paste chain" (high-value UX and helps reproducibility).
- [x] Persist FX chain in `ProjectState` for save/reload:
  - Added `FX_CHAINS`, `FX_BUS`, `FX_UNIT` identifiers to ProjectState
  - `setFXChainForBus()`/`getFXChainForBus()`/`getAllFXChainsJSON()` methods
  - FXChainPanel auto-saves on chain change, loads on init via `setProjectState()`

**Acceptance criteria**
- [x] ~~Changing FX audibly changes playback in the intended scope (track/bus/master)~~ (MixerGraph now processes FX chain)
- [ ] Save/reload preserves FX chain exactly.

---

## 4) Priority 1: Expansion Management Finish ✅ COMPLETE
**Goal**: Complete the expansion UX loop: list expansions, enable/disable, import, scan, resolve instruments.

- [x] Wire enable/disable toggle in `juce/Source/UI/ExpansionBrowserPanel.cpp` to `OSCBridge::sendExpansionEnable(...)`
  - ExpansionCard toggle calls `expansionEnableToggled()` -> `requestExpansionEnableOSC()` -> `oscBridge->sendExpansionEnable()`
  - Server handles `/expansion/enable` in `osc_server.py` -> `expansion_manager.enable_expansion()`
  - UI refreshes expansion list after toggle
- [x] Define "disabled" semantics:
  - **Excluded from resolve**: `_rebuild_matcher()` only includes enabled expansions
  - **Excluded from browser instruments**: `_build_index()` skips disabled expansions
  - **Visual indicator**: ExpansionCard shows red "(Disabled)" text when disabled
  - **Still visible in browser**: Disabled expansions remain in list but greyed/marked
- [x] Persist expansion enable state across restarts:
  - `expansion_manager._save_expansion_state()` writes to `expansion_state.json`
  - `expansion_manager._load_expansion_state()` restores on startup

**Acceptance criteria**
- [x] Toggling an expansion immediately affects instrument resolution

---

## 5) Priority 2: Transport + Timeline Truth ✅ COMPLETE
**Goal**: Time displays and loop behavior reflect actual audio/MIDI, not derived guesses.

- [x] Use actual media duration on generation complete:
  - `TransportComponent::onGenerationComplete()` calls `audioEngine.getTotalDuration()` when MIDI is loaded
  - `AudioEngine::getTotalDuration()` returns `midiPlayer.getTotalDuration()` which is calculated from loaded MIDI
  - Falls back to BPM-based calculation only when no MIDI is loaded
- [x] Loop region selection implemented:
  - AudioEngine has `setLoopRegion()`, `getLoopRegionStart/End()`, `hasLoopRegion()` with atomic loop boundaries
  - TimelineComponent syncs loop region to AudioEngine
  - PianoRollComponent visualizes loop region

---

## 6) Priority 2: Testing & CI (Ship Confidence)
**Goal**: Make regressions detectable and builds repeatable.

- [x] Add protocol tests (Python): `tests/test_protocol.py` (generate/analyze payload parsing, error responses, request_id propagation, take messages).
- [x] Add CI: `.github/workflows/build.yml` created with:
  - Python: install deps, run `python -m pytest -q` on matrix (3.9, 3.10, 3.11)
  - C++: CMake configure/build for Windows and macOS

---

## 7) Priority 3: Distribution Packaging
**Goal**: End-users can install/run without Python setup friction.

- [ ] Bundle Python backend (PyInstaller) and define runtime asset/instrument path strategy.
- [ ] Windows installer (Inno Setup): bundle JUCE app + backend + default libraries.
- [ ] Decide UX: embedded backend vs external server, and update UI messaging accordingly (currently instructs users to run `python main.py --server --verbose` in `juce/Source/MainComponent.cpp`).

---

## 8) NotebookLM Task Intake (Pending)
You mentioned “the following task from NotebookLM”, but it wasn’t included in the prompt. Add it here and we’ll merge it into the priority tree above:

- [ ] Paste NotebookLM task summary and acceptance criteria.

---

## Technical Reference (As Implemented)
**Authoritative sources**:
- Python: `multimodal_gen/server/config.py`
- JUCE: `juce/Source/Communication/Messages.h`

### OSC addresses (high level)
- Client -> Server: `/generate`, `/cancel`, `/analyze`, `/instruments`, `/ping`, `/shutdown`, `/expansion/*`
- Server -> Client: `/progress`, `/complete`, `/analyze_result`, `/error`, `/pong`, `/status`, `/instruments_loaded`, `/expansion/*_response`
