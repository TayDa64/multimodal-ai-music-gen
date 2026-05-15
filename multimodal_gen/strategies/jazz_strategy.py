"""Generic jazz strategy - swing ride pattern, walking bass, and piano comping."""
from typing import List

from .base import DrumConfig, GenreStrategy
from ..arranger import SectionType, SongSection
from ..midi_generator import NoteEvent
from ..prompt_parser import ParsedPrompt
from ..utils import (
    GM_DRUM_CHANNEL,
    GM_DRUM_NOTES,
    ScaleType,
    TICKS_PER_8TH,
    TICKS_PER_16TH,
    TICKS_PER_BAR_4_4,
    TICKS_PER_BEAT,
    beats_to_ticks,
    note_name_to_midi,
)


class JazzStrategy(GenreStrategy):
    """Small-combo jazz strategy that avoids trap/808 signatures."""

    @property
    def genre_name(self) -> str:
        return 'jazz'

    @property
    def supported_genres(self) -> List[str]:
        return ['jazz']

    def get_default_config(self) -> DrumConfig:
        return DrumConfig(
            base_velocity=84,
            swing=0.12,
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
        """Generate a ride-led acoustic jazz kit pattern on the GM drum channel."""
        notes: List[NoteEvent] = []
        density = self._get_effective_drum_density(section.config.drum_density, parsed)
        vel_mult = self._tension_multiplier(tension, 0.88, 1.08)
        swing_ticks = int(TICKS_PER_16TH * 0.45)

        for bar in range(section.bars):
            bar_offset = section.start_tick + bar * TICKS_PER_BAR_4_4

            if section.config.enable_hihat:
                # Ride cymbal quarter-note pulse with swung skips into 2 and 4.
                for beat in range(4):
                    notes.append(NoteEvent(
                        pitch=GM_DRUM_NOTES['ride'],
                        start_tick=bar_offset + beat * TICKS_PER_BEAT,
                        duration_ticks=TICKS_PER_8TH,
                        velocity=self._clamp_velocity(76 * density * vel_mult),
                        channel=GM_DRUM_CHANNEL,
                    ))
                for beat in [1, 3]:
                    notes.append(NoteEvent(
                        pitch=GM_DRUM_NOTES['hihat_pedal'],
                        start_tick=bar_offset + beat * TICKS_PER_BEAT,
                        duration_ticks=TICKS_PER_16TH,
                        velocity=self._clamp_velocity(62 * density * vel_mult),
                        channel=GM_DRUM_CHANNEL,
                    ))
                for beat in [0, 2]:
                    notes.append(NoteEvent(
                        pitch=GM_DRUM_NOTES['ride'],
                        start_tick=bar_offset + beat * TICKS_PER_BEAT + TICKS_PER_8TH + swing_ticks,
                        duration_ticks=TICKS_PER_16TH,
                        velocity=self._clamp_velocity(56 * density * vel_mult),
                        channel=GM_DRUM_CHANNEL,
                    ))

            if section.config.enable_kick:
                for beat in range(4):
                    notes.append(NoteEvent(
                        pitch=GM_DRUM_NOTES['kick'],
                        start_tick=bar_offset + beat * TICKS_PER_BEAT,
                        duration_ticks=TICKS_PER_8TH,
                        velocity=self._clamp_velocity(48 * density * vel_mult),
                        channel=GM_DRUM_CHANNEL,
                    ))

            if section.config.enable_snare:
                for beat in [1, 3]:
                    notes.append(NoteEvent(
                        pitch=GM_DRUM_NOTES['snare'],
                        start_tick=bar_offset + beat * TICKS_PER_BEAT,
                        duration_ticks=TICKS_PER_8TH,
                        velocity=self._clamp_velocity(54 * density * vel_mult),
                        channel=GM_DRUM_CHANNEL,
                    ))
                if density >= 0.45:
                    for pos in [1.75, 3.5]:
                        notes.append(NoteEvent(
                            pitch=GM_DRUM_NOTES['snare_rim'],
                            start_tick=bar_offset + beats_to_ticks(pos),
                            duration_ticks=TICKS_PER_16TH,
                            velocity=self._clamp_velocity(38 * density * vel_mult),
                            channel=GM_DRUM_CHANNEL,
                        ))

        notes.sort(key=lambda n: (n.start_tick, n.pitch))
        return notes

    def generate_bass(
        self,
        section: SongSection,
        parsed: ParsedPrompt,
        tension: float = 0.5,
    ) -> List[NoteEvent]:
        """Generate quarter-note walking acoustic-bass motion."""
        if not section.config.enable_bass:
            return []

        notes: List[NoteEvent] = []
        vel_mult = self._tension_multiplier(tension, 0.90, 1.08)
        intervals = self._walking_intervals(parsed)

        for bar in range(section.bars):
            root = self._section_root(parsed, section.section_type, bar, octave=2)
            bar_offset = section.start_tick + bar * TICKS_PER_BAR_4_4
            for beat, interval in enumerate(intervals):
                pitch = self._fit_range(root + interval, 32, 55)
                notes.append(NoteEvent(
                    pitch=pitch,
                    start_tick=bar_offset + beat * TICKS_PER_BEAT,
                    duration_ticks=TICKS_PER_BEAT - 30,
                    velocity=self._clamp_velocity((72 + (4 if beat == 0 else 0)) * vel_mult),
                    channel=1,
                ))

        return notes

    def generate_chords(
        self,
        section: SongSection,
        parsed: ParsedPrompt,
        tension: float = 0.5,
    ) -> List[NoteEvent]:
        """Generate sparse piano comping voicings."""
        if not section.config.enable_chords:
            return []

        notes: List[NoteEvent] = []
        vel_mult = self._tension_multiplier(tension, 0.88, 1.08)
        voicing = self._comping_voicing(parsed)
        comp_offsets = [0, beats_to_ticks(2.0)]
        if section.section_type in [SectionType.CHORUS, SectionType.BRIDGE, SectionType.VARIATION]:
            comp_offsets = [beats_to_ticks(0.5), beats_to_ticks(2.0), beats_to_ticks(3.0)]

        for bar in range(section.bars):
            root = self._section_root(parsed, section.section_type, bar, octave=3)
            pitches = [self._fit_range(root + interval, 48, 76) for interval in voicing]
            bar_offset = section.start_tick + bar * TICKS_PER_BAR_4_4
            for offset_idx, offset in enumerate(comp_offsets):
                velocity = self._clamp_velocity((64 + (4 if offset_idx == 0 else 0)) * vel_mult)
                for pitch in pitches:
                    notes.append(NoteEvent(
                        pitch=pitch,
                        start_tick=bar_offset + offset,
                        duration_ticks=beats_to_ticks(1.25),
                        velocity=velocity,
                        channel=2,
                    ))

        return notes

    def _walking_intervals(self, parsed: ParsedPrompt) -> List[int]:
        if getattr(parsed, 'scale_type', None) == ScaleType.MAJOR:
            return [0, 4, 7, 10]
        return [0, 3, 7, 10]

    def _comping_voicing(self, parsed: ParsedPrompt) -> List[int]:
        if getattr(parsed, 'scale_type', None) == ScaleType.MAJOR:
            return [4, 10, 14]
        return [3, 10, 14]

    def _section_root(
        self,
        parsed: ParsedPrompt,
        section_type: SectionType,
        bar: int,
        octave: int,
    ) -> int:
        root = self._safe_root(parsed.key, octave)
        offsets = self._progression_offsets(section_type)
        return self._fit_range(root + offsets[bar % len(offsets)], 32 if octave <= 2 else 48, 55 if octave <= 2 else 66)

    def _progression_offsets(self, section_type: SectionType) -> List[int]:
        if section_type == SectionType.BRIDGE:
            return [5, 7, 3, 2]
        if section_type == SectionType.CHORUS:
            return [0, 5, 7, 0]
        if section_type in [SectionType.INTRO, SectionType.OUTRO]:
            return [0, 2, 5, 7]
        return [0, 5, 2, 7]

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