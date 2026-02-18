"""Ambient strategy - sparse, textural percussion when explicitly requested."""
from typing import List

from .base import GenreStrategy, DrumConfig
from ..arranger import SongSection, SectionType
from ..prompt_parser import ParsedPrompt
from ..midi_generator import NoteEvent
from ..utils import GM_DRUM_NOTES, GM_DRUM_CHANNEL, TICKS_PER_BEAT


class AmbientStrategy(GenreStrategy):
    """
    Ambient drum strategy.

    - By default, ambient uses no drums unless explicitly requested.
    - If drums are requested, keep patterns sparse and supportive.
    - Avoid dense transients that fight the pad/drone bed.
    """

    @property
    def genre_name(self) -> str:
        return 'ambient'

    @property
    def supported_genres(self) -> List[str]:
        return ['ambient', 'atmospheric', 'soundscape']

    def get_default_config(self) -> DrumConfig:
        return DrumConfig(
            base_velocity=70,
            swing=0.0,
            half_time=False,
            include_ghost_notes=False,
            include_rolls=False,
            density='sparse',
        )

    def generate_drums(
        self,
        section: SongSection,
        parsed: ParsedPrompt,
        tension: float = 0.5,
    ) -> List[NoteEvent]:
        """Generate sparse ambient percussion if explicitly requested."""
        if not parsed.drum_elements:
            return []

        notes: List[NoteEvent] = []
        config = section.config
        vel_mult = self._tension_multiplier(tension, 0.80, 1.05)
        base_vel = int(config.energy_level * 90 * vel_mult)

        ticks_per_bar = TICKS_PER_BEAT * 4
        wants_kick = 'kick' in parsed.drum_elements
        wants_snare = 'snare' in parsed.drum_elements
        wants_hat = 'hihat' in parsed.drum_elements or 'hihat_open' in parsed.drum_elements
        wants_cymbal = any(d in parsed.drum_elements for d in ('cymbal', 'crash', 'ride'))
        wants_perc = any(d in parsed.drum_elements for d in ('perc', 'shaker', 'rim'))

        for bar in range(section.bars):
            bar_start = section.start_tick + bar * ticks_per_bar

            if wants_kick and bar % 2 == 0:
                notes.append(NoteEvent(
                    pitch=GM_DRUM_NOTES['kick'],
                    start_tick=bar_start,
                    duration_ticks=TICKS_PER_BEAT,
                    velocity=min(127, int(base_vel * 0.8)),
                    channel=GM_DRUM_CHANNEL,
                ))

            if wants_snare and bar % 4 == 2:
                notes.append(NoteEvent(
                    pitch=GM_DRUM_NOTES['snare'],
                    start_tick=bar_start + 2 * TICKS_PER_BEAT,
                    duration_ticks=TICKS_PER_BEAT,
                    velocity=min(127, int(base_vel * 0.7)),
                    channel=GM_DRUM_CHANNEL,
                ))

            if wants_hat and bar % 2 == 1:
                for beat in (1, 3):
                    notes.append(NoteEvent(
                        pitch=GM_DRUM_NOTES['hihat_closed'],
                        start_tick=bar_start + beat * TICKS_PER_BEAT,
                        duration_ticks=TICKS_PER_BEAT // 2,
                        velocity=min(127, int(base_vel * 0.5)),
                        channel=GM_DRUM_CHANNEL,
                    ))

            if wants_perc and bar % 4 == 1:
                notes.append(NoteEvent(
                    pitch=GM_DRUM_NOTES.get('tambourine', 54),
                    start_tick=bar_start + TICKS_PER_BEAT,
                    duration_ticks=TICKS_PER_BEAT // 2,
                    velocity=min(127, int(base_vel * 0.45)),
                    channel=GM_DRUM_CHANNEL,
                ))

            if wants_cymbal:
                if bar == 0 or section.section_type in (SectionType.BREAKDOWN, SectionType.OUTRO):
                    notes.append(NoteEvent(
                        pitch=GM_DRUM_NOTES.get('crash', 49),
                        start_tick=bar_start,
                        duration_ticks=TICKS_PER_BEAT * 2,
                        velocity=min(127, int(base_vel * 0.6)),
                        channel=GM_DRUM_CHANNEL,
                    ))

        return notes
