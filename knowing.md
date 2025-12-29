# 🎵 AI Music Generator - Project Knowledge Base

> **Reference document for continuing development across chat sessions**  
> **Last Updated**: December 29, 2025

---

## 📋 Table of Contents

1. [Project Vision](#-project-vision)
2. [Architecture Overview](#-architecture-overview)
3. [Completed Phases](#-completed-phases)
4. [Current State](#-current-state)
5. [File Structure](#-file-structure)
6. [Key Technical Details](#-key-technical-details)
7. [Known Issues & Fixes](#-known-issues--fixes)
8. [Research & Best Practices](#-research--best-practices)
9. [Next Steps](#-next-steps)
10. [Build & Run Instructions](#-build--run-instructions)
11. [Quick Reference](#-quick-reference)

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
| Ethiopian instruments | ✅ | Krar, Masenqo, Begena, Kebero |
| Instrument shaper | ✅ | Pro-Q3 style spectrum editor |

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

### Ethiopian Instruments (Physical Modeling)
| Instrument | Algorithm | Key Parameters |
|------------|-----------|----------------|
| **Krar** | Karplus-Strong | decay=0.996, brightness, body resonance |
| **Masenqo** | Stick-slip bow model | expressiveness, bow pressure, vibrato |
| **Begena** | Karplus-Strong + buzz | buzz_amount, leather dampening |
| **Kebero** | Modal synthesis | shell modes, skin tension |

**Frequency Range**: 20-3000 Hz (appropriate for acoustic gut strings)
**Attack Times**: All < 10ms (verified via spectrum analysis)

### Instrument Shaper Tool
- **File**: `instrument_shaper.py`
- **Style**: FabFilter Pro-Q3 single-graph interface
- **Features**: Draggable harmonic nodes, real-time preview, Q adjustment
- **Controls**: Mouse drag, scroll for Q, keyboard shortcuts (1-3, Space, R, S)

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

## 📚 Research & Best Practices

### Audio Processing Architecture (JUCE AudioProcessorGraph)
**Source**: [JUCE AudioProcessorGraph Tutorial](https://juce.com/tutorials/cascading_audio_processors/)

**Key Patterns:**
1. **ProcessorBase** - Base class reducing AudioProcessor boilerplate:
   - Returns 2-channel stereo configuration
   - Empty implementations for non-essential methods
   - Used by all channel strip processors

2. **GainProcessor** - Wraps `juce::dsp::Gain<float>`:
   ```cpp
   dsp::Gain<float> gain;
   gain.setGainDecibels(volumeDb);
   gain.setRampDurationSeconds(0.02);  // 20ms anti-click
   ```

3. **PanProcessor** - Wraps `juce::dsp::Panner<float>`:
   ```cpp
   dsp::Panner<float> panner;
   panner.setRule(dsp::PannerRule::balanced);
   panner.setPan(panValue);  // -1.0 to +1.0
   ```

4. **AudioProcessorGraph** - Node-based routing:
   ```cpp
   AudioProcessorGraph graph;
   auto gainNode = graph.addNode(std::make_unique<GainProcessor>());
   auto panNode = graph.addNode(std::make_unique<PanProcessor>());
   graph.addConnection({{gainNode->nodeID, 0}, {panNode->nodeID, 0}});
   ```

### VU Meter Standards
**Source**: ANSI C16.5-1942 (Volume Unit Meters)

| Parameter | Value | Notes |
|-----------|-------|-------|
| Rise Time | 300ms | Time to reach 99% of step input |
| Fall Time | 300ms | Symmetrical decay |
| Reference Level | 0 VU = +4 dBu | Professional standard |
| Averaging | RMS | Not peak detection |
| Peak Hold | 2000ms | Modern DAW convention |

**Implementation:**
```cpp
// Ballistic filter for VU behavior
float attackCoeff = std::exp(-1.0f / (sampleRate * 0.3f));  // 300ms
float releaseCoeff = std::exp(-1.0f / (sampleRate * 0.3f)); // 300ms

// RMS calculation
float rms = std::sqrt(sumOfSquares / numSamples);
```

### Command Pattern for Undo/Redo
**Source**: Gang of Four Design Patterns

**Architecture:**
- Abstract `Command` base class with `execute()` and `undo()` methods
- `UndoManager` with stack of 50 commands
- Command merging for typing operations
- Transaction support (group related commands)

**Benefits:**
- Clean separation of concerns
- Extensible for new operations
- Supports macro recording

### Plugin Development (VST3/AU)
**Source**: JUCE AudioProcessor documentation

**Key Integration Points:**
- `AudioPlayHead` for DAW transport synchronization
- State serialization via `getStateInformation()` / `setStateInformation()`
- Parameter automation with `AudioProcessorParameter`
- Preset management with chunked XML

---

## 🚀 Next Steps

### Phase 8: Track Mixer (NEXT) - ENHANCED
**Goal**: Professional per-track mixing with AudioProcessorGraph-based routing

**Key Architecture Decisions (from JUCE AudioProcessorGraph tutorial):**
- Use `AudioProcessorGraph` for per-track audio processing chain
- Each track gets: `GainProcessor` → `PanProcessor` → `LevelMeter`
- Master bus with final gain and metering
- `ProcessorBase` pattern reduces boilerplate

**Technical Specs:**
| Parameter | Value | Source |
|-----------|-------|--------|
| Volume Range | -∞ to +12 dB | Industry standard |
| Pan Range | -1.0 to +1.0 | dsp::Panner balanced law |
| VU Ballistics | 300ms attack/release | ANSI C16.5-1942 |
| Peak Hold | 2000ms hold + 300ms decay | Professional metering |
| Gain Ramping | 20ms | Click-free transitions |

**Tasks:**
- ProcessorBase class (reduces AudioProcessor boilerplate)
- GainProcessor wrapping dsp::Gain
- PanProcessor wrapping dsp::Panner
- MixerGraph (AudioProcessorGraph wrapper)
- LevelMeter with VU ballistics
- ChannelStrip component (fader + knob + buttons + meter)
- MixerComponent container with horizontal scrolling
- Solo/mute logic (solo overrides mute)
- State persistence (JSON)

### Phase 9: Instrument Browser
- InstrumentDatabase with scanning and indexing
- CategoryTreeComponent for folder navigation
- InstrumentListComponent with AI match badges
- SamplePreviewComponent with waveform + audition
- Drag-and-drop to tracks

### Phase 10: Project Management
- Command pattern for undo/redo (50 level stack)
- Project class with .mmg format (JSON)
- Auto-save every 2 minutes
- Keyboard shortcuts (Ctrl+S, Ctrl+Z, Ctrl+Y)

### Phase 11: VST3/AU Plugin
- PluginProcessor with host transport sync
- PluginEditor embedding MainComponent
- State serialization
- DAW testing (Ableton, FL Studio, Logic, Cubase, Reaper)

### Phase 12: Advanced Features
- Vocal pitch detection (pYIN algorithm)
- AI harmonization (chord suggestion, bass generation)
- MIDI Learn for hardware controllers

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

*This document captures the complete state of the AI Music Generator project as of December 22, 2025. Use it to continue development in new chat sessions.*

---

## 🤖 For AI Assistants: Continuation Guide

### Overview

This project is a **dual-component music production system** with:
- **Python Backend** (multimodal_gen/) - Music generation engine
- **JUCE Frontend** (juce/) - Professional audio UI

### Python Module API Quick Reference

```python
# Core imports
from multimodal_gen import (
    PromptParser,      # Parse natural language → ParsedPrompt dataclass
    Arranger,          # Create song structure → Arrangement
    MidiGenerator,     # Generate MIDI → mido.MidiFile
    AudioRenderer,     # Render audio → numpy array / WAV
)

# Ethiopian instruments
from multimodal_gen.assets_gen import (
    generate_krar_tone,      # Karplus-Strong plucked lyre
    generate_masenqo_tone,   # Stick-slip bowed fiddle (expressiveness param!)
    generate_begena_tone,    # Bass lyre with buzz
    generate_kebero_hit,     # Modal synthesis drum
    SAMPLE_RATE,             # 44100 Hz
)
```

### Key Data Classes

```python
# ParsedPrompt (from prompt_parser.py)
@dataclass
class ParsedPrompt:
    bpm: float = 120.0
    key: str = 'C'
    scale_type: ScaleType = ScaleType.MINOR
    genre: str = 'trap_soul'
    instruments: List[str]
    drum_elements: List[str]
    mood: str = 'neutral'
    raw_prompt: str = ''

# Arrangement (from arranger.py)
@dataclass
class Arrangement:
    bpm: float
    key: str
    scale: List[int]
    sections: List[SongSection]
    total_bars: int
```

### Usage Pattern

```python
# Full generation pipeline
parser = PromptParser()
parsed = parser.parse("trap soul at 87 BPM in C minor")

arranger = Arranger()
arrangement = arranger.create_arrangement(parsed)

generator = MidiGenerator()
midi_file = generator.generate(arrangement, parsed)
midi_file.save('output.mid')
```

### Ethiopian Instrument Generation

```python
# Krar (plucked lyre) - bright, harp-like
krar = generate_krar_tone(
    frequency=261.63,  # Hz (e.g., C4)
    duration=1.0,      # seconds
    velocity=0.8       # 0.0-1.0
)

# Masenqo (bowed fiddle) - expressive, crying tone
masenqo = generate_masenqo_tone(
    frequency=392.0,
    duration=2.0,
    velocity=0.7,
    expressiveness=0.8  # IMPORTANT: Controls vibrato/bow variation
)

# Begena (bass lyre) - deep, meditative with buzz
begena = generate_begena_tone(
    frequency=130.81,  # Lower frequencies work best
    duration=1.5,
    velocity=0.7
)
```

### Running Tests

```bash
# Run comprehensive test suite
python test_suite.py

# Expected: 19/19 tests pass
```

### Development Environment

```bash
# Activate virtual environment (Windows)
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Key packages: numpy, scipy, mido, python-osc, matplotlib
```

### Common Issues

1. **Pylance "import could not be resolved"** - VS Code not using venv
   - Solution: `pyrightconfig.json` configures venv path
   - Or manually select Python interpreter in VS Code

2. **Masenqo generates empty audio** - Duration too short for bow model
   - Solution: Use `duration >= 0.5` seconds

3. **JUCE build fails** - Missing JUCE path
   - Solution: Set `JUCE_DIR` environment variable or install JUCE

### Files Created This Session

| File | Purpose |
|------|---------|
| `instrument_shaper.py` | Pro-Q3 style spectrum editor for instruments |
| `spectrum_viewer.py` | Simple spectrum analysis tool |
| `test_suite.py` | Comprehensive test suite (19 tests) |
| `pyrightconfig.json` | Pylance/Pyright configuration |

### What to Work On Next

Refer to **Phase 8: Track Mixer** in the Next Steps section above, or:

1. **Improve Ethiopian instruments** - Add more scales (Ambassel, Anchihoye)
2. **Track Mixer** - Per-track volume, pan, mute/solo
3. **Instrument Browser** - Browse and preview sounds
4. **VST3 Plugin** - Package as DAW plugin
