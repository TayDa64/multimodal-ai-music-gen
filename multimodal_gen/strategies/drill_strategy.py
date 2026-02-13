"""Drill genre strategy - aggressive hi-hats, sliding 808s, dark patterns."""
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


class DrillStrategy(GenreStrategy):
    """
    UK/NY Drill drum strategy with signature characteristics:
    - Aggressive 16th-note hi-hat patterns with rapid rolls
    - Snare/clap emphasis on beat 3 (half-time feel)
    - Hard-hitting 808 kicks with syncopation
    - Darker, more aggressive velocity curves than standard trap
    - Sliding 808 bass patterns
    """

    @property
    def genre_name(self) -> str:
        return 'drill'

    @property
    def supported_genres(self) -> List[str]:
        return ['drill', 'uk_drill', 'ny_drill']

    def get_default_config(self) -> DrumConfig:
        return DrumConfig(
            base_velocity=110,
            swing=0.0,
            half_time=True,
            include_ghost_notes=False,
            include_rolls=True,
            density='16th',
        )

    def generate_drums(
        self,
        section: SongSection,
        parsed: ParsedPrompt,
        tension: float = 0.5,
    ) -> List[NoteEvent]:
        """Generate drill-style drum pattern — aggressive hi-hats, snare on 3."""
        notes: List[NoteEvent] = []
        config = section.config

        vel_mult = self._tension_multiplier(tension, 0.92, 1.15)
        effective_drum_density = self._get_effective_drum_density(
            config.drum_density, parsed
        )

        # === KICK — syncopated, punchy ===
        if config.enable_kick:
            kicks = generate_trap_kick_pattern(
                section.bars,
                variation=section.pattern_variation,
                base_velocity=int(110 * effective_drum_density * vel_mult),
            )
            for tick, dur, vel in kicks:
                notes.append(
                    NoteEvent(
                        pitch=GM_DRUM_NOTES['kick'],
                        start_tick=section.start_tick + tick,
                        duration_ticks=dur,
                        velocity=min(127, vel + 5),  # drill kicks hit harder
                        channel=GM_DRUM_CHANNEL,
                    )
                )

        # === SNARE on beat 3 (half-time) + layered claps ===
        if config.enable_snare:
            snares = generate_trap_snare_pattern(
                section.bars,
                variation=section.pattern_variation,
                base_velocity=int(105 * effective_drum_density * vel_mult),
                add_ghost_notes=False,  # drill keeps snare clean
                half_time=True,
            )
            for tick, dur, vel in snares:
                notes.append(
                    NoteEvent(
                        pitch=GM_DRUM_NOTES['snare'],
                        start_tick=section.start_tick + tick,
                        duration_ticks=dur,
                        velocity=min(127, vel),
                        channel=GM_DRUM_CHANNEL,
                    )
                )
                # Always layer clap on snare hits for drill
                clap_vel = humanize_velocity(max(55, int(vel * 0.88)), variation=0.08)
                notes.append(
                    NoteEvent(
                        pitch=GM_DRUM_NOTES['clap'],
                        start_tick=section.start_tick + tick,
                        duration_ticks=max(TICKS_PER_16TH, dur // 2),
                        velocity=clap_vel,
                        channel=GM_DRUM_CHANNEL,
                    )
                )

        # === HI-HATS — aggressive 16th rolls ===
        if config.enable_hihat:
            # Drill always uses rolls in energy sections
            include_rolls = section.section_type in [
                SectionType.DROP, SectionType.CHORUS,
                SectionType.BUILDUP, SectionType.VERSE,
            ]
            hihats = generate_trap_hihat_pattern(
                section.bars,
                variation=section.pattern_variation,
                base_velocity=int(85 * effective_drum_density * vel_mult),
                include_rolls=include_rolls,
                swing=0.0,  # drill is straight, no swing
            )
            for tick, dur, vel in hihats:
                notes.append(
                    NoteEvent(
                        pitch=GM_DRUM_NOTES['hihat_closed'],
                        start_tick=section.start_tick + tick,
                        duration_ticks=dur,
                        velocity=vel,
                        channel=GM_DRUM_CHANNEL,
                    )
                )

            # Sporadic open hats for aggression
            for bar in range(section.bars):
                bar_offset = section.start_tick + bar * TICKS_PER_BAR_4_4
                if random.random() < 0.40:
                    pos = random.choice([1.5, 3.5])
                    tick = bar_offset + beats_to_ticks(pos)
                    vel = humanize_velocity(
                        int(70 * config.drum_density), variation=0.12
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
