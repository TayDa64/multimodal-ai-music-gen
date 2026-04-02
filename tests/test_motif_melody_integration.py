"""Motif-driven melody integration tests.

These tests ensure the MIDI pipeline can consume Arrangement.motifs + motif_assignments
and produce a melody track derived from motifs (not just procedural melody).
"""

# Add parent directory to path for imports
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

from multimodal_gen.arranger import Arrangement, SongSection, SectionType, SectionConfig, MotifAssignment
from multimodal_gen.midi_generator import MidiGenerator, NoteEvent
from multimodal_gen.motif_engine import Motif
from multimodal_gen.prompt_parser import ParsedPrompt
from multimodal_gen.utils import ScaleType, bars_to_ticks


def _get_track_name(track) -> str:
    for msg in track:
        if msg.type == "track_name":
            return msg.name
    return ""


def _get_note_on_velocities_by_tick(track) -> dict[int, list[int]]:
    absolute_tick = 0
    note_ons: dict[int, list[int]] = {}
    for msg in track:
        absolute_tick += msg.time
        if msg.type == "note_on" and msg.velocity > 0:
            note_ons.setdefault(absolute_tick, []).append(msg.velocity)
    return note_ons


def test_midi_generator_uses_motif_for_melody_track():
    # Build a minimal arrangement with a single chorus section.
    bars = 4
    section_ticks = bars_to_ticks(bars, (4, 4))

    section = SongSection(
        section_type=SectionType.CHORUS,
        start_tick=0,
        end_tick=section_ticks,
        bars=bars,
        config=SectionConfig(enable_melody=True),
        variation_seed=123,
        pattern_variation=0,
    )

    motif = Motif(
        name="Test Motif",
        intervals=[0, 2, 4],
        rhythm=[1.0, 1.0, 1.0],
        accent_pattern=[1.0, 1.0, 1.0],
        genre_tags=["test"],
    )

    arrangement = Arrangement(
        sections=[section],
        total_bars=bars,
        total_ticks=section_ticks,
        bpm=90.0,
        time_signature=(4, 4),
        motifs=[motif],
        motif_assignments={"chorus_1": MotifAssignment(0, "original", {})},
        tension_arc=None,
    )

    parsed = ParsedPrompt(
        bpm=90.0,
        genre="g_funk",
        key="C",
        scale_type=ScaleType.MAJOR,
        instruments=["synth_lead"],
    )

    midi = MidiGenerator().generate(arrangement, parsed)

    melody_track = next((t for t in midi.tracks if _get_track_name(t) == "Melody"), None)
    assert melody_track is not None, "Expected a Melody track"

    pitches = [msg.note for msg in melody_track if msg.type == "note_on" and msg.velocity > 0]
    assert len(pitches) >= 3, "Expected motif notes in melody track"

    # Motif should start from C5 (72) with intervals 0,2,4.
    assert pitches[0:3] == [72, 74, 76]


def test_midi_generator_uses_motif_for_non_chorus_second_verse_assignment():
    bars = 2
    section_ticks = bars_to_ticks(bars, (4, 4))

    verse_1 = SongSection(
        section_type=SectionType.VERSE,
        start_tick=0,
        end_tick=section_ticks,
        bars=bars,
        config=SectionConfig(enable_melody=False),
        variation_seed=11,
        pattern_variation=0,
    )
    verse_2 = SongSection(
        section_type=SectionType.VERSE,
        start_tick=section_ticks,
        end_tick=section_ticks * 2,
        bars=bars,
        config=SectionConfig(enable_melody=True),
        variation_seed=12,
        pattern_variation=0,
    )

    motif = Motif(
        name="Verse Motif",
        intervals=[0, 7, 10],
        rhythm=[1.0, 1.0, 1.0],
        accent_pattern=[1.0, 1.0, 1.0],
        genre_tags=["test"],
    )

    arrangement = Arrangement(
        sections=[verse_1, verse_2],
        total_bars=bars * 2,
        total_ticks=section_ticks * 2,
        bpm=88.0,
        time_signature=(4, 4),
        motifs=[motif],
        motif_assignments={"verse_2": MotifAssignment(0, "original", {})},
        tension_arc=None,
    )

    parsed = ParsedPrompt(
        bpm=88.0,
        genre="pop",
        key="C",
        scale_type=ScaleType.MINOR,
        instruments=["synth_lead"],
    )

    midi = MidiGenerator().generate(arrangement, parsed)

    melody_track = next((t for t in midi.tracks if _get_track_name(t) == "Melody"), None)
    assert melody_track is not None, "Expected a Melody track"

    pitches = [msg.note for msg in melody_track if msg.type == "note_on" and msg.velocity > 0]
    assert len(pitches) >= 3, "Expected motif notes in melody track"

    # The second verse should resolve the verse_2 assignment, proving counters stay aligned.
    assert pitches[0:3] == [72, 79, 82]


def test_midi_generator_uses_motif_for_cinematic_pre_chorus_sequence_assignment():
    bars = 2
    section_ticks = bars_to_ticks(bars, (4, 4))

    section = SongSection(
        section_type=SectionType.PRE_CHORUS,
        start_tick=0,
        end_tick=section_ticks,
        bars=bars,
        config=SectionConfig(enable_melody=True),
        variation_seed=21,
        pattern_variation=0,
    )

    motif = Motif(
        name="Cinematic Cell",
        intervals=[0, 2, 5],
        rhythm=[1.0, 1.0, 1.0],
        accent_pattern=[1.0, 0.8, 0.9],
        genre_tags=["cinematic"],
    )

    arrangement = Arrangement(
        sections=[section],
        total_bars=bars,
        total_ticks=section_ticks,
        bpm=92.0,
        time_signature=(4, 4),
        motifs=[motif],
        motif_assignments={"pre_chorus_1": MotifAssignment(0, "sequence", {"steps": 2})},
        tension_arc=None,
    )

    parsed = ParsedPrompt(
        bpm=92.0,
        genre="cinematic",
        key="C",
        scale_type=ScaleType.MINOR,
        instruments=["synth_lead"],
    )

    midi = MidiGenerator().generate(arrangement, parsed)

    melody_track = next((t for t in midi.tracks if _get_track_name(t) == "Melody"), None)
    assert melody_track is not None, "Expected a Melody track"

    pitches = [msg.note for msg in melody_track if msg.type == "note_on" and msg.velocity > 0]
    assert len(pitches) >= 3, "Expected motif notes in melody track"
    # Sequence transposition is snapped back onto the active C minor scale in the melody path.
    assert pitches[0:3] == [74, 75, 79]


def test_midi_generator_ethiopian_bass_velocities_follow_motif_accents(monkeypatch):
    bars = 1
    section_ticks = bars_to_ticks(bars, (4, 4))

    section = SongSection(
        section_type=SectionType.VERSE,
        start_tick=0,
        end_tick=section_ticks,
        bars=bars,
        config=SectionConfig(enable_bass=True),
        variation_seed=31,
        pattern_variation=0,
    )

    motif = Motif(
        name="Ethiopian Accent Motif",
        intervals=[0, 2, 5, 7],
        rhythm=[1.0, 1.0, 1.0, 1.0],
        accent_pattern=[1.0, 0.2, 0.95, 0.25],
        genre_tags=["ethiopian"],
    )

    arrangement = Arrangement(
        sections=[section],
        total_bars=bars,
        total_ticks=section_ticks,
        bpm=100.0,
        time_signature=(4, 4),
        motifs=[motif],
        motif_assignments={"verse_1": MotifAssignment(0, "original", {})},
        tension_arc=None,
    )

    parsed = ParsedPrompt(
        bpm=100.0,
        genre="ethiopian",
        key="C",
        scale_type=ScaleType.MINOR,
        instruments=["bass"],
    )

    monkeypatch.setattr(
        "multimodal_gen.midi_generator.generate_808_bass_pattern",
        lambda *args, **kwargs: [
            (0, 240, 36, 100),
            (240, 240, 36, 100),
            (480, 240, 36, 100),
            (720, 240, 36, 100),
        ],
    )
    monkeypatch.setattr(
        MidiGenerator,
        "_apply_performance_humanization",
        lambda self, all_notes, genre, role_hint: all_notes,
    )
    monkeypatch.setattr(
        "multimodal_gen.midi_generator.StrategyRegistry.get_or_default",
        lambda genre: SimpleNamespace(
            generate_bass=lambda section, parsed, tension: [],
            generate_drums=lambda section, parsed, tension: [],
        ),
    )

    midi = MidiGenerator(use_physics_humanization=False).generate(arrangement, parsed)

    bass_track = next((t for t in midi.tracks if _get_track_name(t) == "Bass"), None)
    assert bass_track is not None, "Expected a Bass track"

    velocities = [msg.velocity for msg in bass_track if msg.type == "note_on" and msg.velocity > 0]
    assert velocities[:4] == [106, 96, 105, 97]
    assert velocities[0] > velocities[1]
    assert velocities[2] > velocities[3]


def test_midi_generator_chord_track_reuses_motif_accents_by_onset_group(monkeypatch):
    bars = 1
    section_ticks = bars_to_ticks(bars, (4, 4))

    section = SongSection(
        section_type=SectionType.VERSE,
        start_tick=0,
        end_tick=section_ticks,
        bars=bars,
        config=SectionConfig(enable_chords=True),
        variation_seed=41,
        pattern_variation=0,
    )

    motif = Motif(
        name="Chord Accent Motif",
        intervals=[0, 2, 4],
        rhythm=[1.0, 1.0, 1.0],
        accent_pattern=[10.0, 2.0, 6.0],
        genre_tags=["test"],
    )

    arrangement = Arrangement(
        sections=[section],
        total_bars=bars,
        total_ticks=section_ticks,
        bpm=96.0,
        time_signature=(4, 4),
        motifs=[motif],
        motif_assignments={"verse_1": MotifAssignment(0, "original", {})},
        tension_arc=None,
    )

    parsed = ParsedPrompt(
        bpm=96.0,
        genre="pop",
        key="C",
        scale_type=ScaleType.MAJOR,
        instruments=["piano"],
    )

    monkeypatch.setattr(
        MidiGenerator,
        "_apply_performance_humanization",
        lambda self, all_notes, genre, role_hint: all_notes,
    )
    monkeypatch.setattr("multimodal_gen.midi_generator._HAS_DYNAMICS", False)

    strategy_notes = [
        (0, 240, 60, 100),
        (0, 240, 64, 96),
        (480, 240, 62, 100),
        (480, 240, 65, 96),
        (960, 240, 64, 100),
        (960, 240, 67, 96),
    ]
    fallback_notes = [
        (0, 240, 60, 100),
        (0, 240, 64, 100),
        (480, 240, 62, 100),
        (480, 240, 65, 100),
        (960, 240, 64, 100),
        (960, 240, 67, 100),
    ]

    for use_strategy in (True, False):
        expected_by_tick = {
            0: [104, 104],
            480: [92, 92],
            960: [98, 98],
        } if use_strategy else {
            0: [106, 106],
            480: [94, 94],
            960: [100, 100],
        }
        monkeypatch.setattr(
            "multimodal_gen.midi_generator.StrategyRegistry.get_or_default",
            lambda genre, use_strategy=use_strategy: SimpleNamespace(
                generate_chords=lambda section, parsed, tension, use_strategy=use_strategy: [
                    NoteEvent(
                        pitch=pitch,
                        start_tick=tick,
                        duration_ticks=dur,
                        velocity=vel,
                        channel=2,
                    )
                    for tick, dur, pitch, vel in (strategy_notes if use_strategy else [])
                ],
                generate_drums=lambda section, parsed, tension: [],
                generate_bass=lambda section, parsed, tension: [],
            ),
        )
        monkeypatch.setattr(
            "multimodal_gen.midi_generator.generate_chord_progression_midi",
            lambda *args, **kwargs: fallback_notes,
        )

        midi = MidiGenerator(use_physics_humanization=False).generate(arrangement, parsed)

        chord_track = next((t for t in midi.tracks if _get_track_name(t) == "Chords"), None)
        assert chord_track is not None, "Expected a Chords track"

        velocities_by_tick = _get_note_on_velocities_by_tick(chord_track)
        assert velocities_by_tick == expected_by_tick
        assert all(len(set(velocities)) == 1 for velocities in velocities_by_tick.values())


def test_midi_generator_chord_track_fails_open_when_motif_lookup_is_unusable(monkeypatch):
    bars = 1
    section_ticks = bars_to_ticks(bars, (4, 4))

    section = SongSection(
        section_type=SectionType.VERSE,
        start_tick=0,
        end_tick=section_ticks,
        bars=bars,
        config=SectionConfig(enable_chords=True),
        variation_seed=42,
        pattern_variation=0,
    )

    motif = Motif(
        name="Broken Lookup Motif",
        intervals=[0, 2, 4],
        rhythm=[1.0, 1.0, 1.0],
        accent_pattern=[1.0, 0.0, 0.5],
        genre_tags=["test"],
    )

    arrangement = Arrangement(
        sections=[section],
        total_bars=bars,
        total_ticks=section_ticks,
        bpm=96.0,
        time_signature=(4, 4),
        motifs=[motif],
        motif_assignments={"verse_1": MotifAssignment(0, "original", {})},
        tension_arc=None,
    )

    parsed = ParsedPrompt(
        bpm=96.0,
        genre="pop",
        key="C",
        scale_type=ScaleType.MAJOR,
        instruments=["piano"],
    )

    monkeypatch.setattr(
        MidiGenerator,
        "_apply_performance_humanization",
        lambda self, all_notes, genre, role_hint: all_notes,
    )
    monkeypatch.setattr("multimodal_gen.midi_generator._HAS_DYNAMICS", False)
    monkeypatch.setattr(
        "multimodal_gen.midi_generator.StrategyRegistry.get_or_default",
        lambda genre: SimpleNamespace(
            generate_chords=lambda section, parsed, tension: [],
            generate_drums=lambda section, parsed, tension: [],
            generate_bass=lambda section, parsed, tension: [],
        ),
    )
    monkeypatch.setattr(
        "multimodal_gen.midi_generator.generate_chord_progression_midi",
        lambda *args, **kwargs: [
            (0, 240, 60, 98),
            (0, 240, 64, 98),
            (480, 240, 62, 92),
            (480, 240, 65, 92),
        ],
    )
    monkeypatch.setattr(
        "multimodal_gen.midi_generator.get_section_motif",
        lambda arrangement, section_name: (_ for _ in ()).throw(RuntimeError("bad motif lookup")),
    )

    midi = MidiGenerator(use_physics_humanization=False).generate(arrangement, parsed)

    chord_track = next((t for t in midi.tracks if _get_track_name(t) == "Chords"), None)
    assert chord_track is not None, "Expected a Chords track"

    velocities_by_tick = _get_note_on_velocities_by_tick(chord_track)
    assert velocities_by_tick == {
        0: [98, 98],
        480: [92, 92],
    }
