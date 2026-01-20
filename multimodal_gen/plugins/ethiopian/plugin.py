"""Ethiopian Traditional Instruments Plugin."""
from typing import Optional, Any
import numpy as np

from ..base import (
    IInstrumentPlugin,
    PluginManifest,
    InstrumentDefinition,
)


def _midi_to_frequency(midi_pitch: int) -> float:
    """Convert MIDI pitch to frequency in Hz."""
    return 440.0 * (2.0 ** ((midi_pitch - 69) / 12.0))


class EthiopianPlugin(IInstrumentPlugin):
    """
    Ethiopian traditional instruments plugin.
    
    Provides synthesized versions of:
    - Krar (Ethiopian Lyre) - Program 110
    - Masenqo (Single-string fiddle) - Program 111
    - Washint (Bamboo flute) - Program 112
    - Begena (Bass lyre) - Program 113
    - Kebero (Drum) - Program 114 (notes 50-52 for different hits)
    
    These instruments are fundamental to Ethiopian music traditions:
    - Krar: 5-6 string bowl lyre, used in secular and some religious music
    - Masenqo: Single-string bowed fiddle, accompanies azmaris (minstrels)
    - Washint: End-blown bamboo flute, pastoral and ceremonial music
    - Begena: 10-string bass lyre, meditative/religious music with buzzing
    - Kebero: Double-headed drum, drives Eskista dance rhythms
    """
    
    def __init__(self) -> None:
        self._manifest = self._create_manifest()
    
    def _create_manifest(self) -> PluginManifest:
        """Create the plugin manifest."""
        return PluginManifest(
            id="ethiopian_traditional",
            name="Ethiopian Traditional Instruments",
            version="1.0.0",
            author="AI Music Generator",
            description="Synthesized Ethiopian traditional instruments using physical modeling",
            culture="ethiopian",
            tags=["ethiopian", "african", "world", "traditional", "eskista", "azmari"],
            instruments={
                "krar": InstrumentDefinition(
                    id="krar",
                    name="krar",
                    display_name="Krar (ክራር)",
                    midi_program=110,
                    category="melodic",
                    tags=["string", "plucked", "lyre", "bowl-lyre"],
                    synthesis_params={
                        "brightness": 0.7,
                        "resonance": 0.8,
                        "sympathetic_strings": 5,
                        "tuning": "tizita",
                    },
                ),
                "masenqo": InstrumentDefinition(
                    id="masenqo",
                    name="masenqo",
                    display_name="Masenqo (ማሲንቆ)",
                    midi_program=111,
                    category="melodic",
                    tags=["string", "bowed", "fiddle", "one-string"],
                    synthesis_params={
                        "vibrato_rate": 5.5,
                        "vibrato_depth": 0.03,
                        "nasal_quality": 0.7,
                        "expressiveness": 0.7,
                    },
                ),
                "washint": InstrumentDefinition(
                    id="washint",
                    name="washint",
                    display_name="Washint (ዋሽንት)",
                    midi_program=112,
                    category="melodic",
                    tags=["wind", "flute", "bamboo", "end-blown"],
                    synthesis_params={
                        "breathiness": 0.4,
                        "ornament_probability": 0.3,
                    },
                ),
                "begena": InstrumentDefinition(
                    id="begena",
                    name="begena",
                    display_name="Begena (በገና)",
                    midi_program=113,
                    category="melodic",
                    tags=["string", "plucked", "bass", "lyre", "buzzing"],
                    synthesis_params={
                        "buzz_amount": 0.15,
                        "sustain": 2.0,
                    },
                ),
                "kebero": InstrumentDefinition(
                    id="kebero",
                    name="kebero",
                    display_name="Kebero (ከበሮ)",
                    midi_program=114,
                    category="percussion",
                    tags=["drum", "hand", "percussion", "double-headed"],
                    note_mappings={
                        50: "bass",
                        51: "slap",
                        52: "muted",
                        60: "high_bongo",
                        61: "low_bongo",
                        62: "high_conga",
                        63: "low_conga",
                    },
                ),
            },
            program_range=(110, 114),
        )
    
    @property
    def manifest(self) -> PluginManifest:
        """Return the plugin manifest."""
        return self._manifest
    
    @property
    def is_available(self) -> bool:
        """Always available (synthesis-based, no external dependencies)."""
        return True
    
    def synthesize(
        self,
        instrument_id: str,
        pitch: int,
        duration_samples: int,
        velocity: float,
        sample_rate: int = 48000,
        **kwargs: Any
    ) -> np.ndarray:
        """
        Synthesize an Ethiopian instrument note.
        
        Args:
            instrument_id: One of 'krar', 'masenqo', 'washint', 'begena', 'kebero'
            pitch: MIDI pitch (0-127)
            duration_samples: Duration in samples
            velocity: Velocity 0-1
            sample_rate: Output sample rate
            **kwargs: Additional synthesis parameters
            
        Returns:
            Audio as numpy array
        """
        # Import synthesis functions lazily to avoid circular imports
        from ...assets_gen import (
            generate_krar_tone,
            generate_masenqo_tone,
            generate_washint_tone,
            generate_begena_tone,
            generate_kebero_hit,
        )
        
        duration_sec = duration_samples / sample_rate
        frequency = _midi_to_frequency(pitch)
        
        if instrument_id == "krar":
            # Krar uses frequency-based synthesis
            tuning = kwargs.get('tuning', 'tizita')
            add_ornament = kwargs.get('add_ornament', False)
            return generate_krar_tone(
                frequency=frequency,
                duration=duration_sec,
                velocity=velocity,
                sample_rate=sample_rate,
                tuning=tuning,
                add_ornament=add_ornament,
            )
        
        elif instrument_id == "masenqo":
            # Masenqo uses frequency and expressiveness
            expressiveness = kwargs.get('expressiveness', 0.7)
            add_ornament = kwargs.get('add_ornament', False)
            return generate_masenqo_tone(
                frequency=frequency,
                duration=duration_sec,
                velocity=velocity,
                sample_rate=sample_rate,
                expressiveness=expressiveness,
                add_ornament=add_ornament,
            )
        
        elif instrument_id == "washint":
            # Washint uses frequency-based synthesis
            add_ornament = kwargs.get('add_ornament', False)
            return generate_washint_tone(
                frequency=frequency,
                duration=duration_sec,
                velocity=velocity,
                sample_rate=sample_rate,
                add_ornament=add_ornament,
            )
        
        elif instrument_id == "begena":
            # Begena uses frequency-based synthesis
            return generate_begena_tone(
                frequency=frequency,
                duration=duration_sec,
                velocity=velocity,
                sample_rate=sample_rate,
            )
        
        elif instrument_id == "kebero":
            # Kebero uses MIDI pitch directly to select hit type
            return generate_kebero_hit(
                pitch=pitch,
                velocity=velocity,
                sample_rate=sample_rate,
            )
        
        else:
            # Return silence for unknown instruments
            return np.zeros(duration_samples)
    
    def get_sample(
        self,
        instrument_id: str,
        pitch: int,
        velocity: float = 0.8
    ) -> Optional[np.ndarray]:
        """
        Get a sample for the instrument if available.
        
        Currently returns None as all Ethiopian instruments use synthesis.
        Override this method in subclasses to provide sample-based playback.
        """
        # Check if sample paths are defined for this instrument
        inst = self._manifest.instruments.get(instrument_id)
        if inst and inst.sample_paths:
            # Sample loading could be implemented here
            # For now, return None to use synthesis
            pass
        return None


def register() -> EthiopianPlugin:
    """Register the Ethiopian plugin with the global registry."""
    from ..registry import get_registry
    registry = get_registry()
    plugin = EthiopianPlugin()
    registry.register(plugin)
    return plugin
