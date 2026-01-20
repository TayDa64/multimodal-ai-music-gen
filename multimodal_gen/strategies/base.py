"""Base Strategy interface for genre-specific generation."""
from abc import ABC, abstractmethod
from typing import List, Optional, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from ..arranger import SongSection
    from ..prompt_parser import ParsedPrompt
    from ..midi_generator import NoteEvent


@dataclass
class DrumConfig:
    """Configuration for drum generation."""
    base_velocity: int = 100
    swing: float = 0.0
    half_time: bool = False
    include_ghost_notes: bool = True
    include_rolls: bool = False
    density: str = '8th'  # '8th', '16th', 'sparse'


class GenreStrategy(ABC):
    """
    Abstract base class for genre-specific drum pattern generation.
    
    Implement this class to add support for new genres without modifying
    the MidiGenerator class (Open/Closed Principle).
    """
    
    @property
    @abstractmethod
    def genre_name(self) -> str:
        """Return the primary genre identifier."""
        pass
    
    @property
    def supported_genres(self) -> List[str]:
        """
        Return list of genre aliases this strategy handles.
        
        Override this to support multiple genre names with the same strategy.
        For example, EthiopianStrategy might handle ['ethiopian', 'ethio'].
        """
        return [self.genre_name]
    
    @abstractmethod
    def generate_drums(
        self,
        section: 'SongSection',
        parsed: 'ParsedPrompt',
        tension: float = 0.5
    ) -> List['NoteEvent']:
        """
        Generate drum pattern for the section.
        
        Args:
            section: The song section to generate drums for
            parsed: The parsed prompt with musical parameters
            tension: Tension value from 0.0 to 1.0 for dynamics
            
        Returns:
            List of NoteEvent objects for the drum pattern
        """
        pass
    
    def generate_bass(
        self,
        section: 'SongSection',
        parsed: 'ParsedPrompt',
        tension: float = 0.5
    ) -> List['NoteEvent']:
        """
        Optional: Override for genre-specific bass patterns.
        
        Returns empty list by default, which signals to use the
        standard bass generator.
        """
        return []
    
    def generate_chords(
        self,
        section: 'SongSection',
        parsed: 'ParsedPrompt',
        tension: float = 0.5
    ) -> List['NoteEvent']:
        """
        Optional: Override for genre-specific chord voicings.
        
        Returns empty list by default, which signals to use the
        standard chord generator.
        """
        return []
    
    def get_default_config(self) -> DrumConfig:
        """
        Return default configuration for this genre.
        
        Override to customize velocity, swing, etc. for the genre.
        """
        return DrumConfig()
    
    def _tension_multiplier(
        self,
        tension: float,
        min_mult: float,
        max_mult: float
    ) -> float:
        """
        Calculate a multiplier based on tension value.
        
        Args:
            tension: Tension value from 0.0 to 1.0
            min_mult: Multiplier at tension=0
            max_mult: Multiplier at tension=1
            
        Returns:
            Interpolated multiplier value
        """
        tension = max(0.0, min(1.0, float(tension)))
        return min_mult + (max_mult - min_mult) * tension
