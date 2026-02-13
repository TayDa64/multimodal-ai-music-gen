"""Boom-bap genre strategy - classic hip-hop with swing and chops."""
from typing import List

from .base import GenreStrategy, DrumConfig
from ..arranger import SongSection, SectionType
from ..prompt_parser import ParsedPrompt
from ..midi_generator import NoteEvent, generate_lofi_drum_pattern
from ..utils import (
    GM_DRUM_NOTES,
    GM_DRUM_CHANNEL,
    TICKS_PER_BAR_4_4,
    TICKS_PER_BEAT,
    TICKS_PER_8TH,
    TICKS_PER_16TH,
    humanize_velocity,
    beats_to_ticks,
)


class BoomBapStrategy(GenreStrategy):
    """
    Classic boom-bap drum strategy with signature characteristics:
    - Punchy kick on 1 and the "and" of 2
    - Crisp snare on 2 and 4
    - Swing feel (8-12% offset)
    - Ghost snare notes for groove
    - Open hat accents
    - Minimal use of rolls — emphasis on pocket
    """

    @property
    def genre_name(self) -> str:
        return 'boom_bap'

    @property
    def supported_genres(self) -> List[str]:
        return ['boom_bap', 'boombap']

    def get_default_config(self) -> DrumConfig:
        return DrumConfig(
            base_velocity=95,
            swing=0.10,
            half_time=False,
            include_ghost_notes=True,
            include_rolls=False,
            density='8th',
        )

    def generate_drums(
        self,
        section: SongSection,
        parsed: ParsedPrompt,
        tension: float = 0.5,
    ) -> List[NoteEvent]:
        """Generate classic boom-bap drum pattern with swing."""
        notes: List[NoteEvent] = []
        config = section.config

        vel_mult = self._tension_multiplier(tension, 0.88, 1.08)
        effective_drum_density = self._get_effective_drum_density(
            config.drum_density, parsed
        )

        swing_amount = 0.10  # characteristic boom-bap swing

        for bar in range(section.bars):
            bar_offset = section.start_tick + bar * TICKS_PER_BAR_4_4

            # === KICK — beat 1, "and" of 2, beat 3 (variant) ===
            if config.enable_kick:
                kick_positions = [0.0, 1.5]  # beat 1, and-of-2
                # Add syncopated kick on beat 3 for variation
                if bar % 2 == 1:
                    kick_positions.append(2.75)
                for pos in kick_positions:
                    tick = bar_offset + beats_to_ticks(pos)
                    vel = humanize_velocity(
                        int(100 * effective_drum_density * vel_mult),
                        variation=0.08,
                    )
                    notes.append(
                        NoteEvent(
                            pitch=GM_DRUM_NOTES['kick'],
                            start_tick=tick,
                            duration_ticks=TICKS_PER_8TH,
                            velocity=vel,
                            channel=GM_DRUM_CHANNEL,
                        )
                    )

            # === SNARE — beats 2 and 4, with ghost notes ===
            if config.enable_snare:
                # Main snare hits on 2 and 4
                for pos in [1.0, 3.0]:
                    tick = bar_offset + beats_to_ticks(pos)
                    vel = humanize_velocity(
                        int(100 * effective_drum_density * vel_mult),
                        variation=0.06,
                    )
                    notes.append(
                        NoteEvent(
                            pitch=GM_DRUM_NOTES['snare'],
                            start_tick=tick,
                            duration_ticks=TICKS_PER_8TH,
                            velocity=vel,
                            channel=GM_DRUM_CHANNEL,
                        )
                    )

                # Ghost notes for groove
                if effective_drum_density > 0.4:
                    ghost_positions = [0.75, 2.5]
                    for pos in ghost_positions:
                        tick = bar_offset + beats_to_ticks(pos)
                        ghost_vel = humanize_velocity(
                            int(45 * effective_drum_density * vel_mult),
                            variation=0.15,
                        )
                        notes.append(
                            NoteEvent(
                                pitch=GM_DRUM_NOTES['snare'],
                                start_tick=tick,
                                duration_ticks=TICKS_PER_16TH,
                                velocity=max(20, ghost_vel),
                                channel=GM_DRUM_CHANNEL,
                            )
                        )

            # === HI-HATS — 8th notes with swing ===
            if config.enable_hihat:
                for eighth in range(8):
                    pos = eighth * 0.5
                    tick = bar_offset + beats_to_ticks(pos)
                    # Apply swing to off-beats
                    if eighth % 2 == 1:
                        tick += int(TICKS_PER_16TH * swing_amount * 2)
                    vel = humanize_velocity(
                        int(75 * effective_drum_density * vel_mult),
                        variation=0.10,
                    )
                    notes.append(
                        NoteEvent(
                            pitch=GM_DRUM_NOTES['hihat_closed'],
                            start_tick=tick,
                            duration_ticks=TICKS_PER_16TH,
                            velocity=vel,
                            channel=GM_DRUM_CHANNEL,
                        )
                    )

                # Open hat accent before snare
                if section.section_type in [
                    SectionType.CHORUS, SectionType.DROP,
                    SectionType.VARIATION,
                ]:
                    for open_pos in [0.75, 2.75]:
                        tick = bar_offset + beats_to_ticks(open_pos)
                        vel = humanize_velocity(
                            int(65 * config.drum_density), variation=0.12
                        )
                        notes.append(
                            NoteEvent(
                                pitch=GM_DRUM_NOTES['hihat_open'],
                                start_tick=tick,
                                duration_ticks=TICKS_PER_8TH,
                                velocity=vel,
                                channel=GM_DRUM_CHANNEL,
                            )
                        )

        return notes
