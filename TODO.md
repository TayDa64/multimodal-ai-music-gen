# 🎵 JUCE Integration Implementation Plan

> **Vision**: Transform the Multimodal AI Music Generator from a CLI tool into a professional-grade, real-time music production application with industry-standard UI, visualization, and DAW integration.

---

## 📊 Current State Assessment

### What We Have (Preserve These!)
| Component | Status | Notes |
|-----------|--------|-------|
| `PromptParser` | ✅ Stable | NLP extraction of musical intent |
| `ArrangementEngine` | ✅ Stable | Section-based song structure |
| `MidiGenerator` | ✅ Stable | Humanized MIDI with genre patterns |
| `AudioRenderer` | ✅ Stable | FluidSynth + custom instruments |
| `InstrumentLibrary` | ✅ Stable | AI-powered instrument selection |
| `InstrumentMatcher` | ✅ Stable | Genre/mood-based matching |
| `MpcExporter` | ✅ Stable | MPC project export |
| `AssetsGenerator` | ✅ Stable | Procedural drum synthesis |
| Multi-source support | ✅ Stable | Multiple instrument directories |

### Critical Preservation Strategy
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

## 🏗️ Architecture Design

### System Architecture
```
┌─────────────────────────────────────────────────────────────────────────┐
│                         JUCE APPLICATION                                 │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                         UI LAYER                                    │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────────────┐  │ │
│  │  │Transport │ │ Prompt   │ │ Track    │ │ Visualization         │  │ │
│  │  │Controls  │ │ Input    │ │ Mixer    │ │ (PianoRoll/Waveform)  │  │ │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └───────────┬───────────┘  │ │
│  └───────┼────────────┼────────────┼───────────────────┼──────────────┘ │
│          │            │            │                   │                │
│  ┌───────▼────────────▼────────────▼───────────────────▼──────────────┐ │
│  │                      APPLICATION CORE                               │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │ │
│  │  │ AudioEngine  │  │ MidiEngine   │  │ ProjectState             │  │ │
│  │  │ (Playback)   │  │ (Sequencing) │  │ (Undo/Redo/Save/Load)    │  │ │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘  │ │
│  └────────────────────────────┬───────────────────────────────────────┘ │
│                               │                                         │
│  ┌────────────────────────────▼───────────────────────────────────────┐ │
│  │                    COMMUNICATION BRIDGE                             │ │
│  │  ┌──────────────────────────────────────────────────────────────┐  │ │
│  │  │ OSC Client (Port 9000 → Python)  |  OSC Server (Port 9001)   │  │ │
│  │  │ • /generate {prompt, bpm, key}   |  • /progress {percent}    │  │ │
│  │  │ • /analyze {path}                |  • /complete {midi_path}  │  │ │
│  │  │ • /instruments {paths}           |  • /error {message}       │  │ │
│  │  └──────────────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────┬───────────────────────────────────────┘ │
└───────────────────────────────┼─────────────────────────────────────────┘
                                │ OSC over UDP
                                │
┌───────────────────────────────▼─────────────────────────────────────────┐
│                         PYTHON BACKEND                                   │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                      OSC SERVER MODE                                │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │ │
│  │  │ OSC Receiver │→ │ Request      │→ │ Background Worker        │  │ │
│  │  │ (Port 9000)  │  │ Router       │  │ (ThreadPool)             │  │ │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘  │ │
│  │                                               │                     │ │
│  │  ┌────────────────────────────────────────────▼──────────────────┐ │ │
│  │  │              EXISTING PYTHON MODULES (UNCHANGED)               │ │ │
│  │  │  PromptParser → ArrangementEngine → MidiGenerator              │ │ │
│  │  │       ↓              ↓                    ↓                    │ │ │
│  │  │  InstrumentMatcher ← InstrumentLibrary   Humanizer             │ │ │
│  │  │       ↓                                   ↓                    │ │ │
│  │  │  AudioRenderer ← AssetsGenerator     MpcExporter               │ │ │
│  │  └────────────────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### Message Protocol Specification
```yaml
# Client → Server (JUCE → Python)
/generate:
  prompt: string          # "G-Funk beat with smooth synths"
  bpm: int (optional)     # Override BPM
  key: string (optional)  # Override key "Am", "C#m"
  output_dir: string      # Where to save generated files
  instruments: list       # Paths to instrument libraries
  render_audio: bool      # Whether to render WAV
  export_stems: bool      # Whether to export stems
  export_mpc: bool        # Whether to export MPC project

/analyze:
  path: string            # Path to existing MIDI/audio file

/cancel:
  # No parameters - cancels current generation

/get_instruments:
  paths: list             # Directories to scan

# Server → Client (Python → JUCE)  
/progress:
  step: string            # "parsing", "arranging", "generating", "rendering"
  percent: float          # 0.0 - 1.0
  message: string         # Human-readable status

/complete:
  midi_path: string       # Generated MIDI file path
  audio_path: string      # Generated audio path (if rendered)
  stems_path: string      # Stems directory (if exported)
  mpc_path: string        # MPC project (if exported)
  metadata: object        # {bpm, key, genre, sections, instruments_used}

/error:
  code: int               # Error code
  message: string         # Error description
  recoverable: bool       # Can retry?

/instruments_loaded:
  count: int              # Total instruments found
  categories: object      # {kick: 5, snare: 3, ...}
  sources: object         # {source_path: count, ...}
```

---

## 📅 Implementation Phases

---

### Phase 0: Foundation Research & Prototyping
**Duration**: 2-3 days  
**Risk Level**: 🟡 Medium  
**Goal**: Validate architecture decisions before committing to implementation
**Status**: ✅ COMPLETE (5/5 tasks complete)

#### Tasks
- [x] **0.1** Research JUCE OSC support (`juce_osc` module) ✅ **IMPLEMENTED**
  - ✅ UDP socket handling verified on Windows
  - ✅ JSON payload serialization via `OSCBridge.h/cpp`
  - ✅ Latency expected < 10ms (local UDP)
  - **Implementation**: `juce/Source/Communication/OSCBridge.h/cpp`
  
- [x] **0.2** Prototype Python OSC server ✅ **IMPLEMENTED**
  - ✅ `python-osc` library installed
  - ✅ Full server with request routing in `multimodal_gen/server/osc_server.py`
  - ✅ Bidirectional communication tested
  - **Implementation**: `multimodal_gen/server/` module
  
- [x] **0.3** Research JUCE audio architecture ✅ **IMPLEMENTED**
  - ✅ `AudioDeviceManager` - initialize with `initialiseWithDefaultDevices(0, 2)`
  - ✅ `AudioSource` chain - `AudioSourcePlayer` connected to device manager
  - ✅ `AudioEngine` class with transport controls (play/pause/stop)
  - ✅ Test tone (440Hz) for audio verification
  - ✅ Listener pattern for UI updates
  - **Implementation**: `juce/Source/Audio/AudioEngine.h/cpp`
  - **Integration**: TransportComponent wired to AudioEngine with "Test Tone" checkbox
  
- [x] **0.4** Research JUCE MIDI playback options ✅ **IMPLEMENTED**
  - ✅ JUCE `Synthesiser` with `SimpleSineVoice` (16-voice polyphony)
  - ✅ `MidiFile::readFrom()` + `convertTimestampTicksToSeconds()`
  - ✅ `MidiPlayer` class handles sequencing and synthesis
  - ✅ ADSR envelope on each voice (10ms attack, 100ms decay, 70% sustain, 300ms release)
  - **Implementation**: `juce/Source/Audio/MidiPlayer.h/cpp`, `SimpleSynthVoice.h`
  - **UI**: "Load MIDI" button in transport bar for testing
  - **Future**: Add `SamplerVoice` for sample-based playback
  
- [x] **0.5** Design project file format (.mmg) ✅ **DESIGNED**
  - ✅ Format defined in `Messages.h` structs
  - ✅ `GenerationRequest`, `GenerationResult`, `ProgressUpdate`
  - **Implementation**: `juce/Source/Communication/Messages.h`
  ```json
  {
    "version": "1.0",
    "prompt": "G-Funk beat...",
    "parsed": { "bpm": 87, "key": "Em", ... },
    "midi_path": "relative/path/to.mid",
    "audio_path": "relative/path/to.wav",
    "instruments": [
      { "category": "kick", "name": "Trap-Kick", "path": "...", "source": "..." }
    ],
    "arrangement": [
      { "name": "intro", "start_bar": 0, "length": 4 }
    ],
    "mixer_state": {
      "tracks": [
        { "name": "Drums", "volume": 0.8, "pan": 0.0, "muted": false }
      ]
    }
  }
  ```

#### Success Criteria
- [x] OSC messages round-trip in < 10ms ✅
- [x] Python server handles concurrent requests without blocking ✅
- [x] JUCE can initialize audio and produce test tone ✅ *(Task 0.3 complete)*
- [x] JUCE can load and play a MIDI file with synth ✅ *(Task 0.4 complete)*
- [x] Project file format documented and validated ✅

#### Dependencies
- JUCE 7.x installed ✅
- Python 3.10+ with existing codebase ✅
- `python-osc` package ✅ (installed)

---

### Phase 1: Python Backend OSC Server Mode
**Duration**: 3-4 days  
**Risk Level**: 🟢 Low  
**Goal**: Add OSC server mode to existing Python backend without breaking CLI
**Status**: ✅ COMPLETED

#### Tasks
- [x] **1.1** Add OSC dependencies
  ```
  # requirements.txt additions
  python-osc>=1.8.0
  ```

- [x] **1.2** Create `multimodal_gen/server/osc_server.py`
  ```python
  # Core OSC server with request routing
  class MusicGenOSCServer:
      def __init__(self, recv_port=9000, send_port=9001):
          # Setup dispatcher for incoming messages
          # Setup client for outgoing messages
      
      def on_generate(self, address, *args):
          # Route to generation with progress callbacks
      
      def on_cancel(self):
          # Cancel current generation
      
      def send_progress(self, step, percent, message):
          # Send progress to JUCE client
  ```

- [x] **1.3** Create `multimodal_gen/server/worker.py`
  ```python
  # Background worker for non-blocking generation
  class GenerationWorker:
      def __init__(self, progress_callback):
          self.executor = ThreadPoolExecutor(max_workers=1)
          self.current_task = None
      
      def submit(self, prompt, options):
          # Submit generation task
      
      def cancel(self):
          # Cancel current task
  ```

- [x] **1.4** Add progress callbacks to existing modules
  - Modify `run_generation()` to accept `progress_callback`
  - Emit progress at each step (parsing, arranging, generating, rendering)
  - Ensure callbacks don't break CLI mode (default to no-op)

- [x] **1.5** Add server mode to `main.py`
  ```bash
  # New CLI mode
  python main.py --server --port 9000
  ```

- [x] **1.6** Create server configuration
  ```python
  # multimodal_gen/server/config.py
  DEFAULT_RECV_PORT = 9000
  DEFAULT_SEND_PORT = 9001
  MAX_CONCURRENT_JOBS = 1
  GENERATION_TIMEOUT = 300  # 5 minutes
  ```

- [x] **1.7** Add error handling and recovery
  - Graceful shutdown on SIGINT
  - Automatic restart on unhandled exceptions
  - Client disconnection handling
  - Added `--no-signals` flag for VS Code terminal compatibility

- [ ] **1.8** Write unit tests for OSC server
  - Message parsing tests
  - Progress callback tests
  - Cancellation tests

#### Success Criteria
- [x] `python main.py --server` starts OSC server
- [x] Server responds to `/generate` messages
- [x] Progress updates sent during generation
- [x] CLI mode (`python main.py "prompt"`) still works unchanged
- [x] Server handles malformed messages gracefully

#### File Structure After Phase 1
```
multimodal_gen/
├── server/
│   ├── __init__.py
│   ├── osc_server.py      # OSC message handling
│   ├── worker.py          # Background task execution
│   └── config.py          # Server configuration
├── __init__.py            # Add server exports
└── ... (existing modules unchanged)
```

---

### Phase 2: JUCE Project Foundation
**Duration**: 4-5 days  
**Risk Level**: 🟡 Medium  
**Goal**: Create JUCE application scaffold with build system
**Status**: ✅ COMPLETED

#### Tasks
- [x] **2.1** Create JUCE project structure ✅ **IMPLEMENTED**
  ```
  juce/
  ├── CMakeLists.txt           # CMake build configuration
  ├── build/                   # Build output directory
  ├── Source/
  │   ├── Main.cpp             # Application entry point
  │   ├── MainComponent.h      # Root component header
  │   ├── MainComponent.cpp    # Root component implementation
  │   ├── Application/
  │   │   ├── AppState.h/cpp   # Application state management
  │   │   └── AppConfig.h      # Configuration constants
  │   ├── Audio/               # ✅ Audio engine (Phase 4)
  │   │   ├── AudioEngine.h/cpp    # Audio device management & transport
  │   │   ├── MidiPlayer.h/cpp     # MIDI file playback
  │   │   └── SimpleSynthVoice.h   # Basic synthesizer voice (16-voice)
  │   ├── Communication/
  │   │   ├── Messages.h       # OSC message structures
  │   │   ├── OSCBridge.h/cpp  # JUCE OSC client
  │   │   └── PythonManager.h/cpp  # Python process manager
  │   └── UI/
  │       ├── Theme/
  │       │   ├── ColourScheme.h       # Color palette
  │       │   └── AppLookAndFeel.h/cpp # Custom look and feel
  │       ├── TransportComponent.h/cpp # Transport controls + bar:beat
  │       ├── TimelineComponent.h/cpp  # ✅ Timeline with sections/markers
  │       ├── AudioSettingsDialog.h/cpp # ✅ Audio device settings
  │       ├── PromptPanel.h/cpp        # Prompt input UI
  │       ├── ProgressOverlay.h/cpp    # Progress overlay
  │       └── RecentFilesPanel.h/cpp   # ✅ Generated files list
  └── JuceLibraryCode/         # Auto-generated JUCE headers (in build/)
  ```

- [x] **2.2** Configure CMakeLists.txt
  ```cmake
  cmake_minimum_required(VERSION 3.22)
  project(MultimodalMusicGen VERSION 1.0.0)
  
  # Find JUCE
  find_package(JUCE CONFIG REQUIRED)
  
  # Add executable
  juce_add_gui_app(MultimodalMusicGen
      PRODUCT_NAME "AI Music Generator"
      COMPANY_NAME "Your Name"
      BUNDLE_ID "com.yourname.aimusicgen"
  )
  
  # JUCE modules needed
  target_link_libraries(MultimodalMusicGen PRIVATE
      juce::juce_audio_basics
      juce::juce_audio_devices
      juce::juce_audio_formats
      juce::juce_audio_utils
      juce::juce_core
      juce::juce_graphics
      juce::juce_gui_basics
      juce::juce_gui_extra
      juce::juce_osc
  )
  ```

- [x] **2.3** Create Main.cpp with JUCEApplication
  ```cpp
  class MultimodalMusicGenApplication : public juce::JUCEApplication {
  public:
      const juce::String getApplicationName() override;
      const juce::String getApplicationVersion() override;
      void initialise(const juce::String& commandLine) override;
      void shutdown() override;
      
  private:
      std::unique_ptr<MainWindow> mainWindow;
  };
  ```

- [x] **2.4** Create MainComponent with basic layout
  ```cpp
  class MainComponent : public juce::Component {
  public:
      MainComponent();
      void paint(juce::Graphics& g) override;
      void resized() override;
      
  private:
      // Placeholder areas for future components
      juce::Rectangle<int> transportArea;
      juce::Rectangle<int> promptArea;
      juce::Rectangle<int> mixerArea;
      juce::Rectangle<int> visualizationArea;
  };
  ```

- [x] **2.5** Setup development environment ✅ **IMPLEMENTED**
  - ✅ Visual Studio 2022 project generation (Windows) - `cmake -G "Visual Studio 17 2022"`
  - ⏳ Xcode project generation (macOS - for future)
  - ✅ Build and run verification - `cmake --build . --config Release`

- [x] **2.6** Create application icon and branding
  - 256x256 app icon (placeholder)
  - Splash screen (optional)
  - Color scheme constants (ColourScheme.h)

- [x] **2.7** Implement window management
  - Save/restore window size and position
  - Multi-monitor support
  - Full-screen toggle

#### Success Criteria
- [x] Application builds without errors ✅ (JUCE path auto-detected or configurable via `-DJUCE_DIR`)
- [x] Window opens with basic layout ✅
- [x] Window state persists across restarts ✅
- [x] Clean shutdown without leaks ✅

---

### Phase 3: OSC Communication Bridge
**Duration**: 3-4 days  
**Risk Level**: 🟡 Medium  
**Goal**: Establish reliable bidirectional communication between JUCE and Python
**Status**: ✅ COMPLETED

#### Tasks
- [x] **3.1** Create `Source/Communication/OSCBridge.h/cpp` ✅ **IMPLEMENTED**
  - ✅ Full `OSCBridge` class with listener pattern
  - ✅ `sendGenerate()`, `sendCancel()`, `sendPing()`, `sendShutdown()`
  - ✅ Message handlers: `handleProgress()`, `handleComplete()`, `handleError()`, `handlePong()`
  - **Implementation**: `juce/Source/Communication/OSCBridge.h/cpp` (103+ lines)

- [x] **3.2** Create data structures ✅ **IMPLEMENTED**
  - ✅ `GenerationRequest` struct with all fields (prompt, bpm, key, outputDir, etc.)
  - ✅ `GenerationResult` struct with file paths and metadata
  - ✅ `ProgressUpdate` struct for progress tracking
  - ✅ JSON serialization via `toJSON()` methods
  - **Implementation**: `juce/Source/Communication/Messages.h`

- [x] **3.3** Implement connection management ✅ **IMPLEMENTED**
  - ✅ `connect()` / `disconnect()` methods
  - ✅ `sendPing()` for heartbeat detection
  - ✅ Connection status indicator in UI (status bar)
  - ⏳ Auto-start Python server (partial - PythonManager exists)
  - ⏳ Reconnection with exponential backoff (future enhancement)

- [x] **3.4** Implement message queuing ✅ **BASIC**
  - ✅ Direct message sending when connected
  - ⏳ Queue for disconnected state (future enhancement)
  - ⏳ Timeout handling (future enhancement)

- [x] **3.5** Create Python process manager ✅ **IMPLEMENTED**
  - ✅ `PythonManager` class with `startServer()`, `stopServer()`, `isRunning()`
  - ✅ Auto-detection of Python path (`findPythonExecutable()`)
  - ✅ Process ID tracking
  - **Implementation**: `juce/Source/Communication/PythonManager.h/cpp` (77+ lines)

- [ ] **3.6** Unit test the bridge
  - ⏳ Mock Python server for testing (deferred)
  - ⏳ Message serialization tests (deferred)
  - ⏳ Timeout and error handling tests (deferred)

#### Success Criteria
- [x] JUCE sends `/generate` → Python responds with `/progress` and `/complete` ✅
- [x] Connection status accurately reflected in UI ✅
- [x] Graceful handling of Python server crash ✅ (error callbacks)
- [x] No message loss under normal conditions ✅

---

### Phase 4: Transport & Basic Playback
**Duration**: 5-6 days  
**Risk Level**: 🟠 Medium-High  
**Goal**: Real-time MIDI playback with transport controls
**Status**: ✅ COMPLETED

#### Tasks
- [x] **4.1** Create Audio Engine ✅ **IMPLEMENTED**
  - ✅ `AudioEngine` class with `AudioDeviceManager`, transport controls
  - ✅ `prepareToPlay()`, `releaseResources()`, `getNextAudioBlock()`
  - ✅ `play()`, `pause()`, `stop()`, `setPosition()`, `loadMidiFile()`
  - **Implementation**: `juce/Source/Audio/AudioEngine.h/cpp` (220+ lines)

- [x] **4.2** Implement MIDI Synthesizer ✅ **IMPLEMENTED**
  - ✅ `MidiPlayer` class with JUCE `Synthesiser`
  - ✅ `SimpleSynthVoice` with 16-voice polyphony, ADSR envelopes
  - ✅ MIDI file loading and playback
  - **Implementation**: `juce/Source/Audio/MidiPlayer.h/cpp`, `SimpleSynthVoice.h`

- [x] **4.3** Create Transport Component ✅ **IMPLEMENTED**
  - ✅ Play/Pause/Stop buttons with colored states
  - ✅ Position slider with real-time updates
  - ✅ Time display (M:SS), duration display
  - ✅ BPM slider, Load MIDI button, Test Tone toggle
  - **Implementation**: `juce/Source/UI/TransportComponent.h/cpp` (350+ lines)

- [x] **4.4** Implement position tracking ✅ **IMPLEMENTED**
  - ✅ Accurate sample-based position via `AudioEngine::getPlaybackPosition()`
  - ✅ BPM-aware bar:beat display (shows "Bar:Beat" format)
  - ⏳ Loop region support (future enhancement)

- [x] **4.5** Create timeline component ✅ **IMPLEMENTED**
  - ✅ `TimelineComponent` with section visualization
  - ✅ Beat markers and bar markers with labels
  - ✅ Playhead following playback position
  - ✅ Click-to-seek and drag-to-seek functionality
  - ✅ Time labels along top
  - ✅ Section colors based on name (intro=green, verse=blue, chorus=pink, etc.)
  - **Implementation**: `juce/Source/UI/TimelineComponent.h/cpp` (280+ lines)

- [x] **4.6** Audio device settings ✅ **IMPLEMENTED**
  - ✅ `AudioSettingsDialog` wrapping JUCE's `AudioDeviceSelectorComponent`
  - ✅ Output device selection
  - ✅ Sample rate and buffer size configuration
  - ✅ ASIO support (Windows)
  - ✅ Settings button (⚙) in transport bar
  - **Implementation**: `juce/Source/UI/AudioSettingsDialog.h/cpp` (120+ lines)

#### Success Criteria
- [x] Play/pause/stop work correctly ✅
- [x] Position slider accurate and responsive ✅
- [x] MIDI playback with default synth sounds ✅ (SimpleSynthVoice)
- [x] Timeline shows correct song structure ✅ (sections, beat markers, playhead)
- [x] Seeking works without audio glitches ✅ (click-to-seek via timeline)

---

### Phase 5: Prompt Input & Generation UI
**Duration**: 3-4 days  
**Risk Level**: 🟢 Low  
**Goal**: User can type prompt and trigger generation
**Status**: ✅ COMPLETED

#### Tasks
- [x] **5.1** Create Prompt Panel ✅ **IMPLEMENTED**
  - ✅ `PromptPanel` with text input, genre selector, BPM/duration controls
  - ✅ Generate button, Cancel button
  - ✅ `GenrePreset` struct with name, promptSuffix, suggestedBPM
  - ✅ `AppState::Listener` integration for generation state
  - **Implementation**: `juce/Source/UI/PromptPanel.h/cpp` (200+ lines)

- [x] **5.2** Create Progress Overlay ✅ **IMPLEMENTED**
  - ✅ `ProgressOverlay` with progress bar, status label, cancel button
  - ✅ `AppState::Listener` for progress updates
  - ✅ Modal overlay covering entire window during generation
  - **Implementation**: `juce/Source/UI/ProgressOverlay.h/cpp` (150+ lines)

- [x] **5.3** Implement generation flow ✅ **IMPLEMENTED**
  1. ✅ User types prompt, clicks Generate
  2. ✅ UI disables input, shows progress overlay
  3. ✅ Send `/generate` to Python via OSCBridge
  4. ✅ Receive `/progress` updates, update overlay
  5. ✅ Receive `/complete`, load result, hide overlay
  6. ✅ Auto-load generated MIDI for playback

- [x] **5.4** Add preset prompts ✅ **IMPLEMENTED**
  - ✅ "Boom Bap - 90s hip hop beat" (90 BPM)
  - ✅ "G-Funk - West coast synths" (95 BPM)
  - ✅ "Trap - 808 heavy" (140 BPM)
  - ✅ "Lo-fi - chill beats to study" (75 BPM)
  - ✅ "Drill - dark 808 slides" (140 BPM)
  - ✅ "House - four on the floor" (125 BPM)
  - ⏳ Custom preset saving (future enhancement)

- [x] **5.5** Implement generation history ✅ **IMPLEMENTED**
  - ✅ `RecentFilesPanel` listing output directory contents
  - ✅ Click to load and play previous result
  - ✅ Auto-refresh on new generation
  - **Implementation**: `juce/Source/UI/RecentFilesPanel.h/cpp` (200+ lines)

#### Success Criteria
- [x] User can type prompt and generate ✅
- [x] Progress updates shown in real-time ✅
- [x] Cancel button stops generation ✅
- [x] Generated track auto-loads and plays ✅
- [x] Previous generations accessible ✅ (RecentFilesPanel)

---

### Phase 6: Piano Roll Visualization
**Duration**: 5-6 days  
**Risk Level**: 🟡 Medium  
**Goal**: Visual MIDI display with note information
**Status**: ✅ COMPLETED

#### Tasks
- [x] **6.1** Create Piano Roll Component ✅ **IMPLEMENTED**
  - ✅ `PianoRollComponent` class with MIDI visualization
  - ✅ `MidiNoteEvent` struct for note data storage
  - ✅ AudioEngine::Listener integration for playhead sync
  - ✅ Mouse wheel zoom, click-to-seek, drag scrolling
  - **Implementation**: `juce/Source/UI/Visualization/PianoRollComponent.h/cpp` (700+ lines)

- [x] **6.2** Implement note rendering ✅ **IMPLEMENTED**
  - ✅ Color-code by velocity (darker = louder)
  - ✅ Color-code by track (8-color palette: pink, blue, green, orange, purple, cyan, yellow, red)
  - ✅ Highlight currently playing notes (brighter border)
  - ✅ Show note names on hover (tooltip with name, velocity, duration)

- [x] **6.3** Implement zoom and scroll ✅ **IMPLEMENTED**
  - ✅ Mouse wheel vertical zoom (Ctrl/Cmd + wheel)
  - ✅ Mouse wheel horizontal zoom (Shift + wheel)
  - ✅ Drag to scroll (middle-click or right-drag)
  - ✅ Zoom to fit all notes (`zoomToFit()` method)
  - ✅ Horizontal zoom 0.1x - 10x, Vertical zoom 0.5x - 4x

- [x] **6.4** Add track filtering ✅ **IMPLEMENTED**
  - ✅ Toggle visibility per track (`setTrackVisible()`)
  - ✅ Solo track view (`setTrackSolo()`)
  - ✅ Track color palette for visual distinction
  - ⏳ Track list sidebar (future enhancement)

- [x] **6.5** Create note inspector ✅ **IMPLEMENTED**
  - ✅ Tooltip on hover showing: Note name, Velocity, Duration
  - ✅ Info label in tab bar showing hovered note details
  - ✅ `MidiNoteEvent::getNoteName()` for readable note names (e.g., "C4", "F#5")

- [x] **6.6** Create Visualization Panel ✅ **IMPLEMENTED**
  - ✅ `VisualizationPanel` tabbed container
  - ✅ Tab 1: Piano Roll view
  - ✅ Tab 2: Recent Files view
  - ✅ Listener forwarding for file selection
  - **Implementation**: `juce/Source/UI/VisualizationPanel.h/cpp` (200+ lines)

#### Success Criteria
- [x] All MIDI notes visible ✅
- [x] Playhead follows playback position ✅
- [x] Smooth zoom and scroll ✅
- [x] Track colors distinguishable ✅
- [x] Performance with 1000+ notes ✅ (optimized drawing)

---

### Phase 7: Waveform & Spectrum Visualization
**Duration**: 4-5 days  
**Risk Level**: 🟡 Medium  
**Goal**: Real-time audio visualization
**Status**: ✅ COMPLETED

#### Tasks
- [x] **7.1** Create Waveform Component ✅ **IMPLEMENTED**
  - ✅ Real-time oscilloscope-style display
  - ✅ 4 display modes: Line, Filled, Mirror, Bars
  - ✅ Glow effects with configurable intensity
  - ✅ Lock-free ring buffer (4096 samples)
  - ✅ Catmull-Rom spline interpolation for smooth curves
  - ✅ RMS envelope tracking
  - ✅ 3-point moving average smoothing
  - **Implementation**: `juce/Source/UI/Visualization/WaveformComponent.h/cpp`

- [x] **7.2** Implement real-time processing ✅ **IMPLEMENTED**
  - ✅ 60fps timer-based refresh
  - ✅ Peak metering with proper attack/release ballistics
  - ✅ Stereo mode (L/R split view)
  - ✅ Peak indicators with color coding

- [x] **7.3** Create Spectrum Analyzer ✅ **IMPLEMENTED**
  - ✅ FFT order 11 (2048 samples) with Hann windowing
  - ✅ 4 display modes: Bars, Line, Filled, Glow
  - ✅ Logarithmic/Linear frequency scale option
  - ✅ Peak hold with decay
  - ✅ Frequency labels (Hz/kHz)
  - ✅ **Production-grade envelope follower**:
    - Fast attack (~5ms) for transient response
    - Smooth release (~300ms) for natural decay
  - ✅ **Noise floor gating** at -80dB (prevents flickering)
  - ✅ **Multi-frame averaging** (3-frame buffer for smoother display)
  - **Implementation**: `juce/Source/UI/Visualization/SpectrumComponent.h/cpp`

- [x] **7.4** Add genre-aware color themes ✅ **IMPLEMENTED**
  - ✅ `GenreTheme` struct with comprehensive color sets
  - ✅ 7 genre themes with unique palettes:
    - Default: Blue/Purple
    - G-Funk: Purple/Green/Gold
    - Trap: Red/Black/White
    - Lo-Fi: Orange/Brown/Cream
    - Boom Bap: Gold/Brown/Black
    - Drill: Dark Blue/Black/White
    - House: Cyan/Magenta/Yellow
  - ✅ `GenreThemeManager` for smooth color transitions
  - ✅ Spectrum gradient colors per theme
  - ✅ Waveform glow colors per theme
  - **Implementation**: `juce/Source/UI/Visualization/GenreTheme.h`

- [x] **7.5** Implement view switching ✅ **IMPLEMENTED**
  - ✅ 4 tabbed views: Piano Roll, Waveform, Spectrum, Files
  - ✅ Tab button highlighting for active view
  - ✅ Context-aware info label per tab
  - ✅ `setGenre()` method for theme switching
  - **Implementation**: `juce/Source/UI/VisualizationPanel.h/cpp`

#### Success Criteria
- [x] Waveform displays accurately ✅
- [x] Spectrum responds to audio in real-time ✅ (with envelope follower)
- [x] Theme changes with genre ✅ (7 themes available)
- [x] Smooth 60fps visualization ✅ (no flickering)
- [x] Low CPU usage (< 10%) ✅

---

### Phase 8: Track Mixer
**Duration**: 5-7 days  
**Risk Level**: 🟡 Medium  
**Goal**: Professional per-track mixing with AudioProcessorGraph-based routing
**Status**: 🔲 NOT STARTED

#### Architecture: AudioProcessorGraph-Based Mixer

Based on the JUCE AudioProcessorGraph tutorial, Phase 8 implements a **channel strip architecture** where each MIDI track is processed through a dedicated audio processor chain:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          MIXER AUDIO GRAPH                                   │
│                                                                             │
│  ┌─────────┐    ┌─────────────────────────────────────────────────────┐    │
│  │  MIDI   │    │              CHANNEL STRIP (per track)              │    │
│  │ Track 1 │───▶│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │    │
│  └─────────┘    │  │ Synth/   │→│   Gain   │→│  Panner  │→│ Level  │ │    │
│                 │  │ Sampler  │ │ (Volume) │ │ (Pan)    │ │ Meter  │ │    │
│  ┌─────────┐    │  └──────────┘ └──────────┘ └──────────┘ └────────┘ │    │
│  │  MIDI   │    └─────────────────────────────────────────────────────┘    │
│  │ Track 2 │───▶ ... (same chain per track)                                │
│  └─────────┘                                                               │
│                                     │                                       │
│                                     ▼                                       │
│                         ┌─────────────────────┐                             │
│                         │   MASTER BUS        │                             │
│                         │ ┌───────┐ ┌───────┐ │                             │
│                         │ │ Gain  │→│ Meter │ │──────▶ Audio Output         │
│                         │ └───────┘ └───────┘ │                             │
│                         └─────────────────────┘                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Tasks

- [ ] **8.1** Create ProcessorBase Class (from JUCE tutorial pattern)
  ```cpp
  // Source/Audio/Processors/ProcessorBase.h
  // Base class for all mixer processors, reducing boilerplate
  class ProcessorBase : public juce::AudioProcessor {
  public:
      ProcessorBase()
          : AudioProcessor(BusesProperties()
              .withInput("Input", juce::AudioChannelSet::stereo())
              .withOutput("Output", juce::AudioChannelSet::stereo()))
      {}
      
      // Default implementations for non-essential overrides
      void prepareToPlay(double, int) override {}
      void releaseResources() override {}
      void processBlock(juce::AudioSampleBuffer&, juce::MidiBuffer&) override {}
      
      juce::AudioProcessorEditor* createEditor() override { return nullptr; }
      bool hasEditor() const override { return false; }
      const juce::String getName() const override { return {}; }
      bool acceptsMidi() const override { return false; }
      bool producesMidi() const override { return false; }
      double getTailLengthSeconds() const override { return 0; }
      int getNumPrograms() override { return 0; }
      int getCurrentProgram() override { return 0; }
      void setCurrentProgram(int) override {}
      const juce::String getProgramName(int) override { return {}; }
      void changeProgramName(int, const juce::String&) override {}
      void getStateInformation(juce::MemoryBlock&) override {}
      void setStateInformation(const void*, int) override {}
      
  private:
      JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(ProcessorBase)
  };
  ```

- [ ] **8.2** Create GainProcessor (dsp::Gain wrapper)
  ```cpp
  // Source/Audio/Processors/GainProcessor.h
  class GainProcessor : public ProcessorBase {
  public:
      GainProcessor() { gain.setGainDecibels(0.0f); }
      
      void setGainDecibels(float dB) { gain.setGainDecibels(dB); }
      float getGainDecibels() const { return gain.getGainDecibels(); }
      void setRampDurationSeconds(double duration) { 
          gain.setRampDurationSeconds(duration); 
      }
      
      void prepareToPlay(double sampleRate, int samplesPerBlock) override {
          juce::dsp::ProcessSpec spec { sampleRate, 
              static_cast<juce::uint32>(samplesPerBlock), 2 };
          gain.prepare(spec);
      }
      
      void processBlock(juce::AudioSampleBuffer& buffer, 
                        juce::MidiBuffer&) override {
          juce::dsp::AudioBlock<float> block(buffer);
          juce::dsp::ProcessContextReplacing<float> context(block);
          gain.process(context);
      }
      
      void reset() override { gain.reset(); }
      const juce::String getName() const override { return "Gain"; }
      
  private:
      juce::dsp::Gain<float> gain;
  };
  ```

- [ ] **8.3** Create PanProcessor (dsp::Panner wrapper)
  ```cpp
  // Source/Audio/Processors/PanProcessor.h
  class PanProcessor : public ProcessorBase {
  public:
      PanProcessor() { 
          panner.setRule(juce::dsp::PannerRule::balanced);
          panner.setPan(0.0f); // Center
      }
      
      // Pan: -1.0 (hard left) to +1.0 (hard right)
      void setPan(float newPan) { panner.setPan(newPan); }
      float getPan() const { return currentPan; }
      
      void prepareToPlay(double sampleRate, int samplesPerBlock) override {
          juce::dsp::ProcessSpec spec { sampleRate, 
              static_cast<juce::uint32>(samplesPerBlock), 2 };
          panner.prepare(spec);
      }
      
      void processBlock(juce::AudioSampleBuffer& buffer, 
                        juce::MidiBuffer&) override {
          juce::dsp::AudioBlock<float> block(buffer);
          juce::dsp::ProcessContextReplacing<float> context(block);
          panner.process(context);
      }
      
      void reset() override { panner.reset(); }
      const juce::String getName() const override { return "Pan"; }
      
  private:
      juce::dsp::Panner<float> panner;
      float currentPan = 0.0f;
  };
  ```

- [ ] **8.4** Create MixerGraph (AudioProcessorGraph-based)
  ```cpp
  // Source/Audio/MixerGraph.h
  class MixerGraph {
  public:
      using AudioGraphIOProcessor = juce::AudioProcessorGraph::AudioGraphIOProcessor;
      using Node = juce::AudioProcessorGraph::Node;
      
      MixerGraph() : mainProcessor(new juce::AudioProcessorGraph()) {}
      
      void prepareToPlay(double sampleRate, int samplesPerBlock);
      void processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer& midi);
      void releaseResources();
      
      // Track management
      void addTrack(int trackIndex, const juce::String& name);
      void removeTrack(int trackIndex);
      
      // Per-track controls
      void setTrackVolume(int trackIndex, float dB);
      void setTrackPan(int trackIndex, float pan);
      void setTrackMute(int trackIndex, bool muted);
      void setTrackSolo(int trackIndex, bool soloed);
      
      // Level metering (call from audio thread)
      float getTrackLevel(int trackIndex, int channel) const;
      float getMasterLevel(int channel) const;
      
  private:
      std::unique_ptr<juce::AudioProcessorGraph> mainProcessor;
      
      Node::Ptr audioInputNode;
      Node::Ptr audioOutputNode;
      Node::Ptr midiInputNode;
      Node::Ptr midiOutputNode;
      
      struct ChannelStrip {
          Node::Ptr gainNode;
          Node::Ptr panNode;
          float lastLevel[2] = { 0.0f, 0.0f };
          bool muted = false;
          bool soloed = false;
      };
      std::map<int, ChannelStrip> channelStrips;
      
      void connectAudioNodes();
      void updateGraph();
  };
  ```

- [ ] **8.5** Create LevelMeter Component (VU-style)
  ```cpp
  // Source/UI/Mixer/LevelMeter.h
  // Professional VU meter following industry standards:
  // - 300ms rise/fall time (VU ballistic)
  // - RMS averaging (not peak)
  // - Peak hold with decay (optional)
  // - -60dB to +6dB range
  class LevelMeter : public juce::Component, public juce::Timer {
  public:
      LevelMeter();
      
      // Called from audio thread via lock-free atomic
      void setLevel(float leftRMS, float rightRMS, 
                   float leftPeak = 0.0f, float rightPeak = 0.0f);
      
      void timerCallback() override;  // 60fps refresh
      void paint(juce::Graphics& g) override;
      
      // Display modes
      enum class Mode { VU, Peak, Both };
      void setMode(Mode m) { mode = m; repaint(); }
      
  private:
      // VU ballistics: 300ms attack/release (ANSI standard)
      static constexpr float vuRiseTimeMs = 300.0f;
      static constexpr float vuFallTimeMs = 300.0f;
      
      // Peak hold: 2 second hold, then decay
      static constexpr float peakHoldTimeMs = 2000.0f;
      static constexpr float peakDecayTimeMs = 300.0f;
      
      std::atomic<float> inputLevelL { 0.0f };
      std::atomic<float> inputLevelR { 0.0f };
      std::atomic<float> inputPeakL { 0.0f };
      std::atomic<float> inputPeakR { 0.0f };
      
      float displayLevelL = 0.0f;
      float displayLevelR = 0.0f;
      float peakHoldL = 0.0f;
      float peakHoldR = 0.0f;
      float peakHoldTimeL = 0.0f;
      float peakHoldTimeR = 0.0f;
      
      Mode mode = Mode::Both;
      
      void updateBallistics();
      void drawMeter(juce::Graphics& g, juce::Rectangle<float> bounds, 
                     float level, float peak);
      float dBToPixels(float dB, float height) const;
  };
  ```

- [ ] **8.6** Create ChannelStrip Component
  ```cpp
  // Source/UI/Mixer/ChannelStrip.h
  class ChannelStrip : public juce::Component,
                       public juce::Slider::Listener,
                       public juce::Button::Listener {
  public:
      ChannelStrip(MixerGraph& graph, int trackIndex, 
                   const juce::String& trackName);
      
      void resized() override;
      void paint(juce::Graphics& g) override;
      
      // Update from audio levels
      void setLevels(float left, float right);
      
      class Listener {
      public:
          virtual ~Listener() = default;
          virtual void channelStripChanged(ChannelStrip*) = 0;
      };
      void addListener(Listener* l) { listeners.add(l); }
      
  private:
      MixerGraph& mixerGraph;
      int trackIndex;
      
      juce::Label trackLabel;
      
      // Volume: Vertical fader, -∞ to +12dB
      juce::Slider volumeFader { juce::Slider::LinearVertical, 
                                 juce::Slider::TextBoxBelow };
      
      // Pan: Rotary knob, -1 to +1 (L/R)
      juce::Slider panKnob { juce::Slider::RotaryHorizontalVerticalDrag,
                             juce::Slider::NoTextBox };
      
      // Mute/Solo buttons
      juce::TextButton muteButton { "M" };
      juce::TextButton soloButton { "S" };
      
      // Level meters (stereo)
      LevelMeter levelMeter;
      
      // Listener pattern
      juce::ListenerList<Listener> listeners;
      
      void sliderValueChanged(juce::Slider* slider) override;
      void buttonClicked(juce::Button* button) override;
  };
  ```

- [ ] **8.7** Create MixerComponent (main container)
  ```cpp
  // Source/UI/Mixer/MixerComponent.h
  class MixerComponent : public juce::Component,
                         public ChannelStrip::Listener,
                         public juce::Timer {
  public:
      MixerComponent(MixerGraph& graph);
      
      void setTracks(const juce::Array<TrackInfo>& tracks);
      void resized() override;
      void timerCallback() override;  // Update levels
      
  private:
      MixerGraph& mixerGraph;
      
      juce::OwnedArray<ChannelStrip> channelStrips;
      std::unique_ptr<ChannelStrip> masterStrip;
      
      juce::Viewport scrollView;  // Horizontal scroll for many tracks
      juce::Component stripContainer;
      
      static constexpr int stripWidth = 80;
      static constexpr int masterWidth = 100;
      
      void channelStripChanged(ChannelStrip* strip) override;
  };
  ```

- [ ] **8.8** Implement Solo/Mute Logic
  ```cpp
  // Solo logic: When any track is soloed, mute all non-soloed tracks
  // Mute logic: Track is silent unless it's soloed while muted
  void MixerGraph::updateSoloMuteState() {
      bool anySoloed = false;
      for (const auto& [index, strip] : channelStrips) {
          if (strip.soloed) { anySoloed = true; break; }
      }
      
      for (auto& [index, strip] : channelStrips) {
          bool shouldBeSilent = strip.muted;
          
          if (anySoloed && !strip.soloed) {
              shouldBeSilent = true;  // Silence non-soloed when any is soloed
          }
          if (anySoloed && strip.soloed) {
              shouldBeSilent = false;  // Soloed track plays even if muted
          }
          
          // Apply by bypassing the gain node
          if (strip.gainNode)
              strip.gainNode->setBypassed(shouldBeSilent);
      }
  }
  ```

- [ ] **8.9** Integrate with AudioEngine
  ```cpp
  // Modify AudioEngine to use MixerGraph
  // In AudioEngine::getNextAudioBlock():
  void getNextAudioBlock(const juce::AudioSourceChannelInfo& bufferToFill) {
      // Get audio from MidiPlayer
      midiPlayer.getNextAudioBlock(bufferToFill);
      
      // Process through mixer graph
      juce::MidiBuffer emptyMidi;
      mixerGraph.processBlock(*bufferToFill.buffer, emptyMidi);
      
      // Send to visualization listeners
      notifyVisualizationListeners(*bufferToFill.buffer);
  }
  ```

- [ ] **8.10** Implement Mixer State Persistence
  ```cpp
  // Source/Audio/MixerState.h
  struct TrackMixerState {
      int trackIndex;
      float volumeDb = 0.0f;  // -∞ to +12
      float pan = 0.0f;       // -1 to +1
      bool muted = false;
      bool soloed = false;
  };
  
  struct MixerState {
      juce::Array<TrackMixerState> tracks;
      float masterVolumeDb = 0.0f;
      
      juce::String toJSON() const;
      static MixerState fromJSON(const juce::String& json);
  };
  ```

#### Success Criteria
- [ ] Volume fader changes affect audio output with smooth ramping
- [ ] Pan knob moves sound between L/R channels (balanced panning law)
- [ ] Mute silences track; Solo plays only soloed tracks
- [ ] VU meters respond to audio with correct 300ms ballistics
- [ ] Peak hold indicators show transients with 2s decay
- [ ] Mixer state persists with project save/load
- [ ] No audio glitches during parameter changes (gain ramping)
- [ ] CPU usage remains under 15% with 8-track mixer

#### Technical Specifications
| Parameter | Value | Notes |
|-----------|-------|-------|
| Volume Range | -∞ to +12 dB | Fader with infinity at bottom |
| Pan Range | -1.0 to +1.0 | Balanced panning law |
| VU Ballistics | 300ms attack/release | ANSI C16.5 standard |
| Peak Hold | 2000ms hold + 300ms decay | Industry standard |
| Meter Range | -60 dB to +6 dB | With 0 dB reference line |
| Refresh Rate | 60 fps | Timer-based UI update |
| Gain Ramping | 20ms | Prevent clicks/pops |

#### File Structure After Phase 8
```
juce/Source/
├── Audio/
│   ├── MixerGraph.h/cpp           # NEW: AudioProcessorGraph wrapper
│   ├── MixerState.h/cpp           # NEW: State persistence
│   └── Processors/
│       ├── ProcessorBase.h        # NEW: Base class
│       ├── GainProcessor.h/cpp    # NEW: dsp::Gain wrapper
│       └── PanProcessor.h/cpp     # NEW: dsp::Panner wrapper
└── UI/
    └── Mixer/
        ├── MixerComponent.h/cpp   # NEW: Main mixer container
        ├── ChannelStrip.h/cpp     # NEW: Per-track strip
        └── LevelMeter.h/cpp       # NEW: VU meter component
```

---

### Phase 9: Instrument Browser & Sample Audition
**Duration**: 5-6 days  
**Risk Level**: 🟢 Low  
**Goal**: Browse, preview, and select instruments with AI-powered recommendations
**Status**: 🔲 NOT STARTED (NB Phase 2 UI components created)

#### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      INSTRUMENT BROWSER PANEL                                │
│  ┌───────────────────┬──────────────────────────────────────────────────┐   │
│  │   Category Tree   │              Instrument List                      │   │
│  │  ─────────────── │  ┌────────────────────────────────────────────┐   │   │
│  │  📁 Bass         │  │ 🎵 808-Sub      │ Trap │ ★★★★☆ │ AI Match │   │   │
│  │  📁 Brass        │  │ 🎵 Reese-Bass   │ DnB  │ ★★★☆☆ │          │   │   │
│  │  📁 Drums        │  │ 🎵 Synth-Bass   │ House│ ★★★★★ │ AI Match │   │   │
│  │    ├ 808s        │  │ ...                                         │   │   │
│  │    ├ Kicks       │  └────────────────────────────────────────────┘   │   │
│  │    ├ Snares      │                                                    │   │
│  │    ├ Hihats      │  ┌────────────────────────────────────────────┐   │   │
│  │    └ Claps       │  │           PREVIEW PANEL                     │   │   │
│  │  📁 Keys         │  │  ┌─────────────────────────────────────┐   │   │   │
│  │  📁 Synths       │  │  │    [Waveform Thumbnail]             │   │   │   │
│  │  📁 Strings      │  │  │    ▶ Play  ■ Stop                   │   │   │   │
│  │  📁 FX           │  │  └─────────────────────────────────────┘   │   │   │
│  │                  │  │  Name: 808-Sub-C.wav                       │   │   │
│  │  ─────────────── │  │  Key: C2  |  BPM: --  |  Duration: 1.2s    │   │   │
│  │  🔍 Search...    │  │  Source: instruments/bass/808s/            │   │   │
│  └───────────────────┴──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Tasks

- [ ] **9.1** Create InstrumentDatabase
  ```cpp
  // Source/Instruments/InstrumentDatabase.h
  struct InstrumentInfo {
      juce::String name;
      juce::String path;
      juce::String category;       // "kick", "snare", "bass", etc.
      juce::String genre;          // AI-detected genre affinity
      juce::String detectedKey;    // Pitch-detected root note
      double detectedBPM = 0.0;    // Tempo-detected (for loops)
      float duration = 0.0f;       // Length in seconds
      int sampleRate = 44100;
      float aiMatchScore = 0.0f;   // 0.0-1.0 AI recommendation
      juce::Image waveformThumbnail;
  };
  
  class InstrumentDatabase {
  public:
      void scanDirectories(const juce::StringArray& paths);
      juce::Array<InstrumentInfo> getByCategory(const juce::String& category);
      juce::Array<InstrumentInfo> search(const juce::String& query);
      juce::Array<InstrumentInfo> getAIRecommendations(
          const juce::String& genre, 
          const juce::String& mood,
          int maxResults = 10);
      
  private:
      juce::HashMap<juce::String, juce::Array<InstrumentInfo>> categoryIndex;
      void analyzeFile(const juce::File& file);
      void generateThumbnail(InstrumentInfo& info);
  };
  ```

- [ ] **9.2** Create CategoryTreeComponent
  ```cpp
  // Source/UI/InstrumentBrowser/CategoryTreeComponent.h
  class CategoryTreeComponent : public juce::TreeView {
  public:
      CategoryTreeComponent(InstrumentDatabase& db);
      
      class Listener {
      public:
          virtual ~Listener() = default;
          virtual void categorySelected(const juce::String& category) = 0;
      };
      void addListener(Listener* l) { listeners.add(l); }
      
  private:
      class CategoryItem : public juce::TreeViewItem {
          // Expandable tree items for category hierarchy
      };
  };
  ```

- [ ] **9.3** Create InstrumentListComponent
  ```cpp
  // Source/UI/InstrumentBrowser/InstrumentListComponent.h
  class InstrumentListComponent : public juce::ListBox,
                                  public juce::ListBoxModel {
  public:
      void setInstruments(const juce::Array<InstrumentInfo>& instruments);
      
      // ListBoxModel overrides
      int getNumRows() override;
      void paintListBoxItem(int rowNumber, juce::Graphics& g,
                            int width, int height, bool selected) override;
      
      class Listener {
      public:
          virtual ~Listener() = default;
          virtual void instrumentSelected(const InstrumentInfo& info) = 0;
          virtual void instrumentDoubleClicked(const InstrumentInfo& info) = 0;
      };
      
  private:
      juce::Array<InstrumentInfo> instruments;
      void drawAIMatchBadge(juce::Graphics& g, const InstrumentInfo& info,
                            juce::Rectangle<float> bounds);
  };
  ```

- [ ] **9.4** Create SamplePreviewComponent
  ```cpp
  // Source/UI/InstrumentBrowser/SamplePreviewComponent.h
  class SamplePreviewComponent : public juce::Component,
                                 public juce::Button::Listener {
  public:
      SamplePreviewComponent(juce::AudioDeviceManager& deviceManager);
      
      void setInstrument(const InstrumentInfo& info);
      void play();
      void stop();
      
  private:
      juce::AudioThumbnail thumbnail;
      juce::TextButton playButton { "▶" };
      juce::TextButton stopButton { "■" };
      juce::Label nameLabel, keyLabel, bpmLabel, durationLabel;
      
      // Audio preview engine (separate from main playback)
      juce::AudioTransportSource transport;
      std::unique_ptr<juce::AudioFormatReaderSource> readerSource;
  };
  ```

- [ ] **9.5** Create InstrumentBrowserPanel (main container)
  ```cpp
  // Source/UI/InstrumentBrowser/InstrumentBrowserPanel.h
  class InstrumentBrowserPanel : public juce::Component,
                                 public CategoryTreeComponent::Listener,
                                 public InstrumentListComponent::Listener {
  public:
      InstrumentBrowserPanel(InstrumentDatabase& db, 
                             juce::AudioDeviceManager& deviceManager);
      
      void refresh();
      void setGenreFilter(const juce::String& genre);
      
      class Listener {
      public:
          virtual ~Listener() = default;
          virtual void instrumentChosen(const InstrumentInfo& info) = 0;
      };
      
  private:
      InstrumentDatabase& database;
      CategoryTreeComponent categoryTree;
      InstrumentListComponent instrumentList;
      SamplePreviewComponent previewPanel;
      juce::TextEditor searchBox;
      
      void categorySelected(const juce::String& category) override;
      void instrumentSelected(const InstrumentInfo& info) override;
      void instrumentDoubleClicked(const InstrumentInfo& info) override;
  };
  ```

- [ ] **9.6** Integrate with OSCBridge for AI Recommendations
  ```cpp
  // Request AI recommendations from Python backend
  // /get_instrument_recommendations
  void requestAIRecommendations(const juce::String& genre, 
                                 const juce::String& mood) {
      oscBridge.send("/get_instrument_recommendations", 
                     genre.toStdString(), 
                     mood.toStdString());
  }
  
  // Handle response
  // /instrument_recommendations [{name, path, score}, ...]
  void handleInstrumentRecommendations(const juce::StringArray& recommendations) {
      // Update instrument list with AI match scores
  }
  ```

- [ ] **9.7** Add Drag-and-Drop Support
  ```cpp
  // InstrumentListComponent as drag source
  juce::var getDragSourceDescription(const juce::SparseSet<int>& selectedRows) override {
      // Return instrument path for drop onto piano roll or track
  }
  
  // PianoRollComponent as drop target
  bool isInterestedInDragSource(const SourceDetails& details) override;
  void itemDropped(const SourceDetails& details) override {
      // Add instrument sample at drop position
  }
  ```

#### Success Criteria
- [ ] All instruments from configured paths displayed in tree
- [ ] Search filters instruments by name, category, genre
- [ ] Preview plays audio with waveform visualization
- [ ] AI recommendations sorted by match score
- [ ] Drag-and-drop to piano roll/track functional
- [ ] Key/BPM detection displayed for relevant samples
- [ ] Smooth scrolling with 1000+ instruments

#### File Structure After Phase 9
```
juce/Source/
├── Instruments/
│   ├── InstrumentDatabase.h/cpp    # NEW: Sample catalog
│   ├── InstrumentAnalyzer.h/cpp    # NEW: Key/BPM detection
│   └── WaveformThumbnailCache.h    # NEW: Thumbnail caching
└── UI/
    └── InstrumentBrowser/
        ├── InstrumentBrowserPanel.h/cpp  # NEW: Main container
        ├── CategoryTreeComponent.h/cpp   # NEW: Folder tree
        ├── InstrumentListComponent.h/cpp # NEW: Sample list
        └── SamplePreviewComponent.h/cpp  # NEW: Audio preview

---

### Phase 10: Project Management & Undo/Redo
**Duration**: 4-5 days  
**Risk Level**: 🟢 Low  
**Goal**: Complete project lifecycle with undo/redo using Command Pattern

#### Architecture: Command Pattern for Undo/Redo

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          COMMAND PATTERN                                     │
│                                                                             │
│  User Action         Command Object           Undo Stack                    │
│  ───────────────────────────────────────────────────────────────────────── │
│  Set Track Volume → VolumeChangeCommand ───┐                                │
│                     ├── previousValue     ├──▶ [cmd1, cmd2, cmd3, ...]    │
│                     ├── newValue          │     ▲                          │
│                     ├── execute()         │     │ undo()                   │
│                     └── undo()            │     │                          │
│                                           │                                 │
│  Move MIDI Note   → NoteMoveCommand ──────┘    Redo Stack                  │
│                     ├── noteId                  [cmd4, cmd5, ...]          │
│                     ├── oldPosition                                        │
│                     ├── newPosition                                        │
│                     └── execute() / undo()                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Tasks

- [ ] **10.1** Create Command Interface & Manager
  ```cpp
  // Source/Project/Command.h
  class Command {
  public:
      virtual ~Command() = default;
      virtual void execute() = 0;
      virtual void undo() = 0;
      virtual juce::String getDescription() const = 0;
      
      // For command merging (e.g., continuous slider movements)
      virtual bool mergeWith(const Command* other) { return false; }
      virtual juce::int64 getCommandId() const { return 0; }
  };
  
  // Source/Project/UndoManager.h
  class UndoManager {
  public:
      void execute(std::unique_ptr<Command> cmd);
      bool undo();   // Returns false if nothing to undo
      bool redo();   // Returns false if nothing to redo
      
      bool canUndo() const { return !undoStack.empty(); }
      bool canRedo() const { return !redoStack.empty(); }
      
      juce::String getUndoDescription() const;
      juce::String getRedoDescription() const;
      
      void clear();
      void beginTransaction(const juce::String& name);
      void endTransaction();  // Groups commands into single undo step
      
  private:
      std::vector<std::unique_ptr<Command>> undoStack;
      std::vector<std::unique_ptr<Command>> redoStack;
      
      static constexpr size_t maxUndoLevels = 50;
      
      std::vector<std::unique_ptr<Command>> currentTransaction;
      juce::String transactionName;
      bool inTransaction = false;
  };
  ```

- [ ] **10.2** Create Specific Commands
  ```cpp
  // Source/Project/Commands/MixerCommands.h
  class VolumeChangeCommand : public Command {
  public:
      VolumeChangeCommand(MixerGraph& mixer, int track, 
                          float oldVolume, float newVolume);
      void execute() override;
      void undo() override;
      juce::String getDescription() const override { 
          return "Change Volume"; 
      }
      bool mergeWith(const Command* other) override;
      juce::int64 getCommandId() const override;
  };
  
  class PanChangeCommand : public Command { /* ... */ };
  class MuteToggleCommand : public Command { /* ... */ };
  class SoloToggleCommand : public Command { /* ... */ };
  
  // Source/Project/Commands/ProjectCommands.h
  class BpmChangeCommand : public Command { /* ... */ };
  class KeyChangeCommand : public Command { /* ... */ };
  ```

- [ ] **10.3** Create Project Class
  ```cpp
  // Source/Project/Project.h
  class Project {
  public:
      // File operations
      bool saveAs(const juce::File& file);
      bool save();  // Save to current location
      bool load(const juce::File& file);
      bool isModified() const;
      juce::File getCurrentFile() const;
      
      // Project file format (.mmg - Multimodal Music Generator)
      // Uses JSON internally for human readability
      
      // Project data
      juce::String prompt;
      juce::String genre;
      float bpm = 120.0f;
      juce::String key = "C";
      
      GenerationResult generationResult;
      MixerState mixerState;
      juce::Array<Section> arrangement;
      
      // Instrument assignments
      struct InstrumentAssignment {
          int trackIndex;
          juce::String instrumentPath;
          juce::String instrumentName;
      };
      juce::Array<InstrumentAssignment> instrumentAssignments;
      
      // Undo/redo
      UndoManager& getUndoManager() { return undoManager; }
      
  private:
      juce::File currentFile;
      bool modified = false;
      UndoManager undoManager;
      
      juce::String toJSON() const;
      static Project fromJSON(const juce::String& json);
  };
  ```

- [ ] **10.4** Create Project File Format (.mmg)
  ```json
  // Example: my_track.mmg
  {
    "version": "1.0",
    "created": "2025-12-22T14:30:00Z",
    "modified": "2025-12-22T15:45:00Z",
    
    "generation": {
      "prompt": "G-Funk beat with smooth synths",
      "genre": "g_funk",
      "bpm": 87,
      "key": "Em",
      "scale": "minor"
    },
    
    "files": {
      "midi": "relative/path/to/track.mid",
      "audio": "relative/path/to/track.wav",
      "stems": "relative/path/to/stems/"
    },
    
    "arrangement": [
      {"name": "intro", "startBar": 0, "lengthBars": 4},
      {"name": "verse", "startBar": 4, "lengthBars": 8}
    ],
    
    "mixer": {
      "master": {"volume": 0.0},
      "tracks": [
        {"name": "Drums", "volume": -3.0, "pan": 0.0, "muted": false},
        {"name": "Bass", "volume": -6.0, "pan": 0.1, "muted": false}
      ]
    },
    
    "instruments": [
      {"track": 0, "path": "instruments/drums/kicks/808.wav"},
      {"track": 1, "path": "instruments/bass/synth/reese.wav"}
    ]
  }
  ```

- [ ] **10.5** Create File Dialogs
  ```cpp
  // Source/UI/Dialogs/ProjectDialogs.h
  class ProjectDialogs {
  public:
      // Returns selected file, or empty if cancelled
      static juce::File showSaveAsDialog(juce::Component* parent);
      static juce::File showOpenDialog(juce::Component* parent);
      
      // Export dialogs
      static juce::File showExportWavDialog(juce::Component* parent);
      static juce::File showExportMpcDialog(juce::Component* parent);
      static juce::File showExportStemsDialog(juce::Component* parent);
      
      // Unsaved changes dialog
      enum class SaveResult { Save, DontSave, Cancel };
      static SaveResult showUnsavedChangesDialog(juce::Component* parent);
  };
  ```

- [ ] **10.6** Create Recent Projects Menu
  ```cpp
  // Source/Application/RecentProjects.h
  class RecentProjects {
  public:
      void addRecentFile(const juce::File& file);
      juce::Array<juce::File> getRecentFiles(int maxCount = 10) const;
      void clearRecentFiles();
      
      // Persistence
      void saveToProperties(juce::PropertiesFile& props);
      void loadFromProperties(const juce::PropertiesFile& props);
      
  private:
      juce::StringArray recentPaths;
      static constexpr int maxRecentFiles = 10;
  };
  ```

- [ ] **10.7** Implement Auto-Save
  ```cpp
  // Source/Application/AutoSave.h
  class AutoSave : public juce::Timer {
  public:
      AutoSave(Project& project, int intervalMs = 120000); // 2 minutes
      
      void enable(bool enabled);
      bool isEnabled() const;
      
      void timerCallback() override;
      
      // Recovery on crash
      static juce::File getAutoSaveFile();
      static bool hasAutoSaveRecovery();
      static void clearAutoSave();
      
  private:
      Project& project;
      juce::File autoSaveFile;
  };
  ```

- [ ] **10.8** Add Keyboard Shortcuts
  ```cpp
  // In MainComponent or Application
  void registerKeyboardShortcuts() {
      // File operations
      addKeyCommand(juce::KeyPress('s', juce::ModifierKeys::ctrlModifier, 0), 
                    "Save", [this] { project.save(); });
      addKeyCommand(juce::KeyPress('s', juce::ModifierKeys::ctrlModifier | 
                                        juce::ModifierKeys::shiftModifier, 0),
                    "Save As", [this] { saveAs(); });
      addKeyCommand(juce::KeyPress('o', juce::ModifierKeys::ctrlModifier, 0),
                    "Open", [this] { openProject(); });
      
      // Undo/Redo
      addKeyCommand(juce::KeyPress('z', juce::ModifierKeys::ctrlModifier, 0),
                    "Undo", [this] { project.getUndoManager().undo(); });
      addKeyCommand(juce::KeyPress('y', juce::ModifierKeys::ctrlModifier, 0),
                    "Redo", [this] { project.getUndoManager().redo(); });
      addKeyCommand(juce::KeyPress('z', juce::ModifierKeys::ctrlModifier | 
                                        juce::ModifierKeys::shiftModifier, 0),
                    "Redo", [this] { project.getUndoManager().redo(); });
  }
  ```

#### Success Criteria
- [ ] Project saves all state to .mmg file (JSON format)
- [ ] Project loads and restores complete state
- [ ] Undo/redo works for mixer changes (Ctrl+Z/Ctrl+Y)
- [ ] Recent projects menu shows last 10 projects
- [ ] Auto-save creates recovery file every 2 minutes
- [ ] Crash recovery prompts to restore auto-save on launch
- [ ] Keyboard shortcuts work globally

#### File Structure After Phase 10
```
juce/Source/
├── Project/
│   ├── Project.h/cpp           # NEW: Project state management
│   ├── UndoManager.h/cpp       # NEW: Undo/redo stack
│   ├── Command.h               # NEW: Command interface
│   └── Commands/
│       ├── MixerCommands.h/cpp # NEW: Mixer undo commands
│       └── ProjectCommands.h   # NEW: Project undo commands
├── Application/
│   ├── RecentProjects.h/cpp    # NEW: Recent files tracking
│   └── AutoSave.h/cpp          # NEW: Auto-save timer
└── UI/
    └── Dialogs/
        └── ProjectDialogs.h/cpp # NEW: File dialogs

---

### Phase 11: VST3/AU Plugin Format
**Duration**: 7-10 days  
**Risk Level**: 🔴 High  
**Goal**: Package application as DAW plugin with full DAW integration

#### Architecture: Plugin Wrapper

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DAW HOST                                        │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                    Plugin Instance                                      │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐  │ │
│  │  │                 PluginProcessor : AudioProcessor                  │  │ │
│  │  │  ┌───────────────┐  ┌────────────────┐  ┌────────────────────┐   │  │ │
│  │  │  │ AudioEngine   │  │ MixerGraph     │  │ OSCBridge          │   │  │ │
│  │  │  │ (Playback)    │  │ (Per-track)    │  │ (→Python Backend)  │   │  │ │
│  │  │  └───────────────┘  └────────────────┘  └────────────────────┘   │  │ │
│  │  │                                                                   │  │ │
│  │  │  Transport Sync: Read host BPM, position, playing state          │  │ │
│  │  │  MIDI Sync: Forward host MIDI to internal synth                  │  │ │
│  │  └──────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                         │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐  │ │
│  │  │                 PluginEditor : AudioProcessorEditor               │  │ │
│  │  │  ┌────────────────────────────────────────────────────────────┐  │  │ │
│  │  │  │              MainComponent (Embedded)                       │  │  │ │
│  │  │  │  Same UI as standalone, but resizable within DAW window    │  │  │ │
│  │  │  └────────────────────────────────────────────────────────────┘  │  │ │
│  │  └──────────────────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Tasks

- [ ] **11.1** Create PluginProcessor
  ```cpp
  // Source/Plugin/PluginProcessor.h
  class MusicGenPluginProcessor : public juce::AudioProcessor {
  public:
      MusicGenPluginProcessor();
      ~MusicGenPluginProcessor() override;
      
      // AudioProcessor overrides
      void prepareToPlay(double sampleRate, int samplesPerBlock) override;
      void releaseResources() override;
      void processBlock(juce::AudioBuffer<float>&, juce::MidiBuffer&) override;
      
      // Editor
      juce::AudioProcessorEditor* createEditor() override;
      bool hasEditor() const override { return true; }
      
      // State
      void getStateInformation(juce::MemoryBlock& destData) override;
      void setStateInformation(const void* data, int sizeInBytes) override;
      
      // Transport sync
      void syncToHostTransport();
      
      // Plugin info
      const juce::String getName() const override { return "AI Music Generator"; }
      bool acceptsMidi() const override { return true; }
      bool producesMidi() const override { return true; }
      bool isMidiEffect() const override { return false; }
      double getTailLengthSeconds() const override { return 0.0; }
      
      // Programs (presets)
      int getNumPrograms() override { return 1; }
      int getCurrentProgram() override { return 0; }
      void setCurrentProgram(int) override {}
      const juce::String getProgramName(int) override { return {}; }
      void changeProgramName(int, const juce::String&) override {}
      
      // Bus layout
      bool isBusesLayoutSupported(const BusesLayout& layouts) const override;
      
      // Access for editor
      AudioEngine& getAudioEngine() { return *audioEngine; }
      OSCBridge& getOSCBridge() { return *oscBridge; }
      AppState& getAppState() { return *appState; }
      
  private:
      std::unique_ptr<AudioEngine> audioEngine;
      std::unique_ptr<OSCBridge> oscBridge;
      std::unique_ptr<AppState> appState;
      std::unique_ptr<Project> project;
      
      // Host transport tracking
      juce::Optional<juce::AudioPlayHead::PositionInfo> lastPosition;
      void updateFromHostTransport(const juce::AudioPlayHead::PositionInfo& pos);
  };
  ```

- [ ] **11.2** Create PluginEditor
  ```cpp
  // Source/Plugin/PluginEditor.h
  class MusicGenPluginEditor : public juce::AudioProcessorEditor,
                                public juce::Timer {
  public:
      MusicGenPluginEditor(MusicGenPluginProcessor& processor);
      ~MusicGenPluginEditor() override;
      
      void paint(juce::Graphics&) override;
      void resized() override;
      void timerCallback() override;
      
      // Resizable within DAW constraints
      bool isResizable() const { return true; }
      
  private:
      MusicGenPluginProcessor& processorRef;
      
      // Embed the main component
      std::unique_ptr<MainComponent> mainComponent;
      
      // Plugin-specific sizing
      static constexpr int defaultWidth = 1200;
      static constexpr int defaultHeight = 800;
      static constexpr int minWidth = 800;
      static constexpr int minHeight = 600;
  };
  ```

- [ ] **11.3** Implement Host Transport Sync
  ```cpp
  // In PluginProcessor::processBlock()
  void MusicGenPluginProcessor::processBlock(juce::AudioBuffer<float>& buffer,
                                              juce::MidiBuffer& midiMessages) {
      // Sync with host transport
      if (auto* playHead = getPlayHead()) {
          if (auto pos = playHead->getPosition()) {
              updateFromHostTransport(*pos);
          }
      }
      
      // Forward MIDI to internal synth
      if (midiMessages.getNumEvents() > 0) {
          audioEngine->getMidiPlayer().addMidiEvents(midiMessages);
      }
      
      // Process audio through our engine
      audioEngine->processBlock(buffer, midiMessages);
  }
  
  void MusicGenPluginProcessor::updateFromHostTransport(
      const juce::AudioPlayHead::PositionInfo& pos) {
      
      // Sync BPM
      if (pos.getBpm().hasValue()) {
          double hostBpm = *pos.getBpm();
          if (hostBpm != appState->getBpm()) {
              appState->setBpm(static_cast<float>(hostBpm));
          }
      }
      
      // Sync playback position
      if (pos.getTimeInSamples().hasValue()) {
          auto samples = *pos.getTimeInSamples();
          // Convert to our internal position format
      }
      
      // Sync play/stop state
      if (pos.getIsPlaying()) {
          if (!audioEngine->isPlaying()) {
              audioEngine->play();
          }
      } else {
          if (audioEngine->isPlaying()) {
              audioEngine->pause();
          }
      }
  }
  ```

- [ ] **11.4** Implement State Save/Restore
  ```cpp
  void MusicGenPluginProcessor::getStateInformation(juce::MemoryBlock& destData) {
      // Serialize project state to XML
      auto state = project->toJSON();
      juce::MemoryOutputStream stream(destData, false);
      stream.writeString(state);
  }
  
  void MusicGenPluginProcessor::setStateInformation(const void* data, 
                                                     int sizeInBytes) {
      // Deserialize project state
      juce::MemoryInputStream stream(data, static_cast<size_t>(sizeInBytes), false);
      auto state = stream.readString();
      project = Project::fromJSON(state);
      
      // Restore audio engine state
      if (!project->generationResult.midiPath.isEmpty()) {
          audioEngine->loadMidiFile(juce::File(project->generationResult.midiPath));
      }
  }
  ```

- [ ] **11.5** Add Sidechain Input (Future: Vocal Analysis)
  ```cpp
  // In PluginProcessor constructor
  MusicGenPluginProcessor::MusicGenPluginProcessor()
      : AudioProcessor(BusesProperties()
          .withInput("Input", juce::AudioChannelSet::stereo(), true)
          .withOutput("Output", juce::AudioChannelSet::stereo(), true)
          .withInput("Sidechain", juce::AudioChannelSet::mono(), false)) // Optional sidechain
  {
      // Sidechain can be used for:
      // - Vocal pitch detection → melody generation
      // - Beat detection → tempo sync
      // - Ducking/sidechain compression
  }
  ```

- [ ] **11.6** Update CMakeLists.txt for Plugin Build
  ```cmake
  # CMakeLists.txt additions for plugin
  
  # Plugin target (VST3 + AU)
  juce_add_plugin(MusicGenPlugin
      PLUGIN_MANUFACTURER_CODE MGen
      PLUGIN_CODE MMGn
      FORMATS VST3 AU Standalone
      PRODUCT_NAME "AI Music Generator"
      COMPANY_NAME "Your Name"
      IS_SYNTH TRUE
      NEEDS_MIDI_INPUT TRUE
      NEEDS_MIDI_OUTPUT TRUE
      IS_MIDI_EFFECT FALSE
      EDITOR_WANTS_KEYBOARD_FOCUS TRUE
  )
  
  target_sources(MusicGenPlugin PRIVATE
      Source/Plugin/PluginProcessor.cpp
      Source/Plugin/PluginEditor.cpp
      # ... all other sources
  )
  
  target_link_libraries(MusicGenPlugin PRIVATE
      juce::juce_audio_basics
      juce::juce_audio_devices
      juce::juce_audio_formats
      juce::juce_audio_plugin_client
      juce::juce_audio_processors
      juce::juce_audio_utils
      juce::juce_core
      juce::juce_graphics
      juce::juce_gui_basics
      juce::juce_gui_extra
      juce::juce_osc
      juce::juce_dsp
  )
  ```

- [ ] **11.7** Test in Major DAWs
  
  | DAW | Platform | Test Cases |
  |-----|----------|------------|
  | **Ableton Live** | Win/Mac | Load, transport sync, parameter automation |
  | **FL Studio** | Win | Load, MIDI routing, mixer integration |
  | **Logic Pro** | Mac | AU validation, transport, state save |
  | **Cubase/Nuendo** | Win/Mac | VST3 validation, automation |
  | **Reaper** | Win/Mac/Linux | Load, multi-instance, state |
  | **Pro Tools** | Win/Mac | AAX (future), basic load test |
  
  **Test Checklist:**
  - [ ] Plugin loads without crash
  - [ ] UI renders correctly at various sizes
  - [ ] Transport syncs with host BPM
  - [ ] Play/Stop syncs with host transport
  - [ ] State saves and restores correctly
  - [ ] Multiple instances work simultaneously
  - [ ] CPU usage is reasonable
  - [ ] No audio dropouts under load

- [ ] **11.8** Create Plugin Installers
  ```
  Windows:
  └── Installer.exe (Inno Setup or WiX)
      ├── VST3: C:\Program Files\Common Files\VST3\
      └── Standalone: C:\Program Files\AI Music Generator\
  
  macOS:
  └── Installer.pkg (pkgbuild)
      ├── VST3: /Library/Audio/Plug-Ins/VST3/
      ├── AU: /Library/Audio/Plug-Ins/Components/
      └── Standalone: /Applications/
  
  Linux:
  └── .deb / .rpm / AppImage
      └── VST3: ~/.vst3/
  ```

#### Success Criteria
- [ ] Plugin loads in Ableton, FL Studio, Logic, Cubase, Reaper
- [ ] Transport syncs correctly (BPM, position, play/stop)
- [ ] State persists across DAW sessions
- [ ] UI is responsive and resizable
- [ ] No audio dropouts or crashes
- [ ] Multiple instances work correctly
- [ ] Installer works cleanly on Win/Mac

#### Technical Specifications
| Parameter | Value |
|-----------|-------|
| Plugin Format | VST3, AU (Mac), Standalone |
| Min JUCE Version | 7.0 |
| Default Size | 1200 x 800 |
| Min Size | 800 x 600 |
| Resizable | Yes |
| MIDI I/O | Yes |
| Sidechain | Optional mono input |

#### File Structure After Phase 11
```
juce/Source/
└── Plugin/
    ├── PluginProcessor.h/cpp    # NEW: AudioProcessor implementation
    └── PluginEditor.h/cpp       # NEW: AudioProcessorEditor wrapper

juce/Installer/
├── Windows/
│   └── installer.iss            # Inno Setup script
└── macOS/
    └── installer.pkgproj        # Packages project

---

### Phase 12: Advanced Features & AI Enhancements
**Duration**: Ongoing  
**Risk Level**: 🟡 Variable  
**Goal**: Vocal-to-orchestration, AI harmonization, collaborative features

#### 12.1 Vocal Input & Melody Transcription
**Goal**: Transform sung/hummed melodies into MIDI and harmonized arrangements

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      VOCAL → MIDI PIPELINE                                   │
│                                                                             │
│  🎤 Audio Input    →    Pitch Detection    →    MIDI Transcription         │
│  (Microphone/File)      (pYIN Algorithm)        (Note Events)               │
│                              ↓                        ↓                      │
│                         Onset Detection         Quantization                │
│                         (Transients)           (Beat Grid Snap)             │
│                              ↓                        ↓                      │
│                         Segmentation              AI Harmony                │
│                        (Phrase Detection)        (Chord Suggestion)         │
│                                                       ↓                      │
│                                              Accompaniment Generation        │
│                                              (Bass, Chords, Drums)           │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Tasks:**
- [ ] **12.1.1** Implement Pitch Detection (Python)
  ```python
  # multimodal_gen/vocal/pitch_detector.py
  import librosa
  
  class VocalPitchDetector:
      def __init__(self, sr=44100):
          self.sr = sr
          
      def detect_pitches(self, audio: np.ndarray) -> List[PitchEvent]:
          """
          Uses pYIN algorithm for monophonic pitch detection.
          Returns list of (time_seconds, midi_note, confidence)
          """
          f0, voiced_flag, voiced_prob = librosa.pyin(
              audio, fmin=60, fmax=800, sr=self.sr
          )
          return self._convert_to_events(f0, voiced_prob)
      
      def transcribe_to_midi(self, audio: np.ndarray) -> mido.MidiFile:
          """Convert detected pitches to MIDI file."""
          pass
  ```

- [ ] **12.1.2** Implement Real-time Pitch Display (JUCE)
  ```cpp
  // Source/UI/VocalInput/PitchDisplayComponent.h
  class PitchDisplayComponent : public juce::Component, 
                                 public juce::Timer {
  public:
      void setCurrentPitch(float midiNote, float confidence);
      void paint(juce::Graphics& g) override;
      
  private:
      float currentPitch = 0.0f;
      float confidence = 0.0f;
      juce::Path pitchHistory;  // Rolling display
  };
  ```

- [ ] **12.1.3** Integrate with OSC for Processing
  ```python
  # OSC messages for vocal processing
  # /vocal/start_listening - Begin pitch capture
  # /vocal/stop_listening - End capture, process
  # /vocal/pitch {midi_note, confidence} - Real-time pitch updates
  # /vocal/transcribed {midi_path} - Transcription complete
  ```

#### 12.2 AI Harmonization
**Goal**: Generate chord progressions and accompaniment from melody

**Tasks:**
- [ ] **12.2.1** Chord Suggestion Engine
  ```python
  # multimodal_gen/harmony/chord_suggester.py
  class ChordSuggester:
      def suggest_chords(self, melody_notes: List[int], 
                         key: str, scale: str) -> List[Chord]:
          """
          Suggests chord progression based on:
          - Melody note patterns
          - Key and scale
          - Genre-specific voice leading rules
          """
          pass
      
      def harmonize_melody(self, melody: MidiTrack, 
                           chord_progression: List[Chord]) -> MidiFile:
          """
          Generates full arrangement:
          - Bass line following chord roots
          - Chord voicings (piano/synth)
          - Optional counter-melodies
          """
          pass
  ```

- [ ] **12.2.2** Bass Line Generator
  ```python
  # multimodal_gen/harmony/bass_generator.py
  class BassLineGenerator:
      def generate(self, chords: List[Chord], 
                   genre: str, bpm: float) -> MidiTrack:
          """
          Generates bass line that:
          - Follows chord root movement
          - Applies genre-specific patterns (walking, syncopated, etc.)
          - Humanizes timing and velocity
          """
          pass
  ```

#### 12.3 Real-time Suggestion Engine
**Goal**: Context-aware musical suggestions during composition

**Tasks:**
- [ ] **12.3.1** Next Section Predictor
  ```python
  # Suggest next section based on current arrangement
  class SectionPredictor:
      def predict_next(self, current_sections: List[Section], 
                       genre: str) -> List[SectionSuggestion]:
          """
          Based on genre conventions:
          - After intro → verse
          - After verse → chorus or pre-chorus
          - After chorus → verse2 or bridge
          """
          pass
  ```

- [ ] **12.3.2** Instrument Variation Suggester
  ```python
  # Suggest variations on current instruments
  class VariationSuggester:
      def suggest_variations(self, current_instruments: List[Instrument],
                             mood_change: str) -> List[Instrument]:
          """
          Suggests instrument swaps for:
          - Energy increase (add brass, strings)
          - Energy decrease (remove drums, add pads)
          - Genre fusion (add unexpected instruments)
          """
          pass
  ```

#### 12.4 Collaborative Features
**Goal**: Share and collaborate on projects

**Tasks:**
- [ ] **12.4.1** Project Export/Import
  ```python
  # Export project as shareable archive
  def export_project_archive(project: Project, output_path: str) -> str:
      """
      Creates .mmgz archive containing:
      - Project JSON
      - MIDI files
      - Audio stems
      - Custom instrument samples (optional)
      """
      pass
  ```

- [ ] **12.4.2** Community Preset Sharing
  ```cpp
  // Future: Cloud-based preset sharing
  class PresetCloud {
  public:
      void uploadPreset(const GenrePreset& preset);
      std::vector<GenrePreset> searchPresets(const juce::String& query);
      void downloadPreset(const juce::String& presetId);
  };
  ```

#### 12.5 Hardware Integration
**Goal**: MIDI controller and MPC hardware support

**Tasks:**
- [ ] **12.5.1** MIDI Learn for Parameters
  ```cpp
  // Source/MIDI/MidiLearn.h
  class MidiLearn {
  public:
      void startLearning(juce::Slider* targetSlider);
      void handleMidiMessage(const juce::MidiMessage& msg);
      
      // Save/load mappings
      void saveMappings(const juce::File& file);
      void loadMappings(const juce::File& file);
      
  private:
      std::map<int, juce::Slider*> ccToSlider;  // CC# → Slider mapping
  };
  ```

- [ ] **12.5.2** Pad Controller Support
  ```cpp
  // Support for drum pads (MPC, Launchpad, etc.)
  class PadController {
  public:
      void handleNoteOn(int note, int velocity);
      void handleNoteOff(int note);
      
      // Map pads to instrument triggers
      void mapPadToInstrument(int padIndex, const InstrumentInfo& inst);
  };
  ```

- [ ] **12.5.3** MPC Hardware Sync
  ```python
  # Direct MPC hardware communication
  # - Tempo sync via MIDI clock
  # - Program export to MPC SD card
  # - Sample transfer
  ```

#### Success Criteria (Variable by Feature)

| Feature | Priority | Complexity | Success Metric |
|---------|----------|------------|----------------|
| Pitch Detection | High | Medium | 95% accuracy on clean vocals |
| Melody Transcription | High | Medium | Usable MIDI from hummed melody |
| AI Harmonization | Medium | High | Musically sensible chord suggestions |
| Bass Generation | Medium | Medium | Genre-appropriate bass lines |
| Next Section Prediction | Low | Low | 3+ relevant suggestions |
| MIDI Learn | Medium | Low | Any CC maps to any slider |
| Pad Support | Low | Low | Basic pad triggering works |

#### File Structure After Phase 12
```
multimodal_gen/
├── vocal/
│   ├── pitch_detector.py      # NEW: pYIN pitch detection
│   ├── transcriber.py         # NEW: Audio → MIDI
│   └── onset_detector.py      # NEW: Note onset detection
├── harmony/
│   ├── chord_suggester.py     # NEW: AI chord suggestions
│   ├── bass_generator.py      # NEW: Bass line generation
│   └── harmonizer.py          # NEW: Full harmonization
└── collaboration/
    └── project_archive.py     # NEW: Project sharing format

juce/Source/
├── MIDI/
│   ├── MidiLearn.h/cpp        # NEW: MIDI CC learning
│   └── PadController.h/cpp    # NEW: Pad input handling
└── UI/
    └── VocalInput/
        └── PitchDisplayComponent.h/cpp  # NEW: Real-time pitch display
```

---

## 🔧 Development Environment Setup

### Required Tools
- [ ] **JUCE 7.x** - Already installed ✅
- [ ] **CMake 3.22+** - For build system
- [ ] **Visual Studio 2022** - Windows builds
- [ ] **Python 3.10+** - Backend ✅
- [ ] **Git** - Version control ✅

### Build Instructions (To Be Written)
```bash
# Clone repository
git clone https://github.com/TayDa64/multimodal-ai-music-gen.git
cd multimodal-ai-music-gen

# Build JUCE application
cd juce
mkdir build && cd build
cmake ..
cmake --build . --config Release

# Run application
./MultimodalMusicGen
```

### Directory Structure After Completion
```
multimodal-ai-music-gen/
├── juce/
│   ├── CMakeLists.txt
│   ├── Source/
│   │   ├── Main.cpp
│   │   ├── MainComponent.h/cpp
│   │   ├── Audio/
│   │   │   ├── AudioEngine.h/cpp
│   │   │   └── MidiSynthesizer.h/cpp
│   │   ├── Communication/
│   │   │   ├── OSCBridge.h/cpp
│   │   │   ├── Messages.h
│   │   │   └── PythonManager.h/cpp
│   │   ├── UI/
│   │   │   ├── TransportComponent.h/cpp
│   │   │   ├── PromptPanel.h/cpp
│   │   │   ├── ProgressOverlay.h/cpp
│   │   │   ├── TimelineComponent.h/cpp
│   │   │   ├── Visualization/
│   │   │   │   ├── PianoRollComponent.h/cpp
│   │   │   │   ├── WaveformComponent.h/cpp
│   │   │   │   └── SpectrumComponent.h/cpp
│   │   │   └── Mixer/
│   │   │       ├── MixerComponent.h/cpp
│   │   │       ├── ChannelStrip.h/cpp
│   │   │       └── LevelMeter.h/cpp
│   │   ├── Project/
│   │   │   └── Project.h/cpp
│   │   └── Plugin/
│   │       ├── PluginProcessor.h/cpp
│   │       └── PluginEditor.h/cpp
│   └── Resources/
├── multimodal_gen/
│   ├── server/                    # NEW: OSC server
│   │   ├── __init__.py
│   │   ├── osc_server.py
│   │   ├── worker.py
│   │   └── config.py
│   ├── prompt_parser.py
│   ├── arrangement_engine.py
│   ├── midi_generator.py
│   ├── instrument_manager.py
│   ├── audio_renderer.py
│   └── ... (existing modules)
├── main.py                        # Add --server mode
├── requirements.txt               # Add python-osc
├── TODO.md                        # This file
└── README.md
```

---

## 📊 Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| OSC latency too high | Low | High | Fallback to WebSocket or shared memory |
| FluidSynth integration complex | Medium | Medium | Use JUCE Synthesiser with samples instead |
| Plugin validation fails in DAWs | Medium | High | Test early and often, follow JUCE best practices |
| Cross-platform audio issues | Low | Medium | Use JUCE's abstraction, test on all platforms |
| Python server crashes | Medium | Low | Auto-restart, graceful degradation |
| UI performance with large MIDI | Medium | Medium | Virtualization, level-of-detail rendering |

---

## � Known Issues & Fixes

### Issue #1: Application Crash on Startup (Access Violation 0xC0000005)
**Date Fixed**: December 10, 2025  
**Severity**: Critical  
**Symptoms**: 
- App crashes ~4-5 seconds after launch
- Exit code: -1073741819 (0xC0000005 - STATUS_ACCESS_VIOLATION)
- Crash occurs in both Debug and Release builds
- No visible window or immediate crash depending on timing

**Root Cause**: 
Null pointer dereferences in `MainComponent::resized()`. The method directly accessed child component pointers (`transportBar->`, `promptPanel->`, `progressOverlay->`) without null checks. JUCE's `resized()` can be called before child components are fully initialized, or during component destruction.

**Original Code (Buggy)**:
```cpp
void MainComponent::resized()
{
    // ...
    transportBar->setBounds(bounds.removeFromTop(transportHeight));  // CRASH if null
    promptPanel->setBounds(contentArea.removeFromLeft(promptPanelWidth));  // CRASH if null
    progressOverlay->setBounds(getLocalBounds());  // CRASH if null
}
```

**Fixed Code**:
```cpp
void MainComponent::resized()
{
    // ...
    if (transportBar)
        transportBar->setBounds(bounds.removeFromTop(transportHeight));
    if (promptPanel)
        promptPanel->setBounds(contentArea.removeFromLeft(promptPanelWidth));
    if (progressOverlay)
        progressOverlay->setBounds(getLocalBounds());
}
```

**Additional Fix Applied**:
Static initialization order fiasco in `ColourScheme.h` - changed `static const juce::Colour` to `inline const juce::Colour` for C++17 compatibility:
```cpp
// Before (buggy):
static const juce::Colour background = juce::Colour(0xFF1a1a2e);

// After (fixed):
inline const juce::Colour background { 0xFF1a1a2e };
```

**Debugging Process**:
1. Systematic component isolation testing
2. Disabled timers to rule out timing issues
3. Created minimal test window to isolate dependencies
4. Progressively re-enabled components to identify culprit
5. Clean rebuild after deleting build directory to clear cache

**Lessons Learned**:
- Always null-check `unique_ptr` members before dereferencing in JUCE component callbacks
- `resized()`, `paint()`, and timer callbacks can fire at unexpected times during component lifecycle
- Static `juce::Colour` objects can cause static initialization order issues - use `inline const` in C++17
- Debug builds may mask issues due to different memory initialization patterns
- When debugging JUCE apps, test with minimal components and progressively add complexity

**Files Modified**:
- `juce/Source/MainComponent.cpp` - Added null checks in `resized()`
- `juce/Source/UI/Theme/ColourScheme.h` - Changed `static const` to `inline const`

---

### Issue #2: Duplicate "Disconnected" Status Indicators
**Date Fixed**: December 11, 2025  
**Severity**: Minor (UX)  
**Symptoms**: 
- "Disconnected" text appeared in two locations simultaneously
- Top-right corner of TransportComponent showed connection status
- Bottom-left status bar in MainComponent also showed connection status
- Confusing UI with redundant information

**Root Cause**: 
Both `TransportComponent` and `MainComponent` had their own connection status indicators. The `TransportComponent` had a `connectionIndicator` label that was being updated via `AppState::Listener::onConnectionStatusChanged()`, while `MainComponent::paint()` drew a status bar at the bottom with the same information.

**Solution**:
Removed the duplicate `connectionIndicator` from `TransportComponent` entirely, keeping only the single authoritative status bar in `MainComponent`. This follows Nielsen's heuristic of "Consistency and Standards" - single source of truth for system status.

**Changes Applied**:
```cpp
// TransportComponent.cpp - Removed from resized():
// connectionIndicator.setBounds(...);  // REMOVED

// TransportComponent.cpp - Removed from constructor:
// connectionIndicator.setVisible(true);  // Changed to false

// TransportComponent.cpp - Removed listener callback:
// void onConnectionStatusChanged(bool connected) override { ... }  // Emptied
```

**Files Modified**:
- `juce/Source/UI/TransportComponent.cpp` - Removed connectionIndicator visibility and layout

---

### Issue #3: Prompt Panel Locked After Generation Completes
**Date Fixed**: December 11, 2025  
**Severity**: High (Functional)  
**Symptoms**: 
- After generating a song, the ProgressOverlay closes correctly
- User clicks "Close" on the overlay
- Prompt panel remains disabled (grayed out)
- Cannot type new prompts or click "Generate" button
- App requires restart to generate another song

**Root Cause**: 
Notification flow mismatch between `AppState` methods. The `MainComponent::onGenerationComplete()` was calling `appState.setGenerating(false)` which triggers `onGenerationFinished()` callback. However, `PromptPanel` was listening to `onGenerationCompleted(const juce::File&)` which is a *different* callback that requires an explicit `appState.notifyGenerationCompleted(file)` call.

The two similar-sounding but different callbacks:
- `onGenerationFinished()` - Called when `setGenerating(false)` is invoked
- `onGenerationCompleted(const juce::File&)` - Called when `notifyGenerationCompleted(file)` is invoked

`PromptPanel::onGenerationCompleted()` was responsible for re-enabling the UI controls, but it was never being called.

**Original Code (Buggy)**:
```cpp
// MainComponent.cpp - onGenerationComplete():
void MainComponent::onGenerationComplete(const juce::String& midiPath, const juce::String& audioPath)
{
    // ... handle files ...
    appState.setGenerating(false);  // Only triggers onGenerationFinished()
    // MISSING: appState.notifyGenerationCompleted(outputFile);
}
```

**Fixed Code**:
```cpp
// MainComponent.cpp - onGenerationComplete():
void MainComponent::onGenerationComplete(const juce::String& midiPath, const juce::String& audioPath)
{
    // ... handle files ...
    
    // CRITICAL: Notify listeners FIRST so PromptPanel re-enables
    appState.notifyGenerationCompleted(outputFile);
    
    // THEN update generating state
    appState.setGenerating(false);
}

// Also added for error handling:
void MainComponent::onGenerationError(const juce::String& message)
{
    appState.notifyGenerationError(message);  // NEW
    appState.setGenerating(false);
}

// And for cancellation:
void MainComponent::onCancelClicked()
{
    appState.notifyGenerationError("Cancelled by user");  // NEW
    appState.setGenerating(false);
}
```

**Debugging Process**:
1. Applied Nielsen's 10 Usability Heuristics to evaluate UI
2. Traced the listener callback chain from AppState to PromptPanel
3. Identified two different notification methods with confusingly similar names
4. Added DBG logging to PromptPanel callbacks to verify they were being called
5. Fixed notification order (notify THEN change state)

**Lessons Learned**:
- When using listener patterns, carefully distinguish between similar callback methods
- `notifyXxx()` methods vs `setXxx()` methods may trigger different listener callbacks
- Always call notification methods BEFORE changing state to ensure listeners see consistent state
- Add DBG logging during development to trace callback execution
- Nielsen's "Visibility of System Status" heuristic - UI should always reflect true state

**Files Modified**:
- `juce/Source/MainComponent.cpp` - Added `notifyGenerationCompleted()` and `notifyGenerationError()` calls
- `juce/Source/UI/PromptPanel.cpp` - Added DBG logging, improved state reset in callbacks

---

### Issue #4: Status Bar Height Inconsistency
**Date Fixed**: December 11, 2025  
**Severity**: Minor (Visual)  
**Symptoms**: 
- Status bar at bottom of window had inconsistent height
- Text appeared cut off or poorly centered

**Root Cause**: 
The `MainComponent::paint()` method used a hardcoded height of 20px for the status bar, which was too small for the font size being used.

**Fixed Code**:
```cpp
// MainComponent.cpp - paint():
auto statusBarHeight = 24;  // Changed from 20
auto statusBar = bounds.removeFromBottom(statusBarHeight);
```

**Files Modified**:
- `juce/Source/MainComponent.cpp` - Increased status bar height to 24px

---

## 📈 Milestones

| Milestone | Target Date | Description |
|-----------|-------------|-------------|
| M1: Communication | +1 week | OSC bridge working bidirectionally |
| M2: Basic Playback | +2 weeks | Transport + MIDI playback |
| M3: Generation UI | +3 weeks | Prompt → Generate → Play flow |
| M4: Visualization | +4 weeks | Piano roll + waveform |
| M5: Full App | +6 weeks | Mixer + browser + projects |
| M6: Plugin | +8 weeks | VST3 working in DAWs |
| M7: Release 1.0 | +10 weeks | Polished, tested, documented |

---

## ✅ Current Sprint

### Sprint 1: Foundation (Phases 0-2) ✅ COMPLETE
**Goal**: Establish communication infrastructure and application foundation

- [x] Research JUCE OSC module ✅
- [x] Prototype Python OSC server ✅
- [x] Design message protocol ✅
- [x] Implement `multimodal_gen/server/` module ✅
- [x] Add `--server` mode to `main.py` ✅
- [ ] Write tests for server (deferred)

### Sprint 2: UI Polish & Integration (Current)
**Goal**: Refine UI based on usability heuristics, ensure smooth generation flow

- [x] Fix UI rendering issues (component visibility) ✅
- [x] Remove duplicate status indicators ✅
- [x] Fix prompt panel lockout after generation ✅
- [x] Apply Nielsen's 10 Usability Heuristics ✅
- [x] Improve status bar messaging ✅
- [ ] Test full end-to-end workflow
- [ ] Add error recovery flows

---

## 🎯 Bonus Features Implemented (Beyond Original Plan)

The following features were implemented ahead of schedule:

| Feature | Status | Phase Originally Planned |
|---------|--------|-------------------------|
| AudioEngine with device management | ✅ Complete | Phase 4 |
| MidiPlayer with synthesis | ✅ Complete | Phase 4 |
| SimpleSynthVoice (16-voice polyphony) | ✅ Complete | Phase 4 |
| RecentFilesPanel (generation history) | ✅ Complete | Phase 5 |
| Progress overlay with cancel | ✅ Complete | Phase 5 |
| Genre selector in PromptPanel | ✅ Complete | Phase 5 |
| Duration control | ✅ Complete | Phase 5 |
| Connection status indicator | ✅ Complete | Phase 3 |

---

*Last Updated: December 29, 2025*

---

## 🧠 NotebookLM Strategic Roadmap

### Vision: From "Vending Machine" to "Sous-Chef"

Based on comprehensive NotebookLM synthesis of the codebase and industry best practices, this roadmap transforms the AI Music Generator from a one-shot generation tool into an intelligent music production assistant.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    TRANSFORMATION ARCHITECTURE                               │
│                                                                             │
│   CURRENT STATE                           TARGET STATE                       │
│   "Vending Machine"                       "Sous-Chef"                        │
│   ─────────────────                       ────────────                        │
│   • Prompt → One-shot result              • Continuous collaboration         │
│   • Limited user control                  • Real-time parameter tweaking     │
│   • Regenerate to change                  • Non-destructive adjustments      │
│   • Black box processing                  • Transparent AI decisions         │
│                                                                             │
│   ┌─────────────┐      ┌─────────────┐      ┌─────────────────────────────┐ │
│   │ Text Prompt │ ───▶ │ AI Backend  │ ───▶ │ Final Output (immutable)   │ │
│   └─────────────┘      └─────────────┘      └─────────────────────────────┘ │
│                                                                             │
│                              ▼  BECOMES  ▼                                  │
│                                                                             │
│   ┌─────────────┐      ┌─────────────┐      ┌─────────────────────────────┐ │
│   │ UI Controls │ ◀──▶ │ AI Backend  │ ◀──▶ │ Live Preview (adjustable)  │ │
│   └─────────────┘      └─────────────┘      └─────────────────────────────┘ │
│         │                    │                          │                   │
│         │                    │                          │                   │
│         ▼                    ▼                          ▼                   │
│   Genre Selector      Real-time Params         Drag-Drop Arrangement       │
│   Instrument Browser  Humanization Sliders     Section Restructuring       │
│   FX Chain Toggles    Density Controls         Export Options              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### NB Phase 1: Core Backend & Genre Intelligence ✅ COMPLETE
**Status**: IMPLEMENTED  
**Goal**: Foundational genre-aware generation system

#### Completed Components:
- [x] **genres.json** - Comprehensive genre template system with 10 genres
  - trap, trap_soul, g_funk, rnb, lofi, boom_bap, house, drill, ethiopian_traditional, eskista
  - Mandatory/forbidden/recommended elements per genre
  - Spectral profiles (sub_bass_presence, brightness, warmth, 808_character)
  - FX chains per bus (master, drums, bass, melodic)
  - Humanization profiles (tight, natural, loose, live)

- [x] **genre_intelligence.py** - Python module for genre template access
  - `get_genre_template(genre)` - Full template retrieval
  - `is_element_allowed(genre, element)` - Validation API
  - `get_fx_chain(genre, bus)` - FX chain retrieval
  - `validate_prompt_against_genre()` - Prompt validation
  - `to_json_manifest()` - JSON export for JUCE UI

- [x] **instrument_manager.py** - Enhanced with AI-powered selection
  - `InstrumentAnalyzer` - Spectral fingerprinting
  - `InstrumentMatcher` - Genre/mood matching
  - `InstrumentLibrary` - Discovery and caching

#### File Structure (NB Phase 1):
```
multimodal_gen/
├── genres.json              # ✅ Genre DNA templates
├── genre_intelligence.py    # ✅ Python API for genre templates
└── instrument_manager.py    # ✅ AI-powered instrument selection
```

---

### NB Phase 2: JUCE Framework & UI Standardization
**Status**: ✅ IN PROGRESS (Core components created)  
**Goal**: Industry-standard UI with genre-aware components

#### Completed Components:

- [x] **GenreSelector.h/cpp** - ✅ CREATED
  - Top-level genre selection with theme colors
  - `GenreTemplate` struct with full configuration (BPM range, swing, FX chains)
  - `Listener` pattern for genre change notifications
  - JSON parsing for dynamic genre loading
  - 10 hardcoded defaults matching genres.json
  **Implementation**: `juce/Source/UI/GenreSelector.h/cpp`

- [x] **InstrumentBrowserPanel.h/cpp** - ✅ CREATED
  - `InstrumentInfo` struct (id, name, category, subcategory, key, BPM, duration, tags)
  - `InstrumentCategory` struct with subcategories
  - `InstrumentCard` component with hover/selection states
  - `InstrumentListComponent` with scrollable card list
  - `CategoryTabBar` with 7 default categories (drums, bass, keys, synths, strings, fx, ethiopian)
  - `SamplePreviewPanel` with waveform thumbnail and playback
  - Search filtering and genre filtering
  - Click-to-select, double-click-to-activate
  **Implementation**: `juce/Source/UI/InstrumentBrowserPanel.h/cpp`

- [x] **FXChainPanel.h/cpp** - ✅ CREATED
  - `FXUnit` struct with type, parameters, JSON serialization
  - `FXChainPreset` struct for genre-aware chains
  - `FXUnitComponent` with type-specific colors and icons
  - `FXChainStrip` for each bus (master, drums, bass, melodic)
  - `FXParameterPanel` with dynamic sliders per FX type
  - Genre preset selector with 10 presets
  - Add/remove FX, enable/disable per unit
  - Full JSON import/export
  **Implementation**: `juce/Source/UI/FXChainPanel.h/cpp`

- [x] **CMakeLists.txt** - ✅ UPDATED
  - Added GenreSelector.h/cpp, InstrumentBrowserPanel.h/cpp, FXChainPanel.h/cpp

#### Planned Integration:
- [ ] Integrate GenreSelector into MainComponent/PromptPanel
- [ ] Wire InstrumentBrowserPanel to OSC instrument requests
- [ ] Connect FXChainPanel to Python FX processing
- [ ] Add theme color propagation to visualization components

---

### NB Phase 3: Plugin & Extension Integration
**Status**: PLANNED  
**Goal**: Professional plugin scanning and loading

#### Planned Features:
- [ ] VST3/AU plugin scanning and cataloging
- [ ] Plugin preset browsing per genre
- [ ] Instrument plugin hosting (sample libraries)
- [ ] Effect plugin hosting (third-party FX)

```cpp
// Source/Plugins/PluginScanner.h
class PluginScanner {
public:
    void scanVST3Directories();
    void scanAUPlugins();  // macOS only
    
    juce::Array<PluginDescription> getInstruments();
    juce::Array<PluginDescription> getEffects();
    
    // Plugin instantiation
    std::unique_ptr<AudioPluginInstance> loadPlugin(
        const PluginDescription& desc);
};
```

---

### NB Phase 4: Bidirectional Control & Streaming
**Status**: PLANNED  
**Goal**: Real-time parameter manipulation with live preview

#### Enhanced OSC Protocol:
```yaml
# Real-time parameter updates (JUCE → Python)
/params/set:
  param_name: string    # "swing_amount", "hihat_density", etc.
  value: float          # 0.0 - 1.0 normalized
  
/params/batch_update:
  params: json          # {"swing": 0.15, "velocity_var": 0.12, ...}

# Real-time feedback (Python → JUCE)
/preview/update:
  section: string       # Which section changed
  midi_data: bytes      # Regenerated MIDI for preview
  
/suggestion:
  type: string          # "next_section", "instrument_swap", "density_change"
  options: json         # Array of suggestions with scores
```

#### Humanization Controls:
```cpp
// Source/UI/HumanizationPanel.h
class HumanizationPanel : public juce::Component {
    // Sliders mapped to genres.json humanization_profiles
    juce::Slider velocityVariationSlider;   // 0.05 - 0.25
    juce::Slider timingVariationSlider;     // 0.01 - 0.08
    
    // Presets from humanization_profiles
    juce::ComboBox profileSelector;  // tight, natural, loose, live
};
```

---

### NB Phase 5: Industry-Standard Export & Humanization
**Status**: PLANNED  
**Goal**: Professional export formats with enhanced humanization

#### MPC 3.x Compatibility:
```python
# multimodal_gen/mpc_exporter.py enhancements
class MPCExporter:
    def export_mpc3x_program(self, project):
        """
        MPC 3.x .xpm format with:
        - Pad assignments per layer
        - Velocity switching zones
        - FX chain per pad (if MPC supports)
        - Q-Link assignments for parameters
        """
        pass
```

#### Additional Export Formats:
- [ ] Ableton Live Set (.als) - With arrangement and mixer
- [ ] FL Studio Project (.flp) - Via MIDI + stems
- [ ] Logic Pro X (.logicx) - Via AAF/OMF
- [ ] Stems package (WAV + JSON metadata)

---

### Implementation Priority Matrix

| Phase | Component | Priority | Effort | Dependencies |
|-------|-----------|----------|--------|--------------|
| NB1 | genres.json | ✅ DONE | ✅ | None |
| NB1 | genre_intelligence.py | ✅ DONE | ✅ | genres.json |
| NB1 | instrument_manager.py | ✅ DONE | ✅ | None |
| NB2 | GenreSelector | HIGH | Low | genres.json |
| NB2 | InstrumentBrowserPanel | HIGH | Medium | instrument_manager |
| NB2 | InstrumentCard | MEDIUM | Low | InstrumentBrowserPanel |
| NB2 | FXChainPanel | MEDIUM | Medium | genres.json |
| NB3 | PluginScanner | LOW | High | None |
| NB4 | Real-time params | MEDIUM | High | OSC protocol |
| NB4 | HumanizationPanel | MEDIUM | Low | genres.json |
| NB5 | MPC 3.x export | MEDIUM | Medium | mpc_exporter |
| NB5 | Ableton export | LOW | High | None |

---

### Backward Compatibility Guarantee

All NB Phase implementations MUST preserve existing functionality:

```python
# ✓ CLI mode still works unchanged
python main.py "trap beat with 808s"

# ✓ Server mode still works
python main.py --server --port 9000

# ✓ Existing JUCE UI continues to function
# New components are ADDITIVE, not replacements
```

---

## 📚 Research & Best Practices Applied

This TODO was enhanced with professional patterns from:

### AudioProcessorGraph Tutorial (JUCE Official)
- **ProcessorBase pattern**: Reduces boilerplate for custom audio processors
- **Node connection management**: Proper `addNode()` → `addConnection()` workflow
- **Dynamic graph updates**: Check state changes before rebuilding graph
- **Graph I/O processors**: `AudioGraphIOProcessor` for input/output routing

### VU Meter Standards (ANSI C16.5-1942 / IEC 60268-17)
- **300ms rise/fall time**: Standard VU ballistics for perceived loudness
- **RMS averaging**: Not peak detection (different from PPM)
- **Reference level**: 0 VU = +4 dBu (professional standard)
- **Headroom**: Design for +6dB to +10dB above reference
- **Peak hold**: 2 second hold with 300ms decay (industry convention)

### JUCE DSP Module
- **dsp::Gain**: Smoothed gain with `setRampDurationSeconds()` for click-free changes
- **dsp::Panner**: Balanced panning law (`PannerRule::balanced`)
- **dsp::ProcessSpec**: Standard way to pass sample rate/block size
- **dsp::ProcessContextReplacing**: In-place audio processing pattern

### Command Pattern (Gang of Four)
- **Undo/Redo stack**: Maximum 50 levels, clear on save
- **Command merging**: Group continuous slider movements into single undo
- **Transactions**: Group multiple commands into single undoable action
- **Serialization**: Commands can describe themselves for UI display

### Plugin Development (VST3/AU)
- **AudioPlayHead::PositionInfo**: Proper DAW transport sync
- **State save/restore**: JSON serialization for human-readable project files
- **Sidechain input**: Optional mono input for future vocal analysis
- **Multi-instance support**: Stateless design for multiple plugin instances
