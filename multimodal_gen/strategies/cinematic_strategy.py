"""Cinematic/Orchestral strategy - orchestral percussion with dramatic dynamics."""
import random
from typing import List

from .base import GenreStrategy, DrumConfig
from ..arranger import SongSection, SectionType
from ..prompt_parser import ParsedPrompt
from ..midi_generator import NoteEvent
from ..utils import GM_DRUM_NOTES, GM_DRUM_CHANNEL, TICKS_PER_BEAT


class CinematicStrategy(GenreStrategy):
    """
    Cinematic/Orchestral drum strategy.

    Generates orchestral percussion instead of kit drums:
    - Timpani rolls and hits on downbeats
    - Crash cymbals at section boundaries
    - Triangle for light passages
    - Floor toms for sub-bass rumble
    - Sparse, dramatic patterns that serve the music, not dominate it

    Tension directly modulates density and velocity:
    - Low tension  → sparse triangle/ride taps
    - Mid tension  → timpani + cymbal accents
    - High tension → full orchestral percussion battery
    """

    @property
    def genre_name(self) -> str:
        return 'cinematic'

    @property
    def supported_genres(self) -> List[str]:
        return [
            'cinematic', 'orchestral', 'film_score',
            'soundtrack', 'epic', 'symphonic',
        ]

    def get_default_config(self) -> DrumConfig:
        return DrumConfig(
            base_velocity=80,
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
        """Generate orchestral percussion pattern based on tension."""
        notes: List[NoteEvent] = []
        config = section.config

        vel_mult = self._tension_multiplier(tension, 0.75, 1.15)
        base_vel = int(config.energy_level * 100 * vel_mult)

        ticks_per_bar = TICKS_PER_BEAT * 4  # 4/4 time

        for bar in range(section.bars):
            bar_start = section.start_tick + bar * ticks_per_bar
            bar_tension = self._bar_tension(bar, section.bars, tension)

            # ── Timpani (GM: Low Floor Tom 41 for deep timpani feel) ──
            if bar_tension > 0.3:
                # Downbeat hit
                notes.append(NoteEvent(
                    pitch=GM_DRUM_NOTES['tom_low'],
                    start_tick=bar_start,
                    duration_ticks=TICKS_PER_BEAT,
                    velocity=min(127, int(base_vel * 1.1)),
                    channel=GM_DRUM_CHANNEL,
                ))
                # Beat 3 hit at higher tension
                if bar_tension > 0.6:
                    notes.append(NoteEvent(
                        pitch=GM_DRUM_NOTES['tom_low'],
                        start_tick=bar_start + 2 * TICKS_PER_BEAT,
                        duration_ticks=TICKS_PER_BEAT,
                        velocity=min(127, int(base_vel * 0.9)),
                        channel=GM_DRUM_CHANNEL,
                    ))
                # Timpani roll on climax bars (16th-note tremolo)
                if bar_tension > 0.85:
                    self._add_timpani_roll(
                        notes, bar_start, ticks_per_bar, base_vel
                    )

            # ── Crash cymbal at section starts / climaxes ──
            if bar == 0 and section.section_type in (
                SectionType.CHORUS, SectionType.DROP, SectionType.BUILDUP
            ):
                notes.append(NoteEvent(
                    pitch=GM_DRUM_NOTES['crash'],
                    start_tick=bar_start,
                    duration_ticks=TICKS_PER_BEAT * 2,
                    velocity=min(127, int(base_vel * 1.2)),
                    channel=GM_DRUM_CHANNEL,
                ))
            # Crash on last bar of buildup
            if (bar == section.bars - 1
                    and section.section_type == SectionType.BUILDUP):
                notes.append(NoteEvent(
                    pitch=GM_DRUM_NOTES['crash2'],
                    start_tick=bar_start + 3 * TICKS_PER_BEAT,
                    duration_ticks=TICKS_PER_BEAT,
                    velocity=min(127, base_vel),
                    channel=GM_DRUM_CHANNEL,
                ))

            # ── Triangle / ride for light texture ──
            if bar_tension < 0.5:
                # Light triangle taps on beats 2 and 4
                for beat in (1, 3):
                    notes.append(NoteEvent(
                        pitch=GM_DRUM_NOTES.get('tambourine', 54),
                        start_tick=bar_start + beat * TICKS_PER_BEAT,
                        duration_ticks=TICKS_PER_BEAT // 2,
                        velocity=min(127, int(base_vel * 0.5)),
                        channel=GM_DRUM_CHANNEL,
                    ))
            elif bar_tension > 0.5:
                # Ride bell for medium-high energy
                for beat in range(4):
                    if random.random() < bar_tension * 0.6:
                        notes.append(NoteEvent(
                            pitch=GM_DRUM_NOTES['ride_bell'],
                            start_tick=bar_start + beat * TICKS_PER_BEAT,
                            duration_ticks=TICKS_PER_BEAT // 2,
                            velocity=min(127, int(base_vel * 0.6)),
                            channel=GM_DRUM_CHANNEL,
                        ))

            # ── Bass drum (orchestral) at high tension ──
            if bar_tension > 0.7:
                notes.append(NoteEvent(
                    pitch=GM_DRUM_NOTES['kick'],
                    start_tick=bar_start,
                    duration_ticks=TICKS_PER_BEAT,
                    velocity=min(127, int(base_vel * 0.8)),
                    channel=GM_DRUM_CHANNEL,
                ))

        return notes

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _bar_tension(
        self, bar_index: int, total_bars: int, section_tension: float
    ) -> float:
        """Calculate per-bar tension with a gentle ramp within the section."""
        if total_bars <= 1:
            return section_tension
        progress = bar_index / (total_bars - 1)
        # Slight ramp within section — tension grows toward end of section
        ramp = 0.8 + 0.2 * progress
        return max(0.0, min(1.0, section_tension * ramp))

    def _add_timpani_roll(
        self,
        notes: List[NoteEvent],
        bar_start: int,
        ticks_per_bar: int,
        base_vel: int,
    ) -> None:
        """Add a timpani roll (16th note tremolo) on the last two beats."""
        sixteenth = TICKS_PER_BEAT // 4
        roll_start = bar_start + 2 * TICKS_PER_BEAT  # Start on beat 3
        for i in range(8):  # 8 sixteenths = 2 beats
            vel = min(127, int(base_vel * (0.7 + 0.3 * (i / 7))))  # crescendo
            notes.append(NoteEvent(
                pitch=GM_DRUM_NOTES['tom_low'],
                start_tick=roll_start + i * sixteenth,
                duration_ticks=sixteenth,
                velocity=vel,
                channel=GM_DRUM_CHANNEL,
            ))
