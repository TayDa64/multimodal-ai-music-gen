"""Trap Soul genre strategy - cleaner 8th notes, groove-focused."""
from typing import List

from .base import GenreStrategy, DrumConfig
from ..arranger import SongSection, SectionType
from ..prompt_parser import ParsedPrompt
from ..midi_generator import (
    NoteEvent,
    generate_trap_kick_pattern,
    generate_trap_snare_pattern,
    generate_standard_hihat_pattern,
)
from ..utils import (
    GM_DRUM_NOTES,
    GM_DRUM_CHANNEL,
    TICKS_PER_16TH,
    humanize_velocity,
)


class TrapSoulStrategy(GenreStrategy):
    """
    Trap Soul drum strategy - cleaner than pure trap:
    - 8th note hi-hats (not dense 16ths)
    - No hi-hat rolls
    - Subtle swing for groove
    - Layered claps for body
    """
    
    @property
    def genre_name(self) -> str:
        return 'trap_soul'
    
    @property
    def supported_genres(self) -> List[str]:
        return ['trap_soul', 'trapsoul']
    
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
        """Generate trap soul drum pattern - cleaner than pure trap."""
        notes: List[NoteEvent] = []
        config = section.config
        
        vel_mult = self._tension_multiplier(tension, 0.90, 1.10)
        
        # === KICK ===
        if config.enable_kick:
            kicks = generate_trap_kick_pattern(
                section.bars,
                variation=section.pattern_variation,
                base_velocity=int(90 * config.drum_density * vel_mult)
            )
            for tick, dur, vel in kicks:
                notes.append(NoteEvent(
                    pitch=GM_DRUM_NOTES['kick'],
                    start_tick=section.start_tick + tick,
                    duration_ticks=dur,
                    velocity=vel,
                    channel=GM_DRUM_CHANNEL
                ))
        
        # === SNARE ===
        if config.enable_snare:
            snares = generate_trap_snare_pattern(
                section.bars,
                variation=section.pattern_variation,
                base_velocity=int(85 * config.drum_density * vel_mult),
                add_ghost_notes=False,  # Cleaner for trap_soul
                half_time=False
            )
            for tick, dur, vel in snares:
                notes.append(NoteEvent(
                    pitch=GM_DRUM_NOTES['snare'],
                    start_tick=section.start_tick + tick,
                    duration_ticks=dur,
                    velocity=vel,
                    channel=GM_DRUM_CHANNEL
                ))
            
            # Layer claps
            if 'clap' in parsed.drum_elements:
                for tick, dur, vel in snares:
                    if dur >= TICKS_PER_16TH:
                        notes.append(NoteEvent(
                            pitch=GM_DRUM_NOTES['clap'],
                            start_tick=section.start_tick + tick,
                            duration_ticks=dur // 2,
                            velocity=humanize_velocity(
                                int(vel * 0.85),
                                variation=0.10
                            ),
                            channel=GM_DRUM_CHANNEL
                        ))
        
        # === HI-HATS ===
        if config.enable_hihat:
            # Trap Soul: Use standard 8th note pattern - NOT 16th note trap pattern
            hihats = generate_standard_hihat_pattern(
                section.bars,
                density='8th',  # Clean 8th notes, not dense 16ths
                base_velocity=int(70 * config.drum_density * vel_mult),
                swing=parsed.swing_amount or 0.08,
                include_rolls=False  # No rolls for trap_soul
            )
            for tick, dur, vel in hihats:
                notes.append(NoteEvent(
                    pitch=GM_DRUM_NOTES['hihat_closed'],
                    start_tick=section.start_tick + tick,
                    duration_ticks=dur,
                    velocity=vel,
                    channel=GM_DRUM_CHANNEL
                ))
        
        return notes
