# Master Implementation Plan

> **Synthesis of**: `TODO.md` (JUCE Roadmap), `TODOtasks.md` (Platform Hardening), and `likuTasks.md` (Producer Features).
> **Status**: Living document for remaining implementation work.

---

## 🟢 Phase 1: Platform Hardening (The Bridge)
**Goal**: Ensure rock-solid communication between JUCE UI and Python Backend before adding complex features.

- [ ] **1.1 Protocol Robustness**
    - [ ] **Python**: Update `Messages.py` / OSC handlers to require and echo `request_id`.
    - [ ] **JUCE**: Update `OSCBridge` to generate UUIDs for requests.
    - [ ] **JUCE**: Implement timeout logic (if no response in 5s -> Error).
    - [ ] **JUCE**: Implement Connection State Machine (Connecting, Connected, Disconnected, Generating).

---

## 🟢 Phase 2: The "Producer" Audio Engine (Python Backend)
**Goal**: Upgrade the generation quality with Groove and Mix "Glue" (Milestones F & G from `likuTasks.md`).

- [x] **2.1 Groove Templates (Milestone F)**
    - [x] **Python**: Create `multimodal_gen/groove_templates.py`.
        - Define `GrooveTemplate` dataclass (timing offsets, velocity offsets).
        - Implement serialization to `grooves/<name>.json`.
    - [x] **Python**: Update `MidiGenerator` to apply groove offsets non-destructively (keep base quantization data).
    - [x] **Python**: Expose groove options in `session_manifest.json`.

- [x] **2.2 Mix Glue & Polish (Milestone G)**
    - [x] **Python**: Create `multimodal_gen/mix_chain.py`.
        - Define FX chain models (EQ, Compression, Saturation).
    - [x] **Python**: Update `AudioRenderer` to apply FX chains during rendering.
    - [x] **Python**: Implement configurable audio tails (prevent reverb cutoff).
    - [x] **Python**: Generate `stems_manifest.json` with peak/RMS data.

---

## 🟡 Phase 3: Professional Mixing Interface (JUCE Frontend)
**Goal**: Real-time mixing capability in the UI (Phase 8 from `TODO.md`).

- [x] **3.1 Audio Graph Architecture**
    - [x] **JUCE**: Create `Source/Audio/Processors/ProcessorBase.h`.
    - [x] **JUCE**: Create `GainProcessor` and `PanProcessor` (wrapping `juce::dsp`).
    - [x] **JUCE**: Create `MixerGraph` class to manage the `AudioProcessorGraph`.

- [x] **3.2 Mixer UI**
    - [x] **JUCE**: Create `LevelMeter` component (VU ballistics + Peak hold).
    - [x] **JUCE**: Create `ChannelStrip` component (Volume Fader, Pan Knob, Mute/Solo).
    - [x] **JUCE**: Create `MixerComponent` to host strips dynamically based on track count.

---

## 🟡 Phase 4: Project Management (JUCE Frontend)
**Goal**: Save/Load sessions and Undo/Redo support (Phase 10 from `TODO.md`).

- [ ] **4.1 State Management**
    - [ ] **JUCE**: Create `ProjectState` class wrapping `juce::ValueTree`.
    - [ ] **JUCE**: Integrate `juce::UndoManager` for all value changes.

- [ ] **4.2 Persistence**
    - [ ] **JUCE**: Define `.mmg` file format (JSON + Asset folder structure).
    - [ ] **JUCE**: Implement `saveProject()` and `loadProject()` logic.
    - [ ] **JUCE**: Add "Recent Projects" management.

---

## 🟠 Phase 5: Advanced Producer Tools
**Goal**: High-level features for power users.

- [ ] **5.1 Analysis Workflow** (Milestone 2)
    - [ ] **Python**: Implement `/analyze` endpoint (BPM, Key, Spectral).
    - [ ] **JUCE**: Add "Import & Analyze" UI flow.

- [ ] **5.2 Instrument Browser** (Phase 9)
    - [ ] **JUCE**: Create `InstrumentDatabase` and `CategoryTree`.
    - [ ] **JUCE**: Implement Sample Preview with waveform.

- [ ] **5.3 Plugin Hosting** (Milestone I)
    - [ ] **JUCE**: Implement `PluginDirectoryScanner`.
    - [ ] **JUCE**: Allow loading VST3 effects in the Mixer Graph.
