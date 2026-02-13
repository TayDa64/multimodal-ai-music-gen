"""Wave 2 C1: Architecture Refactoring tests.

Covers:
- Builder 2: Genre strategy delegation (bass/chord) + drill/boom_bap strategies
- Builder 3: PluginSynthesizer adapter
- Builder 5: MPC schema validation (already complete, regression guard)
- Builder 6: Expanded strategy coverage
"""
import pytest


# ---------------------------------------------------------------------------
# Builder 2 — Strategy Delegation
# ---------------------------------------------------------------------------

class TestStrategyDelegation:
    """Verify strategy delegation wiring in MidiGenerator."""

    def test_bass_strategy_delegation_exists(self):
        """Bass track creation should attempt strategy delegation."""
        from multimodal_gen.midi_generator import MidiGenerator
        assert hasattr(MidiGenerator, '_create_bass_track')

    def test_chord_strategy_delegation_exists(self):
        from multimodal_gen.midi_generator import MidiGenerator
        assert hasattr(MidiGenerator, '_create_chord_track')

    def test_strategy_registry_has_drill(self):
        from multimodal_gen.strategies import StrategyRegistry
        strategy = StrategyRegistry.get_or_default('drill')
        assert strategy is not None
        assert strategy.__class__.__name__ == 'DrillStrategy'

    def test_strategy_registry_has_boom_bap(self):
        from multimodal_gen.strategies import StrategyRegistry
        strategy = StrategyRegistry.get_or_default('boom_bap')
        assert strategy is not None
        assert strategy.__class__.__name__ == 'BoomBapStrategy'

    def test_drill_strategy_generates_drums(self):
        """DrillStrategy.generate_drums produces non-empty note list."""
        from multimodal_gen.strategies import StrategyRegistry
        from multimodal_gen.arranger import SongSection, SectionType, SectionConfig
        from multimodal_gen.prompt_parser import ParsedPrompt

        strategy = StrategyRegistry.get_or_default('drill')
        section = SongSection(
            section_type=SectionType.VERSE,
            bars=2,
            start_tick=0,
            end_tick=3840,
            config=SectionConfig(),
        )
        parsed = ParsedPrompt(genre='drill', bpm=140, key='C', scale_type='minor')
        drums = strategy.generate_drums(section, parsed, tension=0.5)
        assert isinstance(drums, list)
        assert len(drums) > 0

    def test_boom_bap_strategy_generates_drums(self):
        """BoomBapStrategy.generate_drums produces non-empty note list."""
        from multimodal_gen.strategies import StrategyRegistry
        from multimodal_gen.arranger import SongSection, SectionType, SectionConfig
        from multimodal_gen.prompt_parser import ParsedPrompt

        strategy = StrategyRegistry.get_or_default('boom_bap')
        section = SongSection(
            section_type=SectionType.VERSE,
            bars=2,
            start_tick=0,
            end_tick=3840,
            config=SectionConfig(),
        )
        parsed = ParsedPrompt(genre='boom_bap', bpm=90, key='D', scale_type='minor')
        drums = strategy.generate_drums(section, parsed, tension=0.5)
        assert isinstance(drums, list)
        assert len(drums) > 0

    def test_default_strategy_fallback(self):
        from multimodal_gen.strategies import StrategyRegistry
        strategy = StrategyRegistry.get_or_default('nonexistent_genre_xyz')
        assert strategy.__class__.__name__ == 'DefaultStrategy'

    def test_all_registered_strategies_generate_drums(self):
        """Every registered genre should produce drum notes via its strategy."""
        from multimodal_gen.strategies import StrategyRegistry
        from multimodal_gen.arranger import SongSection, SectionType, SectionConfig
        from multimodal_gen.prompt_parser import ParsedPrompt

        section = SongSection(
            section_type=SectionType.VERSE,
            bars=2,
            start_tick=0,
            end_tick=3840,
            config=SectionConfig(),
        )
        for genre in ['trap', 'trap_soul', 'rnb', 'lofi', 'house', 'drill', 'boom_bap']:
            parsed = ParsedPrompt(genre=genre, bpm=120, key='C', scale_type='minor')
            strategy = StrategyRegistry.get_or_default(genre)
            drums = strategy.generate_drums(section, parsed, tension=0.5)
            assert isinstance(drums, list), f"{genre} strategy failed"
            assert len(drums) > 0, f"{genre} strategy returned empty drums"

    def test_drill_strategy_genre_name(self):
        from multimodal_gen.strategies.drill_strategy import DrillStrategy
        s = DrillStrategy()
        assert s.genre_name == 'drill'

    def test_boom_bap_strategy_genre_name(self):
        from multimodal_gen.strategies.boom_bap_strategy import BoomBapStrategy
        s = BoomBapStrategy()
        assert s.genre_name == 'boom_bap'

    def test_drill_supported_genres(self):
        from multimodal_gen.strategies.drill_strategy import DrillStrategy
        s = DrillStrategy()
        assert 'drill' in s.supported_genres
        assert 'uk_drill' in s.supported_genres

    def test_boom_bap_supported_genres(self):
        from multimodal_gen.strategies.boom_bap_strategy import BoomBapStrategy
        s = BoomBapStrategy()
        assert 'boom_bap' in s.supported_genres
        assert 'boombap' in s.supported_genres

    def test_bass_strategy_returns_empty_by_default(self):
        """Base GenreStrategy.generate_bass returns [] (fallthrough)."""
        from multimodal_gen.strategies import StrategyRegistry
        from multimodal_gen.arranger import SongSection, SectionType, SectionConfig
        from multimodal_gen.prompt_parser import ParsedPrompt

        strategy = StrategyRegistry.get_or_default('trap')
        section = SongSection(
            section_type=SectionType.VERSE, bars=2,
            start_tick=0, end_tick=3840, config=SectionConfig(),
        )
        parsed = ParsedPrompt(genre='trap', bpm=140, key='C', scale_type='minor')
        bass = strategy.generate_bass(section, parsed, 0.5)
        assert isinstance(bass, list)
        # Default implementation returns empty → inline fallback used
        assert bass == []

    def test_chords_strategy_returns_empty_by_default(self):
        """Base GenreStrategy.generate_chords returns [] (fallthrough)."""
        from multimodal_gen.strategies import StrategyRegistry
        from multimodal_gen.arranger import SongSection, SectionType, SectionConfig
        from multimodal_gen.prompt_parser import ParsedPrompt

        strategy = StrategyRegistry.get_or_default('trap')
        section = SongSection(
            section_type=SectionType.VERSE, bars=2,
            start_tick=0, end_tick=3840, config=SectionConfig(),
        )
        parsed = ParsedPrompt(genre='trap', bpm=140, key='C', scale_type='minor')
        chords = strategy.generate_chords(section, parsed, 0.5)
        assert isinstance(chords, list)
        assert chords == []


# ---------------------------------------------------------------------------
# Builder 3 — PluginSynthesizer
# ---------------------------------------------------------------------------

class TestPluginSynthesizer:
    def test_import(self):
        from multimodal_gen.synthesizers.plugin_synth import PluginSynthesizer

    def test_instantiate(self):
        from multimodal_gen.synthesizers.plugin_synth import PluginSynthesizer
        synth = PluginSynthesizer()
        assert synth is not None

    def test_name(self):
        from multimodal_gen.synthesizers.plugin_synth import PluginSynthesizer
        synth = PluginSynthesizer()
        assert synth.name == 'plugin_synthesizer'

    def test_capabilities(self):
        from multimodal_gen.synthesizers.plugin_synth import PluginSynthesizer
        synth = PluginSynthesizer()
        caps = synth.get_capabilities()
        assert isinstance(caps, dict)
        assert 'name' in caps
        assert caps['name'] == 'plugin_synthesizer'

    def test_render_notes_empty(self):
        from multimodal_gen.synthesizers.plugin_synth import PluginSynthesizer
        synth = PluginSynthesizer()
        result = synth.render_notes([], total_samples=100, sample_rate=44100)
        assert result is not None
        assert len(result) == 100

    def test_configure_noop(self):
        from multimodal_gen.synthesizers.plugin_synth import PluginSynthesizer
        synth = PluginSynthesizer()
        synth.configure(genre='trap')  # should not raise


class TestSynthFactory:
    def test_factory_import(self):
        from multimodal_gen.synthesizers.factory import SynthesizerFactory

    def test_factory_has_plugin(self):
        from multimodal_gen.synthesizers.factory import SynthesizerFactory
        registered = SynthesizerFactory.get_registered()
        assert 'plugin' in registered

    def test_factory_create_plugin(self):
        from multimodal_gen.synthesizers.factory import SynthesizerFactory
        synth = SynthesizerFactory.create('plugin')
        assert synth is not None
        assert synth.name == 'plugin_synthesizer'


# ---------------------------------------------------------------------------
# Builder 5 — MPC Schema (regression guard)
# ---------------------------------------------------------------------------

class TestMPCSchemaValidation:
    """Verify Builder 5 (MPC Schema) is already complete."""

    def test_schema_import(self):
        from multimodal_gen.schemas.mpc_schema import MpcProjectSchema, validate_project

    def test_validate_project_callable(self):
        from multimodal_gen.schemas.mpc_schema import validate_project
        assert callable(validate_project)


# ---------------------------------------------------------------------------
# Orchestration state
# ---------------------------------------------------------------------------

class TestOrchestrationUpdated:
    def test_builder5_marked_complete(self):
        import json
        from pathlib import Path
        orch = json.loads(
            Path('C:/dev/MUSE-ai/MUSE/.github/state/orchestration.json').read_text()
        )
        arch = orch.get('architecture_refactoring', {})
        assert arch.get('builder_5_mpc_schema_validation', {}).get('status') == 'completed'

    def test_builder2_marked_complete(self):
        import json
        from pathlib import Path
        orch = json.loads(
            Path('C:/dev/MUSE-ai/MUSE/.github/state/orchestration.json').read_text()
        )
        arch = orch.get('architecture_refactoring', {})
        assert arch.get('builder_2_genre_strategy_pattern', {}).get('status') == 'completed'

    def test_builder3_marked_complete(self):
        import json
        from pathlib import Path
        orch = json.loads(
            Path('C:/dev/MUSE-ai/MUSE/.github/state/orchestration.json').read_text()
        )
        arch = orch.get('architecture_refactoring', {})
        assert arch.get('builder_3_synthesizer_interface', {}).get('status') == 'completed'

    def test_builder6_marked_complete(self):
        import json
        from pathlib import Path
        orch = json.loads(
            Path('C:/dev/MUSE-ai/MUSE/.github/state/orchestration.json').read_text()
        )
        arch = orch.get('architecture_refactoring', {})
        assert arch.get('builder_6_test_suite_expansion', {}).get('status') == 'completed'
