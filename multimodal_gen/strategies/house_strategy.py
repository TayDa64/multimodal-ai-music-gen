"""House genre strategy - four-on-the-floor."""
from typing import List

from .base import GenreStrategy, DrumConfig
from ..arranger import SongSection, SectionType
from ..prompt_parser import ParsedPrompt
from ..midi_generator import NoteEvent, generate_house_drum_pattern
from ..utils import GM_DRUM_NOTES, GM_DRUM_CHANNEL


class HouseStrategy(GenreStrategy):
    """
    House drum strategy with signature characteristics:
    - Four-on-the-floor kick pattern
    - Clap on 2 and 4
    - Closed hi-hats on beats, open on off-beats
    - No swing (straight feel)
    """
    
    @property
    def genre_name(self) -> str:
        return 'house'
    
    @property
    def supported_genres(self) -> List[str]:
        return ['house', 'deep_house', 'tech_house', 'progressive_house']
    
    def get_default_config(self) -> DrumConfig:
        return DrumConfig(
            base_velocity=100,
            swing=0.0,
            half_time=False,
            include_ghost_notes=False,
            include_rolls=False,
            density='16th'
        )
    
    def generate_drums(
        self,
        section: SongSection,
        parsed: ParsedPrompt,
        tension: float = 0.5
    ) -> List[NoteEvent]:
        """Generate four-on-the-floor house pattern."""
        notes: List[NoteEvent] = []
        config = section.config
        
        vel_mult = self._tension_multiplier(tension, 0.90, 1.10)
        
        # House uses the unified pattern generator
        patterns = generate_house_drum_pattern(
            section.bars,
            base_velocity=int(100 * config.drum_density * vel_mult)
        )
        
        # Mapping of pattern keys to GM drum notes
        drum_mapping = {
            'kick': 'kick',
            'clap': 'clap',
            'hihat': 'hihat_closed',
            'hihat_open': 'hihat_open'
        }
        
        for drum_type, note_name in drum_mapping.items():
            if drum_type in patterns:
                for tick, dur, vel in patterns[drum_type]:
                    notes.append(NoteEvent(
                        pitch=GM_DRUM_NOTES[note_name],
                        start_tick=section.start_tick + tick,
                        duration_ticks=dur,
                        velocity=vel,
                        channel=GM_DRUM_CHANNEL
                    ))
        
        return notes
