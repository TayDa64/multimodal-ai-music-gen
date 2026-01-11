"""Tension arc integration tests.

These tests verify that:
- Arranger produces an Arrangement with a tension arc.
- SessionGraphBuilder persists tension arc data into session manifests.
- MidiGenerator uses tension to shape dynamics (velocity).
"""

import random

import pytest

# Add parent directory to path for imports
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from multimodal_gen.arranger import Arranger
from multimodal_gen.midi_generator import MidiGenerator
from multimodal_gen.prompt_parser import parse_prompt
from multimodal_gen.session_graph import SessionGraphBuilder
from multimodal_gen.tension_arc import TensionArcGenerator


def _avg_note_on_velocity(track) -> float:
    velocities = [msg.velocity for msg in track if msg.type == "note_on" and msg.velocity > 0]
    return sum(velocities) / len(velocities) if velocities else 0.0


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
