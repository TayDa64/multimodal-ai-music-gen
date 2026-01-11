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
from multimodal_gen.utils import normalize_genre


FIXTURES_PATH = Path(__file__).parent / "fixtures" / "golden_prompts.json"


def _load_golden_prompts():
    data = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    for item in data:
        assert "id" in item
        assert "prompt" in item
        assert "expected_genre" in item
    return data


def _count_drum_note_ons(midi_file) -> int:
    for track in midi_file.tracks:
        # Track name is set via a MetaMessage('track_name', name='Drums', time=0)
        if (getattr(track, "name", "") or "").lower() == "drums":
            return sum(
                1
                for msg in track
                if msg.type == "note_on" and getattr(msg, "velocity", 0) and msg.velocity > 0
            )
    # Fallback: any track with 'drum' in name
    for track in midi_file.tracks:
        if "drum" in ((getattr(track, "name", "") or "").lower()):
            return sum(
                1
                for msg in track
                if msg.type == "note_on" and getattr(msg, "velocity", 0) and msg.velocity > 0
            )
    return 0


@pytest.mark.parametrize("case", _load_golden_prompts(), ids=lambda c: c["id"])
def test_golden_prompt_smoke(case):
    parser = PromptParser()
    parsed = parser.parse(case["prompt"])

    expected_genre = normalize_genre(case["expected_genre"])
    parsed_genre = normalize_genre(parsed.genre)

    assert parsed_genre == expected_genre

    # Keep it fast: short target duration.
    arranger = Arranger(target_duration_seconds=30.0)
    arrangement = arranger.create_arrangement(parsed)

    mid = MidiGenerator().generate(arrangement, parsed)

    drum_notes = _count_drum_note_ons(mid)
    assert drum_notes > 0
