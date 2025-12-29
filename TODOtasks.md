# 🎵 TODOtasks.md — Remaining Implementation Roadmap
> **Synthesized from GPT-5.2 (TODO2.md) + Gemini 3 Pro (TODO3.md) + JUCE Documentation**  
> **Generated**: December 29, 2025  
> **Focus**: Context-optimized tasks for Phases 8-12+

---

## 📊 Current State Summary

### ✅ Completed (Phases 0-7)
| Phase | Component | Status |
|-------|-----------|--------|
| 0 | Foundation Research | ✅ OSC validated, Audio architecture documented |
| 1 | Python OSC Server | ✅ `/generate`, `/cancel`, `/ping`, `/shutdown` implemented |
| 2 | JUCE Foundation | ✅ Project structure, CMake, window management |
| 3 | OSC Bridge | ✅ Bidirectional communication, PythonManager |
| 4 | Transport & Playback | ✅ AudioEngine, MidiPlayer, 16-voice synth |
| 5 | Prompt & Generation UI | ✅ PromptPanel, ProgressOverlay, 6 genre presets |
| 6 | Piano Roll | ✅ Visualization, zoom, track filtering, tooltips |
| 7 | Waveform & Spectrum | ✅ 4 display modes, 7 genre themes, VU metering |

### 🔲 Remaining (This Document)
- **Milestone 1**: Protocol Hardening (request_id, schema versioning)
- **Milestone 2**: `/analyze` Endpoint (reference file analysis)
- **Milestone 3**: Track Mixer (AudioProcessorGraph-based)
- **Milestone 4**: Project System (ValueTree, Undo/Redo, Save/Load)
- **Milestone 5**: UI/UX Professionalization (FlexBox, LookAndFeel)
- **Milestone 6**: Testing & CI Hardening
- **Milestone 7**: Distribution (Installer, embedded Python)
- **Stretch**: VST3/AU Plugin, Plugin Hosting, MIDI Input

---

## 🛠️ Design Principles (JUCE Audio Thread Safety)

> **Source**: JUCE Documentation + Senior Audio Engineering Best Practices

| Rule | Implementation |
|------|----------------|
| **Audio thread is sacred** | Never block, never allocate, always fill buffers (silence = zeros) |
| **UI is asynchronous** | Use `MessageManager::callAsync()` for cross-thread UI updates |
| **Timers are UI-thread** | Don't assume timing precision; avoid heavy work in callbacks |
| **Lock-free communication** | Use `juce::AbstractFifo` for audio↔UI data transfer |
| **Pre-allocate everything** | Voices, buffers, and all audio resources in `prepareToPlay()` |

---

## 🏗️ Milestone 1: Protocol Hardening + Request Lifecycle
**Duration**: 2-3 days | **Risk**: 🟢 Low | **Priority**: HIGH

### Goal
Turn OSC from "best effort messages" into a predictable request/response protocol with UI retries, cancel, and robust error reporting.

### Tasks

- [ ] **1.1** Add `request_id` to all OSC messages
  ```python
  # Python side: Messages.py
  @dataclass
  class GenerationRequest:
      request_id: str  # UUID
      schema_version: int = 1
      prompt: str
      bpm: int
      key: str
      # ... existing fields
  ```
  ```cpp
  // JUCE side: Messages.h
  struct GenerationRequest {
      juce::String requestId;  // juce::Uuid::toString()
      int schemaVersion = 1;
      // ... existing fields
  };
  ```

- [ ] **1.2** Implement timeout + retry strategy (JUCE-side)
  - If no `/pong` within 5 seconds → set `connectionStatus = Disconnected`
  - Queue bounded requests (max 1 generate + 1 instruments) when disconnected
  - Reconnect backoff: 250ms → 500ms → 1s → 2s → 5s max

- [ ] **1.3** Graceful shutdown strategy
  - Send `/shutdown` with `request_id` before killing Python process
  - Add explicit "server shutting down" status from Python
  - Timeout for shutdown acknowledgment: 3 seconds

- [ ] **1.4** Connection state machine
  ```cpp
  enum class ConnectionState {
      Disconnected,
      Connecting,
      Connected,
      Generating,
      Canceling,
      Error
  };
  ```

### Acceptance Criteria
- [ ] UI shows: "connected / disconnected / generating / canceling / error" reliably
- [ ] Every completion/error/progress maps to a known `request_id`
- [ ] Cancels are deterministic within bounded latency

---

## 🏗️ Milestone 2: Implement `/analyze` Endpoint
**Duration**: 3-4 days | **Risk**: 🟡 Medium | **Priority**: MEDIUM

### Goal
Make analysis a first-class flow for "import → analyze → generate/refine" workflow.

### Tasks

- [ ] **2.1** Define analysis output schema
  ```python
  @dataclass
  class AnalysisResult:
      request_id: str
      file_path: str
      bpm_estimate: float  # e.g., 120.5
      key_estimate: str    # e.g., "Aminor"
      time_signature: str  # e.g., "4/4"
      loudness_rms: float  # dB
      peak_db: float
      duration_seconds: float
      spectral_centroid: float  # brightness indicator
      prompt_suggestion: str  # AI-generated prompt hint
  ```

- [ ] **2.2** Python implementation
  - Fast path: metadata + basic DSP (RMS/peak, spectral centroid, onset strength)
  - Use `librosa` for BPM/key detection (optional, behind feature flag)
  - Cache by file path + mtime + config hash

- [ ] **2.3** OSC route `/analyze`
  ```python
  # multimodal_gen/server/osc_handlers.py
  @osc_handler('/analyze')
  def handle_analyze(path: str, request_id: str, options: dict):
      # Stream progress: "loading", "analyzing_tempo", "analyzing_key", "complete"
      pass
  ```

- [ ] **2.4** JUCE UI integration
  - "Import & Analyze" button in PromptPanel
  - File picker → progress overlay → populate BPM/key/genre hints
  - Analysis results displayed in info panel

### Acceptance Criteria
- [ ] User can drop a file, see analysis results, and generate a compatible track
- [ ] Analysis never blocks audio thread; file IO is backgrounded
- [ ] Results cached for repeated analysis of same file

---

## 🏗️ Milestone 3: Track Mixer (AudioProcessorGraph-Based)
**Duration**: 5-7 days | **Risk**: 🟡 Medium | **Priority**: HIGH

### Goal
Professional per-track mixing with real multi-stem audio playback.

### Architecture (from JUCE AudioProcessorGraph Tutorial)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          MIXER AUDIO GRAPH                                   │
│                                                                             │
│  Track 1 ───▶ [GainProcessor] → [PanProcessor] → [LevelMeter] ──┐          │
│  Track 2 ───▶ [GainProcessor] → [PanProcessor] → [LevelMeter] ──┼──▶ MASTER│
│  Track N ───▶ [GainProcessor] → [PanProcessor] → [LevelMeter] ──┘    BUS   │
│                                                                   │         │
│                                              [MasterGain] → [MasterMeter]   │
│                                                           └──▶ OUTPUT      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Tasks

- [ ] **3.1** Create `ProcessorBase` class
  ```cpp
  // Source/Audio/Processors/ProcessorBase.h
  class ProcessorBase : public juce::AudioProcessor {
  public:
      ProcessorBase() : AudioProcessor(BusesProperties()
          .withInput("Input", juce::AudioChannelSet::stereo())
          .withOutput("Output", juce::AudioChannelSet::stereo())) {}
      
      void prepareToPlay(double, int) override {}
      void releaseResources() override {}
      void processBlock(juce::AudioBuffer<float>&, juce::MidiBuffer&) override {}
      
      // Boilerplate reduced
      juce::AudioProcessorEditor* createEditor() override { return nullptr; }
      bool hasEditor() const override { return false; }
      const juce::String getName() const override { return "ProcessorBase"; }
      // ... minimal implementations
  };
  ```

- [ ] **3.2** Create `GainProcessor` (dsp::Gain wrapper)
  ```cpp
  class GainProcessor : public ProcessorBase {
  public:
      void setGainDecibels(float dB) {
          gain.setGainDecibels(dB);
      }
      void prepareToPlay(double sampleRate, int blockSize) override {
          juce::dsp::ProcessSpec spec{sampleRate, (uint32)blockSize, 2};
          gain.prepare(spec);
          gain.setRampDurationSeconds(0.02);  // 20ms anti-click
      }
      void processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer&) override {
          juce::dsp::AudioBlock<float> block(buffer);
          gain.process(juce::dsp::ProcessContextReplacing<float>(block));
      }
  private:
      juce::dsp::Gain<float> gain;
  };
  ```

- [ ] **3.3** Create `PanProcessor` (dsp::Panner wrapper)
  ```cpp
  class PanProcessor : public ProcessorBase {
  public:
      void setPan(float pan) { panner.setPan(pan); }  // -1.0 to +1.0
      void prepareToPlay(double sampleRate, int blockSize) override {
          juce::dsp::ProcessSpec spec{sampleRate, (uint32)blockSize, 2};
          panner.prepare(spec);
          panner.setRule(juce::dsp::PannerRule::balanced);
      }
      void processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer&) override {
          juce::dsp::AudioBlock<float> block(buffer);
          panner.process(juce::dsp::ProcessContextReplacing<float>(block));
      }
  private:
      juce::dsp::Panner<float> panner;
  };
  ```

- [ ] **3.4** Create `MixerGraph` class
  ```cpp
  class MixerGraph : public juce::AudioProcessorGraph {
  public:
      void addTrack(int trackIndex);
      void removeTrack(int trackIndex);
      void setTrackGain(int trackIndex, float dB);
      void setTrackPan(int trackIndex, float pan);
      void setTrackMute(int trackIndex, bool mute);
      void setTrackSolo(int trackIndex, bool solo);
      float getTrackLevel(int trackIndex);  // For meters
      float getMasterLevel();
  private:
      struct TrackNodes {
          Node::Ptr gainNode;
          Node::Ptr panNode;
          Node::Ptr meterNode;
      };
      std::map<int, TrackNodes> tracks;
      Node::Ptr masterGainNode;
      Node::Ptr masterMeterNode;
      Node::Ptr audioInputNode;
      Node::Ptr audioOutputNode;
  };
  ```

- [ ] **3.5** Create `LevelMeter` processor (VU-style)
  ```cpp
  class LevelMeterProcessor : public ProcessorBase {
  public:
      float getLevel() const { return currentLevel.load(); }
      float getPeakLevel() const { return peakLevel.load(); }
      
      void processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer&) override {
          float rms = 0.0f;
          for (int ch = 0; ch < buffer.getNumChannels(); ++ch) {
              auto* data = buffer.getReadPointer(ch);
              for (int i = 0; i < buffer.getNumSamples(); ++i)
                  rms += data[i] * data[i];
          }
          rms = std::sqrt(rms / (buffer.getNumSamples() * buffer.getNumChannels()));
          
          // VU ballistics: 300ms attack/release (ANSI C16.5-1942)
          float targetLevel = juce::Decibels::gainToDecibels(rms, -80.0f);
          currentLevel.store(currentLevel.load() * 0.9f + targetLevel * 0.1f);
          
          // Peak hold: 2 seconds
          if (targetLevel > peakLevel.load()) {
              peakLevel.store(targetLevel);
              peakHoldCounter = sampleRate * 2.0;
          } else if (--peakHoldCounter <= 0) {
              peakLevel.store(peakLevel.load() * 0.99f);  // Slow decay
          }
      }
  private:
      std::atomic<float> currentLevel{-80.0f};
      std::atomic<float> peakLevel{-80.0f};
      double sampleRate = 44100.0;
      int peakHoldCounter = 0;
  };
  ```

- [ ] **3.6** Create `ChannelStrip` UI component
  ```cpp
  class ChannelStrip : public juce::Component {
  public:
      ChannelStrip(int trackIndex, MixerGraph& graph);
      void paint(juce::Graphics& g) override;
      void resized() override;
      void timerCallback();  // Update meters at 30fps
  private:
      int trackIndex;
      MixerGraph& mixerGraph;
      juce::Slider volumeFader{juce::Slider::LinearVertical, juce::Slider::NoTextBox};
      juce::Slider panKnob{juce::Slider::RotaryVerticalDrag, juce::Slider::NoTextBox};
      juce::TextButton muteButton{"M"};
      juce::TextButton soloButton{"S"};
      LevelMeterComponent levelMeter;
      juce::Label trackLabel;
  };
  ```

- [ ] **3.7** Create `MixerComponent` container
  ```cpp
  class MixerComponent : public juce::Component {
  public:
      void setNumTracks(int count);
      void resized() override;
  private:
      juce::OwnedArray<ChannelStrip> channelStrips;
      ChannelStrip masterStrip;
      juce::Viewport viewport;  // Horizontal scrolling for many tracks
  };
  ```

- [ ] **3.8** Python: Standardize stem export
  ```python
  # Stem naming convention
  STEM_NAMES = ['drums', 'bass', 'melody', 'pads', 'fx']
  
  # stems.json manifest
  {
      "stems": [
          {"name": "drums", "file": "drums.wav", "default_gain_db": 0.0},
          {"name": "bass", "file": "bass.wav", "default_gain_db": -3.0},
          // ...
      ],
      "master_bpm": 120,
      "master_key": "Aminor"
  }
  ```

### Technical Specs (from ANSI Standards + JUCE Docs)
| Parameter | Value | Source |
|-----------|-------|--------|
| Volume Range | -∞ to +12 dB | Industry standard |
| Pan Range | -1.0 to +1.0 | dsp::Panner balanced law |
| VU Ballistics | 300ms attack/release | ANSI C16.5-1942 |
| Peak Hold | 2000ms + decay | Professional metering |
| Gain Ramping | 20ms | Click-free transitions |
| Meter Update Rate | 30fps | UI responsiveness |

### Acceptance Criteria
- [ ] Generated project loads with stems and mixer can rebalance them
- [ ] Playback is stable (no glitches) under typical buffer sizes
- [ ] Solo/mute logic works correctly (solo overrides mute)
- [ ] Level meters respond accurately to audio
- [ ] Mixer state persists in project file

---

## 🏗️ Milestone 4: Project System + Undo/Redo (ValueTree-Based)
**Duration**: 4-5 days | **Risk**: 🟡 Medium | **Priority**: HIGH

### Goal
Central state management with full undo/redo support using JUCE ValueTree.

### Architecture

```cpp
// ProjectState.h - Central source of truth
class ProjectState : public juce::ValueTree::Listener {
public:
    ProjectState() : state(juce::Identifier("Project")) {
        state.setProperty("version", 1, nullptr);
        state.appendChild(juce::ValueTree(juce::Identifier("Settings")), nullptr);
        state.appendChild(juce::ValueTree(juce::Identifier("Tracks")), nullptr);
        state.appendChild(juce::ValueTree(juce::Identifier("Transport")), nullptr);
        state.appendChild(juce::ValueTree(juce::Identifier("History")), nullptr);
    }
    
    juce::UndoManager& getUndoManager() { return undoManager; }
    juce::ValueTree& getState() { return state; }
    
    // Typed accessors
    float getBpm() const { return state.getChildWithName("Transport")["bpm"]; }
    void setBpm(float bpm) {
        state.getChildWithName("Transport")
            .setProperty("bpm", bpm, &undoManager);
    }
    
private:
    juce::ValueTree state;
    juce::UndoManager undoManager{30000, 50};  // 50 transactions
};
```

### Tasks

- [ ] **4.1** Create `ProjectState` class with ValueTree hierarchy
  ```
  Project (root)
  ├── Settings
  │   ├── sampleRate: 44100
  │   ├── bufferSize: 512
  │   └── outputDevice: "Default"
  ├── Transport
  │   ├── bpm: 120.0
  │   ├── key: "Aminor"
  │   ├── position: 0.0
  │   └── isPlaying: false
  ├── Tracks
  │   └── Track (id=1)
  │       ├── name: "Drums"
  │       ├── gain: 0.0
  │       ├── pan: 0.0
  │       ├── mute: false
  │       └── solo: false
  └── History
      └── Generation (timestamp)
          ├── prompt: "..."
          └── midiPath: "..."
  ```

- [ ] **4.2** Integrate `juce::UndoManager` with ValueTree
  ```cpp
  // All state changes go through UndoManager
  void setTrackGain(int trackIndex, float gain) {
      auto track = getTrack(trackIndex);
      track.setProperty("gain", gain, &undoManager);
  }
  
  // Group related changes
  void moveTrack(int fromIndex, int toIndex) {
      undoManager.beginNewTransaction("Move Track");
      // ... multiple operations
  }
  ```

- [ ] **4.3** Implement Save/Load with `.mmg` format
  ```cpp
  // Project bundle (folder-based for simplicity)
  // project.mmg/
  //   ├── project.json  (ValueTree as JSON)
  //   ├── midi/         (MIDI files)
  //   ├── stems/        (Audio stems)
  //   └── exports/      (Rendered outputs)
  
  void saveProject(const juce::File& folder) {
      folder.createDirectory();
      auto json = juce::JSON::toString(valueTreeToVar(state));
      folder.getChildFile("project.json").replaceWithText(json);
      // Copy stems, midi, etc.
  }
  
  void loadProject(const juce::File& folder) {
      auto json = folder.getChildFile("project.json").loadFileAsString();
      state = varToValueTree(juce::JSON::parse(json));
  }
  ```

- [ ] **4.4** Add auto-save functionality
  ```cpp
  class AutoSaveManager : public juce::Timer {
  public:
      AutoSaveManager(ProjectState& ps) : projectState(ps) {
          startTimer(120000);  // Every 2 minutes
      }
      void timerCallback() override {
          if (projectState.isDirty()) {
              projectState.saveAutoRecovery();
          }
      }
  };
  ```

- [ ] **4.5** Implement `ApplicationCommandManager` for keyboard shortcuts
  ```cpp
  // Keyboard shortcuts
  enum CommandIDs {
      cmdUndo = 0x1000,
      cmdRedo,
      cmdSave,
      cmdOpen,
      cmdPlay,
      cmdStop
  };
  
  // In MainComponent
  getCommandManager().registerAllCommandsForTarget(this);
  addKeyListener(getCommandManager().getKeyMappings());
  ```

| Shortcut | Action |
|----------|--------|
| `Space` | Play/Pause |
| `Ctrl+Z` / `Cmd+Z` | Undo |
| `Ctrl+Y` / `Cmd+Shift+Z` | Redo |
| `Ctrl+S` / `Cmd+S` | Save Project |
| `Ctrl+O` / `Cmd+O` | Open Project |
| `Escape` | Cancel Generation |

### Acceptance Criteria
- [ ] Save/Load is reliable across machines (relative paths)
- [ ] Projects are portable and self-contained
- [ ] Undo/Redo works for all mixer and transport changes
- [ ] Auto-save recovers from crashes
- [ ] Keyboard shortcuts work globally

---

## 🏗️ Milestone 5: UI/UX Professionalization
**Duration**: 3-4 days | **Risk**: 🟢 Low | **Priority**: MEDIUM

### Goal
Modern, responsive, and "dark mode" interface that scales from laptop to 4K.

### Tasks

- [ ] **5.1** Implement FlexBox/Grid layouts (replace hardcoded pixels)
  ```cpp
  void MainComponent::resized() {
      juce::FlexBox fb;
      fb.flexDirection = juce::FlexBox::Direction::column;
      
      fb.items.add(juce::FlexItem(transportComponent).withHeight(60.0f));
      fb.items.add(juce::FlexItem(promptPanel).withHeight(150.0f));
      fb.items.add(juce::FlexItem(visualizationPanel).withFlex(1.0f));
      fb.items.add(juce::FlexItem(mixerComponent).withHeight(200.0f));
      
      fb.performLayout(getLocalBounds().toFloat());
  }
  ```

- [ ] **5.2** Create custom `AppLookAndFeel`
  ```cpp
  class AppLookAndFeel : public juce::LookAndFeel_V4 {
  public:
      AppLookAndFeel() {
          setColour(juce::ResizableWindow::backgroundColourId, Colours::darkBackground);
          // ... comprehensive colour setup
      }
      
      void drawRotarySlider(juce::Graphics& g, int x, int y, int w, int h,
                            float sliderPos, float startAngle, float endAngle,
                            juce::Slider& slider) override {
          // Custom minimalist knob design
      }
      
      void drawButtonBackground(juce::Graphics& g, juce::Button& btn,
                               const juce::Colour& bgColour,
                               bool isMouseOver, bool isButtonDown) override {
          // Custom button with hover/pressed states
      }
  };
  ```

- [ ] **5.3** Add SVG icons for transport (using JUCE's Drawable)
  ```cpp
  std::unique_ptr<juce::Drawable> playIcon = juce::Drawable::createFromSVG(
      *juce::XmlDocument::parse(BinaryData::play_svg));
  playButton.setImages(playIcon.get());
  ```

- [ ] **5.4** Attach OpenGL context to visualization panel
  ```cpp
  // In VisualizationPanel constructor
  openGLContext.attachTo(*this);
  openGLContext.setContinuousRepainting(true);  // 60fps
  ```

- [ ] **5.5** Improve error UX
  ```cpp
  class ToastNotification : public juce::Component, public juce::Timer {
  public:
      void show(const juce::String& message, Type type, int durationMs);
  private:
      enum class Type { Info, Warning, Error, Success };
  };
  ```

- [ ] **5.6** Add "Copy Diagnostic Bundle" for support
  ```cpp
  void copyDiagnosticBundle() {
      juce::StringArray info;
      info.add("OS: " + juce::SystemStats::getOperatingSystemName());
      info.add("JUCE: " + juce::String(JUCE_MAJOR_VERSION) + "." + ...);
      info.add("Audio Device: " + audioEngine.getCurrentDeviceName());
      info.add("Last Request: " + lastOscRequest);
      // Copy to clipboard
      juce::SystemClipboard::copyTextToClipboard(info.joinIntoString("\n"));
  }
  ```

### Acceptance Criteria
- [ ] App feels responsive while generating
- [ ] Clear error messages for disconnected server, missing dependencies
- [ ] UI scales correctly from 1366x768 to 4K
- [ ] All buttons have hover/pressed states

---

## 🏗️ Milestone 6: Test & CI Hardening
**Duration**: 2-3 days | **Risk**: 🟢 Low | **Priority**: MEDIUM

### Tasks

- [ ] **6.1** Python OSC server tests
  ```python
  # tests/test_osc_handlers.py
  def test_generate_handler_returns_progress():
      """Ensure /generate sends /progress updates."""
      
  def test_cancel_stops_generation():
      """Ensure /cancel terminates active generation."""
      
  def test_request_id_correlation():
      """Ensure response request_id matches request."""
  ```

- [ ] **6.2** Python worker cancellation tests
  ```python
  def test_cancellation_latency():
      """Cancel should stop generation within 500ms."""
      
  def test_progress_event_ordering():
      """Progress events should be monotonically increasing."""
  ```

- [ ] **6.3** JUCE OSC message parsing tests
  ```cpp
  class OSCBridgeTest : public juce::UnitTest {
  public:
      void runTest() override {
          beginTest("Parse /complete message");
          // ...
      }
  };
  ```

- [ ] **6.4** CI pipeline
  ```yaml
  # .github/workflows/ci.yml
  jobs:
    python-tests:
      runs-on: ubuntu-latest
      steps:
        - run: python -m pytest tests/
        
    juce-build:
      runs-on: windows-latest
      steps:
        - run: cmake -B build -G "Visual Studio 17 2022"
        - run: cmake --build build --config Release
  ```

### Acceptance Criteria
- [ ] "Change breaks OSC protocol" is caught automatically
- [ ] All Python tests pass in CI
- [ ] JUCE builds successfully in CI

---

## 🏗️ Milestone 7: Distribution (Windows-First)
**Duration**: 3-4 days | **Risk**: 🟠 Medium-High | **Priority**: LOW

### Tasks

- [ ] **7.1** Python distribution strategy
  - **Option A**: Embed Python runtime + wheels (PyInstaller/cx_Freeze)
  - **Option B**: Bundle a venv in installer
  - **Recommended**: Use `pyinstaller --onedir` for Python backend

- [ ] **7.2** Create Windows installer (Inno Setup or WiX)
  ```iss
  [Setup]
  AppName=AI Music Generator
  AppVersion=1.0.0
  DefaultDirName={autopf}\AI Music Generator
  
  [Files]
  Source: "build\Release\MultimodalMusicGen.exe"; DestDir: "{app}"
  Source: "python_dist\*"; DestDir: "{app}\python"; Flags: recursesubdirs
  Source: "instruments\*"; DestDir: "{app}\instruments"; Flags: recursesubdirs
  ```

- [ ] **7.3** File associations for `.mmg` projects
  ```cpp
  // Register .mmg extension on Windows
  juce::File::createShortcut(...);
  ```

- [ ] **7.4** Content distribution (optional instrument packs)
  - Download manager with integrity checks (SHA-256)
  - Progress indicator for large downloads

### Acceptance Criteria
- [ ] Fresh Windows machine can install and generate audio without manual setup
- [ ] Uninstall removes all components cleanly
- [ ] `.mmg` files open with the application

---

## 🚀 Stretch Milestones (Future)

### VST3/AU Plugin Wrapper
- `PluginProcessor` with host transport sync via `AudioPlayHead`
- State serialization via `getStateInformation()` / `setStateInformation()`
- Parameter automation with `AudioProcessorParameter`
- DAW testing matrix: Ableton, FL Studio, Logic, Cubase, Reaper

### Plugin Hosting (Insert Effects)
- `juce::KnownPluginList` and `juce::PluginDirectoryScanner`
- Plugin window management (external editors)
- Insert slots in mixer channel strips
- Plugin state saved in `.mmg` project

### Real-time MIDI Input
- Record into project with quantization
- Humanization/swing post-processing
- Re-synthesize with stem separation

### Collaboration Features
- Share project bundles with deterministic regeneration (seed-based)
- Cloud storage integration (optional)

---

## 📚 Reference Sources

| Topic | Source |
|-------|--------|
| AudioProcessorGraph | [JUCE Tutorial: Cascading Audio Processors](https://juce.com/tutorials/tutorial_audio_processor_graph) |
| ValueTree + UndoManager | [JUCE Tutorial: Using UndoManager with ValueTree](https://juce.com/tutorials/tutorial_undo_manager_value_tree) |
| VU Meter Standards | ANSI C16.5-1942 (300ms ballistics) |
| dsp::Gain/Panner | [JUCE DSP Module Documentation](https://docs.juce.com/master/group__juce__dsp.html) |
| KnownPluginList | [JUCE Plugin Hosting Documentation](https://docs.juce.com/master/classKnownPluginList.html) |
| FlexBox/Grid | [JUCE Tutorial: Responsive GUI Layouts](https://juce.com/tutorials/tutorial_flex_box_grid) |

---

## 📋 Priority Matrix

| Milestone | Business Value | Technical Risk | Recommended Order |
|-----------|---------------|----------------|-------------------|
| M3: Track Mixer | ⭐⭐⭐⭐⭐ | 🟡 Medium | 1st |
| M4: Project System | ⭐⭐⭐⭐⭐ | 🟡 Medium | 2nd |
| M1: Protocol Hardening | ⭐⭐⭐⭐ | 🟢 Low | 3rd |
| M5: UI/UX Polish | ⭐⭐⭐ | 🟢 Low | 4th |
| M2: /analyze | ⭐⭐⭐ | 🟡 Medium | 5th |
| M6: Testing/CI | ⭐⭐⭐ | 🟢 Low | 6th |
| M7: Distribution | ⭐⭐ | 🟠 High | 7th |

---

**Last Updated**: December 29, 2025  
**Context Tokens**: ~3,500 (optimized from ~15,000 in TODO.md)

---

## ✨ Recent Completions (December 29, 2025)

### ✅ User Control Features Implemented

| Feature | Status | Description |
|---------|--------|-------------|
| **Separate Prompt Windows** | ✅ Complete | Main prompt + smaller "Exclude" field for negative prompts |
| **G-Funk Genre Support** | ✅ Complete | West Coast/G-Funk detection, drum patterns, and instruments |
| **Negative Prompt Parsing** | ✅ Complete | "no rolling notes", "negative prompt:", "--no" syntax support |
| **Piano Roll Click-to-Seek** | ✅ Complete | Click anywhere in piano roll to seek playhead |
| **File Management Panel** | ✅ Complete | Delete, export, rename, reveal in explorer for recent files |
| **Auto-Refresh Fix** | ✅ Complete | Recent files now updates reliably using file count |
| **Silent Gap Reduction** | ✅ Complete | Breakdown/intro/buildup sections now include essential elements |
| **Drum Collision Fix** | ✅ Previously | Fixed drum flamming with shared groove timing |

### Code Changes Summary

**Python (`multimodal_gen/`):**
- `prompt_parser.py`: Added G-Funk keywords, negative prompt parsing, excluded_drums/instruments
- `midi_generator.py`: Added `generate_gfunk_drum_pattern()`, G-Funk genre handling
- `arranger.py`: Improved section configs (no more fully empty breakdowns)
- `utils.py`: Added G-Funk to GENRE_DEFAULTS

**JUCE (`juce/Source/`):**
- `UI/PromptPanel.cpp/h`: **NEW** - Separate prompt and negative prompt input fields
- `UI/Visualization/PianoRollComponent.cpp/h`: Click-to-seek without modifier key
- `UI/RecentFilesPanel.cpp/h`: Full file management system

---

## 🎮 Milestone 0: Robust User Control Features (PRIORITY)
**Duration**: 3-5 days | **Risk**: 🟢 Low | **Priority**: CRITICAL

> **Goal**: Professional DAW-like user controls for intuitive music creation

### ✅ Completed Tasks

- [x] **0.1** Click-to-seek in Piano Roll
  - Removed Ctrl/Cmd modifier requirement
  - Click anywhere to move playhead instantly
  - Works in both timeline and piano roll areas

- [x] **0.2** Negative Prompt Support
  - Parse "negative prompt:", "negative:", "--no", "--neg" prefixes
  - Support pipe separator: "prompt | negative elements"
  - Parse "no [element]", "without [element]", "exclude [element]"
  - Automatically filter excluded elements from drum_elements and instruments

- [x] **0.3** G-Funk Genre Implementation
  - Keywords: g-funk, west coast, dr dre, snoop, warren g, nate dogg, etc.
  - Clean 8th note hi-hats (NO 16th rolls like trap)
  - Bouncy, swung groove (~15% swing)
  - Synth-heavy instrumentation with brass stabs
  - BPM range: 88-105 (default 96)

- [x] **0.4** File Management Panel
  - Right-click context menu on recent files
  - Delete file (with confirmation)
  - Export file to new location
  - Rename file
  - Reveal in Explorer/Finder
  - Delete all files option

- [x] **0.5** Arrangement Continuity
  - Breakdown sections now keep kick, hi-hat, bass (sparse)
  - Intro sections include subtle kick and bass
  - Buildup sections include snare for tension
  - Outro sections keep full drum kit (sparse)

- [x] **0.6** Separate Prompt/Negative Prompt UI
  - Larger main prompt textarea for describing desired music
  - Compact "Exclude (optional)" field for negative elements
  - Visual differentiation with darker background on exclude field
  - Optimization: Skips negative parsing when exclude field is empty
  - Maintains backward compatibility with combined syntax

### 🔲 Remaining User Control Tasks

- [ ] **0.7** Loop Region Selection
  - Click-drag on timeline to create loop region
  - Loop indicators (bars with handles)
  - Toggle loop on/off (L key)
  - Loop region saved in project state
  - **Advanced**: Multiple named loop regions (A/B comparison)
  - **Advanced**: Auto-detect loop points from MIDI pattern boundaries

- [ ] **0.8** Enhanced Transport Controls
  - Return to start (Home key)
  - Return to loop start (Shift+Home)
  - Skip forward/backward by bars (Arrow keys)
  - Fine seek (Shift+Arrow = 1 beat)
  - **Advanced**: Tap tempo (T key)
  - **Advanced**: Count-in before playback (1-2 bar countdown)
  - **Advanced**: Named markers/cue points (M key to add, 1-9 to jump)

- [ ] **0.9** Prompt History & Favorites
  - Recent prompts dropdown
  - Star/favorite prompts
  - Quick re-generate with previous prompt
  - Export prompt library
  - **Advanced**: Prompt templates with `{genre}` `{bpm}` `{key}` variables
  - **Advanced**: Import/export prompt collections (JSON)
  - **Advanced**: Prompt diff viewer (compare two prompts side-by-side)

- [ ] **0.10** Real-time BPM/Key Override
  - Editable BPM field that updates transport
  - Key selector dropdown
  - Re-generate button after changes
  - **Advanced**: Real-time transpose without regeneration
  - **Advanced**: Half-time / Double-time toggle
  - **Advanced**: BPM ramping/automation curves

- [ ] **0.11** Generation Queue & Variations
  - Queue multiple prompts for batch generation
  - Progress indicator per queued item
  - Cancel individual queued items
  - **Advanced**: Auto-variation mode (generate 3 variations from one prompt)
  - **Advanced**: Seed control for reproducible generations
  - **Advanced**: A/B blind comparison mode (rate without seeing prompts)

### Acceptance Criteria
- [ ] New users can navigate without reading documentation
- [ ] All common DAW shortcuts work (space, home, arrows)
- [ ] Prompts can be negative-filtered without special syntax knowledge
- [ ] Genre detection is accurate for all supported genres

---
