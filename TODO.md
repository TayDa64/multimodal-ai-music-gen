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

#### Tasks
- [ ] **0.1** Research JUCE OSC support (`juce_osc` module)
  - Verify UDP socket handling on Windows
  - Test message serialization/deserialization
  - Benchmark latency for real-time use
  
- [ ] **0.2** Prototype Python OSC server
  - Install `python-osc` library
  - Create minimal echo server
  - Test bidirectional communication
  
- [ ] **0.3** Research JUCE audio architecture
  - `AudioDeviceManager` for output selection
  - `AudioSource` chain for playback
  - `MidiFile` and `MidiMessageSequence` for MIDI handling
  - `Synthesiser` class for sample playback
  
- [ ] **0.4** Research JUCE MIDI playback options
  - FluidSynth integration (via command-line or library)
  - Native `Synthesiser` with `SamplerSound`
  - Third-party SoundFont loader
  
- [ ] **0.5** Design project file format (.mmg)
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
- [ ] OSC messages round-trip in < 10ms
- [ ] Python server handles concurrent requests without blocking
- [ ] JUCE can load and play a MIDI file with samples
- [ ] Project file format documented and validated

#### Dependencies
- JUCE 7.x installed ✅
- Python 3.10+ with existing codebase ✅
- `python-osc` package (to be added)

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
- [x] **2.1** Create JUCE project structure
  ```
  juce/
  ├── CMakeLists.txt           # CMake build configuration
  ├── Source/
  │   ├── Main.cpp             # Application entry point
  │   ├── MainComponent.h      # Root component header
  │   ├── MainComponent.cpp    # Root component implementation
  │   ├── Application/
  │   │   ├── AppState.h/cpp   # Application state management
  │   │   └── AppConfig.h      # Configuration constants
  │   ├── Communication/
  │   │   ├── Messages.h       # OSC message structures
  │   │   ├── OSCBridge.h/cpp  # JUCE OSC client
  │   │   └── PythonManager.h/cpp  # Python process manager
  │   └── UI/
  │       ├── Theme/
  │       │   ├── ColourScheme.h       # Color palette
  │       │   └── AppLookAndFeel.h/cpp # Custom look and feel
  │       ├── TransportComponent.h/cpp # Transport controls
  │       ├── PromptPanel.h/cpp        # Prompt input UI
  │       └── ProgressOverlay.h/cpp    # Progress overlay
  └── JuceLibraryCode/         # Auto-generated JUCE headers
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

- [ ] **2.5** Setup development environment
  - Visual Studio 2022 project generation (Windows)
  - Xcode project generation (macOS - for future)
  - Build and run verification

- [x] **2.6** Create application icon and branding
  - 256x256 app icon (placeholder)
  - Splash screen (optional)
  - Color scheme constants (ColourScheme.h)

- [x] **2.7** Implement window management
  - Save/restore window size and position
  - Multi-monitor support
  - Full-screen toggle

#### Success Criteria
- [ ] Application builds without errors (requires JUCE path configuration)
- [x] Window opens with basic layout
- [x] Window state persists across restarts
- [x] Clean shutdown without leaks

---

### Phase 3: OSC Communication Bridge
**Duration**: 3-4 days  
**Risk Level**: 🟡 Medium  
**Goal**: Establish reliable bidirectional communication between JUCE and Python

#### Tasks
- [ ] **3.1** Create `Source/Communication/OSCBridge.h/cpp`
  ```cpp
  class OSCBridge : public juce::OSCReceiver::Listener<juce::OSCReceiver::MessageLoopCallback> {
  public:
      OSCBridge(int sendPort = 9000, int receivePort = 9001);
      
      // Outgoing messages
      void sendGenerate(const GenerationRequest& request);
      void sendCancel();
      void sendAnalyze(const juce::File& file);
      
      // Incoming message handling
      void oscMessageReceived(const juce::OSCMessage& message) override;
      
      // Listeners for UI updates
      class Listener {
      public:
          virtual void onProgress(float percent, const juce::String& message) = 0;
          virtual void onGenerationComplete(const GenerationResult& result) = 0;
          virtual void onError(const juce::String& message) = 0;
      };
      void addListener(Listener* listener);
      void removeListener(Listener* listener);
      
  private:
      juce::OSCSender sender;
      juce::OSCReceiver receiver;
      juce::ListenerList<Listener> listeners;
  };
  ```

- [ ] **3.2** Create data structures
  ```cpp
  // Source/Communication/Messages.h
  struct GenerationRequest {
      juce::String prompt;
      int bpm = 0;  // 0 = auto
      juce::String key;  // Empty = auto
      juce::File outputDir;
      juce::StringArray instrumentPaths;
      bool renderAudio = true;
      bool exportStems = false;
      bool exportMpc = false;
  };
  
  struct GenerationResult {
      juce::File midiFile;
      juce::File audioFile;
      juce::File stemsDir;
      juce::File mpcProject;
      int bpm;
      juce::String key;
      juce::String genre;
      // ... metadata
  };
  ```

- [ ] **3.3** Implement connection management
  - Auto-start Python server if not running
  - Heartbeat/ping to detect disconnection
  - Reconnection with exponential backoff
  - Connection status indicator in UI

- [ ] **3.4** Implement message queuing
  - Queue outgoing messages when disconnected
  - Flush queue on reconnection
  - Timeout handling for pending requests

- [ ] **3.5** Create Python process manager
  ```cpp
  // Source/Communication/PythonManager.h
  class PythonManager {
  public:
      bool startServer(const juce::File& pythonPath, int port);
      void stopServer();
      bool isRunning() const;
      
  private:
      std::unique_ptr<juce::ChildProcess> process;
  };
  ```

- [ ] **3.6** Unit test the bridge
  - Mock Python server for testing
  - Message serialization tests
  - Timeout and error handling tests

#### Success Criteria
- [ ] JUCE sends `/generate` → Python responds with `/progress` and `/complete`
- [ ] Connection status accurately reflected in UI
- [ ] Graceful handling of Python server crash
- [ ] No message loss under normal conditions

---

### Phase 4: Transport & Basic Playback
**Duration**: 5-6 days  
**Risk Level**: 🟠 Medium-High  
**Goal**: Real-time MIDI playback with transport controls

#### Tasks
- [ ] **4.1** Create Audio Engine
  ```cpp
  // Source/Audio/AudioEngine.h
  class AudioEngine : public juce::AudioSource {
  public:
      AudioEngine();
      
      // AudioSource interface
      void prepareToPlay(int samplesPerBlockExpected, double sampleRate) override;
      void releaseResources() override;
      void getNextAudioBlock(const juce::AudioSourceChannelInfo& bufferToFill) override;
      
      // Playback control
      void loadMidiFile(const juce::File& midiFile);
      void loadAudioFile(const juce::File& audioFile);
      void play();
      void pause();
      void stop();
      void setPosition(double timeInSeconds);
      
      // Properties
      double getCurrentPosition() const;
      double getTotalLength() const;
      bool isPlaying() const;
      
  private:
      juce::AudioDeviceManager deviceManager;
      juce::AudioSourcePlayer audioSourcePlayer;
      juce::MixerAudioSource mixer;
      // ...
  };
  ```

- [ ] **4.2** Implement MIDI Synthesizer
  ```cpp
  // Source/Audio/MidiSynthesizer.h
  class MidiSynthesizer : public juce::AudioSource {
  public:
      MidiSynthesizer();
      
      // Load samples for playback
      void loadSoundFont(const juce::File& sf2File);
      void loadSamplePack(const juce::File& directory);
      
      // Set MIDI sequence
      void setMidiSequence(const juce::MidiMessageSequence& sequence);
      
      // AudioSource implementation
      void getNextAudioBlock(const juce::AudioSourceChannelInfo& bufferToFill) override;
      
  private:
      juce::Synthesiser synth;
      juce::MidiMessageSequence midiSequence;
      int samplePosition = 0;
  };
  ```

- [ ] **4.3** Create Transport Component
  ```cpp
  // Source/UI/TransportComponent.h
  class TransportComponent : public juce::Component, public juce::Timer {
  public:
      TransportComponent(AudioEngine& engine);
      
      void paint(juce::Graphics& g) override;
      void resized() override;
      void timerCallback() override;  // Update position display
      
  private:
      juce::TextButton playButton, pauseButton, stopButton;
      juce::Slider positionSlider;
      juce::Label timeDisplay, bpmDisplay;
      AudioEngine& audioEngine;
  };
  ```

- [ ] **4.4** Implement position tracking
  - Accurate sample-based position
  - BPM-aware bar/beat display
  - Loop region support (future)

- [ ] **4.5** Create timeline component
  ```cpp
  // Source/UI/TimelineComponent.h
  class TimelineComponent : public juce::Component {
  public:
      void setSections(const juce::Array<Section>& sections);
      void setCurrentPosition(double position);
      
      // Click to seek
      void mouseDown(const juce::MouseEvent& event) override;
      
  private:
      void drawBeatMarkers(juce::Graphics& g);
      void drawSections(juce::Graphics& g);
      void drawPlayhead(juce::Graphics& g);
  };
  ```

- [ ] **4.6** Audio device settings
  - Output device selection dialog
  - Sample rate and buffer size configuration
  - ASIO support (Windows)

#### Success Criteria
- [ ] Play/pause/stop work correctly
- [ ] Position slider accurate and responsive
- [ ] MIDI playback with default synth sounds
- [ ] Timeline shows correct song structure
- [ ] Seeking works without audio glitches

---

### Phase 5: Prompt Input & Generation UI
**Duration**: 3-4 days  
**Risk Level**: 🟢 Low  
**Goal**: User can type prompt and trigger generation

#### Tasks
- [ ] **5.1** Create Prompt Panel
  ```cpp
  // Source/UI/PromptPanel.h
  class PromptPanel : public juce::Component {
  public:
      PromptPanel(OSCBridge& bridge);
      
      void resized() override;
      
      // Get prompt text
      juce::String getPrompt() const;
      
      // Enable/disable during generation
      void setEnabled(bool enabled);
      
  private:
      juce::TextEditor promptEditor;
      juce::TextButton generateButton;
      juce::ComboBox genrePresets;  // Quick genre selection
      juce::Slider bpmSlider;
      juce::ComboBox keySelector;
  };
  ```

- [ ] **5.2** Create Progress Overlay
  ```cpp
  // Source/UI/ProgressOverlay.h
  class ProgressOverlay : public juce::Component, public OSCBridge::Listener {
  public:
      ProgressOverlay();
      
      void show(const juce::String& initialMessage);
      void hide();
      
      // OSCBridge::Listener
      void onProgress(float percent, const juce::String& message) override;
      void onGenerationComplete(const GenerationResult& result) override;
      void onError(const juce::String& message) override;
      
  private:
      juce::ProgressBar progressBar;
      juce::Label statusLabel;
      juce::TextButton cancelButton;
  };
  ```

- [ ] **5.3** Implement generation flow
  1. User types prompt, clicks Generate
  2. UI disables input, shows progress overlay
  3. Send `/generate` to Python
  4. Receive `/progress` updates, update overlay
  5. Receive `/complete`, load result, hide overlay
  6. Auto-play generated track (optional)

- [ ] **5.4** Add preset prompts
  - "Boom Bap - 90s hip hop beat"
  - "G-Funk - West coast synths"
  - "Trap - 808 heavy"
  - "Lo-fi - chill beats to study"
  - Custom preset saving

- [ ] **5.5** Implement generation history
  - List of recent generations
  - Click to reload previous result
  - Delete old generations

#### Success Criteria
- [ ] User can type prompt and generate
- [ ] Progress updates shown in real-time
- [ ] Cancel button stops generation
- [ ] Generated track auto-loads and plays
- [ ] Previous generations accessible

---

### Phase 6: Piano Roll Visualization
**Duration**: 5-6 days  
**Risk Level**: 🟡 Medium  
**Goal**: Visual MIDI display with note information

#### Tasks
- [ ] **6.1** Create Piano Roll Component
  ```cpp
  // Source/UI/Visualization/PianoRollComponent.h
  class PianoRollComponent : public juce::Component {
  public:
      PianoRollComponent();
      
      void setMidiSequence(const juce::MidiFile& midiFile);
      void setPlayheadPosition(double positionInBeats);
      void setZoom(float horizontalZoom, float verticalZoom);
      
      void paint(juce::Graphics& g) override;
      void mouseWheelMove(const juce::MouseEvent&, const juce::MouseWheelDetails&) override;
      
  private:
      void drawPianoKeys(juce::Graphics& g);
      void drawGridLines(juce::Graphics& g);
      void drawNotes(juce::Graphics& g);
      void drawPlayhead(juce::Graphics& g);
      
      juce::Array<MidiNote> notes;
      float hZoom = 1.0f, vZoom = 1.0f;
      double playheadPosition = 0.0;
  };
  ```

- [ ] **6.2** Implement note rendering
  - Color-code by velocity (darker = louder)
  - Color-code by track (drums, bass, melody, etc.)
  - Highlight currently playing notes
  - Show note names on hover

- [ ] **6.3** Implement zoom and scroll
  - Mouse wheel vertical zoom
  - Shift + wheel horizontal zoom
  - Drag to scroll
  - Zoom to fit selection

- [ ] **6.4** Add track filtering
  - Toggle visibility per track
  - Solo track view
  - Track list sidebar

- [ ] **6.5** Create note inspector
  - Click note to see details
  - Note: C4, Velocity: 100, Start: 1.0.0, Length: 0.2.0
  - (Read-only for now, editing in future phase)

#### Success Criteria
- [ ] All MIDI notes visible
- [ ] Playhead follows playback position
- [ ] Smooth zoom and scroll
- [ ] Track colors distinguishable
- [ ] Performance with 1000+ notes

---

### Phase 7: Waveform & Spectrum Visualization
**Duration**: 4-5 days  
**Risk Level**: 🟡 Medium  
**Goal**: Real-time audio visualization

#### Tasks
- [ ] **7.1** Create Waveform Component
  ```cpp
  // Source/UI/Visualization/WaveformComponent.h
  class WaveformComponent : public juce::Component, public juce::ChangeListener {
  public:
      WaveformComponent();
      
      void setAudioFile(const juce::File& audioFile);
      void setPlayheadPosition(double positionInSamples);
      
      void paint(juce::Graphics& g) override;
      void changeListenerCallback(juce::ChangeBroadcaster*) override;
      
  private:
      juce::AudioThumbnailCache thumbnailCache;
      juce::AudioThumbnail thumbnail;
      double playheadPosition = 0.0;
  };
  ```

- [ ] **7.2** Implement thumbnail generation
  - Background thread loading
  - Progress indication for large files
  - Caching for previously loaded files

- [ ] **7.3** Create Spectrum Analyzer
  ```cpp
  // Source/UI/Visualization/SpectrumComponent.h
  class SpectrumComponent : public juce::Component, public juce::Timer {
  public:
      SpectrumComponent(AudioEngine& engine);
      
      void timerCallback() override;
      void paint(juce::Graphics& g) override;
      
  private:
      juce::dsp::FFT fft;
      std::array<float, 2048> fftData;
      std::array<float, 512> spectrumData;
  };
  ```

- [ ] **7.4** Add genre-aware color themes
  ```cpp
  // Color schemes per genre
  struct GenreTheme {
      juce::Colour primary;
      juce::Colour secondary;
      juce::Colour accent;
      juce::Colour waveformFill;
      juce::Colour spectrumGradientStart;
      juce::Colour spectrumGradientEnd;
  };
  
  // Examples:
  // G-Funk: Purple/Green/Gold
  // Trap: Red/Black/White
  // Lo-fi: Warm orange/Brown/Cream
  // Boom Bap: Gold/Brown/Black
  ```

- [ ] **7.5** Implement view switching
  - Tab or button to switch Waveform/Spectrum/PianoRoll
  - Split view option (waveform + piano roll)
  - Remember user preference

#### Success Criteria
- [ ] Waveform displays accurately
- [ ] Spectrum responds to audio in real-time
- [ ] Theme changes with genre
- [ ] Smooth 60fps visualization
- [ ] Low CPU usage (< 10%)

---

### Phase 8: Track Mixer
**Duration**: 4-5 days  
**Risk Level**: 🟡 Medium  
**Goal**: Per-track volume, pan, and mute/solo

#### Tasks
- [ ] **8.1** Create Mixer Component
  ```cpp
  // Source/UI/Mixer/MixerComponent.h
  class MixerComponent : public juce::Component {
  public:
      MixerComponent(AudioEngine& engine);
      
      void setTracks(const juce::Array<TrackInfo>& tracks);
      void resized() override;
      
  private:
      juce::OwnedArray<ChannelStrip> channelStrips;
      MasterStrip masterStrip;
  };
  ```

- [ ] **8.2** Create Channel Strip
  ```cpp
  // Source/UI/Mixer/ChannelStrip.h
  class ChannelStrip : public juce::Component {
  public:
      ChannelStrip(const juce::String& trackName);
      
      float getVolume() const;
      float getPan() const;
      bool isMuted() const;
      bool isSoloed() const;
      
  private:
      juce::Slider volumeSlider;  // Vertical fader
      juce::Slider panKnob;       // Rotary
      juce::TextButton muteButton, soloButton;
      juce::Label trackNameLabel;
      LevelMeter levelMeter;      // VU meter
  };
  ```

- [ ] **8.3** Implement audio routing
  - Separate MIDI tracks to audio channels
  - Apply volume/pan per channel
  - Mix to stereo master output
  - Solo/mute logic (solo overrides mute)

- [ ] **8.4** Create VU Meter
  ```cpp
  // Source/UI/Mixer/LevelMeter.h
  class LevelMeter : public juce::Component, public juce::Timer {
  public:
      void setLevel(float leftLevel, float rightLevel);
      void timerCallback() override;
      void paint(juce::Graphics& g) override;
      
  private:
      float leftLevel = 0.0f, rightLevel = 0.0f;
      float leftPeak = 0.0f, rightPeak = 0.0f;
  };
  ```

- [ ] **8.5** Implement mixer state persistence
  - Save mixer settings to project file
  - Recall on project load
  - Reset to default option

#### Success Criteria
- [ ] Volume changes affect audio output
- [ ] Pan moves sound left/right
- [ ] Mute/solo work correctly
- [ ] VU meters respond to audio
- [ ] Mixer state saves with project

---

### Phase 9: Instrument Browser
**Duration**: 4-5 days  
**Risk Level**: 🟢 Low  
**Goal**: Browse and select custom instruments

#### Tasks
- [ ] **9.1** Create Instrument Browser Panel
  ```cpp
  // Source/UI/InstrumentBrowserComponent.h
  class InstrumentBrowserComponent : public juce::Component {
  public:
      InstrumentBrowserComponent(OSCBridge& bridge);
      
      void setInstrumentPaths(const juce::StringArray& paths);
      void refresh();
      
  private:
      juce::TreeView categoryTree;
      juce::ListBox instrumentList;
      InstrumentPreview previewPanel;
      juce::TextButton addFolderButton;
  };
  ```

- [ ] **9.2** Create Instrument Preview
  - Waveform thumbnail
  - Play button to audition
  - Metadata display (BPM, key if detected)

- [ ] **9.3** Implement category filtering
  - Filter by category (kick, snare, hihat, etc.)
  - Search by name
  - Filter by source folder

- [ ] **9.4** Add drag-and-drop support
  - Drag instrument to track
  - Drag instrument to piano roll (future editing)
  - Drag from file explorer to add

- [ ] **9.5** Integrate with Python matcher
  - Show AI recommendations
  - Highlight best matches for current genre
  - Sort by match score

#### Success Criteria
- [ ] All instruments from paths displayed
- [ ] Preview plays sample audio
- [ ] Search and filter work
- [ ] AI recommendations shown
- [ ] Drag-and-drop functional

---

### Phase 10: Project Management
**Duration**: 3-4 days  
**Risk Level**: 🟢 Low  
**Goal**: Save, load, and manage projects

#### Tasks
- [ ] **10.1** Implement Project class
  ```cpp
  // Source/Project/Project.h
  class Project {
  public:
      bool save(const juce::File& file);
      bool load(const juce::File& file);
      
      // Project data
      juce::String prompt;
      GenerationResult generationResult;
      MixerState mixerState;
      juce::Array<Section> arrangement;
      // ...
  };
  ```

- [ ] **10.2** Create file dialogs
  - Save As dialog
  - Open dialog with recent files
  - Export dialog (WAV, stems, MPC)

- [ ] **10.3** Implement undo/redo
  - Command pattern for all state changes
  - Undo stack with reasonable limit (50 actions)
  - Keyboard shortcuts (Ctrl+Z, Ctrl+Y)

- [ ] **10.4** Add recent projects menu
  - Track last 10 projects
  - Quick access from File menu
  - Pin favorite projects

- [ ] **10.5** Auto-save implementation
  - Save draft every 2 minutes
  - Recover from crash on next launch
  - User preference to enable/disable

#### Success Criteria
- [ ] Project saves and loads correctly
- [ ] Undo/redo work for mixer changes
- [ ] Recent projects menu populated
- [ ] Auto-save prevents data loss

---

### Phase 11: VST3/AU Plugin Format
**Duration**: 5-7 days  
**Risk Level**: 🟠 Medium-High  
**Goal**: Run as plugin inside DAW

#### Tasks
- [ ] **11.1** Create PluginProcessor
  ```cpp
  // Source/Plugin/PluginProcessor.h
  class MusicGenPluginProcessor : public juce::AudioProcessor {
  public:
      void prepareToPlay(double sampleRate, int samplesPerBlock) override;
      void processBlock(juce::AudioBuffer<float>&, juce::MidiBuffer&) override;
      
      juce::AudioProcessorEditor* createEditor() override;
      
      // Sync with DAW transport
      void syncToHostTransport();
      
  private:
      AudioEngine audioEngine;
      OSCBridge oscBridge;
  };
  ```

- [ ] **11.2** Create PluginEditor
  - Embed MainComponent in plugin window
  - Handle resize constraints
  - DAW-specific styling

- [ ] **11.3** Implement DAW transport sync
  - Read host BPM
  - Sync playhead to host position
  - Start/stop with host transport

- [ ] **11.4** Add sidechain input
  - Sidechain for future vocal input
  - Route external audio to analysis

- [ ] **11.5** Test in major DAWs
  - Ableton Live
  - FL Studio
  - Logic Pro
  - Cubase
  - Reaper

- [ ] **11.6** Create plugin installer
  - Windows installer (VST3)
  - macOS installer (VST3 + AU)
  - Linux (VST3)

#### Success Criteria
- [ ] Plugin loads in all tested DAWs
- [ ] Transport syncs correctly
- [ ] Audio output works
- [ ] No crashes or audio dropouts
- [ ] Installer works cleanly

---

### Phase 12: Advanced Features (Future)
**Duration**: Ongoing  
**Risk Level**: 🟡 Variable  
**Goal**: Vocal-to-orchestration and beyond

#### Tasks
- [ ] **12.1** Vocal input processing
  - Pitch detection (using pYIN or similar)
  - Melody transcription
  - Send to Python for harmonization

- [ ] **12.2** AI harmonization
  - Generate chord progression from melody
  - Create bass line that follows chords
  - Add counter-melodies

- [ ] **12.3** Real-time suggestion engine
  - Suggest next section based on current arrangement
  - Suggest instrument variations
  - Suggest automation curves

- [ ] **12.4** Collaborative features
  - Share project via link
  - Real-time collaboration (like Google Docs)
  - Community preset sharing

- [ ] **12.5** Hardware integration
  - MIDI controller mapping
  - MPC hardware direct sync
  - Ableton Push/Launchpad support

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

### Sprint 1: Foundation (Phases 0-1)
**Goal**: Establish communication infrastructure

- [ ] Research JUCE OSC module
- [ ] Prototype Python OSC server
- [ ] Design message protocol
- [ ] Implement `multimodal_gen/server/` module
- [ ] Add `--server` mode to `main.py`
- [ ] Write tests for server

---

*Last Updated: December 10, 2025*
