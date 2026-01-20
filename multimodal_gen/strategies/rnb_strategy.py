"""R&B genre strategy - smooth groove, no rolls."""
from typing import List

from .base import GenreStrategy, DrumConfig
from ..arranger import SongSection, SectionType
from ..prompt_parser import ParsedPrompt
from ..midi_generator import NoteEvent, generate_rnb_drum_pattern
from ..utils import GM_DRUM_NOTES, GM_DRUM_CHANNEL


class RnBStrategy(GenreStrategy):
    """
    R&B drum strategy with signature characteristics:
    - Smooth, groove-oriented feel
    - No hi-hat rolls (clean, understated)
    - Emphasis on the pocket/groove
    - Lighter touch on drums
    - Occasional rim shots for texture
    """
    
    @property
    def genre_name(self) -> str:
        return 'rnb'
    
    @property
    def supported_genres(self) -> List[str]:
        return ['rnb', 'r&b', 'r_and_b']
    
    def get_default_config(self) -> DrumConfig:
        return DrumConfig(
            base_velocity=80,
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
        """Generate R&B smooth groove pattern."""
        notes: List[NoteEvent] = []
        config = section.config
        
        vel_mult = self._tension_multiplier(tension, 0.90, 1.10)
        
        # Use base class helper for reference-aware drum density
        effective_drum_density = self._get_effective_drum_density(config.drum_density, parsed)
        
        # R&B uses the unified pattern generator for groove consistency
        patterns = generate_rnb_drum_pattern(
            section.bars,
            swing=parsed.swing_amount or 0.08,
            base_velocity=int(80 * effective_drum_density * vel_mult)
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
        
        # === RIM SHOTS ===
        if 'rim' in patterns:
            for tick, dur, vel in patterns['rim']:
                notes.append(NoteEvent(
                    pitch=GM_DRUM_NOTES['snare_rim'],
                    start_tick=section.start_tick + tick,
                    duration_ticks=dur,
                    velocity=vel,
                    channel=GM_DRUM_CHANNEL
                ))
        
        return notes
