"""Regression-style musicality tests over generated MIDI.

These are intentionally lightweight and deterministic-ish. They ensure we keep
basic musicality behaviors (density/velocity shaping) as new features land.
"""

import random
import sys
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from multimodal_gen.prompt_parser import PromptParser
from multimodal_gen.arranger import Arrangement, SongSection, SectionType, SECTION_CONFIGS
from multimodal_gen.midi_generator import MidiGenerator, TICKS_PER_BEAT, HAS_PHYSICS_HUMANIZER


def _extract_note_ons(track):
    abs_tick = 0
    events = []
    for msg in track:
        abs_tick += getattr(msg, "time", 0)
        if msg.type == "note_on" and msg.velocity and msg.velocity > 0:
            events.append((abs_tick, msg.note, msg.velocity))
    return events


def _extract_note_intervals(track):
    """Return (start_tick, end_tick, pitch) for note pairs in a single track."""
    abs_tick = 0
    active = {}
    intervals = []
    for msg in track:
        abs_tick += getattr(msg, "time", 0)
        if msg.type == "note_on" and msg.velocity and msg.velocity > 0:
            # For drums it is possible to retrigger, but we still treat this as an overlap.
            if msg.note not in active:
                active[msg.note] = abs_tick
        elif msg.type in ("note_off", "note_on") and (msg.type == "note_off" or msg.velocity == 0):
            if msg.note in active:
                start = active.pop(msg.note)
                intervals.append((start, abs_tick, msg.note))
    return intervals


class TestMusicalityMetrics:
    def test_section_density_changes(self):
        """Chorus should be noticeably denser than breakdown in drums."""
        random.seed(1337)

        parsed = PromptParser().parse("hip hop beat 92 bpm in C minor")

        ticks_per_bar = 4 * TICKS_PER_BEAT
        bars = 8
        breakdown_ticks = bars * ticks_per_bar
        chorus_ticks = bars * ticks_per_bar

        sections = [
            SongSection(
                section_type=SectionType.BREAKDOWN,
                start_tick=0,
                end_tick=breakdown_ticks,
                bars=bars,
                config=SECTION_CONFIGS[SectionType.BREAKDOWN],
            ),
            SongSection(
                section_type=SectionType.CHORUS,
                start_tick=breakdown_ticks,
                end_tick=breakdown_ticks + chorus_ticks,
                bars=bars,
                config=SECTION_CONFIGS[SectionType.CHORUS],
            ),
        ]

        arrangement = Arrangement(
            sections=sections,
            total_bars=bars * 2,
            total_ticks=breakdown_ticks + chorus_ticks,
            bpm=float(parsed.bpm or 92),
            time_signature=(4, 4),
        )

        mid = MidiGenerator().generate(arrangement, parsed)
        drum_track = next((t for t in mid.tracks if (t.name or "").lower() == "drums"), mid.tracks[1])

        events = _extract_note_ons(drum_track)
        assert events, "Expected drum notes to be generated"

        breakdown_count = sum(1 for t, _n, _v in events if 0 <= t < breakdown_ticks)
        chorus_count = sum(1 for t, _n, _v in events if breakdown_ticks <= t < breakdown_ticks + chorus_ticks)

        # Chorus should have clearly more drum events than breakdown.
        # Margin accounts for transition fills at section boundaries.
        assert chorus_count > breakdown_count * 1.15

    def test_velocity_distribution_not_collapsed(self):
        """Generated drums should not be a single repeated velocity."""
        random.seed(2025)

        parsed = PromptParser().parse("hip hop beat 92 bpm in C minor")

        ticks_per_bar = 4 * TICKS_PER_BEAT
        bars = 8
        total_ticks = bars * ticks_per_bar

        section = SongSection(
            section_type=SectionType.CHORUS,
            start_tick=0,
            end_tick=total_ticks,
            bars=bars,
            config=SECTION_CONFIGS[SectionType.CHORUS],
        )
        arrangement = Arrangement(
            sections=[section],
            total_bars=bars,
            total_ticks=total_ticks,
            bpm=float(parsed.bpm or 92),
            time_signature=(4, 4),
        )

        mid = MidiGenerator().generate(arrangement, parsed)
        drum_track = next((t for t in mid.tracks if (t.name or "").lower() == "drums"), mid.tracks[1])

        velocities = [v for _t, _n, v in _extract_note_ons(drum_track)]
        assert velocities, "Expected drum notes to be generated"
        assert len(set(velocities)) > 1

    @pytest.mark.skipif(not HAS_PHYSICS_HUMANIZER, reason="Physics humanizer module not available")
    def test_no_overlapping_same_drum_hit_when_physics_enabled(self):
        """With physics humanization enabled, avoid overlapping same-pitch drum hits."""
        random.seed(7)

        parsed = PromptParser().parse("hip hop beat 92 bpm in C minor")

        ticks_per_bar = 4 * TICKS_PER_BEAT
        bars = 8
        total_ticks = bars * ticks_per_bar

        section = SongSection(
            section_type=SectionType.CHORUS,
            start_tick=0,
            end_tick=total_ticks,
            bars=bars,
            config=SECTION_CONFIGS[SectionType.CHORUS],
        )
        arrangement = Arrangement(
            sections=[section],
            total_bars=bars,
            total_ticks=total_ticks,
            bpm=float(parsed.bpm or 92),
            time_signature=(4, 4),
        )

        mid = MidiGenerator(use_physics_humanization=True).generate(arrangement, parsed)
        drum_track = next((t for t in mid.tracks if (t.name or "").lower() == "drums"), mid.tracks[1])

        intervals = _extract_note_intervals(drum_track)
        assert intervals, "Expected drum notes to be generated"

        by_pitch = {}
        for start, end, pitch in intervals:
            by_pitch.setdefault(pitch, []).append((start, end))

        for pitch, spans in by_pitch.items():
            spans.sort(key=lambda x: x[0])
            for i in range(1, len(spans)):
                prev_start, prev_end = spans[i - 1]
                cur_start, _cur_end = spans[i]
                assert cur_start >= prev_end
