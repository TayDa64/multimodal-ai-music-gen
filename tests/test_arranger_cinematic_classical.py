"""Cinematic/classical arranger and strategy regressions."""

from multimodal_gen.arranger import Arranger, SectionType
from multimodal_gen.prompt_parser import PromptParser, parse_prompt
from multimodal_gen.strategies.cinematic_strategy import CinematicStrategy
from multimodal_gen.strategies.default_strategy import DefaultStrategy
from multimodal_gen.strategies.registry import StrategyRegistry


TASK_063_PROMPT = (
    "cinematic orchestral film score with strings, brass, choir, timpani, "
    "evolving sections, 96 BPM in D minor"
)


def _section_names(arrangement):
    return [section.section_type.value for section in arrangement.sections]


def test_cinematic_classical_prompt_target_16_bars_uses_orchestral_short_arc():
    parsed = PromptParser().parse(TASK_063_PROMPT)
    parsed.target_bars = 16

    arrangement = Arranger().create_arrangement(parsed)

    assert arrangement.total_bars == 16
    assert _section_names(arrangement) == ["intro", "verse", "buildup", "chorus"]
    assert {section.bars for section in arrangement.sections} == {4}
    assert SectionType.DROP.value not in _section_names(arrangement)
    assert SectionType.BRIDGE.value not in _section_names(arrangement)


def test_pure_classical_prompt_target_16_bars_uses_same_orchestral_short_arc():
    parsed = parse_prompt(
        "classical orchestral score with strings, woodwinds, and timpani, 84 BPM in C minor"
    )
    parsed.target_bars = 16

    arrangement = Arranger().create_arrangement(parsed)

    assert parsed.genre == "classical"
    assert arrangement.total_bars == 16
    assert _section_names(arrangement) == ["intro", "verse", "buildup", "chorus"]


def test_strategy_registry_resolves_classical_to_cinematic_strategy():
    StrategyRegistry.reset()

    assert isinstance(StrategyRegistry.get("classical"), CinematicStrategy)
    assert not isinstance(StrategyRegistry.get_or_default("classical"), DefaultStrategy)
