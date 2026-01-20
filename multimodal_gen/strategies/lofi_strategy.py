"""Lo-fi genre strategy - swung feel, softer velocities."""
from typing import List

from .base import GenreStrategy, DrumConfig
from ..arranger import SongSection, SectionType
from ..prompt_parser import ParsedPrompt
from ..midi_generator import NoteEvent, generate_lofi_drum_pattern
from ..utils import GM_DRUM_NOTES, GM_DRUM_CHANNEL


class LofiStrategy(GenreStrategy):
    """
    Lo-fi hip hop drum strategy with characteristics:
    - Strong swing feel (0.12+)
    - Softer, more relaxed velocities
    - Simple, understated patterns
    - Vinyl crackle-friendly (sparse to let textures breathe)
    """
    
    @property
    def genre_name(self) -> str:
        return 'lofi'
    
    @property
    def supported_genres(self) -> List[str]:
        return ['lofi', 'lo_fi', 'lo-fi', 'chillhop']
    
    def get_default_config(self) -> DrumConfig:
        return DrumConfig(
            base_velocity=85,
            swing=0.12,
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
        """Generate lo-fi swing pattern."""
        notes: List[NoteEvent] = []
        config = section.config
        
        vel_mult = self._tension_multiplier(tension, 0.90, 1.10)
        
        # Lo-fi uses unified pattern generator for groove consistency
        patterns = generate_lofi_drum_pattern(
            section.bars,
            swing=parsed.swing_amount or 0.12,
            base_velocity=int(85 * config.drum_density * vel_mult)
        )
        
        # === KICK ===
        if config.enable_kick:
            for tick, dur, vel in patterns['kick']:
                notes.append(NoteEvent(
                    pitch=GM_DRUM_NOTES['kick'],
                    start_tick=section.start_tick + tick,
                    duration_ticks=dur,
                    velocity=vel,
                    channel=GM_DRUM_CHANNEL
                ))
        
        # === SNARE ===
        if config.enable_snare:
            for tick, dur, vel in patterns['snare']:
                notes.append(NoteEvent(
                    pitch=GM_DRUM_NOTES['snare'],
                    start_tick=section.start_tick + tick,
                    duration_ticks=dur,
                    velocity=vel,
                    channel=GM_DRUM_CHANNEL
                ))
        
        # === HI-HATS ===
        if config.enable_hihat:
            for tick, dur, vel in patterns['hihat']:
                notes.append(NoteEvent(
                    pitch=GM_DRUM_NOTES['hihat_closed'],
                    start_tick=section.start_tick + tick,
                    duration_ticks=dur,
                    velocity=vel,
                    channel=GM_DRUM_CHANNEL
                ))
        
        return notes
