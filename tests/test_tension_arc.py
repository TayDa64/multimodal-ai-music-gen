"""
Unit tests for Tension Arc System

Tests tension arc generation, interpolation, curve generation, and integration.
"""

import pytest
import sys
import numpy as np
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from multimodal_gen.tension_arc import (
    ArcShape,
    TensionPoint,
    TensionConfig,
    TensionArc,
    TensionArcGenerator,
    SECTION_TENSION_MAP,
    GENRE_TENSION_PROFILES,
    create_tension_arc,
    apply_tension_to_arrangement,
    get_tension_for_section,
)


class TestTensionPoint:
    """Tests for TensionPoint dataclass."""
    
    def test_tension_point_creation(self):
        """Test creating a tension point."""
        point = TensionPoint(0.5, 0.8, "climax")
        assert point.position == 0.5
        assert point.tension == 0.8
        assert point.label == "climax"
    
    def test_tension_point_default_label(self):
        """Test default label is empty string."""
        point = TensionPoint(0.3, 0.6)
        assert point.label == ""


class TestTensionConfig:
    """Tests for TensionConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = TensionConfig()
        assert config.base_tension == 0.5
        assert config.tension_range == (0.2, 1.0)
        assert config.dynamics_influence == 0.7
        assert config.density_influence == 0.6
        assert config.complexity_influence == 0.5
        assert config.register_influence == 0.4
        assert config.articulation_influence == 0.3
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = TensionConfig(
            base_tension=0.7,
            tension_range=(0.0, 0.8),
            dynamics_influence=0.9
        )
        assert config.base_tension == 0.7
        assert config.tension_range == (0.0, 0.8)
        assert config.dynamics_influence == 0.9


class TestTensionArc:
    """Tests for TensionArc class."""
    
    def test_get_tension_at_empty(self):
        """Test getting tension with no points returns base tension."""
        arc = TensionArc()
        assert arc.get_tension_at(0.5) == 0.5
    
    def test_get_tension_at_single_point(self):
        """Test getting tension with single point."""
        arc = TensionArc(points=[TensionPoint(0.5, 0.8)])
        assert arc.get_tension_at(0.0) == 0.8
        assert arc.get_tension_at(0.5) == 0.8
        assert arc.get_tension_at(1.0) == 0.8
    
    def test_get_tension_at_interpolation(self):
        """Test linear interpolation between points."""
        arc = TensionArc(points=[
            TensionPoint(0.0, 0.2),
            TensionPoint(1.0, 0.8)
        ])
        
        # Check endpoints
        assert arc.get_tension_at(0.0) == 0.2
        assert arc.get_tension_at(1.0) == 0.8
        
        # Check midpoint interpolation
        assert abs(arc.get_tension_at(0.5) - 0.5) < 0.01
    
    def test_get_tension_at_multiple_points(self):
        """Test interpolation with multiple points."""
        arc = TensionArc(points=[
            TensionPoint(0.0, 0.3),
            TensionPoint(0.5, 0.9),
            TensionPoint(1.0, 0.4)
        ])
        
        assert arc.get_tension_at(0.0) == 0.3
        assert abs(arc.get_tension_at(0.5) - 0.9) < 0.001
        assert arc.get_tension_at(1.0) == 0.4
        
        # Check interpolation between 0.0 and 0.5
        tension_025 = arc.get_tension_at(0.25)
        assert 0.3 < tension_025 < 0.9
    
    def test_to_curve(self):
        """Test conversion to dense curve."""
        arc = TensionArc(points=[
            TensionPoint(0.0, 0.0),
            TensionPoint(1.0, 1.0)
        ])
        
        curve = arc.to_curve(num_points=101)
        assert len(curve) == 101
        assert curve[0] == 0.0
        assert curve[-1] == 1.0
        
        # Check curve is monotonically increasing
        for i in range(len(curve) - 1):
            assert curve[i] <= curve[i + 1]


class TestArcShapes:
    """Tests for all arc shape generators."""
    
    def test_flat_shape(self):
        """Test flat arc shape has constant tension."""
        generator = TensionArcGenerator()
        arc = generator.create_arc(ArcShape.FLAT, num_sections=5)
        
        assert len(arc.points) == 5
        
        # All tensions should be base_tension
        for point in arc.points:
            assert point.tension == 0.5
    
    def test_linear_build_shape(self):
        """Test linear build increases steadily."""
        generator = TensionArcGenerator()
        arc = generator.create_arc(ArcShape.LINEAR_BUILD, num_sections=5)
        
        assert len(arc.points) == 5
        
        # Tensions should increase
        tensions = [p.tension for p in arc.points]
        for i in range(len(tensions) - 1):
            assert tensions[i] <= tensions[i + 1]
    
    def test_linear_decay_shape(self):
        """Test linear decay decreases steadily."""
        generator = TensionArcGenerator()
        arc = generator.create_arc(ArcShape.LINEAR_DECAY, num_sections=5)
        
        assert len(arc.points) == 5
        
        # Tensions should decrease
        tensions = [p.tension for p in arc.points]
        for i in range(len(tensions) - 1):
            assert tensions[i] >= tensions[i + 1]
    
    def test_peak_middle_shape(self):
        """Test peak middle shape."""
        generator = TensionArcGenerator()
        arc = generator.create_arc(ArcShape.PEAK_MIDDLE, num_sections=9)
        
        assert len(arc.points) == 9
        
        # Middle should have highest tension
        tensions = [p.tension for p in arc.points]
        mid_index = len(tensions) // 2
        assert tensions[mid_index] >= tensions[0]
        assert tensions[mid_index] >= tensions[-1]
    
    def test_peak_end_shape(self):
        """Test peak at end shape."""
        generator = TensionArcGenerator()
        arc = generator.create_arc(ArcShape.PEAK_END, num_sections=5)
        
        assert len(arc.points) == 5
        
        # End should have highest tension
        tensions = [p.tension for p in arc.points]
        assert tensions[-1] >= tensions[0]
    
    def test_double_peak_shape(self):
        """Test double peak shape."""
        generator = TensionArcGenerator()
        arc = generator.create_arc(ArcShape.DOUBLE_PEAK, num_sections=9)
        
        assert len(arc.points) == 9
        # Just verify it was created successfully
        assert all(0.0 <= p.tension <= 1.0 for p in arc.points)
    
    def test_wave_shape(self):
        """Test wave shape oscillates."""
        generator = TensionArcGenerator()
        arc = generator.create_arc(ArcShape.WAVE, num_sections=10)
        
        assert len(arc.points) == 10
        # Wave should have multiple peaks and troughs
        assert all(0.0 <= p.tension <= 1.0 for p in arc.points)
    
    def test_step_up_shape(self):
        """Test stepwise increase."""
        generator = TensionArcGenerator()
        arc = generator.create_arc(ArcShape.STEP_UP, num_sections=5)
        
        assert len(arc.points) == 5
        
        # Should increase in steps
        tensions = [p.tension for p in arc.points]
        for i in range(len(tensions) - 1):
            assert tensions[i] <= tensions[i + 1]
    
    def test_step_down_shape(self):
        """Test stepwise decrease."""
        generator = TensionArcGenerator()
        arc = generator.create_arc(ArcShape.STEP_DOWN, num_sections=5)
        
        assert len(arc.points) == 5
        
        # Should decrease in steps
        tensions = [p.tension for p in arc.points]
        for i in range(len(tensions) - 1):
            assert tensions[i] >= tensions[i + 1]
    
    def test_dramatic_shape(self):
        """Test dramatic shape has distinct phases."""
        generator = TensionArcGenerator()
        arc = generator.create_arc(ArcShape.DRAMATIC, num_sections=8)
        
        assert len(arc.points) == 8
        
        # Should have low-high-low pattern
        tensions = [p.tension for p in arc.points]
        assert tensions[0] < 0.5  # Start low
        assert max(tensions) > 0.7  # Has high tension
        assert tensions[-1] < tensions[len(tensions) // 2]  # Ends lower than middle


class TestTensionArcGenerator:
    """Tests for TensionArcGenerator class."""
    
    def test_generator_initialization(self):
        """Test generator initializes properly."""
        generator = TensionArcGenerator()
        assert len(generator._shape_functions) == 10
    
    def test_create_custom_arc(self):
        """Test creating custom arc from explicit values."""
        generator = TensionArcGenerator()
        tension_values = [0.2, 0.5, 0.8, 0.6, 0.3]
        
        arc = generator.create_custom_arc(tension_values)
        
        assert len(arc.points) == 5
        for i, expected in enumerate(tension_values):
            assert arc.points[i].tension == expected
    
    def test_create_arc_for_sections(self):
        """Test creating arc based on section types."""
        generator = TensionArcGenerator()
        section_types = ["intro", "verse", "chorus", "outro"]
        
        arc = generator.create_arc_for_sections(section_types)
        
        assert len(arc.points) == 4
        assert arc.points[0].tension == SECTION_TENSION_MAP["intro"]
        assert arc.points[1].tension == SECTION_TENSION_MAP["verse"]
        assert arc.points[2].tension == SECTION_TENSION_MAP["chorus"]
        assert arc.points[3].tension == SECTION_TENSION_MAP["outro"]
    
    def test_create_arc_for_sections_with_genre(self):
        """Test section-based arc with genre-specific adjustments."""
        generator = TensionArcGenerator()
        section_types = ["verse", "chorus"]
        
        arc_pop = generator.create_arc_for_sections(section_types, genre="pop")
        arc_jazz = generator.create_arc_for_sections(section_types, genre="jazz")
        
        # Both should work
        assert len(arc_pop.points) == 2
        assert len(arc_jazz.points) == 2
    
    def test_create_arc_for_sections_unknown_type(self):
        """Test unknown section type defaults to medium tension."""
        generator = TensionArcGenerator()
        section_types = ["unknown_section_type"]
        
        arc = generator.create_arc_for_sections(section_types)
        
        assert len(arc.points) == 1
        assert arc.points[0].tension == 0.5
    
    def test_get_tension_at_position(self):
        """Test getting tension at position wrapper."""
        generator = TensionArcGenerator()
        arc = generator.create_arc(ArcShape.LINEAR_BUILD, num_sections=3)
        
        tension = generator.get_tension_at_position(arc, 0.5)
        assert 0.0 <= tension <= 1.0


class TestCurveGeneration:
    """Tests for curve generation methods."""
    
    def test_dynamics_curve(self):
        """Test dynamics curve generation."""
        generator = TensionArcGenerator()
        arc = generator.create_arc(ArcShape.LINEAR_BUILD, num_sections=5)
        
        curve = generator.get_dynamics_curve(arc, num_points=10)
        
        assert len(curve) == 10
        assert all(40 <= v <= 120 for v in curve)
    
    def test_density_curve(self):
        """Test density curve generation."""
        generator = TensionArcGenerator()
        arc = generator.create_arc(ArcShape.LINEAR_BUILD, num_sections=5)
        
        curve = generator.get_density_curve(arc, num_points=10)
        
        assert len(curve) == 10
        assert all(0.2 <= v <= 1.0 for v in curve)
    
    def test_complexity_curve(self):
        """Test complexity curve generation."""
        generator = TensionArcGenerator()
        arc = generator.create_arc(ArcShape.LINEAR_BUILD, num_sections=5)
        
        curve = generator.get_complexity_curve(arc, num_points=10)
        
        assert len(curve) == 10
        assert all(0.0 <= v <= 1.0 for v in curve)
    
    def test_register_curve(self):
        """Test register curve generation."""
        generator = TensionArcGenerator()
        arc = generator.create_arc(ArcShape.LINEAR_BUILD, num_sections=5)
        
        curve = generator.get_register_curve(arc, num_points=10)
        
        assert len(curve) == 10
        assert all(0.0 <= v <= 1.0 for v in curve)
    
    def test_curves_reflect_tension(self):
        """Test that curves reflect underlying tension."""
        generator = TensionArcGenerator()
        arc_low = generator.create_arc(ArcShape.FLAT, num_sections=5)
        arc_low.config.base_tension = 0.2
        
        arc_high = generator.create_arc(ArcShape.FLAT, num_sections=5)
        arc_high.config.base_tension = 0.9
        
        # Regenerate points with new base tension
        arc_low.points = [TensionPoint(i/4, 0.2) for i in range(5)]
        arc_high.points = [TensionPoint(i/4, 0.9) for i in range(5)]
        
        curve_low = generator.get_dynamics_curve(arc_low, num_points=10)
        curve_high = generator.get_dynamics_curve(arc_high, num_points=10)
        
        # High tension should have higher average dynamics
        assert np.mean(curve_high) > np.mean(curve_low)


class TestVelocityApplication:
    """Tests for applying tension to note velocities."""
    
    def test_apply_to_velocities_empty(self):
        """Test applying to empty note list."""
        generator = TensionArcGenerator()
        arc = generator.create_arc(ArcShape.FLAT, num_sections=3)
        
        result = generator.apply_to_velocities([], arc, 1000)
        assert result == []
    
    def test_apply_to_velocities_basic(self):
        """Test basic velocity application."""
        generator = TensionArcGenerator()
        arc = generator.create_arc(ArcShape.LINEAR_BUILD, num_sections=3)
        
        notes = [
            (0, 240, 60, 80),
            (500, 240, 62, 80),
            (1000, 240, 64, 80),
        ]
        
        result = generator.apply_to_velocities(notes, arc, 1200)
        
        assert len(result) == 3
        
        # All notes should have valid velocities
        for tick, dur, pitch, vel in result:
            assert 1 <= vel <= 127
    
    def test_apply_to_velocities_increasing_tension(self):
        """Test that increasing tension affects velocities."""
        generator = TensionArcGenerator()
        
        # Create arc with clear low-to-high tension
        config = TensionConfig(tension_range=(0.2, 1.0), dynamics_influence=0.9)
        arc = generator.create_arc(ArcShape.LINEAR_BUILD, num_sections=3, config=config)
        
        notes = [
            (0, 240, 60, 80),
            (500, 240, 62, 80),
            (1000, 240, 64, 80),
        ]
        
        result = generator.apply_to_velocities(notes, arc, 1000)
        
        # Later notes should generally have higher velocities (with high influence)
        velocities = [vel for _, _, _, vel in result]
        # First note should be lower than last note
        assert velocities[0] < velocities[-1]
    
    def test_apply_to_velocities_clamping(self):
        """Test velocity clamping to valid MIDI range."""
        generator = TensionArcGenerator()
        
        # Create arc with very high tension and influence
        config = TensionConfig(tension_range=(0.9, 1.0), dynamics_influence=1.0)
        arc = generator.create_arc(ArcShape.FLAT, num_sections=2, config=config)
        
        # Notes with already high velocities
        notes = [
            (0, 240, 60, 120),
            (500, 240, 62, 120),
        ]
        
        result = generator.apply_to_velocities(notes, arc, 1000)
        
        # All velocities should be clamped to valid range
        for tick, dur, pitch, vel in result:
            assert 1 <= vel <= 127


class TestInstrumentSuggestions:
    """Tests for instrument suggestions based on tension."""
    
    def test_suggest_section_instruments(self):
        """Test instrument suggestions."""
        generator = TensionArcGenerator()
        arc = generator.create_arc(ArcShape.LINEAR_BUILD, num_sections=3)
        
        instruments = ["kick", "snare", "hihat", "bass", "synth", "pad"]
        
        # Low tension section
        low_suggestions = generator.suggest_section_instruments(arc, 0, instruments)
        
        # High tension section
        high_suggestions = generator.suggest_section_instruments(arc, 2, instruments)
        
        # High tension should suggest more instruments
        assert len(high_suggestions) >= len(low_suggestions)
    
    def test_suggest_section_instruments_empty(self):
        """Test with empty instrument list."""
        generator = TensionArcGenerator()
        arc = generator.create_arc(ArcShape.FLAT, num_sections=3)
        
        result = generator.suggest_section_instruments(arc, 0, [])
        assert result == []
    
    def test_suggest_section_instruments_invalid_index(self):
        """Test with invalid section index."""
        generator = TensionArcGenerator()
        arc = generator.create_arc(ArcShape.FLAT, num_sections=3)
        
        instruments = ["kick", "snare"]
        
        # Invalid indices should return full list
        result = generator.suggest_section_instruments(arc, -1, instruments)
        assert result == instruments
        
        result = generator.suggest_section_instruments(arc, 10, instruments)
        assert result == instruments


class TestGenreTensionProfiles:
    """Tests for genre-specific tension profiles."""
    
    def test_genre_profiles_exist(self):
        """Test that genre profiles are defined."""
        assert "edm" in GENRE_TENSION_PROFILES
        assert "classical" in GENRE_TENSION_PROFILES
        assert "jazz" in GENRE_TENSION_PROFILES
        assert "pop" in GENRE_TENSION_PROFILES
        assert "hip_hop" in GENRE_TENSION_PROFILES
    
    def test_edm_profile(self):
        """Test EDM profile has expected sections."""
        edm = GENRE_TENSION_PROFILES["edm"]
        assert "breakdown" in edm
        assert "build" in edm
        assert "drop" in edm
        assert edm["drop"] == 1.0  # Maximum tension
    
    def test_classical_profile(self):
        """Test classical profile."""
        classical = GENRE_TENSION_PROFILES["classical"]
        assert "exposition" in classical
        assert "development" in classical
    
    def test_jazz_profile(self):
        """Test jazz profile."""
        jazz = GENRE_TENSION_PROFILES["jazz"]
        assert "head" in jazz
        assert "solo" in jazz
    
    def test_section_tension_map(self):
        """Test base section tension map."""
        assert "intro" in SECTION_TENSION_MAP
        assert "verse" in SECTION_TENSION_MAP
        assert "chorus" in SECTION_TENSION_MAP
        assert "outro" in SECTION_TENSION_MAP
        assert "drop" in SECTION_TENSION_MAP
        
        # Verify relative tensions make sense
        assert SECTION_TENSION_MAP["intro"] < SECTION_TENSION_MAP["chorus"]
        assert SECTION_TENSION_MAP["breakdown"] < SECTION_TENSION_MAP["drop"]


class TestConvenienceFunctions:
    """Tests for convenience functions."""
    
    def test_create_tension_arc_function(self):
        """Test quick tension arc creation."""
        arc = create_tension_arc(shape="peak_middle", num_sections=6)
        
        assert len(arc.points) == 6
        assert arc.shape == ArcShape.PEAK_MIDDLE
    
    def test_create_tension_arc_flat(self):
        """Test creating flat arc via convenience function."""
        arc = create_tension_arc(shape="flat", num_sections=4)
        
        assert len(arc.points) == 4
        assert arc.shape == ArcShape.FLAT
    
    def test_apply_tension_to_arrangement(self):
        """Test applying tension to full arrangement."""
        notes = [
            (0, 240, 60, 80),
            (480, 240, 62, 80),
            (960, 240, 64, 80),
            (1440, 240, 65, 80),
        ]
        
        section_types = ["intro", "verse", "chorus", "outro"]
        section_boundaries = [0, 480, 960, 1440]
        
        result = apply_tension_to_arrangement(
            notes, section_types, section_boundaries, genre="pop"
        )
        
        assert len(result) == 4
        # Verify all velocities are valid
        for tick, dur, pitch, vel in result:
            assert 1 <= vel <= 127
    
    def test_apply_tension_to_arrangement_empty(self):
        """Test with empty notes."""
        result = apply_tension_to_arrangement([], [], [], "pop")
        assert result == []
    
    def test_get_tension_for_section(self):
        """Test getting tension for section type."""
        tension_intro = get_tension_for_section("intro")
        tension_chorus = get_tension_for_section("chorus")
        
        assert tension_intro == SECTION_TENSION_MAP["intro"]
        assert tension_chorus == SECTION_TENSION_MAP["chorus"]
        assert tension_chorus > tension_intro
    
    def test_get_tension_for_section_genre(self):
        """Test getting tension with genre."""
        tension_edm_drop = get_tension_for_section("drop", genre="edm")
        tension_jazz_solo = get_tension_for_section("solo", genre="jazz")
        
        assert tension_edm_drop == GENRE_TENSION_PROFILES["edm"]["drop"]
        assert tension_jazz_solo == GENRE_TENSION_PROFILES["jazz"]["solo"]
    
    def test_get_tension_for_section_unknown(self):
        """Test unknown section type defaults to 0.5."""
        tension = get_tension_for_section("unknown_section", genre="pop")
        assert tension == 0.5


class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_single_section(self):
        """Test with single section."""
        generator = TensionArcGenerator()
        arc = generator.create_arc(ArcShape.LINEAR_BUILD, num_sections=1)
        
        assert len(arc.points) == 1
        assert 0.0 <= arc.points[0].tension <= 1.0
    
    def test_zero_sections(self):
        """Test with zero sections."""
        generator = TensionArcGenerator()
        arc = generator.create_arc(ArcShape.FLAT, num_sections=0)
        
        # Should handle gracefully
        assert len(arc.points) == 0
    
    def test_negative_sections(self):
        """Test with negative sections."""
        generator = TensionArcGenerator()
        arc = generator.create_arc(ArcShape.FLAT, num_sections=-1)
        
        # Should handle gracefully
        assert len(arc.points) >= 0
    
    def test_position_out_of_bounds(self):
        """Test position clamping."""
        arc = TensionArc(points=[
            TensionPoint(0.0, 0.3),
            TensionPoint(1.0, 0.9)
        ])
        
        # Beyond bounds should clamp
        assert arc.get_tension_at(-0.5) == 0.3
        assert arc.get_tension_at(1.5) == 0.9
    
    def test_apply_to_velocities_zero_total_ticks(self):
        """Test with zero total ticks."""
        generator = TensionArcGenerator()
        arc = generator.create_arc(ArcShape.FLAT, num_sections=2)
        
        notes = [(0, 240, 60, 80)]
        result = generator.apply_to_velocities(notes, arc, 0)
        
        # Should return original notes
        assert result == notes
    
    def test_custom_config_ranges(self):
        """Test custom configuration ranges."""
        config = TensionConfig(
            tension_range=(0.1, 0.9),
            dynamics_influence=0.5
        )
        
        generator = TensionArcGenerator()
        arc = generator.create_arc(ArcShape.LINEAR_BUILD, num_sections=5, config=config)
        
        # First point should be near min, last near max
        assert arc.points[0].tension >= 0.1
        assert arc.points[-1].tension <= 0.9


class TestIntegration:
    """Integration tests combining multiple features."""
    
    def test_full_workflow(self):
        """Test complete workflow from arc creation to velocity application."""
        # Create generator
        generator = TensionArcGenerator()
        
        # Create arc
        arc = generator.create_arc(ArcShape.PEAK_MIDDLE, num_sections=8)
        
        # Create some test notes
        notes = [(i * 480, 240, 60 + i % 12, 80) for i in range(16)]
        
        # Apply to velocities
        result = generator.apply_to_velocities(notes, arc, 16 * 480)
        
        assert len(result) == 16
        assert all(1 <= vel <= 127 for _, _, _, vel in result)
    
    def test_section_based_workflow(self):
        """Test workflow using section types."""
        section_types = ["intro", "verse", "pre_chorus", "chorus", "bridge", "chorus", "outro"]
        
        generator = TensionArcGenerator()
        arc = generator.create_arc_for_sections(section_types, genre="pop")
        
        assert len(arc.points) == len(section_types)
        
        # Generate curves
        dynamics = generator.get_dynamics_curve(arc)
        density = generator.get_density_curve(arc)
        complexity = generator.get_complexity_curve(arc)
        
        assert len(dynamics) == 100
        assert len(density) == 100
        assert len(complexity) == 100
    
    def test_genre_comparison(self):
        """Test different genres produce different tension profiles."""
        section_types = ["intro", "verse", "chorus", "outro"]
        
        generator = TensionArcGenerator()
        arc_pop = generator.create_arc_for_sections(section_types, genre="pop")
        arc_edm = generator.create_arc_for_sections(section_types, genre="edm")
        
        # Both should work
        assert len(arc_pop.points) == 4
        assert len(arc_edm.points) == 4
        
        # May have different tensions for same section names if genre overrides exist
        # But at minimum, they should both be valid
        for point in arc_pop.points:
            assert 0.0 <= point.tension <= 1.0
        for point in arc_edm.points:
            assert 0.0 <= point.tension <= 1.0
    
    def test_multiple_arc_shapes_comparison(self):
        """Test different arc shapes produce different patterns."""
        generator = TensionArcGenerator()
        
        arc_flat = generator.create_arc(ArcShape.FLAT, num_sections=5)
        arc_build = generator.create_arc(ArcShape.LINEAR_BUILD, num_sections=5)
        arc_peak = generator.create_arc(ArcShape.PEAK_MIDDLE, num_sections=5)
        
        # Get tension values
        tensions_flat = [p.tension for p in arc_flat.points]
        tensions_build = [p.tension for p in arc_build.points]
        tensions_peak = [p.tension for p in arc_peak.points]
        
        # Flat should be constant
        assert all(t == tensions_flat[0] for t in tensions_flat)
        
        # Build should increase
        assert tensions_build[-1] > tensions_build[0]
        
        # Peak should have variety
        assert len(set(tensions_peak)) > 1
