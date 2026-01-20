"""Abstract interface for instrument plugins."""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np


@dataclass
class InstrumentDefinition:
    """Definition of an instrument within a plugin."""
    id: str
    name: str
    display_name: str
    midi_program: int
    category: str = "melodic"  # melodic, percussion, bass, fx
    tags: List[str] = field(default_factory=list)
    
    # Synthesis parameters
    synthesis_params: Dict[str, Any] = field(default_factory=dict)
    
    # Optional sample paths (override synthesis)
    sample_paths: Dict[int, str] = field(default_factory=dict)  # pitch -> path
    
    # MIDI note mappings for drums
    note_mappings: Dict[int, str] = field(default_factory=dict)  # note -> hit_type


@dataclass
class PluginManifest:
    """Manifest describing a plugin."""
    id: str
    name: str
    version: str = "1.0.0"
    author: str = ""
    description: str = ""
    
    # Plugin metadata
    culture: str = ""  # ethiopian, african, asian, etc.
    tags: List[str] = field(default_factory=list)
    
    # Instruments provided
    instruments: Dict[str, InstrumentDefinition] = field(default_factory=dict)
    
    # MIDI program range this plugin handles
    program_range: tuple = (0, 127)
    
    # Dependencies
    requires: List[str] = field(default_factory=list)  # Other plugin IDs


class IInstrumentPlugin(ABC):
    """
    Abstract interface for instrument plugins.
    
    Plugins provide synthesized instruments that can be loaded dynamically.
    Each plugin can handle multiple instruments (e.g., Ethiopian plugin
    provides krar, masenqo, washint, begena, kebero).
    """
    
    @property
    @abstractmethod
    def manifest(self) -> PluginManifest:
        """Return the plugin manifest."""
        pass
    
    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this plugin can be used."""
        pass
    
    @abstractmethod
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
        Synthesize a note for the specified instrument.
        
        Args:
            instrument_id: ID of instrument within this plugin
            pitch: MIDI pitch (0-127)
            duration_samples: Duration in samples
            velocity: Velocity 0-1
            sample_rate: Output sample rate
            **kwargs: Additional synthesis parameters
            
        Returns:
            Audio as numpy array
        """
        pass
    
    def get_sample(
        self,
        instrument_id: str,
        pitch: int,
        velocity: float = 0.8
    ) -> Optional[np.ndarray]:
        """
        Get a sample for the instrument if available.
        
        Default implementation returns None (no samples).
        Override to provide sample-based playback.
        
        Returns:
            Sample audio or None to use synthesis
        """
        return None
    
    def handles_program(self, program: int) -> bool:
        """Check if this plugin handles a MIDI program number."""
        low, high = self.manifest.program_range
        return low <= program <= high
    
    def get_instrument_for_program(self, program: int) -> Optional[InstrumentDefinition]:
        """Get instrument definition for a MIDI program number."""
        for inst in self.manifest.instruments.values():
            if inst.midi_program == program:
                return inst
        return None
    
    def list_instruments(self) -> List[InstrumentDefinition]:
        """List all instruments in this plugin."""
        return list(self.manifest.instruments.values())
    
    def get_info(self) -> Dict[str, Any]:
        """Get plugin information."""
        return {
            'id': self.manifest.id,
            'name': self.manifest.name,
            'version': self.manifest.version,
            'culture': self.manifest.culture,
            'instruments': [i.name for i in self.manifest.instruments.values()],
            'available': self.is_available,
        }
