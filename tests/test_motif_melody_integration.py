"""Motif-driven melody integration tests.

These tests ensure the MIDI pipeline can consume Arrangement.motifs + motif_assignments
and produce a melody track derived from motifs (not just procedural melody).
"""

# Add parent directory to path for imports
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from multimodal_gen.arranger import Arrangement, SongSection, SectionType, SectionConfig, MotifAssignment
from multimodal_gen.midi_generator import MidiGenerator
from multimodal_gen.motif_engine import Motif
from multimodal_gen.prompt_parser import ParsedPrompt
from multimodal_gen.utils import ScaleType, bars_to_ticks


def _get_track_name(track) -> str:
    for msg in track:
        if msg.type == "track_name":
            return msg.name
    return ""


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
