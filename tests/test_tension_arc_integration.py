"""Tension arc integration tests.

These tests verify that:
- Arranger produces an Arrangement with a tension arc.
- SessionGraphBuilder persists tension arc data into session manifests.
- MidiGenerator uses tension to shape dynamics (velocity).
"""

from copy import deepcopy
import random
from types import SimpleNamespace

import pytest

# Add parent directory to path for imports
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from multimodal_gen.arranger import Arrangement, Arranger, SectionConfig, SectionType, SongSection
from multimodal_gen.midi_generator import MidiGenerator, NoteEvent
from multimodal_gen.prompt_parser import ParsedPrompt, parse_prompt
from multimodal_gen.session_graph import SessionGraphBuilder
from multimodal_gen.tension_arc import TensionArc, TensionArcGenerator, TensionConfig
from multimodal_gen.utils import ScaleType, bars_to_ticks


def _avg_note_on_velocity(track) -> float:
    velocities = [msg.velocity for msg in track if msg.type == "note_on" and msg.velocity > 0]
    return sum(velocities) / len(velocities) if velocities else 0.0


def _note_on_pitches(track) -> list[int]:
    return [msg.note for msg in track if msg.type == "note_on" and msg.velocity > 0]


def _avg_note_on_pitch(track) -> float:
    pitches = _note_on_pitches(track)
    return sum(pitches) / len(pitches) if pitches else 0.0


def _note_on_count(track) -> int:
    return sum(1 for msg in track if msg.type == "note_on" and msg.velocity > 0)


def _get_track(midi_file, name: str):
    return next((t for t in midi_file.tracks if getattr(t, "name", "") == name), None)


def test_arranger_creates_tension_arc():
    parsed = parse_prompt("g_funk beat at 92 bpm in C minor")
    arrangement = Arranger().create_arrangement(parsed)

    assert arrangement.tension_arc is not None
    assert len(arrangement.tension_arc.points) == len(arrangement.sections)


def test_session_graph_persists_tension_arc():
    parsed = parse_prompt("ethiopian groove at 105 bpm in A minor")
    arrangement = Arranger().create_arrangement(parsed)

    builder = SessionGraphBuilder()
    graph = builder.build_from_prompt(parsed)
    graph = builder.build_from_arrangement(graph, arrangement)

    assert graph.tension_arc is not None
    assert "curve" in graph.tension_arc
    assert len(graph.tension_arc["curve"]) == 128

    assert graph.sections
    assert hasattr(graph.sections[0], "tension")


def test_tension_increases_chord_velocity():
    parsed = parse_prompt("g_funk beat at 92 bpm in C minor with piano")
    arrangement = Arranger().create_arrangement(parsed)

    gen = TensionArcGenerator()

    # Force low tension everywhere
    low_arc = gen.create_custom_arc([0.0] * len(arrangement.sections))
    arrangement.tension_arc = low_arc

    random.seed(12345)
    midi_gen = MidiGenerator(use_physics_humanization=False)
    midi_low = midi_gen.generate(arrangement, parsed)

    # Force high tension everywhere (same RNG seed to keep patterns aligned)
    high_arc = gen.create_custom_arc([1.0] * len(arrangement.sections))
    arrangement.tension_arc = high_arc

    random.seed(12345)
    midi_high = midi_gen.generate(arrangement, parsed)

    # Track 0 is meta. Find chords track by name.
    chords_low = next((t for t in midi_low.tracks if getattr(t, "name", "") == "Chords"), None)
    chords_high = next((t for t in midi_high.tracks if getattr(t, "name", "") == "Chords"), None)

    assert chords_low is not None
    assert chords_high is not None

    avg_low = _avg_note_on_velocity(chords_low)
    avg_high = _avg_note_on_velocity(chords_high)

    # Expect a noticeable increase with high tension.
    assert avg_high > avg_low + 2.0


def test_explicit_high_tension_arc_lifts_primary_chord_register_center():
    parsed = parse_prompt("g_funk beat at 92 bpm in C minor with piano")
    base_arrangement = Arranger().create_arrangement(parsed)

    gen = TensionArcGenerator()
    midi_gen = MidiGenerator(use_physics_humanization=False)

    arrangement_low = deepcopy(base_arrangement)
    arrangement_low.tension_arc = gen.create_custom_arc([0.0] * len(arrangement_low.sections))

    arrangement_high = deepcopy(base_arrangement)
    arrangement_high.tension_arc = gen.create_custom_arc([1.0] * len(arrangement_high.sections))

    random.seed(20260403)
    midi_low = midi_gen.generate(arrangement_low, parsed)

    random.seed(20260403)
    midi_high = midi_gen.generate(arrangement_high, parsed)

    chords_low = _get_track(midi_low, "Chords")
    chords_high = _get_track(midi_high, "Chords")

    assert chords_low is not None
    assert chords_high is not None
    assert _avg_note_on_pitch(chords_high) > _avg_note_on_pitch(chords_low) + 6.0


def test_missing_or_unusable_explicit_tension_arc_do_not_trigger_primary_chord_register_lift():
    parsed = parse_prompt("g_funk beat at 92 bpm in C minor with piano")
    base_arrangement = Arranger().create_arrangement(parsed)
    gen = TensionArcGenerator()
    midi_gen = MidiGenerator(use_physics_humanization=False)

    arrangement_none = deepcopy(base_arrangement)
    arrangement_none.tension_arc = None

    arrangement_unusable = deepcopy(base_arrangement)
    arrangement_unusable.tension_arc = TensionArc(points=[], config=TensionConfig())

    arrangement_high = deepcopy(base_arrangement)
    arrangement_high.tension_arc = gen.create_custom_arc([1.0] * len(arrangement_high.sections))

    random.seed(1117)
    midi_none = midi_gen.generate(arrangement_none, parsed)

    random.seed(1117)
    midi_unusable = midi_gen.generate(arrangement_unusable, parsed)

    random.seed(1117)
    midi_high = midi_gen.generate(arrangement_high, parsed)

    chords_none = _get_track(midi_none, "Chords")
    chords_unusable = _get_track(midi_unusable, "Chords")
    chords_high = _get_track(midi_high, "Chords")

    assert chords_none is not None
    assert chords_unusable is not None
    assert chords_high is not None
    assert _avg_note_on_pitch(chords_high) > _avg_note_on_pitch(chords_none) + 6.0
    assert _avg_note_on_pitch(chords_high) > _avg_note_on_pitch(chords_unusable) + 6.0


def test_explicit_high_tension_arc_lifts_strategy_returned_chords(monkeypatch):
    bars = 1
    section_ticks = bars_to_ticks(bars, (4, 4))
    section = SongSection(
        section_type=SectionType.VERSE,
        start_tick=0,
        end_tick=section_ticks,
        bars=bars,
        config=SectionConfig(
            enable_kick=False,
            enable_snare=False,
            enable_hihat=False,
            enable_bass=False,
            enable_chords=True,
            enable_melody=False,
        ),
        variation_seed=7,
        pattern_variation=0,
    )
    base_arrangement = Arrangement(
        sections=[section],
        total_bars=bars,
        total_ticks=section_ticks,
        bpm=96.0,
        time_signature=(4, 4),
        tension_arc=None,
    )
    parsed = ParsedPrompt(
        bpm=96.0,
        genre="pop",
        key="C",
        scale_type=ScaleType.MAJOR,
        instruments=["piano"],
    )

    strategy_notes = [
        NoteEvent(pitch=60, start_tick=0, duration_ticks=240, velocity=96, channel=2),
        NoteEvent(pitch=64, start_tick=0, duration_ticks=240, velocity=96, channel=2),
        NoteEvent(pitch=67, start_tick=0, duration_ticks=240, velocity=96, channel=2),
        NoteEvent(pitch=62, start_tick=480, duration_ticks=240, velocity=92, channel=2),
        NoteEvent(pitch=65, start_tick=480, duration_ticks=240, velocity=92, channel=2),
        NoteEvent(pitch=69, start_tick=480, duration_ticks=240, velocity=92, channel=2),
    ]

    monkeypatch.setattr(
        MidiGenerator,
        "_apply_performance_humanization",
        lambda self, all_notes, genre, role_hint: all_notes,
    )
    monkeypatch.setattr("multimodal_gen.midi_generator._HAS_DYNAMICS", False)
    monkeypatch.setattr(
        "multimodal_gen.midi_generator.StrategyRegistry.get_or_default",
        lambda genre: SimpleNamespace(
            generate_chords=lambda section, parsed, tension: [
                NoteEvent(
                    pitch=note.pitch,
                    start_tick=note.start_tick,
                    duration_ticks=note.duration_ticks,
                    velocity=note.velocity,
                    channel=note.channel,
                )
                for note in strategy_notes
            ],
            generate_drums=lambda section, parsed, tension: [],
            generate_bass=lambda section, parsed, tension: [],
        ),
    )
    monkeypatch.setattr(
        "multimodal_gen.midi_generator.generate_chord_progression_midi",
        lambda *args, **kwargs: pytest.fail("fallback chord path should not run"),
    )

    gen = TensionArcGenerator()
    arrangement_low = deepcopy(base_arrangement)
    arrangement_low.tension_arc = gen.create_custom_arc([0.0])

    arrangement_high = deepcopy(base_arrangement)
    arrangement_high.tension_arc = gen.create_custom_arc([1.0])

    midi_low = MidiGenerator(use_physics_humanization=False).generate(arrangement_low, parsed)
    midi_high = MidiGenerator(use_physics_humanization=False).generate(arrangement_high, parsed)

    chords_low = _get_track(midi_low, "Chords")
    chords_high = _get_track(midi_high, "Chords")

    assert chords_low is not None
    assert chords_high is not None

    low_pitches = _note_on_pitches(chords_low)
    high_pitches = _note_on_pitches(chords_high)

    assert high_pitches == [pitch + 12 for pitch in low_pitches]


def test_complexity_increases_chord_note_count():
    parsed = parse_prompt("ethio_jazz groove at 108 bpm in A minor with piano")
    arrangement = Arranger().create_arrangement(parsed)

    gen = TensionArcGenerator()
    midi_gen = MidiGenerator(use_physics_humanization=False)

    # Low tension (and therefore lower derived complexity)
    arrangement.tension_arc = gen.create_custom_arc([0.0] * len(arrangement.sections))
    random.seed(222)
    midi_low = midi_gen.generate(arrangement, parsed)

    # High tension (higher complexity)
    arrangement.tension_arc = gen.create_custom_arc([1.0] * len(arrangement.sections))
    random.seed(222)
    midi_high = midi_gen.generate(arrangement, parsed)

    chords_low = next((t for t in midi_low.tracks if getattr(t, "name", "") == "Chords"), None)
    chords_high = next((t for t in midi_high.tracks if getattr(t, "name", "") == "Chords"), None)
    assert chords_low is not None
    assert chords_high is not None

    def chord_note_on_count(track) -> int:
        return sum(1 for msg in track if msg.type == "note_on" and msg.velocity > 0)

    # High complexity should generally add more chord tones (7ths/9ths) -> more note_on events.
    assert chord_note_on_count(chords_high) > chord_note_on_count(chords_low)


def test_high_tension_increases_auxiliary_brass_and_choir_activity():
    parsed = parse_prompt("cinematic score in C minor with strings brass choir contrabass")
    arrangement = Arranger().create_arrangement(parsed)
    gen = TensionArcGenerator()
    midi_gen = MidiGenerator(use_physics_humanization=False)

    arrangement.tension_arc = gen.create_custom_arc([0.0] * len(arrangement.sections))
    random.seed(4242)
    midi_low = midi_gen.generate(arrangement, parsed)

    arrangement.tension_arc = gen.create_custom_arc([1.0] * len(arrangement.sections))
    random.seed(4242)
    midi_high = midi_gen.generate(arrangement, parsed)

    brass_low = _get_track(midi_low, "Brass")
    brass_high = _get_track(midi_high, "Brass")
    choir_low = _get_track(midi_low, "Choir")
    choir_high = _get_track(midi_high, "Choir")

    assert brass_low is not None and brass_high is not None
    assert choir_low is not None and choir_high is not None

    assert _note_on_count(brass_high) > _note_on_count(brass_low)
    assert _note_on_count(choir_high) > _note_on_count(choir_low)


def test_high_tension_reduces_texture_activity():
    parsed = parse_prompt("ambient soundscape in C minor with pad strings choir")
    parsed.instruments = [inst for inst in parsed.instruments if inst not in {"synth", "synth_lead", "flute", "oboe", "clarinet", "french_horn", "washint"}]
    arrangement = Arranger().create_arrangement(parsed)
    gen = TensionArcGenerator()
    midi_gen = MidiGenerator(use_physics_humanization=False)

    arrangement.tension_arc = gen.create_custom_arc([0.0] * len(arrangement.sections))
    random.seed(5151)
    midi_low = midi_gen.generate(arrangement, parsed)

    arrangement.tension_arc = gen.create_custom_arc([1.0] * len(arrangement.sections))
    random.seed(5151)
    midi_high = midi_gen.generate(arrangement, parsed)

    texture_low = _get_track(midi_low, "Texture")
    texture_high = _get_track(midi_high, "Texture")

    assert texture_low is not None and texture_high is not None
    assert _note_on_count(texture_low) > _note_on_count(texture_high)


def test_missing_tension_arc_fails_open_for_auxiliary_generation():
    midi_gen = MidiGenerator(use_physics_humanization=False)

    parsed_orchestral = parse_prompt("cinematic score in C minor with strings brass choir contrabass")
    arrangement_orchestral = Arranger().create_arrangement(parsed_orchestral)
    arrangement_orchestral.tension_arc = None

    random.seed(6262)
    midi_orchestral = midi_gen.generate(arrangement_orchestral, parsed_orchestral)

    brass_track = _get_track(midi_orchestral, "Brass")
    choir_track = _get_track(midi_orchestral, "Choir")

    assert brass_track is not None
    assert choir_track is not None
    assert _note_on_count(brass_track) > 0
    assert _note_on_count(choir_track) > 0

    parsed_texture = parse_prompt("ambient soundscape in C minor with pad strings choir")
    parsed_texture.instruments = [inst for inst in parsed_texture.instruments if inst not in {"synth", "synth_lead", "flute", "oboe", "clarinet", "french_horn", "washint"}]
    arrangement_texture = Arranger().create_arrangement(parsed_texture)
    arrangement_texture.tension_arc = None

    random.seed(7373)
    midi_texture = midi_gen.generate(arrangement_texture, parsed_texture)

    texture_track = _get_track(midi_texture, "Texture")

    assert texture_track is not None
    assert _note_on_count(texture_track) > 0
