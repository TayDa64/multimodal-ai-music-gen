from multimodal_gen.prompt_parser import parse_prompt
from multimodal_gen.strategies.ambient_strategy import AmbientStrategy
from multimodal_gen.arranger import SongSection, SectionType, SectionConfig
from multimodal_gen.utils import TICKS_PER_BEAT


def _make_section(bars: int = 4) -> SongSection:
    ticks_per_bar = TICKS_PER_BEAT * 4
    return SongSection(
        section_type=SectionType.INTRO,
        start_tick=0,
        end_tick=bars * ticks_per_bar,
        bars=bars,
        config=SectionConfig(),
    )


def test_ambient_no_drum_intent_disables_defaults():
    parsed = parse_prompt(
        "ambient cinematic soundscape in C minor with atmospheric pads and drone"
    )
    assert parsed.drum_elements == []
    assert parsed.drum_intent is False
    assert parsed.allow_default_drums is False


def test_ambient_drum_intent_allows_sparse_strategy():
    parsed = parse_prompt(
        "ambient pads with soft drums and shakers in C minor"
    )
    assert parsed.drum_elements
    assert parsed.drum_intent is True
    strategy = AmbientStrategy()
    notes = strategy.generate_drums(_make_section(), parsed, tension=0.4)
    assert len(notes) > 0
