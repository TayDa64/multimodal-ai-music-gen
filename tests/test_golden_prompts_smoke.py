"""Golden prompt smoke tests.

Goal: Catch obvious regressions quickly without requiring audio rendering.

- Ensures prompt parsing + genre normalization are stable
- Ensures the generation pipeline produces MIDI with non-empty drums

This is intentionally lightweight and deterministic-ish.
"""

import json
import sys
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from multimodal_gen.prompt_parser import PromptParser
from multimodal_gen.arranger import Arranger
from multimodal_gen.midi_generator import MidiGenerator
from multimodal_gen.output_analyzer import AUDIO_GENRE_TARGETS
from multimodal_gen.utils import normalize_genre


FIXTURES_PATH = Path(__file__).parent / "fixtures" / "golden_prompts.json"


def _load_golden_prompts():
    data = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    seen_ids = set()
    for item in data:
        assert "id" in item
        assert "prompt" in item
        assert "expected_genre" in item
        assert item["id"] not in seen_ids
        seen_ids.add(item["id"])
    return data


def _normalized_items(items) -> set[str]:
    return {
        str(item).strip().lower().replace("-", "_").replace(" ", "_")
        for item in (items or [])
    }


def _scale_name(parsed) -> str:
    scale = getattr(parsed, "scale_type", "")
    return getattr(scale, "name", str(scale)).lower()


def _apply_target_bars_like_main(parsed, bars: int) -> None:
    """Mirror main.py --duration-bars behavior without invoking rendering."""
    bars = int(bars)
    assert bars > 0
    beats_per_bar = parsed.time_signature[0] if parsed.time_signature else 4
    bpm_val = float(parsed.bpm) if parsed.bpm else 120.0
    bpm_val = max(30.0, bpm_val)
    parsed.target_duration_seconds = (bars * beats_per_bar * 60.0) / bpm_val
    parsed.target_bars = bars


def _track_name(track) -> str:
    name = getattr(track, "name", "") or ""
    if name:
        return name
    for msg in track:
        if msg.type == "track_name":
            return getattr(msg, "name", "") or ""
    return ""


def _count_drum_note_ons(midi_file) -> int:
    return len(_drum_note_pitches(midi_file))


def _drum_note_pitches(midi_file) -> list[int]:
    exact_drum_tracks = [track for track in midi_file.tracks if _track_name(track).lower() == "drums"]
    fallback_drum_tracks = [
        track for track in midi_file.tracks if "drum" in _track_name(track).lower()
    ]
    for tracks in (exact_drum_tracks, fallback_drum_tracks):
        if tracks:
            return [
                int(msg.note)
                for track in tracks
                for msg in track
                if msg.type == "note_on" and getattr(msg, "velocity", 0) and msg.velocity > 0
            ]
    return []


def _programs_for_track(midi_file, track_name: str) -> list[int]:
    wanted = track_name.lower()
    return [
        int(msg.program)
        for track in midi_file.tracks
        if _track_name(track).lower() == wanted
        for msg in track
        if msg.type == "program_change"
    ]


@pytest.mark.parametrize("case", _load_golden_prompts(), ids=lambda c: c["id"])
def test_golden_prompt_smoke(case):
    parser = PromptParser()
    parsed = parser.parse(case["prompt"])

    expected_genre = normalize_genre(case["expected_genre"])
    parsed_genre = normalize_genre(parsed.genre)

    assert parsed_genre == expected_genre

    if case.get("expected_analyzer_target", True):
        assert expected_genre in AUDIO_GENRE_TARGETS

    if "expected_bpm" in case:
        assert float(parsed.bpm) == pytest.approx(float(case["expected_bpm"]))
    if "expected_key" in case:
        assert parsed.key == case["expected_key"]
    if "expected_scale" in case:
        assert _scale_name(parsed) == str(case["expected_scale"]).lower()

    parsed_instruments = _normalized_items(getattr(parsed, "instruments", []))
    for instrument in case.get("expected_instruments_include", []):
        assert _normalized_items([instrument]).pop() in parsed_instruments
    for instrument in case.get("expected_instruments_exclude", []):
        assert _normalized_items([instrument]).pop() not in parsed_instruments

    parsed_drums = _normalized_items(getattr(parsed, "drum_elements", []))
    for drum in case.get("expected_drums_include", []):
        assert _normalized_items([drum]).pop() in parsed_drums
    for drum in case.get("expected_drums_exclude", []):
        assert _normalized_items([drum]).pop() not in parsed_drums

    has_expected_target_bars = "expected_target_bars" in case
    if has_expected_target_bars:
        _apply_target_bars_like_main(parsed, case["expected_target_bars"])
        assert parsed.target_bars == case["expected_target_bars"]

    # Keep it fast: short target duration.
    arranger_duration = parsed.target_duration_seconds if has_expected_target_bars else 30.0
    arranger = Arranger(target_duration_seconds=arranger_duration)
    arrangement = arranger.create_arrangement(parsed)

    if "expected_section_names" in case:
        assert [section.section_type.value for section in arrangement.sections] == case[
            "expected_section_names"
        ]
    if "expected_total_bars" in case:
        assert arrangement.total_bars == case["expected_total_bars"]

    mid = MidiGenerator().generate(arrangement, parsed)

    if "expected_midi_bass_program" in case:
        assert _programs_for_track(mid, "Bass") == [case["expected_midi_bass_program"]]
    if "expected_midi_chords_program_range" in case:
        low, high = case["expected_midi_chords_program_range"]
        chord_programs = _programs_for_track(mid, "Chords")
        assert chord_programs
        assert all(low <= program <= high for program in chord_programs)
    for pitch in case.get("expected_midi_drum_pitches_exclude", []):
        assert int(pitch) not in _drum_note_pitches(mid)

    drum_notes = _count_drum_note_ons(mid)
    allow_default_drums = getattr(parsed, "allow_default_drums", True)
    drum_elements = getattr(parsed, "drum_elements", []) or []
    if allow_default_drums or drum_elements:
        assert drum_notes > 0
    else:
        assert drum_notes == 0
