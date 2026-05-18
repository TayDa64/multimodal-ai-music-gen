"""Focused regressions for lofi/boom-bap short arrangements."""

from multimodal_gen.arranger import Arranger
from multimodal_gen.prompt_parser import PromptParser


TASK_066_PROMPT = (
    "lofi boom bap groove with dusty drums, warm bass, mellow keys, "
    "vinyl texture, 88 BPM in C minor"
)


def _section_shapes(arrangement):
    return [(section.section_type.value, section.bars) for section in arrangement.sections]


def test_boom_bap_prompt_target_16_bars_uses_compact_lofi_arc():
    parsed = PromptParser().parse(TASK_066_PROMPT)
    parsed.target_bars = 16

    arrangement = Arranger().create_arrangement(parsed)

    assert parsed.genre == "boom_bap"
    assert arrangement.total_bars == 16
    assert _section_shapes(arrangement) == [
        ("intro", 4),
        ("verse", 4),
        ("variation", 4),
        ("verse", 4),
    ]


def test_default_boom_bap_template_remains_full_length_without_short_target():
    parsed = PromptParser().parse(TASK_066_PROMPT)

    arrangement = Arranger().create_arrangement(parsed)

    assert arrangement.total_bars > 16
    assert [name for name, _bars in _section_shapes(arrangement)] == [
        "intro",
        "verse",
        "chorus",
        "verse",
        "chorus",
        "outro",
    ]