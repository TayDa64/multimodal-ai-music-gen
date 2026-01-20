# Synthesizer Abstraction Layer Research

> **Research Document**: How DAWs and audio libraries abstract multiple synthesis backends
> 
> **Date**: January 2025  
> **Context**: Multimodal AI Music Generator - Audio Renderer Redesign

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Industry Patterns Analysis](#industry-patterns-analysis)
   - [Web Audio Libraries (Tone.js, MIDI.js)](#web-audio-libraries)
   - [Python Audio Libraries (SuperCollider, Csound, pyo)](#python-audio-libraries)
   - [DAW Plugin Architectures (VST3, CLAP, JUCE)](#daw-plugin-architectures)
3. [Design Patterns for Synthesizer Selection](#design-patterns)
4. [Abstract Synthesizer Interface Design](#abstract-synthesizer-interface)
5. [Backend Registration & Selection Patterns](#backend-registration)
6. [Unified API for FluidSynth, Procedural, and Samples](#unified-api)
7. [Migration Strategy for audio_renderer.py](#migration-strategy)
8. [Recommendations](#recommendations)

---

## Executive Summary

This research examines how professional audio software abstracts multiple synthesis backends to inform the redesign of `audio_renderer.py`. Key findings:

1. **Successful abstractions share common patterns**: Unified `play()`/`trigger()` interfaces, lazy loading, capability detection, and graceful fallback chains.

2. **Factory + Strategy patterns dominate**: The Factory pattern handles backend instantiation, while Strategy allows runtime switching between synthesis methods.

3. **Extensions > Inheritance**: Modern audio APIs (CLAP, Tone.js) favor composition with optional extensions over deep inheritance hierarchies.

4. **The existing `StemSeparator` pattern is excellent**: The codebase already uses ABC + registration pattern in `stem_separation.py` - this should be the template for synthesizer abstraction.

---

## Industry Patterns Analysis

### Web Audio Libraries

#### Tone.js Architecture

Tone.js demonstrates an exemplary unified interface across synthesis methods:

```javascript
// Both Synth and Sampler use identical note-playing API
const synth = new Tone.Synth().toDestination();
const sampler = new Tone.Sampler({
    urls: { C4: "C4.mp3" }
}).toDestination();

// Unified playback interface - works for BOTH
synth.triggerAttackRelease("C4", "8n");
sampler.triggerAttackRelease("C4", "8n");
```

**Key Abstractions:**

| Concept | Implementation | Purpose |
|---------|---------------|---------|
| `Source` | Base class | All sound-generating nodes |
| `Instrument` | Extends Source | Musical instruments (Synth, Sampler, etc.) |
| `triggerAttack/Release` | Unified method | Note on/off across all instruments |
| `toDestination()` | Chaining | Audio routing abstraction |
| `Transport` | Global clock | Timing synchronization |

**Lessons for Our Design:**
- Unified `note_on()`/`note_off()` or `render_note()` interface
- All backends implement same abstract interface
- Timing handled separately from synthesis

#### MIDI.js Architecture

MIDI.js uses a simpler plugin-based approach:

```javascript
MIDI.loadPlugin({
    soundfontUrl: "./soundfont/",
    instrument: "acoustic_grand_piano",
    onprogress: function(state, progress) { },
    onsuccess: function() {
        MIDI.noteOn(0, pitch, velocity, delay);
        MIDI.noteOff(0, pitch, delay + 0.75);
    }
});
```

**Key Pattern**: Separation of loading (plugin) from playback (noteOn/Off).

---

### Python Audio Libraries

#### SuperCollider Client/Server Architecture

SuperCollider's most important innovation is **decoupling the language from the audio engine**:

```
┌─────────────────────┐     OSC Messages     ┌─────────────────────┐
│   sclang (Client)   │ ─────────────────────▶│   scsynth (Server)  │
│  (Interpreted Lang) │                       │  (Real-time Audio)  │
└─────────────────────┘                       └─────────────────────┘
         │                                              │
         │                                              │
    ┌────▼────┐                                   ┌─────▼─────┐
    │ Python  │    FoxDot, supriya, etc.          │   UGens   │
    │ Clojure │    (Alternative Clients)          │ (Synthesis)│
    │ etc.    │                                   └───────────┘
    └─────────┘
```

**Key Insight**: Multiple clients can control the same synthesis backend. This is the **Strategy pattern** at the protocol level.

**OSC Message Examples:**
```
/s_new "default" -1 0 0 "freq" 440  # Create synth node
/n_set 1001 "freq" 880              # Set parameter
/n_free 1001                         # Free synth
```

**Lessons:**
- Consider message-based abstraction layer
- Backends should be completely isolated processes/modules
- Parameters passed as key-value pairs

#### Csound Architecture

Csound uses an **opcode abstraction** where synthesis algorithms are building blocks:

```csound
; Both SoundFont and procedural use same output routing
aSig oscil 0.5, 440, 1         ; Procedural oscillator
aSF  sfplay p4, p5, 1, 1, giSF ; SoundFont playback
      outs aSig + aSF, aSig + aSF
```

**Key Features:**
- `sfload`/`sfplay` opcodes for SoundFont
- `oscil`, `vco2`, `poscil` for procedural
- All produce same signal type (`a-rate` audio)

**Lesson**: Output type standardization enables mixing backends freely.

---

### DAW Plugin Architectures

#### VST3 Component Model

VST3 separates processing from UI:

```
┌─────────────────────────────────────────────┐
│                 VST3 Plugin                  │
├──────────────────────┬──────────────────────┤
│    AudioProcessor    │      Controller      │
│  (Real-time Audio)   │   (Parameters/UI)    │
├──────────────────────┴──────────────────────┤
│              IPluginFactory                  │
│         (Creates both components)            │
└─────────────────────────────────────────────┘
```

**Factory Pattern in VST3:**
```cpp
class PluginFactory : public IPluginFactory {
    tresult createInstance(TUID cid, TUID iid, void** obj) {
        if (cid == ProcessorUID)
            *obj = new MyProcessor();
        else if (cid == ControllerUID)
            *obj = new MyController();
        return kResultOk;
    }
};
```

#### CLAP Extension Model

CLAP (CLever Audio Plugin) uses **optional extensions** rather than inheritance:

```c
// Host queries plugin for optional capabilities
const void* get_extension(const clap_plugin_t* plugin, const char* id) {
    if (!strcmp(id, CLAP_EXT_STATE))
        return &my_state_extension;
    if (!strcmp(id, CLAP_EXT_PARAMS))
        return &my_params_extension;
    return NULL;  // Don't support this extension
}
```

**Key Extensions:**
- `CLAP_EXT_AUDIO_PORTS` - Audio I/O capabilities
- `CLAP_EXT_PARAMS` - Parameter handling
- `CLAP_EXT_STATE` - State save/load
- `CLAP_EXT_RENDER` - Rendering mode control

**Lesson**: Optional capabilities via `get_capability()` method rather than requiring all backends implement everything.

#### JUCE Cross-Platform Abstraction

JUCE wraps all plugin formats (VST/VST3/AU/AAX/LV2) in one interface:

```cpp
class MyPlugin : public juce::AudioProcessor {
    void prepareToPlay(double sampleRate, int samplesPerBlock) override;
    void processBlock(juce::AudioBuffer<float>&, juce::MidiBuffer&) override;
    void releaseResources() override;
};
```

**One codebase compiles to all formats** - this is exactly what we want for synthesis backends.

---

## Design Patterns

### Factory Method Pattern

**Intent**: Define an interface for creating objects, but let subclasses decide which class to instantiate.

```
┌─────────────────────┐
│       Creator       │
│  ───────────────    │
│ +factoryMethod()    │◇───────▶ Product interface
│ +someOperation()    │
└─────────┬───────────┘
          │
          │ extends
          ▼
┌─────────────────────┐         ┌─────────────────────┐
│   ConcreteCreator   │         │   ConcreteProduct   │
│  ───────────────    │────────▶│                     │
│ +factoryMethod()    │ creates │                     │
└─────────────────────┘         └─────────────────────┘
```

**Application to Synthesizers:**

```python
class SynthesizerFactory:
    """Factory method pattern for synthesizer creation."""
    
    @abstractmethod
    def create_synthesizer(self, config: dict) -> "BaseSynthesizer":
        """Subclasses override to create specific synthesizer types."""
        pass

class FluidSynthFactory(SynthesizerFactory):
    def create_synthesizer(self, config: dict) -> "FluidSynthBackend":
        return FluidSynthBackend(
            soundfont_path=config.get("soundfont"),
            sample_rate=config.get("sample_rate", 44100)
        )

class ProceduralFactory(SynthesizerFactory):
    def create_synthesizer(self, config: dict) -> "ProceduralBackend":
        return ProceduralBackend(
            sample_rate=config.get("sample_rate", 44100),
            genre=config.get("genre")
        )
```

### Abstract Factory Pattern

**Intent**: Create families of related objects without specifying concrete classes.

Better for our use case because we need:
- Synthesizer + its compatible effects chain
- Synthesizer + its parameter mapping
- Backend + its capability set

```python
class SynthesizerFamily(ABC):
    """Abstract factory for related synthesis components."""
    
    @abstractmethod
    def create_synthesizer(self) -> "BaseSynthesizer": pass
    
    @abstractmethod
    def create_effect_chain(self) -> "EffectChain": pass
    
    @abstractmethod
    def create_parameter_mapper(self) -> "ParameterMapper": pass

class FluidSynthFamily(SynthesizerFamily):
    def create_synthesizer(self):
        return FluidSynthBackend(...)
    
    def create_effect_chain(self):
        return StandardEffectChain()  # FluidSynth has built-in reverb/chorus
    
    def create_parameter_mapper(self):
        return MidiCCMapper()  # Maps MIDI CC to FluidSynth params
```

### Strategy Pattern (Recommended Primary Pattern)

**Intent**: Define a family of algorithms, encapsulate each one, and make them interchangeable.

This is what `stem_separation.py` already uses and should be the primary pattern:

```python
class SynthesizerContext:
    """Context that uses a synthesis strategy."""
    
    def __init__(self, strategy: "BaseSynthesizer"):
        self._strategy = strategy
    
    def set_strategy(self, strategy: "BaseSynthesizer"):
        """Switch synthesis backend at runtime."""
        self._strategy = strategy
    
    def render_note(self, note: SynthNote) -> np.ndarray:
        return self._strategy.render_note(note)
```

---

## Abstract Synthesizer Interface Design

Based on the research, here is the proposed interface:

### Core Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Optional, Set
import numpy as np


class SynthesizerCapability(Enum):
    """Optional capabilities a synthesizer backend may support."""
    SOUNDFONT = auto()          # Can load .sf2/.sf3 files
    SAMPLE_PLAYBACK = auto()    # Can play audio samples
    PROCEDURAL = auto()         # Generates audio mathematically
    REALTIME = auto()           # Supports real-time streaming
    OFFLINE = auto()            # Supports offline rendering
    EFFECTS_BUILTIN = auto()    # Has built-in effects (reverb, etc.)
    MIDI_CC = auto()            # Supports MIDI CC automation
    POLYPHONY = auto()          # Supports multiple simultaneous notes
    VELOCITY_LAYERS = auto()    # Supports velocity-switched samples
    ROUND_ROBIN = auto()        # Supports round-robin sample variation


@dataclass
class SynthNote:
    """Unified note representation for all backends."""
    pitch: int                   # MIDI note number (0-127)
    start_sample: int            # Start position in samples
    duration_samples: int        # Note length in samples
    velocity: float              # Normalized velocity (0.0-1.0)
    channel: int = 0             # MIDI channel
    program: int = 0             # MIDI program number
    bank: int = 0                # MIDI bank number
    pan: float = 0.0             # Stereo pan (-1.0 to 1.0)
    expression: float = 1.0      # Expression controller (0.0-1.0)


@dataclass
class SynthesizerConfig:
    """Configuration for synthesizer initialization."""
    sample_rate: int = 44100
    channels: int = 2
    buffer_size: int = 512
    soundfont_path: Optional[str] = None
    samples_dir: Optional[str] = None
    genre: Optional[str] = None
    mood: Optional[str] = None


class BaseSynthesizer(ABC):
    """
    Abstract base class for all synthesis backends.
    
    All backends must implement:
    - render_note(): Synthesize a single note
    - is_available(): Check if backend is usable
    - capabilities: Report supported features
    
    Modeled after the StemSeparator pattern in stem_separation.py
    and Tone.js unified instrument interface.
    """
    
    def __init__(self, config: SynthesizerConfig):
        self.config = config
        self.sample_rate = config.sample_rate
    
    # =========================================================================
    # ABSTRACT METHODS (Required)
    # =========================================================================
    
    @abstractmethod
    def render_note(self, note: SynthNote) -> np.ndarray:
        """
        Render a single note to audio.
        
        Args:
            note: SynthNote with pitch, timing, velocity, etc.
        
        Returns:
            Stereo audio array of shape (samples, 2) or mono (samples,)
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this backend is installed and usable.
        
        Returns:
            True if all dependencies are satisfied.
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the backend name for logging."""
        pass
    
    @property
    @abstractmethod
    def capabilities(self) -> Set[SynthesizerCapability]:
        """Return set of supported capabilities."""
        pass
    
    # =========================================================================
    # OPTIONAL METHODS (Override if supported)
    # =========================================================================
    
    def render_notes(self, notes: List[SynthNote], duration_samples: int) -> np.ndarray:
        """
        Render multiple notes, mixed together.
        
        Default implementation renders individually and mixes.
        Override for backends with native polyphony.
        
        Args:
            notes: List of SynthNotes to render
            duration_samples: Total output length
        
        Returns:
            Mixed stereo audio array
        """
        output = np.zeros((duration_samples, 2))
        
        for note in notes:
            audio = self.render_note(note)
            
            # Ensure stereo
            if audio.ndim == 1:
                audio = np.column_stack([audio, audio])
            
            # Mix in at correct position
            end = min(note.start_sample + len(audio), duration_samples)
            output[note.start_sample:end] += audio[:end - note.start_sample]
        
        return output
    
    def load_soundfont(self, path: str) -> bool:
        """Load a SoundFont file. Override for SF2-capable backends."""
        return False
    
    def load_samples(self, samples_dir: str) -> int:
        """Load samples from directory. Returns count loaded."""
        return 0
    
    def set_program(self, channel: int, bank: int, program: int):
        """Set MIDI program for a channel. Override if supported."""
        pass
    
    def get_extension(self, extension_id: str) -> Optional[object]:
        """
        CLAP-inspired extension mechanism.
        
        Returns extension object if supported, None otherwise.
        Example extensions: "effects", "automation", "visualization"
        """
        return None
    
    def cleanup(self):
        """Release resources. Called when backend is no longer needed."""
        pass
```

### Backend Implementations

```python
class FluidSynthBackend(BaseSynthesizer):
    """
    FluidSynth SoundFont-based synthesis.
    
    Uses FluidSynth library for high-quality SoundFont playback.
    Supports GM/GS/XG standard instruments.
    """
    
    def __init__(self, config: SynthesizerConfig):
        super().__init__(config)
        self._synth = None
        self._sfont_id = None
        
        if self.is_available() and config.soundfont_path:
            self._init_fluidsynth(config.soundfont_path)
    
    @property
    def name(self) -> str:
        return "fluidsynth"
    
    @property
    def capabilities(self) -> Set[SynthesizerCapability]:
        return {
            SynthesizerCapability.SOUNDFONT,
            SynthesizerCapability.OFFLINE,
            SynthesizerCapability.EFFECTS_BUILTIN,
            SynthesizerCapability.MIDI_CC,
            SynthesizerCapability.POLYPHONY,
            SynthesizerCapability.VELOCITY_LAYERS,
        }
    
    def is_available(self) -> bool:
        try:
            import fluidsynth
            return True
        except ImportError:
            return False
    
    def render_note(self, note: SynthNote) -> np.ndarray:
        # Implementation using FluidSynth sequencer
        ...
    
    def load_soundfont(self, path: str) -> bool:
        # Load SF2/SF3 file
        ...


class ProceduralSynthBackend(BaseSynthesizer):
    """
    CPU-based procedural synthesis.
    
    Uses mathematical waveform generation for offline capability.
    Supports FM synthesis, subtractive synthesis, and drum synthesis.
    """
    
    @property
    def name(self) -> str:
        return "procedural"
    
    @property
    def capabilities(self) -> Set[SynthesizerCapability]:
        return {
            SynthesizerCapability.PROCEDURAL,
            SynthesizerCapability.OFFLINE,
            SynthesizerCapability.POLYPHONY,
        }
    
    def is_available(self) -> bool:
        return True  # Always available - pure Python/NumPy
    
    def render_note(self, note: SynthNote) -> np.ndarray:
        # Dispatch to appropriate generator based on program
        ...


class SampleBackend(BaseSynthesizer):
    """
    Sample-based synthesis using InstrumentLibrary.
    
    Plays pre-recorded samples with pitch shifting and velocity mapping.
    Supports one-shots (drums) and pitched instruments.
    """
    
    def __init__(self, config: SynthesizerConfig, instrument_library=None):
        super().__init__(config)
        self.instrument_library = instrument_library
        self._sample_cache: Dict[str, np.ndarray] = {}
    
    @property
    def name(self) -> str:
        return "samples"
    
    @property
    def capabilities(self) -> Set[SynthesizerCapability]:
        caps = {
            SynthesizerCapability.SAMPLE_PLAYBACK,
            SynthesizerCapability.OFFLINE,
            SynthesizerCapability.POLYPHONY,
        }
        if self.instrument_library:
            caps.add(SynthesizerCapability.VELOCITY_LAYERS)
            caps.add(SynthesizerCapability.ROUND_ROBIN)
        return caps
    
    def is_available(self) -> bool:
        return self.instrument_library is not None
    
    def render_note(self, note: SynthNote) -> np.ndarray:
        # Look up sample from library, pitch-shift if needed
        ...
```

---

## Backend Registration & Selection

### Registry Pattern

```python
from typing import Type, Callable


class SynthesizerRegistry:
    """
    Central registry for synthesizer backends.
    
    Follows the pattern from stem_separation.py with auto-detection
    and priority-based fallback.
    """
    
    _backends: Dict[str, Type[BaseSynthesizer]] = {}
    _priorities: Dict[str, int] = {}  # Lower = higher priority
    
    @classmethod
    def register(
        cls,
        name: str,
        backend_class: Type[BaseSynthesizer],
        priority: int = 100
    ):
        """
        Register a synthesizer backend.
        
        Args:
            name: Unique backend identifier
            backend_class: The backend class
            priority: Selection priority (lower = preferred)
        """
        cls._backends[name] = backend_class
        cls._priorities[name] = priority
    
    @classmethod
    def get(cls, name: str) -> Optional[Type[BaseSynthesizer]]:
        """Get a specific backend by name."""
        return cls._backends.get(name)
    
    @classmethod
    def get_available(cls) -> List[str]:
        """Get names of all available backends."""
        available = []
        for name, backend_cls in cls._backends.items():
            # Create temporary instance to check availability
            try:
                config = SynthesizerConfig()
                backend = backend_cls(config)
                if backend.is_available():
                    available.append(name)
            except Exception:
                pass
        return sorted(available, key=lambda n: cls._priorities.get(n, 100))
    
    @classmethod
    def get_best_available(
        cls,
        required_capabilities: Set[SynthesizerCapability] = None,
        config: SynthesizerConfig = None
    ) -> Optional[BaseSynthesizer]:
        """
        Get the best available backend matching requirements.
        
        Args:
            required_capabilities: Capabilities the backend must support
            config: Configuration for initialization
        
        Returns:
            Instantiated backend or None if no match
        """
        config = config or SynthesizerConfig()
        required = required_capabilities or set()
        
        # Sort by priority
        candidates = sorted(
            cls._backends.items(),
            key=lambda x: cls._priorities.get(x[0], 100)
        )
        
        for name, backend_cls in candidates:
            try:
                backend = backend_cls(config)
                if not backend.is_available():
                    continue
                if required and not required.issubset(backend.capabilities):
                    continue
                return backend
            except Exception as e:
                print(f"  [!] Backend '{name}' failed to initialize: {e}")
                continue
        
        return None
    
    @classmethod
    def create_chain(
        cls,
        preferred_order: List[str] = None,
        config: SynthesizerConfig = None
    ) -> "SynthesizerChain":
        """
        Create a fallback chain of backends.
        
        Args:
            preferred_order: List of backend names in preference order
            config: Configuration for all backends
        
        Returns:
            SynthesizerChain with fallback support
        """
        return SynthesizerChain(preferred_order or [], config or SynthesizerConfig())


# Register default backends
SynthesizerRegistry.register("fluidsynth", FluidSynthBackend, priority=10)
SynthesizerRegistry.register("samples", SampleBackend, priority=20)
SynthesizerRegistry.register("procedural", ProceduralSynthBackend, priority=90)
```

### Fallback Chain

```python
class SynthesizerChain(BaseSynthesizer):
    """
    Chain of synthesizers with automatic fallback.
    
    Tries each backend in order until one succeeds.
    Similar to how Tone.js falls back gracefully.
    """
    
    def __init__(self, preferred_order: List[str], config: SynthesizerConfig):
        super().__init__(config)
        self._backends: List[BaseSynthesizer] = []
        self._active: Optional[BaseSynthesizer] = None
        
        # Initialize backends in order
        for name in preferred_order:
            backend_cls = SynthesizerRegistry.get(name)
            if backend_cls:
                try:
                    backend = backend_cls(config)
                    if backend.is_available():
                        self._backends.append(backend)
                except Exception as e:
                    print(f"  [!] Skipping {name}: {e}")
        
        # Activate first available
        if self._backends:
            self._active = self._backends[0]
    
    @property
    def name(self) -> str:
        if self._active:
            return f"chain({self._active.name})"
        return "chain(none)"
    
    @property
    def capabilities(self) -> Set[SynthesizerCapability]:
        # Union of all backend capabilities
        all_caps = set()
        for backend in self._backends:
            all_caps.update(backend.capabilities)
        return all_caps
    
    def is_available(self) -> bool:
        return len(self._backends) > 0
    
    def render_note(self, note: SynthNote) -> np.ndarray:
        """Render with fallback."""
        for backend in self._backends:
            try:
                return backend.render_note(note)
            except Exception as e:
                print(f"  [!] {backend.name} failed, trying next: {e}")
                continue
        
        # All failed - return silence
        return np.zeros((note.duration_samples, 2))
    
    def select_for_note(self, note: SynthNote) -> BaseSynthesizer:
        """
        Intelligently select backend based on note characteristics.
        
        For example:
        - Drums (channel 10) → SampleBackend if available
        - Piano (program 0-7) → FluidSynth for quality
        - Synth leads → Procedural for control
        """
        is_drum = note.channel == 9  # MIDI drum channel
        
        if is_drum:
            # Prefer samples for drums
            for backend in self._backends:
                if SynthesizerCapability.SAMPLE_PLAYBACK in backend.capabilities:
                    return backend
        
        # Default to first available
        return self._active or self._backends[0]
```

---

## Unified API for FluidSynth, Procedural, and Samples

The key insight from Tone.js is that **all instruments share the same trigger API**. Here's how to unify our three backends:

### Common Interface Pattern

```python
class UnifiedSynthesizer:
    """
    Unified interface for all synthesis methods.
    
    Like Tone.js, provides identical API regardless of backend.
    """
    
    def __init__(
        self,
        config: SynthesizerConfig = None,
        backend: str = "auto",
        instrument_library = None,
        expansion_manager = None
    ):
        self.config = config or SynthesizerConfig()
        self._backend: BaseSynthesizer = None
        self._instrument_library = instrument_library
        self._expansion_manager = expansion_manager
        
        # Select backend
        if backend == "auto":
            self._backend = self._auto_select()
        else:
            self._backend = self._create_backend(backend)
    
    def _auto_select(self) -> BaseSynthesizer:
        """Auto-select best backend based on available resources."""
        # Priority: samples (custom) > fluidsynth (quality) > procedural (fallback)
        
        if self._instrument_library:
            sample_backend = SampleBackend(self.config, self._instrument_library)
            if sample_backend.is_available():
                return sample_backend
        
        if self.config.soundfont_path:
            fs_backend = FluidSynthBackend(self.config)
            if fs_backend.is_available():
                return fs_backend
        
        return ProceduralSynthBackend(self.config)
    
    # =========================================================================
    # UNIFIED API (same for all backends)
    # =========================================================================
    
    def render(
        self,
        notes: List[SynthNote],
        duration_samples: int = None
    ) -> np.ndarray:
        """
        Render notes to audio.
        
        Works identically for FluidSynth, samples, or procedural.
        """
        if not notes:
            return np.zeros((duration_samples or 0, 2))
        
        if duration_samples is None:
            duration_samples = max(n.start_sample + n.duration_samples for n in notes)
        
        return self._backend.render_notes(notes, duration_samples)
    
    def render_midi_track(
        self,
        track: "MidiTrack",
        tempo: float = 120.0
    ) -> np.ndarray:
        """Render an entire MIDI track."""
        notes = self._midi_track_to_notes(track, tempo)
        duration = self._calculate_track_duration(track, tempo)
        return self.render(notes, duration)
    
    def trigger_attack_release(
        self,
        pitch: int,
        duration: float,
        time: float = 0,
        velocity: float = 0.8
    ) -> np.ndarray:
        """
        Tone.js-style note triggering.
        
        Args:
            pitch: MIDI note number
            duration: Note duration in seconds
            time: Start time in seconds
            velocity: Velocity 0-1
        
        Returns:
            Rendered audio
        """
        note = SynthNote(
            pitch=pitch,
            start_sample=int(time * self.config.sample_rate),
            duration_samples=int(duration * self.config.sample_rate),
            velocity=velocity,
            channel=0,
            program=0
        )
        return self._backend.render_note(note)
    
    # =========================================================================
    # BACKEND MANAGEMENT
    # =========================================================================
    
    def set_backend(self, backend_name: str):
        """Switch to a different backend."""
        new_backend = self._create_backend(backend_name)
        if new_backend.is_available():
            self._backend = new_backend
        else:
            raise RuntimeError(f"Backend '{backend_name}' is not available")
    
    def get_backend_name(self) -> str:
        """Get current backend name."""
        return self._backend.name
    
    def get_capabilities(self) -> Set[SynthesizerCapability]:
        """Get current backend capabilities."""
        return self._backend.capabilities
```

### How Each Backend Maps to the Interface

| API Method | FluidSynth | Samples | Procedural |
|------------|------------|---------|------------|
| `render_note()` | Load SF2 program, render via sequencer | Find best sample match, pitch-shift | Generate waveform mathematically |
| `load_soundfont()` | Load .sf2/.sf3 file | N/A | N/A |
| `load_samples()` | N/A | Index instrument library | N/A |
| `set_program()` | Change MIDI program | Select category | Select generator type |
| Capabilities | SF, CC, Poly, VelLayers | Samples, RR, VelLayers | Procedural, Poly |

---

## Migration Strategy for audio_renderer.py

### Current State Analysis

The current [audio_renderer.py](../multimodal_gen/audio_renderer.py) has:

1. **`ProceduralRenderer` class** (line 481) - Handles procedural synthesis + samples
2. **`AudioRenderer` class** (line 1078) - Main class with FluidSynth + fallback logic
3. **Conditional backend selection** in `render_midi_file()` (line 1170) - Checks FluidSynth, custom drums, etc.
4. **Already uses ABC pattern** in `stem_separation.py` - Should follow this pattern

### Phase 1: Extract Interface (Non-Breaking)

Create the abstract interface alongside existing code:

```python
# New file: multimodal_gen/synthesizer_backend.py

from abc import ABC, abstractmethod
from typing import Set
from .audio_renderer import SynthNote  # Reuse existing

class BaseSynthesizer(ABC):
    """Abstract base for synthesis backends."""
    
    @abstractmethod
    def render_note(self, note: SynthNote) -> np.ndarray:
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @property
    @abstractmethod
    def capabilities(self) -> Set[SynthesizerCapability]:
        pass
```

### Phase 2: Wrap Existing Implementations

Create wrapper classes that implement the interface while delegating to existing code:

```python
# In synthesizer_backend.py

class ProceduralSynthAdapter(BaseSynthesizer):
    """Adapter wrapping existing ProceduralRenderer."""
    
    def __init__(self, config: SynthesizerConfig):
        super().__init__(config)
        from .audio_renderer import ProceduralRenderer
        self._renderer = ProceduralRenderer(
            sample_rate=config.sample_rate,
            instrument_library=config.instrument_library,
            genre=config.genre,
            mood=config.mood
        )
    
    @property
    def name(self) -> str:
        return "procedural"
    
    @property
    def capabilities(self) -> Set[SynthesizerCapability]:
        return {
            SynthesizerCapability.PROCEDURAL,
            SynthesizerCapability.SAMPLE_PLAYBACK,  # via InstrumentLibrary
            SynthesizerCapability.OFFLINE,
        }
    
    def is_available(self) -> bool:
        return True
    
    def render_note(self, note: SynthNote) -> np.ndarray:
        # Delegate to existing _synthesize_note method
        return self._renderer._synthesize_note(note)
```

### Phase 3: Refactor AudioRenderer

Modify `AudioRenderer` to use the new abstraction:

```python
class AudioRenderer:
    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        backend: str = "auto",  # NEW: Backend selection
        ...
    ):
        # Create synthesizer using registry
        self.config = SynthesizerConfig(
            sample_rate=sample_rate,
            soundfont_path=soundfont_path,
            genre=genre,
            mood=mood
        )
        
        self.synthesizer = SynthesizerRegistry.get_best_available(
            config=self.config
        ) if backend == "auto" else SynthesizerRegistry.create(backend, self.config)
    
    def render_midi_file(self, midi_path: str, output_path: str, ...) -> bool:
        # Simplified - no more conditional backend checking
        notes = self._parse_midi(midi_path)
        audio = self.synthesizer.render_notes(notes, duration)
        self._save_output(audio, output_path)
        return True
```

### Phase 4: Add New Backends

Now adding new synthesis backends is trivial:

```python
# New file: multimodal_gen/backends/csound_backend.py

class CsoundBackend(BaseSynthesizer):
    """Csound-based synthesis backend."""
    
    @property
    def name(self) -> str:
        return "csound"
    
    def is_available(self) -> bool:
        try:
            import ctcsound
            return True
        except ImportError:
            return False
    
    def render_note(self, note: SynthNote) -> np.ndarray:
        # Use Csound for synthesis
        ...

# Register it
SynthesizerRegistry.register("csound", CsoundBackend, priority=15)
```

### Migration Timeline

| Week | Task | Breaking Changes |
|------|------|------------------|
| 1 | Create `synthesizer_backend.py` with interface | None |
| 2 | Create adapters for existing code | None |
| 3 | Add `SynthesizerRegistry` | None |
| 4 | Update `AudioRenderer.__init__()` to accept `backend=` | None (default = current behavior) |
| 5 | Migrate `render_midi_file()` to use synthesizer | Minor API changes |
| 6 | Deprecate direct `ProceduralRenderer` usage | Deprecation warnings |
| 7+ | Add new backends (Csound, VST host, etc.) | None |

---

## Recommendations

### Immediate Actions

1. **Create `synthesizer_backend.py`** with the `BaseSynthesizer` ABC - modeled on existing `StemSeparator`

2. **Create `SynthesizerRegistry`** for backend registration and discovery

3. **Wrap existing code** in adapter classes before refactoring

### Architecture Principles

1. **Follow the `stem_separation.py` pattern** - it's already proven in this codebase

2. **Use capability-based selection** (CLAP-inspired) rather than fixed backend ordering

3. **Support hybrid rendering** - different backends for different instruments in same track

4. **Keep FluidSynth as primary** for quality, but make it optional

### Future Considerations

1. **Real-time support**: The interface should eventually support streaming/real-time with `start()`/`stop()` methods

2. **VST Host backend**: Consider adding a backend that can host VST3/CLAP plugins for maximum flexibility

3. **GPU acceleration**: Structure allows adding CUDA-accelerated synthesis later

4. **Network synthesis**: SuperCollider-style client/server could enable distributed rendering

---

## References

### Libraries Analyzed
- [Tone.js](https://tonejs.github.io/) - Web Audio framework
- [MIDI.js](https://galactic.ink/midi-js/) - Browser MIDI playback
- [SuperCollider](https://supercollider.github.io/) - Audio synthesis platform
- [Csound](https://csound.com/) - Sound design language
- [CLAP](https://github.com/free-audio/clap) - CLever Audio Plugin
- [JUCE](https://juce.com/) - Cross-platform audio framework

### Design Patterns
- [Factory Method](https://refactoring.guru/design-patterns/factory-method) - Creation pattern
- [Abstract Factory](https://refactoring.guru/design-patterns/abstract-factory) - Family creation
- [Strategy Pattern](https://refactoring.guru/design-patterns/strategy) - Algorithm encapsulation

### Internal References
- [stem_separation.py](../multimodal_gen/stem_separation.py) - Existing backend abstraction pattern
- [audio_renderer.py](../multimodal_gen/audio_renderer.py) - Current implementation to migrate
