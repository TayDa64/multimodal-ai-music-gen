# Template/Configuration-Driven Music Arrangement Systems

## Research Report for RLM-Inspired Orchestration System

**Date:** January 2025  
**Purpose:** Design foundation for migrating from hardcoded `arranger.py` to a fully config-driven arrangement system

---

## Table of Contents

1. [How Music Production Tools Define Song Structures in Data](#1-how-music-production-tools-define-song-structures-in-data)
2. [YAML/JSON Schemas for Music Arrangement](#2-yamljson-schemas-for-music-arrangement)
3. [MusicXML and MIDI File Structure Definitions](#3-musicxml-and-midi-file-structure-definitions)
4. [Band-in-a-Box and iReal Pro Chord Progression Formats](#4-band-in-a-box-and-ireal-pro-chord-progression-formats)
5. [Declarative vs Imperative Arrangement Definition](#5-declarative-vs-imperative-arrangement-definition)
6. [Proposed Schema Design](#6-proposed-schema-design)
7. [Migration Path from Hardcoded arranger.py](#7-migration-path-from-hardcoded-arrangerpy)

---

## 1. How Music Production Tools Define Song Structures in Data

### Industry Approaches

#### 1.1 Traditional DAW Approach (Imperative)
Most DAWs (Ableton, Logic, FL Studio) store arrangements as:
- **Timeline-based events**: Absolute positions in time
- **Clip/Region references**: Pointers to audio/MIDI data
- **Automation lanes**: Parameter changes over time
- **Marker tracks**: Named positions (Verse, Chorus, etc.)

**Pros:** Maximum flexibility, precise control  
**Cons:** Not reusable, tightly coupled to specific project

#### 1.2 Band-in-a-Box Approach (Declarative)
Band-in-a-Box defines songs through four primary inputs:
1. **Chord Progression**: Standard chord notation (Cmaj7, Dm7, G7, etc.)
2. **Key Signature**: Overall tonality
3. **Tempo**: BPM value
4. **Style**: Named arrangement template with associated instrumentation

The "Style" concept is particularly relevant - it encapsulates:
- Drum patterns and fills
- Bass patterns
- Comping patterns for piano/guitar
- Arrangement density rules
- Genre-appropriate articulations

#### 1.3 Sonic Pi (Live Coding Declarative)
```ruby
live_loop :drums do
  sample :bd_haus
  sleep 0.5
end

live_loop :melody do
  use_synth :prophet
  play (ring :c4, :e4, :g4).tick
  sleep 0.25
end
```

Key concepts:
- **live_loop**: Named, repeating pattern blocks
- **sleep**: Duration-based timing (beat units)
- **rings**: Cyclical data structures for patterns
- **tick/look**: Pattern sequencing without explicit counters

#### 1.4 Alda (Text-Based Music Definition)
```alda
piano:
  o4 c4 d e f | g2 g | a4 a a a | g1

violin:
  o5 r1 | r1 | c4 c c c | b1
```

Key concepts:
- **Instrument declarations** with colon syntax
- **Octave notation** (o4, <, >)
- **Note lengths** (c4 = quarter note C, c1 = whole note)
- **Voices** for polyphony (V1:, V2:)
- **Attributes** for tempo, volume, quantization

---

## 2. YAML/JSON Schemas for Music Arrangement

### 2.1 Existing genres.json Analysis

The project already has a well-structured `genres.json` with:
- Genre definitions (tempo, key, instruments, drums, fx_chain, spectral_profile, arrangement)
- Instrument categories
- FX definitions
- Humanization profiles

### 2.2 Proposed Arrangement Template Schema

```yaml
# arrangement_templates.yaml
$schema: "https://json-schema.org/draft/2020-12/schema"
version: "1.0.0"

arrangement_templates:
  trap:
    display_name: "Trap Arrangement"
    genre_ref: "trap"  # Reference to genres.json
    
    sections:
      - type: intro
        bars: 8
        config:
          energy_level: 0.3
          drum_density: 0.4
          instrument_density: 0.3
          enable_bass: false
          enable_melody: true
          filter_cutoff: 0.6
          
      - type: verse
        bars: 16
        config:
          energy_level: 0.6
          drum_density: 0.7
          instrument_density: 0.5
          enable_bass: true
          enable_melody: true
          texture_amount: 0.3
          
      - type: drop
        bars: 16
        config:
          energy_level: 0.95
          drum_density: 1.0
          instrument_density: 0.8
          enable_bass: true
          enable_fx: true
          filter_cutoff: 1.0
          
      - type: breakdown
        bars: 8
        config:
          energy_level: 0.4
          drum_density: 0.2
          instrument_density: 0.3
          enable_pads: true
          enable_drums: false
          
      - type: outro
        bars: 8
        config:
          energy_level: 0.2
          drum_density: 0.3
          instrument_density: 0.2
          filter_cutoff: 0.4
          fade_out: true
    
    transitions:
      verse_to_drop:
        type: riser
        duration_bars: 2
        fx: ["white_noise_sweep", "filter_sweep_up"]
        
      drop_to_breakdown:
        type: cut
        pre_silence_beats: 0.5
        
    motif_assignments:
      intro:
        primary_motif: original
        variation: sparse
      verse:
        primary_motif: original
        variation: melodic
      drop:
        primary_motif: transformed
        transformation: rhythmic_intensify
      breakdown:
        primary_motif: fragmented
        variation: ambient

section_types:
  intro:
    description: "Opening section, establishes mood"
    typical_bars: [4, 8, 16]
    default_energy: 0.3
    
  verse:
    description: "Main lyrical/melodic section"
    typical_bars: [8, 16]
    default_energy: 0.6
    
  pre_chorus:
    description: "Build-up to chorus"
    typical_bars: [4, 8]
    default_energy: 0.7
    
  chorus:
    description: "Main hook, highest energy"
    typical_bars: [8, 16]
    default_energy: 0.85
    
  drop:
    description: "EDM-style climax section"
    typical_bars: [8, 16, 32]
    default_energy: 0.95
    
  breakdown:
    description: "Minimal, atmospheric section"
    typical_bars: [4, 8, 16]
    default_energy: 0.4
    
  buildup:
    description: "Rising tension before drop"
    typical_bars: [4, 8]
    default_energy: 0.7
    
  bridge:
    description: "Contrasting section"
    typical_bars: [8]
    default_energy: 0.5
    
  outro:
    description: "Closing section"
    typical_bars: [4, 8, 16]
    default_energy: 0.2

section_configs:
  # Default configurations per section type
  intro:
    typical_bars: 8
    energy_level: 0.3
    drum_density: 0.4
    instrument_density: 0.3
    texture_amount: 0.4
    filter_cutoff: 0.7
    enable_drums: true
    enable_bass: false
    enable_melody: true
    enable_pads: true
    enable_fx: false
    
  # ... (similar for other section types)
```

### 2.3 Section Configuration JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "section_config_schema",
  "title": "Section Configuration",
  "type": "object",
  "properties": {
    "typical_bars": {
      "type": "integer",
      "minimum": 1,
      "maximum": 64,
      "description": "Default number of bars for this section"
    },
    "energy_level": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 1.0,
      "description": "Overall energy/intensity (0-1)"
    },
    "drum_density": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 1.0,
      "description": "How busy the drum pattern is"
    },
    "instrument_density": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 1.0,
      "description": "How many instruments are active"
    },
    "texture_amount": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 1.0,
      "description": "Ambient texture layer intensity"
    },
    "filter_cutoff": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 1.0,
      "description": "Global filter sweep position"
    },
    "enable_drums": { "type": "boolean", "default": true },
    "enable_bass": { "type": "boolean", "default": true },
    "enable_melody": { "type": "boolean", "default": true },
    "enable_pads": { "type": "boolean", "default": false },
    "enable_fx": { "type": "boolean", "default": false }
  },
  "required": ["energy_level", "drum_density"]
}
```

---

## 3. MusicXML and MIDI File Structure Definitions

### 3.1 MusicXML Structure

MusicXML 4.0 (W3C Community Standard) provides two organizational approaches:

#### Score-Partwise (Parts Contain Measures)
```xml
<score-partwise>
  <part-list>
    <score-part id="P1">
      <part-name>Piano</part-name>
    </score-part>
  </part-list>
  
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>4</divisions>
        <key><fifths>0</fifths></key>
        <time><beats>4</beats><beat-type>4</beat-type></time>
      </attributes>
      <note>
        <pitch><step>C</step><octave>4</octave></pitch>
        <duration>4</duration>
        <type>quarter</type>
      </note>
    </measure>
  </part>
</score-partwise>
```

#### Score-Timewise (Measures Contain Parts)
Better for vertical (harmonic) analysis - all instruments at same time point together.

#### Key MusicXML Elements for Arrangement
- `<direction>`: Tempo, dynamics, rehearsal marks
- `<sound>`: Playback instructions (tempo, dynamics)
- `<barline>`: Section markers, repeats
- `<harmony>`: Chord symbols
- `<attributes>`: Key, time signature, clef changes

### 3.2 MIDI File Structure

Standard MIDI Files (SMF) contain:

#### Header Chunk
- Format type (0, 1, or 2)
- Number of tracks
- Time division (ticks per quarter note)

#### Track Chunks
- Meta events (tempo, time signature, text markers)
- MIDI channel events (note on/off, control change)
- Delta times (ticks since last event)

#### Key Meta Events for Arrangement
```
FF 03 len text    - Track name
FF 04 len text    - Instrument name
FF 06 len text    - Marker (section labels!)
FF 51 03 tttttt   - Tempo (microseconds per quarter)
FF 58 04 nn dd cc bb - Time signature
FF 59 02 sf mi    - Key signature
```

**Marker events (FF 06)** are particularly useful - they can label sections:
```
FF 06 05 "VERSE"
FF 06 06 "CHORUS"
```

---

## 4. Band-in-a-Box and iReal Pro Chord Progression Formats

### 4.1 Band-in-a-Box

#### Input Model
Band-in-a-Box pioneered the "intelligent accompaniment" concept:

1. **Chord Entry**: Type chords in standard notation
   - `C` = C major
   - `Cm7` = C minor 7th
   - `G7sus4` = G dominant 7 sus4
   
2. **Style Selection**: Choose from thousands of "Styles"
   - Each style contains patterns for drums, bass, piano, guitar, strings
   - Patterns vary by section type (A section, B section, fills)
   
3. **Form Definition**:
   - Number of choruses
   - Intro/outro options
   - Tag endings

#### Style File Structure
Each style contains:
- **Pattern slots**: Different variations (1-4 per instrument)
- **Fill patterns**: Transition patterns
- **Push detection**: Anticipation timing rules
- **Instrument patches**: MIDI program numbers
- **Volume/pan settings**: Per-instrument mix

#### RealTracks
Pre-recorded musician performances that adapt to chord changes:
- Time-stretching to match tempo
- Pitch-shifting for chord roots
- Style-matched phrasing

### 4.2 iReal Pro Format

iReal Pro uses a compact chord chart notation:

```
{T: Song Title}
{C: Composer}
{St: Style}
{K: C}        // Key
{Sg: 4}       // Time signature (4/4)

*A
C  |G7  |Am  |F   |
*B
Dm7 |G7  |C   |C   |
```

#### Notation Elements
- `*A`, `*B`: Section markers
- `|`: Bar lines
- Chord symbols follow standard jazz notation
- `N.C.`: No chord
- `%`: Repeat previous bar
- `{ }`: Repeat markers
- `<` `>`: First/second endings

---

## 5. Declarative vs Imperative Arrangement Definition

### 5.1 Imperative Approach (Current arranger.py)

```python
# Current hardcoded approach
ARRANGEMENT_TEMPLATES: Dict[str, List[Tuple[SectionType, int]]] = {
    "trap_soul": [
        (SectionType.INTRO, 8),
        (SectionType.VERSE, 16),
        (SectionType.PRE_CHORUS, 8),
        (SectionType.CHORUS, 16),
        # ...
    ],
}

def create_arrangement(self, parsed: ParsedPrompt, duration_secs: float):
    template = self._get_template(parsed.genre)
    adjusted = self._adjust_to_duration(template, duration_secs, bpm)
    # Procedural construction...
```

**Characteristics:**
- Logic embedded in code
- Changes require code modifications
- Tight coupling between data and behavior
- Harder to add new genres without coding

### 5.2 Declarative Approach (Proposed)

```yaml
# arrangement_templates/trap_soul.yaml
template:
  name: trap_soul
  base_genre: trap_soul
  
  sections:
    - { type: intro, bars: 8 }
    - { type: verse, bars: 16 }
    - { type: pre_chorus, bars: 8 }
    - { type: chorus, bars: 16 }
    - { type: verse, bars: 16 }
    - { type: chorus, bars: 16 }
    - { type: bridge, bars: 8 }
    - { type: chorus, bars: 16 }
    - { type: outro, bars: 8 }
    
  duration_rules:
    min_bars: 32
    max_bars: 256
    expandable_sections: [verse, chorus]
    contractible_sections: [intro, outro, bridge]
```

**Characteristics:**
- Data-driven definitions
- No code changes needed for new templates
- Clear separation of concerns
- User-editable without programming knowledge
- Versionable as separate files
- Supports hot-reloading

### 5.3 Comparison Table

| Aspect | Imperative | Declarative |
|--------|------------|-------------|
| **Adding new genre** | Code change | Add YAML file |
| **User customization** | Requires Python | Edit config file |
| **Validation** | Runtime errors | Schema validation |
| **Version control** | Mixed with code | Separate config repos |
| **A/B testing** | Complex | Easy swap |
| **Documentation** | Code comments | Self-documenting |
| **Runtime flexibility** | Limited | Hot-reload possible |

### 5.4 Hybrid Approach (Recommended)

The Sonic Pi model suggests a useful hybrid:
- **Core engine**: Imperative (Python)
- **Pattern definitions**: Declarative (YAML/JSON)
- **Composition rules**: Declarative with embedded DSL expressions

```yaml
# Hybrid example with embedded expressions
sections:
  - type: verse
    bars: "{{ 16 if energy > 0.7 else 8 }}"
    config:
      drum_density: "{{ base_density * energy_multiplier }}"
      
rules:
  - if: "section.type == 'drop' and previous.type == 'buildup'"
    then:
      apply_transition: "dramatic_cut"
```

---

## 6. Proposed Schema Design

### 6.1 File Structure

```
multimodal_gen/
  configs/
    schemas/
      arrangement_template.schema.json
      section_config.schema.json
      motif_assignment.schema.json
      
    genres/
      genres.json (existing, enhanced)
      
    arrangements/
      templates/
        trap.yaml
        trap_soul.yaml
        rnb.yaml
        lofi.yaml
        house.yaml
        ethiopian.yaml
        eskista.yaml
        ethio_jazz.yaml
      
      section_configs/
        default_sections.yaml
        genre_overrides/
          trap_sections.yaml
          lofi_sections.yaml
          
    motifs/
      genre_mappings/
        trap_motifs.yaml
        ethiopian_motifs.yaml
```

### 6.2 Master Arrangement Template Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "arrangement_template",
  "title": "Arrangement Template",
  "type": "object",
  
  "properties": {
    "template_id": {
      "type": "string",
      "pattern": "^[a-z_]+$",
      "description": "Unique identifier for this template"
    },
    
    "display_name": {
      "type": "string",
      "description": "Human-readable template name"
    },
    
    "genre_ref": {
      "type": "string",
      "description": "Reference to genres.json entry"
    },
    
    "version": {
      "type": "string",
      "pattern": "^\\d+\\.\\d+\\.\\d+$"
    },
    
    "sections": {
      "type": "array",
      "items": { "$ref": "#/$defs/section" },
      "minItems": 1
    },
    
    "transitions": {
      "type": "object",
      "additionalProperties": { "$ref": "#/$defs/transition" }
    },
    
    "motif_assignments": {
      "type": "object",
      "additionalProperties": { "$ref": "#/$defs/motif_assignment" }
    },
    
    "duration_rules": {
      "$ref": "#/$defs/duration_rules"
    }
  },
  
  "$defs": {
    "section": {
      "type": "object",
      "properties": {
        "type": {
          "type": "string",
          "enum": ["intro", "verse", "pre_chorus", "chorus", "drop", 
                   "breakdown", "buildup", "bridge", "outro", "variation"]
        },
        "bars": { "type": "integer", "minimum": 1 },
        "config_override": { "$ref": "section_config.schema.json" },
        "repeat": { "type": "integer", "minimum": 1, "default": 1 }
      },
      "required": ["type", "bars"]
    },
    
    "transition": {
      "type": "object",
      "properties": {
        "type": {
          "type": "string",
          "enum": ["riser", "cut", "fade", "fill", "sweep"]
        },
        "duration_bars": { "type": "number" },
        "fx": {
          "type": "array",
          "items": { "type": "string" }
        }
      }
    },
    
    "motif_assignment": {
      "type": "object",
      "properties": {
        "primary_motif": {
          "type": "string",
          "enum": ["original", "transformed", "fragmented", "inverted"]
        },
        "variation": {
          "type": "string",
          "enum": ["sparse", "melodic", "rhythmic", "ambient", "full"]
        },
        "transformation": {
          "type": "string"
        }
      }
    },
    
    "duration_rules": {
      "type": "object",
      "properties": {
        "min_bars": { "type": "integer" },
        "max_bars": { "type": "integer" },
        "expandable_sections": {
          "type": "array",
          "items": { "type": "string" }
        },
        "contractible_sections": {
          "type": "array",
          "items": { "type": "string" }
        }
      }
    }
  },
  
  "required": ["template_id", "genre_ref", "sections"]
}
```

### 6.3 Example Complete Template (trap_soul.yaml)

```yaml
template_id: trap_soul
display_name: "Trap Soul / R&B Trap"
genre_ref: trap_soul
version: "1.0.0"

metadata:
  author: "RLM System"
  description: "Emotional, melodic trap with R&B influences"
  tags: ["melodic", "emotional", "modern_rnb"]

sections:
  - type: intro
    bars: 8
    config_override:
      energy_level: 0.3
      drum_density: 0.2
      instrument_density: 0.3
      enable_bass: false
      enable_pads: true
      filter_cutoff: 0.6
      
  - type: verse
    bars: 16
    config_override:
      energy_level: 0.5
      drum_density: 0.6
      instrument_density: 0.5
      enable_bass: true
      texture_amount: 0.3
      
  - type: pre_chorus
    bars: 8
    config_override:
      energy_level: 0.65
      drum_density: 0.7
      instrument_density: 0.6
      enable_fx: true
      filter_cutoff: 0.8
      
  - type: chorus
    bars: 16
    config_override:
      energy_level: 0.8
      drum_density: 0.8
      instrument_density: 0.75
      enable_bass: true
      enable_pads: true
      texture_amount: 0.5
      
  - type: verse
    bars: 16
    # Uses default verse config
    
  - type: chorus
    bars: 16
    repeat: 2
    
  - type: bridge
    bars: 8
    config_override:
      energy_level: 0.45
      drum_density: 0.3
      instrument_density: 0.4
      enable_pads: true
      enable_drums: false
      
  - type: chorus
    bars: 16
    config_override:
      energy_level: 0.85
      
  - type: outro
    bars: 8
    config_override:
      energy_level: 0.25
      drum_density: 0.3
      instrument_density: 0.2
      filter_cutoff: 0.4
      fade_out: true

transitions:
  pre_chorus_to_chorus:
    type: riser
    duration_bars: 2
    fx: ["filter_sweep_up", "reverb_swell"]
    
  chorus_to_verse:
    type: fill
    duration_bars: 0.5
    
  bridge_to_chorus:
    type: riser
    duration_bars: 4
    fx: ["white_noise_sweep", "filter_sweep_up", "cymbal_roll"]

motif_assignments:
  intro:
    primary_motif: original
    variation: sparse
    instruments: ["piano", "pad"]
    
  verse:
    primary_motif: original
    variation: melodic
    instruments: ["piano", "rhodes", "bass"]
    
  pre_chorus:
    primary_motif: original
    variation: building
    transformation: add_tension
    
  chorus:
    primary_motif: transformed
    variation: full
    transformation: harmonic_expand
    
  bridge:
    primary_motif: fragmented
    variation: ambient
    instruments: ["pad", "strings"]
    
  outro:
    primary_motif: original
    variation: sparse
    transformation: fade_fragments

duration_rules:
  min_bars: 48
  max_bars: 160
  target_duration_secs: 180  # 3 minutes default
  expandable_sections: [verse, chorus]
  contractible_sections: [intro, outro, bridge]
  repeat_rules:
    chorus:
      max_repeats: 3
      min_bars_between: 16
```

---

## 7. Migration Path from Hardcoded arranger.py

### Phase 1: Schema Definition & Validation

1. **Create JSON schemas** for all config types
2. **Export current hardcoded data** to YAML files
3. **Implement schema validator** using `jsonschema` library
4. **Add unit tests** comparing YAML output to hardcoded behavior

### Phase 2: Config Loading Infrastructure

```python
# multimodal_gen/config_loader.py
from pathlib import Path
from typing import Dict, Any, Optional
import yaml
import json
from jsonschema import validate, ValidationError

class ConfigLoader:
    """Runtime configuration loader for arrangement templates."""
    
    def __init__(self, config_dir: Path = None):
        self.config_dir = config_dir or Path(__file__).parent / "configs"
        self._cache: Dict[str, Any] = {}
        self._schemas: Dict[str, Any] = {}
        self._load_schemas()
    
    def _load_schemas(self):
        """Load all JSON schemas for validation."""
        schema_dir = self.config_dir / "schemas"
        for schema_file in schema_dir.glob("*.schema.json"):
            with open(schema_file) as f:
                self._schemas[schema_file.stem] = json.load(f)
    
    def load_arrangement_template(self, template_id: str) -> Dict[str, Any]:
        """Load and validate an arrangement template."""
        cache_key = f"arrangement:{template_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Try YAML first, then JSON
        template_path = self.config_dir / "arrangements" / "templates" / f"{template_id}.yaml"
        if not template_path.exists():
            template_path = template_path.with_suffix(".json")
        
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_id}")
        
        with open(template_path) as f:
            if template_path.suffix == ".yaml":
                template = yaml.safe_load(f)
            else:
                template = json.load(f)
        
        # Validate against schema
        self._validate(template, "arrangement_template")
        
        self._cache[cache_key] = template
        return template
    
    def _validate(self, data: Dict, schema_name: str):
        """Validate data against a JSON schema."""
        if schema_name in self._schemas:
            validate(instance=data, schema=self._schemas[schema_name])
    
    def reload(self):
        """Clear cache for hot-reloading."""
        self._cache.clear()
    
    def get_available_templates(self) -> list:
        """List all available arrangement templates."""
        templates_dir = self.config_dir / "arrangements" / "templates"
        return [
            p.stem for p in templates_dir.glob("*.yaml")
        ] + [
            p.stem for p in templates_dir.glob("*.json")
        ]
```

### Phase 3: Arranger Refactoring

```python
# multimodal_gen/arranger.py (refactored)
from .config_loader import ConfigLoader

class Arranger:
    """Config-driven arrangement generator."""
    
    def __init__(self, config_loader: ConfigLoader = None):
        self.config_loader = config_loader or ConfigLoader()
        self._section_configs = self._load_section_configs()
    
    def _load_section_configs(self) -> Dict[SectionType, SectionConfig]:
        """Load section configurations from YAML."""
        config = self.config_loader.load_section_configs("default_sections")
        return {
            SectionType[k.upper()]: SectionConfig(**v)
            for k, v in config.items()
        }
    
    def _get_template(self, genre: str) -> List[Tuple[SectionType, int]]:
        """Load arrangement template from config."""
        template_data = self.config_loader.load_arrangement_template(genre)
        
        sections = []
        for section in template_data["sections"]:
            section_type = SectionType[section["type"].upper()]
            bars = section["bars"]
            repeat = section.get("repeat", 1)
            
            for _ in range(repeat):
                sections.append((section_type, bars))
        
        return sections
    
    def _get_section_config(self, 
                           section_type: SectionType, 
                           genre: str,
                           section_data: Optional[Dict] = None) -> SectionConfig:
        """Get section config with optional overrides."""
        base_config = self._section_configs.get(section_type)
        
        if section_data and "config_override" in section_data:
            # Merge overrides
            override = section_data["config_override"]
            return SectionConfig(
                typical_bars=override.get("bars", base_config.typical_bars),
                energy_level=override.get("energy_level", base_config.energy_level),
                drum_density=override.get("drum_density", base_config.drum_density),
                instrument_density=override.get("instrument_density", base_config.instrument_density),
                texture_amount=override.get("texture_amount", base_config.texture_amount),
                filter_cutoff=override.get("filter_cutoff", base_config.filter_cutoff),
                enable_drums=override.get("enable_drums", base_config.enable_drums),
                enable_bass=override.get("enable_bass", base_config.enable_bass),
                enable_melody=override.get("enable_melody", base_config.enable_melody),
                enable_pads=override.get("enable_pads", base_config.enable_pads),
                enable_fx=override.get("enable_fx", base_config.enable_fx),
            )
        
        return base_config
```

### Phase 4: Export Existing Data

```python
# scripts/export_hardcoded_configs.py
"""One-time script to export hardcoded data to YAML files."""

import yaml
from multimodal_gen.arranger import (
    ARRANGEMENT_TEMPLATES, 
    SECTION_CONFIGS, 
    GENRE_MOTIF_MAPPINGS,
    SectionType
)

def export_arrangement_templates():
    """Export ARRANGEMENT_TEMPLATES to individual YAML files."""
    for genre, sections in ARRANGEMENT_TEMPLATES.items():
        template = {
            "template_id": genre,
            "display_name": genre.replace("_", " ").title(),
            "genre_ref": genre,
            "version": "1.0.0",
            "sections": [
                {"type": section_type.name.lower(), "bars": bars}
                for section_type, bars in sections
            ]
        }
        
        with open(f"configs/arrangements/templates/{genre}.yaml", "w") as f:
            yaml.dump(template, f, default_flow_style=False, sort_keys=False)

def export_section_configs():
    """Export SECTION_CONFIGS to YAML."""
    configs = {}
    for section_type, config in SECTION_CONFIGS.items():
        configs[section_type.name.lower()] = {
            "typical_bars": config.typical_bars,
            "energy_level": config.energy_level,
            "drum_density": config.drum_density,
            "instrument_density": config.instrument_density,
            "texture_amount": config.texture_amount,
            "filter_cutoff": config.filter_cutoff,
            "enable_drums": config.enable_drums,
            "enable_bass": config.enable_bass,
            "enable_melody": config.enable_melody,
            "enable_pads": config.enable_pads,
            "enable_fx": config.enable_fx,
        }
    
    with open("configs/arrangements/section_configs/default_sections.yaml", "w") as f:
        yaml.dump(configs, f, default_flow_style=False)

if __name__ == "__main__":
    export_arrangement_templates()
    export_section_configs()
    print("Export complete!")
```

### Phase 5: Testing & Validation

```python
# tests/test_config_migration.py
"""Ensure config-driven behavior matches hardcoded behavior."""

import pytest
from multimodal_gen.arranger import Arranger, ARRANGEMENT_TEMPLATES
from multimodal_gen.config_loader import ConfigLoader

class TestConfigMigration:
    
    def test_template_equivalence(self):
        """Verify loaded templates match hardcoded templates."""
        loader = ConfigLoader()
        arranger = Arranger(config_loader=loader)
        
        for genre, expected_sections in ARRANGEMENT_TEMPLATES.items():
            loaded = arranger._get_template(genre)
            assert loaded == expected_sections, f"Mismatch for {genre}"
    
    def test_section_config_equivalence(self):
        """Verify section configs match."""
        from multimodal_gen.arranger import SECTION_CONFIGS
        
        loader = ConfigLoader()
        loaded_configs = loader.load_section_configs("default_sections")
        
        for section_type, expected in SECTION_CONFIGS.items():
            loaded = loaded_configs[section_type.name.lower()]
            assert loaded["energy_level"] == expected.energy_level
            assert loaded["drum_density"] == expected.drum_density
    
    def test_arrangement_output_equivalence(self):
        """Full integration test: same inputs should produce same outputs."""
        # Test with both old and new implementations
        pass
```

### Phase 6: Gradual Rollout

1. **Feature flag** to switch between hardcoded and config-driven
2. **Shadow mode**: Run both, compare outputs, log differences
3. **A/B testing**: Some generations use configs, measure quality
4. **Full cutover**: Remove hardcoded data, configs become source of truth

```python
# Feature flag implementation
import os

USE_CONFIG_DRIVEN = os.getenv("USE_CONFIG_DRIVEN", "false").lower() == "true"

class Arranger:
    def _get_template(self, genre: str):
        if USE_CONFIG_DRIVEN:
            return self._get_template_from_config(genre)
        else:
            return ARRANGEMENT_TEMPLATES.get(genre, ARRANGEMENT_TEMPLATES["trap"])
```

---

## Summary & Recommendations

### Key Takeaways

1. **MusicXML and MIDI** provide established patterns for representing musical structure in data formats - use their concepts (markers, sections, time signatures) in schema design.

2. **Band-in-a-Box's "Style" concept** aligns perfectly with RLM's needs - encapsulating patterns, instrumentation rules, and arrangement behaviors in a single named entity.

3. **Declarative is clearly superior** for arrangement templates - enables user customization, hot-reloading, and easier testing.

4. **The existing genres.json** is a strong foundation - extend it rather than replace it.

5. **Alda and Sonic Pi** demonstrate that even complex musical logic can be expressed declaratively with the right abstractions.

### Recommended Next Steps

1. **Create the JSON schemas** first - they serve as documentation and validation
2. **Export current hardcoded data** to YAML as a baseline
3. **Implement ConfigLoader** with caching and hot-reload
4. **Refactor Arranger** to use ConfigLoader while maintaining backward compatibility
5. **Add comprehensive tests** ensuring behavioral equivalence
6. **Deploy with feature flag** for safe rollout

### Estimated Effort

| Phase | Effort | Priority |
|-------|--------|----------|
| Schema Definition | 2-3 days | P0 |
| Export Script | 1 day | P0 |
| ConfigLoader | 2-3 days | P0 |
| Arranger Refactoring | 3-5 days | P1 |
| Testing Suite | 2-3 days | P1 |
| Documentation | 1-2 days | P2 |

**Total: ~2-3 weeks for full migration**
