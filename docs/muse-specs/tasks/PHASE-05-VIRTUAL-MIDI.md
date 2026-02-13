# Phase 5 — Virtual MIDI Integration

## Phase Overview

**Goal**: Establish a real-time communication channel between MUSE and MPC Beats via virtual MIDI ports. The AI can send MIDI notes, CC messages, and transport commands to MPC Beats as if it were a physical MIDI controller. This enables the "play-in" feature, live parameter control, and preset switching — all without file-based workarounds.

**Dependencies**: Phase 0 (controller map parser), Phase 3 (MIDI generation for playback content), Phase 1 (harmonic data for what to play)

**Exports consumed by**: Phase 6 (hybrid output: files + MIDI), Phase 7 (controller intelligence sends CCs), Phase 10 (bidirectional MIDI for live performance)

---

## SDK Integration Points

| SDK Feature | Phase 5 Usage |
|---|---|
| `defineTool()` | `send_midi_note`, `send_midi_cc`, `midi_transport`, `play_sequence`, `create_virtual_port` |
| `hooks.onPreToolUse` | Permission check: "MUSE wants to send MIDI to MPC Beats. Allow?" |
| `hooks.onSessionStart` | Check if virtual MIDI port exists, offer to create |
| `hooks.onSessionEnd` | Gracefully close MIDI port |
| MCP Server (optional) | MCP-based MIDI server for editor-agnostic MIDI access |
| `ask_user` tool | Ask user to configure MPC Beats MIDI input settings |

---

## Task Breakdown

### Task 5.1 — Virtual MIDI Port Detection & loopMIDI Integration

**Description**: Detect available MIDI ports on the system, check for existing virtual MIDI ports (loopMIDI), and provide guided setup if no virtual port exists.

**Input**: System MIDI port listing

**Output**:
```typescript
interface MidiPortStatus {
  availableOutputs: string[];
  availableInputs: string[];
  virtualPortDetected: boolean;
  virtualPortName?: string;       // "MPC AI Controller" or existing loopMIDI port
  loopMIDIInstalled: boolean;
  setupRequired: boolean;
  setupInstructions?: string;     // step-by-step if setup needed
}
```

**Implementation Hints**:
- Use `easymidi` or `midi` npm package (wraps RtMidi, cross-platform native binding)
- RtMidi on Windows: lists all MIDI ports via Windows Multimedia API
- loopMIDI (by Tobias Erichsen): creates virtual MIDI cables on Windows
  - Detection: check if "loopMIDI Port" appears in available ports
  - Or check for loopMIDI process: `tasklist | findstr loopMIDI`
  - loopMIDI can be instructed to create ports via its command-line interface
- Alternative: `teVirtualMIDI` SDK (commercial, can be bundled — but has licensing implications)
- Preferred port name: "MPC AI Controller"
- If no virtual port exists:
  1. Check if loopMIDI is installed
  2. If yes, create a port named "MPC AI Controller"
  3. If no, guide user to download loopMIDI (free) or offer manual MIDI routing
- On session start, attempt to auto-open the virtual port silently
- **Important**: MPC Beats must also be configured to receive from this port (user action)

**Testing**: On a system with loopMIDI: verify port detection. Verify port creation via loopMIDI API. On a system without: verify graceful fallback with clear instructions. Mock tests for CI.

**Complexity**: L

---

### Task 5.2 — MIDI Output Service

**Description**: Implement the `VirtualMidiPort` interface (C7 contract) for sending MIDI messages to MPC Beats in real-time.

**Input**: MIDI messages (notes, CCs, transport)

**Output**: Messages sent to virtual MIDI port

**Implementation Hints**:
- Wrap `easymidi` output in the C7 `VirtualMidiPort` interface:
  ```typescript
  class RealTimeMidiPort implements VirtualMidiPort {
    private output: easymidi.Output;
    
    sendNote(ch, note, vel, durMs) {
      this.output.send('noteon', { channel: ch, note, velocity: vel });
      setTimeout(() => {
        this.output.send('noteoff', { channel: ch, note, velocity: 0 });
      }, durMs);
    }
    
    sendCC(ch, cc, value) {
      this.output.send('cc', { channel: ch, controller: cc, value });
    }
    // ...
  }
  ```
- **Threading concern**: Node.js setTimeout has ~4ms minimum resolution, but for note scheduling this is acceptable (human perception threshold: ~10ms)
- For precise multi-note scheduling, use a priority queue with `hrtime()` comparisons:
  - Schedule all events into a sorted queue
  - Run a tight polling loop (requestAnimationFrame not available in Node, use setImmediate or a worker)
  - Better: use `nanotimer` or `worker_threads` with shared buffer
- MIDI channel conventions for MPC Beats:
  - Channel 10: drums (GM standard)
  - Channels 1-9, 11-16: melodic instruments
  - MPC Beats auto-routes based on its track MIDI channel settings
- Error handling: if port closes unexpectedly, log warning and switch to file-only mode

**Testing**: Send a C major chord (C4, E4, G4) → verify all 3 note-on messages are sent. Send CC 74 value 64 → verify CC message. Verify note-off fires after specified duration. Verify no messages sent after port close.

**Complexity**: L

---

### Task 5.3 — MIDI Clock & Transport Sync

**Description**: Implement MIDI clock synchronization so MUSE can start/stop MPC Beats transport and maintain tempo lock.

**Input**: BPM, transport commands (start, stop, continue)

**Output**: MIDI System Real-Time messages

**Implementation Hints**:
- **MIDI Clock**: 24 PPQ (pulses per quarter note) — 24 clock messages per beat
  - At 120 BPM: 24 × 120/60 = 48 clock messages per second → one every ~20.8ms
  - At 130 BPM: one every ~19.2ms
- **Transport messages** (MIDI System Real-Time):
  - Start (0xFA): reset to bar 1, begin playback
  - Stop (0xFC): stop playback
  - Continue (0xFB): resume from current position
  - Clock (0xF8): timing pulse
- Implementation pattern:
  ```typescript
  class MidiClock {
    private intervalMs: number;
    private timer: NodeJS.Timer | null = null;
    
    start(bpm: number) {
      this.intervalMs = 60000 / (bpm * 24);
      this.port.sendStart();
      this.timer = setInterval(() => this.port.sendClock(), this.intervalMs);
    }
    
    stop() {
      if (this.timer) clearInterval(this.timer);
      this.port.sendStop();
    }
  }
  ```
- **Timing accuracy**: setInterval on Node.js has ~1-4ms jitter. For musical applications:
  - Acceptable for non-critical sync (starting/stopping transport)
  - For precise clock, consider `worker_threads` with a high-resolution timer
  - Or: let MPC Beats be the clock master (it generates clock), MUSE just sends start/stop
- MPC Beats clock sync settings: user must set MPC Beats to "MIDI Sync: External" to obey our clock

**Testing**: Start clock at 120 BPM → verify 48 clock messages per second (±2). Stop → verify no more clock messages. Verify Start message precedes first Clock message.

**Complexity**: L

---

### Task 5.4 — Scheduled Event Player

**Description**: Implement the sequence playback system: pre-schedule a set of MIDI events at precise timestamps, then play them back with timing accuracy.

**Input**: `ScheduledMidiEvent[]` (C7 contract) — sorted by timestamp

**Output**: Events dispatched at correct times through the MIDI port

**Implementation Hints**:
- Pre-scheduling pattern (from blueprint): "not reactive firing, but pre-computed event scheduling"
- Algorithm:
  1. Sort events by timestampMs
  2. Record `startTime = process.hrtime.bigint()`
  3. High-resolution playback loop:
     ```typescript
     const playback = setImmediate(function tick() {
       const elapsed = Number(process.hrtime.bigint() - startTime) / 1e6; // ms
       while (eventIndex < events.length && events[eventIndex].timestampMs <= elapsed) {
         dispatch(events[eventIndex]);
         eventIndex++;
       }
       if (eventIndex < events.length) setImmediate(tick);
     });
     ```
  4. For notes: schedule noteOn at timestampMs, noteOff at timestampMs + durationMs
- `worker_threads` variant for better precision:
  - Move the playback loop to a Worker
  - Communicate events via SharedArrayBuffer
  - Worker runs tight loop with < 1ms jitter
- Cancellation: set a flag that the playback loop checks
- Progress callback: report which bar/beat is currently playing
- This is the core of the "play-in" feature: AI generates a sequence, schedules it, MPC Beats records it live

**Testing**: Schedule a 4-beat metronome click (C5 at 0ms, 500ms, 1000ms, 1500ms at 120 BPM). Measure actual dispatch times — verify within 5ms of target. Schedule 100 events → verify all dispatched. Cancel mid-playback → verify remaining events not dispatched.

**Complexity**: XL

---

### Task 5.5 — Custom .xmm Generator ("MPC AI Controller")

**Description**: Generate a custom `.xmm` controller map file that tells MPC Beats how to interpret MIDI from the virtual "MPC AI Controller" port. This maps our MIDI messages to MPC internal controls.

**Input**: Desired mapping configuration (which MIDI CCs map to which Target_controls)

**Output**: Valid `.xmm` file written to MPC Beats `Midi Learn/` directory

**Implementation Hints**:
- Generate XML matching the exact format observed in real .xmm files:
  ```xml
  <?xml version="1.0" encoding="UTF-8"?>
  <MidiLearnMap_ Manufacturer="MUSE" Version="1.0">
    <device>
      <Input WindowsPortName="MPC AI Controller"/>
      <Output WindowsPortName="MPC AI Controller"/>
    </device>
    <midiPreamble/>
    <shouldSyncMidi/>
    <!-- Pad mappings (16 pads) -->
    <pairing>
      <Target_ Target_control="0"/>
      <Mapping_ Mapping_type="1" Mapping_channel="10" Mapping_data1="36" Mapping_control="4"/>
    </pairing>
    <!-- ... -->
    <!-- Knob mappings (8+ knobs) -->
    <pairing>
      <Target_ Target_control="24"/>
      <Mapping_ Mapping_type="2" Mapping_channel="1" Mapping_data1="74" Mapping_control="7"/>
    </pairing>
    <!-- ... -->
  </MidiLearnMap_>
  ```
- Default mapping layout:
  - Pads (Target 0-15): Notes 36-51 on channel 10 — same as MPK mini
  - Knobs (Target 24-31): CCs 74-77 + 70-73 on channel 1
  - Transport: map to MPC transport Target_controls (once reverse-engineered)
- The .xmm file must be placed in the MPC Beats `Midi Learn/` directory
- Use `fast-xml-parser` (builder mode) or string templates for XML generation
- **This is the bridge**: without this file, MPC Beats won't know what to do with our MIDI messages

**Testing**: Generate .xmm file. Parse it back with Phase 0 controller map parser. Verify: manufacturer "MUSE", port name "MPC AI Controller", correct pairing count and mapping values. Verify file is valid XML.

**Complexity**: M

---

### Task 5.6 — MIDI Tool Registration

**Description**: Register all virtual MIDI tools via `defineTool()`.

**Tools to register**:

| Tool | Parameters | Description |
|---|---|---|
| `create_virtual_port` | `{ portName: z.string().default("MPC AI Controller") }` | Create/detect virtual MIDI port |
| `send_midi_note` | `{ channel, note, velocity, durationMs }` | Send a single note |
| `send_midi_cc` | `{ channel, cc, value }` | Send a CC message |
| `midi_transport` | `{ action: "start" | "stop" | "continue" }` | Transport control |
| `play_sequence` | `{ events: ScheduledMidiEvent[], sync: boolean }` | Play a scheduled sequence |
| `play_progression` | `{ progressionPath: string, tempo: number, style: string }` | Play a progression via MIDI |

**Implementation Hints**:
- `play_progression` is a convenience tool that:
  1. Reads the .progression file
  2. Converts to `ScheduledMidiEvent[]` using chord voicing (Task 3.8)
  3. Calculates timing from tempo
  4. Calls `play_sequence`
- All MIDI tools should check if port is open before executing
- Permission handler: first MIDI send in a session requires user approval
- Error messages should guide setup: "Virtual MIDI port not found. Install loopMIDI from..."

**Testing**: End-to-end: create port → play Godly progression at 100 BPM → verify MIDI events sent. Test error handling: attempt send with no port → verify friendly error message.

**Complexity**: M

---

### Task 5.7 — "Play-In" Recording Workflow

**Description**: Implement the complete "play-in" workflow: MUSE sends MIDI Start, streams note events, and MPC Beats records the performance as if a human were playing.

**Input**: Generated MIDI content (from Phase 3) + tempo

**Output**: Live MIDI performance received by MPC Beats recording

**Implementation Hints**:
- Workflow steps:
  1. User arms recording in MPC Beats (manual — guide via chat)
  2. MUSE sends MIDI Start → MPC Beats begins recording
  3. MUSE sends Clock messages for tempo sync
  4. MUSE sends scheduled note events (from the sequence player, Task 5.4)
  5. After sequence completes, MUSE sends MIDI Stop
  6. MPC Beats has recorded the performance as a live take
- Advantages over file import:
  - MPC Beats treats it as a live performance → applies input quantization settings
  - Works with any MPC Beats track (drum programs, keygroups, plugins)
  - No need to navigate import dialogs
- Pre-playback checklist (conveyed to user via chat):
  1. "Is MPC Beats open with a track selected?"
  2. "Is the track's MIDI input set to 'MPC AI Controller'?"
  3. "Is recording armed?"
  4. "Ready to play in a {description}. Press Enter when ready."
- Use `ask_user` SDK tool for the "ready?" confirmation

**Testing**: Full integration test (requires MPC Beats running): play a 4-bar drum pattern → verify recording appears in MPC Beats. Mock test: verify the correct sequence of Start → Clock × N → Notes → Stop messages.

**Complexity**: XL

---

### Task 5.8 — MIDI Input Listener (Foundation for Phase 10)

**Description**: Set up MIDI input listening on the virtual port so MUSE can receive MIDI from MPC Beats or from the user's controller. This is the foundation for Phase 10's live performance features.

**Input**: MIDI messages from the virtual port (note-on, CC, etc.)

**Output**: Parsed MIDI events dispatched to registered callbacks

**Implementation Hints**:
- Use `easymidi` input:
  ```typescript
  const input = new easymidi.Input("MPC AI Controller");
  input.on('noteon', (msg) => {
    callbacks.forEach(cb => cb.onNoteOn(msg.channel, msg.note, msg.velocity));
  });
  input.on('cc', (msg) => {
    callbacks.forEach(cb => cb.onCC(msg.channel, msg.controller, msg.value));
  });
  ```
- Event buffering: collect events in a ring buffer for analysis
  - Buffer last 100 events with timestamps
  - Used by Phase 10 for key detection, pattern analysis
- In Phase 5, just establish the listener infrastructure — Phase 10 adds the intelligence layer
- Handle bidirectional routing carefully: avoid MIDI feedback loops (our output feeding back to our input)
  - Solution: tag outgoing messages and filter them on input

**Testing**: Send a note-on via output → if loopback is configured, verify it appears on input listener. Test callback registration and unregistration. Verify no feedback loop with tagging.

**Complexity**: M

---

### Task 5.9 — MIDI Connection Health Monitor

**Description**: Monitor the virtual MIDI connection health and provide user-friendly status/diagnostics.

**Input**: Ongoing MIDI connection state

**Output**: Health status + diagnostics

**Implementation Hints**:
- Health checks:
  - Port open: `output.isPortOpen()` (or catch errors on send)
  - Latency test: send a CC, measure round-trip if loopback available
  - MPC Beats responsiveness: we can't directly check, but monitor for expected response patterns
- Status levels: "connected", "degraded" (high latency), "disconnected"
- Auto-reconnect: if port drops, attempt to re-open every 5 seconds
- Surface status via a `midi_status` tool that the LLM can query
- Warning on session start if no MIDI port is available (gracefully degrade to file-only mode)

**Testing**: Simulate port disconnection → verify warning emitted and reconnect attempted. Verify `midi_status` tool returns correct status.

**Complexity**: S

---

### Task 5.10 — CC-to-Parameter Mapping Table

**Description**: Create a mapping table that associates MIDI CC numbers used by the virtual controller with meaningful MPC Beats parameters.

**Input**: Phase 0 controller map data + available Target_control indices

**Output**: `data/cc-parameter-map.json`
```typescript
interface CCParameterMap {
  mappings: {
    cc: number;                   // MIDI CC number
    targetControl: number;        // MPC internal Target_control index
    parameterName: string;        // human-readable name
    range: [number, number];      // value range
    defaultValue: number;
    category: "transport" | "mixer" | "plugin" | "performance";
  }[];
}
```

**Implementation Hints**:
- Start with well-known mappings (from observing existing .xmm files):
  - Target 0-15: Pads (note-triggered, not CC)
  - Target 24-31: Knobs (CC-controlled — from MPK mini 3: CCs 70-77)
  - Target 32+: Unknown — require research
- Cross-reference multiple .xmm files to find patterns:
  - What Target_controls do different controllers map to?
  - Which targets appear in ALL controller maps? (likely essential)
  - Which are only in large controllers? (likely advanced features)
- This is a partial deliverable — full reverse-engineering is Phase 7
- For Phase 5, map the basics: pads, first 8 knobs, transport controls (if discoverable)

**Testing**: Verify all CC values are in valid range (0-127). Verify no duplicate Target_control assignments. Cross-reference with at least 3 different controller maps to validate.

**Complexity**: M

---

## Modular Boundaries

| Can develop independently | Notes |
|---|---|
| Task 5.1 (port detection) | Independent — native MIDI enumeration |
| Task 5.2 (MIDI output service) | Depends on 5.1 for port reference |
| Task 5.3 (clock/transport) | Depends on 5.2 |
| Task 5.4 (scheduled player) | Depends on 5.2, independent algorithm |
| Task 5.5 (xmm generator) | Depends on Phase 0 parser knowledge |
| Task 5.8 (input listener) | Depends on 5.1 |
| Task 5.9 (health monitor) | Depends on 5.1 + 5.2 |

**Critical path**: 5.1 → 5.2 → 5.3 + 5.4 (parallel) → 5.7

---

## Cross-Phase Exports

| Export | Consumer |
|---|---|
| `VirtualMidiPort` implementation | Phase 6 (hybrid output), Phase 7 (controller sends CCs), Phase 10 (live) |
| `ScheduledEventPlayer` | Phase 6 (play-in), Phase 10 (real-time harmonization output) |
| `MidiClock` | Phase 6 (synced playback), Phase 10 |
| `MidiInputListener` | Phase 10 (receive user input) |
| `CCParameterMap` | Phase 7 (controller mapping) |
| MIDI tools (all) | Phase 6+ (available to all agents) |

---

## Risk Flags

| Risk | Severity | Description |
|---|---|---|
| loopMIDI dependency | High | Users must install loopMIDI separately. No way to programmatically install it. Must provide clear instructions. |
| Native MIDI library compilation | High | `easymidi`/`midi` use RtMidi native bindings. Must compile for user's system (node-gyp). Consider pre-built binaries or `@julusian/midi`. |
| Real-time timing precision | High | JavaScript's event loop is not real-time. setInterval drift accumulates. For 16th notes at 140 BPM (≈107ms), 4ms jitter may be noticeable. Worker threads or native timing needed. |
| MPC Beats MIDI input configuration | High | User must manually configure MPC Beats to receive from the virtual port. There's no API to automate this. Must provide clear step-by-step guidance. |
| MIDI feedback loops | Medium | If virtual port is bidirectional and improperly configured, outgoing messages may feed back. Implement message tagging or channel isolation. |
| Windows-only | Medium | Virtual MIDI on Windows requires loopMIDI. macOS has IAC Driver (built-in). Linux has ALSA virtual MIDI. Phase 5 should abstract the platform difference even if MPC Beats is Windows-only. |
