"""G-Funk genre strategy - west coast bounce, clean hihats."""
from typing import List

from .base import GenreStrategy, DrumConfig
from ..arranger import SongSection, SectionType
from ..prompt_parser import ParsedPrompt
from ..midi_generator import NoteEvent, generate_gfunk_drum_pattern
from ..utils import GM_DRUM_NOTES, GM_DRUM_CHANNEL


class GFunkStrategy(GenreStrategy):
    """
    G-Funk drum strategy with west coast characteristics:
    - Bouncy, laid-back west coast feel
    - Clean 8th note hi-hats (NO rapid rolls)
    - Strong swing/shuffle (0.15)
    - Emphasis on the groove pocket
    - Influenced by funk and P-Funk
    - Think Dr. Dre's "The Chronic" era
    """
    
    @property
    def genre_name(self) -> str:
        return 'g_funk'
    
    @property
    def supported_genres(self) -> List[str]:
        return ['g_funk', 'gfunk', 'g-funk', 'west_coast', 'westcoast']
    
    def get_default_config(self) -> DrumConfig:
        return DrumConfig(
            base_velocity=85,
            swing=0.15,
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
        """Generate G-Funk west coast pattern."""
        notes: List[NoteEvent] = []
        config = section.config
        
        vel_mult = self._tension_multiplier(tension, 0.90, 1.10)
        
        # G-Funk uses the unified pattern generator
        patterns = generate_gfunk_drum_pattern(
            section.bars,
            swing=parsed.swing_amount or 0.15,
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
        
        # === CLAPS ===
        if 'clap' in patterns and 'clap' in parsed.drum_elements:
            for tick, dur, vel in patterns['clap']:
                notes.append(NoteEvent(
                    pitch=GM_DRUM_NOTES['clap'],
                    start_tick=section.start_tick + tick,
                    duration_ticks=dur,
                    velocity=vel,
                    channel=GM_DRUM_CHANNEL
                ))
        
        return notes
