# OSC Protocol Reference

> **Version**: 1 (SCHEMA_VERSION)  
> **Last Updated**: Synchronized with codebase

This document is the **canonical reference** for the OSC protocol between the Python backend server and JUCE client.

---

## Message Format

All messages use OSC with JSON payloads. Each message includes a `schema_version` field for compatibility checking.

```
/<address> <json_string>
```

### Schema Version Behavior

| Client Version | Server Version | Behavior |
|----------------|----------------|----------|
| Equal | Equal | ✅ Proceed normally |
| Older | Newer | ⚠️ Server warns, proceeds (backward compatible) |
| Newer | Older | ❌ Server rejects with error code 103 (SCHEMA_VERSION_MISMATCH) |

**Design Rationale**:
- **Older clients → Newer servers**: Server accepts to ensure backward compatibility. The server logs a warning and continues processing. The JUCE client surfaces this via `onSchemaVersionWarning()` callback, displaying a status bar notice and optional dialog.
- **Newer clients → Older servers**: Server rejects immediately. This prevents silent data loss if the client sends fields the server doesn't understand. The JUCE client receives error 103 and should prompt the user to update the server.

**Implementation**:
- Python: `multimodal_gen/server/osc_server.py` checks `schema_version` in `_validate_schema_version()`
- JUCE: `juce/Source/Communication/OSCBridge.cpp` tracks `SCHEMA_VERSION` constant and `OSCBridge::Listener::onSchemaVersionWarning()`

---

## Client → Server Messages

### `/generate`
Start a music generation request.

**Payload:**
```json
{
  "schema_version": 1,
  "request_id": "uuid-string",
  "prompt": "Make a G-Funk beat at 92 BPM in A minor",
  "bpm": 92,
  "key": "A",
  "mode": "minor",
  "duration_bars": 8,
  "options": {
    "tension_arc_shape": "linear_build",
    "tension_intensity": 0.8,
    "motif_mode": "auto",
    "num_motifs": 2,
    "preset": "legendary",
    "style_preset": "g_funk_90s",
    "production_preset": "wide_modern",
    "seed": 123
  }
}
```

**Notes:**
- All fields are optional except `schema_version`, `request_id`, and `prompt`.
- `options.*` fields are backward-compatible: older clients can send `options: {}` and get default behavior.
- Some implementations also accept these keys at the top-level (e.g., `tension_intensity`) for convenience; prefer `options` for forward compatibility.

### `/cancel`
Cancel an in-progress generation.

**Payload:**
```json
{
  "schema_version": 1,
  "request_id": "uuid-to-cancel"
}
```

### `/regenerate`
Regenerate a specific bar range of the current project (sectional regeneration).

**Payload:**
```json
{
  "schema_version": 1,
  "request_id": "uuid-string",
  "start_bar": 4,
  "end_bar": 8,
  "tracks": ["drums", "bass"],
  "seed_strategy": "new",
  "prompt": "optional override prompt",
  "options": {
    "bpm": 92,
    "key": "A",
    "mode": "minor",
    "genre": "g_funk",
    "tension_arc_shape": "linear_build",
    "tension_intensity": 0.8,
    "motif_mode": "auto",
    "num_motifs": 2,
    "preset": "legendary",
    "style_preset": "g_funk_90s",
    "production_preset": "wide_modern",
    "seed": 123
  }
}
```

**Fields:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| start_bar | int | ✅ | 0-indexed starting bar |
| end_bar | int | ✅ | 0-indexed ending bar (exclusive) |
| tracks | string[] | ⚪ | Empty = all tracks; otherwise specific track names |
| seed_strategy | string | ⚪ | "new" for fresh seed, "derived" to vary existing |
| prompt | string | ⚪ | Optional override prompt for this section |
| options | object | ⚪ | Generation context (bpm, key, mode, genre) |

### `/controls/set`
Persist control overrides on the server. These overrides are merged into subsequent `/generate` and `/regenerate` requests.

**Payload:**
```json
{
  "schema_version": 1,
  "request_id": "uuid-string",
  "overrides": {
    "tension_arc_shape": "linear_build",
    "tension_intensity": 0.8,
    "motif_mode": "on",
    "num_motifs": 2,
    "preset": "legendary",
    "style_preset": "g_funk_90s",
    "production_preset": "wide_modern",
    "duration_bars": 8,
    "seed": 123
  }
}
```

### `/controls/clear`
Clear persisted control overrides.

**Payload:**
```json
{
  "schema_version": 1,
  "request_id": "uuid-string",
  "keys": ["tension_intensity", "motif_mode"]
}
```

**Notes:**
- If `keys` is omitted or empty, the server clears all overrides.

### `/analyze`
Analyze an audio file or URL for BPM, key, and other characteristics.

**Payload:**
```json
{
  "schema_version": 1,
  "request_id": "uuid-string",
  "file_path": "/path/to/audio.wav",
  "url": "https://...",
  "options": {}
}
```

**Notes:**
- Provide either `file_path` OR `url`, not both.
- **Engine routing**: 
  - URL sources use `reference_analyzer.py` (requires librosa, yt-dlp)
  - Local files also use `reference_analyzer.py` currently
  - `file_analysis.py` is available as a lightweight alternative (offline-first, graceful degradation)

### `/fx_chain`
Send FX chain configuration for offline render parity.

**Payload:**
```json
{
  "schema_version": 1,
  "fx_chain": {
    "master": [
      {
        "type": "eq",
        "enabled": true,
        "params": {
          "lowGain": 0.0,
          "midGain": 2.5,
          "highGain": -1.0
        }
      },
      {
        "type": "compressor",
        "enabled": true,
        "params": {
          "threshold": -12.0,
          "ratio": 4.0,
          "attack": 10.0,
          "release": 100.0
        }
      }
    ],
    "drums": [...],
    "bass": [...],
    "melodic": [...]
  }
}
```

**Notes:**
- The server stores this configuration and applies it during the next generation.
- FX chain is sent automatically when the user modifies FX in the JUCE UI.
- Each track (master, drums, bass, melodic) has its own chain of effects.

### `/instruments`
Request a refresh of available instruments.

**Payload:**
```json
{
  "schema_version": 1
}
```

### `/ping`
Heartbeat to check server availability.

**Payload:**
```json
{
  "schema_version": 1
}
```

### `/shutdown`
Request graceful server shutdown.

**Payload:**
```json
{
  "schema_version": 1,
  "request_id": "uuid-string"
}
```

### `/expansion/list`
Request list of available expansions.

**Payload:**
```json
{
  "schema_version": 1
}
```

### `/expansion/enable`
Enable or disable an expansion pack.

**Payload:**
```json
{
  "schema_version": 1,
  "expansion_id": "expansion-uuid",
  "enabled": true
}
```

---

## Take Management (Client → Server)

### `/take/select`
Select a specific take for a track during audition.

**Payload:**
```json
{
  "request_id": "uuid-string",
  "track": "drums",
  "take_id": "take_001"
}
```

### `/take/comp`
Composite takes across bar regions (pick best sections from multiple takes).

**Payload:**
```json
{
  "request_id": "uuid-string",
  "track": "drums",
  "regions": [
    {"start_bar": 0, "end_bar": 4, "take_id": "take_001"},
    {"start_bar": 4, "end_bar": 8, "take_id": "take_002"}
  ]
}
```

### `/take/render`
Render a specific take or comp to audio.

**Payload:**
```json
{
  "request_id": "uuid-string",
  "track": "drums",
  "take_id": "take_001",
  "use_comp": false,
  "output_path": "/output/drums_take.wav"
}
```

**Notes:**
- If `use_comp` is true, the server renders the comp regions instead of a single take
- `output_path` is optional; server will use default output directory if not provided

---

## Server → Client Messages

### `/status`
General status updates (generation started, cancelled, etc.).

**Payload:**
```json
{
  "schema_version": 1,
  "status": "generation_started",
  "request_id": "uuid-string",
  "message": "Generation started"
}
```

**Status values:**
- `generation_started` - Generation began
- `generation_cancelled` - Generation was cancelled
- `shutdown_ack` - Shutdown acknowledged
- `connected` - Connection established

### `/progress`
Progress updates during generation.

**Payload:**
```json
{
  "schema_version": 1,
  "request_id": "uuid-string",
  "stage": "generating_drums",
  "progress": 0.45,
  "message": "Generating drum pattern..."
}
```

### `/complete`
Generation completed successfully.

**Payload:**
```json
{
  "schema_version": 1,
  "request_id": "uuid-string",
  "midi_path": "/path/to/output.mid",
  "bpm": 92,
  "key": "A",
  "mode": "minor",
  "duration_seconds": 21.74,
  "tracks": ["drums", "bass", "keys", "lead"]
}
```

### `/error`
Error occurred during processing.

**Payload:**
```json
{
  "schema_version": 1,
  "request_id": "uuid-string",
  "error_code": 100,
  "message": "Generation failed: Invalid prompt"
}
```

**Error codes (from config.py):**
| Code | Name | Description |
|------|------|-------------|
| 100 | GENERATION_FAILED | General generation failure |
| 101 | INVALID_REQUEST | Malformed request |
| 102 | SERVER_BUSY | Server cannot accept new requests |
| 103 | SCHEMA_VERSION_MISMATCH | Client schema newer than server |
| 200 | ANALYSIS_FAILED | Analysis operation failed |

### `/analyze_result`
Analysis completed with results.

**Payload:**
```json
{
  "schema_version": 1,
  "request_id": "uuid-string",
  "bpm": 98.5,
  "bpm_confidence": 0.85,
  "key": "G",
  "mode": "minor",
  "key_confidence": 0.72,
  "genre": "hip-hop",
  "genre_confidence": 0.68,
  "prompt_hints": "98 BPM hip-hop track in G minor with punchy drums",
  "duration_seconds": 180.5
}
```

### `/pong`
Response to `/ping`.

**Payload:**
```json
{
  "schema_version": 1
}
```

### `/instruments_loaded`
Response with available instruments.

**Payload:**
```json
{
  "schema_version": 1,
  "scan_id": "abc12345",
  "success": true,
  "count": 150,
  "categories": ["drums", "bass", "keys", "synths", "strings", "brass", "fx"],
  "sources": {
    "/path/to/instruments": 120,
    "/path/to/expansions/funk": 30
  },
  "instruments": {
    "drums": [
      {
        "id": "uuid-string",
        "name": "Tight Kick 01",
        "filename": "tight_kick_01.wav",
        "path": "/path/to/instruments/drums/tight_kick_01.wav",
        "absolute_path": "/path/to/instruments/drums/tight_kick_01.wav",
        "category": "drums",
        "subcategory": "kicks",
        "tags": ["punchy", "tight", "hip-hop"],
        "key": "",
        "bpm": 0,
        "duration_ms": 450.5,
        "file_size_bytes": 98304,
        "favorite": false,
        "play_count": 0
      }
    ],
    "bass": [...],
    "keys": [...]
  }
}
```

**Instrument fields:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | ✅ | Unique identifier (UUID) |
| name | string | ✅ | Display name |
| filename | string | ✅ | File name only |
| path | string | ✅ | Relative or absolute path |
| absolute_path | string | ✅ | Full absolute path |
| category | string | ✅ | Category from enum (drums, bass, keys, etc.) |
| subcategory | string | ⚪ | Sub-category if applicable |
| tags | string[] | ⚪ | Descriptive tags for search/matching |
| key | string | ⚪ | Musical key (e.g., "C", "F#") |
| bpm | number | ⚪ | BPM for loops, 0 if not applicable |
| duration_ms | number | ⚪ | Duration in milliseconds |
| file_size_bytes | number | ⚪ | File size |
| favorite | boolean | ⚪ | User marked as favorite |
| play_count | number | ⚪ | Usage tracking |
```

### `/expansion/list_response`
List of available expansions.

**Payload:**
```json
{
  "schema_version": 1,
  "expansions": [
    {
      "id": "funk_o_rama",
      "name": "Funk-O-Rama",
      "version": "1.0.5",
      "enabled": true,
      "instrument_count": 48
    }
  ]
}
```

### `/expansion/enable_response`
Acknowledgment of enable/disable.

**Payload:**
```json
{
  "schema_version": 1,
  "expansion_id": "funk_o_rama",
  "enabled": true,
  "success": true
}
```

---

## Take Responses (Server → Client)

### `/takes/available`
Sent after generation when multiple takes were requested. Provides available take lanes for audition.

**Payload:**
```json
{
  "request_id": "uuid-string",
  "tracks": {
    "drums": [
      {
        "take_id": "take_001",
        "seed": 12345,
        "variation_type": "rhythm",
        "midi_path": "/output/drums_take_001.mid"
      },
      {
        "take_id": "take_002",
        "seed": 67890,
        "variation_type": "rhythm",
        "midi_path": "/output/drums_take_002.mid"
      }
    ],
    "bass": [
      {
        "take_id": "take_001",
        "seed": 11111,
        "variation_type": "pitch",
        "midi_path": "/output/bass_take_001.mid"
      }
    ]
  }
}
```

**Take fields:**
| Field | Type | Description |
|-------|------|-------------|
| take_id | string | Unique identifier for this take |
| seed | int | Random seed used (for reproducibility) |
| variation_type | string | Type of variation ("rhythm", "pitch", "timing", "combined") |
| midi_path | string | Path to take MIDI file |

### `/take/selected`
Confirmation that a take was selected.

**Payload:**
```json
{
  "request_id": "uuid-string",
  "track": "drums",
  "take_id": "take_001",
  "success": true
}
```

### `/take/rendered`
Confirmation that a take or comp was rendered to audio.

**Payload:**
```json
{
  "request_id": "uuid-string",
  "track": "drums",
  "take_id": "take_001",
  "output_path": "/output/drums_take_001.wav",
  "success": true
}
```

---

## Generation Lifecycle States

The generation state machine defines the valid states and transitions for a generation request.

### State Diagram
```
┌─────────────┐
│    IDLE     │ ◄─────────────────────────────────────────┐
└──────┬──────┘                                           │
       │                                                  │
       │ Client sends /generate                           │
       ▼                                                  │
┌─────────────┐    Client sends /cancel    ┌─────────────┐│
│   STARTED   │───────────────────────────►│  CANCELLED  ││
│ (ack phase) │                            └──────┬──────┘│
└──────┬──────┘                                   │       │
       │                                          │ timeout│
       │ Server sends /status                     └───────┤
       │ {status:"generation_started"}                    │
       ▼                                                  │
┌─────────────┐    Client sends /cancel    ┌─────────────┐│
│ IN_PROGRESS │───────────────────────────►│  CANCELLED  ││
│ (0% - 99%)  │                            └──────┬──────┘│
└──────┬──────┘                                   │       │
       │                                          │       │
       │ Server sends /progress (0.0 → 1.0)       │       │
       │                                          │       │
       ├──────────────────────────────────────────┴───────┤
       │                                                  │
       ▼                                                  │
┌─────────────┐    ────────────────────────────────►──────┘
│  COMPLETE   │    (UI returns to IDLE)
│    100%     │
└─────────────┘

       │ OR (error occurs)
       ▼
┌─────────────┐    ────────────────────────────────►──────┘
│    ERROR    │    (UI returns to IDLE)
└─────────────┘
```

### State Definitions

| State | Description | Messages | Next States |
|-------|-------------|----------|-------------|
| **IDLE** | No active generation. UI accepts input. | — | STARTED |
| **STARTED** | `/generate` sent, awaiting server acknowledgment | `/generate` sent | IN_PROGRESS, CANCELLED, ERROR |
| **IN_PROGRESS** | Generation active, receiving `/progress` updates | `/status`, `/progress` | COMPLETE, CANCELLED, ERROR |
| **COMPLETE** | Generation finished successfully | `/complete` | IDLE |
| **CANCELLED** | User requested cancel, awaiting confirmation | `/cancel` sent → `/status {cancelled}` | IDLE |
| **ERROR** | Generation failed | `/error` | IDLE |

### State Invariants

1. **Request ID Correlation**: All messages related to a generation include the same `request_id`. The client MUST ignore `/progress` or `/complete` with mismatched IDs.

2. **Timeout Handling**: If no `/progress` or `/complete` is received within `ACTIVITY_TIMEOUT_MS` (default: 30000ms), the client transitions back to IDLE.

3. **Cancel Semantics**: `/cancel` is fire-and-forget. The server may respond with either:
   - `/status` with `status: "generation_cancelled"`
   - `/complete` (if generation finished before cancel arrived)
   
4. **Idempotent Cancel**: Calling `/cancel` multiple times or when not in a generation state is safe (server ignores).

5. **UI Blocking**: While in STARTED or IN_PROGRESS states:
   - Generate button shows "Cancel" action
   - Prompt input may be disabled or read-only
   - Progress indicator shows current `progress` percentage

### JUCE Implementation

```cpp
// In OSCBridge.h
enum class ConnectionState {
    DISCONNECTED,
    CONNECTING,
    CONNECTED,
    RECONNECTING
};

// Generation-specific state tracking
bool isGenerating = false;           // True when in STARTED or IN_PROGRESS
juce::String currentRequestId;       // Tracks active generation
double lastActivityTime;             // For timeout detection
```

### Python Implementation

```python
# In worker.py
class GenerationRequest:
    request_id: str
    # ... other fields
    
class GenerationResult:
    request_id: str  # Echoed back for correlation
    success: bool
    midi_path: Optional[str]
    error_message: Optional[str]
```

---

## Source Files

- **Python Server Config**: `multimodal_gen/server/config.py`
- **Python OSC Handler**: `multimodal_gen/server/osc_server.py`
- **JUCE Messages**: `juce/Source/Communication/Messages.h`
- **JUCE OSC Bridge**: `juce/Source/Communication/OSCBridge.cpp`

---

## Deprecated / Removed

| Old Name | Current Status | Notes |
|----------|----------------|-------|
| `/analyze_complete` (OSC address) | Never existed | `analyze_complete` is used as a progress stage name in `file_analysis.py`, not an OSC address. The actual response is `/analyze_result`. |

---

## Error Codes Reference

For complete error code definitions, see `multimodal_gen/server/config.py`:

| Code Range | Category | Examples |
|------------|----------|----------|
| 100-199 | General errors | 100: UNKNOWN, 101: INVALID_MESSAGE, 103: SCHEMA_VERSION_MISMATCH |
| 200-299 | Generation errors | 200: GENERATION_FAILED, 201: TIMEOUT, 202: CANCELLED |
| 300-399 | Audio errors | 300: AUDIO_RENDER_FAILED, 301: SOUNDFONT_NOT_FOUND |
| 400-499 | Instrument errors | 400: INSTRUMENTS_NOT_FOUND, 401: ANALYSIS_FAILED |
| 500-599 | File errors | 500: FILE_NOT_FOUND, 501: FILE_WRITE_FAILED |
| 900-999 | Server errors | 900: SERVER_BUSY, 901: WORKER_CRASHED |
