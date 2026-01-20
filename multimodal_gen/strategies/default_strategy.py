"""Default strategy - boom-bap style fallback."""
from typing import List

from .base import GenreStrategy, DrumConfig
from ..arranger import SongSection, SectionType
from ..prompt_parser import ParsedPrompt
from ..midi_generator import NoteEvent, generate_lofi_drum_pattern
from ..utils import GM_DRUM_NOTES, GM_DRUM_CHANNEL


class DefaultStrategy(GenreStrategy):
    """
    Default fallback drum strategy - boom-bap style.
    
    Used when no specific genre strategy is registered for the
    requested genre. Provides a neutral, professional drum pattern.
    """
    
    @property
    def genre_name(self) -> str:
        return 'default'
    
    @property
    def supported_genres(self) -> List[str]:
        return ['default', 'boom_bap', 'boombap', 'hip_hop', 'hiphop']
    
    def get_default_config(self) -> DrumConfig:
        return DrumConfig(
            base_velocity=90,
            swing=0.08,
            half_time=False,
            include_ghost_notes=False,
            include_rolls=False,
            density='8th'
        )
    
    def generate_drums(
        self,
        section: SongSection,
        parsed: ParsedPrompt,
        tension: float = 0.5
    ) -> List[NoteEvent]:
        """Generate default boom-bap style pattern."""
        notes: List[NoteEvent] = []
        config = section.config
        
        vel_mult = self._tension_multiplier(tension, 0.90, 1.10)
        
        # Use lofi pattern generator as boom-bap base
        patterns = generate_lofi_drum_pattern(
            section.bars,
            swing=0.08,
            base_velocity=int(90 * config.drum_density * vel_mult)
        )
        
        drum_mapping = {
            'kick': 'kick',
            'snare': 'snare',
            'hihat': 'hihat_closed'
        }
        
        for pattern_type, note_name in drum_mapping.items():
            for tick, dur, vel in patterns.get(pattern_type, []):
                notes.append(NoteEvent(
                    pitch=GM_DRUM_NOTES[note_name],
                    start_tick=section.start_tick + tick,
                    duration_ticks=dur,
                    velocity=vel,
                    channel=GM_DRUM_CHANNEL
                ))
        
        return notes
