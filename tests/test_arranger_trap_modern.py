"""Focused regressions for trap/modern-beat short arrangements."""

from multimodal_gen.arranger import Arranger
from multimodal_gen.prompt_parser import PromptParser


TASK_064_PROMPT = (
    "dark trap modern beat with 808 bass, snare, hihat rolls, sparse melody, "
    "140 BPM in C minor"
)


def _section_shapes(arrangement):
    return [(section.section_type.value, section.bars) for section in arrangement.sections]


def test_trap_modern_prompt_target_16_bars_uses_compact_beat_arc():
    parsed = PromptParser().parse(TASK_064_PROMPT)
    parsed.target_bars = 16

    arrangement = Arranger().create_arrangement(parsed)

    assert parsed.genre == "trap"
    assert arrangement.total_bars == 16
    assert _section_shapes(arrangement) == [
        ("intro", 4),
        ("drop", 4),
        ("variation", 4),
        ("drop", 4),
    ]


def test_default_trap_template_remains_full_length_without_short_target():
    parsed = PromptParser().parse(TASK_064_PROMPT)

    arrangement = Arranger().create_arrangement(parsed)

    assert arrangement.total_bars > 16
    assert [name for name, _bars in _section_shapes(arrangement)] == [
        "intro",
        "drop",
        "drop",
        "breakdown",
        "buildup",
        "drop",
        "outro",
    ]