"""Focused regressions for guitar chord-track MIDI routing."""

from mido import MidiFile, MidiTrack

from multimodal_gen.arranger import Arrangement, SECTION_CONFIGS, SectionType, SongSection
from multimodal_gen.midi_generator import MidiGenerator
from multimodal_gen.prompt_parser import ParsedPrompt
from multimodal_gen.utils import ScaleType, TICKS_PER_BAR_4_4


EXACT_1990S_ROCK_PROMPT = (
    "1990's era rock song with crunchy electric guitar, live drums, "
    "bass guitar, verse chorus bridge, energetic band performance, "
    "100 BPM in E minor"
)


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
    return _track_by_name(mid, "Chords")


def _bass_track(mid: MidiFile) -> MidiTrack:
    return _track_by_name(mid, "Bass")


def _track_by_name(mid: MidiFile, name: str) -> MidiTrack:
    for track in mid.tracks:
        if any(msg.type == "track_name" and msg.name == name for msg in track):
            return track
    raise AssertionError(f"{name} track not found")


def _channel_2_program(track: MidiTrack) -> int:
    return _channel_program(track, 2)


def _channel_program(track: MidiTrack, channel: int) -> int:
    programs = [msg.program for msg in track if msg.type == "program_change" and msg.channel == channel]
    assert len(programs) == 1
    return programs[0]


def _channel_1_program(track: MidiTrack) -> int:
    return _channel_program(track, 1)


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


def test_exact_1990s_rock_prompt_bass_track_uses_electric_bass_guitar_not_synth_bass():
    parsed = ParsedPrompt(
        genre="rock",
        bpm=100,
        key="E",
        scale_type=ScaleType.MINOR,
        instruments=["electric guitar", "bass guitar"],
        drum_elements=["kick", "snare", "hihat"],
        raw_prompt=EXACT_1990S_ROCK_PROMPT,
    )

    mid = MidiGenerator(use_physics_humanization=False).generate(_one_bar_arrangement(), parsed)
    bass = _bass_track(mid)
    program = _channel_1_program(bass)
    text_markers = [msg.text for msg in bass if msg.type == "text"]

    assert program == 34
    assert program in {33, 34}
    assert program not in {38, 39}
    assert "instrument:Bass Guitar" in text_markers


def test_non_rock_bass_track_preserves_synth_bass_program():
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
    program = _channel_1_program(_bass_track(mid))

    assert program == 38


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
