"""Focused regressions for the first-class rock strategy."""

import pytest

from multimodal_gen.arranger import SECTION_CONFIGS, SectionType, SongSection
from multimodal_gen.midi_generator import NoteEvent
from multimodal_gen.prompt_parser import ParsedPrompt
from multimodal_gen.strategies.base import DrumConfig
from multimodal_gen.strategies.default_strategy import DefaultStrategy
from multimodal_gen.strategies.registry import StrategyRegistry
from multimodal_gen.strategies.rock_strategy import ROCK_FAMILY_GENRES, RockStrategy
from multimodal_gen.utils import GM_DRUM_CHANNEL, GM_DRUM_NOTES, ScaleType, TICKS_PER_BAR_4_4


def _section(section_type: SectionType = SectionType.VERSE, bars: int = 4) -> SongSection:
    return SongSection(
        section_type=section_type,
        start_tick=0,
        end_tick=bars * TICKS_PER_BAR_4_4,
        bars=bars,
        config=SECTION_CONFIGS[section_type],
    )


def _parsed() -> ParsedPrompt:
    return ParsedPrompt(
        genre='rock',
        bpm=100,
        key='E',
        scale_type=ScaleType.MINOR,
        instruments=['guitar', 'bass'],
        drum_elements=['kick', 'snare', 'hihat', 'hihat_open', 'crash', 'ride'],
    )


def test_rock_strategy_import_genre_aliases_and_default_config():
    strategy = RockStrategy()

    assert strategy.genre_name == 'rock'
    for alias in ['rock', 'classic_rock', 'alternative_rock', 'grunge', 'punk_rock', 'indie_rock']:
        assert alias in strategy.supported_genres

    config = strategy.get_default_config()
    assert isinstance(config, DrumConfig)
    assert config.base_velocity >= 90
    assert config.half_time is False
    assert config.include_rolls is False
    assert config.density == '8th'


def test_registry_resolves_rock_family_aliases_without_changing_unknown_fallback():
    StrategyRegistry.reset()

    for alias in ROCK_FAMILY_GENRES:
        assert isinstance(StrategyRegistry.get(alias), RockStrategy)

    assert StrategyRegistry.get('unknown_genre_xyz_12345') is None
    assert isinstance(StrategyRegistry.get_or_default('unknown_genre_xyz_12345'), DefaultStrategy)


def test_generate_drums_uses_live_kit_channel_and_avoids_clap_signature():
    notes = RockStrategy().generate_drums(_section(SectionType.VERSE, bars=4), _parsed(), tension=0.7)

    assert notes
    assert all(isinstance(note, NoteEvent) for note in notes)
    assert all(note.channel == GM_DRUM_CHANNEL for note in notes)

    pitches = {note.pitch for note in notes}
    assert GM_DRUM_NOTES['kick'] in pitches
    assert GM_DRUM_NOTES['snare'] in pitches
    assert GM_DRUM_NOTES['hihat_closed'] in pitches
    assert GM_DRUM_NOTES['clap'] not in pitches


@pytest.mark.parametrize('section_type', [SectionType.VERSE, SectionType.CHORUS])
def test_generate_bass_and_chords_are_non_empty_for_rock_band_sections(section_type):
    section = _section(section_type, bars=4)
    strategy = RockStrategy()
    parsed = _parsed()

    bass = strategy.generate_bass(section, parsed, tension=0.6)
    chords = strategy.generate_chords(section, parsed, tension=0.6)

    assert bass
    assert chords
    assert all(note.channel == 1 for note in bass)
    assert all(36 <= note.pitch <= 55 for note in bass)
    assert all(note.channel == 2 for note in chords)
    assert all(45 <= note.pitch <= 76 for note in chords)
