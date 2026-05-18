"""Focused regressions for Ethiopian-family short arrangements."""

from multimodal_gen.arranger import Arranger
from multimodal_gen.prompt_parser import PromptParser


TASK_068_PROMPT = (
    "Ethiopian jazz inspired groove with pentatonic melody, bass, "
    "hand percussion feel, 104 BPM in G minor"
)


def _section_shapes(arrangement):
    return [(section.section_type.value, section.bars) for section in arrangement.sections]


def test_ethio_jazz_prompt_target_16_bars_uses_compact_ethiopian_arc():
    parsed = PromptParser().parse(TASK_068_PROMPT)
    parsed.target_bars = 16

    arrangement = Arranger().create_arrangement(parsed)

    assert parsed.genre == "ethio_jazz"
    assert arrangement.total_bars == 16
    assert _section_shapes(arrangement) == [
        ("intro", 4),
        ("verse", 4),
        ("variation", 4),
        ("outro", 4),
    ]


def test_default_ethio_jazz_template_remains_full_length_without_short_target():
    parsed = PromptParser().parse(TASK_068_PROMPT)

    arrangement = Arranger().create_arrangement(parsed)

    assert parsed.genre == "ethio_jazz"
    assert arrangement.total_bars > 16
    assert [name for name, _bars in _section_shapes(arrangement)] == [
        "intro",
        "verse",
        "variation",
        "chorus",
        "breakdown",
        "variation",
        "chorus",
        "outro",
    ]