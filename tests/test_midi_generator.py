"""Focused regressions for guitar chord-track MIDI routing."""

from mido import MidiFile, MidiTrack

from multimodal_gen.arranger import Arrangement, SECTION_CONFIGS, SectionType, SongSection
from multimodal_gen.midi_generator import MidiGenerator
from multimodal_gen.prompt_parser import ParsedPrompt
from multimodal_gen.utils import ScaleType, TICKS_PER_BAR_4_4


def _one_bar_arrangement() -> Arrangement:
    section = SongSection(
        section_type=SectionType.VERSE,
        start_tick=0,
        end_tick=TICKS_PER_BAR_4_4,
        bars=1,
        config=SECTION_CONFIGS[SectionType.VERSE],
    )
    return Arrangement(
        sections=[section],
        total_bars=1,
        total_ticks=TICKS_PER_BAR_4_4,
        bpm=100,
        time_signature=(4, 4),
    )


def _chords_track(mid: MidiFile) -> MidiTrack:
    for track in mid.tracks:
        if any(msg.type == "track_name" and msg.name == "Chords" for msg in track):
            return track
    raise AssertionError("Chords track not found")


def _channel_2_program(track: MidiTrack) -> int:
    programs = [msg.program for msg in track if msg.type == "program_change" and msg.channel == 2]
    assert len(programs) == 1
    return programs[0]


def test_rock_guitar_prompt_creates_guitar_chord_track_not_rhodes():
    parsed = ParsedPrompt(
        genre="rock",
        bpm=100,
        key="E",
        scale_type=ScaleType.MINOR,
        instruments=["guitar", "bass"],
        drum_elements=["kick", "snare", "hihat"],
        raw_prompt="1990s rock with crunchy electric guitar and bass guitar",
    )

    mid = MidiGenerator(use_physics_humanization=False).generate(_one_bar_arrangement(), parsed)
    chords = _chords_track(mid)
    program = _channel_2_program(chords)
    text_markers = [msg.text for msg in chords if msg.type == "text"]

    assert 24 <= program <= 31
    assert program == 30
    assert program != 4
    assert "instrument:Guitar" in text_markers


def test_non_guitar_rhodes_prompt_still_uses_rhodes_program():
    parsed = ParsedPrompt(
        genre="rnb",
        bpm=88,
        key="D",
        scale_type=ScaleType.MINOR,
        instruments=["rhodes", "bass"],
        drum_elements=["kick", "snare", "hihat"],
        raw_prompt="warm rnb rhodes and bass groove",
    )

    mid = MidiGenerator(use_physics_humanization=False).generate(_one_bar_arrangement(), parsed)
    program = _channel_2_program(_chords_track(mid))

    assert program == 4
