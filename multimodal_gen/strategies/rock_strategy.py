"""Rock genre strategy - live-kit drums, driving bass, and power chords."""
from typing import List, Optional

from .base import DrumConfig, GenreStrategy
from ..arranger import SectionType, SongSection
from ..midi_generator import NoteEvent
from ..pattern_library import Pattern, PatternLibrary, PatternType
from ..prompt_parser import ParsedPrompt
from ..utils import (
    GM_DRUM_CHANNEL,
    GM_DRUM_NOTES,
    TICKS_PER_8TH,
    TICKS_PER_16TH,
    TICKS_PER_BAR_4_4,
    TICKS_PER_BEAT,
    beats_to_ticks,
    note_name_to_midi,
)


ROCK_FAMILY_GENRES = [
    'rock',
    'classic_rock',
    'alternative_rock',
    'grunge',
    'punk_rock',
    'indie_rock',
]


class RockStrategy(GenreStrategy):
    """
    Live-band rock strategy.

    This intentionally avoids trap signatures: no 808 assumptions, no claps,
    no half-time backbeat, and no hi-hat rolls. The rhythm section stays close
    to a deterministic live-kit backbeat with guitar/bass-friendly patterns.
    """

    _KICK_PITCHES = {GM_DRUM_NOTES['kick'], GM_DRUM_NOTES['kick2']}
    _SNARE_PITCHES = {GM_DRUM_NOTES['snare'], GM_DRUM_NOTES['snare2'], GM_DRUM_NOTES['snare_rim']}
    _HIHAT_PITCHES = {
        GM_DRUM_NOTES['hihat_closed'],
        GM_DRUM_NOTES['hihat_open'],
        GM_DRUM_NOTES['hihat_pedal'],
        GM_DRUM_NOTES['ride'],
        GM_DRUM_NOTES['ride_bell'],
        GM_DRUM_NOTES['crash'],
        GM_DRUM_NOTES['crash2'],
    }

    def __init__(self) -> None:
        self._library: Optional[PatternLibrary] = None

    @property
    def genre_name(self) -> str:
        return 'rock'

    @property
    def supported_genres(self) -> List[str]:
        return ROCK_FAMILY_GENRES.copy()

    def get_default_config(self) -> DrumConfig:
        return DrumConfig(
            base_velocity=98,
            swing=0.02,
            half_time=False,
            include_ghost_notes=False,
            include_rolls=False,
            density='8th',
        )

    @property
    def _patterns(self) -> PatternLibrary:
        if self._library is None:
            self._library = PatternLibrary()
        return self._library

    def generate_drums(
        self,
        section: SongSection,
        parsed: ParsedPrompt,
        tension: float = 0.5,
    ) -> List[NoteEvent]:
        """Generate a live rock drum part on the GM drum channel."""
        notes: List[NoteEvent] = []
        config = section.config

        vel_mult = self._tension_multiplier(tension, 0.92, 1.12)
        density = self._get_effective_drum_density(config.drum_density, parsed)

        base_pattern = self._get_pattern(PatternType.DRUM, 'rock_basic_beat')
        if base_pattern is not None:
            notes.extend(
                self._repeat_drum_pattern(
                    base_pattern,
                    section,
                    velocity_scale=(0.90 + density * 0.20) * vel_mult,
                )
            )
        else:
            notes.extend(self._fallback_backbeat(section, density, vel_mult))

        if self._is_high_energy(section):
            notes.extend(self._add_high_energy_kit_accents(section, density, vel_mult))

        notes.sort(key=lambda n: (n.start_tick, n.pitch))
        return notes

    def generate_bass(
        self,
        section: SongSection,
        parsed: ParsedPrompt,
        tension: float = 0.5,
    ) -> List[NoteEvent]:
        """Generate simple root/fifth eighth-note rock bass."""
        if not section.config.enable_bass:
            return []

        notes: List[NoteEvent] = []
        vel_mult = self._tension_multiplier(tension, 0.92, 1.10)
        base_velocity = self._clamp_velocity(
            86 * (0.94 + section.config.energy_level * 0.14) * vel_mult
        )

        for bar in range(section.bars):
            chord_root = self._section_root(parsed, section.section_type, bar, octave=2)
            fifth = self._fit_range(chord_root + 7, 36, 55)
            pattern = [chord_root, chord_root, fifth, chord_root, chord_root, fifth, chord_root, chord_root]
            if section.section_type in [SectionType.CHORUS, SectionType.BRIDGE, SectionType.DROP, SectionType.VARIATION]:
                pattern = [chord_root, fifth, chord_root, fifth, chord_root, fifth, chord_root, fifth]

            bar_offset = section.start_tick + bar * TICKS_PER_BAR_4_4
            for idx, pitch in enumerate(pattern):
                velocity = min(127, base_velocity + (5 if idx % 2 == 0 else -2))
                notes.append(NoteEvent(
                    pitch=pitch,
                    start_tick=bar_offset + idx * TICKS_PER_8TH,
                    duration_ticks=TICKS_PER_8TH - 20,
                    velocity=max(1, velocity),
                    channel=1,
                ))

        return notes

    def generate_chords(
        self,
        section: SongSection,
        parsed: ParsedPrompt,
        tension: float = 0.5,
    ) -> List[NoteEvent]:
        """Generate guitar-range power chords (root/fifth/octave)."""
        if not section.config.enable_chords:
            return []

        notes: List[NoteEvent] = []
        vel_mult = self._tension_multiplier(tension, 0.90, 1.12)
        base_velocity = self._clamp_velocity(
            88 * (0.92 + section.config.instrument_density * 0.16) * vel_mult
        )
        strum_offsets = [0]
        if section.section_type in [SectionType.CHORUS, SectionType.BRIDGE, SectionType.DROP, SectionType.VARIATION]:
            strum_offsets = [0, beats_to_ticks(2)]

        for bar in range(section.bars):
            root = self._section_root(parsed, section.section_type, bar, octave=3)
            chord_pitches = [
                root,
                self._fit_range(root + 7, 45, 71),
                self._fit_range(root + 12, 52, 76),
            ]
            bar_offset = section.start_tick + bar * TICKS_PER_BAR_4_4
            duration = TICKS_PER_BAR_4_4 if len(strum_offsets) == 1 else beats_to_ticks(2)

            for strum_idx, strum_offset in enumerate(strum_offsets):
                velocity = min(127, base_velocity + (6 if strum_idx == 0 else 0))
                for pitch in chord_pitches:
                    notes.append(NoteEvent(
                        pitch=pitch,
                        start_tick=bar_offset + strum_offset,
                        duration_ticks=duration,
                        velocity=velocity,
                        channel=2,
                    ))

        return notes

    def _get_pattern(self, pattern_type: PatternType, name: str) -> Optional[Pattern]:
        for pattern in self._patterns.get_patterns('rock', pattern_type):
            if pattern.name == name:
                return pattern
        return None

    def _repeat_drum_pattern(
        self,
        pattern: Pattern,
        section: SongSection,
        velocity_scale: float,
    ) -> List[NoteEvent]:
        notes: List[NoteEvent] = []
        for bar in range(section.bars):
            bar_offset = section.start_tick + bar * TICKS_PER_BAR_4_4
            for tick, dur, pitch, vel in pattern.notes:
                if tick >= TICKS_PER_BAR_4_4:
                    continue
                if not self._drum_pitch_enabled(pitch, section):
                    continue
                notes.append(NoteEvent(
                    pitch=pitch,
                    start_tick=bar_offset + tick,
                    duration_ticks=dur,
                    velocity=self._clamp_velocity(vel * velocity_scale),
                    channel=GM_DRUM_CHANNEL,
                ))
        return notes

    def _fallback_backbeat(
        self,
        section: SongSection,
        density: float,
        vel_mult: float,
    ) -> List[NoteEvent]:
        notes: List[NoteEvent] = []
        for bar in range(section.bars):
            bar_offset = section.start_tick + bar * TICKS_PER_BAR_4_4

            if section.config.enable_kick:
                for pos in [0.0, 2.0]:
                    notes.append(NoteEvent(
                        pitch=GM_DRUM_NOTES['kick'],
                        start_tick=bar_offset + beats_to_ticks(pos),
                        duration_ticks=TICKS_PER_8TH,
                        velocity=self._clamp_velocity(108 * density * vel_mult),
                        channel=GM_DRUM_CHANNEL,
                    ))

            if section.config.enable_snare:
                for pos in [1.0, 3.0]:
                    notes.append(NoteEvent(
                        pitch=GM_DRUM_NOTES['snare'],
                        start_tick=bar_offset + beats_to_ticks(pos),
                        duration_ticks=TICKS_PER_8TH,
                        velocity=self._clamp_velocity(112 * density * vel_mult),
                        channel=GM_DRUM_CHANNEL,
                    ))

            if section.config.enable_hihat:
                for eighth in range(8):
                    notes.append(NoteEvent(
                        pitch=GM_DRUM_NOTES['hihat_closed'],
                        start_tick=bar_offset + eighth * TICKS_PER_8TH,
                        duration_ticks=TICKS_PER_16TH,
                        velocity=self._clamp_velocity((82 if eighth % 2 == 0 else 72) * density * vel_mult),
                        channel=GM_DRUM_CHANNEL,
                    ))
        return notes

    def _add_high_energy_kit_accents(
        self,
        section: SongSection,
        density: float,
        vel_mult: float,
    ) -> List[NoteEvent]:
        notes: List[NoteEvent] = []

        if section.config.enable_hihat:
            notes.append(NoteEvent(
                pitch=GM_DRUM_NOTES['crash'],
                start_tick=section.start_tick,
                duration_ticks=TICKS_PER_BEAT,
                velocity=self._clamp_velocity(112 * density * vel_mult),
                channel=GM_DRUM_CHANNEL,
            ))

            for bar in range(section.bars):
                bar_offset = section.start_tick + bar * TICKS_PER_BAR_4_4
                # Ride accents reinforce chorus/bridge energy without hi-hat rolls.
                for beat in [0, 1, 2, 3]:
                    notes.append(NoteEvent(
                        pitch=GM_DRUM_NOTES['ride'],
                        start_tick=bar_offset + beat * TICKS_PER_BEAT,
                        duration_ticks=TICKS_PER_8TH,
                        velocity=self._clamp_velocity(76 * density * vel_mult),
                        channel=GM_DRUM_CHANNEL,
                    ))
                for pos in [1.5, 3.5]:
                    notes.append(NoteEvent(
                        pitch=GM_DRUM_NOTES['hihat_open'],
                        start_tick=bar_offset + beats_to_ticks(pos),
                        duration_ticks=TICKS_PER_8TH,
                        velocity=self._clamp_velocity(78 * density * vel_mult),
                        channel=GM_DRUM_CHANNEL,
                    ))

        fill_pattern = self._get_pattern(PatternType.FILL, 'rock_fill_crash_cymbal')
        if section.config.enable_snare and fill_pattern is not None and section.bars > 0:
            last_bar_offset = section.start_tick + (section.bars - 1) * TICKS_PER_BAR_4_4
            for tick, dur, pitch, vel in fill_pattern.notes:
                if tick >= TICKS_PER_BAR_4_4:
                    continue
                if pitch == GM_DRUM_NOTES['clap']:
                    continue
                notes.append(NoteEvent(
                    pitch=pitch,
                    start_tick=last_bar_offset + tick,
                    duration_ticks=dur,
                    velocity=self._clamp_velocity(vel * (0.92 + density * 0.16) * vel_mult),
                    channel=GM_DRUM_CHANNEL,
                ))

        return notes

    def _drum_pitch_enabled(self, pitch: int, section: SongSection) -> bool:
        if pitch == GM_DRUM_NOTES['clap']:
            return False
        if pitch in self._KICK_PITCHES:
            return section.config.enable_kick
        if pitch in self._SNARE_PITCHES:
            return section.config.enable_snare
        if pitch in self._HIHAT_PITCHES:
            return section.config.enable_hihat
        return True

    def _is_high_energy(self, section: SongSection) -> bool:
        return section.section_type in [
            SectionType.CHORUS,
            SectionType.DROP,
            SectionType.BRIDGE,
            SectionType.VARIATION,
            SectionType.BUILDUP,
        ]

    def _section_root(
        self,
        parsed: ParsedPrompt,
        section_type: SectionType,
        bar: int,
        octave: int,
    ) -> int:
        root = self._safe_root(parsed.key, octave)
        offsets = self._progression_offsets(section_type)
        shifted = root + offsets[bar % len(offsets)]
        return self._fit_range(shifted, 36 if octave <= 2 else 45, 55 if octave <= 2 else 64)

    def _progression_offsets(self, section_type: SectionType) -> List[int]:
        if section_type == SectionType.CHORUS:
            return [0, 7, 5, 3]
        if section_type == SectionType.BRIDGE:
            return [5, 3, 0, 7]
        if section_type in [SectionType.OUTRO, SectionType.INTRO]:
            return [0, 5, 0, 7]
        return [0, 0, 5, 7]

    def _safe_root(self, key: str, octave: int) -> int:
        try:
            return note_name_to_midi(key or 'C', octave)
        except Exception:
            return note_name_to_midi('C', octave)

    def _fit_range(self, pitch: int, low: int, high: int) -> int:
        while pitch < low:
            pitch += 12
        while pitch > high:
            pitch -= 12
        return max(low, min(high, pitch))

    def _clamp_velocity(self, value: float) -> int:
        return max(1, min(127, int(round(value))))