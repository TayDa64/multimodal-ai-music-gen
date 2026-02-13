# Phase 7 — Controller Intelligence: Engineering Specification

> **Status**: Draft v1.0  
> **Date**: 2026-02-09  
> **Author**: MUSE Engineering  
> **MPC Beats Version Baseline**: 2.9.0.21 (from `Midi Learn/VERSION.xml`)  
> **Scope**: 7 tasks across XL/L/M/S complexity targeting intelligent hardware controller integration

---

## Table of Contents

1. [Phase Summary](#1-phase-summary)
2. [Decision D-012: target_control Reverse Engineering Scope](#2-decision-d-012)
3. [XMM Format Analysis](#3-xmm-format-analysis)
4. [Task Specifications](#4-task-specifications)
   - [P7-T1: target_control Reverse Engineering (XL)](#p7-t1)
   - [P7-T2: Controller Profile Database (M)](#p7-t2)
   - [P7-T3: Context-Sensitive Auto-Mapping (L)](#p7-t3)
   - [P7-T4: Cross-Controller Translation (M)](#p7-t4)
   - [P7-T5: Dynamic Remap Suggestions (M)](#p7-t5)
   - [P7-T6: Controller Agent Config (S)](#p7-t6)
   - [P7-T7: Controller Visualization (S)](#p7-t7)
5. [Cross-Phase Exports](#5-cross-phase-exports)
6. [Risk Matrix](#6-risk-matrix)
7. [Appendices](#7-appendices)

---

## 1. Phase Summary

**Goal**: Transform MPC Beats hardware controllers from static MIDI mappers into intelligent, context-aware instruments that auto-configure, translate between models, and dynamically remap based on workflow.

**Dependencies**:

| Phase | Dependency | Consumed Artifact |
|---|---|---|
| P0 | `.xmm` XML parser | `ParsedControllerMap` (Contract C3) |
| P5 | Virtual MIDI port | `VirtualMidiPort` (Contract C7) — for experimental probing in T1 |
| P6 | Composer pipeline context | `ComposerPipeline` (Contract C13) — workflow state for T3/T5 |
| P4 | Sound Oracle parameters | `EffectChain` (Contract C10) — mappable parameter targets |

**Exports to**: Phase 10 (Live Performance — controller state, auto-mapping engine, target registry)

**Controller corpus**: 67 `.xmm` files spanning 6 manufacturers (Akai, Alesis, Arturia, Korg, M-Audio, Novation, NI, Ableton) representing the complete set bundled with MPC Beats 2.9.0.21.

---

## 2. Decision D-012: target_control Reverse Engineering Scope

### Question

Should we reverse-engineer all ~116+ `target_control` indices or work with a verified subset?

### Options Analysis

| Option | Coverage | Effort | Risk | Maintenance |
|---|---|---|---|---|
| **(a) All 116+** | 100% | 4-6 weeks | Low (complete map) | Must re-verify on MPC Beats updates |
| **(b) Known subset ~50** | ~43% | 1-2 weeks | Medium (gaps cause auto-mapping failures) | Partial re-verify |
| **(c) Community-sourced** | Variable | 1 week integration | High (unverified, inconsistent) | Depends on community |

### Empirical Evidence from .xmm Corpus

Cross-referencing 67 `.xmm` files reveals the following **actually-used** target_control ranges:

| Index Range | Observed Mapping Types | Consistency Across Files | Likely Function |
|---|---|---|---|
| **0–15** | `type=1` (Note), `control=4` (pad/key) | **All** controllers with pads | Pad Bank A (16 pads) |
| **16–23** | `type=1` or `type=2`, `control=3` or `control=5` | Dual-use: extended pads OR knobs | Pad Bank B / Q-Link Knobs |
| **24–31** | `type=2` (CC), `control=5` or `control=7` | Knob/fader controllers map here | Q-Link Knobs (primary) |
| **32–41** | Almost entirely `type=0` (unmapped) | Unmapped across most controllers | Faders / reserved |
| **42–43** | `type=2` (CC), `control=3` or `control=5` | Push 2, nanoKONTROL2 map here | Transport: Play/Stop or Jog |
| **44–45** | `type=2`, `control=5` | nanoKONTROL2 maps here | Transport: Record/Overdub |
| **46–47** | Mostly `type=0` | Sparse | Transport: reserved |
| **48** | `type=2`, `control=1` (button) | Push 2, nanoKONTROL2 | Transport: Play |
| **52–53** | `type=2`, `control=5` | Push 2 maps here | Browser/navigate |
| **66** | `type=2`, `control=1` | Push 2, nanoKONTROL2 | Transport: Stop |
| **67–116** | `type=0` universally | Never mapped in stock files | Unknown / application-specific |
| **117–244** | Present only in nanoKONTROL2 | Extended address space | Mixer faders, solos, mutes, rec-arm |
| **≥4,086,032** | Anomalous high values in MPD218, nanoKONTROL2 | Memory addresses or versioned internal IDs | Internal MPC state hooks (non-MIDI) |

**Key finding**: Of the 0–116 standard range, only indices **0–31, 42–43, 44–45, 48, 52–53, 66** show active mappings across the corpus. That is approximately **40 indices with observed usage** and **~76 indices that are never mapped in any stock file**.

### Recommendation: **(a) All indices, phased approach**

**Rationale**: Option (b) creates a false ceiling — every unmapped target that turns out to be important requires rework in T3/T4/T5. The nanoKONTROL2's extended range (117–244) proves the address space is larger than initially estimated, and these upper indices likely map to MPC Beats' per-track mixer controls (volume, pan, mute, solo, rec-arm × 8 tracks = 40 additional targets). Completing the full map is essential for proper mixer-mode controller support.

**Phased execution**:

| Sub-phase | Scope | Method | Gate |
|---|---|---|---|
| **7.1a** (Week 1–2) | Indices 0–31, 42–48, 52–53, 66 (~40 targets) | Cross-reference .xmm corpus + MPC Beats UI observation | Unblocks T3/T4 |
| **7.1b** (Week 3–4) | Indices 32–41, 49–51, 54–65, 67–116 (~67 targets) | Experimental probing via virtual MIDI (P5 dependency) | Unblocks T5 mixer features |
| **7.1c** (Week 5–6) | Indices 117–244 (nanoKONTROL2 extended) + anomalous high-value targets | Probing + binary analysis of MPC Beats memory | Complete registry |

**Decision**: **APPROVED — Option (a) with phased gates.** T3 development may begin after 7.1a completes.

---

## 3. XMM Format Analysis

### Schema (derived from 67 files)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<MidiLearnMap_ Manufacturer="{string}" Version="{string}?">
  <device>
    <Input UnixPortName="{string}" WindowsPortName="{string}"/>
    <Output UnixPortName="{string}" WindowsPortName="{string}"/>
    <!-- Some controllers have multiple Input/Output ports (e.g., Oxygen Pro 25 has 4) -->
  </device>
  <midiPreamble>?  <!-- SysEx initialization messages, base64 encoded -->
    <message base64:payload="{base64}"/>
  </midiPreamble>
  <shouldSyncMidi/>?  <!-- Flag: MPC sends MIDI clock to this device -->
  <pairing>  <!-- Repeated 117–245+ times -->
    <Target_ Target_control="{int}"/>  <!-- MPC internal function index -->
    <Mapping_ Mapping_type="{0|1|2}"  <!-- 0=unmapped, 1=note, 2=CC -->
              Mapping_channel="{int}" <!-- MIDI channel (0-indexed internally, -1=any) -->
              Mapping_data1="{int}"   <!-- Note# or CC# -->
              Mapping_control="{int}" <!-- Physical control type enum -->
              Mapping_reverse="{0|1}" <!-- Invert control direction -->
    />
  </pairing>
</MidiLearnMap_>
```

### `Mapping_control` Enum (Reverse-Engineered)

| Value | Physical Control Type | Observed Context |
|---|---|---|
| `1` | **Button** (momentary/toggle) | Transport buttons, scene launch |
| `3` | **Pad** (velocity-sensitive trigger) | Drum pads, note triggers on pad controllers |
| `4` | **Key/Pad** (generic note input) | Piano keys, standard pads |
| `5` | **Knob/Fader** (continuous CC) | Rotary encoders, linear faders |
| `7` | **Knob/Slider** (continuous CC, variant) | Some controllers' knobs (e.g., MPK mini 3 uses 7) |

### Corpus Statistics

| Metric | Value |
|---|---|
| Total `.xmm` files | 67 |
| Files with `<device>` block | 47 (70%) — includes port names |
| Files with `<midiPreamble>` | 12 (18%) — SysEx init required |
| Files with `<shouldSyncMidi/>` | 12 (18%) — clock sync capable |
| Minimum target_control range | 0–116 (most controllers) |
| Maximum target_control range | 0–244 (Korg nanoKONTROL2) |
| Anomalous high-value targets | 7 unique giant values (e.g., `4086032`, `96753616`) |
| Manufacturers represented | Akai, Alesis, Ableton, Arturia, Korg, M-Audio, NI, Novation |

---

## 4. Task Specifications

---

### <a id="p7-t1"></a>P7-T1: target_control Reverse Engineering

| Attribute | Value |
|---|---|
| **Task ID** | P7-T1 |
| **Name** | target_control Reverse Engineering |
| **Complexity** | XL (4–6 weeks, research-heavy) |

#### Description

Systematically decode and document the mapping between every `Target_control` integer index used by MPC Beats' internal `.xmm` controller-mapping format and the human-readable parameter/function it controls within the application. This is a pure research task that cannot be accomplished by reading documentation alone — the mapping is proprietary and undocumented. The approach combines statistical cross-referencing of 67 stock `.xmm` files, experimental probing via virtual MIDI ports, observation of MPC Beats UI state changes, and analysis of the `MpcMmcSetup.pdf` document. The output is a versioned JSON registry that serves as the ground-truth lookup table for all subsequent Phase 7 tasks. The registry must include confidence levels per entry, as some targets may remain unverifiable without access to MPC Beats source code.

#### Dependencies

| Task/Phase | Dependency Type | Notes |
|---|---|---|
| P0 (`.xmm` parser) | Hard | Need parsed `ControlPairing[]` to cross-reference |
| P5 (`VirtualMidiPort`) | Soft (for probing) | Experimental probing requires sending CC/Note to MPC Beats via virtual port |
| `MpcMmcSetup.pdf` | Reference | May contain partial MIDI implementation chart |

#### SDK Integration Points

| SDK Feature | Usage |
|---|---|
| `defineTool("probe_target_control")` | Dev-time tool that sends a MIDI message targeting a specific `target_control` index and logs MPC Beats response |
| `skillDirectories` | Output file `skills/controller/target-control-registry.json` loaded as skill context |

#### Input Interface

```typescript
/**
 * Input to the reverse-engineering pipeline.
 * Represents a single parsed .xmm file providing cross-reference data.
 */
interface XmmCrossReferenceInput {
  /** Source .xmm filename (e.g., "Akai MPK mini 3.xmm") */
  readonly sourceFile: string;

  /** Manufacturer from the XML root attribute */
  readonly manufacturer: string;

  /** Known physical layout of this controller (from spec sheets) */
  readonly knownLayout: KnownControllerLayout;

  /** All pairings where Mapping_type != 0 (active mappings only) */
  readonly activePairings: ReadonlyArray<{
    readonly targetControl: number;
    readonly mappingType: 1 | 2;          // 1=note, 2=CC
    readonly channel: number;
    readonly data1: number;
    readonly controlType: number;         // Mapping_control enum
  }>;
}

/**
 * Known physical layout from manufacturer documentation.
 * Used to correlate target_control indices with physical controls.
 */
interface KnownControllerLayout {
  /** Controller model name */
  readonly model: string;
  /** Number of velocity-sensitive pads */
  readonly padCount: number;
  /** Number of rotary knobs */
  readonly knobCount: number;
  /** Number of linear faders */
  readonly faderCount: number;
  /** Number of piano-style keys */
  readonly keyCount: number;
  /** Named transport buttons present on this controller */
  readonly transportButtons: ReadonlyArray<string>;
}

/**
 * Input for experimental probing of a single target_control index.
 * Requires a running MPC Beats instance and an active virtual MIDI port.
 */
interface ProbeRequest {
  /** The target_control index to probe (0–244+) */
  readonly targetIndex: number;
  /** MIDI message type to send */
  readonly probeType: "cc" | "note";
  /** MIDI channel (1-indexed for readability) */
  readonly channel: number;
  /** CC number or note number */
  readonly data1: number;
  /** CC value or note velocity */
  readonly data2: number;
}
```

#### Output Interface

```typescript
/**
 * A single entry in the target_control reverse-engineering registry.
 * Represents one decoded mapping from integer index to MPC Beats function.
 */
interface TargetControlEntry {
  /** The integer index as it appears in Target_control attributes (0–244+) */
  readonly index: number;

  /** Human-readable parameter name (e.g., "Pad 1", "Track 1 Volume") */
  readonly name: string;

  /** Functional category for grouping and auto-mapping logic */
  readonly category: TargetCategory;

  /** Detailed description of what this target controls in MPC Beats */
  readonly description: string;

  /** The specific MPC Beats UI element or parameter affected */
  readonly mpcFunction: string;

  /** Whether this target accepts note input, CC input, or either */
  readonly inputType: "note" | "cc" | "either" | "unknown";

  /** Expected value range for CC targets */
  readonly valueRange?: { readonly min: number; readonly max: number };

  /** Which .xmm files in the corpus have a non-zero mapping for this index */
  readonly observedInFiles: ReadonlyArray<string>;

  /** How this target was identified */
  readonly confidence: "confirmed" | "inferred" | "experimental" | "unknown";

  /** Method(s) used to determine this mapping */
  readonly verificationMethod: ReadonlyArray<
    "cross-reference" | "experimental-probe" | "documentation" | "behavioral-observation"
  >;

  /** MPC Beats version(s) where this mapping was verified */
  readonly verifiedVersions: ReadonlyArray<string>;
}

type TargetCategory =
  | "pad"              // Drum/note pads (0–15, 16–23)
  | "knob"             // Rotary continuous controls (24–31)
  | "fader"            // Linear continuous controls
  | "transport"        // Play, stop, record, etc.
  | "mixer"            // Track volume, pan, mute, solo
  | "browser"          // Navigate sounds/presets
  | "performance"      // Note repeat, arp, full level
  | "program"          // Program/track select
  | "internal"         // MPC internal state (non-MIDI accessible)
  | "unknown";

/**
 * The complete registry output, versioned and timestamped.
 */
interface TargetControlRegistry {
  /** Schema version for migration support */
  readonly schemaVersion: string;
  /** MPC Beats version this registry was verified against */
  readonly mpcBeatsVersion: string;
  /** ISO timestamp of last verification pass */
  readonly lastVerified: string;
  /** Total entries in the registry */
  readonly totalEntries: number;
  /** Breakdown of confidence levels */
  readonly confidenceSummary: {
    readonly confirmed: number;
    readonly inferred: number;
    readonly experimental: number;
    readonly unknown: number;
  };
  /** The registry entries, keyed by index for O(1) lookup */
  readonly entries: ReadonlyArray<TargetControlEntry>;
}
```

#### Implementation Hints

1. **Start with the 67-file cross-reference**: Parse all `.xmm` files and build a matrix of `target_control → [files that map it, with what Mapping_type and Mapping_control]`. Indices mapped by many controllers with consistent `Mapping_control` values are high-confidence inferences.
2. **Exploit the pad-bank pattern**: Targets 0–15 are mapped as `type=1, control=4` (note/pad) across ALL controllers with pads. The note numbers differ per controller but the target indices are constant. This confirms 0–15 = Pad Bank A.
3. **Disambiguate 16–23**: These show dual behavior — Ableton Push 2 maps them as `type=2, control=5` (knobs) while CTRL49 maps them as `type=1, control=3` (pads). This suggests 16–23 are the **secondary pad/knob bank** whose function depends on MPC Beats' internal mode.
4. **Identify transport targets by `Mapping_control=1` (button type)**: Targets 48 and 66 are mapped as `type=2, control=1` on both Push 2 and nanoKONTROL2. These are almost certainly Play and Stop.
5. **Probe unmapped targets (32–41, 49–51, 54–65, 67–116)** using P5's virtual MIDI port: craft a minimal `.xmm` that maps a known CC to one target at a time, load it, send the CC, observe MPC Beats behavior.
6. **Handle the nanoKONTROL2 extended range (117–244)**: This controller has 8 faders + 8 knobs + transport per channel strip. The extended indices likely map to per-track mixer controls: volume×8, pan×8, mute×8, solo×8, rec-arm×8 = 40 targets, plus additional transport/navigation.
7. **Exclude anomalous high-value targets**: Values like `4086032`, `96753616`, `132638976`, `292467232`, `1143453048`, `1203982464`, `1672134317` appear in multiple files but are always `type=0` (unmapped). These are likely memory pointers or feature flags rather than controllable parameters. Document but deprioritize.
8. **Version-gate the registry**: Include `verifiedVersions` per entry. MPC Beats updates may shift indices. The current baseline is `2.9.0.21`.

#### Testing

| # | Test Case | Expected Result |
|---|---|---|
| 1 | Cross-reference all 67 .xmm files for target 0–15 | 100% yield `type=1` (note) across all pad-equipped controllers; category = "pad" |
| 2 | Cross-reference target 24–31 | Majority yield `type=2` (CC) with `control=5` or `control=7`; category = "knob" |
| 3 | Probe target 48 with CC via virtual MIDI | MPC Beats Play transport activates; confidence = "confirmed" |
| 4 | Probe target 66 with CC via virtual MIDI | MPC Beats Stop transport activates; confidence = "confirmed" |
| 5 | Generate registry JSON | Passes JSON schema validation; all `index` values unique; `totalEntries` matches array length |
| 6 | Verify anomalous targets excluded from standard range | Entries with `index > 10000` have category = "internal" or "unknown" |
| 7 | Load registry in runtime context | O(1) lookup by index returns correct `TargetControlEntry` |

#### Risk + Mitigation

| Risk | Severity | Mitigation |
|---|---|---|
| Some targets may be mode-dependent (function changes based on MPC Beats internal state) | High | Document mode-dependency in `description`; test in multiple MPC Beats modes (drum/clip/sample) |
| MPC Beats may not respond to virtual MIDI probing for all targets | Medium | Fall back to behavioral observation via UI screenshots + manual testing |
| Registry stale after MPC Beats update | Medium | Version-gate all entries; add CI job to re-probe on new MPC Beats releases |

---

### <a id="p7-t2"></a>P7-T2: Controller Profile Database

| Attribute | Value |
|---|---|
| **Task ID** | P7-T2 |
| **Name** | Controller Profile Database |
| **Complexity** | M (1–2 weeks) |

#### Description

Build a structured JSON database containing the physical capabilities and MIDI specifications of all 67 controllers represented in the `.xmm` corpus. Each profile captures pad count, knob count, fader count, key count, transport button presence, MIDI channel assignments, note ranges, and CC assignments. Profiles are derived primarily by parsing `.xmm` files (counting `Mapping_type=1` entries for pads, `Mapping_type=2` entries for continuous controls) and cross-referencing with manufacturer specifications for accuracy. The database serves as the input for auto-mapping (T3), cross-controller translation (T4), and visualization (T7).

#### Dependencies

| Task/Phase | Dependency Type | Notes |
|---|---|---|
| P0 (`.xmm` parser) | Hard | Parsed `ControlPairing[]` needed to count/classify controls |
| P7-T1 (target registry) | Soft | Knowing what targets mean helps classify whether indices 16-23 are pads or knobs for a given controller |

#### SDK Integration Points

| SDK Feature | Usage |
|---|---|
| `skillDirectories` | Output stored as `skills/controller/controller-profiles.json` |
| `defineTool("list_controllers")` | Tool that returns available controller profiles for user selection |
| `defineTool("get_controller_profile")` | Tool that returns detailed profile for a specific controller |

#### Input Interface

```typescript
/**
 * Parsed .xmm data that feeds into profile generation.
 * Uses Contract C3: ParsedControllerMap.
 */
interface ProfileGenerationInput {
  /** The parsed .xmm file data per Contract C3 */
  readonly parsedMap: ParsedControllerMap;

  /** Optional manufacturer spec override for accuracy */
  readonly specOverride?: ManufacturerSpec;
}

/**
 * Optional manufacturer specification data for cross-validation.
 * Manually sourced from product pages / manuals.
 */
interface ManufacturerSpec {
  readonly model: string;
  readonly padCount: number;
  readonly knobCount: number;
  readonly faderCount: number;
  readonly keyCount: number;
  readonly hasAftertouch: boolean;
  readonly hasPitchBend: boolean;
  readonly hasModWheel: boolean;
  readonly transportButtons: ReadonlyArray<string>;
  readonly sourceUrl?: string;
}
```

#### Output Interface

```typescript
/**
 * Complete hardware profile for a single MIDI controller.
 * Combines .xmm-derived data with manufacturer specifications.
 */
interface ControllerProfile {
  /** Unique identifier derived from .xmm filename (slugified) */
  readonly id: string;

  /** Controller manufacturer (from .xmm Manufacturer attribute) */
  readonly manufacturer: string;

  /** Controller model name (from .xmm filename) */
  readonly model: string;

  /** Source .xmm filename */
  readonly xmmFile: string;

  /** Physical control inventory */
  readonly physicalControls: PhysicalControls;

  /** MIDI specification derived from .xmm mappings */
  readonly midiSpec: MidiSpec;

  /** Capability flags for feature detection */
  readonly capabilities: ReadonlyArray<ControllerCapability>;

  /** Device connection info (from .xmm <device> block) */
  readonly connection: ControllerConnection;

  /** Whether this controller requires SysEx initialization */
  readonly requiresSysExInit: boolean;

  /** Whether MPC Beats should send MIDI clock to this device */
  readonly supportsClockSync: boolean;
}

interface PhysicalControls {
  /** Number of velocity-sensitive pads (derived from type=1 targets 0-15 count) */
  readonly pads: number;
  /** Number of rotary knobs (derived from type=2 with control=5|7) */
  readonly knobs: number;
  /** Number of linear faders */
  readonly faders: number;
  /** Number of piano-style keys (0 for pad-only controllers) */
  readonly keys: number;
  /** Transport buttons present (derived from target indices 42-48, 66) */
  readonly transportButtons: ReadonlyArray<string>;
  /** Other buttons (e.g., scene launch, pad bank select) */
  readonly otherButtons: ReadonlyArray<string>;
  /** Whether pads support velocity sensitivity */
  readonly velocitySensitivePads: boolean;
}

interface MidiSpec {
  /** MIDI channel used for pad/note input (from Mapping_channel on targets 0-15) */
  readonly padChannel: number;
  /** Note number range for pads [lowest, highest] */
  readonly padNoteRange: readonly [number, number];
  /** CC numbers assigned to knobs (from targets 24-31) */
  readonly knobCCs: ReadonlyArray<number>;
  /** CC numbers assigned to faders */
  readonly faderCCs: ReadonlyArray<number>;
  /** MIDI channel used for CC controls */
  readonly ccChannel: number;
  /** Number of MIDI ports exposed by this device */
  readonly portCount: number;
}

type ControllerCapability =
  | "velocity-sensitive-pads"
  | "aftertouch"
  | "pitch-bend"
  | "mod-wheel"
  | "transport-controls"
  | "clock-sync"
  | "sysex-init"
  | "multi-port"
  | "extended-pads"       // Has targets 16-23 mapped as pads
  | "mixer-mode"          // Has targets 117+ (per-track mixer controls)
  | "encoders-relative";  // Knobs send relative CC values

interface ControllerConnection {
  /** Port names as they appear on Windows */
  readonly windowsPorts: ReadonlyArray<string>;
  /** Port names as they appear on macOS/Linux */
  readonly unixPorts: ReadonlyArray<string>;
}

/**
 * The complete controller profile database.
 */
interface ControllerProfileDatabase {
  readonly schemaVersion: string;
  readonly generatedFrom: string;           // "MPC Beats 2.9.0.21 .xmm corpus"
  readonly totalProfiles: number;          // 67
  readonly manufacturers: ReadonlyArray<string>;
  readonly profiles: ReadonlyArray<ControllerProfile>;
}
```

#### Implementation Hints

1. **Derive pad count from targets 0–15 active mappings**: Count how many of targets 0–15 have `type=1`. MPK mini 3 has all 16 (8 pads × 2 banks), MPD218 has 16, Korg nanoKONTROL2 has 0 (no pads — all are unmapped). Some controllers map targets 0–7 only (8 pads, single bank).
2. **Derive knob count from targets 24–31**: Count `type=2` entries. MPK mini 3 has 8 (targets 24–31 all mapped). Korg nanoKONTROL2 has 8 (same range). Push 2 has 0 in 24–31 (it uses 16–23 for its top-row knobs).
3. **Handle Ableton Push 2's alternate layout**: Push 2 maps targets 16–23 as CC (knobs), not 24–31. This is a special case — flag the profile with a `layoutVariant` or detect during parsing.
4. **Detect transport controls** by checking targets 42, 43, 48, 66 for `type=2, control=1` (button) mappings. nanoKONTROL2 and Push 2 have these; most pad controllers do not.
5. **Count faders separately from knobs**: Manufacturers spec these distinctly (e.g., MPD226 has 4 faders + 4 knobs). In `.xmm` data, faders and knobs both appear as `type=2, control=5` but faders tend to use sequential CC numbers in a lower range.
6. **Store key count from spec, not .xmm**: Piano keys are not represented in `.xmm` target mappings (they use the DAW's native MIDI input, not the MIDI Learn system). Must be sourced from model name parsing ("25" in "MPK mini 3" → 25 keys) or spec lookup.
7. **Detect multi-port controllers**: M-Audio Oxygen Pro 25 and CTRL49 declare 4 Input/Output port pairs. Flag these as `"multi-port"` capability.

#### Testing

| # | Test Case | Expected Result |
|---|---|---|
| 1 | Parse MPK mini 3 → profile | `pads=16, knobs=8, faders=0, keys=25, padChannel=10` |
| 2 | Parse MPD218 → profile | `pads=16, knobs=6 (targets 24-29 active, or 24-35), faders=0, keys=0` |
| 3 | Parse Korg nanoKONTROL2 → profile | `pads=0, knobs=8, faders=8 (if distinguishable), transport=["play","stop","record"]` |
| 4 | Parse Ableton Push 2 → profile | `pads=16 (or 64), knobs=8 (targets 16–23), transport present` |
| 5 | All 67 files produce valid profiles | No parse failures; `totalProfiles=67`; all profiles pass schema validation |
| 6 | Manufacturer grouping | `manufacturers` array contains exactly the unique set from all `.xmm` files |
| 7 | Capability detection | Controllers with `<shouldSyncMidi/>` have `"clock-sync"` capability; controllers with `<midiPreamble>` have `"sysex-init"` |

#### Risk + Mitigation

| Risk | Severity | Mitigation |
|---|---|---|
| Key count cannot be derived from .xmm | Low | Maintain a static lookup table from model name → key count |
| Fader vs. knob distinction unreliable from .xmm alone | Medium | Use manufacturer spec overrides for controllers with both faders and knobs |
| New controllers not in database | Low | Provide `addControllerProfile()` tool for user to register custom controllers |

---

### <a id="p7-t3"></a>P7-T3: Context-Sensitive Auto-Mapping

| Attribute | Value |
|---|---|
| **Task ID** | P7-T3 |
| **Name** | Context-Sensitive Auto-Mapping |
| **Complexity** | L (2–3 weeks) |

#### Description

Given a detected or user-specified controller and the current workflow context (composing, mixing, performing, sound design), automatically generate an optimal mapping that assigns the most relevant MPC Beats parameters to the controller's available physical controls. The system introspects the active `SongState` to determine which tracks exist, what instruments/effects are loaded, and what the user is currently doing. It then uses the target_control registry (T1) and controller profile (T2) to produce a valid `.xmm` file that can be loaded by MPC Beats. The auto-mapping algorithm implements a priority-based assignment strategy that ensures the most impactful parameters are mapped to the most accessible physical controls.

#### Dependencies

| Task/Phase | Dependency Type | Notes |
|---|---|---|
| P7-T1 (registry, phase 7.1a minimum) | Hard | Must know what target indices control to map them meaningfully |
| P7-T2 (profiles) | Hard | Must know what physical controls are available |
| P0 (`.xmm` writer — Task 0.11) | Hard | Must be able to serialize a valid `.xmm` file |
| P4 (Sound Oracle / EffectChain) | Soft | Used to identify mappable synth/effect parameters |
| C1 (SongState) | Hard | Introspects tracks, presets, effects for contextual mapping |
| C13 (ComposerPipeline) | Soft | Pipeline stage awareness for workflow detection |

#### SDK Integration Points

| SDK Feature | Usage |
|---|---|
| `defineTool("auto_map_controller")` | Primary tool — accepts controller ID + context, returns mapping |
| `defineTool("generate_controller_map")` | Lower-level: generates `.xmm` from explicit assignments |
| `hooks.onPostToolUse` | After sound/mix tools run, optionally trigger re-evaluation of mapping relevance |

#### Input Interface

```typescript
/**
 * Request to auto-generate a controller mapping for the current context.
 */
interface AutoMapRequest {
  /** Controller profile ID (from T2 database), or "auto-detect" */
  readonly controllerId: string;

  /** Workflow context — if omitted, inferred from SongState + recent tool usage */
  readonly context?: WorkflowContext;

  /** Current song state (Contract C1) for track/effect introspection */
  readonly songState: SongState;

  /** Optional: specific track to focus mapping on */
  readonly focusTrackId?: string;

  /** Optional: user preferences for mapping style */
  readonly preferences?: MappingPreferences;
}

type WorkflowContext =
  | "composing-harmony"     // Writing chords/progressions
  | "composing-rhythm"      // Programming drums/percussion
  | "composing-melody"      // Writing melodic lines
  | "mixing"                // Adjusting levels, panning, EQ
  | "sound-design"          // Tweaking synth/effect parameters
  | "performing"            // Live jamming / real-time control
  | "arranging";            // Structuring song sections

/**
 * User preferences that bias the auto-mapping algorithm.
 */
interface MappingPreferences {
  /** Prioritize mapping pads to drums vs. chords vs. clips */
  readonly padMode: "drums" | "chords" | "clips" | "auto";
  /** Prioritize knobs for synth params vs. mixer controls */
  readonly knobMode: "synth" | "mixer" | "effects" | "auto";
  /** Whether to preserve existing mappings where possible */
  readonly preserveExisting: boolean;
}
```

#### Output Interface

```typescript
/**
 * The result of an auto-mapping operation.
 * Includes the generated mapping, human-readable summary, and the .xmm file path.
 */
interface AutoMapResult {
  /** Whether the mapping was successfully generated */
  readonly success: boolean;

  /** The controller profile used */
  readonly controller: ControllerProfile;

  /** The detected or specified workflow context */
  readonly context: WorkflowContext;

  /** Human-readable mapping summary (for display to user) */
  readonly summary: MappingSummary;

  /** The generated control assignments */
  readonly assignments: ReadonlyArray<ControlAssignment>;

  /** Path to the generated .xmm file (if written) */
  readonly xmmFilePath?: string;

  /** Warnings or notes about the mapping */
  readonly warnings: ReadonlyArray<string>;
}

/**
 * A single control assignment: physical control → MPC parameter.
 */
interface ControlAssignment {
  /** The target_control index being assigned */
  readonly targetIndex: number;

  /** Human-readable name of the MPC parameter (from T1 registry) */
  readonly targetName: string;

  /** Physical control type on the hardware */
  readonly physicalControl: "pad" | "knob" | "fader" | "button";

  /** Physical control number (e.g., "Knob 3", "Pad 12") */
  readonly physicalLabel: string;

  /** The parameter being controlled (context-dependent) */
  readonly mappedParameter: string;

  /** Why this parameter was chosen for this control */
  readonly rationale: string;

  /** Priority rank (1 = highest priority mapping) */
  readonly priority: number;

  /** MIDI details for the assignment */
  readonly midi: {
    readonly type: 1 | 2;      // note or CC
    readonly channel: number;
    readonly data1: number;
    readonly controlType: number;
  };
}

/**
 * Human-readable mapping summary for user presentation.
 */
interface MappingSummary {
  /** One-line description: "MPK mini 3 — Mixing Mode (4 tracks)" */
  readonly headline: string;

  /** Grouped display: knobs, pads, faders, buttons each with their assignments */
  readonly groups: ReadonlyArray<{
    readonly groupName: string;      // "Knobs", "Pads", "Transport"
    readonly assignments: ReadonlyArray<{
      readonly label: string;        // "Knob 1"
      readonly parameter: string;    // "Track 1 Volume"
    }>;
  }>;

  /** Parameters that couldn't be mapped due to insufficient controls */
  readonly unmappedParameters: ReadonlyArray<string>;
}
```

#### Implementation Hints

1. **Context detection heuristic**: If `WorkflowContext` is not provided, infer from `SongState`:
   - If last 3 tool calls were `generate_effect_chain`, `analyze_frequency_balance`, `suggest_mix_settings` → `"mixing"`
   - If `focusTrackId` points to a drums track → `"composing-rhythm"`
   - If pipeline stage (C13) is "arrangement" → `"arranging"`
2. **Priority-based knob assignment by context**:
   - `"mixing"` → Track 1–4 Volume (knobs 1–4), Track 1–4 Pan (knobs 5–8)
   - `"sound-design"` → Filter Cutoff, Resonance, Envelope Attack, Decay, LFO Rate, LFO Depth, Oscillator Mix, Drive
   - `"composing-rhythm"` → Note Repeat Rate, Swing, Velocity Sensitivity, Pad Threshold, + 4 effect params
   - `"performing"` → Filter Cutoff, LFO Rate, Delay Feedback, Reverb Mix, + 4 real-time params
3. **Smart pad assignment**: In `"composing-harmony"` mode, if a `ProgressionState` exists, map pads to chord MIDI clusters. "Pad 1 → Am7, Pad 2 → Dm9, Pad 3 → G13, Pad 4 → Cmaj7" etc.
4. **Effect chain awareness**: If the focused track has an `EffectChain` (Contract C10), map knobs to the chain's highest-impact parameters (e.g., reverb wet/dry, compressor threshold, EQ band gain).
5. **Fallback to generic mapping**: If context detection fails, use a universal mapping: knobs → track volumes, pads → standard drum kit notes (GM mapping).
6. **Write `.xmm` atomically**: Generate to a temp path, validate XML, then move to `Midi Learn/` directory. Warn user if admin privileges may be needed on Windows.
7. **Preserve custom mappings**: If `preferences.preserveExisting=true`, load the controller's existing `.xmm`, only overwrite targets that are currently `type=0` (unmapped).

#### Testing

| # | Test Case | Expected Result |
|---|---|---|
| 1 | MPK mini 3 + mixing context + 4 tracks | Knobs 1–4 → Track{1-4} Volume, Knobs 5–8 → Track{1-4} Pan |
| 2 | MPK mini 3 + composing-rhythm context | Pads 1–8 → GM drum notes (kick, snare, HH, etc.), Knobs → note repeat / velocity |
| 3 | MPK mini 3 + composing-harmony + ProgressionState [Am7, Dm9, G13, Cmaj7] | Pads 1–4 → chord MIDI clusters, Pads 5–8 → octave variants |
| 4 | Korg nanoKONTROL2 + mixing context | Faders 1–8 → Track{1-8} Volume, Knobs 1–8 → Track{1-8} Pan (if extended targets verified) |
| 5 | Auto-detect context from tool history | After 3 mixing tools → returns `context="mixing"` |
| 6 | Controller with 0 knobs (Launchpad Mk2) + mixing context | Warning: "No continuous controls available for mixer mapping", falls back to pad-based level triggers |
| 7 | Generated .xmm validates against schema | XML well-formed; all target_control indices within known range; Mapping_type values valid |

#### Risk + Mitigation

| Risk | Severity | Mitigation |
|---|---|---|
| Auto-detected context may be wrong | Medium | Always present mapping summary to user before writing `.xmm`; allow override |
| Synth parameter mapping requires knowledge of synth engine internals | High | Start with generic parameter names; enhance as Sound Oracle (P4) matures |
| `.xmm` written to install directory requires elevated privileges | Medium | Offer to write to user's Documents as alternative, with instructions to copy |

---

### <a id="p7-t4"></a>P7-T4: Cross-Controller Translation

| Attribute | Value |
|---|---|
| **Task ID** | P7-T4 |
| **Name** | Cross-Controller Translation |
| **Complexity** | M (1–2 weeks) |

#### Description

Given an existing mapping for a source controller and a target controller profile, translate the mapping so that the same MPC Beats parameters are controlled by the target hardware's physical controls. The translation handles mismatches in control count (source has 16 pads but target has 8), control type (source uses faders but target only has knobs), and capability gaps (source has transport buttons but target does not). The algorithm produces a translated `.xmm` file and a human-readable migration report documenting what was preserved, adapted, and dropped.

#### Dependencies

| Task/Phase | Dependency Type | Notes |
|---|---|---|
| P7-T2 (controller profiles) | Hard | Need profiles for both source and target controllers |
| P7-T1 (target registry) | Soft | Helpful for prioritizing which mappings to preserve when dropping is necessary |
| P0 (`.xmm` parser + writer) | Hard | Must read source `.xmm` and write target `.xmm` |

#### SDK Integration Points

| SDK Feature | Usage |
|---|---|
| `defineTool("translate_controller_map")` | Primary tool — translates mapping between two controllers |

#### Input Interface

```typescript
/**
 * Request to translate a controller mapping from one hardware model to another.
 */
interface TranslationRequest {
  /** Profile of the source controller (the one with the existing mapping) */
  readonly sourceProfile: ControllerProfile;

  /** The existing mapping on the source controller */
  readonly sourceMapping: ReadonlyArray<ControlAssignment>;

  /** Profile of the target controller (the one to translate TO) */
  readonly targetProfile: ControllerProfile;

  /** Translation strategy for handling control count mismatches */
  readonly strategy: TranslationStrategy;

  /** Optional priority ranking for which mappings to preserve first */
  readonly priorityOverrides?: ReadonlyArray<{
    readonly targetIndex: number;
    readonly priority: number;  // Lower = higher priority = preserved first
  }>;
}

type TranslationStrategy =
  | "preserve-all"     // Map everything possible, drop only if target has no capacity
  | "prioritize-pads"  // Preserve pad mappings first, then knobs, then faders
  | "prioritize-knobs" // Preserve continuous control mappings first
  | "balanced";         // Even distribution across all control types
```

#### Output Interface

```typescript
/**
 * Result of a cross-controller translation operation.
 */
interface TranslationResult {
  /** Whether translation succeeded */
  readonly success: boolean;

  /** The translated mapping assignments for the target controller */
  readonly translatedAssignments: ReadonlyArray<ControlAssignment>;

  /** Detailed migration report */
  readonly report: TranslationReport;

  /** Path to the generated .xmm file for the target controller */
  readonly xmmFilePath?: string;
}

/**
 * Detailed report of what happened during translation.
 */
interface TranslationReport {
  /** Source and target controller names */
  readonly from: string;
  readonly to: string;

  /** Total mappings in the source */
  readonly sourceMappingCount: number;

  /** Mappings successfully translated 1:1 */
  readonly preservedCount: number;

  /** Mappings that required adaptation (e.g., knob → fader) */
  readonly adaptedCount: number;

  /** Mappings that could not be translated and were dropped */
  readonly droppedCount: number;

  /** Details of each preserved mapping */
  readonly preserved: ReadonlyArray<{
    readonly targetIndex: number;
    readonly parameterName: string;
    readonly sourceControl: string;  // "Knob 3"
    readonly targetControl: string;  // "Knob 3"
  }>;

  /** Details of each adapted mapping */
  readonly adapted: ReadonlyArray<{
    readonly targetIndex: number;
    readonly parameterName: string;
    readonly sourceControl: string;  // "Fader 2"
    readonly targetControl: string;  // "Knob 6" (type changed)
    readonly adaptationNote: string; // "Fader → Knob (no faders on target)"
  }>;

  /** Details of each dropped mapping */
  readonly dropped: ReadonlyArray<{
    readonly targetIndex: number;
    readonly parameterName: string;
    readonly sourceControl: string;
    readonly reason: string;         // "Target has 8 pads, source mapping used pad 12"
  }>;

  /** Suggestions for the user */
  readonly suggestions: ReadonlyArray<string>;
}
```

#### Implementation Hints

1. **Build a control-type capacity table**: Compare source and target profiles: `{ pads: { source: 16, target: 8, deficit: 8 }, knobs: { source: 8, target: 8, deficit: 0 }, faders: { source: 4, target: 0, deficit: 4 } }`.
2. **1:1 mapping where capacities match**: If both controllers have 8 knobs, directly map source knob assignments to target knobs in the same order.
3. **Downscaling (more → fewer)**: Use priority ordering from T1 to decide which mappings to keep. For pads reducing from 16 → 8, keep pads 0–7 (the primary bank) and drop 8–15.
4. **Upscaling (fewer → more)**: When target has more controls, leave extras unmapped (or suggest additional mappings from the context).
5. **Type adaptation (fader → knob)**: If source uses faders (targets 32–39) but target has no faders, remap those target indices to available knobs. Note: same CC value range applies, so this is a physical reassignment only.
6. **Transport handling**: If source has transport (targets 42–48, 66) and target lacks transport buttons, generate a warning but don't try to map transport to pads (confusing UX).
7. **Report as first-class output**: The migration report should be presentable directly to the user in chat. Format it for readability.
8. **Bidirectional**: The same function handles both downscaling and upscaling — the algorithm is symmetrical.

#### Testing

| # | Test Case | Expected Result |
|---|---|---|
| 1 | MPK mini 3 (8 pads, 8 knobs) → Launchkey 49 (16 pads, 8 knobs) | 8 pad mappings preserved, 8 knob mappings preserved, report suggests 8 additional pad mappings |
| 2 | NI Maschine MK3 (16 pads, 8 knobs) → MPK mini 3 (8 pads, 8 knobs) | First 8 pad mappings preserved, 8 dropped, all knobs preserved, report lists dropped pads |
| 3 | Launchpad Mk2 (64 pads, 0 knobs) → MPK mini 3 (8 pads, 8 knobs) | 8 of 64 pads preserved, 56 dropped, 0 knobs mapped (source had none), strategy="prioritize-pads" |
| 4 | nanoKONTROL2 (8 faders, 8 knobs) → LPD8 (8 pads, 0 knobs) | Fader and knob mappings adapted to pad triggers with warning "continuous controls mapped to momentary pads — functionality degraded" |
| 5 | Identity translation (same controller) | All mappings preserved, 0 adapted, 0 dropped |

#### Risk + Mitigation

| Risk | Severity | Mitigation |
|---|---|---|
| Continuous-to-momentary adaptation produces unusable mappings | Medium | Generate explicit warning; recommend user consider different target controller for this workflow |
| Priority ordering for drops may not match user intent | Low | Allow `priorityOverrides` in the request; learn from user corrections (Phase 9) |

---

### <a id="p7-t5"></a>P7-T5: Dynamic Remap Suggestions

| Attribute | Value |
|---|---|
| **Task ID** | P7-T5 |
| **Name** | Dynamic Remap Suggestions |
| **Complexity** | M (1–2 weeks) |

#### Description

Monitor the user's workflow in real-time by observing tool usage patterns, `SongState` mutations, and explicit context switches (e.g., "now let's mix") to proactively suggest controller remapping when the current mapping is no longer optimal. The system maintains a lightweight state machine that tracks the inferred workflow context and triggers remap suggestions at transition boundaries. Suggestions are non-intrusive — the user can accept, dismiss, or defer them. The system avoids "nagging" by rate-limiting suggestions and learning from dismissals.

#### Dependencies

| Task/Phase | Dependency Type | Notes |
|---|---|---|
| P7-T3 (auto-mapping) | Hard | Uses auto-mapping to generate the suggested new mapping |
| P6 (pipeline context / C13) | Soft | Pipeline stage provides strong context signal |
| C1 (SongState) | Hard | Observes track/effect mutations |
| SDK hooks | Hard | Requires `onPostToolUse` for monitoring |

#### SDK Integration Points

| SDK Feature | Usage |
|---|---|
| `hooks.onPostToolUse` | After each tool execution, evaluate workflow context and queue remap suggestion if context changed |
| `hooks.onUserPromptSubmitted` | Detect explicit context-switch phrases ("let's mix", "time to perform") |
| `defineTool("suggest_remap")` | Internal tool that generates and presents a remap suggestion |

#### Input Interface

```typescript
/**
 * The state maintained by the remap suggestion engine.
 * Updated after each tool call via onPostToolUse.
 */
interface RemapEngineState {
  /** Currently active controller profile */
  readonly activeController: ControllerProfile | null;

  /** Current workflow context (as last detected) */
  readonly currentContext: WorkflowContext;

  /** The mapping currently loaded for the active controller */
  readonly currentMapping: ReadonlyArray<ControlAssignment>;

  /** Rolling window of recent tool calls (last N tool names) */
  readonly recentTools: ReadonlyArray<{
    readonly toolName: string;
    readonly timestamp: string;
    readonly agentUsed: string;
  }>;

  /** Number of suggestions dismissed in this session (for rate limiting) */
  readonly dismissedCount: number;

  /** Timestamp of last suggestion (for cooldown) */
  readonly lastSuggestionTime: string | null;

  /** Contexts the user has dismissed suggestions for (don't suggest again) */
  readonly suppressedContexts: ReadonlyArray<WorkflowContext>;
}

/**
 * Tool call event that triggers context re-evaluation.
 */
interface ToolCallEvent {
  /** Name of the tool that was just executed */
  readonly toolName: string;
  /** Which agent handled it */
  readonly agentName: string;
  /** Any SongState mutations that occurred */
  readonly songStateDelta?: ReadonlyArray<{
    readonly path: string;
    readonly changeType: "add" | "modify" | "delete";
  }>;
}
```

#### Output Interface

```typescript
/**
 * A remap suggestion presented to the user.
 */
interface RemapSuggestion {
  /** Whether a suggestion is being made */
  readonly shouldSuggest: boolean;

  /** The detected new workflow context */
  readonly detectedContext: WorkflowContext;

  /** The previous workflow context */
  readonly previousContext: WorkflowContext;

  /** Human-readable reason for the suggestion */
  readonly reason: string;

  /** The proposed new mapping (preview, not yet applied) */
  readonly proposedMapping: AutoMapResult;

  /** Changes from current mapping (for user review) */
  readonly changeSummary: {
    readonly reassignedControls: number;
    readonly newlyMappedControls: number;
    readonly unaffectedControls: number;
  };

  /** Confidence that the context switch is genuine (0–1) */
  readonly confidence: number;
}

/**
 * User response to a remap suggestion.
 * Used to update engine state and learn preferences.
 */
interface RemapResponse {
  /** User's decision */
  readonly action: "accept" | "dismiss" | "defer" | "customize";

  /** If customize, which assignments the user modified */
  readonly customizations?: ReadonlyArray<{
    readonly targetIndex: number;
    readonly newParameter: string;
  }>;
}
```

#### Implementation Hints

1. **Context detection via tool-call classification**: Maintain a lookup table mapping tool names to workflow contexts:
   - `generate_progression`, `analyze_harmony`, `transpose_progression` → `"composing-harmony"`
   - `generate_midi`, `humanize_midi`, `analyze_rhythm` → `"composing-rhythm"`
   - `analyze_frequency_balance`, `suggest_mix_settings`, `generate_effect_chain` → `"mixing"`
   - `search_presets`, `modify_preset_params` → `"sound-design"`
2. **Sliding window consensus**: Require 3 consecutive tool calls in the same context category before triggering a suggestion. Single tool calls should not trigger context switches (user might be making a quick adjustment).
3. **Rate limiting**: Minimum 5-minute cooldown between suggestions. Maximum 3 suggestions per session. After 2 dismissals for the same context, suppress that context for the remainder of the session.
4. **Explicit keyword detection via `onUserPromptSubmitted`**: Phrases like "let's mix", "time to master", "let's jam", "play it back" should immediately trigger context detection with high confidence, bypassing the 3-tool-call window.
5. **Confidence scoring**: `confidence = (matchingToolCalls / totalRecentCalls) * contextSwitchFreshness`. Where `contextSwitchFreshness` decays from 1.0 if the user has been in the new context for a while (no need to suggest after 10 minutes).
6. **Non-blocking presentation**: The suggestion is returned as a text message in the chat flow, not as a blocking modal. User can ignore it and continue working.
7. **Persistence of responses**: Store `RemapResponse` in `SongState.history` for Phase 9 (personalization) to learn user preferences.

#### Testing

| # | Test Case | Expected Result |
|---|---|---|
| 1 | Tool sequence: `generate_progression` → `analyze_harmony` → `transpose_progression` | `detectedContext="composing-harmony"`, suggestion generated if current context differs |
| 2 | Tool sequence: `analyze_frequency_balance` → `generate_effect_chain` → `suggest_mix_settings` | `detectedContext="mixing"`, suggestion with `confidence >= 0.8` |
| 3 | User types "let's mix this" (no tool call) | `onUserPromptSubmitted` detects mixing intent, triggers suggestion immediately |
| 4 | User dismisses 2 mixing-context suggestions | Third mixing transition: `shouldSuggest=false` (suppressed) |
| 5 | Rapid context switching (1 mixing tool, then 1 composing tool, then 1 mixing tool) | No suggestion triggered (no 3-consecutive-call consensus) |
| 6 | Same context maintained for 15 minutes | No re-suggestion (context hasn't changed) |
| 7 | User accepts suggestion → mapping applied | `currentMapping` updated, `currentContext` updated, acknowledgment message |

#### Risk + Mitigation

| Risk | Severity | Mitigation |
|---|---|---|
| False positive context detection annoys user | Medium | 3-tool-call consensus + rate limiting + suppression after dismissals |
| `onPostToolUse` hook overhead affects performance | Low | Context evaluation is a lightweight string classification — <1ms |
| User-initiated context phrases not recognized | Low | Maintain extensible keyword list; allow user to add custom trigger phrases |

---

### <a id="p7-t6"></a>P7-T6: Controller Agent Config

| Attribute | Value |
|---|---|
| **Task ID** | P7-T6 |
| **Name** | Controller Agent Configuration |
| **Complexity** | S (0.5–1 week) |

#### Description

Create the `skills/controller/` directory structure and configure the `controller` customAgent with its system prompt, tool registrations, skill file references, and routing rules. The Controller agent is the user-facing interface for all hardware mapping operations — it handles natural language requests like "map my knobs to filter controls", "I switched from MPK mini to Launchkey", and "what is knob 3 doing?" by routing to the appropriate tools from T1–T5. The agent's system prompt includes domain expertise about MIDI controller conventions, MPC Beats' control surface model, and the target_control registry.

#### Dependencies

| Task/Phase | Dependency Type | Notes |
|---|---|---|
| P7-T1 (registry) | Soft | Registry JSON loaded as skill context |
| P7-T2 (profiles) | Soft | Profiles JSON loaded as skill context |
| P7-T3, T4, T5 (tools) | Soft | Tools registered but agent can be configured before they exist |

#### SDK Integration Points

| SDK Feature | Usage |
|---|---|
| `customAgents` | Register the `controller` agent with `infer: true` |
| `skillDirectories` | Point to `skills/controller/` |
| `defineTool()` | Register phase 7 tools under the controller agent |

#### Input Interface

```typescript
/**
 * Controller agent configuration following the Copilot SDK customAgents spec.
 */
interface ControllerAgentConfig {
  readonly name: "controller";
  readonly displayName: "Controller Agent";
  readonly description: string;
  readonly prompt: string;
  readonly tools: ReadonlyArray<string>;
  readonly infer: true;
}
```

#### Output Interface

```typescript
/**
 * The skill directory structure produced by this task.
 */
interface ControllerSkillDirectory {
  /** Skill description file for SDK discovery */
  readonly skillMd: string;        // skills/controller/SKILL.md

  /** Target control registry (from T1) */
  readonly registryJson: string;   // skills/controller/target-control-registry.json

  /** Controller profiles database (from T2) */
  readonly profilesJson: string;   // skills/controller/controller-profiles.json

  /** Workflow-to-mapping conventions reference */
  readonly mappingConventions: string; // skills/controller/mapping-conventions.md
}

/**
 * The agent registration object to include in the main SDK config.
 */
interface ControllerAgentRegistration {
  readonly agent: ControllerAgentConfig;
  readonly tools: ReadonlyArray<MuseToolDefinition>;
}

/**
 * Tool definition following MUSE's defineMuseTool() pattern.
 */
interface MuseToolDefinition {
  readonly name: string;
  readonly description: string;
  readonly parameters: Record<string, unknown>;  // Zod schema reference
  readonly handler: string;                       // module path to handler function
}
```

#### Implementation Hints

1. **Agent system prompt** should include:
   - Domain context: "You are a MIDI controller mapping specialist for MPC Beats..."
   - Target control ranges summary (from T1): "Targets 0–15 = pads, 24–31 = knobs, 48 = play, 66 = stop..."
   - Controller corpus summary: "67 supported controllers from Akai, Alesis, Arturia, Korg, M-Audio, NI, Novation, Ableton"
   - Workflow-mapping conventions: context → knob/pad assignment tables
2. **Tool registrations** (5 tools):
   - `read_controller_map` — parse and display current mapping
   - `generate_controller_map` — generate `.xmm` from explicit assignments
   - `auto_map_controller` — context-aware auto-mapping (T3)
   - `translate_controller_map` — cross-controller translation (T4)
   - `list_controllers` — list available controller profiles
3. **SKILL.md content**: Describe the agent's capabilities, when to route to it, and what data files it references.
4. **Routing hints for `infer: true`**: The description should include keywords like "controller", "knob", "pad", "fader", "mapping", "MIDI controller", "hardware" to help the SDK router dispatch correctly.
5. **File paths are relative to project root**: `skills/controller/SKILL.md`, `skills/controller/target-control-registry.json`, `skills/controller/controller-profiles.json`.

#### Testing

| # | Test Case | Expected Result |
|---|---|---|
| 1 | "Map my knobs to filter controls" → agent routing | SDK routes to `controller` agent, not `sound` or `mix` |
| 2 | "I switched from MPK mini to Launchkey" → agent routing | Routes to `controller` agent, calls `translate_controller_map` |
| 3 | "What is knob 3 doing?" → agent routing | Routes to `controller` agent, calls `read_controller_map` |
| 4 | SKILL.md loads in SDK | Skill directory recognized, JSON files accessible in agent context |
| 5 | All 5 tools registered | `list_controllers`, `read_controller_map`, `generate_controller_map`, `auto_map_controller`, `translate_controller_map` all callable |

#### Risk + Mitigation

| Risk | Severity | Mitigation |
|---|---|---|
| SDK router misroutes controller queries to `mix` agent | Low | Include explicit "controller", "mapping", "hardware" keywords in agent description; test routing priority |
| Skill files too large for context window | Low | Summarize registry/profiles in SKILL.md; load full JSON only when tools are invoked |

---

### <a id="p7-t7"></a>P7-T7: Controller Visualization

| Attribute | Value |
|---|---|
| **Task ID** | P7-T7 |
| **Name** | Controller Visualization |
| **Complexity** | S (0.5–1 week) |

#### Description

Generate human-readable text visualizations of the current controller mapping state, allowing users to see at a glance what each physical control on their hardware is mapped to. The visualization adapts to the specific controller's layout (number of pads, knobs, faders) and includes both the physical control label and the mapped MPC Beats parameter. The output is primarily ASCII/Unicode art suitable for inline display in a CLI chat session, with optional Mermaid diagram output for richer rendering environments. The visualization also shows unmapped controls (available for assignment) and highlights any conflicts or warnings.

#### Dependencies

| Task/Phase | Dependency Type | Notes |
|---|---|---|
| P7-T2 (controller profiles) | Hard | Need physical layout info to draw the controller |
| P7-T1 (target registry) | Soft | Need target names for labels |
| Active mapping (from T3 or existing `.xmm`) | Hard | Need current assignments |

#### SDK Integration Points

| SDK Feature | Usage |
|---|---|
| `defineTool("visualize_controller")` | Generates and returns the visualization string |
| Agent response formatting | Visualization is returned as pre-formatted text in the chat response |

#### Input Interface

```typescript
/**
 * Request to visualize a controller's current mapping state.
 */
interface VisualizationRequest {
  /** Controller profile for layout information */
  readonly profile: ControllerProfile;

  /** Current mapping assignments to display */
  readonly assignments: ReadonlyArray<ControlAssignment>;

  /** Current workflow context (for header display) */
  readonly context: WorkflowContext;

  /** Output format preference */
  readonly format: "ascii" | "mermaid" | "compact";

  /** Whether to show unmapped controls */
  readonly showUnmapped: boolean;

  /** Whether to show MIDI details (CC#, channel) */
  readonly showMidiDetails: boolean;
}
```

#### Output Interface

```typescript
/**
 * The generated visualization.
 */
interface VisualizationResult {
  /** The formatted visualization string */
  readonly visualization: string;

  /** Alternative Mermaid markup (if requested) */
  readonly mermaidMarkup?: string;

  /** Summary statistics */
  readonly stats: {
    readonly mappedControls: number;
    readonly unmappedControls: number;
    readonly totalControls: number;
    readonly utilizationPercent: number;
  };
}
```

#### Implementation Hints

1. **ASCII templates per controller class**: Define templates for common layouts:
   ```
   ┌─────────────────────────────────────────────────────────┐
   │  MPK mini 3 — Mixing Mode                              │
   ├─────────────────────────────────────────────────────────┤
   │  Knobs:                                                 │
   │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                  │
   │  │Vol 1 │ │Vol 2 │ │Vol 3 │ │Vol 4 │                  │
   │  │CC 74 │ │CC 75 │ │CC 76 │ │CC 77 │                  │
   │  └──────┘ └──────┘ └──────┘ └──────┘                  │
   │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                  │
   │  │Pan 1 │ │Pan 2 │ │Pan 3 │ │Pan 4 │                  │
   │  │CC 70 │ │CC 71 │ │CC 72 │ │CC 73 │                  │
   │  └──────┘ └──────┘ └──────┘ └──────┘                  │
   ├─────────────────────────────────────────────────────────┤
   │  Pads:       Bank A                                     │
   │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                  │
   │  │Kick  │ │Snare │ │HH Cl │ │HH Op │                  │
   │  │Note36│ │Note38│ │Note42│ │Note46│                  │
   │  └──────┘ └──────┘ └──────┘ └──────┘                  │
   │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                  │
   │  │Perc1 │ │Clap  │ │Tom H │ │Crash │                  │
   │  │Note44│ │Note40│ │Note48│ │Note49│                  │
   │  └──────┘ └──────┘ └──────┘ └──────┘                  │
   ├─────────────────────────────────────────────────────────┤
   │  8/8 knobs mapped │ 8/8 pads mapped │ 100% utilization │
   └─────────────────────────────────────────────────────────┘
   ```
2. **Compact format** for quick reference: Single line per group: `Knobs: [Vol1] [Vol2] [Vol3] [Vol4] [Pan1] [Pan2] [Pan3] [Pan4]`
3. **Mermaid format** for richer rendering:
   ```mermaid
   graph LR
     subgraph Knobs
       K1["Knob 1<br/>Track 1 Volume<br/>CC 74"]
       K2["Knob 2<br/>Track 2 Volume<br/>CC 75"]
     end
   ```
4. **Unmapped controls** shown as `[──────]` or `[empty]` with a dotted border.
5. **Color-code by category** in Mermaid: pads=blue, knobs=green, faders=orange, transport=red, unmapped=gray.
6. **Pad grid layout**: Show 4×4 grid for 16-pad controllers, 2×4 for 8-pad. Mirror the physical layout.

#### Testing

| # | Test Case | Expected Result |
|---|---|---|
| 1 | MPK mini 3, mixing mode, ASCII format | 8 knobs + 8 pads shown in grid layout with parameter labels |
| 2 | nanoKONTROL2, mixing mode, ASCII format | 8 faders + 8 knobs + transport section shown |
| 3 | Controller with no active mapping (all unmapped) | All controls show `[empty]`, `utilizationPercent=0` |
| 4 | Compact format | One line per control group, no box-drawing characters |
| 5 | Mermaid format | Valid Mermaid graph markup that renders without errors |
| 6 | `showMidiDetails=false` | CC numbers and note numbers omitted from labels |
| 7 | `showUnmapped=false` | Only mapped controls displayed; stats still accurate |

#### Risk + Mitigation

| Risk | Severity | Mitigation |
|---|---|---|
| ASCII art breaks in narrow terminal widths | Low | Compact format as fallback; detect terminal width if available |
| Complex controllers (Push 2 with 64 pads) produce overwhelming output | Low | Show paginated view or summarize large grids: "64 pads: 48 mapped to drum kit, 16 unmapped" |

---

## 5. Cross-Phase Exports

| Export Artifact | Type | Producer Task | Consumer Phase(s) | Contract |
|---|---|---|---|---|
| `target-control-registry.json` | Data file | P7-T1 | P10 (live input → MPC control routing) | `TargetControlRegistry` |
| `controller-profiles.json` | Data file | P7-T2 | P10 (understanding user's physical setup) | `ControllerProfileDatabase` |
| `auto_map_controller` tool | SDK tool | P7-T3 | P6 (include controller setup in pipeline), P10 (performance-mode mapping) | `AutoMapRequest → AutoMapResult` |
| `translate_controller_map` tool | SDK tool | P7-T4 | P10 (controller hot-swap during performance) | `TranslationRequest → TranslationResult` |
| `generate_controller_map` tool | SDK tool | P7-T3 | P6 (full pipeline `.xmm` output) | `ControlAssignment[] → .xmm file` |
| `suggest_remap` tool | SDK tool | P7-T5 | P10 (real-time performance context shifts) | `RemapSuggestion` |
| `visualize_controller` tool | SDK tool | P7-T7 | P10 (live controller overlay display) | `VisualizationResult` |
| `ControllerProfile` interface | TypeScript type | P7-T2 | P6, P10 | Exported from `src/schemas/controller.ts` |
| Controller agent config | SDK config | P7-T6 | P0 (main agent registration) | `ControllerAgentConfig` |

### Contract C11: ControllerMapping (Refined)

The original Contract C11 is refined here with the complete type surface:

```typescript
/**
 * Contract C11 (Refined): Complete controller mapping state.
 * Extends the original ControlAssignment[] + AutomationRoute[] contract
 * with the full type surface produced by Phase 7.
 */
interface ControllerMappingState {
  /** Active controller profile */
  readonly activeProfile: ControllerProfile;

  /** Current workflow context */
  readonly context: WorkflowContext;

  /** Active control assignments (the mapping) */
  readonly assignments: ReadonlyArray<ControlAssignment>;

  /** Automation routes (from original C11 — for time-based parameter automation) */
  readonly automationRoutes: ReadonlyArray<AutomationRoute>;

  /** Mapping metadata */
  readonly metadata: {
    readonly generatedBy: "auto-map" | "translation" | "manual" | "stock";
    readonly generatedAt: string;
    readonly sourceXmmFile?: string;
  };
}

interface AutomationRoute {
  /** Source: physical control on the controller */
  readonly sourceControlIndex: number;
  /** Target: MPC parameter being automated */
  readonly targetControlIndex: number;
  /** Scaling/curve applied to the automation */
  readonly curve: "linear" | "logarithmic" | "exponential";
  /** Value range clamping */
  readonly range: { readonly min: number; readonly max: number };
}
```

---

## 6. Risk Matrix

| ID | Risk | Severity | Probability | Impact | Tasks Affected | Mitigation | Owner |
|---|---|---|---|---|---|---|---|
| R7-01 | target_control indices undiscoverable for some ranges | **Critical** | Medium | Auto-mapping gaps, broken translations | T1, T3, T4 | Phased approach (D-012); mark unknown targets as `"unknown"` category; graceful degradation in T3 | T1 lead |
| R7-02 | MPC Beats version updates shift target indices | **High** | Medium | Entire registry invalidated | T1, T3, T4, T5 | Version-gate registry; detect MPC Beats version from `VERSION.xml`; maintain per-version registries | T1 lead |
| R7-03 | `.xmm` file write requires admin privileges on Windows | **High** | High | Users can't load auto-generated mappings | T3, T4 | Write to user-accessible directory (Documents); provide copy instructions; or use MPC Beats user-data directory | T3 lead |
| R7-04 | Virtual MIDI probing doesn't trigger observable MPC Beats behavior for passive targets | **Medium** | Medium | Some targets remain `"unknown"` | T1 | Mark as unknown; solicit community contributions; attempt binary analysis as last resort | T1 lead |
| R7-05 | Context detection false positives annoy users | **Medium** | Medium | Users disable remap suggestions | T5 | 3-tool consensus, rate limiting, suppression after dismissals | T5 lead |
| R7-06 | Controller SDK router misroutes queries | **Low** | Low | Controller queries handled by wrong agent | T6 | Explicit keywords in agent description; routing integration tests | T6 lead |
| R7-07 | nanoKONTROL2 extended range (117–244) represents a fundamentally different mapping model | **Medium** | Low | Profile/translation logic needs branching | T1, T2, T4 | Separate "extended mixer mode" flag in profiles; handle as a capability tier | T2 lead |
| R7-08 | Anomalous high-value target_controls (>10M) cause integer overflow in some contexts | **Low** | Low | Parser/serializer errors | T1, T2 | Use string representation for anomalous targets; validate range on parse | T1 lead |

---

## 7. Appendices

### Appendix A: .xmm File Corpus Inventory

| # | Filename | Manufacturer | Pads (Active 0–15) | Knobs (Active 24–31) | Transport (42–48, 66) | Extended Range | SysEx Init | Clock Sync |
|---|---|---|---|---|---|---|---|---|
| 1 | Ableton Push 1.xmm | Ableton | 16 | 0* | Yes | No | No | No |
| 2 | Ableton Push 2.xmm | Ableton | 16 | 0* | Yes | No | No | No |
| 3–7 | Akai Advance 25/49/61, APC Key 25, LPD8 Wireless | Akai | Varies | Varies | No | No | No | No |
| 8 | Akai MPD218.xmm | Akai | 16 | 8 | No | No | No | No |
| 9 | Akai MPK mini 3.xmm | Akai | 16 | 8 | No | No | Yes | Yes |
| 10–14 | Akai MPK series | Akai | 16 | 8 | No | No | Varies | Varies |
| 15–29 | Alesis Q/V/VI series | Alesis | Varies | Varies | No | No | No | No |
| 30–31 | Arturia KeyLab/MiniLab | Arturia | Varies | 8 | No | No | No | No |
| 32–34 | Korg nanoKONTROL/nanoPAD | Korg | 0 | 8 | Yes | **0–244** | No | No |
| 35–51 | M-Audio Code/CTRL/Oxygen/Keystation/Hammer series | M-Audio | Varies | 8 | No | No | No | No |
| 52–58 | NI Maschine/Traktor series | NI | 16 | 8 | Varies | No | No | No |
| 59–67 | Novation Impulse/Launchkey/Launchpad series | Novation | Varies | Varies | No | No | No | No |

\* Push 1/2 map targets 16–23 as knobs instead of 24–31.

### Appendix B: Mapping_type and Mapping_control Cross-Reference

```
Mapping_type values:
  0 = Unmapped (no MIDI assignment — target is available for mapping)
  1 = Note On/Off (velocity-sensitive, used for pads and keys)
  2 = Control Change (continuous 0–127, used for knobs, faders, buttons)

Mapping_control values (physical control type hint):
  1 = Button (momentary or toggle, CC-based)
  3 = Pad (velocity-sensitive note trigger — alternate pad mode)
  4 = Key/Pad (standard note input — piano keys or standard pads)
  5 = Knob/Fader (rotary or linear continuous controller)
  7 = Knob/Slider (variant continuous controller — observed on MPK mini 3 knobs)

Channel encoding:
  Values 1–16 represent MIDI channels 1–16
  Value 0 appears in unmapped entries (no channel assigned)
  Value -1 observed in M-Audio Oxygen Pro 25 — likely means "any channel" / omni
  Value 10 is the standard GM drum channel (used by most pad controllers)
  Value 16 used by CTRL49 (DAW integration channel)
```

### Appendix C: Observed Anomalous target_control Values

These values appear in multiple `.xmm` files and are always `type=0` (unmapped). They are NOT part of the standard 0–244 parameter space.

| Value | Hex | Observed In | Hypothesis |
|---|---|---|---|
| 4,086,032 | 0x3E5510 | MPD218, nanoKONTROL2 | Internal feature flag / memory offset |
| 96,753,616 | 0x5C3D7D0 | MPD218, nanoKONTROL2 | MPC Beats preference address |
| 132,638,976 | 0x7E7E500 | MPD218, nanoKONTROL2 | GUI state identifier |
| 292,467,232 | 0x116F2E20 | MPD218, nanoKONTROL2 | Plugin host reference |
| 1,143,453,048 | 0x4424AF78 | MPD218, nanoKONTROL2 | Unknown internal |
| 1,203,982,464 | 0x47C30C80 | MPD218, nanoKONTROL2 | Unknown internal |
| 1,672,134,317 | 0x63A8F2AD | MPD218, nanoKONTROL2 | Unknown internal |

**Recommendation**: Document but exclude from the standard registry. Include in a separate `internal-targets.json` for future binary analysis.

### Appendix D: Task Dependency DAG

```
                   ┌─────────┐
                   │ P0: XMM │
                   │ Parser  │
                   └────┬────┘
                        │
              ┌─────────┼──────────┐
              ▼         ▼          │
         ┌────────┐ ┌────────┐    │
         │ P7-T1  │ │ P7-T2  │    │
         │Registry│ │Profiles│    │
         │  (XL)  │ │  (M)   │    │
         └───┬────┘ └───┬────┘    │
             │          │         │
       ┌─────┼──────────┤         │
       ▼     ▼          ▼         │
  ┌────────┐ ┌────────┐ ┌──────┐ │
  │ P7-T3  │ │ P7-T4  │ │P7-T7│ │
  │AutoMap │ │Translat│ │Viz   │ │
  │  (L)   │ │  (M)   │ │ (S)  │ │
  └───┬────┘ └────────┘ └──────┘ │
      │                           │
      ▼                           │
 ┌────────┐              ┌──────┐│
 │ P7-T5  │              │P7-T6││
 │Dynamic │              │Agent ││
 │Remap(M)│              │ (S)  ││
 └────────┘              └──────┘│
                                  │
                      ┌───────────┘
                      ▼
               ┌────────────┐
               │  Phase 10  │
               │Live Perform│
               └────────────┘
```

**Critical path**: P0 → P7-T1 → P7-T3 → P7-T5

**Parallelizable**: T2 ∥ T1 (after P0), T4 ∥ T3 (after T2), T6 ∥ T7 ∥ T5 (after T2)

### Appendix E: Estimated Effort Breakdown

| Task | Complexity | Dev-Days | Parallelizable With |
|---|---|---|---|
| P7-T1 (Registry) | XL | 15–20 | T2 (after P0 complete) |
| P7-T2 (Profiles) | M | 5–7 | T1 (after P0 complete) |
| P7-T3 (Auto-Map) | L | 8–12 | T4 (after T1a + T2 complete) |
| P7-T4 (Translation) | M | 5–7 | T3 (after T2 complete) |
| P7-T5 (Dynamic Remap) | M | 5–7 | T6, T7 (after T3 complete) |
| P7-T6 (Agent Config) | S | 2–3 | T5, T7 (after T2 complete) |
| P7-T7 (Visualization) | S | 2–3 | T5, T6 (after T2 complete) |
| **Total** | | **42–59 days** | **Critical path: ~30 days (T1→T3→T5)** |

---

*End of Phase 7 Engineering Specification*
