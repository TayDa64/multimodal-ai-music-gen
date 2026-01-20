"""Trap genre strategy - dense 16th notes, half-time snare, hi-hat rolls."""
from typing import List
import random

from .base import GenreStrategy, DrumConfig
from ..arranger import SongSection, SectionType
from ..prompt_parser import ParsedPrompt
from ..midi_generator import (
    NoteEvent,
    generate_trap_kick_pattern,
    generate_trap_snare_pattern,
    generate_trap_hihat_pattern,
)
from ..utils import (
    GM_DRUM_NOTES,
    GM_DRUM_CHANNEL,
    TICKS_PER_BAR_4_4,
    TICKS_PER_8TH,
    TICKS_PER_16TH,
    TICKS_PER_BEAT,
    humanize_velocity,
    beats_to_ticks,
)


class TrapStrategy(GenreStrategy):
    """
    Trap drum strategy with signature characteristics:
    - Dense 16th note hi-hats with rolls
    - Half-time snare on beat 3
    - 808-style kicks with syncopation
    - Layered claps on snare hits
    """
    
    @property
    def genre_name(self) -> str:
        return 'trap'
    
    @property
    def supported_genres(self) -> List[str]:
        return ['trap', 'drill']
    
    def get_default_config(self) -> DrumConfig:
        return DrumConfig(
            base_velocity=100,
            swing=0.0,
            half_time=True,
            include_ghost_notes=True,
            include_rolls=True,
            density='16th'
        )
    
    def generate_drums(
        self,
        section: SongSection,
        parsed: ParsedPrompt,
        tension: float = 0.5
    ) -> List[NoteEvent]:
        """Generate trap-style drum pattern."""
        notes: List[NoteEvent] = []
        config = section.config
        
        # Apply tension as velocity scaler
        vel_mult = self._tension_multiplier(tension, 0.90, 1.10)
        
        # === REFERENCE ANALYSIS PARAMS ===
        # Use base class helper to blend section config with reference analysis
        effective_drum_density = self._get_effective_drum_density(config.drum_density, parsed)
        
        # Reference trap_hihats influences hi-hat roll and density behavior
        use_trap_hihats = getattr(parsed, 'reference_trap_hihats', None)
        if use_trap_hihats is None:
            # Default: enable trap hi-hats for trap genre
            use_trap_hihats = True
        
        # === KICK ===
        if config.enable_kick:
            kicks = generate_trap_kick_pattern(
                section.bars,
                variation=section.pattern_variation,
                base_velocity=int(100 * effective_drum_density * vel_mult)
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
                base_velocity=int(95 * effective_drum_density * vel_mult),
                add_ghost_notes=effective_drum_density > 0.5,
                half_time=True
            )
            for tick, dur, vel in snares:
                notes.append(NoteEvent(
                    pitch=GM_DRUM_NOTES['snare'],
                    start_tick=section.start_tick + tick,
                    duration_ticks=dur,
                    velocity=vel,
                    channel=GM_DRUM_CHANNEL
                ))
            
            # Add layered claps
            if 'clap' in parsed.drum_elements:
                for tick, dur, vel in snares:
                    if dur >= TICKS_PER_16TH:
                        clap_vel = humanize_velocity(
                            max(50, int(vel * 0.90)),
                            variation=0.10
                        )
                        notes.append(NoteEvent(
                            pitch=GM_DRUM_NOTES['clap'],
                            start_tick=section.start_tick + tick,
                            duration_ticks=max(TICKS_PER_16TH, dur // 2),
                            velocity=clap_vel,
                            channel=GM_DRUM_CHANNEL
                        ))
        
        # === HI-HATS ===
        if config.enable_hihat:
            # For trap: dense 16th notes, rolls based on reference analysis OR explicit request
            # If reference detected trap_hihats, ALWAYS include rolls in energy sections
            include_rolls = (
                ('hihat_roll' in parsed.drum_elements or use_trap_hihats) and
                section.section_type in [SectionType.DROP, SectionType.CHORUS, SectionType.BUILDUP]
            )
            hihats = generate_trap_hihat_pattern(
                section.bars,
                variation=section.pattern_variation,
                base_velocity=int(75 * effective_drum_density * vel_mult),
                include_rolls=include_rolls,
                swing=parsed.swing_amount
            )
            for tick, dur, vel in hihats:
                notes.append(NoteEvent(
                    pitch=GM_DRUM_NOTES['hihat_closed'],
                    start_tick=section.start_tick + tick,
                    duration_ticks=dur,
                    velocity=vel,
                    channel=GM_DRUM_CHANNEL
                ))
            
            # Open hats for high-energy sections
            if section.section_type in [
                SectionType.DROP, SectionType.VARIATION, SectionType.BUILDUP
            ]:
                for bar in range(section.bars):
                    bar_offset = section.start_tick + bar * TICKS_PER_BAR_4_4
                    if random.random() < 0.55:
                        for pos in [1.5, 3.5]:
                            tick = bar_offset + beats_to_ticks(pos)
                            vel = humanize_velocity(
                                int(60 * config.drum_density),
                                variation=0.15
                            )
                            notes.append(NoteEvent(
                                pitch=GM_DRUM_NOTES['hihat_open'],
                                start_tick=tick,
                                duration_ticks=TICKS_PER_8TH,
                                velocity=vel,
                                channel=GM_DRUM_CHANNEL
                            ))
            
            # Crash on drop/chorus entry
            if 'crash' in parsed.drum_elements and section.section_type in [
                SectionType.DROP, SectionType.CHORUS
            ]:
                notes.append(NoteEvent(
                    pitch=GM_DRUM_NOTES['crash'],
                    start_tick=section.start_tick,
                    duration_ticks=TICKS_PER_BEAT,
                    velocity=humanize_velocity(
                        int(85 * config.drum_density * vel_mult),
                        variation=0.10
                    ),
                    channel=GM_DRUM_CHANNEL
                ))
        
        return notes
