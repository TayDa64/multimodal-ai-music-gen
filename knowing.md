# 🎵 AI Music Generator - Project Knowledge Base

> **Reference document for continuing development across chat sessions**  
> **Last Updated**: December 11, 2025

---

## 📋 Table of Contents

1. [Project Vision](#-project-vision)
2. [Architecture Overview](#-architecture-overview)
3. [Completed Phases](#-completed-phases)
4. [Current State](#-current-state)
5. [File Structure](#-file-structure)
6. [Key Technical Details](#-key-technical-details)
7. [Known Issues & Fixes](#-known-issues--fixes)
8. [Next Steps](#-next-steps)
9. [Build & Run Instructions](#-build--run-instructions)
10. [Quick Reference](#-quick-reference)

---

## 🎯 Project Vision

**Transform the Multimodal AI Music Generator from a CLI tool into a professional-grade, real-time music production application with industry-standard UI, visualization, and DAW integration.**

### What This Project Is

A **dual-component music production system**:

1. **Python Backend** - The AI brain that handles:
   - Natural language prompt parsing
   - Musical arrangement generation
   - MIDI composition with humanization
   - Audio rendering
   - Instrument AI matching
   - MPC project export

2. **JUCE Frontend** - The professional UI that handles:
   - Real-time audio playback
   - Visual MIDI editing (Piano Roll)
   - Waveform & spectrum visualization
   - Transport controls
   - OSC communication with Python
   - Future: VST3/AU plugin format

### Critical Design Principle

```
┌─────────────────────────────────────────────────────────────────┐
│  RULE: Python backend remains THE source of truth for:          │
│  • Prompt parsing & musical analysis                            │
│  • MIDI generation & humanization                               │
│  • Instrument AI matching                                       │
│  • Arrangement intelligence                                     │
│                                                                 │
│  JUCE handles ONLY:                                             │
│  • Real-time audio playback                                     │
│  • User interface & visualization                               │
│  • Transport control                                            │
│  • Communication with Python backend                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         JUCE APPLICATION                                 │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                         UI LAYER                                    │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────────────┐  │ │
│  │  │Transport │ │ Prompt   │ │ Progress │ │ Visualization         │  │ │
│  │  │Controls  │ │ Panel    │ │ Overlay  │ │ (Piano/Wave/Spectrum) │  │ │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └───────────┬───────────┘  │ │
│  └───────┼────────────┼────────────┼───────────────────┼──────────────┘ │
│          │            │            │                   │                │
│  ┌───────▼────────────▼────────────▼───────────────────▼──────────────┐ │
│  │                      APPLICATION CORE                               │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │ │
│  │  │ AudioEngine  │  │ MidiPlayer   │  │ AppState                 │  │ │
│  │  │ (Playback)   │  │ (Synth)      │  │ (State Management)       │  │ │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘  │ │
│  └────────────────────────────┬───────────────────────────────────────┘ │
│                               │                                         │
│  ┌────────────────────────────▼───────────────────────────────────────┐ │
│  │                    OSC COMMUNICATION BRIDGE                         │ │
│  │     Port 9001 (receive) ←──────→ Port 9000 (send to Python)        │ │
│  └────────────────────────────┬───────────────────────────────────────┘ │
└───────────────────────────────┼─────────────────────────────────────────┘
                                │ UDP
┌───────────────────────────────▼─────────────────────────────────────────┐
│                         PYTHON BACKEND                                   │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  OSC Server (--server mode) → Worker Thread → Generation Pipeline  │ │
│  │                                                                     │ │
│  │  PromptParser → Arranger → MidiGenerator → AudioRenderer → Export  │ │
│  │       ↓           ↓            ↓              ↓                    │ │
│  │  InstrumentMatcher ← InstrumentLibrary    MpcExporter             │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## ✅ Completed Phases

### Phase 0: Foundation Research ✅
- OSC communication validated (<10ms latency)
- Python-osc server mode implemented
- JUCE audio architecture researched
- Project file format designed

### Phase 1: Python OSC Server ✅
- `multimodal_gen/server/` module created
- `--server` mode added to `main.py`
- Progress callbacks integrated
- Graceful shutdown handling

### Phase 2: JUCE Project Foundation ✅
- CMake build system configured
- MainComponent with responsive layout
- Window state persistence
- Theme/ColourScheme system

### Phase 3: OSC Communication Bridge ✅
- `OSCBridge` class with listener pattern
- `PythonManager` for process control
- `Messages.h` with data structures
- Connection status UI indicator

### Phase 4: Transport & Playback ✅
- `AudioEngine` with device management
- `MidiPlayer` with 16-voice polyphony
- `SimpleSynthVoice` with ADSR envelopes
- `TransportComponent` (play/pause/stop/seek)
- `TimelineComponent` with sections
- `AudioSettingsDialog` for device config

### Phase 5: Prompt & Generation UI ✅
- `PromptPanel` with genre presets
- `ProgressOverlay` with cancel
- Generation flow (prompt → Python → load result)
- `RecentFilesPanel` for history

### Phase 6: Piano Roll Visualization ✅
- `PianoRollComponent` (700+ lines)
- Note rendering with velocity/track colors
- Zoom (0.1x-10x) and scroll
- Track filtering (show/hide/solo)
- Note inspector tooltips
- `VisualizationPanel` with tabs

### Phase 7: Waveform & Spectrum ✅
- `WaveformComponent` with 4 display modes
- `SpectrumComponent` with FFT analysis
- **FFT Normalization Fix** (critical bug fixed)
- Production-grade envelope follower
- Noise floor gating (-80dB)
- Multi-frame averaging
- Genre-aware color themes (7 themes)
- 60fps smooth rendering

---

## 📊 Current State

### Git Repository
- **Repository**: `TayDa64/multimodal-ai-music-gen`
- **Branch**: `master`
- **Latest Commit**: `f196f50` - "Fix: Normalize FFT output to prevent spectrum bars going off-screen"

### Recent Commits (Last 10)
```
f196f50 Fix: Normalize FFT output to prevent spectrum bars going off-screen
3248b7e Fix: Spectrum visualization bounds clamping
dc3f8b7 Update TODO.md: Mark Phase 7 as complete with details
4b824ba Phase 7 Enhancement: Production-grade visualization improvements
b620566 Phase 7: Waveform & Spectrum Visualization
1f97d90 Fix Phase 6 Piano Roll interaction bugs
38b3901 Complete Phase 6: Piano Roll Visualization
514b430 Complete Phase 4 & 5: Timeline, AudioSettings, bar/beat display
f489f81 Complete Phases 0-3: OSC bridge, Audio engine, UI polish
91764ef Phase 2: JUCE project foundation complete
```

### What Works Right Now
| Feature | Status | Notes |
|---------|--------|-------|
| JUCE app launches | ✅ | No crashes |
| Audio playback | ✅ | 16-voice synth |
| Load MIDI files | ✅ | Drag-drop or button |
| Transport controls | ✅ | Play/pause/stop/seek |
| Piano Roll view | ✅ | Zoom, scroll, note info |
| Waveform view | ✅ | Real-time, 4 modes |
| Spectrum view | ✅ | FFT, normalized, 4 modes |
| Files tab | ✅ | Browse output folder |
| Genre themes | ✅ | 7 color themes |
| Python OSC server | ✅ | `--server` mode |
| Generation flow | ✅ | Prompt → Python → Load |

### Known Limitations
- No per-track mixer yet (Phase 8)
- No instrument browser yet (Phase 9)
- No project save/load yet (Phase 10)
- No VST3 plugin yet (Phase 11)

---

## 📁 File Structure

```
multimodal-ai-music-gen/
├── main.py                          # CLI entry + --server mode
├── requirements.txt                 # Python deps (python-osc)
├── TODO.md                          # Detailed implementation plan
├── knowing.md                       # THIS FILE - project knowledge
├── README.md                        # User documentation
│
├── multimodal_gen/                  # Python backend
│   ├── __init__.py
│   ├── prompt_parser.py             # NLP extraction
│   ├── arranger.py                  # Song structure
│   ├── midi_generator.py            # MIDI composition
│   ├── audio_renderer.py            # WAV rendering
│   ├── mpc_exporter.py              # MPC export
│   ├── instrument_manager.py        # Instrument library
│   ├── assets_gen.py                # Procedural samples
│   ├── sample_loader.py             # Custom samples
│   ├── reference_analyzer.py        # YouTube analysis
│   ├── utils.py                     # Helpers
│   └── server/                      # OSC server module
│       ├── __init__.py
│       ├── osc_server.py            # MusicGenOSCServer
│       ├── worker.py                # GenerationWorker
│       └── config.py                # Port config
│
├── juce/                            # JUCE frontend
│   ├── CMakeLists.txt               # Build config
│   ├── build/                       # Build output
│   │   └── MultimodalMusicGen_artefacts/
│   │       └── Release/
│   │           └── AI Music Generator.exe
│   └── Source/
│       ├── Main.cpp                 # App entry
│       ├── MainComponent.h/cpp      # Root component
│       │
│       ├── Application/
│       │   ├── AppState.h/cpp       # State + listeners
│       │   └── AppConfig.h          # Constants
│       │
│       ├── Audio/
│       │   ├── AudioEngine.h/cpp    # Playback engine
│       │   ├── MidiPlayer.h/cpp     # MIDI sequencing
│       │   └── SimpleSynthVoice.h   # Synth voice
│       │
│       ├── Communication/
│       │   ├── OSCBridge.h/cpp      # OSC client
│       │   ├── Messages.h           # Data structs
│       │   └── PythonManager.h/cpp  # Process control
│       │
│       └── UI/
│           ├── Theme/
│           │   ├── ColourScheme.h   # Colors
│           │   └── AppLookAndFeel.h/cpp
│           │
│           ├── TransportComponent.h/cpp
│           ├── TimelineComponent.h/cpp
│           ├── PromptPanel.h/cpp
│           ├── ProgressOverlay.h/cpp
│           ├── RecentFilesPanel.h/cpp
│           ├── AudioSettingsDialog.h/cpp
│           ├── VisualizationPanel.h/cpp
│           │
│           └── Visualization/
│               ├── PianoRollComponent.h/cpp
│               ├── WaveformComponent.h/cpp
│               ├── SpectrumComponent.h/cpp
│               └── GenreTheme.h
│
├── output/                          # Generated files
├── instruments/                     # Sample libraries
└── test_*.py                        # Test scripts
```

---

## 🔧 Key Technical Details

### OSC Communication
- **JUCE → Python**: Port 9000
- **Python → JUCE**: Port 9001
- **Protocol**: UDP with JSON payloads
- **Messages**: `/generate`, `/cancel`, `/progress`, `/complete`, `/error`

### Audio Engine
- **Sample Rate**: 44100 Hz (configurable)
- **Buffer Size**: 512 samples default
- **Voices**: 16 polyphony
- **ADSR**: 10ms attack, 100ms decay, 70% sustain, 300ms release

### Spectrum Analyzer (Phase 7)
- **FFT Size**: 2048 samples (order 11)
- **Window**: Hann
- **Normalization**: `2.0f / fftSize` (CRITICAL - fixes off-screen bug)
- **Envelope Follower**: ~5ms attack, ~300ms release
- **Noise Gate**: -80dB threshold
- **Frame Averaging**: 3 frames

### Genre Themes
| Genre | Colors |
|-------|--------|
| Default | Blue/Purple |
| G-Funk | Purple/Green/Gold |
| Trap | Red/Black/White |
| Lo-Fi | Orange/Brown/Cream |
| Boom Bap | Gold/Brown/Black |
| Drill | Dark Blue/Black/White |
| House | Cyan/Magenta/Yellow |

---

## 🐛 Known Issues & Fixes

### Critical Fixes Applied

1. **FFT Normalization** (f196f50)
   - JUCE FFT returns un-normalized magnitudes (scale with fftSize)
   - Fix: Multiply by `2.0f / fftSize`
   - Without this, spectrum bars shoot off-screen

2. **Null Pointer in resized()** (f489f81)
   - Child components accessed before initialization
   - Fix: Add null checks for all unique_ptr members

3. **Prompt Panel Lockout** (f489f81)
   - Different callbacks: `onGenerationFinished()` vs `onGenerationCompleted()`
   - Fix: Call `notifyGenerationCompleted()` explicitly

4. **Static Initialization Order**
   - `static const juce::Colour` caused crashes
   - Fix: Use `inline const juce::Colour` (C++17)

---

## 🚀 Next Steps

### Phase 8: Track Mixer (NEXT)
**Goal**: Per-track volume, pan, mute/solo

Tasks:
- [ ] Create `MixerComponent`
- [ ] Create `ChannelStrip` with faders
- [ ] Create `LevelMeter` (VU meters)
- [ ] Implement audio routing per track
- [ ] Solo/mute logic
- [ ] Mixer state persistence

### Phase 9: Instrument Browser
**Goal**: Browse and select custom instruments
- Tree view by category
- Waveform preview
- Drag-and-drop to tracks
- AI recommendations

### Phase 10: Project Management
**Goal**: Save, load, manage projects
- `.mmg` project file format
- Undo/redo (command pattern)
- Recent projects menu
- Auto-save

### Phase 11: VST3/AU Plugin
**Goal**: Run inside DAWs
- `PluginProcessor` class
- DAW transport sync
- Sidechain input
- Plugin installer

### Phase 12: Advanced Features
- Vocal input processing
- AI harmonization
- Real-time suggestions
- Collaborative features

---

## 🛠️ Build & Run Instructions

### Prerequisites
- **JUCE 7.x** installed (auto-detected or set `-DJUCE_DIR`)
- **CMake 3.22+**
- **Visual Studio 2022** (Windows)
- **Python 3.10+**

### Build JUCE Application
```powershell
cd "c:\dev\AI Music Generator\multimodal-ai-music-gen\juce"
mkdir build -Force
cd build
cmake .. -G "Visual Studio 17 2022"
cmake --build . --config Release
```

### Run Application
```powershell
Start-Process ".\MultimodalMusicGen_artefacts\Release\AI Music Generator.exe"
```

### Start Python Server (for generation)
```powershell
cd "c:\dev\AI Music Generator\multimodal-ai-music-gen"
python main.py --server --no-signals
```

### Full End-to-End Test
1. Start Python server in terminal 1
2. Launch JUCE app
3. Type prompt, click Generate
4. Wait for generation
5. Play result, check visualizations

---

## 📚 Quick Reference

### Key Files to Edit

| Task | File(s) |
|------|---------|
| Add UI component | `juce/Source/UI/`, `MainComponent.cpp` |
| Modify transport | `TransportComponent.h/cpp` |
| Modify visualization | `Visualization/*.cpp` |
| Change colors | `ColourScheme.h`, `GenreTheme.h` |
| Add OSC message | `OSCBridge.cpp`, `Messages.h` |
| Modify audio engine | `AudioEngine.cpp` |
| Modify Python generation | `multimodal_gen/*.py` |

### Important Classes

| Class | Purpose |
|-------|---------|
| `MainComponent` | Root component, layout |
| `AppState` | State management, listeners |
| `AudioEngine` | Audio device, playback |
| `MidiPlayer` | MIDI sequencing, synth |
| `OSCBridge` | Python communication |
| `VisualizationPanel` | Tabbed viz container |
| `PianoRollComponent` | MIDI visualization |
| `SpectrumComponent` | FFT display |
| `WaveformComponent` | Oscilloscope display |

### Common Commands

```powershell
# Build
cd juce/build && cmake --build . --config Release

# Run app
Start-Process "juce/build/MultimodalMusicGen_artefacts/Release/AI Music Generator.exe"

# Start Python server
python main.py --server --no-signals

# Git status
git status

# Commit changes
git add -A && git commit -m "message"

# Push
git push origin master
```

---

## 📝 Session Continuation Checklist

When starting a new chat session:

1. ✅ Reference this file (`knowing.md`)
2. ✅ Reference `TODO.md` for detailed phase plans
3. ✅ Check `git log --oneline -10` for recent changes
4. ✅ Identify which phase you're working on
5. ✅ Build and test before making changes

---

*This document captures the complete state of the AI Music Generator project as of December 11, 2025. Use it to continue development in new chat sessions.*
