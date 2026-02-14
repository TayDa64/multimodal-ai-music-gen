# Implementation Plan — Post-Masterclass Phase

> **Generated**: 2026-02-14 | **Grounded against**: codebase truth + research subagents  
> **Baseline**: 1223 tests passed, 6 skipped | All 15 TASKS_CODING_AGENT items COMPLETE  
> **ROADMAP**: 22/22 COMPLETE

---

## Executive Summary

The Python backend musicality engine is feature-complete. Remaining work falls into two categories:

1. **Python-Side Polish** (6-10 hours, low risk) — `/analyze` routing, dependency messaging  
2. **JUCE Desktop/DAW Features** (20-40+ days, medium-high risk) — mixer, save/load, arrangement, distribution, VST3

---

## Wave 4: Python-Side Polish (Quick Wins)

### P1. Optional Dependency Error Codes (2-3 hours) ⬜
**Why first**: Item P2 depends on this error pathway.

**Current state**: When `librosa`/`yt-dlp` is missing, `/analyze` catches `ImportError` at `osc_server.py:575` and sends generic `ErrorCode.UNKNOWN (100)`. User sees "Generation Error" — wrong title, wrong code, no guidance.

**Changes**:
| File | Change |
|------|--------|
| `multimodal_gen/server/config.py` | Add `OPTIONAL_DEPENDENCY_MISSING = 600` to ErrorCode enum |
| `multimodal_gen/server/osc_server.py` | Catch `ImportError` specifically in `/analyze`, send code 600 with structured message (dep name + pip command) |
| JUCE `MainComponent.cpp` | Handle code 600 in `onError()` — show "Optional Feature Unavailable" with install instructions |

**Tests**: 2-3 new tests in `tests/test_protocol.py` for error code 600 pathway.

### P2. `/analyze` Smart Routing (3-4 hours) ⬜
**Why**: Currently only `reference_analyzer.py` is reachable from `/analyze`. MIDI files and librosa-less scenarios fail entirely. `file_analysis.py` is fully implemented but unreachable.

**Routing rules**:
| Input | librosa? | Route | Rationale |
|-------|----------|-------|-----------|
| URL | yes | `reference_analyzer.analyze_url()` | Rich output (BPM, key, chords, genre) |
| URL | no | Error 600 + "install librosa yt-dlp" | Can't download without yt-dlp |
| Local `.mid`/`.midi` | any | `file_analysis.analyze_path()` | Doesn't need librosa, uses mido |
| Local audio | yes | `reference_analyzer.analyze_file()` | Rich output |
| Local audio | no | `file_analysis.analyze_path()` | Fallback: loudness/peak/centroid via numpy |

**Output normalization**: Thin adapter in `_handle_analyze` to unify `ReferenceAnalysis` and `AnalysisResult` into a common JSON schema for the JUCE client.

**Tests**: 3-4 new tests for routing logic (MIDI path, audio fallback, URL rejection).

### P3. FX Reset/Copy/Paste Verification (1 hour) ⬜
**Discovery**: Research found this is **ALREADY FULLY IMPLEMENTED** in JUCE:
- `FXChainPanel::resetToDefault()` — clears all 4 bus strips
- `FXChainPanel::copyChainToClipboard()` — serializes to JSON + system clipboard  
- `FXChainPanel::pasteChainFromClipboard()` — deserializes from clipboard

**Action**: Verify save/load roundtrip is lossless. Remove from `remainingTasks.md` open items.

### P4. Take Render Integration (4-6 hours, DEFERRED) ⬜
**What**: `osc_server.py:1326` has `# TODO: Actually render the take (integrate with audio_renderer)`. Take metadata is surfaced in protocol but audio rendering of takes is stubbed.

**Defer rationale**: Not blocking any current user-facing workflow. Takes work for MIDI; audio rendering is a future polish.

---

## Wave 5: JUCE Desktop/DAW Features

### J1. Track Mixer — Level Meter Hookup + Master Strip (1 day) ⬜
**Problem**: `LevelMeter::setLevel()` exists and renders beautifully, but `MixerComponent` never feeds actual RMS/peak data from `AudioEngine` tracks. Meters show 0.

**Changes**:
- `AudioEngine`: Add per-track RMS/peak extraction in audio callback (atomic float storage)
- `MixerComponent`: Timer-driven reading of `AudioEngine::getTrackLevel(idx)` → `channelStrip.meter.setLevel()`
- Add `MasterChannelStrip` at right edge of mixer viewport

**Risk**: Low — additive change to audio callback with atomic reads.

### J2. Project Save/Load — Relative Paths + Collect-and-Copy (1-2 days) ⬜
**Problem**: File paths stored as absolute strings. Projects not portable.

**Changes**:
- `ProjectState::saveProject()`: Convert absolute paths to relative (from `.mmg` location)
- `ProjectState::loadProject()`: Resolve relative paths against `.mmg` location
- Add `ProjectState::collectAndCopy(destFolder)`: Copy referenced WAV/MIDI into project subfolder
- Add version migration framework for future schema changes

**Risk**: Very low — core save/load already works.

### J3. Track Mixer — dB Scale Faders + Send/Return (2-3 days) ⬜
**Problem**: Volume slider is 0.0-1.0 linear, not dB-calibrated. No send/return architecture.

**Changes**:
- `ChannelStrip`: Convert fader to dB scale (-∞ to +12dB), logarithmic mapping
- `MixerGraph`: Add auxiliary send buses (reverb, delay sends per track)
- `ChannelStrip`: Add send knobs below pan knob
- `MixerGraph`: Add return buses that sum send contributions

**Risk**: Low-medium.

### J4. Timeline Arrangement — Clip Data Model + Drag/Move (3-5 days) ⬜
**Problem**: Notes are stored flat in global `NOTES` node. No "clip region" that can be moved/duplicated on timeline.

**Architecture**:
1. Introduce `CLIP` ValueTree node: `{trackIndex, startBeat, endBeat, type(MIDI|Audio), sourceFile?}`
2. `ClipComponent`: `juce::Component` + `DragAndDropTarget` (pattern proven in `FXChainPanel`)
3. `juce::ComponentDragger` for move operations
4. Left/right edge hit-test zones for trim handles
5. Keep flat `NOTES` as raw data; overlay clip metadata

**Risk**: Medium — data model change, but notes stay in existing format.

### J5. Distribution Packaging (3-5 days) ⬜
**Architecture**:
- Python: `PyInstaller --onedir` for backend (~150-200MB without ML models)
- JUCE: Single `.exe` + DLLs (~10-20MB)
- Installer: NSIS/WiX via CPack
- `PythonManager` already launches subprocess — just point at bundled `backend/` folder

**Size estimates**:
| Component | Size |
|-----------|------|
| JUCE app | 10-20 MB |
| Python backend (lean) | 150-200 MB |
| Python backend (with torch) | 2-3 GB |

### J6. Timeline Automation Lanes (2-3 days, DEFERRED) ⬜
Automation tracks for volume/pan curves over time. Deferred — additive, not blocking.

### J7. VST3/AU Plugin Wrapper (8-15 days, DEFERRED) ⬜
**Risk**: HIGH. Architecture is standalone-first (`AppState`, `PythonManager` subprocess, `AudioDeviceManager` ownership). Plugin mode requires fundamentally different lifecycle. OSC bridge from plugin sandbox is non-trivial. **Defer until standalone is feature-complete.**

---

## Recommended Execution Order

```
Phase A: Python Polish (P1 → P2 → P3)          ~6-8 hours, Low risk
Phase B: JUCE Quick Wins (J1 → J2)              ~2-3 days, Low risk
Phase C: JUCE Professional (J3 → J4)            ~5-8 days, Medium risk
Phase D: Distribution (J5)                       ~3-5 days, Medium risk
Phase E: Stretch (J6 → J7)                      ~10-18 days, High risk
```

**Phase A + B are safe to execute immediately** — additive, low risk, high UX impact.

---

## Dependencies

```
P1 (error codes) ──► P2 (/analyze routing uses error code 600)
J1 (meter hookup) ── independent
J2 (relative paths) ── independent  
J3 (dB faders) ──► J1 (requires working meters for verification)
J4 (clips) ── independent (but benefits from J2 for save/load)
J5 (distribution) ──► J1, J2 (ship what works)
J6 (automation) ──► J4 (clip model)
J7 (VST3) ──► everything else
```
