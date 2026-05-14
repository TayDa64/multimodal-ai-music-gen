"""Rock-family arranger regressions."""

from multimodal_gen.arranger import ARRANGEMENT_TEMPLATES, Arranger, SectionType
from multimodal_gen.prompt_parser import parse_prompt


EXACT_1990S_ROCK_PROMPT = (
    "1990's era rock song with crunchy electric guitar, live drums, "
    "bass guitar, verse chorus bridge, energetic band performance, "
    "100 BPM in E minor"
)


def test_exact_1990s_rock_prompt_target_16_bars_stays_bounded_and_rock_structured():
    parsed = parse_prompt(EXACT_1990S_ROCK_PROMPT)
    parsed.target_bars = 16
    parsed.target_duration_seconds = (16 * 4 * 60.0) / parsed.bpm

    arrangement = Arranger(target_duration_seconds=parsed.target_duration_seconds).create_arrangement(parsed)
    section_names = [section.section_type.value for section in arrangement.sections]

    assert parsed.genre == 'rock'
    assert arrangement.total_bars == 16
    assert section_names == ['verse', 'chorus', 'bridge', 'chorus']
    assert {'verse', 'chorus', 'bridge'}.issubset(section_names)
    assert 'drop' not in section_names
    assert 'buildup' not in section_names
    assert 'variation' not in section_names


def test_rock_family_templates_use_band_song_sections():
    expected = [
        (SectionType.INTRO, 4),
        (SectionType.VERSE, 8),
        (SectionType.CHORUS, 8),
        (SectionType.VERSE, 8),
        (SectionType.CHORUS, 8),
        (SectionType.BRIDGE, 4),
        (SectionType.CHORUS, 8),
        (SectionType.OUTRO, 4),
    ]

    for genre in ['rock', 'classic_rock', 'alternative_rock', 'grunge', 'punk_rock', 'indie_rock']:
        assert ARRANGEMENT_TEMPLATES[genre] == expected
        section_types = [section_type for section_type, _ in ARRANGEMENT_TEMPLATES[genre]]
        assert SectionType.DROP not in section_types
        assert SectionType.BUILDUP not in section_types
        assert SectionType.VARIATION not in section_types


def test_existing_trap_soul_template_is_unchanged_by_rock_addition():
    assert ARRANGEMENT_TEMPLATES['trap_soul'] == [
        (SectionType.INTRO, 4),
        (SectionType.DROP, 8),
        (SectionType.VARIATION, 8),
        (SectionType.BREAKDOWN, 8),
        (SectionType.BUILDUP, 4),
        (SectionType.DROP, 8),
        (SectionType.OUTRO, 4),
    ]
