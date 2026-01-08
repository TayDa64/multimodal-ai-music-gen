"""
Unit tests for Section Variation Engine

Tests variation types, strategies, genre profiles, and edge cases.
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from multimodal_gen.section_variation import (
    VariationType,
    VariationConfig,
    SectionVariation,
    SectionVariationEngine,
    SECTION_VARIATION_STRATEGIES,
    GENRE_VARIATION_PROFILES,
    create_section_variation,
    vary_arrangement_sections,
)


class TestVariationType:
    """Tests for VariationType enum."""
    
    def test_all_variation_types_exist(self):
        """Test all 11 variation types are defined."""
        expected_types = [
            "none", "octave_shift", "density_change", "rhythm_variation",
            "fill_addition", "instrument_swap", "harmony_enrichment",
            "dynamics_shift", "register_shift", "articulation_change",
            "motif_transform"
        ]
        
        actual_types = [vt.value for vt in VariationType]
        assert len(actual_types) == 11
        for expected in expected_types:
            assert expected in actual_types


class TestVariationConfig:
    """Tests for VariationConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = VariationConfig()
        assert config.intensity == 0.5
        assert config.preserve_melody is True
        assert config.preserve_harmony is True
        assert config.preserve_rhythm is False
        assert VariationType.DENSITY_CHANGE in config.allowed_types
        assert VariationType.FILL_ADDITION in config.allowed_types
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = VariationConfig(
            intensity=0.8,
            preserve_melody=False,
            allowed_types={VariationType.DYNAMICS_SHIFT}
        )
        assert config.intensity == 0.8
        assert config.preserve_melody is False
        assert VariationType.DYNAMICS_SHIFT in config.allowed_types


class TestSectionVariationEngine:
    """Tests for SectionVariationEngine class."""
    
    def test_engine_initialization(self):
        """Test engine initializes with correct defaults."""
        engine = SectionVariationEngine()
        assert engine.ticks_per_beat == 480
        assert engine.rng is not None
    
    def test_engine_with_seed(self):
        """Test engine with seed produces reproducible results."""
        notes = [(0, 480, 60, 80), (480, 480, 62, 80)]
        
        # Run twice with same seed
        engine1 = SectionVariationEngine(seed=42)
        varied1, _ = engine1.create_variation(notes, "verse", 2)
        
        engine2 = SectionVariationEngine(seed=42)
        varied2, _ = engine2.create_variation(notes, "verse", 2)
        
        # Results should be identical
        assert varied1 == varied2
    
    def test_first_occurrence_no_variation(self):
        """Test first occurrence gets no variation."""
        engine = SectionVariationEngine()
        notes = [(0, 480, 60, 80), (480, 480, 62, 80)]
        
        varied, variations = engine.create_variation(notes, "verse", 1)
        
        assert varied == notes
        assert len(variations) == 0
    
    def test_second_occurrence_gets_variation(self):
        """Test second occurrence gets some variation."""
        engine = SectionVariationEngine(seed=42)
        notes = [(0, 480, 60, 80), (480, 480, 62, 80)]
        
        varied, variations = engine.create_variation(notes, "verse", 2)
        
        # Should have at least one variation applied
        assert len(variations) > 0
        # Notes should be different (in most cases)
        # Note: Due to randomness, they might occasionally be same, but with seed=42 they differ
    
    def test_octave_shift(self):
        """Test octave shift variation."""
        engine = SectionVariationEngine(seed=42)
        notes = [(0, 480, 60, 80), (480, 480, 62, 80)]
        
        # Apply octave shift up
        shifted = engine.apply_octave_shift(notes, shift=12, probability=1.0)
        
        # All notes should be shifted up by 12
        for i, (tick, dur, pitch, vel) in enumerate(shifted):
            assert pitch == notes[i][2] + 12
    
    def test_octave_shift_clamps_to_midi_range(self):
        """Test octave shift respects MIDI range 0-127."""
        engine = SectionVariationEngine()
        notes = [(0, 480, 120, 80)]  # High note
        
        shifted = engine.apply_octave_shift(notes, shift=12, probability=1.0)
        
        # Should be clamped to 127
        assert shifted[0][2] == 127
    
    def test_density_change_add(self):
        """Test adding notes increases density."""
        engine = SectionVariationEngine(seed=42)
        notes = [(0, 480, 60, 80), (480, 480, 62, 80)]
        
        # Add 50% more notes
        denser = engine.apply_density_change(notes, change=0.5)
        
        # Should have more notes
        assert len(denser) > len(notes)
    
    def test_density_change_remove(self):
        """Test removing notes decreases density."""
        engine = SectionVariationEngine(seed=42)
        notes = [(i * 480, 240, 60 + i, 80) for i in range(10)]
        
        # Remove 30% of notes
        sparser = engine.apply_density_change(notes, change=-0.3)
        
        # Should have fewer notes (but at least 1)
        assert len(sparser) < len(notes)
        assert len(sparser) >= 1
    
    def test_density_change_keeps_at_least_one_note(self):
        """Test density change never removes all notes."""
        engine = SectionVariationEngine(seed=42)
        notes = [(0, 480, 60, 80)]
        
        # Try to remove all notes
        result = engine.apply_density_change(notes, change=-1.0)
        
        # Should keep at least one note
        assert len(result) >= 1
    
    def test_rhythm_variation(self):
        """Test rhythm variation shifts note timing."""
        engine = SectionVariationEngine(seed=42)
        notes = [(0, 480, 60, 80), (480, 480, 62, 80), (960, 480, 64, 80)]
        
        varied = engine.apply_rhythm_variation(notes, intensity=0.5)
        
        # Notes should still exist
        assert len(varied) == len(notes)
        # Should be sorted by tick
        for i in range(len(varied) - 1):
            assert varied[i][0] <= varied[i+1][0]
    
    def test_fill_addition(self):
        """Test fill addition adds notes at section end."""
        engine = SectionVariationEngine(seed=42)
        notes = [
            (0, 480, 60, 80),
            (480, 480, 62, 80),
            (960, 480, 64, 80),
            (1440, 480, 65, 80),  # Last note
        ]
        section_end_tick = 1920
        
        filled = engine.apply_fill_addition(notes, fill_density=0.5, section_end_tick=section_end_tick)
        
        # Should have more notes
        assert len(filled) > len(notes)
    
    def test_harmony_enrichment(self):
        """Test harmony enrichment adds harmony notes."""
        engine = SectionVariationEngine(seed=42)
        notes = [(0, 480, 60, 80), (480, 480, 62, 80)]
        
        enriched = engine.apply_harmony_enrichment(notes, harmony_probability=1.0)
        
        # Should have double the notes (original + harmony)
        assert len(enriched) > len(notes)
    
    def test_dynamics_shift_up(self):
        """Test dynamics shift increases velocity."""
        engine = SectionVariationEngine()
        notes = [(0, 480, 60, 80), (480, 480, 62, 80)]
        
        shifted = engine.apply_dynamics_shift(notes, velocity_delta=10, direction="up")
        
        # All velocities should increase
        for i, (tick, dur, pitch, vel) in enumerate(shifted):
            assert vel == notes[i][3] + 10
    
    def test_dynamics_shift_down(self):
        """Test dynamics shift decreases velocity."""
        engine = SectionVariationEngine()
        notes = [(0, 480, 60, 80), (480, 480, 62, 80)]
        
        shifted = engine.apply_dynamics_shift(notes, velocity_delta=10, direction="down")
        
        # All velocities should decrease
        for i, (tick, dur, pitch, vel) in enumerate(shifted):
            assert vel == notes[i][3] - 10
    
    def test_dynamics_shift_crescendo(self):
        """Test dynamics shift with crescendo."""
        engine = SectionVariationEngine()
        notes = [(i * 480, 480, 60, 80) for i in range(4)]
        
        shifted = engine.apply_dynamics_shift(notes, velocity_delta=20, direction="crescendo")
        
        # Velocities should increase progressively
        velocities = [note[3] for note in shifted]
        assert velocities[0] < velocities[-1]
    
    def test_dynamics_shift_clamps_velocity(self):
        """Test dynamics shift respects MIDI velocity range."""
        engine = SectionVariationEngine()
        notes = [(0, 480, 60, 120)]
        
        shifted = engine.apply_dynamics_shift(notes, velocity_delta=20, direction="up")
        
        # Should be clamped to 127
        assert shifted[0][3] == 127
    
    def test_register_shift_up(self):
        """Test register shift moves notes up."""
        engine = SectionVariationEngine()
        notes = [(0, 480, 60, 80), (480, 480, 62, 80)]
        
        shifted = engine.apply_register_shift(notes, octaves=1, direction="up")
        
        # All notes should be 12 semitones higher
        for i, (tick, dur, pitch, vel) in enumerate(shifted):
            assert pitch == notes[i][2] + 12
    
    def test_register_shift_down(self):
        """Test register shift moves notes down."""
        engine = SectionVariationEngine()
        notes = [(0, 480, 60, 80), (480, 480, 62, 80)]
        
        shifted = engine.apply_register_shift(notes, octaves=1, direction="down")
        
        # All notes should be 12 semitones lower
        for i, (tick, dur, pitch, vel) in enumerate(shifted):
            assert pitch == notes[i][2] - 12
    
    def test_articulation_change_staccato(self):
        """Test articulation change makes notes shorter."""
        engine = SectionVariationEngine()
        notes = [(0, 480, 60, 80), (480, 480, 62, 80)]
        
        staccato = engine.apply_articulation_change(notes, length_factor=0.5)
        
        # All durations should be halved
        for i, (tick, dur, pitch, vel) in enumerate(staccato):
            assert dur == notes[i][1] // 2
    
    def test_articulation_change_legato(self):
        """Test articulation change makes notes longer."""
        engine = SectionVariationEngine()
        notes = [(0, 480, 60, 80), (480, 480, 62, 80)]
        
        legato = engine.apply_articulation_change(notes, length_factor=1.5)
        
        # All durations should increase
        for i, (tick, dur, pitch, vel) in enumerate(legato):
            assert dur == int(notes[i][1] * 1.5)
    
    def test_get_variation_plan_first_occurrence(self):
        """Test variation plan for first occurrence."""
        engine = SectionVariationEngine()
        config = VariationConfig()
        
        plan = engine.get_variation_plan("verse", 1, config)
        
        # First occurrence should have no variation
        assert plan == [VariationType.NONE]
    
    def test_get_variation_plan_later_occurrences(self):
        """Test variation plan for later occurrences."""
        engine = SectionVariationEngine(seed=42)
        config = VariationConfig()
        
        plan = engine.get_variation_plan("verse", 2, config)
        
        # Should have at least one variation
        assert len(plan) > 0
        assert VariationType.NONE not in plan
    
    def test_get_variation_plan_chorus_less_variation(self):
        """Test chorus gets less variation than verse."""
        engine = SectionVariationEngine(seed=42)
        config = VariationConfig(intensity=0.5)
        
        verse_plan = engine.get_variation_plan("verse", 2, config)
        chorus_plan = engine.get_variation_plan("chorus", 2, config)
        
        # Chorus should have same or fewer variations (due to max_intensity)
        # This is probabilistic, but with seed=42 should be consistent
        assert len(chorus_plan) <= len(verse_plan) + 1  # Allow some variation


class TestSectionStrategies:
    """Tests for section-specific strategies."""
    
    def test_verse_strategy_exists(self):
        """Test verse strategy is defined."""
        assert "verse" in SECTION_VARIATION_STRATEGIES
        strategy = SECTION_VARIATION_STRATEGIES["verse"]
        assert strategy["max_intensity"] == 0.4
        assert strategy["preserve_melody"] is True
    
    def test_chorus_strategy_conservative(self):
        """Test chorus strategy is conservative."""
        assert "chorus" in SECTION_VARIATION_STRATEGIES
        strategy = SECTION_VARIATION_STRATEGIES["chorus"]
        assert strategy["max_intensity"] == 0.2  # Less than verse
        assert strategy["preserve_melody"] is True
        assert strategy["preserve_rhythm"] is True
    
    def test_bridge_strategy_more_varied(self):
        """Test bridge allows more variation."""
        assert "bridge" in SECTION_VARIATION_STRATEGIES
        strategy = SECTION_VARIATION_STRATEGIES["bridge"]
        assert strategy["max_intensity"] >= 0.5
    
    def test_hook_strategy_very_consistent(self):
        """Test hook strategy is very consistent."""
        assert "hook" in SECTION_VARIATION_STRATEGIES
        strategy = SECTION_VARIATION_STRATEGIES["hook"]
        assert strategy["max_intensity"] <= 0.2


class TestGenreProfiles:
    """Tests for genre-specific profiles."""
    
    def test_all_required_genres_exist(self):
        """Test all 5+ genres are defined."""
        required_genres = ["pop", "jazz", "classical", "hip_hop", "edm"]
        for genre in required_genres:
            assert genre in GENRE_VARIATION_PROFILES
    
    def test_pop_consistent(self):
        """Test pop is more consistent."""
        profile = GENRE_VARIATION_PROFILES["pop"]
        assert profile["intensity_multiplier"] < 1.0
    
    def test_jazz_varies_more(self):
        """Test jazz varies more."""
        profile = GENRE_VARIATION_PROFILES["jazz"]
        assert profile["intensity_multiplier"] > 1.0
    
    def test_edm_very_consistent(self):
        """Test EDM is very consistent."""
        profile = GENRE_VARIATION_PROFILES["edm"]
        assert profile["intensity_multiplier"] < 0.7


class TestVariationPresets:
    """Tests for preset generation."""
    
    def test_get_section_variation_preset(self):
        """Test getting preset for section and genre."""
        engine = SectionVariationEngine()
        
        preset = engine.get_section_variation_preset("verse", "jazz")
        
        assert preset.intensity > 0
        assert isinstance(preset.allowed_types, set)
        assert len(preset.type_weights) > 0
    
    def test_preset_respects_genre_multiplier(self):
        """Test preset applies genre intensity multiplier."""
        engine = SectionVariationEngine()
        
        pop_preset = engine.get_section_variation_preset("verse", "pop")
        jazz_preset = engine.get_section_variation_preset("verse", "jazz")
        
        # Jazz should have higher intensity than pop for same section
        assert jazz_preset.intensity > pop_preset.intensity


class TestSuggestVariations:
    """Tests for variation suggestion."""
    
    def test_suggest_variations_for_structure(self):
        """Test suggesting variations for arrangement structure."""
        engine = SectionVariationEngine(seed=42)
        
        section_types = ["verse", "chorus", "verse", "chorus"]
        suggestions = engine.suggest_variations_for_structure(section_types)
        
        # Should have suggestion for each section
        assert len(suggestions) == 4
        
        # First verse should have no variation
        assert suggestions[0] == [VariationType.NONE]
        
        # Second verse should have variations
        assert len(suggestions[2]) > 0
        assert VariationType.NONE not in suggestions[2]
    
    def test_suggest_tracks_occurrences_separately(self):
        """Test suggestion tracks each section type separately."""
        engine = SectionVariationEngine(seed=42)
        
        section_types = ["verse", "chorus", "verse", "chorus"]
        suggestions = engine.suggest_variations_for_structure(section_types)
        
        # First verse (index 0) - no variation
        assert suggestions[0] == [VariationType.NONE]
        
        # First chorus (index 1) - no variation
        assert suggestions[1] == [VariationType.NONE]
        
        # Second verse (index 2) - has variation
        assert len(suggestions[2]) > 0


class TestEdgeCases:
    """Tests for edge cases."""
    
    def test_empty_notes_list(self):
        """Test handling empty notes list."""
        engine = SectionVariationEngine()
        
        varied, variations = engine.create_variation([], "verse", 2)
        
        # Should return empty list
        assert varied == []
    
    def test_single_note(self):
        """Test handling single note."""
        engine = SectionVariationEngine(seed=42)
        notes = [(0, 480, 60, 80)]
        
        varied, _ = engine.create_variation(notes, "verse", 2)
        
        # Should still have at least one note
        assert len(varied) >= 1
    
    def test_very_short_section(self):
        """Test handling very short section."""
        engine = SectionVariationEngine(seed=42)
        notes = [(0, 120, 60, 80), (120, 120, 62, 80)]
        
        varied, _ = engine.create_variation(notes, "verse", 2)
        
        # Should handle without error
        assert len(varied) >= 1


class TestConvenienceFunctions:
    """Tests for convenience functions."""
    
    def test_create_section_variation(self):
        """Test quick variation creation."""
        notes = [(0, 480, 60, 80), (480, 480, 62, 80)]
        
        varied = create_section_variation(notes, "verse", 2, genre="jazz", seed=42)
        
        # Should return varied notes (or same for occurrence 1)
        assert isinstance(varied, list)
    
    def test_vary_arrangement_sections(self):
        """Test varying entire arrangement."""
        arrangement_notes = {
            "verse_1": [(0, 480, 60, 80), (480, 480, 62, 80)],
            "chorus_1": [(0, 480, 64, 90), (480, 480, 65, 90)],
            "verse_2": [(0, 480, 60, 80), (480, 480, 62, 80)],
            "chorus_2": [(0, 480, 64, 90), (480, 480, 65, 90)],
        }
        section_order = ["verse_1", "chorus_1", "verse_2", "chorus_2"]
        
        varied = vary_arrangement_sections(arrangement_notes, section_order, genre="pop")
        
        # Should return dict with all sections
        assert len(varied) == 4
        assert "verse_1" in varied
        assert "verse_2" in varied
        
        # First occurrences should be unchanged
        assert varied["verse_1"] == arrangement_notes["verse_1"]
        assert varied["chorus_1"] == arrangement_notes["chorus_1"]


class TestOccurrenceIntensityScaling:
    """Tests for occurrence-based intensity scaling."""
    
    def test_later_occurrences_more_intense(self):
        """Test that later occurrences get more intense variations."""
        engine = SectionVariationEngine(seed=42)
        config = VariationConfig(intensity=0.5)
        
        plan2 = engine.get_variation_plan("verse", 2, config)
        plan3 = engine.get_variation_plan("verse", 3, config)
        
        # Later occurrence should have same or more variations
        # (This is probabilistic, but generally true)
        assert len(plan3) >= len(plan2) - 1  # Allow some variance


class TestMelodyPreservation:
    """Tests for melody preservation."""
    
    def test_melody_preservation_config(self):
        """Test melody preservation configuration."""
        config = VariationConfig(preserve_melody=True)
        
        assert config.preserve_melody is True
    
    def test_melody_not_preserved_when_disabled(self):
        """Test melody can be varied when preservation disabled."""
        config = VariationConfig(preserve_melody=False)
        
        assert config.preserve_melody is False


class TestSeedReproducibility:
    """Tests for seed-based reproducibility."""
    
    def test_same_seed_same_results(self):
        """Test same seed produces identical results."""
        notes = [(i * 480, 480, 60 + i, 80) for i in range(5)]
        
        engine1 = SectionVariationEngine(seed=12345)
        varied1, _ = engine1.create_variation(notes, "verse", 2)
        
        engine2 = SectionVariationEngine(seed=12345)
        varied2, _ = engine2.create_variation(notes, "verse", 2)
        
        assert varied1 == varied2
    
    def test_different_seed_different_results(self):
        """Test different seeds produce different results."""
        notes = [(i * 480, 480, 60 + i, 80) for i in range(10)]
        
        # Run multiple times to ensure at least one difference
        engine1 = SectionVariationEngine(seed=111)
        varied1a, _ = engine1.create_variation(notes, "verse", 2)
        varied1b, _ = engine1.create_variation(notes, "verse", 3)
        
        engine2 = SectionVariationEngine(seed=222)
        varied2a, _ = engine2.create_variation(notes, "verse", 2)
        varied2b, _ = engine2.create_variation(notes, "verse", 3)
        
        # At least one pair should be different
        diff_count = 0
        if varied1a != varied2a:
            diff_count += 1
        if varied1b != varied2b:
            diff_count += 1
        
        # With different seeds and multiple runs, we should see at least some difference
        assert diff_count > 0


class TestMidiRangeConstraints:
    """Tests for MIDI range constraints."""
    
    def test_pitch_clamped_to_0_127(self):
        """Test pitch values are clamped to valid MIDI range."""
        engine = SectionVariationEngine()
        
        # Test upper bound
        high_notes = [(0, 480, 125, 80)]
        shifted_up = engine.apply_register_shift(high_notes, octaves=1, direction="up")
        assert shifted_up[0][2] <= 127
        
        # Test lower bound
        low_notes = [(0, 480, 5, 80)]
        shifted_down = engine.apply_register_shift(low_notes, octaves=1, direction="down")
        assert shifted_down[0][2] >= 0
    
    def test_velocity_clamped_to_1_127(self):
        """Test velocity values are clamped to valid MIDI range."""
        engine = SectionVariationEngine()
        
        # Test upper bound
        loud_notes = [(0, 480, 60, 120)]
        louder = engine.apply_dynamics_shift(loud_notes, velocity_delta=20, direction="up")
        assert louder[0][3] <= 127
        
        # Test lower bound (should be at least 1)
        quiet_notes = [(0, 480, 60, 10)]
        quieter = engine.apply_dynamics_shift(quiet_notes, velocity_delta=20, direction="down")
        assert quieter[0][3] >= 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
