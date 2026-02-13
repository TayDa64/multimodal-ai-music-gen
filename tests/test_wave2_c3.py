"""Wave 2 C3: Groove & Expression tests.

Covers:
- Task 1: Phrase boundary detection + phrase-aware dynamics
- Task 2: Per-instrument groove composition + GrooveProfileLoader
- Task 3: Genre fill patterns + energy-aware fill selection
- Regression guards for existing groove capabilities
"""
import pytest


# ---------------------------------------------------------------------------
# Task 1 — Phrase Boundary Detection + Phrase-Aware Dynamics
# ---------------------------------------------------------------------------

class TestPhraseBoundaries:

    def test_detect_boundaries_returns_list(self):
        from multimodal_gen.dynamics import detect_phrase_boundaries
        notes = [(0, 60, 100, 480), (480, 62, 100, 480), (960, 64, 100, 480)]
        boundaries = detect_phrase_boundaries(notes)
        assert isinstance(boundaries, list)
        assert 0 in boundaries  # Always includes start

    def test_rest_creates_boundary(self):
        from multimodal_gen.dynamics import detect_phrase_boundaries
        # Two phrases separated by a rest > 1 beat (>480 ticks)
        notes = [
            (0, 480, 60, 100),      # Phrase 1
            (480, 480, 62, 100),
            (1920, 480, 64, 100),   # Phrase 2 starts after >1 beat rest
        ]
        boundaries = detect_phrase_boundaries(notes, ticks_per_beat=480)
        assert len(boundaries) >= 2
        assert 1920 in boundaries

    def test_long_note_creates_boundary(self):
        from multimodal_gen.dynamics import detect_phrase_boundaries
        # Note at tick 0 with duration 1920 (4 beats > 2-beat threshold)
        notes = [
            (0, 1920, 60, 100),     # Long note (4 beats) = phrase end
            (1920, 480, 62, 100),   # New phrase
        ]
        boundaries = detect_phrase_boundaries(notes, ticks_per_beat=480)
        assert len(boundaries) >= 2
        assert 1920 in boundaries

    def test_empty_notes(self):
        from multimodal_gen.dynamics import detect_phrase_boundaries
        boundaries = detect_phrase_boundaries([])
        assert boundaries == [0]

    def test_single_note(self):
        from multimodal_gen.dynamics import detect_phrase_boundaries
        boundaries = detect_phrase_boundaries([(0, 480, 60, 100)])
        assert 0 in boundaries

    def test_phrase_aware_dynamics_preserves_count(self):
        from multimodal_gen.dynamics import DynamicsEngine, detect_phrase_boundaries
        engine = DynamicsEngine()
        notes = [(i * 480, 480, 60, 100) for i in range(16)]
        boundaries = detect_phrase_boundaries(notes)
        result = engine.apply_phrase_aware_dynamics(notes, boundaries)
        assert len(result) == len(notes)

    def test_phrase_aware_dynamics_empty_notes(self):
        from multimodal_gen.dynamics import DynamicsEngine
        engine = DynamicsEngine()
        result = engine.apply_phrase_aware_dynamics([], [0])
        assert result == []

    def test_apply_with_auto_detect_flag(self):
        from multimodal_gen.dynamics import DynamicsEngine, DynamicsConfig
        engine = DynamicsEngine()
        notes = [(i * 480, 480, 60, 100) for i in range(8)]
        config = DynamicsConfig()
        # Must not raise with auto_detect_phrases=True
        result = engine.apply(notes, config, auto_detect_phrases=True)
        assert len(result) == len(notes)

    def test_apply_without_auto_detect_unchanged_behavior(self):
        """Existing behavior (fixed phrase) must still work."""
        from multimodal_gen.dynamics import DynamicsEngine, DynamicsConfig
        engine = DynamicsEngine()
        notes = [(i * 480, 480, 60, 100) for i in range(8)]
        config = DynamicsConfig()
        result = engine.apply(notes, config)
        assert len(result) == len(notes)


# ---------------------------------------------------------------------------
# Task 2 — Per-Instrument Groove Composition + GrooveProfileLoader
# ---------------------------------------------------------------------------

class TestInstrumentGroove:

    def test_groove_applicator_has_instrument_method(self):
        from multimodal_gen.groove_templates import GrooveApplicator
        assert hasattr(GrooveApplicator, 'apply_with_instrument_offset')

    def test_groove_profile_loader_import(self):
        from multimodal_gen.groove_templates import GrooveProfileLoader  # noqa: F401

    def test_groove_profile_loader_list(self):
        from multimodal_gen.groove_templates import GrooveProfileLoader
        loader = GrooveProfileLoader()
        profiles = loader.list_profiles()
        assert isinstance(profiles, list)

    def test_groove_profile_loader_missing_dir(self):
        from multimodal_gen.groove_templates import GrooveProfileLoader
        loader = GrooveProfileLoader(groove_dir="/nonexistent/dir")
        assert loader.list_profiles() == []

    def test_groove_profile_loader_file_not_found(self):
        from multimodal_gen.groove_templates import GrooveProfileLoader
        loader = GrooveProfileLoader()
        with pytest.raises(FileNotFoundError):
            loader.load_profile("__does_not_exist__")

    def test_apply_instrument_offset_returns_notes(self):
        from multimodal_gen.groove_templates import GrooveApplicator, GrooveTemplate
        applicator = GrooveApplicator()
        template = GrooveTemplate(name="test")
        notes = [
            {'tick': 0, 'velocity': 100, 'note': 36},
            {'tick': 480, 'velocity': 90, 'note': 38},
        ]
        result = applicator.apply_with_instrument_offset(notes, template, 'trap', 'kick')
        assert len(result) == len(notes)

    def test_apply_instrument_offset_applies_genre_shift(self):
        """For genres with non-zero offset, ticks should change."""
        from multimodal_gen.groove_templates import (
            GrooveApplicator, GrooveTemplate, GENRE_TIMING_OFFSETS,
        )
        applicator = GrooveApplicator()
        # boom_bap bass has offset 10
        template = GrooveTemplate(name="test")
        notes = [{'tick': 960, 'velocity': 80, 'note': 36}]
        result = applicator.apply_with_instrument_offset(
            notes, template, 'boom_bap', 'bass',
        )
        # The note should be shifted by the per-instrument offset
        offset = GENRE_TIMING_OFFSETS.get('boom_bap', {}).get('bass', 0)
        if offset != 0:
            assert result[0]['tick'] != notes[0]['tick']

    def test_apply_instrument_offset_fallback_unknown_genre(self):
        """Unknown genre should still return notes (falls back to apply)."""
        from multimodal_gen.groove_templates import GrooveApplicator, GrooveTemplate
        applicator = GrooveApplicator()
        template = GrooveTemplate(name="test")
        notes = [{'tick': 0, 'velocity': 100, 'note': 60}]
        result = applicator.apply_with_instrument_offset(
            notes, template, 'zydeco_reggae', 'bass',
        )
        assert len(result) == len(notes)


# ---------------------------------------------------------------------------
# Task 3 — Genre Fill Patterns + Energy-Aware Fill Selection
# ---------------------------------------------------------------------------

class TestGenreFillPatterns:

    def test_fill_patterns_exist(self):
        from multimodal_gen.drum_humanizer import GENRE_FILL_PATTERNS
        assert isinstance(GENRE_FILL_PATTERNS, dict)
        assert len(GENRE_FILL_PATTERNS) >= 3

    def test_trap_fill_patterns(self):
        from multimodal_gen.drum_humanizer import GENRE_FILL_PATTERNS
        assert 'trap' in GENRE_FILL_PATTERNS
        trap = GENRE_FILL_PATTERNS['trap']
        assert len(trap) >= 1

    def test_boom_bap_fills(self):
        from multimodal_gen.drum_humanizer import GENRE_FILL_PATTERNS
        assert 'boom_bap' in GENRE_FILL_PATTERNS

    def test_house_fills(self):
        from multimodal_gen.drum_humanizer import GENRE_FILL_PATTERNS
        assert 'house' in GENRE_FILL_PATTERNS

    def test_generate_pattern_fill(self):
        from multimodal_gen.drum_humanizer import DrumHumanizer
        humanizer = DrumHumanizer()
        fill = humanizer.generate_pattern_fill('trap', 'hi_hat_roll', start_tick=0)
        assert isinstance(fill, list)
        assert len(fill) > 0
        # Each element should be (tick, duration, pitch, velocity)
        for note in fill:
            assert len(note) == 4

    def test_generate_pattern_fill_with_offset(self):
        from multimodal_gen.drum_humanizer import DrumHumanizer
        humanizer = DrumHumanizer()
        fill = humanizer.generate_pattern_fill('boom_bap', 'classic_break', start_tick=1920)
        assert all(note[0] >= 1920 for note in fill)

    def test_generate_pattern_fill_unknown_genre(self):
        from multimodal_gen.drum_humanizer import DrumHumanizer
        humanizer = DrumHumanizer()
        fill = humanizer.generate_pattern_fill('polka', 'waltz', start_tick=0)
        assert fill == []

    def test_energy_aware_fill_selection(self):
        from multimodal_gen.drum_humanizer import energy_aware_fill_selection
        high_fill = energy_aware_fill_selection('trap', energy=0.9)
        low_fill = energy_aware_fill_selection('trap', energy=0.2)
        assert isinstance(high_fill, str)
        assert isinstance(low_fill, str)

    def test_energy_aware_different_energy_levels(self):
        from multimodal_gen.drum_humanizer import energy_aware_fill_selection
        low = energy_aware_fill_selection('trap', energy=0.1)
        high = energy_aware_fill_selection('trap', energy=0.9)
        # With two patterns, low and high should differ
        assert low != high

    def test_energy_aware_unknown_genre_fallback(self):
        from multimodal_gen.drum_humanizer import energy_aware_fill_selection
        result = energy_aware_fill_selection('unknown_genre_xyz', energy=0.5)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Regression guards – existing groove capabilities must still work
# ---------------------------------------------------------------------------

class TestExistingGrooveCapabilities:
    """Verify existing groove features still work."""

    def test_microtiming_apply(self):
        from multimodal_gen.microtiming import apply_microtiming
        assert callable(apply_microtiming)

    def test_groove_templates_presets(self):
        from multimodal_gen.groove_templates import PRESET_GROOVES
        assert len(PRESET_GROOVES) >= 10

    def test_drum_humanizer_ghost_notes(self):
        from multimodal_gen.drum_humanizer import add_ghost_notes
        assert callable(add_ghost_notes)

    def test_performance_models_exist(self):
        from multimodal_gen.performance_models import apply_performance_model
        assert callable(apply_performance_model)

    def test_dynamics_apply_existing(self):
        from multimodal_gen.dynamics import DynamicsEngine, DynamicsConfig
        engine = DynamicsEngine()
        notes = [(0, 480, 60, 100), (480, 480, 62, 90)]
        config = DynamicsConfig()
        result = engine.apply(notes, config)
        assert len(result) == len(notes)

    def test_dynamics_genre_presets(self):
        from multimodal_gen.dynamics import GENRE_DYNAMICS
        assert len(GENRE_DYNAMICS) >= 10

    def test_groove_applicator_apply(self):
        from multimodal_gen.groove_templates import GrooveApplicator, GrooveTemplate
        applicator = GrooveApplicator()
        template = GrooveTemplate(name="test")
        notes = [{'tick': 0, 'velocity': 100, 'note': 60}]
        result = applicator.apply(notes, template)
        assert len(result) == 1

    def test_fill_generation(self):
        from multimodal_gen.drum_humanizer import DrumHumanizer, FillConfig
        humanizer = DrumHumanizer()
        config = FillConfig()
        fill = humanizer.generate_fill('trap', 2.0, config, seed=42)
        assert isinstance(fill, list)
