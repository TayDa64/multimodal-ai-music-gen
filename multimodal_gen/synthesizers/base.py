"""Abstract interface for synthesizer backends."""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
import numpy as np


@dataclass
class SynthNote:
    """Note to be synthesized."""
    pitch: int
    start_sample: int
    duration_samples: int
    velocity: float  # 0-1
    channel: int
    program: int = 0


@dataclass
class SynthTrack:
    """A track containing notes to synthesize."""
    name: str
    notes: List[SynthNote]
    is_drums: bool = False
    channel: int = 0


@dataclass
class SynthResult:
    """Result of synthesis operation."""
    audio: np.ndarray
    sample_rate: int
    success: bool
    message: str = ""
    metadata: Optional[Dict[str, Any]] = None


class ISynthesizer(ABC):
    """
    Abstract interface for synthesizer backends.
    
    All synthesizer implementations must inherit from this interface.
    This enables swapping synth engines without modifying AudioRenderer.
    
    Capabilities:
    - render_notes: Synthesize individual notes to audio
    - render_midi_file: Render complete MIDI files (optional, not all backends support this)
    
    Implementations:
    - FluidSynthSynthesizer: Uses external FluidSynth with SoundFont files
    - ProceduralSynthesizer: CPU-based synthesis with intelligent instrument selection
    - (Future) VSTSynthesizer: VST plugin hosting
    - (Future) SurgeXTSynthesizer: Surge XT synthesizer integration
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of this synthesizer."""
        pass
    
    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this synthesizer is available/installed."""
        pass
    
    @abstractmethod
    def render_notes(
        self,
        notes: List[SynthNote],
        total_samples: int,
        is_drums: bool = False,
        sample_rate: int = 48000
    ) -> np.ndarray:
        """
        Render a list of notes to audio.
        
        Args:
            notes: List of SynthNote objects to render
            total_samples: Total length of output in samples
            is_drums: Whether these are drum notes (channel 10)
            sample_rate: Output sample rate
            
        Returns:
            Audio as numpy array (mono)
        """
        pass
    
    def render_midi_file(
        self,
        midi_path: str,
        output_path: str,
        sample_rate: int = 48000
    ) -> SynthResult:
        """
        Render a complete MIDI file to audio.
        
        Default implementation returns failure - subclass should override
        if direct MIDI file rendering is supported.
        
        Args:
            midi_path: Path to input MIDI file
            output_path: Path for output audio file
            sample_rate: Output sample rate
            
        Returns:
            SynthResult with success status and audio
        """
        return SynthResult(
            audio=np.array([]),
            sample_rate=sample_rate,
            success=False,
            message=f"{self.name} does not support direct MIDI file rendering"
        )
    
    def get_capabilities(self) -> Dict[str, bool]:
        """
        Return capabilities of this synthesizer.
        
        Returns:
            Dict with capability flags:
            - 'render_midi_file': Can render MIDI files directly
            - 'render_notes': Can render individual notes
            - 'drums': Supports drum channel
            - 'soundfonts': Supports SoundFont loading
            - 'intelligent_selection': Has genre-aware instrument selection
        """
        return {
            'render_midi_file': False,
            'render_notes': True,
            'drums': True,
            'soundfonts': False,
            'intelligent_selection': False,
        }
    
    def configure(self, **kwargs) -> None:
        """
        Configure synthesizer settings.
        
        Subclasses can override to accept settings like:
        - soundfont_path: Path to SoundFont file
        - instrument_library: InstrumentLibrary for intelligent selection
        - expansion_manager: ExpansionManager for specialized instruments
        - genre: Target genre for intelligent selection
        - mood: Mood modifier for selection
        """
        pass
    
    def get_info(self) -> Dict[str, Any]:
        """
        Get detailed information about this synthesizer.
        
        Returns:
            Dict with synthesizer details
        """
        return {
            'name': self.name,
            'available': self.is_available,
            'capabilities': self.get_capabilities(),
        }
