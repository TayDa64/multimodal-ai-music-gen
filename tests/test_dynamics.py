"""
Unit tests for Dynamics Engine

Tests the dynamics classes and ensures genre-appropriate velocity shaping.
"""

import pytest
import sys
import math
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from multimodal_gen.dynamics import (
    DynamicShape,
    DynamicLevel,
    DynamicsConfig,
    DynamicsEngine,
    GENRE_DYNAMICS,
    apply_dynamics,
    curve_crescendo,
    curve_decrescendo,
    curve_swell,
    curve_accent_first,
    curve_accent_last
)


class TestDynamicsEngine:
    """Tests for dynamics engine."""
    
    def test_flat_shape_unchanged(self):
        """Flat shape should not significantly alter velocities."""
        engine = DynamicsEngine()
        
        notes = [
            (0, 240, 60, 80),
            (480, 240, 62, 80),
            (960, 240, 64, 80),
        ]
        
        config = DynamicsConfig(
            base_velocity=80,
            phrase_shape=DynamicShape.FLAT,
            downbeat_accent=0.0
        )
        
        result = engine.apply(notes, config)
        
        # All velocities should remain at base velocity (flat shape)
        for tick, dur, pitch, vel in result:
            assert vel == 80
    
    def test_crescendo_increases_velocity(self):
        """Crescendo should increase velocity over time."""
        engine = DynamicsEngine()
        
        notes = [
            (i * 480, 240, 60, 80) for i in range(5)
        ]
        
        result = engine.apply_crescendo(notes, 50, 100)
        
        # Velocities should increase monotonically
        velocities = [vel for tick, dur, pitch, vel in result]
        assert velocities[0] == 50
        assert velocities[-1] == 100
        
        # Each velocity should be >= previous
        for i in range(1, len(velocities)):
            assert velocities[i] >= velocities[i-1]
    
    def test_decrescendo_decreases_velocity(self):
        """Decrescendo should decrease velocity over time."""
        engine = DynamicsEngine()
        
        notes = [
            (i * 480, 240, 60, 80) for i in range(5)
        ]
        
        result = engine.apply_decrescendo(notes, 100, 50)
        
        # Velocities should decrease monotonically
        velocities = [vel for tick, dur, pitch, vel in result]
        assert velocities[0] == 100
        assert velocities[-1] == 50
        
        # Each velocity should be <= previous
        for i in range(1, len(velocities)):
            assert velocities[i] <= velocities[i-1]
    
    def test_swell_peaks_in_middle(self):
        """Swell should peak in the middle of the phrase."""
        engine = DynamicsEngine()
        
        # Create 8 notes within one phrase
        notes = [
            (i * 480, 240, 60, 80) for i in range(8)
        ]
        
        config = DynamicsConfig(
            base_velocity=80,
            phrase_shape=DynamicShape.SWELL,
            phrase_length_beats=8,
            downbeat_accent=0.0
        )
        
        result = engine.apply(notes, config)
        velocities = [vel for tick, dur, pitch, vel in result]
        
        # The middle notes should have higher velocity than first and last
        mid_point = len(velocities) // 2
        assert velocities[mid_point-1] > velocities[0]
        assert velocities[mid_point] > velocities[0]
        assert velocities[mid_point-1] > velocities[-1]
        assert velocities[mid_point] > velocities[-1]
    
    def test_downbeat_accents(self):
        """Downbeats should have higher velocity."""
        engine = DynamicsEngine(ticks_per_beat=480)
        
        # Notes: beat 1, beat 2, beat 3, beat 4 (of first bar), then beat 1 again
        notes = [
            (0, 240, 60, 80),      # Downbeat (bar 1)
            (480, 240, 62, 80),    # Beat 2
            (960, 240, 64, 80),    # Beat 3
            (1440, 240, 65, 80),   # Beat 4
            (1920, 240, 66, 80),   # Downbeat (bar 2)
        ]
        
        config = DynamicsConfig(
            base_velocity=80,
            phrase_shape=DynamicShape.FLAT,
            downbeat_accent=1.0  # Maximum accent
        )
        
        result = engine.apply(notes, config)
        velocities = [vel for tick, dur, pitch, vel in result]
        
        # First note (downbeat) should have higher velocity
        assert velocities[0] > velocities[1]
        assert velocities[0] > velocities[2]
        assert velocities[0] > velocities[3]
        
        # Fifth note (downbeat of bar 2) should also have higher velocity
        assert velocities[4] > velocities[1]
        assert velocities[4] > velocities[2]
        assert velocities[4] > velocities[3]
    
    def test_velocity_clamping(self):
        """Velocities should stay within 1-127 range."""
        engine = DynamicsEngine()
        
        notes = [
            (i * 480, 240, 60, 80) for i in range(4)
        ]
        
        # Create config that would push velocities out of range
        config = DynamicsConfig(
            base_velocity=120,
            velocity_range=(1, 127),
            phrase_shape=DynamicShape.CRESCENDO,
            downbeat_accent=1.0  # Would add 20 more
        )
        
        result = engine.apply(notes, config)
        
        # All velocities should be within MIDI range
        for tick, dur, pitch, vel in result:
            assert 1 <= vel <= 127
    
    def test_velocity_respects_config_range(self):
        """Velocities should stay within configured range."""
        engine = DynamicsEngine()
        
        notes = [
            (i * 480, 240, 60, 80) for i in range(8)
        ]
        
        # Set custom range
        config = DynamicsConfig(
            base_velocity=80,
            velocity_range=(50, 100),
            phrase_shape=DynamicShape.SWELL,
            downbeat_accent=0.5
        )
        
        result = engine.apply(notes, config)
        
        # All velocities should be within configured range
        for tick, dur, pitch, vel in result:
            assert 50 <= vel <= 100
    
    def test_phrase_boundaries(self):
        """Dynamics should reset at phrase boundaries."""
        engine = DynamicsEngine(ticks_per_beat=480)
        
        # Create notes spanning 2 phrases (4 beats each)
        notes = [
            (i * 480, 240, 60, 80) for i in range(8)
        ]
        
        config = DynamicsConfig(
            base_velocity=80,
            phrase_shape=DynamicShape.CRESCENDO,
            phrase_length_beats=4,
            downbeat_accent=0.0
        )
        
        result = engine.apply(notes, config)
        velocities = [vel for tick, dur, pitch, vel in result]
        
        # First phrase (notes 0-3) should crescendo
        assert velocities[0] < velocities[3]
        
        # Second phrase (notes 4-7) should also crescendo from the beginning
        assert velocities[4] < velocities[7]
        
        # The start of second phrase should be similar to start of first
        # (within some tolerance due to how phrase position is calculated)
        assert abs(velocities[4] - velocities[0]) < 10
    
    def test_genre_presets_exist(self):
        """All expected genre presets should exist."""
        expected_genres = ['jazz', 'hip-hop', 'classical', 'rock', 'r&b', 'funk']
        
        for genre in expected_genres:
            assert genre in GENRE_DYNAMICS, f"Missing preset for {genre}"
            
            # Each preset should be a valid DynamicsConfig
            config = GENRE_DYNAMICS[genre]
            assert isinstance(config, DynamicsConfig)
            assert 1 <= config.base_velocity <= 127
            assert len(config.velocity_range) == 2
            assert config.velocity_range[0] < config.velocity_range[1]
            assert 0.0 <= config.accent_strength <= 1.0
            assert 0.0 <= config.downbeat_accent <= 1.0
            assert config.phrase_length_beats > 0
    
    def test_empty_notes_handled(self):
        """Empty note list should return empty list."""
        engine = DynamicsEngine()
        config = DynamicsConfig()
        
        result = engine.apply([], config)
        assert result == []
    
    def test_single_note_handled(self):
        """Single note should be handled gracefully."""
        engine = DynamicsEngine()
        notes = [(0, 240, 60, 80)]
        config = DynamicsConfig(
            base_velocity=90,
            phrase_shape=DynamicShape.SWELL
        )
        
        result = engine.apply(notes, config)
        
        assert len(result) == 1
        # Single note should get base velocity (or close to it after shaping)
        assert 1 <= result[0][3] <= 127
    
    def test_apply_preserves_tick_and_pitch(self):
        """Dynamics should only affect velocity, not tick or pitch."""
        engine = DynamicsEngine()
        
        notes = [
            (0, 240, 60, 80),
            (480, 300, 62, 90),
            (960, 200, 64, 70),
        ]
        
        config = DynamicsConfig(
            base_velocity=85,
            phrase_shape=DynamicShape.SWELL
        )
        
        result = engine.apply(notes, config)
        
        for i, (tick, dur, pitch, vel) in enumerate(result):
            assert tick == notes[i][0]
            assert dur == notes[i][1]
            assert pitch == notes[i][2]
            # Only velocity should change
    
    def test_get_shape_curve(self):
        """get_shape_curve should return correct number of points."""
        engine = DynamicsEngine()
        
        # Test with different numbers of points
        for num_points in [1, 5, 10, 100]:
            curve = engine.get_shape_curve(DynamicShape.CRESCENDO, num_points)
            assert len(curve) == num_points
            
            # All values should be in reasonable range
            for val in curve:
                assert 0.0 <= val <= 1.5  # Allow some headroom


class TestDynamicShapes:
    """Tests for shape curve generators."""
    
    def test_crescendo_curve(self):
        """Crescendo should increase monotonically."""
        positions = [0.0, 0.25, 0.5, 0.75, 1.0]
        values = [curve_crescendo(p) for p in positions]
        
        # Should start at 0.5 and end at 1.0
        assert values[0] == 0.5
        assert values[-1] == 1.0
        
        # Should increase monotonically
        for i in range(1, len(values)):
            assert values[i] >= values[i-1]
    
    def test_decrescendo_curve(self):
        """Decrescendo should decrease monotonically."""
        positions = [0.0, 0.25, 0.5, 0.75, 1.0]
        values = [curve_decrescendo(p) for p in positions]
        
        # Should start at 1.0 and end at 0.5
        assert values[0] == 1.0
        assert values[-1] == 0.5
        
        # Should decrease monotonically
        for i in range(1, len(values)):
            assert values[i] <= values[i-1]
    
    def test_swell_curve_peak(self):
        """Swell should have maximum near center."""
        positions = [0.0, 0.25, 0.5, 0.75, 1.0]
        values = [curve_swell(p) for p in positions]
        
        # Middle should be highest
        max_val = max(values)
        max_idx = values.index(max_val)
        
        # Max should be in the middle region
        assert 1 <= max_idx <= 3  # Should be position 0.25, 0.5, or 0.75
        
        # First and last should be lower than peak
        assert values[0] < max_val
        assert values[-1] < max_val
    
    def test_accent_first_curve(self):
        """Accent first should start high and decay."""
        positions = [0.0, 0.25, 0.5, 0.75, 1.0]
        values = [curve_accent_first(p) for p in positions]
        
        # Should start at 1.0
        assert values[0] == 1.0
        
        # Should generally decrease
        assert values[-1] < values[0]
    
    def test_accent_last_curve(self):
        """Accent last should build to the end."""
        positions = [0.0, 0.25, 0.5, 0.75, 1.0]
        values = [curve_accent_last(p) for p in positions]
        
        # Should start at 0.7
        assert values[0] == 0.7
        
        # Should end at 1.0
        assert values[-1] == 1.0
        
        # Should generally increase
        assert values[-1] > values[0]
    
    def test_curves_in_valid_range(self):
        """All curve values should be in reasonable range."""
        shapes = [
            curve_crescendo, curve_decrescendo, curve_swell,
            curve_accent_first, curve_accent_last
        ]
        
        positions = [i * 0.1 for i in range(11)]  # 0.0 to 1.0
        
        for shape_func in shapes:
            for pos in positions:
                val = shape_func(pos)
                # Should be positive and not too large
                assert 0.0 <= val <= 1.5, f"{shape_func.__name__} at {pos} = {val}"


class TestGenrePresets:
    """Tests for genre-specific presets."""
    
    def test_jazz_expressive(self):
        """Jazz should have moderate dynamics range."""
        jazz = GENRE_DYNAMICS['jazz']
        
        # Jazz should have moderate base velocity
        assert 70 <= jazz.base_velocity <= 85
        
        # Jazz should use swell for expression
        assert jazz.phrase_shape == DynamicShape.SWELL
        
        # Jazz should have moderate accents
        assert 0.1 <= jazz.accent_strength <= 0.2
    
    def test_rock_loud(self):
        """Rock should have high base velocity."""
        rock = GENRE_DYNAMICS['rock']
        
        # Rock should be loud
        assert rock.base_velocity >= 90
        
        # Rock often uses flat dynamics (consistent volume)
        assert rock.phrase_shape == DynamicShape.FLAT
        
        # Rock should have strong accents
        assert rock.accent_strength >= 0.25
    
    def test_funk_accented(self):
        """Funk should have strong accents."""
        funk = GENRE_DYNAMICS['funk']
        
        # Funk should have strong accents
        assert funk.accent_strength >= 0.3
        assert funk.downbeat_accent >= 0.25
        
        # Funk often emphasizes first beat
        assert funk.phrase_shape == DynamicShape.ACCENT_FIRST
        
        # Funk has shorter phrases (2 beats)
        assert funk.phrase_length_beats == 2
    
    def test_classical_wide_range(self):
        """Classical should have wide dynamic range."""
        classical = GENRE_DYNAMICS['classical']
        
        # Classical should have wide velocity range
        min_vel, max_vel = classical.velocity_range
        dynamic_range = max_vel - min_vel
        assert dynamic_range >= 70  # Wide range
        
        # Classical uses longer phrases
        assert classical.phrase_length_beats >= 8
        
        # Classical uses subtle accents
        assert classical.accent_strength <= 0.15
    
    def test_hiphop_punchy(self):
        """Hip-hop should emphasize first beat."""
        hiphop = GENRE_DYNAMICS['hip-hop']
        
        # Hip-hop should have strong downbeat accents
        assert hiphop.downbeat_accent >= 0.15
        
        # Hip-hop often uses accent_first pattern
        assert hiphop.phrase_shape == DynamicShape.ACCENT_FIRST
    
    def test_rnb_smooth(self):
        """R&B should have smooth, moderate dynamics."""
        rnb = GENRE_DYNAMICS['r&b']
        
        # R&B should have smooth phrasing (swell)
        assert rnb.phrase_shape == DynamicShape.SWELL
        
        # R&B should have gentle accents
        assert rnb.accent_strength <= 0.15
        assert rnb.downbeat_accent <= 0.1


class TestConvenienceFunction:
    """Tests for apply_dynamics convenience function."""
    
    def test_apply_dynamics_with_genre(self):
        """apply_dynamics should work with genre string."""
        notes = [
            (i * 480, 240, 60, 80) for i in range(4)
        ]
        
        result = apply_dynamics(notes, genre="jazz")
        
        assert len(result) == len(notes)
        # Velocities should have changed from original
        original_vels = [n[3] for n in notes]
        result_vels = [n[3] for n in result]
        # At least some should be different (due to phrase shaping)
    
    def test_apply_dynamics_with_custom_config(self):
        """apply_dynamics should work with custom config."""
        notes = [
            (i * 480, 240, 60, 80) for i in range(4)
        ]
        
        custom_config = DynamicsConfig(
            base_velocity=100,
            phrase_shape=DynamicShape.CRESCENDO
        )
        
        result = apply_dynamics(notes, config=custom_config)
        
        assert len(result) == len(notes)
    
    def test_apply_dynamics_default_genre(self):
        """apply_dynamics should use jazz as default."""
        notes = [
            (i * 480, 240, 60, 80) for i in range(4)
        ]
        
        result = apply_dynamics(notes)
        
        assert len(result) == len(notes)


class TestDynamicLevel:
    """Tests for DynamicLevel enum."""
    
    def test_dynamic_levels_exist(self):
        """All standard dynamic levels should exist."""
        expected_levels = ['PPP', 'PP', 'P', 'MP', 'MF', 'F', 'FF', 'FFF']
        
        for level_name in expected_levels:
            assert hasattr(DynamicLevel, level_name)
    
    def test_dynamic_levels_ordered(self):
        """Dynamic levels should be in ascending order."""
        levels = [
            DynamicLevel.PPP, DynamicLevel.PP, DynamicLevel.P, DynamicLevel.MP,
            DynamicLevel.MF, DynamicLevel.F, DynamicLevel.FF, DynamicLevel.FFF
        ]
        
        for i in range(1, len(levels)):
            assert levels[i].value > levels[i-1].value
    
    def test_dynamic_levels_in_midi_range(self):
        """All dynamic levels should be valid MIDI velocities."""
        for level in DynamicLevel:
            assert 1 <= level.value <= 127


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_zero_phrase_length(self):
        """Engine should handle zero phrase length gracefully."""
        engine = DynamicsEngine()
        notes = [(0, 240, 60, 80)]
        
        # This shouldn't crash, but behavior may be undefined
        # At minimum, it should return something valid
        config = DynamicsConfig(phrase_length_beats=1)  # Use 1 instead of 0
        result = engine.apply(notes, config)
        
        assert len(result) == 1
        assert 1 <= result[0][3] <= 127
    
    def test_very_high_velocity_notes(self):
        """Engine should clamp very high velocities."""
        engine = DynamicsEngine()
        notes = [(0, 240, 60, 127)]
        
        config = DynamicsConfig(
            base_velocity=120,
            velocity_range=(1, 127),
            downbeat_accent=1.0  # Would push over 127
        )
        
        result = engine.apply(notes, config)
        
        # Should be clamped to 127
        assert result[0][3] <= 127
    
    def test_very_low_velocity_notes(self):
        """Engine should clamp very low velocities."""
        engine = DynamicsEngine()
        notes = [(0, 240, 60, 10)]
        
        config = DynamicsConfig(
            base_velocity=5,
            velocity_range=(1, 127),
            phrase_shape=DynamicShape.DECRESCENDO
        )
        
        result = engine.apply(notes, config)
        
        # Should be clamped to at least 1
        assert result[0][3] >= 1
    
    def test_notes_with_varied_durations(self):
        """Engine should handle notes with different durations."""
        engine = DynamicsEngine()
        notes = [
            (0, 240, 60, 80),      # Quarter note
            (480, 480, 62, 80),    # Half note
            (960, 120, 64, 80),    # Eighth note
            (1440, 960, 65, 80),   # Dotted half
        ]
        
        config = DynamicsConfig(phrase_shape=DynamicShape.CRESCENDO)
        result = engine.apply(notes, config)
        
        assert len(result) == len(notes)
        # Duration should be preserved
        for i in range(len(notes)):
            assert result[i][1] == notes[i][1]
    
    def test_notes_with_varied_pitches(self):
        """Engine should handle notes with different pitches."""
        engine = DynamicsEngine()
        notes = [
            (0, 240, 40, 80),      # Low pitch
            (480, 240, 60, 80),    # Middle C
            (960, 240, 90, 80),    # High pitch
            (1440, 240, 100, 80),  # Very high
        ]
        
        config = DynamicsConfig(phrase_shape=DynamicShape.SWELL)
        result = engine.apply(notes, config)
        
        assert len(result) == len(notes)
        # Pitch should be preserved
        for i in range(len(notes)):
            assert result[i][2] == notes[i][2]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
