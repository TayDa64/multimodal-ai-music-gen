"""Focused regressions for R&B/neo-soul short arrangements."""

from multimodal_gen.arranger import Arranger
from multimodal_gen.prompt_parser import PromptParser


TASK_065_PROMPT = (
    "neo-soul R&B groove with warm electric piano, bass, laid-back drums, "
    "lush chords, 82 BPM in F minor"
)


def _section_shapes(arrangement):
    return [(section.section_type.value, section.bars) for section in arrangement.sections]


def test_neo_soul_prompt_target_16_bars_uses_compact_rnb_arc():
    parsed = PromptParser().parse(TASK_065_PROMPT)
    parsed.target_bars = 16

    arrangement = Arranger().create_arrangement(parsed)

    assert parsed.genre == "neo_soul"
    assert arrangement.total_bars == 16
    assert _section_shapes(arrangement) == [
        ("verse", 4),
        ("chorus", 4),
        ("bridge", 4),
        ("chorus", 4),
    ]


def test_default_neo_soul_template_remains_full_length_without_short_target():
    parsed = PromptParser().parse(TASK_065_PROMPT)

    arrangement = Arranger().create_arrangement(parsed)

    assert arrangement.total_bars > 16
    assert [name for name, _bars in _section_shapes(arrangement)] == [
        "intro",
        "verse",
        "chorus",
        "verse",
        "chorus",
        "bridge",
        "chorus",
        "outro",
    ]