"""Focused regressions for guitar chord-track MIDI routing."""

import random

from mido import MidiFile, MidiTrack

from multimodal_gen.arranger import Arrangement, Arranger, SECTION_CONFIGS, SectionType, SongSection
from multimodal_gen.instrument_ranges import get_melody_octave, get_range
from multimodal_gen.instrument_resolution import InstrumentResolutionService
from multimodal_gen.midi_generator import (
    JAZZ_CHORD_CC74_CAP,
    JAZZ_HORN_MELODY_VELOCITY_CAP,
    JAZZ_SAX_MELODY_CC74_CAP,
    MidiGenerator,
    generate_chord_progression_midi,
)
from multimodal_gen.prompt_parser import ParsedPrompt
from multimodal_gen.prompt_parser import PromptParser
from multimodal_gen.tension_arc import TensionArc, TensionPoint
from multimodal_gen.utils import GM_DRUM_NOTES, ScaleType, TICKS_PER_BAR_4_4


EXACT_1990S_ROCK_PROMPT = (
    "1990's era rock song with crunchy electric guitar, live drums, "
    "bass guitar, verse chorus bridge, energetic band performance, "
    "100 BPM in E minor"
)

LYRICAL_CINEMATIC_PIANO_PROMPT = (
    "cinematic orchestral score with lyrical piano, warm strings, flute, oboe, "
    "harp, and soft choir, emotional rising theme, 78 BPM in G major"
)

TASK_113_ESKISTA_PROMPT = (
    "eskista shoulder dance groove with kebero and bright washint riffs at 126 BPM "
    "in E minor with krar lead and masenqo answers"
)

TASK_127_TRADITIONAL_AMBASSEL_PROMPT = (
    "traditional Ethiopian ambassel groove with krar, washint, masenqo, kebero at 104 BPM"
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


def _piano_track(mid: MidiFile) -> MidiTrack:
    return _track_by_name(mid, "Piano")


def _melody_track(mid: MidiFile) -> MidiTrack:
    return _track_by_name(mid, "Melody")


def _organ_track(mid: MidiFile) -> MidiTrack:
    return _track_by_name(mid, "Organ")


def _strings_track(mid: MidiFile) -> MidiTrack:
    return _track_by_name(mid, "Strings")


def _track_by_name(mid: MidiFile, name: str) -> MidiTrack:
    for track in mid.tracks:
        if any(msg.type == "track_name" and msg.name == name for msg in track):
            return track
    raise AssertionError(f"{name} track not found")


def _track_names(mid: MidiFile) -> list[str]:
    return [
        msg.name
        for track in mid.tracks
        for msg in track
        if msg.type == "track_name"
    ]


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


def _channel_10_program(track: MidiTrack) -> int:
    return _channel_program(track, 10)


def _text_markers(track: MidiTrack) -> list[str]:
    return [msg.text for msg in track if msg.type == "text"]


def _note_on_velocities(track: MidiTrack) -> list[int]:
    return [msg.velocity for msg in track if msg.type == "note_on" and msg.velocity > 0]


def _note_on_pitches(track: MidiTrack) -> list[int]:
    return [msg.note for msg in track if msg.type == "note_on" and msg.velocity > 0]


def _note_on_pitches_by_absolute_tick(track: MidiTrack) -> dict[int, list[int]]:
    absolute_tick = 0
    grouped: dict[int, list[int]] = {}
    for msg in track:
        absolute_tick += msg.time
        if msg.type == "note_on" and msg.velocity > 0:
            grouped.setdefault(absolute_tick, []).append(msg.note)
    return grouped


def _note_on_bars(track: MidiTrack) -> set[int]:
    absolute_tick = 0
    bars: set[int] = set()
    for msg in track:
        absolute_tick += msg.time
        if msg.type == "note_on" and msg.velocity > 0:
            bars.add(absolute_tick // TICKS_PER_BAR_4_4)
    return bars


def _cc_values(track: MidiTrack, control: int) -> list[int]:
    return [msg.value for msg in track if msg.type == "control_change" and msg.control == control]


def _lowest_bar_start_pitches(pattern: list[tuple[int, int, int, int]], bars: int) -> list[int]:
    grouped: dict[int, list[int]] = {}
    for tick, _duration, pitch, _velocity in pattern:
        grouped.setdefault(tick, []).append(pitch)
    return [min(grouped[bar * TICKS_PER_BAR_4_4]) for bar in range(bars)]


def test_generate_chord_progression_midi_ambassel_default_progression_stays_safe_and_non_empty():
    pattern = generate_chord_progression_midi(
        bars=4,
        key="C",
        scale_type=ScaleType.AMBASSEL,
    )

    assert pattern
    assert all(isinstance(tick, int) and tick >= 0 for tick, _duration, _pitch, _velocity in pattern)
    assert all(isinstance(duration, int) and duration > 0 for _tick, duration, _pitch, _velocity in pattern)
    assert all(isinstance(pitch, int) and 0 <= pitch <= 127 for _tick, _duration, pitch, _velocity in pattern)
    assert all(isinstance(velocity, int) and 1 <= velocity <= 127 for _tick, _duration, _pitch, velocity in pattern)


def test_ethiopian_traditional_ambassel_prompt_generates_midi_without_scale_degree_index_error():
    parsed = PromptParser().parse(TASK_127_TRADITIONAL_AMBASSEL_PROMPT)

    mid = MidiGenerator(use_physics_humanization=False).generate(
        _one_bar_arrangement(SectionType.CHORUS),
        parsed,
    )
    krar = _track_by_name(mid, "Krar")

    assert parsed.genre == "ethiopian_traditional"
    assert parsed.scale_type == ScaleType.AMBASSEL
    assert mid.tracks
    assert _note_on_pitches(krar)


def test_generate_chord_progression_midi_major_default_progression_preserves_seven_note_roots():
    pattern = generate_chord_progression_midi(
        bars=4,
        key="C",
        scale_type=ScaleType.MAJOR,
    )

    assert _lowest_bar_start_pitches(pattern, bars=4) == [60, 67, 69, 65]


def test_eskista_multi_instrument_prompt_preserves_distinct_ethiopian_tracks_and_programs():
    parsed = PromptParser().parse(TASK_113_ESKISTA_PROMPT)

    mid = MidiGenerator(use_physics_humanization=False).generate(
        _one_bar_arrangement(SectionType.CHORUS),
        parsed,
    )
    drums = _track_by_name(mid, "Drums")
    krar = _track_by_name(mid, "Krar")
    washint = _track_by_name(mid, "Washint")
    masenqo = _track_by_name(mid, "Masenqo")
    track_names = [
        msg.name
        for track in mid.tracks
        for msg in track
        if msg.type == "track_name"
    ]

    assert parsed.genre == "eskista"
    assert track_names.count("Krar") == 1
    assert track_names.count("Washint") == 1
    assert track_names.count("Masenqo") == 1
    assert "Chords" not in track_names
    assert "Melody" not in track_names
    assert _channel_2_program(krar) == 110
    assert _channel_3_program(washint) == 112
    assert _channel_4_program(masenqo) == 111
    assert _note_on_pitches(krar)
    assert _note_on_pitches(washint)
    assert _note_on_pitches(masenqo)
    assert "instrument:Kebero" in _text_markers(drums)


def test_eskista_base_midi_drums_track_stays_generic_with_kebero_marker():
    parsed = PromptParser().parse(TASK_113_ESKISTA_PROMPT)

    mid = MidiGenerator(use_physics_humanization=False).generate(
        _one_bar_arrangement(SectionType.CHORUS),
        parsed,
    )
    drums = _track_by_name(mid, "Drums")
    track_names = [
        msg.name
        for track in mid.tracks
        for msg in track
        if msg.type == "track_name"
    ]
    drum_pitches = _note_on_pitches(drums)
    drum_pitch_set = set(drum_pitches)
    low_head_hits = drum_pitches.count(GM_DRUM_NOTES["conga_low"])
    high_head_hits = drum_pitches.count(GM_DRUM_NOTES["conga_high"])

    assert track_names.count("Drums") == 1
    assert "Kebero" not in track_names
    assert "instrument:Kebero" in _text_markers(drums)
    assert GM_DRUM_NOTES["conga_low"] in drum_pitch_set
    assert GM_DRUM_NOTES["conga_high"] in drum_pitch_set
    assert low_head_hits == 2
    assert high_head_hits == 2
    assert high_head_hits < 4


def test_eskista_krar_track_avoids_same_tick_western_block_chord_clusters():
    parsed = PromptParser().parse(TASK_113_ESKISTA_PROMPT)

    mid = MidiGenerator(use_physics_humanization=False).generate(
        _one_bar_arrangement(SectionType.CHORUS),
        parsed,
    )
    krar = _track_by_name(mid, "Krar")
    onset_groups = _note_on_pitches_by_absolute_tick(krar)

    assert onset_groups
    assert max(len(set(pitches)) for pitches in onset_groups.values()) <= 2


def test_eskista_krar_track_still_emits_sparse_support_notes():
    parsed = PromptParser().parse(TASK_113_ESKISTA_PROMPT)

    mid = MidiGenerator(use_physics_humanization=False).generate(
        _one_bar_arrangement(SectionType.CHORUS),
        parsed,
    )
    krar = _track_by_name(mid, "Krar")
    onset_groups = _note_on_pitches_by_absolute_tick(krar)

    assert _note_on_pitches(krar)
    assert len(onset_groups) >= 2


def test_eskista_krar_support_change_preserves_task_113_identity_contract():
    parsed = PromptParser().parse(TASK_113_ESKISTA_PROMPT)

    mid = MidiGenerator(use_physics_humanization=False).generate(
        _one_bar_arrangement(SectionType.CHORUS),
        parsed,
    )
    drums = _track_by_name(mid, "Drums")
    krar = _track_by_name(mid, "Krar")
    washint = _track_by_name(mid, "Washint")
    masenqo = _track_by_name(mid, "Masenqo")
    track_names = [
        msg.name
        for track in mid.tracks
        for msg in track
        if msg.type == "track_name"
    ]

    assert track_names.count("Krar") == 1
    assert track_names.count("Washint") == 1
    assert track_names.count("Masenqo") == 1
    assert "Chords" not in track_names
    assert "Melody" not in track_names
    assert _channel_2_program(krar) == 110
    assert _channel_3_program(washint) == 112
    assert _channel_4_program(masenqo) == 111
    assert "instrument:Kebero" in _text_markers(drums)


def test_compact_eskista_exact_prompt_keeps_identity_and_thins_krar_intro_outro_bars():
    state = random.getstate()
    random.seed(0)
    try:
        parsed = PromptParser().parse(TASK_113_ESKISTA_PROMPT)
        parsed.target_bars = 16
        arrangement = Arranger().create_arrangement(parsed)

        mid = MidiGenerator(use_physics_humanization=False).generate(arrangement, parsed)
        drums = _track_by_name(mid, "Drums")
        krar = _track_by_name(mid, "Krar")
        washint = _track_by_name(mid, "Washint")
        masenqo = _track_by_name(mid, "Masenqo")
        track_names = [
            msg.name
            for track in mid.tracks
            for msg in track
            if msg.type == "track_name"
        ]
        krar_bars = _note_on_bars(krar)

        assert [section.section_type.value for section in arrangement.sections] == [
            "intro",
            "verse",
            "variation",
            "outro",
        ]
        assert track_names.count("Drums") == 1
        assert track_names.count("Krar") == 1
        assert track_names.count("Washint") == 1
        assert track_names.count("Masenqo") == 1
        assert "Chords" not in track_names
        assert "Melody" not in track_names
        assert _channel_2_program(krar) == 110
        assert _channel_3_program(washint) == 112
        assert _channel_4_program(masenqo) == 111
        assert "instrument:Kebero" in _text_markers(drums)
        assert krar_bars
        assert not (krar_bars & {0, 1, 2, 3})
        assert krar_bars & {4, 5, 6, 7, 8, 9, 10, 11}
        assert not (krar_bars & {12, 13, 14, 15})
    finally:
        random.setstate(state)


def test_compact_eskista_secondary_begena_honors_intro_outro_chord_disable_with_high_tension():
    state = random.getstate()
    random.seed(0)
    try:
        parsed = PromptParser().parse(
            "eskista groove with kebero, krar, washint, and begena at 126 BPM in E minor"
        )
        parsed.target_bars = 16
        arrangement = Arranger().create_arrangement(parsed)
        arrangement.tension_arc = TensionArc(
            points=[TensionPoint(0.0, 0.95), TensionPoint(1.0, 0.95)]
        )

        mid = MidiGenerator(use_physics_humanization=False).generate(arrangement, parsed)
        begena = _track_by_name(mid, "Begena")
        begena_bars = _note_on_bars(begena)

        assert begena_bars
        assert not (begena_bars & {0, 1, 2, 3})
        assert begena_bars & {4, 5, 6, 7, 8, 9, 10, 11}
        assert not (begena_bars & {12, 13, 14, 15})
    finally:
        random.setstate(state)


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


def test_exact_rock_prompt_service_routing_uses_crunch_guitar_chord_program():
    parsed = PromptParser().parse(EXACT_1990S_ROCK_PROMPT)
    service = InstrumentResolutionService()

    mid = MidiGenerator(
        use_physics_humanization=False,
        instrument_service=service,
    ).generate(_one_bar_arrangement(), parsed)
    chords = _chords_track(mid)
    program = _channel_2_program(chords)

    assert parsed.genre == "rock"
    assert program == 30
    assert program != 25
    assert "instrument:Guitar" in _text_markers(chords)


def test_acoustic_rock_guitar_service_routing_keeps_steel_guitar_chord_program():
    parsed = PromptParser().parse(
        "acoustic rock song with acoustic guitar, bass guitar, live drums, 100 BPM in E minor"
    )
    service = InstrumentResolutionService()

    mid = MidiGenerator(
        use_physics_humanization=False,
        instrument_service=service,
    ).generate(_one_bar_arrangement(), parsed)
    chords = _chords_track(mid)
    program = _channel_2_program(chords)

    assert parsed.genre == "rock"
    assert program == 25
    assert "instrument:Guitar" in _text_markers(chords)


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


def test_exact_1990s_rock_prompt_suppresses_unrequested_synth_melody():
    parsed = PromptParser().parse(EXACT_1990S_ROCK_PROMPT)

    mid = MidiGenerator(use_physics_humanization=False).generate(_one_bar_arrangement(), parsed)
    track_names = _track_names(mid)
    programs = [msg.program for track in mid.tracks for msg in track if msg.type == "program_change"]

    assert parsed.genre == "rock"
    assert {"guitar", "bass"}.issubset(set(parsed.instruments))
    assert "Melody" not in track_names
    assert 80 not in programs


def test_rock_synth_lead_prompt_still_emits_synth_melody_program_80():
    parsed = PromptParser().parse(f"{EXACT_1990S_ROCK_PROMPT}, synth lead")

    mid = MidiGenerator(use_physics_humanization=False).generate(_one_bar_arrangement(), parsed)
    melody = _melody_track(mid)

    assert parsed.genre == "rock"
    assert _channel_3_program(melody) == 80
    assert "instrument:Synth" in _text_markers(melody)


def test_rock_lead_guitar_and_guitar_solo_route_melody_to_guitar_program():
    prompts = [
        "1990's era rock song with crunchy lead guitar, live drums, bass guitar, 100 BPM in E minor",
        "1990's era rock song with crunchy electric guitar solo, live drums, bass guitar, 100 BPM in E minor",
    ]

    for prompt in prompts:
        parsed = PromptParser().parse(prompt)
        mid = MidiGenerator(use_physics_humanization=False).generate(_one_bar_arrangement(), parsed)
        melody = _melody_track(mid)
        program = _channel_3_program(melody)

        assert parsed.genre == "rock"
        assert 24 <= program <= 31
        assert program == 30
        assert program != 80
        assert "instrument:Guitar" in _text_markers(melody)


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


def test_generic_non_rock_bass_track_preserves_synth_bass_program():
    parsed = ParsedPrompt(
        genre="pop",
        bpm=88,
        key="D",
        scale_type=ScaleType.MINOR,
        instruments=["synth", "bass"],
        drum_elements=["kick", "snare", "hihat"],
        raw_prompt="warm pop synth and bass groove",
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


def test_lyrical_cinematic_prompt_emits_first_class_piano_track_and_strings_bed():
    parsed = PromptParser().parse(LYRICAL_CINEMATIC_PIANO_PROMPT)

    mid = MidiGenerator(use_physics_humanization=False).generate(
        _one_bar_arrangement(SectionType.CHORUS),
        parsed,
    )
    piano = _piano_track(mid)
    strings = _strings_track(mid)

    assert parsed.genre == "cinematic"
    assert _channel_2_program(piano) == 0
    assert "instrument:Piano" in _text_markers(piano)
    assert _note_on_pitches(piano)
    assert _channel_10_program(strings) == 48
    assert "instrument:Strings" in _text_markers(strings)
    assert _note_on_pitches(strings)
    assert not any(
        any(msg.type == "track_name" and msg.name == "Chords" for msg in track)
        for track in mid.tracks
    )


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
