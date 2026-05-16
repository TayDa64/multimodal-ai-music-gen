"""Focused regressions for guitar chord-track MIDI routing."""

from mido import MidiFile, MidiTrack

from multimodal_gen.arranger import Arrangement, SECTION_CONFIGS, SectionType, SongSection
from multimodal_gen.instrument_ranges import get_melody_octave, get_range
from multimodal_gen.instrument_resolution import InstrumentResolutionService
from multimodal_gen.midi_generator import (
    JAZZ_CHORD_CC74_CAP,
    JAZZ_HORN_MELODY_VELOCITY_CAP,
    JAZZ_SAX_MELODY_CC74_CAP,
    MidiGenerator,
)
from multimodal_gen.prompt_parser import ParsedPrompt
from multimodal_gen.prompt_parser import PromptParser
from multimodal_gen.tension_arc import TensionArc, TensionPoint
from multimodal_gen.utils import ScaleType, TICKS_PER_BAR_4_4


EXACT_1990S_ROCK_PROMPT = (
    "1990's era rock song with crunchy electric guitar, live drums, "
    "bass guitar, verse chorus bridge, energetic band performance, "
    "100 BPM in E minor"
)


def _one_bar_arrangement(section_type: SectionType = SectionType.VERSE) -> Arrangement:
    section = SongSection(
        section_type=section_type,
        start_tick=0,
        end_tick=TICKS_PER_BAR_4_4,
        bars=1,
        config=SECTION_CONFIGS[section_type],
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


def _melody_track(mid: MidiFile) -> MidiTrack:
    return _track_by_name(mid, "Melody")


def _organ_track(mid: MidiFile) -> MidiTrack:
    return _track_by_name(mid, "Organ")


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


def _channel_3_program(track: MidiTrack) -> int:
    return _channel_program(track, 3)


def _channel_4_program(track: MidiTrack) -> int:
    return _channel_program(track, 4)


def _text_markers(track: MidiTrack) -> list[str]:
    return [msg.text for msg in track if msg.type == "text"]


def _note_on_velocities(track: MidiTrack) -> list[int]:
    return [msg.velocity for msg in track if msg.type == "note_on" and msg.velocity > 0]


def _note_on_pitches(track: MidiTrack) -> list[int]:
    return [msg.note for msg in track if msg.type == "note_on" and msg.velocity > 0]


def _cc_values(track: MidiTrack, control: int) -> list[int]:
    return [msg.value for msg in track if msg.type == "control_change" and msg.control == control]


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


def test_classic_rock_hammond_prompt_keeps_guitar_chords_and_adds_organ_bed():
    parsed = PromptParser().parse(
        "classic rock anthem with crunchy electric guitar, Hammond organ, "
        "melodic bass guitar, live drums, verse chorus bridge, 108 BPM in A minor"
    )

    mid = MidiGenerator(use_physics_humanization=False).generate(
        _one_bar_arrangement(SectionType.CHORUS),
        parsed,
    )
    chords = _chords_track(mid)
    organ = _organ_track(mid)
    bass = _bass_track(mid)

    assert parsed.genre == "classic_rock"
    assert {"guitar", "bass", "organ"}.issubset(set(parsed.instruments))
    assert _channel_2_program(chords) == 30
    assert "instrument:Guitar" in _text_markers(chords)
    assert _channel_4_program(organ) == 16
    assert "instrument:Organ" in _text_markers(organ)
    assert _note_on_pitches(organ)
    assert _channel_1_program(bass) == 34


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


def test_exact_jazz_sax_prompt_uses_sax_melody_program_and_capped_velocity():
    parsed = PromptParser().parse(
        "small-combo jazz quartet with walking upright bass, ride cymbal swing, "
        "acoustic piano comping, warm saxophone lead, 120 BPM in Bb major"
    )

    arrangement = _one_bar_arrangement(SectionType.CHORUS)
    arrangement.tension_arc = TensionArc(points=[TensionPoint(0.0, 0.95), TensionPoint(1.0, 0.95)])
    mid = MidiGenerator(use_physics_humanization=False).generate(arrangement, parsed)
    chords = _chords_track(mid)
    melody = _melody_track(mid)
    chord_cc74_values = _cc_values(chords, 74)
    chord_cc11_values = _cc_values(chords, 11)
    program = _channel_3_program(melody)
    velocities = _note_on_velocities(melody)
    pitches = _note_on_pitches(melody)
    cc1_values = _cc_values(melody, 1)
    cc11_values = _cc_values(melody, 11)
    cc74_values = _cc_values(melody, 74)

    assert program == 65
    assert program != 56
    assert "instrument:Sax" in _text_markers(melody)
    assert velocities
    assert max(velocities) <= JAZZ_HORN_MELODY_VELOCITY_CAP
    assert JAZZ_HORN_MELODY_VELOCITY_CAP < 127
    assert pitches
    assert max(pitches) <= 80
    assert cc1_values
    assert cc11_values
    assert cc74_values
    assert max(cc74_values) <= JAZZ_SAX_MELODY_CC74_CAP
    assert _channel_2_program(chords) == 0
    assert "instrument:Piano" in _text_markers(chords)
    assert max(_note_on_pitches(chords)) <= 76
    assert chord_cc11_values
    assert chord_cc74_values
    assert max(chord_cc74_values) <= JAZZ_CHORD_CC74_CAP


def test_jazz_tenor_sax_uses_lower_register_and_program_than_generic_sax():
    parsed = ParsedPrompt(
        genre="jazz",
        bpm=120,
        key="Bb",
        scale_type=ScaleType.MAJOR,
        instruments=["tenor_sax"],
        drum_elements=["kick", "snare", "hihat", "ride"],
        raw_prompt="small combo jazz with warm tenor saxophone lead",
    )

    mid = MidiGenerator(use_physics_humanization=False).generate(_one_bar_arrangement(SectionType.CHORUS), parsed)
    melody = _melody_track(mid)

    assert _channel_3_program(melody) == 66
    assert "instrument:Tenor Sax" in _text_markers(melody)
    assert max(_note_on_pitches(melody)) <= get_range("tenor sax").sweet_high
    assert get_melody_octave("tenor sax") < get_melody_octave("sax")


def test_jazz_trombone_and_flute_melody_programs_remain_distinct():
    trombone = ParsedPrompt(
        genre="jazz",
        bpm=120,
        key="Bb",
        scale_type=ScaleType.MAJOR,
        instruments=["trombone"],
        drum_elements=["kick", "snare", "hihat", "ride"],
        raw_prompt="jazz quartet with trombone lead",
    )
    flute = ParsedPrompt(
        genre="jazz",
        bpm=120,
        key="Bb",
        scale_type=ScaleType.MAJOR,
        instruments=["flute"],
        drum_elements=["kick", "snare", "hihat", "ride"],
        raw_prompt="jazz quartet with flute lead",
    )

    trombone_program = _channel_3_program(
        _melody_track(MidiGenerator(use_physics_humanization=False).generate(_one_bar_arrangement(SectionType.CHORUS), trombone))
    )
    flute_program = _channel_3_program(
        _melody_track(MidiGenerator(use_physics_humanization=False).generate(_one_bar_arrangement(SectionType.CHORUS), flute))
    )

    assert trombone_program == 57
    assert flute_program == 73


def test_jazz_trumpet_lead_and_generic_brass_melody_markers_are_distinct():
    trumpet = ParsedPrompt(
        genre="jazz",
        bpm=120,
        key="Bb",
        scale_type=ScaleType.MAJOR,
        instruments=["trumpet"],
        drum_elements=["kick", "snare", "hihat", "ride"],
        raw_prompt="jazz quartet with trumpet lead",
    )
    brass = ParsedPrompt(
        genre="jazz",
        bpm=120,
        key="Bb",
        scale_type=ScaleType.MAJOR,
        instruments=["brass"],
        drum_elements=["kick", "snare", "hihat", "ride"],
        raw_prompt="jazz quartet with brass section hits",
    )

    trumpet_track = _melody_track(
        MidiGenerator(use_physics_humanization=False).generate(_one_bar_arrangement(SectionType.CHORUS), trumpet)
    )
    brass_track = _melody_track(
        MidiGenerator(use_physics_humanization=False).generate(_one_bar_arrangement(SectionType.CHORUS), brass)
    )

    assert _channel_3_program(trumpet_track) == 56
    assert _channel_3_program(brass_track) == 56
    assert "instrument:Trumpet" in _text_markers(trumpet_track)
    assert "instrument:Brass" in _text_markers(brass_track)


def test_instrument_resolution_saxophone_aliases_resolve_to_gm_sax_programs():
    service = InstrumentResolutionService()

    assert service.resolve_instrument("saxophone").program == 65
    assert service.resolve_instrument("alto saxophone").program == 65
    assert service.resolve_instrument("tenor saxophone").program == 66
    assert service.get_instrument_for_program(65) == "alto_sax"
    assert service.get_instrument_for_program(66) == "tenor_sax"


def test_instrument_range_saxophone_aliases_use_warm_jazz_lead_octaves():
    for alias in ["sax", "saxophone", "saxes", "saxophones", "alto_sax", "alto sax", "alto_saxophone", "alto saxophone"]:
        sax_range = get_range(alias)
        assert sax_range.melody_octave == 4
        assert sax_range.high == 80

    for alias in ["tenor_sax", "tenor sax", "tenor_saxophone", "tenor saxophone"]:
        tenor_range = get_range(alias)
        assert tenor_range.melody_octave == 3
        assert tenor_range.high < get_range("sax").high
