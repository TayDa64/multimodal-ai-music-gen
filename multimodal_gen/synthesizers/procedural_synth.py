"""Procedural synthesis backend."""
from typing import List, Dict, Optional, Any, TYPE_CHECKING
import numpy as np

from .base import ISynthesizer, SynthNote as InterfaceSynthNote, SynthResult

if TYPE_CHECKING:
    from ..audio_renderer import ProceduralRenderer
    from ..instrument_manager import InstrumentLibrary
    from ..expansion_manager import ExpansionManager


class ProceduralSynthesizer(ISynthesizer):
    """
    Procedural synthesis backend.
    
    Uses CPU-based synthesis with optional intelligent instrument selection.
    This is a thin wrapper around the existing ProceduralRenderer class
    from audio_renderer.py.
    
    Features:
    - Genre-aware instrument selection via InstrumentLibrary
    - Expansion pack support for specialized instruments (Ethiopian, etc.)
    - Mood-based timbre adjustments
    - Always available (no external dependencies)
    """
    
    def __init__(
        self,
        sample_rate: int = 48000,
        instrument_library: Optional['InstrumentLibrary'] = None,
        expansion_manager: Optional['ExpansionManager'] = None,
        genre: Optional[str] = None,
        mood: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize Procedural synthesizer.
        
        Args:
            sample_rate: Output sample rate
            instrument_library: Optional InstrumentLibrary for intelligent selection
            expansion_manager: Optional ExpansionManager for specialized instruments
            genre: Target genre for intelligent selection
            mood: Mood modifier for selection
            **kwargs: Additional options (ignored for forward compatibility)
        """
        self._sample_rate = sample_rate
        self._instrument_library = instrument_library
        self._expansion_manager = expansion_manager
        self._genre = genre or "trap"
        self._mood = mood
        self._renderer: Optional['ProceduralRenderer'] = None
    
    @property
    def name(self) -> str:
        return "Procedural"
    
    @property
    def is_available(self) -> bool:
        """Procedural synthesis is always available."""
        return True
    
    def _ensure_renderer(self) -> 'ProceduralRenderer':
        """Lazy-initialize the ProceduralRenderer."""
        if self._renderer is None:
            # Import here to avoid circular imports
            from ..audio_renderer import ProceduralRenderer
            self._renderer = ProceduralRenderer(
                sample_rate=self._sample_rate,
                instrument_library=self._instrument_library,
                expansion_manager=self._expansion_manager,
                genre=self._genre,
                mood=self._mood
            )
        return self._renderer
    
    def configure(
        self,
        instrument_library: Optional['InstrumentLibrary'] = None,
        expansion_manager: Optional['ExpansionManager'] = None,
        genre: Optional[str] = None,
        mood: Optional[str] = None,
        sample_rate: Optional[int] = None,
        **kwargs
    ) -> None:
        """
        Update configuration.
        
        Args:
            instrument_library: InstrumentLibrary for intelligent selection
            expansion_manager: ExpansionManager for specialized instruments
            genre: Target genre for intelligent selection
            mood: Mood modifier for selection
            sample_rate: Output sample rate
            **kwargs: Additional options (ignored)
        """
        config_changed = False
        
        if instrument_library is not None:
            self._instrument_library = instrument_library
            config_changed = True
        if expansion_manager is not None:
            self._expansion_manager = expansion_manager
            config_changed = True
        if genre is not None:
            self._genre = genre
            config_changed = True
        if mood is not None:
            self._mood = mood
            config_changed = True
        if sample_rate is not None:
            self._sample_rate = sample_rate
            config_changed = True
        
        # Reset renderer to pick up new config
        if config_changed:
            self._renderer = None
    
    def render_notes(
        self,
        notes: List[InterfaceSynthNote],
        total_samples: int,
        is_drums: bool = False,
        sample_rate: int = 48000
    ) -> np.ndarray:
        """
        Render notes using procedural synthesis.
        
        Args:
            notes: List of SynthNote objects to render
            total_samples: Total length of output in samples
            is_drums: Whether these are drum notes (channel 10)
            sample_rate: Output sample rate
            
        Returns:
            Audio as numpy array (mono)
        """
        renderer = self._ensure_renderer()
        
        # Convert from interface SynthNote to ProceduralRenderer's SynthNote
        # They should be compatible, but we need to import the renderer's type
        from ..audio_renderer import SynthNote as RendererSynthNote
        
        renderer_notes = [
            RendererSynthNote(
                pitch=n.pitch,
                start_sample=n.start_sample,
                duration_samples=n.duration_samples,
                velocity=n.velocity,
                channel=n.channel,
                program=n.program
            )
            for n in notes
        ]
        
        return renderer.render_notes(renderer_notes, total_samples, is_drums)
    
    def set_genre_mood(self, genre: str, mood: Optional[str] = None) -> None:
        """
        Update genre and mood, reloading instruments.
        
        Args:
            genre: Target genre
            mood: Optional mood modifier
        """
        self._genre = genre
        self._mood = mood
        
        if self._renderer is not None:
            self._renderer.set_genre_mood(genre, mood)
    
    def get_capabilities(self) -> Dict[str, bool]:
        """Return Procedural synthesizer capabilities."""
        return {
            'render_midi_file': False,  # Uses render_notes instead
            'render_notes': True,
            'drums': True,
            'soundfonts': False,
            'intelligent_selection': self._instrument_library is not None,
            'expansion_packs': self._expansion_manager is not None,
        }
    
    def get_info(self) -> Dict[str, Any]:
        """Get detailed Procedural synthesizer information."""
        info = super().get_info()
        info.update({
            'sample_rate': self._sample_rate,
            'genre': self._genre,
            'mood': self._mood,
            'has_instrument_library': self._instrument_library is not None,
            'has_expansion_manager': self._expansion_manager is not None,
        })
        
        # Add custom instrument stats if renderer is initialized
        if self._renderer is not None:
            custom_drums = len(getattr(self._renderer, '_custom_drum_cache', {}) or {})
            custom_melodic = len(getattr(self._renderer, '_custom_melodic_cache', {}) or {})
            expansion_samples = len(getattr(self._renderer, '_expansion_sample_cache', {}) or {})
            
            info['loaded_samples'] = {
                'custom_drums': custom_drums,
                'custom_melodic': custom_melodic,
                'expansion_samples': expansion_samples,
            }
        
        return info
