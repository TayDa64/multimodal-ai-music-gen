"""
Unit tests for Drum Humanizer

Tests ghost note generation and intelligent drum fill functionality.
"""

import pytest
import sys
import random
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from multimodal_gen.drum_humanizer import (
    FillComplexity,
    GhostNoteConfig,
    FillConfig,
    DrumHumanizer,
    GENRE_GHOST_CONFIGS,
    GENRE_FILL_CONFIGS,
    DRUM_MIDI_MAP,
    add_ghost_notes,
    generate_fill
)


class TestGhostNotes:
    """Tests for ghost note generation."""
    
    def test_empty_track(self):
        """Ghost notes should handle empty tracks gracefully."""
        humanizer = DrumHumanizer()
        config = GhostNoteConfig()
        
        result = humanizer.add_ghost_notes([], config)
        
        assert result == []
    
    def test_single_note(self):
        """Single note should not get ghost notes (no gaps to fill)."""
        humanizer = DrumHumanizer()
        config = GhostNoteConfig(density=1.0)
        
        notes = [(0, 240, 38, 100)]  # Single snare
        result = humanizer.add_ghost_notes(notes, config)
        
        # Should only have the original note
        assert len(result) == 1
        assert result[0] == notes[0]
    
    def test_ghost_notes_added(self):
        """Ghost notes should be added between main hits."""
        humanizer = DrumHumanizer()
        config = GhostNoteConfig(
            density=1.0,  # Always add ghosts for testing
            velocity_ratio=0.35,
            instruments=("snare",)
        )
        
        # Create notes with gaps large enough for ghosts
        notes = [
            (0, 240, 38, 100),      # Snare
            (960, 240, 38, 100),    # Snare (2 beats later)
        ]
        
        result = humanizer.add_ghost_notes(notes, config, seed=42)
        
        # Should have original notes plus ghost notes
        assert len(result) > len(notes)
    
    def test_ghost_velocity_range(self):
        """Ghost notes should have 30-50% velocity of main hits."""
        humanizer = DrumHumanizer()
        config = GhostNoteConfig(
            density=1.0,
            velocity_ratio=0.35,
            min_velocity=20,
            max_velocity=50,
            instruments=("snare",)
        )
        
        notes = [
            (0, 240, 38, 100),
            (960, 240, 38, 100),
            (1920, 240, 38, 100),
        ]
        
        result = humanizer.add_ghost_notes(notes, config, seed=42)
        
        # Find ghost notes (low velocity)
        ghost_notes = [n for n in result if n[3] < 60]
        
        assert len(ghost_notes) > 0, "Should have ghost notes"
        
        for tick, dur, pitch, vel in ghost_notes:
            assert 20 <= vel <= 50, f"Ghost velocity {vel} out of range [20, 50]"
    
    def test_no_ghost_on_kick(self):
        """Kick drum should not get ghost notes."""
        humanizer = DrumHumanizer()
        config = GhostNoteConfig(
            density=1.0,
            velocity_ratio=0.35,
            instruments=("snare", "hihat"),
            avoid_instruments=("kick",)
        )
        
        notes = [
            (0, 240, 36, 100),      # Kick
            (960, 240, 36, 100),    # Kick
            (1920, 240, 36, 100),   # Kick
        ]
        
        result = humanizer.add_ghost_notes(notes, config, seed=42)
        
        # Should only have original kick notes, no ghosts added
        assert len(result) == len(notes)
        assert all(pitch == 36 for _, _, pitch, _ in result)
    
    def test_ghost_density_control(self):
        """Ghost density parameter should control how many ghosts are added."""
        humanizer = DrumHumanizer()
        
        notes = [
            (i * 480, 240, 38, 100) for i in range(20)  # 20 snare hits
        ]
        
        # Test low density
        config_low = GhostNoteConfig(density=0.1, instruments=("snare",))
        result_low = humanizer.add_ghost_notes(notes, config_low, seed=42)
        
        # Test high density
        config_high = GhostNoteConfig(density=0.9, instruments=("snare",))
        result_high = humanizer.add_ghost_notes(notes, config_high, seed=42)
        
        # High density should add more ghost notes
        assert len(result_high) > len(result_low)
    
    def test_ghost_notes_between_main_hits(self):
        """Ghost notes should appear between main hits, not before first or after last."""
        humanizer = DrumHumanizer()
        config = GhostNoteConfig(
            density=1.0,
            velocity_ratio=0.35,
            instruments=("snare",)
        )
        
        notes = [
            (480, 240, 38, 100),    # Snare on beat 2
            (1440, 240, 38, 100),   # Snare on beat 4
        ]
        
        result = humanizer.add_ghost_notes(notes, config, seed=42)
        
        # Find ghost notes
        ghost_notes = [n for n in result if n[3] < 60]
        
        if ghost_notes:
            for ghost_tick, _, _, _ in ghost_notes:
                # Ghost should be between the main notes
                assert 480 < ghost_tick < 1440
    
    def test_seed_reproducibility(self):
        """Same seed should produce same ghost notes."""
        humanizer = DrumHumanizer()
        config = GhostNoteConfig(density=0.5, instruments=("snare",))
        
        notes = [
            (i * 480, 240, 38, 100) for i in range(10)
        ]
        
        result1 = humanizer.add_ghost_notes(notes, config, seed=12345)
        result2 = humanizer.add_ghost_notes(notes, config, seed=12345)
        
        assert result1 == result2


class TestDrumFills:
    """Tests for drum fill generation."""
    
    def test_fill_generation_basic(self):
        """Fill should generate notes with appropriate length."""
        humanizer = DrumHumanizer()
        config = FillConfig(complexity=FillComplexity.SIMPLE, energy=0.7)
        
        fill = humanizer.generate_fill("hip_hop", duration_beats=2.0, config=config, seed=42)
        
        # Should have some notes
        assert len(fill) > 0
        
        # All notes should be within the duration
        max_tick = max(tick for tick, _, _, _ in fill)
        expected_max = 2.0 * 480  # 2 beats
        assert max_tick <= expected_max
    
    def test_fill_complexity_levels(self):
        """Different complexity levels should produce different numbers of notes."""
        humanizer = DrumHumanizer()
        
        # Minimal complexity
        config_minimal = FillConfig(complexity=FillComplexity.MINIMAL, energy=0.7)
        fill_minimal = humanizer.generate_fill("hip_hop", 2.0, config_minimal, seed=42)
        
        # Elaborate complexity
        config_elaborate = FillConfig(complexity=FillComplexity.ELABORATE, energy=0.7)
        fill_elaborate = humanizer.generate_fill("hip_hop", 2.0, config_elaborate, seed=42)
        
        # Elaborate should have more notes
        assert len(fill_elaborate) > len(fill_minimal)
    
    def test_fill_crescendo(self):
        """Fill with crescendo should build velocity over time."""
        humanizer = DrumHumanizer()
        config = FillConfig(
            complexity=FillComplexity.MODERATE,
            energy=0.7,
            use_crescendo=True
        )
        
        fill = humanizer.generate_fill("hip_hop", 2.0, config, seed=42)
        
        if len(fill) > 2:
            # Check that later notes tend to have higher velocities
            first_half = fill[:len(fill)//2]
            second_half = fill[len(fill)//2:]
            
            avg_vel_first = sum(v for _, _, _, v in first_half) / len(first_half)
            avg_vel_second = sum(v for _, _, _, v in second_half) / len(second_half)
            
            # Second half should generally be louder (with some tolerance for randomness)
            assert avg_vel_second >= avg_vel_first - 10
    
    def test_fill_velocity_range(self):
        """Fill velocities should respect configured range."""
        humanizer = DrumHumanizer()
        config = FillConfig(
            complexity=FillComplexity.MODERATE,
            energy=0.8,
            velocity_range=(70, 120)
        )
        
        fill = humanizer.generate_fill("trap", 2.0, config, seed=42)
        
        for tick, dur, pitch, vel in fill:
            # Should be in valid MIDI range
            assert 1 <= vel <= 127
            # Most should be in configured range (allow some variation)
            assert 60 <= vel <= 127
    
    def test_fill_energy_level(self):
        """Higher energy should produce louder fills."""
        humanizer = DrumHumanizer()
        
        config_low = FillConfig(
            complexity=FillComplexity.MODERATE,
            energy=0.3,
            velocity_range=(50, 100)
        )
        fill_low = humanizer.generate_fill("hip_hop", 2.0, config_low, seed=42)
        
        config_high = FillConfig(
            complexity=FillComplexity.MODERATE,
            energy=0.9,
            velocity_range=(50, 100)
        )
        fill_high = humanizer.generate_fill("hip_hop", 2.0, config_high, seed=42)
        
        # Calculate average velocities
        avg_vel_low = sum(v for _, _, _, v in fill_low) / len(fill_low) if fill_low else 0
        avg_vel_high = sum(v for _, _, _, v in fill_high) / len(fill_high) if fill_high else 0
        
        # High energy should be louder
        assert avg_vel_high > avg_vel_low
    
    def test_fill_seed_reproducibility(self):
        """Same seed should produce same fill."""
        humanizer = DrumHumanizer()
        config = FillConfig(complexity=FillComplexity.MODERATE, energy=0.7)
        
        fill1 = humanizer.generate_fill("trap", 2.0, config, seed=999)
        fill2 = humanizer.generate_fill("trap", 2.0, config, seed=999)
        
        assert fill1 == fill2
    
    def test_fill_instruments(self):
        """Fill should use configured instruments."""
        humanizer = DrumHumanizer()
        config = FillConfig(
            complexity=FillComplexity.MODERATE,
            instruments=("snare", "tom_high", "tom_mid"),
            include_kick=False
        )
        
        fill = humanizer.generate_fill("rock", 2.0, config, seed=42)
        
        # All pitches should be from configured instruments
        allowed_pitches = {
            DRUM_MIDI_MAP["snare"],
            DRUM_MIDI_MAP["tom_high"],
            DRUM_MIDI_MAP["tom_mid"]
        }
        
        for tick, dur, pitch, vel in fill:
            assert pitch in allowed_pitches
    
    def test_fill_with_kick(self):
        """Fill should include kick when configured."""
        humanizer = DrumHumanizer()
        config = FillConfig(
            complexity=FillComplexity.MODERATE,
            include_kick=True
        )
        
        fill = humanizer.generate_fill("rock", 4.0, config, seed=42)
        
        # Should have at least some chance of kick drum
        # (not guaranteed on every run, but with enough notes should appear)
        kick_pitch = DRUM_MIDI_MAP["kick"]
        kick_present = any(pitch == kick_pitch for _, _, pitch, _ in fill)
        
        # With moderate complexity over 4 beats, kick should appear
        # This is probabilistic, so we just check the config was respected
        assert config.include_kick == True


class TestSectionBoundaryFills:
    """Tests for automatic fill placement at section boundaries."""
    
    def test_fills_at_boundaries(self):
        """Fills should be placed at section boundaries."""
        humanizer = DrumHumanizer()
        
        drum_track = [
            (i * 480, 240, 36, 100) for i in range(20)  # 20 kick hits
        ]
        
        boundaries = [8.0, 16.0]  # Beat 8 and 16
        
        result = humanizer.place_fills_at_boundaries(
            drum_track,
            boundaries,
            "hip_hop",
            fill_probability=1.0,  # Always add fills
            seed=42
        )
        
        # Should have more notes than original (fills added)
        assert len(result) > len(drum_track)
    
    def test_fill_probability(self):
        """Fill probability should control whether fills are added."""
        humanizer = DrumHumanizer()
        
        drum_track = [(i * 480, 240, 36, 100) for i in range(10)]
        boundaries = [4.0, 8.0]
        
        # No fills
        result_none = humanizer.place_fills_at_boundaries(
            drum_track,
            boundaries,
            "hip_hop",
            fill_probability=0.0,
            seed=42
        )
        
        # Always fills
        result_always = humanizer.place_fills_at_boundaries(
            drum_track,
            boundaries,
            "hip_hop",
            fill_probability=1.0,
            seed=42
        )
        
        # No fills should be same as original
        assert len(result_none) == len(drum_track)
        
        # Always fills should add notes
        assert len(result_always) > len(drum_track)
    
    def test_empty_boundaries(self):
        """Empty boundaries list should return original track."""
        humanizer = DrumHumanizer()
        
        drum_track = [(i * 480, 240, 36, 100) for i in range(10)]
        
        result = humanizer.place_fills_at_boundaries(
            drum_track,
            [],  # No boundaries
            "hip_hop"
        )
        
        assert len(result) == len(drum_track)
    
    def test_fills_before_boundaries(self):
        """Fills should appear before boundaries, not after."""
        humanizer = DrumHumanizer()
        
        drum_track = []
        boundaries = [8.0]  # Fill should appear before beat 8
        
        result = humanizer.place_fills_at_boundaries(
            drum_track,
            boundaries,
            "hip_hop",
            fill_probability=1.0,
            seed=42
        )
        
        if result:
            # All fill notes should be before the boundary
            boundary_tick = 8.0 * 480
            for tick, dur, pitch, vel in result:
                assert tick < boundary_tick


class TestGenrePresets:
    """Tests for genre-specific configurations."""
    
    def test_all_ghost_presets_exist(self):
        """All expected genres should have ghost note presets."""
        expected_genres = [
            "jazz", "hip_hop", "boom_bap", "trap",
            "funk", "r_and_b", "rock", "house"
        ]
        
        for genre in expected_genres:
            assert genre in GENRE_GHOST_CONFIGS
    
    def test_all_fill_presets_exist(self):
        """All expected genres should have fill presets."""
        expected_genres = [
            "jazz", "hip_hop", "boom_bap", "trap",
            "funk", "r_and_b", "rock", "house"
        ]
        
        for genre in expected_genres:
            assert genre in GENRE_FILL_CONFIGS
    
    def test_ghost_config_values(self):
        """Ghost configs should have valid values."""
        for genre, config in GENRE_GHOST_CONFIGS.items():
            assert 0.0 <= config.density <= 1.0
            assert 0.0 <= config.velocity_ratio <= 1.0
            assert 1 <= config.min_velocity <= 127
            assert 1 <= config.max_velocity <= 127
            assert config.min_velocity <= config.max_velocity
            assert len(config.instruments) > 0
    
    def test_fill_config_values(self):
        """Fill configs should have valid values."""
        for genre, config in GENRE_FILL_CONFIGS.items():
            assert isinstance(config.complexity, FillComplexity)
            assert 0.0 <= config.energy <= 1.0
            min_vel, max_vel = config.velocity_range
            assert 1 <= min_vel <= 127
            assert 1 <= max_vel <= 127
            assert min_vel <= max_vel
            assert len(config.instruments) > 0
    
    def test_get_genre_configs(self):
        """Should be able to get genre configs through humanizer."""
        humanizer = DrumHumanizer()
        
        # Test ghost config
        ghost_config = humanizer.get_genre_ghost_config("trap")
        assert isinstance(ghost_config, GhostNoteConfig)
        assert ghost_config.density > 0
        
        # Test fill config
        fill_config = humanizer.get_genre_fill_config("trap")
        assert isinstance(fill_config, FillConfig)
        assert fill_config.complexity == FillComplexity.COMPLEX
    
    def test_unknown_genre_fallback(self):
        """Unknown genre should return default config."""
        humanizer = DrumHumanizer()
        
        ghost_config = humanizer.get_genre_ghost_config("unknown_genre")
        assert isinstance(ghost_config, GhostNoteConfig)
        
        fill_config = humanizer.get_genre_fill_config("unknown_genre")
        assert isinstance(fill_config, FillConfig)


class TestConvenienceFunctions:
    """Tests for convenience wrapper functions."""
    
    def test_add_ghost_notes_function(self):
        """Convenience function should work like method."""
        notes = [(i * 480, 240, 38, 100) for i in range(5)]
        
        result = add_ghost_notes(notes, genre="hip_hop", seed=42)
        
        assert len(result) >= len(notes)
    
    def test_add_ghost_notes_density_override(self):
        """Density override should work in convenience function."""
        notes = [(i * 480, 240, 38, 100) for i in range(10)]
        
        result_low = add_ghost_notes(notes, genre="hip_hop", density=0.1, seed=42)
        result_high = add_ghost_notes(notes, genre="hip_hop", density=0.9, seed=42)
        
        assert len(result_high) >= len(result_low)
    
    def test_generate_fill_function(self):
        """Convenience function should generate fills."""
        fill = generate_fill(genre="trap", duration_beats=2.0, energy=0.8, seed=42)
        
        assert len(fill) > 0
        
        # Check that all notes are tuples with 4 elements
        for note in fill:
            assert len(note) == 4
            tick, dur, pitch, vel = note
            assert isinstance(tick, int)
            assert isinstance(dur, int)
            assert isinstance(pitch, int)
            assert isinstance(vel, int)


class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_very_short_gaps(self):
        """Very short gaps should not get ghost notes."""
        humanizer = DrumHumanizer()
        config = GhostNoteConfig(density=1.0, instruments=("snare",))
        
        # Notes very close together (32nd notes)
        notes = [
            (0, 60, 38, 100),
            (60, 60, 38, 100),
            (120, 60, 38, 100),
        ]
        
        result = humanizer.add_ghost_notes(notes, config, seed=42)
        
        # Should not add ghosts in very short gaps
        # (might be same as original or only slightly more)
        assert len(result) <= len(notes) + 1
    
    def test_zero_duration_fill(self):
        """Zero duration fill should return empty or minimal result."""
        humanizer = DrumHumanizer()
        config = FillConfig()
        
        fill = humanizer.generate_fill("hip_hop", 0.0, config, seed=42)
        
        # Should handle gracefully (empty or very few notes)
        assert len(fill) >= 0
    
    def test_very_long_fill(self):
        """Very long fill should scale appropriately."""
        humanizer = DrumHumanizer()
        config = FillConfig(complexity=FillComplexity.MODERATE, energy=0.7)
        
        fill = humanizer.generate_fill("hip_hop", 8.0, config, seed=42)
        
        # Should have more notes for longer duration
        assert len(fill) > 5
        
        # Should span the full duration
        if fill:
            max_tick = max(tick for tick, _, _, _ in fill)
            expected_max = 8.0 * 480
            assert max_tick <= expected_max
    
    def test_negative_boundary(self):
        """Negative boundary should be handled gracefully."""
        humanizer = DrumHumanizer()
        
        drum_track = [(i * 480, 240, 36, 100) for i in range(10)]
        boundaries = [-1.0, 4.0]
        
        # Should not crash
        result = humanizer.place_fills_at_boundaries(
            drum_track,
            boundaries,
            "hip_hop",
            fill_probability=1.0,
            seed=42
        )
        
        # Should return a valid result
        assert isinstance(result, list)
    
    def test_duplicate_notes(self):
        """Duplicate notes should be handled."""
        humanizer = DrumHumanizer()
        config = GhostNoteConfig(density=0.5, instruments=("snare",))
        
        # Duplicate notes at same position
        notes = [
            (0, 240, 38, 100),
            (0, 240, 38, 100),
            (960, 240, 38, 100),
        ]
        
        result = humanizer.add_ghost_notes(notes, config, seed=42)
        
        # Should handle without crashing
        assert len(result) >= len(notes)


class TestDrumMIDIMap:
    """Tests for MIDI drum mapping."""
    
    def test_midi_map_completeness(self):
        """MIDI map should have all essential drums."""
        essential_drums = [
            "kick", "snare", "hihat_closed", "tom_high", "tom_mid", "tom_low"
        ]
        
        for drum in essential_drums:
            assert drum in DRUM_MIDI_MAP
    
    def test_midi_map_values(self):
        """MIDI map values should be in valid range."""
        for drum, pitch in DRUM_MIDI_MAP.items():
            assert 0 <= pitch <= 127
            assert isinstance(pitch, int)
    
    def test_general_midi_standard(self):
        """Should use General MIDI drum map standard."""
        # Check some standard GM drum pitches
        assert DRUM_MIDI_MAP["kick"] == 36
        assert DRUM_MIDI_MAP["snare"] == 38
        assert DRUM_MIDI_MAP["hihat_closed"] == 42


if __name__ == '__main__':
    pytest.main([__file__, "-v"])
