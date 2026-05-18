"""Focused regressions for lofi/boom-bap MIDI/session parity."""

from mido import MidiFile

from multimodal_gen.arranger import Arrangement, SECTION_CONFIGS, SectionType, SongSection
from multimodal_gen.midi_generator import MidiGenerator
from multimodal_gen.prompt_parser import PromptParser
from multimodal_gen.utils import TICKS_PER_BAR_4_4


TASK_066_PROMPT = (
    "lofi boom bap groove with dusty drums, warm bass, mellow keys, "
    "vinyl texture, 88 BPM in C minor"
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
        bpm=88,
        time_signature=(4, 4),
    )


def _track_names(mid: MidiFile) -> list[str]:
    return [msg.name for track in mid.tracks for msg in track if msg.type == "track_name"]


def test_boom_bap_baseline_has_rhythm_section_chords_and_no_default_melody():
    parsed = PromptParser().parse(TASK_066_PROMPT)

    mid = MidiGenerator(use_physics_humanization=False).generate(_one_bar_arrangement(), parsed)
    names = _track_names(mid)

    assert parsed.genre == "boom_bap"
    assert "Drums" in names
    assert "Bass" in names
    assert "Chords" in names
    assert "Melody" not in names


def test_boom_bap_explicit_hook_melody_keeps_melody_track():
    parsed = PromptParser().parse(TASK_066_PROMPT + " with a hook melody")

    mid = MidiGenerator(use_physics_humanization=False).generate(_one_bar_arrangement(), parsed)

    assert "Melody" in _track_names(mid)