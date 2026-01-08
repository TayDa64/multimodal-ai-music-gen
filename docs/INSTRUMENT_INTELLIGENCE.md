# Instrument Intelligence System

## Overview

The Instrument Intelligence System gives the AI **semantic awareness** of available instruments, enabling **deliberate, genre-appropriate selections** instead of random or inappropriate choices.

## The Problem

Previously, the AI would randomly select instruments from the library, leading to:
- Whistles playing during smooth G-Funk tracks
- Harsh synths in mellow lo-fi beats
- Bright sounds in dark trap productions

## The Solution: Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   USER PROMPT                                    │
│  "smooth g_funk beat with warm pads and funky bassline"         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              LAYER 1: SEMANTIC UNDERSTANDING                     │
│                   (InstrumentIntelligence)                       │
│                                                                  │
│  • Parses filenames for instrument type, key, BPM                │
│  • Tags instruments with mood, genre affinity, use cases         │
│  • Identifies EXCLUSIONS (no whistles for G-Funk)                │
│  • Outputs: Filtered candidate list                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              LAYER 2: SONIC MATCHING                             │
│                   (InstrumentMatcher)                            │
│                                                                  │
│  • Analyzes audio characteristics (brightness, punch, warmth)    │
│  • Computes similarity to ideal genre profile                    │
│  • Ranks candidates by sonic fit                                 │
│  • Outputs: Best matching instrument                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              LAYER 3: AUDIO RENDERING                            │
│                   (AudioRenderer)                                │
│                                                                  │
│  • Loads selected samples                                        │
│  • Applies genre-appropriate processing                          │
│  • Renders final audio                                           │
└─────────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. InstrumentIntelligence (`instrument_intelligence.py`)

The brain of the system. Provides:

- **Filename Parsing**: Extracts instrument type, key, BPM from filenames
- **Genre Profiles**: Defines ideal characteristics per genre
- **Exclusion Rules**: Prevents inappropriate selections
- **Palette Selection**: Picks instruments for each track role

```python
from multimodal_gen import InstrumentIntelligence

engine = InstrumentIntelligence()
engine.index_directory("./instruments")

palette = engine.select_instrument_palette(
    genre="g_funk",
    mood_keywords=["smooth", "warm"],
    required_tracks=["kick", "snare", "bass", "keys"]
)
```

### 2. InstrumentMatcher (`instrument_manager.py`)

Finds the best sonic match from allowed candidates:

```python
from multimodal_gen import InstrumentMatcher

matcher = InstrumentMatcher(library)
matcher.set_intelligence(engine)  # Enable semantic filtering

# Now get_best_match() will:
# 1. Filter out excluded sounds
# 2. Score remaining by sonic similarity
# 3. Return the best fit
best_kick = matcher.get_best_match("kick", genre="g_funk")
```

### 3. Genre Profiles (`GENRE_PROFILES`)

Define what each genre needs:

```python
GENRE_PROFILES = {
    "g_funk": {
        "description": "West Coast hip-hop: smooth, laid-back, funky",
        "preferred_drums": {
            "kick": {"warmth": (0.6, 1.0), "tags": ["deep", "808"]},
            "snare": {"brightness": (0.4, 0.7), "tags": ["crisp"]},
        },
        "excluded_sounds": ["whistle", "harsh", "aggressive"],
    },
    # ... other genres
}
```

## How Exclusions Work

1. **At Index Time**: Each sample is tagged with `exclude_contexts`
2. **At Selection Time**: Samples are filtered before scoring
3. **Integration**: `InstrumentMatcher._is_excluded()` checks against intelligence

```python
# Whistle samples get these tags:
metadata = InstrumentMetadata(
    ...
    exclude_contexts=[
        'main_melody', 'harmony', 'sustained', 
        'g_funk', 'lofi', 'jazz', 'rnb', 'smooth'
    ]
)
```

## Testing

Run the comprehensive test suite:

```bash
python test_intelligence.py
```

This verifies:
1. Instrument indexing works
2. Exclusion rules are applied
3. Palette selection is genre-appropriate
4. Matcher integration is functional
5. Genre profiles are comprehensive
6. Different genres get different instruments

## Adding New Genres

1. Add profile to `GENRE_PROFILES` in `instrument_intelligence.py`
2. Define:
   - `description`: Human-readable description
   - `tempo_range`: BPM range (min, max)
   - `preferred_drums`: Ideal drum characteristics
   - `preferred_bass`: Ideal bass characteristics
   - `excluded_sounds`: List of sounds to never select

Example:
```python
"synthwave": {
    "description": "80s retro electronic: big drums, analog synths",
    "tempo_range": (100, 130),
    "preferred_drums": {
        "kick": {"punch": (0.6, 0.9), "tags": ["gated", "80s"]},
        "snare": {"brightness": (0.6, 0.9), "tags": ["gated", "reverb"]},
    },
    "preferred_synths": {
        "tags": ["analog", "pad", "arp", "80s"],
    },
    "excluded_sounds": ["modern", "trap", "mumble"],
}
```

## Future Improvements

1. **Audio Analysis**: Use librosa to analyze actual sonic content
2. **User Preferences**: Learn from user selections over time
3. **Contextual Awareness**: Adjust based on song section (intro vs chorus)
4. **Ensemble Coherence**: Ensure selected instruments work well together
