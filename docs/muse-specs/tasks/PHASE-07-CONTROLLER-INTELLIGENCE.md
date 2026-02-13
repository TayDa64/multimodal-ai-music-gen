# Phase 7 — Controller Intelligence

## Phase Overview

**Goal**: Enable intelligent hardware controller integration. The system can auto-configure controller mappings based on workflow context, translate mappings between different controllers, dynamically remap knobs/pads based on the active task, and guide users through physical performance workflows.

**Dependencies**: Phase 0 (controller map parser), Phase 5 (virtual MIDI port, CC parameter mapping), Phase 4 (sound/mix parameters to map)

**Exports consumed by**: Phase 10 (live performance controller integration)

---

## SDK Integration Points

| SDK Feature | Phase 7 Usage |
|---|---|
| `defineTool()` | `auto_map_controller`, `translate_controller_map`, `suggest_mapping`, `generate_controller_map` |
| `customAgents` | `controller` agent with hardware expertise |
| `skillDirectories` | `skills/controller/` with target-control-map.json, controller-profiles.json |
| `hooks.onPostToolUse` | When user switches tasks (mixing → performing), suggest remap |

---

## Task Breakdown

### Task 7.1 — Target_control Reverse Engineering

**Description**: Systematically document what each `Target_control` index (0-115+) maps to in MPC Beats. This is a research task that unlocks all controller intelligence.

**Input**: All 67 `.xmm` files + MPC Beats documentation + experimental testing

**Output**: `data/target-control-registry.json`
```typescript
interface TargetControlEntry {
  index: number;
  name: string;              // "Pad 1", "Track Volume", "Master Tempo"
  category: "pad" | "knob" | "transport" | "mixer" | "browser" | "performance" | "unknown";
  description: string;
  mpcFunction: string;       // detailed MPC Beats function
  observedIn: string[];      // which .xmm files use this target
  confidence: "confirmed" | "inferred" | "unknown";
}
```

**Implementation Hints**:
- **Method 1: Cross-referencing existing .xmm files**
  - Target 0-15: Pads (all controllers with pads map notes here)
  - Target 16-23: Extended pads (16-pad controllers use these)
  - Target 24-31: Knobs (consistent across MPK mini, Code 25, etc.)
  - Targets used by transport controllers map to Play, Stop, Record
  - Targets used only by large controllers (61-key) likely map to advanced features
- **Method 2: Experimental probing**
  - Create custom .xmm with a CC mapped to target N
  - Send CC via virtual MIDI
  - Observe what happens in MPC Beats
  - Document the result
  - Iterate for all target indices 0-115+
- **Method 3: MPC Beats PDF documentation**
  - MpcMmcSetup.pdf may contain MIDI implementation details
  - Check for target control list in official docs
- Known mappings (from observation):
  - 0-15: Pads (drum/note input)
  - 24-31: Track-level knobs (Q-Link knobs on MPC hardware)
  - Likely: track select, program select, master volume, note repeat, pad bank switch
- This is a **high-value research task** — everything in Phase 7 depends on completeness of this registry

**Testing**: Verify by experimental probing for at least 20 target indices. Cross-validate with documented MPC MIDI implementation. Confidence levels assigned for each entry.

**Complexity**: XL

---

### Task 7.2 — Controller Profile Database

**Description**: Build a structured database of all supported controllers with their physical characteristics (pad count, knob count, fader count, transport buttons).

**Input**: 67 `.xmm` files + manufacturer specifications

**Output**: `data/controller-profiles.json`
```typescript
interface ControllerProfile {
  manufacturer: string;
  model: string;
  xmmFile: string;
  physicalControls: {
    pads: number;           // 0-16
    knobs: number;          // 0-8+
    faders: number;         // 0-8+
    keys: number;           // 0-88
    transportButtons: string[];  // ["play", "stop", "record"]
    otherButtons: string[];
  };
  midiSpec: {
    padChannel: number;
    padNoteRange: [number, number];
    knobCCs: number[];
    faderCCs: number[];
  };
  capabilities: string[];  // ["velocity-sensitive-pads", "aftertouch", "pitch-bend"]
}
```

**Implementation Hints**:
- Derive from .xmm parsing:
  - Count Mapping_type=1 entries → pad/key count
  - Count Mapping_type=2 entries → knob/fader count
  - Identify channel + note ranges
- Cross-reference with known specs:
  - MPK mini 3: 8 pads, 8 knobs, 25 keys
  - Launchkey 49: 16 pads, 8 knobs, 49 keys
  - Trigger Finger Pro: 16 pads, 4 knobs, 4 faders
- Store as JSON for runtime lookup

**Testing**: Verify profiles for 5 known controllers against manufacturer specs. Verify pad counts match Mapping_type=1 counts from .xmm. Verify all 67 controllers have profiles.

**Complexity**: M

---

### Task 7.3 — Context-Sensitive Auto-Mapping

**Description**: Given a controller profile and a current workflow context (composing, mixing, performing), automatically generate optimal knob/pad mappings.

**Input**: `ControllerProfile` + current context + active SongState

**Output**: Mapping suggestions + generated .xmm file

**Implementation Hints**:
- Context modes:
  - **Composing (harmony)**: Knobs → synth filter, resonance, envelope, detune
  - **Composing (rhythm)**: Pads → drum sounds, Knobs → velocity sensitivity, note repeat
  - **Mixing**: Knobs → track volumes (first 4), pans, master EQ
  - **Performing**: Knobs → real-time synth parameters (cutoff, LFO rate), Pads → clip launch
  - **Sound design**: Knobs → oscillator params, filter envelope, effects
- Algorithm:
  1. Identify available physical controls from controller profile
  2. For current context, prioritize parameters from Phase 4's effect chain / preset data
  3. Assign highest-priority params to most accessible controls
  4. Generate .xmm file (Task 5.5)
  5. Present mapping to user with descriptions: "Knob 1 → Filter Cutoff, Knob 2 → Resonance, ..."
- Smart features:
  - If user is working on bass track → map bass-relevant parameters
  - If user has an effect chain → map the most impactful effect parameters
  - Suggest complementary pads: "I've mapped pad 13 to A minor, pad 14 to E minor — these are chords from your progression"

**Testing**: Given MPK mini 3 + mixing context → verify 8 knobs mapped to: 4 track volumes + 4 track pans. Given composing context with TubeSynth → verify knobs mapped to synth parameters.

**Complexity**: L

---

### Task 7.4 — Cross-Controller Translation

**Description**: Translate a mapping from one controller to another, adapting for different control counts and capabilities.

**Input**: Source controller profile + target controller profile + existing mapping

**Output**: Translated mapping for target controller

**Implementation Hints**:
- Translation challenges:
  - MPK mini 3 (8 knobs) → Launchkey 61 (8 knobs + 8 faders): distribute across more controls
  - NI Maschine (16 pads, 8 knobs) → MPK mini 3 (8 pads, 8 knobs): merge/prioritize pads
  - Korg nanoKONTROL2 (8 faders, 8 knobs) → LPD8 (8 pads only): map critical controls to pads
- Priority-based assignment:
  1. Map transport controls first (if target has transport buttons)
  2. Map pads (limited by target pad count — prioritize most-used)
  3. Map continuous controls (knobs/faders — prioritize by usage frequency)
  4. Drop lowest-priority mappings if target has fewer controls
- Provide migration report: "Translated 32 mappings from Maschine MK3 to MPK mini 3. 16 pad mappings preserved (8 of 16 — dropped pads 9-16). 8 knob mappings preserved. 12 mappings could not be translated."

**Testing**: Translate MPK mini 3 mapping to Launchkey 49 → verify pad count adapts (8→16). Translate Launchpad Mk2 (64 pads, 0 knobs) to MPK mini 3 (8 pads, 8 knobs) → verify graceful degradation with report.

**Complexity**: M

---

### Task 7.5 — Dynamic Remap Suggestions

**Description**: Monitor workflow context and proactively suggest controller remaps when the user's activity changes.

**Input**: SongState changes, tool usage patterns

**Output**: Remap suggestions at appropriate moments

**Implementation Hints**:
- Triggers for remap suggestions:
  - User switches from composing to mixing ("Now let's work on the mix" → suggest mixing mapping)
  - User starts working on a different track ("Let's adjust the bass" → suggest bass-relevant mappings)
  - User enters performance mode ("Let's jam" → suggest performance mapping)
- Detection heuristic:
  - Track sequence of tool calls: if last 3 calls were `generate_effect_chain`, `analyze_frequency_balance`, `suggest_mix_settings` → mixing context
  - SongState changes: new track added → composing, effect chain modified → mixing
- Implementation via `onPostToolUse` hook:
  - After each tool call, evaluate context
  - If context changed from previous evaluation, queue a remap suggestion
  - Don't suggest more than once per context switch (avoid nagging)
- Suggestion format: "I notice you're working on mixing now. Want me to remap your MPK mini 3 knobs to track volumes and pans?"

**Testing**: Simulate composing → mixing workflow transition. Verify remap suggested after 3rd mixing-related tool call. Verify no duplicate suggestions after dismissal.

**Complexity**: M

---

### Task 7.6 — Controller Agent & Skill Directory

**Description**: Create the `skills/controller/` directory and define the Controller `customAgent`.

**Input**: All Phase 7 outputs

**Output**:
- `skills/controller/SKILL.md`
- `skills/controller/target-control-map.json`
- `skills/controller/controller-profiles.json`
- Controller agent config

**Implementation Hints**:
- Controller agent handles: "Map my knobs to filter controls", "I switched from MPK mini to Launchkey", "What is knob 3 doing?"
- Tools: `["read_controller_map", "generate_controller_map", "auto_map_controller", "translate_controller_map"]`
- Agent prompt includes:
  - Target_control registry reference
  - Controller profile database
  - Workflow-to-mapping conventions

**Testing**: "Map my MPK mini 3 knobs to the TubeSynth filter" → routes to Controller agent → calls auto_map_controller.

**Complexity**: S

---

### Task 7.7 — Controller Visualization

**Description**: Generate a text-based visualization of the current controller mapping so the user can understand what each physical control does.

**Input**: Active mapping + controller profile

**Output**: Formatted text/ASCII visualization

**Implementation Hints**:
- ASCII art layouts for common controllers:
  ```
  MPK mini 3 — Current Mapping (Mixing Mode)
  
  Knobs:  [Vol 1] [Vol 2] [Vol 3] [Vol 4] [Pan 1] [Pan 2] [Pan 3] [Pan 4]
  
  Pads:   [Kick ] [Snare] [HH Cl] [HH Op] [Perc1] [Perc2] [FX   ] [Fill ]
          [Kick2] [Rim  ] [Clap ] [Crash] [Shak ] [Tom H] [Tom M] [Tom L]
  ```
- Include CC numbers and target descriptions
- For complex controllers (Maschine, Push), show simplified view
- LLM can present this inline in chat

**Testing**: Generate visualization for MPK mini 3 composing mode. Verify all 8 knobs and 8 pads shown. Verify labels match the mapping.

**Complexity**: S

---

## Modular Boundaries

| Can develop independently | Notes |
|---|---|
| Task 7.1 (reverse engineering) | Independent research task — START EARLY |
| Task 7.2 (controller profiles) | Depends on Phase 0 parser, otherwise independent |
| Task 7.3 (auto-mapping) | Needs 7.1 + 7.2 |
| Task 7.4 (translation) | Needs 7.2 |
| Task 7.5 (dynamic suggestions) | Needs 7.3 + Phase 6 pipeline context |
| Task 7.7 (visualization) | Needs 7.2 |

**Critical path**: 7.1 → 7.3 → 7.5

---

## Cross-Phase Exports

| Export | Consumer |
|---|---|
| Target_control registry | Phase 10 (mapping live inputs to MPC controls) |
| Controller profiles | Phase 10 (understanding user's physical setup) |
| Auto-mapping engine | Phase 10 (performance-mode mapping) |
| `generate_controller_map` tool | Phase 6 (include controller setup in full pipeline output) |

---

## Risk Flags

| Risk | Severity | Description |
|---|---|---|
| Target_control reverse engineering | Critical | If we can't determine what most targets do, auto-mapping is severely limited. This is THE key research task. |
| MPC Beats version dependency | High | Target indices may change between MPC Beats versions. Need version detection + compatibility matrix. |
| .xmm write permission | Medium | Writing to MPC Beats install directory may require admin privileges on Windows. May need to direct user to copy the file manually. |
| Controller detection | Medium | We can detect controller via MIDI port name matching, but port names aren't always consistent across OS/drivers. |
