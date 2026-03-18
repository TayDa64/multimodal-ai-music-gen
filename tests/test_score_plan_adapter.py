from multimodal_gen.score_plan_adapter import (
    extract_mastering_overrides,
    score_plan_to_parsed_prompt,
    score_plan_to_performance_score,
)
from multimodal_gen.utils import bars_to_ticks


def _sample_plan():
    return {
        "schema_version": "score_plan_v1",
        "prompt": "ambient cinematic soundscape in C minor with atmospheric pads",
        "bpm": 72,
        "key": "C",
        "mode": "minor",
        "time_signature": [4, 4],
        "sections": [
            {"name": "intro", "type": "intro", "bars": 4},
            {"name": "main", "type": "verse", "bars": 8},
        ],
        "tracks": [
            {"role": "pad", "instrument": "pad"},
            {"role": "strings", "instrument": "strings"},
            {"role": "drums", "instrument": "kick"},
        ],
        "chord_map": [{"bar": 1, "chord": "Cm"}],
        "cue_points": [{"bar": 5, "type": "build", "intensity": 0.6}],
        "constraints": {"avoid_instruments": ["brass"], "avoid_drums": ["snare"]},
        "mastering": {
            "production_preset": "ambient_ethereal",
            "target_lufs": -16.0,
            "master_ceiling_db": -1.5,
            "brightness_target": 0.6,
            "warmth_target": 0.7,
        },
    }


def test_score_plan_overrides_parsed_prompt():
    plan = _sample_plan()
    parsed = score_plan_to_parsed_prompt(plan)
    assert parsed.bpm == 72
    assert parsed.key == "C"
    assert parsed.scale_type.name.lower() == "minor"
    assert "pad" in parsed.instruments
    assert "strings" in parsed.instruments
    assert "kick" in parsed.drum_elements
    assert "brass" in parsed.excluded_instruments
    assert "snare" in parsed.excluded_drums
    assert parsed.production_preset == "ambient_ethereal"
    assert parsed.brightness == 0.6
    assert parsed.warmth == 0.7


def test_score_plan_builds_performance_score():
    plan = _sample_plan()
    score = score_plan_to_performance_score(plan)
    assert score.sections
    assert score.tempo_map.get(0) == 72
    assert score.key_map.get(0) == "C"
    assert score.chord_map.get(0) == "Cm"

    build_tick = bars_to_ticks(4, (4, 4))
    cues = [c for c in score.cue_points if c.get("type") == "build"]
    assert cues and cues[0]["tick"] == build_tick


def test_extract_mastering_overrides_returns_structured_block():
    mastering = extract_mastering_overrides(_sample_plan())
    assert mastering["production_preset"] == "ambient_ethereal"
    assert mastering["target_lufs"] == -16.0
    assert mastering["master_ceiling_db"] == -1.5
