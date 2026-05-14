# 1990s Rock Quality Degradation and UI Upgrade Plan — 2026-05-14

## Purpose

Document a source-grounded investigation plan for the 1990s rock quality regression and the related JUCE UI polish upgrade. This plan is intentionally documentation/state only: it records what the smoke run proved, what must be preserved, and the smallest future PR sequence to make a prompt for a 1990s rock band route through rock-aware parsing, arrangement, strategy, rendering, analysis, and UI affordances before judging musicality.

## Scope and guardrails

- **Current task scope:** documentation/state updates only; no production code or tests are changed here.
- **Primary quality goal:** the prompt below should produce a rock/band arrangement with guitars, bass guitar, live drums, verse/chorus/bridge structure, 100 BPM, E minor, and a rendered audio artifact.
- **Primary safety goal:** do not regress existing high-priority genres and workflows while adding rock coverage. The fix must connect all genre layers instead of making one isolated parser or renderer tweak.

## Smoke command summary and artifacts

### Prompt under investigation

```text
1990's era rock song with crunchy electric guitar, live drums, bass guitar, verse chorus bridge, energetic band performance, 100 BPM in E minor
```

### Failed runner attempt

- Artifact directory: `output/_diagnostics/rock_1990s_20260514_044251`
- Outcome: failed before generation; `generation.stdout.log` is empty.
- Error evidence: `generation.stderr.log` contains argparse exit text ending with:

  ```text
  main.py: error: unrecognized arguments: era rock song with crunchy electric guitar, live drums, bass guitar, verse chorus bridge, energetic band performance, 100 BPM in E minor
  ```

- Diagnosis: the PowerShell `Start-Process` call split the prompt instead of passing it as one positional argument, so argparse interpreted prompt words after `1990's` as unrecognized arguments and exited with code 2.

### Real smoke

- Artifact directory: `output/_diagnostics/rock_1990s_20260514_044327`
- Runner/process result: PID `31368` was polled to completion; process exit code was `0`.
- Key artifacts:
  - `output/_diagnostics/rock_1990s_20260514_044327/generation.stdout.log`
  - `output/_diagnostics/rock_1990s_20260514_044327/generation.stderr.log`
  - `output/_diagnostics/rock_1990s_20260514_044327/project_metadata.json`
  - `output/_diagnostics/rock_1990s_20260514_044327/session_manifest.json`
  - `output/_diagnostics/rock_1990s_20260514_044327/trap_soul_100bpm_Eminor_20260514_044333.mid`
  - `output/_diagnostics/rock_1990s_20260514_044327/trap_soul_100bpm_Eminor_20260514_044333_render_report.json`
  - `output/_diagnostics/rock_1990s_20260514_044327/trap_soul_100bpm_Eminor_20260514_044333_render_error.txt`
- Smoke classification:
  - **PASS for diagnostic evidence:** artifacts captured parser output, arrangement inflation, MIDI, session metadata, selected instruments, render report, and render error.
  - **FAIL for genre correctness:** prompt routed to `trap_soul`, not rock.
  - **FAIL for audio correctness:** audio output remained `null` and render diagnostics report `render_exception @ render_tracks`.

## Findings grounded in artifacts and source

### 1. The prompt parsed as `trap_soul`, not rock

- Artifact evidence:
  - `project_metadata.json` has `current.parsed.genre: "trap_soul"` and `current.outputs.genre: "trap_soul"`.
  - `generation.stdout.log` prints `Genre: trap_soul` in the parsed prompt block.
- Source evidence:
  - `multimodal_gen/prompt_parser.py` defines `GENRE_KEYWORDS` without a `rock`, `classic_rock`, `alternative_rock`, or `grunge` entry.
  - `PromptParser._extract_genre()` falls through to `return 'trap_soul'  # Safe default` when no keyword matches.
- Implication: a rock prompt cannot become rock in the current parser path; it reaches downstream layers already mislabeled.

### 2. The parser extracted `guitar`, `bass`, and `choir`; `chorus` likely cross-matched `choir`

- Artifact evidence:
  - `project_metadata.json` has `current.parsed.instruments: ["guitar", "bass", "choir"]`.
  - `generation.stdout.log` prints `Instruments: guitar, bass, choir`.
- Source evidence:
  - `multimodal_gen/prompt_parser.py` has `INSTRUMENT_KEYWORDS['guitar']` and `INSTRUMENT_KEYWORDS['bass']`, which explain the intended guitar/bass detections.
  - The same file has `INSTRUMENT_KEYWORDS['choir']` including `chorus`; `_extract_instruments()` uses word-boundary matching, so the arrangement word `chorus` is treated as the instrument `choir`.
- Implication: section language and instrument language are conflated. Future parser work must classify `chorus` as a section hint unless the prompt asks for `choir`, `choral`, or voices.

### 3. Rock drums inherited trap-soul 808 defaults

- Artifact evidence:
  - `project_metadata.json` has `current.parsed.drum_elements: ["kick", "808", "snare", "clap", "hihat"]`.
  - `generation.stdout.log` prints `Drums: kick, 808, snare, clap, hihat`.
- Source evidence:
  - `multimodal_gen/prompt_parser.py` hardcoded genre defaults include `_get_genre_drums()['trap_soul'] = ['kick', '808', 'snare', 'clap', 'hihat']`.
- Implication: the 808 is not a rock-specific choice; it is a symptom of the fallback genre. Rock needs its own default drum vocabulary, e.g. kick/snare/hihat_open/crash/ride/toms/fills without mandatory 808/clap.

### 4. No rock strategy is registered

- Source evidence:
  - `multimodal_gen/strategies/registry.py` imports and registers trap, trap_soul, rnb, lofi, g_funk, house, Ethiopian-family, default, drill, boom_bap, cinematic, and ambient strategies.
  - The registry does not import or register a `RockStrategy`.
- Smoke corroboration:
  - The diagnostic script that listed `StrategyRegistry.list_genres()` showed `rock`, `classic_rock`, and `alternative_rock` absent, while `trap_soul` was present.
- Implication: even if parsing starts returning `rock`, the generator would currently fall back to `DefaultStrategy` unless a rock strategy is added and registered.

### 5. Rock patterns, presets, microtiming, and dynamics exist but are orphaned from the main path

Existing rock-aware material is present:

- `multimodal_gen/pattern_library.py`
  - Loads rock patterns via `_load_rock_patterns()`.
  - Contains examples such as `rock_basic_beat`, `rock_hard_double_kick`, `rock_eighth_note_bass`, `rock_power_chord`, `rock_riff_pentatonic`, plus extended fill/transition examples like `rock_fill_crash_cymbal` and `rock_transition_buildup`.
- `multimodal_gen/preset_system.py`
  - Defines `rock_classic` and `rock_indie` preset configs.
- `multimodal_gen/microtiming.py`
  - Defines a `rock` microtiming config.
- `multimodal_gen/dynamics.py`
  - Defines `rock` dynamics/CC expression entries.

Why this is still orphaned:

- The parser cannot return `rock` from the smoke prompt.
- `StrategyRegistry` has no `RockStrategy`.
- `arranger.py` has no hardcoded `rock` template and falls back unknown templates to `trap_soul`.
- `output_analyzer.py` has no `rock` entry in `AUDIO_GENRE_TARGETS`, so rendered-audio validation would otherwise treat rock as unknown and return a neutral score.

### 6. The arrangement ignored the 16-bar smoke intent and inflated to 28 bars

- Artifact evidence:
  - `generation.stdout.log` prints `Target duration: 0.6 min -> 28 bars (~1.1 min)` and `Arrangement: 7 sections, 28 bars`.
  - `session_manifest.json` has `total_bars: 28` and `total_ticks: 53760`; at 480 PPQ and 4/4 this is exactly 28 bars.
  - `project_metadata.json` sections are seven 4-bar sections: intro, drop, variation, breakdown, buildup, drop, outro.
- Source evidence:
  - `main.py` forwards `--duration-bars` by setting `parsed.target_duration_seconds` and `parsed.target_bars`.
  - `multimodal_gen/arranger.py` selects the genre template through `_get_template()`. Unknown genres fall back to `ARRANGEMENT_TEMPLATES['trap_soul']`.
  - `ARRANGEMENT_TEMPLATES['trap_soul']` has seven sections.
  - `_adjust_to_duration()` scales each template section but clamps every section to at least 4 bars with `new_bars = max(4, ...)`.
- Implication: the duration override is forwarded, but the selected seven-section trap-soul template cannot compress below 28 bars. Rock needs a template and a bounded-duration policy that can preserve `verse chorus bridge` intent while fitting short smoke targets.

### 7. Audio render failed in `render_tracks` due an unguarded organ click array length

- Artifact evidence:
  - `*_render_error.txt` reports `failure_reason: render_exception`, `failure_stage: render_tracks`, `exception_type: ValueError`, and `exception_message: operands could not be broadcast together with shapes (100,) (220,) (100,)`.
  - `*_render_report.json` mirrors the same failure in `render_status.failure`.
  - `generation.stderr.log` contains the traceback.
- Source evidence:
  - Traceback path: `audio_renderer.py::render_midi_file` → `_render_procedural()` → `_render_track_procedural()` → `ProceduralSynthesizer.render_notes()` → `_synthesize_note()` → `assets_gen.py::generate_organ_tone()`.
  - `audio_renderer.py` dispatches GM organ programs 16-23 to `generate_organ_tone()`.
  - `assets_gen.py::generate_organ_tone()` creates `click_duration = int(0.005 * sample_rate)` and then does `audio[:click_duration] += click` without clamping the click to the actual audio length.
- Implication: short MIDI notes shorter than the organ key-click length can crash procedural rendering. This is renderer correctness, independent of rock genre quality.

### 8. CLI returned success and printed `Generation Complete` despite `audio: null`

- Artifact evidence:
  - Runner exit code was `0`.
  - `project_metadata.json` has `current.outputs.audio: null`.
  - `generation.stdout.log` prints `[!] Audio rendering returned no output (render_exception @ render_tracks)` and later `[v] Generation Complete!`.
- Source evidence:
  - `main.py` computes `require_soundfont_failed = bool(args.require_soundfont and not results.get('audio'))`.
  - The CLI return path is `return 2 if require_soundfont_failed else 0`.
- Implication: for smoke/CI, exit code alone is not a reliable audio-quality signal unless a strict audio flag exists. Future verification should assert audio presence via metadata/render reports, not just process exit.

### 9. Guitar loading gap: custom melodic mapping does not include guitar; GM guitar programs map to keys

- Artifact evidence:
  - `project_metadata.json` selected no custom `guitar` instrument in the final render report; `custom_audio.custom_melodic_loaded` reports `bass` and `pad` only.
  - `generation.stdout.log` says `Prompt-filtered instruments: bass, pad` even though the prompt asked for guitar.
- Source evidence:
  - `audio_renderer.py::_load_custom_instruments()` has `melodic_mappings` for synth, bass, keys, pad, brass, and strings, but no guitar mapping.
  - `_INSTRUMENT_TO_MELODIC` does not map `guitar` or `electric guitar` to a melodic cache key.
  - `audio_renderer.py::_synthesize_note()` maps GM guitar programs 24-31 to `keys` in `program_to_type`.
  - Expansion fallback mapping can map program 25 to `guitar`, but the custom melodic path checks the `keys` cache first for 24-31.
- Implication: even if the MIDI asks for guitar, sample loading and synthesis routing can still produce keys/pads or fallback timbres. Guitar needs a first-class cache/category/synthesis route.

### 10. Missing module warning in smart instrument selection

- Artifact evidence:
  - `generation.stdout.log` contains `[!]  Smart instrument selection: No module named 'multimodal_gen.instrument_index'`.
- Source evidence:
  - `main.py` imports `from multimodal_gen.instrument_index import InstrumentIndex, InstrumentResolver, create_instrument_index` inside the smart instrument selection path.
  - Repository search finds only `multimodal_gen/_deprecated/instrument_index.py`; no live `multimodal_gen/instrument_index.py` exists.
- Implication: the warning is expected under the current file layout. Future work should either restore a supported shim/module or remove/replace this stale import path.

## Preserve list for future implementation

Do not regress or remove these existing behaviors while adding rock support:

1. Existing genres, strategies, and golden prompts.
2. `trap_soul`, `rnb`, and `neo_soul` priority/order and their current routing semantics.
3. Preference-driven defaults and user overrides, including BPM, key, presets, production presets, style presets, duration-bars, and reference-derived settings.
4. Default fallback for unknown genres; add rock explicitly without making unknown prompts fail.
5. Existing render diagnostics: `*_render_report.json`, `*_render_error.txt`, `render_status`, warnings, tracebacks, and metadata links.
6. MPC export, stems, takes, comping, session manifest, project metadata, and BWF/session graph outputs.
7. Ethiopian instrument procedural paths and the protective skip of generic melodic loading when Ethiopian instruments are requested.
8. JUCE generate, analyze, tools, takes, mixer, arrangement/regenerate, controls, and mastering workflows.
9. Existing expansion-pack loading behavior and Funk o Rama / R&B sample compatibility.
10. The current ability to run without FluidSynth by using procedural rendering and diagnostic warnings.

## Phased generation fix plan

### Phase 0 — Baseline lock and smoke harness

**Goal:** make the current failure reproducible and enforce future acceptance with artifacts, not listening impressions alone.

**File targets:**

- `docs/UPGRADE_PLAN_2026-05-14_1990S_ROCK_QUALITY_UI.md` — this plan and artifact baseline.
- Future harness target: `scripts/smoke_1990s_rock.ps1` or `scripts/smoke_1990s_rock.py`.
- Future focused test target: `tests/test_smoke_1990s_rock_contract.py`.

**Work:**

- Capture the exact prompt, seed, output directory convention, and expected artifact names.
- Make the runner quote the prompt as one argument; do not use `Start-Process` argument splitting that reproduces the first failed attempt.
- Require the harness to parse `project_metadata.json`, `session_manifest.json`, and render report/error files.
- Record expected current baseline failures: parsed genre `trap_soul`, 28 bars, audio null, render exception.

**Focused tests / verification commands:**

```powershell
Set-Location c:\dev\MUSE-ai\MUSE
.\.venv\Scripts\python.exe -m pytest tests/test_smoke_1990s_rock_contract.py -q
.\scripts\smoke_1990s_rock.ps1 -OutputRoot output\_diagnostics
```

**Acceptance:** current baseline test can prove the failure before fixes and can later be flipped to assert `rock`, bounded bars, non-null audio, and rock analyzer pass.

### Phase 1 — Renderer correctness and CLI success semantics

**Goal:** a render exception should not be hidden by `Generation Complete`, and short organ notes must not crash rendering.

**File targets:**

- `multimodal_gen/assets_gen.py`
- `multimodal_gen/audio_renderer.py`
- `main.py`
- `tests/test_assets_gen.py` or `tests/test_audio_renderer.py`
- `tests/test_main_render_diagnostics.py`

**Work:**

- Clamp organ key-click length to `min(click_duration, len(audio))` before adding click noise.
- Add a strict smoke/CI audio-success option, e.g. additive `--require-audio`, or make render exceptions non-zero under an existing strict flag while preserving default ad hoc behavior.
- Ensure the human summary distinguishes `Generation Complete (MIDI only)` from full audio success when `results['audio']` is null.
- Preserve existing `--require-soundfont` semantics for the specific SoundFont-required path.

**Focused tests / verification commands:**

```powershell
Set-Location c:\dev\MUSE-ai\MUSE
.\.venv\Scripts\python.exe -m pytest tests/test_render_report_schema.py tests/test_main_render_diagnostics.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_audio_renderer.py tests/test_assets_gen.py -q
```

**Acceptance:** short organ notes render without ValueError; render reports still persist; strict audio smoke exits non-zero on audio null/render_exception; default no-FluidSynth fallback remains documented and diagnostic-rich.

### Phase 2 — Rock parser, defaults, and genre intelligence

**Goal:** the investigated prompt becomes a rock-family parsed prompt with band defaults and no accidental choir/808 fallback.

**File targets:**

- `multimodal_gen/prompt_parser.py`
- `multimodal_gen/utils.py`
- `multimodal_gen/genre_rules.py` if rock-specific rules are needed
- `tests/test_prompt_parser.py`
- `tests/test_genre_normalization.py`

**Work:**

- Add `rock`, `classic_rock`, `alternative_rock`, and `grunge` keyword coverage, including `rock song`, `electric guitar`, `crunchy guitar`, `live drums`, `band performance`, `90s rock`, `1990s rock`, `alt rock`, `alternative rock`, and `grunge`.
- Put rock-family priority before `boom_bap` so `90s rock` does not become golden-era hip-hop, while preserving `boom_bap` for `90s hip hop`, `golden era`, and `old school` prompts.
- Add rock-family genre defaults: BPM bands, straight or subtle human feel, live drums, guitar/bass emphasis, no default 808/clap.
- Make `chorus` a section hint by default, not a choir instrument, unless the prompt contains explicit choir/choral/voices language.
- Keep unknown genre fallback to `trap_soul` or the current default so unsupported prompts remain fail-open.

**Focused tests / verification commands:**

```powershell
Set-Location c:\dev\MUSE-ai\MUSE
.\.venv\Scripts\python.exe -m pytest tests/test_prompt_parser.py tests/test_genre_normalization.py -q
```

**Acceptance:** the smoke prompt parses to `rock` or a canonical rock-family genre; instruments include guitar and bass but not choir; drums include live kit elements and exclude 808 unless explicitly requested; trap_soul/rnb/neo_soul existing parser tests still pass.

### Phase 3 — `RockStrategy` and PatternLibrary wiring

**Goal:** parsed rock must route to a real strategy that reuses existing rock pattern assets rather than falling back to `DefaultStrategy`.

**File targets:**

- `multimodal_gen/strategies/rock_strategy.py` (new)
- `multimodal_gen/strategies/registry.py`
- `multimodal_gen/pattern_library.py` only if adapters are needed; avoid rewriting existing patterns unnecessarily
- `multimodal_gen/arranger.py`
- `tests/test_strategy_registry.py` or new `tests/test_rock_strategy.py`
- `tests/test_arranger.py` or focused arranger tests

**Work:**

- Implement a minimal `RockStrategy` that supports `rock`, `classic_rock`, `alternative_rock`, and `grunge` aliases.
- Reuse existing `PatternLibrary` rock patterns for drums, bass, power chords, riffs, fills, and transitions.
- Add an arranger template for rock with verse/chorus/bridge semantics and a short-target path that can honor 16-bar smoke intent without expanding to seven mandatory sections.
- Keep strategy fallback behavior for unsupported genres.

**Focused tests / verification commands:**

```powershell
Set-Location c:\dev\MUSE-ai\MUSE
.\.venv\Scripts\python.exe -m pytest tests/test_strategy_registry.py tests/test_rock_strategy.py tests/test_arranger.py -q
```

**Acceptance:** `StrategyRegistry.get('rock')` returns `RockStrategy`; rock arrangements use verse/chorus/bridge labels when requested; 16-bar smoke targets produce a bounded arrangement rather than the trap-soul 28-bar minimum; existing strategy tests still pass.

### Phase 4 — Guitar/band instrumentation

**Goal:** rock MIDI and audio should sound like guitar/bass/drums rather than keys/pads/808 trap-soul fallback.

**File targets:**

- `multimodal_gen/instrument_manager.py`
- `multimodal_gen/audio_renderer.py`
- `multimodal_gen/assets_gen.py` if a procedural guitar fallback is added
- `multimodal_gen/midi_generator.py` if track/program selection needs explicit guitar programs
- `tests/test_instrument_manager.py`
- `tests/test_audio_renderer.py`
- `tests/test_midi_generator.py` or focused render-routing tests

**Work:**

- Add or expose a guitar category if the current instrument index can classify Funk o Rama / expansion guitar samples safely.
- Map prompt `guitar`, `electric guitar`, and `crunchy guitar` to a `guitar` melodic cache key.
- Map GM guitar programs 24-31 to `guitar`, not `keys`, in custom melodic lookup.
- Provide a procedural distorted/crunch guitar fallback only if no sample is available; keep it bounded and testable.
- Preserve Ethiopian instrument guardrails and existing expansion preload behavior.

**Focused tests / verification commands:**

```powershell
Set-Location c:\dev\MUSE-ai\MUSE
.\.venv\Scripts\python.exe -m pytest tests/test_instrument_manager.py tests/test_audio_renderer.py -q
```

**Acceptance:** guitar prompt causes guitar samples or guitar fallback to load; render report records `custom_melodic_loaded.guitar` when samples are available; GM 24-31 no longer route through keys first; Ethiopian procedural instruments still bypass generic melodic sample loading.

### Phase 5 — Output analyzer rock targets and repair loop

**Goal:** rendered-audio acceptance should know what rock is and should reject trap/808/pad-heavy outputs for rock prompts.

**File targets:**

- `multimodal_gen/output_analyzer.py`
- `tests/test_output_analyzer.py`
- `../copilot-Liku-cli/src/main/agents/producer.js` only if producer repair routing must react to rock-specific corrections
- `../copilot-Liku-cli/scripts/test-output-analysis-repair.js` only if producer repair routing changes

**Work:**

- Add conservative `rock` and optional rock-family entries to `AUDIO_GENRE_TARGETS`.
- Include expected timbres such as electric guitar/bass/drums and forbidden timbres such as 808/electronic trap drums for rock-family prompts.
- Ensure unknown-genre neutral score remains available for truly unsupported genres, but rock no longer uses that path.
- Add repair suggestions for too much sub-bass/808, missing live-drums, missing guitar-band timbre, and over-synthetic pads only when issues are measurable.

**Focused tests / verification commands:**

```powershell
Set-Location c:\dev\MUSE-ai\MUSE
.\.venv\Scripts\python.exe -m pytest tests/test_output_analyzer.py -q
node ..\copilot-Liku-cli\scripts\test-output-analysis-repair.js
```

**Acceptance:** rock gets a real analyzer target instead of neutral `0.75`; trap-soul-like 808 output fails rock validation; a guitar/bass/drums render can pass conservative rock thresholds; existing analyzer targets and repair routes remain stable.

### Phase 6 — Regression/golden prompts

**Goal:** lock the cross-layer rock fix without regressing current golden prompts.

**File targets:**

- `tests/test_prompt_parser.py`
- `tests/test_strategy_registry.py`
- `tests/test_output_analyzer.py`
- `tests/test_main_render_diagnostics.py`
- `output_cli_golden/`, `output_cli_golden_short/`, or a new documented diagnostics baseline if golden audio artifacts are intentionally not committed
- `docs/MASTERCLASS_MUSICALITY_IMPLEMENTATION_TRACKER.md` only if milestone tracking needs an accepted update

**Work:**

- Add golden prompt cases for:
  - the exact 1990s rock prompt in this document;
  - `90s boom bap hip hop` to preserve `boom_bap`;
  - `trap soul with 808 and rhodes` to preserve `trap_soul`;
  - `neo soul with rhodes and warm bass` to preserve `neo_soul`.
- Add a smoke assertion matrix: parsed genre, instruments, drums, sections/bars, render audio presence, render report success, analyzer score.
- Keep heavy audio golden artifacts optional; prefer deterministic metadata/render report assertions for CI speed.

**Focused tests / verification commands:**

```powershell
Set-Location c:\dev\MUSE-ai\MUSE
.\.venv\Scripts\python.exe -m pytest tests/test_prompt_parser.py tests/test_strategy_registry.py tests/test_output_analyzer.py tests/test_main_render_diagnostics.py -q
.\scripts\smoke_1990s_rock.ps1 -StrictAudio
```

**Acceptance:** exact prompt routes rock end-to-end; current trap_soul/rnb/neo_soul/boom_bap golden prompts retain prior classifications and critical artifacts; smoke is deterministic and does not rely on manual listening alone.

## Phased UI plan

### UI Phase A — Baseline checklist

**File targets:**

- `juce/Source/MainComponent.h`
- `juce/Source/MainComponent.cpp`
- `juce/Source/UI/GenreSelector.h`
- `juce/Source/UI/GenreSelector.cpp`
- `juce/Source/UI/InstrumentBrowserPanel.h`
- `juce/Source/UI/InstrumentBrowserPanel.cpp`
- `juce/Source/UI/ControlsPanel.h`
- `juce/Source/UI/ControlsPanel.cpp`
- `juce/Source/UI/Theme/ThemeManager.h`
- `juce/Source/UI/Theme/LayoutConstants.h`
- `juce/Source/UI/Visualization/GenreTheme.h`

**Checklist:**

- Build the current JUCE app before UI changes.
- Screenshot or checklist current main layout: transport, timeline, prompt panel, visualization, bottom panel, tools menu, instruments, FX, expansions, mixer, takes, controls, mastering.
- Verify generate/analyze/regenerate/takes/mixer workflows still open and close before any visual polish.

**Verification/build commands:**

```powershell
Set-Location c:\dev\MUSE-ai\MUSE
npm run build:debug
npm run build
```

### UI Phase B — Theme token unification

**Goal:** centralize visual constants before polishing individual panels.

**File targets:**

- `juce/Source/UI/Theme/ThemeManager.h`
- `juce/Source/UI/Theme/LayoutConstants.h`
- `juce/Source/UI/Visualization/GenreTheme.h`
- Panel files only where hardcoded colors/radii/padding need to be replaced.

**Work:**

- Add or reuse tokens for panel background, elevated surface, border, text primary/secondary, accent, warning, success, control radius, focus ring, row height, and standard gaps.
- Preserve existing genre theme behavior; tokens should be additive and low-risk.

**Verification:** app builds, panels retain layout, no component loses readability at default size.

### UI Phase C — `InstrumentBrowser`, `GenreSelector`, and `ControlsPanel` polish

**Goal:** improve the panels most relevant to genre/instrument intent without changing backend request semantics.

**File targets:**

- `juce/Source/UI/InstrumentBrowserPanel.cpp/.h`
- `juce/Source/UI/GenreSelector.cpp/.h`
- `juce/Source/UI/ControlsPanel.cpp/.h`

**Work:**

- InstrumentBrowser: clearer category chips, search/empty states, selected-state contrast, compact rows, and instrument source badges.
- GenreSelector: add rock-family choices only after generation backend supports them; ensure `auto` remains default and existing choices preserve IDs.
- ControlsPanel: clearer scope labels for global vs next generate/regenerate overrides; preserve `nextGenerateOverrides` and `nextRegenerateOverrides` wiring.

**Verification:** build plus manual checklist that selected genre/instrument changes still reach current UI state and do not break generate/regenerate payloads.

### UI Phase D — Tool-window and arrangement/takes preservation

**Goal:** avoid UI polish regressing tool-window behavior, bottom-panel behavior, arrangement edits, takes, and mixer.

**File targets:**

- `juce/Source/MainComponent.h/.cpp`
- `juce/Source/UI/FloatingToolWindow.h/.cpp`
- `juce/Source/UI/TakeLaneComponent.h/.cpp`
- `juce/Source/UI/Mixer/MixerComponent.h/.cpp`
- `juce/Source/UI/TimelineComponent.h/.cpp`

**Work:**

- Preserve existing tool IDs from `MainComponent::showToolWindow(int toolId)`.
- Preserve current bottom panel semantics for FX, Mixer, Takes, and any existing Instruments behavior unless intentionally changed in its own PR.
- Verify arrangement/regenerate controls, take audition/restore, take comp snapshots, and mixer binding remain intact.

**Verification:** build plus manual smoke of Tools menu, Takes, Mixer, and Generate/Analyze.

### UI Phase E — Optional genre accent

**Goal:** make genre identity visible without introducing hardcoded style forks that drift from backend support.

**File targets:**

- `juce/Source/UI/Visualization/GenreTheme.h`
- `juce/Source/MainComponent.cpp`
- `juce/Source/UI/GenreSelector.cpp`

**Work:**

- Add a subtle rock accent only after backend parser/strategy/analyzer support lands.
- Keep accent optional; if genre is `auto` or unsupported, use existing neutral theme.

**Verification/build commands:**

```powershell
Set-Location c:\dev\MUSE-ai\MUSE
npm run build:debug
npm run build
```

**UI acceptance:** visual improvements compile, preserve workflows, and do not ship rock UI choices that imply backend support before the generation path is ready.

## Next 10 PR-sized tasks

### PR 1 — Add strict 1990s rock smoke harness

- **Acceptance criteria:** one command reproduces the prompt, captures output under `output/_diagnostics`, records PID/exit/artifacts, and asserts current baseline failures before fixes.
- **Verification:**

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_smoke_1990s_rock_contract.py -q
  .\scripts\smoke_1990s_rock.ps1 -OutputRoot output\_diagnostics
  ```

### PR 2 — Fix organ key-click crash for short notes

- **Acceptance criteria:** `generate_organ_tone()` handles durations shorter than 5 ms; no ValueError from click addition; render report schema remains unchanged.
- **Verification:**

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_audio_renderer.py tests/test_render_report_schema.py -q
  ```

### PR 3 — Add strict audio success semantics for smoke/CI

- **Acceptance criteria:** strict flag or strict mode exits non-zero when audio is null or render status has `success: false`; default permissive no-FluidSynth behavior remains documented; summary no longer implies full success when only MIDI exists.
- **Verification:**

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_main_render_diagnostics.py -q
  .\scripts\smoke_1990s_rock.ps1 -StrictAudio
  ```

### PR 4 — Add rock-family parser coverage and section-aware `chorus`

- **Acceptance criteria:** exact prompt parses to rock-family genre, instruments include guitar/bass and exclude choir, drums exclude 808 unless explicit; `90s boom bap hip hop` still parses to boom_bap.
- **Verification:**

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_prompt_parser.py tests/test_genre_normalization.py -q
  ```

### PR 5 — Add rock defaults without disturbing soul/trap defaults

- **Acceptance criteria:** rock defaults include live-kit/band emphasis, reasonable BPM range, no hihat-roll/808 defaults; trap_soul/rnb/neo_soul parser/default tests still pass.
- **Verification:**

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_prompt_parser.py tests/test_genre_normalization.py -q
  ```

### PR 6 — Add and register minimal `RockStrategy`

- **Acceptance criteria:** `StrategyRegistry.get('rock')`, `get('classic_rock')`, `get('alternative_rock')`, and `get('grunge')` return rock strategy; unknown genres still get default fallback.
- **Verification:**

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_strategy_registry.py tests/test_rock_strategy.py -q
  ```

### PR 7 — Wire rock patterns and bounded rock arrangement

- **Acceptance criteria:** rock strategy uses existing rock patterns; exact 16-bar smoke target produces bounded verse/chorus/bridge-compatible sections instead of trap-soul seven-section minimum; existing arranger templates still pass.
- **Verification:**

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_rock_strategy.py tests/test_arranger.py -q
  ```

### PR 8 — Make guitar first-class in instrument loading/render routing

- **Acceptance criteria:** guitar prompt loads guitar samples when available or uses a guitar fallback; GM guitar programs 24-31 route to guitar cache/type, not keys; Ethiopian procedural skip remains intact.
- **Verification:**

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_instrument_manager.py tests/test_audio_renderer.py -q
  ```

### PR 9 — Add rock rendered-audio targets and repair signals

- **Acceptance criteria:** rock no longer uses unknown neutral analyzer score; trap/808-heavy output fails rock validation; rock-like guitar/bass/drums output can pass conservative thresholds; repair suggestions are concrete and bounded.
- **Verification:**

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_output_analyzer.py -q
  node ..\copilot-Liku-cli\scripts\test-output-analysis-repair.js
  ```

### PR 10 — UI polish pass with workflow preservation

- **Acceptance criteria:** theme tokens unified; InstrumentBrowser, GenreSelector, and ControlsPanel polish compiles; Generate/Analyze/Tools/Takes/Mixer workflows preserved; optional rock accent appears only after backend rock support exists.
- **Verification:**

  ```powershell
  npm run build:debug
  npm run build
  ```

## Final readiness criteria

The 1990s rock prompt should not be judged musically until all of these are true in one smoke run:

1. Parser output genre is rock-family, not `trap_soul`.
2. Instruments include guitar and bass without accidental choir from `chorus`.
3. Drums are live-kit rock drums without default 808.
4. Strategy is `RockStrategy`, not `DefaultStrategy` or trap-soul.
5. Arrangement honors the requested compact smoke duration or explains any intentional expansion.
6. Renderer produces a non-null audio artifact or strict smoke fails non-zero with render diagnostics.
7. Render report is successful and includes expected guitar/bass/drum loading where available.
8. Output analyzer evaluates rock with real targets and passes conservatively.
9. Existing trap_soul/rnb/neo_soul/boom_bap/Ethiopian/JUCE workflows still pass their focused proofs.

## Implementation and validation results — 2026-05-14

This plan has now been implemented through the generation, analyzer, golden-regression, UI-polish, and app-validation milestones. The final validation used the running JUCE Release app plus the JSON-RPC gateway to exercise the same backend workflow from an opened desktop session.

### Source-control state observed during app validation

- Initial Source Control concern: VS Code showed pending/outgoing activity, but `git status --short --untracked-files=all` in `c:\dev\MUSE-ai\MUSE` was clean before the app-validation milestone.
- Branch state before this validation milestone: `master...origin/master [ahead 10]`; no local working-tree diff in the MUSE repo.
- After the final app-validation proof, one backend transport bug was fixed and documented in this milestone: JSON-RPC/OSC requests can send `key` and `mode` separately, but the worker previously forwarded only `key="E"`, which forced E major. `build_run_generation_kwargs()` now compacts `key="E", mode="minor"` into the `Em` key override expected by `main.run_generation()`.

### Backend/app launch validation

- Release app launched from:
  `juce\build\MultimodalMusicGen_artefacts\Release\AI Music Generator.exe`
- Gateway launched with:
  `.\.venv\Scripts\python.exe -m multimodal_gen.server --gateway --verbose`
- Stale hidden gateway PIDs were identified and stopped before the final E-minor validation so the running JSON-RPC server loaded the latest worker code.
- Final gateway health proof: JSON-RPC `ping` returned `status: ok` from the fresh backend process.

### Final rock request proof

Prompt:

```text
1990's era rock song with crunchy electric guitar, live drums, bass guitar, verse chorus bridge, energetic band performance, 100 BPM in E minor
```

Final artifact directory:

```text
output\ui_validation\rock_app_validation_20260514_eminor_fixed
```

Key proof from `generate_sync` request `ui-rock-eminor-fixed-20260514`:

- JSON-RPC success: `true`
- Task ID: `ff861647`
- MIDI: `output\ui_validation\rock_app_validation_20260514_eminor_fixed\rock_100bpm_Eminor_20260514_101946.mid` (`5151` bytes)
- WAV: `output\ui_validation\rock_app_validation_20260514_eminor_fixed\rock_100bpm_Eminor_20260514_101946.wav` (`7183920` bytes)
- The final WAV was opened in the default Windows audio player for listening review.

Metadata proof:

- Genre: `rock`
- BPM: `100`
- Key/scale: `E minor`
- Sections: `verse` 4 bars, `chorus` 4 bars, `bridge` 4 bars, `chorus` 4 bars (`16` bars total)

Render/audio-analysis proof:

- `render_status.success: true`
- `audio_analysis.target_genre: rock`
- `audio_analysis.passed: true`
- `genre_match_score: 0.997`
- `spectral.sub_bass_energy_ratio: 0.1245`
- `drums.percussive_ratio: 0.112`
- Required drum parts detected: `has_kick=true`, `has_snare_or_clap=true`, `has_hihats=true`
- `onset_density: 4.69`
- Remaining analyzer note is a warning, not a failure: live drum presence is slightly below the strict rock target but required drum parts are present, so the tolerance gate passes as intended.

MIDI proof:

- Bass track uses GM electric bass program `34` (0-based), not Synth Bass/808 routing.
- Chords track uses GM guitar program `25` (0-based), not Rhodes/keys.
- Clap pitch `39` is absent.

### Verification commands after the transport fix

```powershell
Set-Location c:\dev\MUSE-ai\MUSE
.\.venv\Scripts\python.exe -m pytest tests/test_protocol.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_golden_prompts_smoke.py tests/test_smoke_1990s_rock_contract.py -q
git diff --check
```

Results:

- `tests/test_protocol.py`: `39 passed`
- Golden/rock smoke contracts: `26 passed`
- `git diff --check`: `PASS`

### Remaining caveats

- FluidSynth remains unavailable in this environment; final validation used the procedural renderer, which is the supported fallback path.
- Generated output directories under `output\ui_validation\...` are validation artifacts and are intentionally not staged.
- Source-control outgoing commits still need to be pushed separately if remote synchronization is desired; this validation milestone only stages/commits local repo progress.
