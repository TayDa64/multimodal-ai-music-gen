# InstrumentResolutionService Implementation Summary

## Overview

Created `multimodal_gen/instrument_resolution.py` - a new service that bridges expansion instruments to the generation pipeline, solving the problem where "1031 Funk o Rama instruments are loaded but never used" due to hardcoded mappings.

## Files Created

### `multimodal_gen/instrument_resolution.py`
- **InstrumentResolutionService** class with:
  - Takes an `ExpansionManager` instance (optional, falls back to defaults)
  - Maintains dynamic `program↔instrument` registry
  - Auto-allocates MIDI programs (110-127) for expansion instruments
  - Methods:
    - `resolve_instrument(name, genre, prefer_expansion)` → `ResolvedInstrument`
    - `get_program_for_instrument(name)` → `int`
    - `get_instrument_for_program(program)` → `Optional[str]`
    - `get_instruments_for_genre(genre)` → `List[str]`
    - `register_instrument(name, program, override)` → `int`
    - `get_registry_stats()` → `Dict`
    - `list_registered_instruments()` → `List[Dict]`

- **ResolvedInstrument** dataclass with:
  - `name`: Resolved instrument name
  - `program`: MIDI program number (0-127)
  - `sample_paths`: List of audio file paths
  - `match_type`: How it was resolved (exact, mapped, semantic, spectral, default)
  - `confidence`: Resolution confidence (0-1)
  - `source`, `original_request`, `genre`, `note`: Metadata

- **Defaults exported**:
  - `DEFAULT_GENRE_INSTRUMENTS`: Genre → instrument list mapping
  - `DEFAULT_INSTRUMENT_TO_PROGRAM`: Instrument → MIDI program mapping
  - `DEFAULT_PROGRAM_TO_INSTRUMENT`: MIDI program → instrument mapping

## Files Modified

### `multimodal_gen/midi_generator.py`
- Added import for `InstrumentResolutionService`
- Added `instrument_service` parameter to `MidiGenerator.__init__`
- Added `_resolve_instrument_program()` helper method
- Updated `_create_chord_track()` to use service when available
- Updated `_create_melody_track()` to use service when available
- **Backward compatible**: Falls back to hardcoded mappings when no service

### `multimodal_gen/audio_renderer.py`
- Added import for `InstrumentResolutionService`
- Added `instrument_service` parameter to `ProceduralRenderer.__init__`
- Updated `_load_expansion_instruments()` to use service for genre instruments
- Updated `_get_expansion_sample_for_program()` to use service for program→instrument
- Added `instrument_service` parameter to `AudioRenderer.__init__`
- **Backward compatible**: Falls back to hardcoded dicts when no service

### `multimodal_gen/prompt_parser.py`
- Added import for `InstrumentResolutionService` and `DEFAULT_GENRE_INSTRUMENTS`
- Added module-level `_instrument_service` variable
- Added `set_instrument_service(service)` function for orchestrator injection
- Added `get_genre_instruments_via_service(genre)` helper function
- Updated `ParsedPrompt._get_genre_instruments()` to use service when available
- **Backward compatible**: Falls back to hardcoded mappings when no service

### `multimodal_gen/__init__.py`
- Added exports for new module components

## Usage Example

```python
from multimodal_gen.expansion_manager import create_expansion_manager
from multimodal_gen.instrument_resolution import InstrumentResolutionService
from multimodal_gen.midi_generator import MidiGenerator
from multimodal_gen.audio_renderer import AudioRenderer
from multimodal_gen.prompt_parser import set_instrument_service

# Create expansion manager and scan expansions
exp_mgr = create_expansion_manager()
exp_mgr.scan_expansions("./expansions")

# Create resolution service
service = InstrumentResolutionService(exp_mgr)

# Inject into prompt parser (module-level)
set_instrument_service(service)

# Use with MidiGenerator
midi_gen = MidiGenerator(instrument_service=service)

# Use with AudioRenderer  
renderer = AudioRenderer(
    expansion_manager=exp_mgr,
    instrument_service=service,
    genre='eskista'
)

# Resolve an instrument
resolved = service.resolve_instrument('krar', genre='eskista')
print(f"Resolved: {resolved.name}, program={resolved.program}")

# Get instruments for a genre
instruments = service.get_instruments_for_genre('trap')
```

## Key Design Decisions

1. **Optional dependency**: Service is optional in all classes - existing code works unchanged
2. **Bidirectional mapping**: Program→instrument and instrument→program both supported
3. **Auto-allocation**: MIDI programs 110-127 auto-assigned to expansion instruments
4. **Caching**: Resolution results cached for performance
5. **Thread-safe**: Uses locks for registry modifications
6. **5-tier fallback**: Exact → Mapped → Semantic → Spectral → Default

## MIDI Program Allocation

- **0-109**: Reserved for standard GM instruments (hardcoded)
- **110-127**: Reserved for expansion instruments (dynamic allocation)
- Ethiopian instruments pre-registered: krar=110, masenqo=111, washint=112, begena=113

## Tests Passed

1. ✅ Module imports correctly
2. ✅ Service creates without ExpansionManager (uses defaults)
3. ✅ Service creates with ExpansionManager (registers expansion instruments)
4. ✅ `resolve_instrument()` works for known and unknown instruments
5. ✅ `get_instruments_for_genre()` returns correct lists
6. ✅ Bidirectional program mapping works
7. ✅ MidiGenerator accepts `instrument_service` parameter
8. ✅ ProceduralRenderer accepts `instrument_service` parameter
9. ✅ `set_instrument_service()` in prompt_parser works
10. ✅ Backward compatibility: All classes work without service
