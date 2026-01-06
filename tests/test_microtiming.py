"""
Unit tests for Microtiming Engine

Tests the microtiming classes and ensures genre-appropriate timing variations.
"""

import pytest
import sys
import random
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from multimodal_gen.microtiming import (
    GrooveStyle,
    MicrotimingConfig,
    MicrotimingEngine,
    GENRE_PRESETS,
    apply_microtiming
)


class TestMicrotimingEngine:
    """Tests for microtiming engine."""
    
    def test_straight_timing_unchanged(self):
        """With swing=0, push_pull=0, randomness=0, notes should be unchanged."""
        engine = MicrotimingEngine()
        
        notes = [
            (0, 240, 60, 100),
            (240, 240, 62, 90),
            (480, 240, 64, 100),
        ]
        
        config = MicrotimingConfig(
            swing_amount=0.0,
            push_pull=0.0,
            randomness=0.0
        )
        
        result = engine.apply(notes, config)
        
        # Notes should be unchanged
        assert result == notes
    
    def test_swing_delays_offbeats(self):
        """Swing should delay notes on off-beats (the 'and' of each beat)."""
        engine = MicrotimingEngine(ticks_per_beat=480)
        
        notes = [
            (0, 240, 60, 100),      # Beat 1 (on-beat)
            (240, 240, 62, 90),     # Off-beat (and of 1)
            (480, 240, 64, 100),    # Beat 2 (on-beat)
            (720, 240, 65, 90),     # Off-beat (and of 2)
        ]
        
        # Apply 50% swing
        result = engine.apply_swing(notes, 0.5)
        
        # Expected swing offset: 0.5 * (480 / 3) = 0.5 * 160 = 80 ticks
        expected_offset = 80
        
        # On-beats should be unchanged
        assert result[0][0] == 0
        assert result[2][0] == 480
        
        # Off-beats should be delayed
        assert result[1][0] == 240 + expected_offset
        assert result[3][0] == 720 + expected_offset
    
    def test_swing_preserves_downbeats(self):
        """Swing should not affect notes on downbeats."""
        engine = MicrotimingEngine(ticks_per_beat=480)
        
        # Notes on downbeats
        notes = [
            (0, 240, 60, 100),
            (480, 240, 62, 100),
            (960, 240, 64, 100),
            (1440, 240, 65, 100),
        ]
        
        # Apply full swing
        result = engine.apply_swing(notes, 1.0)
        
        # All should be unchanged (they're on downbeats)
        for i, (tick, dur, pitch, vel) in enumerate(result):
            assert tick == notes[i][0]
            assert dur == notes[i][1]
            assert pitch == notes[i][2]
            assert vel == notes[i][3]
    
    def test_push_pull_positive(self):
        """Positive push_pull should shift notes earlier (ahead of beat)."""
        engine = MicrotimingEngine(ticks_per_beat=480)
        
        notes = [
            (0, 240, 60, 100),
            (480, 240, 62, 100),
        ]
        
        # Push ahead by +0.5 (half of max shift)
        result = engine.apply_push_pull(notes, 0.5)
        
        # Max shift = ticks_per_beat / 4 = 120
        # Shift = -0.5 * 120 = -60 (negative = earlier)
        expected_shift = -60
        
        for i, (tick, dur, pitch, vel) in enumerate(result):
            assert tick == notes[i][0] + expected_shift
            assert dur == notes[i][1]
            assert pitch == notes[i][2]
            assert vel == notes[i][3]
    
    def test_push_pull_negative(self):
        """Negative push_pull should shift notes later (behind beat)."""
        engine = MicrotimingEngine(ticks_per_beat=480)
        
        notes = [
            (480, 240, 60, 100),
            (960, 240, 62, 100),
        ]
        
        # Pull behind by -0.5 (half of max shift)
        result = engine.apply_push_pull(notes, -0.5)
        
        # Max shift = ticks_per_beat / 4 = 120
        # Shift = -(-0.5) * 120 = +60 (positive = later)
        expected_shift = 60
        
        for i, (tick, dur, pitch, vel) in enumerate(result):
            assert tick == notes[i][0] + expected_shift
            assert dur == notes[i][1]
            assert pitch == notes[i][2]
            assert vel == notes[i][3]
    
    def test_humanize_adds_variation(self):
        """Humanize should add random but bounded variations."""
        engine = MicrotimingEngine(ticks_per_beat=480)
        
        notes = [
            (0, 240, 60, 100),
            (240, 240, 62, 90),
            (480, 240, 64, 100),
        ]
        
        # Set seed for reproducibility
        random.seed(42)
        result = engine.apply_humanize(notes, 0.5)
        
        # Check that notes are varied but within reasonable bounds
        # Max variation at 0.5 randomness = 0.5 * (480/8) = 30 ticks
        max_variation = 30
        
        for i, (tick, dur, pitch, vel) in enumerate(result):
            original_tick = notes[i][0]
            # Variation should be within bounds
            assert abs(tick - original_tick) <= max_variation * 3  # 3 std devs
            # Other properties unchanged
            assert dur == notes[i][1]
            assert pitch == notes[i][2]
            assert vel == notes[i][3]
    
    def test_humanize_deterministic_with_seed(self):
        """With same seed, humanize should produce same results."""
        engine = MicrotimingEngine(ticks_per_beat=480)
        
        notes = [
            (0, 240, 60, 100),
            (240, 240, 62, 90),
            (480, 240, 64, 100),
        ]
        
        # First run
        random.seed(12345)
        result1 = engine.apply_humanize(notes, 0.3)
        
        # Second run with same seed
        random.seed(12345)
        result2 = engine.apply_humanize(notes, 0.3)
        
        # Should be identical
        assert result1 == result2
    
    def test_genre_presets_exist(self):
        """All expected genre presets should exist."""
        expected_genres = ['jazz', 'hip-hop', 'funk', 'r&b', 'rock', 'blues']
        
        for genre in expected_genres:
            assert genre in GENRE_PRESETS, f"Missing preset for {genre}"
            
            # Each preset should be a valid MicrotimingConfig
            config = GENRE_PRESETS[genre]
            assert isinstance(config, MicrotimingConfig)
            assert 0.0 <= config.swing_amount <= 1.0
            assert -1.0 <= config.push_pull <= 1.0
            assert 0.0 <= config.randomness <= 1.0
            assert isinstance(config.groove_style, GrooveStyle)
    
    def test_genre_preset_jazz(self):
        """Jazz preset should have significant swing."""
        jazz_config = GENRE_PRESETS['jazz']
        
        # Jazz should have substantial swing
        assert jazz_config.swing_amount >= 0.5
        # Jazz swing style
        assert jazz_config.groove_style == GrooveStyle.SWING
        # Some randomness for humanization
        assert jazz_config.randomness > 0.0
    
    def test_combined_transforms(self):
        """Multiple transforms should combine correctly."""
        engine = MicrotimingEngine(ticks_per_beat=480)
        
        notes = [
            (0, 240, 60, 100),      # On-beat
            (240, 240, 62, 90),     # Off-beat
            (480, 240, 64, 100),    # On-beat
        ]
        
        # Apply jazz preset (swing + humanize)
        random.seed(42)
        config = MicrotimingConfig(
            swing_amount=0.6,
            push_pull=-0.1,
            randomness=0.15,
            groove_style=GrooveStyle.SWING
        )
        
        result = engine.apply(notes, config)
        
        # Result should have:
        # 1. Swing applied to off-beats
        # 2. All notes pushed back slightly
        # 3. Random humanization
        
        # Verify we got results
        assert len(result) == len(notes)
        
        # On-beats should be affected by push_pull and humanize, but not swing
        # Off-beats should be affected by all three
        
        # First note (on-beat) should be close to original + push_pull
        # Max push_pull shift at -0.1 = +12 ticks
        # Plus some random variation
        assert result[0][0] != notes[0][0]  # Should have changed
        
        # Second note (off-beat) should have significant delay from swing
        # Plus push_pull and humanize
        assert result[1][0] > notes[1][0]  # Should be later due to swing
    
    def test_no_negative_ticks(self):
        """Timing adjustments should never result in negative tick values."""
        engine = MicrotimingEngine(ticks_per_beat=480)
        
        # Notes very close to zero
        notes = [
            (0, 240, 60, 100),
            (10, 240, 62, 90),
            (20, 240, 64, 100),
        ]
        
        # Apply strong push ahead (which would normally make ticks negative)
        config = MicrotimingConfig(
            swing_amount=0.0,
            push_pull=1.0,  # Maximum push ahead
            randomness=0.0
        )
        
        result = engine.apply(notes, config)
        
        # All ticks should be >= 0
        for tick, dur, pitch, vel in result:
            assert tick >= 0, f"Negative tick: {tick}"
    
    def test_convenience_function(self):
        """Test apply_microtiming convenience function."""
        notes = [
            (0, 240, 60, 100),
            (240, 240, 62, 90),
        ]
        
        # With genre preset
        result1 = apply_microtiming(notes, genre='jazz')
        assert len(result1) == len(notes)
        
        # With custom config
        config = MicrotimingConfig(swing_amount=0.3)
        result2 = apply_microtiming(notes, config=config)
        assert len(result2) == len(notes)
        
        # With neither (should use default config with no changes)
        result3 = apply_microtiming(notes)
        assert result3 == notes
    
    def test_get_preset_method(self):
        """Test get_preset method returns correct configs."""
        engine = MicrotimingEngine()
        
        # Get jazz preset
        jazz = engine.get_preset('jazz')
        assert jazz.groove_style == GrooveStyle.SWING
        
        # Get rock preset
        rock = engine.get_preset('rock')
        assert rock.groove_style == GrooveStyle.STRAIGHT
        
        # Get r&b preset
        rnb = engine.get_preset('r&b')
        assert rnb.groove_style == GrooveStyle.LAID_BACK
        
        # Unknown genre should return default (straight)
        unknown = engine.get_preset('unknown-genre')
        assert unknown.swing_amount == 0.0
        assert unknown.push_pull == 0.0
        assert unknown.randomness == 0.0


class TestGrooveStyle:
    """Tests for GrooveStyle enum."""
    
    def test_groove_styles_exist(self):
        """All groove styles should be defined."""
        expected_styles = [
            'STRAIGHT', 'SWING', 'LAID_BACK', 
            'PUSHED', 'SHUFFLE', 'HUMAN'
        ]
        
        for style_name in expected_styles:
            assert hasattr(GrooveStyle, style_name)
    
    def test_groove_style_values(self):
        """Groove style values should be lowercase strings or snake_case."""
        for style in GrooveStyle:
            assert isinstance(style.value, str)
            # Check that value is either lowercase or snake_case (lowercase with underscores)
            is_valid = style.value.replace('_', '').islower()
            assert is_valid, f"Style value '{style.value}' should be lowercase or snake_case"


class TestMicrotimingConfig:
    """Tests for MicrotimingConfig dataclass."""
    
    def test_config_defaults(self):
        """Config should have sensible defaults."""
        config = MicrotimingConfig()
        
        assert config.swing_amount == 0.0
        assert config.push_pull == 0.0
        assert config.randomness == 0.0
        assert config.groove_style == GrooveStyle.STRAIGHT
        assert config.ticks_per_beat == 480
    
    def test_config_custom_values(self):
        """Config should accept custom values."""
        config = MicrotimingConfig(
            swing_amount=0.7,
            push_pull=-0.2,
            randomness=0.15,
            groove_style=GrooveStyle.SWING,
            ticks_per_beat=960
        )
        
        assert config.swing_amount == 0.7
        assert config.push_pull == -0.2
        assert config.randomness == 0.15
        assert config.groove_style == GrooveStyle.SWING
        assert config.ticks_per_beat == 960


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_empty_notes_list(self):
        """Engine should handle empty notes list gracefully."""
        engine = MicrotimingEngine()
        config = MicrotimingConfig(swing_amount=0.5)
        
        result = engine.apply([], config)
        assert result == []
    
    def test_single_note(self):
        """Engine should handle single note."""
        engine = MicrotimingEngine()
        notes = [(0, 240, 60, 100)]
        config = MicrotimingConfig(swing_amount=0.5, randomness=0.1)
        
        random.seed(42)
        result = engine.apply(notes, config)
        
        assert len(result) == 1
        # Should have some variation from humanize
        # Swing won't affect it (it's on a downbeat)
    
    def test_very_high_swing(self):
        """Engine should handle swing values at boundary (1.0)."""
        engine = MicrotimingEngine(ticks_per_beat=480)
        notes = [(0, 240, 60, 100), (240, 240, 62, 90)]
        
        result = engine.apply_swing(notes, 1.0)
        
        # Full swing = 160 tick delay on off-beats
        expected_offset = 160
        assert result[1][0] == 240 + expected_offset
    
    def test_very_high_randomness(self):
        """Engine should handle maximum randomness (1.0)."""
        engine = MicrotimingEngine(ticks_per_beat=480)
        notes = [(480, 240, 60, 100)]
        
        random.seed(42)
        result = engine.apply_humanize(notes, 1.0)
        
        # Should produce variation within bounds
        # Max variation = 480 / 8 = 60 ticks
        max_expected_variation = 60 * 3  # 3 std devs
        assert abs(result[0][0] - notes[0][0]) <= max_expected_variation
    
    def test_notes_preserve_other_attributes(self):
        """Duration, pitch, and velocity should never change."""
        engine = MicrotimingEngine()
        notes = [
            (0, 100, 60, 80),
            (240, 200, 62, 90),
            (480, 150, 64, 70),
        ]
        
        config = MicrotimingConfig(
            swing_amount=0.5,
            push_pull=-0.2,
            randomness=0.2
        )
        
        random.seed(42)
        result = engine.apply(notes, config)
        
        for i, (tick, dur, pitch, vel) in enumerate(result):
            # Only tick should change
            assert dur == notes[i][1]
            assert pitch == notes[i][2]
            assert vel == notes[i][3]


class TestGenrePresets:
    """Tests for specific genre preset characteristics."""
    
    def test_jazz_has_swing(self):
        """Jazz should have significant swing."""
        jazz = GENRE_PRESETS['jazz']
        assert jazz.swing_amount >= 0.5
    
    def test_rock_is_straight(self):
        """Rock should have minimal swing (straight feel)."""
        rock = GENRE_PRESETS['rock']
        assert rock.swing_amount == 0.0
        assert rock.groove_style == GrooveStyle.STRAIGHT
    
    def test_rnb_laid_back(self):
        """R&B should be behind the beat."""
        rnb = GENRE_PRESETS['r&b']
        assert rnb.push_pull < 0  # Behind the beat
        assert rnb.groove_style == GrooveStyle.LAID_BACK
    
    def test_funk_pushed(self):
        """Funk should be slightly ahead."""
        funk = GENRE_PRESETS['funk']
        assert funk.push_pull > 0  # Ahead of beat
        assert funk.groove_style == GrooveStyle.PUSHED
    
    def test_hiphop_laid_back(self):
        """Hip-hop should have some swing and be slightly laid back."""
        hiphop = GENRE_PRESETS['hip-hop']
        assert hiphop.swing_amount > 0
        assert hiphop.push_pull < 0
        assert hiphop.groove_style == GrooveStyle.LAID_BACK
    
    def test_blues_shuffle(self):
        """Blues should have shuffle feel."""
        blues = GENRE_PRESETS['blues']
        assert blues.swing_amount >= 0.4
        assert blues.groove_style == GrooveStyle.SHUFFLE


class TestOffbeatDetection:
    """Tests for offbeat detection logic."""
    
    def test_is_offbeat_eighth_notes(self):
        """Test offbeat detection for eighth notes."""
        engine = MicrotimingEngine(ticks_per_beat=480)
        
        # On-beats (quarter notes)
        assert not engine._is_offbeat(0)
        assert not engine._is_offbeat(480)
        assert not engine._is_offbeat(960)
        
        # Off-beats (eighth note subdivisions)
        assert engine._is_offbeat(240)
        assert engine._is_offbeat(720)
        assert engine._is_offbeat(1200)
    
    def test_is_offbeat_with_tolerance(self):
        """Offbeat detection should have some tolerance."""
        engine = MicrotimingEngine(ticks_per_beat=480)
        
        # Slightly off but within tolerance
        # Tolerance = 480 / 8 = 60 ticks
        assert engine._is_offbeat(240 - 50)  # Within tolerance
        assert engine._is_offbeat(240 + 50)  # Within tolerance
        
        # Too far off
        assert not engine._is_offbeat(240 - 100)  # Outside tolerance
        assert not engine._is_offbeat(240 + 100)  # Outside tolerance


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
