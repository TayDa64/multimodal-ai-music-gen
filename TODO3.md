# 🚀 TODO3.md: The Path to Professional Grade
> **Strategic Roadmap for Multimodal AI Music Generator v2.0**
> **Generated**: December 29, 2025
> **Focus**: Architecture, Professional UI/UX, and Advanced Audio Features

---

## 🧐 Comprehensive Analysis & Synthesis

### 1. Current State Assessment
Based on `knowing.md`, `TODO.md`, and codebase analysis, the project has successfully graduated from "Prototype" to "Functional Alpha".

| Component | Status | Strengths | Critical Gaps for "Pro" Status |
|-----------|--------|-----------|--------------------------------|
| **Architecture** | 🟡 Partial | OSC Bridge is robust; Python backend is solid. | **State Management**: Currently ad-hoc. No central "Source of Truth" (ValueTree). No Undo/Redo. |
| **UI/UX** | 🟡 Partial | Visualizations (Spectrum/Piano Roll) are excellent. | **Layout**: Hardcoded `resized()` logic is brittle. **Styling**: Standard JUCE look. **Responsiveness**: Limited. |
| **Audio Engine** | 🟠 Basic | Plays MIDI with simple synth. | **Routing**: No mixer, no effects chain. **Plugins**: No VST/AU hosting. **Latency**: Basic handling. |
| **AI Integration** | 🟢 Good | Prompt parsing and generation work well. | **Workflow**: Linear "Prompt -> Result". Needs "Co-pilot" feel (In-painting, Variations, Drag-and-Drop). |

### 2. The "Professional Grade" Gap
To move from a "Cool Tech Demo" to a "Professional Tool", we must address three pillars:
1.  **Data Integrity**: Users trust the app not to lose work (Undo/Redo, Auto-save).
2.  **Flexibility**: Users want to tweak *everything* (Mixer, Plugins, MIDI editing).
3.  **Feel**: The app must look and feel premium (Custom LookAndFeel, 60fps animations).

---

## 📅 Advanced Implementation Plan (Phases 8-12)

### Phase 8: Architecture Refactor (The "Brain" Transplant)
**Goal**: Move from ad-hoc state to `juce::ValueTree` with full Undo/Redo support.

- [ ] **8.1** Create `ProjectState` class
    - Root `juce::ValueTree` ("Project")
    - Child trees: `Settings`, `Tracks`, `Transport`, `History`
    - Integrate `juce::UndoManager`
- [ ] **8.2** Refactor `AudioEngine` to listen to `ValueTree`
    - Tempo changes in ValueTree -> AudioEngine updates automatically
- [ ] **8.3** Refactor UI to listen to `ValueTree`
    - `ValueTree::Listener` for all components
    - Decouple UI from logic completely
- [ ] **8.4** Implement `ApplicationCommandManager`
    - Centralize all actions (Play, Stop, Generate, Undo, Redo)
    - Add Keyboard Shortcuts (Space for Play, Ctrl+Z for Undo)

### Phase 9: The Mixer & Audio Graph
**Goal**: Professional mixing capabilities with per-track control.

- [ ] **9.1** Implement `juce::AudioProcessorGraph`
    - Replace simple `Synthesiser` with a graph-based engine
    - Allow flexible routing (Track -> Bus -> Master)
- [ ] **9.2** Create `MixerComponent`
    - Vertical channel strips
    - Volume Faders (dB scaled)
    - Pan Knobs
    - Mute/Solo logic (exclusive solo, etc.)
    - VU Meters (Peak & RMS)
- [ ] **9.3** Track Management
    - Add/Remove tracks dynamically
    - Track naming and coloring

### Phase 10: Professional UI/UX Overhaul
**Goal**: A modern, responsive, and "dark mode" interface.

- [ ] **10.1** Implement `juce::FlexBox` & `juce::Grid` layouts
    - Replace hardcoded pixel math in `resized()`
    - Ensure UI scales correctly from Laptop to 4K screens
- [ ] **10.2** Create Custom `LookAndFeel`
    - `AppLookAndFeel` class inheriting `juce::LookAndFeel_V4`
    - SVG Icons for Transport (Play, Stop, Record)
    - Custom Rotary Sliders (minimalist design)
    - Consistent Color Palette (defined in `ColourScheme.h`)
- [ ] **10.3** Hardware Acceleration
    - Attach `juce::OpenGLContext` to `VisualizationPanel`
    - Ensure 60fps rendering for Spectrum and Waveform

### Phase 11: Project Management & Persistence
**Goal**: Save and Load complex projects.

- [ ] **11.1** Define `.mmg` (Multimodal Music Gen) file format
    - XML-based (via `ValueTree::toXmlString`)
    - Stores: MIDI data, Instrument settings, Mixer state, History
- [ ] **11.2** Implement Save/Load Logic
    - `File::saveAsString` / `File::createFile`
    - "Save Changes?" dialog on exit
- [ ] **11.3** Auto-save functionality
    - Background timer saving to `autosave.mmg` every 2 minutes

### Phase 12: VST3/AU Plugin Hosting (The "Holy Grail")
**Goal**: Allow users to use their own plugins on generated tracks.

- [ ] **12.1** Plugin Scanning
    - `juce::KnownPluginList` and `juce::PluginDirectoryScanner`
    - UI for scanning user VST folders
- [ ] **12.2** Plugin Window Management
    - Opening external plugin editors
- [ ] **12.3** Insert Slots in Mixer
    - Allow adding plugins to Mixer channels
    - Save plugin state in `.mmg` file

---

## 🧠 "Ultra-Think" Best Practices (Grounded by Research)

### 1. The "Co-Pilot" Workflow
Don't just generate music; *collaborate* with the user.
*   **History Drag-and-Drop**: The `RecentFilesPanel` should allow dragging a previous MIDI file directly onto a specific track in the `PianoRoll`.
*   **In-Painting**: Allow selecting a time range in the Piano Roll and sending *only that range* back to Python for regeneration ("Fix this drum fill").

### 2. Audio Thread Safety
*   **Rule**: NEVER allocate memory or lock a mutex on the audio thread.
*   **Solution**: Use `juce::AbstractFifo` for passing data between UI (Spectrum) and Audio Thread.
*   **Solution**: Pre-allocate all voices and buffers.

### 3. Visual Feedback
*   **Rule**: The UI should feel "alive".
*   **Implementation**:
    *   Playhead should move smoothly (interpolate between blocks).
    *   Meters should have a slow fallback (peak hold).
    *   Buttons should have "down" states and hover effects.

### 4. Python-JUCE Bridge Optimization
*   **Current**: UDP is fast but unreliable (packet loss).
*   **Future**: Consider TCP for critical messages (Project Save/Load) or Shared Memory (if running locally) for audio data transfer.
