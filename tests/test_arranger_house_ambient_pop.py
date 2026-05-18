"""Focused regressions for house/ambient/pop short arrangements."""

from multimodal_gen.arranger import Arranger
from multimodal_gen.prompt_parser import PromptParser


TASK_067_PROMPT = (
    "atmospheric house pop track with pads, four-on-floor drums, bass, "
    "hook synth, 124 BPM in A minor"
)


def _section_shapes(arrangement):
    return [(section.section_type.value, section.bars) for section in arrangement.sections]


def test_house_pop_prompt_target_16_bars_uses_compact_house_arc():
    parsed = PromptParser().parse(TASK_067_PROMPT)
    parsed.target_bars = 16

    arrangement = Arranger().create_arrangement(parsed)

    assert parsed.genre == "house"
    assert arrangement.total_bars == 16
    assert _section_shapes(arrangement) == [
        ("intro", 4),
        ("buildup", 4),
        ("drop", 4),
        ("outro", 4),
    ]


def test_default_house_template_remains_full_length_without_short_target():
    parsed = PromptParser().parse(TASK_067_PROMPT)

    arrangement = Arranger().create_arrangement(parsed)

    assert arrangement.total_bars > 16
    assert [name for name, _bars in _section_shapes(arrangement)] == [
        "intro",
        "buildup",
        "drop",
        "breakdown",
        "buildup",
        "drop",
        "outro",
    ]