"""Focused regressions for R&B/neo-soul MIDI semantics."""

from mido import MidiFile, MidiTrack

from multimodal_gen.arranger import Arrangement, SECTION_CONFIGS, SectionType, SongSection
from multimodal_gen.midi_generator import MidiGenerator
from multimodal_gen.prompt_parser import PromptParser
from multimodal_gen.utils import TICKS_PER_BAR_4_4


TASK_065_PROMPT = (
    "neo-soul R&B groove with warm electric piano, bass, laid-back drums, "
    "lush chords, 82 BPM in F minor"
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
        bpm=82,
        time_signature=(4, 4),
    )


def _track_names(mid: MidiFile) -> list[str]:
    return [msg.name for track in mid.tracks for msg in track if msg.type == "track_name"]


def _track_by_name(mid: MidiFile, name: str) -> MidiTrack:
    for track in mid.tracks:
        if any(msg.type == "track_name" and msg.name == name for msg in track):
            return track
    raise AssertionError(f"{name} track not found")


def _channel_program(track: MidiTrack, channel: int) -> int:
    programs = [msg.program for msg in track if msg.type == "program_change" and msg.channel == channel]
    assert len(programs) == 1
    return programs[0]


def _text_markers(track: MidiTrack) -> list[str]:
    return [msg.text for msg in track if msg.type == "text"]


def test_neo_soul_bass_uses_electric_bass_and_no_default_melody():
    parsed = PromptParser().parse(TASK_065_PROMPT)

    mid = MidiGenerator(use_physics_humanization=False).generate(_one_bar_arrangement(), parsed)
    bass = _track_by_name(mid, "Bass")
    chords = _track_by_name(mid, "Chords")

    assert parsed.genre == "neo_soul"
    assert _channel_program(bass, 1) in {33, 34}
    assert _channel_program(bass, 1) != 38
    assert "instrument:Bass Guitar" in _text_markers(bass)
    assert _channel_program(chords, 2) == 4
    assert "Melody" not in _track_names(mid)


def test_neo_soul_explicit_hook_keeps_melody_track():
    parsed = PromptParser().parse(TASK_065_PROMPT + " with a vocal chop hook")

    mid = MidiGenerator(use_physics_humanization=False).generate(_one_bar_arrangement(), parsed)

    assert "Melody" in _track_names(mid)