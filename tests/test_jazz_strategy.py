"""Focused regressions for the first-class generic jazz route."""

from multimodal_gen.arranger import ARRANGEMENT_TEMPLATES, Arranger, SECTION_CONFIGS, SectionType, SongSection
from multimodal_gen.midi_generator import MidiGenerator, NoteEvent
from multimodal_gen.prompt_parser import ParsedPrompt, parse_prompt
from multimodal_gen.strategies.ethiopian_strategy import EthioJazzStrategy
from multimodal_gen.strategies.jazz_strategy import JazzStrategy
from multimodal_gen.strategies.registry import StrategyRegistry
from multimodal_gen.utils import GM_DRUM_CHANNEL, GM_DRUM_NOTES, ScaleType, TICKS_PER_BAR_4_4


GENERIC_JAZZ_PROMPT = (
    "small-combo jazz quartet with walking bass, ride cymbal, "
    "piano comping, 120 BPM in Bb major"
)


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
        genre='jazz',
        bpm=120,
        key='Bb',
        scale_type=ScaleType.MAJOR,
        instruments=['piano', 'bass'],
        drum_elements=['kick', 'snare', 'hihat', 'ride'],
        raw_prompt=GENERIC_JAZZ_PROMPT,
    )


def _track_name(track) -> str:
    for msg in track:
        if msg.type == 'track_name':
            return getattr(msg, 'name', '') or ''
    return getattr(track, 'name', '') or ''


def _programs_for_track(midi_file, track_name: str) -> list[int]:
    return [
        int(msg.program)
        for track in midi_file.tracks
        if _track_name(track).lower() == track_name.lower()
        for msg in track
        if msg.type == 'program_change'
    ]


def test_registry_resolves_generic_jazz_without_overriding_ethio_jazz():
    StrategyRegistry.reset()

    assert isinstance(StrategyRegistry.get('jazz'), JazzStrategy)
    assert isinstance(StrategyRegistry.get('ethio_jazz'), EthioJazzStrategy)


def test_jazz_strategy_default_config_is_swinging_no_rolls():
    config = JazzStrategy().get_default_config()

    assert config.swing > 0
    assert config.include_rolls is False
    assert config.half_time is False
    assert config.density == '8th'


def test_generate_drums_uses_ride_kit_and_avoids_trap_signature():
    notes = JazzStrategy().generate_drums(_section(SectionType.VERSE, bars=2), _parsed(), tension=0.6)

    assert notes
    assert all(isinstance(note, NoteEvent) for note in notes)
    assert all(note.channel == GM_DRUM_CHANNEL for note in notes)

    pitches = {note.pitch for note in notes}
    assert GM_DRUM_NOTES['kick'] in pitches
    assert GM_DRUM_NOTES['snare'] in pitches
    assert GM_DRUM_NOTES['ride'] in pitches
    assert GM_DRUM_NOTES['hihat_pedal'] in pitches
    assert GM_DRUM_NOTES['clap'] not in pitches


def test_generate_bass_and_chords_are_walking_combo_parts():
    strategy = JazzStrategy()
    section = _section(SectionType.CHORUS, bars=2)

    bass = strategy.generate_bass(section, _parsed(), tension=0.6)
    chords = strategy.generate_chords(section, _parsed(), tension=0.6)

    assert bass
    assert chords
    assert all(note.channel == 1 for note in bass)
    assert all(32 <= note.pitch <= 55 for note in bass)
    assert all(note.channel == 2 for note in chords)
    assert all(48 <= note.pitch <= 76 for note in chords)


def test_jazz_arrangement_templates_avoid_trap_drop_and_buildup():
    section_types = [section_type for section_type, _ in ARRANGEMENT_TEMPLATES['jazz']]

    assert SectionType.DROP not in section_types
    assert SectionType.BUILDUP not in section_types
    assert SectionType.VARIATION not in section_types
    assert {SectionType.VERSE, SectionType.CHORUS, SectionType.BRIDGE}.issubset(section_types)


def test_exact_jazz_prompt_target_8_bars_uses_bounded_jazz_sections_and_acoustic_bass():
    parsed = parse_prompt(GENERIC_JAZZ_PROMPT)
    parsed.target_bars = 8
    parsed.target_duration_seconds = (8 * 4 * 60.0) / parsed.bpm

    arrangement = Arranger(target_duration_seconds=parsed.target_duration_seconds).create_arrangement(parsed)
    midi_file = MidiGenerator().generate(arrangement, parsed)

    assert parsed.genre == 'jazz'
    assert arrangement.total_bars == 8
    assert [section.section_type.value for section in arrangement.sections] == ['verse', 'chorus']
    assert _programs_for_track(midi_file, 'Bass') == [32]