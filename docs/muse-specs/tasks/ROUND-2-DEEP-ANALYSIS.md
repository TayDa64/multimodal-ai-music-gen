````markdown
# MUSE — Round 2 Deep Analysis

## Cross-Cutting Architectural Decisions & SDK Integration Strategy

> **Context**: This document deepens the existing per-phase task files (PHASE-00 through PHASE-10) with cross-cutting analysis, SDK integration trade-offs, integration test plans, and gotcha documentation. It answers the six deep questions (A–F) with concrete architectural prescriptions.

---

## Part I: The Six Deep Questions

### Question A — Multi-Agent Architecture via `customAgents`

**The Problem**: The blueprint defines 6+ specialized agents (Harmony, Rhythm, Sound, Mix, Controller, Composer). The Copilot SDK's `customAgents` supports named agents with `infer: true` for auto-routing. How should we structure this?

**Architecture Decision: Single Session, 6 Agents, Shared Tool Pool**

```typescript
// Entry point configuration
const config: CopilotConfig = {
  customAgents: [
    harmonyAgent,    // chord progressions, music theory
    rhythmAgent,     // beats, grooves, arp patterns
    soundAgent,      // preset selection, timbral design
    mixAgent,        // mixing, mastering, frequency balance
    controllerAgent, // hardware mapping, MIDI controller config
    composerAgent,   // orchestrator — access to ALL tools
  ],
  // Tools are registered globally; agents declare which subset they use
  tools: [...allTools],
  systemMessage: { mode: "append", content: museSystemPrompt },
  infiniteSessions: true,
};
```

**Why Single Session (not Multiple Sessions)**:

| Approach | Latency | Context Sharing | State Consistency | SDK Fit |
|---|---|---|---|---|
| **Single session, 6 agents** | Low (same session, agent-to-agent routing is internal) | Implicit (shared conversation context) | Guaranteed (one SongState) | Native (`customAgents` + `infer`) |
| Multiple sessions (one per agent) | High (session creation ~500ms each, JSON-RPC overhead) | Explicit (must serialize/deserialize between sessions) | Manual (multiple SongStates to reconcile) | Forced (SDK doesn't provide inter-session messaging) |
| Single agent with role-switching | Lowest | Full | Guaranteed | Possible but loses routing intelligence |

**Verdict**: Single session with 6 agents. The `infer: true` routing handles 80% of queries correctly. The Composer agent acts as catch-all for complex or ambiguous requests.

**Trade-off: `infer` Routing Accuracy**

The SDK's LLM-based routing examines the user query and dispatches to the best-matching agent based on `description` fields. Failure modes:

1. **Ambiguous domain**: "Make the bass warmer" — Sound (timbral design) or Mix (EQ adjustment)?
   - Mitigation: Sound agent handles creative warmth (preset, effect choice). Mix agent handles corrective warmth (EQ cut at 2kHz). Both descriptions must be precise.
   - Fallback: Composer agent has `tools: ["*"]` and catches misrouted queries.

2. **Cross-domain requests**: "Create a neo-soul chord progression and suggest presets for it"
   - This is a Composer-level task (multi-agent coordination).
   - Routing: Composer's description includes "multi-step", "combine", "full song", "end-to-end".
   - The Composer internally calls harmony tools then sound tools sequentially.

3. **Simple factual queries**: "What presets does TubeSynth have?"
   - Could route to Sound agent or Composer.
   - Low-stakes misrouting — both have access to `list_presets`.

**Agent Prompt Size Budget**:

Each `customAgent.prompt` consumes context. Budget allocation:

| Agent | Prompt Tokens | Content |
|---|---|---|
| Harmony | ~800 | Theory reference, voicing rules, tension formula, corpus examples |
| Rhythm | ~600 | Groove conventions, humanization philosophy, GM drum map |
| Sound | ~700 | Preset catalog summary, signal flow rules, genre-preset map |
| Mix | ~500 | Frequency zones, genre mix templates, masking rules |
| Controller | ~400 | Target_control reference, controller profiles summary |
| Composer | ~1000 | Pipeline stages, sensitivity annotations, iteration philosophy, artist-genre lookup |
| **Total** | **~4000** | Only active agent's prompt is loaded per turn |

**Critical Insight**: The SDK loads only the active agent's prompt per turn (not all 6 simultaneously). This means per-agent prompts can be richer than if all were concatenated into a single system message. This is a significant advantage of `customAgents` over a single-agent architecture.

---

### Question B — Musical Knowledge: Skills vs. Tools vs. System Message

**The Problem**: Where should musical knowledge live? The SDK offers three vehicles:
- `systemMessage.content` — always in context
- `skillDirectories` — loaded as files the LLM can reference
- `defineTool()` — callable functions that compute and return results

**Architecture Decision: Three-Tier Knowledge Placement**

```
┌─────────────────────────────────────────────────────────────────┐
│ Tier 1: System Message (~700 tokens)                            │
│ ─────────────────────────────────────────────────────────────── │
│ Identity, behavioral rules, workspace summary, active SongState │
│ L0 summary. ALWAYS in context. Changes every session.           │
│                                                                 │
│ Content: "You are MUSE... This workspace has 47 progressions,   │
│ 80 arp patterns... Current song: Eb minor, 130 BPM, 4 tracks"  │
├─────────────────────────────────────────────────────────────────┤
│ Tier 2: Skill Files (loaded on demand by agent)                 │
│ ─────────────────────────────────────────────────────────────── │
│ Static domain knowledge that grounds the LLM's existing         │
│ knowledge in MUSE-specific vocabulary and conventions.           │
│                                                                 │
│ • skills/harmony/theory-reference.md (~2000 tokens)             │
│   → Scales, modes, chord construction, cadence types, Roman     │
│     numeral conventions used by MUSE's analyzer                 │
│                                                                 │
│ • skills/harmony/genre-dna.json (~500 tokens)                   │
│   → Genre DNA vectors — the LLM reasons about these directly   │
│                                                                 │
│ • skills/sound/preset-catalog.json (~3000 tokens for summary)   │
│   → Engine names, categories, counts — NOT full descriptions    │
│                                                                 │
│ • skills/rhythm/groove-templates.json (~400 tokens)             │
│   → Named groove types with parameter values                   │
│                                                                 │
│ • skills/mix/frequency-zones.md (~300 tokens)                   │
│   → Frequency zone definitions, genre mixing conventions        │
│                                                                 │
│ • skills/controller/target-control-map.json (~800 tokens)       │
│   → Reverse-engineered MPC internal function indices            │
├─────────────────────────────────────────────────────────────────┤
│ Tier 3: Tools (computed on demand, returns structured data)      │
│ ─────────────────────────────────────────────────────────────── │
│ Any knowledge that requires COMPUTATION or FILE ACCESS.          │
│                                                                 │
│ • read_progression → parse JSON + enrich with analysis          │
│ • search_assets → embed query + cosine similarity search        │
│ • analyze_harmony → Roman numerals + tension scoring            │
│ • recommend_preset → filter + rank + explain                    │
│ • analyze_frequency_balance → spectral estimation               │
│ • calculate_effect_params → BPM-synced delay/LFO values        │
└─────────────────────────────────────────────────────────────────┘
```

**Why This Split**:

| Knowledge Type | Vehicle | Reasoning |
|---|---|---|
| MUSE identity & behavioral rules | System message | Must ALWAYS be present; defines persona |
| Current SongState L0 | System message | Changes every turn; context-critical |
| Music theory reference tables | Skill files | Static; the LLM already knows theory but needs MUSE's specific vocabulary/conventions grounded |
| Genre DNA vectors | Skill files | Static data; LLM reasons about it directly without computation |
| Preset catalog summary | Skill files | Too large for system message (~3000 tokens), but agents need high-level awareness |
| Full preset descriptions (~400 items) | Tools (`list_presets`, `search_assets`) | Too large to ever fit in context; must be queried on demand |
| Progression analysis | Tools (`analyze_harmony`) | Requires computation (tension formula, voice leading algorithm) |
| Embedding search results | Tools (`search_assets`) | Requires ONNX inference; cannot be pre-loaded |

**Trade-off: Skills vs. Enlarged Agent Prompts**

The SDK loads skill files from `skillDirectories` and makes them available to the LLM. An alternative is to inline the content directly into the agent's `prompt` field. Trade-offs:

- **Skill files**: Modular, replaceable, version-controlled independently, can be shared across agents. But: the SDK's skill loading mechanism may have undocumented behavior around when/how skills are injected.
- **Agent prompt inlining**: Guaranteed to be in context when that agent is active. Full control over ordering and emphasis. But: harder to maintain, duplicated if shared between agents.

**Recommendation**: Use skill files for shared knowledge (genre DNA, frequency zones). Use agent prompt inlining for agent-specific framing (the Harmony agent's theory emphasis, the Rhythm agent's groove philosophy). The hybrid approach:

```typescript
const harmonyAgent = {
  name: "harmony",
  prompt: `You are the Harmony specialist within MUSE.
    
    When analyzing progressions, use the tension formula:
    T = w_r·R + w_s·(1-S) + w_d·D + w_c·C
    
    Always ground explanations in the MPC Beats corpus
    (47 progressions available via read_progression tool).
    
    Refer to skills/harmony/genre-dna.json for genre vectors.
    Refer to skills/harmony/theory-reference.md for terminology.`,
  tools: [...harmonyTools],
  infer: true,
};
```

---

### Question C — `infiniteSessions` Compaction vs. L0–L3 Hierarchical Compression

**The Problem**: The SDK's `infiniteSessions` feature automatically compacts conversation history when the context window fills up (`backgroundCompactionThreshold: 0.80`). Our blueprint specifies a separate 4-level hierarchical compression system (L0–L3) for SongState. How do these interact?

**Architecture Decision: Dual Compression — SDK for Conversation, MUSE for Musical State**

```
┌──────────────────────────────────────────────────────────────┐
│                    Context Window                             │
│                                                              │
│ ┌─────────┐ ┌─────────────────────────┐ ┌────────────────┐  │
│ │ System   │ │ SDK-Managed             │ │ MUSE-Managed   │  │
│ │ Message  │ │ Conversation History    │ │ SongState      │  │
│ │ (~700t)  │ │ (auto-compacted by SDK) │ │ (L0/L1/L2     │  │
│ │          │ │                         │ │  injected per  │  │
│ │ FIXED    │ │ SDK compacts older      │ │  tool call)    │  │
│ │          │ │ turns → summaries       │ │                │  │
│ │          │ │ preserves recent turns  │ │ MUSE compacts  │  │
│ │          │ │                         │ │ based on need  │  │
│ └─────────┘ └─────────────────────────┘ └────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

**Interaction Model**:

1. **SDK compaction** handles conversation flow: it summarizes older user/assistant turns, preserving recent ones. We have limited control over WHAT it compacts.

2. **MUSE's L0–L3 system** handles musical state: we inject the appropriate compression level into tool context, NOT the conversation history.

3. **The key insight**: SongState should NEVER rely on conversation history for persistence. It must be maintained as an external data structure, re-injected fresh at each tool call.

**Implementation**:

```typescript
// In onPostToolUse hook: re-inject SongState at appropriate level
hooks.onPostToolUse = async (toolName, result, context) => {
  // Update SongState from tool result
  songStateManager.applyToolResult(toolName, result);
  
  // Determine compression level needed
  const level = determineCompressionLevel(context);
  // L0 for simple queries, L1 for most work, L2 for note-level editing
  
  // Return as additional context for next turn
  return {
    additionalContext: songStateManager.compress(level),
  };
};

function determineCompressionLevel(context: ToolContext): 0 | 1 | 2 | 3 {
  const lastToolCategory = categorize(context.toolName);
  
  if (lastToolCategory === "read" || lastToolCategory === "analyze") return 0;
  if (lastToolCategory === "generate") return 1;
  if (lastToolCategory === "edit_note" || lastToolCategory === "voice_lead") return 2;
  return 1; // default
}
```

**Critical Risk**: SDK compaction may discard conversation context that contains musical decisions (e.g., "the user said they want the 3rd chord darker"). Mitigation:

1. Every musical decision is immediately written to SongState.history (not just conversation).
2. SongState.history is injected alongside the L1 summary, so even if conversation is compacted, the decision chain is preserved.
3. Use `backgroundCompactionThreshold: 0.85` (conservative — let the window fill more before compacting, because our SongState injection handles the critical context).

**Compaction Compatibility Matrix**:

| Scenario | SDK Compaction Impact | MUSE L0-L3 Response |
|---|---|---|
| Turn 15 of composition, user iterating on chords | SDK summarizes turns 1-10 | L1 SongState preserves full chord progression + history of chord changes |
| Turn 40, complex pipeline + iteration | SDK aggressively summarizes turns 1-30 | L1 SongState still has full current state; L3 history has all decisions |
| Turn 80+, very long session | SDK may lose early creative intent | SongState.metadata.influences[] preserves original intent from turn 1 |
| Live performance (Phase 10), 200+ turns | SDK compaction every ~20 turns | LiveAnalysis is real-time (doesn't rely on conversation); recordings are on disk |

---

### Question D — `onPostToolUse` Hooks as Quality Gates (Multi-Critic)

**The Problem**: Can we use `onPostToolUse` to intercept tool outputs and run them through the multi-critic system before the LLM sees them?

**Architecture Decision: Post-Processing in Hooks, Not Blocking**

The SDK's `onPostToolUse` hook fires AFTER the tool handler returns but BEFORE the result is sent to the LLM. This is the right interception point for quality scoring, but NOT for blocking/re-generation.

**Why Not Blocking**:

```typescript
// ❌ WRONG: Trying to block and re-generate in hook
hooks.onPostToolUse = async (toolName, result) => {
  if (isGenerativeTool(toolName)) {
    const score = critic.evaluate(result);
    if (score < 0.7) {
      // Problem: we can't re-invoke the tool from a hook.
      // The hook can only modify the result or add context.
      return { modifiedResult: result, additionalContext: "Score was low" };
      // The LLM sees the low score and must decide to re-call.
    }
  }
};
```

The hook CAN:
- Annotate the result with critic scores
- Add advisory context ("This scored 0.58 on harmony — consider regenerating")
- Log quality metrics
- Update SongState

The hook CANNOT:
- Re-invoke the tool (tool calls are LLM-driven, not hook-driven)
- Block the result from reaching the LLM
- Redirect to a different tool

**Correct Architecture: Critic-in-the-Loop via Tool Wrapping**

```typescript
// ✅ CORRECT: Wrap the generator tool to include critic evaluation
const generateProgressionWithCritic = defineTool("generate_progression", {
  description: "Generate a chord progression with automatic quality evaluation",
  parameters: progressionRequestSchema,
  handler: async (params, context) => {
    let bestResult = null;
    let bestScore = 0;
    
    for (let attempt = 0; attempt < 3; attempt++) {
      const result = await progressionEngine.generate(params);
      const score = critic.evaluate(result, params);
      
      if (score.pass) return { progression: result, quality: score };
      
      if (score.overall > bestScore) {
        bestResult = result;
        bestScore = score.overall;
      }
      
      // Adjust parameters for next attempt
      params = adjustForCritic(params, score);
    }
    
    // Return best attempt with warning
    return {
      progression: bestResult,
      quality: { ...score, warning: "Below target quality after 3 attempts" },
    };
  },
});
```

**And use `onPostToolUse` for passive quality tracking**:

```typescript
hooks.onPostToolUse = async (toolName, result) => {
  if (result.quality) {
    // Track quality metrics for Phase 9 (personalization)
    qualityTracker.record(toolName, result.quality);
    
    // Inject quality context for LLM awareness
    return {
      additionalContext: result.quality.pass
        ? `Quality check passed (${result.quality.overall.toFixed(2)})`
        : `⚠ Quality below target (${result.quality.overall.toFixed(2)}). Issues: ${result.quality.flags.map(f => f.description).join(", ")}`,
    };
  }
};
```

**Summary**: The multi-critic lives INSIDE the tool handler (retry loop), not in the hook. The hook provides passive quality annotation and preference signal capture.

---

### Question E — MCP Servers vs. Inline Tools for Musical Knowledge

**The Problem**: When would `mcpServers` be better than inline tools defined via `defineTool()` for serving musical knowledge?

**Architecture Decision: MCP for Infrastructure, Tools for Domain Logic**

| Use Case | MCP Server | Inline Tool | Reasoning |
|---|---|---|---|
| Filesystem watching (new .progression files) | ✅ | ❌ | MCP's filesystem server handles watch natively |
| MIDI port management | ✅ (Phase 5+) | ✅ | MCP server could provide editor-agnostic MIDI; but inline is simpler for single-platform |
| Progression parsing + enrichment | ❌ | ✅ | Domain-specific computation; no benefit from MCP indirection |
| Embedding search | ❌ | ✅ | Latency-sensitive; MCP adds JSON-RPC overhead (~5-10ms per call) |
| Preset catalog browsing | Either | Either | MCP if we want to share catalog across multiple AI tools; inline if MUSE-only |
| SongState management | ❌ | ✅ | Core state; must be in-process for consistency |
| External sample library indexing | ✅ | ❌ | If user has 10K+ samples outside MPC Beats, MCP server can index asynchronously |
| DAW transport control | ✅ (Phase 10) | ❌ | MCP server can run as persistent daemon, surviving SDK session restarts |

**Concrete MCP Server Candidates**:

```typescript
const mcpConfig: Record<string, MCPServerConfig> = {
  // 1. Filesystem watcher — detects new/modified assets in MPC Beats directory
  "mpc-filesystem": {
    command: "node",
    args: ["./mcp-servers/filesystem-watcher.js"],
    env: { MPC_PATH: mpcBeatsPath },
    // Provides: watch_directory, list_files, file_changed events
  },
  
  // 2. MIDI daemon (Phase 10) — persistent MIDI port management
  "mpc-midi": {
    command: "node",
    args: ["./mcp-servers/midi-daemon.js"],
    env: { MIDI_PORT: "MPC AI Controller" },
    // Provides: send_note, send_cc, start_listening, get_status
    // ADVANTAGE: survives SDK session restarts; MIDI port stays open
  },
};
```

**Why NOT MCP for core features**:

1. **Latency**: MCP adds JSON-RPC serialization overhead. For a `search_assets` call that should take <5ms, adding ~10ms of serialization doubles the latency.
2. **State coupling**: SongState must be updated atomically with tool results. Cross-process state synchronization is fragile.
3. **Deployment simplicity**: Each MCP server is a separate process to manage. For a v1 product, fewer processes = more reliable.
4. **Debugging**: Inline tools are easier to test and debug (same process, same debugger).

**When MCP becomes necessary (post-v1)**:

- Multi-editor support (MUSE running in VS Code + JetBrains + CLI simultaneously — MCP servers provide shared state)
- External plugin integration (third-party developers adding custom knowledge servers)
- Persistent daemons (MIDI port, filesystem watcher must survive session restarts)
- Scalability (heavy computation offloaded to dedicated MCP server process)

---

### Question F — Real-Time MIDI Scheduling Inside Async Tool Handlers

**The Problem**: SDK tool handlers are `async` functions that return promises. Real-time MIDI scheduling demands 2-5ms timing precision. These are fundamentally incompatible.

**Architecture Decision: Decouple Scheduling from Tool Handlers**

```
┌────────────────────────────────────────────────────────────────┐
│ Main Thread (Node.js event loop)                                │
│                                                                │
│ ┌────────────┐    ┌─────────────────┐    ┌───────────────────┐ │
│ │ Tool       │    │ Scheduling      │    │ State             │ │
│ │ Handlers   │───→│ Queue           │    │ Management        │ │
│ │ (async)    │    │ (in-process     │    │ (SongState,       │ │
│ │            │    │  sorted buffer) │    │  preferences)     │ │
│ └────────────┘    └────────┬────────┘    └───────────────────┘ │
│                            │                                    │
│                            ▼                                    │
│              ┌─────────────────────────┐                       │
│              │ Worker Thread           │                       │
│              │ (high-res timer loop)   │                       │
│              │                         │                       │
│              │ while(running) {        │                       │
│              │   now = hrtime()        │                       │
│              │   while(queue.peek()    │                       │
│              │         <= now) {       │                       │
│              │     dispatch(queue.pop) │                       │
│              │   }                     │                       │
│              │   // ~0.5ms resolution  │                       │
│              │ }                       │                       │
│              └──────────┬──────────────┘                       │
│                         │                                      │
│                         ▼                                      │
│              ┌─────────────────────────┐                       │
│              │ Native MIDI Output      │                       │
│              │ (RtMidi via easymidi)   │                       │
│              └─────────────────────────┘                       │
└────────────────────────────────────────────────────────────────┘
```

**Implementation Strategy**:

1. **Tool handler** (async, main thread): Computes WHAT to play (notes, timing, durations). Returns immediately with a schedule ID.

2. **Scheduling queue** (shared between main thread and worker): A sorted array of `ScheduledMidiEvent` objects with absolute timestamps (based on `process.hrtime.bigint()`).

3. **Worker thread** (dedicated, high-priority): A tight polling loop that dispatches events at their scheduled timestamps. Uses `Atomics.wait()` with timeout or `setImmediate()` for sub-millisecond resolution.

4. **Communication**: `SharedArrayBuffer` or `MessageChannel` between main thread and worker. For the queue, a lock-free ring buffer pattern works well given single-producer (main thread), single-consumer (worker thread).

**Latency Budget**:

| Component | Latency | Mitigation |
|---|---|---|
| Tool handler computation | 10-50ms | Pre-compute; return schedule, not real-time stream |
| Queue insertion | <0.1ms | In-memory sorted insert |
| Worker loop resolution | 0.5-2ms | `setImmediate` or busy-wait with `hrtime` |
| RtMidi dispatch | 0.1-0.5ms | Native binding, minimal overhead |
| Virtual MIDI cable | 0.5-1ms | loopMIDI kernel-level routing |
| MPC Beats input processing | 1-3ms | DAW internal buffering |
| **Total** | **12-57ms** | Acceptable for non-live use (file play-in) |
| **Live mode total** (skip tool handler) | **2-7ms** | Acceptable for live harmonization |

**Critical Distinction: Play-In vs. Live**:

- **Play-in** (Phase 5): Not truly real-time. Pre-compute entire sequence, schedule all events, then let the worker play them out. Tool handler computes for 50ms, then playback is sample-accurate. This is easy.

- **Live harmonization** (Phase 10): Truly real-time. Input note arrives → must output harmony note within 5ms. The tool handler is NOT involved per-note. Instead:
  - MIDI input arrives at worker thread directly (via `easymidi` callback)
  - Worker thread runs the harmonization lookup (pre-computed scale table — O(1))
  - Worker thread dispatches harmony note immediately
  - Worker thread asynchronously notifies main thread for state updates

```typescript
// Phase 10 live path — runs IN the worker thread, not as a tool
class LiveHarmonizer {
  private scaleTable: Map<number, number>; // input note → harmony note
  
  // Pre-computed when key is detected (main thread sends via MessageChannel)
  setKey(root: number, mode: string) {
    this.scaleTable = buildDiatonicThirdsTable(root, mode);
  }
  
  // Called directly from MIDI input callback — NO async, NO tool handler
  onNoteOn(note: number, velocity: number, channel: number) {
    const harmonyNote = this.scaleTable.get(note % 12);
    if (harmonyNote !== undefined) {
      this.output.sendNoteOn(channel + 1, harmonyNote + Math.floor(note / 12) * 12, velocity);
    }
  }
}
```

**Summary**: Tool handlers schedule; they don't dispatch. A dedicated worker thread handles real-time dispatch. For live mode, the critical path bypasses tool handlers entirely.

---

## Part II: Per-Phase SDK Mapping & Integration Tests

### Phase 0 — Foundation

**SDK Primitive Mapping**:

| SDK Primitive | Binding |
|---|---|
| `CopilotClient` | Entry point — spawned in `src/index.ts` |
| `CopilotSession.create()` | One session per MUSE interaction |
| `defineTool()` × 5 | `read_progression`, `read_arp_pattern`, `read_controller_map`, `list_presets`, `list_assets` |
| `systemMessage` (append) | MUSE persona + workspace manifest L0 |
| `onSessionStart` | Workspace scan, SongState load |
| `onSessionEnd` | SongState persist |
| `onPostToolUse` | SongState delta tracking |
| `onErrorOccurred` | Friendly error messages |
| `infiniteSessions` | Enabled, threshold 0.85 |
| `skillDirectories` | `["./skills"]` — empty skills initially, structure established |

**Trade-off: `systemMessage` mode "append" vs "replace"**:
- `append`: Preserves SDK's built-in system prompt (Copilot identity, tool-use instructions). Our MUSE persona is ADDED. Safest — SDK prompt includes critical instructions about tool calling format.
- `replace`: Full control over system prompt but we must replicate SDK's tool-use instructions. Risk of breaking tool invocation patterns.
- **Decision**: Use `append`. The SDK's default prompt is beneficial for tool-use scaffolding. Our MUSE content adds domain expertise on top.

**Integration Test Plan**:

| Test ID | Description | Verification |
|---|---|---|
| INT-0.1 | Session lifecycle | Create session → send message → receive response → end session → verify SongState persisted to disk |
| INT-0.2 | Tool invocation roundtrip | Send "List all progressions" → verify `list_assets` tool called → verify response includes 47 progression names |
| INT-0.3 | Asset parsing accuracy | Call `read_progression` for Godly → verify 16 chords, root "E", scale "Pentatonic Minor" |
| INT-0.4 | Error handling | Call `read_progression` with nonexistent path → verify friendly error, session continues |
| INT-0.5 | Workspace scanning | Start session with MPC Beats at standard path → verify manifest has 47+80+67 assets |
| INT-0.6 | SongState persistence roundtrip | Create SongState → modify via tool → end session → restart → verify state recovered |
| INT-0.7 | Infinite session compaction survival | Send 30 messages → verify SongState L0 is still present in context after compaction |

**SDK Gotchas — Phase 0**:

1. **`CopilotClient` spawn timing**: The CLI server may take 2-5 seconds to start. The first `session.create()` call will block until the server is ready. Implement a startup progress indicator.

2. **Tool parameter serialization**: The SDK serializes Zod schemas to JSON Schema for the LLM. Complex Zod types (`z.discriminatedUnion`, `z.lazy`) may not serialize correctly. Stick to `z.object`, `z.string`, `z.number`, `z.enum`, `z.array`, `z.optional`.

3. **`onPostToolUse` return value**: The hook's return type should include `{ additionalContext?: string }` to inject context for the next LLM turn. If the documented API doesn't support this, the fallback is updating the system message dynamically (which may or may not be supported mid-session).

4. **Windows path handling in tool parameters**: The LLM may generate forward-slash paths in tool calls. Always normalize paths in tool handlers with `path.resolve()` before file access.

5. **`infiniteSessions` compaction visibility**: We cannot observe WHEN compaction occurs or WHAT was compacted. We must assume older conversation turns may be summarized at any time. Never rely on exact wording from early turns — only on SongState.

---

### Phase 1 — Harmonic Brain

**SDK Primitive Mapping**:

| SDK Primitive | Binding |
|---|---|
| `defineTool()` × 6 | `analyze_harmony`, `generate_progression`, `transpose_progression`, `suggest_substitution`, `explain_theory`, `get_genre_dna` |
| `customAgents[0]` | Harmony agent (name: "harmony", infer: true) |
| `skillDirectories` | `skills/harmony/` with SKILL.md, theory-reference.md, genre-dna.json, voicing-rules.md |

**Trade-off: Harmony — Agent vs. Skill**:
- **As `customAgent`**: Gets its own prompt with theory grounding. LLM reasons within harmonic context. Auto-routed for theory questions.
- **As `skill` only (no dedicated agent)**: Knowledge loaded into whichever agent handles the query. Simpler architecture but less focused reasoning.
- **Decision**: `customAgent`. Harmonic analysis is deep enough to warrant a specialized prompt. The agent's `infer` routing catches "What key is this?", "Explain this chord", "Why does this progression work?" naturally.

**Integration Test Plan**:

| Test ID | Description | Verification |
|---|---|---|
| INT-1.1 | Harmony agent routing | "What key is the Godly progression in?" → routes to harmony agent (not composer) |
| INT-1.2 | Full enrichment pipeline | `read_progression("Godly")` → enriched result has Roman numerals, tension values, genre associations |
| INT-1.3 | Progression generation | "Generate a neo-soul progression in Eb minor" → valid .progression JSON with ≥4 chords, all in Eb minor scale |
| INT-1.4 | Transposition accuracy | Transpose Godly to A minor → all notes shifted +5, chord names correct |
| INT-1.5 | Genre DNA query | "What does neo-soul harmony look like?" → references genre DNA vector values |
| INT-1.6 | Cross-tool: Harmony → Sound | "Generate a progression and suggest presets for it" → harmony tool + sound tool called in sequence |

**SDK Gotchas — Phase 1**:

1. **Agent prompt vs. skill content overlap**: If `theory-reference.md` is loaded as a skill AND referenced in the agent prompt, the LLM sees it twice — wasted tokens. Solution: agent prompt REFERENCES skills ("See theory-reference.md for...") but doesn't duplicate content.

2. **Tool return format**: The `generate_progression` tool should return BOTH the raw `.progression` JSON (for file writing) AND a human-readable summary (for the LLM to present). If the tool returns a large JSON blob, the LLM may struggle to summarize it. Structure the return as `{ summary: string, data: object, filePath?: string }`.

---

### Phase 2 — Embeddings & Search

**SDK Primitive Mapping**:

| SDK Primitive | Binding |
|---|---|
| `defineTool()` × 1 | `search_assets` |
| `onSessionStart` | Load embedding index into memory |
| MCP (optional) | Filesystem watcher for new assets → trigger re-indexing |

**Trade-off: Embedding index as tool vs. implicit context injection**:
- **As tool**: LLM explicitly calls `search_assets` when it needs to find assets. Transparent, controllable.
- **As implicit injection**: Every query automatically gets top-3 relevant assets injected via `onPreToolUse`. Seamless but noisy — may inject irrelevant results.
- **Decision**: Explicit tool. The LLM should decide when to search. The system message should instruct: "When the user asks for sounds, presets, or progressions matching a description, use the search_assets tool."

**Integration Test Plan**:

| Test ID | Description | Verification |
|---|---|---|
| INT-2.1 | Semantic search accuracy | "warm Sunday morning" → Slow Praise and RhodesBallad in top 5 |
| INT-2.2 | Type-filtered search | `search_assets("aggressive bass", type="preset")` → only preset results |
| INT-2.3 | Cross-modal search | "gospel" → progressions AND presets (DB-33, Mini Grand) returned |
| INT-2.4 | Index completeness | Verify index has ≥ 47 + 80 + 297 + 60 = 484 entries |
| INT-2.5 | Cold start: index building | Delete index → start session → verify index rebuilt automatically |
| INT-2.6 | Phase 1 → 2 integration | Enriched progression description used in embedding (not raw JSON) |

**SDK Gotchas — Phase 2**:

1. **ONNX Runtime + Node.js version**: `onnxruntime-node` has specific Node.js version requirements. Pin the Node.js version in `package.json` engines field. Test with both Node 18 LTS and Node 20 LTS.

2. **Model file size in distribution**: The ONNX model is ~80MB. Options: (a) bundle in npm package (large install), (b) download on first use (requires internet), (c) lazy-load from CDN with hash verification. Recommend (b) with offline fallback to keyword search.

3. **Memory residency**: Embedding model stays in memory (~80MB) after first load. For long sessions, this is fine. For CLI one-shot usage, consider lazy unloading after 5 minutes of no search calls.

---

### Phase 3 — Rhythm Engine

**SDK Primitive Mapping**:

| SDK Primitive | Binding |
|---|---|
| `defineTool()` × 7 | `generate_drum_pattern`, `generate_bassline`, `generate_melody`, `humanize_midi`, `transform_arp`, `generate_chord_voicing_midi`, `set_groove` |
| `customAgents[1]` | Rhythm agent |
| `skillDirectories` | `skills/rhythm/` |
| Streaming | Progress for multi-bar generation |

**Integration Test Plan**:

| Test ID | Description | Verification |
|---|---|---|
| INT-3.1 | Phase 1 → 3: Harmonic-rhythmic integration | Generate bassline over Godly progression → every bass note is a chord tone or approach tone |
| INT-3.2 | MIDI file roundtrip | Generate drum pattern → write .mid → read back → identical note events |
| INT-3.3 | Humanization idempotency | Humanize a pattern → humanize again → result is different (stochastic) but within bounds |
| INT-3.4 | Arp transformation: fit to chords | Transform arp 025 to fit Trap 1 chords → all notes are target chord tones |
| INT-3.5 | Arrangement assembly | 4 individual tracks → assembled multi-track .mid → correct track count, total duration |
| INT-3.6 | Energy mapping | Energy arc [0.2, 0.8] → drum density increases, hi-hat subdivision increases |

**SDK Gotchas — Phase 3**:

1. **Large tool outputs**: A 16-bar drum pattern at 16th-note resolution = ~256 note events. If the tool returns all events as JSON, it consumes significant context tokens. Return a SUMMARY ("16-bar pattern: kick on 1&3, snare on 2&4, 16th hi-hats, 2 fills") + file path, NOT the raw event array.

2. **Streaming for generation progress**: The SDK supports `assistant.message_delta` for streaming. But tool handlers return complete results, not streams. Progress updates must be implemented differently — perhaps by sending status messages via a separate mechanism or by breaking generation into sub-tools called sequentially ("generate bars 1-4" → "generate bars 5-8" → ...).

---

### Phase 4 — Sound Oracle

**Integration Test Plan**:

| Test ID | Description | Verification |
|---|---|---|
| INT-4.1 | Phase 2 → 4: Semantic preset search | Sound agent searches for "warm pad" → uses Phase 2 embedding index |
| INT-4.2 | Phase 1 → 4: Genre-aware recommendation | Preset for "gospel chords" → DB-33 or Mini Grand (genre DNA guides) |
| INT-4.3 | Effect chain signal flow | Generated chain NEVER has delay before compressor (physics order enforced) |
| INT-4.4 | Frequency analysis with Phase 3 MIDI | Analyze SongState with generated tracks → detect real masking issues |
| INT-4.5 | BPM-synced parameters | At 130 BPM → delay time = 461.5ms (quarter note), 346.2ms (dotted 8th) |
| INT-4.6 | X-Ray explanation | Recommend preset → ask "why?" → explanation references genre, spectral region, corpus |

**SDK Gotchas — Phase 4**:

1. **Sound vs. Mix agent overlap**: Both agents deal with effect chains. When the LLM encounters "add reverb to the pad", `infer: true` may oscillate between agents. Solution: Sound agent description emphasizes "creative sound design and timbral choices"; Mix agent emphasizes "technical mixing, frequency balance, and loudness." Test routing with 20 common queries and adjust descriptions until routing accuracy > 90%.

---

### Phase 5 — Virtual MIDI

**SDK Primitive Mapping**:

| SDK Primitive | Binding |
|---|---|
| `defineTool()` × 6 | `create_virtual_port`, `send_midi_note`, `send_midi_cc`, `midi_transport`, `play_sequence`, `play_progression` |
| Permission handler | User approval for first MIDI send in session |
| `ask_user` | "Ready to play in? Arm recording in MPC Beats and press Enter" |
| MCP (recommended) | MIDI daemon that persists across sessions |

**Integration Test Plan**:

| Test ID | Description | Verification |
|---|---|---|
| INT-5.1 | Phase 0 → 5: .xmm generation | Generated .xmm for "MPC AI Controller" parses correctly with Phase 0 parser |
| INT-5.2 | Phase 1 → 5: Play progression via MIDI | `play_progression("Godly", 100)` → MIDI events match Godly chord notes with correct timing |
| INT-5.3 | Phase 3 → 5: Play generated MIDI | Generate drum pattern → play via virtual port → events dispatched within 5ms of schedule |
| INT-5.4 | Transport sync | Start clock at 120 BPM → verify 48 clock messages/second ±2 |
| INT-5.5 | Play-in workflow | Schedule 4-bar sequence → Start → Clock → Notes → Stop → verify correct message order |
| INT-5.6 | Port health monitor | Disconnect port → verify warning → reconnect → verify recovery |

**SDK Gotchas — Phase 5**:

1. **Native dependency compilation**: `easymidi` (RtMidi binding) requires C++ compilation via node-gyp. This is a significant deployment hazard on Windows (requires Visual Studio Build Tools). Consider: (a) pre-built binaries via `prebuildify`, (b) `@julusian/midi` which ships pre-built binaries, (c) fallback to `navigator.requestMIDIAccess` if running in Electron.

2. **Permission handler UX**: The SDK's permission handler fires before tool execution. For MIDI, the prompt should be informative: "MUSE wants to send MIDI data to 'MPC AI Controller' virtual port. This will send musical notes to MPC Beats. Allow?" Not just "Allow tool execution?"

3. **Tool handler timeout**: The `play_sequence` tool may run for 30+ seconds (playing a 16-bar sequence at 90 BPM). The SDK may have implicit timeouts for tool handlers. Implementation: the tool handler should schedule the playback and return immediately with a status, not block until playback completes.

---

### Phase 6 — Full Pipeline

**SDK Primitive Mapping**:

| SDK Primitive | Binding |
|---|---|
| `customAgents` | Composer agent — `tools: ["*"]`, catches complex requests |
| `onUserPromptSubmitted` | Intent classification: simple query vs. pipeline trigger |
| `ask_user` | Genre disambiguation, A/B choices, stage approval |
| `infiniteSessions` | Critical: pipeline + iteration = 50+ turns |
| Streaming | Progress per pipeline stage |

**Trade-off: Explicit Pipeline vs. LLM-Driven Orchestration**:

| Approach | Pros | Cons |
|---|---|---|
| **Explicit pipeline** (hard-coded stage sequence) | Predictable, debuggable, consistent output structure | Inflexible — can't skip irrelevant stages, hard to iterate |
| **LLM-driven orchestration** (Composer agent decides tool sequence) | Flexible, adapts to user intent, handles partial requests | Non-deterministic, may skip steps, harder to test |
| **Hybrid** (stages defined, LLM decides which to run) | Best of both; LLM interprets intent → maps to stages → executes | Moderate complexity |

**Decision**: Hybrid. The tool `decompose_intent` returns a `PipelineIntent` with `requestedOutputs[]`. The Composer agent then executes only the relevant stages. If the user says "just give me chords", stages 4-8 are skipped.

**Integration Test Plan**:

| Test ID | Description | Verification |
|---|---|---|
| INT-6.1 | End-to-end pipeline | "Neo soul, Eb minor, 90 BPM" → .progression + 4 .mid files + preset list + effect chains |
| INT-6.2 | All phases integrated | Pipeline uses Phase 1 (harmony) → Phase 3 (MIDI) → Phase 4 (presets) → Phase 5 (optional playback) |
| INT-6.3 | Iteration: single element change | Generate song → "make the bass simpler" → only bass .mid regenerated, drums unchanged |
| INT-6.4 | A/B generation | "Give me 3 bassline options" → 3 different .mid files returned |
| INT-6.5 | Sensitivity annotations | Change key → all tracks regenerated (verified by timestamp check) |
| INT-6.6 | Pipeline + Phase 2 search | "Something warm" → search_assets called during preset selection stage |
| INT-6.7 | Output file structure | Verify output directory has expected structure (manifest, midi/, progression/, notes/) |
| INT-6.8 | Intent disambiguation | "Something moody" → ask_user called for genre/tempo clarification |

**SDK Gotchas — Phase 6**:

1. **Multi-tool turns**: The Composer agent needs to call 4-6 tools in sequence per pipeline stage. The SDK processes tool calls sequentially within a single LLM turn. If the LLM tries to call 6 tools in one response, they execute one-by-one. This is fine for correctness but may take 10-20 seconds for a full pipeline. The LLM should be prompted to emit progress messages between tool calls.

2. **Context window exhaustion during pipeline**: A full pipeline generates significant tool-call + result data. By stage 7, the context may already be at compaction threshold. Mitigation: tool results should be COMPRESSED — return summaries, not full data. Store full data in SongState (external JSON), not conversation history.

3. **Agent routing vs. Composer**: When the user says "Create a beat", does it route to Rhythm agent (beat = drums) or Composer agent (beat = full song)? The Composer agent's description must include "create a beat", "make a track", "compose a song" to capture these.

---

### Phase 7 — Controller Intelligence

**Integration Test Plan**:

| Test ID | Description | Verification |
|---|---|---|
| INT-7.1 | Phase 0 → 7: Controller parsing → profiling | Parse MPK mini 3 .xmm → profile has 8 pads, 8 knobs, 25 keys |
| INT-7.2 | Phase 5 → 7: Generated .xmm → MIDI routing | Generate "MPC AI Controller" .xmm → virtual port sends CC → mapped to Target_control |
| INT-7.3 | Phase 4 → 7: Context-sensitive mapping | Mixing context + MPK mini 3 → knobs mapped to track volumes |
| INT-7.4 | Cross-controller translation | MPK mini 3 mapping → Launchkey 49 mapping → pad count adjusted |
| INT-7.5 | Dynamic remap suggestion | 3 mixing tools called → remap to mixing mode suggested |

---

### Phase 8 — Creative Frontier

**Trade-off: Critics in Tool Handlers vs. Separate Evaluation Tool**:

| Approach | Pros | Cons |
|---|---|---|
| **Critic inside generator tools** (Task 8.3 architecture) | Automatic, guaranteed quality check, retries transparent | Couples generation + evaluation, harder to test independently |
| **Separate `judge_output` tool** | Decoupled, testable, LLM can decide when to evaluate | LLM may skip evaluation, not automatic |
| **Both** | Critic inside for automatic floor, separate tool for explicit re-evaluation | Redundant evaluation possible |

**Decision**: Both. The automatic critic inside generators enforces the floor (no axis < 0.5). The separate `judge_output` tool allows the LLM (or user) to request explicit evaluation of any artifact. The separate tool is useful for Phase 9 (personalization signals) and user-facing quality reports.

**Integration Test Plan**:

| Test ID | Description | Verification |
|---|---|---|
| INT-8.1 | Phase 1 → 8: Harmonic creativity dial | Creativity=0.1 → only diatonic chords. Creativity=0.9 → tritone subs, chromatic mediants appear |
| INT-8.2 | Phase 3 → 8: Rhythmic creativity dial | Creativity=0.1 → straight 4/4. Creativity=0.9 → odd groupings, polyrhythm |
| INT-8.3 | Phase 6 → 8: Pipeline quality gate | Generate with forced low quality → verify regeneration attempted up to 3 times |
| INT-8.4 | Happy accident traceability | Accident occurs → tagged in output → user can undo specifically |
| INT-8.5 | Genre bending | Blend jazz + trap → output has jazz harmony + trap rhythm |
| INT-8.6 | Explanation accuracy | Tritone sub explanation → mentions shared tritone interval (factual check) |

---

### Phase 9 — Personalization

**Integration Test Plan**:

| Test ID | Description | Verification |
|---|---|---|
| INT-9.1 | Phase 6 → 9: Preference signal capture | Accept 5 jazz progressions in pipeline → verify harmonicComplexity trending up |
| INT-9.2 | Phase 8 → 9: Creativity calibration | User keeps high-creativity outputs → verify experimentalTendency increases |
| INT-9.3 | Session persistence roundtrip | End session → start new session → verify preferences loaded unchanged |
| INT-9.4 | Exploration diversity | 100 generations → verify ~20% are exploration (deviated from preferences) |
| INT-9.5 | Producer mode switching | Switch to "Jazz Cat" → generate → verify jazz-style defaults applied |
| INT-9.6 | Preference-driven defaults chain | No explicit genre → top affinity genre used → correct preset defaults |
| INT-9.7 | Speculative generation hit rate | After progression → drums pre-generated → user asks for drums → served from cache |

---

### Phase 10 — Live Performance

**Integration Test Plan**:

| Test ID | Description | Verification |
|---|---|---|
| INT-10.1 | Phase 5 → 10: MIDI I/O bidirectional | Input notes received → harmony notes output → latency < 10ms |
| INT-10.2 | Phase 1 → 10: Real-time key detection | Play C major scale → key detected as C major within 8 notes |
| INT-10.3 | Phase 3 → 10: Auto-complement generation | Auto-bass follows detected chords → bass notes are chord tones |
| INT-10.4 | Phase 7 → 10: Live controller mapping | Performance mode controller map → pads toggle auto-parts |
| INT-10.5 | Phase 9 → 10: Style adaptation | User's preference model affects harmonization choices (prefer 6ths over 3rds if experimentalism high) |
| INT-10.6 | Session recording accuracy | Record 16-bar session → playback reproduces → conversion to SongState preserves key/tempo |
| INT-10.7 | Energy response | Play crescendo → auto-drums add complexity within 4 beats |

---

## Part III: Shared Contracts Addendum

The existing contracts (C1–C9 in the overview file) are comprehensive. Here are additional contracts needed for cross-phase integration that emerged from this deep analysis:

### Contract C10: ToolResult (universal tool return shape)

```typescript
/** Every tool should return this shape for consistent LLM interaction */
interface MuseToolResult<T = unknown> {
  /** Human-readable summary for the LLM to present */
  summary: string;
  
  /** Structured data (for SongState updates, downstream tool consumption) */
  data: T;
  
  /** Quality score if applicable (from Phase 8 critic) */
  quality?: CriticReport;
  
  /** File paths of generated artifacts */
  artifacts?: { path: string; type: string; description: string }[];
  
  /** Suggestions for next steps (guides the LLM's follow-up) */
  nextSteps?: string[];
  
  /** Metadata for preference tracking (Phase 9) */
  meta?: {
    toolName: string;
    generationParams: Record<string, unknown>;
    timestamp: number;
  };
}
```

### Contract C11: LiveAnalysis (Phase 10, but structure needed by Phase 5)

```typescript
/** Real-time analysis state — continuously updated during live performance */
interface LiveAnalysis {
  detectedKey: { root: string; mode: string; confidence: number } | null;
  detectedTempo: { bpm: number; confidence: number } | null;
  currentEnergy: { level: number; trend: "rising" | "falling" | "stable" };
  noteBuffer: RingBuffer<TimestampedMidiNote>;
  chordBuffer: RingBuffer<DetectedChord>;
  phrasePosition: { bar: number; beat: number; subdivision: number };
  inputChannel: number;
  activeComplementParts: Set<"bass" | "drums" | "harmony" | "counter">;
}

interface TimestampedMidiNote {
  note: number;
  velocity: number;
  channel: number;
  timestampMs: number;
  durationMs?: number;
}
```

### Contract C12: PipelineStage (Phase 6 internal, but referenced by Phase 8 critics)

```typescript
interface PipelineStage {
  id: string;                    // "harmony", "rhythm.drums", "rhythm.bass", "sound", "mix", "assembly"
  status: "pending" | "running" | "completed" | "failed" | "skipped";
  startTime?: number;
  endTime?: number;
  toolsCalled: string[];
  result?: MuseToolResult;
  criticReport?: CriticReport;
  attempts: number;
}

interface PipelineExecution {
  intent: PipelineIntent;
  stages: PipelineStage[];
  currentStage: number;
  songStateBefore: string;      // JSON hash for delta tracking
  songStateAfter?: string;
}
```

---

## Part IV: Master SDK Gotchas Reference

### Category 1: Session & Context Management

| ID | Gotcha | Impact | Mitigation |
|---|---|---|---|
| G-1.1 | `infiniteSessions` compaction is opaque — we cannot control what gets summarized | Musical decisions in early turns may be lost | Store ALL decisions in SongState.history immediately; never rely on conversation memory for state |
| G-1.2 | `systemMessage` modification mid-session may not be supported | Cannot dynamically inject SongState L0 into system prompt between turns | Use `onPostToolUse` return value for `additionalContext`; if not supported, prepend SongState to next tool result |
| G-1.3 | Session resume may not reload `customAgents` or `tools` | Resumed session might have stale tool definitions | Re-register all tools on session resume; verify via a health-check tool call |
| G-1.4 | Context window size unknown for BYOK providers | Different models have different context limits; compaction threshold may be wrong | Auto-detect model context size where possible; default to conservative 8K assumption for compaction math |

### Category 2: Tool Execution

| ID | Gotcha | Impact | Mitigation |
|---|---|---|---|
| G-2.1 | Tool handler timeouts | Long-running tools (play_sequence, generate_arrangement) may be killed by the SDK | Return immediately with a "scheduled" status; use background processing for long tasks |
| G-2.2 | Tool result size limits | Large MIDI event arrays in tool results consume excessive context tokens | Always return summaries, not raw data; persist full data to files referenced by path |
| G-2.3 | Zod schema serialization limits | Complex union types, recursive schemas may not serialize to JSON Schema correctly | Test every Zod schema's `.jsonSchema()` output; stick to simple types |
| G-2.4 | Tool call error propagation | Unhandled exceptions in tool handlers may crash the SDK session | Wrap every handler in try/catch; return structured error objects, never throw |
| G-2.5 | Parallel tool calling not guaranteed | The LLM may call tools one-by-one even when parallel is possible | Design for sequential execution; parallel is a nice-to-have optimization |

### Category 3: Agent Routing

| ID | Gotcha | Impact | Mitigation |
|---|---|---|---|
| G-3.1 | `infer: true` routing is probabilistic, not deterministic | Same query may route to different agents on different runs | Test routing with 50 common queries; tune agent descriptions until accuracy > 85% |
| G-3.2 | Agent prompt accumulation | If SDK loads all agent prompts simultaneously (not one-at-a-time), 4000 tokens of agent prompts consume significant context | Verify SDK behavior: does it load only the active agent's prompt? If not, truncate prompts aggressively |
| G-3.3 | No inter-agent communication primitive | The Composer can't "call" the Harmony agent; it can only call harmony TOOLS | Design tools as the communication layer; agent specialization is in prompts, not in code |
| G-3.4 | Agent switching mid-conversation | If user asks a harmony question then a rhythm question, does the SDK switch agents mid-session? | Test agent switching behavior; if problematic, consider the Composer as the sole agent with domain tools |

### Category 4: Platform & Deployment

| ID | Gotcha | Impact | Mitigation |
|---|---|---|---|
| G-4.1 | `@github/copilot-sdk` version stability | SDK is new; breaking changes between minor versions | Pin exact version in package.json; test on each upgrade |
| G-4.2 | Node.js native addons on Windows | `onnxruntime-node` and `easymidi` require compilation or pre-built binaries | Ship pre-built binaries for Windows x64; test on clean Windows install |
| G-4.3 | BYOK provider compatibility | Different providers (OpenAI, Anthropic, Ollama) may handle tool calls differently | Test core flows with at least 3 providers; maintain compatibility matrix |
| G-4.4 | File system permissions | Writing to MPC Beats install directory (for .xmm) may require elevation | Write to user-accessible directory first; provide copy instruction for protected directories |
| G-4.5 | SDK CLI server process management | The spawned CLI process may orphan on crash | Implement graceful shutdown with SIGTERM handler; use PID file for orphan detection |

### Category 5: Musical Domain

| ID | Gotcha | Impact | Mitigation |
|---|---|---|---|
| G-5.1 | LLM music theory hallucination | LLM may generate incorrect theory explanations despite being grounded | All theory facts go through structured templates (Phase 8.7), not free-form LLM generation |
| G-5.2 | Chord symbol parsing ambiguity | "Badd9" — is root B-major-add9 or Bb-add9? | Default to rule: capital letter = root, "b" after capital = flat. Always verify against MIDI notes |
| G-5.3 | MIDI timing determinism | JavaScript event loop timing is non-deterministic | For play-in: pre-compute all events with absolute timestamps; dispatch in worker thread |
| G-5.4 | Cross-cultural music theory | Western-centric theory may not apply to all genre requests | Acknowledge in system prompt; provide escape hatch for user-defined scales |

---

## Part V: Implementation Priority Reordering

Based on the deep analysis, the original phase ordering (0-10 sequential) should be adjusted for maximum velocity with parallelization:

```
Sprint 1 (Weeks 1-4):
├── Phase 0: Foundation (FULL)
│   All 12 tasks — scaffold, parsers, SongState, tool infra, CLI
│
Sprint 2 (Weeks 5-8):  ← THREE PHASES IN PARALLEL
├── Phase 1: Harmonic Brain (Tasks 1.1-1.6, 1.9, 1.10)
│   Core analysis + generation (defer Task 1.5 XL to Sprint 3)
├── Phase 2: Embeddings (Tasks 2.1-2.5)
│   Description catalogs + ONNX setup (index building needs Phase 1 for 2.1)
├── Phase 3: Rhythm Engine (Tasks 3.1-3.5, 3.9)
│   MIDI writer + generators + humanization (defer arrangement assembly)
│
Sprint 3 (Weeks 9-12): ← TWO PHASES IN PARALLEL
├── Phase 1 completion: Task 1.5 (progression generation XL)
├── Phase 2 completion: Tasks 2.6-2.8 (index building + search)
├── Phase 3 completion: Tasks 3.6-3.8, 3.10-3.11
├── Phase 4: Sound Oracle (Tasks 4.1-4.9)
│   Preset recommendation + effect chains + mix analysis
├── Phase 5: Virtual MIDI (Tasks 5.1-5.6)
│   Port setup + output service + clock (defer play-in to Sprint 4)
│
Sprint 4 (Weeks 13-16):
├── Phase 5 completion: Tasks 5.7-5.10 (play-in, input listener)
├── Phase 6: Full Pipeline (ALL)
│   Integration of everything built so far
│   THIS IS THE MVP MILESTONE
│
Sprint 5 (Weeks 17-20): ← THREE PHASES IN PARALLEL
├── Phase 7: Controller Intelligence
├── Phase 8: Creative Frontier
├── Phase 9: Personalization
│
Sprint 6 (Weeks 21-26):
├── Phase 10: Live Performance
├── Polish + integration testing + documentation
```

**Critical Path**: 0 → 1 → 6 → 10 (harmonic analysis is prerequisite for everything downstream)

**MVP at Week 16**: System can take "Neo soul in Eb minor" → produce chord progression + MIDI tracks + preset recommendations + effect chains + optionally play via virtual MIDI. This is the killer demo.

---

## Part VI: Architecture Decision Records (ADRs)

### ADR-001: Single Session Architecture
- **Status**: Accepted
- **Context**: 6 specialized agents need to coordinate
- **Decision**: Single `CopilotSession` with 6 `customAgents`, not multiple sessions
- **Consequences**: Simpler state management, but relies on SDK routing accuracy

### ADR-002: SongState as External Ground Truth
- **Status**: Accepted
- **Context**: SDK conversation compaction may lose musical decisions
- **Decision**: SongState is persisted to JSON file, re-injected per tool call; NEVER rely on conversation memory for musical state
- **Consequences**: Slightly more token usage per turn (L0/L1 injection), but complete resilience to compaction

### ADR-003: Tool-Based Quality Gates
- **Status**: Accepted
- **Context**: `onPostToolUse` hooks cannot block/retry tool execution
- **Decision**: Multi-critic lives INSIDE tool handlers (retry loop); hooks provide passive annotation
- **Consequences**: More complex tool handlers, but guaranteed quality enforcement

### ADR-004: Worker Thread for MIDI Timing
- **Status**: Accepted
- **Context**: Node.js event loop cannot guarantee <5ms timing
- **Decision**: Dedicated `worker_threads` worker with high-resolution timer for MIDI dispatch
- **Consequences**: Added complexity (inter-thread communication), but necessary for musical timing

### ADR-005: MCP for Infrastructure Only (v1)
- **Status**: Accepted
- **Context**: MCP servers add deployment complexity
- **Decision**: v1 uses inline tools for all domain logic; MCP only for filesystem watching (optional) and MIDI daemon (Phase 10)
- **Consequences**: Simpler deployment, but limits multi-editor scenarios until v2

### ADR-006: Hybrid Pipeline Orchestration
- **Status**: Accepted
- **Context**: Fully explicit pipelines are inflexible; fully LLM-driven is non-deterministic
- **Decision**: `PipelineIntent` defines which stages to run; Composer agent executes stage tools in sequence
- **Consequences**: Predictable output structure with flexible intent interpretation

### ADR-007: Compressed Tool Results
- **Status**: Accepted
- **Context**: Large tool outputs (MIDI event arrays, full progression data) exhaust context
- **Decision**: All tools return `{ summary: string, data: <compressed>, artifacts: [{path}] }`; full data goes to files
- **Consequences**: More file I/O, but context stays manageable even in long sessions

### ADR-008: Skill Files for Shared Knowledge, Agent Prompts for Framing
- **Status**: Accepted
- **Context**: Knowledge needs to be available to agents without duplication
- **Decision**: Static domain knowledge (genre DNA, frequency zones) in skill files; agent-specific framing (persona, focus areas) in agent prompts
- **Consequences**: Modular knowledge management; depends on SDK correctly loading skill files per-agent

````
