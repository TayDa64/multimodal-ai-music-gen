# Motif Engine Integration Guide

## Overview

The Motif Generation Engine provides a foundation for creating short, memorable melodic/rhythmic phrases (motifs) that can be developed throughout a composition. This guide explains how to integrate the motif engine with the existing MIDI generation system.

## Architecture

### Core Components

1. **`Motif`** - Represents a musical motif with:
   - `intervals`: Relative semitone intervals from root (for transposition)
   - `rhythm`: Note durations in beats
   - `accent_pattern`: Velocity weights (0.0-1.0)
   - `genre_tags`: Classification tags (e.g., ["jazz", "bebop"])
   - `chord_context`: Optional chord type (e.g., "dominant7")

2. **`MotifLibrary`** - Storage and retrieval system with filtering by:
   - Genre (e.g., "jazz", "blues")
   - Chord type (e.g., "dominant7", "minor7")
   - Tags (e.g., ["bebop", "chromatic"])

3. **`MotifGenerator`** - Generates or selects motifs based on:
   - Genre identifier
   - Musical context (chord, scale, mood)

### Jazz Motif Patterns (25 patterns)

The library includes 25 built-in jazz motif patterns:

#### Bebop Vocabulary (6 patterns)
- Chromatic enclosures (above, below, combined)
- Bebop scale runs (major, dominant)
- Classic Parker licks

#### ii-V-I Patterns (3 patterns)
- Voice leading progressions
- Resolution patterns
- Enclosure approaches

#### Blues Licks (4 patterns)
- Minor pentatonic patterns
- Blue note licks (with b5)
- Blues turnarounds
- Blues scale runs

#### Rhythmic Motifs (4 patterns)
- Swing eighths with anticipation
- Triplet figures
- Syncopated phrases

#### Call-and-Response (3 patterns)
- Call phrases (questions)
- Response phrases (answers)
- Complete call-response pairs

#### Additional Vocabulary (5 patterns)
- Tritone substitution licks
- Diminished scale patterns
- 7th chord arpeggios (dominant, minor, major)

## Integration with midi_generator.py

### Option 1: Direct MIDI Note Generation

The simplest integration is to use motifs to generate MIDI notes directly:

```python
from multimodal_gen.motif_engine import MotifGenerator

# In your melody generation function
generator = MotifGenerator()

# Generate a jazz motif for a specific chord
motif = generator.generate_motif("jazz", {
    "chord_type": "dominant7",
    "scale": "mixolydian"
})

# Convert to MIDI notes
root_pitch = 60  # C4
notes = motif.to_midi_notes(
    root_pitch=root_pitch,
    start_tick=current_tick,
    ticks_per_beat=TICKS_PER_BEAT,
    base_velocity=90
)

# Add to your track
for tick, dur, pitch, vel in notes:
    track_data.add_note(pitch, tick, dur, vel)
```

### Option 2: Motif-Based Melody Generation

Use motifs as building blocks for longer melodies:

```python
from multimodal_gen.motif_engine import MotifGenerator

def generate_melody_with_motifs(
    bars: int,
    key: str,
    chord_progression: List[str],
    genre: str = "jazz"
) -> List[Tuple[int, int, int, int]]:
    """
    Generate melody using motifs.
    
    This is an EXAMPLE of how motifs SHOULD be integrated.
    To implement: add this function to midi_generator.py
    """
    generator = MotifGenerator()
    notes = []
    current_tick = 0
    
    # Get root pitch from key
    root_pitch = note_name_to_midi(key, octave=5)
    
    for bar_idx in range(bars):
        # Get chord for this bar
        chord_idx = bar_idx % len(chord_progression)
        chord_type = chord_progression[chord_idx]
        
        # Generate motif for this chord
        motif = generator.generate_motif(genre, {
            "chord_type": chord_type
        })
        
        # Convert to MIDI notes
        motif_notes = motif.to_midi_notes(
            root_pitch=root_pitch,
            start_tick=current_tick,
            base_velocity=90
        )
        
        notes.extend(motif_notes)
        
        # Advance to next bar
        current_tick += TICKS_PER_BAR_4_4
    
    return notes
```

### Option 3: Motif Development and Variation

Develop motifs throughout a composition:

```python
from multimodal_gen.motif_engine import MotifGenerator

# Select a primary motif for the piece
generator = MotifGenerator()
primary_motif = generator.generate_motif("jazz", {})

# Intro: Present the motif in original form
intro_notes = primary_motif.to_midi_notes(
    root_pitch=60,
    start_tick=0
)

# Variation 1: Transpose up a 5th
var1_motif = primary_motif.transpose(7)
var1_notes = var1_motif.to_midi_notes(
    root_pitch=60,
    start_tick=TICKS_PER_BAR_4_4 * 4
)

# Variation 2: Transpose down a 4th
var2_motif = primary_motif.transpose(-5)
var2_notes = var2_motif.to_midi_notes(
    root_pitch=60,
    start_tick=TICKS_PER_BAR_4_4 * 8
)
```

## Usage Examples

### Basic Usage

```python
from multimodal_gen.motif_engine import MotifGenerator

# Create generator
generator = MotifGenerator()

# Generate a jazz motif
motif = generator.generate_motif("jazz", {})
print(f"Generated: {motif.name}")
print(f"Intervals: {motif.intervals}")
print(f"Duration: {motif.get_total_duration()} beats")
```

### Chord-Specific Motifs

```python
# Generate motif for dominant 7th chord
dom7_motif = generator.generate_motif("jazz", {
    "chord_type": "dominant7"
})

# Generate motif for minor 7th chord
min7_motif = generator.generate_motif("jazz", {
    "chord_type": "minor7"
})
```

### Get All Jazz Motifs

```python
# Get all available jazz motifs
all_jazz = generator.get_jazz_motifs()
print(f"Total jazz motifs: {len(all_jazz)}")

# Filter by tags
bebop_motifs = [m for m in all_jazz if "bebop" in m.genre_tags]
blues_motifs = [m for m in all_jazz if "blues" in m.genre_tags]
```

### Transposition

```python
# Get a motif
motif = generator.generate_motif("jazz", {})

# Transpose to different keys
motif_in_g = motif.transpose(7)   # Up a 5th
motif_in_f = motif.transpose(-2)  # Down a whole step
```

### MIDI Conversion

```python
# Convert motif to MIDI notes
notes = motif.to_midi_notes(
    root_pitch=60,        # C4
    start_tick=0,         # Start immediately
    ticks_per_beat=480,   # Standard resolution
    base_velocity=90      # Medium-loud
)

# Notes are (tick, duration, pitch, velocity) tuples
for tick, dur, pitch, vel in notes:
    print(f"Note: pitch={pitch}, tick={tick}, duration={dur}, velocity={vel}")
```

### Motif Library Persistence

```python
from multimodal_gen.motif_engine import MotifLibrary, Motif

# Create custom library
library = MotifLibrary()

# Add custom motifs
custom_motif = Motif(
    name="My Custom Lick",
    intervals=[0, 2, 4, 7],
    rhythm=[0.5, 0.5, 0.5, 0.5],
    genre_tags=["jazz", "custom"]
)
library.add_motif(custom_motif)

# Save to file
library.save_to_file("my_motifs.json")

# Load from file
loaded_library = MotifLibrary.load_from_file("my_motifs.json")

# Use with generator
generator = MotifGenerator(library=loaded_library)
```

## Design Decisions

### Why Intervals Instead of Pitches?

Motifs use **relative intervals** (semitones from root) instead of absolute pitches:
- ✅ Transposable to any key
- ✅ Works over different chord types
- ✅ More flexible for composition

### Why Separate Rhythm and Intervals?

Keeping rhythm and pitch separate allows:
- ✅ Rhythmic variation with same pitches
- ✅ Pitch variation with same rhythm
- ✅ Independent development of each aspect

### Why Accent Patterns?

Accent patterns (velocity weights) provide:
- ✅ Musical expression
- ✅ Emphasis on important notes
- ✅ Realistic performance feel

## Extending the System

### Adding New Genres

To add motifs for other genres (hip-hop, R&B, funk):

1. Create a new file in `multimodal_gen/motifs/`:
   ```python
   # multimodal_gen/motifs/hiphop_motifs.py
   from multimodal_gen.motif_engine import Motif
   
   def get_hiphop_motifs() -> List[Motif]:
       motifs = []
       # Add hip-hop specific patterns
       return motifs
   ```

2. Update `multimodal_gen/motifs/__init__.py`:
   ```python
   from .hiphop_motifs import get_hiphop_motifs
   ```

3. Update `MotifGenerator._create_default_library()` in `motif_engine.py`:
   ```python
   from .motifs import hiphop_motifs
   for motif in hiphop_motifs.get_hiphop_motifs():
       library.add_motif(motif)
   ```

### Creating Custom Motifs

```python
from multimodal_gen.motif_engine import Motif, create_motif

# Method 1: Using Motif class directly
my_motif = Motif(
    name="Custom Riff",
    intervals=[0, 3, 5, 7, 8],
    rhythm=[0.5, 0.5, 0.5, 0.5, 1.0],
    accent_pattern=[1.0, 0.8, 0.9, 0.85, 0.95],
    genre_tags=["custom", "funk"],
    chord_context="minor7",
    description="Custom funk riff"
)

# Method 2: Using helper function
my_motif = create_motif(
    name="Custom Riff",
    intervals=[0, 3, 5, 7, 8],
    rhythm=[0.5, 0.5, 0.5, 0.5, 1.0],
    genre_tags=["custom", "funk"]
)
```

## Testing

Run the test suite:

```bash
cd multimodal-ai-music-gen
python -m pytest tests/test_motif_engine.py -v
```

Test the command line interface:

```bash
python -c "from multimodal_gen.motif_engine import MotifGenerator; mg = MotifGenerator(); print(mg.generate_motif('jazz', {}))"
```

## Future Enhancements

Potential additions for future development:

1. **Motif Transformation**
   - Inversion (mirror intervals)
   - Retrograde (reverse order)
   - Augmentation/diminution (change durations)

2. **Motif Sequencing**
   - Sequence motifs up or down by steps
   - Create patterns from motif repetition

3. **Context-Aware Generation**
   - Consider previous motifs
   - Maintain melodic contour
   - Avoid awkward leaps

4. **Integration with Arranger**
   - Different motifs for different sections
   - Motif development through arrangement
   - Thematic relationships

## Notes

- All motifs are interval-based and transposable
- The system is designed to be **additive** - no breaking changes to existing code
- Integration with `midi_generator.py` is **optional** and should be done through documented interfaces
- The motif engine can be used independently or as part of the larger generation system

## Questions?

For questions about integration or to report issues, please file a GitHub issue with the "motif-engine" label.
