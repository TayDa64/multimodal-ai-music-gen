# Plugin Architectures for Musical Instruments
## Research Report for Multimodal AI Music Generator

**Date:** January 20, 2026  
**Purpose:** Design modular, hot-reloadable Ethiopian instrument plugins

---

## Table of Contents

1. [VST/AU Plugin Architecture](#1-vstau-plugin-architecture)
2. [Python Plugin Systems](#2-python-plugin-systems)
3. [Professional Synthesizer Instrument Loading](#3-professional-synthesizer-instrument-loading)
4. [SoundFont (.sf2) Architecture](#4-soundfont-sf2-architecture)
5. [Kontakt/Native Instruments Architecture](#5-kontaktnative-instruments-architecture)
6. [Recommendations for Ethiopian Instruments](#6-recommendations-for-ethiopian-instruments)

---

## 1. VST/AU Plugin Architecture

### Overview

Virtual Studio Technology (VST) is the dominant audio plugin standard, created by Steinberg in 1996. As of VST 3.8.0 (October 2025), it's now open source under MIT license.

### Core Architecture Patterns

```
┌─────────────────────────────────────────────────────────┐
│                      VST HOST (DAW)                      │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │   Plugin    │  │   Plugin    │  │   Plugin    │     │
│  │  Instance   │  │  Instance   │  │  Instance   │     │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘     │
│         │                │                │             │
│  ┌──────┴────────────────┴────────────────┴──────┐     │
│  │              Plugin Interface API              │     │
│  │  • IComponent (audio processing)               │     │
│  │  • IEditController (UI/parameters)             │     │
│  │  • IAudioProcessor (DSP)                       │     │
│  └───────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────┘
```

### Key Design Patterns

1. **Component-Based Architecture**
   - Separation of concerns: Audio processing vs UI vs parameters
   - `IComponent`: Core audio processing logic
   - `IEditController`: Parameter management and UI
   - Factory pattern for creating instances

2. **Dynamic Loading**
   - Plugins are DLLs (.dll/.vst3 on Windows, .component/.vst3 on macOS)
   - Host scans plugin directories at startup
   - Lazy loading: Only load when needed

3. **Parameter Model**
   ```cpp
   // VST3-style parameter definition
   struct ParameterInfo {
       ParamID id;           // Unique identifier
       String title;         // Display name
       String units;         // "Hz", "dB", "%"
       ParamValue defaultValue;
       int32 flags;          // Read-only, automatable, etc.
   };
   ```

4. **State Persistence**
   - Presets stored as FXP (single) or FXB (bank) files
   - Binary serialization of parameter states
   - Version compatibility management

### Competing Standards

| Standard | Platform | License | Notes |
|----------|----------|---------|-------|
| VST3 | Cross-platform | MIT (as of 2025) | Most widely used |
| Audio Units (AU) | macOS/iOS | Apple proprietary | Required for Logic Pro |
| AAX | Pro Tools | Avid proprietary | Requires PACE signing |
| LV2 | Linux | Open source | FOSS alternative |
| CLAP | Cross-platform | MIT | Modern open alternative |

### Relevance for Our Project

- **Interface contract pattern**: Define clear `InstrumentPlugin` interface
- **Factory pattern**: Create instruments on demand
- **Parameter model**: Standardize instrument configuration
- **Dynamic loading**: Enable hot-reload of instruments

---

## 2. Python Plugin Systems

### 2.1 Entry Points (setuptools/importlib.metadata)

The standard Python mechanism for plugin discovery.

```python
# pyproject.toml - Plugin definition
[project.entry-points."aimusic.instruments"]
krar = "ethiopian_instruments.krar:KrarInstrument"
masenqo = "ethiopian_instruments.masenqo:MasenqoInstrument"
washint = "ethiopian_instruments.washint:WashintInstrument"
```

```python
# Host application - Plugin discovery
from importlib.metadata import entry_points

def discover_instruments():
    """Discover all installed instrument plugins."""
    eps = entry_points(group='aimusic.instruments')
    instruments = {}
    for ep in eps:
        try:
            instrument_class = ep.load()
            instruments[ep.name] = instrument_class
        except Exception as e:
            print(f"Failed to load {ep.name}: {e}")
    return instruments
```

**Pros:**
- Standard Python mechanism
- Works with pip install
- Namespace isolation

**Cons:**
- Requires package installation
- No hot-reload without reimport

### 2.2 Pluggy (pytest's plugin system)

The hook-based plugin system used by pytest, tox, and others.

```python
import pluggy

# Define hook specifications (interface contract)
hookspec = pluggy.HookspecMarker("aimusic")
hookimpl = pluggy.HookimplMarker("aimusic")

class InstrumentSpec:
    """Hook specifications for instrument plugins."""
    
    @hookspec
    def get_instrument_info(self) -> dict:
        """Return instrument metadata."""
    
    @hookspec
    def generate_tone(self, frequency: float, duration: float, 
                      velocity: float) -> np.ndarray:
        """Generate audio for a single note."""
    
    @hookspec
    def get_articulations(self) -> list:
        """Return supported articulations."""

# Plugin implementation
class KrarPlugin:
    """Krar instrument plugin."""
    
    @hookimpl
    def get_instrument_info(self):
        return {
            "name": "Krar",
            "category": "ethiopian_string",
            "midi_program": 110,
            "range": {"low": 48, "high": 84}
        }
    
    @hookimpl
    def generate_tone(self, frequency, duration, velocity):
        return generate_krar_tone(frequency, duration, velocity)

# Host usage
pm = pluggy.PluginManager("aimusic")
pm.add_hookspecs(InstrumentSpec)
pm.register(KrarPlugin())

# Call all implementations
results = pm.hook.generate_tone(frequency=440, duration=1.0, velocity=0.8)
```

**Pros:**
- Powerful hook system
- Supports wrappers and ordering
- Battle-tested (1400+ pytest plugins)

**Cons:**
- Additional dependency
- Slightly more complex API

### 2.3 Stevedore (OpenStack's plugin manager)

Higher-level abstraction over entry points with multiple loading strategies.

```python
from stevedore import driver, extension, named

# Load a single driver by name
mgr = driver.DriverManager(
    namespace='aimusic.instruments',
    name='krar',
    invoke_on_load=True,
)
krar = mgr.driver

# Load all extensions
mgr = extension.ExtensionManager(
    namespace='aimusic.instruments',
    invoke_on_load=True,
    on_load_failure_callback=lambda mgr, ep, err: print(f"Failed: {ep}")
)

# Use extensions
for ext in mgr:
    tone = ext.obj.generate_tone(440, 1.0, 0.8)
```

**Loading Patterns:**

| Manager | Use Case |
|---------|----------|
| `DriverManager` | Single plugin by name |
| `ExtensionManager` | All plugins in namespace |
| `NamedExtensionManager` | Specific plugins by name list |
| `EnabledExtensionManager` | Plugins with enable check |
| `HookManager` | Call same method on all plugins |
| `DispatchExtensionManager` | Route to specific plugin by criteria |

### 2.4 Hot-Reload Mechanisms

```python
import importlib
import sys
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class InstrumentReloader(FileSystemEventHandler):
    """Watch instrument modules and reload on change."""
    
    def __init__(self, instrument_manager):
        self.manager = instrument_manager
    
    def on_modified(self, event):
        if event.src_path.endswith('.py'):
            module_name = self._path_to_module(event.src_path)
            self._reload_module(module_name)
    
    def _reload_module(self, module_name):
        """Safely reload a module and update instruments."""
        if module_name in sys.modules:
            # Save old state
            old_module = sys.modules[module_name]
            
            try:
                # Reload
                importlib.reload(old_module)
                
                # Re-register instruments
                self.manager.refresh_instruments()
                
                print(f"✓ Reloaded {module_name}")
            except Exception as e:
                print(f"✗ Reload failed: {e}")
                # Keep old module on failure

# Usage
observer = Observer()
observer.schedule(InstrumentReloader(manager), path='./instruments', recursive=True)
observer.start()
```

---

## 3. Professional Synthesizer Instrument Loading

### Hardware Synthesizer Patterns

Professional synthesizers (Korg, Roland, Yamaha) use these patterns:

```
┌────────────────────────────────────────────────────────┐
│                    SYNTHESIZER ROM                      │
├────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │  WAVE ROM       │  │  PROGRAM/PATCH BANK         │  │
│  │  (PCM Samples)  │  │  • Oscillator routing       │  │
│  │  • Multisamples │  │  • Filter settings          │  │
│  │  • Attack xfade │  │  • Envelope params          │  │
│  │  • Loop points  │  │  • LFO configuration        │  │
│  └─────────────────┘  │  • Velocity curves          │  │
│                       │  • Layer/split points       │  │
│                       └─────────────────────────────┘  │
├────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────┐   │
│  │              SYNTHESIS ENGINE                    │   │
│  │  • Wavetable lookup                              │   │
│  │  • Filter (TVF) processing                       │   │
│  │  • Envelope generators (TVA, TVF, Pitch)         │   │
│  │  • Effects chain                                 │   │
│  └─────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────┘
```

### Korg/Roland Program Structure

```json
{
  "program_name": "Ethiopian Krar",
  "category": "World/Ethnic",
  "oscillators": [
    {
      "type": "pcm",
      "wave_id": 1024,
      "pitch_offset": 0,
      "velocity_sens": 80
    }
  ],
  "filter": {
    "type": "lpf24",
    "cutoff": 8000,
    "resonance": 20,
    "env_depth": 40
  },
  "envelopes": {
    "amp": {"a": 10, "d": 200, "s": 70, "r": 300},
    "filter": {"a": 5, "d": 150, "s": 50, "r": 200}
  },
  "velocity_zones": [
    {"low": 0, "high": 64, "sample": "krar_soft.wav"},
    {"low": 65, "high": 127, "sample": "krar_hard.wav"}
  ]
}
```

---

## 4. SoundFont (.sf2) Architecture

### Overview

SoundFont is a RIFF-based format for sample-based MIDI synthesis, developed by E-mu/Creative Labs.

### File Structure

```
SF2 File Structure
├── INFO-list (metadata)
│   ├── ifil: Version (2.04)
│   ├── isng: Sound engine ("EMU8000")
│   ├── INAM: Bank name
│   └── ...
├── sdta-list (sample data)
│   ├── smpl: 16-bit PCM samples
│   └── sm24: 24-bit extension (2.04)
└── pdta-list (preset data)
    ├── phdr: Preset headers
    ├── pbag: Preset zones
    ├── pmod: Preset modulators
    ├── pgen: Preset generators
    ├── inst: Instruments
    ├── ibag: Instrument zones
    ├── imod: Instrument modulators
    ├── igen: Instrument generators
    └── shdr: Sample headers
```

### Hierarchy

```
┌─────────────────────────────────────────────┐
│                   PRESETS                    │
│  (MIDI Program + Bank → Preset mapping)      │
├─────────────────────────────────────────────┤
│  Preset 0: "Krar"                           │
│  ├── Zone 1: Key 36-60, Vel 0-64            │
│  │   └── → Instrument: "Krar Soft"          │
│  └── Zone 2: Key 36-60, Vel 65-127          │
│      └── → Instrument: "Krar Hard"          │
├─────────────────────────────────────────────┤
│                 INSTRUMENTS                  │
│  (Collections of samples with parameters)    │
├─────────────────────────────────────────────┤
│  Instrument: "Krar Soft"                    │
│  ├── Zone 1: Key 36-48                      │
│  │   └── → Sample: "krar_c2_soft.wav"       │
│  ├── Zone 2: Key 49-60                      │
│  │   └── → Sample: "krar_c3_soft.wav"       │
│  └── Generators: attack=10ms, release=200ms │
├─────────────────────────────────────────────┤
│                  SAMPLES                     │
│  (Raw PCM audio data)                        │
└─────────────────────────────────────────────┘
```

### Generator Parameters (Synthesis Control)

| Generator | Description | Range |
|-----------|-------------|-------|
| startAddrsOffset | Sample start offset | samples |
| endAddrsOffset | Sample end offset | samples |
| startloopAddrsOffset | Loop start | samples |
| endloopAddrsOffset | Loop end | samples |
| pan | Stereo position | -500 to 500 (0.1% units) |
| delayVolEnv | Volume envelope delay | timecents |
| attackVolEnv | Volume envelope attack | timecents |
| holdVolEnv | Volume envelope hold | timecents |
| decayVolEnv | Volume envelope decay | timecents |
| sustainVolEnv | Volume envelope sustain | 0.1% units |
| releaseVolEnv | Volume envelope release | timecents |
| coarseTune | Pitch coarse tune | semitones |
| fineTune | Pitch fine tune | cents |
| scaleTuning | Pitch tracking | cents/key |
| initialFilterFc | Filter cutoff | cents |
| initialFilterQ | Filter resonance | centibels |

### Relevance for Ethiopian Instruments

SoundFont's layered architecture is perfect for:
- **Velocity layers**: Soft/hard krar plucks
- **Key zones**: Different samples per octave
- **Modulators**: Expressive masenqo vibrato
- **Loop points**: Sustained begena drones

---

## 5. Kontakt/Native Instruments Architecture

### Overview

Kontakt is the industry-standard sampler with a proprietary scripting language (KSP - Kontakt Script Processor).

### File Formats

| Extension | Description |
|-----------|-------------|
| .nki | Kontakt Instrument (single patch) |
| .nkm | Kontakt Multi (multiple instruments) |
| .nkc | Kontakt Container (compressed library) |
| .nkx | Kontakt Encrypted Samples |
| .nks | NKS preset (Native Kontrol Standard) |

### Architecture

```
┌───────────────────────────────────────────────────────────┐
│                    KONTAKT ENGINE                          │
├───────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐  │
│  │                  KSP SCRIPT ENGINE                   │  │
│  │  • Real-time scripting                               │  │
│  │  • UI building                                       │  │
│  │  • MIDI transformation                               │  │
│  │  • Sample playback control                           │  │
│  └─────────────────────────────────────────────────────┘  │
├───────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  GROUP 1    │  │  GROUP 2    │  │  GROUP 3    │        │
│  │  (Sustain)  │  │  (Staccato) │  │  (Legato)   │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
│         │                │                │                │
│  ┌──────┴────────────────┴────────────────┴──────┐        │
│  │                    ZONES                       │        │
│  │  Key range + Velocity range → Sample mapping   │        │
│  └───────────────────────────────────────────────┘        │
├───────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐  │
│  │                   SAMPLE POOL                        │  │
│  │  • NCW compression (lossless)                        │  │
│  │  • Streaming from disk                               │  │
│  │  • RAM preload configuration                         │  │
│  └─────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────┘
```

### KSP Scripting Example

```ksp
on init
    declare ui_knob $vibrato_depth (0, 100, 1)
    declare ui_knob $vibrato_speed (1, 10, 1)
    
    set_knob_label($vibrato_depth, "Vibrato")
    set_knob_label($vibrato_speed, "Speed")
    
    make_persistent($vibrato_depth)
    make_persistent($vibrato_speed)
end on

on note
    { Apply Ethiopian-style delayed vibrato }
    wait(500000)  { 500ms delay before vibrato }
    
    while ($NOTE_HELD = 1)
        change_tune($EVENT_ID, $vibrato_depth * 10, 0)
        wait($vibrato_speed * 10000)
        change_tune($EVENT_ID, -$vibrato_depth * 10, 0)
        wait($vibrato_speed * 10000)
    end while
end on
```

### Creator Tools (NI's Development Kit)

Native Instruments provides "Creator Tools" for building Kontakt libraries:
- **Instrument Editor**: Visual zone/group editing
- **Lua Scripting**: Build tools automation
- **NKS Support**: Integration with NI hardware

---

## 6. Recommendations for Ethiopian Instruments

### Proposed Architecture

Based on the research, here's the recommended plugin architecture:

```
multimodal_gen/
├── instruments/
│   ├── __init__.py              # Plugin discovery
│   ├── base.py                  # InstrumentPlugin ABC
│   ├── registry.py              # InstrumentRegistry (runtime)
│   └── loader.py                # Hot-reload support
├── plugins/
│   ├── ethiopian/
│   │   ├── __init__.py
│   │   ├── manifest.json        # Plugin metadata
│   │   ├── krar.py              # Krar plugin
│   │   ├── masenqo.py           # Masenqo plugin
│   │   ├── washint.py           # Washint plugin
│   │   ├── begena.py            # Begena plugin
│   │   ├── kebero.py            # Kebero plugin
│   │   └── samples/             # Optional: real samples
│   │       ├── krar/
│   │       └── masenqo/
│   └── world/
│       ├── manifest.json
│       └── ...
└── config/
    └── instruments.yaml         # Global instrument config
```

### 6.1 Plugin Interface Design

```python
# instruments/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum
import numpy as np

class ArticulationType(Enum):
    SUSTAIN = "sustain"
    STACCATO = "staccato"
    LEGATO = "legato"
    TREMOLO = "tremolo"
    PIZZICATO = "pizzicato"
    HARMONIC = "harmonic"
    
    # Ethiopian-specific
    MELISMA = "melisma"          # Ornamental runs
    YARED_VIBRATO = "yared"      # Orthodox church vibrato
    TIZITA_BEND = "tizita"       # Characteristic scale bends

@dataclass
class InstrumentMetadata:
    """Instrument metadata following SoundFont/Kontakt patterns."""
    id: str                       # Unique identifier
    name: str                     # Display name
    name_amharic: str = ""        # አማርኛ name
    category: str = "world"
    subcategory: str = "ethiopian"
    
    # MIDI mapping
    midi_program: int = 0
    midi_bank: int = 0
    
    # Playable range
    key_range: tuple = (36, 96)   # MIDI note numbers
    velocity_layers: int = 1
    
    # Sonic profile
    brightness: float = 0.5       # For intelligent matching
    warmth: float = 0.5
    attack_character: float = 0.5
    
    # Cultural context
    traditional_tuning: str = ""  # e.g., "tizita", "bati"
    playing_techniques: List[str] = None
    cultural_context: str = ""

class InstrumentPlugin(ABC):
    """Abstract base class for instrument plugins."""
    
    @property
    @abstractmethod
    def metadata(self) -> InstrumentMetadata:
        """Return instrument metadata."""
        pass
    
    @abstractmethod
    def generate_tone(
        self,
        frequency: float,
        duration: float,
        velocity: float = 0.8,
        sample_rate: int = 44100,
        articulation: ArticulationType = ArticulationType.SUSTAIN,
        **kwargs
    ) -> np.ndarray:
        """Generate audio for a single note."""
        pass
    
    def get_articulations(self) -> List[ArticulationType]:
        """Return supported articulations."""
        return [ArticulationType.SUSTAIN]
    
    def get_parameters(self) -> Dict[str, dict]:
        """Return tweakable parameters (like VST parameters)."""
        return {}
    
    def set_parameter(self, name: str, value: float):
        """Set a parameter value."""
        pass
    
    def on_load(self):
        """Called when plugin is loaded (for initialization)."""
        pass
    
    def on_unload(self):
        """Called when plugin is unloaded (for cleanup)."""
        pass
```

### 6.2 Manifest-Driven Configuration

```json
// plugins/ethiopian/manifest.json
{
    "id": "ethiopian-instruments",
    "name": "Ethiopian Traditional Instruments",
    "version": "1.0.0",
    "author": "AI Music Generator Project",
    "description": "Authentic Ethiopian instrument synthesis",
    
    "target_genres": [
        "ethiopian_traditional",
        "eskista",
        "tizita",
        "ethio_jazz"
    ],
    
    "instruments": {
        "krar": {
            "class": "krar.KrarInstrument",
            "metadata": {
                "name": "Krar",
                "name_amharic": "ክራር",
                "midi_program": 110,
                "key_range": [48, 84],
                "category": "plucked_string",
                "traditional_tuning": "tizita",
                "cultural_context": "6-string bowl lyre, primary melodic instrument"
            },
            "parameters": {
                "body_resonance": {"min": 0, "max": 1, "default": 0.7},
                "string_brightness": {"min": 0, "max": 1, "default": 0.6},
                "sympathetic_strings": {"min": 0, "max": 1, "default": 0.3}
            }
        },
        "masenqo": {
            "class": "masenqo.MasenqoInstrument",
            "metadata": {
                "name": "Masenqo",
                "name_amharic": "ማሲንቆ",
                "midi_program": 111,
                "key_range": [48, 72],
                "category": "bowed_string",
                "cultural_context": "Single-string spike fiddle, voice of the azmari"
            },
            "parameters": {
                "bow_pressure": {"min": 0, "max": 1, "default": 0.5},
                "expressiveness": {"min": 0, "max": 1, "default": 0.8},
                "growl": {"min": 0, "max": 1, "default": 0.3}
            }
        }
    },
    
    "instrument_mappings": {
        "violin": ["masenqo"],
        "guitar": ["krar"],
        "harp": ["krar", "begena"],
        "flute": ["washint"],
        "conga": ["kebero"]
    }
}
```

### 6.3 Hot-Reload Implementation

```python
# instruments/loader.py
import importlib
import sys
import json
from pathlib import Path
from typing import Dict, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class InstrumentLoader:
    """Load and hot-reload instrument plugins."""
    
    def __init__(self, plugins_dir: str):
        self.plugins_dir = Path(plugins_dir)
        self.plugins: Dict[str, 'InstrumentPlugin'] = {}
        self.manifests: Dict[str, dict] = {}
        self._observer: Optional[Observer] = None
    
    def scan_plugins(self):
        """Discover all plugins in the plugins directory."""
        for manifest_path in self.plugins_dir.rglob("manifest.json"):
            self._load_plugin_pack(manifest_path)
    
    def _load_plugin_pack(self, manifest_path: Path):
        """Load a plugin pack from its manifest."""
        try:
            with open(manifest_path) as f:
                manifest = json.load(f)
            
            pack_dir = manifest_path.parent
            pack_id = manifest['id']
            
            self.manifests[pack_id] = manifest
            
            # Add to Python path if needed
            if str(pack_dir.parent) not in sys.path:
                sys.path.insert(0, str(pack_dir.parent))
            
            # Load each instrument
            for inst_id, inst_config in manifest.get('instruments', {}).items():
                self._load_instrument(pack_dir, inst_id, inst_config)
                
        except Exception as e:
            print(f"Failed to load plugin pack {manifest_path}: {e}")
    
    def _load_instrument(self, pack_dir: Path, inst_id: str, config: dict):
        """Load a single instrument from configuration."""
        try:
            module_path, class_name = config['class'].rsplit('.', 1)
            
            # Import the module
            module_name = f"{pack_dir.name}.{module_path}"
            module = importlib.import_module(module_name)
            
            # Get the class
            instrument_class = getattr(module, class_name)
            
            # Instantiate with metadata
            metadata = config.get('metadata', {})
            instrument = instrument_class(**metadata)
            
            # Call load hook
            instrument.on_load()
            
            # Register
            self.plugins[inst_id] = instrument
            print(f"  ✓ Loaded: {inst_id}")
            
        except Exception as e:
            print(f"  ✗ Failed to load {inst_id}: {e}")
    
    def enable_hot_reload(self):
        """Enable file watching for hot-reload."""
        handler = _ReloadHandler(self)
        self._observer = Observer()
        self._observer.schedule(handler, str(self.plugins_dir), recursive=True)
        self._observer.start()
        print("Hot-reload enabled")
    
    def disable_hot_reload(self):
        """Disable hot-reload."""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
    
    def reload_plugin(self, plugin_id: str):
        """Reload a specific plugin."""
        if plugin_id in self.plugins:
            old_plugin = self.plugins[plugin_id]
            old_plugin.on_unload()
            
            # Find and reload
            for pack_id, manifest in self.manifests.items():
                if plugin_id in manifest.get('instruments', {}):
                    config = manifest['instruments'][plugin_id]
                    module_path = config['class'].rsplit('.', 1)[0]
                    
                    # Reload module
                    module_name = f"{pack_id}.{module_path}"
                    if module_name in sys.modules:
                        importlib.reload(sys.modules[module_name])
                    
                    # Reload instrument
                    pack_dir = Path(manifest.get('_path', '')).parent
                    self._load_instrument(pack_dir, plugin_id, config)
                    break
    
    def get_plugin(self, name: str) -> Optional['InstrumentPlugin']:
        """Get a plugin by name."""
        return self.plugins.get(name)
    
    def list_plugins(self) -> Dict[str, dict]:
        """List all loaded plugins with metadata."""
        return {
            name: plugin.metadata.__dict__
            for name, plugin in self.plugins.items()
        }

class _ReloadHandler(FileSystemEventHandler):
    """Handle file changes for hot-reload."""
    
    def __init__(self, loader: InstrumentLoader):
        self.loader = loader
    
    def on_modified(self, event):
        if event.src_path.endswith('.py'):
            # Find which plugin this file belongs to
            path = Path(event.src_path)
            for pack_id, manifest in self.loader.manifests.items():
                for inst_id, config in manifest.get('instruments', {}).items():
                    if config['class'].split('.')[0] in path.stem:
                        print(f"🔄 Reloading {inst_id}...")
                        self.loader.reload_plugin(inst_id)
                        break
```

### 6.4 Ethiopian Instrument Plugin Example

```python
# plugins/ethiopian/krar.py
import numpy as np
from instruments.base import InstrumentPlugin, InstrumentMetadata, ArticulationType

class KrarInstrument(InstrumentPlugin):
    """
    Krar (ክራር) - Ethiopian 6-string bowl lyre.
    
    Physical modeling using Karplus-Strong algorithm with:
    - Goatskin body resonance
    - Nylon/gut string characteristics  
    - Sympathetic string coupling
    """
    
    def __init__(self, **kwargs):
        self._metadata = InstrumentMetadata(
            id="krar",
            name="Krar",
            name_amharic="ክራር",
            category="plucked_string",
            subcategory="ethiopian",
            midi_program=110,
            key_range=(48, 84),
            brightness=0.7,
            warmth=0.5,
            attack_character=0.8,
            traditional_tuning="tizita",
            playing_techniques=["pluck", "strum", "mute"],
            cultural_context="Primary melodic instrument of Ethiopian secular music"
        )
        
        # Tweakable parameters
        self.body_resonance = kwargs.get('body_resonance', 0.7)
        self.string_brightness = kwargs.get('string_brightness', 0.6)
        self.sympathetic_strings = kwargs.get('sympathetic_strings', 0.3)
    
    @property
    def metadata(self) -> InstrumentMetadata:
        return self._metadata
    
    def generate_tone(
        self,
        frequency: float,
        duration: float,
        velocity: float = 0.8,
        sample_rate: int = 44100,
        articulation: ArticulationType = ArticulationType.SUSTAIN,
        **kwargs
    ) -> np.ndarray:
        """Generate Krar tone using Karplus-Strong with body resonance."""
        
        n_samples = int(duration * sample_rate)
        
        # Karplus-Strong parameters
        period = int(sample_rate / frequency)
        
        # Initialize with noise burst (pluck excitation)
        noise = np.random.uniform(-1, 1, period)
        
        # Apply pluck shaping
        noise *= np.linspace(1, 0.3, period) ** 0.5
        
        # Velocity affects brightness
        brightness = self.string_brightness * (0.5 + 0.5 * velocity)
        
        # Karplus-Strong synthesis
        output = np.zeros(n_samples)
        buffer = noise.copy()
        
        for i in range(n_samples):
            output[i] = buffer[i % period]
            
            # Feedback with lowpass (string damping)
            if i >= period:
                # Two-point average with brightness control
                buffer[i % period] = (
                    brightness * output[i - period] + 
                    (1 - brightness) * output[i - period + 1]
                ) * 0.996  # Decay factor
        
        # Add body resonance (formants)
        output = self._add_body_resonance(output, sample_rate)
        
        # Add sympathetic strings
        if self.sympathetic_strings > 0:
            output = self._add_sympathetic(output, frequency, sample_rate)
        
        # Apply velocity
        output *= velocity
        
        # Normalize
        max_val = np.max(np.abs(output))
        if max_val > 0:
            output /= max_val
        
        return output
    
    def _add_body_resonance(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Add goatskin membrane body resonance."""
        # Formant frequencies for bowl lyre body
        formants = [
            (150, 0.5, 50),   # Low body resonance
            (400, 0.7, 80),   # Main body
            (800, 0.3, 100),  # Brightness
        ]
        
        resonated = audio.copy()
        
        for freq, gain, q in formants:
            # Simple resonant filter
            resonated = self._apply_resonance(resonated, freq, q, gain * self.body_resonance, sr)
        
        return audio * 0.7 + resonated * 0.3
    
    def _add_sympathetic(self, audio: np.ndarray, base_freq: float, sr: int) -> np.ndarray:
        """Add sympathetic string resonance (other strings ringing)."""
        # Sympathetic frequencies (perfect 5th, octave)
        sympathetic_freqs = [base_freq * 1.5, base_freq * 2.0]
        
        sympathetic = np.zeros_like(audio)
        for freq in sympathetic_freqs:
            # Generate quiet sympathetic tone
            t = np.arange(len(audio)) / sr
            tone = np.sin(2 * np.pi * freq * t) * 0.05
            tone *= np.exp(-t * 3)  # Quick decay
            sympathetic += tone
        
        return audio + sympathetic * self.sympathetic_strings
    
    def _apply_resonance(self, audio, freq, q, gain, sr):
        """Apply resonant bandpass filter."""
        # Simplified biquad resonance
        omega = 2 * np.pi * freq / sr
        alpha = np.sin(omega) / (2 * q)
        
        b0 = alpha
        b1 = 0
        b2 = -alpha
        a0 = 1 + alpha
        a1 = -2 * np.cos(omega)
        a2 = 1 - alpha
        
        # Normalize
        b = [b0/a0, b1/a0, b2/a0]
        a = [1, a1/a0, a2/a0]
        
        # Apply filter (scipy.signal.lfilter equivalent)
        output = np.zeros_like(audio)
        x1, x2, y1, y2 = 0, 0, 0, 0
        
        for i, x in enumerate(audio):
            y = b[0]*x + b[1]*x1 + b[2]*x2 - a[1]*y1 - a[2]*y2
            output[i] = y
            x2, x1 = x1, x
            y2, y1 = y1, y
        
        return output * gain
    
    def get_articulations(self):
        return [
            ArticulationType.SUSTAIN,
            ArticulationType.STACCATO,
            ArticulationType.TREMOLO,
        ]
    
    def get_parameters(self):
        return {
            "body_resonance": {
                "min": 0, "max": 1, "default": 0.7,
                "description": "Goatskin body resonance amount"
            },
            "string_brightness": {
                "min": 0, "max": 1, "default": 0.6,
                "description": "String brightness/darkness"
            },
            "sympathetic_strings": {
                "min": 0, "max": 1, "default": 0.3,
                "description": "Sympathetic string resonance"
            }
        }
    
    def set_parameter(self, name: str, value: float):
        if hasattr(self, name):
            setattr(self, name, np.clip(value, 0, 1))
```

### 6.5 Integration with Existing System

```python
# Integrate with expansion_manager.py

from instruments.loader import InstrumentLoader
from instruments.base import InstrumentPlugin

class ExpansionManager:
    """Extended to support instrument plugins."""
    
    def __init__(self, ...):
        # Existing initialization
        ...
        
        # Add plugin support
        self.instrument_loader = InstrumentLoader(
            plugins_dir=str(Path(__file__).parent / "plugins")
        )
        self.instrument_loader.scan_plugins()
    
    def resolve_instrument(self, requested: str, genre: str = "", ...):
        """Extended resolution with plugin fallback."""
        
        # First check plugins (highest priority for synthesized instruments)
        plugin = self.instrument_loader.get_plugin(requested.lower())
        if plugin:
            return ResolvedInstrument(
                path="",  # No file path - synthesized
                name=plugin.metadata.name,
                source="plugin:" + plugin.metadata.id,
                match_type=MatchType.EXACT,
                confidence=1.0,
                requested=requested,
                genre=genre,
                plugin=plugin  # Include reference
            )
        
        # Fall back to existing expansion resolution
        return self.matcher.resolve(requested, genre, ...)
    
    def generate_instrument_audio(
        self,
        resolved: ResolvedInstrument,
        frequency: float,
        duration: float,
        velocity: float = 0.8,
        **kwargs
    ) -> np.ndarray:
        """Generate audio from resolved instrument."""
        
        if resolved.source.startswith("plugin:"):
            # Use plugin synthesis
            plugin = resolved.plugin
            return plugin.generate_tone(frequency, duration, velocity, **kwargs)
        else:
            # Load from file (existing behavior)
            return self._load_audio_file(resolved.path)
```

---

## Summary: Key Takeaways

### Design Patterns to Adopt

| Pattern | Source | Application |
|---------|--------|-------------|
| **Component Interface** | VST3 | `InstrumentPlugin` abstract base class |
| **Hook System** | pluggy | Extensible articulation/effect hooks |
| **Entry Points** | setuptools | Pip-installable instrument packages |
| **Manifest Files** | SoundFont/Kontakt | JSON configuration for instruments |
| **Velocity Layers** | All formats | Multi-sample support per instrument |
| **Parameter Model** | VST3 | Tweakable instrument parameters |
| **Hot-Reload** | watchdog | Development-time auto-refresh |

### Implementation Priority

1. **Phase 1 - Core**: `InstrumentPlugin` base class + `InstrumentLoader`
2. **Phase 2 - Ethiopian**: Migrate krar/masenqo/washint/begena/kebero to plugins
3. **Phase 3 - Manifest**: Add JSON manifest support with parameters
4. **Phase 4 - Hot-Reload**: File watching for development
5. **Phase 5 - Samples**: Optional real sample integration (hybrid)

### File Structure Mapping

| Current Location | New Plugin Location |
|------------------|---------------------|
| `assets_gen.py::generate_krar_tone()` | `plugins/ethiopian/krar.py::KrarInstrument` |
| `assets_gen.py::generate_masenqo_tone()` | `plugins/ethiopian/masenqo.py::MasenqoInstrument` |
| `assets_gen.py::generate_washint_tone()` | `plugins/ethiopian/washint.py::WashintInstrument` |
| `assets_gen.py::generate_begena_tone()` | `plugins/ethiopian/begena.py::BegenaInstrument` |
| `assets_gen.py::generate_kebero_hit()` | `plugins/ethiopian/kebero.py::KeberoInstrument` |

---

## References

1. VST 3 SDK Documentation - https://steinbergmedia.github.io/vst3_dev_portal/
2. pluggy Documentation - https://pluggy.readthedocs.io/
3. stevedore Documentation - https://docs.openstack.org/stevedore/
4. setuptools Entry Points - https://setuptools.pypa.io/en/latest/userguide/entry_point.html
5. SoundFont 2.04 Specification - http://www.synthfont.com/sfspec24.pdf
6. SFZ Format - https://sfzformat.com/
7. Kontakt Scripting Reference - Native Instruments Documentation
8. JUCE Framework - https://github.com/juce-framework/JUCE
9. watchdog Documentation - https://watchdog.readthedocs.io/
